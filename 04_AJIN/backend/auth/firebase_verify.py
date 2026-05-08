"""Firebase ID Token 검증 (firebase-admin 7.4.0 + PyJWT/JWKS fallback).

Day 5++.5: Firebase Auth → 백엔드 JWT 자동 교환을 위한 ID Token 검증.

검증 흐름:
1. firebase-admin 가용 시 → ``auth.verify_id_token`` (default app 자동 초기화)
2. 미설치 또는 import 실패 시 → PyJWT + JWKS (Google securetoken 공개 키)

Service Account JSON 미사용 — projectId 만으로 동작 (zero config).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

logger = logging.getLogger(__name__)

# Firebase 표준 endpoints (Google securetoken)
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "ajin-cb")
FIREBASE_X509_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "securetoken@system.gserviceaccount.com"
)
FIREBASE_ISSUER = f"https://securetoken.google.com/{FIREBASE_PROJECT_ID}"

# JWKS 캐시 (TTL 1시간)
_jwks_cache: dict[str, Any] = {"keys": None, "ts": 0.0}
_JWKS_TTL_SEC = 3600

# firebase-admin 초기화 캐시
_fb_admin_ready = False


def _ensure_firebase_admin() -> bool:
    """firebase-admin SDK default app 을 초기화한다.

    Returns:
        True: 초기화 성공 (또는 이미 초기화됨)
        False: firebase-admin 미설치 또는 초기화 실패
    """
    global _fb_admin_ready
    if _fb_admin_ready:
        return True
    try:
        from firebase_admin import initialize_app, get_app  # type: ignore
        try:
            get_app()
        except ValueError:
            initialize_app(options={"projectId": FIREBASE_PROJECT_ID})
        _fb_admin_ready = True
        return True
    except Exception as e:  # ImportError, ValueError 등 모두 fallback 처리
        logger.warning(f"[Firebase Verify] firebase-admin 초기화 실패 → JWKS fallback: {e}")
        return False


def _fetch_x509_certs() -> dict[str, str]:
    """Firebase 공개 키 (PEM x509) 를 fetch 한다 (TTL 캐시).

    Returns: {kid: pem_cert} dict.
    Raises: httpx.HTTPError on network failure.
    """
    now = time.time()
    cached = _jwks_cache["keys"]
    if cached and (now - _jwks_cache["ts"]) < _JWKS_TTL_SEC:
        return cached  # type: ignore[return-value]

    with httpx.Client(timeout=5.0) as client:
        resp = client.get(FIREBASE_X509_URL)
        resp.raise_for_status()
        certs: dict[str, str] = resp.json()

    _jwks_cache["keys"] = certs
    _jwks_cache["ts"] = now
    return certs


def _verify_via_pyjwt(id_token: str) -> dict[str, Any]:
    """PyJWT + Google x509 공개 키로 검증한다 (firebase-admin fallback)."""
    # 1) Header 에서 kid 추출
    unverified_header = jwt.get_unverified_header(id_token)
    kid = unverified_header.get("kid")
    if not kid:
        raise jwt.InvalidTokenError("Firebase ID Token 헤더에 kid 가 없습니다.")

    # 2) 공개 키 fetch
    certs = _fetch_x509_certs()
    cert_pem = certs.get(kid)
    if not cert_pem:
        # kid 미스 시 캐시 무효화 후 재시도
        _jwks_cache["ts"] = 0.0
        certs = _fetch_x509_certs()
        cert_pem = certs.get(kid)
    if not cert_pem:
        raise jwt.InvalidTokenError(f"Firebase 공개 키를 찾을 수 없습니다 (kid={kid}).")

    # 3) PEM x509 → public key 객체
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend

    cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"), default_backend())
    public_key = cert.public_key()

    # 4) 서명 + 표준 클레임 검증
    payload: dict[str, Any] = jwt.decode(
        id_token,
        public_key,  # type: ignore[arg-type]
        algorithms=["RS256"],
        audience=FIREBASE_PROJECT_ID,
        issuer=FIREBASE_ISSUER,
    )

    # 5) auth_time / sub 검증 (firebase-admin 동일 정책)
    if not payload.get("sub"):
        raise jwt.InvalidTokenError("Firebase ID Token sub 누락")
    return payload


def verify_firebase_id_token(id_token: str) -> dict[str, Any]:
    """Firebase ID Token 을 검증하고 payload 를 반환한다.

    Args:
        id_token: Firebase Web SDK 의 ``user.getIdToken()`` 결과.

    Returns:
        decoded payload (uid/email/aud/iss/exp 등 포함).

    Raises:
        ValueError: 검증 실패 (위조, 만료, project 불일치, 네트워크 실패 등).
    """
    if not id_token or not isinstance(id_token, str):
        raise ValueError("Firebase ID Token 이 비어있거나 형식이 올바르지 않습니다.")

    # 1) firebase-admin 우선 시도
    if _ensure_firebase_admin():
        try:
            from firebase_admin import auth as fb_auth  # type: ignore
            decoded = fb_auth.verify_id_token(id_token, check_revoked=False)
            return dict(decoded)
        except Exception as e:
            logger.warning(f"[Firebase Verify] firebase-admin 검증 실패 → PyJWT fallback: {e}")

    # 2) PyJWT + JWKS fallback
    try:
        return _verify_via_pyjwt(id_token)
    except jwt.PyJWTError as e:
        raise ValueError(f"Firebase ID Token 검증 실패: {e}") from e
    except httpx.HTTPError as e:
        raise ValueError(f"Firebase 공개 키 조회 실패: {e}") from e
    except Exception as e:
        raise ValueError(f"Firebase ID Token 검증 중 오류: {e}") from e
