"""Request size and value limit tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import status
from fastapi.testclient import TestClient
from src.db.dependencies import get_rls_context_session
from src.main import create_app


async def _fake_rls_session() -> AsyncIterator[object]:
    """Yield a stand-in session so request-validation tests never open a real engine.

    The RLS-migrated routes depend on ``get_rls_context_session``, which eagerly
    begins a transaction (connecting the shared async engine). Body-validation
    422s fire before the route handler runs, so the yielded value is never used;
    overriding it keeps these stateless validation tests off the real engine
    (avoiding cross-test event-loop pollution).
    """
    yield object()


def _client_without_db() -> TestClient:
    """Build a TestClient whose RLS session dependency is a no-op stand-in."""
    app = create_app()
    app.dependency_overrides[get_rls_context_session] = _fake_rls_session
    return TestClient(app)


def test_activity_rejects_too_many_peer_scores() -> None:
    """Verify activity score requests cap peer score payload size."""
    client = _client_without_db()

    response = client.post(
        "/api/v1/activity/score",
        json={
            "profile": {"age": 50, "sex": "female", "height_cm": 160, "weight_kg": 68},
            "daily_steps": 7000,
            "group_v2_scores": [50.0] * 501,
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_activity_rejects_too_many_chronic_disease_codes() -> None:
    """Verify profile disease-code list size is bounded."""
    client = _client_without_db()

    response = client.post(
        "/api/v1/activity/score",
        json={
            "profile": {
                "age": 50,
                "sex": "female",
                "height_cm": 160,
                "weight_kg": 68,
                "chronic_diseases": [f"condition_{index}" for index in range(11)],
            },
            "daily_steps": 7000,
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_weight_prediction_rejects_period_over_one_year() -> None:
    """Verify prediction periods are capped at one year."""
    client = _client_without_db()

    response = client.post(
        "/api/v1/predictions/weight",
        json={
            "age": 50,
            "sex": "female",
            "height_cm": 160,
            "weight_kg": 68,
            "daily_steps": 6500,
            "daily_intake_kcal": 1500,
            "periods_days": [366],
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_weight_prediction_rejects_too_many_periods() -> None:
    """Verify period list size is bounded."""
    client = _client_without_db()

    response = client.post(
        "/api/v1/predictions/weight",
        json={
            "age": 50,
            "sex": "female",
            "height_cm": 160,
            "weight_kg": 68,
            "daily_steps": 6500,
            "daily_intake_kcal": 1500,
            "periods_days": list(range(1, 14)),
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_nutrition_analysis_rejects_too_many_intakes() -> None:
    """Verify nutrition analysis caps intake list size."""
    client = _client_without_db()

    response = client.post(
        "/api/v1/nutrition/analyze",
        json={
            "profile": {"age": 30, "sex": "male", "height_cm": 170, "weight_kg": 70},
            "intakes": [
                {"nutrient_code": "vitamin_c_mg", "amount": 30, "unit": "mg"} for _ in range(101)
            ],
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_nutrition_analysis_rejects_long_code_and_unit() -> None:
    """Verify nutrient code and unit string lengths are bounded."""
    client = _client_without_db()

    response = client.post(
        "/api/v1/nutrition/analyze",
        json={
            "profile": {"age": 30, "sex": "male", "height_cm": 170, "weight_kg": 70},
            "intakes": [
                {
                    "nutrient_code": "x" * 65,
                    "amount": 30,
                    "unit": "milligrams_per_day",
                }
            ],
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
