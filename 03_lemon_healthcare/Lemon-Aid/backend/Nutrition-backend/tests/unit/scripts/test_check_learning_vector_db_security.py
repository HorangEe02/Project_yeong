"""Learning/vector DB security preflight script tests."""

from __future__ import annotations

import importlib
import json
import sys
from io import StringIO
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

check_learning_vector_db_security = importlib.import_module(
    "scripts.check_learning_vector_db_security"
)


def test_preflight_constants_cover_supabase_learning_tables_and_raw_keys() -> None:
    """Verify the DB preflight checks the sensitive Supabase exposure surface."""
    assert check_learning_vector_db_security.LEARNING_VECTOR_TABLES == (
        "learning_image_objects",
        "image_embedding_jobs",
        "image_embedding_records",
    )
    assert check_learning_vector_db_security.INTERNAL_MEDIA_TABLES == (
        "media_objects",
        "media_processing_runs",
        "supplement_image_evidence",
    )
    assert check_learning_vector_db_security.FOOD_MEAL_TABLES == (
        "meal_records",
        "meal_food_items",
        "food_image_analysis_runs",
    )
    assert check_learning_vector_db_security.HEALTH_PROFILE_TABLES == (
        "users",
        "health_sync_batches",
        "health_daily_summaries",
        "body_profile_snapshots",
        "health_metric_samples",
    )
    assert check_learning_vector_db_security.MEDICAL_RECORD_TABLES == (
        "regulated_documents",
        "prescription_items",
        "lab_result_items",
        "medical_record_collections",
        "patient_conditions",
        "patient_medications",
        "patient_status_snapshots",
    )
    assert check_learning_vector_db_security.LEARNING_RETRAINING_TABLES == (
        "learning_dataset_versions",
        "learning_dataset_items",
        "annotation_tasks",
        "model_training_runs",
        "model_registry",
        "model_eval_results",
    )
    assert check_learning_vector_db_security.SENSITIVE_INTERNAL_TABLES == (
        "learning_image_objects",
        "image_embedding_jobs",
        "image_embedding_records",
        "media_objects",
        "media_processing_runs",
        "supplement_image_evidence",
        "meal_records",
        "meal_food_items",
        "food_image_analysis_runs",
        "users",
        "health_sync_batches",
        "health_daily_summaries",
        "body_profile_snapshots",
        "health_metric_samples",
        "regulated_documents",
        "prescription_items",
        "lab_result_items",
        "medical_record_collections",
        "patient_conditions",
        "patient_medications",
        "patient_status_snapshots",
        "learning_dataset_versions",
        "learning_dataset_items",
        "annotation_tasks",
        "model_training_runs",
        "model_registry",
        "model_eval_results",
    )
    assert check_learning_vector_db_security.SUPABASE_API_ROLES == (
        "PUBLIC",
        "anon",
        "authenticated",
        "service_role",
    )
    assert check_learning_vector_db_security.LEARNING_STORAGE_BUCKET == "learning-images"
    assert (
        check_learning_vector_db_security.LEARNING_STORAGE_FILE_SIZE_LIMIT_BYTES == 20 * 1024 * 1024
    )
    assert check_learning_vector_db_security.LEARNING_STORAGE_ALLOWED_MIME_TYPES == (
        "image/jpeg",
        "image/png",
        "image/webp",
    )
    assert check_learning_vector_db_security.SUPABASE_CLIENT_STORAGE_ROLES == (
        "public",
        "anon",
        "authenticated",
    )
    assert check_learning_vector_db_security.SUPABASE_CLIENT_EXECUTE_ROLES == (
        "PUBLIC",
        "anon",
        "authenticated",
        "service_role",
    )
    assert {
        "access_token",
        "device_payload",
        "diagnosis",
        "diagnosis_text",
        "image_bytes",
        "ocr_text",
        "public_url",
        "provider_raw_payload",
        "prescription_instruction",
        "raw_payload",
        "raw_document",
        "raw_document_text",
        "raw_ocr_text",
        "provider_payload",
        "raw_provider_payload",
        "request_headers",
        "secret",
        "signed_url",
        "treatment_instruction",
        "treatment_instructions",
    }.issubset(check_learning_vector_db_security.FORBIDDEN_COLUMNS)


def test_view_security_helpers_detect_public_api_exposure() -> None:
    """Verify public view exposure reasons stay sanitized and fail closed."""
    assert check_learning_vector_db_security._view_has_security_invoker("{security_invoker=true}")
    assert check_learning_vector_db_security._view_has_security_invoker(
        "check_option=cascaded, security_invoker = true"
    )
    assert not check_learning_vector_db_security._view_has_security_invoker("")
    assert not check_learning_vector_db_security._view_has_security_invoker("security_barrier=true")
    assert (
        check_learning_vector_db_security._public_view_exposure_reason(
            relkind="m",
            reloptions="security_invoker=true",
        )
        == "materialized_view_exposed"
    )
    assert (
        check_learning_vector_db_security._public_view_exposure_reason(
            relkind="v",
            reloptions="security_barrier=true",
        )
        == "security_invoker_missing"
    )
    assert (
        check_learning_vector_db_security._public_view_exposure_reason(
            relkind="v",
            reloptions="security_invoker=true",
        )
        is None
    )


@pytest.mark.asyncio
async def test_run_preflight_outputs_sanitized_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify successful reports do not need database URLs or secrets."""

    async def fake_collect_security_report() -> dict[str, object]:
        """Return a sanitized success report."""
        return {
            "schema_version": check_learning_vector_db_security.SCHEMA_VERSION,
            "passed": True,
            "vector_extension_schema": "extensions",
            "unsafe_security_definer_function_count": 0,
            "unsafe_security_definer_functions": [],
            "unsafe_public_view_count": 0,
            "unsafe_public_views": [],
            "unsafe_learning_storage_policy_count": 0,
            "unsafe_learning_storage_policies": [],
            "learning_storage_bucket": {
                "bucket": "learning-images",
                "exists": True,
                "private": True,
                "file_size_limit_ok": True,
                "allowed_mime_types_ok": True,
            },
            "raw_image_bytes_stored_in_db": False,
            "raw_ocr_text_stored_in_db": False,
        }

    monkeypatch.setattr(
        check_learning_vector_db_security,
        "collect_security_report",
        fake_collect_security_report,
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = await check_learning_vector_db_security.run_preflight(
        strict=True,
        stdout=stdout,
        stderr=stderr,
    )

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert payload["passed"] is True
    assert "database_url" not in payload


@pytest.mark.asyncio
async def test_run_preflight_outputs_sanitized_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify connection failures do not print URLs, passwords, or raw data."""

    async def fake_collect_security_report() -> dict[str, object]:
        """Raise a representative connection failure."""
        raise RuntimeError("postgresql://user:" + "password@example.com/lemon")

    monkeypatch.setattr(
        check_learning_vector_db_security,
        "collect_security_report",
        fake_collect_security_report,
    )
    stdout = StringIO()
    stderr = StringIO()

    exit_code = await check_learning_vector_db_security.run_preflight(
        strict=True,
        stdout=stdout,
        stderr=stderr,
    )

    payload = json.loads(stderr.getvalue())
    assert exit_code == 1
    assert stdout.getvalue() == ""
    assert payload == {
        "error_type": "RuntimeError",
        "schema_version": check_learning_vector_db_security.SCHEMA_VERSION,
        "status": "failed",
    }
    assert "password" not in stderr.getvalue()
