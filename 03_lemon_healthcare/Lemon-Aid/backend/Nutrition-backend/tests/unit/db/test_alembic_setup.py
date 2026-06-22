"""Alembic configuration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_ROOT = Path(__file__).resolve().parents[4]


def test_alembic_script_directory_loads_initial_revision() -> None:
    """Verify Alembic can load the local migration directory."""
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["0046_merge_40class_dyslipidemia"]


def test_alembic_script_directory_loads_outside_backend_cwd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify Alembic script location does not depend on backend as cwd."""
    monkeypatch.chdir(BACKEND_ROOT.parent)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["0046_merge_40class_dyslipidemia"]


def test_alembic_env_widens_revision_id_capacity() -> None:
    """Verify live migration smoke can store descriptive revision ids."""
    env_path = BACKEND_ROOT / "alembic" / "env.py"
    env_source = env_path.read_text(encoding="utf-8")

    assert "_ensure_revision_id_capacity(connection)" in env_source
    assert "connection.commit()" in env_source
    assert "version_num VARCHAR(255)" in env_source
    assert "ALTER COLUMN version_num TYPE VARCHAR(255)" in env_source


def test_initial_migration_file_exists() -> None:
    """Verify the initial users migration file exists."""
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "0001_create_users_table.py"

    assert migration_path.is_file()


def test_analysis_results_migration_file_exists() -> None:
    """Verify the analysis result migration file exists."""
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "0002_create_analysis_results_table.py"

    assert migration_path.is_file()


def test_privacy_migration_file_exists() -> None:
    """Verify the privacy consent and audit migration file exists."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0003_create_privacy_consent_audit_tables.py"
    )

    assert migration_path.is_file()


def test_p1_supplement_health_migration_file_exists() -> None:
    """Verify the P1 supplement and health migration file exists."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0004_create_p1_supplement_health_tables.py"
    )

    assert migration_path.is_file()


def test_learning_vector_migration_file_exists() -> None:
    """Verify the learning vector migration file exists."""
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "0005_create_learning_vector_tables.py"

    assert migration_path.is_file()


def test_learning_vector_migration_uses_supabase_extension_schema() -> None:
    """Verify pgvector is not installed in the public schema."""
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "0005_create_learning_vector_tables.py"
    migration = migration_path.read_text(encoding="utf-8")

    assert "CREATE SCHEMA IF NOT EXISTS extensions" in migration
    assert "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions" in migration
    assert "extensions.vector" in migration


def test_regulated_ocr_intake_migration_file_exists() -> None:
    """Verify the regulated OCR intake migration file exists."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0006_create_regulated_ocr_intake_tables.py"
    )

    assert migration_path.is_file()


def test_health_daily_summaries_composite_pk_migration_file_exists() -> None:
    """Verify the PR-O composite-PK migration file exists."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0007_health_daily_summaries_composite_pk.py"
    )

    assert migration_path.is_file()


def test_health_daily_summaries_hypertable_migration_file_exists() -> None:
    """Verify the PR-P opt-in hypertable migration file exists."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0008_health_daily_summaries_hypertable.py"
    )

    assert migration_path.is_file()


def test_learning_vector_supabase_access_migration_file_exists() -> None:
    """Verify the Supabase access hardening migration file exists."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0009_harden_learning_vector_supabase_access.py"
    )

    assert migration_path.is_file()


def test_learning_vector_supabase_access_migration_is_fail_closed() -> None:
    """Verify learning/vector tables are not exposed to Supabase API roles."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0009_harden_learning_vector_supabase_access.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    for table_name in (
        "learning_image_objects",
        "image_embedding_jobs",
        "image_embedding_records",
    ):
        assert "public.{table_name}" in migration
        assert table_name in migration

    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FROM PUBLIC" in migration
    assert "'anon', 'authenticated', 'service_role'" in migration
    assert "'pending_auto_filter'" in migration
    assert "'pending_manual_review'" in migration
    assert "'rejected_by_auto_filter'" in migration
    assert "GRANT " not in migration


def test_learning_vector_remote_grant_revoke_migration_file_exists() -> None:
    """Verify the remote Supabase drift hardening migration file exists."""
    migration_path = (
        BACKEND_ROOT
        / "alembic"
        / "versions"
        / "0010_revoke_learning_api_grants_and_public_definers.py"
    )

    assert migration_path.is_file()


def test_learning_vector_remote_grant_revoke_migration_is_fail_closed() -> None:
    """Verify remote drift migration revokes Data API and public definer access."""
    migration_path = (
        BACKEND_ROOT
        / "alembic"
        / "versions"
        / "0010_revoke_learning_api_grants_and_public_definers.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    assert "REVOKE ALL PRIVILEGES ON TABLE" in migration
    assert "public.learning_image_objects" in migration
    assert "public.image_embedding_jobs" in migration
    assert "public.image_embedding_records" in migration
    assert "REVOKE EXECUTE ON FUNCTION" in migration
    assert "rls_auto_enable" in migration
    assert "'anon', 'authenticated', 'service_role'" in migration
    assert "GRANT " not in migration


def test_learning_review_metadata_migration_file_exists() -> None:
    """Verify the manual review metadata migration file exists."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0011_add_learning_review_metadata_snapshot.py"
    )

    assert migration_path.is_file()


def test_learning_review_metadata_migration_stores_only_sanitized_snapshot() -> None:
    """Verify review metadata migration adds no raw payload columns or grants."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0011_add_learning_review_metadata_snapshot.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    assert "review_metadata_snapshot" in migration
    assert "postgresql.JSONB" in migration
    assert "image_bytes" not in migration
    assert "provider_payload" not in migration
    assert "GRANT " not in migration


def test_user_supplement_precaution_snapshot_migration_is_sanitized() -> None:
    """Verify precaution snapshots store only confirmed text arrays."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0024_add_user_supplement_precaution_snapshot.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    assert "precaution_snapshot" in migration
    assert "postgresql.JSONB" in migration
    assert "raw_ocr_text" not in migration
    assert "provider_payload" not in migration
    assert "image_bytes" not in migration


def test_supplement_food_taxonomy_migration_is_sanitized() -> None:
    """Verify taxonomy catalog tables do not introduce raw payload storage."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0025_create_supplement_food_taxonomy_tables.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    assert "supplement_categories" in migration
    assert "food_cuisines" in migration
    assert "food_catalog_items" in migration
    assert "crawling-image-folder-v1" in migration
    assert "된장찌개" in migration
    assert "김치찌개" in migration
    assert "raw_ocr_text" not in migration
    assert "image_bytes" not in migration
    assert "provider_payload" not in migration


def test_learning_private_storage_bucket_migration_file_exists() -> None:
    """Verify the private learning Storage bucket migration file exists."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0012_configure_learning_private_storage_bucket.py"
    )

    assert migration_path.is_file()


def test_learning_private_storage_bucket_migration_is_private() -> None:
    """Verify the learning Storage bucket is private and image-only."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0012_configure_learning_private_storage_bucket.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    assert "storage.buckets" in migration
    assert "learning-images" in migration
    assert "public = false" in migration
    assert "image/jpeg" in migration
    assert "image/png" in migration
    assert "image/webp" in migration
    assert "20 * 1024 * 1024" in migration
    assert "raw_ocr_text" not in migration
    assert "provider_payload" not in migration
    assert "GRANT " not in migration


def test_user_supplement_fk_index_migration_file_exists() -> None:
    """Verify the user_supplements foreign-key index migration file exists."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0013_index_user_supplement_foreign_keys.py"
    )

    assert migration_path.is_file()


def test_user_supplement_fk_index_migration_adds_no_data_exposure() -> None:
    """Verify FK index migration is limited to performance-only index DDL."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0013_index_user_supplement_foreign_keys.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    assert "CREATE INDEX IF NOT EXISTS ix_user_supplements_source_analysis_run_id" in migration
    assert "CREATE INDEX IF NOT EXISTS ix_user_supplements_matched_product_id" in migration
    assert "GRANT " not in migration
    assert "POLICY" not in migration
    assert "raw_ocr_text" not in migration
    assert "provider_payload" not in migration


def test_user_supplement_evidence_refs_migration_adds_no_raw_data() -> None:
    """Verify evidence-ref migration stores only sanitized reference ids."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0019_add_user_supplement_evidence_refs.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    assert migration_path.is_file()
    assert "evidence_refs" in migration
    assert "jsonb_typeof(evidence_refs) = 'array'" in migration
    assert "raw OCR text" in migration
    assert "provider payloads" in migration
    assert "image bytes" in migration
    assert "GRANT " not in migration
    assert "POLICY" not in migration


def test_backend_only_media_migration_file_exists() -> None:
    """Verify the backend-only media table migration file exists."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0014_create_backend_only_media_tables.py"
    )

    assert migration_path.is_file()


def test_backend_only_media_migration_is_fail_closed() -> None:
    """Verify media tables are internal and do not store raw payload columns."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0014_create_backend_only_media_tables.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    assert "media_objects" in migration
    assert "media_processing_runs" in migration
    assert "supplement_image_evidence" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL PRIVILEGES ON TABLE" in migration
    assert "FROM PUBLIC" in migration
    assert "'anon', 'authenticated', 'service_role'" in migration
    assert "object_ref NOT LIKE '%://%'" in migration
    assert "object_ref NOT LIKE '/%'" in migration
    assert "object_ref NOT LIKE '%..%'" in migration
    assert "quality_codes" in migration
    assert "roi_snapshot" in migration
    assert "jsonb_typeof(quality_codes) = 'array'" in migration
    assert "jsonb_typeof(roi_snapshot) = 'object'" in migration
    assert "Raw image bytes" in migration
    assert "raw OCR" in migration
    assert "provider payloads" in migration
    assert "GRANT " not in migration
    assert "image_bytes" not in migration
    assert "raw_ocr_text" not in migration
    assert "provider_payload" not in migration
    assert "request_headers" not in migration
    assert "access_token" not in migration


def test_food_meal_migration_file_exists() -> None:
    """Verify the food and meal preview migration file exists."""
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "0015_create_food_meal_tables.py"

    assert migration_path.is_file()


def test_food_meal_migration_is_fail_closed() -> None:
    """Verify food/meal tables are internal and do not store raw payload columns."""
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "0015_create_food_meal_tables.py"
    migration = migration_path.read_text(encoding="utf-8")

    assert "meal_records" in migration
    assert "meal_food_items" in migration
    assert "food_image_analysis_runs" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL PRIVILEGES ON TABLE" in migration
    assert "FROM PUBLIC" in migration
    assert "'anon', 'authenticated', 'service_role'" in migration
    assert "jsonb_typeof(nutrition_summary) = 'object'" in migration
    assert "jsonb_typeof(detected_items_snapshot) = 'object'" in migration
    assert "jsonb_typeof(nutrition_estimate_snapshot) = 'object'" in migration
    assert "jsonb_typeof(warning_codes) = 'array'" in migration
    assert "Original images" in migration
    assert "provider payloads" in migration
    assert "GRANT " not in migration
    assert "image_bytes" not in migration
    assert "raw_ocr_text" not in migration
    assert "provider_payload" not in migration
    assert "request_headers" not in migration
    assert "access_token" not in migration


def test_health_profile_metric_migration_file_exists() -> None:
    """Verify the health profile and metric sample migration file exists."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0016_create_health_profile_metric_tables.py"
    )

    assert migration_path.is_file()


def test_health_profile_metric_migration_is_fail_closed() -> None:
    """Verify health/profile tables are hardened against Supabase client exposure."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0016_create_health_profile_metric_tables.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    assert "body_profile_snapshots" in migration
    assert "health_metric_samples" in migration
    assert "public.users" in migration
    assert "public.health_sync_batches" in migration
    assert "public.health_daily_summaries" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL PRIVILEGES ON TABLE" in migration
    assert "FROM PUBLIC" in migration
    assert "'anon', 'authenticated', 'service_role'" in migration
    assert "jsonb_typeof(consent_snapshot) = 'object'" in migration
    assert "jsonb_typeof(quality_flags) = 'array'" in migration
    assert "Direct backend PostgreSQL access only" in migration
    assert "GRANT " not in migration
    assert "raw_payload" not in migration
    assert "provider_payload" not in migration
    assert "request_headers" not in migration
    assert "access_token" not in migration


def test_medical_record_status_migration_file_exists() -> None:
    """Verify the medical record and patient status migration file exists."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0017_create_medical_record_status_tables.py"
    )

    assert migration_path.is_file()


def test_medical_record_status_migration_is_fail_closed() -> None:
    """Verify medical record tables are internal and avoid raw payload columns."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0017_create_medical_record_status_tables.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    assert "medical_record_collections" in migration
    assert "patient_conditions" in migration
    assert "patient_medications" in migration
    assert "patient_status_snapshots" in migration
    assert "public.regulated_documents" in migration
    assert "public.prescription_items" in migration
    assert "public.lab_result_items" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL PRIVILEGES ON TABLE" in migration
    assert "FROM PUBLIC" in migration
    assert "'anon', 'authenticated', 'service_role'" in migration
    assert "jsonb_typeof(consent_snapshot) = 'object'" in migration
    assert "jsonb_typeof(symptom_categories) = 'array'" in migration
    assert "jsonb_typeof(metric_summary) = 'object'" in migration
    assert "jsonb_typeof(risk_flags) = 'array'" in migration
    assert "Direct backend PostgreSQL access only" in migration
    assert "GRANT " not in migration
    for forbidden_column in (
        'sa.Column("diagnosis"',
        'sa.Column("diagnosis_text"',
        'sa.Column("image_bytes"',
        'sa.Column("provider_payload"',
        'sa.Column("raw_document"',
        'sa.Column("raw_ocr_text"',
        'sa.Column("request_headers"',
        'sa.Column("treatment_instruction"',
    ):
        assert forbidden_column not in migration


def test_learning_dataset_model_registry_migration_file_exists() -> None:
    """Verify the retraining dataset and model registry migration file exists."""
    migration_path = (
        BACKEND_ROOT
        / "alembic"
        / "versions"
        / "0018_create_learning_dataset_model_registry_tables.py"
    )

    assert migration_path.is_file()


def test_learning_dataset_model_registry_migration_is_fail_closed() -> None:
    """Verify retraining lineage tables are backend-only and privacy-safe."""
    migration_path = (
        BACKEND_ROOT
        / "alembic"
        / "versions"
        / "0018_create_learning_dataset_model_registry_tables.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    assert "learning_dataset_versions" in migration
    assert "learning_dataset_items" in migration
    assert "annotation_tasks" in migration
    assert "model_training_runs" in migration
    assert "model_registry" in migration
    assert "model_eval_results" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL PRIVILEGES ON TABLE" in migration
    assert "FROM PUBLIC" in migration
    assert "'anon', 'authenticated', 'service_role'" in migration
    assert "jsonb_typeof(label_snapshot) = 'object'" in migration
    assert "jsonb_typeof(consent_snapshot) = 'object'" in migration
    assert "jsonb_typeof(metrics_snapshot) = 'object'" in migration
    assert "jsonb_typeof(metric_gate_snapshot) = 'object'" in migration
    assert "artifact_ref NOT LIKE '%://%'" in migration
    assert "Backend-only direct PostgreSQL access" in migration
    assert "GRANT " not in migration
    for forbidden_column in (
        'sa.Column("access_token"',
        'sa.Column("image_bytes"',
        'sa.Column("object_uri"',
        'sa.Column("owner_subject",',
        'sa.Column("provider_payload"',
        'sa.Column("public_url"',
        'sa.Column("raw_image"',
        'sa.Column("raw_ocr_text"',
        'sa.Column("raw_payload"',
        'sa.Column("request_headers"',
        'sa.Column("secret"',
        'sa.Column("signed_url"',
    ):
        assert forbidden_column not in migration


def test_normalize_check_constraint_migration_file_exists() -> None:
    """Verify the check-constraint normalization migration file exists."""
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0044_normalize_check_constraint_names.py"
    )

    assert migration_path.is_file()


def test_normalize_check_constraint_migration_is_definition_based_and_idempotent() -> None:
    """Verify 0044 locates constraints by CHECK definition and converges safely.

    The fix must (a) match by ``pg_get_constraintdef`` rather than the
    version-sensitive drifted name, (b) rename the drifted constraint when the
    canonical target is absent, and (c) drop the drifted duplicate when both the
    drifted and canonical names exist (a partial manual fix) instead of leaving
    an orphan. Targets are frozen literals because SQLAlchemy's truncation/hash
    is version-sensitive.
    """
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "0044_normalize_check_constraint_names.py"
    )
    migration = migration_path.read_text(encoding="utf-8")

    assert "pg_get_constraintdef(oid) ILIKE" in migration
    assert "RENAME CONSTRAINT %I TO %I" in migration
    assert "DROP CONSTRAINT %I" in migration
    assert "v_has_target" in migration
    assert "ck_supplement_product_ingredients_daily_value_percent_n_230f" in migration
    assert "ck_user_supplement_ingredients_daily_value_percent_nonnegative" in migration
    assert "ck_user_supplements_evidence_refs_array" in migration
    assert "ck_user_supplements_precaution_snapshot_array" in migration
    # Ingredient needle is the discriminating clause, not the bare column name.
    assert "daily_value_percent IS NULL" in migration


def test_check_constraint_source_migrations_use_bare_tokens_and_definition_drop() -> None:
    """Verify 0019/0021/0024 pass bare tokens and drop by CHECK definition.

    The naming convention ``ck_%(table_name)s_%(constraint_name)s`` prefixes the
    token at execution time, so the create call must pass the bare token (an
    already-prefixed name would double-wrap). The downgrade must drop by CHECK
    definition so it succeeds whether the live name is convention-correct or a
    historical double-wrapped variant — i.e. it must not depend on 0044.
    """
    versions = BACKEND_ROOT / "alembic" / "versions"

    evidence = (versions / "0019_add_user_supplement_evidence_refs.py").read_text(encoding="utf-8")
    assert 'op.create_check_constraint(\n        "evidence_refs_array",' in evidence
    assert (
        '_drop_check_by_definition("user_supplements", "jsonb_typeof(evidence_refs)")' in evidence
    )

    dvp = (versions / "0021_add_ingredient_daily_value_percent.py").read_text(encoding="utf-8")
    assert 'op.create_check_constraint(\n        "daily_value_percent_nonnegative",' in dvp
    assert "_drop_check_by_definition(" in dvp
    assert "daily_value_percent IS NULL" in dvp

    precaution = (versions / "0024_add_user_supplement_precaution_snapshot.py").read_text(
        encoding="utf-8"
    )
    assert 'op.create_check_constraint(\n        "precaution_snapshot_array",' in precaution
    assert (
        '_drop_check_by_definition("user_supplements", "jsonb_typeof(precaution_snapshot)")'
        in precaution
    )
