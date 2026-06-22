"""애플리케이션 설정."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://lemon:lemon@localhost:5432/lemon"  # pragma: allowlist secret
)
POSTGRESQL_ASYNCPG_DRIVER = "postgresql+asyncpg"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_ALLOWED_HOSTS = ["localhost", "127.0.0.1", "10.0.2.2", "testserver"]
DEFAULT_JWT_ALGORITHMS = ["RS256"]
DEFAULT_JWT_REQUIRED_CLAIMS = ["exp", "iss", "sub", "aud", "iat"]
DEFAULT_JWT_SCOPE_CLAIMS = ["scope", "scp"]
DEFAULT_VISION_ROI_ALLOWED_CLASSES = [
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
# Stock Ultralytics net shipped as the default ``vision_classifier_model``. It is a
# generic COCO model that fails ``_validate_model_class_contract`` at load, so a
# trained supplement section detector must replace it before YOLO ROI runs.
DEFAULT_VISION_CLASSIFIER_MODEL = "yolo26n.pt"
DEFAULT_LLM_WIKI_PATH = Path("/Volumes/Corsair EX400U Media/LLM-WIKI")
# Deliberately insecure development sentinel; production validation rejects this exact value.
DEFAULT_PRIVACY_HASH_SECRET = (
    "development-insecure-privacy-hash-secret"  # noqa: S105, RUF100  # pragma: allowlist secret
)
# Minimum production length for the privacy HMAC secret (~192 bits of entropy at
# base64). Enforced only in production; dev keeps the short sentinel above.
DEFAULT_PRIVACY_HASH_SECRET_MIN_LENGTH = 32
BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE_CANDIDATES = (PROJECT_ROOT / ".env", BACKEND_ROOT / ".env")

NUTRITION_REFERENCE_MARKER = Path("data") / "nutrition_reference"


def resolve_nutrition_reference_root(explicit: str | None = None) -> Path:
    """Resolve the ``data/nutrition_reference`` root deterministically.

    The repository layout (``Lemon-Aid/data/nutrition_reference``) and the Docker
    image layout (``/app/data/nutrition_reference``, mounted read-only) place the
    reference data at different depths relative to the source tree, so a fixed
    ``parents[N]`` offset resolves correctly in one layout but not the other.

    This walks upward from the source file (and, as a secondary anchor, the
    process working directory) and returns the first ancestor that actually
    contains ``data/nutrition_reference``. An explicit override (settings /
    ``NUTRITION_REFERENCE_PATH``) always wins. The returned path is not required
    to exist when an override is given, so callers can fail fast with a clear
    message at startup.

    Args:
        explicit: Optional override path (absolute, or relative to CWD).

    Returns:
        Absolute path to the reference-data root (existing when discovered).
    """
    if explicit:
        candidate = Path(explicit)
        return candidate if candidate.is_absolute() else (Path.cwd() / candidate).resolve()
    anchors = (Path(__file__).resolve().parent, Path.cwd().resolve())
    for anchor in anchors:
        for parent in (anchor, *anchor.parents):
            candidate = parent / NUTRITION_REFERENCE_MARKER
            if candidate.is_dir():
                return candidate.resolve()
    # No marker found on disk: return the repository-relative location so the
    # error surfaced by the caller names the canonical expected path.
    return (PROJECT_ROOT / NUTRITION_REFERENCE_MARKER).resolve()


JWT_CORE_REQUIRED_CLAIMS = {"aud", "exp", "iat", "iss", "sub"}
WILDCARD_VALUES = {"*"}
ASYMMETRIC_JWT_ALGORITHMS = {
    "EdDSA",
    "ES256",
    "ES384",
    "ES512",
    "PS256",
    "PS384",
    "PS512",
    "RS256",
    "RS384",
    "RS512",
}


def _default_allowed_hosts() -> list[str]:
    """Return default hosts for local development and TestClient.

    Returns:
        Hostnames allowed by default outside production.
    """
    return DEFAULT_ALLOWED_HOSTS.copy()


def _default_jwt_algorithms() -> list[str]:
    """Return default public-key JWT algorithms.

    Returns:
        JWT algorithms accepted by default for OAuth/OIDC access tokens.
    """
    return DEFAULT_JWT_ALGORITHMS.copy()


def _default_jwt_required_claims() -> list[str]:
    """Return default JWT claims required for OAuth/OIDC access tokens.

    Returns:
        Required JWT claim names.
    """
    return DEFAULT_JWT_REQUIRED_CLAIMS.copy()


def _default_jwt_scope_claims() -> list[str]:
    """Return default JWT claims used to extract OAuth scopes.

    Returns:
        Scope claim names checked in order.
    """
    return DEFAULT_JWT_SCOPE_CLAIMS.copy()


def _default_vision_roi_allowed_classes() -> list[str]:
    """Return default YOLO ROI labels allowed for supplement image preprocessing.

    Returns:
        Allowed object-detection labels for supplement ROI assistance.
    """
    return DEFAULT_VISION_ROI_ALLOWED_CLASSES.copy()


def _contains_wildcard(values: list[str]) -> bool:
    """Check whether a security setting contains a wildcard value.

    Args:
        values: Setting values to inspect.

    Returns:
        True if a wildcard token is present.
    """
    return any(value.strip() in WILDCARD_VALUES for value in values)


def _failed_checks(checks: tuple[tuple[bool, str], ...]) -> list[str]:
    """Return messages for failed production security checks.

    Args:
        checks: Pairs of failure condition and error message.

    Returns:
        Error messages whose condition evaluated to True.
    """
    return [message for failed, message in checks if failed]


def _missing_required_field_errors(fields: tuple[tuple[str, str | None], ...]) -> list[str]:
    """Return production errors for missing required fields.

    Args:
        fields: Environment variable names and values to inspect.

    Returns:
        Error messages for empty values.
    """
    return [
        f"{name} is required when ENVIRONMENT=production." for name, value in fields if not value
    ]


def _is_local_http_url(value: str) -> bool:
    """Return whether a URL points at a loopback HTTP endpoint.

    Args:
        value: URL string to inspect.

    Returns:
        True if the URL scheme is http(s) and the host is loopback.
    """
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }


def _is_non_https_url(value: str | None) -> bool:
    """Check whether a configured URL is present but not HTTPS.

    Args:
        value: URL string or None.

    Returns:
        True if the URL is set and does not start with https://.
    """
    return value is not None and not value.startswith("https://")


def _secret_value(value: SecretStr | None) -> str | None:
    """Return the raw secret value for production validation.

    Args:
        value: Secret setting value.

    Returns:
        Raw secret string or None.
    """
    if value is None:
        return None
    return value.get_secret_value()


def _database_drivername(database_url: str) -> str:
    """Return the SQLAlchemy driver name for a configured database URL.

    Args:
        database_url: SQLAlchemy database URL.

    Returns:
        SQLAlchemy driver name such as ``postgresql+asyncpg``.

    Raises:
        ValueError: If the URL cannot be parsed by SQLAlchemy.
    """
    try:
        return make_url(database_url).drivername
    except ArgumentError as exc:
        raise ValueError("DATABASE_URL must be a valid SQLAlchemy database URL.") from exc


class Settings(BaseSettings):
    """환경 변수 기반 애플리케이션 설정.

    Attributes:
        environment: 실행 환경.
        log_level: 애플리케이션 로그 레벨.
        database_url: PostgreSQL asyncpg SQLAlchemy 연결 URL.
        redis_url: Redis 연결 URL.
        supabase_project_ref: Supabase hosted project ref for CLI/MCP scoping.
        supabase_url: Supabase project API URL.
        supabase_publishable_key: Client-safe Supabase publishable API key.
        supabase_secret_key: Backend-only Supabase secret API key.
        supabase_access_token: Developer-only Supabase Management/MCP token.
        supabase_db_url: Direct Supabase Postgres URL for migration/preflight use.
        supabase_mcp_read_only: Whether Supabase MCP should run read-only by default.
        supabase_mcp_features: Comma-separated Supabase MCP feature groups.
        supabase_storage_private_bucket: Private bucket id for opt-in learning images.
        supabase_storage_s3_access_key_id: Server-only Supabase Storage S3 access key id.
        supabase_storage_s3_secret_access_key: Server-only Supabase Storage S3 secret key.
        media_object_storage_provider: Backend-only private media object storage provider.
        media_object_storage_bucket: Private bucket for retained media object deletion.
        media_object_storage_endpoint_url: S3-compatible endpoint for retained media objects.
        media_object_storage_region: Region for retained media object deletion.
        media_object_storage_local_path: Development-only local retained media path.
        allowed_origins: CORS 허용 origin 목록.
        allowed_hosts: TrustedHost 허용 host 목록.
        auth_mode: 인증 모드. 실제 사용자 앱은 production에서 jwt를 사용한다.
        jwt_issuer: OAuth/OIDC issuer URL.
        jwt_audience: JWT audience.
        jwt_jwks_url: OAuth/OIDC JWKS URL.
        jwt_algorithms: JWT signature algorithms allowed for JWKS verification.
        jwt_leeway_seconds: Clock-skew leeway for exp, nbf, and iat checks.
        jwt_required_claims: JWT claims that must be present.
        jwt_scope_claims: JWT claim names used for OAuth scopes.
        jwt_expected_token_type: Optional JOSE typ value expected for access tokens.
        jwt_token_use_claim: Optional provider-specific claim used to distinguish access tokens.
        jwt_token_use_allowed_values: Allowed provider-specific access-token values.
        jwt_jwks_cache_ttl_seconds: JWKS cache lifespan.
        jwt_jwks_timeout_seconds: JWKS retrieval timeout.
        oidc_discovery_url: Optional OIDC discovery document URL for operational preflight.
        privacy_hash_secret: HMAC secret used for privacy-preserving audit identifiers.
        llm_provider: 기본 LLM provider. Ollama 또는 로컬/자가호스팅 SGLang을 허용한다.
        ollama_base_url: Ollama Local API 기본 주소.
        ollama_model: 텍스트 구조화 출력 기본 모델.
        ollama_vision_model: 이미지 입력 실험용 모델.
        ollama_timeout_sec: Ollama 요청 타임아웃.
        ollama_temperature: 구조화 출력 안정성을 위한 temperature.
        allow_external_llm: 외부 LLM 사용 허용 여부.
        ocr_primary_provider: Primary supplement-label OCR provider selector. Defaults to
            ``paddleocr`` (local). ``google_vision`` is an opt-in external option.
        allow_external_ocr: Whether external OCR providers can receive image bytes.
        google_vision_auth_mode: Google Vision authentication mode.
        google_cloud_api_key: Google Cloud Vision REST API key.
        google_cloud_project: Google Cloud project used for quota and regional OCR.
        google_vision_location: Google Vision OCR processing location.
        google_vision_feature: Google Vision OCR feature type.
        google_vision_language_hints: Optional BCP-47 language hints passed to OCR.
        google_vision_timeout_seconds: Google Vision request timeout.
        google_vision_max_retries: Google Vision retry count for transient failures.
        google_application_credentials: Deprecated Google Cloud 인증 파일 경로.
        clova_ocr_api_url: CLOVA OCR API Gateway invoke URL.
        clova_ocr_secret: CLOVA OCR client secret.
        mfds_api_key: 식약처/공공데이터 API 키.
        supplement_image_max_bytes: Maximum uploaded supplement label image size.
        supplement_image_max_pixels: Maximum decoded supplement label image pixels.
        supplement_preview_ttl_minutes: Minutes before an intake-only preview expires.
        supplement_ocr_text_max_chars: Maximum OCR text characters sent to the parser.
        supplement_parser_algorithm_version: Version label for structured supplement parsing.
        supplement_parser_max_ingredients: Maximum ingredient candidates accepted from the parser.
        regulated_document_preview_ttl_minutes: Minutes before a regulated OCR preview expires.
        sensitive_document_original_image_retention_seconds: Seconds raw regulated document images
            may be retained before deletion. The default 0 means request-memory only.
        ocr_roi_preprocessing_policy: Whether detected ROI metadata should crop primary OCR input.
        ocr_roi_crop_padding_ratio: Fractional padding applied around YOLO OCR crops.
        ocr_roi_crop_min_padding_px: Minimum pixel padding applied around YOLO OCR crops.
        ocr_roi_crop_max_padding_px: Maximum pixel padding applied around YOLO OCR crops.
        multimodal_ocr_assist_policy: Policy controlling when local vision LLM fallback may run.
        enable_multimodal_verification: Whether local vision verification can sample OCR outputs.
        multimodal_verification_sample_rate: Fraction of accepted OCR outputs to verify.
        multimodal_verification_threshold: Minimum normalized text similarity for verification.
        enable_local_ocr: Whether local OCR fallback adapters may run.
        local_ocr_provider: Local OCR provider selector.
        local_ocr_language: Language setting passed to local OCR providers.
        local_ocr_device: Optional local OCR runtime device selector.
        local_ocr_confidence_threshold: Legacy calibration value for local OCR diagnostics.
            Low-confidence OCR text is still returned for parser and user review.
        local_ocr_model_profile: Local PaddleOCR model profile used for diagnostic comparisons.
        local_ocr_text_recognition_model_dir: Optional custom PaddleOCR recognizer inference
            directory for a fine-tuned local model.
        local_ocr_preprocess_mode: Optional local OCR-only image preprocessing mode.
        enable_clova_ocr: Whether NAVER Cloud CLOVA OCR fallback may run.
        vision_roi_min_confidence: Minimum detection confidence accepted for a YOLO ROI.
        vision_roi_allowed_classes: Allowed OCR ROI object or label-section classes from YOLO.
        feature_hall_lite_weight_prediction: Whether Hall-lite weight prediction can run.
        weight_prediction_engine: Internal weight prediction engine selector.
        kdris_data_version: KDRIs dataset version used by runtime lookup.
        kdris_data_path: Optional explicit KDRIs CSV path.
        kdris_manifest_path: Optional explicit KDRIs source manifest path.
        allow_sample_kdris: Whether the 2020 sample KDRIs fixture may be used.
        feature_prescription_ocr_intake: 처방전 OCR intake 기능 플래그.
        feature_lab_result_ocr_intake: 검사표 OCR intake 기능 플래그.
        persist_daily_health_score: 대시보드 일일 건강 점수의 1일 1회 영속화 여부.
        feature_dosage_change_recommendation: 복용량 변경 추천 기능 플래그.
        feature_medication_safety_alert: 복약 안전 알림 기능 플래그.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_CANDIDATES,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = Field(default="INFO")

    database_url: str = Field(default=DEFAULT_DATABASE_URL)
    audit_database_url: str | None = Field(
        default=None,
        description=(
            "Optional privileged PostgreSQL asyncpg URL for out-of-band audit "
            "writes. Under FORCE RLS Stage-2 the request role (lemon_app) holds "
            "only SELECT on audit_logs, so set this to a role that can INSERT "
            "audit rows. None reuses DATABASE_URL (correct while the request role "
            "is still privileged)."
        ),
    )
    learning_database_url: str | None = Field(
        default=None,
        description=(
            "Optional privileged PostgreSQL asyncpg URL for post-commit learning "
            "writes (learning_image_objects, annotation_tasks). Those tables are "
            "under FORCE RLS, so the fresh GUC-less post-commit session needs a "
            "superuser or BYPASSRLS role; lemon_app would fail closed. None reuses "
            "DATABASE_URL (correct while the request role is still privileged)."
        ),
    )
    db_pool_size: int = Field(
        default=5,
        ge=1,
        le=100,
        description=(
            "SQLAlchemy connection pool size, applied per engine per worker "
            "process to the main, audit, and learning engines independently. Peak "
            "Postgres connections = workers x active_engines x (db_pool_size + "
            "db_max_overflow); keep that under the server's max_connections "
            "(audit/learning engines only materialize when their URL is set)."
        ),
    )
    db_max_overflow: int = Field(
        default=10,
        ge=0,
        le=100,
        description=(
            "SQLAlchemy overflow connections allowed beyond db_pool_size, per "
            "engine per worker. See db_pool_size for the total-connection budget."
        ),
    )
    redis_url: str = Field(default=DEFAULT_REDIS_URL)
    supabase_project_ref: str | None = Field(default=None)
    supabase_url: str | None = Field(default=None)
    supabase_publishable_key: SecretStr | None = Field(default=None)
    supabase_secret_key: SecretStr | None = Field(default=None)
    supabase_access_token: SecretStr | None = Field(default=None)
    supabase_db_url: SecretStr | None = Field(default=None)
    supabase_mcp_read_only: bool = Field(
        default=True,
        description="Keep Supabase MCP read-only unless a reviewed migration task needs writes.",
    )
    supabase_mcp_features: str = Field(default="database,docs,debugging,storage")
    supabase_storage_private_bucket: str = Field(default="learning-images")
    supabase_storage_s3_access_key_id: SecretStr | None = Field(default=None)
    supabase_storage_s3_secret_access_key: SecretStr | None = Field(default=None)
    media_object_storage_provider: Literal["disabled", "local", "s3", "supabase_s3"] = Field(
        default="disabled",
        description=(
            "Backend-only retained media object storage provider. Defaults disabled; "
            "Supabase private Storage uses supabase_s3."
        ),
    )
    media_object_storage_bucket: str | None = Field(default=None)
    media_object_storage_endpoint_url: str | None = Field(default=None)
    media_object_storage_region: str | None = Field(default=None)
    media_object_storage_local_path: Path = Field(
        default=PROJECT_ROOT / ".local" / "media-objects",
        description="개발/테스트 전용 retained media object storage 경로.",
    )
    allowed_origins: list[str] = Field(default_factory=list)
    allowed_hosts: list[str] = Field(default_factory=_default_allowed_hosts)

    auth_mode: Literal["disabled", "jwt"] = "disabled"
    jwt_issuer: str | None = Field(default=None)
    jwt_audience: str | None = Field(default=None)
    jwt_jwks_url: str | None = Field(default=None)
    jwt_algorithms: list[str] = Field(default_factory=_default_jwt_algorithms)
    jwt_leeway_seconds: int = Field(default=60, ge=0, le=300)
    jwt_required_claims: list[str] = Field(default_factory=_default_jwt_required_claims)
    jwt_scope_claims: list[str] = Field(default_factory=_default_jwt_scope_claims)
    jwt_expected_token_type: str | None = Field(default=None)
    jwt_token_use_claim: str | None = Field(default=None)
    jwt_token_use_allowed_values: list[str] = Field(default_factory=list)
    jwt_jwks_cache_ttl_seconds: int = Field(default=300, ge=1, le=86400)
    jwt_jwks_timeout_seconds: int = Field(default=5, ge=1, le=30)
    oidc_discovery_url: str | None = Field(default=None)
    privacy_hash_secret: SecretStr = Field(default=SecretStr(DEFAULT_PRIVACY_HASH_SECRET))
    privacy_hash_secret_min_length: int = Field(
        default=DEFAULT_PRIVACY_HASH_SECRET_MIN_LENGTH, ge=16, le=512
    )
    privacy_hash_secret_audit_pepper: SecretStr | None = Field(default=None)

    llm_provider: Literal["ollama", "sglang"] = "ollama"
    ollama_base_url: str = Field(default="http://127.0.0.1:11434")
    ollama_model: str = Field(default="gemma4:e4b")
    ollama_vision_model: str | None = Field(default="gemma4:e4b")
    ollama_timeout_sec: int = Field(default=60, ge=1)
    ollama_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    ollama_vision_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    # Seconds to keep the gemma model resident between requests so an idle unload
    # does not force a ~10s cold reload on the next analyze. -1 = keep loaded
    # until evicted by another model (no idle unload).
    ollama_keep_alive_sec: int = Field(default=-1)
    sglang_base_url: str = Field(default="http://127.0.0.1:30000/v1")
    sglang_model: str = Field(default="Qwen/Qwen2.5-0.5B-Instruct")
    sglang_api_key: SecretStr | None = Field(default=None)
    kdca_healthinfo_url_template: str | None = Field(default=None)
    kdca_healthinfo_topic_ids_file: Path | None = Field(default=None)
    kdca_healthinfo_topic_ids: dict[str, str] = Field(default_factory=dict)
    kdca_healthinfo_api_key: SecretStr | None = Field(default=None)
    allow_external_llm: bool = Field(default=False)
    llm_wiki_retrieval_enabled: bool = Field(default=True)
    llm_wiki_path: Path = Field(default=DEFAULT_LLM_WIKI_PATH)
    llm_wiki_max_sources: int = Field(default=4, ge=0, le=8)
    llm_wiki_excerpt_chars: int = Field(default=700, ge=120, le=1500)
    llm_wiki_retrieval_mode: Literal["lexical", "vector", "hybrid"] = Field(
        default="hybrid",
        description=(
            "WIKI 검색 모드. lexical=기존 어휘 스캔만. vector/hybrid 는 "
            "enable_wiki_vector_rag=true + pgvector 임베딩 적재가 있어야 동작하며, "
            "조건 미충족 시 자동으로 lexical 로 fallback 한다."
        ),
    )
    enable_wiki_vector_rag: bool = Field(
        default=False,
        description=(
            "pgvector 기반 WIKI 시맨틱 RAG 활성화. 이미지-학습 게이트"
            "(ENABLE_PGVECTOR_STORAGE)와 분리된 레퍼런스-지식 검색이다. "
            "false 면 vector/hybrid 모드여도 lexical 만 사용한다."
        ),
    )
    wiki_embedding_provider: Literal["ollama"] = Field(
        default="ollama",
        description="WIKI 임베딩 제공자. ollama_base_url 의 embeddings API 를 사용한다.",
    )
    wiki_embedding_model: str = Field(
        default="bge-m3",
        description="WIKI 임베딩 모델명(Ollama). 변경 시 재인제스천 필요.",
    )
    wiki_embedding_dimensions: int = Field(
        default=1024,
        ge=1,
        le=16000,
        description="WIKI 임베딩 차원. wiki_chunk_embeddings.embedding 컬럼과 일치해야 한다.",
    )

    ocr_primary_provider: Literal["none", "google_vision", "paddleocr", "clova"] = Field(
        default="paddleocr"
    )
    allow_external_ocr: bool = Field(default=False)
    google_vision_auth_mode: Literal["api_key", "adc"] = Field(default="adc")
    allow_google_api_key_auth: bool = Field(
        default=False,
        description=(
            "Permit GOOGLE_VISION_AUTH_MODE=api_key. Non-production only "
            "(local smoke/dev). Production forbids API-key auth entirely."
        ),
    )
    google_cloud_api_key: SecretStr | None = Field(default=None)
    google_cloud_project: str | None = Field(default=None)
    google_vision_location: Literal["global", "us", "eu"] = Field(default="global")
    google_vision_feature: Literal["document_text_detection"] = Field(
        default="document_text_detection"
    )
    google_vision_language_hints: list[str] = Field(default_factory=list, max_length=8)
    google_vision_timeout_seconds: int = Field(default=15, ge=1, le=60)
    google_vision_max_retries: int = Field(default=2, ge=0, le=5)
    google_application_credentials: str | None = Field(default=None)
    clova_ocr_api_url: str | None = Field(default=None)
    clova_ocr_secret: SecretStr | None = Field(default=None)
    mfds_api_key: SecretStr | None = Field(default=None)
    data_go_kr_service_key: SecretStr | None = Field(default=None)
    mfds_data_api_key: SecretStr | None = Field(default=None)
    ncbi_api_key: SecretStr | None = Field(default=None)
    ncbi_tool_name: str = Field(default="lemon-aid")
    ncbi_email: str | None = Field(default=None)
    semantic_scholar_api_key: SecretStr | None = Field(default=None)
    openfda_api_key: SecretStr | None = Field(default=None)
    crossref_mailto: str | None = Field(default=None)
    google_cse_api_key: SecretStr | None = Field(default=None)
    google_cse_id: str | None = Field(default=None)

    supplement_image_max_bytes: int = Field(default=5 * 1024 * 1024, ge=1024, le=10 * 1024 * 1024)
    supplement_image_max_pixels: int = Field(default=12_000_000, ge=1, le=25_000_000)

    # Abuse controls for the expensive OCR + LLM inference endpoints. The limiter
    # is in-process (no external dependency) and path-scoped; it sheds floods per
    # caller, and the concurrency cap bounds how many inferences run in parallel.
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_analyze_per_minute: int = Field(default=12, ge=1, le=600)
    rate_limit_analyze_burst: int = Field(default=6, ge=1, le=600)
    # Lowered 4 -> 2: the single resident local Ollama model (qwen3.5:9b on a 24GB
    # unified-memory host) degrades to empty/truncated structured output when several
    # parses run at once. This caps admitted concurrent inference requests so excess
    # callers get a fast retryable 503 instead of blocking behind the serialized parse
    # (ollama_parse_max_concurrency) past the 120s mobile upload timeout.
    inference_max_concurrency: int = Field(default=2, ge=1, le=64)
    inference_acquire_timeout_sec: float = Field(default=20.0, ge=0.1, le=120.0)
    # Serialize the local Ollama structured-parse call so concurrent supplement scans
    # never split the single resident model's batch/KV-cache, which yields empty parses
    # (0 ingredients). 1 = strict serialization; raise only if the host runs
    # OLLAMA_NUM_PARALLEL>1. NOTE: in-process only — it cannot serialize the separate
    # ai_agent_chat coaching process that shares the same Ollama host; that
    # cross-process contention is mitigated only by the bounded retry below.
    ollama_parse_max_concurrency: int = Field(default=1, ge=1, le=8)
    # Bounded retry for the parse when it errors or returns 0 ingredients despite
    # non-trivial OCR text (transient degradation, e.g. cross-process Ollama load).
    # 2 = one retry. Each attempt is capped to the wall-clock left in
    # ollama_parse_total_budget_sec, so the whole parse (queue wait + attempts +
    # backoff) stays under the 120s mobile upload timeout once upstream OCR is counted.
    ollama_parse_max_attempts: int = Field(default=2, ge=1, le=3)
    ollama_parse_total_budget_sec: float = Field(default=95.0, ge=10.0, le=115.0)
    supplement_preview_ttl_minutes: int = Field(default=30, ge=1, le=1440)
    supplement_ocr_text_max_chars: int = Field(default=12_000, ge=100, le=50_000)
    # Operator opt-in: when True, the normalized full OCR text is retained at a
    # top-level `raw_ocr_text` key in the owner-scoped supplement analysis snapshot so
    # the "OCR 텍스트 전체" view can show the source text. Default False keeps the
    # EXTERNAL_OCR_PROCESSING consent promise ("raw OCR text are not stored") accurate;
    # enabling in production requires updating that consent text + bumping its version.
    store_raw_ocr_text: bool = Field(default=False)
    supplement_parser_algorithm_version: str = Field(
        default="supplement-ollama-parser-v1.0.0",
        min_length=1,
        max_length=64,
    )
    supplement_parser_max_ingredients: int = Field(default=80, ge=1, le=80)
    # One-shot multi-image OCR fusion: when a batch is one product
    # (merge_strategy=single_product), OCR every image in-request, fuse the text,
    # and run the structured parser ONCE so the model sees the whole label.
    # Dark-launched (default False): single_product requests fall through to the
    # per-image distinct path until real multi-image label verification passes.
    # Flip to True (env override) to exercise the fusion path.
    supplement_one_shot_fusion_enabled: bool = Field(default=False)
    # Async supplement analyze: when enabled, POST /supplements/analyze(-multi) creates
    # the run row(s) in 'processing' status, returns 202 immediately, and runs the heavy
    # OCR/parse/vision pipeline in an in-process background task that flips the run to
    # 'requires_confirmation'/'failed'. The mobile client then polls the analysis by id.
    # Dark-launched (default False): the endpoints stay fully synchronous until flipped.
    supplement_analyze_async_enabled: bool = Field(default=False)
    # A run left in 'processing' longer than this is considered stale (the worker died,
    # e.g. on a deploy/restart) and is reported as failed by the poll endpoint so the
    # client is never wedged. Comfortably above the measured worst-case pipeline (~143s).
    supplement_analyze_worker_deadline_sec: int = Field(default=300, ge=30, le=900)
    regulated_document_preview_ttl_minutes: int = Field(default=30, ge=1, le=1440)
    sensitive_document_original_image_retention_seconds: int = Field(default=0, ge=0, le=3600)

    feature_hall_lite_weight_prediction: bool = Field(
        default=False,
        description="Hall-lite 동적 체중 예측 활성화. 기본값은 기존 7-step fallback.",
    )
    weight_prediction_engine: Literal["static_7step", "hall_lite", "auto"] = Field(
        default="static_7step",
        description="체중 예측 엔진 선택. 기본값은 기존 static 7-step.",
    )

    kdris_data_version: Literal["2020-sample", "2025"] = "2020-sample"
    kdris_data_path: str | None = Field(default=None)
    kdris_manifest_path: str | None = Field(default=None)
    allow_sample_kdris: bool = Field(default=True)

    feature_prescription_ocr_intake: bool = Field(default=False)
    feature_lab_result_ocr_intake: bool = Field(default=False)
    persist_daily_health_score: bool = Field(default=False)
    feature_dosage_change_recommendation: bool = Field(default=False)
    feature_medication_safety_alert: bool = Field(default=False)

    # Phase 게이트 플래그 — docs/17 §9 매핑. 모든 기본값 False/0.
    # 운영 활성화 전에는 발주처 리뷰 게이트(#1/#2/#3) 통과 후에만 변경.
    enable_multimodal_llm: bool = Field(
        default=False,
        description="Ollama 멀티모달(예: Gemma 4) 보조 채널 활성화. docs/17 §9 게이트 #1 필요.",
    )
    enable_supplement_label_vision_extraction: bool = Field(
        default=False,
        description=(
            "영양제 라벨 함량/분류용 로컬 비전 구조화 추출(Gemma 4) 머지 활성화. 기본값 False. "
            "텍스트 파서(qwen)와 비전 모델을 한 요청에서 번갈아 호출하면 단일 GPU 호스트에서 "
            "모델 스왑(요청당 ~2회 reload, ~10s씩)이 발생해 60s 모바일 타임아웃을 넘기고, "
            "e4b 비전은 한글 함량 transcription 정확도가 낮다. 분류는 성분명 기반 코드 매핑으로 "
            "대체했으므로 더 강한 비전 모델이 검증되기 전까지 off로 유지한다."
        ),
    )
    enable_vision_classifier: bool = Field(
        default=False,
        description="라벨 영역 검출용 YOLO 어댑터 활성화. docs/17 §9 게이트 #2 필요.",
    )
    vision_classifier_model: str = Field(
        default=DEFAULT_VISION_CLASSIFIER_MODEL,
        description=(
            "공급 라벨 SECTION 검출용 8-class YOLO 모델 경로/태그. 기본값은 stock "
            "yolo26n.pt이며, 운영 시 학습된 section 가중치로 교체해야 한다. 로드 시 "
            "_validate_model_class_contract가 VISION_SECTION_LABELS 노출을 강제한다."
        ),
    )
    ocr_roi_preprocessing_policy: Literal[
        "disabled",
        "detect_only",
        "crop_before_primary",
    ] = Field(
        default="disabled",
        description="YOLO ROI를 primary OCR 입력에 적용하는 정책. 기본값 disabled.",
    )
    ocr_roi_crop_padding_ratio: float = Field(
        default=0.08,
        ge=0.0,
        le=0.50,
        description=(
            "YOLO ROI crop에 적용할 box-relative padding 비율. Detector box가 "
            "성분표 경계를 타이트하게 잡아 성분명/함량 열이 잘리는 것을 줄인다."
        ),
    )
    ocr_roi_crop_min_padding_px: int = Field(
        default=16,
        ge=0,
        le=256,
        description=(
            "YOLO ROI crop padding의 최소 픽셀값. 작은 section box에서도 OCR "
            "글자 가장자리가 잘리지 않도록 보수적인 여백을 보장한다."
        ),
    )
    ocr_roi_crop_max_padding_px: int = Field(
        default=96,
        ge=0,
        le=1024,
        description="YOLO ROI crop padding의 최대 픽셀값. 큰 box에서 과도한 full-image화를 막는다.",
    )
    multimodal_ocr_assist_policy: Literal[
        "disabled",
        "ocr_empty_only",
        "low_confidence",
    ] = Field(
        default="disabled",
        description="Ollama vision assist 호출 조건. 기본값 disabled.",
    )
    ocr_secondary_merge_policy: Literal["disabled", "always", "low_confidence"] = Field(
        default="disabled",
        description=(
            "Secondary OCR provider 병합 정책. 'disabled'(기본)=기존 fallback 체인 유지. "
            "'always'=secondary(Paddle)를 항상 실행해 primary(Clova)에 line-union 병합(보충). "
            "'low_confidence'=primary가 약할 때만 병합."
        ),
    )
    ocr_merge_dedup_threshold: float = Field(
        default=0.92,
        ge=0.0,
        le=1.0,
        description=(
            "Cross-provider line near-duplicate 임계값(SequenceMatcher ratio). 기본 "
            "0.92는 공백·대소문자 변형과 매우 높은 유사도만 잡는다 — 짧은 토큰의 한 글자 "
            "드리프트(예: 0↔O는 ratio 0.78~0.88)는 임계 미만이라 보충 라인에 남을 수 있다 "
            "(보충은 데이터를 잃지 않으므로 보수적 기본값; 더 공격적 dedup은 값을 낮추되 "
            "서로 다른 짧은 성분명 과병합 위험 주의)."
        ),
    )
    ocr_merge_max_supplement_lines: int = Field(
        default=40,
        ge=0,
        le=200,
        description="Secondary가 추가로 보충할 수 있는 최대 line 수(비용/garbage bound).",
    )
    ocr_ensemble_verification_mode: Literal["inherit_sample", "always_on_merge"] = Field(
        default="inherit_sample",
        description=(
            "'inherit_sample'(기본)=기존 multimodal_verification_sample_rate 사용. "
            "'always_on_merge'=병합이 실제로 일어난 결과는 sample_rate와 무관하게 항상 Gemma 검증. "
            "(두 모드 모두 ENABLE_MULTIMODAL_VERIFICATION=true·ENABLE_MULTIMODAL_LLM=true 전제.)"
        ),
    )
    enable_multimodal_verification: bool = Field(
        default=False,
        description="Primary OCR 결과를 local vision model로 샘플 검증. 기본값 disabled.",
    )
    multimodal_verification_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    multimodal_verification_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    analyze_optional_stage_budget_sec: int = Field(
        default=15,
        ge=1,
        le=20,
        description=(
            "지원 분석 동기 응답 안에서 *선택적·비동기* vision 추론 단계(multimodal vision 보조·"
            "multimodal 검증)가 단계당 점유할 수 있는 최대 시간(초). 이 단계들은 에러 시 primary "
            "결과로 graceful degrade하지만 *느린* local vision 추론(CPU에서 수십 초)은 막지 못해 "
            "모바일 업로드 타임아웃(60s)을 초과시킬 수 있다 → 이 예산을 넘으면 해당 단계를 건너뛰고 "
            "primary 결과/무경고로 진행한다. ⚠️ 단계당 적용이므로 활성 단계 수만큼 합산된다(현재 최대 "
            "2단계). primary Clova OCR + parser(약 ~15s) 위에 더해지므로 모바일 60s 대비 여유를 "
            "두고 설정할 것(그래서 le=20 상한). cross-provider 병합(local Paddle)은 동기 blocking "
            "predict라 asyncio timeout으로 선점 불가 → 이 예산이 아니라 자기 완료시간으로 bound된다. "
            "ollama_timeout_sec(전역, 기본 60)와 별개로 요청 경로 보강 단계에만 적용된다. GPU 등 빠른 "
            "추론 호스트에서만 상향."
        ),
    )
    enable_local_ocr: bool = Field(
        default=True,
        description=(
            "Local OCR (PaddleOCR) 운영 활성화. PaddleOCR이 primary로 동작하려면 true여야 한다. "
            "Google Vision primary 운영 환경에서 PaddleOCR fallback을 끄려면 false."
        ),
    )
    local_ocr_provider: Literal["paddleocr"] = Field(default="paddleocr")
    local_ocr_language: str = Field(default="korean")
    local_ocr_device: str | None = Field(default=None)
    local_ocr_confidence_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description=(
            "Legacy local OCR diagnostic threshold. The Paddle adapter preserves "
            "low-confidence text so downstream review and fallback logic can decide."
        ),
    )
    local_ocr_model_profile: Literal["mobile", "server_detection", "server"] = Field(
        default="mobile",
        description=(
            "PaddleOCR model profile for controlled diagnostic reruns. The default "
            "keeps PP-OCRv5 mobile detection and language-specific mobile recognition."
        ),
    )
    local_ocr_text_recognition_model_dir: Path | None = Field(
        default=None,
        description=(
            "Optional PaddleOCR inference model directory for a fine-tuned local "
            "recognizer. When set, the Paddle adapter forwards it as "
            "text_recognition_model_dir while keeping the selected detector/profile."
        ),
    )
    local_ocr_secondary_text_recognition_model_dir: Path | None = Field(
        default=None,
        description=(
            "Optional secondary PaddleOCR inference model directory used only by "
            "the OCR secondary-merge stage. This lets production run a primary "
            "recognizer and a distinct recall-oriented recognizer, then line-union "
            "their visible OCR text candidates without replacing the primary."
        ),
    )
    local_ocr_preprocess_mode: Literal[
        "none",
        "autocontrast",
        "grayscale_autocontrast",
    ] = Field(
        default="autocontrast",
        description=(
            "Local PaddleOCR input preprocessing mode. Defaults to a conservative "
            "autocontrast pass: it stretches contrast to the full dynamic range, "
            "which is a near-identity enhancement on already-clean images, never "
            "binarizes/deskews, preserves color, and cannot crash on arbitrary "
            "photos (a decode failure degrades to manual entry, not an error). "
            "It reduces truncated/garbled fragments on dense, low-contrast Korean "
            "labels. Override via LOCAL_OCR_PREPROCESS_MODE=none to disable."
        ),
    )
    local_ocr_use_textline_orientation: bool = Field(
        default=False,
        description=(
            "Whether PaddleOCR's textline orientation classifier is enabled. "
            "Default false matches the P1-5 isolation finding (commit 101df18e). "
            "Set true to re-measure tilted smartphone captures during OCR "
            "regression investigations."
        ),
    )
    local_ocr_text_det_limit_side_len: int | None = Field(
        default=None,
        ge=256,
        le=4096,
        description=(
            "Optional PaddleOCR predict() text_det_limit_side_len override for "
            "dense supplement labels. None keeps the upstream pipeline default."
        ),
    )
    local_ocr_text_det_limit_type: Literal["min", "max"] | None = Field(
        default=None,
        description=(
            "Optional PaddleOCR predict() text_det_limit_type override. Set only "
            "during measured OCR tuning runs."
        ),
    )
    local_ocr_text_rec_score_thresh: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Optional PaddleOCR predict() text_rec_score_thresh override. None "
            "keeps the upstream recognition-score default."
        ),
    )
    # PaddleOCR 3.x DB text-detection thresholds (predict()-time overrides).
    # Names/defaults per the official PP-OCR pipeline parameter reference:
    # https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-ChatOCRv4.en.md
    # None keeps the upstream pipeline default for text_det_thresh; box_thresh
    # and unclip_ratio below use measured Lemon-Aid defaults.
    local_ocr_text_det_thresh: float | None = Field(
        default=None,
        gt=0.0,
        le=1.0,
        description=(
            "Optional PaddleOCR predict() text_det_thresh override (pixel score "
            "threshold; upstream default 0.3). None keeps the pipeline default."
        ),
    )
    # Adopted default 0.4 (team decision 2026-06-14). The held-out detection
    # sweep picked box_thresh=0.4 as the single best lever (within-sweep macro
    # +0.0098 / micro +0.0175 / ingredient_recall +0.021 vs the 0.6 upstream
    # default). Authority: outputs/todo-list/2026-06-13/
    # 2026-06-13-ocr-benchmark-required-section-decision.md §7. PaddleOCR's own
    # upstream default is 0.6 (confirmed against the official reference above);
    # set LOCAL_OCR_TEXT_DET_BOX_THRESH to None/another value to override.
    local_ocr_text_det_box_thresh: float | None = Field(
        default=0.4,
        gt=0.0,
        le=1.0,
        description=(
            "PaddleOCR predict() text_det_box_thresh (box average-score "
            "threshold). Adopted default 0.4 (held-out sweep winner; upstream "
            "PaddleOCR default 0.6). Override via LOCAL_OCR_TEXT_DET_BOX_THRESH."
        ),
    )
    # Adopted candidate default 3.0 (team decision 2026-06-17). The latest
    # held-out b128 detector sweep kept the current recognizer and showed
    # unclip30 as the better micro/ingredient-recall runtime candidate among
    # measured unclip25/30/35 options. This is still a runtime candidate, not a
    # production gate pass; structured ROI/full fallback metrics remain the
    # promotion authority.
    # PaddleOCR's upstream default is 2.0; set LOCAL_OCR_TEXT_DET_UNCLIP_RATIO
    # to None/another value to override in controlled experiments.
    local_ocr_text_det_unclip_ratio: float | None = Field(
        default=3.0,
        gt=0.0,
        le=10.0,
        description=(
            "PaddleOCR predict() text_det_unclip_ratio override (text region "
            "expansion coefficient). Adopted runtime candidate default 3.0 from "
            "held-out A100 structured gate measurements; upstream PaddleOCR "
            "default is 2.0."
        ),
    )
    paddle_disable_model_source_check: bool = Field(
        default=True,
        description=(
            "Set PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=true at startup so the local "
            "PaddleOCR runtime never probes external model hosters on first call. "
            "Required for closed-network deployments (docs/32 §6)."
        ),
    )
    enable_clova_ocr: bool = Field(
        default=False,
        description="NAVER Cloud CLOVA OCR external fallback 활성화. 기본값 disabled.",
    )
    vision_roi_min_confidence: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="YOLO ROI 후보로 인정할 최소 confidence.",
    )
    vision_roi_allowed_classes: list[str] = Field(
        default_factory=_default_vision_roi_allowed_classes,
        min_length=1,
        max_length=16,
        description="YOLO ROI 보조에서 허용하는 object-detection 또는 label-section class labels.",
    )
    vision_roi_max_detections: int = Field(
        default=16,
        ge=1,
        le=50,
        description=(
            "YOLO section 검출기가 반환할 최대 ROI box 수. 다운스트림 OCR cap"
            "(MAX_PRIMARY_OCR_ROI_CANDIDATES=4)보다 앞선 source-level 상한이다."
        ),
    )
    enable_food_yolo_detector: bool = Field(
        default=False,
        description=(
            "식단 이미지 음식 후보 탐지용 local YOLO 활성화. 기본값 false이며 "
            "사용자 확인용 후보만 생성한다."
        ),
    )
    meal_yolo_model_path: str | None = Field(
        default=None,
        description="식단 이미지 음식 탐지 YOLO 모델 경로. 예: /app/Food-backend/best.pt",
    )
    meal_yolo_model_label: str = Field(
        default="food_yolo_local",
        description="식단 YOLO 모델을 API metadata에 노출할 때 쓰는 안전한 라벨.",
    )
    meal_yolo_min_confidence: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="식단 YOLO 후보 최소 confidence. Ultralytics predict 기본값과 같은 0.25.",
    )
    meal_yolo_max_detections: int = Field(
        default=20,
        ge=1,
        le=50,
        description="식단 YOLO가 review UI에 반환할 최대 후보 수.",
    )
    enable_food_dino_classifier: bool = Field(
        default=False,
        description=(
            "식단 이미지 단일요리 후보 분류용 exp16b+DINOv3 adapter 활성화. "
            "기본값 false이며 사용자 확인용 후보만 생성한다."
        ),
    )
    meal_food_classifier_module_dir: str = Field(
        default=str(BACKEND_ROOT / "Food-backend" / "src" / "classifier"),
        description="Food-backend canonical 음식 분류기 모듈 디렉터리.",
    )
    meal_food_classifier_exp16b_model_path: str | None = Field(
        default=str(BACKEND_ROOT / "Food-backend" / "best.pt"),
        description="음식 유무 gate용 exp16b YOLO 가중치 경로.",
    )
    meal_food_classifier_probe_path: str | None = Field(
        default=str(BACKEND_ROOT / "Food-backend" / "src" / "classifier" / "probe_head.pt"),
        description="DINOv3 linear probe checkpoint 경로.",
    )
    meal_food_classifier_nutrition_csv_path: str | None = Field(
        default=str(
            BACKEND_ROOT
            / "Food-backend"
            / "src"
            / "classifier"
            / "nutrition"
            / "food_nutrition_40class.csv"
        ),
        description="40-class food nutrition CSV 경로.",
    )
    meal_food_classifier_model_label: str = Field(
        default="food_dino_exp16b",
        description="음식 분류기 모델을 API metadata에 노출할 때 쓰는 안전한 라벨.",
    )
    meal_food_classifier_gate_confidence: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description=(
            "팀 food_classifier.py 기본 gate confidence. 공식 권장값이 아니라 "
            "해당 handoff 모듈의 실험 설정이다."
        ),
    )
    meal_food_classifier_max_px: int = Field(
        default=896,
        ge=224,
        le=2048,
        description="DINOv3 분류 전 이미지 축소 상한. 팀 handoff 모듈 기본값.",
    )
    enable_food_clip_filter: bool = Field(
        default=False,
        description=(
            "식단 분류 파이프라인에 CLIP 비음식 zero-shot 필터를 추가한다. YOLO 게이트와 "
            "DINOv3 분류 사이에서 사람·빈 식기·소스 종지 등 YOLO 오탐을 컷한다. 기본 false이며 "
            "enable_food_dino_classifier가 활성일 때만 의미가 있다. ⚠️ 활성화 시 요청당 CLIP(CPU) "
            "추가 추론 + 최초 1회 ~600MB 모델 로드가 동기 경로에 더해진다(모바일 타임아웃 민감). "
            "프로덕션 적용 전 지연 측정·warm-up 권장."
        ),
    )
    food_clip_filter_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="CLIP 음식 확률 임계값. 미만이면 비음식으로 컷(재촬영 안내).",
    )
    food_clip_filter_model_id: str = Field(
        default="openai/clip-vit-base-patch16",
        description="CLIP zero-shot 음식/비음식 필터 모델 ID(HuggingFace).",
    )
    label_studio_url: str = Field(
        default="http://localhost:8080",
        description="Label Studio 기본 URL. YOLO section annotation API 연동에 사용.",
    )
    label_studio_api_token: SecretStr | None = Field(
        default=None,
        description=(
            "Label Studio Personal Access Token. YOLO section bbox annotation을 "
            "API로 가져올 때 사용한다(.env 의 LABEL_STUDIO_API_TOKEN). 미설정 시 "
            "파일 export 경로만 사용한다."
        ),
    )
    enable_image_learning_pipeline: bool = Field(
        default=False,
        description="가명화 영양제 이미지의 학습 데이터셋 적재 활성화. docs/17 §9 게이트 #3 필요.",
    )
    enable_pgvector_storage: bool = Field(
        default=False,
        description="pgvector 기반 임베딩 저장소 활성화. docs/17 §9 게이트 #3 필요.",
    )
    embedding_model: str = Field(default="clip-ViT-B-32")
    embedding_dimensions: int | None = Field(
        default=None,
        ge=1,
        le=16000,
        description="검증된 embedding 차원. None이면 runner 결과를 그대로 기록한다.",
    )
    image_retention_days: int = Field(
        default=0,
        ge=0,
        le=730,
        description="영양제 이미지 보유 일수. 0 = 분석 직후 즉시 삭제(docs/17 §5).",
    )
    require_learning_manual_review: bool = Field(
        default=True,
        description=(
            "Require operator review before user opt-in learning images can enter "
            "embedding jobs. Keep true for private Supabase storage deployments."
        ),
    )
    enable_learning_auto_filter: bool = Field(
        default=True,
        description=(
            "Run deterministic safety/quality filters before operator review or "
            "embedding job creation for user opt-in learning images."
        ),
    )
    learning_object_storage_provider: Literal["disabled", "local", "s3", "supabase_s3"] = Field(
        default="disabled",
        description=(
            "학습 이미지 object storage provider. 기본값 disabled. "
            "Supabase private Storage는 supabase_s3를 사용한다."
        ),
    )
    learning_object_storage_bucket: str | None = Field(default=None)
    learning_object_storage_prefix: str = Field(default="learning/images")
    learning_object_storage_endpoint_url: str | None = Field(default=None)
    learning_object_storage_region: str | None = Field(default=None)
    learning_object_storage_sse: str | None = Field(default="AES256")
    learning_object_storage_local_path: Path = Field(
        default=PROJECT_ROOT / ".local" / "learning-images",
        description="개발/테스트 전용 local object storage 경로.",
    )

    @model_validator(mode="after")
    def validate_runtime_security(self) -> Self:
        """Validate database and production-only security requirements.

        Returns:
            Validated settings instance.

        Raises:
            ValueError: If settings contain an unsupported database URL, or if
                production settings contain unsafe defaults or missing OAuth/JWT
                configuration.
        """
        if _database_drivername(self.database_url) != POSTGRESQL_ASYNCPG_DRIVER:
            raise ValueError(
                f"DATABASE_URL must use {POSTGRESQL_ASYNCPG_DRIVER}; "
                "SQLite and sync PostgreSQL drivers are not supported."
            )
        self._validate_learning_object_storage_settings()
        self._validate_media_object_storage_settings()
        if (
            self.environment in {"staging", "production"}
            and self.enable_image_learning_pipeline
            and not self.require_learning_manual_review
        ):
            raise ValueError(
                "REQUIRE_LEARNING_MANUAL_REVIEW=true is required when image learning "
                "is enabled outside development."
            )
        if (
            self.enable_image_learning_pipeline
            and not self.enable_learning_auto_filter
            and not self.require_learning_manual_review
        ):
            raise ValueError(
                "ENABLE_LEARNING_AUTO_FILTER=true or REQUIRE_LEARNING_MANUAL_REVIEW=true "
                "is required when image learning is enabled."
            )

        if self.environment in {"staging", "production"} and self.auth_mode == "disabled":
            raise ValueError(
                "AUTH_MODE=disabled is forbidden outside development; "
                "set AUTH_MODE=jwt for staging and production."
            )
        if self.google_vision_auth_mode == "api_key" and not self.allow_google_api_key_auth:
            raise ValueError(
                "GOOGLE_VISION_AUTH_MODE=api_key requires "
                "ALLOW_GOOGLE_API_KEY_AUTH=true (non-production only)."
            )
        self._validate_food_image_model_settings()
        if self.allow_google_api_key_auth and self.environment == "production":
            raise ValueError(
                "ALLOW_GOOGLE_API_KEY_AUTH=true is forbidden in production; "
                "use GOOGLE_VISION_AUTH_MODE=adc with an attached service account."
            )
        if self.environment == "staging" and not self.allowed_hosts:
            raise ValueError("ALLOWED_HOSTS must be explicit in staging.")
        if self.environment == "staging" and _contains_wildcard(self.allowed_hosts):
            raise ValueError("ALLOWED_HOSTS must not contain wildcards in staging.")
        if (
            self.llm_provider == "sglang"
            and not self.allow_external_llm
            and not _is_local_http_url(self.sglang_base_url)
        ):
            raise ValueError(
                "SGLANG_BASE_URL must be a local loopback endpoint when "
                "ALLOW_EXTERNAL_LLM=false."
            )

        if self.environment != "production":
            return self

        privacy_hash_secret = _secret_value(self.privacy_hash_secret)
        errors = _failed_checks(
            (
                (
                    self.database_url == DEFAULT_DATABASE_URL,
                    "DATABASE_URL must not use the development default in production.",
                ),
                (
                    self.log_level.upper() == "DEBUG",
                    "LOG_LEVEL=DEBUG is not allowed in production.",
                ),
                (
                    self.allow_external_llm,
                    "ALLOW_EXTERNAL_LLM=true is not allowed in production.",
                ),
                (
                    self.ocr_primary_provider == "google_vision" and not self.allow_external_ocr,
                    "ALLOW_EXTERNAL_OCR=true is required when OCR_PRIMARY_PROVIDER=google_vision in production.",
                ),
                (
                    self.ocr_primary_provider == "google_vision"
                    and self.google_vision_auth_mode != "adc",
                    "GOOGLE_VISION_AUTH_MODE=adc is required when OCR_PRIMARY_PROVIDER=google_vision in production.",
                ),
                (
                    self.ocr_primary_provider == "google_vision" and not self.google_cloud_project,
                    "GOOGLE_CLOUD_PROJECT is required when OCR_PRIMARY_PROVIDER=google_vision in production.",
                ),
                (
                    self.ocr_primary_provider == "google_vision"
                    and bool(self.google_application_credentials),
                    "GOOGLE_APPLICATION_CREDENTIALS file-based credentials are not allowed for Google Vision in production.",
                ),
                (
                    self.ocr_primary_provider == "clova" and not self.allow_external_ocr,
                    "ALLOW_EXTERNAL_OCR=true is required when OCR_PRIMARY_PROVIDER=clova in production.",
                ),
                (
                    self.ocr_primary_provider == "clova" and not self.clova_ocr_api_url,
                    "CLOVA_OCR_API_URL is required when OCR_PRIMARY_PROVIDER=clova in production.",
                ),
                (
                    self.ocr_primary_provider == "clova" and self.clova_ocr_secret is None,
                    "CLOVA_OCR_SECRET is required when OCR_PRIMARY_PROVIDER=clova in production.",
                ),
                (
                    self.ocr_roi_preprocessing_policy != "disabled"
                    and not self.enable_vision_classifier,
                    "OCR_ROI_PREPROCESSING_POLICY requires ENABLE_VISION_CLASSIFIER=true.",
                ),
                (
                    self.enable_multimodal_verification and not self.enable_multimodal_llm,
                    "ENABLE_MULTIMODAL_VERIFICATION=true requires ENABLE_MULTIMODAL_LLM=true.",
                ),
                (
                    self.enable_multimodal_verification
                    and self.multimodal_verification_sample_rate <= 0,
                    "MULTIMODAL_VERIFICATION_SAMPLE_RATE must be greater than 0 when verification is enabled.",
                ),
                (
                    self.enable_clova_ocr and not self.allow_external_ocr,
                    "ALLOW_EXTERNAL_OCR=true is required when ENABLE_CLOVA_OCR=true in production.",
                ),
                (
                    self.enable_clova_ocr and not self.clova_ocr_api_url,
                    "CLOVA_OCR_API_URL is required when ENABLE_CLOVA_OCR=true in production.",
                ),
                (
                    self.enable_clova_ocr and self.clova_ocr_secret is None,
                    "CLOVA_OCR_SECRET is required when ENABLE_CLOVA_OCR=true in production.",
                ),
                (not self.allowed_origins, "ALLOWED_ORIGINS must be explicit in production."),
                (not self.allowed_hosts, "ALLOWED_HOSTS must be explicit in production."),
                (
                    _contains_wildcard(self.allowed_origins),
                    "ALLOWED_ORIGINS must not contain wildcards in production.",
                ),
                (
                    any(not origin.startswith("https://") for origin in self.allowed_origins),
                    "ALLOWED_ORIGINS must contain only https:// URLs in production.",
                ),
                (
                    _contains_wildcard(self.allowed_hosts),
                    "ALLOWED_HOSTS must not contain wildcards in production.",
                ),
                (self.auth_mode != "jwt", "AUTH_MODE=jwt is required for production user apps."),
                (
                    _is_non_https_url(self.jwt_jwks_url),
                    "JWT_JWKS_URL must use https in production.",
                ),
                (
                    _is_non_https_url(self.oidc_discovery_url),
                    "OIDC_DISCOVERY_URL must use https in production.",
                ),
                (not self.jwt_algorithms, "JWT_ALGORITHMS must be explicit in production."),
                (
                    not set(self.jwt_algorithms).issubset(ASYMMETRIC_JWT_ALGORITHMS),
                    "JWT_ALGORITHMS must use supported asymmetric signing algorithms.",
                ),
                (
                    not JWT_CORE_REQUIRED_CLAIMS.issubset(set(self.jwt_required_claims)),
                    "JWT_REQUIRED_CLAIMS must include aud, exp, iat, iss, and sub in production.",
                ),
                (
                    not self.jwt_scope_claims,
                    "JWT_SCOPE_CLAIMS must be explicit in production.",
                ),
                (
                    not self.jwt_expected_token_type
                    and (not self.jwt_token_use_claim or not self.jwt_token_use_allowed_values),
                    "JWT_EXPECTED_TOKEN_TYPE or JWT_TOKEN_USE_CLAIM with allowed values is required in production.",
                ),
                (
                    not privacy_hash_secret or privacy_hash_secret == DEFAULT_PRIVACY_HASH_SECRET,
                    "PRIVACY_HASH_SECRET must be set to a non-default value in production.",
                ),
                (
                    # Length/entropy floor: the HMAC peppers audit_logs actor-subject
                    # hashes; a short secret is brute-forceable to correlate hashes
                    # to known subjects. Only checked once a real secret is set.
                    bool(privacy_hash_secret)
                    and privacy_hash_secret != DEFAULT_PRIVACY_HASH_SECRET
                    and len(privacy_hash_secret) < self.privacy_hash_secret_min_length,
                    "PRIVACY_HASH_SECRET must be at least "
                    f"{self.privacy_hash_secret_min_length} characters in production.",
                ),
                (
                    self.allow_sample_kdris,
                    "ALLOW_SAMPLE_KDRIS=false is required in production.",
                ),
                (
                    self.kdris_data_version != "2025",
                    "KDRIS_DATA_VERSION=2025 is required in production.",
                ),
                (
                    not self.kdris_data_path,
                    "KDRIS_DATA_PATH is required in production.",
                ),
                (
                    self.enable_multimodal_llm,
                    "ENABLE_MULTIMODAL_LLM=true requires docs/17 §9 gate #1 sign-off.",
                ),
                (
                    self.enable_multimodal_verification,
                    "ENABLE_MULTIMODAL_VERIFICATION=true requires docs/17 §9 gate #1 sign-off.",
                ),
                (
                    self.enable_vision_classifier,
                    "ENABLE_VISION_CLASSIFIER=true requires docs/17 §9 gate #2 sign-off.",
                ),
                (
                    self.enable_food_yolo_detector,
                    "ENABLE_FOOD_YOLO_DETECTOR=true requires food YOLO validation sign-off.",
                ),
                (
                    self.enable_food_dino_classifier,
                    "ENABLE_FOOD_DINO_CLASSIFIER=true requires food classifier validation sign-off.",
                ),
                (
                    self.ocr_roi_preprocessing_policy != "disabled",
                    "OCR_ROI_PREPROCESSING_POLICY requires docs/17 §9 gate #2 sign-off.",
                ),
                (
                    self.ocr_primary_provider == "paddleocr" and not self.enable_local_ocr,
                    "OCR_PRIMARY_PROVIDER=paddleocr requires ENABLE_LOCAL_OCR=true.",
                ),
                (
                    self.enable_local_ocr and self.ocr_primary_provider != "paddleocr",
                    "ENABLE_LOCAL_OCR=true alongside a non-paddleocr primary requires local OCR fallback validation sign-off.",
                ),
                (
                    self.enable_clova_ocr,
                    "ENABLE_CLOVA_OCR=true requires external OCR fallback vendor sign-off.",
                ),
                (
                    self.enable_image_learning_pipeline,
                    "ENABLE_IMAGE_LEARNING_PIPELINE=true requires docs/17 §9 gate #3 sign-off.",
                ),
                (
                    self.enable_pgvector_storage,
                    "ENABLE_PGVECTOR_STORAGE=true requires docs/17 §9 gate #3 sign-off.",
                ),
                (
                    self.learning_object_storage_provider != "disabled",
                    "LEARNING_OBJECT_STORAGE_PROVIDER requires docs/17 §9 gate #3 sign-off.",
                ),
                (
                    self.media_object_storage_provider != "disabled",
                    "MEDIA_OBJECT_STORAGE_PROVIDER requires docs/53 media retention sign-off.",
                ),
                (
                    self.feature_hall_lite_weight_prediction,
                    "FEATURE_HALL_LITE_WEIGHT_PREDICTION=true requires Hall-lite validation sign-off.",
                ),
                (
                    self.feature_prescription_ocr_intake,
                    "FEATURE_PRESCRIPTION_OCR_INTAKE=true requires regulated OCR intake sign-off.",
                ),
                (
                    self.feature_lab_result_ocr_intake,
                    "FEATURE_LAB_RESULT_OCR_INTAKE=true requires regulated OCR intake sign-off.",
                ),
                (
                    self.sensitive_document_original_image_retention_seconds > 0,
                    "SENSITIVE_DOCUMENT_ORIGINAL_IMAGE_RETENTION_SECONDS>0 requires regulated OCR retention sign-off.",
                ),
                (
                    self.feature_medication_safety_alert,
                    "FEATURE_MEDICATION_SAFETY_ALERT=true requires medication safety workflow sign-off.",
                ),
            )
        )
        errors.extend(
            _missing_required_field_errors(
                (
                    ("JWT_ISSUER", self.jwt_issuer),
                    ("JWT_AUDIENCE", self.jwt_audience),
                    ("JWT_JWKS_URL", self.jwt_jwks_url),
                )
            )
        )

        if errors:
            raise ValueError(" ".join(errors))
        return self

    def _validate_food_image_model_settings(self) -> None:
        """Validate local food image detector/classifier settings.

        Raises:
            ValueError: If an enabled food image model lacks required local paths.
        """
        if self.enable_food_yolo_detector and not (
            self.meal_yolo_model_path and self.meal_yolo_model_path.strip()
        ):
            raise ValueError(
                "MEAL_YOLO_MODEL_PATH is required when ENABLE_FOOD_YOLO_DETECTOR=true."
            )
        if not self.enable_food_dino_classifier:
            return

        missing_food_classifier_fields = [
            name
            for name, value in (
                (
                    "MEAL_FOOD_CLASSIFIER_EXP16B_MODEL_PATH",
                    self.meal_food_classifier_exp16b_model_path,
                ),
                ("MEAL_FOOD_CLASSIFIER_PROBE_PATH", self.meal_food_classifier_probe_path),
                (
                    "MEAL_FOOD_CLASSIFIER_NUTRITION_CSV_PATH",
                    self.meal_food_classifier_nutrition_csv_path,
                ),
            )
            if not (value and value.strip())
        ]
        if missing_food_classifier_fields:
            fields = ", ".join(missing_food_classifier_fields)
            raise ValueError(f"{fields} required when ENABLE_FOOD_DINO_CLASSIFIER=true.")

    def _validate_learning_object_storage_settings(self) -> None:
        """Validate consent-gated learning image object storage settings.

        Raises:
            ValueError: If an enabled object store is missing private storage
                settings or server-only credentials.
        """
        if (
            self.learning_object_storage_provider == "s3"
            and not self.learning_object_storage_bucket
        ):
            raise ValueError(
                "LEARNING_OBJECT_STORAGE_BUCKET is required when "
                "LEARNING_OBJECT_STORAGE_PROVIDER=s3."
            )
        if self.learning_object_storage_provider != "supabase_s3":
            return
        if not self.supabase_storage_private_bucket and not self.learning_object_storage_bucket:
            raise ValueError(
                "SUPABASE_STORAGE_PRIVATE_BUCKET or LEARNING_OBJECT_STORAGE_BUCKET "
                "is required when LEARNING_OBJECT_STORAGE_PROVIDER=supabase_s3."
            )
        if not self.learning_object_storage_endpoint_url and not self.supabase_project_ref:
            raise ValueError(
                "SUPABASE_PROJECT_REF or LEARNING_OBJECT_STORAGE_ENDPOINT_URL is required "
                "when LEARNING_OBJECT_STORAGE_PROVIDER=supabase_s3."
            )
        if not self.learning_object_storage_region:
            raise ValueError(
                "LEARNING_OBJECT_STORAGE_REGION is required when "
                "LEARNING_OBJECT_STORAGE_PROVIDER=supabase_s3."
            )
        if self.supabase_storage_s3_access_key_id is None:
            raise ValueError(
                "SUPABASE_STORAGE_S3_ACCESS_KEY_ID is required when "
                "LEARNING_OBJECT_STORAGE_PROVIDER=supabase_s3."
            )
        if self.supabase_storage_s3_secret_access_key is None:
            raise ValueError(
                "SUPABASE_STORAGE_S3_SECRET_ACCESS_KEY is required when "
                "LEARNING_OBJECT_STORAGE_PROVIDER=supabase_s3."
            )

    def _validate_media_object_storage_settings(self) -> None:
        """Validate backend-only retained media object storage settings.

        Raises:
            ValueError: If an enabled object store is missing private storage
                settings or server-only credentials.
        """
        if self.media_object_storage_provider == "s3" and not self.media_object_storage_bucket:
            raise ValueError(
                "MEDIA_OBJECT_STORAGE_BUCKET is required when MEDIA_OBJECT_STORAGE_PROVIDER=s3."
            )
        if self.media_object_storage_provider != "supabase_s3":
            return
        if not self.supabase_storage_private_bucket and not self.media_object_storage_bucket:
            raise ValueError(
                "SUPABASE_STORAGE_PRIVATE_BUCKET or MEDIA_OBJECT_STORAGE_BUCKET "
                "is required when MEDIA_OBJECT_STORAGE_PROVIDER=supabase_s3."
            )
        if not self.media_object_storage_endpoint_url and not self.supabase_project_ref:
            raise ValueError(
                "SUPABASE_PROJECT_REF or MEDIA_OBJECT_STORAGE_ENDPOINT_URL is required "
                "when MEDIA_OBJECT_STORAGE_PROVIDER=supabase_s3."
            )
        if not self.media_object_storage_region:
            raise ValueError(
                "MEDIA_OBJECT_STORAGE_REGION is required when "
                "MEDIA_OBJECT_STORAGE_PROVIDER=supabase_s3."
            )
        if self.supabase_storage_s3_access_key_id is None:
            raise ValueError(
                "SUPABASE_STORAGE_S3_ACCESS_KEY_ID is required when "
                "MEDIA_OBJECT_STORAGE_PROVIDER=supabase_s3."
            )
        if self.supabase_storage_s3_secret_access_key is None:
            raise ValueError(
                "SUPABASE_STORAGE_S3_SECRET_ACCESS_KEY is required when "
                "MEDIA_OBJECT_STORAGE_PROVIDER=supabase_s3."
            )


@lru_cache
def get_settings() -> Settings:
    """애플리케이션 설정 싱글턴을 반환한다.

    Returns:
        환경 변수와 기본값에서 로드한 설정 객체.
    """
    return Settings()
