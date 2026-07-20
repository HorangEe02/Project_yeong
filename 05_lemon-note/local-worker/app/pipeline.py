"""백그라운드 처리 파이프라인.

uploaded -> normalizing_audio -> transcribing -> summarizing -> ready_for_review
각 단계에서 jobs.status 와 meetings.status 를 함께 갱신한다
(문서 검토 finding #5 대응: status write-through 로 이중 소스 불일치 방지).
"""
import time
import traceback

from . import config, database, db
from .providers import get_summary_provider, get_transcription_provider


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
        conn.commit()
        db.audit(conn, meeting["user_id"], meeting_id, "transcription_completed",
                 {"segments": len(seg_rows)})
        time.sleep(config.STUB_STAGE_DELAY)

        # 3) 요약
        _set_status(conn, job_id, meeting_id, "summarizing", 0.8, "summarize")
        sp = get_summary_provider()
        result = sp.summarize(
            seg_rows, language=meeting["language"],
            context={"recorded_at": meeting["recorded_at"], "title": meeting["title"]},
        )
        db.store_summary_version(conn, meeting_id, result, source="ai",
                                 created_by=meeting["user_id"])
        db.audit(conn, meeting["user_id"], meeting_id, "summary_created", {"source": "ai"})
        time.sleep(config.STUB_STAGE_DELAY)

        # 4) 검토 대기
        _set_status(conn, job_id, meeting_id, "ready_for_review", 1.0, None)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        try:
            _set_status(conn, job_id, meeting_id, "failed", 0.0, None,
                        error_code="pipeline_error", error_message=str(e)[:500])
        except Exception:  # noqa: BLE001
            pass
    finally:
        conn.close()
