"""Meal image analysis preview service tests."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from typing import Self, cast
from uuid import uuid4

import pytest
from fastapi import UploadFile
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import Settings
from src.db.tx import REQUEST_MANAGED_TX
from src.models.db.meal import (
    FoodImageAnalysisRun,
    FoodNutrition,
    MealFoodItem,
    MealRecord,
)
from src.models.schemas.meal import (
    MealAnalysisStatus,
    MealConfirmationRequest,
    MealFoodItemInput,
    MealType,
)
from src.models.schemas.taxonomy import FoodCatalogItemReference
from src.security.auth import AuthenticatedUser
from src.services.meal_image_analysis import (
    FOOD_IMAGE_ANALYSIS_ALGORITHM_VERSION,
    MealConfirmationValidationError,
    MealImageAnalysisConflictError,
    MealImageValidationError,
    MealPreviewStateError,
    ValidatedMealImage,
    confirm_meal_record_from_preview,
    create_meal_image_analysis_preview,
    meal_confirmation_to_response,
    meal_image_analysis_to_preview,
    meal_record_to_response,
    read_and_validate_meal_image,
)
from src.vision.base import BoundingBox, VisionError
from src.vision.food_dino_classifier import FoodClassification
from src.vision.food_yolo import FoodDetection
from starlette.datastructures import Headers


class _ScalarResult:
    """Fake SQLAlchemy scalar result returning configured rows."""

    def __init__(self, rows: list[object]) -> None:
        """Store configured rows.

        Args:
            rows: Rows returned by ``all``.
        """
        self.rows = rows

    def all(self) -> list[object]:
        """Return configured rows.

        Returns:
            Rows configured for the fake result.
        """
        return self.rows


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


class _FakeStoreSession:
    """Fake async session for meal image preview write tests."""

    def __init__(
        self,
        *,
        existing_run: FoodImageAnalysisRun | None = None,
        existing_meal: MealRecord | None = None,
        food_nutrition_rows: list[FoodNutrition] | None = None,
        request_managed: bool = False,
    ) -> None:
        """Initialize fake persisted records.

        Args:
            existing_run: Existing food image analysis run returned for idempotency lookup.
            existing_meal: Existing meal record returned for idempotency lookup.
            food_nutrition_rows: Active food nutrition rows returned for class lookups.
            request_managed: Stamp the request-managed marker so persist_scope participates.
        """
        self.existing_run = existing_run
        self.existing_meal = existing_meal
        self.food_nutrition_rows = food_nutrition_rows or []
        self.added: list[object] = []
        self.refreshed: list[object] = []
        self.flush_count = 0
        self.committed = False
        self.commits = 0
        # A real AsyncSession always exposes ``.info``; persist_scope reads it.
        self.info: dict[str, object] = {REQUEST_MANAGED_TX: True} if request_managed else {}

    async def scalars(self, statement: object) -> _ScalarResult:
        """Return fake nutrition rows for food nutrition class lookups.

        Args:
            statement: SQLAlchemy select statement.

        Returns:
            Fake scalar result with configured rows.
        """
        column_descriptions = getattr(statement, "column_descriptions", [])
        model = column_descriptions[0].get("entity") if column_descriptions else None
        if model is FoodNutrition:
            return _ScalarResult(list(self.food_nutrition_rows))
        return _ScalarResult([])

    def begin(self) -> _TransactionContext:
        """Return a fake transaction context.

        Returns:
            Fake async transaction context.
        """
        return _TransactionContext()

    async def scalar(self, statement: object) -> object | None:
        """Return fake existing rows based on selected ORM entity.

        Args:
            statement: SQLAlchemy select statement.

        Returns:
            Existing ORM row or None.
        """
        column_descriptions = getattr(statement, "column_descriptions", [])
        model = column_descriptions[0].get("entity") if column_descriptions else None
        if model is FoodImageAnalysisRun:
            return self.existing_run
        if model is MealRecord:
            return self.existing_meal
        return None

    def add(self, record: object) -> None:
        """Capture the ORM record being added.

        Args:
            record: ORM object passed by the service.

        Returns:
            None.
        """
        self.added.append(record)

    async def flush(self) -> None:
        """Match the async session flush interface.

        Returns:
            None.
        """
        self.flush_count += 1

    async def commit(self) -> None:
        """Record that the fake transaction was committed.

        Returns:
            None.
        """
        self.committed = True
        self.commits += 1

    async def rollback(self) -> None:
        """No-op rollback (persist_scope own-mode rolls back on exception)."""

    async def refresh(self, record: object) -> None:
        """Populate server-generated timestamps after fake persistence.

        Args:
            record: ORM object to refresh.

        Returns:
            None.
        """
        if hasattr(record, "created_at"):
            record.created_at = datetime.now(UTC)
        if hasattr(record, "updated_at"):
            record.updated_at = datetime.now(UTC)
        self.refreshed.append(record)


class _FakeFoodDetector:
    """Fake food detector for meal image preview tests."""

    def __init__(self, detections: list[FoodDetection] | None = None) -> None:
        """Initialize fake detector output.

        Args:
            detections: Detections returned by detect_foods.
        """
        self.detections = detections or []
        self.received_image_bytes: bytes | None = None

    def detect_foods(self, image_bytes: bytes) -> list[FoodDetection]:
        """Return configured detections while capturing input bytes.

        Args:
            image_bytes: Request-local normalized image bytes.

        Returns:
            Configured detections.
        """
        self.received_image_bytes = image_bytes
        return self.detections


class _FailingFoodDetector:
    """Fake food detector that fails safely."""

    def detect_foods(self, _image_bytes: bytes) -> list[FoodDetection]:
        """Raise a stable vision error.

        Args:
            image_bytes: Request-local normalized image bytes.

        Raises:
            VisionError: Always raised.
        """
        raise VisionError("detector unavailable")


class _FakeFoodClassifier:
    """Fake food classifier for meal image preview tests."""

    def __init__(self, classification: FoodClassification | None = None) -> None:
        """Initialize fake classifier output.

        Args:
            classification: Classification returned by classify_food.
        """
        self.classification = classification
        self.received_image_bytes: bytes | None = None

    def classify_food(self, image_bytes: bytes) -> FoodClassification | None:
        """Return configured classification while capturing input bytes.

        Args:
            image_bytes: Request-local normalized image bytes.

        Returns:
            Configured classification result.
        """
        self.received_image_bytes = image_bytes
        return self.classification


class _FailingFoodClassifier:
    """Fake food classifier that fails safely."""

    def classify_food(self, _image_bytes: bytes) -> FoodClassification | None:
        """Raise a stable vision error.

        Args:
            image_bytes: Request-local normalized image bytes.

        Raises:
            VisionError: Always raised.
        """
        raise VisionError("classifier unavailable")


def _settings(
    *,
    supplement_image_max_bytes: int = 5 * 1024 * 1024,
    supplement_image_max_pixels: int = 12_000_000,
    enable_food_yolo_detector: bool = False,
    enable_food_dino_classifier: bool = False,
) -> Settings:
    """Return settings for meal image analysis tests.

    Args:
        supplement_image_max_bytes: Maximum image byte size.
        supplement_image_max_pixels: Maximum decoded image pixels.
        enable_food_yolo_detector: Whether the optional food detector is enabled.
        enable_food_dino_classifier: Whether the optional food classifier is enabled.

    Returns:
        Settings object.
    """
    return Settings(
        supplement_image_max_bytes=supplement_image_max_bytes,
        supplement_image_max_pixels=supplement_image_max_pixels,
        enable_food_yolo_detector=enable_food_yolo_detector,
        meal_yolo_model_path=("/app/Food-backend/best.pt" if enable_food_yolo_detector else None),
        enable_food_dino_classifier=enable_food_dino_classifier,
        meal_food_classifier_exp16b_model_path=(
            "/app/Food-backend/best.pt" if enable_food_dino_classifier else None
        ),
    )


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


def _png_bytes(size: tuple[int, int] = (3, 2)) -> bytes:
    """Return a tiny PNG image.

    Args:
        size: Image size.

    Returns:
        PNG image bytes.
    """
    buffer = BytesIO()
    Image.new("RGB", size, color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(data: bytes, content_type: str = "image/png") -> UploadFile:
    """Build an UploadFile for service tests.

    Args:
        data: File bytes.
        content_type: Declared upload MIME type.

    Returns:
        UploadFile object.
    """
    return UploadFile(
        file=BytesIO(data),
        filename="raw-client-name.png",
        headers=Headers({"content-type": content_type}),
    )


def _image_metadata(sha256: str = "a" * 64) -> ValidatedMealImage:
    """Return validated image metadata fixture.

    Args:
        sha256: Image SHA-256 hex digest.

    Returns:
        Validated meal image metadata.
    """
    return ValidatedMealImage(
        sha256=sha256,
        mime_type="image/png",
        size_bytes=128,
        width=3,
        height=2,
        normalized_bytes=_png_bytes(),
    )


def _food_detection(label: str = "비빔밥", confidence: float = 0.88) -> FoodDetection:
    """Return a sanitized food detection fixture.

    Args:
        label: Candidate label.
        confidence: Candidate confidence.

    Returns:
        Food detection fixture.
    """
    return FoodDetection(
        label=label,
        confidence=confidence,
        bbox=BoundingBox(
            x=1,
            y=2,
            width=10,
            height=12,
            confidence=confidence,
            label=label,
            model="food_yolo_local:best.pt",
        ),
        model="food_yolo_local:best.pt",
    )


def _food_classification(label: str = "pizza", confidence: float = 0.93) -> FoodClassification:
    """Return a sanitized food classification fixture.

    Args:
        label: English class key.
        confidence: Candidate confidence.

    Returns:
        Food classification fixture.
    """
    return FoodClassification(
        name_en=label,
        display_name="피자",
        confidence=confidence,
        bbox=BoundingBox(
            x=0,
            y=0,
            width=3,
            height=2,
            confidence=confidence,
            label=label,
            model="food_dino_exp16b:probe_head.pt",
        ),
        model="food_dino_exp16b:probe_head.pt",
        nutrition={
            "serving_g": "150.0",
            "kcal_100g": "250.0",
            "carb_g": "30.0",
            "sugar_g": "4.0",
            "fat_g": "9.0",
            "protein_g": "11.0",
            "sodium_mg": "550.0",
            "chol_mg": "18.0",
            "sat_fat_g": "3.0",
            "trans_fat_g": "0.1",
        },
    )


def _fried_chicken_nutrition() -> FoodNutrition:
    """Return a seeded-style food nutrition row for the fried-chicken class.

    Returns:
        Active food nutrition row mirroring the migration 0027 seed values.
    """
    return FoodNutrition(
        class_en="fried-chicken",
        class_ko="후라이드치킨",
        n_source_codes=43,
        serving_g=Decimal("217.0"),
        kcal_100g=Decimal("236.26"),
        carb_g=Decimal("21.37"),
        sugar_g=Decimal("4.98"),
        fat_g=Decimal("11.69"),
        protein_g=Decimal("11.37"),
        sodium_mg=Decimal("355.92"),
        chol_mg=Decimal("14.93"),
        sat_fat_g=Decimal("0.4"),
        trans_fat_g=Decimal("0.83"),
        source="aihub_taxo59_csv",
        is_active=True,
    )


def _existing_preview(image_sha256: str) -> tuple[MealRecord, FoodImageAnalysisRun]:
    """Return an existing meal preview and analysis run fixture.

    Args:
        image_sha256: Stored image hash.

    Returns:
        Meal record and food image analysis run.
    """
    now = datetime.now(UTC)
    meal = MealRecord(
        id=uuid4(),
        owner_subject="https://auth.example.com/::user_123",
        client_request_id="client-1",
        eaten_at=now,
        meal_type=MealType.LUNCH.value,
        source="camera",
        status=MealAnalysisStatus.REQUIRES_CONFIRMATION.value,
        nutrition_summary={"items": [], "totals": {}},
        created_at=now,
        updated_at=now,
    )
    run = FoodImageAnalysisRun(
        id=uuid4(),
        owner_subject=meal.owner_subject,
        client_request_id=meal.client_request_id,
        meal_id=meal.id,
        image_sha256=image_sha256,
        image_mime_type="image/png",
        image_size_bytes=128,
        status=MealAnalysisStatus.REQUIRES_CONFIRMATION.value,
        detected_items_snapshot={"items": []},
        nutrition_estimate_snapshot={"status": "analysis_unavailable", "totals": {}},
        warning_codes=["manual_entry_required"],
        created_at=now,
        updated_at=now,
    )
    return meal, run


@pytest.mark.asyncio
async def test_read_and_validate_meal_image_returns_hash_and_dimensions() -> None:
    """Verify valid food images return only bounded image metadata."""
    data = _png_bytes()

    result = await read_and_validate_meal_image(_upload(data), _settings())

    assert result.sha256 == hashlib.sha256(data).hexdigest()
    assert result.mime_type == "image/png"
    assert result.size_bytes == len(data)
    assert (result.width, result.height) == (3, 2)


@pytest.mark.asyncio
async def test_read_and_validate_meal_image_rejects_spoofed_content_type() -> None:
    """Verify declared MIME type must match image magic bytes."""
    with pytest.raises(MealImageValidationError) as exc_info:
        await read_and_validate_meal_image(_upload(_png_bytes(), "image/jpeg"), _settings())

    assert exc_info.value.code == "unsupported_media_type"
    assert exc_info.value.status_code == 415


@pytest.mark.asyncio
async def test_create_meal_image_preview_stores_manual_entry_preview_only() -> None:
    """Verify food image preview rows contain no raw image or provider payload."""
    fake_session = _FakeStoreSession()
    eaten_at = datetime(2026, 5, 27, 12, 30, tzinfo=UTC)

    result = await create_meal_image_analysis_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image_metadata=_image_metadata(),
        meal_type=MealType.LUNCH,
        eaten_at=eaten_at,
        client_request_id="client-1",
        settings=_settings(),
    )

    assert result.reused_existing is False
    assert fake_session.added == [result.meal_record, result.analysis_run]
    # persist_scope adds one flush on scope exit, on top of the in-body flush.
    assert fake_session.flush_count == 2
    assert fake_session.refreshed == [result.meal_record, result.analysis_run]
    assert result.meal_record.meal_type == "lunch"
    assert result.meal_record.eaten_at == eaten_at
    assert result.meal_record.nutrition_summary == {
        "status": "analysis_unavailable",
        "items": [],
        "totals": {},
        "detector_used": False,
        "classifier_used": False,
    }
    assert result.analysis_run.media_object_id is None
    assert result.analysis_run.image_sha256 == "a" * 64
    assert result.analysis_run.detected_items_snapshot == {"items": []}
    assert result.analysis_run.nutrition_estimate_snapshot == {
        "status": "analysis_unavailable",
        "items": [],
        "totals": {},
        "detector_used": False,
        "classifier_used": False,
    }
    serialized_records = str(result.meal_record.__dict__) + str(result.analysis_run.__dict__)
    assert "raw-client-name" not in serialized_records
    assert "provider_payload" not in serialized_records
    assert "image_bytes" not in serialized_records


@pytest.mark.asyncio
async def test_create_meal_image_preview_uses_food_dino_classifier_candidate() -> None:
    """Verify enabled food classifier stores review candidates and nutrition estimates."""
    fake_session = _FakeStoreSession()
    classifier = _FakeFoodClassifier(_food_classification())

    result = await create_meal_image_analysis_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image_metadata=_image_metadata(),
        meal_type=MealType.LUNCH,
        eaten_at=None,
        client_request_id="client-1",
        settings=_settings(enable_food_dino_classifier=True),
        food_classifier=classifier,
    )

    assert classifier.received_image_bytes == _png_bytes()
    assert result.analysis_run.classifier_model == "food_dino_exp16b:probe_head.pt"
    assert result.analysis_run.detector_model is None
    assert result.analysis_run.detected_items_snapshot["items"][0]["display_name"] == "피자"
    assert result.analysis_run.detected_items_snapshot["items"][0]["class_en"] == "pizza"
    assert result.analysis_run.warning_codes == ["food_classification_review_required"]

    preview = meal_image_analysis_to_preview(result)
    assert preview.food_candidates[0].display_name == "피자"
    assert preview.food_candidates[0].kcal == 375.0
    assert preview.food_candidates[0].protein_g == 16.5
    assert preview.food_candidates[0].portion_amount == 150.0
    assert preview.food_candidates[0].portion_unit == "g"
    assert preview.pipeline_metadata.classifier_used is True
    assert preview.pipeline_metadata.detector_used is False
    assert preview.pipeline_metadata.requires_manual_entry is False
    assert result.analysis_run.nutrition_estimate_snapshot["totals"]["kcal"] == 375.0
    serialized_records = str(result.meal_record.__dict__) + str(result.analysis_run.__dict__)
    assert "provider_payload" not in serialized_records
    assert "image_bytes" not in serialized_records


@pytest.mark.asyncio
async def test_create_meal_image_preview_ignores_blank_classifier_nutrition_values() -> None:
    """Verify blank optional nutrition strings do not abort food image analysis."""
    fake_session = _FakeStoreSession()
    classification = _food_classification()
    nutrition = dict(classification.nutrition or {})
    nutrition["sugar_g"] = ""
    classifier = _FakeFoodClassifier(replace(classification, nutrition=nutrition))

    result = await create_meal_image_analysis_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image_metadata=_image_metadata(),
        meal_type=MealType.LUNCH,
        eaten_at=None,
        client_request_id="client-blank-nutrition",
        settings=_settings(enable_food_dino_classifier=True),
        food_classifier=classifier,
    )

    assert result.analysis_run.nutrition_estimate_snapshot["status"] == ("detected_review_required")
    # The blank classifier nutrition string is coerced to None and dropped from
    # the snapshot rather than aborting analysis with a 500.
    item_nutrition = result.analysis_run.nutrition_estimate_snapshot["items"][0]["nutrition"]
    assert "sugar_g" not in item_nutrition
    assert item_nutrition["kcal"] is not None


@pytest.mark.asyncio
async def test_create_meal_image_preview_uses_food_yolo_candidates() -> None:
    """Verify enabled food YOLO stores review candidates without raw payloads."""
    fake_session = _FakeStoreSession()
    detector = _FakeFoodDetector([_food_detection()])

    result = await create_meal_image_analysis_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image_metadata=_image_metadata(),
        meal_type=MealType.LUNCH,
        eaten_at=None,
        client_request_id="client-1",
        settings=_settings(enable_food_yolo_detector=True),
        food_detector=detector,
    )

    assert detector.received_image_bytes == _png_bytes()
    # persist_scope adds one flush on scope exit, on top of the in-body flush.
    assert fake_session.flush_count == 2
    assert result.analysis_run.detector_model == "food_yolo_local:best.pt"
    assert result.analysis_run.detected_items_snapshot["items"][0]["display_name"] == "비빔밥"
    assert result.analysis_run.warning_codes == ["food_detection_review_required"]

    preview = meal_image_analysis_to_preview(result)
    assert preview.food_candidates[0].display_name == "비빔밥"
    assert preview.food_candidates[0].confidence == 0.88
    assert preview.pipeline_metadata.detector_used is True
    assert preview.pipeline_metadata.requires_manual_entry is False
    serialized_records = str(result.meal_record.__dict__) + str(result.analysis_run.__dict__)
    assert "provider_payload" not in serialized_records
    assert "image_bytes" not in serialized_records


@pytest.mark.asyncio
async def test_create_meal_image_preview_attaches_class_average_nutrition() -> None:
    """Verify a detection matching a seeded class yields advisory nutrition totals."""
    fake_session = _FakeStoreSession(food_nutrition_rows=[_fried_chicken_nutrition()])
    detector = _FakeFoodDetector([_food_detection(label="fried-chicken", confidence=0.91)])

    result = await create_meal_image_analysis_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image_metadata=_image_metadata(),
        meal_type=MealType.LUNCH,
        eaten_at=None,
        client_request_id="client-1",
        settings=_settings(enable_food_yolo_detector=True),
        food_detector=detector,
    )

    snapshot = result.analysis_run.nutrition_estimate_snapshot
    assert snapshot["status"] == "detected_review_required"
    assert snapshot["basis"] == "class_average_per_serving"
    assert snapshot["precision_note"] == "demo_class_average_not_medical_or_prescriptive"

    item = snapshot["items"][0]
    assert item["display_name"] == "fried-chicken"
    assert item["source"] == "vision"
    # 236.26 kcal/100g * 217.0g / 100 = 512.68 kcal for one class-average serving.
    assert item["nutrition"]["kcal"] == 512.68
    assert item["nutrition"]["protein_g"] == 24.67

    totals = snapshot["totals"]
    assert totals["kcal"] == 512.68
    assert totals["sodium_mg"] == round(355.92 * 2.17, 2)
    assert result.meal_record.nutrition_summary == snapshot


@pytest.mark.asyncio
async def test_create_meal_image_preview_leaves_unmatched_detection_without_nutrition() -> None:
    """Verify a detection without a seeded class stays vision-only with empty totals."""
    fake_session = _FakeStoreSession(food_nutrition_rows=[])
    detector = _FakeFoodDetector([_food_detection(label="unknown-food", confidence=0.7)])

    result = await create_meal_image_analysis_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image_metadata=_image_metadata(),
        meal_type=MealType.LUNCH,
        eaten_at=None,
        client_request_id="client-1",
        settings=_settings(enable_food_yolo_detector=True),
        food_detector=detector,
    )

    snapshot = result.analysis_run.nutrition_estimate_snapshot
    assert snapshot["totals"] == {}
    assert "basis" not in snapshot
    assert "precision_note" not in snapshot
    item = snapshot["items"][0]
    assert item["source"] == "vision"
    assert "nutrition" not in item


@pytest.mark.asyncio
async def test_create_meal_image_preview_degrades_when_food_yolo_fails() -> None:
    """Verify detector failures degrade to manual entry without leaking details."""
    fake_session = _FakeStoreSession()

    result = await create_meal_image_analysis_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image_metadata=_image_metadata(),
        meal_type=MealType.LUNCH,
        eaten_at=None,
        client_request_id="client-1",
        settings=_settings(enable_food_yolo_detector=True),
        food_detector=_FailingFoodDetector(),
    )

    assert result.analysis_run.detector_model == "food_yolo_local:best.pt"
    assert result.analysis_run.detected_items_snapshot == {"items": []}
    assert result.analysis_run.warning_codes == [
        "food_detector_unavailable",
        "manual_entry_required",
    ]

    preview = meal_image_analysis_to_preview(result)
    assert preview.food_candidates == []
    assert preview.pipeline_metadata.detector_used is False
    assert preview.pipeline_metadata.requires_manual_entry is True


@pytest.mark.asyncio
async def test_create_meal_image_preview_degrades_when_food_classifier_fails() -> None:
    """Verify classifier failures degrade to manual entry without leaking details."""
    fake_session = _FakeStoreSession()

    result = await create_meal_image_analysis_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image_metadata=_image_metadata(),
        meal_type=MealType.LUNCH,
        eaten_at=None,
        client_request_id="client-1",
        settings=_settings(enable_food_dino_classifier=True),
        food_classifier=_FailingFoodClassifier(),
    )

    assert result.analysis_run.classifier_model == "food_dino_exp16b:probe_head.pt"
    assert result.analysis_run.detected_items_snapshot == {"items": []}
    assert result.analysis_run.warning_codes == [
        "food_classifier_unavailable",
        "manual_entry_required",
    ]

    preview = meal_image_analysis_to_preview(result)
    assert preview.food_candidates == []
    assert preview.pipeline_metadata.classifier_used is False
    assert preview.pipeline_metadata.requires_manual_entry is True


@pytest.mark.asyncio
async def test_create_meal_image_preview_reuses_matching_idempotency_key() -> None:
    """Verify matching idempotency keys reuse existing safe previews."""
    meal, run = _existing_preview("a" * 64)
    fake_session = _FakeStoreSession(existing_run=run, existing_meal=meal)

    result = await create_meal_image_analysis_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image_metadata=_image_metadata(),
        meal_type=MealType.DINNER,
        eaten_at=None,
        client_request_id="client-1",
        settings=_settings(),
    )

    assert result.reused_existing is True
    assert result.meal_record is meal
    assert result.analysis_run is run
    assert fake_session.added == []
    assert fake_session.refreshed == []


@pytest.mark.asyncio
async def test_create_meal_image_preview_rejects_idempotency_conflict() -> None:
    """Verify idempotency keys cannot be reused for different image hashes."""
    meal, run = _existing_preview("b" * 64)
    fake_session = _FakeStoreSession(existing_run=run, existing_meal=meal)

    with pytest.raises(MealImageAnalysisConflictError):
        await create_meal_image_analysis_preview(
            session=cast(AsyncSession, fake_session),
            user=_user(),
            image_metadata=_image_metadata("a" * 64),
            meal_type=MealType.LUNCH,
            eaten_at=None,
            client_request_id="client-1",
            settings=_settings(),
        )


def test_meal_image_analysis_to_preview_is_sanitized() -> None:
    """Verify API preview exposes only structured metadata and warning codes."""
    meal, run = _existing_preview("a" * 64)
    result = meal_image_analysis_to_preview(
        result=type(
            "Result",
            (),
            {
                "meal_record": meal,
                "analysis_run": run,
                "image_metadata": _image_metadata(),
                "reused_existing": True,
            },
        )()
    )

    assert result.analysis_id == run.id
    assert result.meal_id == meal.id
    assert result.status == MealAnalysisStatus.REQUIRES_CONFIRMATION
    assert result.meal_type == MealType.LUNCH
    assert result.food_candidates == []
    assert result.pipeline_metadata.raw_image_stored is False
    assert result.pipeline_metadata.raw_provider_payload_stored is False
    assert result.pipeline_metadata.requires_manual_entry is True
    assert result.algorithm_version == FOOD_IMAGE_ANALYSIS_ALGORITHM_VERSION


@pytest.mark.asyncio
async def test_confirm_meal_record_persists_user_confirmed_items() -> None:
    """Verify meal image preview confirmation stores only reviewed food rows."""
    meal, run = _existing_preview("a" * 64)
    fake_session = _FakeStoreSession(existing_run=run, existing_meal=meal)
    request = MealConfirmationRequest(
        analysis_id=run.id,
        meal_type=MealType.LUNCH,
        food_items=[
            MealFoodItemInput(
                display_name="비빔밥",
                portion_amount=1,
                portion_unit="bowl",
                kcal=520,
                carb_g=78,
                protein_g=18,
                fat_g=12,
                sodium_mg=820,
                confidence=0.88,
                source="vision",
            )
        ],
        user_confirmed=True,
    )

    result = await confirm_meal_record_from_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        meal_id=meal.id,
        request=request,
    )

    assert fake_session.committed is True
    assert result.meal_record.status == "confirmed"
    assert result.meal_record.confirmed_at is not None
    assert result.analysis_run is run
    assert run.status == "confirmed"
    assert result.meal_record.nutrition_summary == {
        "status": "user_confirmed",
        "items_count": 1,
        "totals": {
            "kcal": 520.0,
            "carb_g": 78.0,
            "protein_g": 18.0,
            "fat_g": 12.0,
            "sodium_mg": 820.0,
        },
    }
    assert result.food_items[0].food_name_text == "비빔밥"
    assert result.food_items[0].source == "vision"
    serialized_records = str(result.meal_record.__dict__) + str(result.food_items[0].__dict__)
    assert "provider_payload" not in serialized_records
    assert "image_bytes" not in serialized_records

    response = meal_confirmation_to_response(result)
    assert response.status == MealAnalysisStatus.CONFIRMED
    assert response.food_items[0].display_name == "비빔밥"
    assert response.food_items[0].kcal == 520
    assert response.nutrition_summary["status"] == "user_confirmed"


def test_meal_record_to_response_attaches_food_catalog_reference() -> None:
    """Verify confirmed meal response includes safe food taxonomy metadata."""
    meal, _run = _existing_preview("a" * 64)
    now = datetime.now(UTC)
    meal.status = MealAnalysisStatus.CONFIRMED.value
    meal.confirmed_at = now
    catalog_item_id = uuid4()
    food_item = MealFoodItem(
        id=uuid4(),
        meal_id=meal.id,
        food_name_text="된장찌개",
        food_catalog_item_id=catalog_item_id,
        portion_amount=1,
        portion_unit="bowl",
        kcal=180,
        source="database_match",
        sort_order=0,
        created_at=now,
        updated_at=now,
    )

    response = meal_record_to_response(
        meal,
        [food_item],
        catalog_item_refs={
            catalog_item_id: FoodCatalogItemReference(
                cuisine_code="korean",
                course_code="soup_stew",
                canonical_name_ko="된장찌개",
                canonical_name_en="Soybean Paste Stew",
            )
        },
    )

    assert response.food_items[0].food_catalog_item_id == catalog_item_id
    assert response.food_items[0].catalog_item is not None
    assert response.food_items[0].catalog_item.cuisine_code == "korean"


@pytest.mark.asyncio
async def test_confirm_meal_record_rejects_mismatched_analysis_id() -> None:
    """Verify confirmation cannot attach another meal's analysis preview."""
    meal, run = _existing_preview("a" * 64)
    run.meal_id = uuid4()
    fake_session = _FakeStoreSession(existing_run=run, existing_meal=meal)

    with pytest.raises(MealConfirmationValidationError):
        await confirm_meal_record_from_preview(
            session=cast(AsyncSession, fake_session),
            user=_user(),
            meal_id=meal.id,
            request=MealConfirmationRequest(
                analysis_id=run.id,
                food_items=[MealFoodItemInput(display_name="수정 음식")],
                user_confirmed=True,
            ),
        )


@pytest.mark.asyncio
async def test_confirm_meal_record_rejects_non_review_state() -> None:
    """Verify already-confirmed meal previews are not silently overwritten."""
    meal, run = _existing_preview("a" * 64)
    meal.status = MealAnalysisStatus.CONFIRMED.value
    fake_session = _FakeStoreSession(existing_run=run, existing_meal=meal)

    with pytest.raises(MealPreviewStateError):
        await confirm_meal_record_from_preview(
            session=cast(AsyncSession, fake_session),
            user=_user(),
            meal_id=meal.id,
            request=MealConfirmationRequest(
                analysis_id=run.id,
                food_items=[MealFoodItemInput(display_name="수정 음식")],
                user_confirmed=True,
            ),
        )


def _confirm_request(run_id: object) -> MealConfirmationRequest:
    """Build a minimal valid confirmation request for persist_scope contract tests."""
    return MealConfirmationRequest(
        analysis_id=run_id,
        meal_type=MealType.LUNCH,
        food_items=[
            MealFoodItemInput(
                display_name="비빔밥",
                portion_amount=1,
                portion_unit="bowl",
                kcal=520,
                confidence=0.88,
                source="vision",
            )
        ],
        user_confirmed=True,
    )


@pytest.mark.asyncio
async def test_create_preview_owns_transaction_in_legacy_mode() -> None:
    """Legacy (get_async_session) sessions commit the meal preview exactly once."""
    fake_session = _FakeStoreSession()  # no marker → OWN mode

    await create_meal_image_analysis_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image_metadata=_image_metadata(),
        meal_type=MealType.LUNCH,
        eaten_at=None,
        client_request_id="client-own",
        settings=_settings(),
    )

    assert fake_session.commits == 1


@pytest.mark.asyncio
async def test_create_preview_participates_in_request_managed_transaction() -> None:
    """RLS (get_rls_context_session) sessions never commit; the dependency owns the tx."""
    fake_session = _FakeStoreSession(request_managed=True)

    await create_meal_image_analysis_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image_metadata=_image_metadata(),
        meal_type=MealType.LUNCH,
        eaten_at=None,
        client_request_id="client-participate",
        settings=_settings(),
    )

    assert fake_session.commits == 0


@pytest.mark.asyncio
async def test_confirm_owns_transaction_in_legacy_mode() -> None:
    """Legacy sessions commit the confirmation (meal update + food items) exactly once."""
    meal, run = _existing_preview("a" * 64)
    fake_session = _FakeStoreSession(existing_run=run, existing_meal=meal)  # OWN mode

    await confirm_meal_record_from_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        meal_id=meal.id,
        request=_confirm_request(run.id),
    )

    assert fake_session.commits == 1


@pytest.mark.asyncio
async def test_confirm_participates_in_request_managed_transaction() -> None:
    """RLS sessions never commit the confirmation; the dependency owns the tx."""
    meal, run = _existing_preview("a" * 64)
    fake_session = _FakeStoreSession(existing_run=run, existing_meal=meal, request_managed=True)

    await confirm_meal_record_from_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        meal_id=meal.id,
        request=_confirm_request(run.id),
    )

    assert fake_session.commits == 0


@pytest.mark.asyncio
async def test_create_preview_reuse_owns_transaction_in_legacy_mode() -> None:
    """Legacy sessions commit the read-only idempotency-reuse path exactly once.

    The reuse branch performs no writes; persist_scope OWN mode must still commit the
    autobegun read transaction (reproducing the old ``async with session.begin()`` exit).
    """
    meal, run = _existing_preview("a" * 64)
    fake_session = _FakeStoreSession(existing_run=run, existing_meal=meal)  # OWN mode

    result = await create_meal_image_analysis_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image_metadata=_image_metadata(),
        meal_type=MealType.DINNER,
        eaten_at=None,
        client_request_id="client-1",
        settings=_settings(),
    )

    assert result.reused_existing is True
    assert fake_session.added == []  # read-only reuse: no rows written
    assert fake_session.commits == 1


@pytest.mark.asyncio
async def test_create_preview_reuse_participates_in_request_managed_transaction() -> None:
    """RLS sessions never commit the reuse path; the dependency owns the tx."""
    meal, run = _existing_preview("a" * 64)
    fake_session = _FakeStoreSession(existing_run=run, existing_meal=meal, request_managed=True)

    result = await create_meal_image_analysis_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        image_metadata=_image_metadata(),
        meal_type=MealType.DINNER,
        eaten_at=None,
        client_request_id="client-1",
        settings=_settings(),
    )

    assert result.reused_existing is True
    assert fake_session.commits == 0


def _confirm_request_without_analysis() -> MealConfirmationRequest:
    """Build a valid confirmation request that carries no analysis run id."""
    return MealConfirmationRequest(
        meal_type=MealType.LUNCH,
        food_items=[
            MealFoodItemInput(
                display_name="비빔밥",
                portion_amount=1,
                portion_unit="bowl",
                kcal=520,
                confidence=0.88,
                source="vision",
            )
        ],
        user_confirmed=True,
    )


@pytest.mark.asyncio
async def test_confirm_without_analysis_id_owns_transaction_in_legacy_mode() -> None:
    """Legacy sessions commit a confirm with no analysis run exactly once.

    Exercises the ``analysis_run is None`` confirm branch (meal update + food items only)
    under persist_scope OWN mode.
    """
    meal, _run = _existing_preview("a" * 64)
    fake_session = _FakeStoreSession(existing_meal=meal)  # OWN, no analysis run

    await confirm_meal_record_from_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        meal_id=meal.id,
        request=_confirm_request_without_analysis(),
    )

    assert fake_session.commits == 1


@pytest.mark.asyncio
async def test_confirm_without_analysis_id_participates_in_request_managed_transaction() -> None:
    """RLS sessions never commit the no-analysis-run confirm; the dependency owns the tx."""
    meal, _run = _existing_preview("a" * 64)
    fake_session = _FakeStoreSession(existing_meal=meal, request_managed=True)

    await confirm_meal_record_from_preview(
        session=cast(AsyncSession, fake_session),
        user=_user(),
        meal_id=meal.id,
        request=_confirm_request_without_analysis(),
    )

    assert fake_session.commits == 0
