"""DB 백엔드 어댑터: sqlite(기본, 검증됨) | postgres(Supabase, psycopg + native 타입).

`config.DB_BACKEND` 로 선택한다. sqlite 는 JSON 문자열/정수 boolean 으로 축소 저장하고,
postgres 는 native 타입(uuid, text[]/uuid[], jsonb, boolean, timestamptz)을 그대로 쓴다.

인코딩/디코딩 헬퍼(enc_*/dec_*)를 통해 상위 코드(db.py/main.py)는 백엔드 차이를 몰라도 된다.
`_PgConn` 은 sqlite3.Connection 과 동일한 최소 인터페이스(execute/executescript/commit/close)를
psycopg 위에 얹어, `?` 플레이스홀더를 psycopg 의 `%s` 로 번역한다.

주의: `sql.replace("?", "%s")` 는 SQL 문자열 리터럴 안에 `?` 가 없을 때만 안전하다
(이 앱의 SQL 에는 없음). psycopg 의 dict_row 는 dict 행을, sqlite3.Row 는 키 접근 가능한
행을 돌려주므로 양쪽 모두 `row["col"]` 로 읽을 수 있다.
"""
import json
import os
import uuid
from datetime import datetime, timedelta

from . import config

BACKEND = config.DB_BACKEND  # "sqlite" | "postgres"


def new_id(prefix: str = "") -> str:
    """postgres: uuid PK 이므로 순수 uuid. sqlite: 사람이 읽기 쉬운 prefix + 짧은 uuid."""
    return str(uuid.uuid4()) if BACKEND == "postgres" else f"{prefix}{uuid.uuid4().hex[:12]}"


def enc_array(lst):
    """text[]/uuid[] 컬럼용. postgres: Python list(그대로), sqlite: JSON 문자열."""
    lst = list(lst or [])
    return lst if BACKEND == "postgres" else json.dumps(lst, ensure_ascii=False)


def dec_array(v):
    if v is None:
        return []
    return list(v) if BACKEND == "postgres" else json.loads(v or "[]")


def enc_json(obj):
    """jsonb 컬럼용. postgres: psycopg Json 래퍼, sqlite: JSON 문자열."""
    if BACKEND == "postgres":
        from psycopg.types.json import Json
        return Json(obj)
    return json.dumps(obj, ensure_ascii=False)


def dec_json(v):
    if BACKEND == "postgres":
        return v if isinstance(v, (dict, list)) else (json.loads(v) if v else {})
    return json.loads(v or "{}")


def enc_bool(b):
    """boolean 컬럼용. postgres: native bool, sqlite: 0/1 정수."""
    return bool(b) if BACKEND == "postgres" else (1 if b else 0)


def _local_timezone() -> str:
    """Postgres 세션 타임존으로 쓸 값.

    postgres 는 timestamptz 를 '세션 타임존'으로 렌더링한다(기본 UTC).
    sqlite 백엔드는 원본 ISO 문자열(+09:00 등)을 그대로 보존하므로,
    두 백엔드가 같은 로컬 시각을 보이도록 세션 타임존을 로컬로 맞춘다.
    (안 맞추면 달력·내보내기 시각이 UTC로 밀리고, 자정 근처 녹음은 날짜 그룹핑까지 어긋난다)
    """
    # PG_TIMEZONE > TZ > /etc/localtime > UTC 오프셋.
    # 서버리스(Vercel) 컨테이너는 로컬 타임존이 UTC 라 자동감지만으로는 시각이 밀린다.
    tz = os.getenv("PG_TIMEZONE", "").strip() or os.getenv("TZ", "").strip()
    if tz:
        return tz
    # /etc/localtime 심볼릭 링크에서 IANA 이름 추출 (macOS/Linux)
    try:
        link = os.path.realpath("/etc/localtime")
        if "zoneinfo/" in link:
            return link.split("zoneinfo/", 1)[1]
    except OSError:
        pass
    # 마지막 수단: 현재 UTC 오프셋
    off = datetime.now().astimezone().utcoffset() or timedelta(0)
    total = int(off.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"


def connect():
    if BACKEND == "postgres":
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.connect(config.DATABASE_URL, row_factory=dict_row)
        with conn.cursor() as cur:
            # SET TIME ZONE 은 유틸리티 명령이라 바인드 파라미터를 못 받는다.
            # set_config() 는 함수라 파라미터 바인딩이 되므로 인젝션 걱정 없이 안전하다.
            cur.execute("SELECT set_config('timezone', %s, false)", (_local_timezone(),))
        conn.commit()
        return _PgConn(conn)
    import sqlite3
    c = sqlite3.connect(str(config.DB_PATH), timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA foreign_keys=ON;")
    return c


class _PgConn:
    """sqlite3.Connection 유사 파사드(psycopg 위) — `?` → `%s` 번역."""

    def __init__(self, c):
        self._c = c

    def execute(self, sql, params=()):
        cur = self._c.cursor()
        cur.execute(sql.replace("?", "%s"), tuple(params))
        return cur

    def executescript(self, s):
        with self._c.cursor() as cur:
            cur.execute(s)
        self._c.commit()

    def commit(self):
        self._c.commit()

    def close(self):
        self._c.close()
