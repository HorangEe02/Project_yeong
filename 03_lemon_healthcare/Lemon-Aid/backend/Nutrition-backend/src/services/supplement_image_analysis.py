"""Supplement image analysis orchestration service.

This service keeps the existing intake flow intact while creating a stable place
to plug in OCR, vision ROI detection, and future learning pipelines. Default
runtime behavior remains intake-only unless adapters are explicitly provided.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Awaitable
from dataclasses import dataclass
from decimal import Decimal
from difflib import SequenceMatcher
from http import HTTPStatus
from random import random
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config import Settings
from src.db.session import get_learning_sessionmaker
from src.db.tx import persist_scope
from src.learning.consent_gate import evaluate_image_learning_gate
from src.learning.object_storage import LearningImageObjectStore
from src.learning.pipeline import (
    enqueue_learning_embedding_job_for_confirmation,
    maybe_store_learning_image_object,
)
from src.learning.supplement_section_labels import (
    SUPPLEMENT_SECTION_ANNOTATION_REVIEW_NOTES_CODE,
    SUPPLEMENT_SECTION_ANNOTATION_TASK_TYPE,
    SupplementSectionLabelCandidateError,
    build_supplement_section_annotation_task,
    page_dimensions_from_ocr_result,
)
from src.llm.ollama import (
    OllamaClientError,
    OllamaConfigurationError,
    OllamaStructuredOutputError,
)
from src.llm.ollama_vision import (
    OllamaVisionAssistAdapter,
    OllamaVisionIngredient,
    OllamaVisionStructuredExtractionResult,
    OllamaVisionTextVerificationResult,
)
from src.models.db.learning import LearningImageObject
from src.models.db.retraining import AnnotationTask
from src.models.db.supplement import SupplementAnalysisRun
from src.models.schemas.image_quality import ImageQualityReport
from src.models.schemas.privacy import ConsentType
from src.models.schemas.supplement_image import (
    SupplementImagePipelineMetadata,
    bucket_ocr_confidence,
    count_snapshot_list,
    infer_missing_required_sections,
    parser_contract_version,
    safe_snapshot_string,
)
from src.ocr.base import OCRAdapter, OCRError, OCRImageInput, OCRPage, OCRResult
from src.parsing.layout_parser import parse_label_layout
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject
from src.services.nutrient_category_map import allowed_supplement_category_keys
from src.services.supplement_intake import (
    SupplementImageValidationError,
    SupplementIntakeStoreResult,
    ValidatedSupplementImage,
    create_supplement_analysis_intake,
    read_and_validate_supplement_image,
)
from src.services.supplement_parser import (
    OCR_LOW_CONFIDENCE_THRESHOLD,
    SupplementOCRTextParser,
    SupplementParserInputError,
    parse_supplement_analysis_ocr_text,
)
from src.services.supplement_span_grounding import is_amount_grounded
from src.utils.image_safety import ImageSafetyError, safe_load_with_bomb_guard, strip_image_metadata
from src.vision.base import BoundingBox, VisionAdapter, VisionError
from src.vision.preprocessing import (
    VisionPreprocessingError,
    crop_image_to_bounding_box,
    expand_bounding_box,
    select_best_label_region,
)
from src.vision.taxonomy import label_priority

logger = logging.getLogger(__name__)

AUTOMATIC_OCR_UNAVAILABLE_WARNING = (
    "Automatic text extraction is unavailable. Continue by entering label details manually."
)
OCR_TEXT_EMPTY_WARNING = (
    "No readable label text was extracted. Continue by entering label details manually."
)
OCR_PARSE_PREVIEW_UNAVAILABLE_WARNING = (
    "Automatic text parsing is unavailable. Continue by reviewing or entering details manually."
)
OCR_ROI_CROP_UNAVAILABLE_WARNING = (
    "Label-region crop was unavailable. Automatic text extraction used the full image."
)
OCR_VERIFICATION_MISMATCH_WARNING = (
    "Automatic text verification found a mismatch. Review the extracted label details manually."
)
SUPPLEMENT_FACTS_REQUIRED_WARNING = "supplement_facts_required"
SUPPLEMENT_FACTS_RETAKE_MESSAGE = (
    "제품명은 확인했지만 성분표가 보이지 않아요. 성분표를 다시 찍어주세요."
)
AUTOMATIC_OCR_UNAVAILABLE_CODE = "automatic_ocr_unavailable"
OCR_TEXT_EMPTY_CODE = "ocr_text_empty"
OCR_PARSE_PREVIEW_UNAVAILABLE_CODE = "ocr_parse_preview_unavailable"
OCR_ROI_CROP_UNAVAILABLE_CODE = "ocr_roi_crop_unavailable"
OCR_VERIFICATION_MISMATCH_CODE = "ocr_verification_mismatch"
SUPPLEMENT_FACTS_REQUIRED_CODE = "supplement_facts_required"
SUPPLEMENT_FACTS_SECTION_TYPES = frozenset({"supplement_facts", "ingredients", "nutrition_info"})
MAX_PRIMARY_OCR_ROI_CANDIDATES = 4
PARSER_RECOVERABLE_ERRORS = (
    SupplementParserInputError,
    OllamaClientError,
    OllamaConfigurationError,
    OllamaStructuredOutputError,
)


async def _within_optional_budget[T](
    awaitable: Awaitable[T],
    *,
    budget_sec: float,
    fallback: T,
    label: str,
) -> T:
    """Run an *optional* OCR-enrichment stage under a hard per-stage time budget.

    The optional/warn-only enrichment stages (cross-provider ensemble merge,
    multimodal vision OCR assist, multimodal verification) call OCR/vision
    inference that can be slow on CPU hosts — a single local vision call can take
    tens of seconds. They already degrade gracefully on *error*; this also
    degrades on *slowness* so no single optional stage can push the synchronous
    analyze response past the mobile upload timeout. On timeout the awaited stage
    is cancelled and the caller-supplied fallback (primary result / no-warning) is
    returned. Load-bearing stages (primary OCR, parser) are never wrapped here.

    Args:
        awaitable: The optional stage coroutine to run.
        budget_sec: Maximum seconds the stage may block the request.
        fallback: Value to return if the stage exceeds the budget.
        label: Stage name for diagnostic logging.

    Returns:
        The stage result, or ``fallback`` on timeout.
    """
    try:
        return await asyncio.wait_for(awaitable, timeout=budget_sec)
    except TimeoutError:
        logger.warning(
            "Optional analyze stage '%s' exceeded its %ss budget; using primary result.",
            label,
            budget_sec,
        )
        return fallback


class SupplementImageAnalysisConfigurationError(RuntimeError):
    """Raised when a feature flag is enabled without the required adapter."""


@runtime_checkable
class _MultimodalTextVerifier(Protocol):
    """Optional protocol for local vision models that verify OCR text directly."""

    async def verify_text(
        self,
        image: OCRImageInput,
        text: str,
    ) -> OllamaVisionTextVerificationResult:
        """Verify OCR text against visible image text."""
        ...


@dataclass(frozen=True)
class SupplementImageAnalysisAdapters:
    """Optional adapters used by the image analysis pipeline.

    Attributes:
        ocr: OCR adapter. When absent, the pipeline remains intake-only.
        parser: Structured OCR text parser, primarily injected by tests.
        vision: Label-region detector. Used only when ``enable_vision_classifier`` is true.
        multimodal_ocr: Local vision LLM assist adapter used only as OCR fallback.
        secondary_merge_ocr: Optional secondary OCR adapter line-union merged into
            the primary result (ensemble supplement), distinct from the fallback chain.
        fallback_ocr_adapters: Optional secondary OCR fallback adapters.
    """

    ocr: OCRAdapter | None = None
    parser: SupplementOCRTextParser | None = None
    vision: VisionAdapter | None = None
    multimodal_ocr: OCRAdapter | None = None
    secondary_merge_ocr: OCRAdapter | None = None
    fallback_ocr_adapters: tuple[OCRAdapter, ...] = ()


@dataclass(frozen=True)
class SupplementLearningArtifactsInput:
    """Deferred inputs for post-commit learning image storage + annotation enqueue.

    The orchestrator no longer writes learning rows inside the request
    transaction (a mid-request ``commit`` would drop the FORCE-RLS GUCs, and the
    learning store needs the analysis row to be durable for its foreign key).
    Instead, when the image-learning gate passes, it bundles these inputs so the
    route can hand them to :func:`store_supplement_learning_artifacts` as a
    post-commit background task running on a fresh session.

    Attributes:
        analysis_id: Durable supplement analysis run id the learning object links to.
        image_bytes: Validated image bytes retained only for the consented store.
        image_metadata: Validated image metadata (sha256/mime/size).
        ocr_result: OCR output used to derive sanitized section annotation candidates.
        learning_consents: Active learning consent grants used by the gate + snapshot.
    """

    analysis_id: UUID
    image_bytes: bytes
    image_metadata: ValidatedSupplementImage
    ocr_result: OCRResult | None
    learning_consents: tuple[ConsentType, ...]


@dataclass(frozen=True)
class SupplementLearningEmbeddingInput:
    """Deferred inputs for post-commit supplement learning embedding enqueue.

    After a user confirms a supplement, the embedding-job enqueue
    (:func:`enqueue_learning_embedding_job_for_confirmation`, which commits and
    reads FORCE-RLS learning tables) must run post-commit on the privileged
    learning engine, not inside the request transaction. The route bundles these
    inputs and hands them to :func:`store_supplement_learning_embedding_job`.

    Attributes:
        analysis_id: Source supplement analysis run id (embedding job FK).
        metadata_snapshot: User-confirmed structured metadata for the job.
        learning_consents: Active learning consent grants used by the gate.
    """

    analysis_id: UUID | None
    metadata_snapshot: dict[str, Any]
    learning_consents: tuple[ConsentType, ...]


@dataclass(frozen=True)
class SupplementImageAnalysisResult:
    """Result returned by the image analysis orchestration service.

    Attributes:
        record: Persisted supplement analysis preview.
        reused_existing: Whether idempotency returned an existing preview.
        image_metadata: Validated image metadata.
        vision_region: Optional label-region ROI used by OCR.
        vision_regions: Bounded candidate regions returned by the vision adapter.
        image_quality_report: Optional deterministic image-quality report.
        ocr_result: Optional OCR output used by the parser.
        parser_used: Whether structured OCR text parsing was invoked.
        ocr_attempted: Whether a primary OCR adapter was configured and called.
        ocr_warning_codes: Recoverable OCR/parser warning codes added to the preview.
        learning_artifacts: Deferred post-commit learning inputs when the image
            learning gate passed; ``None`` when learning is not eligible. The
            orchestrator does not itself persist learning rows — the route
            schedules :func:`store_supplement_learning_artifacts` post-commit.
            Used by the single-image and per-image (distinct) paths.
        learning_artifacts_per_image: Deferred post-commit learning inputs, one
            per physical image, used only by the one-shot fusion path
            (:func:`analyze_fused_supplement_images`). The fused parse yields a
            single preview, but the section-detector training dataset needs each
            image with its own layout-bearing OCR result (the fused ``OCRResult``
            drops per-image layout), so each image is bundled separately. Empty
            for the single-image and distinct paths (which use
            ``learning_artifacts``). The route schedules one
            :func:`store_supplement_learning_artifacts` task per entry.
    """

    record: SupplementAnalysisRun
    reused_existing: bool
    image_metadata: ValidatedSupplementImage
    vision_region: BoundingBox | None
    vision_regions: tuple[BoundingBox, ...]
    image_quality_report: ImageQualityReport | None
    ocr_result: OCRResult | None
    parser_used: bool
    ocr_attempted: bool
    ocr_warning_codes: tuple[str, ...]
    learning_artifacts: SupplementLearningArtifactsInput | None
    learning_artifacts_per_image: tuple[SupplementLearningArtifactsInput, ...] = ()


@dataclass(frozen=True)
class _OCRExtractionResult:
    """Internal OCR extraction result with recoverable warning metadata."""

    ocr_result: OCRResult | None
    warning_code: str | None = None
    warning_message: str | None = None


@dataclass(frozen=True)
class _SupplementFactsGuidance:
    """Internal retake guidance for previews missing ingredient evidence."""

    image_quality_report: ImageQualityReport
    missing_required_sections: tuple[str, ...]
    image_role: str
    analysis_scope: str
    action_required: str


@dataclass(frozen=True)
class _VisionExtractionOutcome:
    """Diagnostic outcome of the additive local vision transcription merge.

    Attributes:
        attempted: Whether the local Gemma vision transcription pass was attempted.
        category_applied: Whether the pass set an otherwise-unset category key.
        amounts_filled: Number of ingredient candidates whose null amount was filled.
    """

    attempted: bool = False
    category_applied: bool = False
    amounts_filled: int = 0


# Empty (not-attempted) vision-merge outcome used when the gate is closed or the
# pass is skipped, so the pipeline-metadata flags default to a clean no-op state.
_VISION_EXTRACTION_SKIPPED = _VisionExtractionOutcome()


async def analyze_supplement_image(
    session: AsyncSession,
    user: AuthenticatedUser,
    image: UploadFile,
    client_request_id: str | None,
    settings: Settings,
    adapters: SupplementImageAnalysisAdapters | None = None,
    learning_consents: tuple[ConsentType, ...] = (),
) -> SupplementImageAnalysisResult:
    """Validate, persist, and optionally OCR/parse a supplement label image.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        image: Uploaded supplement label image.
        client_request_id: Optional client idempotency key.
        settings: Runtime settings.
        adapters: Optional OCR/parser/vision adapters. Missing adapters keep the flow
            intake-only unless a corresponding feature flag requires one.
        learning_consents: Active learning consent grants. Used to evaluate the
            image-learning gate and, when it passes, bundle deferred inputs
            (``learning_artifacts``) for the route's post-commit background task.

    Returns:
        Image analysis result with the current preview record. Learning image
        storage is not performed here; eligible inputs are returned via
        ``learning_artifacts`` for :func:`store_supplement_learning_artifacts`.

    Raises:
        SupplementImageAnalysisConfigurationError: If vision is enabled without an adapter.
        SupplementImageValidationError: If image validation fails.
        SupplementIntakeConflictError: If idempotency conflicts.
        SupplementParserInputError: If manual parser validation fails outside recoverable OCR flow.
    """
    active_adapters = adapters or SupplementImageAnalysisAdapters()
    image_metadata = await read_and_validate_supplement_image(image, settings)
    intake = await create_supplement_analysis_intake(
        session=session,
        user=user,
        image_metadata=image_metadata,
        client_request_id=client_request_id,
        settings=settings,
    )

    learning_gate_allowed = evaluate_image_learning_gate(settings, learning_consents).allowed
    image_bytes = await _read_validated_image_bytes_if_needed(
        image,
        active_adapters=active_adapters,
        settings=settings,
        needs_learning_image_bytes=learning_gate_allowed,
        image_metadata=image_metadata,
    )
    vision_regions = await _detect_label_regions_if_enabled(
        image_bytes=image_bytes,
        settings=settings,
        vision_adapter=active_adapters.vision,
    )
    vision_region = _select_vision_region(vision_regions)
    ocr_attempted = active_adapters.ocr is not None
    ocr_extraction = await _extract_ocr_if_configured(
        image_bytes=image_bytes,
        image_metadata=image_metadata,
        label_regions=vision_regions,
        selected_region=vision_region,
        ocr_adapter=active_adapters.ocr,
        settings=settings,
    )
    ocr_result = ocr_extraction.ocr_result
    optional_budget = settings.analyze_optional_stage_budget_sec
    # The ensemble secondary OCR (local Paddle) now runs off the event loop in a
    # dedicated single-worker thread (PaddleOCRAdapter offloads its synchronous,
    # CPU-bound predict()), so it no longer stalls the loop. It is intentionally
    # NOT wrapped in the optional-stage budget: it is load-bearing (supplements the
    # primary OCR text) and abandoning it would drop useful recognition. The budget
    # is applied only to the genuinely-optional vision-inference stages below
    # (multimodal assist + verification), where the request-blowing local vision
    # LLM spikes (tens of seconds) occur.
    ocr_result = await _supplement_ensemble_ocr_if_allowed(
        image_bytes=image_bytes,
        image_metadata=image_metadata,
        label_region=vision_region,
        ocr_result=ocr_result,
        secondary_merge_adapter=active_adapters.secondary_merge_ocr,
        settings=settings,
    )
    ocr_result = await _within_optional_budget(
        _extract_multimodal_ocr_if_allowed(
            image_bytes=image_bytes,
            image_metadata=image_metadata,
            label_region=vision_region,
            ocr_result=ocr_result,
            primary_ocr_attempted=active_adapters.ocr is not None,
            settings=settings,
            multimodal_adapter=active_adapters.multimodal_ocr,
        ),
        budget_sec=optional_budget,
        fallback=ocr_result,
        label="multimodal_assist",
    )
    ocr_result = await _extract_secondary_ocr_if_allowed(
        image_bytes=image_bytes,
        image_metadata=image_metadata,
        label_region=vision_region,
        ocr_result=ocr_result,
        primary_ocr_attempted=active_adapters.ocr is not None,
        fallback_adapters=active_adapters.fallback_ocr_adapters,
    )
    verification_warning_code, verification_warning_message = await _within_optional_budget(
        _verify_ocr_with_multimodal_if_allowed(
            image_bytes=image_bytes,
            image_metadata=image_metadata,
            label_region=vision_region,
            ocr_result=ocr_result,
            settings=settings,
            multimodal_adapter=active_adapters.multimodal_ocr,
        ),
        budget_sec=optional_budget,
        fallback=(None, None),
        label="multimodal_verification",
    )
    parsed_record, parse_warning_code, parse_warning_message = await _parse_ocr_if_available(
        session=session,
        user=user,
        intake=intake,
        ocr_result=ocr_result,
        settings=settings,
        parser=active_adapters.parser,
    )
    warning_pairs = [
        (ocr_extraction.warning_code, ocr_extraction.warning_message),
        (verification_warning_code, verification_warning_message),
        (parse_warning_code, parse_warning_message),
    ]
    warning_codes = tuple(code for code, message in warning_pairs if code and message)
    warning_messages = [message for code, message in warning_pairs if code and message]
    if warning_messages:
        await _store_preview_warnings(session, parsed_record or intake.record, warning_messages)

    result_record = parsed_record or intake.record
    facts_guidance = _build_supplement_facts_guidance(
        record=result_record,
        ocr_result=ocr_result,
        parser_used=parsed_record is not None,
    )
    if facts_guidance is not None:
        warning_codes = (*warning_codes, SUPPLEMENT_FACTS_REQUIRED_CODE)
        result_record = await _store_supplement_facts_guidance(
            session,
            result_record,
            facts_guidance,
        )
    result_record, vision_outcome = await _within_optional_budget(
        _merge_vision_structured_extraction_if_allowed(
            session=session,
            record=result_record,
            image_bytes=image_bytes,
            image_metadata=image_metadata,
            label_region=vision_region,
            ocr_text=ocr_result.text if ocr_result else "",
            parser_used=parsed_record is not None,
            settings=settings,
        ),
        budget_sec=optional_budget,
        fallback=(result_record, _VISION_EXTRACTION_SKIPPED),
        label="vision_structured_extraction",
    )
    pipeline_metadata = _build_pipeline_metadata(
        record=result_record,
        vision_region=vision_region,
        vision_regions=vision_regions,
        ocr_result=ocr_result,
        ocr_attempted=ocr_attempted,
        warning_codes=warning_codes,
        parser_used=parsed_record is not None,
        settings=settings,
        vision_outcome=vision_outcome,
    )
    if _should_store_pipeline_metadata(result_record, pipeline_metadata, vision_regions):
        result_record = await _store_pipeline_metadata(
            session,
            result_record,
            pipeline_metadata,
            vision_regions=vision_regions,
            selected_region=vision_region,
            image_metadata=image_metadata,
        )

    learning_artifacts = (
        SupplementLearningArtifactsInput(
            analysis_id=result_record.id,
            image_bytes=image_bytes,
            image_metadata=image_metadata,
            ocr_result=ocr_result,
            learning_consents=learning_consents,
        )
        if learning_gate_allowed and image_bytes is not None
        else None
    )

    return SupplementImageAnalysisResult(
        record=result_record,
        reused_existing=intake.reused_existing,
        image_metadata=image_metadata,
        vision_region=vision_region,
        vision_regions=vision_regions,
        image_quality_report=(
            facts_guidance.image_quality_report if facts_guidance is not None else None
        ),
        ocr_result=ocr_result,
        parser_used=parsed_record is not None,
        ocr_attempted=ocr_attempted,
        ocr_warning_codes=warning_codes,
        learning_artifacts=learning_artifacts,
    )


@dataclass(frozen=True)
class SupplementOCROnlyResult:
    """OCR-phase output for one image, with no intake row and no structured parse.

    Used by the one-shot multi-image fusion path so several images can be OCR'd
    in-request and their texts fused before a single structured parse. No raw OCR
    text is persisted; only the in-memory ``ocr_result`` is returned.
    """

    image_metadata: ValidatedSupplementImage
    image_bytes: bytes | None
    vision_region: BoundingBox | None
    vision_regions: tuple[BoundingBox, ...]
    ocr_result: OCRResult | None
    ocr_attempted: bool
    ocr_warning_codes: tuple[str, ...]
    learning_gate_allowed: bool


async def extract_supplement_ocr_only(
    image: UploadFile,
    *,
    settings: Settings,
    adapters: SupplementImageAnalysisAdapters | None = None,
    learning_consents: tuple[ConsentType, ...] = (),
) -> SupplementOCROnlyResult:
    """Run the OCR phase for one image without creating an intake row or parsing.

    Re-uses the same OCR helpers as :func:`analyze_supplement_image` (validation,
    optional vision ROI, primary OCR, cross-provider ensemble, optional multimodal
    assist, secondary fallback) but performs no database write and no structured
    parse — the caller fuses several results and parses once. The optional
    warn-only multimodal *verification* stage is intentionally skipped here: it
    never changes the OCR text, only emits a per-image diagnostic warning.

    NOTE: keep the stage order here in sync with the OCR section of
    :func:`analyze_supplement_image`.
    """
    active_adapters = adapters or SupplementImageAnalysisAdapters()
    image_metadata = await read_and_validate_supplement_image(image, settings)
    learning_gate_allowed = evaluate_image_learning_gate(settings, learning_consents).allowed
    image_bytes = await _read_validated_image_bytes_if_needed(
        image,
        active_adapters=active_adapters,
        settings=settings,
        needs_learning_image_bytes=learning_gate_allowed,
        image_metadata=image_metadata,
    )
    vision_regions = await _detect_label_regions_if_enabled(
        image_bytes=image_bytes,
        settings=settings,
        vision_adapter=active_adapters.vision,
    )
    vision_region = _select_vision_region(vision_regions)
    ocr_attempted = active_adapters.ocr is not None
    ocr_extraction = await _extract_ocr_if_configured(
        image_bytes=image_bytes,
        image_metadata=image_metadata,
        label_regions=vision_regions,
        selected_region=vision_region,
        ocr_adapter=active_adapters.ocr,
        settings=settings,
    )
    ocr_result = ocr_extraction.ocr_result
    optional_budget = settings.analyze_optional_stage_budget_sec
    ocr_result = await _supplement_ensemble_ocr_if_allowed(
        image_bytes=image_bytes,
        image_metadata=image_metadata,
        label_region=vision_region,
        ocr_result=ocr_result,
        secondary_merge_adapter=active_adapters.secondary_merge_ocr,
        settings=settings,
    )
    ocr_result = await _within_optional_budget(
        _extract_multimodal_ocr_if_allowed(
            image_bytes=image_bytes,
            image_metadata=image_metadata,
            label_region=vision_region,
            ocr_result=ocr_result,
            primary_ocr_attempted=active_adapters.ocr is not None,
            settings=settings,
            multimodal_adapter=active_adapters.multimodal_ocr,
        ),
        budget_sec=optional_budget,
        fallback=ocr_result,
        label="multimodal_assist",
    )
    ocr_result = await _extract_secondary_ocr_if_allowed(
        image_bytes=image_bytes,
        image_metadata=image_metadata,
        label_region=vision_region,
        ocr_result=ocr_result,
        primary_ocr_attempted=active_adapters.ocr is not None,
        fallback_adapters=active_adapters.fallback_ocr_adapters,
    )
    warning_codes = tuple(
        code
        for code, message in ((ocr_extraction.warning_code, ocr_extraction.warning_message),)
        if code and message
    )
    return SupplementOCROnlyResult(
        image_metadata=image_metadata,
        image_bytes=image_bytes,
        vision_region=vision_region,
        vision_regions=vision_regions,
        ocr_result=ocr_result,
        ocr_attempted=ocr_attempted,
        ocr_warning_codes=warning_codes,
        learning_gate_allowed=learning_gate_allowed,
    )


# Defensive upper bound on fused content lines before the parser's own char-level
# truncation (``supplement_ocr_text_max_chars``) applies. A multi-image label is
# small; this only guards against pathological OCR output.
_MAX_FUSED_OCR_LINES = 1_000


def _fuse_supplement_ocr_texts(
    labeled_results: list[tuple[str, OCRResult | None]],
    settings: Settings,
) -> OCRResult | None:
    """Fuse per-image OCR text into one block for a single structured parse.

    Each non-empty image contributes an image-role marker line followed by its OCR
    lines; content lines are near-duplicate-deduplicated across images (so a line
    shared by overlapping photos appears once) while the role markers are kept to
    help the parser place sections. The composite provider records every
    contributing OCR provider; confidence anchors to the first non-null result.

    Args:
        labeled_results: ``(image_role, ocr_result)`` pairs in upload order.
        settings: Runtime settings (near-duplicate dedup threshold).

    Returns:
        A single fused ``OCRResult`` or ``None`` when no image produced text.
    """
    seen: set[str] = set()
    parts: list[str] = []
    providers: list[str] = []
    confidence: float | None = None
    threshold = settings.ocr_merge_dedup_threshold
    content_lines = 0
    for index, (role, result) in enumerate(labeled_results, start=1):
        if result is None or not result.text.strip():
            continue
        providers.append(result.provider)
        if confidence is None and result.confidence is not None:
            confidence = result.confidence
        kept: list[str] = []
        for line in _normalized_nonempty_lines(result.text):
            if content_lines >= _MAX_FUSED_OCR_LINES:
                break
            key = _line_dedup_key(line)
            if key in seen or _is_near_duplicate(key, seen, threshold):
                continue
            seen.add(key)
            kept.append(line)
            content_lines += 1
        if kept:
            safe_role = role.strip() or "unknown"
            parts.append(f"=== [이미지 {index} · {safe_role}] ===")
            parts.extend(kept)
        if content_lines >= _MAX_FUSED_OCR_LINES:
            break
    if not parts:
        return None
    unique_providers = list(dict.fromkeys(providers))
    return OCRResult(
        text="\n".join(parts),
        provider="+".join(unique_providers) if unique_providers else "fused",
        confidence=confidence,
    )


def _build_fused_image_metadata(
    metadatas: list[ValidatedSupplementImage],
) -> ValidatedSupplementImage:
    """Synthesize one image metadata for the single fused run.

    The sha256 is derived from the sorted set of per-image sha256s so the same
    image set in any order yields a stable idempotency anchor for the fused run.
    Size/width/height use the per-image maxima as a safe representative.

    Args:
        metadatas: Per-image validated metadata (must be non-empty).

    Returns:
        Synthetic validated metadata describing the fused batch.
    """
    ordered_hashes = sorted(meta.sha256 for meta in metadatas)
    fused_sha = hashlib.sha256("".join(ordered_hashes).encode("utf-8")).hexdigest()
    return ValidatedSupplementImage(
        sha256=fused_sha,
        mime_type=metadatas[0].mime_type,
        size_bytes=max(meta.size_bytes for meta in metadatas),
        width=max(meta.width for meta in metadatas),
        height=max(meta.height for meta in metadatas),
    )


async def analyze_fused_supplement_images(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    images: list[UploadFile],
    image_roles: list[str],
    client_request_id: str | None,
    settings: Settings,
    adapters: SupplementImageAnalysisAdapters | None = None,
    learning_consents: tuple[ConsentType, ...] = (),
) -> SupplementImageAnalysisResult:
    """OCR each image, fuse the text, and parse ONCE into a single analysis run.

    The one-shot fusion path for a single-product multi-image batch: every image
    is OCR'd in-memory (no per-image intake or parse), the texts are fused with
    image-role markers and near-duplicate line dedup, and the structured parser
    runs once over the fused text so the model reasons over the whole label. Raw
    OCR text is never persisted (only the parsed snapshot and an OCR text hash).

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        images: Uploaded label images for one product (must be non-empty).
        image_roles: Role labels aligned one-to-one with ``images``.
        client_request_id: Optional batch idempotency key.
        settings: Runtime settings.
        adapters: Optional OCR/parser/vision adapters.
        learning_consents: Active learning consent grants.

    Returns:
        Image analysis result holding the single fused preview record.
    """
    active_adapters = adapters or SupplementImageAnalysisAdapters()
    ocr_only_results = [
        await extract_supplement_ocr_only(
            image,
            settings=settings,
            adapters=active_adapters,
            learning_consents=learning_consents,
        )
        for image in images
    ]
    roles = list(image_roles)
    labeled = [
        (roles[index] if index < len(roles) else "unknown", result.ocr_result)
        for index, result in enumerate(ocr_only_results)
    ]
    fused_ocr_result = _fuse_supplement_ocr_texts(labeled, settings)
    fused_metadata = _build_fused_image_metadata(
        [result.image_metadata for result in ocr_only_results]
    )
    intake = await create_supplement_analysis_intake(
        session=session,
        user=user,
        image_metadata=fused_metadata,
        client_request_id=client_request_id,
        settings=settings,
    )
    parsed_record, parse_warning_code, parse_warning_message = await _parse_ocr_if_available(
        session=session,
        user=user,
        intake=intake,
        ocr_result=fused_ocr_result,
        settings=settings,
        parser=active_adapters.parser,
    )
    warning_codes_list: list[str] = []
    warning_messages: list[str] = []
    for result in ocr_only_results:
        warning_codes_list.extend(result.ocr_warning_codes)
    if parse_warning_code and parse_warning_message:
        warning_codes_list.append(parse_warning_code)
        warning_messages.append(parse_warning_message)
    if warning_messages:
        await _store_preview_warnings(session, parsed_record or intake.record, warning_messages)

    result_record = parsed_record or intake.record
    facts_guidance = _build_supplement_facts_guidance(
        record=result_record,
        ocr_result=fused_ocr_result,
        parser_used=parsed_record is not None,
    )
    warning_codes = tuple(warning_codes_list)
    if facts_guidance is not None:
        warning_codes = (*warning_codes, SUPPLEMENT_FACTS_REQUIRED_CODE)
        result_record = await _store_supplement_facts_guidance(
            session,
            result_record,
            facts_guidance,
        )

    representative = ocr_only_results[0] if ocr_only_results else None
    vision_region = representative.vision_region if representative else None
    vision_regions = representative.vision_regions if representative else ()
    ocr_attempted = any(result.ocr_attempted for result in ocr_only_results)
    # Additive vision transcription over every uploaded product image. A single
    # supplement label is often split across facts/directions/warnings photos, so
    # using only the first image can miss the evidence needed to fill amounts or
    # category. Bytes stay request-local and the helper remains best-effort.
    optional_budget = settings.analyze_optional_stage_budget_sec
    result_record, vision_outcome = await _within_optional_budget(
        _merge_vision_structured_extraction_for_ocr_only_results_if_allowed(
            session=session,
            record=result_record,
            ocr_only_results=ocr_only_results,
            parser_used=parsed_record is not None,
            settings=settings,
        ),
        budget_sec=optional_budget,
        fallback=(result_record, _VISION_EXTRACTION_SKIPPED),
        label="vision_structured_extraction_fused",
    )
    pipeline_metadata = _build_pipeline_metadata(
        record=result_record,
        vision_region=vision_region,
        vision_regions=vision_regions,
        ocr_result=fused_ocr_result,
        ocr_attempted=ocr_attempted,
        warning_codes=warning_codes,
        parser_used=parsed_record is not None,
        settings=settings,
        vision_outcome=vision_outcome,
    )
    if _should_store_pipeline_metadata(result_record, pipeline_metadata, vision_regions):
        result_record = await _store_pipeline_metadata(
            session,
            result_record,
            pipeline_metadata,
            vision_regions=vision_regions,
            selected_region=vision_region,
            image_metadata=fused_metadata,
        )

    # Per-image learning artifacts: the fused parse yields ONE preview, but the
    # section-detector training dataset needs each physical image paired with its
    # own layout-bearing OCR result (the fused OCRResult intentionally drops
    # per-image layout). Emit one artifact per image whose learning gate passed
    # and whose bytes were retained; all link to the single fused analysis run id
    # — ``maybe_store_learning_image_object`` dedups on
    # ``(owner, analysis_id, image_sha256)``, so distinct images coexist under one
    # run and each gets its own section annotation task.
    learning_artifacts_per_image = tuple(
        SupplementLearningArtifactsInput(
            analysis_id=result_record.id,
            image_bytes=ocr_only.image_bytes,
            image_metadata=ocr_only.image_metadata,
            ocr_result=ocr_only.ocr_result,
            learning_consents=learning_consents,
        )
        for ocr_only in ocr_only_results
        if ocr_only.learning_gate_allowed and ocr_only.image_bytes is not None
    )
    return SupplementImageAnalysisResult(
        record=result_record,
        reused_existing=intake.reused_existing,
        image_metadata=fused_metadata,
        vision_region=vision_region,
        vision_regions=vision_regions,
        image_quality_report=(
            facts_guidance.image_quality_report if facts_guidance is not None else None
        ),
        ocr_result=fused_ocr_result,
        parser_used=parsed_record is not None,
        ocr_attempted=ocr_attempted,
        ocr_warning_codes=warning_codes,
        learning_artifacts=None,
        learning_artifacts_per_image=learning_artifacts_per_image,
    )


def _normalize_ingredient_match_key(value: object) -> str:
    """Normalize an ingredient name for case/space-insensitive matching.

    Args:
        value: Candidate name value from a parsed candidate or vision ingredient.

    Returns:
        Lowercased, whitespace-collapsed match key, or an empty string.
    """
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().casefold().split())


def _merge_vision_amounts_into_snapshot(
    parsed_snapshot: dict[str, Any],
    extraction: OllamaVisionStructuredExtractionResult,
    allowed_categories: frozenset[str],
    ocr_text: str,
) -> _VisionExtractionOutcome:
    """Additively fill null amounts and set an unset category from vision output.

    The merge never overwrites existing good data: a non-null ingredient amount is
    left untouched, and the category is set only when the snapshot does not already
    carry a non-empty ``product_category_key``. Vision amounts are matched to parsed
    candidates by normalized name against both the display and original names.

    A vision amount fills a null candidate only when it is span-grounded in the OCR
    text (Lever 4 "never guess amount"): a JSON schema constrains the vision output's
    shape, not its truth, and the model can omit or invent a number, so an amount
    that does not appear in the OCR text is dropped (the candidate stays null).

    Args:
        parsed_snapshot: Parsed snapshot dict mutated in place.
        extraction: Schema-validated transcription-only vision extraction.
        allowed_categories: Closed allow-list of category keys.
        ocr_text: OCR text the vision amounts must be grounded in.

    Returns:
        Diagnostic outcome describing what (if anything) was applied.
    """
    # Index only amount-bearing vision ingredients by normalized name; the merge
    # never copies a null vision amount over a parsed candidate.
    vision_by_name: dict[str, OllamaVisionIngredient] = {}
    for ingredient in extraction.ingredients:
        if ingredient.amount is None:
            continue
        name_key = _normalize_ingredient_match_key(ingredient.name)
        if name_key and name_key not in vision_by_name:
            vision_by_name[name_key] = ingredient

    amounts_filled = 0
    candidates = parsed_snapshot.get("ingredient_candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict) or candidate.get("amount") is not None:
                continue
            match: OllamaVisionIngredient | None = None
            for name_key in (
                _normalize_ingredient_match_key(candidate.get("display_name")),
                _normalize_ingredient_match_key(candidate.get("original_name")),
            ):
                if name_key and name_key in vision_by_name:
                    match = vision_by_name[name_key]
                    break
            if match is None or match.amount is None:
                continue
            # Span-grounding guardrail: only fill an amount the vision model proposes
            # when it actually appears in the OCR text. An ungrounded (possibly
            # invented) amount is dropped so it can never reach the review UX.
            if not is_amount_grounded(match.amount, match.unit, ocr_text):
                continue
            candidate["amount"] = match.amount
            if match.unit and not candidate.get("unit"):
                candidate["unit"] = match.unit
            amounts_filled += 1

    category_applied = False
    existing_category = parsed_snapshot.get("product_category_key")
    has_existing_category = isinstance(existing_category, str) and bool(existing_category.strip())
    if (
        not has_existing_category
        and extraction.product_category_key is not None
        and extraction.product_category_key in allowed_categories
    ):
        parsed_snapshot["product_category_key"] = extraction.product_category_key
        category_applied = True

    return _VisionExtractionOutcome(
        attempted=True,
        category_applied=category_applied,
        amounts_filled=amounts_filled,
    )


async def _merge_vision_structured_extraction_if_allowed(
    *,
    session: AsyncSession,
    record: SupplementAnalysisRun,
    image_bytes: bytes | None,
    image_metadata: ValidatedSupplementImage,
    label_region: BoundingBox | None,
    ocr_text: str,
    parser_used: bool,
    settings: Settings,
) -> tuple[SupplementAnalysisRun, _VisionExtractionOutcome]:
    """Run a best-effort local vision transcription and merge it additively.

    Gated on the existing local multimodal flags. The vision pass transcribes only
    visibly-printed ingredient amounts and a category key from the allow-list, then
    fills parsed candidates whose amount is null and sets the category when unset.
    Any vision failure (configuration, transport, schema, timeout) is swallowed so
    the analysis is never broken by this enrichment.

    Args:
        session: Request-scoped async database session.
        record: Parsed analysis row whose snapshot is enriched in place.
        image_bytes: Validated image bytes, if loaded for adapter use.
        image_metadata: Validated image metadata.
        label_region: Optional YOLO ROI passed to the vision model.
        ocr_text: OCR text the merged vision amounts must be grounded in.
        parser_used: Whether structured parsing produced a snapshot to enrich.
        settings: Runtime settings (multimodal flags, vision model, temperature).

    Returns:
        The (possibly refreshed) record and the diagnostic merge outcome.
    """
    if not parser_used or image_bytes is None:
        return record, _VISION_EXTRACTION_SKIPPED
    if (
        not settings.enable_supplement_label_vision_extraction
        or not settings.enable_multimodal_llm
        or not settings.ollama_vision_model
    ):
        return record, _VISION_EXTRACTION_SKIPPED
    parsed_snapshot = record.parsed_snapshot if isinstance(record.parsed_snapshot, dict) else None
    if parsed_snapshot is None:
        return record, _VISION_EXTRACTION_SKIPPED

    allowed_categories = list(allowed_supplement_category_keys())
    try:
        extraction = await OllamaVisionAssistAdapter(settings).extract_structured(
            OCRImageInput(
                image_bytes=image_bytes,
                mime_type=image_metadata.mime_type,
                width=image_metadata.width,
                height=image_metadata.height,
                label_region=label_region,
            ),
            allowed_categories,
        )
    except Exception as exc:
        # Best-effort enrichment: swallow every failure class the vision pass can
        # raise (OllamaConfigurationError / OllamaClientError /
        # OllamaStructuredOutputError / OCRError / TimeoutError and any other) so a
        # vision miss never breaks analysis. Diagnostic only — the logged value is
        # the exception class name (no raw OCR text / image payload / secrets).
        logger.warning(
            "Local vision structured extraction failed (%s); skipping additive merge.",
            exc.__class__.__name__,
        )
        return record, _VISION_EXTRACTION_SKIPPED

    working_snapshot = dict(parsed_snapshot)
    outcome = _merge_vision_amounts_into_snapshot(
        working_snapshot,
        extraction,
        frozenset(allowed_categories),
        ocr_text,
    )
    if not outcome.category_applied and outcome.amounts_filled == 0:
        return record, outcome

    async with persist_scope(session):
        record.parsed_snapshot = working_snapshot
    await session.refresh(record)
    return record, outcome


async def _merge_vision_structured_extraction_for_ocr_only_results_if_allowed(
    *,
    session: AsyncSession,
    record: SupplementAnalysisRun,
    ocr_only_results: list[SupplementOCROnlyResult],
    parser_used: bool,
    settings: Settings,
) -> tuple[SupplementAnalysisRun, _VisionExtractionOutcome]:
    """Run additive local vision extraction for a fused multi-image preview.

    Args:
        session: Request-scoped async database session.
        record: Parsed fused analysis row whose snapshot may be enriched.
        ocr_only_results: Per-image OCR-phase outputs with request-local bytes.
        parser_used: Whether structured parsing produced a snapshot to enrich.
        settings: Runtime settings (multimodal flags, vision model, temperature).

    Returns:
        The latest record and a combined diagnostic outcome.
    """
    combined = _VISION_EXTRACTION_SKIPPED
    current_record = record
    for ocr_only in ocr_only_results:
        current_record, outcome = await _merge_vision_structured_extraction_if_allowed(
            session=session,
            record=current_record,
            image_bytes=ocr_only.image_bytes,
            image_metadata=ocr_only.image_metadata,
            label_region=ocr_only.vision_region,
            ocr_text=ocr_only.ocr_result.text if ocr_only.ocr_result else "",
            parser_used=parser_used,
            settings=settings,
        )
        combined = _combine_vision_extraction_outcomes(combined, outcome)
    return current_record, combined


def _combine_vision_extraction_outcomes(
    first: _VisionExtractionOutcome,
    second: _VisionExtractionOutcome,
) -> _VisionExtractionOutcome:
    """Combine per-image local vision merge diagnostics.

    Args:
        first: Existing accumulated outcome.
        second: New per-image outcome.

    Returns:
        Aggregated outcome for pipeline metadata.
    """
    return _VisionExtractionOutcome(
        attempted=first.attempted or second.attempted,
        category_applied=first.category_applied or second.category_applied,
        amounts_filled=first.amounts_filled + second.amounts_filled,
    )


def _build_pipeline_metadata(
    *,
    record: SupplementAnalysisRun,
    vision_region: BoundingBox | None,
    vision_regions: tuple[BoundingBox, ...],
    ocr_result: OCRResult | None,
    ocr_attempted: bool,
    warning_codes: tuple[str, ...],
    parser_used: bool,
    settings: Settings,
    vision_outcome: _VisionExtractionOutcome = _VISION_EXTRACTION_SKIPPED,
) -> SupplementImagePipelineMetadata:
    """Build sanitized OCR/YOLO/parser metadata for preview response diagnostics.

    Args:
        record: Persisted supplement analysis run.
        vision_region: Optional YOLO-detected ROI used as OCR input metadata.
        vision_regions: Candidate ROI list returned by the vision layer.
        ocr_result: OCR-like result selected for parsing, when available.
        ocr_attempted: Whether a primary OCR adapter was configured and attempted.
        warning_codes: Safe warning codes accumulated during OCR/parser stages.
        parser_used: Whether structured text parsing ran.
        settings: Runtime settings that determine skipped versus warning states.
        vision_outcome: Diagnostic outcome of the additive vision transcription merge.

    Returns:
        Non-sensitive pipeline metadata without raw image, OCR, or provider payloads.
    """
    parsed_snapshot = record.parsed_snapshot if isinstance(record.parsed_snapshot, dict) else {}
    parser_metadata = parsed_snapshot.get("parser_metadata")
    ocr_text_present = bool(ocr_result is not None and ocr_result.text.strip())
    ocr_confidence = ocr_result.confidence if ocr_result is not None else record.ocr_confidence
    return SupplementImagePipelineMetadata(
        intake_completed=True,
        image_count=1,
        image_role=safe_snapshot_string(parsed_snapshot.get("image_role"), default="unknown"),
        vision_roi_used=vision_region is not None,
        ocr_status=_ocr_stage_status(
            ocr_text_present=ocr_text_present,
            ocr_attempted=ocr_attempted,
            warning_codes=warning_codes,
        ),
        vision_status=_vision_stage_status(
            settings=settings,
            vision_regions=vision_regions,
        ),
        llm_status=_llm_stage_status(
            parser_used=parser_used,
            ocr_text_present=ocr_text_present,
            warning_codes=warning_codes,
        ),
        ocr_provider=ocr_result.provider if ocr_result is not None else record.ocr_provider,
        ocr_text_present=ocr_text_present,
        ocr_confidence_bucket=bucket_ocr_confidence(
            ocr_confidence,
            ocr_text_present=ocr_text_present,
        ),
        roi_count=len(vision_regions),
        section_count=count_snapshot_list(parsed_snapshot.get("label_sections")),
        llm_parser_used=parser_used,
        parser_contract_version=parser_contract_version(parser_metadata),
        missing_required_sections=infer_missing_required_sections(
            parsed_snapshot,
            ocr_text_present=ocr_text_present,
        ),
        raw_image_stored=False,
        raw_ocr_text_stored=False,
        vision_extraction_attempted=vision_outcome.attempted,
        vision_category_applied=vision_outcome.category_applied,
        vision_amounts_filled=vision_outcome.amounts_filled,
    )


def _ocr_stage_status(
    *,
    ocr_text_present: bool,
    ocr_attempted: bool,
    warning_codes: tuple[str, ...],
) -> str:
    """Return the public OCR stage status without exposing OCR text.

    Args:
        ocr_text_present: Whether the selected OCR result contains text.
        ocr_attempted: Whether primary OCR was configured for this run.
        warning_codes: Safe warning codes accumulated during the run.

    Returns:
        One of ``success``, ``warning``, ``failed``, or ``skipped``.
    """
    if ocr_text_present:
        return "success"
    if not ocr_attempted:
        return "skipped"
    if AUTOMATIC_OCR_UNAVAILABLE_CODE in warning_codes:
        return "failed"
    return "warning"


def _vision_stage_status(
    *,
    settings: Settings,
    vision_regions: tuple[BoundingBox, ...],
) -> str:
    """Return the public vision ROI stage status.

    Args:
        settings: Runtime feature flags.
        vision_regions: Candidate regions returned by the vision adapter.

    Returns:
        One of ``success``, ``warning``, ``failed``, or ``skipped``.
    """
    if vision_regions:
        return "success"
    return "warning" if settings.enable_vision_classifier else "skipped"


def _llm_stage_status(
    *,
    parser_used: bool,
    ocr_text_present: bool,
    warning_codes: tuple[str, ...],
) -> str:
    """Return the public local-parser stage status.

    Args:
        parser_used: Whether structured parsing completed.
        ocr_text_present: Whether OCR produced non-empty text for parsing.
        warning_codes: Safe warning codes accumulated during the run.

    Returns:
        One of ``success``, ``warning``, ``failed``, or ``skipped``.
    """
    if parser_used:
        return "success"
    if OCR_PARSE_PREVIEW_UNAVAILABLE_CODE in warning_codes:
        return "failed"
    return "warning" if ocr_text_present else "skipped"


def _build_supplement_facts_guidance(
    *,
    record: SupplementAnalysisRun,
    ocr_result: OCRResult | None,
    parser_used: bool,
) -> _SupplementFactsGuidance | None:
    """Build retake guidance when OCR text lacks ingredient amount evidence.

    Args:
        record: Persisted analysis row after parser execution.
        ocr_result: OCR result held in request memory.
        parser_used: Whether structured parsing completed.

    Returns:
        Safe retake guidance, or ``None`` when the preview has usable ingredient
        evidence or the issue belongs to a different failure mode.
    """
    if not parser_used or ocr_result is None or not ocr_result.text.strip():
        return None

    parsed_snapshot = record.parsed_snapshot if isinstance(record.parsed_snapshot, dict) else {}
    ingredient_count = count_snapshot_list(parsed_snapshot.get("ingredient_candidates"))
    if ingredient_count > 0:
        return None

    section_types = _snapshot_section_types(parsed_snapshot)
    has_facts_section = bool(SUPPLEMENT_FACTS_SECTION_TYPES & section_types)
    guidance_snapshot = dict(parsed_snapshot)
    guidance_snapshot["missing_required_sections"] = _with_unique_sections(
        parsed_snapshot.get("missing_required_sections"),
        "ingredients" if has_facts_section else "supplement_facts",
    )
    missing_sections = infer_missing_required_sections(
        guidance_snapshot,
        ocr_text_present=True,
    )
    reason_code = "partial_table" if has_facts_section else "cover_only"
    return _SupplementFactsGuidance(
        image_quality_report=ImageQualityReport.model_validate(
            {
                "status": "retake_recommended",
                "issues": [
                    {
                        "reason_code": reason_code,
                        "severity": "retake",
                        "message": SUPPLEMENT_FACTS_RETAKE_MESSAGE,
                        "evidence": {
                            "ocr_text_present": True,
                            "ingredient_candidate_count": 0,
                            "facts_section_present": has_facts_section,
                        },
                    }
                ],
                "metrics": {
                    "ingredient_candidate_count": 0,
                    "label_section_count": count_snapshot_list(
                        parsed_snapshot.get("label_sections")
                    ),
                },
                "detected_rois": [],
                "retake_reasons": [reason_code],
            }
        ),
        missing_required_sections=tuple(missing_sections),
        image_role="mixed" if has_facts_section else "front_label",
        analysis_scope="full_image_review" if has_facts_section else "identity_only",
        action_required="additional_label_image_required",
    )


async def _store_supplement_facts_guidance(
    session: AsyncSession,
    record: SupplementAnalysisRun,
    guidance: _SupplementFactsGuidance,
) -> SupplementAnalysisRun:
    """Persist safe missing-section guidance without raw OCR or image data.

    Args:
        session: Request-scoped async database session.
        record: Preview row to update.
        guidance: Safe retake guidance.

    Returns:
        Refreshed preview row.
    """
    async with persist_scope(session):
        parsed_snapshot = dict(record.parsed_snapshot or {})
        parsed_snapshot["image_quality_report"] = guidance.image_quality_report.model_dump(
            exclude_none=True
        )
        parsed_snapshot["missing_required_sections"] = list(guidance.missing_required_sections)
        parsed_snapshot["action_required"] = guidance.action_required
        parsed_snapshot["analysis_scope"] = guidance.analysis_scope
        parsed_snapshot["image_role"] = guidance.image_role
        record.parsed_snapshot = parsed_snapshot
        record.warnings = _append_unique_warning(
            record.warnings,
            SUPPLEMENT_FACTS_REQUIRED_WARNING,
        )
    await session.refresh(record)
    return record


def _snapshot_section_types(parsed_snapshot: dict[str, object]) -> set[str]:
    """Return section types present in a sanitized parsed snapshot."""
    label_sections = parsed_snapshot.get("label_sections")
    if not isinstance(label_sections, list):
        return set()
    return {
        section.get("section_type")
        for section in label_sections
        if isinstance(section, dict) and isinstance(section.get("section_type"), str)
    }


def _with_unique_sections(value: object, required_section: str) -> list[str]:
    """Append one missing-section marker to an existing bounded section list."""
    sections: list[str] = []
    seen: set[str] = set()
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, str):
                continue
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            sections.append(normalized)
            seen.add(normalized)
    if required_section not in seen:
        sections.insert(0, required_section)
    return sections[:10]


def _append_unique_warning(value: object, warning: str) -> list[str]:
    """Append a safe warning code while preserving existing warning order."""
    warnings: list[str] = []
    seen: set[str] = set()
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, str):
                continue
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            warnings.append(normalized)
            seen.add(normalized)
    if warning not in seen:
        warnings.append(warning)
    return warnings


def _should_store_pipeline_metadata(
    record: SupplementAnalysisRun,
    metadata: SupplementImagePipelineMetadata,
    vision_regions: tuple[BoundingBox, ...],
) -> bool:
    """Return whether metadata must be persisted beyond record-derived defaults.

    Args:
        record: Persisted supplement analysis run.
        metadata: Sanitized pipeline metadata built for the current execution.
        vision_regions: Candidate ROI list returned by the vision layer.

    Returns:
        True when record fields cannot reconstruct the execution metadata.
    """
    parsed_snapshot = record.parsed_snapshot if isinstance(record.parsed_snapshot, dict) else {}
    if isinstance(parsed_snapshot.get("pipeline_metadata"), dict):
        return True
    if metadata.vision_roi_used or vision_regions:
        return True
    if (
        metadata.ocr_status != "skipped"
        or metadata.vision_status != "skipped"
        or metadata.llm_status != "skipped"
    ):
        return True
    return metadata.ocr_provider is not None and metadata.ocr_provider != record.ocr_provider


async def _store_pipeline_metadata(
    session: AsyncSession,
    record: SupplementAnalysisRun,
    metadata: SupplementImagePipelineMetadata,
    *,
    vision_regions: tuple[BoundingBox, ...],
    selected_region: BoundingBox | None,
    image_metadata: ValidatedSupplementImage,
) -> SupplementAnalysisRun:
    """Persist sanitized pipeline metadata inside the preview snapshot.

    Args:
        session: Request-scoped async database session.
        record: Preview row to update.
        metadata: Non-sensitive pipeline metadata.
        vision_regions: Candidate ROI list returned by the vision layer.
        selected_region: ROI selected for OCR metadata, if any.
        image_metadata: Decoded image metadata used for safe area ratios.

    Returns:
        Refreshed preview row.
    """
    async with persist_scope(session):
        parsed_snapshot = dict(record.parsed_snapshot or {})
        detected_regions = _vision_regions_to_preview(
            vision_regions,
            selected_region=selected_region,
            image_metadata=image_metadata,
        )
        if detected_regions:
            parsed_snapshot["detected_product_regions"] = detected_regions
            selected_region_id = next(
                (region["region_id"] for region in detected_regions if region["selected"]),
                None,
            )
            if selected_region_id is not None:
                parsed_snapshot["selected_region_id"] = selected_region_id
        parsed_snapshot["pipeline_metadata"] = metadata.model_dump(exclude_none=True)
        record.parsed_snapshot = parsed_snapshot
    await session.refresh(record)
    return record


async def _enqueue_supplement_section_annotation_task_if_available(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    learning_object: LearningImageObject | None,
    ocr_result: OCRResult | None,
    settings: Settings,
) -> bool:
    """Queue sanitized OCR layout section candidates for human review.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner used only to derive the privacy-preserving hash.
        learning_object: Consent-retained source image object.
        ocr_result: OCR result containing page dimensions and layout text boxes.
        settings: Runtime settings containing the privacy hash secret.

    Returns:
        True when a new pending annotation task was stored.
    """
    if learning_object is None or ocr_result is None:
        return False
    existing = await session.scalar(
        select(AnnotationTask).where(
            AnnotationTask.learning_image_object_id == learning_object.id,
            AnnotationTask.task_type == SUPPLEMENT_SECTION_ANNOTATION_TASK_TYPE,
            AnnotationTask.review_notes_code == SUPPLEMENT_SECTION_ANNOTATION_REVIEW_NOTES_CODE,
            AnnotationTask.status.in_(("pending", "in_review", "accepted")),
        )
    )
    if existing is not None:
        return False
    try:
        task = build_supplement_section_annotation_task(
            owner_subject_hash=hash_actor_subject(user, settings),
            learning_image_object_id=learning_object.id,
            layout=parse_label_layout(ocr_result),
            page_dimensions=page_dimensions_from_ocr_result(ocr_result),
        )
    except (SupplementSectionLabelCandidateError, ValueError):
        logger.debug("Skipping supplement section annotation task: no safe layout candidate.")
        return False
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return True


async def store_supplement_learning_artifacts(
    *,
    user: AuthenticatedUser,
    artifacts: SupplementLearningArtifactsInput,
    settings: Settings,
    object_store: LearningImageObjectStore,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Persist consent-retained learning image + section annotation post-commit.

    Runs as a route-level FastAPI background task after the request transaction
    commits, so the analysis row is already durable (the learning object's
    foreign key) and the request session's transaction-local RLS GUCs have been
    released. A short-lived session opened from its own factory keeps this work
    fully independent of the request transaction; ``maybe_store_learning_image_object``
    keeps its own commit semantics (DO-NOT-TOUCH learning pipeline). Best-effort:
    any failure is logged and swallowed so a learning miss never surfaces to the
    user (matching the prior in-request best-effort behavior).

    Args:
        user: Authenticated owner used for the privacy-preserving subject hash.
        artifacts: Deferred learning inputs bundled by :func:`analyze_supplement_image`.
        settings: Runtime settings (privacy hash secret, retention, gate flags).
        object_store: Learning image object store the route built for this request.
        session_factory: Optional session factory override (tests); defaults to the
            privileged learning session factory (``get_learning_sessionmaker``),
            which bypasses FORCE RLS so the GUC-less post-commit fresh session can
            write the learning tables under the Stage-2 ``lemon_app`` posture.

    Returns:
        None.
    """
    factory = session_factory or get_learning_sessionmaker()
    try:
        async with factory() as session:
            analysis = await session.get(SupplementAnalysisRun, artifacts.analysis_id)
            if analysis is None:
                logger.warning(
                    "Skipping learning artifacts: analysis row is not durable yet.",
                )
                return
            learning_object = await maybe_store_learning_image_object(
                session=session,
                user=user,
                analysis=analysis,
                image_bytes=artifacts.image_bytes,
                image_metadata=artifacts.image_metadata,
                settings=settings,
                object_store=object_store,
                granted_consents=artifacts.learning_consents,
            )
            if learning_object is None:
                return
            await _enqueue_supplement_section_annotation_task_if_available(
                session=session,
                user=user,
                learning_object=learning_object,
                ocr_result=artifacts.ocr_result,
                settings=settings,
            )
    except Exception:
        # Best-effort post-commit task: a learning miss must never surface to the user.
        logger.exception("Post-commit learning artifact storage failed.")


async def store_supplement_learning_embedding_job(
    *,
    user: AuthenticatedUser,
    embedding_input: SupplementLearningEmbeddingInput,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Enqueue the supplement learning embedding job post-commit.

    Runs as a route-level FastAPI background task after the request transaction
    commits, so the confirmed supplement and its learning image object are
    durable. Uses the privileged learning session factory
    (``get_learning_sessionmaker``) because
    ``enqueue_learning_embedding_job_for_confirmation`` reads/writes the FORCE-RLS
    learning tables and commits on its own (DO-NOT-TOUCH learning pipeline).
    Best-effort: any failure is logged and swallowed so a learning miss never
    surfaces to the user (matching the prior in-request best-effort behavior).

    Args:
        user: Authenticated owner used for the privacy-preserving subject hash.
        embedding_input: Deferred inputs bundled by the confirmation route.
        settings: Runtime settings (privacy hash secret, gate flags, model).
        session_factory: Optional session factory override (tests); defaults to
            the privileged learning session factory.

    Returns:
        None.
    """
    try:
        factory = session_factory or get_learning_sessionmaker()
        async with factory() as session:
            await enqueue_learning_embedding_job_for_confirmation(
                session=session,
                user=user,
                analysis_id=embedding_input.analysis_id,
                metadata_snapshot=embedding_input.metadata_snapshot,
                settings=settings,
                granted_consents=embedding_input.learning_consents,
            )
    except Exception:
        # Best-effort post-commit task: a learning miss must never surface to the user.
        logger.exception("Post-commit learning embedding enqueue failed.")


def _select_vision_region(vision_regions: tuple[BoundingBox, ...]) -> BoundingBox | None:
    """Select the single ROI used for existing OCR preprocessing.

    Args:
        vision_regions: Candidate ROI list returned by the vision layer.

    Returns:
        Best label-region candidate, or None when no usable candidate exists.
    """
    if not vision_regions:
        return None
    try:
        return select_best_label_region(list(vision_regions))
    except VisionPreprocessingError:
        return None


def _vision_regions_to_preview(
    vision_regions: tuple[BoundingBox, ...],
    *,
    selected_region: BoundingBox | None,
    image_metadata: ValidatedSupplementImage,
) -> list[dict[str, object]]:
    """Serialize detected regions into bounded review metadata.

    Args:
        vision_regions: Candidate ROI list returned by the vision layer.
        selected_region: ROI selected for OCR metadata, if any.
        image_metadata: Decoded image metadata used for safe area ratios.

    Returns:
        List of sanitized region dictionaries for preview snapshots.
    """
    regions: list[dict[str, object]] = []
    for index, region in enumerate(vision_regions[:20], start=1):
        regions.append(
            {
                "region_id": f"vision-{index}",
                "label": region.label,
                "x": region.x,
                "y": region.y,
                "width": region.width,
                "height": region.height,
                "confidence": region.confidence,
                "area_ratio": _region_area_ratio(region, image_metadata),
                "selected": _same_region(region, selected_region),
            }
        )
    return regions


def _same_region(candidate: BoundingBox, selected: BoundingBox | None) -> bool:
    """Return whether two bounding boxes represent the selected ROI."""
    if selected is None:
        return False
    return candidate == selected


def _region_area_ratio(
    region: BoundingBox,
    image_metadata: ValidatedSupplementImage,
) -> float | None:
    """Return the region area ratio bounded to the input image size."""
    image_area = image_metadata.width * image_metadata.height
    if image_area <= 0:
        return None
    return min(1.0, max(0.0, (region.width * region.height) / image_area))


async def _read_validated_image_bytes_if_needed(
    image: UploadFile,
    *,
    active_adapters: SupplementImageAnalysisAdapters,
    settings: Settings,
    needs_learning_image_bytes: bool = False,
    image_metadata: ValidatedSupplementImage,
) -> bytes | None:
    """Read image bytes for adapters only when an adapter path may execute.

    Bytes returned here are stripped of EXIF/XMP/IPTC metadata so downstream
    OCR adapters, learning storage, and audit consumers never observe user
    GPS coordinates or device identifiers.

    Args:
        image: Already validated upload file.
        active_adapters: Pipeline adapters requested for this call.
        settings: Runtime settings containing feature flags.
        needs_learning_image_bytes: Whether learning retention needs the original image bytes.
        image_metadata: Validated metadata used to authorize the MIME for stripping.

    Returns:
        Sanitized image bytes, or None when no adapter needs them.

    Raises:
        SupplementImageValidationError: If the validated image fails the
            sanitization re-encode pass.
    """
    needs_bytes = active_adapters.ocr is not None or settings.enable_vision_classifier
    needs_bytes = needs_bytes or bool(active_adapters.fallback_ocr_adapters)
    needs_bytes = needs_bytes or needs_learning_image_bytes
    needs_bytes = needs_bytes or (
        active_adapters.multimodal_ocr is not None and settings.enable_multimodal_llm
    )
    if not needs_bytes:
        return None
    await image.seek(0)
    raw = await image.read()
    try:
        return strip_image_metadata(raw, image_metadata.mime_type)
    except ImageSafetyError as exc:
        raise SupplementImageValidationError(
            code="invalid_image",
            message="Uploaded label image cannot be normalized for downstream use.",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        ) from exc


async def _detect_label_regions_if_enabled(
    *,
    image_bytes: bytes | None,
    settings: Settings,
    vision_adapter: VisionAdapter | None,
) -> tuple[BoundingBox, ...]:
    """Run label-region detection only when the vision feature flag is enabled.

    Args:
        image_bytes: Validated image bytes, if loaded for adapter use.
        settings: Runtime settings.
        vision_adapter: Optional vision adapter.

    Returns:
        Detected label regions, or an empty tuple when disabled.

    Raises:
        SupplementImageAnalysisConfigurationError: If the flag is enabled without an adapter.
    """
    if not settings.enable_vision_classifier:
        return ()
    if vision_adapter is None or image_bytes is None:
        raise SupplementImageAnalysisConfigurationError(
            "ENABLE_VISION_CLASSIFIER=true requires a VisionAdapter."
        )
    try:
        return tuple(await vision_adapter.detect_regions(image_bytes))
    except VisionError:
        return ()


async def _extract_ocr_if_configured(
    *,
    image_bytes: bytes | None,
    image_metadata: ValidatedSupplementImage,
    label_regions: tuple[BoundingBox, ...],
    selected_region: BoundingBox | None,
    ocr_adapter: OCRAdapter | None,
    settings: Settings,
) -> _OCRExtractionResult:
    """Run OCR only when an OCR adapter is injected.

    Args:
        image_bytes: Validated image bytes, if loaded for adapter use.
        image_metadata: Validated image metadata.
        label_regions: Candidate label-region ROIs from the vision layer.
        selected_region: Best ROI selected for preview metadata.
        ocr_adapter: Optional OCR adapter.
        settings: Runtime settings controlling ROI preprocessing.

    Returns:
        OCR extraction result and optional recoverable warning metadata.
    """
    if ocr_adapter is None or image_bytes is None:
        return _OCRExtractionResult(ocr_result=None)

    ocr_inputs, warning_code, warning_message = _prepare_primary_ocr_image_inputs(
        image_bytes=image_bytes,
        image_metadata=image_metadata,
        label_regions=label_regions,
        selected_region=selected_region,
        settings=settings,
    )
    results: list[OCRResult] = []
    for ocr_input in ocr_inputs:
        try:
            results.append(await ocr_adapter.extract_text(ocr_input))
        except OCRError:
            continue

    result = _merge_ocr_results(results)
    if result is None:
        return _OCRExtractionResult(
            ocr_result=None,
            warning_code=AUTOMATIC_OCR_UNAVAILABLE_CODE,
            warning_message=AUTOMATIC_OCR_UNAVAILABLE_WARNING,
        )
    return _OCRExtractionResult(
        ocr_result=result,
        warning_code=warning_code,
        warning_message=warning_message,
    )


def _prepare_primary_ocr_image_inputs(
    *,
    image_bytes: bytes,
    image_metadata: ValidatedSupplementImage,
    label_regions: tuple[BoundingBox, ...],
    selected_region: BoundingBox | None,
    settings: Settings,
) -> tuple[list[OCRImageInput], str | None, str | None]:
    """Build one or more OCR inputs for ROI-first extraction plus fallback.

    Args:
        image_bytes: Validated source image bytes.
        image_metadata: Validated image metadata.
        label_regions: Candidate label regions from vision detection.
        selected_region: Best label region used first when present.
        settings: Runtime settings controlling ROI preprocessing.

    Returns:
        OCR inputs plus optional warning code and message.
    """
    if settings.ocr_roi_preprocessing_policy != "crop_before_primary" or not label_regions:
        ocr_input, warning_code, warning_message = _prepare_primary_ocr_image_input(
            image_bytes=image_bytes,
            image_metadata=image_metadata,
            label_region=selected_region,
            settings=settings,
        )
        return [ocr_input], warning_code, warning_message

    inputs: list[OCRImageInput] = []
    warning_code: str | None = None
    warning_message: str | None = None
    for region in _ordered_ocr_regions(label_regions, selected_region):
        ocr_input, crop_warning_code, crop_warning_message = _prepare_primary_ocr_image_input(
            image_bytes=image_bytes,
            image_metadata=image_metadata,
            label_region=region,
            settings=settings,
        )
        if crop_warning_code is not None and warning_code is None:
            warning_code = crop_warning_code
            warning_message = crop_warning_message
        if ocr_input.label_region is None and ocr_input.image_bytes == image_bytes:
            continue
        inputs.append(ocr_input)

    inputs.append(
        OCRImageInput(
            image_bytes=image_bytes,
            mime_type=image_metadata.mime_type,
            width=image_metadata.width,
            height=image_metadata.height,
            label_region=None,
        )
    )
    return inputs, warning_code, warning_message


def _ordered_ocr_regions(
    label_regions: tuple[BoundingBox, ...],
    selected_region: BoundingBox | None,
) -> list[BoundingBox]:
    """Return a bounded ROI list prioritized for section-level OCR.

    Args:
        label_regions: Candidate regions from the vision adapter.
        selected_region: Best region selected by existing scorer.

    Returns:
        De-duplicated regions capped for OCR provider cost control.
    """
    unique_regions: list[BoundingBox] = []
    for region in (selected_region, *label_regions):
        if region is None or region in unique_regions:
            continue
        unique_regions.append(region)
    return sorted(
        unique_regions,
        key=lambda region: (label_priority(region.label), -region.confidence),
    )[:MAX_PRIMARY_OCR_ROI_CANDIDATES]


def _normalized_nonempty_lines(text: str) -> list[str]:
    """Return stripped non-empty lines from OCR text.

    Args:
        text: Raw OCR text.

    Returns:
        Stripped lines with empty lines removed, in original order.
    """
    return [line.strip() for line in text.splitlines() if line.strip()]


def _merge_ocr_results(results: list[OCRResult]) -> OCRResult | None:
    """Merge multi-ROI OCR text in memory without preserving raw provider payloads.

    Args:
        results: OCR results returned by one provider for ROI and fallback inputs.

    Returns:
        A single OCR result for parser input, or ``None`` if every call failed.
    """
    if not results:
        return None
    usable = [result for result in results if result.text.strip()]
    if not usable:
        return results[-1]
    if len(usable) == 1:
        return usable[0]

    text_parts: list[str] = []
    seen_texts: set[str] = set()
    confidences: list[float] = []
    pages: list[OCRPage] = []
    for result in usable:
        normalized = "\n".join(_normalized_nonempty_lines(result.text))
        if not normalized or normalized in seen_texts:
            continue
        text_parts.append(normalized)
        seen_texts.add(normalized)
        pages.extend(result.pages)
        if result.confidence is not None:
            confidences.append(result.confidence)
    confidence = sum(confidences) / len(confidences) if confidences else None
    return OCRResult(
        text="\n\n".join(text_parts),
        provider=usable[0].provider,
        confidence=confidence,
        pages=tuple(pages),
    )


def _line_dedup_key(line: str) -> str:
    """Build a whitespace-insensitive, case-folded dedup key for one OCR line.

    Args:
        line: OCR line text.

    Returns:
        Dedup key with all whitespace stripped and case folded.
    """
    return "".join(line.casefold().split())


def _is_near_duplicate(key: str, seen: set[str], threshold: float) -> bool:
    """Check whether a dedup key is a near-duplicate of any seen key.

    Args:
        key: Candidate line dedup key.
        seen: Dedup keys already accepted into the merge.
        threshold: SequenceMatcher ratio threshold for treating two keys as duplicates.

    Returns:
        True when any seen key has a similarity ratio at or above ``threshold``.
    """
    return any(SequenceMatcher(None, key, existing).ratio() >= threshold for existing in seen)


def _merge_confidence(primary: OCRResult, secondary: OCRResult) -> float | None:
    """Choose the merged confidence, deliberately anchoring on the primary provider.

    The primary (e.g. Clova) confidence is the trust anchor and is reported
    verbatim even when many secondary lines were supplemented — the merge adds
    coverage, it does not dilute the primary's reliability. This anchor-on-primary
    choice is load-bearing: the legacy ``_extract_secondary_ocr_if_allowed`` no-op
    under ensemble mode relies on a merged result keeping the primary's
    (above-threshold) confidence so ``_should_run_secondary_fallback`` stays False
    and Paddle is not run a second time.

    Args:
        primary: Primary OCR result.
        secondary: Secondary OCR result.

    Returns:
        Primary confidence when present, otherwise the secondary confidence.
    """
    return primary.confidence if primary.confidence is not None else secondary.confidence


# Upper bound on how many secondary lines the cross-provider merge will examine.
# ``ocr_merge_max_supplement_lines`` bounds how many are *appended*; this bounds the
# *iteration* so a noisy secondary pass that emits only near-duplicates (appends
# stay low, so that cap never trips) cannot make the per-line near-dup scan run
# over an unbounded number of lines. Real supplement labels are well under this.
_MAX_SECONDARY_MERGE_CANDIDATES = 200


def _merge_cross_provider_ocr_results(
    primary: OCRResult | None,
    secondary: OCRResult | None,
    settings: Settings,
) -> OCRResult | None:
    """Line-union merge a secondary OCR result into a primary result (supplement).

    The primary text is never replaced; only novel secondary lines (neither exact,
    whitespace/casing, nor SequenceMatcher near-duplicates of a primary line) are
    appended, bounded by ``ocr_merge_max_supplement_lines`` and, for iteration cost,
    ``_MAX_SECONDARY_MERGE_CANDIDATES``.

    Carve-out: when the primary is empty/whitespace this returns the secondary
    result object *unchanged* (a graceful stand-in, not a merge) — its provider is
    the secondary's own label (no ``"+"`` marker), so the always-on-merge
    verification gate does not treat that empty-primary stand-in as a merge.

    Args:
        primary: Primary OCR result, if any.
        secondary: Secondary OCR result to merge in, if any.
        settings: Runtime settings controlling dedup threshold and line cap.

    Returns:
        Merged OCR result, or whichever single result is non-empty, or None.
    """
    primary_lines = _normalized_nonempty_lines(primary.text) if primary is not None else []
    secondary_lines = _normalized_nonempty_lines(secondary.text) if secondary is not None else []
    if not primary_lines:
        return secondary if secondary is not None else primary
    if not secondary_lines:
        return primary
    assert primary is not None
    assert secondary is not None

    merged = list(primary_lines)
    seen = {_line_dedup_key(line) for line in primary_lines}
    threshold = settings.ocr_merge_dedup_threshold
    appended = 0
    for line in secondary_lines[:_MAX_SECONDARY_MERGE_CANDIDATES]:
        if appended >= settings.ocr_merge_max_supplement_lines:
            break
        key = _line_dedup_key(line)
        if key in seen or _is_near_duplicate(key, seen, threshold):
            continue
        merged.append(line)
        seen.add(key)
        appended += 1

    return OCRResult(
        text="\n".join(merged),
        provider=f"{primary.provider}+{secondary.provider}",
        confidence=_merge_confidence(primary, secondary),
        pages=(*primary.pages, *secondary.pages),
    )


def _should_run_ensemble_merge(primary_result: OCRResult | None, settings: Settings) -> bool:
    """Determine whether the ensemble secondary-merge stage should run.

    Args:
        primary_result: Primary OCR result, if any.
        settings: Runtime settings controlling the merge policy.

    Returns:
        True only for the configured ``always`` or qualifying ``low_confidence`` cases.
    """
    if settings.ocr_secondary_merge_policy == "disabled":
        return False
    if settings.ocr_secondary_merge_policy == "always":
        return True
    if primary_result is None or not primary_result.text.strip():
        return True
    return _is_low_confidence(primary_result.confidence)


async def _supplement_ensemble_ocr_if_allowed(
    *,
    image_bytes: bytes | None,
    image_metadata: ValidatedSupplementImage,
    label_region: BoundingBox | None,
    ocr_result: OCRResult | None,
    secondary_merge_adapter: OCRAdapter | None,
    settings: Settings,
) -> OCRResult | None:
    """Always-run secondary OCR and line-union merge it into the primary result.

    Unlike the legacy fallback chain this stage supplements the primary result
    instead of replacing it, and uses a single full-image OCR call with no ROI
    fan-out. It is fully config-gated and defaults to a passthrough.

    Args:
        image_bytes: Validated image bytes, if loaded for adapter use.
        image_metadata: Validated image metadata.
        label_region: Optional YOLO ROI metadata passed to the secondary adapter.
        ocr_result: Primary OCR result candidate.
        secondary_merge_adapter: Optional secondary OCR adapter to merge in.
        settings: Runtime settings controlling the merge policy.

    Returns:
        Primary OCR result unchanged, or the cross-provider merged result.
    """
    if not _should_run_ensemble_merge(ocr_result, settings):
        return ocr_result
    if secondary_merge_adapter is None or image_bytes is None:
        return ocr_result

    secondary_input = OCRImageInput(
        image_bytes=image_bytes,
        mime_type=image_metadata.mime_type,
        width=image_metadata.width,
        height=image_metadata.height,
        label_region=label_region,
    )
    try:
        secondary_result = await secondary_merge_adapter.extract_text(secondary_input)
    except OCRError as exc:
        # Diagnostic only: a failed supplement merge leaves the primary result
        # intact. Log the failure class so a silently-skipped merge is observable.
        logger.warning(
            "Secondary ensemble OCR merge failed (%s); using primary OCR result.",
            exc.__class__.__name__,
        )
        return ocr_result

    return _merge_cross_provider_ocr_results(ocr_result, secondary_result, settings)


def _prepare_primary_ocr_image_input(
    *,
    image_bytes: bytes,
    image_metadata: ValidatedSupplementImage,
    label_region: BoundingBox | None,
    settings: Settings,
) -> tuple[OCRImageInput, str | None, str | None]:
    """Build primary OCR input, cropping ROI only when policy and metadata allow it.

    Args:
        image_bytes: Validated source image bytes.
        image_metadata: Validated image metadata.
        label_region: Optional detected label-region ROI.
        settings: Runtime settings controlling ROI preprocessing.

    Returns:
        OCR input plus optional warning code and message.
    """
    original_input = OCRImageInput(
        image_bytes=image_bytes,
        mime_type=image_metadata.mime_type,
        width=image_metadata.width,
        height=image_metadata.height,
        label_region=label_region,
    )
    if settings.ocr_roi_preprocessing_policy != "crop_before_primary" or label_region is None:
        return original_input, None, None

    try:
        crop_region = _effective_primary_ocr_crop_region(
            image_bytes=image_bytes,
            label_region=label_region,
            settings=settings,
        )
        cropped_bytes = crop_image_to_bounding_box(image_bytes, crop_region)
    except VisionPreprocessingError:
        return original_input, OCR_ROI_CROP_UNAVAILABLE_CODE, OCR_ROI_CROP_UNAVAILABLE_WARNING

    return (
        OCRImageInput(
            image_bytes=cropped_bytes,
            mime_type="image/png",
            width=crop_region.width,
            height=crop_region.height,
            label_region=None,
        ),
        None,
        None,
    )


def _effective_primary_ocr_crop_region(
    *,
    image_bytes: bytes,
    label_region: BoundingBox,
    settings: Settings,
) -> BoundingBox:
    """Return the ROI crop box used for primary OCR.

    Padding helps real supplement labels because detector boxes often clip table
    columns. When a tiny or edge-touching ROI would expand to the full image,
    though, the crop stops being ROI-scoped. In that case use the detector box
    itself so the pipeline preserves ROI-first behavior and still sends a full
    image fallback as the secondary OCR input.

    Args:
        image_bytes: Validated source image bytes.
        label_region: Detector-provided ROI box.
        settings: Runtime settings containing OCR crop padding controls.

    Returns:
        The effective crop region to encode as primary OCR input.

    Raises:
        VisionPreprocessingError: If the image cannot be decoded or the box/padding
            values are invalid.
    """
    try:
        decoded = safe_load_with_bomb_guard(image_bytes)
    except ImageSafetyError as exc:
        raise VisionPreprocessingError("Image cannot be decoded for OCR ROI crop.") from exc

    with decoded as image:
        image_width, image_height = image.size

    expanded_region = expand_bounding_box(
        label_region,
        image_width=image_width,
        image_height=image_height,
        padding_ratio=settings.ocr_roi_crop_padding_ratio,
        min_padding_px=settings.ocr_roi_crop_min_padding_px,
        max_padding_px=settings.ocr_roi_crop_max_padding_px,
    )
    if expanded_region.width >= image_width and expanded_region.height >= image_height:
        return label_region
    return expanded_region


async def _extract_multimodal_ocr_if_allowed(
    *,
    image_bytes: bytes | None,
    image_metadata: ValidatedSupplementImage,
    label_region: BoundingBox | None,
    ocr_result: OCRResult | None,
    primary_ocr_attempted: bool,
    settings: Settings,
    multimodal_adapter: OCRAdapter | None,
) -> OCRResult | None:
    """Run local vision LLM candidate extraction only as an OCR fallback.

    Args:
        image_bytes: Validated image bytes, if loaded for adapter use.
        image_metadata: Validated image metadata.
        label_region: Optional YOLO ROI that may reduce the image sent to the model.
        ocr_result: Primary OCR result, if any.
        primary_ocr_attempted: Whether a primary OCR adapter was actually configured.
        settings: Runtime settings controlling fallback policy.
        multimodal_adapter: Optional local vision LLM adapter.

    Returns:
        Primary OCR result, fallback candidate result, or None.
    """
    if not primary_ocr_attempted:
        return ocr_result
    if ocr_result is not None and not _should_run_multimodal_fallback(ocr_result, settings):
        return ocr_result
    if not settings.enable_multimodal_llm or multimodal_adapter is None or image_bytes is None:
        return ocr_result
    try:
        return await multimodal_adapter.extract_text(
            OCRImageInput(
                image_bytes=image_bytes,
                mime_type=image_metadata.mime_type,
                width=image_metadata.width,
                height=image_metadata.height,
                label_region=label_region,
            )
        )
    except (
        OCRError,
        OllamaClientError,
        OllamaConfigurationError,
        OllamaStructuredOutputError,
    ) as exc:
        # Diagnostic only: log the failure class (no raw OCR text / payload / secrets)
        # so a silently-skipped vision fallback is observable once the gate opens.
        logger.warning(
            "Multimodal vision OCR fallback failed (%s); using primary OCR result.",
            exc.__class__.__name__,
        )
        return ocr_result


async def _extract_secondary_ocr_if_allowed(
    *,
    image_bytes: bytes | None,
    image_metadata: ValidatedSupplementImage,
    label_region: BoundingBox | None,
    ocr_result: OCRResult | None,
    primary_ocr_attempted: bool,
    fallback_adapters: tuple[OCRAdapter, ...],
) -> OCRResult | None:
    """Run optional secondary OCR providers after primary/multimodal weakness.

    Args:
        image_bytes: Validated image bytes, if loaded for adapter use.
        image_metadata: Validated image metadata.
        label_region: Optional YOLO ROI metadata.
        ocr_result: Current OCR result candidate.
        primary_ocr_attempted: Whether a primary OCR adapter was configured.
        fallback_adapters: Optional secondary OCR fallback adapters.

    Returns:
        Current OCR result or the first usable fallback result.
    """
    if not primary_ocr_attempted or image_bytes is None or not fallback_adapters:
        return ocr_result
    if not _should_run_secondary_fallback(ocr_result):
        return ocr_result

    fallback_input = OCRImageInput(
        image_bytes=image_bytes,
        mime_type=image_metadata.mime_type,
        width=image_metadata.width,
        height=image_metadata.height,
        label_region=label_region,
    )
    for adapter in fallback_adapters:
        try:
            candidate = await adapter.extract_text(fallback_input)
        except OCRError:
            continue
        if candidate.text.strip():
            return candidate
    return ocr_result


async def _verify_ocr_with_multimodal_if_allowed(
    *,
    image_bytes: bytes | None,
    image_metadata: ValidatedSupplementImage,
    label_region: BoundingBox | None,
    ocr_result: OCRResult | None,
    settings: Settings,
    multimodal_adapter: OCRAdapter | None,
) -> tuple[str | None, str | None]:
    """Optionally verify accepted OCR text with the local vision assist adapter.

    Args:
        image_bytes: Validated image bytes, if loaded.
        image_metadata: Validated image metadata.
        label_region: Optional YOLO ROI metadata.
        ocr_result: OCR result selected for parsing.
        settings: Runtime settings controlling verification.
        multimodal_adapter: Local vision assist adapter.

    Returns:
        Optional warning code and message.
    """
    if not _should_run_multimodal_verification(
        ocr_result=ocr_result,
        settings=settings,
        multimodal_adapter=multimodal_adapter,
        image_bytes=image_bytes,
    ):
        return None, None

    assert ocr_result is not None
    assert multimodal_adapter is not None
    assert image_bytes is not None
    verification_input = OCRImageInput(
        image_bytes=image_bytes,
        mime_type=image_metadata.mime_type,
        width=image_metadata.width,
        height=image_metadata.height,
        label_region=label_region,
    )
    if isinstance(multimodal_adapter, _MultimodalTextVerifier):
        return await _verify_ocr_with_structured_multimodal(
            verification_input=verification_input,
            ocr_text=ocr_result.text,
            settings=settings,
            verifier=multimodal_adapter,
        )

    try:
        candidate = await multimodal_adapter.extract_text(verification_input)
    except (OCRError, OllamaClientError, OllamaConfigurationError, OllamaStructuredOutputError):
        return None, None

    similarity = _normalized_text_similarity(ocr_result.text, candidate.text)
    if similarity < Decimal(str(settings.multimodal_verification_threshold)):
        return OCR_VERIFICATION_MISMATCH_CODE, OCR_VERIFICATION_MISMATCH_WARNING
    return None, None


async def _verify_ocr_with_structured_multimodal(
    *,
    verification_input: OCRImageInput,
    ocr_text: str,
    settings: Settings,
    verifier: _MultimodalTextVerifier,
) -> tuple[str | None, str | None]:
    """Verify OCR text with schema-aware local vision output.

    Args:
        verification_input: Image input used for local vision verification.
        ocr_text: OCR text selected by the backend pipeline.
        settings: Runtime settings containing verification threshold.
        verifier: Local vision adapter implementing structured verification.

    Returns:
        Optional warning code and message.
    """
    try:
        verification = await verifier.verify_text(verification_input, ocr_text)
    except (
        OCRError,
        OllamaClientError,
        OllamaConfigurationError,
        OllamaStructuredOutputError,
    ):
        return None, None
    if _verification_indicates_mismatch(verification, settings):
        return OCR_VERIFICATION_MISMATCH_CODE, OCR_VERIFICATION_MISMATCH_WARNING
    return None, None


def _verification_indicates_mismatch(
    verification: OllamaVisionTextVerificationResult,
    settings: Settings,
) -> bool:
    """Return whether structured vision verification should warn the user.

    Args:
        verification: Schema-validated local vision verification result.
        settings: Runtime settings containing confidence threshold.

    Returns:
        True when the local vision model reports unsupported OCR text or missing
        critical supplement sections.
    """
    if verification.verification_status == "mismatch":
        return True
    if verification.missing_critical_sections:
        return True
    if verification.verification_status == "partial":
        return Decimal(str(verification.confidence)) < Decimal(
            str(settings.multimodal_verification_threshold)
        )
    return False


def _should_run_multimodal_fallback(ocr_result: OCRResult | None, settings: Settings) -> bool:
    """Determine whether OCR output is weak enough to call vision assist.

    Args:
        ocr_result: Primary OCR output, if any.
        settings: Runtime settings containing fallback policy.

    Returns:
        True only for configured OCR-empty or low-confidence fallback cases.
    """
    if settings.multimodal_ocr_assist_policy == "disabled":
        return False
    if ocr_result is None:
        return settings.multimodal_ocr_assist_policy in {"ocr_empty_only", "low_confidence"}
    if not ocr_result.text.strip():
        return settings.multimodal_ocr_assist_policy in {"ocr_empty_only", "low_confidence"}
    if settings.multimodal_ocr_assist_policy != "low_confidence":
        return False
    return _is_low_confidence(ocr_result.confidence)


def _should_run_secondary_fallback(ocr_result: OCRResult | None) -> bool:
    """Determine whether secondary OCR fallback providers should run.

    Args:
        ocr_result: Current OCR candidate.

    Returns:
        True when the current OCR candidate is empty or low confidence.
    """
    if ocr_result is None:
        return True
    if not ocr_result.text.strip():
        return True
    return _is_low_confidence(ocr_result.confidence)


def _should_run_multimodal_verification(
    *,
    ocr_result: OCRResult | None,
    settings: Settings,
    multimodal_adapter: OCRAdapter | None,
    image_bytes: bytes | None,
) -> bool:
    """Determine whether local vision verification should run.

    Args:
        ocr_result: OCR result selected for parsing.
        settings: Runtime settings.
        multimodal_adapter: Local vision assist adapter.
        image_bytes: Validated image bytes.

    Returns:
        True only when verification is enabled and sampled.
    """
    if not settings.enable_multimodal_verification or not settings.enable_multimodal_llm:
        return False
    if multimodal_adapter is None or image_bytes is None or ocr_result is None:
        return False
    if not ocr_result.text.strip() or ocr_result.provider == "ollama_vision_assist":
        return False
    if settings.ocr_ensemble_verification_mode == "always_on_merge" and "+" in ocr_result.provider:
        return True
    return _verification_sample_passes(settings.multimodal_verification_sample_rate)


def _verification_sample_passes(sample_rate: float) -> bool:
    """Resolve the verification sampling decision for the inherit-sample path.

    Args:
        sample_rate: Configured verification sample rate.

    Returns:
        True when the configured sampling rate selects this result.
    """
    if sample_rate <= 0:
        return False
    if sample_rate >= 1:
        return True
    return random() < sample_rate


def _is_low_confidence(confidence: float | None) -> bool:
    """Check whether OCR confidence should trigger vision assist review.

    Args:
        confidence: Provider-level confidence.

    Returns:
        True when confidence is present and below the parser low-confidence threshold.
    """
    if confidence is None:
        return False
    return Decimal(str(confidence)) < OCR_LOW_CONFIDENCE_THRESHOLD


def _normalized_text_similarity(left: str, right: str) -> Decimal:
    """Return normalized similarity between OCR text candidates.

    Args:
        left: Primary OCR text.
        right: Verification text.

    Returns:
        Decimal similarity in the inclusive range 0.0 to 1.0.
    """
    left_normalized = " ".join(left.casefold().split())
    right_normalized = " ".join(right.casefold().split())
    if not left_normalized and not right_normalized:
        return Decimal("1")
    ratio = SequenceMatcher(a=left_normalized, b=right_normalized).ratio()
    return Decimal(str(ratio))


async def _parse_ocr_if_available(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    intake: SupplementIntakeStoreResult,
    ocr_result: OCRResult | None,
    settings: Settings,
    parser: SupplementOCRTextParser | None,
) -> tuple[SupplementAnalysisRun | None, str | None, str | None]:
    """Parse OCR text only when OCR produced non-empty text.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        intake: Stored intake result.
        ocr_result: OCR result to parse.
        settings: Runtime settings.
        parser: Optional parser adapter.

    Returns:
        Updated analysis row and optional warning metadata.
    """
    if ocr_result is None or not ocr_result.text.strip():
        if ocr_result is None:
            return None, None, None
        return None, OCR_TEXT_EMPTY_CODE, OCR_TEXT_EMPTY_WARNING
    try:
        parsed = await parse_supplement_analysis_ocr_text(
            session=session,
            user=user,
            analysis_id=intake.record.id,
            ocr_text=ocr_result.text,
            ocr_provider=ocr_result.provider,
            ocr_confidence=ocr_result.confidence,
            settings=settings,
            ocr_layout=parse_label_layout(ocr_result),
            parser=parser,
        )
    except PARSER_RECOVERABLE_ERRORS:
        return (
            None,
            OCR_PARSE_PREVIEW_UNAVAILABLE_CODE,
            OCR_PARSE_PREVIEW_UNAVAILABLE_WARNING,
        )
    return parsed.record, None, None


async def _store_preview_warnings(
    session: AsyncSession,
    record: SupplementAnalysisRun,
    warnings: list[str],
) -> None:
    """Persist recoverable OCR/parser warnings on an intake preview.

    Args:
        session: Request-scoped async database session.
        record: Intake preview row.
        warnings: Safe warning strings to add.
    """
    async with persist_scope(session):
        existing_warnings = list(record.warnings or [])
        for warning in warnings:
            if warning not in existing_warnings:
                existing_warnings.append(warning)
        record.warnings = existing_warnings
    await session.refresh(record)
