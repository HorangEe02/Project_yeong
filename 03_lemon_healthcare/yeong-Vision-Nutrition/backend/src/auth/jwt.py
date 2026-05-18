"""JWT access / refresh token 발급 + 검증.

Refresh token 무효화(blacklist)는 Phase 05 service 레이어가 Redis 에서 처리한다.
본 모듈은 토큰 인코딩 / 디코딩 + payload 구조 정의만 담당.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-05-api-integration.md Step 2
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import jwt as pyjwt

from src.config import Settings, get_settings


class InvalidTokenError(Exception):
    """JWT 디코드 / 서명 검증 / 만료 검사 실패."""


@dataclass(frozen=True)
class TokenPayload:
    """디코드된 JWT payload."""

    sub: str
    """user_id (UUID string)."""

    jti: str
    """Token 식별자. blacklist key 로 사용."""

    exp: int
    """Unix epoch seconds."""

    typ: Literal["access", "refresh"]


def _now_epoch() -> int:
    return int(datetime.now(UTC).timestamp())


def _encode(
    *,
    user_id: str,
    typ: Literal["access", "refresh"],
    ttl_seconds: int,
    settings: Settings,
) -> tuple[str, str]:
    """내부 인코딩 헬퍼."""
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": user_id,
        "jti": jti,
        "exp": _now_epoch() + ttl_seconds,
        "typ": typ,
    }
    token = pyjwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, jti


def encode_access(user_id: str, settings: Settings | None = None) -> tuple[str, str]:
    """Access token 발급.

    Args:
        user_id: 토큰의 ``sub`` 클레임으로 들어갈 UUID 문자열.
        settings: 의존성 주입용 ``Settings``. ``None`` 이면 싱글턴.

    Returns:
        ``(token, jti)``.
    """
    s = settings or get_settings()
    return _encode(
        user_id=user_id,
        typ="access",
        ttl_seconds=s.access_token_ttl_minutes * 60,
        settings=s,
    )


def encode_refresh(user_id: str, settings: Settings | None = None) -> tuple[str, str]:
    """Refresh token 발급."""
    s = settings or get_settings()
    return _encode(
        user_id=user_id,
        typ="refresh",
        ttl_seconds=s.refresh_token_ttl_days * 86400,
        settings=s,
    )


def decode_token(token: str, settings: Settings | None = None) -> TokenPayload:
    """JWT 를 디코드하고 서명·만료를 검증한다.

    Args:
        token: 인코딩된 JWT.
        settings: 의존성 주입용.

    Returns:
        ``TokenPayload``.

    Raises:
        InvalidTokenError: 디코드 / 서명 / 만료 실패.
    """
    s = settings or get_settings()
    try:
        data = pyjwt.decode(
            token,
            s.jwt_secret_key.get_secret_value(),
            algorithms=[s.jwt_algorithm],
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("Token expired") from exc
    except pyjwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    typ = data.get("typ")
    if typ not in ("access", "refresh"):
        raise InvalidTokenError(f"Invalid token typ: {typ!r}")
    return TokenPayload(
        sub=str(data["sub"]),
        jti=str(data["jti"]),
        exp=int(data["exp"]),
        typ=typ,
    )
