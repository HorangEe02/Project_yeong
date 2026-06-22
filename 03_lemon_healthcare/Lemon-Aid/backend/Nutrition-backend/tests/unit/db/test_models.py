"""Database model metadata tests."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from sqlalchemy import CheckConstraint, Index, Numeric, Table
from src.db.base import Base
from src.models.db import (
    AnalysisResult,
    AnnotationTask,
    AuditLog,
    BodyProfileSnapshot,
    ConsentPolicy,
    ConsentRecord,
    DeletionRequest,
    FoodCatalogItem,
    FoodCourse,
    FoodCuisine,
    FoodImageAnalysisRun,
    HealthDailySummary,
    HealthMetricSample,
    HealthSyncBatch,
    ImageEmbeddingJob,
    ImageEmbeddingRecord,
    LabResultItem,
    LearningDatasetItem,
    LearningDatasetVersion,
    LearningImageObject,
    MealFoodItem,
    MealRecord,
    MediaObject,
    MediaProcessingRun,
    MedicalRecordCollection,
    ModelEvalResult,
    ModelRegistryEntry,
    ModelTrainingRun,
    PatientCondition,
    PatientMedication,
    PatientStatusSnapshot,
    PrescriptionItem,
    RegulatedDocument,
    SupplementAnalysisRun,
    SupplementCategory,
    SupplementImageEvidence,
    SupplementProduct,
    SupplementProductCategory,
    SupplementProductIngredient,
    User,
    UserSupplement,
    UserSupplementIngredient,
)


def test_user_table_is_registered_with_required_columns() -> None:
    """Verify that the users table is registered in shared ORM metadata."""
    table = cast(Table, User.__table__)

    assert "users" in Base.metadata.tables
    assert table.name == "users"
    assert set(table.c.keys()) == {
        "id",
        "sex",
        "birth_date",
        "height_cm",
        "base_weight_kg",
        "created_at",
        "updated_at",
    }
    assert table.c.id.primary_key is True
    assert table.c.sex.nullable is False
    assert table.c.created_at.nullable is False
    assert table.c.updated_at.nullable is False


def test_user_numeric_columns_use_expected_precision() -> None:
    """Verify Phase 1 body-measure columns retain predictable decimal precision."""
    table = cast(Table, User.__table__)
    height_type = cast(Numeric[Decimal], table.c.height_cm.type)
    weight_type = cast(Numeric[Decimal], table.c.base_weight_kg.type)

    assert height_type.precision == 5
    assert height_type.scale == 2
    assert weight_type.precision == 5
    assert weight_type.scale == 2


def test_user_constraints_are_named_for_alembic() -> None:
    """Verify constraints use deterministic names for migration diffs."""
    table = cast(Table, User.__table__)
    constraint_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert {
        "ck_users_sex_allowed",
        "ck_users_height_cm_positive",
        "ck_users_base_weight_kg_positive",
    }.issubset(constraint_names)


def test_base_metadata_uses_naming_convention() -> None:
    """Verify the shared metadata has a stable naming convention."""
    assert Base.metadata.naming_convention["pk"] == "pk_%(table_name)s"
    assert Base.metadata.naming_convention["ix"] == "ix_%(table_name)s_%(column_0_name)s"


def test_analysis_result_table_is_registered_with_required_columns() -> None:
    """Verify that the analysis results table is registered in shared ORM metadata."""
    table = cast(Table, AnalysisResult.__table__)

    assert "analysis_results" in Base.metadata.tables
    assert table.name == "analysis_results"
    assert set(table.c.keys()) == {
        "id",
        "owner_subject",
        "analysis_type",
        "algorithm_version",
        "kdris_source_manifest_version",
        "input_snapshot",
        "result_snapshot",
        "created_at",
        "updated_at",
    }
    assert table.c.id.primary_key is True
    assert table.c.owner_subject.nullable is False
    assert table.c.input_snapshot.nullable is False
    assert table.c.result_snapshot.nullable is False


def test_analysis_result_constraints_and_indexes_are_defined() -> None:
    """Verify owner-scoped result storage uses deterministic constraints and indexes."""
    table = cast(Table, AnalysisResult.__table__)
    constraint_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    index_names = {index.name for index in table.indexes if isinstance(index, Index)}

    assert "ck_analysis_results_analysis_type_allowed" in constraint_names
    assert "ix_analysis_results_owner_created_at" in index_names
    assert "ix_analysis_results_owner_type_created_at" in index_names


def test_privacy_tables_are_registered_with_required_columns() -> None:
    """Verify privacy tables are registered in shared ORM metadata."""
    assert "consent_policies" in Base.metadata.tables
    assert "consent_records" in Base.metadata.tables
    assert "deletion_requests" in Base.metadata.tables
    assert "audit_logs" in Base.metadata.tables

    consent_policy = cast(Table, ConsentPolicy.__table__)
    consent_record = cast(Table, ConsentRecord.__table__)
    deletion_request = cast(Table, DeletionRequest.__table__)
    audit_log = cast(Table, AuditLog.__table__)

    assert {"consent_type", "version", "content_hash", "effective_at"}.issubset(
        set(consent_policy.c.keys())
    )
    assert {"owner_subject", "policy_version", "granted", "ip_hash"}.issubset(
        set(consent_record.c.keys())
    )
    assert {"owner_subject_hash", "request_type", "deleted_counts"}.issubset(
        set(deletion_request.c.keys())
    )
    assert {"actor_subject_hash", "action", "event_metadata", "record_hash"}.issubset(
        set(audit_log.c.keys())
    )


def test_privacy_constraints_and_indexes_are_defined() -> None:
    """Verify privacy tables expose deterministic constraints and lookup indexes."""
    deletion_request = cast(Table, DeletionRequest.__table__)
    audit_log = cast(Table, AuditLog.__table__)
    audit_index_names = {index.name for index in audit_log.indexes if isinstance(index, Index)}
    deletion_constraint_names = {
        constraint.name
        for constraint in deletion_request.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "ck_deletion_requests_deletion_request_type_allowed" in deletion_constraint_names
    assert "ck_deletion_requests_deletion_request_status_allowed" in deletion_constraint_names
    assert "ix_audit_logs_actor_created_at" in audit_index_names
    assert "ix_audit_logs_resource_created_at" in audit_index_names


def test_regulated_document_tables_are_registered_with_required_columns() -> None:
    """Verify regulated OCR intake tables are registered in shared ORM metadata."""
    regulated_document = cast(Table, RegulatedDocument.__table__)
    prescription_item = cast(Table, PrescriptionItem.__table__)
    lab_result_item = cast(Table, LabResultItem.__table__)

    assert "regulated_documents" in Base.metadata.tables
    assert "prescription_items" in Base.metadata.tables
    assert "lab_result_items" in Base.metadata.tables
    assert {
        "owner_subject_hash",
        "document_type",
        "status",
        "image_sha256",
        "ocr_text_hash",
        "parsed_snapshot",
        "warning_codes",
        "consult_cta",
        "raw_image_deleted_at",
        "expires_at",
        "confirmed_at",
    }.issubset(set(regulated_document.c.keys()))
    assert {
        "document_id",
        "medication_name_text",
        "dose_text",
        "frequency_text",
        "period_text",
        "source",
    }.issubset(set(prescription_item.c.keys()))
    assert {
        "document_id",
        "test_name_text",
        "value_text",
        "unit_text",
        "reference_range_text",
        "source",
    }.issubset(set(lab_result_item.c.keys()))


def test_regulated_document_constraints_and_indexes_are_defined() -> None:
    """Verify regulated OCR intake tables expose deterministic safety constraints."""
    regulated_document = cast(Table, RegulatedDocument.__table__)
    prescription_item = cast(Table, PrescriptionItem.__table__)
    lab_result_item = cast(Table, LabResultItem.__table__)
    document_constraint_names = {
        constraint.name
        for constraint in regulated_document.constraints
        if isinstance(constraint, CheckConstraint)
    }
    prescription_constraint_names = {
        constraint.name
        for constraint in prescription_item.constraints
        if isinstance(constraint, CheckConstraint)
    }
    lab_constraint_names = {
        constraint.name
        for constraint in lab_result_item.constraints
        if isinstance(constraint, CheckConstraint)
    }
    document_index_names = {
        index.name for index in regulated_document.indexes if isinstance(index, Index)
    }

    assert "ck_regulated_documents_regulated_document_type_allowed" in document_constraint_names
    assert "ck_regulated_documents_regulated_document_status_allowed" in document_constraint_names
    assert "ck_regulated_documents_regulated_document_image_mime_type_allowed" in (
        document_constraint_names
    )
    assert "ck_prescription_items_prescription_item_confidence_range" in (
        prescription_constraint_names
    )
    assert "ck_lab_result_items_lab_result_item_confidence_range" in lab_constraint_names
    assert "ix_regulated_documents_owner_status_created_at" in document_index_names


def test_medical_record_tables_are_registered_without_raw_payload_columns() -> None:
    """Verify medical record tables store only confirmed structured fields."""
    medical_collection = cast(Table, MedicalRecordCollection.__table__)
    patient_condition = cast(Table, PatientCondition.__table__)
    patient_medication = cast(Table, PatientMedication.__table__)
    patient_status = cast(Table, PatientStatusSnapshot.__table__)

    assert "medical_record_collections" in Base.metadata.tables
    assert "patient_conditions" in Base.metadata.tables
    assert "patient_medications" in Base.metadata.tables
    assert "patient_status_snapshots" in Base.metadata.tables
    assert {
        "owner_subject_hash",
        "record_type",
        "source",
        "source_document_id",
        "status",
        "consent_snapshot",
        "deleted_at",
    }.issubset(set(medical_collection.c.keys()))
    assert {
        "medical_collection_id",
        "condition_text",
        "condition_code_system",
        "condition_code_hash",
        "clinical_status",
        "onset_date_text",
        "source",
        "confirmed_at",
    }.issubset(set(patient_condition.c.keys()))
    assert {
        "medical_collection_id",
        "medication_name_text",
        "dose_text",
        "frequency_text",
        "route_text",
        "period_text",
        "active_status",
        "source_document_id",
        "confirmed_at",
    }.issubset(set(patient_medication.c.keys()))
    assert {
        "owner_subject_hash",
        "status_at",
        "summary_type",
        "input_window_start",
        "input_window_end",
        "symptom_categories",
        "metric_summary",
        "medication_summary",
        "risk_flags",
        "data_quality",
        "generated_by",
        "expires_at",
    }.issubset(set(patient_status.c.keys()))
    for table in (medical_collection, patient_condition, patient_medication, patient_status):
        assert {
            "image_bytes",
            "raw_image",
            "raw_ocr_text",
            "provider_payload",
            "request_headers",
            "access_token",
            "diagnosis",
            "treatment_instruction",
        }.isdisjoint(set(table.c.keys()))


def test_medical_record_constraints_and_indexes_are_fail_closed() -> None:
    """Verify medical records use owner constraints and deterministic indexes."""
    medical_collection = cast(Table, MedicalRecordCollection.__table__)
    patient_condition = cast(Table, PatientCondition.__table__)
    patient_medication = cast(Table, PatientMedication.__table__)
    patient_status = cast(Table, PatientStatusSnapshot.__table__)
    collection_constraint_names = {
        constraint.name
        for constraint in medical_collection.constraints
        if isinstance(constraint, CheckConstraint)
    }
    condition_constraint_names = {
        constraint.name
        for constraint in patient_condition.constraints
        if isinstance(constraint, CheckConstraint)
    }
    medication_constraint_names = {
        constraint.name
        for constraint in patient_medication.constraints
        if isinstance(constraint, CheckConstraint)
    }
    status_constraint_names = {
        constraint.name
        for constraint in patient_status.constraints
        if isinstance(constraint, CheckConstraint)
    }
    collection_index_names = {
        index.name for index in medical_collection.indexes if isinstance(index, Index)
    }
    condition_index_names = {
        index.name for index in patient_condition.indexes if isinstance(index, Index)
    }
    medication_index_names = {
        index.name for index in patient_medication.indexes if isinstance(index, Index)
    }
    status_index_names = {
        index.name for index in patient_status.indexes if isinstance(index, Index)
    }

    assert "ck_medical_record_collections_medical_owner_hash_length" in (
        collection_constraint_names
    )
    assert "ck_medical_record_collections_medical_record_type_allowed" in (
        collection_constraint_names
    )
    assert "ck_medical_record_collections_medical_record_status_allowed" in (
        collection_constraint_names
    )
    assert "ck_patient_conditions_patient_condition_text_nonempty" in (condition_constraint_names)
    assert "ck_patient_conditions_patient_condition_code_hash_length" in (
        condition_constraint_names
    )
    assert "ck_patient_medications_patient_medication_name_nonempty" in (
        medication_constraint_names
    )
    assert "ck_patient_status_snapshots_patient_status_owner_hash_length" in (
        status_constraint_names
    )
    assert "ck_patient_status_snapshots_patient_status_summary_type_allowed" in (
        status_constraint_names
    )
    assert "ck_patient_status_snapshots_patient_status_input_window_order" in (
        status_constraint_names
    )
    assert "ix_medical_record_collections_owner_status_created_at" in collection_index_names
    assert "ix_medical_record_collections_owner_type_created_at" in collection_index_names
    assert "ix_patient_conditions_medical_collection_id" in condition_index_names
    assert "ix_patient_medications_medical_collection_id" in medication_index_names
    assert "ix_patient_status_snapshots_owner_status_at" in status_index_names


def test_supplement_tables_are_registered_with_required_columns() -> None:
    """Verify P1 supplement tables are registered in shared ORM metadata."""
    supplement_category = cast(Table, SupplementCategory.__table__)
    supplement_product = cast(Table, SupplementProduct.__table__)
    supplement_product_category = cast(Table, SupplementProductCategory.__table__)
    supplement_product_ingredient = cast(Table, SupplementProductIngredient.__table__)
    supplement_analysis_run = cast(Table, SupplementAnalysisRun.__table__)
    user_supplement = cast(Table, UserSupplement.__table__)
    user_supplement_ingredient = cast(Table, UserSupplementIngredient.__table__)

    assert "supplement_categories" in Base.metadata.tables
    assert "supplement_products" in Base.metadata.tables
    assert "supplement_product_categories" in Base.metadata.tables
    assert "supplement_product_ingredients" in Base.metadata.tables
    assert "supplement_analysis_runs" in Base.metadata.tables
    assert "user_supplements" in Base.metadata.tables
    assert "user_supplement_ingredients" in Base.metadata.tables
    assert {
        "category_key",
        "display_name",
        "source_folder_name",
        "source_path",
        "source_payload",
        "source_manifest_version",
        "sort_order",
        "is_active",
    }.issubset(set(supplement_category.c.keys()))
    assert {
        "source_provider",
        "source_product_id",
        "product_name",
        "normalized_product_name",
        "source_payload",
        "source_manifest_version",
    }.issubset(set(supplement_product.c.keys()))
    assert {
        "product_id",
        "category_id",
        "source",
        "confidence",
        "is_primary",
        "source_payload",
        "sort_order",
    }.issubset(set(supplement_product_category.c.keys()))
    assert {
        "product_id",
        "standard_name",
        "nutrient_code",
        "amount",
        "source_payload",
    }.issubset(set(supplement_product_ingredient.c.keys()))
    assert {
        "owner_subject",
        "client_request_id",
        "status",
        "image_sha256",
        "ocr_text_hash",
        "parsed_snapshot",
        "match_snapshot",
        "algorithm_version",
        "source_manifest_version",
        "expires_at",
    }.issubset(set(supplement_analysis_run.c.keys()))
    assert {
        "owner_subject",
        "source_analysis_run_id",
        "matched_product_id",
        "display_name",
        "serving_snapshot",
        "intake_schedule",
        "precaution_snapshot",
        "evidence_refs",
        "deleted_at",
    }.issubset(set(user_supplement.c.keys()))
    assert {
        "user_supplement_id",
        "display_name",
        "nutrient_code",
        "amount",
        "confidence",
        "source",
    }.issubset(set(user_supplement_ingredient.c.keys()))


def test_supplement_constraints_and_indexes_are_defined() -> None:
    """Verify P1 supplement tables expose deterministic constraints and lookup indexes."""
    supplement_category = cast(Table, SupplementCategory.__table__)
    supplement_product = cast(Table, SupplementProduct.__table__)
    supplement_product_category = cast(Table, SupplementProductCategory.__table__)
    supplement_analysis_run = cast(Table, SupplementAnalysisRun.__table__)
    user_supplement = cast(Table, UserSupplement.__table__)
    user_supplement_ingredient = cast(Table, UserSupplementIngredient.__table__)
    category_constraint_names = {constraint.name for constraint in supplement_category.constraints}
    product_constraint_names = {constraint.name for constraint in supplement_product.constraints}
    product_category_constraint_names = {
        constraint.name for constraint in supplement_product_category.constraints
    }
    run_constraint_names = {constraint.name for constraint in supplement_analysis_run.constraints}
    ingredient_constraint_names = {
        constraint.name for constraint in user_supplement_ingredient.constraints
    }
    user_supplement_constraint_names = {
        constraint.name for constraint in user_supplement.constraints
    }
    category_index_names = {
        index.name for index in supplement_category.indexes if isinstance(index, Index)
    }
    product_index_names = {
        index.name for index in supplement_product.indexes if isinstance(index, Index)
    }
    product_category_index_names = {
        index.name for index in supplement_product_category.indexes if isinstance(index, Index)
    }
    run_index_names = {
        index.name for index in supplement_analysis_run.indexes if isinstance(index, Index)
    }
    user_supplement_index_names = {
        index.name for index in user_supplement.indexes if isinstance(index, Index)
    }
    ingredient_index_names = {
        index.name for index in user_supplement_ingredient.indexes if isinstance(index, Index)
    }

    assert "uq_supplement_categories_category_key" in category_constraint_names
    assert "ck_supplement_categories_category_key_nonempty" in category_constraint_names
    assert "uq_supplement_products_source_provider_product_id" in product_constraint_names
    assert "ck_supplement_products_source_provider_nonempty" in product_constraint_names
    assert "uq_supplement_product_categories_product_category" in product_category_constraint_names
    assert "ck_supplement_product_categories_confidence_range" in (
        product_category_constraint_names
    )
    assert "ck_supplement_analysis_runs_status_allowed" in run_constraint_names
    assert "ck_supplement_analysis_runs_ocr_confidence_range" in run_constraint_names
    assert "ck_user_supplements_precaution_snapshot_array" in user_supplement_constraint_names
    assert "ck_user_supplement_ingredients_confidence_range" in ingredient_constraint_names
    assert "ix_supplement_categories_active_sort" in category_index_names
    assert "ix_supplement_products_normalized_name" in product_index_names
    assert "ix_supplement_product_categories_category_id" in product_category_index_names
    assert "ix_supplement_analysis_runs_owner_created_at" in run_index_names
    assert "ix_supplement_analysis_runs_owner_status_created_at" in run_index_names
    assert "ix_user_supplements_source_analysis_run_id" in user_supplement_index_names
    assert "ix_user_supplements_matched_product_id" in user_supplement_index_names
    assert "ix_user_supplement_ingredients_supplement_id" in ingredient_index_names


def test_health_tables_are_registered_with_required_columns() -> None:
    """Verify P1 health tables are registered in shared ORM metadata."""
    health_sync_batch = cast(Table, HealthSyncBatch.__table__)
    health_daily_summary = cast(Table, HealthDailySummary.__table__)

    assert "health_sync_batches" in Base.metadata.tables
    assert "health_daily_summaries" in Base.metadata.tables
    assert {
        "owner_subject",
        "client_batch_id",
        "source_platform",
        "record_count",
        "accepted_count",
        "rejected_count",
        "input_snapshot",
        "result_snapshot",
        "synced_at",
    }.issubset(set(health_sync_batch.c.keys()))
    assert {
        "owner_subject",
        "measured_date",
        "source_platform",
        "steps",
        "weight_kg",
        "resting_heart_rate_bpm",
        "active_energy_kcal",
        "source_record_hash",
        "synced_at",
    }.issubset(set(health_daily_summary.c.keys()))


def test_health_constraints_and_indexes_are_defined() -> None:
    """Verify P1 health tables expose deterministic constraints and lookup indexes."""
    health_sync_batch = cast(Table, HealthSyncBatch.__table__)
    health_daily_summary = cast(Table, HealthDailySummary.__table__)
    sync_constraint_names = {constraint.name for constraint in health_sync_batch.constraints}
    summary_constraint_names = {constraint.name for constraint in health_daily_summary.constraints}
    sync_index_names = {
        index.name for index in health_sync_batch.indexes if isinstance(index, Index)
    }
    summary_index_names = {
        index.name for index in health_daily_summary.indexes if isinstance(index, Index)
    }

    assert "uq_health_sync_batches_owner_client_batch" in sync_constraint_names
    assert "ck_health_sync_batches_source_platform_allowed" in sync_constraint_names
    assert "ck_health_sync_batches_accepted_rejected_count_valid" in sync_constraint_names
    assert "uq_health_daily_summaries_owner_date_platform" in summary_constraint_names
    assert "ck_health_daily_summaries_health_metric_present" in summary_constraint_names
    assert "ck_health_daily_summaries_weight_kg_range" in summary_constraint_names
    assert "ix_health_sync_batches_owner_synced_at" in sync_index_names
    assert "ix_health_daily_summaries_owner_measured_date" in summary_index_names
    assert "ix_health_daily_summaries_owner_source_date" in summary_index_names


def test_health_profile_tables_are_registered_without_raw_payload_columns() -> None:
    """Verify Phase 3 health profile tables store bounded structured values only."""
    body_profile = cast(Table, BodyProfileSnapshot.__table__)
    metric_sample = cast(Table, HealthMetricSample.__table__)

    assert "body_profile_snapshots" in Base.metadata.tables
    assert "health_metric_samples" in Base.metadata.tables
    assert {
        "owner_subject",
        "effective_at",
        "source",
        "sex",
        "birth_year",
        "height_cm",
        "weight_kg",
        "waist_cm",
        "pregnancy_status",
        "lactation_status",
        "activity_level",
        "consent_snapshot",
        "superseded_at",
    }.issubset(set(body_profile.c.keys()))
    assert {
        "owner_subject",
        "metric_type",
        "measured_at",
        "value_numeric",
        "unit",
        "source_platform",
        "source_record_hash",
        "quality_flags",
    }.issubset(set(metric_sample.c.keys()))

    all_columns = set(body_profile.c.keys()) | set(metric_sample.c.keys())
    forbidden_columns = {
        "access_token",
        "device_payload",
        "image_bytes",
        "provider_payload",
        "raw_payload",
        "request_headers",
        "secret",
    }

    assert forbidden_columns.isdisjoint(all_columns)


def test_health_profile_constraints_and_indexes_are_fail_closed() -> None:
    """Verify Phase 3 health profile tables expose deterministic safety constraints."""
    body_profile = cast(Table, BodyProfileSnapshot.__table__)
    metric_sample = cast(Table, HealthMetricSample.__table__)
    profile_constraint_names = {
        constraint.name
        for constraint in body_profile.constraints
        if isinstance(constraint, CheckConstraint)
    }
    metric_constraint_names = {
        constraint.name
        for constraint in metric_sample.constraints
        if isinstance(constraint, CheckConstraint)
    }
    metric_unique_names = {constraint.name for constraint in metric_sample.constraints}
    profile_index_names = {index.name for index in body_profile.indexes if isinstance(index, Index)}
    metric_index_names = {index.name for index in metric_sample.indexes if isinstance(index, Index)}

    assert "ck_body_profile_snapshots_body_profile_owner_subject_nonempty" in (
        profile_constraint_names
    )
    assert "ck_body_profile_snapshots_body_profile_source_allowed" in profile_constraint_names
    assert "ck_body_profile_snapshots_body_profile_height_cm_range" in profile_constraint_names
    assert "ck_body_profile_snapshots_body_profile_consent_snapshot_object" in (
        profile_constraint_names
    )
    assert "ck_health_metric_samples_health_metric_owner_subject_nonempty" in (
        metric_constraint_names
    )
    assert "ck_health_metric_samples_health_metric_type_allowed" in metric_constraint_names
    assert "ck_health_metric_samples_health_metric_source_record_hash_length" in (
        metric_constraint_names
    )
    assert "ck_health_metric_samples_health_metric_quality_flags_array" in (metric_constraint_names)
    assert "uq_health_metric_samples_owner_source_hash" in metric_unique_names
    assert "ix_body_profile_snapshots_owner_effective_at" in profile_index_names
    assert "ix_health_metric_samples_owner_measured_at" in metric_index_names
    assert "ix_health_metric_samples_owner_metric_measured_at" in metric_index_names


def test_learning_tables_are_registered_without_raw_payload_columns() -> None:
    """Verify learning tables store references and embeddings without raw payloads."""
    image_object = cast(Table, LearningImageObject.__table__)
    embedding_job = cast(Table, ImageEmbeddingJob.__table__)
    embedding_record = cast(Table, ImageEmbeddingRecord.__table__)

    assert "learning_image_objects" in Base.metadata.tables
    assert "image_embedding_jobs" in Base.metadata.tables
    assert "image_embedding_records" in Base.metadata.tables
    assert {
        "owner_subject_hash",
        "analysis_id",
        "image_sha256",
        "object_uri",
        "retained_until",
        "consent_snapshot",
    }.issubset(set(image_object.c.keys()))
    assert {
        "image_object_id",
        "analysis_id",
        "owner_subject_hash",
        "embedding_model",
        "metadata_snapshot",
    }.issubset(set(embedding_job.c.keys()))
    assert {
        "owner_subject_hash",
        "analysis_id",
        "image_object_id",
        "embedding_dimensions",
        "embedding",
        "metadata",
    }.issubset(set(embedding_record.c.keys()))

    all_columns = set(image_object.c.keys()) | set(embedding_job.c.keys())
    all_columns |= set(embedding_record.c.keys())
    forbidden_columns = {"raw_image", "raw_image_bytes", "image_base64", "raw_ocr_text"}

    assert forbidden_columns.isdisjoint(all_columns)


def test_learning_constraints_and_indexes_are_defined() -> None:
    """Verify learning tables expose deterministic constraints and indexes."""
    image_object = cast(Table, LearningImageObject.__table__)
    embedding_job = cast(Table, ImageEmbeddingJob.__table__)
    embedding_record = cast(Table, ImageEmbeddingRecord.__table__)
    image_constraint_names = {constraint.name for constraint in image_object.constraints}
    job_constraint_names = {constraint.name for constraint in embedding_job.constraints}
    record_constraint_names = {constraint.name for constraint in embedding_record.constraints}
    job_index_names = {index.name for index in embedding_job.indexes if isinstance(index, Index)}
    record_index_names = {
        index.name for index in embedding_record.indexes if isinstance(index, Index)
    }

    assert "uq_learning_image_objects_owner_analysis_hash" in image_constraint_names
    assert (
        "ck_learning_image_objects_learning_image_object_status_allowed" in image_constraint_names
    )
    assert "uq_image_embedding_jobs_object_model" in job_constraint_names
    assert "ck_image_embedding_jobs_image_embedding_job_status_allowed" in job_constraint_names
    assert "uq_image_embedding_records_owner_analysis_model_hash" in record_constraint_names
    assert "ck_image_embedding_records_embedding_dimensions_positive" in record_constraint_names
    assert "ix_image_embedding_jobs_status_next_run" in job_index_names
    assert "ix_image_embedding_records_owner_created_at" in record_index_names


def test_retraining_tables_are_registered_without_raw_payload_columns() -> None:
    """Verify retraining lineage stores sanitized labels and private refs only."""
    dataset_version = cast(Table, LearningDatasetVersion.__table__)
    dataset_item = cast(Table, LearningDatasetItem.__table__)
    annotation_task = cast(Table, AnnotationTask.__table__)
    training_run = cast(Table, ModelTrainingRun.__table__)
    registry_entry = cast(Table, ModelRegistryEntry.__table__)
    eval_result = cast(Table, ModelEvalResult.__table__)

    assert "learning_dataset_versions" in Base.metadata.tables
    assert "learning_dataset_items" in Base.metadata.tables
    assert "annotation_tasks" in Base.metadata.tables
    assert "model_training_runs" in Base.metadata.tables
    assert "model_registry" in Base.metadata.tables
    assert "model_eval_results" in Base.metadata.tables
    assert {
        "dataset_key",
        "version",
        "status",
        "manifest_hash",
        "privacy_review_status",
        "created_by_hash",
        "frozen_at",
    }.issubset(set(dataset_version.c.keys()))
    assert {
        "dataset_version_id",
        "owner_subject_hash",
        "media_object_id",
        "learning_image_object_id",
        "source_domain",
        "task_type",
        "label_status",
        "split",
        "label_snapshot",
        "label_hash",
        "quality_score",
        "consent_snapshot",
        "retained_until",
        "revoked_at",
    }.issubset(set(dataset_item.c.keys()))
    assert {
        "owner_subject_hash",
        "media_object_id",
        "learning_image_object_id",
        "task_type",
        "status",
        "assignee_role",
        "label_snapshot",
        "review_notes_code",
        "reviewer_hash",
        "completed_at",
    }.issubset(set(annotation_task.c.keys()))
    assert {
        "model_family",
        "base_model",
        "dataset_version_id",
        "hyperparam_snapshot",
        "metrics_snapshot",
        "artifact_ref",
        "status",
    }.issubset(set(training_run.c.keys()))
    assert {
        "task_type",
        "model_version",
        "training_run_id",
        "artifact_ref",
        "deployment_status",
        "metric_gate_snapshot",
        "rollback_model_id",
        "approved_by_hash",
        "approved_at",
    }.issubset(set(registry_entry.c.keys()))
    assert {
        "model_id",
        "eval_dataset_version_id",
        "metric_name",
        "metric_value",
        "subgroup_key",
        "failure_bucket",
    }.issubset(set(eval_result.c.keys()))

    all_columns = (
        set(dataset_version.c.keys())
        | set(dataset_item.c.keys())
        | set(annotation_task.c.keys())
        | set(training_run.c.keys())
        | set(registry_entry.c.keys())
        | set(eval_result.c.keys())
    )
    forbidden_columns = {
        "access_token",
        "image_bytes",
        "object_uri",
        "owner_subject",
        "provider_payload",
        "public_url",
        "raw_image",
        "raw_ocr_text",
        "raw_payload",
        "request_headers",
        "secret",
        "signed_url",
    }

    assert forbidden_columns.isdisjoint(all_columns)


def test_retraining_constraints_and_indexes_are_fail_closed() -> None:
    """Verify retraining lineage tables constrain private refs and revoke lookup."""
    dataset_version = cast(Table, LearningDatasetVersion.__table__)
    dataset_item = cast(Table, LearningDatasetItem.__table__)
    annotation_task = cast(Table, AnnotationTask.__table__)
    training_run = cast(Table, ModelTrainingRun.__table__)
    registry_entry = cast(Table, ModelRegistryEntry.__table__)
    eval_result = cast(Table, ModelEvalResult.__table__)
    dataset_constraint_names = {
        constraint.name
        for constraint in dataset_version.constraints
        if isinstance(constraint, CheckConstraint)
    }
    item_constraint_names = {
        constraint.name
        for constraint in dataset_item.constraints
        if isinstance(constraint, CheckConstraint)
    }
    annotation_constraint_names = {
        constraint.name
        for constraint in annotation_task.constraints
        if isinstance(constraint, CheckConstraint)
    }
    training_constraint_names = {
        constraint.name
        for constraint in training_run.constraints
        if isinstance(constraint, CheckConstraint)
    }
    registry_constraint_names = {
        constraint.name
        for constraint in registry_entry.constraints
        if isinstance(constraint, CheckConstraint)
    }
    eval_constraint_names = {
        constraint.name
        for constraint in eval_result.constraints
        if isinstance(constraint, CheckConstraint)
    }
    item_index_names = {index.name for index in dataset_item.indexes if isinstance(index, Index)}
    annotation_index_names = {
        index.name for index in annotation_task.indexes if isinstance(index, Index)
    }
    training_index_names = {
        index.name for index in training_run.indexes if isinstance(index, Index)
    }
    registry_index_names = {
        index.name for index in registry_entry.indexes if isinstance(index, Index)
    }

    assert "ck_learning_dataset_versions_learning_dataset_key_allowed" in (dataset_constraint_names)
    assert "ck_learning_dataset_versions_learning_dataset_privacy_review_status_allowed" in (
        dataset_constraint_names
    )
    assert "ck_learning_dataset_items_dataset_item_owner_hash_length" in item_constraint_names
    assert "ck_learning_dataset_items_dataset_item_source_required" in item_constraint_names
    assert "ck_learning_dataset_items_dataset_item_label_snapshot_object" in item_constraint_names
    assert "ck_learning_dataset_items_dataset_item_consent_snapshot_object" in item_constraint_names
    assert "ck_annotation_tasks_annotation_task_owner_hash_length" in annotation_constraint_names
    assert "ck_annotation_tasks_annotation_task_label_snapshot_object" in (
        annotation_constraint_names
    )
    assert "ck_model_training_runs_model_training_artifact_ref_private" in (
        training_constraint_names
    )
    assert "ck_model_training_runs_model_training_metrics_snapshot_object" in (
        training_constraint_names
    )
    assert "ck_model_registry_model_registry_artifact_ref_private" in registry_constraint_names
    assert "ck_model_registry_model_registry_metric_gate_snapshot_object" in (
        registry_constraint_names
    )
    assert "ck_model_eval_results_model_eval_metric_value_nonnegative" in eval_constraint_names
    assert "ix_learning_dataset_items_owner_status" in item_index_names
    assert "ix_annotation_tasks_owner_status" in annotation_index_names
    assert "ix_model_training_runs_family_status" in training_index_names
    assert "ix_model_registry_task_status" in registry_index_names


def test_media_tables_are_registered_without_raw_payload_columns() -> None:
    """Verify backend-only media tables retain private references only."""
    media_object = cast(Table, MediaObject.__table__)
    processing_run = cast(Table, MediaProcessingRun.__table__)
    supplement_image_evidence = cast(Table, SupplementImageEvidence.__table__)

    assert "media_objects" in Base.metadata.tables
    assert "media_processing_runs" in Base.metadata.tables
    assert "supplement_image_evidence" in Base.metadata.tables
    assert {
        "owner_subject_hash",
        "domain",
        "source_run_id",
        "object_storage_provider",
        "object_ref",
        "object_version_id",
        "image_sha256",
        "image_mime_type",
        "image_size_bytes",
        "retained_until",
        "consent_snapshot",
        "deleted_at",
    }.issubset(set(media_object.c.keys()))
    assert {
        "media_object_id",
        "pipeline_type",
        "provider",
        "model_version",
        "status",
        "confidence",
        "output_hash",
        "sanitized_snapshot",
        "warning_codes",
        "error_code",
    }.issubset(set(processing_run.c.keys()))
    assert {
        "analysis_run_id",
        "media_object_id",
        "image_role",
        "quality_status",
        "quality_codes",
        "roi_snapshot",
    }.issubset(set(supplement_image_evidence.c.keys()))

    all_columns = (
        set(media_object.c.keys())
        | set(processing_run.c.keys())
        | set(supplement_image_evidence.c.keys())
    )
    forbidden_columns = {
        "image_base64",
        "image_bytes",
        "provider_payload",
        "raw_image",
        "raw_image_bytes",
        "raw_ocr_text",
        "request_headers",
        "secret",
    }

    assert forbidden_columns.isdisjoint(all_columns)


def test_media_constraints_and_indexes_are_fail_closed() -> None:
    """Verify media tables constrain private object references and lookup paths."""
    media_object = cast(Table, MediaObject.__table__)
    processing_run = cast(Table, MediaProcessingRun.__table__)
    supplement_image_evidence = cast(Table, SupplementImageEvidence.__table__)
    object_constraint_names = {
        constraint.name
        for constraint in media_object.constraints
        if isinstance(constraint, CheckConstraint)
    }
    processing_constraint_names = {
        constraint.name
        for constraint in processing_run.constraints
        if isinstance(constraint, CheckConstraint)
    }
    evidence_constraint_names = {
        constraint.name
        for constraint in supplement_image_evidence.constraints
        if isinstance(constraint, CheckConstraint)
    }
    object_index_names = {index.name for index in media_object.indexes if isinstance(index, Index)}
    processing_index_names = {
        index.name for index in processing_run.indexes if isinstance(index, Index)
    }
    evidence_index_names = {
        index.name for index in supplement_image_evidence.indexes if isinstance(index, Index)
    }

    assert "ck_media_objects_media_object_domain_allowed" in object_constraint_names
    assert "ck_media_objects_media_object_storage_provider_allowed" in object_constraint_names
    assert "ck_media_objects_media_object_ref_private" in object_constraint_names
    assert "ck_media_objects_media_object_status_allowed" in object_constraint_names
    assert "ck_media_processing_runs_media_processing_pipeline_type_allowed" in (
        processing_constraint_names
    )
    assert "ck_media_processing_runs_media_processing_confidence_range" in (
        processing_constraint_names
    )
    assert "ck_supplement_image_evidence_image_role_allowed" in evidence_constraint_names
    assert "ck_supplement_image_evidence_quality_status_allowed" in evidence_constraint_names
    assert "ck_supplement_image_evidence_quality_codes_array" in evidence_constraint_names
    assert "ck_supplement_image_evidence_roi_snapshot_object" in evidence_constraint_names
    assert "ix_media_objects_owner_domain_created_at" in object_index_names
    assert "ix_media_objects_retained_until" in object_index_names
    assert "ix_media_processing_runs_pipeline_status" in processing_index_names
    assert "ix_supplement_image_evidence_analysis_run_id" in evidence_index_names
    assert "ix_supplement_image_evidence_quality_status" in evidence_index_names


def test_meal_tables_are_registered_without_raw_payload_columns() -> None:
    """Verify meal and food image tables retain sanitized preview metadata only."""
    food_cuisine = cast(Table, FoodCuisine.__table__)
    food_course = cast(Table, FoodCourse.__table__)
    food_catalog_item = cast(Table, FoodCatalogItem.__table__)
    meal_record = cast(Table, MealRecord.__table__)
    meal_food_item = cast(Table, MealFoodItem.__table__)
    food_image_run = cast(Table, FoodImageAnalysisRun.__table__)

    assert "food_cuisines" in Base.metadata.tables
    assert "food_courses" in Base.metadata.tables
    assert "food_catalog_items" in Base.metadata.tables
    assert "meal_records" in Base.metadata.tables
    assert "meal_food_items" in Base.metadata.tables
    assert "food_image_analysis_runs" in Base.metadata.tables
    assert {
        "cuisine_code",
        "display_name_ko",
        "display_name_en",
        "sort_order",
        "is_active",
    }.issubset(set(food_cuisine.c.keys()))
    assert {
        "cuisine_id",
        "course_code",
        "display_name_ko",
        "display_name_en",
        "sort_order",
        "is_active",
    }.issubset(set(food_course.c.keys()))
    assert {
        "cuisine_id",
        "course_id",
        "canonical_name_ko",
        "canonical_name_en",
        "aliases",
        "nutrition_reference",
        "source",
        "source_payload",
        "is_active",
    }.issubset(set(food_catalog_item.c.keys()))
    assert {
        "owner_subject",
        "client_request_id",
        "eaten_at",
        "meal_type",
        "source",
        "status",
        "nutrition_summary",
        "confidence",
        "confirmed_at",
        "deleted_at",
    }.issubset(set(meal_record.c.keys()))
    assert {
        "meal_id",
        "food_name_text",
        "food_catalog_item_id",
        "canonical_food_id",
        "portion_amount",
        "portion_unit",
        "kcal",
        "carb_g",
        "protein_g",
        "fat_g",
        "sodium_mg",
        "source",
        "confidence",
        "sort_order",
    }.issubset(set(meal_food_item.c.keys()))
    assert {
        "owner_subject",
        "client_request_id",
        "media_object_id",
        "meal_id",
        "image_sha256",
        "image_mime_type",
        "image_size_bytes",
        "detector_model",
        "classifier_model",
        "status",
        "detected_items_snapshot",
        "nutrition_estimate_snapshot",
        "warning_codes",
    }.issubset(set(food_image_run.c.keys()))

    all_columns = (
        set(food_cuisine.c.keys())
        | set(food_course.c.keys())
        | set(food_catalog_item.c.keys())
        | set(meal_record.c.keys())
        | set(meal_food_item.c.keys())
        | set(food_image_run.c.keys())
    )
    forbidden_columns = {
        "image_base64",
        "image_bytes",
        "provider_payload",
        "raw_image",
        "raw_image_bytes",
        "raw_ocr_text",
        "request_headers",
        "secret",
    }

    assert forbidden_columns.isdisjoint(all_columns)


def test_meal_constraints_and_indexes_are_fail_closed() -> None:
    """Verify meal/food image tables constrain user-scoped sanitized records."""
    food_cuisine = cast(Table, FoodCuisine.__table__)
    food_course = cast(Table, FoodCourse.__table__)
    food_catalog_item = cast(Table, FoodCatalogItem.__table__)
    meal_record = cast(Table, MealRecord.__table__)
    meal_food_item = cast(Table, MealFoodItem.__table__)
    food_image_run = cast(Table, FoodImageAnalysisRun.__table__)
    cuisine_constraint_names = {
        constraint.name
        for constraint in food_cuisine.constraints
        if isinstance(constraint, CheckConstraint)
    }
    course_constraint_names = {
        constraint.name
        for constraint in food_course.constraints
        if isinstance(constraint, CheckConstraint)
    }
    food_catalog_constraint_names = {
        constraint.name
        for constraint in food_catalog_item.constraints
        if isinstance(constraint, CheckConstraint)
    }
    meal_constraint_names = {
        constraint.name
        for constraint in meal_record.constraints
        if isinstance(constraint, CheckConstraint)
    }
    item_constraint_names = {
        constraint.name
        for constraint in meal_food_item.constraints
        if isinstance(constraint, CheckConstraint)
    }
    run_constraint_names = {
        constraint.name
        for constraint in food_image_run.constraints
        if isinstance(constraint, CheckConstraint)
    }
    cuisine_index_names = {index.name for index in food_cuisine.indexes if isinstance(index, Index)}
    course_index_names = {index.name for index in food_course.indexes if isinstance(index, Index)}
    food_catalog_index_names = {
        index.name for index in food_catalog_item.indexes if isinstance(index, Index)
    }
    meal_index_names = {index.name for index in meal_record.indexes if isinstance(index, Index)}
    item_index_names = {index.name for index in meal_food_item.indexes if isinstance(index, Index)}
    run_index_names = {index.name for index in food_image_run.indexes if isinstance(index, Index)}

    assert "ck_food_cuisines_cuisine_code_nonempty" in cuisine_constraint_names
    assert "ck_food_courses_course_code_nonempty" in course_constraint_names
    assert "ck_food_catalog_items_aliases_array" in food_catalog_constraint_names
    assert "ck_food_catalog_items_nutrition_reference_object" in food_catalog_constraint_names
    assert "ck_meal_records_owner_subject_nonempty" in meal_constraint_names
    assert "ck_meal_records_meal_type_allowed" in meal_constraint_names
    assert "ck_meal_records_meal_status_allowed" in meal_constraint_names
    assert "ck_meal_records_nutrition_summary_object" in meal_constraint_names
    assert "ck_meal_food_items_food_name_text_nonempty" in item_constraint_names
    assert "ck_meal_food_items_meal_food_source_allowed" in item_constraint_names
    assert "ck_meal_food_items_meal_food_confidence_range" in item_constraint_names
    assert "ck_food_image_analysis_runs_image_sha256_length" in run_constraint_names
    assert "ck_food_image_analysis_runs_food_image_status_allowed" in run_constraint_names
    assert "ck_food_image_analysis_runs_detected_items_snapshot_object" in run_constraint_names
    assert "ck_food_image_analysis_runs_warning_codes_array" in run_constraint_names
    assert "ix_food_cuisines_active_sort" in cuisine_index_names
    assert "ix_food_courses_cuisine_sort" in course_index_names
    assert "ix_food_catalog_items_cuisine_course" in food_catalog_index_names
    assert "ix_meal_records_owner_eaten_at" in meal_index_names
    assert "ix_meal_records_owner_status" in meal_index_names
    assert "ix_meal_food_items_food_catalog_item_id" in item_index_names
    assert "ix_meal_food_items_meal_id" in item_index_names
    assert "ix_food_image_analysis_runs_owner_created_at" in run_index_names
    assert "ix_food_image_analysis_runs_owner_status_created_at" in run_index_names


def test_health_daily_summary_pk_is_composite_with_measured_date() -> None:
    """Verify the PK widens to (id, measured_date) so the table is hypertable-ready.

    TimescaleDB requires every UNIQUE/PRIMARY KEY constraint on a hypertable to
    include the time partitioning column. PR-O widens the PK to satisfy that
    rule; PR-P then performs the opt-in ``create_hypertable`` conversion.
    """
    table = cast(Table, HealthDailySummary.__table__)
    pk_column_names = [column.name for column in table.primary_key.columns]

    assert pk_column_names == ["id", "measured_date"]
    assert table.primary_key.name == "pk_health_daily_summaries"
