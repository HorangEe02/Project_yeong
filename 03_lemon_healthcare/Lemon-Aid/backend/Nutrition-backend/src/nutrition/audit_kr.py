"""AUDIT-KR self-check scoring.

This module intentionally accepts numeric item scores only. UI copy for the
10 AUDIT-KR questions should live in reviewed product content so this backend
algorithm can stay focused on validation, scoring, and safe routing.
"""

from __future__ import annotations

from src.models.schemas.nutrition import AuditKRRequest, AuditKRResponse

AUDIT_KR_ALGORITHM_VERSION = "audit-kr-v1.0.0"
AUDIT_KR_QUESTION_COUNT = 10
AUDIT_KR_RISK_CUTOFF = 3
AUDIT_KR_DEPENDENCE_MALE_CUTOFF = 10
AUDIT_KR_DEPENDENCE_FEMALE_CUTOFF = 8
AUDIT_KR_SUPPORT_NUTRIENTS = ("thiamin_mg", "folate_ug", "magnesium_mg", "zinc_mg")
LOW_RISK_MESSAGE = "현재 입력 기준으로 위험 음주 cut-off 미만입니다. 절주 정보를 참고하세요."
RISK_DRINKING_MESSAGE = (
    "AUDIT-KR 위험 음주 범위입니다. B1, 엽산, 마그네슘, 아연 섭취 상태 확인과 "
    "절주 상담 정보를 우선 확인하세요."
)
DEPENDENCE_CUTOFF_MESSAGE = (
    "AUDIT-KR 점수가 높아 영양제 자동 추천보다 1577-0199 또는 "
    "중독관리통합지원센터 상담 연결이 우선입니다."
)


def _dependence_cutoff(sex: str) -> int:
    """Return sex-specific AUDIT-KR alcohol use disorder screening cutoff.

    Args:
        sex: User sex field.

    Returns:
        Male or female cutoff score.
    """
    return AUDIT_KR_DEPENDENCE_MALE_CUTOFF if sex == "male" else AUDIT_KR_DEPENDENCE_FEMALE_CUTOFF


def score_audit_kr(request: AuditKRRequest) -> AuditKRResponse:
    """Score a 10-item AUDIT-KR self-check response.

    Args:
        request: Numeric AUDIT-KR item scores and sex-specific cutoff context.

    Returns:
        Scored screening result with safe nutrition-routing messages.
    """
    score = sum(request.item_scores)
    dependence_cutoff = _dependence_cutoff(request.sex)

    if score >= dependence_cutoff:
        risk_level = "dependence_cutoff"
        messages = [DEPENDENCE_CUTOFF_MESSAGE]
        paused = True
        priority_nutrients: list[str] = []
    elif score >= AUDIT_KR_RISK_CUTOFF:
        risk_level = "risky_drinking"
        messages = [RISK_DRINKING_MESSAGE]
        paused = False
        priority_nutrients = list(AUDIT_KR_SUPPORT_NUTRIENTS)
    else:
        risk_level = "low_risk"
        messages = [LOW_RISK_MESSAGE]
        paused = False
        priority_nutrients = []

    return AuditKRResponse(
        score=score,
        risk_level=risk_level,
        risk_cutoff=AUDIT_KR_RISK_CUTOFF,
        dependence_cutoff=dependence_cutoff,
        nutrition_priority_nutrients=priority_nutrients,
        supplement_recommendation_paused=paused,
        recommendation_messages=messages,
        algorithm_version=AUDIT_KR_ALGORITHM_VERSION,
    )
