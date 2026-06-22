"""Local Ollama vision assist for OCR fallback candidate extraction."""

from __future__ import annotations

import base64
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from src.config import Settings
from src.llm.ollama import (
    OllamaChatClient,
    OllamaClientError,
    OllamaConfigurationError,
    OllamaReadiness,
    OllamaStructuredOutputError,
    extract_ollama_message_content,
    extract_ollama_model_names,
    validate_local_ollama_settings,
)
from src.ocr.base import OCRAdapter, OCRImageInput, OCRResult
from src.vision.preprocessing import VisionPreprocessingError, crop_image_to_bounding_box

OLLAMA_VISION_ASSIST_PROVIDER = "ollama_vision_assist"

OLLAMA_VISION_ASSIST_SYSTEM_PROMPT = """
You are a local supplement label OCR fallback component.
Extract only text fragments that are visibly present in the image.
Do not infer ingredients, amounts, dosage, health effects, risks, or product facts
from outside knowledge. Do not provide medical or nutrition advice. If text is not
visible, return an empty list or null. Return only JSON matching the supplied schema.
""".strip()
OLLAMA_VISION_VERIFY_SYSTEM_PROMPT = """
You are a local supplement label OCR verification component.
Compare the provided OCR text with only the visible text in the image.
Do not infer hidden text, ingredients, amounts, dosage, health effects, risks, or
medical advice. Mark missing critical sections when product name, supplement
facts, intake method, or precautions are absent from the visible image. Return
only JSON matching the supplied schema.
""".strip()
OLLAMA_VISION_EXTRACT_SYSTEM_PROMPT = """
You are a local supplement label transcription component. Read ONLY values that are
visibly printed on the supplement label image. Transcribe each ingredient's name with
its printed amount and unit exactly as shown in the supplement facts or ingredient
table; if an amount or unit is not visibly printed for an ingredient, use null. Choose
product_category_key ONLY from the provided allowed list, based solely on the visibly
printed product name/ingredients; if none clearly applies, return null. Do NOT infer
hidden values, do NOT recommend dosage, do NOT add health, disease, efficacy, or
medical claims or advice. Return only JSON matching the supplied schema.
""".strip()
MAX_VERIFICATION_OCR_TEXT_CHARS = 4_000
MAX_VISION_EXTRACTION_INGREDIENTS = 60
MAX_VISION_EXTRACTION_CATEGORIES = 60
VISION_READINESS_PROBE_IMAGE_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class OllamaVisionReadinessProbeResult(BaseModel):
    """Validated response for the local vision image-input smoke test.

    Attributes:
        vision_input_supported: Whether the model accepted the submitted image.
        visible_text_present: Whether the probe image contains visible text.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    vision_input_supported: bool
    visible_text_present: bool


class OllamaVisionTextCandidateResult(BaseModel):
    """Validated visible-text candidates returned by a local vision model.

    Attributes:
        visible_text_fragments: Text fragments visibly present in the image.
        possible_product_name: Product name candidate only when visibly present.
        source_region: Whether the image sent to the model was full image or YOLO ROI.
        low_confidence_fields: Candidate fields requiring user review.
        warnings: Non-medical warnings to surface in preview metadata.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    visible_text_fragments: list[str] = Field(default_factory=list, max_length=30)
    possible_product_name: str | None = Field(default=None, max_length=200)
    source_region: Literal["full_image", "yolo_roi"]
    low_confidence_fields: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("visible_text_fragments", "low_confidence_fields", "warnings")
    @classmethod
    def _normalize_string_list(cls, values: list[str]) -> list[str]:
        """Normalize model-produced string lists and remove duplicates.

        Args:
            values: Candidate string values.

        Returns:
            Trimmed non-empty strings in first-seen order.
        """
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            stripped = value.strip()
            if not stripped or stripped in seen:
                continue
            normalized.append(stripped)
            seen.add(stripped)
        return normalized


class OllamaVisionTextVerificationResult(BaseModel):
    """Validated visible-text verification returned by a local vision model.

    Attributes:
        verification_status: Overall match decision for OCR text versus image text.
        confidence: Model confidence in the verification decision.
        source_region: Whether the image submitted was full image or YOLO ROI.
        matched_fragments: OCR fragments that are visibly supported.
        missing_fragments: OCR fragments not supported by the visible image.
        missing_critical_sections: Required supplement sections not visible in the image.
        warnings: Non-medical warnings to surface in preview metadata.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    verification_status: Literal["match", "partial", "mismatch", "uncertain"]
    confidence: float = Field(ge=0, le=1)
    source_region: Literal["full_image", "yolo_roi"]
    matched_fragments: list[str] = Field(default_factory=list, max_length=30)
    missing_fragments: list[str] = Field(default_factory=list, max_length=30)
    missing_critical_sections: list[
        Literal["product_name", "supplement_facts", "intake_method", "precautions"]
    ] = Field(default_factory=list, max_length=4)
    warnings: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("matched_fragments", "missing_fragments", "warnings")
    @classmethod
    def _normalize_string_list(cls, values: list[str]) -> list[str]:
        """Normalize model-produced string lists and remove duplicates.

        Args:
            values: Candidate string values.

        Returns:
            Trimmed non-empty strings in first-seen order.
        """
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            stripped = value.strip()
            if not stripped or stripped in seen:
                continue
            normalized.append(stripped)
            seen.add(stripped)
        return normalized


class OllamaVisionIngredient(BaseModel):
    """One ingredient transcribed from a supplement label image.

    Attributes:
        name: Ingredient name visibly printed on the label.
        amount: Printed amount per serving, or null when not visibly printed.
        unit: Printed amount unit, or null when not visibly printed.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    amount: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=32)


class OllamaVisionStructuredExtractionResult(BaseModel):
    """Validated transcription-only structured extraction from a label image.

    Attributes:
        product_category_key: Allowed-list category key, or null when none applies.
        ingredients: Visibly printed ingredient names with printed amount/unit.
        low_confidence_fields: Candidate fields requiring user review.
        warnings: Non-medical warnings to surface in preview metadata.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_category_key: str | None = Field(default=None, max_length=64)
    ingredients: list[OllamaVisionIngredient] = Field(
        default_factory=list,
        max_length=MAX_VISION_EXTRACTION_INGREDIENTS,
    )
    low_confidence_fields: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("low_confidence_fields", "warnings")
    @classmethod
    def _normalize_string_list(cls, values: list[str]) -> list[str]:
        """Normalize model-produced string lists and remove duplicates.

        Args:
            values: Candidate string values.

        Returns:
            Trimmed non-empty strings in first-seen order.
        """
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            stripped = value.strip()
            if not stripped or stripped in seen:
                continue
            normalized.append(stripped)
            seen.add(stripped)
        return normalized


class OllamaVisionAssistAdapter(OCRAdapter):
    """OCR-like fallback adapter backed by a local Ollama vision model.

    This adapter is intentionally not a primary OCR provider. Callers must invoke it
    only when OCR is empty or low-confidence according to runtime policy.
    """

    def __init__(
        self,
        settings: Settings,
        client: OllamaChatClient | None = None,
    ) -> None:
        """Initialize the local Ollama vision assist adapter.

        Args:
            settings: Runtime settings containing local Ollama and model configuration.
            client: Optional injected Ollama transport for tests.
        """
        self.settings = settings
        self.client = client or OllamaChatClient(settings)

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Extract visible text candidates from an image as OCR fallback.

        Args:
            image: Validated image input. If ``label_region`` is present, only that
                crop is sent to the local vision model.

        Returns:
            OCR-like text candidate result with provider ``ollama_vision_assist``.

        Raises:
            OllamaConfigurationError: If the feature flag or local model is invalid.
            OllamaClientError: If the local Ollama API call fails.
            OllamaStructuredOutputError: If model output fails schema validation.
        """
        _validate_vision_settings(self.settings)
        image_payload, source_region = _build_image_payload(image)
        schema = OllamaVisionTextCandidateResult.model_json_schema()
        payload = _build_vision_chat_payload(
            image_payload=image_payload,
            source_region=source_region,
            schema=schema,
            settings=self.settings,
        )
        response_data = await self.client.post_chat(payload)
        content = extract_ollama_message_content(response_data)
        result = _parse_vision_candidate_result(content)
        return OCRResult(
            text=_candidate_text(result),
            provider=OLLAMA_VISION_ASSIST_PROVIDER,
            confidence=None,
        )

    async def verify_text(
        self,
        image: OCRImageInput,
        text: str,
    ) -> OllamaVisionTextVerificationResult:
        """Verify OCR text against visible image text with local Ollama vision.

        Args:
            image: Validated image input. If ``label_region`` is present, only that
                crop is sent to the local vision model.
            text: OCR text selected for parsing. It is sent only to local Ollama and
                is not persisted by this adapter.

        Returns:
            Schema-validated verification result.

        Raises:
            OllamaConfigurationError: If the feature flag or local model is invalid.
            OllamaClientError: If the local Ollama API call fails.
            OllamaStructuredOutputError: If model output fails schema validation.
        """
        _validate_vision_settings(self.settings)
        image_payload, source_region = _build_image_payload(image)
        schema = OllamaVisionTextVerificationResult.model_json_schema()
        payload = _build_vision_verification_payload(
            image_payload=image_payload,
            source_region=source_region,
            ocr_text=text,
            schema=schema,
            settings=self.settings,
        )
        response_data = await self.client.post_chat(payload)
        content = extract_ollama_message_content(response_data)
        return _parse_vision_verification_result(content)

    async def extract_structured(
        self,
        image: OCRImageInput,
        allowed_categories: list[str],
    ) -> OllamaVisionStructuredExtractionResult:
        """Transcribe ingredient amounts and a category key from a label image.

        This is a transcription-only pass: it reads only values visibly printed on
        the image and returns them as structured JSON so the caller can additively
        fill ingredient amounts the OCR text never carried and set a category key
        from the supplied allow-list. It never infers hidden values or adds advice.

        Args:
            image: Validated image input. If ``label_region`` is present, only that
                crop is sent to the local vision model.
            allowed_categories: Closed allow-list of category keys the model may
                choose ``product_category_key`` from.

        Returns:
            Schema-validated structured extraction result.

        Raises:
            OllamaConfigurationError: If the feature flag or local model is invalid.
            OllamaClientError: If the local Ollama API call fails.
            OllamaStructuredOutputError: If model output fails schema validation.
        """
        _validate_vision_settings(self.settings)
        image_payload, source_region = _build_image_payload(image)
        schema = OllamaVisionStructuredExtractionResult.model_json_schema()
        payload = _build_vision_extraction_payload(
            image_payload=image_payload,
            source_region=source_region,
            allowed_categories=allowed_categories,
            schema=schema,
            settings=self.settings,
        )
        response_data = await self.client.post_chat(payload)
        content = extract_ollama_message_content(response_data)
        return _parse_vision_extraction_result(content)


async def check_ollama_vision_readiness(
    settings: Settings,
    client: OllamaChatClient | None = None,
    *,
    probe_image_input: bool = False,
) -> OllamaReadiness:
    """Check whether the configured local Ollama vision model is available.

    Args:
        settings: Runtime settings.
        client: Optional Ollama transport, primarily for tests.
        probe_image_input: Whether to send a tiny local image payload through
            ``POST /api/chat`` to verify actual vision-input support.

    Returns:
        Sanitized readiness status for the configured vision model.
    """
    model = settings.ollama_vision_model or ""
    try:
        validate_local_ollama_settings(settings)
        if not model:
            raise OllamaConfigurationError("OLLAMA_VISION_MODEL is required.")
    except OllamaConfigurationError:
        return OllamaReadiness(
            base_url=settings.ollama_base_url,
            model=model,
            ready=False,
            model_present=False,
            error_code="configuration_invalid",
        )

    active_client = client or OllamaChatClient(settings)
    try:
        response_data = await active_client.list_models()
        model_names = extract_ollama_model_names(response_data)
    except OllamaClientError:
        return OllamaReadiness(
            base_url=settings.ollama_base_url,
            model=model,
            ready=False,
            model_present=False,
            error_code="ollama_unavailable",
        )

    model_present = model in model_names
    if not model_present:
        return OllamaReadiness(
            base_url=settings.ollama_base_url,
            model=model,
            ready=False,
            model_present=False,
            model_names=model_names,
            error_code="model_missing",
        )
    if probe_image_input:
        try:
            await _probe_ollama_vision_image_input(settings, active_client)
        except (OllamaClientError, OllamaStructuredOutputError):
            return OllamaReadiness(
                base_url=settings.ollama_base_url,
                model=model,
                ready=False,
                model_present=True,
                model_names=model_names,
                error_code="vision_probe_failed",
            )
    return OllamaReadiness(
        base_url=settings.ollama_base_url,
        model=model,
        ready=True,
        model_present=True,
        model_names=model_names,
        error_code=None,
    )


async def _probe_ollama_vision_image_input(
    settings: Settings,
    client: OllamaChatClient,
) -> None:
    """Verify that the configured local model accepts an image payload.

    Args:
        settings: Runtime settings with local Ollama model configuration.
        client: Ollama transport used for the probe request.

    Raises:
        OllamaClientError: If the local ``POST /api/chat`` probe fails.
        OllamaStructuredOutputError: If the model response cannot be validated.
    """
    schema = OllamaVisionReadinessProbeResult.model_json_schema()
    payload = {
        "model": settings.ollama_vision_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a local readiness smoke test. Return only JSON matching "
                    "the supplied schema. Do not provide advice."
                ),
            },
            {
                "role": "user",
                "content": (
                    "This is a one-pixel test image with no visible text. "
                    "Return vision_input_supported=true and visible_text_present=false "
                    "only if the image payload was accepted.\n\n"
                    "Return JSON that conforms to this JSON Schema:\n"
                    f"{json.dumps(schema, ensure_ascii=False)}"
                ),
                "images": [VISION_READINESS_PROBE_IMAGE_BASE64],
            },
        ],
        "stream": False,
        "think": False,
        "format": schema,
        "keep_alive": settings.ollama_keep_alive_sec,
        "options": {"temperature": settings.ollama_vision_temperature},
    }
    response_data = await client.post_chat(payload)
    content = extract_ollama_message_content(response_data)
    result = _parse_vision_readiness_probe_result(content)
    if not result.vision_input_supported or result.visible_text_present:
        raise OllamaStructuredOutputError("Ollama vision probe returned an unsupported result.")


def _validate_vision_settings(settings: Settings) -> None:
    """Validate local-only settings before sending image bytes to Ollama.

    Args:
        settings: Runtime settings.

    Raises:
        OllamaConfigurationError: If the feature is disabled or not local-only.
    """
    if not settings.enable_multimodal_llm:
        raise OllamaConfigurationError("ENABLE_MULTIMODAL_LLM=false blocks vision assist.")
    if not settings.ollama_vision_model:
        raise OllamaConfigurationError("OLLAMA_VISION_MODEL is required for vision assist.")
    validate_local_ollama_settings(settings)


def _build_image_payload(image: OCRImageInput) -> tuple[str, Literal["full_image", "yolo_roi"]]:
    """Build a base64 image payload without persisting raw image bytes.

    Args:
        image: Validated image input.

    Returns:
        Base64 image payload and source-region marker.

    Raises:
        OllamaClientError: If a requested ROI crop cannot be produced.
    """
    if image.label_region is None:
        return base64.b64encode(image.image_bytes).decode("ascii"), "full_image"
    try:
        cropped = crop_image_to_bounding_box(image.image_bytes, image.label_region)
    except VisionPreprocessingError as exc:
        raise OllamaClientError("Vision assist ROI crop failed.") from exc
    return base64.b64encode(cropped).decode("ascii"), "yolo_roi"


def _build_vision_chat_payload(
    *,
    image_payload: str,
    source_region: Literal["full_image", "yolo_roi"],
    schema: dict[str, object],
    settings: Settings,
) -> dict[str, object]:
    """Build an Ollama Chat API payload for visible-text candidate extraction.

    Args:
        image_payload: Base64-encoded image bytes.
        source_region: Source marker for the submitted image.
        schema: JSON Schema for structured output.
        settings: Runtime settings.

    Returns:
        JSON payload for ``POST /api/chat``.
    """
    user_prompt = (
        "Extract only text that is visibly present on this supplement image. "
        f"The submitted image source is {source_region}. "
        "Do not infer hidden ingredients, amounts, dosage, benefits, risks, or advice. "
        "Use null or empty arrays for unknown values.\n\n"
        "Return JSON that conforms to this JSON Schema:\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )
    return {
        "model": settings.ollama_vision_model,
        "messages": [
            {"role": "system", "content": OLLAMA_VISION_ASSIST_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt, "images": [image_payload]},
        ],
        "stream": False,
        "think": False,
        "format": schema,
        "keep_alive": settings.ollama_keep_alive_sec,
        "options": {"temperature": settings.ollama_vision_temperature},
    }


def _build_vision_verification_payload(
    *,
    image_payload: str,
    source_region: Literal["full_image", "yolo_roi"],
    ocr_text: str,
    schema: dict[str, object],
    settings: Settings,
) -> dict[str, object]:
    """Build an Ollama Chat API payload for OCR text verification.

    Args:
        image_payload: Base64-encoded image bytes.
        source_region: Source marker for the submitted image.
        ocr_text: OCR text selected by the backend pipeline.
        schema: JSON Schema for structured output.
        settings: Runtime settings.

    Returns:
        JSON payload for ``POST /api/chat``.
    """
    bounded_text = ocr_text.strip()[:MAX_VERIFICATION_OCR_TEXT_CHARS]
    user_prompt = (
        "Verify whether the OCR text below is visibly supported by this supplement image. "
        f"The submitted image source is {source_region}. "
        "Classify the result as match, partial, mismatch, or uncertain. "
        "Report missing critical sections only from this allowed set: "
        "product_name, supplement_facts, intake_method, precautions. "
        "Do not add advice or outside facts.\n\n"
        "OCR text to verify:\n"
        f"{bounded_text}\n\n"
        "Return JSON that conforms to this JSON Schema:\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )
    return {
        "model": settings.ollama_vision_model,
        "messages": [
            {"role": "system", "content": OLLAMA_VISION_VERIFY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt, "images": [image_payload]},
        ],
        "stream": False,
        "think": False,
        "format": schema,
        "keep_alive": settings.ollama_keep_alive_sec,
        "options": {"temperature": settings.ollama_vision_temperature},
    }


def _build_vision_extraction_payload(
    *,
    image_payload: str,
    source_region: Literal["full_image", "yolo_roi"],
    allowed_categories: list[str],
    schema: dict[str, object],
    settings: Settings,
) -> dict[str, object]:
    """Build an Ollama Chat API payload for transcription-only label extraction.

    Args:
        image_payload: Base64-encoded image bytes.
        source_region: Source marker for the submitted image.
        allowed_categories: Closed allow-list of category keys the model may use.
        schema: JSON Schema for structured output.
        settings: Runtime settings.

    Returns:
        JSON payload for ``POST /api/chat``.
    """
    bounded_categories = [
        category.strip()
        for category in allowed_categories[:MAX_VISION_EXTRACTION_CATEGORIES]
        if category and category.strip()
    ]
    user_prompt = (
        "Transcribe only values visibly printed on this supplement image. "
        f"The submitted image source is {source_region}. "
        "For each ingredient in the supplement facts or ingredient table, transcribe "
        "its printed name, amount, and unit; use null when an amount or unit is not "
        "visibly printed. Do not infer hidden values, dosage, benefits, risks, or advice.\n\n"
        "Choose product_category_key only from this allowed list (or null if none "
        "clearly applies):\n"
        f"{json.dumps(bounded_categories, ensure_ascii=False)}\n\n"
        "Return JSON that conforms to this JSON Schema:\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )
    return {
        "model": settings.ollama_vision_model,
        "messages": [
            {"role": "system", "content": OLLAMA_VISION_EXTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt, "images": [image_payload]},
        ],
        "stream": False,
        "think": False,
        "format": schema,
        "keep_alive": settings.ollama_keep_alive_sec,
        "options": {"temperature": settings.ollama_vision_temperature},
    }


def _vision_json_candidates(content: str) -> list[str]:
    """Return JSON-object candidates from raw model content.

    Local vision models sometimes wrap structured output in markdown code fences
    or add prose around the JSON object. This mirrors the text parser's tolerance
    so a fenced/padded response is not rejected outright.

    Args:
        content: Raw assistant message content.

    Returns:
        Ordered, de-duplicated candidate strings to attempt JSON validation on.
    """
    candidates: list[str] = []
    raw = content.strip()
    if raw:
        candidates.append(raw)
    fenced = raw
    if fenced.startswith("```"):
        fenced = re.sub(r"^```[A-Za-z0-9]*\s*", "", fenced)
        fenced = re.sub(r"\s*```$", "", fenced).strip()
        if fenced and fenced not in candidates:
            candidates.append(fenced)
    start = fenced.find("{")
    end = fenced.rfind("}")
    if start != -1 and end != -1 and end > start:
        substring = fenced[start : end + 1].strip()
        if substring and substring not in candidates:
            candidates.append(substring)
    return candidates


def _parse_vision_candidate_result(content: str) -> OllamaVisionTextCandidateResult:
    """Validate vision-assist output, tolerating markdown fences and prose.

    Args:
        content: Raw assistant message content.

    Returns:
        Schema-validated vision candidate result.

    Raises:
        OllamaStructuredOutputError: If no candidate passes schema validation.
    """
    candidates = _vision_json_candidates(content)
    if not candidates:
        raise OllamaStructuredOutputError("Ollama vision assist returned empty content.")
    last_error: ValidationError | None = None
    for candidate in candidates:
        try:
            return OllamaVisionTextCandidateResult.model_validate_json(candidate)
        except ValidationError as exc:
            last_error = exc
    raise OllamaStructuredOutputError(
        "Ollama vision assist output failed schema validation."
    ) from last_error


def _parse_vision_verification_result(content: str) -> OllamaVisionTextVerificationResult:
    """Validate vision verification output, tolerating markdown fences and prose.

    Args:
        content: Raw assistant message content.

    Returns:
        Schema-validated vision verification result.

    Raises:
        OllamaStructuredOutputError: If no candidate passes schema validation.
    """
    candidates = _vision_json_candidates(content)
    if not candidates:
        raise OllamaStructuredOutputError("Ollama vision verification returned empty content.")
    last_error: ValidationError | None = None
    for candidate in candidates:
        try:
            return OllamaVisionTextVerificationResult.model_validate_json(candidate)
        except ValidationError as exc:
            last_error = exc
    raise OllamaStructuredOutputError(
        "Ollama vision verification output failed schema validation."
    ) from last_error


def _parse_vision_extraction_result(content: str) -> OllamaVisionStructuredExtractionResult:
    """Validate structured extraction output, tolerating markdown fences and prose.

    Args:
        content: Raw assistant message content.

    Returns:
        Schema-validated structured extraction result.

    Raises:
        OllamaStructuredOutputError: If no candidate passes schema validation.
    """
    candidates = _vision_json_candidates(content)
    if not candidates:
        raise OllamaStructuredOutputError("Ollama vision extraction returned empty content.")
    last_error: ValidationError | None = None
    for candidate in candidates:
        try:
            return OllamaVisionStructuredExtractionResult.model_validate_json(candidate)
        except ValidationError as exc:
            last_error = exc
    raise OllamaStructuredOutputError(
        "Ollama vision extraction output failed schema validation."
    ) from last_error


def _parse_vision_readiness_probe_result(content: str) -> OllamaVisionReadinessProbeResult:
    """Validate the readiness image-probe response.

    Args:
        content: Raw assistant message content.

    Returns:
        Schema-validated image-probe result.

    Raises:
        OllamaStructuredOutputError: If no candidate passes schema validation.
    """
    candidates = _vision_json_candidates(content)
    if not candidates:
        raise OllamaStructuredOutputError("Ollama vision probe returned empty content.")
    last_error: ValidationError | None = None
    for candidate in candidates:
        try:
            return OllamaVisionReadinessProbeResult.model_validate_json(candidate)
        except ValidationError as exc:
            last_error = exc
    raise OllamaStructuredOutputError(
        "Ollama vision probe output failed schema validation."
    ) from last_error


def _candidate_text(result: OllamaVisionTextCandidateResult) -> str:
    """Convert visible-text candidates into parser input text.

    Args:
        result: Schema-validated vision assist result.

    Returns:
        Newline-delimited candidate text. The text remains a preview input and is
        never persisted raw by downstream parser storage.
    """
    fragments = list(result.visible_text_fragments)
    if result.possible_product_name and result.possible_product_name not in fragments:
        fragments.insert(0, result.possible_product_name)
    return "\n".join(fragments).strip()
