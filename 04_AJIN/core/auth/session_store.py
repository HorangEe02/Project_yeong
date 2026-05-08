"""v2.4.1: 서버 사이드 세션 저장소 — 새로고침 시 세션 유지

브라우저 쿠키의 session_id → 서버 파일에서 JWT 토큰을 조회하여
st.session_state를 복원한다. Streamlit의 WebSocket 초기화 문제를 우회.

흐름:
1. 로그인 성공 → session_id 생성 → 서버 파일에 JWT 저장 → 쿠키에 session_id 설정
2. 새로고침 → st.context.headers에서 Cookie 읽기 → session_id 추출 → 파일에서 JWT 로드 → 검증 → 복원
3. 로그아웃 → 서버 파일 삭제 → 쿠키 삭제
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path

SESSION_DIR = Path(__file__).parent.parent.parent / "data" / ".sessions"
SESSION_COOKIE_NAME = "ajin_sid"
SESSION_MAX_AGE_HOURS = 24


def create_session(jwt_token: str, employee_id: str) -> str:
    """새 세션을 생성하고 session_id를 반환한다."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    session_id = secrets.token_urlsafe(32)
    session_data = {
        "jwt_token": jwt_token,
        "employee_id": employee_id,
        "created_at": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(hours=SESSION_MAX_AGE_HOURS)).isoformat(),
    }

    session_file = SESSION_DIR / f"{session_id}.json"
    session_file.write_text(json.dumps(session_data), encoding="utf-8")

    # 오래된 세션 정리 (24시간 초과)
    _cleanup_expired_sessions()

    return session_id


def load_session(session_id: str) -> str | None:
    """session_id로 JWT 토큰을 로드한다. 만료/없으면 None."""
    if not session_id:
        return None

    session_file = SESSION_DIR / f"{session_id}.json"
    if not session_file.exists():
        return None

    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
        expires = datetime.fromisoformat(data["expires_at"])
        if datetime.now() > expires:
            session_file.unlink(missing_ok=True)
            return None
        return data.get("jwt_token")
    except Exception:
        session_file.unlink(missing_ok=True)
        return None


def delete_session(session_id: str):
    """세션을 삭제한다."""
    if not session_id:
        return
    session_file = SESSION_DIR / f"{session_id}.json"
    session_file.unlink(missing_ok=True)


def get_session_id_from_cookies(headers: dict | None = None) -> str:
    """HTTP 헤더에서 쿠키를 파싱하여 session_id를 추출한다.

    방법 1: st.context.headers["Cookie"] (Streamlit 1.37+)
    방법 2: 외부 전달 headers dict

    v3.3: 폴백(최근 세션 파일 자동 로드) 제거 — 쿠키 없으면 로그인 필요.
    기존 폴백은 단일 사용자 개발 환경용이었으나, 다중 사용자 환경에서
    다른 사용자가 이전 세션(예: admin)으로 자동 인증되는 보안 문제 유발.
    """
    import logging
    _log = logging.getLogger("ajin.auth")

    cookie_header = ""

    # 방법 1: st.context.headers
    try:
        import streamlit as st
        cookie_header = st.context.headers.get("Cookie", "")
        if cookie_header:
            _log.info(f"[쿠키읽기] st.context.headers Cookie 발견 ({len(cookie_header)}자)")
    except Exception as e:
        _log.warning(f"[쿠키읽기] st.context.headers 실패: {e}")

    # 방법 2: 외부 headers
    if not cookie_header and headers:
        cookie_header = headers.get("Cookie", headers.get("cookie", ""))

    # 쿠키에서 session_id 파싱
    if cookie_header:
        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith(f"{SESSION_COOKIE_NAME}="):
                sid = part.split("=", 1)[1].strip()
                if sid:
                    _log.info(f"[쿠키읽기] session_id 추출 성공: {sid[:20]}...")
                    return sid

    # 쿠키에 session_id 없음 → 로그인 페이지로 이동해야 함
    _log.info("[쿠키읽기] 쿠키에서 session_id를 찾지 못함 → 로그인 필요")
    return ""


def _get_latest_session_id() -> str:
    """[DEPRECATED v3.3] 더 이상 사용하지 않음. 보안 문제로 폴백 제거됨.
    가장 최근에 생성된 유효한 세션 파일의 ID를 반환한다."""
    import logging
    _log = logging.getLogger("ajin.auth")

    if not SESSION_DIR.exists():
        return ""

    import json
    from datetime import datetime

    latest_file = None
    latest_time = None

    for f in SESSION_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            expires = datetime.fromisoformat(data["expires_at"])
            if datetime.now() > expires:
                f.unlink(missing_ok=True)
                continue
            created = datetime.fromisoformat(data["created_at"])
            if latest_time is None or created > latest_time:
                latest_time = created
                latest_file = f
        except Exception:
            continue

    if latest_file:
        sid = latest_file.stem
        _log.info(f"[쿠키읽기] 폴백: 최근 세션 파일 사용 {sid[:20]}...")
        return sid

    return ""


def _cleanup_expired_sessions():
    """만료된 세션 파일을 정리한다."""
    if not SESSION_DIR.exists():
        return
    now = datetime.now()
    for f in SESSION_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            expires = datetime.fromisoformat(data["expires_at"])
            if now > expires:
                f.unlink(missing_ok=True)
        except Exception:
            f.unlink(missing_ok=True)
