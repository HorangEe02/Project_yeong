"""User supplement registration, lookup, and deletion services."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any
from uuid import UUID

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import resolve_nutrition_reference_root
from src.db.tx import persist_scope
from src.models.db.supplement import (
    SupplementAnalysisRun,
    SupplementCategory,
    SupplementProductCategory,
    UserSupplement,
    UserSupplementIngredient,
)
from src.models.schemas.supplement import (
    USER_SUPPLEMENT_EVIDENCE_REF_LIMIT,
    USER_SUPPLEMENT_EVIDENCE_REF_MAX_LENGTH,
    SupplementAnalysisStatus,
    SupplementIngredientCandidate,
    SupplementIntakeSchedule,
    SupplementServing,
    UserSupplementCreate,
    UserSupplementListResponse,
    UserSupplementResponse,
)
from src.models.schemas.taxonomy import SupplementCategorySummary
from src.security.auth import AuthenticatedUser
from src.security.subjects import build_owner_subject
from src.services.supplement_matching import match_supplement_product
from src.services.taxonomy_catalog import (
    TaxonomyFilterNotFoundError,
    resolve_supplement_category_filter,
)

REFERENCE_DATA_PATH = resolve_nutrition_reference_root() / "nutrient"
NUTRIENT_CODES_PATH = REFERENCE_DATA_PATH / "nutrient_codes.json"


@dataclass(frozen=True)
class UserSupplementStoreResult:
    """Stored user supplement result.

    Attributes:
        supplement: Persisted user supplement row.
        ingredients: Persisted ingredient rows.
        categories: Curated categories attached through the matched reference product.
    """

    supplement: UserSupplement
    ingredients: list[UserSupplementIngredient]
    categories: list[SupplementCategorySummary] = field(default_factory=list)


class SupplementRegistrationError(ValueError):
    """Base error for user supplement registration failures."""


class SupplementRegistrationValidationError(SupplementRegistrationError):
    """Raised when a confirmed supplement payload violates server validation rules."""


class SupplementPreviewNotFoundError(SupplementRegistrationError):
    """Raised when a preview row is absent or inaccessible to the current user."""


class SupplementPreviewStateError(SupplementRegistrationError):
    """Raised when a preview row cannot be confirmed in its current state."""


class SupplementPreviewExpiredError(SupplementRegistrationError):
    """Raised when a preview row expired before user confirmation."""


async def create_user_supplement_from_confirmation(
    session: AsyncSession,
    user: AuthenticatedUser,
    request: UserSupplementCreate,
    _settings: object | None = None,
) -> UserSupplementStoreResult:
    """Persist a user-confirmed supplement and optional preview confirmation.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        request: User-confirmed supplement creation request.
        _settings: Optional route settings reserved for audit-compatible callers.

    Returns:
        Persisted supplement and ingredient rows.

    Raises:
        SupplementRegistrationValidationError: If nutrient codes are not in the allowlist.
        SupplementPreviewNotFoundError: If `analysis_id` is absent for this owner.
        SupplementPreviewExpiredError: If the linked preview has expired.
        SupplementPreviewStateError: If the linked preview was already confirmed or failed.
    """
    _validate_nutrient_codes(request)
    owner_subject = build_owner_subject(user)
    now = datetime.now(UTC)

    # Validate the user-chosen category before any write so an unknown key
    # returns 422 without leaving a partial record.
    chosen_category = await _resolve_chosen_category(session, request.category_key)

    preview = await _get_owned_preview_for_confirmation(
        session,
        owner_subject,
        request.analysis_id,
        now,
    )
    evidence_refs = _validate_preview_evidence_refs(request.evidence_refs, preview)
    match = await match_supplement_product(session, request)
    supplement = UserSupplement(
        owner_subject=owner_subject,
        source_analysis_run_id=preview.id if preview is not None else None,
        matched_product_id=match.matched_product_id,
        display_name=request.display_name,
        manufacturer=request.manufacturer,
        category_key=chosen_category.category_key if chosen_category is not None else None,
        serving_snapshot=request.serving.model_dump(mode="json", exclude_none=True),
        intake_schedule=(
            request.intake_schedule.model_dump(mode="json", exclude_none=True)
            if request.intake_schedule is not None
            else {}
        ),
        precaution_snapshot=request.precaution_snapshot,
        evidence_refs=evidence_refs,
        user_confirmed_at=now,
    )
    async with persist_scope(session):
        session.add(supplement)
        await session.flush()

        ingredients = [
            UserSupplementIngredient(
                user_supplement_id=supplement.id,
                display_name=ingredient.display_name,
                nutrient_code=ingredient.nutrient_code,
                amount=_decimal_or_none(ingredient.amount),
                unit=ingredient.unit,
                daily_value_percent=_decimal_or_none(ingredient.daily_value_percent),
                confidence=Decimal(str(ingredient.confidence)),
                source=ingredient.source,
                sort_order=index,
            )
            for index, ingredient in enumerate(request.ingredients)
        ]
        for ingredient in ingredients:
            session.add(ingredient)

        if preview is not None:
            preview.status = SupplementAnalysisStatus.CONFIRMED.value
            preview.confirmed_at = now
            preview.match_snapshot = {
                "matched_product_candidates": [
                    candidate.model_dump(mode="json") for candidate in match.candidates
                ]
            }
            if match.matched_source_manifest_version is not None:
                preview.source_manifest_version = match.matched_source_manifest_version

    await session.refresh(supplement)
    product_categories = await _load_categories_for_products(
        session,
        [supplement.matched_product_id] if supplement.matched_product_id else [],
    )
    chosen_by_key = (
        {chosen_category.category_key: _category_summary(chosen_category)}
        if chosen_category is not None
        else {}
    )
    return UserSupplementStoreResult(
        supplement=supplement,
        ingredients=ingredients,
        categories=_effective_categories(
            supplement,
            chosen_by_key=chosen_by_key,
            product_categories=product_categories.get(supplement.matched_product_id, []),
        ),
    )


async def list_user_supplement_records(
    session: AsyncSession,
    user: AuthenticatedUser,
    limit: int,
    offset: int,
    *,
    category_key: str | None = None,
    category_id: UUID | None = None,
    q: str | None = None,
) -> UserSupplementListResponse:
    """List active user supplement records visible to the current owner.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        limit: Maximum row count.
        offset: Row offset.
        category_key: Optional curated supplement category key filter.
        category_id: Optional curated supplement category id filter.
        q: Optional supplement display-name or manufacturer substring filter.

    Returns:
        Paginated response model.
    """
    category = await resolve_supplement_category_filter(
        session,
        category_key=category_key,
        category_id=category_id,
    )
    records = await _list_owned_supplements(
        session,
        user,
        limit,
        offset,
        category=category,
        q=q,
    )
    ingredients = await _load_ingredients_for_supplements(
        session, [record.id for record in records]
    )
    categories = await _load_categories_for_products(
        session,
        [record.matched_product_id for record in records if record.matched_product_id],
    )
    chosen_by_key = await _load_user_chosen_categories(
        session,
        [record.category_key for record in records if record.category_key],
    )
    return UserSupplementListResponse(
        results=[
            user_supplement_to_response(
                record,
                ingredients.get(record.id, []),
                categories=_effective_categories(
                    record,
                    chosen_by_key=chosen_by_key,
                    product_categories=categories.get(record.matched_product_id, []),
                ),
            )
            for record in records
        ],
        limit=limit,
        offset=offset,
    )


async def get_user_supplement_record(
    session: AsyncSession,
    user: AuthenticatedUser,
    supplement_id: UUID,
) -> UserSupplementStoreResult | None:
    """Return one active user supplement if it belongs to the current owner.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        supplement_id: Persisted user supplement identifier.

    Returns:
        Supplement and ingredients, or None when absent or inaccessible.
    """
    record = await session.scalar(
        select(UserSupplement).where(
            UserSupplement.id == supplement_id,
            UserSupplement.owner_subject == build_owner_subject(user),
            UserSupplement.deleted_at.is_(None),
        )
    )
    if record is None:
        return None
    ingredients = await _load_ingredients_for_supplements(session, [record.id])
    categories = await _load_categories_for_products(
        session,
        [record.matched_product_id] if record.matched_product_id else [],
    )
    chosen_by_key = await _load_user_chosen_categories(
        session,
        [record.category_key] if record.category_key else [],
    )
    return UserSupplementStoreResult(
        supplement=record,
        ingredients=ingredients.get(record.id, []),
        categories=_effective_categories(
            record,
            chosen_by_key=chosen_by_key,
            product_categories=categories.get(record.matched_product_id, []),
        ),
    )


async def soft_delete_user_supplement(
    session: AsyncSession,
    user: AuthenticatedUser,
    supplement_id: UUID,
) -> bool:
    """Soft-delete one active user supplement owned by the current user.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        supplement_id: Persisted user supplement identifier.

    Returns:
        True when a row was marked deleted, False when not found.
    """
    record = await session.scalar(
        select(UserSupplement).where(
            UserSupplement.id == supplement_id,
            UserSupplement.owner_subject == build_owner_subject(user),
            UserSupplement.deleted_at.is_(None),
        )
    )
    if record is None:
        return False
    async with persist_scope(session):
        record.deleted_at = datetime.now(UTC)
    return True


def user_supplement_to_response(
    supplement: UserSupplement,
    ingredients: Iterable[UserSupplementIngredient],
    *,
    categories: Iterable[SupplementCategorySummary] | None = None,
) -> UserSupplementResponse:
    """Convert persisted supplement rows into the public API response.

    Args:
        supplement: Persisted user supplement row.
        ingredients: Persisted ingredient rows.
        categories: Curated categories attached through the matched reference product.

    Returns:
        Public user supplement response without owner identifiers.
    """
    sorted_ingredients = sorted(ingredients, key=lambda item: item.sort_order)
    return UserSupplementResponse(
        id=supplement.id,
        display_name=supplement.display_name,
        manufacturer=supplement.manufacturer,
        ingredients=[
            SupplementIngredientCandidate(
                display_name=ingredient.display_name,
                nutrient_code=ingredient.nutrient_code,
                amount=float(ingredient.amount) if ingredient.amount is not None else None,
                unit=ingredient.unit,
                confidence=float(ingredient.confidence),
                source=ingredient.source,
            )
            for ingredient in sorted_ingredients
        ],
        serving=SupplementServing.model_validate(supplement.serving_snapshot),
        intake_schedule=(
            SupplementIntakeSchedule.model_validate(supplement.intake_schedule)
            if supplement.intake_schedule
            else None
        ),
        precaution_snapshot=list(supplement.precaution_snapshot or []),
        evidence_refs=_safe_evidence_refs(supplement.evidence_refs),
        category_key=supplement.category_key,
        categories=list(categories or []),
        user_confirmed_at=supplement.user_confirmed_at,
        created_at=supplement.created_at,
    )


async def _resolve_chosen_category(
    session: AsyncSession,
    category_key: str | None,
) -> SupplementCategory | None:
    """Resolve and validate a user-chosen category key against the catalog.

    Args:
        session: Request-scoped async database session.
        category_key: Optional category key the user selected.

    Returns:
        The active category row, or None when no key was chosen.

    Raises:
        SupplementRegistrationValidationError: If a key was supplied but does not
            match an active catalog category (mapped to HTTP 422 by the route).
    """
    if category_key is None:
        return None
    try:
        return await resolve_supplement_category_filter(
            session,
            category_key=category_key,
            category_id=None,
        )
    except TaxonomyFilterNotFoundError as exc:
        raise SupplementRegistrationValidationError("선택한 영양제 분류를 찾을 수 없어요.") from exc


def _category_summary(category: SupplementCategory) -> SupplementCategorySummary:
    """Build a safe public category summary from a category row."""
    return SupplementCategorySummary(
        id=category.id,
        category_key=category.category_key,
        display_name=category.display_name,
        sort_order=category.sort_order,
    )


async def _load_user_chosen_categories(
    session: AsyncSession,
    category_keys: list[str],
) -> dict[str, SupplementCategorySummary]:
    """Resolve active curated categories for user-chosen keys, grouped by key.

    Args:
        session: Request-scoped async database session.
        category_keys: User-chosen category keys stored on supplement rows.

    Returns:
        Mapping from category key to public summary for keys that still resolve
        to an active catalog row. Deactivated/unknown keys are omitted so the
        response falls back to product-derived categories.
    """
    keys = [key for key in dict.fromkeys(category_keys) if key]
    if not keys:
        return {}
    rows = await session.scalars(
        select(SupplementCategory).where(
            SupplementCategory.category_key.in_(keys),
            SupplementCategory.is_active.is_(True),
        )
    )
    return {row.category_key: _category_summary(row) for row in rows.all()}


def _effective_categories(
    supplement: UserSupplement,
    *,
    chosen_by_key: dict[str, SupplementCategorySummary],
    product_categories: list[SupplementCategorySummary],
) -> list[SupplementCategorySummary]:
    """Pick the categories to surface: user choice when it resolves, else product.

    The user-chosen category is authoritative when it still maps to an active
    catalog row; otherwise the matched-product categories are used so display
    degrades gracefully without losing the stored key.
    """
    chosen = (
        chosen_by_key.get(supplement.category_key) if supplement.category_key is not None else None
    )
    if chosen is not None:
        return [chosen]
    return list(product_categories)


async def _get_owned_preview_for_confirmation(
    session: AsyncSession,
    owner_subject: str,
    analysis_id: UUID | None,
    now: datetime,
) -> SupplementAnalysisRun | None:
    """Load and validate the optional source preview for confirmation.

    Args:
        session: Request-scoped async database session.
        owner_subject: Issuer-qualified owner subject.
        analysis_id: Optional preview identifier.
        now: Current server time.

    Returns:
        Preview row or None when no analysis id is provided.

    Raises:
        SupplementPreviewNotFoundError: If the preview is absent for this owner.
        SupplementPreviewExpiredError: If the preview has expired.
        SupplementPreviewStateError: If the preview cannot be confirmed.
    """
    if analysis_id is None:
        return None
    preview = await session.scalar(
        select(SupplementAnalysisRun).where(
            SupplementAnalysisRun.id == analysis_id,
            SupplementAnalysisRun.owner_subject == owner_subject,
        )
    )
    if preview is None:
        raise SupplementPreviewNotFoundError("Supplement analysis preview was not found.")
    if preview.expires_at <= now:
        raise SupplementPreviewExpiredError("Supplement analysis preview has expired.")
    if preview.status != SupplementAnalysisStatus.REQUIRES_CONFIRMATION.value:
        raise SupplementPreviewStateError("Supplement analysis preview is not confirmable.")
    if preview.confirmed_at is not None:
        raise SupplementPreviewStateError("Supplement analysis preview was already confirmed.")
    return preview


def _validate_preview_evidence_refs(
    evidence_refs: list[str],
    preview: SupplementAnalysisRun | None,
) -> list[str]:
    """Validate confirmed evidence ids against the linked preview.

    Args:
        evidence_refs: User-confirmed evidence ids from the registration request.
        preview: Optional source analysis preview row.

    Returns:
        Safe evidence ids in request order.

    Raises:
        SupplementRegistrationValidationError: If refs are supplied without a
            source preview or any ref is absent from the preview evidence spans.
    """
    if not evidence_refs:
        return []
    if preview is None:
        raise SupplementRegistrationValidationError(
            "evidence_refs require a linked analysis preview."
        )
    allowed_refs = _preview_evidence_ref_ids(preview)
    unknown_refs = [ref for ref in evidence_refs if ref not in allowed_refs]
    if unknown_refs:
        raise SupplementRegistrationValidationError(
            "Unknown evidence_refs for analysis preview: " + ", ".join(unknown_refs[:5])
        )
    return list(evidence_refs)


def _preview_evidence_ref_ids(preview: SupplementAnalysisRun) -> set[str]:
    """Return evidence ids present in a preview parsed snapshot.

    Args:
        preview: Source analysis preview row.

    Returns:
        Set of sanitized evidence span ids.
    """
    snapshot = preview.parsed_snapshot if isinstance(preview.parsed_snapshot, dict) else {}
    spans = snapshot.get("evidence_spans")
    if not isinstance(spans, list):
        return set()
    ids: set[str] = set()
    for span in spans:
        if not isinstance(span, dict):
            continue
        span_id = span.get("span_id")
        if isinstance(span_id, str) and span_id.strip():
            ids.add(span_id.strip())
    return ids


def _safe_evidence_refs(value: object) -> list[str]:
    """Return bounded evidence refs from persisted JSON.

    Args:
        value: Persisted JSON value.

    Returns:
        Evidence refs safe for the public current-user response.
    """
    if not isinstance(value, list):
        return []
    refs: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        ref = item.strip()
        if not ref or len(ref) > USER_SUPPLEMENT_EVIDENCE_REF_MAX_LENGTH or ref in seen:
            continue
        seen.add(ref)
        refs.append(ref)
        if len(refs) >= USER_SUPPLEMENT_EVIDENCE_REF_LIMIT:
            break
    return refs


async def _list_owned_supplements(
    session: AsyncSession,
    user: AuthenticatedUser,
    limit: int,
    offset: int,
    *,
    category: SupplementCategory | None = None,
    q: str | None = None,
) -> list[UserSupplement]:
    """Load active supplement rows for a current user.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        limit: Maximum row count.
        offset: Row offset.
        category: Optional active category row to filter by.
        q: Optional display-name or manufacturer substring.

    Returns:
        Active supplement rows.
    """
    stmt = select(UserSupplement).where(
        UserSupplement.owner_subject == build_owner_subject(user),
        UserSupplement.deleted_at.is_(None),
    )
    if category is not None:
        stmt = (
            stmt.join(
                SupplementProductCategory,
                UserSupplement.matched_product_id == SupplementProductCategory.product_id,
            )
            .where(SupplementProductCategory.category_id == category.id)
            .distinct()
        )
    query_text = _normalized_query(q)
    if query_text:
        pattern = f"%{query_text}%"
        stmt = stmt.where(
            or_(
                UserSupplement.display_name.ilike(pattern),
                UserSupplement.manufacturer.ilike(pattern),
            )
        )
    result = await session.scalars(
        stmt.order_by(desc(UserSupplement.created_at)).limit(limit).offset(offset)
    )
    return list(result.all())


async def _load_categories_for_products(
    session: AsyncSession,
    product_ids: list[UUID],
) -> dict[UUID, list[SupplementCategorySummary]]:
    """Load active supplement categories grouped by product id.

    Args:
        session: Request-scoped async database session.
        product_ids: Matched reference product ids.

    Returns:
        Mapping from reference product id to public category summaries.
    """
    ids = list(dict.fromkeys(product_ids))
    if not ids:
        return {}
    result = await session.execute(
        select(SupplementProductCategory.product_id, SupplementCategory)
        .join(SupplementCategory, SupplementProductCategory.category_id == SupplementCategory.id)
        .where(
            SupplementProductCategory.product_id.in_(ids),
            SupplementCategory.is_active.is_(True),
        )
        .order_by(
            SupplementProductCategory.product_id.asc(),
            SupplementProductCategory.is_primary.desc(),
            SupplementProductCategory.sort_order.asc(),
            SupplementCategory.sort_order.asc(),
            SupplementCategory.display_name.asc(),
        )
    )
    grouped: dict[UUID, list[SupplementCategorySummary]] = {}
    for product_id, category in result.all():
        grouped.setdefault(product_id, []).append(
            SupplementCategorySummary(
                id=category.id,
                category_key=category.category_key,
                display_name=category.display_name,
                sort_order=category.sort_order,
            )
        )
    return grouped


def _normalized_query(value: str | None) -> str | None:
    """Trim optional query text and normalize blanks to None."""
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


async def _load_ingredients_for_supplements(
    session: AsyncSession,
    supplement_ids: list[UUID],
) -> dict[UUID, list[UserSupplementIngredient]]:
    """Load ingredient rows grouped by user supplement id.

    Args:
        session: Request-scoped async database session.
        supplement_ids: User supplement identifiers.

    Returns:
        Mapping from supplement id to ingredient rows.
    """
    if not supplement_ids:
        return {}
    result = await session.scalars(
        select(UserSupplementIngredient).where(
            UserSupplementIngredient.user_supplement_id.in_(supplement_ids)
        )
    )
    grouped: dict[UUID, list[UserSupplementIngredient]] = {}
    for ingredient in result.all():
        grouped.setdefault(ingredient.user_supplement_id, []).append(ingredient)
    return grouped


def _validate_nutrient_codes(request: UserSupplementCreate) -> None:
    """Validate confirmed nutrient codes against the local allowlist.

    Args:
        request: User-confirmed supplement creation request.

    Raises:
        SupplementRegistrationValidationError: If an unknown nutrient code is present.
    """
    provided_codes = {
        ingredient.nutrient_code for ingredient in request.ingredients if ingredient.nutrient_code
    }
    if not provided_codes:
        return
    allowed_codes = _load_nutrient_codes()
    unknown_codes = sorted(code for code in provided_codes if code not in allowed_codes)
    if unknown_codes:
        raise SupplementRegistrationValidationError(
            f"Unknown nutrient_code values: {', '.join(unknown_codes)}"
        )


@lru_cache(maxsize=1)
def _load_nutrient_codes() -> frozenset[str]:
    """Load nutrient code allowlist from local reference data.

    Returns:
        Frozen set of allowed nutrient code strings.

    Raises:
        SupplementRegistrationValidationError: If reference data is unavailable or invalid.
    """
    try:
        raw = json.loads(NUTRIENT_CODES_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SupplementRegistrationValidationError(
            "Nutrient code reference data is unavailable."
        ) from exc
    if not isinstance(raw, dict):
        raise SupplementRegistrationValidationError("Nutrient code reference data is invalid.")
    return frozenset(str(code) for code in raw)


def _decimal_or_none(value: float | None) -> Decimal | None:
    """Convert an optional float value to Decimal for database storage.

    Args:
        value: Optional numeric amount.

    Returns:
        Decimal amount or None.
    """
    if value is None:
        return None
    return Decimal(str(value))


async def load_active_supplement_context(
    session: AsyncSession,
    user: AuthenticatedUser,
    *,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Load confirmed supplement records as chatbot-safe snapshot context."""
    response = await list_user_supplement_records(session, user, limit, offset)
    return build_active_supplement_snapshot(response.results)


def build_active_supplement_snapshot(
    supplements: Iterable[UserSupplementResponse],
) -> dict[str, Any]:
    """Build the active supplement snapshot from confirmed user records only."""
    return {
        "registered_supplements": [
            {
                "supplement_id": str(supplement.id),
                "display_name": supplement.display_name,
                "manufacturer": supplement.manufacturer,
                "ingredients": [
                    {
                        "display_name": ingredient.display_name,
                        "nutrient_code": ingredient.nutrient_code,
                        "amount": ingredient.amount,
                        "unit": ingredient.unit,
                        "analysis_use": (
                            "standard_nutrient" if ingredient.nutrient_code else "label_only"
                        ),
                        "source": ingredient.source,
                    }
                    for ingredient in supplement.ingredients
                ],
                "serving": supplement.serving.model_dump(mode="json", exclude_none=True),
                "intake_schedule": (
                    supplement.intake_schedule.model_dump(mode="json", exclude_none=True)
                    if supplement.intake_schedule is not None
                    else None
                ),
                "user_confirmed_at": supplement.user_confirmed_at.isoformat(),
                "user_confirmed": True,
            }
            for supplement in supplements
        ],
        "checked_today": [],
        "policy": {
            "nutrient_code_required_for_standard_analysis": True,
            "unconfirmed_preview_excluded": True,
            "label_only_ingredients_do_not_drive_nutrient_analysis": True,
        },
    }
