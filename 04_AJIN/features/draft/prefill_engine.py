"""v4.7 Sprint 2 P0 (축 ③) — 템플릿 prefill 엔진.

특정 context (예: SPC 위반 ID) 와 template_id 를 받아, YAML 메타 템플릿의
subject/body placeholder 를 채워 메일 초안 prefill payload 를 반환한다.

지원 템플릿:
  - spc_violation : data/spc_violations.db 의 violation 1건을 조회하여 채움.

응답 스키마는 프론트엔드 draft.tsx 의 메일 form 과 호환:
  { subject: str, body: str, to: list[{email, name}], cc: list[{email, name}] }
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _safe_format(template: str, context: dict[str, Any]) -> str:
    """str.format_map 폴리필 — 누락된 키는 빈 문자열로 대체."""

    class _Defaulted(dict):
        def __missing__(self, key: str) -> str:  # type: ignore[override]
            return ""

    try:
        return template.format_map(_Defaulted(context))
    except Exception:
        return template


def _prefill_spc_violation(context_id: str) -> dict[str, Any] | None:
    """SPC violation 컨텍스트로 메일 초안 prefill.

    Args:
        context_id: spc_violations.db 의 violation row id.

    Returns: { subject, body, to, cc } 또는 None (조회 실패).
    """
    from features.equipment.spc_violations_db import get_by_id
    from features.draft.template_catalog import load_yaml_template

    violation = get_by_id(context_id)
    if not violation:
        return None

    meta = load_yaml_template("spc_violation")
    if not meta:
        logger.warning("spc_violation YAML 메타 미존재")
        return None

    subject_template = meta.get("subject_template", "")
    body_template = meta.get("body_template", "")

    ctx = {
        "violation_id": violation.get("id", ""),
        "process": violation.get("process", ""),
        "lot_id": violation.get("lot_id", ""),
        "rule_number": violation.get("rule_number", 0),
        "rule_name": violation.get("rule_name", ""),
        "violating_count": violation.get("violating_count", 0),
        "severity": violation.get("severity", ""),
        "recommended_action": violation.get("recommended_action", ""),
        "detected_at": violation.get("detected_at", ""),
    }

    subject = _safe_format(subject_template, ctx)
    body = _safe_format(body_template, ctx)

    # CC 추천 — 본 PR 에서는 경량 (품질팀 + 생산기술팀 기본). 액션 3 트랙 A 가
    # cc_recommender 의 incident_report 카테고리 라우팅을 보강할 예정.
    cc: list[dict[str, str]] = []
    to: list[dict[str, str]] = []
    try:
        from features.draft.cc_recommender import recommend_cc  # type: ignore

        rec = recommend_cc(
            doc_type="incident_report",
            sender_dept=None,
            subject=subject,
            body=body,
        )
        # recommend_cc 응답 shape 은 사이트마다 다름 — 안전 unwrap.
        for tier in ("required", "recommended", "optional"):
            for item in (rec or {}).get(tier, []) or []:
                email = item.get("email") if isinstance(item, dict) else None
                if email:
                    cc.append({"email": email, "name": item.get("name", "")})
    except Exception:
        # cc_recommender 가 다른 시그니처면 우아 폴백 — incident 라우팅은 액션 3 트랙 A.
        cc = []

    return {
        "subject": subject,
        "body": body,
        "to": to,
        "cc": cc,
    }


def prefill_template(template_id: str, context_id: str) -> dict[str, Any] | None:
    """템플릿 ID 와 컨텍스트 ID 로 메일 초안 prefill payload 생성.

    Returns: { subject, body, to, cc } 또는 None — 미지원 template/context.
    """
    if template_id == "spc_violation":
        return _prefill_spc_violation(context_id)
    return None
