"""FastAPI 로컬 Worker — 데모 MVP.

정적 프론트엔드(web/)를 같은 서버에서 서빙하고, REST API를 /v1 아래로 노출한다.
docs/api-spec.md 계약을 따르며, 데모 편의를 위한 소수 추가 필드/엔드포인트가 있다.
"""
import json
import os
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

from fastapi import (BackgroundTasks, FastAPI, File, Form, Header, HTTPException,
                     Request, UploadFile)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import config, database, db, pipeline, textbuild
from .models import (ExportIn, MeetingPatch, SegmentPatch, SlackShareIn,
                     SpeakerPatch, SummaryPatch)
from .providers import slack
from .providers.storage import storage

app = FastAPI(title="Meeting Recorder — Local Demo Worker", version="0.1.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
    allow_headers=["*"],
)

P = config.API_PREFIX  # "/v1"


@app.on_event("startup")
def _startup():
    db.init_db()


# --- 인증 (데모: 토큰 미설정 시 통과) ---
def require_user(authorization: Optional[str] = Header(default=None)) -> str:
    if not config.AUTH_ENABLED:
        return config.DEFAULT_USER_ID
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if token != config.LOCAL_API_TOKEN:
        raise HTTPException(status_code=401, detail={"error": {
            "code": "unauthorized", "message": "인증 토큰이 필요합니다."}})
    return config.DEFAULT_USER_ID


def _err(status, code, message, details=None):
    return JSONResponse(status_code=status, content={
        "error": {"code": code, "message": message, "details": details or {}}})


def _as_dt(value) -> datetime:
    """recorded_at 정규화. postgres는 datetime, sqlite는 ISO 문자열로 돌아온다."""
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime.now().astimezone()


def _same_id(a, b) -> bool:
    """ID 비교. postgres(psycopg)는 uuid 컬럼을 UUID 객체로 돌려주므로 문자열로 정규화한다.
    (sqlite 는 TEXT 라 그대로 문자열)"""
    return str(a) == str(b)


def _day_bounds(date_str: str):
    """'YYYY-MM-DD' → (그날 00:00, 다음날 00:00) 로컬 ISO 문자열."""
    d = datetime.fromisoformat(date_str).replace(
        hour=0, minute=0, second=0, microsecond=0)
    tz = datetime.now().astimezone().tzinfo
    start = d.replace(tzinfo=d.tzinfo or tz)
    return start.isoformat(), (start + timedelta(days=1)).isoformat()


def _get_meeting(conn, meeting_id, user_id):
    row = conn.execute(
        "SELECT * FROM meetings WHERE id=? AND deleted_at IS NULL", (meeting_id,)
    ).fetchone()
    if not row or not _same_id(row["user_id"], user_id):
        raise HTTPException(status_code=404, detail={"error": {
            "code": "meeting_not_found", "message": "회의를 찾을 수 없습니다."}})
    return row


# ============================ Jobs ============================
_ALLOWED_EXT = {"m4a", "aac", "webm", "wav", "mp3", "ogg", "mp4"}


@app.post(P + "/jobs", status_code=201)
async def create_job(
    background: BackgroundTasks,
    audio_file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    recorded_at: Optional[str] = Form(None),
    duration_ms: Optional[int] = Form(None),
    source_device: Optional[str] = Form(None),
    language: str = Form("ko"),
    hotwords: Optional[str] = Form(None),
    recording_consent_confirmed: str = Form("false"),
):
    # 데모: 단일 로컬 사용자 (AUTH_ENABLED 시 별도 인증 레이어로 확장)
    user_id = config.DEFAULT_USER_ID

    content = await audio_file.read()
    ext = (os.path.splitext(audio_file.filename or "")[1] or "").lstrip(".").lower()
    if ext and ext not in _ALLOWED_EXT:
        return _err(415, "unsupported_media_type",
                    "지원하지 않는 녹음 파일입니다. m4a, aac, webm, wav 파일을 사용하세요.")
    if len(content) < 256:
        return _err(422, "audio_too_short",
                    "녹음 길이가 너무 짧아 회의록을 만들 수 없습니다.")

    consent = str(recording_consent_confirmed).lower() in ("true", "1", "yes", "on")
    hotwords_list = None
    if hotwords:
        try:
            parsed = json.loads(hotwords)
            if isinstance(parsed, list):
                hotwords_list = [str(x) for x in parsed if str(x).strip()]
        except (ValueError, TypeError):
            hotwords_list = [w.strip() for w in hotwords.split(",") if w.strip()]

    conn = db.connect()
    try:
        now = db.now_iso()
        meeting_id = db.new_id("meeting_")
        job_id = db.new_id("job_")
        rec_id = db.new_id("file_")
        title_final = (title or "").strip() or f"회의 {now[:10]}"

        saved = storage.save_original(user_id, meeting_id, audio_file.filename or "audio.webm", content)

        conn.execute(
            """INSERT INTO meetings
               (id,user_id,title,recorded_at,duration_ms,language,source_device,hotwords,
                status,recording_consent_confirmed,recording_consent_confirmed_at,
                created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (meeting_id, user_id, title_final, recorded_at or now, duration_ms,
             language or "ko", source_device,
             database.enc_array(hotwords_list) if hotwords_list else None,
             "uploaded", database.enc_bool(consent), now if consent else None, now, now),
        )
        conn.execute(
            """INSERT INTO recording_files
               (id,meeting_id,user_id,kind,storage_path,mime_type,size_bytes,duration_ms,checksum_sha256,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (rec_id, meeting_id, user_id, "original", saved["path"],
             audio_file.content_type, saved["size"], duration_ms, saved["checksum"], now),
        )
        conn.execute(
            """INSERT INTO jobs (id,meeting_id,status,progress,created_at,updated_at)
               VALUES (?,?,?,?,?,?)""",
            (job_id, meeting_id, "uploaded", 0.0, now, now),
        )
        conn.commit()
        db.audit(conn, user_id, meeting_id, "meeting_created",
                 {"source_device": source_device, "consent": consent})
    finally:
        conn.close()

    background.add_task(pipeline.run_pipeline, job_id, meeting_id)
    return {"job_id": job_id, "meeting_id": meeting_id, "status": "uploaded",
            "created_at": now}


@app.get(P + "/jobs/{job_id}")
def get_job(job_id: str, user_id: str = None):
    conn = db.connect()
    try:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return _err(404, "job_not_found", "job을 찾을 수 없습니다.")
        return {
            "job_id": row["id"], "meeting_id": row["meeting_id"],
            "status": row["status"], "progress": row["progress"],
            "current_stage": row["current_stage"], "error_code": row["error_code"],
            "error_message": row["error_message"], "updated_at": row["updated_at"],
        }
    finally:
        conn.close()


@app.post(P + "/meetings/{meeting_id}/retry")
def retry_job(meeting_id: str, background: BackgroundTasks, body: dict = None):
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        _get_meeting(conn, meeting_id, user_id)
        job = conn.execute(
            "SELECT * FROM jobs WHERE meeting_id=? ORDER BY created_at DESC LIMIT 1",
            (meeting_id,),
        ).fetchone()
        if not job:
            return _err(404, "job_not_found", "job을 찾을 수 없습니다.")
        # 재처리를 위해 기존 전사/요약 정리 (데모 단순화)
        conn.execute("DELETE FROM transcript_segments WHERE meeting_id=?", (meeting_id,))
        svs = conn.execute("SELECT id FROM summary_versions WHERE meeting_id=?", (meeting_id,)).fetchall()
        for sv in svs:
            conn.execute("DELETE FROM summary_decisions WHERE summary_version_id=?", (sv["id"],))
            conn.execute("DELETE FROM action_items WHERE summary_version_id=?", (sv["id"],))
            conn.execute("DELETE FROM calendar_candidates WHERE summary_version_id=?", (sv["id"],))
        conn.execute("DELETE FROM summary_versions WHERE meeting_id=?", (meeting_id,))
        conn.execute(
            "UPDATE jobs SET status='uploaded', progress=0, current_stage=NULL, "
            "error_code=NULL, error_message=NULL, updated_at=? WHERE id=?",
            (db.now_iso(), job["id"]),
        )
        conn.execute("UPDATE meetings SET status='uploaded', updated_at=? WHERE id=?",
                     (db.now_iso(), meeting_id))
        conn.commit()
        job_id = job["id"]
    finally:
        conn.close()
    background.add_task(pipeline.run_pipeline, job_id, meeting_id)
    return {"job_id": job_id, "meeting_id": meeting_id, "status": "uploaded"}


# ============================ Meetings ============================
@app.get(P + "/meetings")
def list_meetings(status: Optional[str] = None, q: Optional[str] = None,
                  date: Optional[str] = None,
                  limit: int = 20, cursor: Optional[str] = None):
    """회의 목록. `date=YYYY-MM-DD` 를 주면 그 날짜에 녹음한 회의만 반환한다."""
    user_id = config.DEFAULT_USER_ID
    limit = max(1, min(100, limit))
    offset = 0
    if cursor:
        try:
            offset = max(0, int(cursor))
        except ValueError:
            offset = 0
    conn = db.connect()
    try:
        where = ["m.user_id=?", "m.deleted_at IS NULL"]
        params = [user_id]
        if date:
            try:
                d_start, d_end = _day_bounds(date)
            except ValueError:
                return _err(422, "invalid_date", "date 는 YYYY-MM-DD 형식이어야 합니다.")
            where.append("m.recorded_at >= ? AND m.recorded_at < ?")
            params += [d_start, d_end]
        if status:
            where.append("m.status=?")
            params.append(status)
        if q:
            where.append(
                "(m.title LIKE ? OR m.id IN (SELECT meeting_id FROM transcript_segments "
                "WHERE text LIKE ? OR corrected_text LIKE ?))")
            like = f"%{q}%"
            params += [like, like, like]
        sql = (
            "SELECT m.*, "
            "EXISTS(SELECT 1 FROM summary_versions sv WHERE sv.meeting_id=m.id) AS has_summary, "
            "(SELECT COUNT(*) FROM share_logs s WHERE s.meeting_id=m.id AND s.status='sent') AS shared_count "
            "FROM meetings m WHERE " + " AND ".join(where) +
            " ORDER BY m.recorded_at DESC LIMIT ? OFFSET ?")
        rows = conn.execute(sql, params + [limit + 1, offset]).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [{
            "meeting_id": r["id"], "title": r["title"], "recorded_at": r["recorded_at"],
            "duration_ms": r["duration_ms"], "status": r["status"],
            "has_summary": bool(r["has_summary"]), "shared_count": r["shared_count"],
        } for r in rows]
        next_cursor = str(offset + limit) if has_more else None
        return {"items": items, "next_cursor": next_cursor}
    finally:
        conn.close()


# 주의: 이 라우트는 반드시 "/meetings/{meeting_id}" 보다 먼저 등록되어야 한다.
# (그렇지 않으면 "calendar" 가 meeting_id 로 해석된다)
@app.get(P + "/meetings/calendar")
def meetings_calendar(year: Optional[int] = None, month: Optional[int] = None):
    """녹음 달력: 해당 월의 '날짜별 녹음 건수 · 총 길이 · 시간대 목록'.

    각 item 의 start_minute/end_minute(0~1440)은 하루 24시간 타임라인 렌더링용이다.
    """
    user_id = config.DEFAULT_USER_ID
    now = datetime.now().astimezone()
    y = year or now.year
    mo = month or now.month
    if not (1 <= mo <= 12):
        return _err(422, "invalid_month", "month 는 1~12 사이여야 합니다.")

    tz = now.tzinfo
    start = datetime(y, mo, 1, tzinfo=tz)
    end = datetime(y + (1 if mo == 12 else 0), 1 if mo == 12 else mo + 1, 1, tzinfo=tz)

    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT m.*, "
            "EXISTS(SELECT 1 FROM summary_versions sv WHERE sv.meeting_id=m.id) AS has_summary "
            "FROM meetings m WHERE m.user_id=? AND m.deleted_at IS NULL "
            "AND m.recorded_at >= ? AND m.recorded_at < ? "
            "ORDER BY m.recorded_at ASC",
            (user_id, start.isoformat(), end.isoformat()),
        ).fetchall()

        days = {}
        for r in rows:
            dt = _as_dt(r["recorded_at"])
            key = dt.date().isoformat()
            dur = int(r["duration_ms"] or 0)
            day = days.setdefault(key, {
                "date": key, "count": 0, "total_duration_ms": 0, "items": []})
            day["count"] += 1
            day["total_duration_ms"] += dur
            end_dt = dt + timedelta(milliseconds=dur)
            start_min = dt.hour * 60 + dt.minute
            day["items"].append({
                "meeting_id": r["id"], "title": r["title"],
                "recorded_at": dt.isoformat(), "duration_ms": dur,
                "status": r["status"], "has_summary": bool(r["has_summary"]),
                "start_hm": dt.strftime("%H:%M"), "end_hm": end_dt.strftime("%H:%M"),
                "start_minute": start_min,
                "end_minute": min(24 * 60, start_min + max(1, dur // 60000)),
            })
        return {
            "year": y, "month": mo,
            "total_count": sum(d["count"] for d in days.values()),
            "days": [days[k] for k in sorted(days)],
        }
    finally:
        conn.close()


@app.get(P + "/meetings/{meeting_id}")
def get_meeting(meeting_id: str):
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        m = _get_meeting(conn, meeting_id, user_id)
        rec = conn.execute(
            "SELECT * FROM recording_files WHERE meeting_id=? AND kind='original' LIMIT 1",
            (meeting_id,),
        ).fetchone()
        sv = db.latest_summary_version_row(conn, meeting_id)
        audio = None
        if rec:
            audio = {"recording_file_id": rec["id"],
                     "stream_url": f"{P}/recording-files/{rec['id']}/stream"}
        return {
            "meeting_id": m["id"], "title": m["title"], "recorded_at": m["recorded_at"],
            "duration_ms": m["duration_ms"], "status": m["status"], "audio": audio,
            "summary_version_id": sv["id"] if sv else None,
        }
    finally:
        conn.close()


@app.patch(P + "/meetings/{meeting_id}")
def patch_meeting(meeting_id: str, body: MeetingPatch):
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        _get_meeting(conn, meeting_id, user_id)
        conn.execute("UPDATE meetings SET title=?, updated_at=? WHERE id=?",
                     (body.title, db.now_iso(), meeting_id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.delete(P + "/meetings/{meeting_id}")
def delete_meeting(meeting_id: str):
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        _get_meeting(conn, meeting_id, user_id)
        conn.execute("UPDATE meetings SET deleted_at=?, updated_at=? WHERE id=?",
                     (db.now_iso(), db.now_iso(), meeting_id))
        conn.commit()
        db.audit(conn, user_id, meeting_id, "meeting_deleted", {})
        return {"ok": True}
    finally:
        conn.close()


# ============================ Segments ============================
@app.get(P + "/meetings/{meeting_id}/segments")
def get_segments(meeting_id: str):
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        _get_meeting(conn, meeting_id, user_id)
        rows = conn.execute(
            "SELECT * FROM transcript_segments WHERE meeting_id=? ORDER BY segment_index",
            (meeting_id,),
        ).fetchall()
        items = [{
            "segment_id": r["id"], "speaker_label": r["speaker_label"],
            "speaker_name": r["speaker_name"], "start_ms": r["start_ms"],
            "end_ms": r["end_ms"], "text": r["text"],
            "corrected_text": r["corrected_text"], "confidence": r["confidence"],
            "bookmarked": bool(r["bookmarked"]),
        } for r in rows]
        return {"items": items}
    finally:
        conn.close()


@app.patch(P + "/meetings/{meeting_id}/segments/{segment_id}")
def patch_segment(meeting_id: str, segment_id: str, body: SegmentPatch):
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        _get_meeting(conn, meeting_id, user_id)
        seg = conn.execute(
            "SELECT * FROM transcript_segments WHERE id=? AND meeting_id=?",
            (segment_id, meeting_id),
        ).fetchone()
        if not seg:
            return _err(404, "segment_not_found", "세그먼트를 찾을 수 없습니다.")
        sets, params = [], []
        if body.corrected_text is not None:
            sets.append("corrected_text=?")
            params.append(body.corrected_text)
        if body.bookmarked is not None:
            sets.append("bookmarked=?")
            params.append(database.enc_bool(body.bookmarked))
        if sets:
            sets.append("updated_at=?")
            params.append(db.now_iso())
            params += [segment_id, meeting_id]
            conn.execute(
                f"UPDATE transcript_segments SET {', '.join(sets)} WHERE id=? AND meeting_id=?",
                params)
            conn.commit()
        r = conn.execute("SELECT * FROM transcript_segments WHERE id=?", (segment_id,)).fetchone()
        return {
            "segment_id": r["id"], "speaker_label": r["speaker_label"],
            "speaker_name": r["speaker_name"], "start_ms": r["start_ms"],
            "end_ms": r["end_ms"], "text": r["text"],
            "corrected_text": r["corrected_text"], "confidence": r["confidence"],
            "bookmarked": bool(r["bookmarked"]),
        }
    finally:
        conn.close()


@app.patch(P + "/meetings/{meeting_id}/speakers/{speaker_label}")
def patch_speaker(meeting_id: str, speaker_label: str, body: SpeakerPatch):
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        _get_meeting(conn, meeting_id, user_id)
        now = db.now_iso()
        # alias 저장 (정본) + 세그먼트 speaker_name write-through (finding #10)
        conn.execute(
            """INSERT INTO speaker_aliases (id,meeting_id,speaker_label,speaker_name,updated_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(meeting_id,speaker_label)
               DO UPDATE SET speaker_name=excluded.speaker_name, updated_at=excluded.updated_at""",
            (db.new_id("alias_"), meeting_id, speaker_label, body.speaker_name, now),
        )
        conn.execute(
            "UPDATE transcript_segments SET speaker_name=?, updated_at=? "
            "WHERE meeting_id=? AND speaker_label=?",
            (body.speaker_name, now, meeting_id, speaker_label),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ============================ Summary ============================
@app.get(P + "/meetings/{meeting_id}/summary")
def get_summary(meeting_id: str):
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        _get_meeting(conn, meeting_id, user_id)
        sv = db.latest_summary_version_row(conn, meeting_id)
        if not sv:
            return _err(404, "summary_not_found", "아직 요약이 없습니다.")
        return db.load_summary_version(conn, sv)
    finally:
        conn.close()


@app.patch(P + "/meetings/{meeting_id}/summary")
def patch_summary(meeting_id: str, body: SummaryPatch):
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        _get_meeting(conn, meeting_id, user_id)
        result = {
            "title": body.title, "summary": body.summary,
            "decisions": [d.model_dump() for d in body.decisions],
            "action_items": [a.model_dump() for a in body.action_items],
            "calendar_candidates": [c.model_dump() for c in body.calendar_candidates],
        }
        sv_id, version = db.store_summary_version(
            conn, meeting_id, result, source="user", created_by=user_id)
        db.audit(conn, user_id, meeting_id, "summary_edited", {"version": version})
        return {"summary_version_id": sv_id, "version": version, "source": "user"}
    finally:
        conn.close()


# ============================ Exports ============================
def _load_summary_for(conn, meeting_id, summary_version_id=None):
    if summary_version_id:
        sv = conn.execute("SELECT * FROM summary_versions WHERE id=? AND meeting_id=?",
                          (summary_version_id, meeting_id)).fetchone()
    else:
        sv = db.latest_summary_version_row(conn, meeting_id)
    return db.load_summary_version(conn, sv) if sv else None


def _segments_for(conn, meeting_id):
    rows = conn.execute(
        "SELECT * FROM transcript_segments WHERE meeting_id=? ORDER BY segment_index",
        (meeting_id,)).fetchall()
    return [dict(r) for r in rows]


@app.post(P + "/meetings/{meeting_id}/exports", status_code=201)
def create_export(meeting_id: str, body: ExportIn):
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        m = _get_meeting(conn, meeting_id, user_id)
        fmt = (body.format or "md").lower()
        if fmt not in ("md", "txt"):
            return _err(422, "unsupported_format", "MVP는 md, txt 내보내기만 지원합니다.")
        summary = _load_summary_for(conn, meeting_id, body.summary_version_id)
        segments = _segments_for(conn, meeting_id)
        meeting_dict = dict(m)
        if fmt == "md":
            content = textbuild.build_markdown(meeting_dict, summary, segments, body.include_transcript)
        else:
            content = textbuild.build_txt(meeting_dict, summary, segments, body.include_transcript)

        export_id = db.new_id("export_")
        saved = storage.save_export(user_id, meeting_id, export_id, fmt, content)
        conn.execute(
            """INSERT INTO exports (id,meeting_id,summary_version_id,format,include_transcript,
               storage_path,status,created_at) VALUES (?,?,?,?,?,?,?,?)""",
            (export_id, meeting_id, body.summary_version_id, fmt,
             database.enc_bool(body.include_transcript), saved["path"], "ready", db.now_iso()),
        )
        conn.commit()
        db.audit(conn, user_id, meeting_id, "export_created", {"format": fmt})
        return {"export_id": export_id, "format": fmt, "status": "ready",
                "download_url": f"{P}/exports/{export_id}/download"}
    finally:
        conn.close()


@app.get(P + "/exports/{export_id}/download")
def download_export(export_id: str):
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        row = conn.execute("SELECT e.*, m.user_id AS owner, m.title AS mtitle "
                           "FROM exports e JOIN meetings m ON m.id=e.meeting_id "
                           "WHERE e.id=?", (export_id,)).fetchone()
        if not row or not _same_id(row["owner"], user_id) or not row["storage_path"]:
            return _err(404, "export_not_found", "내보내기 파일을 찾을 수 없습니다.")
        media = "text/markdown" if row["format"] == "md" else "text/plain"
        filename = f"{row['mtitle']}.{row['format']}"
        data = storage.read_all(row["storage_path"])
        if data is None:
            return _err(404, "export_not_found", "내보내기 파일을 찾을 수 없습니다.")
        # 저장 위치(local/supabase) 무관하게 Provider 로 읽어 동일하게 첨부 응답한다.
        quoted = urllib.parse.quote(filename)
        return Response(
            content=data, media_type=f"{media}; charset=utf-8",
            headers={"Content-Disposition":
                     f"attachment; filename*=UTF-8''{quoted}"})
    finally:
        conn.close()


# ============================ Slack Share ============================
@app.post(P + "/meetings/{meeting_id}/share/slack")
def share_slack(meeting_id: str, body: SlackShareIn):
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        m = _get_meeting(conn, meeting_id, user_id)
        summary = _load_summary_for(conn, meeting_id, body.summary_version_id)
        text = body.message_override or textbuild.build_slack_text(dict(m), summary)
        result = slack.send_summary(text)

        sv = (conn.execute("SELECT * FROM summary_versions WHERE id=?",
                          (body.summary_version_id,)).fetchone()
              if body.summary_version_id else db.latest_summary_version_row(conn, meeting_id))
        share_id = db.new_id("share_")
        now = db.now_iso()
        conn.execute(
            """INSERT INTO share_logs (id,meeting_id,summary_version_id,provider,target_label,
               status,request_payload,response_status,response_body,sent_at,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (share_id, meeting_id, sv["id"] if sv else None, "slack_webhook",
             body.channel_label, result["status"],
             database.enc_json({"text": text}),
             result.get("http_status"), (result.get("body") or "")[:500],
             now if result["status"] == "sent" else None, now),
        )
        conn.commit()
        db.audit(conn, user_id, meeting_id, "shared_slack", {"status": result["status"]})
        return {
            "share_log_id": share_id, "provider": "slack_webhook",
            "status": result["status"],
            "sent_at": now if result["status"] == "sent" else None,
            "detail": ("데모 시뮬레이션 전송(Webhook 미설정)" if result.get("simulated")
                       else result.get("body", "")[:200]),
        }
    finally:
        conn.close()


# ============================ Audio stream (Range) ============================
@app.get(P + "/recording-files/{recording_file_id}/stream")
def stream_file(recording_file_id: str, request: Request):
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        row = conn.execute("SELECT r.*, m.user_id AS owner FROM recording_files r "
                           "JOIN meetings m ON m.id=r.meeting_id WHERE r.id=?",
                           (recording_file_id,)).fetchone()
        if not row or not _same_id(row["owner"], user_id):
            return _err(404, "file_not_found", "음성 파일을 찾을 수 없습니다.")
        path = row["storage_path"]
        mime = row["mime_type"] or "application/octet-stream"
    finally:
        conn.close()

    # 저장 위치(local/supabase)와 무관하게 Provider 를 통해 읽는다.
    # Supabase Storage 는 비공개 버킷이므로 서버가 Range 요청을 대신 수행해
    # 클라이언트에는 동일한 206 응답 계약을 유지한다.
    file_size = storage.size(path)
    if file_size is None:
        return _err(404, "file_not_found", "음성 파일이 존재하지 않습니다.")

    range_header = request.headers.get("range")

    if range_header and range_header.startswith("bytes="):
        try:
            start_s, end_s = range_header[6:].split("-", 1)
            start = int(start_s) if start_s else 0
            end = int(end_s) if end_s else file_size - 1
        except ValueError:
            start, end = 0, file_size - 1
        start = max(0, start)
        end = min(end, file_size - 1)
        if start > end:
            start = 0
        data = storage.read_range(path, start, end)
        if data is None:
            return _err(404, "file_not_found", "음성 파일이 존재하지 않습니다.")
        return Response(content=data, status_code=206, media_type=mime, headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(len(data)),
        })

    data = storage.read_all(path)
    if data is None:
        return _err(404, "file_not_found", "음성 파일이 존재하지 않습니다.")
    return Response(content=data, status_code=200, media_type=mime, headers={
        "Accept-Ranges": "bytes", "Content-Length": str(len(data))})


# ============================ Health & static ============================
@app.get(P + "/health")
def health():
    from .providers import diarization
    return {"ok": True, "asr_provider": config.ASR_PROVIDER,
            "whisper_model": config.WHISPER_MODEL,
            "summary_provider": config.SUMMARY_PROVIDER,
            "ollama_model": config.OLLAMA_MODEL,
            "diarizer": diarization._resolve_mode(),
            "supabase_configured": config.SUPABASE_CONFIGURED,
            "supabase_url": config.SUPABASE_URL or None,
            "db_backend": config.DB_BACKEND,  # sqlite(기본) | postgres(Supabase)
            "storage_provider": storage.name,  # local(기본) | supabase
            "auth_enabled": config.AUTH_ENABLED}


config.WEB_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(config.WEB_DIR), html=True, check_dir=False),
          name="web")
