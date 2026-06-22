"""OpenAPI example coverage tests."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

from fastapi import status
from fastapi.testclient import TestClient
from src.main import create_app
from src.nutrition.deficiency_analysis import FORBIDDEN_TERMS


def _openapi_schema() -> dict[str, Any]:
    """Return the generated OpenAPI schema.

    Returns:
        OpenAPI schema dictionary from the FastAPI app.
    """
    client = TestClient(create_app())
    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    return cast(dict[str, Any], response.json())


def _iter_strings(value: object) -> Iterator[str]:
    """Yield strings recursively from a JSON-compatible object.

    Args:
        value: JSON-compatible value.

    Yields:
        String values contained in the object.
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_strings(child)


def test_openapi_contains_named_request_examples() -> None:
    """Verify POST endpoints expose named OpenAPI request examples."""
    schema = _openapi_schema()

    activity_examples = schema["paths"]["/api/v1/activity/score"]["post"]["requestBody"]["content"][
        "application/json"
    ]["examples"]
    weight_examples = schema["paths"]["/api/v1/predictions/weight"]["post"]["requestBody"][
        "content"
    ]["application/json"]["examples"]
    nutrition_examples = schema["paths"]["/api/v1/nutrition/analyze"]["post"]["requestBody"][
        "content"
    ]["application/json"]["examples"]
    health_sync_examples = schema["paths"]["/api/v1/health/sync"]["post"]["requestBody"]["content"][
        "application/json"
    ]["examples"]

    assert "phase1_chronic_disease" in activity_examples
    assert "phase1_weight_prediction" in weight_examples
    assert "vitamin_status_sample" in nutrition_examples
    assert "ios_healthkit_daily_aggregate" in health_sync_examples
    assert "android_health_connect_daily_aggregate" in health_sync_examples


def test_openapi_contains_success_response_examples() -> None:
    """Verify core endpoints expose 200 response examples."""
    schema = _openapi_schema()

    health_examples = schema["paths"]["/health"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["examples"]
    activity_examples = schema["paths"]["/api/v1/activity/score"]["post"]["responses"]["200"][
        "content"
    ]["application/json"]["examples"]
    kdris_examples = schema["paths"]["/api/v1/nutrition/kdris"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["examples"]
    health_sync_examples = schema["paths"]["/api/v1/health/sync"]["post"]["responses"]["202"][
        "content"
    ]["application/json"]["examples"]

    assert health_examples["healthy"]["value"] == {"status": "ok", "version": "0.1.0"}
    assert activity_examples["activity_score"]["value"]["recommended_steps"] == 7500
    assert kdris_examples["kdris_lookup_sample"]["value"]["dataset_status"].startswith(
        "implementation_sample"
    )
    assert health_sync_examples["accepted_health_aggregate"]["value"]["accepted_count"] == 1


def test_openapi_contains_validation_error_examples() -> None:
    """Verify endpoints include reusable 422 examples."""
    schema = _openapi_schema()

    for path, method in (
        ("/api/v1/activity/score", "post"),
        ("/api/v1/predictions/weight", "post"),
        ("/api/v1/nutrition/kdris", "get"),
        ("/api/v1/nutrition/analyze", "post"),
        ("/api/v1/health/sync", "post"),
    ):
        examples = schema["paths"][path][method]["responses"]["422"]["content"]["application/json"][
            "examples"
        ]
        assert "validation_error" in examples


def test_openapi_examples_do_not_contain_forbidden_terms() -> None:
    """Verify user-facing examples avoid regulated wording."""
    schema = _openapi_schema()
    example_strings = list(_iter_strings(schema["paths"]))

    assert not any(term in text for term in FORBIDDEN_TERMS for text in example_strings)
