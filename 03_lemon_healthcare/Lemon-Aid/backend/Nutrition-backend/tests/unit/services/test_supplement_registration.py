"""User supplement registration service tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Self, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.tx import REQUEST_MANAGED_TX
from src.models.db.supplement import (
    SupplementAnalysisRun,
    SupplementCategory,
    SupplementProduct,
    SupplementProductIngredient,
    UserSupplement,
    UserSupplementIngredient,
)
from src.models.schemas.supplement import SupplementAnalysisStatus, UserSupplementCreate
from src.security.auth import AuthenticatedUser
from src.services import supplement_registration as registration_service
from src.services.supplement_matching import normalize_supplement_text
from src.services.supplement_registration import (
    SupplementPreviewExpiredError,
    SupplementRegistrationValidationError,
    create_user_supplement_from_confirmation,
    get_user_supplement_record,
    list_user_supplement_records,
    soft_delete_user_supplement,
    user_supplement_to_response,
)


class _TransactionContext:
    """Async context manager used by fake sessions."""

    async def __aenter__(self) -> Self:
        """Enter the fake transaction.

        Returns:
            Context manager instance.
        """
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Exit the fake transaction.

        Args:
            *_exc_info: Exception details ignored by the fake context.

        Returns:
            None.
        """


class _ScalarResult:
    """Fake SQLAlchemy scalar result."""

    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def all(self) -> list[object]:
        """Return fake rows.

        Returns:
            Configured rows.
        """
        return self.rows


class _FakeRegistrationSession:
    """Fake async session for supplement registration service tests."""

    def __init__(
        self,
        *,
        scalar_result: object | None = None,
        scalars_results: list[list[object]] | None = None,
        execute_results: list[list[object]] | None = None,
    ) -> None:
        self.scalar_result = scalar_result
        self.scalars_results = [_ScalarResult(rows) for rows in (scalars_results or [])]
        self.execute_results = [_ScalarResult(rows) for rows in (execute_results or [])]
        self.added: list[object] = []
        self.committed = False
        self.refreshed: object | None = None
        self.flushed = False
        # A real AsyncSession always exposes ``.info``; persist_scope reads it.
        self.info: dict[str, object] = {}

    def begin(self) -> _TransactionContext:
        """Return a fake transaction context.

        Returns:
            Fake transaction context.
        """
        return _TransactionContext()

    async def scalar(self, _statement: object) -> object | None:
        """Return a configured scalar row.

        Args:
            _statement: SQLAlchemy select statement.

        Returns:
            Configured scalar row.
        """
        return self.scalar_result

    async def scalars(self, _statement: object) -> _ScalarResult:
        """Return the next configured scalar result.

        Args:
            _statement: SQLAlchemy select statement.

        Returns:
            Fake scalar result.
        """
        return self.scalars_results.pop(0)

    async def execute(self, _statement: object) -> _ScalarResult:
        """Return the next configured execute result.

        Args:
            _statement: SQLAlchemy statement.

        Returns:
            Fake row result.
        """
        if not self.execute_results:
            return _ScalarResult([])
        return self.execute_results.pop(0)

    def add(self, record: object) -> None:
        """Capture a persisted ORM object.

        Args:
            record: ORM object passed to the session.

        Returns:
            None.
        """
        self.added.append(record)

    async def flush(self) -> None:
        """Assign fake identifiers before child rows are built.

        Returns:
            None.
        """
        self.flushed = True
        for record in self.added:
            if isinstance(record, UserSupplement) and cast(object | None, record.id) is None:
                record.id = uuid4()

    async def commit(self) -> None:
        """Record a fake commit.

        Returns:
            None.
        """
        self.committed = True

    async def refresh(self, record: object) -> None:
        """Populate server-generated timestamps.

        Args:
            record: ORM object being refreshed.

        Returns:
            None.
        """
        if isinstance(record, UserSupplement):
            if cast(object | None, record.id) is None:
                record.id = uuid4()
            record.created_at = datetime.now(UTC)
            record.updated_at = datetime.now(UTC)
        self.refreshed = record


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


def _request(
    *,
    analysis_id: object | None = None,
    nutrient_code: str | None = "vitamin_d_ug",
    evidence_refs: list[str] | None = None,
    category_key: str | None = None,
) -> UserSupplementCreate:
    """Return a confirmed supplement creation request.

    Args:
        analysis_id: Optional source analysis id.
        nutrient_code: Ingredient nutrient code.
        evidence_refs: Optional preview evidence ids.
        category_key: Optional user-chosen curated category key.

    Returns:
        User supplement creation request.
    """
    payload = {
        "analysis_id": analysis_id,
        "display_name": "Vitamin D 1000 IU",
        "manufacturer": "Sample Nutrition",
        "ingredients": [
            {
                "display_name": "Vitamin D",
                "nutrient_code": nutrient_code,
                "amount": 25,
                "unit": "ug",
                "confidence": 1,
                "source": "user_confirmed",
            }
        ],
        "serving": {"amount": 1, "unit": "capsule", "daily_servings": 1},
        "intake_schedule": {"frequency": "daily", "time_of_day": ["morning"]},
        "user_confirmed": True,
    }
    if evidence_refs is not None:
        payload["evidence_refs"] = evidence_refs
    if category_key is not None:
        payload["category_key"] = category_key
    return UserSupplementCreate.model_validate(payload)


def _category(category_key: str = "비타민B") -> SupplementCategory:
    """Return a curated supplement category row.

    Args:
        category_key: Stable folder-derived category key.

    Returns:
        Active supplement category row.
    """
    return SupplementCategory(
        id=uuid4(),
        category_key=category_key,
        display_name=category_key,
        sort_order=1,
        is_active=True,
    )


def _preview(analysis_id: object | None = None, *, expired: bool = False) -> SupplementAnalysisRun:
    """Return a supplement analysis preview row.

    Args:
        analysis_id: Optional preview identifier.
        expired: Whether the preview should be expired.

    Returns:
        Supplement analysis preview row.
    """
    now = datetime.now(UTC)
    return SupplementAnalysisRun(
        id=analysis_id or uuid4(),
        owner_subject="https://auth.example.com/::user_123",
        client_request_id="client-1",
        status=SupplementAnalysisStatus.REQUIRES_CONFIRMATION.value,
        image_sha256="a" * 64,
        image_mime_type="image/png",
        image_size_bytes=128,
        ocr_provider="ollama",
        parsed_snapshot={
            "parsed_product": {"product_name": "Vitamin D 1000 IU"},
            "evidence_spans": [
                {
                    "span_id": "span-1",
                    "source_type": "ocr_layout",
                    "section_type": "supplement_facts",
                    "text_excerpt": "Vitamin D 25 ug",
                }
            ],
        },
        match_snapshot={"matched_product_candidates": []},
        warnings=[],
        algorithm_version="supplement-ollama-parser-v1.0.0",
        expires_at=now - timedelta(minutes=1) if expired else now + timedelta(minutes=30),
        created_at=now,
        updated_at=now,
    )


def _product() -> SupplementProduct:
    """Return a reference supplement product.

    Returns:
        Supplement product row.
    """
    return SupplementProduct(
        id=uuid4(),
        source_provider="mfds",
        source_product_id="P-001",
        product_name="Vitamin D 1000 IU",
        normalized_product_name=normalize_supplement_text("Vitamin D 1000 IU"),
        manufacturer="Sample Nutrition",
        source_payload={},
        source_manifest_version="mfds-2026-05",
    )


def _product_ingredient(product_id: object) -> SupplementProductIngredient:
    """Return a reference product ingredient.

    Args:
        product_id: Parent product id.

    Returns:
        Supplement product ingredient row.
    """
    return SupplementProductIngredient(
        id=uuid4(),
        product_id=product_id,
        standard_name="Vitamin D",
        nutrient_code="vitamin_d_ug",
        amount=Decimal("25"),
        unit="ug",
        source_payload={},
        sort_order=0,
    )


def _stored_supplement() -> UserSupplement:
    """Return a persisted user supplement fixture.

    Returns:
        User supplement row.
    """
    now = datetime.now(UTC)
    return UserSupplement(
        id=uuid4(),
        owner_subject="https://auth.example.com/::user_123",
        display_name="Vitamin D 1000 IU",
        manufacturer="Sample Nutrition",
        serving_snapshot={"amount": 1, "unit": "capsule", "daily_servings": 1},
        intake_schedule={"frequency": "daily", "time_of_day": ["morning"]},
        user_confirmed_at=now,
        created_at=now,
        updated_at=now,
    )


def _stored_ingredient(supplement_id: object) -> UserSupplementIngredient:
    """Return a persisted user supplement ingredient fixture.

    Args:
        supplement_id: Parent user supplement id.

    Returns:
        User supplement ingredient row.
    """
    return UserSupplementIngredient(
        id=uuid4(),
        user_supplement_id=supplement_id,
        display_name="Vitamin D",
        nutrient_code="vitamin_d_ug",
        amount=Decimal("25"),
        unit="ug",
        confidence=Decimal("1"),
        source="user_confirmed",
        sort_order=0,
    )


@pytest.mark.asyncio
async def test_create_user_supplement_confirms_preview_and_persists_rows() -> None:
    """Verify confirmed payloads are stored and linked to matched reference products."""
    product = _product()
    preview = _preview()
    session = _FakeRegistrationSession(
        scalar_result=preview,
        scalars_results=[[product], [_product_ingredient(product.id)]],
    )

    result = await create_user_supplement_from_confirmation(
        cast(AsyncSession, session),
        _user(),
        _request(analysis_id=preview.id, evidence_refs=["span-1"]),
    )

    assert session.flushed is True
    assert session.committed is True
    assert result.supplement in session.added
    assert result.ingredients[0] in session.added
    assert result.supplement.owner_subject == "https://auth.example.com/::user_123"
    assert result.supplement.source_analysis_run_id == preview.id
    assert result.supplement.matched_product_id == product.id
    assert result.supplement.evidence_refs == ["span-1"]
    assert result.ingredients[0].user_supplement_id == result.supplement.id
    assert preview.status == SupplementAnalysisStatus.CONFIRMED.value
    assert preview.confirmed_at is not None
    assert preview.source_manifest_version == "mfds-2026-05"
    assert preview.match_snapshot["matched_product_candidates"][0]["source_id"] == "mfds:P-001"


@pytest.mark.asyncio
async def test_create_user_supplement_allows_manual_ingredient_without_nutrient_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify manual un-mapped ingredients do not require reference allowlist data."""

    def fail_load_nutrient_codes() -> frozenset[str]:
        raise AssertionError("nutrient reference data should not be loaded")

    monkeypatch.setattr(
        registration_service,
        "_load_nutrient_codes",
        fail_load_nutrient_codes,
    )
    session = _FakeRegistrationSession(scalars_results=[[], []])

    result = await create_user_supplement_from_confirmation(
        cast(AsyncSession, session),
        _user(),
        _request(nutrient_code=None),
    )

    assert session.committed is True
    assert result.ingredients[0].nutrient_code is None


@pytest.mark.asyncio
async def test_create_user_supplement_rejects_unknown_nutrient_code() -> None:
    """Verify nutrient codes must be present in the deterministic allowlist."""
    session = _FakeRegistrationSession(scalars_results=[[], []])

    with pytest.raises(SupplementRegistrationValidationError):
        await create_user_supplement_from_confirmation(
            cast(AsyncSession, session),
            _user(),
            _request(nutrient_code="fake_code"),
        )


@pytest.mark.asyncio
async def test_create_user_supplement_stores_user_chosen_category() -> None:
    """Verify a valid user-chosen category is stored and becomes authoritative.

    The single ``scalar`` call resolves the category (no preview because
    ``analysis_id`` is None), so the fake session can return the category row.
    """
    session = _FakeRegistrationSession(
        scalar_result=_category("비타민B"),
        scalars_results=[[], []],
    )

    result = await create_user_supplement_from_confirmation(
        cast(AsyncSession, session),
        _user(),
        _request(analysis_id=None, category_key="비타민B"),
    )

    assert session.committed is True
    assert result.supplement.category_key == "비타민B"
    # The user choice overrides product-derived categories.
    assert [summary.category_key for summary in result.categories] == ["비타민B"]
    response = user_supplement_to_response(
        result.supplement,
        result.ingredients,
        categories=result.categories,
    )
    assert response.category_key == "비타민B"
    assert [summary.category_key for summary in response.categories] == ["비타민B"]


@pytest.mark.asyncio
async def test_create_user_supplement_rejects_unknown_category_key() -> None:
    """Verify an unknown category key fails validation before any write."""
    session = _FakeRegistrationSession(scalar_result=None, scalars_results=[[], []])

    with pytest.raises(SupplementRegistrationValidationError):
        await create_user_supplement_from_confirmation(
            cast(AsyncSession, session),
            _user(),
            _request(analysis_id=None, category_key="없는분류"),
        )

    # Validation happens before persistence, so nothing is committed.
    assert session.committed is False
    assert session.added == []


@pytest.mark.asyncio
async def test_create_user_supplement_without_category_leaves_key_null() -> None:
    """Verify omitting a category stores a null key and no override occurs."""
    session = _FakeRegistrationSession(scalars_results=[[], []])

    result = await create_user_supplement_from_confirmation(
        cast(AsyncSession, session),
        _user(),
        _request(analysis_id=None),
    )

    assert session.committed is True
    assert result.supplement.category_key is None
    response = user_supplement_to_response(
        result.supplement,
        result.ingredients,
        categories=result.categories,
    )
    assert response.category_key is None


@pytest.mark.asyncio
async def test_create_user_supplement_rejects_unknown_evidence_ref() -> None:
    """Verify confirmed evidence refs must exist in the linked preview."""
    preview = _preview()
    session = _FakeRegistrationSession(scalar_result=preview)

    with pytest.raises(SupplementRegistrationValidationError, match="Unknown evidence_refs"):
        await create_user_supplement_from_confirmation(
            cast(AsyncSession, session),
            _user(),
            _request(analysis_id=preview.id, evidence_refs=["missing-span"]),
        )

    assert session.committed is False


@pytest.mark.asyncio
async def test_create_user_supplement_rejects_evidence_ref_without_preview() -> None:
    """Verify evidence refs cannot be stored without a source preview."""
    session = _FakeRegistrationSession()

    with pytest.raises(SupplementRegistrationValidationError, match="linked analysis preview"):
        await create_user_supplement_from_confirmation(
            cast(AsyncSession, session),
            _user(),
            _request(evidence_refs=["span-1"]),
        )

    assert session.committed is False

    assert session.added == []


@pytest.mark.asyncio
async def test_create_user_supplement_rejects_expired_preview() -> None:
    """Verify expired previews cannot be confirmed."""
    preview = _preview(expired=True)
    session = _FakeRegistrationSession(scalar_result=preview, scalars_results=[[], []])

    with pytest.raises(SupplementPreviewExpiredError):
        await create_user_supplement_from_confirmation(
            cast(AsyncSession, session),
            _user(),
            _request(analysis_id=preview.id),
        )

    assert session.added == []


@pytest.mark.asyncio
async def test_list_get_and_soft_delete_user_supplements_are_owner_scoped() -> None:
    """Verify read and delete services operate through owner-scoped rows."""
    supplement = _stored_supplement()
    ingredient = _stored_ingredient(supplement.id)
    list_session = _FakeRegistrationSession(scalars_results=[[supplement], [ingredient]])

    list_response = await list_user_supplement_records(
        cast(AsyncSession, list_session),
        _user(),
        limit=20,
        offset=0,
    )

    assert list_response.results[0].display_name == "Vitamin D 1000 IU"
    assert "owner_subject" not in list_response.results[0].model_dump()

    get_session = _FakeRegistrationSession(scalar_result=supplement, scalars_results=[[ingredient]])
    get_result = await get_user_supplement_record(
        cast(AsyncSession, get_session),
        _user(),
        supplement.id,
    )

    assert get_result is not None
    assert (
        user_supplement_to_response(
            get_result.supplement,
            get_result.ingredients,
        )
        .ingredients[0]
        .nutrient_code
        == "vitamin_d_ug"
    )

    delete_session = _FakeRegistrationSession(scalar_result=supplement)
    deleted = await soft_delete_user_supplement(
        cast(AsyncSession, delete_session),
        _user(),
        supplement.id,
    )

    assert deleted is True
    assert delete_session.committed is True
    assert supplement.deleted_at is not None


@pytest.mark.asyncio
async def test_soft_delete_user_supplement_participates_in_request_transaction() -> None:
    """Request-managed sessions flush the soft delete but never commit it.

    Under the RLS Stage-2 seam (``get_rls_context_session``) the delete route owns
    the transaction; ``soft_delete_user_supplement`` must participate (flush only)
    so the per-request RLS GUCs survive to the dependency's single commit. A
    mid-service commit here would drop the GUCs and break the owner DELETE.
    """
    supplement = _stored_supplement()
    session = _FakeRegistrationSession(scalar_result=supplement)
    session.info[REQUEST_MANAGED_TX] = True

    deleted = await soft_delete_user_supplement(
        cast(AsyncSession, session),
        _user(),
        supplement.id,
    )

    assert deleted is True
    assert supplement.deleted_at is not None
    assert session.flushed is True  # the soft delete is flushed into the request tx
    assert session.committed is False  # the dependency owns the commit (GUC survives)
