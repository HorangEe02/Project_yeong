"""OAuth scope registry tests."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from src.security.auth import AuthenticatedUser, require_meal_read
from src.security.scopes import ALL_API_SCOPES, SCOPE_DESCRIPTIONS, ApiScope, scope_values


def test_scope_registry_values_are_unique_and_documented() -> None:
    """Verify every registered scope has one value and one description."""
    scope_values_from_enum = [scope.value for scope in ApiScope]

    assert len(scope_values_from_enum) == len(set(scope_values_from_enum))
    assert set(ALL_API_SCOPES) == set(scope_values_from_enum)
    assert set(SCOPE_DESCRIPTIONS) == set(ApiScope)


def test_p1_scope_registry_contains_supplement_health_and_dashboard_scopes() -> None:
    """Verify P1 contract scopes are centrally registered."""
    assert scope_values(
        ApiScope.SUPPLEMENT_READ,
        ApiScope.SUPPLEMENT_WRITE,
        ApiScope.SUPPLEMENT_DELETE,
        ApiScope.MEAL_READ,
        ApiScope.MEAL_WRITE,
        ApiScope.HEALTH_WRITE,
        ApiScope.MEDICAL_READ,
        ApiScope.MEDICAL_WRITE,
        ApiScope.REGULATED_INPUT_WRITE,
        ApiScope.DASHBOARD_READ,
    ) == (
        "supplement:read",
        "supplement:write",
        "supplement:delete",
        "meal:read",
        "meal:write",
        "health:write",
        "medical:read",
        "medical:write",
        "regulated_input:write",
        "dashboard:read",
    )


@pytest.mark.asyncio
async def test_meal_read_scope_is_distinct_from_meal_write_scope() -> None:
    """Verify read-only meal APIs reject users that only have meal write scope."""
    write_only_user = AuthenticatedUser(subject="user_1", scopes=("meal:write",))

    with pytest.raises(HTTPException) as exc_info:
        await require_meal_read(write_only_user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.headers == {
        "WWW-Authenticate": (
            'Bearer realm="lemon-healthcare", ' 'error="insufficient_scope", scope="meal:read"'
        )
    }

    read_user = AuthenticatedUser(subject="user_1", scopes=("meal:read",))
    assert await require_meal_read(read_user) is read_user
