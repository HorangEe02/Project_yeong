"""Server-side refresh-token allowlist and rotation helpers."""

from __future__ import annotations

from core.auth.jwt_handler import JWT_REFRESH_EXPIRE_DAYS, create_refresh_token, verify_token
from core.auth.session_store import get_session_store

REFRESH_SESSION_PREFIX = "refresh:"


def _refresh_key(jti: str) -> str:
    return f"{REFRESH_SESSION_PREFIX}{jti}"


def issue_refresh_session(employee_id: str) -> str:
    """Issue and allowlist a refresh JWT.

    Args:
        employee_id: AJIN employee id used as the refresh token subject.

    Returns:
        str: Signed refresh JWT with a unique ``jti`` claim.
    """

    refresh_token = create_refresh_token(employee_id)
    payload = verify_token(refresh_token) or {}
    jti = str(payload.get("jti") or "")
    if not jti:
        raise RuntimeError("refresh token missing jti")
    ttl_seconds = JWT_REFRESH_EXPIRE_DAYS * 24 * 60 * 60
    get_session_store().put(_refresh_key(jti), refresh_token, employee_id, ttl_seconds)
    return refresh_token


def refresh_session_is_active(refresh_token: str) -> bool:
    """Return whether a refresh JWT is valid and still allowlisted."""

    payload = verify_token(refresh_token) or {}
    if payload.get("type") != "refresh":
        return False
    jti = str(payload.get("jti") or "")
    if not jti:
        return False
    return get_session_store().get(_refresh_key(jti)) == refresh_token


def revoke_refresh_session(refresh_token: str | None) -> None:
    """Remove a refresh JWT from the server-side allowlist if possible."""

    if not refresh_token:
        return
    payload = verify_token(refresh_token) or {}
    jti = str(payload.get("jti") or "")
    if jti:
        get_session_store().delete(_refresh_key(jti))


def rotate_refresh_session(refresh_token: str, employee_id: str) -> str:
    """Revoke the old refresh JWT and issue a new allowlisted one."""

    revoke_refresh_session(refresh_token)
    return issue_refresh_session(employee_id)
