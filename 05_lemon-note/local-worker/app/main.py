"""FastAPI 로컬 Worker — 데모 MVP.

정적 프론트엔드(web/)를 같은 서버에서 서빙하고, REST API를 /v1 아래로 노출한다.
docs/api-spec.md 계약을 따르며, 데모 편의를 위한 소수 추가 필드/엔드포인트가 있다.
"""
import hashlib
import hmac
import json
import os
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import (BackgroundTasks, Body, Depends, FastAPI, File, Form, Header, HTTPException,
                     Request, UploadFile)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import config, database, db, pipeline, textbuild
from .models import (ExportIn, FolderCreate, FolderMoveIn, FolderPatch,
                     MeetingPatch, SegmentPatch, SlackShareIn,
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
    """회의 자체를 바꾸는 라우트 게이트(제목·전사·요약 수정, 회의 삭제, 외부 전송).

    북마크·하이라이트·공유 링크는 여기 걸지 않는다. 본인이 올린 내용에 대한
    '추가 주석'이지 남의 데이터를 파괴하는 조작이 아니고, 공개 데모에서 막으면
    기능 자체를 쓸 수 없게 된다. 그쪽은 require_user 로 — 토큰이 설정되면
    똑같이 인증을 요구하고, 데모에서는 열린다.
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
    # 업로드는 WRITE_PROTECTED 의 의도된 예외다(config.py: "읽기·업로드만 열리고
    # 수정·삭제는 401"). require_write 를 달면 공개 데모에서 회의 생성 자체가 401 이
    # 되어 앱의 존재 이유가 사라진다. 대신 require_user 로 걸어, 토큰이 설정되면
    # (AUTH_ENABLED) 인증을 요구하고 사용자 신원도 토큰에서 온다.
    user_id: str = Depends(require_user),
):
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
def presign_upload(body: dict, user_id: str = Depends(require_user)):
    """브라우저가 Storage 로 직접 올릴 1회용 URL 을 발급한다.

    create_job 과 한 쌍인 업로드 경로라 게이트도 같다(require_user) —
    require_write 면 대용량 업로드만 401 이 되어 경로가 반쪽이 된다.

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
def retry_job(meeting_id: str, background: BackgroundTasks, body: dict = None,
              user_id: str = Depends(require_write)):
    """재처리. 기존 전사·요약을 **삭제하고** 다시 만드는 파괴적 조작이라
    config.py 의 정책("수정·삭제는 401")상 require_write 가 맞다.
    프런트는 이 엔드포인트를 호출하지 않는다(재시도 버튼은 #/new 로 이동) → UI 영향 없음.
    무인증으로 열려 있던 동안은 아무나 남의 회의 전사를 지울 수 있었고, 동시 호출로
    파이프라인 2개를 붙여 상태를 고착시킬 수도 있었다."""
    conn = db.connect()
    try:
        _get_meeting(conn, meeting_id, user_id)
        job = conn.execute(
            "SELECT * FROM jobs WHERE meeting_id=? ORDER BY created_at DESC LIMIT 1",
            (meeting_id,),
        ).fetchone()
        if not job:
            return _err(404, "job_not_found", "job을 찾을 수 없습니다.")
        # 먼저 job 을 원자적으로 '선점'한다. 이 UPDATE 를 아래 삭제보다 앞에 두고
        # attempts 를 CAS 조건으로 쓰는 것이 핵심이다:
        #  - attempts=? 는 방금 읽은 값과 비교하는 compare-and-swap 이라, 동시 retry
        #    두 개 중 하나만 성공한다(먼저 커밋한 쪽이 attempts 를 올려 뒤쪽은 0행).
        #  - status NOT IN (진행 중) 은 돌고 있는 파이프라인 위에 덮어쓰지 않게 막는다.
        # 검사-후-사용(if job["status"] == ...)으로 짜면 두 요청이 같은 스냅샷을 보고
        # 둘 다 통과해, 파이프라인 2개가 같은 회의에 세그먼트를 넣다가
        # UNIQUE(meeting_id, segment_index) 를 위반한다. jobs_status_check 제약 때문에
        # 새 상태값을 만들 수는 없어 attempts 를 잠금 토큰으로 쓴다.
        claimed = conn.execute(
            "UPDATE jobs SET status='uploaded', progress=0, current_stage=NULL, "
            "error_code=NULL, error_message=NULL, attempts=attempts+1, updated_at=? "
            "WHERE id=? AND attempts=? AND status NOT IN "
            "('normalizing_audio','transcribing','summarizing')",
            (db.now_iso(), job["id"], job["attempts"]),
        )
        if not claimed.rowcount:
            return _err(409, "job_busy",
                        "이미 재처리가 진행 중입니다. 끝난 뒤 다시 시도해 주세요.")
        # 재처리를 위해 기존 전사/요약 정리 (데모 단순화)
        conn.execute("DELETE FROM transcript_segments WHERE meeting_id=?", (meeting_id,))
        svs = conn.execute("SELECT id FROM summary_versions WHERE meeting_id=?", (meeting_id,)).fetchall()
        for sv in svs:
            conn.execute("DELETE FROM summary_decisions WHERE summary_version_id=?", (sv["id"],))
            conn.execute("DELETE FROM action_items WHERE summary_version_id=?", (sv["id"],))
            conn.execute("DELETE FROM calendar_candidates WHERE summary_version_id=?", (sv["id"],))
        conn.execute("DELETE FROM summary_versions WHERE meeting_id=?", (meeting_id,))
        # jobs 상태는 위 선점 UPDATE 가 이미 초기화했다(중복 UPDATE 금지 — 잠금 의미가 흐려진다).
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


# SQLite 에는 ILIKE 가 없다(문법 오류). postgres 는 ILIKE 도 pg_trgm GIN 인덱스를 탄다.
# 이 상수 하나로 검색 LIKE 11곳(list_meetings 7 + _search_matches 4)이 같은 연산자를 쓴다.
_LIKE_OP = "ILIKE" if database.BACKEND == "postgres" else "LIKE"


def _like_pattern(q: str) -> str:
    """검색어를 LIKE 패턴으로 감싼다. `%`·`_` 는 와일드카드라 escape 하지 않으면
    '100%' 검색이 전체 노트를, 'a_b' 가 'axb' 를 잘못 잡는다. SQL 쪽에 ESCAPE '\\' 를 붙여 쓴다.
    """
    esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


def _search_matches(conn, meeting_id: str, q: str, title: str, limit: int = 3) -> list:
    """검색어가 어디에 걸렸는지(제목/전사/요약/구간) 스니펫과 함께 돌려준다.

    클로바 노트가 '음성기록 결과 / 메모 결과' 라벨을 보여주는 것과 같은 목적 —
    왜 이 회의가 결과에 떴는지 사용자가 바로 알 수 있어야 한다.
    """
    like = _like_pattern(q)
    out = []
    if title and q.lower() in title.lower():
        out.append({"source": "title", "label": "제목", "text": _snippet(title, q), "start_ms": None})
    for r in conn.execute(
            "SELECT start_ms, text, corrected_text FROM transcript_segments "
            f"WHERE meeting_id=? AND (text {_LIKE_OP} ? ESCAPE '\\' OR corrected_text {_LIKE_OP} ? ESCAPE '\\') "
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
                f"WHERE summary_version_id=? AND (text {_LIKE_OP} ? ESCAPE '\\' OR heading {_LIKE_OP} ? ESCAPE '\\') "
                "ORDER BY section_index LIMIT ?", (sv["id"], like, like, limit)).fetchall():
            body = r["text"] or r["heading"] or ""
            out.append({"source": "section", "label": "구간 요약",
                        "text": _snippet(body, q), "start_ms": r["start_ms"]})
    return out[:5]

_SORT_COLUMNS = {"recorded_at": "m.recorded_at", "title": "m.title", "duration": "m.duration_ms"}


def _sort_clause(sort: Optional[str]) -> str:
    """`<col>` 또는 `<col>:asc|desc` → 안전한 ORDER BY 절. 화이트리스트만 허용."""
    col, _, direction = (sort or "").partition(":")
    column = _SORT_COLUMNS.get(col, "m.recorded_at")
    order = "ASC" if direction.lower() == "asc" else "DESC"
    return f"{column} {order}"


@app.get(P + "/meetings")
def list_meetings(status: Optional[str] = None, q: Optional[str] = None,
                  date: Optional[str] = None, folder: Optional[str] = None,
                  sort: Optional[str] = None,
                  limit: int = 20, cursor: Optional[str] = None):
    """회의 목록. `date=YYYY-MM-DD`·`folder`(<id>|null|shared|trash)·`sort` 지원."""
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
        # folder=trash 면 삭제된 것만, 그 외엔 삭제 안 된 것만.
        if folder == "trash":
            where = ["m.user_id=?", "m.deleted_at IS NOT NULL"]
        else:
            where = ["m.user_id=?", "m.deleted_at IS NULL"]
        params = [user_id]
        if folder == "null":
            where.append("m.folder_id IS NULL")
        elif folder == "shared":
            where.append("m.id IN (SELECT meeting_id FROM share_links WHERE revoked_at IS NULL)")
        elif folder and folder != "trash":
            where.append("m.folder_id=?"); params.append(folder)
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
            # postgres 에는 pg_trgm GIN 인덱스가 있어 이 ILIKE 가 인덱스를 탄다(gin_trgm_ops).
            where.append(
                f"(m.title {_LIKE_OP} ? ESCAPE '\\'"
                " OR m.id IN (SELECT meeting_id FROM transcript_segments"
                f"             WHERE text {_LIKE_OP} ? ESCAPE '\\' OR corrected_text {_LIKE_OP} ? ESCAPE '\\')"
                " OR m.id IN (SELECT meeting_id FROM summary_versions"
                f"             WHERE title {_LIKE_OP} ? ESCAPE '\\' OR summary {_LIKE_OP} ? ESCAPE '\\')"
                " OR m.id IN (SELECT sv.meeting_id FROM summary_sections ss"
                "             JOIN summary_versions sv ON sv.id = ss.summary_version_id"
                f"             WHERE ss.text {_LIKE_OP} ? ESCAPE '\\' OR ss.heading {_LIKE_OP} ? ESCAPE '\\'))")
            like = _like_pattern(q)
            params += [like] * 7
        sql = (
            "SELECT m.*, "
            "EXISTS(SELECT 1 FROM summary_versions sv WHERE sv.meeting_id=m.id) AS has_summary, "
            "(SELECT COUNT(*) FROM share_logs s WHERE s.meeting_id=m.id AND s.status='sent') AS shared_count "
            "FROM meetings m WHERE " + " AND ".join(where) +
            " ORDER BY " + _sort_clause(sort) + " LIMIT ? OFFSET ?")
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
            "language": m["language"],
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


@app.post(P + "/meetings/{meeting_id}/move")
def move_meeting(meeting_id: str, body: FolderMoveIn, _: str = Depends(require_write)):
    """노트를 폴더로 이동. folder_id=null 이면 기본폴더(미분류)."""
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        _get_meeting(conn, meeting_id, user_id)
        if body.folder_id:
            _get_folder(conn, body.folder_id, user_id)  # 대상 폴더 존재·소유 검증
        conn.execute("UPDATE meetings SET folder_id=?, updated_at=? WHERE id=?",
                     (body.folder_id, db.now_iso(), meeting_id))
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


def _get_deleted_meeting(conn, meeting_id, user_id):
    """휴지통 대상(soft-delete + 본인)만 반환. 아니면 404. purge 안전 2중 확인."""
    row = conn.execute(
        "SELECT * FROM meetings WHERE id=? AND deleted_at IS NOT NULL", (meeting_id,)
    ).fetchone()
    if not row or not _same_id(row["user_id"], user_id):
        raise HTTPException(status_code=404, detail={"error": {
            "code": "meeting_not_found", "message": "휴지통에서 회의를 찾을 수 없습니다."}})
    return row


def _purge_meeting(conn, meeting_id):
    """스토리지 파일 + 회의/자식 전부 하드삭제. 호출측이 soft-delete+본인 검증을 마친 상태여야.

    ON DELETE CASCADE 에 의존하지 않고 자식을 명시 삭제한다:
    (a) SQLite 는 FK/CASCADE 가 아예 없어 DELETE FROM meetings 가 자식을 고아로 남기고,
    (b) Postgres 도 audit_logs.meeting_id 는 cascade 가 없어 FK 위반으로 500 이 난다.
    retry_job(main.py)의 수동 삭제 패턴과 동일한 접근. 테이블명은 상수라 인젝션 없음."""
    # 스토리지: 녹음 원본 + 내보내기 파일 (경로가 없으면 storage.delete 가 무시)
    for tbl in ("recording_files", "exports"):
        for r in conn.execute(f"SELECT storage_path FROM {tbl} WHERE meeting_id=?", (meeting_id,)).fetchall():
            storage.delete(r["storage_path"])
    # 요약 버전의 자식들(summary_version_id 로 연결)
    svs = conn.execute("SELECT id FROM summary_versions WHERE meeting_id=?", (meeting_id,)).fetchall()
    for sv in svs:
        for tbl in ("summary_sections", "summary_decisions", "action_items", "calendar_candidates"):
            conn.execute(f"DELETE FROM {tbl} WHERE summary_version_id=?", (sv["id"],))
    # 알림 상태(F): audit_id 로만 연결돼 있어 audit_logs 를 지우기 전에 정리해야 한다.
    # 순서가 뒤집히면 서브쿼리가 아무것도 못 찾아 고아 행이 영구히 남는다.
    conn.execute(
        "DELETE FROM notification_states WHERE audit_id IN "
        "(SELECT id FROM audit_logs WHERE meeting_id=?)", (meeting_id,))
    # meetings 의 직속 자식 전부
    # summary_versions 는 exports·share_logs 가 summary_version_id 로 참조하고(둘 다 no-cascade)
    # Postgres 는 즉시 FK 검사를 하므로 그 둘보다 뒤에 지운다(순서 어기면 프로덕션 500).
    for tbl in ("jobs", "recording_files", "transcript_segments", "speaker_aliases",
                "transcript_highlights", "share_links", "meeting_bookmarks",
                "exports", "share_logs", "audit_logs", "summary_versions"):
        conn.execute(f"DELETE FROM {tbl} WHERE meeting_id=?", (meeting_id,))
    conn.execute("DELETE FROM meetings WHERE id=?", (meeting_id,))


@app.post(P + "/meetings/{meeting_id}/restore")
def restore_meeting(meeting_id: str, _: str = Depends(require_write)):
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        _get_deleted_meeting(conn, meeting_id, user_id)
        conn.execute("UPDATE meetings SET deleted_at=NULL, updated_at=? WHERE id=?",
                     (db.now_iso(), meeting_id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.delete(P + "/meetings/{meeting_id}/purge")
def purge_meeting(meeting_id: str, _: str = Depends(require_write)):
    """영구삭제. soft-delete 된 본인 회의만(2중 확인). 스토리지+DB 하드삭제."""
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        _get_deleted_meeting(conn, meeting_id, user_id)
        _purge_meeting(conn, meeting_id)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.post(P + "/trash/empty")
def empty_trash(_: str = Depends(require_write)):
    """휴지통 비우기. 무조건부 대량 DELETE 아니라 대상 목록을 뽑아 건별 purge."""
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT id FROM meetings WHERE user_id=? AND deleted_at IS NOT NULL",
            (user_id,)).fetchall()
        for r in rows:
            _purge_meeting(conn, r["id"])
        conn.commit()
        return {"ok": True, "purged": len(rows)}
    finally:
        conn.close()


# ============================ Folders ============================

def _get_folder(conn, folder_id, user_id):
    row = conn.execute("SELECT * FROM folders WHERE id=?", (folder_id,)).fetchone()
    if not row or not _same_id(row["user_id"], user_id):
        raise HTTPException(status_code=404, detail={"error": {
            "code": "folder_not_found", "message": "폴더를 찾을 수 없습니다."}})
    return row


def _folder_descendant_ids(conn, folder_id, user_id):
    """folder_id 와 그 모든 자손 id 집합. postgres 는 uuid 컬럼을 UUID 객체로 돌려주므로
    문자열로 정규화한다(안 하면 str==UUID 가 항상 거짓이라 사이클 검사가 프로덕션에서 무력화)."""
    root = str(folder_id)
    ids, frontier = {root}, [root]
    while frontier:
        cur = frontier.pop()
        kids = conn.execute(
            "SELECT id FROM folders WHERE user_id=? AND parent_id=?", (user_id, cur)
        ).fetchall()
        for k in kids:
            kid = str(k["id"])
            if kid not in ids:
                ids.add(kid); frontier.append(kid)
    return ids


@app.get(P + "/folders")
def list_folders():
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT f.id, f.name, f.parent_id, "
            "(SELECT COUNT(*) FROM meetings m WHERE m.folder_id=f.id AND m.deleted_at IS NULL) AS note_count "
            "FROM folders f WHERE f.user_id=? ORDER BY f.name", (user_id,)).fetchall()
        folders = [{"id": r["id"], "name": r["name"],
                    "parent_id": r["parent_id"], "note_count": r["note_count"]} for r in rows]

        def _c(extra):
            return conn.execute(
                "SELECT COUNT(*) AS n FROM meetings m WHERE m.user_id=? " + extra,
                (user_id,)).fetchone()["n"]
        counts = {
            "all": _c("AND m.deleted_at IS NULL"),
            "unfiled": _c("AND m.deleted_at IS NULL AND m.folder_id IS NULL"),
            "trash": _c("AND m.deleted_at IS NOT NULL"),
            "shared": conn.execute(
                "SELECT COUNT(DISTINCT m.id) AS n FROM meetings m "
                "JOIN share_links sl ON sl.meeting_id=m.id "
                "WHERE m.user_id=? AND m.deleted_at IS NULL AND sl.revoked_at IS NULL",
                (user_id,)).fetchone()["n"],
        }
        return {"folders": folders, "counts": counts}
    finally:
        conn.close()


@app.post(P + "/folders")
def create_folder(body: FolderCreate, _: str = Depends(require_write)):
    user_id = config.DEFAULT_USER_ID
    name = (body.name or "").strip()
    if not name:
        return _err(422, "invalid_name", "폴더 이름이 필요합니다.")
    conn = db.connect()
    try:
        if body.parent_id:
            _get_folder(conn, body.parent_id, user_id)  # 부모 존재·소유 검증
        fid = db.new_id("folder_")
        now = db.now_iso()
        conn.execute(
            "INSERT INTO folders (id,user_id,name,parent_id,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?)", (fid, user_id, name, body.parent_id, now, now))
        conn.commit()
        return {"id": fid, "name": name, "parent_id": body.parent_id, "note_count": 0}
    finally:
        conn.close()


@app.patch(P + "/folders/{folder_id}")
def patch_folder(folder_id: str, body: FolderPatch, _: str = Depends(require_write)):
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        _get_folder(conn, folder_id, user_id)
        if body.parent_id is not None:
            # 사이클 금지: 새 부모가 자기 자신 또는 자손이면 거부
            if body.parent_id:
                _get_folder(conn, body.parent_id, user_id)
                if body.parent_id in _folder_descendant_ids(conn, folder_id, user_id):
                    return _err(409, "folder_cycle", "폴더를 자기 자신 또는 하위로 이동할 수 없습니다.")
            conn.execute("UPDATE folders SET parent_id=?, updated_at=? WHERE id=?",
                         (body.parent_id, db.now_iso(), folder_id))
        if body.name is not None:
            nm = body.name.strip()
            if not nm:
                return _err(422, "invalid_name", "폴더 이름이 필요합니다.")
            conn.execute("UPDATE folders SET name=?, updated_at=? WHERE id=?",
                         (nm, db.now_iso(), folder_id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.delete(P + "/folders/{folder_id}")
def delete_folder(folder_id: str, _: str = Depends(require_write)):
    """자식 승격(비파괴): 직속 노트→기본폴더(NULL), 직속 하위폴더→이 폴더의 부모."""
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        row = _get_folder(conn, folder_id, user_id)
        parent = row["parent_id"]
        conn.execute("UPDATE meetings SET folder_id=NULL, updated_at=? WHERE folder_id=? AND user_id=?",
                     (db.now_iso(), folder_id, user_id))
        conn.execute("UPDATE folders SET parent_id=?, updated_at=? WHERE parent_id=? AND user_id=?",
                     (parent, db.now_iso(), folder_id, user_id))
        conn.execute("DELETE FROM folders WHERE id=?", (folder_id,))
        conn.commit()
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
def add_bookmark(meeting_id: str, body: dict, _: str = Depends(require_user)):
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
def delete_bookmark(meeting_id: str, bookmark_id: str, _: str = Depends(require_user)):
    conn = db.connect()
    try:
        conn.execute("DELETE FROM meeting_bookmarks WHERE id=? AND meeting_id=?",
                     (bookmark_id, meeting_id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.get(P + "/meetings/{meeting_id}/highlights")
def list_highlights(meeting_id: str):
    conn = db.connect()
    try:
        if _get_meeting(conn, meeting_id, config.DEFAULT_USER_ID) is None:
            return _err(404, "meeting_not_found", "회의를 찾을 수 없습니다.")
        rows = conn.execute(
            "SELECT id, segment_id, start_offset, end_offset, note "
            "FROM transcript_highlights WHERE meeting_id=? ORDER BY segment_id, start_offset",
            (meeting_id,)).fetchall()
        return {"items": [{"id": r["id"], "segment_id": r["segment_id"],
                           "start_offset": r["start_offset"], "end_offset": r["end_offset"],
                           "note": r["note"]} for r in rows]}
    finally:
        conn.close()


@app.post(P + "/meetings/{meeting_id}/highlights", status_code=201)
def add_highlight(meeting_id: str, body: dict, _: str = Depends(require_user)):
    conn = db.connect()
    try:
        if _get_meeting(conn, meeting_id, config.DEFAULT_USER_ID) is None:
            return _err(404, "meeting_not_found", "회의를 찾을 수 없습니다.")
        body = body or {}
        seg_id = str(body.get("segment_id") or "")
        try:
            s = int(body.get("start_offset")); e = int(body.get("end_offset"))
        except (ValueError, TypeError):
            return _err(422, "invalid_range", "하이라이트 범위가 올바르지 않습니다.")
        if s < 0 or e <= s:
            return _err(422, "invalid_range", "하이라이트 범위가 올바르지 않습니다.")
        seg = conn.execute(
            "SELECT id, text, corrected_text FROM transcript_segments WHERE id=? AND meeting_id=?",
            (seg_id, meeting_id)).fetchone()
        if seg is None:
            return _err(404, "segment_not_found", "해당 발화를 찾을 수 없습니다.")
        # 오프셋이 실제 본문 길이를 벗어나면 저장하지 않는다(렌더 시 깨진다).
        body_text = seg["corrected_text"] or seg["text"] or ""
        if e > len(body_text):
            return _err(422, "range_out_of_bounds", "하이라이트 범위가 발화 길이를 벗어납니다.")
        hl_id = db.new_id("hl_")
        conn.execute(
            "INSERT INTO transcript_highlights "
            "(id,meeting_id,segment_id,start_offset,end_offset,note,created_at) VALUES (?,?,?,?,?,?,?)",
            (hl_id, meeting_id, seg_id, s, e, body.get("note"), db.now_iso()))
        conn.commit()
        return {"id": hl_id, "segment_id": seg_id, "start_offset": s, "end_offset": e,
                "note": body.get("note")}
    finally:
        conn.close()


@app.delete(P + "/meetings/{meeting_id}/highlights/{highlight_id}")
def delete_highlight(meeting_id: str, highlight_id: str, _: str = Depends(require_user)):
    conn = db.connect()
    try:
        conn.execute("DELETE FROM transcript_highlights WHERE id=? AND meeting_id=?",
                     (highlight_id, meeting_id))
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
        try:
            sv_id, version = db.store_summary_version(
                conn, meeting_id, result, source="user", created_by=user_id,
                expect_version=body.base_version)
        except Exception as exc:  # noqa: BLE001
            # HAVING 은 커밋된 상태만 본다. Postgres 에서 동시 저장 두 개가 서로의 커밋 전
            # 행을 못 보면 둘 다 통과하고 진 쪽이 UNIQUE(meeting_id, version) 에 걸린다.
            # 그건 500 이 아니라 충돌이다.
            if body.base_version is None or not database.is_unique_violation(exc):
                raise
            # 실패한 문장이 트랜잭션을 aborted 로 만들었으므로, 아래 조회 전에 되돌린다.
            conn.rollback()
            sv_id = None
        if sv_id is None:
            # 낙관적 잠금 충돌: 편집을 시작한 뒤 다른 탭·다른 방문자가 먼저 저장했다.
            # 덮어쓰지 않고 거부한다(공용 계정이라 남의 편집을 지우는 일이 실제로 생긴다).
            latest = db.latest_summary_version_row(conn, meeting_id)
            return _err(409, "summary_conflict",
                        "다른 곳에서 요약이 먼저 저장됐습니다. 최신 내용을 확인한 뒤 다시 저장해 주세요.",
                        {"current_version": latest["version"] if latest else 0,
                         "your_base_version": body.base_version})
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
def create_export(meeting_id: str, body: ExportIn,
                  user_id: str = Depends(require_user)):
    """내보내기 파일 생성. 회의 내용을 바꾸지 않는 파생 산출물이고 프런트의
    내보내기 버튼(web/app.js)이 프로덕션에서 쓰므로 require_write 는 달 수 없다
    (401 이면 기능이 죽는다). require_user 로 걸어 토큰 설정 시 인증을 요구한다."""
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
        try:
            conn.execute(
                """INSERT INTO exports (id,meeting_id,summary_version_id,format,include_transcript,
                   storage_path,status,created_at) VALUES (?,?,?,?,?,?,?,?)""",
                (export_id, meeting_id, body.summary_version_id, fmt,
                 database.enc_bool(body.include_transcript), saved["path"], "ready", db.now_iso()),
            )
            conn.commit()
        except Exception:  # noqa: BLE001
            # 행이 안 남으면 이 파일은 어떤 경로로도 회수되지 않는다 —
            # _purge_meeting 은 exports 행을 뒤져 파일을 지우므로 고아 파일이 영구 잔존한다.
            # (동시 retry 가 summary_versions 를 지우면 여기서 FK 위반이 난다)
            storage.delete(saved["path"])
            raise
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

# ============================ 공유 링크 ============================
#
# /v1 는 공개 데모라 무인증이다. 공유 링크를 그 위에 그대로 얹으면 "보호되는 것처럼
# 보이지만 실제로는 아무나 보는" 상태가 된다. 그래서 공유는 다음을 지킨다:
#   1) /v1/shared/{token} 은 토큰 자체가 인가 근거다. 다른 /v1 라우트의 개방성에
#      의존하지 않으므로, 나중에 LOCAL_API_TOKEN 으로 앱을 잠가도 그대로 동작한다.
#   2) 토큰 평문은 저장하지 않는다(발급 시 1회만 노출). DB 가 새도 링크가 열리지 않는다.
#   3) 비밀번호는 pbkdf2(솔트+10만 반복). 비교는 타이밍 안전 비교를 쓴다.
#   4) 만료·폐기·실패횟수를 서버가 강제한다. 응답에는 해당 회의 외 어떤 것도 담지 않는다.
_SHARE_MAX_FAILS = 10
_SHARE_TTL_DAYS = {7, 30, 90, 180, 365}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    iters = 100_000
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, iters)
    return f"pbkdf2${iters}${salt.hex()}${dk.hex()}"


def _verify_password(pw: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", (pw or "").encode("utf-8"),
                                 bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


@app.post(P + "/meetings/{meeting_id}/share-links", status_code=201)
def create_share_link(meeting_id: str, body: dict, _: str = Depends(require_user)):
    body = body or {}
    try:
        days = int(body.get("expires_in_days", 30))
    except (ValueError, TypeError):
        days = 30
    if days not in _SHARE_TTL_DAYS:
        return _err(422, "invalid_expiry", "유효기간은 7·30·90·180·365일 중에서 고르세요.")
    conn = db.connect()
    try:
        if _get_meeting(conn, meeting_id, config.DEFAULT_USER_ID) is None:
            return _err(404, "meeting_not_found", "회의를 찾을 수 없습니다.")
        active = conn.execute(
            "SELECT COUNT(*) AS n FROM share_links WHERE meeting_id=? AND revoked_at IS NULL",
            (meeting_id,)).fetchone()
        if (active["n"] if active else 0) >= 20:
            return _err(429, "too_many_links",
                        "유효한 공유 링크가 너무 많습니다. 쓰지 않는 링크를 폐기해 주세요.")
        token = secrets.token_urlsafe(32)
        pw = (body.get("password") or "").strip()
        link_id = db.new_id("shr_")
        expires = datetime.now(timezone.utc) + timedelta(days=days)
        conn.execute(
            "INSERT INTO share_links (id,meeting_id,token_hash,password_hash,include_transcript,"
            "expires_at,created_at) VALUES (?,?,?,?,?,?,?)",
            (link_id, meeting_id, _hash_token(token),
             _hash_password(pw) if pw else None,
             database.enc_bool(bool(body.get("include_transcript", True))),
             expires, db.now_iso()))
        conn.commit()
        db.audit(conn, config.DEFAULT_USER_ID, meeting_id, "share_link_created",
                 {"expires_in_days": days, "password": bool(pw)})
        # 평문 토큰은 이 응답에서 딱 한 번만 나간다. 저장하지 않는다.
        return {"id": link_id, "token": token, "path": f"/s/{token}",
                "expires_at": expires.isoformat(), "has_password": bool(pw)}
    finally:
        conn.close()


@app.get(P + "/meetings/{meeting_id}/share-links")
def list_share_links(meeting_id: str):
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT id, expires_at, revoked_at, access_count, last_accessed_at, "
            "password_hash, include_transcript FROM share_links "
            "WHERE meeting_id=? ORDER BY created_at DESC", (meeting_id,)).fetchall()
        # token_hash 는 절대 내보내지 않는다.
        return {"items": [{
            "id": r["id"], "expires_at": r["expires_at"], "revoked_at": r["revoked_at"],
            "access_count": r["access_count"], "last_accessed_at": r["last_accessed_at"],
            "has_password": bool(r["password_hash"]),
            "include_transcript": bool(r["include_transcript"]),
        } for r in rows]}
    finally:
        conn.close()


@app.delete(P + "/meetings/{meeting_id}/share-links/{link_id}")
def revoke_share_link(meeting_id: str, link_id: str, _: str = Depends(require_user)):
    conn = db.connect()
    try:
        conn.execute("UPDATE share_links SET revoked_at=? WHERE id=? AND meeting_id=?",
                     (db.now_iso(), link_id, meeting_id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def _resolve_share(conn, token: str, password: Optional[str]):
    """토큰을 검증하고 (share_row, error_response) 를 돌려준다.

    존재하지 않음·만료·폐기를 모두 같은 404 로 응답한다 — 토큰이 '있긴 한데
    만료됐다'는 사실 자체가 정보이기 때문이다.
    """
    row = conn.execute("SELECT * FROM share_links WHERE token_hash=?",
                       (_hash_token(token or ""),)).fetchone()
    gone = _err(404, "share_not_found", "링크가 없거나 만료되었습니다.")
    if row is None or row["revoked_at"]:
        return None, gone
    if _as_dt(row["expires_at"]) < datetime.now(timezone.utc).astimezone():
        return None, gone
    if row["failed_attempts"] >= _SHARE_MAX_FAILS:
        return None, _err(429, "too_many_attempts",
                          "비밀번호 시도가 너무 많습니다. 링크 소유자에게 재발급을 요청하세요.")
    if row["password_hash"]:
        if not password:
            return None, _err(401, "password_required", "비밀번호가 필요합니다.")
        # 검증 **전에** 시도 슬롯을 조건부 UPDATE 로 확보한다. 위쪽의
        # failed_attempts >= _SHARE_MAX_FAILS 검사는 이미 잠긴 링크를 값싸게 걷어내는
        # 빠른 경로일 뿐이고, 그것만으로는 병렬 요청이 전부 같은 스냅샷을 보고
        # 통과한다(실측: 상한 10 인데 총 23 회 시도가 허용됐다).
        # 영향 행 수가 0 이면 이미 상한에 도달한 것이다.
        claimed = conn.execute(
            "UPDATE share_links SET failed_attempts=failed_attempts+1 "
            "WHERE id=? AND failed_attempts < ?", (row["id"], _SHARE_MAX_FAILS))
        conn.commit()
        if not claimed.rowcount:
            return None, _err(429, "too_many_attempts",
                              "비밀번호 시도가 너무 많습니다. 링크 소유자에게 재발급을 요청하세요.")
        if not _verify_password(password, row["password_hash"]):
            return None, _err(401, "invalid_password", "비밀번호가 올바르지 않습니다.")
        # 맞았으면 방금 선점한 슬롯을 돌려준다(호출측의 리셋과 중복이어도 무해하다).
        conn.execute("UPDATE share_links SET failed_attempts=0 WHERE id=?", (row["id"],))
        conn.commit()
    return row, None


@app.get(P + "/shared/{token}")
def read_shared(token: str, password: Optional[str] = Header(default=None, alias="X-Share-Password")):
    conn = db.connect()
    try:
        share, err = _resolve_share(conn, token, password)
        if err is not None:
            return err
        m = conn.execute("SELECT * FROM meetings WHERE id=? AND deleted_at IS NULL",
                         (share["meeting_id"],)).fetchone()
        if m is None:
            return _err(404, "share_not_found", "링크가 없거나 만료되었습니다.")
        conn.execute("UPDATE share_links SET access_count=access_count+1, last_accessed_at=?, "
                     "failed_attempts=0 WHERE id=?", (db.now_iso(), share["id"]))
        conn.commit()
        try:
            # 알림용 — '내 공유 링크가 열렸다'. 공개 라우트라 기록 실패가 열람을 막으면 안 된다.
            db.audit(conn, m["user_id"], share["meeting_id"], "share_accessed",
                     {"access_count": (share["access_count"] or 0) + 1})
        except Exception:  # noqa: BLE001
            pass
        out = {"title": m["title"], "recorded_at": m["recorded_at"],
               "duration_ms": m["duration_ms"], "status": m["status"],
               "expires_at": share["expires_at"]}
        sv = db.latest_summary_version_row(conn, share["meeting_id"])
        if sv is not None:
            s = db.load_summary_version(conn, sv)
            # 내부 식별자는 공유 응답에서 제거한다.
            s.pop("summary_version_id", None)
            out["summary"] = s
        if bool(share["include_transcript"]):
            segs = conn.execute(
                "SELECT speaker_label, speaker_name, start_ms, end_ms, text, corrected_text "
                "FROM transcript_segments WHERE meeting_id=? ORDER BY start_ms",
                (share["meeting_id"],)).fetchall()
            out["segments"] = [{
                "speaker": r["speaker_name"] or r["speaker_label"],
                "start_ms": r["start_ms"], "end_ms": r["end_ms"],
                "text": r["corrected_text"] or r["text"],
            } for r in segs]
        return out
    finally:
        conn.close()

@app.get(P + "/keywords")
def list_keywords():
    """검색 칩에 쓸 추천 키워드 — 노트 요약(raw_json.keywords)을 빈도순으로 집계한다.

    읽기 전용이라 WRITE_PROTECTED 게이트를 붙이지 않는다.
    한계: 사용자가 요약을 편집하면 그 버전 raw_json 에는 keywords 가 없다(patch_summary
    가 키워드를 싣지 않음). 그래서 최신 버전만 보지 않고, 노트별로 version 내림차순으로
    훑어 keywords 가 있는 첫 버전을 채택한다.
    """
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        # raw_json 은 요약 전문이라 행마다 크다. 최근 노트로 상한을 두어
        # 노트가 쌓여도 칩 8개 뽑자고 전체 이력을 읽지 않게 한다.
        rows = conn.execute(
            "SELECT sv.meeting_id, sv.raw_json FROM summary_versions sv "
            "WHERE sv.meeting_id IN (SELECT id FROM meetings WHERE user_id=? "
            "                        AND deleted_at IS NULL AND status <> 'failed' "
            "                        ORDER BY recorded_at DESC LIMIT 200) "
            "ORDER BY sv.meeting_id, sv.version DESC", (user_id,)).fetchall()
        counts = {}
        seen = set()  # 노트당 keywords 를 가진 첫(=최신) 버전만 센다
        for r in rows:
            mid = r["meeting_id"]
            if mid in seen:
                continue
            try:
                raw = database.dec_json(r["raw_json"]) or {}
            except (ValueError, TypeError):
                continue  # 손상된 행 하나 때문에 추천 칩 전체가 죽지 않게 한다
            if not isinstance(raw, dict):
                continue  # postgres jsonb 가 배열이거나 값이 깨진 행은 건너뛴다
            words = [k.strip() for k in (raw.get("keywords") or [])
                     if isinstance(k, str) and k.strip()]
            if not words:
                continue
            seen.add(mid)
            for w in words:
                counts[w] = counts.get(w, 0) + 1
        top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
        return {"keywords": [{"text": t, "count": c} for t, c in top]}
    finally:
        conn.close()


# --- 마이페이지: 프로필 · 사용자 설정 (서브프로젝트 E1) ---

_SETTINGS_LANGS = {"ko", "en", "ja", "zh", "auto"}   # web/app.js 의 전사 언어 셀렉트와 동일
_MAX_HOTWORDS = 10          # 새 회의 폼이 콤마 구분 한 줄이라 이 정도가 실용 상한
_MAX_INTERESTS = 12
_MAX_TERM = 24
_MAX_SETTINGS_BYTES = 2048


def _read_profile(conn, user_id: str):
    """프로필 행과 설정을 함께 읽는다.

    settings 컬럼이 아직 없는 DB(마이그레이션 미적용)에서도 500 이 아니라 빈 설정으로
    내려가야 한다. 컬럼을 나열해 SELECT 하면 쿼리 자체가 실패해 가드가 돌 기회조차
    없으므로 반드시 SELECT * 로 읽는다.
    """
    row = conn.execute("SELECT * FROM profiles WHERE id=?", (user_id,)).fetchone()
    if row is None:
        return None, {}
    if "settings" not in row.keys():
        return row, {}
    return row, (database.dec_json(row["settings"]) or {})


def _clean_terms(raw, field: str, max_items: int, allow_comma: bool = True) -> list:
    if not isinstance(raw, list):
        raise HTTPException(status_code=422, detail={"error": {
            "code": "invalid_settings", "message": f"{field} 는 문자열 배열이어야 합니다."}})
    out = []
    for item in raw:
        if not isinstance(item, str):
            raise HTTPException(status_code=422, detail={"error": {
                "code": "invalid_settings", "message": f"{field} 항목은 문자열이어야 합니다."}})
        # 개행·중괄호는 요약 프롬프트에 실릴 때를 대비해 저장 시점에 털어낸다.
        term = item.replace("\n", " ").replace("\r", " ").replace("{", "").replace("}", "").strip()
        if not term:
            continue
        if not allow_comma and "," in term:
            raise HTTPException(status_code=422, detail={"error": {
                "code": "invalid_settings",
                "message": "자주 쓰는 단어에는 쉼표를 넣을 수 없습니다."}})
        if len(term) > _MAX_TERM:
            raise HTTPException(status_code=422, detail={"error": {
                "code": "invalid_settings",
                "message": f"{field} 항목은 {_MAX_TERM}자 이하여야 합니다."}})
        if term not in out:
            out.append(term)
    if len(out) > max_items:
        raise HTTPException(status_code=422, detail={"error": {
            "code": "invalid_settings", "message": f"{field} 는 최대 {max_items}개까지입니다."}})
    return out


_NOTIFY_KEYS = ("summary", "failure", "share", "export")


def _validate_notify(value) -> dict:
    """알림 토글 — boolean 4개만. 2KB 설정 예산을 E 키와 공유하므로 중첩 1단으로 제한한다."""
    if not isinstance(value, dict):
        raise HTTPException(status_code=422, detail={"error": {
            "code": "invalid_settings", "message": "알림 설정은 객체여야 합니다."}})
    out = {}
    for k, v in value.items():
        if k not in _NOTIFY_KEYS:
            raise HTTPException(status_code=422, detail={"error": {
                "code": "invalid_settings", "message": f"알 수 없는 알림 항목입니다: {k}"}})
        if not isinstance(v, bool):
            raise HTTPException(status_code=422, detail={"error": {
                "code": "invalid_settings", "message": f"{k} 는 true/false 여야 합니다."}})
        out[k] = v
    return out


def _notify_prefs(settings: dict) -> dict:
    """실효 토글값. 키가 없으면 켜짐으로 본다 — 기존 사용자에게 알림이 조용히 사라지면 안 된다."""
    raw = (settings or {}).get("notify")
    raw = raw if isinstance(raw, dict) else {}
    return {k: bool(raw.get(k, True)) for k in _NOTIFY_KEYS}


def _validate_settings(patch: dict) -> dict:
    """요청에 들어온 키만 검증한다. 저장된 blob 은 재검증하지 않는다 —
    F(알림)가 나중에 넣을 키를 E 시절 코드가 지우면 안 된다.
    """
    out = {}
    for key, value in patch.items():
        if key == "language":
            if value not in _SETTINGS_LANGS:
                raise HTTPException(status_code=422, detail={"error": {
                    "code": "invalid_settings", "message": "지원하지 않는 언어입니다."}})
            out["language"] = value
        elif key == "hotwords":
            out["hotwords"] = _clean_terms(value, "자주 쓰는 단어", _MAX_HOTWORDS, allow_comma=False)
        elif key == "interests":
            out["interests"] = _clean_terms(value, "관심 분야", _MAX_INTERESTS)
        elif key == "notify":
            out["notify"] = _validate_notify(value)
        else:
            # 무음 드롭 대신 명시적으로 거부한다(오타를 조용히 삼키지 않게).
            raise HTTPException(status_code=422, detail={"error": {
                "code": "unknown_setting", "message": f"알 수 없는 설정 항목입니다: {key}"}})
    return out


@app.get(P + "/me")
def get_me():
    """마이페이지용 프로필 + 설정. 인증 없는 공개 데모라 email·id 는 내리지 않는다.

    write_protected 는 HEALTH_DETAIL(운영자 전용) 규칙의 의도적 예외 —
    '읽기 전용 데모' 안내에 필요하고 401 한 번이면 알 수 있는 정보다.
    여기에 다른 구성 값을 추가하지 않는다.
    """
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        row, settings = _read_profile(conn, user_id)
        return {
            "display_name": (row["display_name"] if row else None) or config.DEFAULT_USER_NAME,
            "created_at": row["created_at"] if row else None,
            "settings": settings,
            "write_protected": bool(config.WRITE_PROTECTED),
        }
    finally:
        conn.close()


@app.patch(P + "/me/settings")
def patch_me_settings(body: dict = Body(...), user_id: str = Depends(require_user)):
    """본인 설정 저장. 회의를 바꾸는 게 아니라 본인 취향값이라 require_user 로 건다
    (require_write 는 공개 데모에서 401 이라 설정 자체를 못 쓴다).
    """
    if not isinstance(body, dict):
        return _err(422, "invalid_body", "설정 본문이 올바르지 않습니다.")
    validated = _validate_settings(body)
    conn = db.connect()
    try:
        _row, stored = _read_profile(conn, user_id)
        # 크기 상한은 읽은 값 기준으로 본다. 경합해도 상한 근처에서 오차가 나는 정도라 해가 없다.
        preview = dict(stored)
        preview.update(validated)
        if len(json.dumps(preview, ensure_ascii=False).encode("utf-8")) > _MAX_SETTINGS_BYTES:
            return _err(422, "settings_too_large", "설정이 너무 큽니다.")
        # 병합을 파이썬이 아니라 DB 가 원자적으로 하게 한다. 예전처럼 읽은 blob 에
        # 파이썬에서 머지해 통째로 되쓰면(settings = excluded.settings) SELECT~INSERT
        # 사이에 다른 요청이 저장한 키가 사라진다. 공용 계정(DEFAULT_USER_ID)이라
        # 동시 저장은 예외 상황이 아니라 기본 상황이다.
        # 요청에 담긴 키(validated)만 보내고 나머지는 DB 의 현재 값을 유지한다.
        merge_expr = ("coalesce(profiles.settings, '{}'::jsonb) || excluded.settings"
                      if database.BACKEND == "postgres"
                      else "json_patch(coalesce(profiles.settings, '{}'), excluded.settings)")
        try:
            # 프로필 행이 없을 수도 있어(프로덕션 시드는 best-effort) UPSERT 로 넣는다.
            # 단순 UPDATE 면 0 행 갱신인데 200 을 돌려줘 '저장됐다'고 거짓말하게 된다.
            conn.execute(
                "INSERT INTO profiles (id,email,display_name,created_at,settings) VALUES (?,?,?,?,?) "
                f"ON CONFLICT (id) DO UPDATE SET settings = {merge_expr}",
                (user_id, config.DEFAULT_USER_EMAIL, config.DEFAULT_USER_NAME,
                 db.now_iso(), database.enc_json(validated)),
            )
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            if "settings" in str(exc):
                # 컬럼이 아직 없는 상태 — 읽기는 degrade 하지만 쓰기는 구분 가능한 코드로 알린다.
                return _err(503, "settings_unavailable", "설정 저장소가 아직 준비되지 않았습니다.")
            raise
        # 병합을 DB 가 했으니 실제 저장 결과를 되읽어 돌려준다(파이썬 머지 결과를 돌려주면
        # 다른 요청이 같이 저장한 키가 응답에서 빠져 프런트가 낡은 상태를 붙잡는다).
        _row2, merged = _read_profile(conn, user_id)
        return {"settings": merged}
    finally:
        conn.close()


@app.get(P + "/usage")
def get_usage():
    """마이페이지 사용량 — 실제 수치만 돌려준다(쿼터 개념은 앱에 없으므로 만들지 않는다).

    빈 DB 에서 SUM 은 NULL 이라 COALESCE 로 0 을 보장한다(프로덕션이 지금 그 상태).
    노트 카운트 규칙은 list_folders 와 동일하게 맞춘다.
    """
    user_id = config.DEFAULT_USER_ID
    conn = db.connect()
    try:
        def _c(extra):
            return conn.execute(
                "SELECT COUNT(*) AS n FROM meetings m WHERE m.user_id=? " + extra,
                (user_id,)).fetchone()["n"]

        notes = {
            "all": _c("AND m.deleted_at IS NULL"),
            "unfiled": _c("AND m.deleted_at IS NULL AND m.folder_id IS NULL"),
            "trash": _c("AND m.deleted_at IS NOT NULL"),
            "shared": conn.execute(
                "SELECT COUNT(DISTINCT m.id) AS n FROM meetings m "
                "JOIN share_links sl ON sl.meeting_id=m.id "
                "WHERE m.user_id=? AND m.deleted_at IS NULL AND sl.revoked_at IS NULL",
                (user_id,)).fetchone()["n"],
        }
        total_ms = conn.execute(
            "SELECT COALESCE(SUM(duration_ms),0) AS s FROM meetings "
            "WHERE user_id=? AND deleted_at IS NULL", (user_id,)).fetchone()["s"]
        storage = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(size_bytes),0) AS s "
            "FROM recording_files WHERE user_id=?", (user_id,)).fetchone()

        # 이번 달: recorded_at 문자열 앞 7자리(YYYY-MM) 비교 — 양 백엔드 공통으로 안전하다.
        month = db.now_iso()[:7]
        this_month = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(duration_ms),0) AS s FROM meetings "
            "WHERE user_id=? AND deleted_at IS NULL AND CAST(recorded_at AS TEXT) LIKE ?",
            (user_id, month + "%")).fetchone()

        return {
            "notes": notes,
            "total_duration_ms": total_ms,
            "storage": {"files": storage["n"], "bytes": storage["s"]},
            "this_month": {"count": this_month["n"], "duration_ms": this_month["s"]},
        }
    finally:
        conn.close()


# --- 알림 인박스 (서브프로젝트 F1) ---
# 본문은 audit_logs 에서 파생한다(중복 저장 없음). 항목별 읽음/숨김만 notification_states 에.
# event_type -> (탭 카테고리, 표시 문구, 토글 키). 자기가 방금 한 행동
# (meeting_created·meeting_deleted·summary_edited)은 알림으로선 소음이라 넣지 않는다.
_NOTIF_KINDS = {
    "transcription_completed": ("info", "전사가 끝났어요", "summary"),
    "summary_created": ("info", "요약이 만들어졌어요", "summary"),
    "pipeline_failed": ("info", "처리에 실패했어요", "failure"),
    "share_link_created": ("notice", "공유 링크를 만들었어요", "share"),
    "share_accessed": ("notice", "공유 링크가 열렸어요", "share"),
    "shared_slack": ("notice", "Slack 으로 보냈어요", "share"),
    "export_created": ("notice", "내보내기가 준비됐어요", "export"),
}


def _notif_kinds(tab: str, prefs: dict) -> list:
    """탭 ∩ 켜진 토글. 빈 리스트면 호출측이 SQL 을 아예 타지 않아야 한다 —
    postgres 는 `IN ()` 가 문법 오류다(sqlite 는 통과해서 로컬로는 안 잡힌다).
    """
    return [k for k, (cat, _label, toggle) in _NOTIF_KINDS.items()
            if (tab in ("", "all") or cat == tab) and prefs.get(toggle, True)]


def _notif_where(kinds: list) -> str:
    marks = ",".join(["?"] * len(kinds))
    return (" FROM audit_logs a "
            " LEFT JOIN notification_states n ON n.audit_id=a.id AND n.user_id=? "
            " JOIN meetings m ON m.id=a.meeting_id "
            " WHERE a.user_id=? AND m.deleted_at IS NULL AND n.dismissed_at IS NULL "
            f" AND a.event_type IN ({marks})")


@app.get(P + "/notifications")
def list_notifications(tab: str = "all", limit: int = 20, cursor: Optional[str] = None):
    user_id = config.DEFAULT_USER_ID
    limit = max(1, min(int(limit or 20), 100))
    try:
        offset = max(0, int(cursor)) if cursor else 0
    except (TypeError, ValueError):
        offset = 0
    conn = db.connect()
    try:
        _row, settings = _read_profile(conn, user_id)
        prefs = _notify_prefs(settings)
        # 안읽음 배지는 탭과 무관하게 '켜진 것 전체' 기준이되, 목록과 같은 필터를 쓴다.
        all_kinds = _notif_kinds("all", prefs)
        kinds = _notif_kinds(tab, prefs)

        unread = 0
        if all_kinds:
            unread = conn.execute(
                "SELECT COUNT(*) AS n" + _notif_where(all_kinds) + " AND n.read_at IS NULL",
                [user_id, user_id] + all_kinds).fetchone()["n"]
        if not kinds:
            # 토글을 끈 탓에 교집합이 빌 수 있다(예: info 탭인데 summary·failure 가 꺼짐).
            return {"items": [], "next_cursor": None, "unread_count": unread, "notify": prefs}

        rows = conn.execute(
            "SELECT a.id AS id, a.event_type AS event_type, a.meeting_id AS meeting_id, "
            "a.created_at AS created_at, m.title AS title, n.read_at AS read_at" +
            _notif_where(kinds) + " ORDER BY a.created_at DESC LIMIT ? OFFSET ?",
            [user_id, user_id] + kinds + [limit + 1, offset]).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = []
        for r in rows:
            cat, label, _toggle = _NOTIF_KINDS[r["event_type"]]
            items.append({
                "id": r["id"], "kind": r["event_type"], "category": cat, "label": label,
                "title": r["title"], "meeting_id": r["meeting_id"],
                "created_at": r["created_at"], "read": r["read_at"] is not None,
            })
        return {"items": items,
                "next_cursor": str(offset + limit) if has_more else None,
                "unread_count": unread, "notify": prefs}
    finally:
        conn.close()


def _own_audit(conn, audit_id: str, user_id: str):
    """본인 이벤트인지 확인. postgres 는 audit_logs.id 가 uuid 라 형식이 틀리면 예외가 나는데
    (sqlite 는 타입이 없어 조용히 0행) 그걸 500 으로 흘리지 않고 404 로 만든다."""
    try:
        return conn.execute("SELECT 1 FROM audit_logs WHERE id=? AND user_id=?",
                            (audit_id, user_id)).fetchone()
    except Exception:  # noqa: BLE001
        return None


@app.patch(P + "/notifications/{audit_id}")
def patch_notification(audit_id: str, body: dict = Body(...),
                       user_id: str = Depends(require_user)):
    if not isinstance(body, dict):
        return _err(422, "invalid_body", "요청 본문이 올바르지 않습니다.")
    read = bool(body.get("read"))
    dismissed = bool(body.get("dismissed"))
    if not read and not dismissed:
        return _err(422, "invalid_body", "read 또는 dismissed 가 필요합니다.")
    conn = db.connect()
    try:
        if _own_audit(conn, audit_id, user_id) is None:
            return _err(404, "notification_not_found", "알림을 찾을 수 없습니다.")
        now = db.now_iso()
        conn.execute(
            "INSERT INTO notification_states (user_id,audit_id,read_at,dismissed_at) "
            "VALUES (?,?,?,?) ON CONFLICT (user_id,audit_id) DO UPDATE SET "
            "read_at=COALESCE(excluded.read_at, notification_states.read_at), "
            "dismissed_at=COALESCE(excluded.dismissed_at, notification_states.dismissed_at)",
            (user_id, audit_id, now if read else None, now if dismissed else None))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.post(P + "/notifications/read-all")
def read_all_notifications(user_id: str = Depends(require_user)):
    conn = db.connect()
    try:
        _row, settings = _read_profile(conn, user_id)
        kinds = _notif_kinds("all", prefs=_notify_prefs(settings))
        if not kinds:
            return {"marked": 0}
        rows = conn.execute(
            "SELECT a.id AS id" + _notif_where(kinds) +
            " AND n.read_at IS NULL ORDER BY a.created_at DESC LIMIT 100",
            [user_id, user_id] + kinds).fetchall()
        now = db.now_iso()
        for r in rows:
            conn.execute(
                "INSERT INTO notification_states (user_id,audit_id,read_at) VALUES (?,?,?) "
                "ON CONFLICT (user_id,audit_id) DO UPDATE SET "
                "read_at=COALESCE(excluded.read_at, notification_states.read_at)",
                (user_id, r["id"], now))
        conn.commit()
        return {"marked": len(rows)}
    finally:
        conn.close()


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


@app.get("/s/{token}", include_in_schema=False)
def share_page(token: str):
    """공유 링크 페이지. 토큰 검증은 페이지가 아니라 /v1/shared/{token} 이 한다.

    Vercel 은 vercel.json 의 라우트가 이 경로를 share.html 로 보내지만, 로컬
    uvicorn 은 StaticFiles 뿐이라 같은 동작을 여기서 맞춰준다.
    """
    page = config.WEB_DIR / "share.html"
    if not page.exists():
        return _err(404, "not_found", "페이지를 찾을 수 없습니다.")
    return FileResponse(str(page), media_type="text/html; charset=utf-8")


config.WEB_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(config.WEB_DIR), html=True, check_dir=False),
          name="web")
