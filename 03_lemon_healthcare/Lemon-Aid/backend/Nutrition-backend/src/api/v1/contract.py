"""OpenAPI contract helpers for API v1 routes."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import HTTPException, status

from src.models.schemas.privacy import ConsentType
from src.security.scopes import ApiScope

P1_CONTRACT_STATUS = "p1_0_contract_stub"
P1_2_INTAKE_READY_STATUS = "p1_2_intake_ready"
P1_4_SUPPLEMENT_REGISTRATION_READY_STATUS = "p1_4_registration_ready"
P1_5_DEFICIENCY_DASHBOARD_READY_STATUS = "p1_5_deficiency_dashboard_ready"
P1_6_HEALTH_SYNC_READY_STATUS = "p1_6_health_sync_ready"
P1_7_SUPPLEMENT_RECOMMENDATION_READY_STATUS = "p1_7_supplement_recommendation_ready"
P1_7_AI_AGENT_DAILY_COACHING_READY_STATUS = "p1_7_ai_agent_daily_coaching_ready"


def route_contract(
    *,
    scopes: Sequence[ApiScope],
    consents: Sequence[ConsentType] = (),
    conditional_consents: Sequence[ConsentType] = (),
    contract_status: str = P1_CONTRACT_STATUS,
) -> dict[str, object]:
    """Build OpenAPI extensions for route-level security contracts.

    Args:
        scopes: OAuth scopes required by the route.
        consents: Consent buckets required by the route.
        conditional_consents: Consent buckets required only for enabled optional providers.
        contract_status: Route implementation contract status.

    Returns:
        OpenAPI extension dictionary.
    """
    return {
        "x-contract-status": contract_status,
        "x-required-scopes": [scope.value for scope in scopes],
        "x-required-consents": [consent.value for consent in consents],
        "x-conditional-consents": [consent.value for consent in conditional_consents],
    }


def contract_stub(feature_name: str) -> HTTPException:
    """Build a P1-0 contract stub exception.

    Args:
        feature_name: Human-readable feature name.

    Returns:
        HTTP 501 exception indicating that only the contract is frozen.
    """
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "code": "p1_contract_stub",
            "message": f"{feature_name} API contract is frozen; implementation starts after P1-0.",
        },
    )
