"""SQLite 접근 계층: 스키마 초기화, 연결, 공용 헬퍼.

논리 스키마는 docs/db-schema.md(Postgres 기준)를 SQLite로 축소한 것이다.
테이블/필드명은 문서를 그대로 따르고, 타입만 SQLite에 맞춘다
(uuid→TEXT, timestamptz→ISO TEXT, jsonb/array→JSON TEXT, boolean→INTEGER).
"""
from datetime import datetime, timezone

from . import config, database

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
  id TEXT PRIMARY KEY,
  email TEXT,
  display_name TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meetings (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  title TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  duration_ms INTEGER,
  language TEXT NOT NULL DEFAULT 'ko',
  source_device TEXT,
  hotwords TEXT,                                   -- JSON array (findings #4 대응: 영속화)
  status TEXT NOT NULL DEFAULT 'uploaded',
  recording_consent_confirmed INTEGER NOT NULL DEFAULT 0,
  recording_consent_confirmed_at TEXT,
  deleted_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  meeting_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'uploaded',
  progress REAL NOT NULL DEFAULT 0,
  current_stage TEXT,
  error_code TEXT,
  error_message TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recording_files (
  id TEXT PRIMARY KEY,
  meeting_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  kind TEXT NOT NULL,                              -- original | normalized | export_audio_clip
  storage_path TEXT NOT NULL,
  mime_type TEXT,
  size_bytes INTEGER,
  sample_rate INTEGER,
  channels INTEGER,
  duration_ms INTEGER,
  checksum_sha256 TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transcript_segments (
  id TEXT PRIMARY KEY,
  meeting_id TEXT NOT NULL,
  segment_index INTEGER NOT NULL,
  speaker_label TEXT NOT NULL,
  speaker_name TEXT,
  start_ms INTEGER NOT NULL,
  end_ms INTEGER NOT NULL,
  text TEXT NOT NULL,
  corrected_text TEXT,
  confidence REAL,
  bookmarked INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'asr',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (meeting_id, segment_index)
);

CREATE TABLE IF NOT EXISTS speaker_aliases (
  id TEXT PRIMARY KEY,
  meeting_id TEXT NOT NULL,
  speaker_label TEXT NOT NULL,
  speaker_name TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (meeting_id, speaker_label)
);

CREATE TABLE IF NOT EXISTS summary_versions (
  id TEXT PRIMARY KEY,
  meeting_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  source TEXT NOT NULL,                            -- ai | user | regenerated
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  raw_json TEXT NOT NULL,
  raw_model_output TEXT,
  created_by TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (meeting_id, version)
);

CREATE TABLE IF NOT EXISTS summary_decisions (
  id TEXT PRIMARY KEY,
  summary_version_id TEXT NOT NULL,
  decision_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  source_segment_ids TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS action_items (
  id TEXT PRIMARY KEY,
  summary_version_id TEXT NOT NULL,
  item_index INTEGER NOT NULL,
  owner TEXT,
  task TEXT NOT NULL,
  due_date TEXT,
  source_segment_ids TEXT NOT NULL DEFAULT '[]',
  confidence REAL,
  status TEXT NOT NULL DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS calendar_candidates (
  id TEXT PRIMARY KEY,
  summary_version_id TEXT NOT NULL,
  item_index INTEGER NOT NULL,
  title TEXT NOT NULL,
  start_at TEXT,
  end_at TEXT,
  attendees TEXT NOT NULL DEFAULT '[]',
  source_segment_ids TEXT NOT NULL DEFAULT '[]',
  confidence REAL,
  status TEXT NOT NULL DEFAULT 'pending',
  created_calendar_url TEXT
);

CREATE TABLE IF NOT EXISTS exports (
  id TEXT PRIMARY KEY,
  meeting_id TEXT NOT NULL,
  summary_version_id TEXT,
  format TEXT NOT NULL,
  include_transcript INTEGER NOT NULL DEFAULT 1,
  storage_path TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  error_message TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS share_logs (
  id TEXT PRIMARY KEY,
  meeting_id TEXT NOT NULL,
  summary_version_id TEXT,
  provider TEXT NOT NULL,
  target_label TEXT,
  status TEXT NOT NULL,
  request_payload TEXT,
  response_status INTEGER,
  response_body TEXT,
  sent_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  meeting_id TEXT,
  event_type TEXT NOT NULL,
  metadata TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS meetings_user_recorded_idx ON meetings(user_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS jobs_meeting_idx ON jobs(meeting_id);
CREATE INDEX IF NOT EXISTS segments_meeting_time_idx ON transcript_segments(meeting_id, start_ms);
CREATE INDEX IF NOT EXISTS summary_versions_meeting_version_idx ON summary_versions(meeting_id, version DESC);
CREATE INDEX IF NOT EXISTS exports_meeting_idx ON exports(meeting_id, created_at DESC);
CREATE INDEX IF NOT EXISTS share_logs_meeting_idx ON share_logs(meeting_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_logs_meeting_idx ON audit_logs(meeting_id, created_at DESC);
"""


def connect():
    """백엔드(sqlite|postgres) 어댑터 연결을 돌려준다."""
    return database.connect()


def init_db() -> None:
    if database.BACKEND == "postgres":
        # postgres 스키마는 Supabase 에 이미 적용됨 → DDL 실행하지 않는다.
        # 기본 프로필만 best-effort 시드하고, 비밀번호 미설정 등 연결 오류는 무시한다.
        try:
            conn = connect()
            try:
                conn.execute(
                    "INSERT INTO profiles (id,email,display_name,created_at) "
                    "VALUES (?,?,?,?) ON CONFLICT (id) DO NOTHING",
                    (config.DEFAULT_USER_ID, config.DEFAULT_USER_EMAIL,
                     config.DEFAULT_USER_NAME, now_iso()),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:  # noqa: BLE001 - DATABASE_URL 비밀번호 미설정 시 데모 부팅을 막지 않는다
            pass
        return

    conn = connect()
    try:
        conn.executescript(SCHEMA)
        # 단일 로컬 사용자 시드
        exists = conn.execute(
            "SELECT 1 FROM profiles WHERE id=?", (config.DEFAULT_USER_ID,)
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO profiles (id,email,display_name,created_at) VALUES (?,?,?,?)",
                (config.DEFAULT_USER_ID, config.DEFAULT_USER_EMAIL,
                 config.DEFAULT_USER_NAME, now_iso()),
            )
        conn.commit()
    finally:
        conn.close()


# --- 공용 헬퍼 ---
def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def new_id(prefix: str = "") -> str:
    return database.new_id(prefix)


def audit(conn, user_id, meeting_id, event_type, metadata=None) -> None:
    conn.execute(
        "INSERT INTO audit_logs (id,user_id,meeting_id,event_type,metadata,created_at) VALUES (?,?,?,?,?,?)",
        (new_id("audit_"), user_id, meeting_id, event_type,
         database.enc_json(metadata or {}), now_iso()),
    )
    conn.commit()


def store_summary_version(conn, meeting_id, result, source, created_by=None,
                          raw_model_output=None):
    """summary_versions + 자식(decisions/action_items/calendar_candidates)을 새 버전으로 저장.

    version은 (meeting_id) 기준 max+1 로 원자적으로 채번한다.
    """
    row = conn.execute(
        "SELECT COALESCE(MAX(version),0)+1 AS v FROM summary_versions WHERE meeting_id=?",
        (meeting_id,),
    ).fetchone()
    version = row["v"]
    sv_id = new_id("summary_")
    now = now_iso()
    # NOT NULL 텍스트 컬럼은 None→"" 로 방어 (LLM이 null 필드를 반환해도 저장 실패 금지)
    def s(v):
        return v if isinstance(v, str) else ("" if v is None else str(v))
    conn.execute(
        """INSERT INTO summary_versions
           (id,meeting_id,version,source,title,summary,raw_json,raw_model_output,created_by,created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (sv_id, meeting_id, version, source, s(result.get("title")),
         s(result.get("summary")), database.enc_json(result),
         raw_model_output, created_by, now),
    )
    for i, d in enumerate(result.get("decisions", []) or []):
        conn.execute(
            "INSERT INTO summary_decisions (id,summary_version_id,decision_index,text,source_segment_ids) VALUES (?,?,?,?,?)",
            (new_id("dec_"), sv_id, i, s(d.get("text")),
             database.enc_array(d.get("source_segment_ids", []))),
        )
    for i, a in enumerate(result.get("action_items", []) or []):
        conn.execute(
            """INSERT INTO action_items
               (id,summary_version_id,item_index,owner,task,due_date,source_segment_ids,confidence,status)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (new_id("act_"), sv_id, i, a.get("owner"), s(a.get("task")),
             a.get("due_date"), database.enc_array(a.get("source_segment_ids", [])),
             a.get("confidence"), a.get("status", "open")),
        )
    for i, c in enumerate(result.get("calendar_candidates", []) or []):
        conn.execute(
            """INSERT INTO calendar_candidates
               (id,summary_version_id,item_index,title,start_at,end_at,attendees,source_segment_ids,confidence,status,created_calendar_url)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (new_id("cal_"), sv_id, i, s(c.get("title")), c.get("start_at"),
             c.get("end_at"), database.enc_array(c.get("attendees", [])),
             database.enc_array(c.get("source_segment_ids", [])),
             c.get("confidence"), c.get("status", "pending"), c.get("created_calendar_url")),
        )
    conn.commit()
    return sv_id, version


def load_summary_version(conn, sv_row) -> dict:
    """summary_versions row → API 응답 dict (자식 포함)."""
    sv_id = sv_row["id"]
    decisions = [
        {"text": r["text"], "source_segment_ids": database.dec_array(r["source_segment_ids"])}
        for r in conn.execute(
            "SELECT * FROM summary_decisions WHERE summary_version_id=? ORDER BY decision_index",
            (sv_id,),
        ).fetchall()
    ]
    action_items = [
        {"owner": r["owner"], "task": r["task"], "due_date": r["due_date"],
         "source_segment_ids": database.dec_array(r["source_segment_ids"]),
         "confidence": r["confidence"], "status": r["status"]}
        for r in conn.execute(
            "SELECT * FROM action_items WHERE summary_version_id=? ORDER BY item_index",
            (sv_id,),
        ).fetchall()
    ]
    calendar_candidates = [
        {"title": r["title"], "start_at": r["start_at"], "end_at": r["end_at"],
         "attendees": database.dec_array(r["attendees"]),
         "source_segment_ids": database.dec_array(r["source_segment_ids"]),
         "confidence": r["confidence"], "status": r["status"],
         "created_calendar_url": r["created_calendar_url"]}
        for r in conn.execute(
            "SELECT * FROM calendar_candidates WHERE summary_version_id=? ORDER BY item_index",
            (sv_id,),
        ).fetchall()
    ]
    return {
        "summary_version_id": sv_id,
        "version": sv_row["version"],
        "source": sv_row["source"],
        "title": sv_row["title"],
        "summary": sv_row["summary"],
        "decisions": decisions,
        "action_items": action_items,
        "calendar_candidates": calendar_candidates,
    }


def latest_summary_version_row(conn, meeting_id):
    return conn.execute(
        "SELECT * FROM summary_versions WHERE meeting_id=? ORDER BY version DESC LIMIT 1",
        (meeting_id,),
    ).fetchone()
