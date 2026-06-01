"""JWT 토큰 생성/검증 — PyJWT 기반"""

import secrets
from datetime import datetime, timedelta, timezone

# v2.2.1: JWT 비밀키를 파일 기반으로 영속화 — 새로고침해도 동일한 키 사용
import os
from pathlib import Path as _Path

_SECRET_PATH = _Path(__file__).parent.parent.parent / "data" / ".jwt_secret"


def _load_or_create_secret() -> str:
    """JWT 시크릿을 파일에서 로드하거나, 없으면 새로 생성한다."""
    env_secret = os.environ.get("AJIN_JWT_SECRET")
    if env_secret:
        return env_secret
    try:
        if _SECRET_PATH.exists():
            return _SECRET_PATH.read_text(encoding="utf-8").strip()
        _SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
        secret = secrets.token_hex(32)
        _SECRET_PATH.write_text(secret, encoding="utf-8")
        return secret
    except Exception:
        return secrets.token_hex(32)


JWT_SECRET = _load_or_create_secret()
JWT_ALGORITHM = "HS256"
JWT_ACCESS_EXPIRE_MINUTES = int(os.environ.get("JWT_ACCESS_EXPIRE_MINUTES", "15"))
JWT_EXPIRE_HOURS = 24
JWT_REFRESH_EXPIRE_DAYS = 7


def create_access_token(
    employee_id: str,
    username: str,
    role_name: str,
    role_level: int,
    expires_hours: int | None = None,
    expires_minutes: int | None = None,
) -> str:
    """액세스 토큰을 생성한다."""
    # SEC-P0: PyJWT 필수 — 무서명 폴백 토큰 제거
    import jwt

    if expires_hours is not None:
        expires_delta = timedelta(hours=expires_hours)
    else:
        expires_delta = timedelta(minutes=expires_minutes or JWT_ACCESS_EXPIRE_MINUTES)

    payload = {
        "sub": employee_id,
        "username": username,
        "role": role_name,
        "role_level": role_level,
        "exp": datetime.now(timezone.utc) + expires_delta,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def mint_from_idp(
    employee_id: str,
    username: str,
    role_name: str,
    role_level: int,
    idp_subject: str,
    idp_name: str = "oidc",
    expires_hours: int | None = None,
    expires_minutes: int | None = None,
) -> str:
    """v4.7 Feature E — 외부 IdP 인증 결과로 JWT 발급.

    일반 `create_access_token` 과 동일한 페이로드 + IdP 메타 claim.
    감사 로그에서 IdP 발급 토큰을 식별할 수 있도록 `idp` claim 포함.
    """
    import jwt

    if expires_hours is not None:
        expires_delta = timedelta(hours=expires_hours)
    else:
        expires_delta = timedelta(minutes=expires_minutes or JWT_ACCESS_EXPIRE_MINUTES)

    payload = {
        "sub": employee_id,
        "username": username,
        "role": role_name,
        "role_level": role_level,
        "exp": datetime.now(timezone.utc) + expires_delta,
        "iat": datetime.now(timezone.utc),
        "type": "access",
        "idp": idp_name,
        "idp_sub": idp_subject,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def mint_mid_token(employee_id: str, ttl_seconds: int = 60) -> str:
    """v4.7 Feature E Phase 2 — 2FA 중간 토큰.

    1차 로그인 (id/pw 통과) 후 2FA 코드 검증 대기용. TTL 60초.
    이 토큰은 `2fa_required=true, mid=true` claim 으로 식별되며,
    오직 `POST /auth/2fa/verify` 에서만 소비된다.
    """
    import jwt

    payload = {
        "sub": employee_id,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        "iat": datetime.now(timezone.utc),
        "type": "mid",
        "mid": True,
        "2fa_required": True,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(employee_id: str, jti: str | None = None) -> str:
    """리프레시 토큰을 생성한다."""
    try:
        import jwt
    except ImportError:
        return secrets.token_hex(32)

    payload = {
        "sub": employee_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_REFRESH_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "jti": jti or secrets.token_urlsafe(24),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict | None:
    """토큰을 검증하고 페이로드를 반환한다. 실패 시 None.
    SEC-P0: 무서명 폴백 제거 — PyJWT 서명 검증만 허용.
    """
    try:
        import jwt
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        return None


# SEC-P0: 폴백 토큰 함수 제거됨 (무서명 base64 토큰은 위조 가능)
def _fallback_verify(token: str) -> dict | None:
    """[DEPRECATED] 더 이상 사용되지 않음. 항상 None 반환."""
    return None


def _fallback_token(*args, **kwargs) -> str:
    """[DEPRECATED] 더 이상 사용되지 않음."""
    raise ImportError("PyJWT is required. Install: pip install PyJWT")
