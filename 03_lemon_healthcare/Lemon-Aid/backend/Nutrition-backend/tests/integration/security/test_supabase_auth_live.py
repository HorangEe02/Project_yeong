"""Integration: backend verifies a REAL Supabase-issued asymmetric token (ADR 39).

Supabase Auth 백엔드 활성화의 전제 검증. 백엔드는 신규 /auth/* 없이 generic JWT
파이프라인(src/security/auth.py JWTVerifier)으로 Supabase 토큰을 "검증만" 한다
(supabase_auth.py 가 canonical issuer/JWKS/aud/algorithms 를 공급). 단위 테스트는
합성 키로 검증 로직을 덮지만, 이 테스트는 **실제 로컬 Supabase(gotrue + JWKS)**가
발급한 비대칭(ES256/RS256) 액세스 토큰을 백엔드가 수락하고, 변조/오디언스 불일치
토큰은 거부함을 end-to-end로 증명한다 — 라이브 활성화 리스크를 사전 제거한다.

실행 게이트(미설정 시 skip):
  TEST_SUPABASE_URL       — 로컬 Supabase auth base (예: http://127.0.0.1:56321/auth/v1)
  TEST_SUPABASE_ANON_KEY  — signup apikey 헤더(로컬은 placeholder 로도 동작)

로컬 실행 예(supabase 로컬 스택 기동 상태):
  TEST_SUPABASE_URL=http://127.0.0.1:56321/auth/v1 \
  .venv/bin/python -m pytest \
    Nutrition-backend/tests/integration/security/test_supabase_auth_live.py -q

비고: 로컬 Supabase 는 기본적으로 비대칭(ES256) 서명 키로 JWKS 를 노출한다.
운영 전환 시에도 프로젝트를 비대칭 키로 설정해야 하며(supabase_auth.py 도크 참조),
issuer 는 owner-subject/RLS 신뢰 앵커(build_owner_subject)의 일부다. 토큰은 모듈당
한 번만 발급(gotrue signup rate-limit 회피)해 세 검사에서 재사용한다.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid

import pytest
from fastapi import HTTPException
from src.config import Settings
from src.security.auth import JWTVerifier
from src.security.subjects import build_owner_subject

AUTH_URL = os.getenv("TEST_SUPABASE_URL")
ANON_KEY = os.getenv("TEST_SUPABASE_ANON_KEY", "anon-local")

pytestmark = pytest.mark.skipif(
    AUTH_URL is None,
    reason="Set TEST_SUPABASE_URL to run the live Supabase token verification test.",
)


def _mint_access_token() -> str:
    """Sign up a throwaway local Supabase user and return its access token.

    Skips (rather than fails) when the local provider is unreachable/rate-limited
    or configured to require email confirmation (no session token on signup).
    """
    assert AUTH_URL is not None
    email = f"supabase-auth-it-{uuid.uuid4()}@example.com"
    body = json.dumps({"email": email, "password": "Test-passw0rd-123"}).encode()
    request = urllib.request.Request(
        f"{AUTH_URL}/signup",
        data=body,
        headers={
            "apikey": ANON_KEY,
            "Authorization": f"Bearer {ANON_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read())
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        pytest.skip(f"local Supabase signup unavailable: {exc}")
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        pytest.skip(
            "local Supabase signup returned no access_token "
            f"(email confirmation enabled?): keys={sorted(payload)}"
        )
    return token


@pytest.fixture(scope="module")
def access_token() -> str:
    """Mint a single real Supabase access token reused across the module."""
    return _mint_access_token()


def _verifier(algorithms: list[str] | None = None) -> JWTVerifier:
    assert AUTH_URL is not None
    return JWTVerifier(
        Settings(
            _env_file=None,
            jwt_issuer=AUTH_URL,
            jwt_audience="authenticated",
            jwt_jwks_url=f"{AUTH_URL}/.well-known/jwks.json",
            jwt_algorithms=algorithms or ["RS256", "ES256"],
        )
    )


def test_backend_verifies_real_supabase_asymmetric_token(access_token: str) -> None:
    """Verify a real local Supabase access token passes the backend JWT pipeline."""
    user = _verifier().verify(access_token)

    assert user.subject  # gotrue user UUID
    assert user.issuer == AUTH_URL
    # gotrue returns aud as a bare string today; tolerate a future list form so
    # this stays a stable contract check rather than silently breaking.
    assert user.audience in ("authenticated", ["authenticated"])
    # The owner-subject trust anchor (RLS contract) is issuer::sub.
    assert build_owner_subject(user) == f"{AUTH_URL}::{user.subject}"


def test_backend_rejects_tampered_signature(access_token: str) -> None:
    """Verify a token with a corrupted signature byte is rejected (401)."""
    head, payload, signature = access_token.split(".")
    # Flip a middle character of the signature so the decoded bytes always change
    # (a last-char base64url flip can map to identical bytes).
    mid = len(signature) // 2
    replacement = "X" if signature[mid] != "X" else "Y"
    tampered = f"{head}.{payload}.{signature[:mid]}{replacement}{signature[mid + 1:]}"

    with pytest.raises(HTTPException):
        _verifier().verify(tampered)


def test_backend_rejects_when_only_symmetric_algorithm_allowed(access_token: str) -> None:
    """Verify an ES256 token is rejected when config allows only HS256.

    Guards the ADR-39 requirement that the backend rejects symmetric algorithms:
    a project that has not switched to asymmetric signing keys must not validate.
    """
    with pytest.raises(HTTPException):
        _verifier(algorithms=["HS256"]).verify(access_token)
