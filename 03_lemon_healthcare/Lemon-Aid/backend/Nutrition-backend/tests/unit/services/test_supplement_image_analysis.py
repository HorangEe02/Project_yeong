"""Supplement image analysis orchestration service tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from io import BytesIO
from typing import Self, cast
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile
from PIL import Image
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.config import Settings
from src.learning.object_storage import (
    LearningImageObjectInput,
    LearningImageObjectStore,
    StoredLearningImage,
)
from src.llm.ollama_vision import (
    OllamaVisionStructuredExtractionResult,
    OllamaVisionTextVerificationResult,
)
from src.models.db.learning import LearningImageObject
from src.models.db.retraining import AnnotationTask
from src.models.db.supplement import SupplementAnalysisRun
from src.models.schemas.privacy import ConsentType
from src.models.schemas.supplement_parser import SupplementStructuredParseResult
from src.ocr.base import (
    OCRAdapter,
    OCRBlock,
    OCRBoundingPoly,
    OCRImageInput,
    OCRPage,
    OCRParagraph,
    OCRResult,
    OCRVertex,
    OCRWord,
)
from src.parsing.layout_parser import parse_label_layout
from src.security.auth import AuthenticatedUser
from src.services import supplement_image_analysis
from src.services.supplement_image_analysis import (
    OCR_PARSE_PREVIEW_UNAVAILABLE_CODE,
    OCR_VERIFICATION_MISMATCH_CODE,
    SUPPLEMENT_FACTS_REQUIRED_CODE,
    SupplementImageAnalysisAdapters,
    SupplementLearningArtifactsInput,
    SupplementLearningEmbeddingInput,
    _merge_vision_amounts_into_snapshot,
    analyze_supplement_image,
    store_supplement_learning_artifacts,
    store_supplement_learning_embedding_job,
)
from src.services.supplement_intake import (
    ValidatedSupplementImage,
    supplement_analysis_run_to_preview,
)
from src.vision.base import BoundingBox, VisionAdapter, VisionError
from starlette.datastructures import Headers


@pytest.fixture(autouse=True)
def _isolate_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make these settings hermetic: ignore a developer's local PROJECT_ROOT/.env.

    These tests build ``Settings(...)`` directly and assert *default* OCR-ensemble /
    multimodal behavior. A live local ``.env`` (e.g. the OCR-ensemble activation
    ``OCR_SECONDARY_MERGE_POLICY=always`` + ``ENABLE_MULTIMODAL_*=true``) is read by
    pydantic-settings for any field the test leaves unset, flipping those defaults
    and breaking the assertions locally. CI has no ``.env`` so this only neutralizes
    local leakage; explicit ``Settings(field=...)`` init args still take precedence.
    """
    monkeypatch.setitem(Settings.model_config, "env_file", None)


class _TransactionContext:
    """Async context manager used by the fake session transaction."""

    async def __aenter__(self) -> Self:
        """Enter the fake transaction.

        Returns:
            Context manager instance.
        """
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Exit the fake transaction.

        Args:
            *_exc_info: Exception information ignored by the fake context.

        Returns:
            None.
        """


class _FakePipelineSession:
    """Fake async session for image analysis orchestration tests."""

    def __init__(self) -> None:
        self.added_analysis: SupplementAnalysisRun | None = None
        self.added_records: list[object] = []
        self.existing_learning_object: LearningImageObject | None = None
        self.existing_annotation_task: AnnotationTask | None = None
        self.committed = False
        self.commits = 0
        self.refresh_count = 0
        # A real AsyncSession always exposes ``.info``; persist_scope reads it.
        self.info: dict[str, object] = {}

    async def flush(self) -> None:
        """No-op flush (persist_scope flushes pending writes)."""

    async def rollback(self) -> None:
        """No-op rollback (persist_scope own-mode rolls back on exception)."""

    def begin(self) -> _TransactionContext:
        """Return a fake transaction context.

        Returns:
            Fake transaction context.
        """
        return _TransactionContext()

    async def scalar(self, _statement: object) -> object | None:
        """Return the stored analysis row for parser lookup.

        Args:
            _statement: SQLAlchemy select statement.

        Returns:
            Stored analysis row.
        """
        entity = _selected_entity(_statement)
        if entity is LearningImageObject:
            return self.existing_learning_object
        if entity is AnnotationTask:
            return self.existing_annotation_task
        return self.added_analysis

    async def get(self, _entity: object, _ident: object) -> object | None:
        """Return the stored analysis row for a primary-key lookup.

        Args:
            _entity: ORM entity class requested.
            _ident: Primary-key identity requested.

        Returns:
            Stored analysis row (used by the post-commit learning helper).
        """
        return self.added_analysis

    def add(self, record: object) -> None:
        """Capture the ORM record being added.

        Args:
            record: ORM object passed by the service.

        Returns:
            None.
        """
        self.added_records.append(record)
        if isinstance(record, SupplementAnalysisRun):
            self.added_analysis = record

    async def refresh(self, record: object) -> None:
        """Populate server-generated fields after fake persistence.

        Args:
            record: ORM object to refresh.

        Returns:
            None.
        """
        if (
            isinstance(record, SupplementAnalysisRun | LearningImageObject | AnnotationTask)
            and record.id is None
        ):
            record.id = uuid4()
        if isinstance(record, SupplementAnalysisRun):
            record.created_at = datetime.now(UTC)
            record.updated_at = datetime.now(UTC)
        self.refresh_count += 1

    async def commit(self) -> None:
        """Record a parser commit.

        Returns:
            None.
        """
        self.committed = True
        self.commits += 1


def _selected_entity(statement: object) -> type[object] | None:
    """Return the ORM entity selected by a SQLAlchemy statement fixture."""
    descriptions = getattr(statement, "column_descriptions", None)
    if not descriptions:
        return None
    entity = descriptions[0].get("entity")
    return cast(type[object] | None, entity)


class _FakeLearningImageObjectStore(LearningImageObjectStore):
    """Fake learning image store that records put requests without filesystem IO."""

    def __init__(self) -> None:
        self.put_payload: LearningImageObjectInput | None = None
        self.deleted: list[tuple[str, str | None]] = []

    async def put_image(self, payload: LearningImageObjectInput) -> StoredLearningImage:
        """Capture one retained image payload.

        Args:
            payload: Validated learning image payload.

        Returns:
            Fake private object reference.
        """
        self.put_payload = payload
        return StoredLearningImage(object_uri="local://unit/learning-image.png", provider="local")

    async def get_image(self, object_uri: str, version_id: str | None = None) -> bytes:
        """Return fake image bytes for interface completeness."""
        _ = (object_uri, version_id)
        return b"image"

    async def delete_image(self, object_uri: str, version_id: str | None = None) -> None:
        """Record deleted fake image references.

        Args:
            object_uri: Fake object URI.
            version_id: Optional fake version id.
        """
        self.deleted.append((object_uri, version_id))


class _FakeSessionContext:
    """Async context manager yielding a pre-built fake session."""

    def __init__(self, session: _FakePipelineSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakePipelineSession:
        """Return the wrapped fake session."""
        return self._session

    async def __aexit__(self, *_exc_info: object) -> bool:
        """Exit without suppressing exceptions."""
        return False


class _FakeSessionFactory:
    """Callable session factory returning one fixed fake session per call.

    Mirrors the ``async_sessionmaker`` call shape used by the post-commit
    learning helper (``async with factory() as session``) without a real engine.
    """

    def __init__(self, session: _FakePipelineSession) -> None:
        self._session = session

    def __call__(self) -> _FakeSessionContext:
        """Return a fresh async context wrapping the fixed fake session."""
        return _FakeSessionContext(self._session)


class _FakeOCRAdapter(OCRAdapter):
    """Fake OCR adapter returning configured text."""

    def __init__(
        self,
        text: str,
        *,
        confidence: float | None = 0.88,
        pages: tuple[OCRPage, ...] = (),
    ) -> None:
        self.text = text
        self.confidence = confidence
        self.pages = pages
        self.received_image: OCRImageInput | None = None
        self.received_images: list[OCRImageInput] = []
        self.call_count = 0

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Capture image input and return fake OCR text.

        Args:
            image: OCR image input.

        Returns:
            Fake OCR result.
        """
        self.call_count += 1
        self.received_image = image
        self.received_images.append(image)
        return OCRResult(
            text=self.text,
            provider="fake-ocr",
            confidence=self.confidence,
            pages=self.pages,
        )


class _SequenceOCRAdapter(OCRAdapter):
    """Fake OCR adapter returning one configured result per call."""

    def __init__(self, results: list[OCRResult]) -> None:
        self.results = results
        self.received_images: list[OCRImageInput] = []

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Capture each OCR input and return the matching configured result.

        Args:
            image: OCR image input.

        Returns:
            Configured OCR result for the call index.
        """
        self.received_images.append(image)
        index = min(len(self.received_images) - 1, len(self.results) - 1)
        return self.results[index]


class _FakeVisionAdapter(VisionAdapter):
    """Fake vision adapter returning a configured ROI."""

    def __init__(
        self,
        region: BoundingBox | None = None,
        *,
        regions: list[BoundingBox] | None = None,
        fail: bool = False,
    ) -> None:
        self.region = region or BoundingBox(
            x=0,
            y=0,
            width=2,
            height=2,
            confidence=0.9,
            label="supplement_label",
        )
        self.regions = regions
        self.fail = fail
        self.call_count = 0

    async def detect_label_region(self, image_bytes: bytes) -> BoundingBox:
        """Capture detector calls and return or raise a fake ROI.

        Args:
            image_bytes: Validated image bytes.

        Returns:
            Configured ROI.

        Raises:
            VisionError: When configured to fail.
        """
        self.call_count += 1
        if self.fail:
            raise VisionError("fake detector failure")
        assert image_bytes
        return self.region

    async def detect_regions(self, image_bytes: bytes) -> list[BoundingBox]:
        """Return configured detector regions.

        Args:
            image_bytes: Validated image bytes.

        Returns:
            Configured ROI list.

        Raises:
            VisionError: When configured to fail.
        """
        self.call_count += 1
        if self.fail:
            raise VisionError("fake detector failure")
        assert image_bytes
        return self.regions or [self.region]


class _FakeMultimodalOCRAdapter(OCRAdapter):
    """Fake local vision LLM OCR fallback adapter."""

    def __init__(self, text: str = "비타민 D 1000") -> None:
        self.text = text
        self.received_image: OCRImageInput | None = None
        self.call_count = 0

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Capture fallback input and return configured candidate text.

        Args:
            image: OCR image input with optional ROI.

        Returns:
            Fake OCR-like result.
        """
        self.call_count += 1
        self.received_image = image
        return OCRResult(text=self.text, provider="ollama_vision_assist", confidence=None)


class _FakeMultimodalVerifierAdapter(_FakeMultimodalOCRAdapter):
    """Fake local vision LLM adapter with structured verification support."""

    def __init__(
        self,
        verification: OllamaVisionTextVerificationResult,
        text: str = "비타민 D 1000",
    ) -> None:
        super().__init__(text)
        self.verification = verification
        self.verify_call_count = 0
        self.received_verification_text: str | None = None
        self.received_verification_image: OCRImageInput | None = None

    async def verify_text(
        self,
        image: OCRImageInput,
        text: str,
    ) -> OllamaVisionTextVerificationResult:
        """Capture verification input and return the configured result.

        Args:
            image: OCR image input used for local vision verification.
            text: OCR text selected by the pipeline.

        Returns:
            Configured verification result.
        """
        self.verify_call_count += 1
        self.received_verification_text = text
        self.received_verification_image = image
        return self.verification


class _FakeParser:
    """Fake structured parser for OCR text."""

    def __init__(self, result: SupplementStructuredParseResult) -> None:
        self.result = result
        self.received_text: str | None = None

    async def parse_supplement_ocr_text(
        self,
        ocr_text: str,
    ) -> SupplementStructuredParseResult:
        """Capture OCR text and return a configured parser result.

        Args:
            ocr_text: OCR text passed by the service.

        Returns:
            Configured structured parse result.
        """
        self.received_text = ocr_text
        return self.result


def _settings() -> Settings:
    """Return service test settings.

    Returns:
        Settings object.
    """
    return Settings(privacy_hash_secret=SecretStr("test-privacy-secret"))


def _user() -> AuthenticatedUser:
    """Return an authenticated user fixture.

    Returns:
        Authenticated user model.
    """
    return AuthenticatedUser(
        subject="user_123",
        issuer="https://auth.example.com/",
        claims={"sub": "user_123"},
    )


def _png_bytes() -> bytes:
    """Return a tiny PNG image.

    Returns:
        PNG image bytes.
    """
    buffer = BytesIO()
    Image.new("RGB", (3, 2), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(data: bytes) -> UploadFile:
    """Build an UploadFile for service tests.

    Args:
        data: File bytes.

    Returns:
        UploadFile object.
    """
    return UploadFile(
        file=BytesIO(data),
        filename="label.png",
        headers=Headers({"content-type": "image/png"}),
    )


def _validated_image() -> ValidatedSupplementImage:
    """Return validated image metadata for post-commit helper tests.

    Returns:
        Minimal validated supplement image metadata fixture.
    """
    return ValidatedSupplementImage(
        sha256="0" * 64,
        mime_type="image/png",
        size_bytes=64,
        width=3,
        height=2,
    )


def _parse_result() -> SupplementStructuredParseResult:
    """Return a valid structured parser result.

    Returns:
        Structured supplement parse result fixture.
    """
    return SupplementStructuredParseResult.model_validate(
        {
            "parsed_product": {"product_name": "비타민 D 1000"},
            "ingredient_candidates": [
                {
                    "display_name": "비타민 D",
                    "amount": 25,
                    "unit": "ug",
                    "confidence": 0.91,
                }
            ],
            "intake_method": {
                "text": "하루 1회 1캡슐",
                "confidence": 0.86,
                "evidence_refs": ["intake-1"],
            },
            "precautions": [
                {
                    "text": "임신 중이면 전문가와 상담하세요.",
                    "category": "pregnancy",
                    "severity": "warning",
                    "confidence": 0.84,
                    "evidence_refs": ["precaution-1"],
                }
            ],
            "low_confidence_fields": [],
            "warnings": [],
        }
    )


def _learning_image_object(*, object_id: UUID | None = None) -> LearningImageObject:
    """Return a consent-retained learning image fixture."""
    now = datetime.now(UTC)
    return LearningImageObject(
        id=object_id or uuid4(),
        owner_subject_hash="a" * 64,
        analysis_id=uuid4(),
        image_sha256="b" * 64,
        object_uri="local://unit/learning-image.png",
        object_storage_provider="local",
        image_mime_type="image/png",
        image_size_bytes=77,
        retained_until=now,
        status="awaiting_confirmation",
        consent_snapshot={"consents": ["ocr_image_processing"]},
    )


def _verification_result(
    *,
    status: str = "match",
    confidence: float = 0.96,
    missing_sections: list[str] | None = None,
) -> OllamaVisionTextVerificationResult:
    """Return a structured local vision verification fixture.

    Args:
        status: Verification status.
        confidence: Verification confidence.
        missing_sections: Required sections reported missing.

    Returns:
        Validated verification result.
    """
    return OllamaVisionTextVerificationResult.model_validate(
        {
            "verification_status": status,
            "confidence": confidence,
            "source_region": "full_image",
            "matched_fragments": ["비타민 D 1000"],
            "missing_fragments": [],
            "missing_critical_sections": missing_sections or [],
            "warnings": [],
        }
    )


def _front_label_parse_result() -> SupplementStructuredParseResult:
    """Return a parse result with product identity but no ingredient evidence.

    Returns:
        Structured parse result for a front-label-only OCR case.
    """
    return SupplementStructuredParseResult.model_validate(
        {
            "parsed_product": {"product_name": "레몬 비타민 D"},
            "ingredient_candidates": [],
            "missing_required_sections": [],
            "low_confidence_fields": [],
            "warnings": [],
        }
    )


def _ocr_page() -> OCRPage:
    """Return coordinate-bearing OCR words for deterministic layout parsing."""
    words = (
        _ocr_word("Supplement", 10, 10, 110, 40, 0, 0.92),
        _ocr_word("Facts", 120, 10, 190, 40, 1, 0.91),
        _ocr_word("Vitamin", 10, 50, 90, 80, 2, 0.9),
        _ocr_word("D", 100, 50, 115, 80, 3, 0.9),
        _ocr_word("25", 170, 50, 200, 80, 4, 0.88),
        _ocr_word("ug", 205, 50, 230, 80, 5, 0.88),
        _ocr_word("섭취방법", 10, 100, 90, 130, 6, 0.87),
        _ocr_word("1일", 110, 100, 145, 130, 7, 0.86),
        _ocr_word("1정", 155, 100, 190, 130, 8, 0.86),
    )
    paragraph = OCRParagraph(
        text=" ".join(word.text for word in words),
        confidence=0.89,
        bounding_box=None,
        words=words,
    )
    block = OCRBlock(
        text=paragraph.text,
        confidence=0.89,
        bounding_box=None,
        block_type="TEXT",
        paragraphs=(paragraph,),
    )
    return OCRPage(width=300, height=200, confidence=0.89, blocks=(block,))


def _ocr_warning_page() -> OCRPage:
    """Return OCR words for deterministic warning/precaution layout parsing."""
    words = (
        _ocr_word("Warning", 10, 10, 105, 40, 0, 0.91),
        _ocr_word("Allergy", 10, 50, 95, 80, 1, 0.9),
        _ocr_word("Information", 105, 50, 210, 80, 2, 0.89),
        _ocr_word("Contains", 10, 90, 95, 120, 3, 0.89),
        _ocr_word("soy.", 105, 90, 150, 120, 4, 0.89),
        _ocr_word("If", 10, 130, 30, 160, 5, 0.88),
        _ocr_word("pregnant,", 40, 130, 125, 160, 6, 0.88),
        _ocr_word("consult", 135, 130, 205, 160, 7, 0.88),
        _ocr_word("doctor.", 215, 130, 285, 160, 8, 0.88),
    )
    paragraph = OCRParagraph(
        text=" ".join(word.text for word in words),
        confidence=0.89,
        bounding_box=None,
        words=words,
    )
    block = OCRBlock(
        text=paragraph.text,
        confidence=0.89,
        bounding_box=None,
        block_type="TEXT",
        paragraphs=(paragraph,),
    )
    return OCRPage(width=300, height=200, confidence=0.89, blocks=(block,))


def _ocr_contains_allergen_page() -> OCRPage:
    """Return OCR words where the ROI starts directly at an allergen statement."""
    words = (
        _ocr_word("Contains", 10, 10, 95, 40, 0, 0.9),
        _ocr_word("soy", 105, 10, 140, 40, 1, 0.9),
        _ocr_word("and", 150, 10, 185, 40, 2, 0.89),
        _ocr_word("milk.", 195, 10, 245, 40, 3, 0.89),
        _ocr_word("Consult", 10, 50, 85, 80, 4, 0.88),
        _ocr_word("doctor", 95, 50, 160, 80, 5, 0.88),
        _ocr_word("before", 170, 50, 235, 80, 6, 0.88),
        _ocr_word("use.", 245, 50, 290, 80, 7, 0.88),
    )
    paragraph = OCRParagraph(
        text=" ".join(word.text for word in words),
        confidence=0.89,
        bounding_box=None,
        words=words,
    )
    block = OCRBlock(
        text=paragraph.text,
        confidence=0.89,
        bounding_box=None,
        block_type="TEXT",
        paragraphs=(paragraph,),
    )
    return OCRPage(width=320, height=120, confidence=0.89, blocks=(block,))


def _ocr_contains_soybean_tree_nut_page() -> OCRPage:
    """Return OCR words for allergen wording that lacks a warning heading."""
    words = (
        _ocr_word("Contains", 10, 10, 95, 40, 0, 0.9),
        _ocr_word("soybean", 105, 10, 175, 40, 1, 0.9),
        _ocr_word("and", 185, 10, 220, 40, 2, 0.89),
        _ocr_word("tree", 230, 10, 270, 40, 3, 0.89),
        _ocr_word("nuts.", 280, 10, 330, 40, 4, 0.89),
    )
    paragraph = OCRParagraph(
        text=" ".join(word.text for word in words),
        confidence=0.89,
        bounding_box=None,
        words=words,
    )
    block = OCRBlock(
        text=paragraph.text,
        confidence=0.89,
        bounding_box=None,
        block_type="TEXT",
        paragraphs=(paragraph,),
    )
    return OCRPage(width=360, height=70, confidence=0.89, blocks=(block,))


def _ocr_word(
    text: str,
    left: float,
    top: float,
    right: float,
    bottom: float,
    word_index: int,
    confidence: float,
) -> OCRWord:
    """Return one OCR word with a rectangular bounding polygon."""
    return OCRWord(
        text=text,
        confidence=confidence,
        bounding_box=OCRBoundingPoly(
            vertices=(
                OCRVertex(x=left, y=top),
                OCRVertex(x=right, y=top),
                OCRVertex(x=right, y=bottom),
                OCRVertex(x=left, y=bottom),
            )
        ),
        block_index=0,
        paragraph_index=0,
        word_index=word_index,
    )


def test_parse_label_layout_detects_allergen_contains_roi_without_heading() -> None:
    """Allergen-only ROI crops should become allergen-warning sections."""
    layout = parse_label_layout(
        OCRResult(
            text="Contains soy and milk.\nConsult doctor before use.",
            provider="fake-ocr",
            confidence=0.89,
            pages=(_ocr_contains_allergen_page(),),
        )
    )

    assert len(layout.sections) == 1
    assert layout.sections[0].section_type == "allergen_warning"
    assert layout.sections[0].anchor_text == "Contains allergen"
    assert layout.sections[0].rows[0][0].text == "Contains soy and milk."


def test_parse_label_layout_detects_soybean_tree_nut_allergen_row() -> None:
    """Common allergen variants should not require an explicit Warning heading."""
    layout = parse_label_layout(
        OCRResult(
            text="Contains soybean and tree nuts.",
            provider="fake-ocr",
            confidence=0.89,
            pages=(_ocr_contains_soybean_tree_nut_page(),),
        )
    )

    assert len(layout.sections) == 1
    assert layout.sections[0].section_type == "allergen_warning"
    assert layout.sections[0].anchor_text == "Contains allergen"
    assert layout.sections[0].rows[0][0].text == "Contains soybean and tree nuts."


@pytest.mark.asyncio
async def test_analyze_supplement_image_defaults_to_intake_only() -> None:
    """Verify the orchestration service preserves the existing intake-only behavior."""
    fake_session = _FakePipelineSession()

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        "client-1",
        _settings(),
    )

    assert result.parser_used is False
    assert result.ocr_result is None
    assert result.vision_region is None
    assert result.record.ocr_text_hash is None
    assert result.record.algorithm_version == "supplement-intake-v1.0.0"
    preview = supplement_analysis_run_to_preview(result.record)
    assert preview.pipeline_metadata.ocr_provider == "intake-only"
    assert preview.pipeline_metadata.image_count == 1
    assert preview.pipeline_metadata.image_role == "unknown"
    assert preview.pipeline_metadata.ocr_text_present is False
    assert preview.pipeline_metadata.ocr_confidence_bucket == "none"
    assert preview.pipeline_metadata.vision_roi_used is False
    assert preview.pipeline_metadata.roi_count == 0
    assert preview.pipeline_metadata.section_count == 0
    assert preview.pipeline_metadata.llm_parser_used is False
    assert preview.pipeline_metadata.parser_contract_version is None
    assert preview.pipeline_metadata.missing_required_sections == [
        "product_name",
        "supplement_facts",
        "intake_method",
        "precautions",
    ]
    # Intake-only path: only the intake persist_scope commits; no parser/pipeline writes.
    assert fake_session.commits == 1


@pytest.mark.asyncio
async def test_analyze_supplement_image_runs_ocr_then_parser_when_adapter_supplied() -> None:
    """Verify an injected OCR adapter can feed the existing structured parser service."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter(" 비타민 D 1000\n비타민 D 25 ug ")
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        _settings(),
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr, parser=fake_parser),
    )

    assert result.parser_used is True
    assert result.ocr_result is not None
    assert result.ocr_result.provider == "fake-ocr"
    assert fake_ocr.received_image is not None
    assert fake_ocr.received_image.mime_type == "image/png"
    assert fake_parser.received_text == "비타민 D 1000\n비타민 D 25 μg"
    assert result.record.ocr_provider == "fake-ocr"
    assert result.record.parsed_snapshot["parsed_product"]["product_name"] == "비타민 D 1000"
    assert result.record.parsed_snapshot["parser_metadata"]["raw_ocr_text_stored"] is False
    preview = supplement_analysis_run_to_preview(result.record)
    assert preview.pipeline_metadata.ocr_provider == "fake-ocr"
    assert preview.pipeline_metadata.ocr_text_present is True
    assert preview.pipeline_metadata.ocr_confidence_bucket == "medium"
    assert preview.pipeline_metadata.llm_parser_used is True
    assert preview.pipeline_metadata.parser_contract_version == result.record.algorithm_version
    assert preview.pipeline_metadata.missing_required_sections == []
    assert fake_session.committed is True


@pytest.mark.asyncio
async def test_analyze_supplement_image_degrades_gracefully_when_fallback_exceeds_max() -> None:
    """Verify an over-limit parser+fallback result degrades instead of raising (no 500).

    Regression for the legacy per-image analyze-multi path: when the LLM returns the
    maximum ingredient candidates and OCR yields one more amount-pattern candidate, the
    deterministic fallback merge would push the structured result past the schema bound
    and raise a raw ``pydantic`` ``ValidationError`` that escaped to HTTP 500. The
    orchestrator must surface this as a recoverable parse failure (``parser_used=False``
    with the ``ocr_parse_preview_unavailable`` warning) so the route still returns 202.
    """
    settings = _settings()
    max_candidates = settings.supplement_parser_max_ingredients
    maxed_result = SupplementStructuredParseResult.model_validate(
        {
            "ingredient_candidates": [
                {
                    "display_name": f"성분{index}",
                    "amount": 1,
                    "unit": "mg",
                    "confidence": 0.9,
                }
                for index in range(max_candidates)
            ],
            "missing_required_sections": [],
            "low_confidence_fields": [],
            "warnings": [],
        }
    )
    fake_session = _FakePipelineSession()
    # OCR yields one amount-pattern ingredient the LLM result did not include, so the
    # deterministic fallback merge appends it on top of the already-maxed candidate list.
    fake_ocr = _FakeOCRAdapter("아연\t10 mg\t50%")
    fake_parser = _FakeParser(maxed_result)

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        settings,
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr, parser=fake_parser),
    )

    assert result.parser_used is False
    assert OCR_PARSE_PREVIEW_UNAVAILABLE_CODE in result.ocr_warning_codes
    preview = supplement_analysis_run_to_preview(result.record)
    assert preview.pipeline_metadata.llm_parser_used is False


@pytest.mark.asyncio
async def test_analyze_supplement_image_keeps_front_label_ocr_but_requests_facts() -> None:
    """Verify front-label OCR stays usable without inventing ingredient candidates."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("레몬 비타민 D 1000\n60 capsules", confidence=0.86)
    fake_parser = _FakeParser(_front_label_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        _settings(),
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr, parser=fake_parser),
    )

    assert result.parser_used is True
    assert result.image_quality_report is not None
    assert result.image_quality_report.status == "retake_recommended"
    assert result.image_quality_report.retake_reasons == ["cover_only"]
    assert SUPPLEMENT_FACTS_REQUIRED_CODE in result.ocr_warning_codes
    preview = supplement_analysis_run_to_preview(result.record)
    assert preview.parsed_product.product_name == "레몬 비타민 D"
    assert preview.ingredient_candidates == []
    assert preview.missing_required_sections == [
        "supplement_facts",
        "intake_method",
        "precautions",
    ]
    assert preview.pipeline_metadata.missing_required_sections == [
        "supplement_facts",
        "intake_method",
        "precautions",
    ]
    assert preview.action_required == "additional_label_image_required"
    assert preview.analysis_scope == "identity_only"
    assert preview.image_role == "front_label"
    assert preview.image_quality_report is not None
    assert preview.image_quality_report.issues[0].reason_code == "cover_only"
    assert "supplement_facts_required" in preview.warnings
    assert "60 capsules" not in preview.model_dump_json()


@pytest.mark.asyncio
async def test_analyze_supplement_image_promotes_ocr_layout_to_preview_sections() -> None:
    """Verify OCR coordinates become reviewable section evidence in the preview."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter(
        "Supplement Facts\nVitamin D 25 ug\n섭취방법 1일 1정",
        pages=(_ocr_page(),),
    )
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        _settings(),
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr, parser=fake_parser),
    )

    preview = supplement_analysis_run_to_preview(result.record)
    assert preview.layout_available is True
    assert [section.section_type for section in preview.label_sections] == [
        "supplement_facts",
        "intake_method",
    ]
    assert preview.evidence_spans[-1].source_type == "ocr_layout"
    assert preview.pipeline_metadata.section_count == 2
    assert preview.pipeline_metadata.missing_required_sections == []


@pytest.mark.asyncio
async def test_analyze_supplement_image_defers_learning_artifacts_for_post_commit() -> None:
    """Verify the orchestrator defers learning writes instead of storing in-request."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter(
        "Warning Allergy Information Contains soy. If pregnant, consult doctor.",
        pages=(_ocr_warning_page(),),
    )
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_image_learning_pipeline=True,
            enable_pgvector_storage=True,
            image_retention_days=30,
        ),
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr, parser=fake_parser),
        learning_consents=(
            ConsentType.OCR_IMAGE_PROCESSING,
            ConsentType.DATA_RETENTION,
            ConsentType.IMAGE_LEARNING_DATASET,
        ),
    )

    # The orchestrator must NOT write learning rows inside the request transaction.
    assert not [
        record for record in fake_session.added_records if isinstance(record, LearningImageObject)
    ]
    assert not [
        record for record in fake_session.added_records if isinstance(record, AnnotationTask)
    ]
    # Instead it bundles the deferred inputs for the route's post-commit task.
    assert result.learning_artifacts is not None
    assert result.learning_artifacts.analysis_id == result.record.id
    assert result.learning_artifacts.image_bytes
    assert result.learning_artifacts.ocr_result is not None
    assert ConsentType.IMAGE_LEARNING_DATASET in result.learning_artifacts.learning_consents


@pytest.mark.asyncio
async def test_analyze_supplement_image_skips_learning_artifacts_when_gate_closed() -> None:
    """Verify no deferred learning inputs are produced without learning consents."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("Supplement Facts\nVitamin D 25 ug", pages=(_ocr_page(),))
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_image_learning_pipeline=True,
            enable_pgvector_storage=True,
            image_retention_days=30,
        ),
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr, parser=fake_parser),
        learning_consents=(),
    )

    assert result.learning_artifacts is None


@pytest.mark.asyncio
async def test_store_supplement_learning_artifacts_persists_image_and_annotation() -> None:
    """Verify the post-commit helper stores the image and queues a section review task."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter(
        "Warning Allergy Information Contains soy. If pregnant, consult doctor.",
        pages=(_ocr_warning_page(),),
    )
    fake_parser = _FakeParser(_parse_result())
    settings = Settings(
        privacy_hash_secret=SecretStr("test-privacy-secret"),
        enable_image_learning_pipeline=True,
        enable_pgvector_storage=True,
        image_retention_days=30,
    )

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        settings,
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr, parser=fake_parser),
        learning_consents=(
            ConsentType.OCR_IMAGE_PROCESSING,
            ConsentType.DATA_RETENTION,
            ConsentType.IMAGE_LEARNING_DATASET,
        ),
    )
    assert result.learning_artifacts is not None

    # Post-commit: a FRESH session re-fetches the now-durable analysis row.
    post_session = _FakePipelineSession()
    post_session.added_analysis = result.record
    fake_store = _FakeLearningImageObjectStore()

    await store_supplement_learning_artifacts(
        user=_user(),
        artifacts=result.learning_artifacts,
        settings=settings,
        object_store=fake_store,
        session_factory=cast(async_sessionmaker[AsyncSession], _FakeSessionFactory(post_session)),
    )

    learning_objects = [
        record for record in post_session.added_records if isinstance(record, LearningImageObject)
    ]
    annotation_tasks = [
        record for record in post_session.added_records if isinstance(record, AnnotationTask)
    ]

    assert fake_store.put_payload is not None
    assert len(learning_objects) == 1
    assert len(annotation_tasks) == 1
    task = annotation_tasks[0]
    assert task.media_object_id is None
    assert task.learning_image_object_id == learning_objects[0].id
    assert task.task_type == "supplement_roi_box"
    assert task.status == "pending"
    assert task.label_snapshot["candidate_source"] == "ocr_layout"
    assert task.label_snapshot["training_export_allowed"] is False
    assert task.label_snapshot["boxes"][0]["label"] == "precautions"
    serialized = str(task.label_snapshot)
    assert "Contains soy" not in serialized
    assert str(learning_objects[0].id) not in serialized


@pytest.mark.asyncio
async def test_store_supplement_learning_artifacts_skips_when_analysis_missing() -> None:
    """Verify the helper is a no-op when the analysis row is not yet durable."""
    post_session = _FakePipelineSession()  # added_analysis stays None -> get() returns None
    fake_store = _FakeLearningImageObjectStore()
    artifacts = SupplementLearningArtifactsInput(
        analysis_id=uuid4(),
        image_bytes=_png_bytes(),
        image_metadata=_validated_image(),
        ocr_result=None,
        learning_consents=(
            ConsentType.OCR_IMAGE_PROCESSING,
            ConsentType.DATA_RETENTION,
            ConsentType.IMAGE_LEARNING_DATASET,
        ),
    )

    await store_supplement_learning_artifacts(
        user=_user(),
        artifacts=artifacts,
        settings=Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_image_learning_pipeline=True,
            enable_pgvector_storage=True,
            image_retention_days=30,
        ),
        object_store=fake_store,
        session_factory=cast(async_sessionmaker[AsyncSession], _FakeSessionFactory(post_session)),
    )

    assert fake_store.put_payload is None
    assert not post_session.added_records


@pytest.mark.asyncio
async def test_store_supplement_learning_artifacts_defaults_to_learning_sessionmaker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default (no session_factory) must resolve via the privileged learning factory.

    After the Step 8 flip the main factory binds ``lemon_app`` (NOSUPERUSER /
    NOBYPASSRLS), which cannot write the FORCE-RLS learning tables from a fresh
    GUC-less session. The default must therefore be ``get_learning_sessionmaker``,
    never ``get_sessionmaker``.
    """
    post_session = _FakePipelineSession()  # added_analysis None -> get() returns None -> no-op
    fake_store = _FakeLearningImageObjectStore()
    used: dict[str, bool] = {}

    def _fake_learning_sessionmaker() -> _FakeSessionFactory:
        used["called"] = True
        return _FakeSessionFactory(post_session)

    monkeypatch.setattr(
        "src.services.supplement_image_analysis.get_learning_sessionmaker",
        _fake_learning_sessionmaker,
    )

    artifacts = SupplementLearningArtifactsInput(
        analysis_id=uuid4(),
        image_bytes=_png_bytes(),
        image_metadata=_validated_image(),
        ocr_result=None,
        learning_consents=(ConsentType.IMAGE_LEARNING_DATASET,),
    )

    await store_supplement_learning_artifacts(
        user=_user(),
        artifacts=artifacts,
        settings=Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_image_learning_pipeline=True,
            enable_pgvector_storage=True,
            image_retention_days=30,
        ),
        object_store=fake_store,
    )

    assert used.get("called") is True


@pytest.mark.asyncio
async def test_store_supplement_learning_embedding_job_defaults_to_learning_sessionmaker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default (no session_factory) must resolve via the privileged learning factory.

    The post-commit embedding-job enqueue calls
    ``enqueue_learning_embedding_job_for_confirmation``, which reads/writes the
    FORCE-RLS learning tables. After the Step 8 flip the main factory binds
    ``lemon_app`` (NOSUPERUSER / NOBYPASSRLS) and cannot touch those tables from a
    fresh GUC-less session, so the default must be ``get_learning_sessionmaker``.
    """
    post_session = _FakePipelineSession()
    used: dict[str, bool] = {}

    def _fake_learning_sessionmaker() -> _FakeSessionFactory:
        used["called"] = True
        return _FakeSessionFactory(post_session)

    monkeypatch.setattr(
        "src.services.supplement_image_analysis.get_learning_sessionmaker",
        _fake_learning_sessionmaker,
    )

    # analysis_id=None short-circuits enqueue before any DB access, so the fake
    # session is only exercised through the factory/context-manager call shape.
    embedding_input = SupplementLearningEmbeddingInput(
        analysis_id=None,
        metadata_snapshot={},
        learning_consents=(ConsentType.IMAGE_LEARNING_DATASET,),
    )

    await store_supplement_learning_embedding_job(
        user=_user(),
        embedding_input=embedding_input,
        settings=Settings(privacy_hash_secret=SecretStr("test-privacy-secret")),
    )

    assert used.get("called") is True


@pytest.mark.asyncio
async def test_store_supplement_learning_embedding_job_swallows_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A post-commit enqueue failure must be logged and swallowed (best-effort)."""

    def _raising_learning_sessionmaker() -> _FakeSessionFactory:
        raise RuntimeError("learning engine unavailable")

    monkeypatch.setattr(
        "src.services.supplement_image_analysis.get_learning_sessionmaker",
        _raising_learning_sessionmaker,
    )

    embedding_input = SupplementLearningEmbeddingInput(
        analysis_id=None,
        metadata_snapshot={},
        learning_consents=(),
    )

    # Must not raise: a learning miss never surfaces to the user.
    await store_supplement_learning_embedding_job(
        user=_user(),
        embedding_input=embedding_input,
        settings=Settings(privacy_hash_secret=SecretStr("test-privacy-secret")),
    )


@pytest.mark.asyncio
async def test_store_supplement_learning_artifacts_swallows_store_failure() -> None:
    """Verify a learning-store failure is logged and swallowed (best-effort)."""

    class _RaisingStore(_FakeLearningImageObjectStore):
        async def put_image(self, _payload: LearningImageObjectInput) -> StoredLearningImage:
            raise RuntimeError("object store unavailable")

    post_session = _FakePipelineSession()
    post_session.added_analysis = SupplementAnalysisRun(id=uuid4())
    artifacts = SupplementLearningArtifactsInput(
        analysis_id=post_session.added_analysis.id,
        image_bytes=_png_bytes(),
        image_metadata=_validated_image(),
        ocr_result=None,
        learning_consents=(
            ConsentType.OCR_IMAGE_PROCESSING,
            ConsentType.DATA_RETENTION,
            ConsentType.IMAGE_LEARNING_DATASET,
        ),
    )

    # Must NOT raise even though the object store fails mid-store.
    await store_supplement_learning_artifacts(
        user=_user(),
        artifacts=artifacts,
        settings=Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_image_learning_pipeline=True,
            enable_pgvector_storage=True,
            image_retention_days=30,
        ),
        object_store=_RaisingStore(),
        session_factory=cast(async_sessionmaker[AsyncSession], _FakeSessionFactory(post_session)),
    )

    assert not [
        record for record in post_session.added_records if isinstance(record, LearningImageObject)
    ]


@pytest.mark.asyncio
async def test_within_optional_budget_returns_fallback_on_timeout() -> None:
    """A slow optional stage is abandoned at the budget and yields the fallback."""

    async def _fast() -> str:
        return "real"

    async def _slow() -> str:
        await asyncio.sleep(5)
        return "real"

    assert (
        await supplement_image_analysis._within_optional_budget(
            _fast(), budget_sec=5, fallback="fallback", label="fast"
        )
        == "real"
    )
    assert (
        await supplement_image_analysis._within_optional_budget(
            _slow(), budget_sec=0.05, fallback="fallback", label="slow"
        )
        == "fallback"
    )


class _SlowMultimodalAdapter(OCRAdapter):
    """Multimodal vision adapter that sleeps past the optional-stage budget."""

    def __init__(self, delay_sec: float) -> None:
        self.delay_sec = delay_sec
        self.call_count = 0

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Sleep, then return a deliberately mismatching candidate."""
        _ = image
        self.call_count += 1
        await asyncio.sleep(self.delay_sec)
        return OCRResult(text="UNRELATED TEXT", provider="ollama_vision_assist", confidence=None)


@pytest.mark.asyncio
async def test_analyze_supplement_image_skips_slow_verification_within_budget() -> None:
    """A slow warn-only verification is bounded by the budget and degrades to no warning."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("비타민 D 1000", confidence=0.9)
    fake_parser = _FakeParser(_parse_result())
    slow_verifier = _SlowMultimodalAdapter(delay_sec=5)

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_multimodal_llm=True,
            enable_multimodal_verification=True,
            multimodal_verification_sample_rate=1.0,
            analyze_optional_stage_budget_sec=1,
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            multimodal_ocr=slow_verifier,
        ),
    )

    # Verification was attempted but abandoned at the 1s budget -> no mismatch warning,
    # and the rest of the pipeline still produced a usable preview.
    assert slow_verifier.call_count == 1
    assert OCR_VERIFICATION_MISMATCH_CODE not in result.ocr_warning_codes
    assert result.parser_used is True
    assert result.ocr_result is not None


@pytest.mark.asyncio
async def test_supplement_section_annotation_task_enqueue_skips_existing_task() -> None:
    """Verify an existing active task prevents duplicate pending review work."""
    fake_session = _FakePipelineSession()
    learning_object = _learning_image_object()
    fake_session.existing_annotation_task = AnnotationTask(
        id=uuid4(),
        owner_subject_hash="a" * 64,
        learning_image_object_id=learning_object.id,
        task_type="supplement_roi_box",
        status="pending",
        assignee_role="data_reviewer",
        label_snapshot={"schema_version": "existing"},
        review_notes_code="ocr_layout_section_candidate",
    )

    created = (
        await supplement_image_analysis._enqueue_supplement_section_annotation_task_if_available(
            session=cast(AsyncSession, fake_session),
            user=_user(),
            learning_object=learning_object,
            ocr_result=OCRResult(
                text="Warning Contains soy.",
                provider="fake-ocr",
                confidence=0.88,
                pages=(_ocr_warning_page(),),
            ),
            settings=_settings(),
        )
    )

    assert created is False
    assert not [
        record for record in fake_session.added_records if isinstance(record, AnnotationTask)
    ]


@pytest.mark.asyncio
async def test_analyze_supplement_image_passes_yolo_roi_to_ocr_when_enabled() -> None:
    """Verify YOLO ROI metadata is used only as OCR input preprocessing metadata."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("비타민 D 1000")
    fake_parser = _FakeParser(_parse_result())
    region = BoundingBox(
        x=1,
        y=0,
        width=2,
        height=2,
        confidence=0.92,
        label="supplement_label",
        model="local-supplement-roi.pt",
    )
    fake_vision = _FakeVisionAdapter(region)

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_vision_classifier=True,
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            vision=fake_vision,
        ),
    )

    assert result.vision_region == region
    assert result.vision_regions == (region,)
    assert fake_vision.call_count == 1
    assert fake_ocr.received_image is not None
    assert fake_ocr.received_image.label_region == region
    assert result.record.parsed_snapshot["pipeline_metadata"]["vision_roi_used"] is True
    assert result.record.parsed_snapshot["detected_product_regions"][0]["label"] == (
        "supplement_label"
    )
    assert result.record.parsed_snapshot["detected_product_regions"][0]["selected"] is True
    preview = supplement_analysis_run_to_preview(result.record)
    assert preview.pipeline_metadata.vision_roi_used is True
    assert preview.pipeline_metadata.roi_count == 1
    assert preview.detected_product_regions[0].selected is True
    assert preview.selected_region_id == "vision-1"
    assert preview.pipeline_metadata.ocr_provider == "fake-ocr"
    assert result.parser_used is True


@pytest.mark.asyncio
async def test_analyze_supplement_image_crops_primary_ocr_input_when_policy_enabled() -> None:
    """Verify ROI crop policy sends cropped image bytes to primary OCR."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("비타민 D 1000")
    fake_parser = _FakeParser(_parse_result())
    region = BoundingBox(
        x=1,
        y=0,
        width=2,
        height=2,
        confidence=0.92,
        label="supplement_label",
    )

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_vision_classifier=True,
            ocr_roi_preprocessing_policy="crop_before_primary",
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            vision=_FakeVisionAdapter(region),
        ),
    )

    assert result.vision_region == region
    assert fake_ocr.received_image is not None
    assert len(fake_ocr.received_images) == 2
    assert fake_ocr.received_images[0].label_region is None
    assert fake_ocr.received_images[0].mime_type == "image/png"
    assert fake_ocr.received_images[0].width == 2
    assert fake_ocr.received_images[0].height == 2
    assert fake_ocr.received_images[1].label_region is None
    assert fake_ocr.received_images[1].width == 3
    assert fake_ocr.received_images[1].height == 2
    assert fake_parser.received_text == "비타민 D 1000"


@pytest.mark.asyncio
async def test_analyze_supplement_image_preserves_multi_roi_precaution_layout() -> None:
    """Verify section ROI OCR preserves warning text and layout sections."""
    fake_session = _FakePipelineSession()
    fake_ocr = _SequenceOCRAdapter(
        [
            OCRResult(
                text="Supplement Facts\nVitamin D 25 ug",
                provider="fake-ocr",
                confidence=0.9,
                pages=(_ocr_page(),),
            ),
            OCRResult(
                text="Warning\nAllergy Information\nContains soy. If pregnant, consult doctor.",
                provider="fake-ocr",
                confidence=0.88,
                pages=(_ocr_warning_page(),),
            ),
            OCRResult(
                text="Suggested Use\nTake 1 softgel daily with food.",
                provider="fake-ocr",
                confidence=0.87,
                pages=(),
            ),
            OCRResult(
                text="Front Label\nVitamin D",
                provider="fake-ocr",
                confidence=0.84,
                pages=(),
            ),
            OCRResult(
                text="Supplement Facts\nVitamin D 25 ug\nWarning\nContains soy.",
                provider="fake-ocr",
                confidence=0.82,
                pages=(),
            ),
        ]
    )
    fake_parser = _FakeParser(_parse_result())
    regions = [
        BoundingBox(
            x=1,
            y=0,
            width=1,
            height=1,
            confidence=0.84,
            label="supplement_label",
        ),
        BoundingBox(
            x=0,
            y=0,
            width=1,
            height=1,
            confidence=0.91,
            label="supplement_facts",
        ),
        BoundingBox(
            x=1,
            y=1,
            width=1,
            height=1,
            confidence=0.89,
            label="precautions",
        ),
        BoundingBox(
            x=2,
            y=1,
            width=1,
            height=1,
            confidence=0.88,
            label="intake_method",
        ),
    ]

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_vision_classifier=True,
            ocr_roi_preprocessing_policy="crop_before_primary",
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            vision=_FakeVisionAdapter(regions=regions),
        ),
    )

    assert result.ocr_result is not None
    assert result.ocr_result.pages == (_ocr_page(), _ocr_warning_page())
    assert fake_parser.received_text is not None
    assert "Warning" in fake_parser.received_text
    assert "Allergy Information" in fake_parser.received_text
    assert "Contains soy" in fake_parser.received_text
    assert [image.width for image in fake_ocr.received_images] == [1, 1, 1, 1, 3]
    preview = supplement_analysis_run_to_preview(result.record)
    section_types = {section.section_type for section in preview.label_sections}
    assert "supplement_facts" in section_types
    assert "precautions" in section_types
    assert "allergen_warning" in section_types
    assert preview.pipeline_metadata.section_count >= 2


@pytest.mark.asyncio
async def test_analyze_supplement_image_falls_back_to_full_image_ocr_when_vision_fails() -> None:
    """Verify ROI detection failure does not block the OCR-first path."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("비타민 D 1000")
    fake_parser = _FakeParser(_parse_result())
    fake_vision = _FakeVisionAdapter(fail=True)

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_vision_classifier=True,
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            vision=fake_vision,
        ),
    )

    assert result.vision_region is None
    assert fake_ocr.received_image is not None
    assert fake_ocr.received_image.label_region is None
    assert result.parser_used is True


@pytest.mark.asyncio
async def test_analyze_supplement_image_does_not_call_multimodal_when_ocr_is_usable() -> None:
    """Verify multimodal assist is not a primary path when OCR succeeds."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("비타민 D 1000", confidence=0.88)
    fake_multimodal = _FakeMultimodalOCRAdapter()
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_multimodal_llm=True,
            multimodal_ocr_assist_policy="low_confidence",
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            multimodal_ocr=fake_multimodal,
        ),
    )

    assert result.ocr_result is not None
    assert result.ocr_result.provider == "fake-ocr"
    assert fake_multimodal.call_count == 0
    assert fake_parser.received_text == "비타민 D 1000"


@pytest.mark.asyncio
async def test_analyze_supplement_image_calls_multimodal_when_ocr_is_empty() -> None:
    """Verify multimodal assist can provide visible-text candidates after OCR failure."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("", confidence=None)
    fake_multimodal = _FakeMultimodalOCRAdapter("비타민 D 1000\n비타민 D 25 ug")
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_multimodal_llm=True,
            multimodal_ocr_assist_policy="ocr_empty_only",
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            multimodal_ocr=fake_multimodal,
        ),
    )

    assert fake_ocr.call_count == 1
    assert fake_multimodal.call_count == 1
    assert fake_parser.received_text == "비타민 D 1000\n비타민 D 25 μg"
    assert result.ocr_result is not None
    assert result.ocr_result.provider == "ollama_vision_assist"
    assert result.record.parsed_snapshot["parser_metadata"]["input_provider"] == (
        "ollama_vision_assist"
    )


@pytest.mark.asyncio
async def test_analyze_supplement_image_calls_multimodal_when_ocr_is_low_confidence() -> None:
    """Verify low OCR confidence can trigger the configured vision assist fallback."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("흐린 텍스트", confidence=0.70)
    fake_multimodal = _FakeMultimodalOCRAdapter("비타민 D 1000")
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_multimodal_llm=True,
            multimodal_ocr_assist_policy="low_confidence",
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            multimodal_ocr=fake_multimodal,
        ),
    )

    assert fake_multimodal.call_count == 1
    assert fake_parser.received_text == "비타민 D 1000"
    assert result.ocr_result is not None
    assert result.ocr_result.provider == "ollama_vision_assist"


@pytest.mark.asyncio
async def test_analyze_supplement_image_calls_secondary_fallback_after_low_confidence_ocr() -> None:
    """Verify optional secondary OCR providers can recover weak primary OCR."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("흐린 텍스트", confidence=0.70)
    fallback_ocr = _FakeOCRAdapter("비타민 D 1000", confidence=0.83)
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        _settings(),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            fallback_ocr_adapters=(fallback_ocr,),
        ),
    )

    assert fake_ocr.call_count == 1
    assert fallback_ocr.call_count == 1
    assert fake_parser.received_text == "비타민 D 1000"
    assert result.ocr_result is not None
    assert result.ocr_result.confidence == 0.83


@pytest.mark.asyncio
async def test_analyze_supplement_image_records_multimodal_verification_mismatch() -> None:
    """Verify local vision verification can mark mismatched accepted OCR text."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("비타민 D 1000", confidence=0.91)
    fake_multimodal = _FakeMultimodalOCRAdapter("마그네슘 400")
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_multimodal_llm=True,
            enable_multimodal_verification=True,
            multimodal_verification_sample_rate=1.0,
            multimodal_verification_threshold=0.95,
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            multimodal_ocr=fake_multimodal,
        ),
    )

    assert fake_multimodal.call_count == 1
    assert fake_parser.received_text == "비타민 D 1000"
    assert OCR_VERIFICATION_MISMATCH_CODE in result.ocr_warning_codes
    assert result.record.warnings


@pytest.mark.asyncio
async def test_analyze_supplement_image_uses_structured_multimodal_verification() -> None:
    """Verify local vision verification can use schema output instead of OCR similarity."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("비타민 D 1000\n주의사항", confidence=0.91)
    fake_multimodal = _FakeMultimodalVerifierAdapter(
        _verification_result(
            status="partial",
            confidence=0.82,
            missing_sections=["precautions"],
        )
    )
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_multimodal_llm=True,
            enable_multimodal_verification=True,
            multimodal_verification_sample_rate=1.0,
            multimodal_verification_threshold=0.95,
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            multimodal_ocr=fake_multimodal,
        ),
    )

    assert fake_multimodal.verify_call_count == 1
    assert fake_multimodal.call_count == 0
    assert fake_multimodal.received_verification_text == "비타민 D 1000\n주의사항"
    assert fake_multimodal.received_verification_image is not None
    assert fake_parser.received_text == "비타민 D 1000\n주의사항"
    assert OCR_VERIFICATION_MISMATCH_CODE in result.ocr_warning_codes


@pytest.mark.asyncio
async def test_analyze_supplement_image_accepts_structured_multimodal_match() -> None:
    """Verify schema-based vision verification does not warn on a supported match."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("비타민 D 1000", confidence=0.91)
    fake_multimodal = _FakeMultimodalVerifierAdapter(_verification_result())
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_multimodal_llm=True,
            enable_multimodal_verification=True,
            multimodal_verification_sample_rate=1.0,
            multimodal_verification_threshold=0.95,
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            multimodal_ocr=fake_multimodal,
        ),
    )

    assert fake_multimodal.verify_call_count == 1
    assert OCR_VERIFICATION_MISMATCH_CODE not in result.ocr_warning_codes


@pytest.mark.asyncio
async def test_multimodal_verification_sampled_branch_is_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the fractional verification-sampling RNG draw-below-rate path runs.

    The sampling decision uses the module-level ``random()``. With a fractional
    ``multimodal_verification_sample_rate`` the result depends on that draw, which
    is flaky-prone in tests. Pinning ``random`` to a value *below* the rate
    deterministically forces the sampled branch, so verification runs (the
    adapter is called exactly once) without changing production probabilities.
    """
    monkeypatch.setattr(supplement_image_analysis, "random", lambda: 0.4)
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("비타민 D 1000", confidence=0.91)
    fake_multimodal = _FakeMultimodalOCRAdapter("마그네슘 400")
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_multimodal_llm=True,
            enable_multimodal_verification=True,
            multimodal_verification_sample_rate=0.5,
            multimodal_verification_threshold=0.95,
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            multimodal_ocr=fake_multimodal,
        ),
    )

    assert fake_multimodal.call_count == 1
    assert OCR_VERIFICATION_MISMATCH_CODE in result.ocr_warning_codes


@pytest.mark.asyncio
async def test_multimodal_verification_skipped_branch_is_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the fractional verification-sampling RNG draw-at-or-above-rate path skips.

    Pinning the module-level ``random`` to a value *at or above* the fractional
    rate deterministically forces the non-sampled branch, so verification is
    skipped (the adapter is never called and no mismatch warning is emitted).
    """
    monkeypatch.setattr(supplement_image_analysis, "random", lambda: 0.6)
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("비타민 D 1000", confidence=0.91)
    fake_multimodal = _FakeMultimodalOCRAdapter("마그네슘 400")
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_multimodal_llm=True,
            enable_multimodal_verification=True,
            multimodal_verification_sample_rate=0.5,
            multimodal_verification_threshold=0.95,
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            multimodal_ocr=fake_multimodal,
        ),
    )

    assert fake_multimodal.call_count == 0
    assert OCR_VERIFICATION_MISMATCH_CODE not in result.ocr_warning_codes


@pytest.mark.asyncio
async def test_ensemble_merge_disabled_is_passthrough() -> None:
    """Verify the secondary-merge adapter is never called when policy is disabled."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("비타민 D 1000", confidence=0.91)
    secondary_merge = _FakeOCRAdapter("마그네슘 400mg", confidence=0.80)
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        _settings(),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            secondary_merge_ocr=secondary_merge,
        ),
    )

    assert fake_ocr.call_count == 1
    assert secondary_merge.call_count == 0
    assert fake_parser.received_text == "비타민 D 1000"
    assert result.ocr_result is not None
    assert result.ocr_result.provider == "fake-ocr"


@pytest.mark.asyncio
async def test_ensemble_merge_always_runs_and_merges() -> None:
    """Verify the secondary adapter always runs and its novel line is merged in."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("비타민 D 1000", confidence=0.91)
    secondary_merge = _FakeOCRAdapter("비타민 D 1000\n마그네슘 400mg", confidence=0.80)
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            ocr_secondary_merge_policy="always",
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            secondary_merge_ocr=secondary_merge,
        ),
    )

    assert fake_ocr.call_count == 1
    assert secondary_merge.call_count == 1
    assert fake_parser.received_text == "비타민 D 1000\n마그네슘 400mg"
    assert result.ocr_result is not None
    assert result.ocr_result.provider == "fake-ocr+fake-ocr"


@pytest.mark.asyncio
async def test_ensemble_merge_does_not_trigger_legacy_secondary_fallback() -> None:
    """Verify a strong merged result does not invoke the legacy fallback chain."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("비타민 D 1000", confidence=0.91)
    secondary_merge = _FakeOCRAdapter("비타민 D 1000\n마그네슘 400mg", confidence=0.80)
    fallback_ocr = _FakeOCRAdapter("주의사항", confidence=0.83)
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            ocr_secondary_merge_policy="always",
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            secondary_merge_ocr=secondary_merge,
            fallback_ocr_adapters=(fallback_ocr,),
        ),
    )

    assert secondary_merge.call_count == 1
    assert fallback_ocr.call_count == 0
    assert result.ocr_result is not None
    assert result.ocr_result.provider == "fake-ocr+fake-ocr"


@pytest.mark.asyncio
async def test_ensemble_merge_low_confidence_policy_skips_when_primary_strong() -> None:
    """Verify the low_confidence policy skips the merge when primary is confident."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("비타민 D 1000", confidence=0.91)
    secondary_merge = _FakeOCRAdapter("마그네슘 400mg", confidence=0.80)
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            ocr_secondary_merge_policy="low_confidence",
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            secondary_merge_ocr=secondary_merge,
        ),
    )

    assert secondary_merge.call_count == 0
    assert result.ocr_result is not None
    assert result.ocr_result.provider == "fake-ocr"


@pytest.mark.asyncio
async def test_always_on_merge_forces_verification_despite_zero_sample_rate() -> None:
    """Verify a merged result is always verified when mode is always_on_merge."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter("비타민 D 1000", confidence=0.91)
    secondary_merge = _FakeOCRAdapter("비타민 D 1000\n마그네슘 400mg", confidence=0.80)
    fake_multimodal = _FakeMultimodalVerifierAdapter(_verification_result())
    fake_parser = _FakeParser(_parse_result())

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            ocr_secondary_merge_policy="always",
            ocr_ensemble_verification_mode="always_on_merge",
            enable_multimodal_llm=True,
            enable_multimodal_verification=True,
            multimodal_verification_sample_rate=0.0,
            multimodal_verification_threshold=0.95,
        ),
        adapters=SupplementImageAnalysisAdapters(
            ocr=fake_ocr,
            parser=fake_parser,
            secondary_merge_ocr=secondary_merge,
            multimodal_ocr=fake_multimodal,
        ),
    )

    assert secondary_merge.call_count == 1
    assert fake_multimodal.verify_call_count == 1
    assert result.ocr_result is not None
    assert result.ocr_result.provider == "fake-ocr+fake-ocr"


@pytest.mark.asyncio
async def test_extract_supplement_ocr_only_returns_ocr_without_intake_or_parse() -> None:
    """OCR-only extraction returns text but creates no intake row and runs no parse."""
    fake_ocr = _SequenceOCRAdapter(
        [OCRResult(text="비타민 C 1000 mg", provider="clova", confidence=0.9)]
    )

    result = await supplement_image_analysis.extract_supplement_ocr_only(
        _upload(_png_bytes()),
        settings=_settings(),
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr),
    )

    assert isinstance(result, supplement_image_analysis.SupplementOCROnlyResult)
    assert result.ocr_result is not None
    assert result.ocr_result.text == "비타민 C 1000 mg"
    assert result.ocr_attempted is True
    # One OCR call, no DB session passed → no intake row and no structured parse.
    assert len(fake_ocr.received_images) == 1


def test_fuse_supplement_ocr_texts_joins_with_role_markers_and_dedups() -> None:
    """Fusion adds per-image role markers, dedups shared lines, composites provider."""
    labeled = [
        (
            "front_label",
            OCRResult(text="Product Name\nVitamin D Complex", provider="clova", confidence=0.9),
        ),
        (
            "intake_method",
            OCRResult(text="Product Name\nVitamin D 25 ug", provider="paddleocr", confidence=0.8),
        ),
    ]

    fused = supplement_image_analysis._fuse_supplement_ocr_texts(labeled, _settings())

    assert fused is not None
    assert "[이미지 1 · front_label]" in fused.text
    assert "[이미지 2 · intake_method]" in fused.text
    assert "Vitamin D Complex" in fused.text
    assert "Vitamin D 25 ug" in fused.text
    # "Product Name" appears once (deduplicated across the two images).
    assert fused.text.count("Product Name") == 1
    # Composite provider records every contributing OCR provider; confidence anchors first.
    assert fused.provider == "clova+paddleocr"
    assert fused.confidence == 0.9


@pytest.mark.asyncio
async def test_analyze_fused_supplement_images_creates_single_run_and_parses_once() -> None:
    """Two images fuse into ONE run; the parser runs once over the fused text."""
    fake_session = _FakePipelineSession()
    fake_ocr = _SequenceOCRAdapter(
        [
            OCRResult(text="ALPHAONE Vitamin C", provider="clova", confidence=0.9),
            OCRResult(text="BRAVOTWO 1000 mg", provider="clova", confidence=0.8),
        ]
    )
    fake_parser = _FakeParser(_parse_result())

    result = await supplement_image_analysis.analyze_fused_supplement_images(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        images=[_upload(_png_bytes()), _upload(_png_bytes())],
        image_roles=["front_label", "intake_method"],
        client_request_id=None,
        settings=_settings(),
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr, parser=fake_parser),
    )

    # Exactly one analysis run is persisted for the whole batch.
    runs = [r for r in fake_session.added_records if isinstance(r, SupplementAnalysisRun)]
    assert len(runs) == 1
    # The parser ran once over the fused text containing BOTH images plus role markers.
    assert fake_parser.received_text is not None
    assert "ALPHAONE" in fake_parser.received_text
    assert "BRAVOTWO" in fake_parser.received_text
    assert "이미지 1" in fake_parser.received_text
    assert "이미지 2" in fake_parser.received_text
    assert result.parser_used is True
    assert result.record.ocr_text_hash is not None
    assert result.record.parsed_snapshot["parser_metadata"]["raw_ocr_text_stored"] is False
    # No learning consents → gate closed → no per-image learning artifacts bundled.
    assert result.learning_artifacts is None
    assert result.learning_artifacts_per_image == ()


@pytest.mark.asyncio
async def test_analyze_fused_supplement_images_emits_per_image_learning_artifacts() -> None:
    """One-shot fusion bundles one learning artifact PER image, not one fused.

    The fused parse is a single preview, but the section-detector training
    dataset needs each physical image with its own layout-bearing OCR result, so
    the orchestrator emits a per-image artifact list (all linked to the single
    fused run) and leaves the singular ``learning_artifacts`` field None.
    """
    fake_session = _FakePipelineSession()
    fake_ocr = _SequenceOCRAdapter(
        [
            OCRResult(text="ALPHAONE Vitamin C", provider="clova", confidence=0.9),
            OCRResult(text="BRAVOTWO 1000 mg", provider="clova", confidence=0.8),
        ]
    )
    fake_parser = _FakeParser(_parse_result())

    result = await supplement_image_analysis.analyze_fused_supplement_images(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        images=[_upload(_png_bytes()), _upload(_png_bytes())],
        image_roles=["front_label", "intake_method"],
        client_request_id=None,
        settings=Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_image_learning_pipeline=True,
            enable_pgvector_storage=True,
            image_retention_days=30,
        ),
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr, parser=fake_parser),
        learning_consents=(
            ConsentType.OCR_IMAGE_PROCESSING,
            ConsentType.DATA_RETENTION,
            ConsentType.IMAGE_LEARNING_DATASET,
        ),
    )

    # The fused path bundles one artifact per image — NOT a single fused artifact.
    assert result.learning_artifacts is None
    assert len(result.learning_artifacts_per_image) == 2
    # All per-image artifacts link to the SAME single fused analysis run.
    assert {a.analysis_id for a in result.learning_artifacts_per_image} == {result.record.id}
    # Each artifact carries its OWN image's OCR result (layout-bearing), not the
    # layout-less fused text — proving the per-image learning signal is preserved.
    per_image_texts = {
        a.ocr_result.text for a in result.learning_artifacts_per_image if a.ocr_result is not None
    }
    assert per_image_texts == {"ALPHAONE Vitamin C", "BRAVOTWO 1000 mg"}
    assert all(a.image_bytes for a in result.learning_artifacts_per_image)


def _vision_extraction(
    *,
    product_category_key: str | None = None,
    ingredients: list[dict[str, object]] | None = None,
) -> OllamaVisionStructuredExtractionResult:
    """Return a structured vision extraction fixture.

    Args:
        product_category_key: Allowed-list category key the model returned.
        ingredients: Transcribed ingredient name/amount/unit rows.

    Returns:
        Validated structured extraction result.
    """
    return OllamaVisionStructuredExtractionResult.model_validate(
        {
            "product_category_key": product_category_key,
            "ingredients": ingredients or [],
            "low_confidence_fields": [],
            "warnings": [],
        }
    )


def test_merge_vision_amounts_fills_null_amount_by_name_and_sets_category() -> None:
    """Verify the additive merge fills a null amount by name and sets an unset category."""
    snapshot: dict[str, object] = {
        "ingredient_candidates": [
            {
                "display_name": "마그네슘",
                "original_name": "Magnesium",
                "amount": None,
                "unit": None,
            },
        ],
    }

    outcome = _merge_vision_amounts_into_snapshot(
        snapshot,
        _vision_extraction(
            product_category_key="마그네슘",
            ingredients=[{"name": "magnesium", "amount": 400, "unit": "mg"}],
        ),
        frozenset({"마그네슘", "비타민D"}),
        "마그네슘 Magnesium 400 mg",
    )

    assert outcome.attempted is True
    assert outcome.amounts_filled == 1
    assert outcome.category_applied is True
    candidate = snapshot["ingredient_candidates"][0]
    assert candidate["amount"] == 400
    assert candidate["unit"] == "mg"
    assert snapshot["product_category_key"] == "마그네슘"


def test_merge_vision_amounts_never_overwrites_existing_amount_or_category() -> None:
    """Verify the merge leaves a non-null amount and an existing category untouched."""
    snapshot: dict[str, object] = {
        "product_category_key": "비타민D",
        "ingredient_candidates": [
            {"display_name": "비타민 D", "original_name": "Vitamin D", "amount": 25, "unit": "ug"},
        ],
    }

    outcome = _merge_vision_amounts_into_snapshot(
        snapshot,
        _vision_extraction(
            product_category_key="마그네슘",
            ingredients=[{"name": "vitamin d", "amount": 9999, "unit": "iu"}],
        ),
        frozenset({"마그네슘", "비타민D"}),
        "",
    )

    assert outcome.attempted is True
    assert outcome.amounts_filled == 0
    assert outcome.category_applied is False
    candidate = snapshot["ingredient_candidates"][0]
    assert candidate["amount"] == 25
    assert candidate["unit"] == "ug"
    assert snapshot["product_category_key"] == "비타민D"


def test_merge_vision_amounts_ignores_category_outside_allowed_list() -> None:
    """Verify a vision category not in the allow-list is never applied."""
    snapshot: dict[str, object] = {"ingredient_candidates": []}

    outcome = _merge_vision_amounts_into_snapshot(
        snapshot,
        _vision_extraction(product_category_key="존재하지않는카테고리"),
        frozenset({"마그네슘", "비타민D"}),
        "",
    )

    assert outcome.category_applied is False
    assert "product_category_key" not in snapshot


def test_merge_vision_amounts_drops_amount_not_grounded_in_ocr() -> None:
    """Verify a vision amount absent from the OCR text is dropped (never guessed)."""
    snapshot: dict[str, object] = {
        "ingredient_candidates": [
            {
                "display_name": "마그네슘",
                "original_name": "Magnesium",
                "amount": None,
                "unit": None,
            },
        ],
    }

    outcome = _merge_vision_amounts_into_snapshot(
        snapshot,
        _vision_extraction(
            ingredients=[{"name": "magnesium", "amount": 400, "unit": "mg"}],
        ),
        frozenset({"마그네슘", "비타민D"}),
        "원재료명: 마그네슘",  # OCR text has no "400 mg" → amount is not grounded
    )

    assert outcome.amounts_filled == 0
    candidate = snapshot["ingredient_candidates"][0]
    assert candidate["amount"] is None
    assert candidate["unit"] is None


@pytest.mark.asyncio
async def test_analyze_supplement_image_merges_vision_extraction_into_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the orchestrator runs the vision pass and records the merge outcome."""
    fake_session = _FakePipelineSession()
    # Parser yields a name-only candidate (amount None) and no category.
    parse_result = SupplementStructuredParseResult.model_validate(
        {
            "parsed_product": {"product_name": "마그네슘 400"},
            "ingredient_candidates": [
                {
                    "display_name": "마그네슘",
                    "original_name": "Magnesium",
                    "amount": None,
                    "confidence": 0.6,
                }
            ],
            "low_confidence_fields": [],
            "warnings": [],
        }
    )
    # The amount is printed on the label (so it is span-groundable) but the parser
    # left the candidate's amount null (no pairable ingredient name beside it). The
    # vision pass attributes "400 mg" to magnesium and the grounding check confirms
    # the number actually appears in the OCR text before filling.
    fake_ocr = _FakeOCRAdapter("표시 성분 함량 400 mg", confidence=0.91)
    fake_parser = _FakeParser(parse_result)

    async def _fake_extract_structured(
        _self: object,
        image: OCRImageInput,
        allowed_categories: list[str],
    ) -> OllamaVisionStructuredExtractionResult:
        assert image.mime_type == "image/png"
        assert "마그네슘" in allowed_categories
        return _vision_extraction(
            product_category_key="마그네슘",
            ingredients=[{"name": "마그네슘", "amount": 400, "unit": "mg"}],
        )

    monkeypatch.setattr(
        supplement_image_analysis.OllamaVisionAssistAdapter,
        "extract_structured",
        _fake_extract_structured,
    )

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_multimodal_llm=True,
            enable_supplement_label_vision_extraction=True,
            ollama_vision_model="gemma4:e4b",
        ),
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr, parser=fake_parser),
    )

    candidate = result.record.parsed_snapshot["ingredient_candidates"][0]
    assert candidate["amount"] == 400
    assert candidate["unit"] == "mg"
    assert result.record.parsed_snapshot["product_category_key"] == "마그네슘"
    preview = supplement_analysis_run_to_preview(result.record)
    assert preview.pipeline_metadata.vision_extraction_attempted is True
    assert preview.pipeline_metadata.vision_category_applied is True
    assert preview.pipeline_metadata.vision_amounts_filled == 1


@pytest.mark.asyncio
async def test_analyze_supplement_image_swallows_vision_extraction_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a vision-pass failure never breaks analysis (best-effort)."""
    fake_session = _FakePipelineSession()
    fake_ocr = _FakeOCRAdapter(" 비타민 D 1000\n비타민 D 25 ug ", confidence=0.91)
    fake_parser = _FakeParser(_parse_result())

    async def _boom(
        _self: object,
        _image: OCRImageInput,
        _allowed_categories: list[str],
    ) -> OllamaVisionStructuredExtractionResult:
        raise RuntimeError("vision host unreachable")

    monkeypatch.setattr(
        supplement_image_analysis.OllamaVisionAssistAdapter,
        "extract_structured",
        _boom,
    )

    result = await analyze_supplement_image(
        cast(AsyncSession, fake_session),
        _user(),
        _upload(_png_bytes()),
        None,
        Settings(
            privacy_hash_secret=SecretStr("test-privacy-secret"),
            enable_multimodal_llm=True,
            enable_supplement_label_vision_extraction=True,
            ollama_vision_model="gemma4:e4b",
        ),
        adapters=SupplementImageAnalysisAdapters(ocr=fake_ocr, parser=fake_parser),
    )

    assert result.parser_used is True
    preview = supplement_analysis_run_to_preview(result.record)
    assert preview.pipeline_metadata.vision_extraction_attempted is False
    assert preview.pipeline_metadata.vision_amounts_filled == 0
