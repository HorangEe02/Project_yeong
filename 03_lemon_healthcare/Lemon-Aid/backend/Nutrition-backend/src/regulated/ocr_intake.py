"""Intake-only OCR service for prescription and lab result documents."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from http import HTTPStatus
from io import BytesIO
from typing import Any
from uuid import UUID, uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.db.tx import persist_scope
from src.models.db.medical import MedicalRecordCollection, PatientMedication
from src.models.db.regulated import LabResultItem, PrescriptionItem, RegulatedDocument
from src.models.schemas.regulated import (
    ConsultProfessionalCTA,
    LabResultItemConfirm,
    LabResultItemPreview,
    LabResultOCRPreviewResponse,
    PrescriptionItemConfirm,
    PrescriptionItemPreview,
    PrescriptionOCRPreviewResponse,
    RegulatedDocumentConfirmRequest,
    RegulatedDocumentConfirmResponse,
    RegulatedDocumentStatus,
    RegulatedDocumentType,
)
from src.ocr.base import OCRAdapter, OCRError, OCRImageInput, OCRResult
from src.regulated.factory import RegulatedOCRAdapters
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject
from src.utils.image_safety import (
    ImageSafetyError,
    safe_load_with_bomb_guard,
    strip_image_metadata,
)

REGULATED_INTAKE_ALGORITHM_VERSION = "regulated-ocr-intake-v1.0.0"
REGULATED_INTAKE_PROVIDER = "intake-only"
REGULATED_ALLOWED_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
READ_CHUNK_SIZE_BYTES = 64 * 1024
WEBP_HEADER_MIN_BYTES = 12
MAX_PREVIEW_ITEMS = 40
MAX_OCR_PARSE_CHARS = 20_000
AUTOMATIC_OCR_UNAVAILABLE_CODE = "automatic_ocr_unavailable"
AUTOMATIC_OCR_UNAVAILABLE_WARNING = (
    "자동 OCR을 사용할 수 없습니다. 문서 내용을 직접 확인해 입력하세요."
)
OCR_TEXT_EMPTY_CODE = "ocr_text_empty"
OCR_TEXT_EMPTY_WARNING = "문서에서 읽을 수 있는 텍스트를 찾지 못했습니다. 직접 확인해 입력하세요."
OCR_PROVIDER_FAILED_CODE = "ocr_provider_failed"
OCR_PROVIDER_FAILED_WARNING = "OCR 제공자 호출이 실패했습니다. 직접 확인해 입력하세요."
REQUIRES_CONFIRMATION_WARNING = "OCR 결과는 저장 전 사용자가 직접 확인해야 합니다."
LAB_REQUIRES_CONFIRMATION_WARNING = "검사 결과 해석은 담당 의료진과 상담해야 합니다."

BLOCKED_OUTPUT_KEYS = {
    "diagnosis",
    "disease_probability",
    "dose_change_instruction",
    "medication_adjustment",
    "recommended_dose",
    "stop_medication_instruction",
    "substitute_medication",
    "treatment_recommendation",
}
BLOCKED_OUTPUT_PHRASES = (
    "감량하세요",
    "증량하세요",
    "줄이세요",
    "늘리세요",
    "중단하세요",
    "끊으세요",
    "대체하세요",
    "바꾸세요",
    "복용량을 변경",
    "용량을 변경",
    "진단됩니다",
    "치료하세요",
    "change your dose",
    "increase your dose",
    "decrease your dose",
    "stop taking",
    "switch to",
    "diagnosed with",
    "treatment recommendation",
)
DOSE_PATTERN = re.compile(
    r"(?P<dose>\d+(?:\.\d+)?\s?(?:mg|g|mcg|ug|µg|μg|iu|IU|ml|mL|정|캡슐|포|앰플))"
)
FREQUENCY_PATTERN = re.compile(
    r"(?P<frequency>(?:하루|1일|매일|daily|bid|tid|qid)[^\n,;/]{0,24})",
    re.IGNORECASE,
)
PERIOD_PATTERN = re.compile(
    r"(?P<period>\d+\s?(?:일|주|개월|days?|weeks?|months?))",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(r"(?P<date>\d{4}[./-]\d{1,2}[./-]\d{1,2})")
LAB_VALUE_PATTERN = re.compile(
    r"^(?P<name>[A-Za-z가-힣][A-Za-z0-9가-힣 ./()%+-]{0,80}?)\s+"
    r"(?P<value>[<>=]?\s?\d+(?:\.\d+)?)"
    r"(?:\s*(?P<unit>[A-Za-z%/µμ가-힣]+))?"
    r"(?:\s*(?P<reference>(?:\(?\s*(?:참고|정상|ref|reference)?[:\s]*)?"
    r"[<>=]?\d+(?:\.\d+)?\s*[-~]\s*[<>=]?\d+(?:\.\d+)?[A-Za-z%/µμ가-힣\s]*\)?))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ValidatedRegulatedImage:
    """Validated regulated document image and bounded bytes.

    Attributes:
        image_bytes: Bounded image bytes used only in request memory.
        sha256: SHA-256 hex digest of the image bytes.
        mime_type: Detected image MIME type.
        size_bytes: Uploaded image size in bytes.
        width: Decoded image width in pixels.
        height: Decoded image height in pixels.
    """

    image_bytes: bytes
    sha256: str
    mime_type: str
    size_bytes: int
    width: int
    height: int


class RegulatedImageValidationError(ValueError):
    """Raised when a regulated document image fails validation."""

    def __init__(self, *, code: str, message: str, status_code: int) -> None:
        """Initialize a safe validation error.

        Args:
            code: Stable API error code.
            message: Safe user-facing message.
            status_code: HTTP status code to return from the route.
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class RegulatedDocumentConfigurationError(RuntimeError):
    """Raised when settings request an unsupported regulated intake mode."""


class RegulatedDocumentNotFoundError(ValueError):
    """Raised when a regulated document preview is not found for the user."""


class RegulatedDocumentExpiredError(ValueError):
    """Raised when a regulated document preview is expired."""


class RegulatedDocumentStateError(ValueError):
    """Raised when a regulated document preview cannot transition state."""


class RegulatedDocumentTypeMismatchError(ValueError):
    """Raised when a confirmation payload targets the wrong document type."""


class RegulatedMedicalOutputBlockedError(ValueError):
    """Raised when a regulated response or confirmation contains prohibited advice."""


def prescription_consult_cta() -> ConsultProfessionalCTA:
    """Build the prescription consult-professional CTA.

    Returns:
        CTA that directs medication decisions to a clinician or pharmacist.
    """
    return ConsultProfessionalCTA(action="contact_clinician_or_pharmacist")


def lab_result_consult_cta() -> ConsultProfessionalCTA:
    """Build the lab result consult-professional CTA.

    Returns:
        CTA that directs lab interpretation to a clinician.
    """
    return ConsultProfessionalCTA(
        message="검사 결과 해석, 진단, 치료 판단은 담당 의료진과 상담하세요.",
        action="contact_clinician",
    )


async def create_prescription_ocr_preview(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    image: UploadFile,
    settings: Settings,
    adapters: RegulatedOCRAdapters | None = None,
) -> PrescriptionOCRPreviewResponse:
    """Create an intake-only prescription OCR preview.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        image: Uploaded prescription document image.
        settings: Runtime settings.
        adapters: Optional OCR adapter bundle.

    Returns:
        Prescription OCR preview that requires user confirmation.

    Raises:
        RegulatedDocumentConfigurationError: If raw image retention is configured.
        RegulatedImageValidationError: If the upload is invalid.
        RegulatedMedicalOutputBlockedError: If parser output contains prohibited advice.
    """
    document = await _create_regulated_ocr_preview(
        session=session,
        user=user,
        image=image,
        settings=settings,
        adapters=adapters,
        document_type=RegulatedDocumentType.PRESCRIPTION,
    )
    return regulated_document_to_prescription_preview(document)


async def create_lab_result_ocr_preview(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    image: UploadFile,
    settings: Settings,
    adapters: RegulatedOCRAdapters | None = None,
) -> LabResultOCRPreviewResponse:
    """Create an intake-only lab result OCR preview.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        image: Uploaded lab result document image.
        settings: Runtime settings.
        adapters: Optional OCR adapter bundle.

    Returns:
        Lab result OCR preview that requires user confirmation.

    Raises:
        RegulatedDocumentConfigurationError: If raw image retention is configured.
        RegulatedImageValidationError: If the upload is invalid.
        RegulatedMedicalOutputBlockedError: If parser output contains prohibited advice.
    """
    document = await _create_regulated_ocr_preview(
        session=session,
        user=user,
        image=image,
        settings=settings,
        adapters=adapters,
        document_type=RegulatedDocumentType.LAB_RESULT,
    )
    return regulated_document_to_lab_result_preview(document)


async def confirm_regulated_document(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    document_id: UUID,
    request: RegulatedDocumentConfirmRequest,
    settings: Settings,
) -> RegulatedDocumentConfirmResponse:
    """Confirm a regulated OCR preview after user review.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        document_id: Preview identifier.
        request: User-confirmed structured fields.
        settings: Runtime settings.

    Returns:
        Confirmation response.

    Raises:
        RegulatedDocumentNotFoundError: If the preview does not belong to the user.
        RegulatedDocumentExpiredError: If the preview has expired.
        RegulatedDocumentStateError: If the preview was already finalized.
        RegulatedDocumentTypeMismatchError: If payload and stored document type differ.
        RegulatedMedicalOutputBlockedError: If confirmed fields contain prohibited advice.
    """
    now = _utc_now()
    owner_subject_hash = hash_actor_subject(user, settings)
    assert_no_blocked_medical_outputs(request.model_dump(mode="json"))

    async with persist_scope(session):
        document = await session.scalar(
            select(RegulatedDocument).where(
                RegulatedDocument.id == document_id,
                RegulatedDocument.owner_subject_hash == owner_subject_hash,
            )
        )
        if document is None:
            raise RegulatedDocumentNotFoundError("Regulated OCR preview was not found.")
        if document.document_type != request.document_type.value:
            raise RegulatedDocumentTypeMismatchError(
                "Confirmation document_type does not match the preview."
            )
        if document.status != RegulatedDocumentStatus.REQUIRES_CONFIRMATION.value:
            raise RegulatedDocumentStateError("Regulated OCR preview cannot be confirmed.")
        if document.expires_at <= now:
            raise RegulatedDocumentExpiredError("Regulated OCR preview has expired.")

        if request.document_type == RegulatedDocumentType.PRESCRIPTION:
            if not request.prescription_items or request.lab_result_items:
                raise RegulatedDocumentTypeMismatchError(
                    "Prescription confirmation requires prescription_items only."
                )
            _add_confirmed_prescription_items(session, document.id, request.prescription_items)
            _add_prescription_medical_records(
                session,
                document,
                request.prescription_items,
                now,
            )
            confirmed_items = [item.model_dump(mode="json") for item in request.prescription_items]
        else:
            if not request.lab_result_items or request.prescription_items:
                raise RegulatedDocumentTypeMismatchError(
                    "Lab result confirmation requires lab_result_items only."
                )
            _add_confirmed_lab_result_items(session, document.id, request.lab_result_items)
            _add_lab_result_medical_collection(session, document)
            confirmed_items = [item.model_dump(mode="json") for item in request.lab_result_items]

        document.status = RegulatedDocumentStatus.CONFIRMED.value
        document.confirmed_at = now
        document.parsed_snapshot = {
            "confirmed_items": confirmed_items,
            "consult_professional_acknowledged": request.consult_professional_acknowledged,
            "raw_image_stored": False,
            "raw_ocr_text_stored": False,
        }

    return RegulatedDocumentConfirmResponse(
        document_id=document.id,
        document_type=RegulatedDocumentType(document.document_type),
        confirmed_at=now,
        consult_professional_cta=ConsultProfessionalCTA.model_validate(document.consult_cta),
    )


def regulated_document_to_prescription_preview(
    document: RegulatedDocument,
) -> PrescriptionOCRPreviewResponse:
    """Convert a regulated prescription document row to an API preview.

    Args:
        document: Persisted regulated document row.

    Returns:
        Prescription OCR preview response.
    """
    return PrescriptionOCRPreviewResponse(
        document_id=document.id,
        status=RegulatedDocumentStatus(document.status),
        recognized_items=[
            PrescriptionItemPreview.model_validate(item)
            for item in _snapshot_items(document.parsed_snapshot)
        ],
        warnings=_warnings_for_document(document),
        warning_codes=list(_string_items(document.warning_codes)),
        consult_professional_cta=ConsultProfessionalCTA.model_validate(document.consult_cta),
        expires_at=document.expires_at,
    )


def regulated_document_to_lab_result_preview(
    document: RegulatedDocument,
) -> LabResultOCRPreviewResponse:
    """Convert a regulated lab result document row to an API preview.

    Args:
        document: Persisted regulated document row.

    Returns:
        Lab result OCR preview response.
    """
    return LabResultOCRPreviewResponse(
        document_id=document.id,
        status=RegulatedDocumentStatus(document.status),
        recognized_items=[
            LabResultItemPreview.model_validate(item)
            for item in _snapshot_items(document.parsed_snapshot)
        ],
        warnings=_warnings_for_document(document),
        warning_codes=list(_string_items(document.warning_codes)),
        consult_professional_cta=ConsultProfessionalCTA.model_validate(document.consult_cta),
        expires_at=document.expires_at,
    )


async def _create_regulated_ocr_preview(
    *,
    session: AsyncSession,
    user: AuthenticatedUser,
    image: UploadFile,
    settings: Settings,
    adapters: RegulatedOCRAdapters | None,
    document_type: RegulatedDocumentType,
) -> RegulatedDocument:
    """Create a regulated OCR preview for one document type.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        image: Uploaded regulated document image.
        settings: Runtime settings.
        adapters: Optional OCR adapter bundle.
        document_type: Regulated document type.

    Returns:
        Persisted regulated document row.
    """
    _ensure_memory_only_raw_image_policy(settings)
    image_metadata = await read_and_validate_regulated_image(image, settings)
    ocr_result, warning_codes = await _extract_ocr_text(
        image_metadata=image_metadata,
        adapter=adapters.ocr if adapters else None,
    )
    raw_ocr_text = ocr_result.text if ocr_result else ""
    confidence = ocr_result.confidence if ocr_result else None
    if document_type == RegulatedDocumentType.PRESCRIPTION:
        recognized_items = [
            item.model_dump(mode="json")
            for item in parse_prescription_ocr_text(raw_ocr_text, confidence=confidence)
        ]
        consult_cta = prescription_consult_cta()
    else:
        recognized_items = [
            item.model_dump(mode="json")
            for item in parse_lab_result_ocr_text(raw_ocr_text, confidence=confidence)
        ]
        consult_cta = lab_result_consult_cta()
    assert_no_blocked_medical_outputs(recognized_items)

    now = _utc_now()
    document = RegulatedDocument(
        id=uuid4(),
        owner_subject_hash=hash_actor_subject(user, settings),
        document_type=document_type.value,
        status=RegulatedDocumentStatus.REQUIRES_CONFIRMATION.value,
        image_sha256=image_metadata.sha256,
        image_mime_type=image_metadata.mime_type,
        image_size_bytes=image_metadata.size_bytes,
        ocr_provider=ocr_result.provider if ocr_result else REGULATED_INTAKE_PROVIDER,
        ocr_confidence=Decimal(str(confidence)) if confidence is not None else None,
        ocr_text_hash=(
            hashlib.sha256(raw_ocr_text.encode("utf-8")).hexdigest()
            if raw_ocr_text.strip()
            else None
        ),
        parsed_snapshot={
            "recognized_items": recognized_items,
            "raw_image_stored": False,
            "raw_ocr_text_stored": False,
        },
        warning_codes=warning_codes,
        consult_cta=consult_cta.model_dump(mode="json"),
        algorithm_version=REGULATED_INTAKE_ALGORITHM_VERSION,
        raw_image_deleted_at=now,
        expires_at=now + timedelta(minutes=settings.regulated_document_preview_ttl_minutes),
        confirmed_at=None,
    )
    async with persist_scope(session):
        session.add(document)
        await session.flush()
        await session.refresh(document)
    return document


async def read_and_validate_regulated_image(
    image: UploadFile,
    settings: Settings,
) -> ValidatedRegulatedImage:
    """Read, bound, hash, and validate a regulated document image.

    Args:
        image: Uploaded document image.
        settings: Runtime settings containing upload limits.

    Returns:
        Validated image metadata with request-memory bytes.

    Raises:
        RegulatedImageValidationError: If the upload is empty, too large, spoofed,
            unsupported, or not a valid image.
    """
    data = await _read_limited_upload(image, settings.supplement_image_max_bytes)
    content_type = image.content_type
    detected_mime = detect_regulated_image_mime(data[:16])

    if not data:
        raise RegulatedImageValidationError(
            code="invalid_image",
            message="Uploaded regulated document image is empty.",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )
    if content_type not in REGULATED_ALLOWED_IMAGE_MIME_TYPES or detected_mime is None:
        raise RegulatedImageValidationError(
            code="unsupported_media_type",
            message="Only JPEG, PNG, and WebP document images are accepted.",
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        )
    if content_type != detected_mime:
        raise RegulatedImageValidationError(
            code="unsupported_media_type",
            message="Uploaded document image content does not match its declared media type.",
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        )

    width, height = _validate_decodable_image(data, settings.supplement_image_max_pixels)

    try:
        sanitized = strip_image_metadata(data, detected_mime)
    except ImageSafetyError as exc:
        raise RegulatedImageValidationError(
            code="invalid_image",
            message="Uploaded regulated document image cannot be normalized.",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        ) from exc

    return ValidatedRegulatedImage(
        image_bytes=sanitized,
        sha256=hashlib.sha256(sanitized).hexdigest(),
        mime_type=detected_mime,
        size_bytes=len(sanitized),
        width=width,
        height=height,
    )


def detect_regulated_image_mime(data: bytes) -> str | None:
    """Detect supported regulated document image MIME type from magic bytes.

    Args:
        data: Beginning or full image bytes.

    Returns:
        Detected MIME type, or None when unsupported.
    """
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= WEBP_HEADER_MIN_BYTES and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def parse_prescription_ocr_text(
    ocr_text: str,
    *,
    confidence: float | None,
) -> list[PrescriptionItemPreview]:
    """Parse visible OCR text into prescription preview fields.

    Args:
        ocr_text: OCR text used only for in-memory parsing.
        confidence: Provider confidence propagated to preview items.

    Returns:
        Bounded prescription preview items.
    """
    items: list[PrescriptionItemPreview] = []
    for line in _bounded_ocr_lines(ocr_text):
        medication_name = _extract_medication_name(line)
        if not medication_name:
            continue
        items.append(
            PrescriptionItemPreview(
                medication_name_text=medication_name,
                dose_text=_regex_group(DOSE_PATTERN, line, "dose"),
                frequency_text=_regex_group(FREQUENCY_PATTERN, line, "frequency"),
                period_text=_regex_group(PERIOD_PATTERN, line, "period"),
                prescribed_date_text=_regex_group(DATE_PATTERN, line, "date"),
                confidence=confidence,
            )
        )
        if len(items) >= MAX_PREVIEW_ITEMS:
            break
    return items


def parse_lab_result_ocr_text(
    ocr_text: str,
    *,
    confidence: float | None,
) -> list[LabResultItemPreview]:
    """Parse visible OCR text into lab result preview fields.

    Args:
        ocr_text: OCR text used only for in-memory parsing.
        confidence: Provider confidence propagated to preview items.

    Returns:
        Bounded lab result preview items.
    """
    items: list[LabResultItemPreview] = []
    for line in _bounded_ocr_lines(ocr_text):
        match = LAB_VALUE_PATTERN.search(line)
        if match:
            item = LabResultItemPreview(
                test_name_text=_bounded_text(match.group("name"), 160),
                value_text=_bounded_text(match.group("value"), 80),
                unit_text=_bounded_text(match.group("unit"), 40),
                reference_range_text=_bounded_text(match.group("reference"), 120),
                measured_at_text=_regex_group(DATE_PATTERN, line, "date"),
                confidence=confidence,
            )
        else:
            item = LabResultItemPreview(
                test_name_text=_bounded_text(line, 160),
                measured_at_text=_regex_group(DATE_PATTERN, line, "date"),
                confidence=confidence,
            )
        if item.test_name_text:
            items.append(item)
        if len(items) >= MAX_PREVIEW_ITEMS:
            break
    return items


def assert_no_blocked_medical_outputs(value: Any) -> None:
    """Reject direct diagnosis, treatment, or medication adjustment content.

    Args:
        value: Nested candidate output to inspect.

    Raises:
        RegulatedMedicalOutputBlockedError: If blocked keys or phrases are present.
    """
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if key.lower() in BLOCKED_OUTPUT_KEYS:
                raise RegulatedMedicalOutputBlockedError(f"Blocked regulated output key: {key}.")
            assert_no_blocked_medical_outputs(nested_value)
        return
    if isinstance(value, list):
        for item in value:
            assert_no_blocked_medical_outputs(item)
        return
    if isinstance(value, str):
        lowered = value.lower()
        if any(phrase.lower() in lowered for phrase in BLOCKED_OUTPUT_PHRASES):
            raise RegulatedMedicalOutputBlockedError(
                "Direct diagnosis, treatment, or medication dose-change guidance is not allowed."
            )


async def _extract_ocr_text(
    *,
    image_metadata: ValidatedRegulatedImage,
    adapter: OCRAdapter | None,
) -> tuple[OCRResult | None, list[str]]:
    """Extract OCR text when an adapter is configured.

    Args:
        image_metadata: Validated image and metadata.
        adapter: Optional OCR adapter.

    Returns:
        OCR result plus stable warning codes.
    """
    if adapter is None:
        return None, [AUTOMATIC_OCR_UNAVAILABLE_CODE]
    try:
        result = await adapter.extract_text(
            OCRImageInput(
                image_bytes=image_metadata.image_bytes,
                mime_type=image_metadata.mime_type,
                width=image_metadata.width,
                height=image_metadata.height,
                label_region=None,
            )
        )
    except OCRError:
        return None, [OCR_PROVIDER_FAILED_CODE]
    if not result.text.strip():
        return result, [OCR_TEXT_EMPTY_CODE]
    return result, []


def _ensure_memory_only_raw_image_policy(settings: Settings) -> None:
    """Reject unsupported raw regulated image retention modes.

    Args:
        settings: Runtime settings.

    Raises:
        RegulatedDocumentConfigurationError: If raw image retention is greater than zero.
    """
    if settings.sensitive_document_original_image_retention_seconds > 0:
        raise RegulatedDocumentConfigurationError(
            "Raw regulated document image retention is not implemented in this MVP."
        )


async def _read_limited_upload(image: UploadFile, max_bytes: int) -> bytes:
    """Read an uploaded file while enforcing a byte limit.

    Args:
        image: Uploaded file.
        max_bytes: Maximum accepted byte count.

    Returns:
        Uploaded bytes.

    Raises:
        RegulatedImageValidationError: If the upload exceeds the size limit.
    """
    chunks: list[bytes] = []
    total_size = 0
    while True:
        chunk = await image.read(READ_CHUNK_SIZE_BYTES)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_bytes:
            raise RegulatedImageValidationError(
                code="payload_too_large",
                message="Uploaded document image exceeds the configured size limit.",
                status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _validate_decodable_image(data: bytes, max_pixels: int) -> tuple[int, int]:
    """Verify image structure and pixel bounds without persisting image bytes.

    Args:
        data: Uploaded image bytes.
        max_pixels: Maximum accepted pixel count.

    Returns:
        Image width and height.

    Raises:
        RegulatedImageValidationError: If the image is malformed or too large.
    """
    try:
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
            if width <= 0 or height <= 0:
                raise RegulatedImageValidationError(
                    code="invalid_image",
                    message="Uploaded document image has invalid dimensions.",
                    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                )
            if width * height > max_pixels:
                raise RegulatedImageValidationError(
                    code="payload_too_large",
                    message="Uploaded document image exceeds the configured pixel limit.",
                    status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                )
            image.verify()
    except RegulatedImageValidationError:
        raise
    except Image.DecompressionBombError as exc:
        raise RegulatedImageValidationError(
            code="payload_too_large",
            message="Uploaded document image exceeds the configured pixel limit.",
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        ) from exc
    except (OSError, UnidentifiedImageError) as exc:
        raise RegulatedImageValidationError(
            code="invalid_image",
            message="Uploaded document image cannot be decoded.",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        ) from exc

    try:
        with safe_load_with_bomb_guard(data) as decoded:
            width, height = decoded.size
            return int(width), int(height)
    except ImageSafetyError as exc:
        raise RegulatedImageValidationError(
            code="payload_too_large",
            message="Uploaded document image is too large to decode safely.",
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        ) from exc


def _add_confirmed_prescription_items(
    session: AsyncSession,
    document_id: UUID,
    items: list[PrescriptionItemConfirm],
) -> None:
    """Add user-confirmed prescription items to the session.

    Args:
        session: Request-scoped async database session.
        document_id: Source regulated document identifier.
        items: User-confirmed prescription items.
    """
    for sort_order, item in enumerate(items):
        session.add(
            PrescriptionItem(
                document_id=document_id,
                medication_name_text=item.medication_name_text,
                dose_text=item.dose_text,
                frequency_text=item.frequency_text,
                period_text=item.period_text,
                route_text=item.route_text,
                prescribed_date_text=item.prescribed_date_text,
                confidence=Decimal(str(item.confidence)),
                source=item.source,
                sort_order=sort_order,
            )
        )


def _add_confirmed_lab_result_items(
    session: AsyncSession,
    document_id: UUID,
    items: list[LabResultItemConfirm],
) -> None:
    """Add user-confirmed lab result items to the session.

    Args:
        session: Request-scoped async database session.
        document_id: Source regulated document identifier.
        items: User-confirmed lab result items.
    """
    for sort_order, item in enumerate(items):
        session.add(
            LabResultItem(
                document_id=document_id,
                test_name_text=item.test_name_text,
                value_text=item.value_text,
                unit_text=item.unit_text,
                reference_range_text=item.reference_range_text,
                measured_at_text=item.measured_at_text,
                confidence=Decimal(str(item.confidence)),
                source=item.source,
                sort_order=sort_order,
            )
        )


def _add_prescription_medical_records(
    session: AsyncSession,
    document: RegulatedDocument,
    items: list[PrescriptionItemConfirm],
    confirmed_at: datetime,
) -> None:
    """Add longitudinal medication records from confirmed prescription fields.

    Args:
        session: Request-scoped async database session.
        document: Confirmed regulated document source.
        items: User-confirmed prescription items.
        confirmed_at: Confirmation timestamp.
    """
    for item in items:
        collection = _medical_collection_for_regulated_document(document, "prescription")
        session.add(collection)
        session.add(
            PatientMedication(
                medical_collection_id=collection.id,
                medication_name_text=item.medication_name_text,
                dose_text=item.dose_text,
                frequency_text=item.frequency_text,
                route_text=item.route_text,
                period_text=item.period_text,
                active_status="active",
                source_document_id=document.id,
                confirmed_at=confirmed_at,
            )
        )


def _add_lab_result_medical_collection(
    session: AsyncSession,
    document: RegulatedDocument,
) -> None:
    """Add a longitudinal lab-result collection from a confirmed lab document.

    Args:
        session: Request-scoped async database session.
        document: Confirmed regulated document source.
    """
    session.add(_medical_collection_for_regulated_document(document, "lab_result"))


def _medical_collection_for_regulated_document(
    document: RegulatedDocument,
    record_type: str,
) -> MedicalRecordCollection:
    """Build a user-confirmed medical collection linked to a regulated document.

    Args:
        document: Source regulated document.
        record_type: Medical record type to create.

    Returns:
        Medical record collection row with no raw document content.
    """
    return MedicalRecordCollection(
        id=uuid4(),
        owner_subject_hash=document.owner_subject_hash,
        record_type=record_type,
        source="regulated_ocr_confirmed",
        source_document_id=document.id,
        status="active",
        consent_snapshot={
            "consent_type": "sensitive_health_analysis",
            "source": "regulated_ocr_confirmed",
        },
    )


def _bounded_ocr_lines(ocr_text: str) -> list[str]:
    """Return bounded non-empty OCR lines for in-memory parsing.

    Args:
        ocr_text: Raw OCR text held only in request memory.

    Returns:
        Bounded, stripped lines.
    """
    normalized = ocr_text[:MAX_OCR_PARSE_CHARS]
    lines = []
    for raw_line in normalized.splitlines():
        line = " ".join(raw_line.strip().split())
        if line:
            lines.append(line)
    return lines[:MAX_PREVIEW_ITEMS]


def _extract_medication_name(line: str) -> str | None:
    """Extract a conservative medication-name candidate from one OCR line.

    Args:
        line: Bounded OCR line.

    Returns:
        Medication name candidate, or None when the line is not useful.
    """
    earliest_match_start = len(line)
    for pattern in (DOSE_PATTERN, FREQUENCY_PATTERN, PERIOD_PATTERN, DATE_PATTERN):
        match = pattern.search(line)
        if match:
            earliest_match_start = min(earliest_match_start, match.start())
    candidate = line[:earliest_match_start].strip(" -:/,")
    if not candidate:
        candidate = line.strip(" -:/,")
    return _bounded_text(candidate, 160)


def _regex_group(pattern: re.Pattern[str], text: str, group_name: str) -> str | None:
    """Return a bounded regex named group from text.

    Args:
        pattern: Compiled regex pattern.
        text: Text to inspect.
        group_name: Named group to return.

    Returns:
        Trimmed match group or None.
    """
    match = pattern.search(text)
    if not match:
        return None
    return _bounded_text(match.group(group_name), 120)


def _bounded_text(value: str | None, max_length: int) -> str | None:
    """Normalize and bound optional text.

    Args:
        value: Candidate text.
        max_length: Maximum returned character count.

    Returns:
        Trimmed text or None.
    """
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    if not normalized:
        return None
    return normalized[:max_length]


def _snapshot_items(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Return recognized item dictionaries from a persisted snapshot.

    Args:
        snapshot: Regulated document parsed snapshot.

    Returns:
        Recognized item dictionaries.
    """
    items = snapshot.get("recognized_items") if isinstance(snapshot, dict) else None
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _warnings_for_document(document: RegulatedDocument) -> list[str]:
    """Build safe warnings for a regulated preview response.

    Args:
        document: Persisted regulated document row.

    Returns:
        Warning messages without raw OCR text.
    """
    warnings = [
        (
            LAB_REQUIRES_CONFIRMATION_WARNING
            if document.document_type == RegulatedDocumentType.LAB_RESULT.value
            else REQUIRES_CONFIRMATION_WARNING
        )
    ]
    warning_by_code = {
        AUTOMATIC_OCR_UNAVAILABLE_CODE: AUTOMATIC_OCR_UNAVAILABLE_WARNING,
        OCR_TEXT_EMPTY_CODE: OCR_TEXT_EMPTY_WARNING,
        OCR_PROVIDER_FAILED_CODE: OCR_PROVIDER_FAILED_WARNING,
    }
    warnings.extend(
        warning_by_code[code]
        for code in _string_items(document.warning_codes)
        if code in warning_by_code
    )
    return warnings


def _string_items(value: Any) -> list[str]:
    """Return string items from a candidate list.

    Args:
        value: Candidate list value.

    Returns:
        String items only.
    """
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _utc_now() -> datetime:
    """Return current UTC timestamp.

    Returns:
        Timezone-aware current datetime.
    """
    return datetime.now(UTC)
