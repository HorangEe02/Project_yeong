"""v4.7 Feature E — 외부 IdP (OIDC/SAML) 라우터.

엔드포인트:
  GET /auth/idp/capabilities                  → 활성 IdP 목록
  GET /auth/idp/{provider}/login?next_url=    → IdP 로그인 페이지로 redirect
  GET /auth/idp/{provider}/callback?code=&state=
                                              → state 검증 → tokens 교환 →
                                                JIT provisioning →
                                                cookie session redirect

기본 상태(IDP_PROVIDER=disabled)에서는 capabilities 는 빈 배열, login/callback
은 404 반환 — 기존 로그인 흐름에 무영향.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from core.auth.idp_provider import get_idp_provider
from core.auth.state_store import get_state_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["idp"])


def _enabled_providers() -> list[str]:
    name = os.environ.get("IDP_PROVIDER", "disabled").strip().lower()
    if name in ("", "disabled", "none"):
        return []
    if name in ("oidc", "saml", "ldap"):
        return [name]
    return []


def _absolute_callback_uri(request: Request, provider: str) -> str:
    """IdP 가 redirect 할 콜백 URL.

    Cloud Run 의 X-Forwarded-Proto/Host 를 신뢰해 동일 origin 으로 조립.
    """
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}/api/auth/idp/{provider}/callback"


def _append_query_flag(target: str, key: str, value: str) -> str:
    """Append a non-secret query flag to an internal redirect target."""

    qs = urlencode({key: value})
    sep = "&" if "?" in target else "?"
    return f"{target}{sep}{qs}"


def _issue_idp_browser_session(response: Response, internal, info_subject: str, idp_name: str) -> None:
    """Issue AJIN auth cookies for a successfully mapped IdP user.

    Args:
        response: Redirect or JSON response that should receive Set-Cookie.
        internal: Internal user object returned by the IdP provider mapper.
        info_subject: Provider subject claim for audit/debug JWT metadata.
        idp_name: Provider name included in the access JWT metadata.
    """

    from core.auth.cookies import set_auth_cookies
    from core.auth.jwt_handler import mint_from_idp
    from core.auth.refresh_sessions import issue_refresh_session

    access_token = mint_from_idp(
        employee_id=internal.employee_id,
        username=internal.username,
        role_name=internal.role_name,
        role_level=internal.role_level,
        idp_subject=info_subject,
        idp_name=idp_name,
    )
    refresh_token = issue_refresh_session(internal.employee_id)
    set_auth_cookies(response, access_token, refresh_token)


@router.get("/capabilities")
async def capabilities() -> dict[str, list[str]]:
    """프론트가 IdP 로그인 버튼 표시 여부를 판단할 때 호출."""
    return {"providers": _enabled_providers()}


@router.get("/{provider}/login")
async def login_redirect(provider: str, request: Request, next_url: str = "/"):
    """state 토큰 발급 후 IdP authorize_url 로 302 redirect."""
    if provider not in _enabled_providers():
        raise HTTPException(status_code=404, detail=f"IdP 비활성: {provider}")

    p = get_idp_provider(provider)
    if not p:
        raise HTTPException(status_code=404, detail=f"지원하지 않는 IdP: {provider}")

    # next_url 화이트리스트 — open redirect 차단 (내부 경로만 허용)
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = "/"

    store = get_state_store()
    state = store.issue({"provider": provider, "next_url": next_url})
    redirect_uri = _absolute_callback_uri(request, provider)

    try:
        url = await p.authorize_url(state=state, redirect_uri=redirect_uri)
    except Exception as e:
        logger.exception("IdP authorize_url 실패")
        raise HTTPException(status_code=500, detail=f"IdP 설정 오류: {e}") from e

    return RedirectResponse(url=url, status_code=302)


@router.get("/{provider}/callback")
async def callback(provider: str, request: Request, code: str = "", state: str = ""):
    """IdP callback — state 검증 → tokens 교환 → JIT provisioning → cookie redirect."""
    if provider not in _enabled_providers():
        raise HTTPException(status_code=404, detail=f"IdP 비활성: {provider}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="code/state 누락")

    store = get_state_store()
    payload = store.consume(state)
    if not payload:
        raise HTTPException(status_code=400, detail="state 무효 또는 만료 (CSRF 방어)")
    if payload.get("provider") != provider:
        raise HTTPException(status_code=400, detail="state provider mismatch")
    next_url = payload.get("next_url", "/")
    if not isinstance(next_url, str) or not next_url.startswith("/") or next_url.startswith("//"):
        next_url = "/"

    p = get_idp_provider(provider)
    if not p:
        raise HTTPException(status_code=404, detail=f"지원하지 않는 IdP: {provider}")

    redirect_uri = _absolute_callback_uri(request, provider)
    try:
        tokens = await p.exchange_code(code=code, redirect_uri=redirect_uri)
        info = await p.fetch_userinfo(tokens)
        internal = await p.map_to_internal_user(info)
    except ValueError as e:
        logger.warning("IdP 매핑 실패: %s", e)
        # 감사 로그
        _emit_idp_audit(provider, info_subject="", success=False, reason=str(e))
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        logger.exception("IdP 콜백 처리 실패")
        raise HTTPException(status_code=502, detail=f"IdP 통신 오류: {e}") from e

    _emit_idp_audit(provider, info_subject=info.subject, success=True, reason=internal.employee_id)

    response = RedirectResponse(url=_append_query_flag(next_url, "ajin_idp", p.name), status_code=302)
    _issue_idp_browser_session(response, internal, info.subject, p.name)
    return response


@router.post("/saml/acs")
async def saml_acs(
    request: Request,
    SAMLResponse: str = Form(...),
    RelayState: str = Form(""),
):
    """SAML Assertion Consumer Service (POST binding).

    IdP 가 사용자 인증 후 SAMLResponse 를 본 endpoint 로 POST 한다.
    RelayState 에는 /login 단계에서 발급한 state 토큰이 그대로 담겨 돌아온다.

    흐름: state 검증 → exchange_code(SAMLResponse) → fetch_userinfo → JIT
    provisioning → auth cookie + next_url redirect (OIDC callback 과 동일).
    """
    if "saml" not in _enabled_providers():
        raise HTTPException(status_code=404, detail="IdP 비활성: saml")
    if not SAMLResponse:
        raise HTTPException(status_code=400, detail="SAMLResponse 누락")

    store = get_state_store()
    payload = store.consume(RelayState) if RelayState else None
    if not payload:
        raise HTTPException(status_code=400, detail="RelayState 무효 또는 만료 (CSRF 방어)")
    if payload.get("provider") != "saml":
        raise HTTPException(status_code=400, detail="state provider mismatch")
    next_url = payload.get("next_url", "/")
    if not isinstance(next_url, str) or not next_url.startswith("/") or next_url.startswith("//"):
        next_url = "/"

    p = get_idp_provider("saml")
    if not p:
        raise HTTPException(status_code=404, detail="지원하지 않는 IdP: saml")

    info = None
    try:
        tokens = await p.exchange_code(code=SAMLResponse, redirect_uri="")
        info = await p.fetch_userinfo(tokens)
        internal = await p.map_to_internal_user(info)
    except ValueError as e:
        logger.warning("SAML 매핑 실패: %s", e)
        _emit_idp_audit("saml", info_subject=getattr(info, "subject", "") or "", success=False, reason=str(e))
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        logger.exception("SAML ACS 처리 실패")
        raise HTTPException(status_code=502, detail=f"SAML 통신 오류: {e}") from e

    _emit_idp_audit("saml", info_subject=info.subject, success=True, reason=internal.employee_id)

    response = RedirectResponse(url=_append_query_flag(next_url, "ajin_idp", p.name), status_code=302)
    _issue_idp_browser_session(response, internal, info.subject, p.name)
    return response


@router.post("/ldap/login")
async def ldap_login(
    response: Response,
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """LDAP direct-bind 로그인.

    OIDC/SAML 의 redirect-callback 흐름과 달리, LDAP 은 form 으로 자격증명을 받아
    LDAPProvider.verify_credentials 로 직접 bind 한다.
    """
    if "ldap" not in _enabled_providers():
        raise HTTPException(status_code=404, detail="IdP 비활성: ldap")

    p = get_idp_provider("ldap")
    if not p:
        raise HTTPException(status_code=404, detail="지원하지 않는 IdP: ldap")

    try:
        info = await p.verify_credentials(username, password)
    except Exception as e:
        logger.exception("LDAP verify_credentials 예외")
        raise HTTPException(status_code=502, detail=f"LDAP 통신 오류: {e}") from e

    if info is None:
        _emit_idp_audit("ldap", info_subject=username, success=False, reason="bind 실패")
        raise HTTPException(status_code=401, detail="LDAP 인증 실패")

    try:
        internal = await p.map_to_internal_user(info)
    except ValueError as e:
        _emit_idp_audit("ldap", info_subject=info.subject, success=False, reason=str(e))
        raise HTTPException(status_code=403, detail=str(e)) from e

    _emit_idp_audit("ldap", info_subject=info.subject, success=True, reason=internal.employee_id)
    _issue_idp_browser_session(response, internal, info.subject, p.name)

    return {
        "token_type": "cookie",
        "idp": p.name,
        "employee_id": internal.employee_id,
        "username": internal.username,
        "role": internal.role_name,
    }


def _emit_idp_audit(provider: str, info_subject: str, success: bool, reason: str) -> None:
    """IdP 로그인 시도를 Firestore audit_logs + Cloud Logging 으로 기록.

    실패해도 응답 영향 X.
    """
    try:
        from core.auth.firestore_audit import write_event  # type: ignore

        write_event(
            "idp_login",
            {
                "provider": provider,
                "subject": info_subject,
                "success": success,
                "reason": reason,
            },
        )
    except Exception:  # pragma: no cover
        # core.audit_log_emitter 만 있는 경우 graceful
        pass
