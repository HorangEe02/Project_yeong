"""P5 §6 — Atlassian Jira REST API 양방향 sync.

P3 D9 의 단방향 webhook (`JIRA_WEBHOOK_URL` POST) 와 별개로 Atlassian Cloud REST API
직접 호출. collab ticket / change transition 시 Jira issue 동기화 + Jira webhook 수신
시 우리 시스템 ticket 상태 자동 갱신.

자격증명 우선순위:
  1. .env 의 JIRA_BASE_URL + JIRA_USER_EMAIL + JIRA_API_TOKEN 모두 설정 → 활성
  2. 하나라도 미설정 → jira_enabled() False, 모든 호출 graceful skip + 'jira_disabled'
     로 audit (일관된 거동, 호출처는 분기 불필요).

보안:
  - 토큰은 Authorization 헤더 Basic auth 로만 전송, 절대 log 에 출력 X
  - HTTP 호출 timeout 10초 — Jira 장애 시 우리 시스템 hang 방지
  - inbound webhook (`/jira/webhook`) 은 별도 검증 (라우터에서 처리)
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 우리 status ↔ Jira status 매핑
# ─────────────────────────────────────────────────────────────


# 우리 → Jira (default workflow 기준)
STATUS_MAP: dict[str, str] = {
    "pending": "To Do",
    "reviewing": "In Progress",
    "planning": "In Progress",
    "announced": "In Progress",
    "done": "Done",
    "filtered": "Done",
}

# Jira → 우리 (보수적 — Jira 측은 To Do/In Progress/Done 3단)
REVERSE_STATUS_MAP: dict[str, str] = {
    "To Do": "pending",
    "Open": "pending",
    "In Progress": "reviewing",
    "Done": "done",
    "Closed": "done",
    "Resolved": "done",
}


# ─────────────────────────────────────────────────────────────
# 자격 / 헬퍼
# ─────────────────────────────────────────────────────────────


def _config() -> dict[str, str]:
    """env 에서 Jira 자격 + base URL 읽기. 미설정 키는 빈 문자열."""
    return {
        "base_url": (os.environ.get("JIRA_BASE_URL") or "").rstrip("/"),
        "email": (os.environ.get("JIRA_USER_EMAIL") or "").strip(),
        "token": (os.environ.get("JIRA_API_TOKEN") or "").strip(),
        "default_project_key": (os.environ.get("JIRA_DEFAULT_PROJECT_KEY") or "").strip(),
    }


def jira_enabled() -> bool:
    """Atlassian REST API 호출이 가능한지 — 3개 필수 자격이 모두 있을 때만 True."""
    c = _config()
    return bool(c["base_url"] and c["email"] and c["token"])


def _auth_header(email: str, token: str) -> str:
    raw = f"{email}:{token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _safe_response(error: str, **kwargs: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "error": error}
    out.update(kwargs)
    return out


# ─────────────────────────────────────────────────────────────
# Outbound — issue 생성 / transition / comment
# ─────────────────────────────────────────────────────────────


def create_issue(
    title: str,
    *,
    description: str = "",
    project_key: str | None = None,
    issue_type: str = "Task",
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Jira issue 생성 (POST /rest/api/3/issue).

    Returns: {ok, issue_key, issue_url, error}
    jira_enabled=False 또는 project_key 부재 / 4xx/5xx 시 graceful skip.
    """
    if not jira_enabled():
        return _safe_response("jira_disabled")
    c = _config()
    pkey = (project_key or c["default_project_key"]).strip()
    if not pkey:
        return _safe_response("missing_project_key")

    title = (title or "").strip() or "(제목 없음)"
    body = {
        "fields": {
            "project": {"key": pkey},
            "summary": title[:250],
            "issuetype": {"name": issue_type},
            "description": _adf_paragraph(description or title),
        }
    }
    try:
        import httpx
        r = httpx.post(
            f"{c['base_url']}/rest/api/3/issue",
            headers={
                "Authorization": _auth_header(c["email"], c["token"]),
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=timeout,
        )
    except Exception as e:
        logger.warning("Jira create_issue 호출 실패: %s", type(e).__name__)
        return _safe_response(f"http_error:{type(e).__name__}")
    if r.status_code >= 400:
        # body 일부만 사유로 노출 (토큰 등 secret 없음 — Jira 응답)
        snippet = (r.text or "")[:200]
        logger.warning("Jira create_issue HTTP %s: %s", r.status_code, snippet)
        return _safe_response(f"http_{r.status_code}", detail=snippet)
    try:
        data = r.json()
    except ValueError:
        return _safe_response("invalid_json")
    issue_key = data.get("key") or ""
    if not issue_key:
        return _safe_response("no_issue_key")
    return {
        "ok": True,
        "issue_key": issue_key,
        "issue_url": f"{c['base_url']}/browse/{issue_key}",
    }


def transition_issue(
    issue_key: str,
    target_status_name: str,
    *,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Jira issue 의 status 를 target_status_name 으로 transition.

    1) GET /rest/api/3/issue/{key}/transitions → status_name → transition_id 매핑
    2) POST /rest/api/3/issue/{key}/transitions {transition: {id}}
    """
    if not jira_enabled():
        return _safe_response("jira_disabled")
    if not issue_key:
        return _safe_response("missing_issue_key")
    if not target_status_name:
        return _safe_response("missing_target_status")
    c = _config()
    headers = {
        "Authorization": _auth_header(c["email"], c["token"]),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    try:
        import httpx
        list_r = httpx.get(
            f"{c['base_url']}/rest/api/3/issue/{issue_key}/transitions",
            headers=headers, timeout=timeout,
        )
        if list_r.status_code >= 400:
            return _safe_response(f"http_{list_r.status_code}",
                                  detail=(list_r.text or "")[:200])
        items = (list_r.json() or {}).get("transitions") or []
        # status name 부분 매치 (대소문자 무시)
        target_low = target_status_name.lower()
        match = next(
            (t for t in items
             if (t.get("to") or {}).get("name", "").lower() == target_low),
            None,
        )
        if match is None:
            available = [(t.get("to") or {}).get("name") for t in items]
            return _safe_response(
                f"transition_not_found:{target_status_name}",
                available=available,
            )
        transition_id = match.get("id")
        post_r = httpx.post(
            f"{c['base_url']}/rest/api/3/issue/{issue_key}/transitions",
            headers=headers,
            json={"transition": {"id": transition_id}},
            timeout=timeout,
        )
        if post_r.status_code >= 400:
            return _safe_response(f"http_{post_r.status_code}",
                                  detail=(post_r.text or "")[:200])
    except Exception as e:
        logger.warning("Jira transition_issue 실패: %s", type(e).__name__)
        return _safe_response(f"http_error:{type(e).__name__}")
    return {
        "ok": True,
        "issue_key": issue_key,
        "transition_id": transition_id,
        "target_status": target_status_name,
    }


def add_comment(
    issue_key: str,
    body_text: str,
    *,
    timeout: float = 10.0,
) -> dict[str, Any]:
    if not jira_enabled():
        return _safe_response("jira_disabled")
    if not issue_key or not body_text:
        return _safe_response("missing_arg")
    c = _config()
    try:
        import httpx
        r = httpx.post(
            f"{c['base_url']}/rest/api/3/issue/{issue_key}/comment",
            headers={
                "Authorization": _auth_header(c["email"], c["token"]),
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={"body": _adf_paragraph(body_text)},
            timeout=timeout,
        )
    except Exception as e:
        return _safe_response(f"http_error:{type(e).__name__}")
    if r.status_code >= 400:
        return _safe_response(f"http_{r.status_code}",
                              detail=(r.text or "")[:200])
    try:
        data = r.json()
    except ValueError:
        return _safe_response("invalid_json")
    return {"ok": True, "comment_id": data.get("id", "")}


def health() -> dict[str, Any]:
    """현재 Jira 자격 + 토큰 유효성 + default project 존재 여부."""
    if not jira_enabled():
        return {
            "enabled": False,
            "myself_ok": False,
            "default_project_ok": False,
            "note": "JIRA_BASE_URL/USER_EMAIL/API_TOKEN 미설정",
        }
    c = _config()
    headers = {
        "Authorization": _auth_header(c["email"], c["token"]),
        "Accept": "application/json",
    }
    out: dict[str, Any] = {
        "enabled": True,
        "myself_ok": False,
        "default_project_ok": False,
        "note": "",
    }
    try:
        import httpx
        r = httpx.get(f"{c['base_url']}/rest/api/3/myself", headers=headers, timeout=10.0)
        out["myself_ok"] = (r.status_code == 200)
        if r.status_code != 200:
            out["note"] = f"myself HTTP {r.status_code} (read:jira-user scope 필요할 수 있음)"
        if c["default_project_key"]:
            r2 = httpx.get(
                f"{c['base_url']}/rest/api/3/project/{c['default_project_key']}",
                headers=headers, timeout=10.0,
            )
            out["default_project_ok"] = (r2.status_code == 200)
            if r2.status_code != 200:
                out["note"] = (
                    out["note"]
                    + f" / project {c['default_project_key']} HTTP {r2.status_code}"
                ).strip(" /")
    except Exception as e:
        out["note"] = f"http_error:{type(e).__name__}"
    return out


# ─────────────────────────────────────────────────────────────
# ADF (Atlassian Document Format) — description/comment body 형식
# ─────────────────────────────────────────────────────────────


def _adf_paragraph(text: str) -> dict[str, Any]:
    """plain text → ADF v1 doc (Jira REST API v3 의 description/comment 표준)."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": (text or "")[:2000]}],
            }
        ],
    }


# ─────────────────────────────────────────────────────────────
# Inbound webhook helpers (라우터에서 호출)
# ─────────────────────────────────────────────────────────────


def parse_webhook_status(payload: dict[str, Any]) -> tuple[str, str]:
    """Jira webhook payload → (issue_key, our_status). 매칭 안 되면 둘 다 빈 문자열.

    Atlassian 의 jira:issue_updated 이벤트는 issue.fields.status.name 에 현재 상태를 담음.
    """
    if not isinstance(payload, dict):
        return ("", "")
    issue = payload.get("issue") or {}
    if not isinstance(issue, dict):
        return ("", "")
    issue_key = str(issue.get("key") or "").strip()
    fields = issue.get("fields") or {}
    status = (fields.get("status") or {}).get("name") or ""
    our_status = REVERSE_STATUS_MAP.get(status, "")
    return (issue_key, our_status)
