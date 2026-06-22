"""Sanitized runtime readiness helpers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.config import DEFAULT_VISION_CLASSIFIER_MODEL, Settings
from src.ocr.factory import (
    OCRConfigurationError,
    SupplementOCRProviderSelector,
    build_supplement_image_analysis_adapters,
    build_supplement_image_analysis_adapters_for_provider,
    is_external_ocr_pipeline_enabled,
)
from src.services.supplement_image_analysis import SupplementImageAnalysisAdapters
from src.vision.taxonomy import VISION_SECTION_LABELS, normalize_vision_label_set

OCR_PROVIDER_SELECTORS: tuple[SupplementOCRProviderSelector, ...] = (
    "configured",
    "paddleocr",
    "google_vision",
    "clova",
)
ADAPTER_PROVIDER_LABELS = {
    "ClovaOCRAdapter": "clova_ocr",
    "GoogleVisionOCRAdapter": "google_vision_document",
    "PaddleOCRAdapter": "paddleocr_local",
}


class OCRProviderReadiness(BaseModel):
    """Sanitized readiness status for one OCR selector.

    Attributes:
        selector: Request-level OCR selector.
        configured: Whether an OCR adapter can be built from settings.
        status: Safe configuration-level provider status for operators.
        status_reason: Stable non-secret reason for non-ready provider states.
        provider_label: Stable provider label used by preview metadata.
        external_ocr: Whether this selector may send image bytes to an external OCR provider.
        error_class: Exception class name when configuration fails.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    selector: SupplementOCRProviderSelector
    configured: bool
    status: Literal["ready", "disabled", "degraded", "misconfigured"]
    status_reason: str | None = Field(default=None, max_length=120)
    provider_label: str | None = Field(default=None, max_length=80)
    external_ocr: bool
    error_class: str | None = Field(default=None, max_length=120)


class OCRReadiness(BaseModel):
    """Sanitized OCR configuration summary for mobile smoke tests.

    Attributes:
        primary_provider: Settings-driven primary OCR provider.
        local_ocr_enabled: Whether local PaddleOCR is allowed.
        external_ocr_allowed: Whether external OCR providers are allowed.
        clova_fallback_enabled: Whether CLOVA fallback may be built.
        google_vision_auth_mode: Google Vision auth mode label, without credentials.
        live_provider_auth_checked: Always false; live auth is checked by smoke requests.
        providers: Provider-selector readiness rows.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    primary_provider: Literal["none", "google_vision", "paddleocr", "clova"]
    local_ocr_enabled: bool
    external_ocr_allowed: bool
    clova_fallback_enabled: bool
    google_vision_auth_mode: Literal["api_key", "adc"]
    live_provider_auth_checked: Literal[False] = False
    providers: list[OCRProviderReadiness]


class VisionReadiness(BaseModel):
    """Sanitized YOLO/ROI readiness flags.

    Attributes:
        classifier_enabled: Whether YOLO ROI detection is enabled.
        roi_preprocessing_policy: OCR ROI preprocessing policy.
        supplement_yolo_contract: Safe class-name contract required for supplement ROI detection.
        supplement_yolo_allowed_labels: Canonical configured labels accepted for supplement ROI OCR.
        supplement_yolo_required_section_labels: Required section labels for custom detector readiness.
        section_roi_model_configured: Whether a non-stock section detector model is wired.
        food_yolo_enabled: Whether food image YOLO candidate detection is enabled.
        food_yolo_model_configured: Whether a food YOLO model path is configured.
        food_yolo_model_label: Safe local model label for food YOLO metadata.
        food_yolo_min_confidence: Minimum confidence accepted for food YOLO candidates.
        food_yolo_max_detections: Maximum food YOLO candidates returned for review.
        multimodal_llm_enabled: Whether local multimodal LLM calls are enabled.
        multimodal_ocr_assist_policy: Policy for local vision OCR assist.
        multimodal_verification_enabled: Whether accepted OCR can be sampled for verification.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    classifier_enabled: bool
    roi_preprocessing_policy: str
    supplement_yolo_contract: Literal[
        "disabled",
        "section_roi_model_required",
    ]
    supplement_yolo_allowed_labels: list[str]
    supplement_yolo_required_section_labels: list[str]
    section_roi_model_configured: bool
    food_yolo_enabled: bool
    food_yolo_model_configured: bool
    food_yolo_model_label: str | None = Field(default=None, max_length=80)
    food_yolo_min_confidence: float
    food_yolo_max_detections: int
    multimodal_llm_enabled: bool
    multimodal_ocr_assist_policy: str
    multimodal_verification_enabled: bool


class ParserReadiness(BaseModel):
    """Sanitized structured parser configuration.

    Attributes:
        provider: Configured parser provider label.
        model_configured: Whether a parser model name is configured.
        live_model_checked: Always false; live model availability is checked by preflight scripts.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: Literal["ollama"]
    model_configured: bool
    live_model_checked: Literal[False] = False


class ReadinessResponse(BaseModel):
    """Top-level sanitized readiness response.

    Attributes:
        status: API readiness status for config-level mobile smoke checks.
        version: API version.
        ocr: OCR provider configuration summary.
        vision: YOLO and multimodal feature flags.
        parser: Structured parser configuration summary.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["ok"]
    version: str
    ocr: OCRReadiness
    vision: VisionReadiness
    parser: ParserReadiness


def build_readiness_response(settings: Settings) -> ReadinessResponse:
    """Build a sanitized readiness response without live provider calls.

    The response intentionally does not call OCR vendors, Ollama, object stores,
    or databases. Provider credentials and public URLs are not included; live
    auth and model availability are verified by explicit smoke scripts.

    Args:
        settings: Runtime settings.

    Returns:
        Readiness response safe for local mobile smoke diagnostics.
    """
    configured_adapters = None
    try:
        configured_adapters = build_supplement_image_analysis_adapters(settings)
    except OCRConfigurationError:
        configured_adapters = None

    return ReadinessResponse(
        status="ok",
        version="0.1.0",
        ocr=OCRReadiness(
            primary_provider=settings.ocr_primary_provider,
            local_ocr_enabled=settings.enable_local_ocr,
            external_ocr_allowed=settings.allow_external_ocr,
            clova_fallback_enabled=settings.enable_clova_ocr,
            google_vision_auth_mode=settings.google_vision_auth_mode,
            providers=[
                _provider_readiness(
                    settings,
                    selector,
                    configured_adapters=configured_adapters,
                )
                for selector in OCR_PROVIDER_SELECTORS
            ],
        ),
        vision=VisionReadiness(
            classifier_enabled=settings.enable_vision_classifier,
            roi_preprocessing_policy=settings.ocr_roi_preprocessing_policy,
            supplement_yolo_contract=(
                "section_roi_model_required" if settings.enable_vision_classifier else "disabled"
            ),
            supplement_yolo_allowed_labels=normalize_vision_label_set(
                settings.vision_roi_allowed_classes
            ),
            supplement_yolo_required_section_labels=sorted(VISION_SECTION_LABELS),
            section_roi_model_configured=(
                settings.enable_vision_classifier
                and settings.vision_classifier_model.strip()
                not in {"", DEFAULT_VISION_CLASSIFIER_MODEL}
            ),
            food_yolo_enabled=settings.enable_food_yolo_detector,
            food_yolo_model_configured=bool(
                settings.meal_yolo_model_path and settings.meal_yolo_model_path.strip()
            ),
            food_yolo_model_label=(
                settings.meal_yolo_model_label.strip()
                if settings.enable_food_yolo_detector and settings.meal_yolo_model_label.strip()
                else None
            ),
            food_yolo_min_confidence=settings.meal_yolo_min_confidence,
            food_yolo_max_detections=settings.meal_yolo_max_detections,
            multimodal_llm_enabled=settings.enable_multimodal_llm,
            multimodal_ocr_assist_policy=settings.multimodal_ocr_assist_policy,
            multimodal_verification_enabled=settings.enable_multimodal_verification,
        ),
        parser=ParserReadiness(
            provider=settings.llm_provider,
            model_configured=bool(settings.ollama_model.strip()),
        ),
    )


def _provider_readiness(
    settings: Settings,
    selector: SupplementOCRProviderSelector,
    *,
    configured_adapters: SupplementImageAnalysisAdapters | None,
) -> OCRProviderReadiness:
    """Build a sanitized readiness row for one request-level OCR selector.

    Args:
        settings: Runtime settings.
        selector: Request-level OCR selector.
        configured_adapters: Optional prebuilt configured adapter bundle.

    Returns:
        OCR provider readiness row.
    """
    try:
        adapters = build_supplement_image_analysis_adapters_for_provider(
            settings,
            selector,
            configured_adapters=configured_adapters,
        )
    except OCRConfigurationError as exc:
        return OCRProviderReadiness(
            selector=selector,
            configured=False,
            status="misconfigured",
            status_reason="configuration_error",
            provider_label=None,
            external_ocr=is_external_ocr_pipeline_enabled(settings, selector),
            error_class=exc.__class__.__name__,
        )
    external_ocr = is_external_ocr_pipeline_enabled(settings, selector)
    status, status_reason = _provider_status(
        configured=adapters.ocr is not None,
        external_ocr=external_ocr,
    )
    return OCRProviderReadiness(
        selector=selector,
        configured=adapters.ocr is not None,
        status=status,
        status_reason=status_reason,
        provider_label=_adapter_provider_label(adapters.ocr),
        external_ocr=external_ocr,
    )


def _provider_status(
    *,
    configured: bool,
    external_ocr: bool,
) -> tuple[Literal["ready", "disabled", "degraded", "misconfigured"], str | None]:
    """Return a sanitized provider status without calling vendor services.

    Args:
        configured: Whether an adapter is available for the selector.
        external_ocr: Whether the selector may call an external OCR provider.

    Returns:
        Status and stable reason. External OCR is degraded until an explicit live
        smoke verifies credentials, because this readiness endpoint intentionally
        avoids vendor calls and never exposes credential material.
    """
    if not configured:
        return "disabled", "adapter_disabled"
    if external_ocr:
        return "degraded", "live_auth_not_checked"
    return "ready", None


def _adapter_provider_label(adapter: object | None) -> str | None:
    """Return a stable provider label for a built OCR adapter.

    Args:
        adapter: OCR adapter instance.

    Returns:
        Provider label used in preview metadata, or None when no OCR adapter is active.
    """
    if adapter is None:
        return None
    return ADAPTER_PROVIDER_LABELS.get(adapter.__class__.__name__, "unknown")
