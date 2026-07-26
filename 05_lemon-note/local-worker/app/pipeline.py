"""백그라운드 처리 파이프라인.

uploaded -> normalizing_audio -> transcribing -> summarizing -> ready_for_review
각 단계에서 jobs.status 와 meetings.status 를 함께 갱신한다
(문서 검토 finding #5 대응: status write-through 로 이중 소스 불일치 방지).
"""
import time
import traceback

from . import config, database, db
from .providers import get_summary_provider, get_transcription_provider


def _user_interests(conn, user_id) -> list:
    """마이페이지에 저장한 관심 분야를 요약 힌트로 넘기기 위해 읽는다.

    설정을 못 읽어도 요약은 계속돼야 하므로(노트 하나가 실패하면 안 된다) 모든 실패를
    빈 목록으로 흘린다. profiles.settings 컬럼이 없는 DB 도 여기에 해당한다.
    """
    try:
        row = conn.execute("SELECT * FROM profiles WHERE id=?", (user_id,)).fetchone()
        if row is None or "settings" not in row.keys():
            return []
        raw = database.dec_json(row["settings"]) or {}
        if not isinstance(raw, dict):
            return []
        return [t for t in (raw.get("interests") or []) if isinstance(t, str) and t.strip()]
    except Exception:  # noqa: BLE001 - 설정 조회 실패가 요약을 막지 않는다
        return []


def _set_status(conn, job_id, meeting_id, status, progress, stage,
                error_code=None, error_message=None):
    now = db.now_iso()
    conn.execute(
        "UPDATE jobs SET status=?, progress=?, current_stage=?, error_code=?, "
        "error_message=?, updated_at=? WHERE id=?",
        (status, progress, stage, error_code, error_message, now, job_id),
    )
    conn.execute(
        "UPDATE meetings SET status=?, updated_at=? WHERE id=?",
        (status, now, meeting_id),
    )
    conn.commit()


def run_pipeline(job_id: str, meeting_id: str) -> None:
    conn = db.connect()
    # except 절에서 참조하므로 try 밖에서 초기화한다. 아래 SELECT 전에 실패하면
    # unbound 라 except 안에서 UnboundLocalError 가 나고, 그게 자기 except 에 삼켜져
    # 실패 알림이 조용히 사라진다(실패가 실패를 숨기는 형태).
    meeting = None
    try:
        conn.execute(
            "UPDATE jobs SET attempts=attempts+1, updated_at=? WHERE id=?",
            (db.now_iso(), job_id),
        )
        conn.commit()

        meeting = conn.execute(
            "SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
        rec = conn.execute(
            "SELECT * FROM recording_files WHERE meeting_id=? AND kind='original'",
            (meeting_id,),
        ).fetchone()

        duration_ms = (meeting["duration_ms"]
                       or (rec["duration_ms"] if rec else None) or 180_000)
        hotwords = database.dec_array(meeting["hotwords"]) or None
        audio_path = rec["storage_path"] if rec else None

        # 1) 오디오 정규화 (stub: 원본을 그대로 사용, ffmpeg 불필요)
        _set_status(conn, job_id, meeting_id, "normalizing_audio", 0.15, "normalize_audio")
        time.sleep(config.STUB_STAGE_DELAY)

        # 2) 전사
        _set_status(conn, job_id, meeting_id, "transcribing", 0.45, "transcribe")
        tp = get_transcription_provider()
        segments = tp.transcribe(
            audio_path, language=meeting["language"],
            hotwords=hotwords, duration_ms=duration_ms,
        )
        seg_rows = []
        now = db.now_iso()
        for i, s in enumerate(segments):
            seg_id = db.new_id("seg_")
            conn.execute(
                """INSERT INTO transcript_segments
                   (id,meeting_id,segment_index,speaker_label,speaker_name,start_ms,
                    end_ms,text,corrected_text,confidence,bookmarked,source,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (seg_id, meeting_id, i, s["speaker_label"], None, s["start_ms"],
                 s["end_ms"], s["text"], None, s.get("confidence"),
                 database.enc_bool(False), "asr", now, now),
            )
            row = dict(s)
            row["id"] = seg_id
            row["segment_index"] = i
            seg_rows.append(row)
        # 녹음 중 찍은 북마크를 전사 세그먼트에 매핑한다.
        # 북마크는 '중요한 말이 나온 직후' 누르는 경우가 많아, 그 시각을 포함하는
        # 세그먼트가 없으면 바로 앞 세그먼트를 표시한다.
        marked = 0
        for bm in conn.execute(
                "SELECT at_ms FROM meeting_bookmarks WHERE meeting_id=? ORDER BY at_ms",
                (meeting_id,)).fetchall():
            at = bm["at_ms"]
            hit = next((r for r in seg_rows if r["start_ms"] <= at <= r["end_ms"]), None)
            if hit is None:
                prev = [r for r in seg_rows if r["start_ms"] <= at]
                hit = prev[-1] if prev else (seg_rows[0] if seg_rows else None)
            if hit is not None:
                conn.execute("UPDATE transcript_segments SET bookmarked=? WHERE id=?",
                             (database.enc_bool(True), hit["id"]))
                marked += 1
        conn.commit()
        db.audit(conn, meeting["user_id"], meeting_id, "transcription_completed",
                 {"segments": len(seg_rows), "bookmarks_mapped": marked})
        time.sleep(config.STUB_STAGE_DELAY)

        # 3) 요약
        _set_status(conn, job_id, meeting_id, "summarizing", 0.8, "summarize")
        sp = get_summary_provider()
        result = sp.summarize(
            seg_rows, language=meeting["language"],
            context={"recorded_at": meeting["recorded_at"], "title": meeting["title"],
                     "interests": _user_interests(conn, meeting["user_id"])},
        )
        db.store_summary_version(conn, meeting_id, result, source="ai",
                                 created_by=meeting["user_id"])
        db.audit(conn, meeting["user_id"], meeting_id, "summary_created", {"source": "ai"})
        time.sleep(config.STUB_STAGE_DELAY)

        # 4) 검토 대기
        _set_status(conn, job_id, meeting_id, "ready_for_review", 1.0, None)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        # 실패 기록 전에 반드시 롤백한다. DB 오류로 여기 들어왔다면 Postgres 트랜잭션이
        # aborted 상태라, 롤백 없이는 아래 _set_status·db.audit 가 둘 다
        # InFailedSqlTransaction 으로 죽고 그게 자기 except 에 삼켜진다
        # → 상태가 중간값에 영구 고착하고 실패 알림도 안 생긴다(실패가 실패를 숨김).
        # SQLite 에서는 재현되지 않아 로컬 검증으로 잡히지 않았던 결함이다.
        # 덤으로 커밋 안 된 부분 전사(세그먼트 일부)도 함께 버려진다.
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001 - 롤백 실패가 아래 기록 시도를 막지 않는다
            pass
        try:
            _set_status(conn, job_id, meeting_id, "failed", 0.0, None,
                        error_code="pipeline_error", error_message=str(e)[:500])
        except Exception:  # noqa: BLE001
            pass
        try:
            # 알림용 이벤트. user_id 를 NULL 로 두면 인박스가 user_id 로 걸러서
            # 영원히 안 보이므로 기본 사용자로 폴백한다. 오류 원문은 넣지 않는다.
            db.audit(conn, meeting["user_id"] if meeting else config.DEFAULT_USER_ID,
                     meeting_id, "pipeline_failed", {"stage": "pipeline"})
        except Exception:  # noqa: BLE001 - 알림 기록 실패가 파이프라인 정리를 막지 않는다
            pass
    finally:
        conn.close()
