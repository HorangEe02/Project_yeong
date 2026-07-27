#!/usr/bin/env python3
"""동시 요청 경합·부분 쓰기 재현 하니스 (P0-1 / P0-3).

배경·수정 내역: ../docs/race-conditions.md (저장소 루트 기준 05_lemon-note/docs/race-conditions.md)

재현하는 결함
  P0-1  같은 회의에 파이프라인이 두 번 돌면 transcript_segments 의
        UNIQUE(meeting_id, segment_index) 를 위반한다. Postgres 는 그 순간
        트랜잭션이 aborted 로 바뀌어, except 절의 실패 기록(_set_status('failed'),
        db.audit('pipeline_failed')) 이 둘 다 InFailedSqlTransaction 으로 죽고
        `except: pass` 에 삼켜진다 → 상태가 중간값에 영구 고착, 실패 알림도 없음.
        _PgConn 에 rollback() 이 없어 복구 경로도 없다.
        **SQLite 에서는 재현되지 않는다** — 그래서 로컬 검증으로는 잡히지 않았다.

  P0-3  공유 링크 비밀번호 잠금(_SHARE_MAX_FAILS=10) 검사가 스냅샷 기반이라
        (main.py:1403 이 1396 에서 읽은 값을 본다) 병렬 요청이 모두 검사를
        통과한다 → 상한을 버스트 크기만큼 초과. 공개 무인증 경로다.

의존성
  requirements.txt + httpx (하니스 전용). requirements-dev.txt 로 한 번에 설치:
    python -m pip install -r requirements.txt -r requirements-dev.txt

안전장치 (프로덕션 오염 방지)
  - DB 호스트가 127.0.0.1/localhost/::1 이 아니면 **거부**한다.
  - DSN 에 supabase/pooler 문자열이 있으면 **거부**한다.
  - 자식 프로세스 환경의 DATABASE_URL 을 명시적으로 덮어써, local-worker/.env 의
    프로덕션 DATABASE_URL 이 setdefault 로 새어들지 못하게 한다.
  - API 대상 호스트도 로컬만 허용한다.

사용법
  # 1) 로컬 Postgres (P0-1 재현에 필수)
  docker run -d --name lemon-race-pg -e POSTGRES_PASSWORD=postgres \
      -e POSTGRES_DB=lemonrace -p 55432:5432 postgres:16
  ./.venv/bin/python scripts/repro_races.py init-schema \
      --pg-dsn postgresql://postgres:postgres@127.0.0.1:55432/lemonrace

  # 2) 전체 재현 (두 백엔드 대조 포함)
  ./.venv/bin/python scripts/repro_races.py all \
      --pg-dsn postgresql://postgres:postgres@127.0.0.1:55432/lemonrace

  # 개별 실행
  ./.venv/bin/python scripts/repro_races.py abort-swallow --backend postgres --pg-dsn ...
  ./.venv/bin/python scripts/repro_races.py share-lockout --backend postgres --pg-dsn ...

종료 코드
  0  경합 미검출 (수정이 적용된 상태)
  1  경합 재현됨 (결함 존재)
  2  실행 오류 또는 안전장치 거부
"""
import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parent.parent
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
# sqlite 모드에서 .env 의 프로덕션 DATABASE_URL 이 새어들지 못하게 넣는 막힌 값.
_BLOCKED_DSN = "postgresql://blocked:blocked@127.0.0.1:1/blocked"


def die(msg: str, code: int = 2):
    print(f"\n[중단] {msg}", file=sys.stderr)
    raise SystemExit(code)


def assert_local_dsn(dsn: str):
    """프로덕션 DB 를 절대 건드리지 않게 하는 하드 가드."""
    if not dsn:
        die("DSN 이 비어 있다.")
    low = dsn.lower()
    for bad in ("supabase", "pooler", "amazonaws", "neon.tech", "rds."):
        if bad in low:
            die(f"원격 DB 로 보이는 DSN 을 거부한다(포함 문자열: {bad!r}). 이 하니스는 로컬 전용이다.")
    host = (urlparse(dsn).hostname or "").lower()
    if host not in _LOCAL_HOSTS:
        die(f"비로컬 DB 호스트를 거부한다: {host!r}. 허용: {sorted(_LOCAL_HOSTS)}")


def assert_local_url(url: str):
    host = (urlparse(url).hostname or "").lower()
    if host not in _LOCAL_HOSTS:
        die(f"비로컬 API 대상을 거부한다: {host!r}")


def _env_for(backend: str, dsn: str, workdir: Path, write_protected: str = "0",
             max_jobs: str = "0") -> dict:
    """백엔드별 실행 환경. DATABASE_URL 을 항상 명시해 .env 유입을 차단한다."""
    env = dict(os.environ)
    env["DB_BACKEND"] = backend
    env["DATABASE_URL"] = dsn if backend == "postgres" else _BLOCKED_DSN
    env["DB_PATH"] = str(workdir / "app.db")
    env["LOCAL_STORAGE_ROOT"] = str(workdir / "storage")
    env["ASR_PROVIDER"] = "stub"
    env["SUMMARY_PROVIDER"] = "stub"
    env["STUB_STAGE_DELAY"] = "0"
    env["SYNC_PIPELINE"] = "1"
    env["WRITE_PROTECTED"] = write_protected
    env["HEALTH_DETAIL"] = "1"
    env["MAX_JOBS_PER_HOUR"] = max_jobs     # 기본 0=끔(다른 시나리오를 방해하지 않게)
    env["PYTHONPATH"] = str(REPO)
    env.pop("LOCAL_API_TOKEN", None)         # 인증 비활성(데모와 동일)
    return env


def _load_app(backend: str, dsn: str, workdir: Path):
    """이 프로세스에 app 모듈을 적재한다. database.BACKEND 가 모듈 상수라
    한 프로세스는 백엔드 하나만 다룰 수 있다 — 대조는 별도 프로세스로 한다."""
    os.environ.update(_env_for(backend, dsn, workdir))
    sys.path.insert(0, str(REPO))
    from app import config, database, db, pipeline  # noqa: E402
    if config.DB_BACKEND != backend:
        die(f"백엔드 불일치: 요청={backend} 실제={config.DB_BACKEND}")
    if backend == "postgres":
        assert_local_dsn(config.DATABASE_URL)     # 해석된 실제 값으로 재확인
    if database.BACKEND != backend:
        die(f"database.BACKEND 불일치: {database.BACKEND}")
    db.init_db()
    return config, database, db, pipeline


# --------------------------------------------------------------------------
# 시드 (API 멀티파트를 거치지 않고 최소 행만 만든다)
# --------------------------------------------------------------------------

def _seed_meeting(config, database, db, title="경합 재현용 회의"):
    conn = db.connect()
    try:
        mid = db.new_id("mtg_")
        rid = db.new_id("rec_")
        jid = db.new_id("job_")
        now = db.now_iso()
        conn.execute(
            """INSERT INTO meetings
               (id,user_id,title,recorded_at,duration_ms,language,source_device,hotwords,
                status,recording_consent_confirmed,recording_consent_confirmed_at,
                created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (mid, config.DEFAULT_USER_ID, title, now, 180_000, "ko", "harness", None,
             "uploaded", database.enc_bool(True), now, now, now),
        )
        conn.execute(
            """INSERT INTO recording_files
               (id,meeting_id,user_id,kind,storage_path,mime_type,size_bytes,
                duration_ms,checksum_sha256,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (rid, mid, config.DEFAULT_USER_ID, "original", "harness/dummy.webm",
             "audio/webm", 1234, 180_000, "0" * 64, now),
        )
        conn.execute(
            "INSERT INTO jobs (id,meeting_id,status,progress,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (jid, mid, "uploaded", 0.0, now, now),
        )
        conn.commit()
        return mid, jid
    finally:
        conn.close()


def _seed_share_link(config, database, db, meeting_id, password):
    """토큰 평문을 알아야 하므로 API 대신 직접 넣는다(해시는 앱과 같은 함수 사용)."""
    from app import main as appmain
    token = secrets.token_urlsafe(32)
    conn = db.connect()
    try:
        from datetime import datetime, timedelta, timezone
        conn.execute(
            """INSERT INTO share_links
               (id,meeting_id,token_hash,password_hash,include_transcript,
                expires_at,access_count,failed_attempts,created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (db.new_id("shr_"), meeting_id, appmain._hash_token(token),
             appmain._hash_password(password), database.enc_bool(True),
             datetime.now(timezone.utc) + timedelta(days=30), 0, 0, db.now_iso()),
        )
        conn.commit()
        return token
    finally:
        conn.close()


def _status(db, job_id, meeting_id):
    conn = db.connect()
    try:
        j = conn.execute("SELECT status,progress,current_stage,error_code FROM jobs WHERE id=?",
                         (job_id,)).fetchone()
        m = conn.execute("SELECT status FROM meetings WHERE id=?", (meeting_id,)).fetchone()
        return {"job": j["status"] if j else None,
                "stage": j["current_stage"] if j else None,
                "error_code": j["error_code"] if j else None,
                "meeting": m["status"] if m else None}
    finally:
        conn.close()


def _count(db, sql, params):
    conn = db.connect()
    try:
        row = conn.execute(sql, params).fetchone()
        return list(row.values())[0] if hasattr(row, "values") else row[0]
    finally:
        conn.close()


# --------------------------------------------------------------------------
# 시나리오 1: P0-1 — 파이프라인 실패가 자기 자신을 숨긴다
# --------------------------------------------------------------------------

_TERMINAL = {"ready_for_review", "failed"}


def scenario_abort_swallow(backend: str, dsn: str, workdir: Path) -> dict:
    """같은 회의에 파이프라인을 두 번 돌린다.

    두 번째 실행은 동시 retry 두 개 중 '뒤늦은 쪽'이 놓이는 상태와 동일하다
    (앞선 실행이 세그먼트를 이미 커밋한 뒤 시작). segment_index 충돌이 확정이라
    타이밍 운에 의존하지 않는 결정론적 재현이다.
    """
    config, database, db, pipeline = _load_app(backend, dsn, workdir)
    mid, jid = _seed_meeting(config, database, db)

    pipeline.run_pipeline(jid, mid)                      # 1차: 정상 완료
    st1 = _status(db, jid, mid)
    seg1 = _count(db, "SELECT COUNT(*) AS n FROM transcript_segments WHERE meeting_id=?", (mid,))

    escaped = None
    try:
        pipeline.run_pipeline(jid, mid)                  # 2차: UNIQUE 충돌
    except BaseException as e:                           # noqa: BLE001
        escaped = f"{type(e).__name__}: {e}"

    st2 = _status(db, jid, mid)
    seg2 = _count(db, "SELECT COUNT(*) AS n FROM transcript_segments WHERE meeting_id=?", (mid,))
    audit_failed = _count(
        db, "SELECT COUNT(*) AS n FROM audit_logs WHERE meeting_id=? AND event_type=?",
        (mid, "pipeline_failed"))
    versions = _count(db, "SELECT COUNT(*) AS n FROM summary_versions WHERE meeting_id=?", (mid,))

    stuck = st2["job"] not in _TERMINAL
    silent = audit_failed == 0 and st2["job"] != "failed"
    return {
        "scenario": "abort-swallow (P0-1)",
        "backend": backend,
        "run1_status": st1, "run1_segments": seg1,
        "run2_status": st2, "run2_segments": seg2,
        "escaped_exception": escaped,
        "pipeline_failed_audits": audit_failed,
        "summary_versions": versions,
        "stuck_in_nonterminal": stuck,
        "failure_silently_swallowed": silent,
        "reproduced": bool(stuck and silent),
    }


# --------------------------------------------------------------------------
# 시나리오 2: P0-3 — 공유 링크 비밀번호 잠금 우회
# --------------------------------------------------------------------------

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(env: dict, port: int):
    proc = subprocess.Popen(
        # sys.executable 을 쓴다 — .venv 경로를 박아두면 CI 처럼 venv 없이 돌리는 환경에서 깨진다.
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=str(REPO), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    import httpx
    base = f"http://127.0.0.1:{port}"
    for _ in range(120):
        if proc.poll() is not None:
            out = proc.stdout.read() if proc.stdout else ""
            die(f"서버가 죽었다(종료코드 {proc.returncode}).\n{out[-2000:]}")
        try:
            if httpx.get(base + "/v1/health", timeout=1.0).status_code == 200:
                return proc, base
        except Exception:  # noqa: BLE001 - 기동 대기
            pass
        time.sleep(0.25)
    proc.terminate()
    die("서버 기동 시간 초과")


def scenario_share_lockout(backend: str, dsn: str, workdir: Path, burst: int = 60) -> dict:
    """failed_attempts 를 상한-1 까지 순차로 올린 뒤, 틀린 비밀번호로 병렬 버스트를 쏜다.

    검사가 스냅샷 기반이면 버스트 전체가 검사를 통과해 비밀번호 판정(401)을 받는다.
    올바르게 조건부 UPDATE 로 고쳤다면 1건만 401 이고 나머지는 429 여야 한다.
    """
    import httpx
    config, database, db, _pipeline = _load_app(backend, dsn, workdir)
    mid, _jid = _seed_meeting(config, database, db, title="공유 잠금 재현용")
    password = "correct-horse-battery"
    token = _seed_share_link(config, database, db, mid, password)

    from app import main as appmain
    cap = appmain._SHARE_MAX_FAILS

    env = _env_for(backend, dsn, workdir)
    port = _free_port()
    proc, base = _start_server(env, port)
    assert_local_url(base)
    url = f"{base}/v1/shared/{token}"
    try:
        # 상한-1 까지 순차로 실패시킨다 (여기까지는 정상 동작)
        seq = []
        for _ in range(cap - 1):
            r = httpx.get(url, headers={"X-Share-Password": "wrong"}, timeout=15.0)
            seq.append(r.status_code)
        attempts_used = cap - 1

        remaining_allowed = cap - attempts_used          # 정상이라면 1건만 더 허용
        counter_before = _count(
            db, "SELECT failed_attempts AS n FROM share_links WHERE meeting_id=?", (mid,))

        # 병렬 버스트 — 전부 같은 스냅샷을 읽게 한다
        def one(_i):
            try:
                r = httpx.get(url, headers={"X-Share-Password": "wrong"}, timeout=30.0)
                body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                return r.status_code, (body.get("error") or {}).get("code")
            except Exception as e:  # noqa: BLE001
                return None, f"{type(e).__name__}"

        with ThreadPoolExecutor(max_workers=burst) as ex:
            results = list(ex.map(one, range(burst)))

        got_401 = sum(1 for c, code in results if c == 401 and code == "invalid_password")
        got_429 = sum(1 for c, code in results if c == 429)
        other = [(c, code) for c, code in results if c not in (401, 429)]
        counter_after = _count(
            db, "SELECT failed_attempts AS n FROM share_links WHERE meeting_id=?", (mid,))

        # 정상 구현이면 버스트 중 비밀번호 판정을 받는 건 remaining_allowed 개 이하
        excess = got_401 - remaining_allowed
        return {
            "scenario": "share-lockout (P0-3)",
            "backend": backend,
            "cap": cap,
            "sequential_status_codes": {"401": seq.count(401), "429": seq.count(429)},
            "attempts_used_before_burst": attempts_used,
            "counter_before_burst": counter_before,
            "burst_size": burst,
            "burst_allowed_by_spec": remaining_allowed,
            "burst_got_password_verdict_401": got_401,
            "burst_got_429": got_429,
            "burst_other": other[:5],
            "counter_after_burst": counter_after,
            "excess_attempts_granted": excess,
            "reproduced": excess > 0,
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# --------------------------------------------------------------------------
# 시나리오 3: 동시 retry 선점 (P0-1 의 트리거 경로)
# --------------------------------------------------------------------------

def scenario_retry_lock(backend: str, dsn: str, workdir: Path) -> dict:
    """같은 회의에 POST /retry 두 개를 동시에 쏜다.

    선점이 원자적이면 하나만 200, 나머지는 409 job_busy 여야 한다.
    둘 다 200 이면 파이프라인 2개가 같은 회의에 붙어 P0-1 로 이어진다.
    """
    import httpx
    config, database, db, pipeline = _load_app(backend, dsn, workdir)
    mid, jid = _seed_meeting(config, database, db, title="retry 선점 재현용")
    pipeline.run_pipeline(jid, mid)                  # 종료 상태로 만든다(재처리 가능 상태)

    env = _env_for(backend, dsn, workdir)
    port = _free_port()
    proc, base = _start_server(env, port)
    assert_local_url(base)
    url = f"{base}/v1/meetings/{mid}/retry"
    try:
        def one(_i):
            try:
                r = httpx.post(url, json={}, timeout=60.0)
                body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                return r.status_code, (body.get("error") or {}).get("code")
            except Exception as e:  # noqa: BLE001
                return None, type(e).__name__

        with ThreadPoolExecutor(max_workers=2) as ex:
            results = list(ex.map(one, range(2)))

        ok = sum(1 for c, _ in results if c == 200)
        busy = sum(1 for c, code in results if c == 409 and code == "job_busy")
        segs = _count(db, "SELECT COUNT(*) AS n FROM transcript_segments WHERE meeting_id=?", (mid,))
        dup = _count(
            db, "SELECT COUNT(*) AS n FROM (SELECT segment_index FROM transcript_segments "
                "WHERE meeting_id=? GROUP BY segment_index HAVING COUNT(*) > 1) d", (mid,))
        return {
            "scenario": "retry-lock (P0-1 트리거)",
            "backend": backend,
            "responses": results,
            "http_200": ok,
            "http_409_job_busy": busy,
            "segments_after": segs,
            "duplicate_segment_indexes": dup,
            "reproduced": bool(ok > 1),
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# --------------------------------------------------------------------------
# 시나리오 4: 설정 동시 저장 갱신 유실 (P0-4)
# --------------------------------------------------------------------------

def scenario_settings_merge(backend: str, dsn: str, workdir: Path, rounds: int = 8) -> dict:
    """서로 다른 최상위 키를 동시에 PATCH 한다.

    서버가 파이썬에서 머지해 blob 을 통째로 되쓰면 한쪽 키가 사라진다.
    DB 가 원자적으로 병합하면 매 라운드마다 두 키가 모두 남는다.
    """
    import httpx
    config, database, db, _pipeline = _load_app(backend, dsn, workdir)
    env = _env_for(backend, dsn, workdir)
    port = _free_port()
    proc, base = _start_server(env, port)
    assert_local_url(base)
    url = f"{base}/v1/me/settings"
    try:
        lost = []
        for r in range(rounds):
            lang = ["ko", "en", "ja", "zh"][r % 4]
            word = f"라운드{r}"
            # 서로 겹치지 않는 키를 동시에 저장한다
            def a():
                return httpx.patch(url, json={"language": lang}, timeout=30.0).status_code

            def b():
                return httpx.patch(url, json={"hotwords": [word]}, timeout=30.0).status_code

            with ThreadPoolExecutor(max_workers=2) as ex:
                codes = [f.result() for f in [ex.submit(a), ex.submit(b)]]

            got = httpx.get(f"{base}/v1/me", timeout=30.0).json().get("settings") or {}
            miss = []
            if got.get("language") != lang:
                miss.append(f"language({got.get('language')!r}≠{lang!r})")
            if (got.get("hotwords") or []) != [word]:
                miss.append(f"hotwords({got.get('hotwords')!r}≠{[word]!r})")
            if miss:
                lost.append({"round": r, "codes": codes, "lost": miss})

        return {
            "scenario": "settings-merge (P0-4)",
            "backend": backend,
            "rounds": rounds,
            "rounds_with_lost_update": len(lost),
            "detail": lost[:4],
            "reproduced": bool(lost),
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# --------------------------------------------------------------------------
# 시나리오 5: 수정이 정상 경로를 깨지 않았는지 (회귀)
# --------------------------------------------------------------------------

def scenario_smoke(backend: str, dsn: str, workdir: Path) -> dict:
    """버전 채번·설정 저장·내보내기의 정상 동작 확인. 여기서 실패하면 수정이 회귀를 냈다."""
    import httpx
    config, database, db, pipeline = _load_app(backend, dsn, workdir)
    mid, jid = _seed_meeting(config, database, db, title="회귀 확인용")

    # 버전 채번: 요약을 세 번 저장하면 1,2,3 이어야 한다(INSERT...SELECT 단일 문장)
    conn = db.connect()
    try:
        for i in range(3):
            db.store_summary_version(conn, mid, {"title": f"t{i}", "summary": "s",
                                                 "sections": [], "decisions": []},
                                     source="user", created_by=config.DEFAULT_USER_ID)
        versions = [r["version"] for r in conn.execute(
            "SELECT version FROM summary_versions WHERE meeting_id=? ORDER BY version",
            (mid,)).fetchall()]
    finally:
        conn.close()

    env = _env_for(backend, dsn, workdir)
    port = _free_port()
    proc, base = _start_server(env, port)
    assert_local_url(base)
    try:
        # 설정: 두 키를 순차로 저장하면 둘 다 남아야 한다
        httpx.patch(f"{base}/v1/me/settings", json={"language": "en"}, timeout=30.0)
        r2 = httpx.patch(f"{base}/v1/me/settings", json={"hotwords": ["킥오프"]}, timeout=30.0)
        saved = (r2.json() or {}).get("settings") or {}

        # 내보내기: 201 + 다운로드 200
        ex_res = httpx.post(f"{base}/v1/meetings/{mid}/exports",
                            json={"format": "md", "include_transcript": False}, timeout=60.0)
        dl = None
        if ex_res.status_code == 201:
            dl = httpx.get(base + (ex_res.json() or {}).get("download_url", ""), timeout=60.0).status_code
        exports_rows = _count(db, "SELECT COUNT(*) AS n FROM exports WHERE meeting_id=?", (mid,))

        ok = (versions == [1, 2, 3] and saved.get("language") == "en"
              and (saved.get("hotwords") or []) == ["킥오프"]
              and ex_res.status_code == 201 and dl == 200 and exports_rows == 1)
        return {
            "scenario": "smoke (수정 회귀 확인)",
            "backend": backend,
            "summary_versions": versions,
            "settings_after_two_patches": saved,
            "export_status": ex_res.status_code,
            "download_status": dl,
            "exports_rows": exports_rows,
            "all_ok": ok,
            "reproduced": not ok,      # 여기서는 'reproduced' = 회귀 발생
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# --------------------------------------------------------------------------
# 시나리오 10: 업로드 레이트리밋 (검사-후-사용)
# --------------------------------------------------------------------------

_RL_CAP = 5


def scenario_rate_limit(backend: str, dsn: str, workdir: Path, burst: int = 32) -> dict:
    """MAX_JOBS_PER_HOUR=5 로 띄우고 회의 생성을 병렬로 20건 쏜다.

    상한 검사가 별도 커넥션에서 세고 닫은 뒤 **업로드 전체를 사이에 두고** INSERT 하면,
    병렬 요청이 모두 상한 미달을 보고 통과해 상한을 넘긴다.
    거부된 요청의 스토리지 파일이 정리되는지도 함께 본다(고아 파일).
    """
    import httpx
    config, database, db, _pipeline = _load_app(backend, dsn, workdir)

    # postgres 는 DB 를 재사용하므로 앞선 시나리오의 jobs 가 상한 계산에 섞인다. 비우고 시작한다.
    conn = db.connect()
    try:
        for tbl in ("summary_sections", "summary_decisions", "action_items", "calendar_candidates"):
            conn.execute(f"DELETE FROM {tbl}")
        conn.execute("DELETE FROM notification_states")
        for tbl in ("jobs", "recording_files", "transcript_segments", "speaker_aliases",
                    "transcript_highlights", "share_links", "meeting_bookmarks",
                    "exports", "share_logs", "audit_logs", "summary_versions"):
            conn.execute(f"DELETE FROM {tbl}")
        conn.execute("DELETE FROM meetings")
        conn.commit()
    finally:
        conn.close()

    env = _env_for(backend, dsn, workdir, max_jobs=str(_RL_CAP))
    port = _free_port()
    proc, base = _start_server(env, port)
    assert_local_url(base)
    try:
        # 창을 실제 크기로 만든다. 프로덕션은 파일이 네트워크로 Supabase Storage 까지
        # 가므로 검사~INSERT 사이가 수백 ms~초다. 로컬에서 4KB 를 쓰면 마이크로초라
        # 창이 사실상 없어져 결함이 드러나지 않는다(실측: 4KB 로는 재현 안 됨).
        blob = b"x" * (6 * 1024 * 1024)

        def create(i):
            try:
                r = httpx.post(f"{base}/v1/jobs", timeout=120.0,
                               files={"audio_file": (f"a{i}.webm", blob, "audio/webm")},
                               data={"title": f"rl-{i}", "duration_ms": "180000",
                                     "recording_consent_confirmed": "true"})
                body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                err = ((body.get("detail") or {}).get("error") or body.get("error") or {})
                return r.status_code, err.get("code")
            except Exception as e:  # noqa: BLE001
                return None, type(e).__name__

        with ThreadPoolExecutor(max_workers=burst) as ex:
            results = list(ex.map(create, range(burst)))

        created = _count(db, "SELECT COUNT(*) AS n FROM jobs", ())
        meetings = _count(db, "SELECT COUNT(*) AS n FROM meetings", ())
        recs = _count(db, "SELECT COUNT(*) AS n FROM recording_files", ())
        ok = sum(1 for c, _ in results if c == 201)
        limited = sum(1 for c, code in results if c == 429 and code == "rate_limited")
        other = [r for r in results if r[0] not in (201, 429)]

        # 거부된 업로드의 파일이 남았는지 — 로컬 저장소 파일 수는 수락된 건수와 같아야 한다.
        storage_root = workdir / "storage"
        files = [f for f in storage_root.rglob("*") if f.is_file()] if storage_root.exists() else []

        problems = []
        if created != _RL_CAP:
            problems.append(f"jobs 행 {created}건 (상한 {_RL_CAP} 이어야 함)")
        if ok != _RL_CAP:
            problems.append(f"201 응답 {ok}건 (상한 {_RL_CAP} 이어야 함)")
        if meetings != _RL_CAP or recs != _RL_CAP:
            problems.append(f"거부된 요청의 행이 남았다: meetings={meetings} recording_files={recs}")
        if len(files) != _RL_CAP:
            problems.append(f"고아 스토리지 파일: {len(files)}개 (수락 {_RL_CAP}건과 같아야 함)")
        if other:
            problems.append(f"예상 밖 응답: {other[:3]}")

        return {
            "scenario": "rate-limit (상한 검사-후-사용)",
            "backend": backend,
            "cap": _RL_CAP,
            "burst": burst,
            "http_201": ok,
            "http_429": limited,
            "other": other[:3],
            "jobs_rows": created,
            "meetings_rows": meetings,
            "recording_files_rows": recs,
            "storage_files": len(files),
            "problems": problems,
            "reproduced": bool(problems),
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# --------------------------------------------------------------------------
# 시나리오 9: 폴더 이동 사이클 (교차 이동 경합)
# --------------------------------------------------------------------------

def scenario_folder_cycle(backend: str, dsn: str, workdir: Path, pairs: int = 20) -> dict:
    """A→B 와 B→A 이동을 동시에 쏜다.

    사이클 검사가 읽기 기반이면 두 요청이 서로의 커밋 전 상태를 못 봐 **둘 다 통과**하고,
    A.parent=B / B.parent=A 인 순환이 생긴다. 그 서브트리는 루트에서 도달할 수 없어
    폴더 화면에서 영원히 사라진다(_folder_descendant_ids 는 순환에 안전해 서버는 안 죽는다).

    창이 좁아 한 쌍으로는 잘 안 걸리므로 여러 쌍을 동시에 돌린다.
    """
    import httpx
    config, database, db, _pipeline = _load_app(backend, dsn, workdir)

    # 깨끗한 상태에서 시작한다. sqlite 는 실행마다 새 임시 DB 라 상관없지만 postgres 는
    # 같은 DB 를 재사용해서, 앞선 실행이 남긴 순환 폴더가 이번 판정에 섞여 들어온다
    # (실제로 수정 후에도 '재현됨' 으로 오판했다 — 하니스 쪽 거짓 양성이었다).
    conn = db.connect()
    try:
        conn.execute("UPDATE meetings SET folder_id=NULL WHERE user_id=?", (config.DEFAULT_USER_ID,))
        conn.execute("DELETE FROM folders WHERE user_id=?", (config.DEFAULT_USER_ID,))
        conn.commit()
    finally:
        conn.close()

    env = _env_for(backend, dsn, workdir)
    port = _free_port()
    proc, base = _start_server(env, port)
    assert_local_url(base)
    try:
        def mkfolder(name):
            r = httpx.post(f"{base}/v1/folders", json={"name": name}, timeout=30.0)
            return (r.json() or {}).get("id") if r.status_code in (200, 201) else None

        couples = []
        for i in range(pairs):
            a, b = mkfolder(f"A{i}"), mkfolder(f"B{i}")
            if a and b:
                couples.append((a, b))

        def move(args):
            fid, parent = args
            try:
                r = httpx.patch(f"{base}/v1/folders/{fid}", json={"parent_id": parent}, timeout=30.0)
                body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                err = ((body.get("detail") or {}).get("error") or body.get("error") or {})
                return r.status_code, err.get("code")
            except Exception as e:  # noqa: BLE001
                return None, type(e).__name__

        # 각 쌍의 두 이동을 동시에. 쌍끼리도 동시에 돌려 창을 넓힌다.
        jobs = []
        for a, b in couples:
            jobs.append((a, b))
            jobs.append((b, a))
        with ThreadPoolExecutor(max_workers=min(32, len(jobs) or 1)) as ex:
            results = list(ex.map(move, jobs))

        # 사이클 검출: parent 를 따라 올라가다 자기 자신을 다시 만나면 순환이다.
        conn = db.connect()
        try:
            rows = conn.execute("SELECT id, parent_id FROM folders WHERE user_id=?",
                                (config.DEFAULT_USER_ID,)).fetchall()
        finally:
            conn.close()
        parent = {str(r["id"]): (str(r["parent_id"]) if r["parent_id"] else None) for r in rows}
        cycles = set()
        for fid in parent:
            seen, cur = set(), fid
            while cur is not None:
                if cur in seen:
                    cycles.add(cur)
                    break
                seen.add(cur)
                cur = parent.get(cur)

        ok = sum(1 for c, _ in results if c == 200)
        conflict = sum(1 for c, code in results if c == 409 and code == "folder_cycle")
        return {
            "scenario": "folder-cycle (교차 이동)",
            "backend": backend,
            "pairs": len(couples),
            "moves_sent": len(jobs),
            "http_200": ok,
            "http_409_folder_cycle": conflict,
            "other": [r for r in results if r[0] not in (200, 409)][:5],
            "folders_in_cycle": len(cycles),
            "reproduced": bool(cycles),
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# --------------------------------------------------------------------------
# 시나리오 8: 나머지 수정 묶음 (겹침 하이라이트 · 공유링크 상한 · 비uuid id · purge 순서)
# --------------------------------------------------------------------------

def scenario_misc(backend: str, dsn: str, workdir: Path) -> dict:
    """P1 잔여 항목들의 회귀 확인.

    - 겹치는 하이라이트는 409 로 거부돼야 한다(예전엔 저장되고 렌더에서 스킵돼
      UI 로 지울 수 없는 고아 행이 됐다).
    - 공유 링크 20개 상한은 병렬 생성에서도 지켜져야 한다(검사-후-사용 → 단일 문장).
    - 형식이 잘못된 id 는 404 여야 한다(postgres 에서 500 이었다).
    - purge 는 DB 커밋 뒤 파일을 지운다 — 정상 경로에서 둘 다 사라져야 한다.
    """
    import httpx
    config, database, db, pipeline = _load_app(backend, dsn, workdir)
    mid, jid = _seed_meeting(config, database, db, title="잔여 수정 확인용")
    pipeline.run_pipeline(jid, mid)          # 세그먼트 12개 생성

    env = _env_for(backend, dsn, workdir)
    port = _free_port()
    proc, base = _start_server(env, port)
    assert_local_url(base)
    try:
        def code(method, path, **kw):
            r = httpx.request(method, base + path, timeout=60.0, **kw)
            body = {}
            if r.headers.get("content-type", "").startswith("application/json"):
                try:
                    body = r.json()
                except Exception:  # noqa: BLE001
                    body = {}
            err = ((body.get("detail") or {}).get("error") or body.get("error") or {})
            return r.status_code, err.get("code"), body

        # --- 겹치는 하이라이트 ---
        segs = httpx.get(f"{base}/v1/meetings/{mid}/segments", timeout=30.0)
        seg_id, seg_len = None, 0
        if segs.status_code == 200:
            items = (segs.json() or {}).get("items") or []
            # 오프셋이 본문 길이를 넘으면 422 라, 충분히 긴 발화를 고른다.
            for it in items:
                text = it.get("corrected_text") or it.get("text") or ""
                if len(text) >= 10:
                    seg_id, seg_len = it["segment_id"], len(text)
                    break
        hl = {}
        if seg_id:
            hl["first"] = code("POST", f"/v1/meetings/{mid}/highlights",
                               json={"segment_id": seg_id, "start_offset": 0, "end_offset": 5})[:2]
            hl["overlap"] = code("POST", f"/v1/meetings/{mid}/highlights",
                                 json={"segment_id": seg_id, "start_offset": 3, "end_offset": 8})[:2]
            hl["adjacent_ok"] = code("POST", f"/v1/meetings/{mid}/highlights",
                                     json={"segment_id": seg_id, "start_offset": 5, "end_offset": 9})[:2]

        # --- 공유 링크 상한: 25개 병렬 생성 → 정확히 20개만 ---
        def mk(_i):
            return code("POST", f"/v1/meetings/{mid}/share-links", json={"expires_in_days": 30})[0]
        with ThreadPoolExecutor(max_workers=25) as ex:
            codes = list(ex.map(mk, range(25)))
        created = _count(
            db, "SELECT COUNT(*) AS n FROM share_links WHERE meeting_id=? AND revoked_at IS NULL",
            (mid,))

        # --- 형식이 잘못된 id ---
        bad = {
            "GET /meetings/<bad>": code("GET", "/v1/meetings/not-a-uuid")[0],
            "POST /exports/<bad>": code("POST", "/v1/meetings/not-a-uuid/exports",
                                        json={"format": "md", "include_transcript": False})[0],
        }

        # --- purge: soft-delete 후 영구삭제하면 행도 파일도 사라져야 한다 ---
        files_before = _count(
            db, "SELECT COUNT(*) AS n FROM recording_files WHERE meeting_id=?", (mid,))
        code("DELETE", f"/v1/meetings/{mid}")            # soft delete
        purge = code("DELETE", f"/v1/meetings/{mid}/purge")[0]
        rows_after = _count(db, "SELECT COUNT(*) AS n FROM meetings WHERE id=?", (mid,))
        seg_after = _count(
            db, "SELECT COUNT(*) AS n FROM transcript_segments WHERE meeting_id=?", (mid,))

        problems = []
        if seg_id:
            if hl["first"][0] != 201:
                problems.append(f"첫 하이라이트가 201 이 아님: {hl['first']}")
            if not (hl["overlap"][0] == 409 and hl["overlap"][1] == "highlight_overlap"):
                problems.append(f"겹침이 409 로 거부되지 않음: {hl['overlap']}")
            if hl["adjacent_ok"][0] != 201:
                problems.append(f"인접(비겹침)이 거부됨: {hl['adjacent_ok']}")
        else:
            problems.append("10자 이상 발화를 못 찾아 하이라이트 검사를 못 함")
        if created != 20:
            problems.append(f"공유 링크 상한 초과/미달: {created} (20 이어야 함)")
        for k, v in bad.items():
            if v == 500:
                problems.append(f"{k} 가 500 (404 여야 함)")
        if purge != 200 or rows_after != 0 or seg_after != 0:
            problems.append(f"purge 정상 경로 실패: status={purge} rows={rows_after} seg={seg_after}")

        return {
            "scenario": "misc (P1 잔여 수정)",
            "backend": backend,
            "highlight": hl,
            "segment_text_len": seg_len,
            "share_link_parallel_25_created": created,
            "share_link_status_codes": {str(c): codes.count(c) for c in set(codes)},
            "invalid_id_status": bad,
            "recording_files_before_purge": files_before,
            "purge_status": purge,
            "rows_after_purge": rows_after,
            "segments_after_purge": seg_after,
            "problems": problems,
            "reproduced": bool(problems),
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# --------------------------------------------------------------------------
# 시나리오 7: 요약 저장 낙관적 잠금
# --------------------------------------------------------------------------

def scenario_summary_lock(backend: str, dsn: str, workdir: Path) -> dict:
    """같은 base_version 으로 두 개의 요약 저장을 동시에 쏜다.

    낙관적 잠금이 있으면 하나만 200 이고 나머지는 409 summary_conflict 여야 한다.
    둘 다 200 이면 나중 것이 앞 편집을 덮어쓴 것이다(공용 계정이라 남의 편집이 사라진다).
    base_version 없이 보내면 예전처럼 통과해야 한다(구 클라이언트 호환).
    """
    import httpx
    config, database, db, pipeline = _load_app(backend, dsn, workdir)
    mid, jid = _seed_meeting(config, database, db, title="요약 잠금 재현용")
    pipeline.run_pipeline(jid, mid)          # v1(ai) 생성

    env = _env_for(backend, dsn, workdir)
    port = _free_port()
    proc, base = _start_server(env, port)
    assert_local_url(base)
    url = f"{base}/v1/meetings/{mid}/summary"
    try:
        cur = httpx.get(f"{base}/v1/meetings/{mid}/summary", timeout=30.0)
        start_version = (cur.json() or {}).get("version") if cur.status_code == 200 else None

        def save(tag, base_version):
            body = {"title": f"제목-{tag}", "summary": f"본문-{tag}",
                    "decisions": [], "action_items": [], "calendar_candidates": []}
            if base_version is not None:
                body["base_version"] = base_version
            try:
                r = httpx.patch(url, json=body, timeout=60.0)
                d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                err = (d.get("error") or {})
                return {"tag": tag, "status": r.status_code,
                        "code": err.get("code"), "version": d.get("version"),
                        "current_version": (err.get("details") or {}).get("current_version")}
            except Exception as e:  # noqa: BLE001
                return {"tag": tag, "status": None, "code": type(e).__name__}

        # 두 '탭'이 같은 base 에서 동시에 저장
        with ThreadPoolExecutor(max_workers=2) as ex:
            results = list(ex.map(lambda t: save(t, start_version), ["A", "B"]))
        ok = [r for r in results if r["status"] == 200]
        conflict = [r for r in results if r["status"] == 409 and r["code"] == "summary_conflict"]

        # 최신 버전 = 이긴 쪽의 내용이어야 한다(진 쪽이 덮어쓰지 못했는지)
        after = httpx.get(f"{base}/v1/meetings/{mid}/summary", timeout=30.0).json()
        winner = ok[0]["tag"] if len(ok) == 1 else None
        stored_matches_winner = (winner is not None
                                 and (after.get("title") or "").endswith(winner))

        # 구 클라이언트 호환: base_version 없이 보내면 통과
        legacy = save("LEGACY", None)

        return {
            "scenario": "summary-lock (낙관적 잠금)",
            "backend": backend,
            "start_version": start_version,
            "concurrent": results,
            "http_200": len(ok),
            "http_409_conflict": len(conflict),
            "stored_title_after": after.get("title"),
            "stored_matches_winner": stored_matches_winner,
            "legacy_no_base_version": legacy,
            "reproduced": not (len(ok) == 1 and len(conflict) == 1
                               and stored_matches_winner and legacy["status"] == 200),
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# --------------------------------------------------------------------------
# 시나리오 6: 인증 게이트 (WRITE_PROTECTED=1 프로덕션 구성)
# --------------------------------------------------------------------------

def scenario_gates(backend: str, dsn: str, workdir: Path) -> dict:
    """프로덕션과 같은 WRITE_PROTECTED=1 로 띄워 게이트를 실측한다.

    정책(config.py): "읽기·업로드만 열리고 수정·삭제는 401".
      업로드 계열(jobs·presign)과 파생 산출물(exports)은 **열려 있어야** 하고,
      파괴적 재처리(retry)와 수정·삭제는 **401** 이어야 한다.
    """
    import httpx
    config, database, db, pipeline = _load_app(backend, dsn, workdir)
    mid, jid = _seed_meeting(config, database, db, title="게이트 확인용")
    pipeline.run_pipeline(jid, mid)          # 내보내기에 요약이 필요하다

    env = _env_for(backend, dsn, workdir, write_protected="1")
    port = _free_port()
    proc, base = _start_server(env, port)
    assert_local_url(base)
    try:
        def code(method, path, **kw):
            r = httpx.request(method, base + path, timeout=60.0, **kw)
            body = {}
            if r.headers.get("content-type", "").startswith("application/json"):
                try:
                    body = r.json()
                except Exception:  # noqa: BLE001
                    body = {}
            err = ((body.get("detail") or {}).get("error") or body.get("error") or {})
            return r.status_code, err.get("code")

        # 열려 있어야 하는 것 (401 이면 데모가 죽는다)
        must_open = {
            "POST /jobs": code("POST", "/v1/jobs", data={"title": "x"}),
            "POST /uploads/presign": code("POST", "/v1/uploads/presign",
                                          json={"filename": "a.webm"}),
            "POST /exports": code("POST", f"/v1/meetings/{mid}/exports",
                                  json={"format": "md", "include_transcript": False}),
        }
        # 401 이어야 하는 것
        must_block = {
            "POST /retry": code("POST", f"/v1/meetings/{mid}/retry", json={}),
            "DELETE /meetings/{id}": code("DELETE", f"/v1/meetings/{mid}"),   # 대조군
            "PATCH /meetings/{id}/summary": code("PATCH", f"/v1/meetings/{mid}/summary",
                                                 json={"summary": "x"}),
        }
        wrongly_blocked = {k: v for k, v in must_open.items() if v[0] == 401}
        wrongly_open = {k: v for k, v in must_block.items() if v[0] != 401}
        return {
            "scenario": "gates (WRITE_PROTECTED=1)",
            "backend": backend,
            "must_stay_open": must_open,
            "must_return_401": must_block,
            "wrongly_blocked": wrongly_blocked,
            "wrongly_open": wrongly_open,
            "reproduced": bool(wrongly_blocked or wrongly_open),
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# --------------------------------------------------------------------------

def _report(res: dict) -> bool:
    print("\n" + "=" * 74)
    print(f"  {res['scenario']}   backend={res['backend']}")
    print("=" * 74)
    for k, v in res.items():
        if k in ("scenario", "backend", "reproduced"):
            continue
        print(f"  {k:34} {json.dumps(v, ensure_ascii=False, default=str)}")
    verdict = "재현됨 — 결함 존재" if res["reproduced"] else "미검출"
    print(f"  {'>>> 판정':34} {verdict}")
    return res["reproduced"]


def _run_child(sub: str, backend: str, args) -> dict:
    """백엔드별로 별도 프로세스에서 실행하고 결과 JSON 을 회수한다."""
    cmd = [sys.executable, __file__, sub, "--backend", backend,
           "--pg-dsn", args.pg_dsn, "--json"]
    if sub == "share-lockout":
        cmd += ["--burst", str(args.burst)]
    if sub == "settings-merge":
        cmd += ["--rounds", str(args.rounds)]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))
    if p.returncode == 2:
        print(p.stdout, file=sys.stderr)
        die(f"자식 프로세스 실패({sub}/{backend}):\n{p.stderr[-2000:]}")
    for line in reversed(p.stdout.strip().splitlines()):
        if line.startswith("{"):
            return json.loads(line)
    die(f"자식 프로세스 결과를 못 읽었다({sub}/{backend}):\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["init-schema", "abort-swallow", "share-lockout",
                                        "retry-lock", "settings-merge", "smoke",
                                        "gates", "summary-lock", "misc",
                                        "folder-cycle", "rate-limit", "all"])
    ap.add_argument("--pg-dsn", default=os.getenv("REPRO_PG_DSN", ""),
                    help="로컬 Postgres DSN (비로컬은 거부됨)")
    ap.add_argument("--backend", choices=["postgres", "sqlite"], default="postgres")
    ap.add_argument("--burst", type=int, default=60, help="병렬 요청 수 (share-lockout)")
    ap.add_argument("--rounds", type=int, default=8, help="라운드 수 (settings-merge)")
    ap.add_argument("--json", action="store_true", help="결과 JSON 한 줄만 출력")
    ap.add_argument("--keep", action="store_true", help="임시 작업 디렉터리 보존")
    args = ap.parse_args()

    if args.command == "init-schema":
        assert_local_dsn(args.pg_dsn)
        import psycopg
        sql = (REPO / "app" / "sql" / "schema_postgres.sql").read_text(encoding="utf-8")
        with psycopg.connect(args.pg_dsn, autocommit=True) as c:
            c.execute(sql)
            n = c.execute("SELECT count(*) FROM information_schema.tables "
                          "WHERE table_schema='public'").fetchone()[0]
        print(f"스키마 적용 완료 — public 테이블 {n}개")
        return 0

    if args.backend == "postgres" or args.command == "all":
        assert_local_dsn(args.pg_dsn)

    if args.command == "all":
        # P0-1 은 두 백엔드를 대조해야 'Postgres 전용' 이라는 주장이 증명된다.
        results = [
            _run_child("abort-swallow", "postgres", args),
            _run_child("abort-swallow", "sqlite", args),
            _run_child("share-lockout", "postgres", args),
            _run_child("retry-lock", "postgres", args),
            _run_child("settings-merge", "postgres", args),
            _run_child("smoke", "postgres", args),
            _run_child("smoke", "sqlite", args),
            _run_child("gates", "postgres", args),
            _run_child("summary-lock", "postgres", args),
            _run_child("summary-lock", "sqlite", args),
            _run_child("misc", "postgres", args),
            _run_child("misc", "sqlite", args),
            _run_child("folder-cycle", "postgres", args),
            _run_child("folder-cycle", "sqlite", args),
            _run_child("rate-limit", "postgres", args),
            _run_child("rate-limit", "sqlite", args),
        ]
        any_repro = False
        for r in results:
            any_repro |= _report(r)
        print("\n" + "-" * 74)
        pg = next(r for r in results if r["scenario"].startswith("abort") and r["backend"] == "postgres")
        lite = next(r for r in results if r["scenario"].startswith("abort") and r["backend"] == "sqlite")
        print("  백엔드 대조 (P0-1):")
        print(f"    postgres → job status={pg['run2_status']['job']!r}, "
              f"pipeline_failed audit={pg['pipeline_failed_audits']}, 재현={pg['reproduced']}")
        print(f"    sqlite   → job status={lite['run2_status']['job']!r}, "
              f"pipeline_failed audit={lite['pipeline_failed_audits']}, 재현={lite['reproduced']}")
        if pg["reproduced"] and not lite["reproduced"]:
            print("    ⇒ Postgres 전용 결함으로 확인. 로컬 SQLite 검증으로는 잡히지 않는다.")
        print("-" * 74)
        return 1 if any_repro else 0

    workdir = Path(tempfile.mkdtemp(prefix="repro-races-"))
    try:
        if args.command == "abort-swallow":
            res = scenario_abort_swallow(args.backend, args.pg_dsn, workdir)
        elif args.command == "retry-lock":
            res = scenario_retry_lock(args.backend, args.pg_dsn, workdir)
        elif args.command == "settings-merge":
            res = scenario_settings_merge(args.backend, args.pg_dsn, workdir, rounds=args.rounds)
        elif args.command == "smoke":
            res = scenario_smoke(args.backend, args.pg_dsn, workdir)
        elif args.command == "gates":
            res = scenario_gates(args.backend, args.pg_dsn, workdir)
        elif args.command == "summary-lock":
            res = scenario_summary_lock(args.backend, args.pg_dsn, workdir)
        elif args.command == "misc":
            res = scenario_misc(args.backend, args.pg_dsn, workdir)
        elif args.command == "folder-cycle":
            res = scenario_folder_cycle(args.backend, args.pg_dsn, workdir)
        elif args.command == "rate-limit":
            res = scenario_rate_limit(args.backend, args.pg_dsn, workdir)
        else:
            res = scenario_share_lockout(args.backend, args.pg_dsn, workdir, burst=args.burst)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, default=str))
        else:
            _report(res)
        return 1 if res["reproduced"] else 0
    finally:
        if not args.keep:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
