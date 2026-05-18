"""``src.auth.jwt`` 단위 테스트."""

from __future__ import annotations

import time
import uuid
from unittest.mock import patch

import pytest
from src.auth.jwt import (
    InvalidTokenError,
    decode_token,
    encode_access,
    encode_refresh,
)
from src.config import get_settings


def test_encode_access_then_decode_round_trip() -> None:
    settings = get_settings()
    user_id = str(uuid.uuid4())
    token, jti = encode_access(user_id, settings)
    payload = decode_token(token, settings)
    assert payload.sub == user_id
    assert payload.jti == jti
    assert payload.typ == "access"
    assert payload.exp > int(time.time())


def test_encode_refresh_decode_round_trip() -> None:
    settings = get_settings()
    user_id = str(uuid.uuid4())
    token, _ = encode_refresh(user_id, settings)
    payload = decode_token(token, settings)
    assert payload.typ == "refresh"


def test_invalid_signature_raises() -> None:
    settings = get_settings()
    token, _ = encode_access(str(uuid.uuid4()), settings)
    # 토큰의 마지막 문자를 변조해 서명을 깨뜨림
    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    with pytest.raises(InvalidTokenError):
        decode_token(tampered, settings)


def test_garbage_token_raises() -> None:
    with pytest.raises(InvalidTokenError):
        decode_token("not-a-jwt-at-all", get_settings())


def test_expired_token_raises() -> None:
    """``access_token_ttl_minutes`` 를 잠시 -1 로 만들어 만료 토큰 발급."""
    settings = get_settings()
    user_id = str(uuid.uuid4())
    # 음수 TTL 로 즉시 만료
    with patch.object(settings, "access_token_ttl_minutes", -1):
        token, _ = encode_access(user_id, settings)
    with pytest.raises(InvalidTokenError):
        decode_token(token, settings)


def test_access_and_refresh_have_different_jti() -> None:
    settings = get_settings()
    user_id = str(uuid.uuid4())
    _, jti_a = encode_access(user_id, settings)
    _, jti_r = encode_refresh(user_id, settings)
    assert jti_a != jti_r
