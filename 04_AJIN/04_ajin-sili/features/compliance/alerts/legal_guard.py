"""Legal judgment guardrails for Feature D outputs and status changes."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any


COMPLIANCE_AI_DISCLAIMER = (
    "※ AI 자동 분류·요약·추천은 참고용이며 법적 판단/대외 통보/조치는 "
    "담당 부서 검토 및 승인 후 확정해야 합니다."
)
LEGAL_FINAL_STATUSES = {"announced", "done"}
LEGAL_REVIEW_GRADES = {"CRITICAL", "HIGH"}
LEGAL_IMPACT_CLASSES = {"criminal", "administrative", "civil", "contract", "standardization"}
LEGAL_REVIEW_ACTIONS = {
    "legal_review",
    "human_review",
    "review",
    "approve",
    "approved",
    "approval_decision",
}


def ensure_legal_disclaimer(text: str) -> str:
    """Append the Feature D legal disclaimer when it is missing.

    Args:
        text: Existing output text.

    Returns:
        str: Text with the disclaimer included exactly once.
    """

    body = text or ""
    if COMPLIANCE_AI_DISCLAIMER in body:
        return body
    separator = "\n\n" if body.strip() else ""
    return f"{body.rstrip()}{separator}{COMPLIANCE_AI_DISCLAIMER}"


def parse_json_list(value: Any) -> list[Any]:
    """Normalize a JSON-string or sequence field into a list.

    Args:
        value: Raw value from SQLite, Pydantic, or a crawler result.

    Returns:
        list[Any]: Parsed list or an empty list for malformed input.
    """

    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value or "[]")
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def requires_legal_review(change: Mapping[str, Any]) -> bool:
    """Return whether a compliance change needs independent human review.

    Args:
        change: Regulation change row or dict.

    Returns:
        bool: True for high/critical grade or legal impact classes.
    """

    grade = str(change.get("grade") or "").upper()
    if grade in LEGAL_REVIEW_GRADES:
        return True
    legal_classes = {str(item).lower() for item in parse_json_list(change.get("legal_class"))}
    return bool(legal_classes.intersection(LEGAL_IMPACT_CLASSES))


def has_independent_human_review(audit_trail: Sequence[Any], actor_id: str) -> bool:
    """Check whether a different user already reviewed the change.

    Args:
        audit_trail: Parsed audit trail entries.
        actor_id: Current transition actor identifier.

    Returns:
        bool: True when a review-like audit entry exists from another user.
    """

    actor = str(actor_id or "")
    for item in audit_trail:
        if not isinstance(item, Mapping):
            continue
        user = str(item.get("user") or item.get("reviewer") or item.get("approver") or "")
        if not user or user == actor:
            continue
        action = str(item.get("action") or "").lower()
        to_status = str(item.get("to") or "").lower()
        decision = str(item.get("decision") or "").lower()
        if action in LEGAL_REVIEW_ACTIONS or to_status in {"reviewing", "planning"}:
            return True
        if decision in {"approved", "pass", "pass_with_comment"}:
            return True
    return False
