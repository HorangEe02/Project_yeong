"""Application settings security tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import SecretStr, ValidationError
from src.config import DEFAULT_DATABASE_URL, DEFAULT_PRIVACY_HASH_SECRET, Settings

PROJECT_ROOT = Path(__file__).resolve().parents[4]
READINESS_SETTINGS_PATH = PROJECT_ROOT / "config" / "implementation-readiness.settings.json"
ENV_EXAMPLE_PATH = PROJECT_ROOT / "backend" / ".env.example"


def _load_json_object(path: Path) -> dict[str, object]:
    """Load a JSON document and verify it is an object.

    Args:
        path: JSON file path.

    Returns:
        Parsed JSON object with string keys.
    """
    raw_value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(raw_value, dict)
    parsed: dict[str, object] = {}
    for key, value in raw_value.items():
        assert isinstance(key, str)
        parsed[key] = value
    return parsed


def _object_field(mapping: dict[str, object], key: str) -> dict[str, object]:
    """Return a nested JSON object field.

    Args:
        mapping: Parent JSON object.
        key: Nested object key.

    Returns:
        Nested JSON object with string keys.
    """
    raw_value = mapping[key]
    assert isinstance(raw_value, dict)
    parsed: dict[str, object] = {}
    for nested_key, nested_value in raw_value.items():
        assert isinstance(nested_key, str)
        parsed[nested_key] = nested_value
    return parsed


def _env_example_value(name: str) -> str:
    """Return one raw value from the backend example environment file.

    Args:
        name: Environment variable name.

    Returns:
        Raw value string from ``backend/.env.example``.

    Raises:
        AssertionError: If the key is absent from the example file.
    """
    prefix = f"{name}="
    for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"{name} missing from backend/.env.example")


def _valid_production_kwargs() -> dict[str, Any]:
    """Return a valid production settings baseline.

    Returns:
        Keyword arguments accepted by Settings.
    """
    return {
        "_env_file": None,
        "environment": "production",
        "database_url": "postgresql+asyncpg://lemon_prod:secret@db.example.com:5432/lemon",  # pragma: allowlist secret
        "allowed_origins": ["https://app.example.com"],
        "allowed_hosts": ["api.example.com"],
        "auth_mode": "jwt",
        "jwt_issuer": "https://auth.example.com/",
        "jwt_audience": "lemon-api",
        "jwt_jwks_url": "https://auth.example.com/.well-known/jwks.json",
        "jwt_expected_token_type": "at+jwt",
        "privacy_hash_secret": "prod-privacy-hash-secret-at-least-32",  # pragma: allowlist secret
        "kdris_data_version": "2025",
        "kdris_data_path": "data/nutrition_reference/kdris/kdris_2025.csv",
        "allow_sample_kdris": False,
    }


def test_default_development_settings_load(  # noqa: PLR0915
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify development defaults remain usable for local work."""
    monkeypatch.delenv("GOOGLE_CLOUD_API_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.supabase_project_ref is None
    assert settings.supabase_url is None
    assert settings.supabase_publishable_key is None
    assert settings.supabase_secret_key is None
    assert settings.supabase_access_token is None
    assert settings.supabase_db_url is None
    assert settings.supabase_mcp_read_only is True
    assert settings.supabase_mcp_features == "database,docs,debugging,storage"
    assert settings.supabase_storage_private_bucket == "learning-images"
    assert settings.supabase_storage_s3_access_key_id is None
    assert settings.supabase_storage_s3_secret_access_key is None
    assert settings.media_object_storage_provider == "disabled"
    assert "testserver" in settings.allowed_hosts
    assert "10.0.2.2" in settings.allowed_hosts
    assert settings.auth_mode == "disabled"
    assert settings.supplement_image_max_bytes == 5 * 1024 * 1024
    assert settings.supplement_image_max_pixels == 12_000_000
    assert settings.supplement_preview_ttl_minutes == 30
    # Raw-OCR-text retention opt-in defaults OFF to keep the EXTERNAL_OCR_PROCESSING
    # consent promise ("raw OCR text are not stored") accurate.
    assert settings.store_raw_ocr_text is False
    assert settings.regulated_document_preview_ttl_minutes == 30
    assert settings.sensitive_document_original_image_retention_seconds == 0
    assert not settings.feature_hall_lite_weight_prediction
    assert settings.weight_prediction_engine == "static_7step"
    assert settings.feature_prescription_ocr_intake is False
    assert settings.feature_lab_result_ocr_intake is False
    assert settings.feature_dosage_change_recommendation is False
    assert settings.feature_medication_safety_alert is False
    assert settings.ocr_primary_provider == "paddleocr"
    assert settings.allow_external_ocr is False
    assert settings.google_vision_auth_mode == "adc"
    assert settings.allow_google_api_key_auth is False
    assert settings.google_cloud_api_key is None
    assert settings.google_cloud_project is None
    assert settings.google_vision_location == "global"
    assert settings.google_vision_feature == "document_text_detection"
    assert settings.google_vision_language_hints == []
    assert settings.google_vision_timeout_seconds == 15
    assert settings.google_vision_max_retries == 2
    assert settings.enable_multimodal_llm is False
    assert settings.ollama_model == "gemma4:e4b"
    assert settings.ollama_vision_model == "gemma4:e4b"
    assert settings.allow_external_llm is False
    assert settings.llm_wiki_retrieval_enabled is True
    assert str(settings.llm_wiki_path) == "/Volumes/Corsair EX400U Media/LLM-WIKI"
    assert settings.llm_wiki_max_sources == 4
    assert settings.llm_wiki_excerpt_chars == 700
    assert settings.multimodal_ocr_assist_policy == "disabled"
    assert settings.ocr_secondary_merge_policy == "disabled"
    assert settings.ocr_merge_dedup_threshold == 0.92
    assert settings.ocr_merge_max_supplement_lines == 40
    assert settings.ocr_ensemble_verification_mode == "inherit_sample"
    assert settings.enable_multimodal_verification is False
    assert settings.multimodal_verification_sample_rate == 0.0
    assert settings.multimodal_verification_threshold == 0.80
    assert settings.enable_vision_classifier is False
    assert settings.vision_classifier_model == "yolo26n.pt"
    assert settings.enable_food_yolo_detector is False
    assert settings.meal_yolo_model_path is None
    assert settings.meal_yolo_model_label == "food_yolo_local"
    assert settings.meal_yolo_min_confidence == 0.25
    assert settings.meal_yolo_max_detections == 20
    assert settings.enable_food_dino_classifier is False
    assert settings.meal_food_classifier_module_dir.endswith("Food-backend/src/classifier")
    assert settings.meal_food_classifier_exp16b_model_path is not None
    assert settings.meal_food_classifier_exp16b_model_path.endswith("Food-backend/best.pt")
    assert settings.meal_food_classifier_probe_path is not None
    assert settings.meal_food_classifier_probe_path.endswith(
        "Food-backend/src/classifier/probe_head.pt"
    )
    assert settings.meal_food_classifier_nutrition_csv_path is not None
    assert settings.meal_food_classifier_nutrition_csv_path.endswith(
        "Food-backend/src/classifier/nutrition/food_nutrition_40class.csv"
    )
    assert settings.meal_food_classifier_model_label == "food_dino_exp16b"
    assert settings.meal_food_classifier_gate_confidence == 0.10
    assert settings.meal_food_classifier_max_px == 896
    assert settings.ocr_roi_preprocessing_policy == "disabled"
    assert settings.ocr_roi_crop_padding_ratio == 0.08
    assert settings.ocr_roi_crop_min_padding_px == 16
    assert settings.ocr_roi_crop_max_padding_px == 96
    assert settings.enable_local_ocr is True
    assert settings.local_ocr_secondary_text_recognition_model_dir is None
    assert settings.local_ocr_text_det_unclip_ratio == 3.0
    assert settings.local_ocr_provider == "paddleocr"
    assert settings.local_ocr_language == "korean"
    assert settings.local_ocr_device is None
    assert settings.local_ocr_confidence_threshold == 0.75
    assert settings.local_ocr_model_profile == "mobile"
    assert settings.local_ocr_preprocess_mode == "autocontrast"
    assert settings.enable_clova_ocr is False
    assert settings.vision_roi_min_confidence == 0.50
    assert settings.vision_roi_max_detections == 16
    assert settings.vision_roi_allowed_classes == [
        "product_identity",
        "supplement_facts",
        "ingredient_amounts",
        "precautions",
        "allergen_warning",
        "intake_method",
        "other_ingredients",
        "functional_claims",
        "supplement_label",
        "supplement_bottle",
        "blister_pack",
    ]
    assert settings.enable_image_learning_pipeline is False
    assert settings.enable_pgvector_storage is False
    assert settings.embedding_model == "clip-ViT-B-32"
    assert settings.embedding_dimensions is None
    assert settings.image_retention_days == 0
    assert settings.learning_object_storage_provider == "disabled"


def test_google_cloud_api_key_can_be_loaded_as_secret() -> None:
    """Verify local Google Vision REST API key input is accepted as a secret value."""
    settings = Settings(
        _env_file=None,
        google_cloud_api_key=SecretStr("test-google-cloud-api-key"),
    )

    assert settings.google_cloud_api_key is not None
    assert settings.google_cloud_api_key.get_secret_value() == "test-google-cloud-api-key"


def test_env_example_matches_supplement_section_yolo_defaults() -> None:
    """Verify the example env enables the same section-ROI contract as Settings.

    The supplement OCR pipeline depends on YOLO section boxes for facts,
    precautions, intake method, and ingredients. Keeping ``.env.example`` aligned
    with ``Settings`` prevents a copied local config from silently filtering out
    warning/allergy regions.
    """
    settings = Settings(_env_file=None)

    assert _env_example_value("VISION_CLASSIFIER_MODEL") == settings.vision_classifier_model
    assert json.loads(_env_example_value("VISION_ROI_ALLOWED_CLASSES")) == (
        settings.vision_roi_allowed_classes
    )
    assert _env_example_value("ENABLE_FOOD_DINO_CLASSIFIER") == "false"
    assert _env_example_value("MEAL_FOOD_CLASSIFIER_MODEL_LABEL") == (
        settings.meal_food_classifier_model_label
    )


def test_google_cloud_api_key_can_be_loaded_from_dotenv(tmp_path: Path) -> None:
    """Verify Google Vision API key placeholders can be filled through dotenv."""
    env_file = tmp_path / ".env"
    env_file.write_text(  # pragma: allowlist secret
        "GOOGLE_CLOUD_API_KEY=test-dotenv-google-key\n",  # pragma: allowlist secret
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.google_cloud_api_key is not None
    assert settings.google_cloud_api_key.get_secret_value() == "test-dotenv-google-key"


def test_empty_google_cloud_api_key_dotenv_value_is_ignored(tmp_path: Path) -> None:
    """Verify an empty local dotenv placeholder does not become an active secret."""
    env_file = tmp_path / ".env"
    env_file.write_text("GOOGLE_CLOUD_API_KEY=\n", encoding="utf-8")

    settings = Settings(_env_file=env_file)

    assert settings.google_cloud_api_key is None


def test_supabase_inputs_can_be_loaded_from_dotenv(tmp_path: Path) -> None:
    """Verify Supabase MCP and hosted project inputs stay backend-scoped."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "SUPABASE_PROJECT_REF=lemonprojectrefdev01",  # pragma: allowlist secret
                "SUPABASE_URL=https://lemonprojectrefdev01.supabase.co",
                "SUPABASE_PUBLISHABLE_KEY=sb_publishable_placeholder",  # pragma: allowlist secret
                "SUPABASE_SECRET_KEY=sb_secret_placeholder",  # pragma: allowlist secret
                "SUPABASE_ACCESS_TOKEN=sbp_placeholder",  # pragma: allowlist secret
                "SUPABASE_DB_URL=postgresql://postgres:placeholder@db.example.com:5432/postgres",  # pragma: allowlist secret
                "SUPABASE_MCP_READ_ONLY=false",
                "SUPABASE_MCP_FEATURES=database,docs,debugging,storage",
                "SUPABASE_STORAGE_PRIVATE_BUCKET=learning-images",  # pragma: allowlist secret
                "SUPABASE_STORAGE_S3_ACCESS_KEY_ID=supabase_storage_access_key",  # pragma: allowlist secret
                "SUPABASE_STORAGE_S3_SECRET_ACCESS_KEY=supabase_storage_secret_key",  # pragma: allowlist secret
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.supabase_project_ref == "lemonprojectrefdev01"
    assert settings.supabase_url == "https://lemonprojectrefdev01.supabase.co"
    assert settings.supabase_publishable_key is not None
    assert settings.supabase_publishable_key.get_secret_value() == "sb_publishable_placeholder"
    assert settings.supabase_secret_key is not None
    assert settings.supabase_secret_key.get_secret_value() == "sb_secret_placeholder"
    assert settings.supabase_access_token is not None
    assert settings.supabase_access_token.get_secret_value() == "sbp_placeholder"
    assert settings.supabase_db_url is not None
    assert settings.supabase_db_url.get_secret_value().startswith("postgresql://")
    assert settings.supabase_mcp_read_only is False
    assert settings.supabase_mcp_features == "database,docs,debugging,storage"
    assert settings.supabase_storage_private_bucket == "learning-images"
    assert settings.supabase_storage_s3_access_key_id is not None
    assert (
        settings.supabase_storage_s3_access_key_id.get_secret_value()
        == "supabase_storage_access_key"
    )
    assert settings.supabase_storage_s3_secret_access_key is not None
    assert (
        settings.supabase_storage_s3_secret_access_key.get_secret_value()
        == "supabase_storage_secret_key"
    )


@pytest.mark.parametrize(
    "database_url",
    (
        "sqlite+aiosqlite:///tmp/lemon.db",
        "sqlite:///tmp/lemon.db",
        "postgresql://lemon:lemon@localhost:5432/lemon",  # pragma: allowlist secret
        "mysql+aiomysql://lemon:lemon@localhost:3306/lemon",  # pragma: allowlist secret
    ),
)
def test_database_url_must_use_postgresql_asyncpg(database_url: str) -> None:
    """Verify every runtime environment is pinned to PostgreSQL asyncpg."""
    with pytest.raises(ValidationError, match=r"postgresql\+asyncpg"):
        Settings(database_url=database_url)


def test_production_rejects_development_database_url() -> None:
    """Verify production cannot boot with the development database URL."""
    kwargs = _valid_production_kwargs()
    kwargs["database_url"] = DEFAULT_DATABASE_URL

    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(**kwargs)


def test_production_rejects_debug_logging() -> None:
    """Verify production cannot boot with DEBUG logging."""
    kwargs = _valid_production_kwargs()
    kwargs["log_level"] = "DEBUG"

    with pytest.raises(ValidationError, match="LOG_LEVEL"):
        Settings(**kwargs)


def test_production_rejects_external_llm() -> None:
    """Verify production cannot enable external LLM calls by default."""
    kwargs = _valid_production_kwargs()
    kwargs["allow_external_llm"] = True

    with pytest.raises(ValidationError, match="ALLOW_EXTERNAL_LLM"):
        Settings(**kwargs)


def test_production_rejects_wildcard_origins_and_hosts() -> None:
    """Verify production requires explicit origins and hosts."""
    kwargs = _valid_production_kwargs()
    kwargs["allowed_origins"] = ["*"]
    kwargs["allowed_hosts"] = ["*"]

    with pytest.raises(ValidationError, match="wildcards"):
        Settings(**kwargs)


def test_production_rejects_http_only_allowed_origin() -> None:
    """Verify production CORS origins must use https://."""
    kwargs = _valid_production_kwargs()
    kwargs["allowed_origins"] = ["http://insecure.example.com"]
    kwargs["allowed_hosts"] = ["api.example.com"]

    with pytest.raises(ValidationError, match="https://"):
        Settings(**kwargs)


def test_production_accepts_https_allowed_origins() -> None:
    """Verify production CORS https URLs are accepted."""
    kwargs = _valid_production_kwargs()
    kwargs["allowed_origins"] = ["https://lemonaid.example.com"]
    kwargs["allowed_hosts"] = ["api.lemonaid.example.com"]
    kwargs["ocr_primary_provider"] = "none"
    kwargs["enable_local_ocr"] = False

    settings = Settings(**kwargs)

    assert settings.allowed_origins == ["https://lemonaid.example.com"]


def test_staging_rejects_auth_mode_disabled() -> None:
    """Verify ``AUTH_MODE=disabled`` is forbidden outside development environments."""
    with pytest.raises(ValidationError, match="AUTH_MODE=disabled is forbidden"):
        Settings(_env_file=None, environment="staging", auth_mode="disabled")


def test_production_rejects_auth_mode_disabled_via_staging_guard() -> None:
    """Verify the staging guard also fires for production with ``AUTH_MODE=disabled``."""
    with pytest.raises(ValidationError, match="AUTH_MODE=disabled is forbidden"):
        Settings(_env_file=None, environment="production", auth_mode="disabled")


def test_development_accepts_auth_mode_disabled() -> None:
    """Verify dev environments retain ``AUTH_MODE=disabled`` so local smoke runs."""
    settings = Settings(_env_file=None, environment="development", auth_mode="disabled")
    assert settings.auth_mode == "disabled"


def test_production_requires_jwt_configuration() -> None:
    """Verify production user apps must be configured for OAuth/OIDC JWT."""
    kwargs = _valid_production_kwargs()
    kwargs["auth_mode"] = "disabled"
    kwargs["jwt_issuer"] = None

    with pytest.raises(ValidationError, match="AUTH_MODE=jwt"):
        Settings(**kwargs)


def test_production_rejects_sample_kdris_fixture() -> None:
    """Verify production cannot use the local KDRIs sample fixture."""
    kwargs = _valid_production_kwargs()
    kwargs["kdris_data_version"] = "2020-sample"
    kwargs["allow_sample_kdris"] = True

    with pytest.raises(ValidationError, match="KDRIS_DATA_VERSION=2025"):
        Settings(**kwargs)


def test_production_requires_explicit_kdris_data_path() -> None:
    """Verify production must explicitly pin the reviewed KDRIs dataset path."""
    kwargs = _valid_production_kwargs()
    kwargs["kdris_data_path"] = None

    with pytest.raises(ValidationError, match="KDRIS_DATA_PATH"):
        Settings(**kwargs)


def test_production_rejects_default_privacy_hash_secret() -> None:
    """Verify production audit hashes cannot use the development HMAC secret."""
    kwargs = _valid_production_kwargs()
    kwargs["privacy_hash_secret"] = DEFAULT_PRIVACY_HASH_SECRET

    with pytest.raises(ValidationError, match="PRIVACY_HASH_SECRET"):
        Settings(**kwargs)


def test_development_allows_default_privacy_hash_secret() -> None:
    """Verify the default secret remains usable in development environments.

    This sibling guard ensures a future refactor that moves the production
    rejection out of ``validate_runtime_security`` cannot also silently
    drop the secret from non-prod environments.
    """
    settings = Settings(_env_file=None, environment="development")
    assert settings.privacy_hash_secret.get_secret_value() == DEFAULT_PRIVACY_HASH_SECRET


def test_production_rejects_hall_lite_weight_prediction_without_signoff() -> None:
    """Verify production cannot enable Hall-lite before validation sign-off."""
    kwargs = _valid_production_kwargs()
    kwargs["feature_hall_lite_weight_prediction"] = True

    with pytest.raises(ValidationError, match="FEATURE_HALL_LITE_WEIGHT_PREDICTION"):
        Settings(**kwargs)


def test_production_rejects_multimodal_llm_without_signoff() -> None:
    """Verify production cannot enable multimodal LLM before gate sign-off."""
    kwargs = _valid_production_kwargs()
    kwargs["enable_multimodal_llm"] = True

    with pytest.raises(ValidationError, match="ENABLE_MULTIMODAL_LLM"):
        Settings(**kwargs)


def test_production_rejects_vision_classifier_without_signoff() -> None:
    """Verify production cannot enable YOLO ROI detection before gate sign-off."""
    kwargs = _valid_production_kwargs()
    kwargs["enable_vision_classifier"] = True

    with pytest.raises(ValidationError, match="ENABLE_VISION_CLASSIFIER"):
        Settings(**kwargs)


def test_development_food_yolo_requires_model_path() -> None:
    """Verify food YOLO cannot be enabled without an explicit local model path."""
    with pytest.raises(ValidationError, match="MEAL_YOLO_MODEL_PATH"):
        Settings(_env_file=None, enable_food_yolo_detector=True)


def test_development_food_yolo_settings_load() -> None:
    """Verify local food YOLO settings can be enabled for operator smoke tests."""
    settings = Settings(
        _env_file=None,
        enable_food_yolo_detector=True,
        meal_yolo_model_path="/app/Food-backend/best.pt",
        meal_yolo_model_label="food_yolo_local",
        meal_yolo_min_confidence=0.42,
        meal_yolo_max_detections=7,
    )

    assert settings.enable_food_yolo_detector is True
    assert settings.meal_yolo_model_path == "/app/Food-backend/best.pt"
    assert settings.meal_yolo_model_label == "food_yolo_local"
    assert settings.meal_yolo_min_confidence == 0.42
    assert settings.meal_yolo_max_detections == 7


def test_development_food_dino_classifier_requires_model_paths() -> None:
    """Verify food classifier cannot be enabled without required local artifacts."""
    with pytest.raises(ValidationError, match="MEAL_FOOD_CLASSIFIER_EXP16B_MODEL_PATH"):
        Settings(
            _env_file=None,
            enable_food_dino_classifier=True,
            meal_food_classifier_exp16b_model_path=None,
        )


def test_development_food_dino_classifier_settings_load() -> None:
    """Verify local food DINO settings can be enabled for operator smoke tests."""
    settings = Settings(
        _env_file=None,
        enable_food_dino_classifier=True,
        meal_food_classifier_module_dir="/app/Food-backend/src/classifier",
        meal_food_classifier_exp16b_model_path="/app/Food-backend/best.pt",
        meal_food_classifier_probe_path="/app/Food-backend/src/classifier/probe_head.pt",
        meal_food_classifier_nutrition_csv_path=(
            "/app/Food-backend/src/classifier/nutrition/food_nutrition_40class.csv"
        ),
        meal_food_classifier_model_label="food_dino_exp16b",
        meal_food_classifier_gate_confidence=0.11,
        meal_food_classifier_max_px=768,
    )

    assert settings.enable_food_dino_classifier is True
    assert settings.meal_food_classifier_module_dir == "/app/Food-backend/src/classifier"
    assert settings.meal_food_classifier_exp16b_model_path == "/app/Food-backend/best.pt"
    assert settings.meal_food_classifier_model_label == "food_dino_exp16b"
    assert settings.meal_food_classifier_gate_confidence == 0.11
    assert settings.meal_food_classifier_max_px == 768


def test_production_rejects_food_yolo_without_signoff() -> None:
    """Verify production cannot enable food YOLO before validation sign-off."""
    kwargs = _valid_production_kwargs()
    kwargs["enable_food_yolo_detector"] = True
    kwargs["meal_yolo_model_path"] = "/app/Food-backend/best.pt"

    with pytest.raises(ValidationError, match="ENABLE_FOOD_YOLO_DETECTOR"):
        Settings(**kwargs)


def test_production_rejects_food_dino_classifier_without_signoff() -> None:
    """Verify production cannot enable food DINO classifier before validation sign-off."""
    kwargs = _valid_production_kwargs()
    kwargs["enable_food_dino_classifier"] = True
    kwargs["meal_food_classifier_exp16b_model_path"] = "/app/Food-backend/best.pt"

    with pytest.raises(ValidationError, match="ENABLE_FOOD_DINO_CLASSIFIER"):
        Settings(**kwargs)


def test_production_rejects_roi_crop_policy_without_vision_gate() -> None:
    """Verify ROI crop policy cannot be enabled without the YOLO gate."""
    kwargs = _valid_production_kwargs()
    kwargs["ocr_roi_preprocessing_policy"] = "crop_before_primary"

    with pytest.raises(ValidationError, match="OCR_ROI_PREPROCESSING_POLICY"):
        Settings(**kwargs)


def test_production_rejects_multimodal_verification_without_llm_gate() -> None:
    """Verify verification cannot run without the local multimodal gate."""
    kwargs = _valid_production_kwargs()
    kwargs["enable_multimodal_verification"] = True
    kwargs["multimodal_verification_sample_rate"] = 1.0

    with pytest.raises(ValidationError, match="ENABLE_MULTIMODAL_VERIFICATION"):
        Settings(**kwargs)


def test_production_rejects_local_ocr_alongside_non_paddleocr_primary() -> None:
    """Verify local OCR fallback alongside a non-paddleocr primary needs sign-off."""
    kwargs = _valid_production_kwargs()
    kwargs["ocr_primary_provider"] = "none"
    kwargs["enable_local_ocr"] = True

    with pytest.raises(ValidationError, match="ENABLE_LOCAL_OCR"):
        Settings(**kwargs)


def test_production_rejects_paddleocr_primary_without_local_ocr() -> None:
    """Verify PaddleOCR primary cannot run while local OCR is disabled."""
    kwargs = _valid_production_kwargs()
    kwargs["ocr_primary_provider"] = "paddleocr"
    kwargs["enable_local_ocr"] = False

    with pytest.raises(ValidationError, match="OCR_PRIMARY_PROVIDER=paddleocr"):
        Settings(**kwargs)


def test_production_rejects_clova_ocr_without_external_gate() -> None:
    """Verify CLOVA fallback cannot run while external OCR is disabled."""
    kwargs = _valid_production_kwargs()
    kwargs["enable_clova_ocr"] = True
    kwargs["clova_ocr_api_url"] = "https://example.apigw.ntruss.com/custom/v1/infer"
    kwargs["clova_ocr_secret"] = "secret"  # pragma: allowlist secret

    with pytest.raises(ValidationError, match="ALLOW_EXTERNAL_OCR"):
        Settings(**kwargs)


def test_production_rejects_clova_primary_without_external_gate() -> None:
    """Verify CLOVA primary requires ALLOW_EXTERNAL_OCR in production."""
    kwargs = _valid_production_kwargs()
    kwargs["ocr_primary_provider"] = "clova"
    kwargs["clova_ocr_api_url"] = "https://example.apigw.ntruss.com/custom/v1/infer"
    kwargs["clova_ocr_secret"] = "secret"  # pragma: allowlist secret

    with pytest.raises(
        ValidationError,
        match="ALLOW_EXTERNAL_OCR=true is required when OCR_PRIMARY_PROVIDER=clova",
    ):
        Settings(**kwargs)


def test_production_rejects_clova_primary_without_api_url() -> None:
    """Verify CLOVA primary requires CLOVA_OCR_API_URL in production."""
    kwargs = _valid_production_kwargs()
    kwargs["ocr_primary_provider"] = "clova"
    kwargs["allow_external_ocr"] = True
    kwargs["clova_ocr_secret"] = "secret"  # pragma: allowlist secret

    with pytest.raises(
        ValidationError,
        match="CLOVA_OCR_API_URL is required when OCR_PRIMARY_PROVIDER=clova",
    ):
        Settings(**kwargs)


def test_production_rejects_clova_primary_without_secret() -> None:
    """Verify CLOVA primary requires CLOVA_OCR_SECRET in production."""
    kwargs = _valid_production_kwargs()
    kwargs["ocr_primary_provider"] = "clova"
    kwargs["allow_external_ocr"] = True
    kwargs["clova_ocr_api_url"] = "https://example.apigw.ntruss.com/custom/v1/infer"

    with pytest.raises(
        ValidationError,
        match="CLOVA_OCR_SECRET is required when OCR_PRIMARY_PROVIDER=clova",
    ):
        Settings(**kwargs)


@pytest.mark.parametrize(
    ("setting_name", "error_message"),
    (
        ("enable_image_learning_pipeline", "ENABLE_IMAGE_LEARNING_PIPELINE"),
        ("enable_pgvector_storage", "ENABLE_PGVECTOR_STORAGE"),
    ),
)
def test_production_rejects_learning_storage_flags_without_signoff(
    setting_name: str,
    error_message: str,
) -> None:
    """Verify production cannot enable learning storage gates before sign-off."""
    kwargs = _valid_production_kwargs()
    kwargs[setting_name] = True

    with pytest.raises(ValidationError, match=error_message):
        Settings(**kwargs)


def test_production_rejects_learning_object_storage_without_signoff() -> None:
    """Verify production cannot enable learning object storage before sign-off."""
    kwargs = _valid_production_kwargs()
    kwargs["learning_object_storage_provider"] = "s3"
    kwargs["learning_object_storage_bucket"] = "learning-images"

    with pytest.raises(ValidationError, match="LEARNING_OBJECT_STORAGE_PROVIDER"):
        Settings(**kwargs)


def test_production_rejects_media_object_storage_without_signoff() -> None:
    """Verify production cannot enable retained media storage before sign-off."""
    kwargs = _valid_production_kwargs()
    kwargs["media_object_storage_provider"] = "s3"
    kwargs["media_object_storage_bucket"] = "media-objects"

    with pytest.raises(ValidationError, match="MEDIA_OBJECT_STORAGE_PROVIDER"):
        Settings(**kwargs)


def test_production_rejects_regulated_raw_image_retention_without_signoff() -> None:
    """Verify regulated document raw images remain memory-only before sign-off."""
    kwargs = _valid_production_kwargs()
    kwargs["sensitive_document_original_image_retention_seconds"] = 60

    with pytest.raises(
        ValidationError,
        match="SENSITIVE_DOCUMENT_ORIGINAL_IMAGE_RETENTION_SECONDS",
    ):
        Settings(**kwargs)


def test_s3_learning_object_storage_requires_bucket() -> None:
    """Verify S3 learning object storage cannot start without a bucket."""
    with pytest.raises(ValidationError, match="LEARNING_OBJECT_STORAGE_BUCKET"):
        Settings(_env_file=None, learning_object_storage_provider="s3")


def test_supabase_s3_learning_object_storage_requires_project_or_endpoint() -> None:
    """Verify Supabase Storage cannot be configured without a scoped endpoint."""
    with pytest.raises(
        ValidationError,
        match="SUPABASE_PROJECT_REF or LEARNING_OBJECT_STORAGE_ENDPOINT_URL",
    ):
        Settings(
            _env_file=None,
            learning_object_storage_provider="supabase_s3",
            learning_object_storage_region="ap-northeast-2",
            supabase_storage_s3_access_key_id="access",
            supabase_storage_s3_secret_access_key="secret",  # pragma: allowlist secret
        )


def test_supabase_s3_learning_object_storage_requires_region() -> None:
    """Verify Supabase Storage S3 uses the official project region explicitly."""
    with pytest.raises(ValidationError, match="LEARNING_OBJECT_STORAGE_REGION"):
        Settings(
            _env_file=None,
            learning_object_storage_provider="supabase_s3",
            supabase_project_ref="projectref",
            supabase_storage_s3_access_key_id="access",
            supabase_storage_s3_secret_access_key="secret",  # pragma: allowlist secret
        )


def test_supabase_s3_learning_object_storage_requires_server_credentials() -> None:
    """Verify Supabase Storage S3 cannot rely on public client keys."""
    with pytest.raises(ValidationError, match="SUPABASE_STORAGE_S3_ACCESS_KEY_ID"):
        Settings(
            _env_file=None,
            learning_object_storage_provider="supabase_s3",
            supabase_project_ref="projectref",
            learning_object_storage_region="ap-northeast-2",
        )


def test_s3_media_object_storage_requires_bucket() -> None:
    """Verify S3 media object storage cannot start without a bucket."""
    with pytest.raises(ValidationError, match="MEDIA_OBJECT_STORAGE_BUCKET"):
        Settings(_env_file=None, media_object_storage_provider="s3")


def test_supabase_s3_media_object_storage_requires_project_or_endpoint() -> None:
    """Verify Supabase media Storage cannot be configured without a scoped endpoint."""
    with pytest.raises(
        ValidationError,
        match="SUPABASE_PROJECT_REF or MEDIA_OBJECT_STORAGE_ENDPOINT_URL",
    ):
        Settings(
            _env_file=None,
            media_object_storage_provider="supabase_s3",
            media_object_storage_region="ap-northeast-2",
            supabase_storage_s3_access_key_id="access",
            supabase_storage_s3_secret_access_key="secret",  # pragma: allowlist secret
        )


def test_supabase_s3_media_object_storage_requires_region() -> None:
    """Verify Supabase media Storage S3 uses the project region explicitly."""
    with pytest.raises(ValidationError, match="MEDIA_OBJECT_STORAGE_REGION"):
        Settings(
            _env_file=None,
            media_object_storage_provider="supabase_s3",
            supabase_project_ref="projectref",
            supabase_storage_s3_access_key_id="access",
            supabase_storage_s3_secret_access_key="secret",  # pragma: allowlist secret
        )


def test_supabase_s3_media_object_storage_requires_server_credentials() -> None:
    """Verify Supabase media Storage S3 cannot rely on public client keys."""
    with pytest.raises(ValidationError, match="SUPABASE_STORAGE_S3_ACCESS_KEY_ID"):
        Settings(
            _env_file=None,
            media_object_storage_provider="supabase_s3",
            supabase_project_ref="projectref",
            media_object_storage_region="ap-northeast-2",
        )


def test_staging_requires_manual_review_when_image_learning_enabled() -> None:
    """Verify deployed image learning cannot bypass operator review."""
    with pytest.raises(ValidationError, match="REQUIRE_LEARNING_MANUAL_REVIEW"):
        Settings(
            _env_file=None,
            environment="staging",
            auth_mode="jwt",
            allowed_hosts=["staging.example.com"],
            enable_image_learning_pipeline=True,
            enable_pgvector_storage=True,
            image_retention_days=30,
            require_learning_manual_review=False,
        )


def test_learning_requires_auto_filter_or_manual_review() -> None:
    """Verify learning cannot bypass both automatic filtering and review."""
    with pytest.raises(ValidationError, match="ENABLE_LEARNING_AUTO_FILTER"):
        Settings(
            _env_file=None,
            enable_image_learning_pipeline=True,
            enable_pgvector_storage=True,
            image_retention_days=30,
            enable_learning_auto_filter=False,
            require_learning_manual_review=False,
        )


@pytest.mark.parametrize(
    ("setting_name", "error_message"),
    (
        ("feature_prescription_ocr_intake", "FEATURE_PRESCRIPTION_OCR_INTAKE"),
        ("feature_lab_result_ocr_intake", "FEATURE_LAB_RESULT_OCR_INTAKE"),
        ("feature_medication_safety_alert", "FEATURE_MEDICATION_SAFETY_ALERT"),
    ),
)
def test_production_rejects_regulated_feature_flags_without_signoff(
    setting_name: str,
    error_message: str,
) -> None:
    """Verify production cannot enable non-P1 regulated flags before sign-off."""
    kwargs = _valid_production_kwargs()
    kwargs[setting_name] = True

    with pytest.raises(ValidationError, match=error_message):
        Settings(**kwargs)


def test_implementation_readiness_regulated_flags_default_off() -> None:
    """Verify the readiness manifest matches P1 default-off policy."""
    manifest = _load_json_object(READINESS_SETTINGS_PATH)
    environment_variables = _object_field(manifest, "environment_variables")
    feature_flags = _object_field(environment_variables, "feature_flags")

    for flag_name in (
        "FEATURE_PRESCRIPTION_OCR_INTAKE",
        "FEATURE_LAB_RESULT_OCR_INTAKE",
        "FEATURE_HOSPITAL_MOCK_FHIR",
        "FEATURE_MEDICATION_SAFETY_ALERT",
    ):
        flag_config = _object_field(feature_flags, flag_name)
        assert flag_config["default"] is False


def test_implementation_readiness_google_vision_defaults_fail_closed() -> None:
    """Verify the readiness manifest keeps external OCR off by default."""
    manifest = _load_json_object(READINESS_SETTINGS_PATH)
    environment_variables = _object_field(manifest, "environment_variables")
    ocr_settings = _object_field(environment_variables, "ocr")

    primary_provider = _object_field(ocr_settings, "OCR_PRIMARY_PROVIDER")
    allow_external_ocr = _object_field(ocr_settings, "ALLOW_EXTERNAL_OCR")
    auth_mode = _object_field(ocr_settings, "GOOGLE_VISION_AUTH_MODE")
    credentials = _object_field(ocr_settings, "GOOGLE_APPLICATION_CREDENTIALS")
    enable_local_ocr = _object_field(ocr_settings, "ENABLE_LOCAL_OCR")

    assert primary_provider["default"] == "paddleocr"
    assert "paddleocr" in cast(list[str], primary_provider["allowed_values"])
    assert allow_external_ocr["default"] is False
    assert auth_mode["default"] == "api_key"
    assert auth_mode["production_required_value"] == "adc"
    assert credentials["default"] is None
    assert enable_local_ocr["default"] is True


def test_production_requires_external_ocr_gate_for_google_vision() -> None:
    """Verify production cannot enable Google Vision while the external gate is off."""
    kwargs = _valid_production_kwargs()
    kwargs["ocr_primary_provider"] = "google_vision"
    kwargs["google_vision_auth_mode"] = "adc"
    kwargs["google_cloud_project"] = "lemon-prod"

    with pytest.raises(ValidationError, match="ALLOW_EXTERNAL_OCR"):
        Settings(**kwargs)


def test_production_requires_adc_for_google_vision() -> None:
    """Verify production Google Vision cannot use API key auth.

    The PR-K guard fires from the api_key path: even with ALLOW_GOOGLE_API_KEY_AUTH=true,
    production rejects the combination outright.
    """
    kwargs = _valid_production_kwargs()
    kwargs["ocr_primary_provider"] = "google_vision"
    kwargs["allow_external_ocr"] = True
    kwargs["google_vision_auth_mode"] = "api_key"
    kwargs["allow_google_api_key_auth"] = True
    kwargs["google_cloud_api_key"] = "local-only-key"  # pragma: allowlist secret
    kwargs["google_cloud_project"] = "lemon-prod"

    with pytest.raises(ValidationError, match="ALLOW_GOOGLE_API_KEY_AUTH=true is forbidden"):
        Settings(**kwargs)


def test_api_key_auth_requires_allow_flag() -> None:
    """Verify GOOGLE_VISION_AUTH_MODE=api_key needs ALLOW_GOOGLE_API_KEY_AUTH=true."""
    with pytest.raises(ValidationError, match="ALLOW_GOOGLE_API_KEY_AUTH"):
        Settings(
            _env_file=None,
            environment="development",
            google_vision_auth_mode="api_key",
        )


def test_api_key_auth_passes_with_allow_flag_in_development() -> None:
    """Verify api_key + allow flag is accepted in development."""
    settings = Settings(
        _env_file=None,
        environment="development",
        google_vision_auth_mode="api_key",
        allow_google_api_key_auth=True,
    )
    assert settings.google_vision_auth_mode == "api_key"
    assert settings.allow_google_api_key_auth is True


def test_staging_requires_explicit_allowed_hosts() -> None:
    """Verify staging cannot boot with an empty ALLOWED_HOSTS list."""
    with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
        Settings(_env_file=None, environment="staging", auth_mode="jwt", allowed_hosts=[])


def test_staging_rejects_wildcard_allowed_hosts() -> None:
    """Verify wildcards in ALLOWED_HOSTS are rejected in staging."""
    with pytest.raises(ValidationError, match="wildcard"):
        Settings(
            _env_file=None,
            environment="staging",
            auth_mode="jwt",
            allowed_hosts=["*"],
        )


def test_production_requires_project_for_google_vision_adc() -> None:
    """Verify production Google Vision ADC mode pins the quota project."""
    kwargs = _valid_production_kwargs()
    kwargs["ocr_primary_provider"] = "google_vision"
    kwargs["allow_external_ocr"] = True
    kwargs["google_vision_auth_mode"] = "adc"

    with pytest.raises(ValidationError, match="GOOGLE_CLOUD_PROJECT"):
        Settings(**kwargs)


def test_production_rejects_google_application_credentials_for_google_vision() -> None:
    """Verify production Google Vision does not use checked-in JSON credential paths."""
    kwargs = _valid_production_kwargs()
    kwargs["ocr_primary_provider"] = "google_vision"
    kwargs["allow_external_ocr"] = True
    kwargs["google_vision_auth_mode"] = "adc"
    kwargs["google_cloud_project"] = "lemon-prod"
    kwargs["google_application_credentials"] = "/run/secrets/google-service-account.json"

    with pytest.raises(ValidationError, match="GOOGLE_APPLICATION_CREDENTIALS"):
        Settings(**kwargs)


def test_valid_production_google_vision_adc_settings_load() -> None:
    """Verify production accepts Google Vision only through attached-account ADC mode."""
    kwargs = _valid_production_kwargs()
    kwargs["ocr_primary_provider"] = "google_vision"
    kwargs["allow_external_ocr"] = True
    kwargs["google_vision_auth_mode"] = "adc"
    kwargs["google_cloud_project"] = "lemon-prod"
    kwargs["enable_local_ocr"] = False

    settings = Settings(**kwargs)

    assert settings.ocr_primary_provider == "google_vision"
    assert settings.allow_external_ocr is True
    assert settings.google_vision_auth_mode == "adc"
    assert settings.google_cloud_project == "lemon-prod"
    assert settings.enable_local_ocr is False


def test_production_rejects_non_https_jwks_url() -> None:
    """Verify production JWKS URL must use HTTPS."""
    kwargs = _valid_production_kwargs()
    kwargs["jwt_jwks_url"] = "http://auth.example.com/.well-known/jwks.json"

    with pytest.raises(ValidationError, match="https"):
        Settings(**kwargs)


def test_production_requires_core_jwt_claims() -> None:
    """Verify production JWT validation cannot omit core access-token claims."""
    kwargs = _valid_production_kwargs()
    kwargs["jwt_required_claims"] = ["exp", "iss", "sub", "aud"]

    with pytest.raises(ValidationError, match="JWT_REQUIRED_CLAIMS"):
        Settings(**kwargs)


def test_production_requires_token_confusion_guard() -> None:
    """Verify production must configure a token type or provider token-use guard."""
    kwargs = _valid_production_kwargs()
    kwargs["jwt_expected_token_type"] = None
    kwargs["jwt_token_use_claim"] = None

    with pytest.raises(ValidationError, match="JWT_EXPECTED_TOKEN_TYPE"):
        Settings(**kwargs)


def test_valid_production_settings_load() -> None:
    """Verify explicit production security settings are accepted."""
    settings = Settings(**_valid_production_kwargs())

    assert settings.environment == "production"
    assert settings.auth_mode == "jwt"
    assert settings.jwt_audience == "lemon-api"
