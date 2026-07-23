"""FastAPI 로컬 Worker — 데모 MVP.

정적 프론트엔드(web/)를 같은 서버에서 서빙하고, REST API를 /v1 아래로 노출한다.
docs/api-spec.md 계약을 따르며, 데모 편의를 위한 소수 추가 필드/엔드포인트가 있다.
"""
import json
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import (BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException,
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
    CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    """기본 보안 헤더. 업로드된 파일을 브라우저가 HTML 로 해석하는 것을 막는 nosniff 가 핵심."""
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=(self)")
    return resp

P = config.API_PREFIX  # "/v1"


@app.on_event("startup")
def _startup():
    db.init_db()


# --- 인증 (데모: 토큰 미설정 시 통과) ---
def require_write(authorization: Optional[str] = Header(default=None)) -> str:
    """수정·삭제 라우트 게이트.

    이 앱은 공개 데모라 읽기와 업로드는 열어 두지만, 파괴적 작업까지 열면
    인터넷의 누구나 남의 회의록을 지우거나 고칠 수 있다.
    토큰이 설정돼 있으면 그 토큰을, 없고 WRITE_PROTECTED 면 차단한다.
    """
    if config.AUTH_ENABLED:
        return require_user(authorization)
    if config.WRITE_PROTECTED:
        raise HTTPException(status_code=401, detail={"error": {
            "code": "write_disabled",
            "message": "공개 데모에서는 수정·삭제가 비활성화돼 있습니다."}})
    return config.DEFAULT_USER_ID


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
    """저장된 시각 → 프로세스 로컬 타임존의 datetime.

    postgres 는 datetime, sqlite 는 ISO 문자열로 돌아온다. postgres 는 timestamptz 를
    세션 타임존으로 렌더링하는데, Supabase 풀러(6543)는 transaction 모드라 세션 설정이
    유지되지 않는다(UTC 로 돌아옴). 그래서 표시 직전에 파이썬에서 로컬로 변환한다.
    """
    if not isinstance(value, datetime):
        try:
            value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return datetime.now().astimezone()
    return value.astimezone() if value.tzinfo else value


def _enqueue(background, job_id, meeting_id):
    """파이프라인 실행. 서버리스는 응답 후 백그라운드 실행이 보장되지 않아 동기로 돌린다."""
    if config.SYNC_PIPELINE:
        pipeline.run_pipeline(job_id, meeting_id)
    else:
        background.add_task(pipeline.run_pipeline, job_id, meeting_id)


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

# 클라이언트가 보낸 Content-Type 을 그대로 저장하면 text/html 로 올려서
# 다운로드 라우트가 그대로 되돌려줄 때 앱 오리진에서 스크립트가 실행된다(저장형 XSS).
# 확장자에서 서버가 직접 정한다.
_EXT_MIME = {"m4a": "audio/mp4", "mp4": "audio/mp4", "aac": "audio/aac",
             "webm": "audio/webm", "wav": "audio/wav", "mp3": "audio/mpeg",
             "ogg": "audio/ogg"}


def _safe_mime(ext: str) -> str:
    return _EXT_MIME.get((ext or "").lower(), "application/octet-stream")


@app.post(P + "/jobs", status_code=201)
async def create_job(
    background: BackgroundTasks,
    audio_file: Optional[UploadFile] = File(None),
    # 브라우저가 Supabase Storage 로 직접 올린 뒤 경로만 넘기는 경로(대용량용).
    storage_path: Optional[str] = Form(None),
    meeting_id_in: Optional[str] = Form(None, alias="meeting_id"),
    title: Optional[str] = Form(None),
    recorded_at: Optional[str] = Form(None),
    duration_ms: Optional[int] = Form(None),
    source_device: Optional[str] = Form(None),
    language: str = Form("ko"),
    hotwords: Optional[str] = Form(None),
    recording_consent_confirmed: str = Form("false"),
    # 녹음 중 찍은 북마크(밀리초 배열 JSON). 웹 레코더가 보낸다.
    bookmarks: Optional[str] = Form(None),
):
    # 데모: 단일 로컬 사용자 (AUTH_ENABLED 시 별도 인증 레이어로 확장)
    user_id = config.DEFAULT_USER_ID

    limited = _rate_limited()
    if limited:
        return limited

    direct = bool(storage_path and meeting_id_in)
    if direct:
        # 클라이언트가 보고한 크기·체크섬을 믿지 않고 서버가 객체를 확인한다.
        meta = storage.stat_uploaded(storage_path)
        if not meta:
            return _err(404, "upload_not_found",
                        "업로드된 파일을 찾을 수 없습니다. 다시 시도해 주세요.")
        ext = (os.path.splitext(storage_path)[1] or "").lstrip(".").lower()
        if ext not in _ALLOWED_EXT:
            return _err(415, "unsupported_media_type",
                        "지원하지 않는 녹음 파일입니다. m4a, aac, webm, wav 파일을 사용하세요.")
        if meta["size"] < 256:
            return _err(422, "audio_too_short",
                        "녹음 길이가 너무 짧아 회의록을 만들 수 없습니다.")
        content = None
    else:
        if audio_file is None:
            return _err(422, "audio_required", "녹음 파일이 필요합니다.")
        content = await audio_file.read()
    if content is not None and len(content) > config.MAX_UPLOAD_BYTES:
        return _err(413, "audio_too_large",
                    f"녹음 파일이 너무 큽니다. {config.MAX_UPLOAD_BYTES // (1024 * 1024)}MB 이하로 업로드하세요.")
    if not direct:
        ext = (os.path.splitext(audio_file.filename or "")[1] or "").lstrip(".").lower()
    # 확장자가 비면 통과시키던 구멍 — 이제 확장자를 반드시 요구한다.
    if ext not in _ALLOWED_EXT:
        return _err(415, "unsupported_media_type",
                    "지원하지 않는 녹음 파일입니다. m4a, aac, webm, wav 파일을 사용하세요.")
    if content is not None and len(content) < 256:
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
        meeting_id = meeting_id_in if direct else db.new_id("meeting_")
        job_id = db.new_id("job_")
        rec_id = db.new_id("file_")
        title_final = (title or "").strip() or f"회의 {now[:10]}"

        saved = (meta if direct
                 else storage.save_original(user_id, meeting_id,
                                            audio_file.filename or "audio.webm", content))

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
             _safe_mime(ext), saved["size"], duration_ms, saved["checksum"], now),
        )
        conn.execute(
            """INSERT INTO jobs (id,meeting_id,status,progress,created_at,updated_at)
               VALUES (?,?,?,?,?,?)""",
            (job_id, meeting_id, "uploaded", 0.0, now, now),
        )
        for at_ms in _parse_bookmarks(bookmarks):
            conn.execute(
                "INSERT INTO meeting_bookmarks (id,meeting_id,at_ms,label,created_at) VALUES (?,?,?,?,?)",
                (db.new_id("bm_"), meeting_id, at_ms, None, now),
            )
        conn.commit()
        db.audit(conn, user_id, meeting_id, "meeting_created",
                 {"source_device": source_device, "consent": consent})
    finally:
        conn.close()

    _enqueue(background, job_id, meeting_id)
    return {"job_id": job_id, "meeting_id": meeting_id, "status": "uploaded",
            "created_at": now}



def _rate_limited():
    """시간당 업로드 상한. 직접 업로드 경로(presign)와 기존 multipart 가 함께 쓴다."""
    if config.MAX_JOBS_PER_HOUR <= 0:
        return None
    conn = db.connect()
    try:
        row = conn.execute("SELECT COUNT(*) AS n FROM jobs WHERE created_at > ?",
                           (datetime.now(timezone.utc) - timedelta(hours=1),)).fetchone()
        n = row["n"] if row is not None else 0
    finally:
        conn.close()
    if n >= config.MAX_JOBS_PER_HOUR:
        return _err(429, "rate_limited",
                    "지금은 업로드가 몰려 처리할 수 없습니다. 잠시 후 다시 시도해 주세요.")
    return None


@app.post(P + "/uploads/presign", status_code=201)
def presign_upload(body: dict):
    """브라우저가 Storage 로 직접 올릴 1회용 URL 을 발급한다.

    Vercel 서버리스는 요청 본문이 4.5MB 로 제한돼, 파일이 API 를 통과하는 구조로는
    2분 남짓 녹음도 못 올린다. 파일은 브라우저 → Storage 로 직행하고 서버는
    경로만 받는다. 로컬 저장소에서는 빈 응답을 주어 호출측이 기존 multipart 로 돌아간다.
    """
    limited = _rate_limited()
    if limited:
        return limited
    filename = str((body or {}).get("filename") or "")
    ext = (os.path.splitext(filename)[1] or "").lstrip(".").lower()
    if ext not in _ALLOWED_EXT:
        return _err(415, "unsupported_media_type",
                    "지원하지 않는 녹음 파일입니다. m4a, aac, webm, wav 파일을 사용하세요.")
    meeting_id = db.new_id("meeting_")
    signed = storage.create_signed_upload(config.DEFAULT_USER_ID, meeting_id, ext)
    if not signed:
        return {"supported": False}
    return {"supported": True, "meeting_id": meeting_id,
            "upload_url": signed["upload_url"], "storage_path": signed["path"],
            "max_bytes": config.MAX_UPLOAD_BYTES}

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
    _enqueue(background, job_id, meeting_id)
    return {"job_id": job_id, "meeting_id": meeting_id, "status": "uploaded"}


# ============================ Meetings ============================

def _snippet(text: str, q: str, width: int = 46) -> str:
    """매치 지점 주변만 잘라낸다. 앞뒤가 잘리면 … 을 붙인다."""
    if not text:
        return ""
    i = text.lower().find(q.lower())
    if i < 0:
        return text[:width * 2].strip()
    start = max(0, i - width // 2)
    end = min(len(text), i + len(q) + width)
    out = text[start:end].strip()
    return ("…" if start > 0 else "") + out + ("…" if end < len(text) else "")


def _search_matches(conn, meeting_id: str, q: str, title: str, limit: int = 3) -> list:
    """검색어가 어디에 걸렸는지(제목/전사/요약/구간) 스니펫과 함께 돌려준다.

    클로바 노트가 '음성기록 결과 / 메모 결과' 라벨을 보여주는 것과 같은 목적 —
    왜 이 회의가 결과에 떴는지 사용자가 바로 알 수 있어야 한다.
    """
    like = f"%{q}%"
    out = []
    if title and q.lower() in title.lower():
        out.append({"source": "title", "label": "제목", "text": _snippet(title, q), "start_ms": None})
    for r in conn.execute(
            "SELECT start_ms, text, corrected_text FROM transcript_segments "
            "WHERE meeting_id=? AND (text LIKE ? OR corrected_text LIKE ?) "
            "ORDER BY start_ms LIMIT ?", (meeting_id, like, like, limit)).fetchall():
        body = r["corrected_text"] or r["text"] or ""
        out.append({"source": "transcript", "label": "전사",
                    "text": _snippet(body, q), "start_ms": r["start_ms"]})
    sv = conn.execute(
        "SELECT id, summary FROM summary_versions WHERE meeting_id=? "
        "ORDER BY version DESC LIMIT 1", (meeting_id,)).fetchone()
    if sv:
        if sv["summary"] and q.lower() in sv["summary"].lower():
            out.append({"source": "summary", "label": "요약",
                        "text": _snippet(sv["summary"], q), "start_ms": None})
        for r in conn.execute(
                "SELECT start_ms, heading, text FROM summary_sections "
                "WHERE summary_version_id=? AND (text LIKE ? OR heading LIKE ?) "
                "ORDER BY section_index LIMIT ?", (sv["id"], like, like, limit)).fetchall():
            body = r["text"] or r["heading"] or ""
            out.append({"source": "section", "label": "구간 요약",
                        "text": _snippet(body, q), "start_ms": r["start_ms"]})
    return out[:5]

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
            # 제목 · 전사 · 요약 본문 · 구간 요약을 모두 훑는다.
            # 한국어는 교착어라 형태소 분석 없이는 부분 일치가 사실상 유일한 선택이고,
            # postgres 에는 pg_trgm GIN 인덱스가 있어 이 LIKE 가 인덱스를 탄다.
            where.append(
                "(m.title LIKE ?"
                " OR m.id IN (SELECT meeting_id FROM transcript_segments"
                "             WHERE text LIKE ? OR corrected_text LIKE ?)"
                " OR m.id IN (SELECT meeting_id FROM summary_versions"
                "             WHERE title LIKE ? OR summary LIKE ?)"
                " OR m.id IN (SELECT sv.meeting_id FROM summary_sections ss"
                "             JOIN summary_versions sv ON sv.id = ss.summary_version_id"
                "             WHERE ss.text LIKE ? OR ss.heading LIKE ?))")
            like = f"%{q}%"
            params += [like] * 7
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
        if q:
            for it in items:
                it["matches"] = _search_matches(conn, it["meeting_id"], q, it["title"])
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
def patch_meeting(meeting_id: str, body: MeetingPatch,
                  _: str = Depends(require_write)):
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
def delete_meeting(meeting_id: str, _: str = Depends(require_write)):
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

def _parse_bookmarks(raw) -> list:
    """녹음 중 북마크(밀리초 배열)를 정규화. 잘못된 값은 조용히 버린다."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for v in data:
        try:
            ms = int(v)
        except (ValueError, TypeError):
            continue
        if 0 <= ms <= 24 * 60 * 60 * 1000:
            out.append(ms)
    return sorted(set(out))[:200]


@app.get(P + "/meetings/{meeting_id}/bookmarks")
def list_bookmarks(meeting_id: str):
    conn = db.connect()
    try:
        m = _get_meeting(conn, meeting_id, config.DEFAULT_USER_ID)
        if m is None:
            return _err(404, "meeting_not_found", "회의를 찾을 수 없습니다.")
        rows = conn.execute(
            "SELECT id, at_ms, label FROM meeting_bookmarks WHERE meeting_id=? ORDER BY at_ms",
            (meeting_id,)).fetchall()
        return {"items": [{"id": r["id"], "at_ms": r["at_ms"], "label": r["label"]} for r in rows]}
    finally:
        conn.close()


@app.post(P + "/meetings/{meeting_id}/bookmarks", status_code=201)
def add_bookmark(meeting_id: str, body: dict, _: str = Depends(require_write)):
    conn = db.connect()
    try:
        m = _get_meeting(conn, meeting_id, config.DEFAULT_USER_ID)
        if m is None:
            return _err(404, "meeting_not_found", "회의를 찾을 수 없습니다.")
        try:
            at_ms = int((body or {}).get("at_ms"))
        except (ValueError, TypeError):
            return _err(422, "invalid_at_ms", "북마크 시각이 올바르지 않습니다.")
        bm_id = db.new_id("bm_")
        conn.execute(
            "INSERT INTO meeting_bookmarks (id,meeting_id,at_ms,label,created_at) VALUES (?,?,?,?,?)",
            (bm_id, meeting_id, at_ms, (body or {}).get("label"), db.now_iso()))
        conn.commit()
        return {"id": bm_id, "at_ms": at_ms, "label": (body or {}).get("label")}
    finally:
        conn.close()


@app.delete(P + "/meetings/{meeting_id}/bookmarks/{bookmark_id}")
def delete_bookmark(meeting_id: str, bookmark_id: str, _: str = Depends(require_write)):
    conn = db.connect()
    try:
        conn.execute("DELETE FROM meeting_bookmarks WHERE id=? AND meeting_id=?",
                     (bookmark_id, meeting_id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

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
def patch_segment(meeting_id: str, segment_id: str, body: SegmentPatch,
                  _: str = Depends(require_write)):
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
def patch_speaker(meeting_id: str, speaker_label: str, body: SpeakerPatch,
                  _: str = Depends(require_write)):
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
def patch_summary(meeting_id: str, body: SummaryPatch,
                  _: str = Depends(require_write)):
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
def share_slack(meeting_id: str, body: SlackShareIn,
               _: str = Depends(require_write)):
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
        # 회의를 지워도 파일 접근이 살아 있으면 삭제가 접근 회수로 이어지지 않는다.
        row = conn.execute("SELECT r.*, m.user_id AS owner FROM recording_files r "
                           "JOIN meetings m ON m.id=r.meeting_id "
                           "WHERE r.id=? AND m.deleted_at IS NULL",
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
    if not config.HEALTH_DETAIL:
        # 구성 정보는 운영자만 볼 수 있게 한다(HEALTH_DETAIL=1). 기본은 생존 여부만.
        return {"ok": True}
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
