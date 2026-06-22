"""OCR adapter factory helpers."""

from __future__ import annotations

import logging
from typing import Literal

from src.config import Settings
from src.llm.ollama_vision import OllamaVisionAssistAdapter
from src.ocr.base import OCRAdapter
from src.ocr.providers.clova import ClovaOCRAdapter
from src.ocr.providers.google_vision import (
    GoogleVisionOCRAdapter,
    build_google_vision_endpoint,
)
from src.ocr.providers.google_vision_auth import (
    GoogleVisionADCAuthHeaders,
    GoogleVisionApiKeyAuthHeaders,
    GoogleVisionAuthHeadersProvider,
)
from src.ocr.providers.paddle import PaddleOCRAdapter
from src.services.supplement_image_analysis import SupplementImageAnalysisAdapters
from src.vision.yolo import YoloLabelDetector

logger = logging.getLogger(__name__)


class OCRConfigurationError(RuntimeError):
    """Raised when OCR settings request a provider that cannot be built."""


SupplementOCRProviderSelector = Literal["configured", "google_vision", "paddleocr", "clova"]


def is_external_ocr_pipeline_enabled(
    settings: Settings,
    provider_selector: SupplementOCRProviderSelector = "configured",
) -> bool:
    """Return whether the selected OCR chain may call an external provider.

    Args:
        settings: Runtime settings.
        provider_selector: Per-request OCR provider selector. ``configured``
            uses the settings-driven provider chain.

    Returns:
        True when the active OCR path may send image bytes to an external OCR
        provider.
    """
    if provider_selector == "google_vision":
        return True
    if provider_selector == "clova":
        return True
    if provider_selector == "paddleocr":
        return False
    return settings.ocr_primary_provider in {"google_vision", "clova"} or settings.enable_clova_ocr


def build_supplement_ocr_adapter(settings: Settings) -> OCRAdapter | None:
    """Build the configured supplement-label OCR adapter.

    Args:
        settings: Runtime settings.

    Returns:
        OCR adapter, or None when OCR is intentionally disabled.

    Raises:
        OCRConfigurationError: If the selected provider is missing its required gates.
    """
    if settings.ocr_primary_provider == "none":
        return None
    if settings.ocr_primary_provider == "paddleocr":
        return _build_paddleocr_primary_adapter(settings)
    if settings.ocr_primary_provider == "google_vision":
        return _build_google_vision_adapter(settings)
    if settings.ocr_primary_provider == "clova":
        return _build_clova_primary_adapter(settings)
    raise OCRConfigurationError(
        f"Unsupported OCR_PRIMARY_PROVIDER: {settings.ocr_primary_provider}"
    )


def build_supplement_image_analysis_adapters(settings: Settings) -> SupplementImageAnalysisAdapters:
    """Build the complete supplement image analysis adapter set.

    Args:
        settings: Runtime settings.

    Returns:
        Service adapter bundle for OCR, ROI detection, vision assist, and fallback OCR.

    Raises:
        OCRConfigurationError: If requested adapter settings are incomplete or unsafe.
    """
    return SupplementImageAnalysisAdapters(
        ocr=build_supplement_ocr_adapter(settings),
        vision=_build_vision_adapter(settings),
        multimodal_ocr=_build_multimodal_ocr_adapter(settings),
        secondary_merge_ocr=_build_secondary_merge_ocr_adapter(settings),
        fallback_ocr_adapters=tuple(_build_fallback_ocr_adapters(settings)),
    )


def build_supplement_image_analysis_adapters_for_provider(
    settings: Settings,
    provider_selector: SupplementOCRProviderSelector,
    *,
    configured_adapters: SupplementImageAnalysisAdapters | None = None,
) -> SupplementImageAnalysisAdapters:
    """Build adapters constrained to a request-selected OCR provider.

    Args:
        settings: Runtime settings.
        provider_selector: Provider selected by the multipart request.
        configured_adapters: Already-built settings-driven adapter bundle used
            when ``provider_selector`` is ``configured``.

    Returns:
        Adapter bundle for the selected OCR path.

    Raises:
        OCRConfigurationError: If the requested provider is not configured.
    """
    if provider_selector == "configured":
        return configured_adapters or build_supplement_image_analysis_adapters(settings)
    if provider_selector == "google_vision":
        return SupplementImageAnalysisAdapters(
            ocr=_build_google_vision_adapter(settings),
            vision=_build_vision_adapter(settings),
            multimodal_ocr=_build_multimodal_ocr_adapter(settings),
            secondary_merge_ocr=None,
            fallback_ocr_adapters=(),
        )
    if provider_selector == "paddleocr":
        return SupplementImageAnalysisAdapters(
            ocr=_build_paddleocr_primary_adapter(settings),
            vision=_build_vision_adapter(settings),
            multimodal_ocr=_build_multimodal_ocr_adapter(settings),
            secondary_merge_ocr=None,
            fallback_ocr_adapters=(),
        )
    if provider_selector == "clova":
        return SupplementImageAnalysisAdapters(
            ocr=_build_clova_primary_adapter(settings),
            vision=_build_vision_adapter(settings),
            multimodal_ocr=_build_multimodal_ocr_adapter(settings),
            secondary_merge_ocr=None,
            fallback_ocr_adapters=(),
        )
    raise OCRConfigurationError(f"Unsupported OCR provider selector: {provider_selector}")


def _build_vision_adapter(settings: Settings) -> YoloLabelDetector | None:
    """Build the gated YOLO ROI adapter when enabled.

    Args:
        settings: Runtime settings.

    Returns:
        YOLO ROI detector or None.
    """
    if not settings.enable_vision_classifier:
        return None
    return YoloLabelDetector(settings)


def _build_multimodal_ocr_adapter(settings: Settings) -> OllamaVisionAssistAdapter | None:
    """Build the local Ollama vision assist adapter when a policy can call it.

    Args:
        settings: Runtime settings.

    Returns:
        Ollama vision assist adapter or None.

    Raises:
        OCRConfigurationError: If a multimodal policy is enabled without the gate.
    """
    wants_fallback = settings.multimodal_ocr_assist_policy != "disabled"
    wants_verification = settings.enable_multimodal_verification
    if not wants_fallback and not wants_verification:
        return None
    if not settings.enable_multimodal_llm:
        raise OCRConfigurationError(
            "ENABLE_MULTIMODAL_LLM=true is required for Ollama vision assist."
        )
    return OllamaVisionAssistAdapter(settings)


def _build_secondary_merge_ocr_adapter(settings: Settings) -> OCRAdapter | None:
    """Build the optional PaddleOCR secondary-merge adapter for the ensemble stage.

    The ensemble stage line-union merges this provider into the primary OCR
    result instead of replacing it. Paddle is merged into Paddle only when a
    distinct secondary recognition model directory is configured; otherwise the
    factory avoids duplicating the same local OCR pass.

    Args:
        settings: Runtime settings.

    Returns:
        PaddleOCR adapter when the merge policy is enabled and Paddle is not the
        primary provider, otherwise None.
    """
    if settings.ocr_secondary_merge_policy == "disabled":
        return None
    if not settings.enable_local_ocr:
        return None
    if (
        settings.ocr_primary_provider == "paddleocr"
        and settings.local_ocr_secondary_text_recognition_model_dir is None
    ):
        return None
    return PaddleOCRAdapter(_secondary_merge_paddle_settings(settings))


def _secondary_merge_paddle_settings(settings: Settings) -> Settings:
    """Return settings for the secondary PaddleOCR merge adapter.

    Args:
        settings: Runtime settings.

    Returns:
        Original settings, or a copy whose recognizer directory points at the
        secondary merge model.
    """
    secondary_recognition_model_dir = settings.local_ocr_secondary_text_recognition_model_dir
    if secondary_recognition_model_dir is None:
        return settings
    return settings.model_copy(
        update={"local_ocr_text_recognition_model_dir": secondary_recognition_model_dir}
    )


def _build_paddleocr_primary_adapter(settings: Settings) -> PaddleOCRAdapter:
    """Build PaddleOCR as the primary OCR adapter.

    Args:
        settings: Runtime settings.

    Returns:
        PaddleOCR adapter.

    Raises:
        OCRConfigurationError: If local OCR is disabled.
    """
    if not settings.enable_local_ocr:
        raise OCRConfigurationError(
            "ENABLE_LOCAL_OCR=true is required when OCR_PRIMARY_PROVIDER=paddleocr."
        )
    return PaddleOCRAdapter(settings)


def _build_fallback_ocr_adapters(settings: Settings) -> list[OCRAdapter]:
    """Build optional secondary OCR fallback adapters in configured order.

    PaddleOCR and CLOVA are each omitted from the secondary list when already
    selected as the primary provider, so the same adapter is never invoked
    twice in a single pipeline.

    Args:
        settings: Runtime settings.

    Returns:
        OCR fallback adapters.
    """
    adapters: list[OCRAdapter] = []
    if settings.enable_local_ocr and settings.ocr_primary_provider != "paddleocr":
        adapters.append(PaddleOCRAdapter(settings))
    if settings.enable_clova_ocr and settings.ocr_primary_provider != "clova":
        adapters.append(ClovaOCRAdapter(settings))
    return adapters


def _build_clova_primary_adapter(settings: Settings) -> ClovaOCRAdapter:
    """Build NAVER Cloud CLOVA OCR as the primary OCR adapter.

    Args:
        settings: Runtime settings.

    Returns:
        CLOVA OCR adapter.

    Raises:
        OCRConfigurationError: If external OCR gates or CLOVA credentials are missing.
    """
    if not settings.allow_external_ocr:
        raise OCRConfigurationError(
            "ALLOW_EXTERNAL_OCR=true is required when OCR_PRIMARY_PROVIDER=clova."
        )
    if not settings.clova_ocr_api_url:
        raise OCRConfigurationError(
            "CLOVA_OCR_API_URL is required when OCR_PRIMARY_PROVIDER=clova."
        )
    if settings.clova_ocr_secret is None:
        raise OCRConfigurationError("CLOVA_OCR_SECRET is required when OCR_PRIMARY_PROVIDER=clova.")
    return ClovaOCRAdapter(settings)


def _build_google_vision_adapter(settings: Settings) -> GoogleVisionOCRAdapter:
    """Build a Google Vision OCR adapter from settings.

    Args:
        settings: Runtime settings.

    Returns:
        Google Vision OCR adapter.

    Raises:
        OCRConfigurationError: If required Google Vision settings are missing.
    """
    if not settings.allow_external_ocr:
        raise OCRConfigurationError("ALLOW_EXTERNAL_OCR=true is required for Google Vision.")
    if settings.environment == "production" and settings.google_vision_auth_mode != "adc":
        raise OCRConfigurationError("GOOGLE_VISION_AUTH_MODE=adc is required in production.")
    if settings.google_vision_auth_mode == "api_key":
        if settings.google_cloud_api_key is None:
            raise OCRConfigurationError("GOOGLE_CLOUD_API_KEY is required for Google Vision.")
        if settings.environment == "staging":
            logger.warning(
                "Google Vision api_key mode active in staging; ADC migration recommended.",
            )
        auth_headers: GoogleVisionAuthHeadersProvider = GoogleVisionApiKeyAuthHeaders(
            settings.google_cloud_api_key
        )
    else:
        if settings.google_cloud_project is None:
            raise OCRConfigurationError(
                "GOOGLE_CLOUD_PROJECT is required for Google Vision ADC mode."
            )
        auth_headers = GoogleVisionADCAuthHeaders(project_id=settings.google_cloud_project)

    try:
        endpoint = build_google_vision_endpoint(
            project_id=settings.google_cloud_project,
            location=settings.google_vision_location,
        )
    except ValueError as exc:
        raise OCRConfigurationError(str(exc)) from exc

    return GoogleVisionOCRAdapter(
        auth_headers=auth_headers,
        endpoint=endpoint,
        feature=settings.google_vision_feature,
        language_hints=settings.google_vision_language_hints,
        timeout_seconds=settings.google_vision_timeout_seconds,
        max_retries=settings.google_vision_max_retries,
    )
