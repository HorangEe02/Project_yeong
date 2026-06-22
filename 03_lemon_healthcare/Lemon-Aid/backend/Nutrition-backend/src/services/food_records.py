"""Current-user food record services and v1 food tagger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.db.tx import persist_scope
from src.models.db.food_record import FoodRecord
from src.models.schemas.food_record import FoodRecordCreate, FoodRecordResponse, FoodRecordUpdate
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject


@dataclass(frozen=True)
class FoodTagEstimate:
    estimated_tags: list[str]
    rough_nutrient_axes: list[str]


class FoodRecordNotFoundError(ValueError):
    """Raised when a current-user food record row does not exist."""


FOOD_TAG_RULES: tuple[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("라면", "ramen"),
        ("sodium_high", "refined_carb", "soup_or_stew"),
        ("sodium_high", "carbohydrate_high"),
    ),
    (("흰쌀밥", "쌀밥", "white rice"), ("carbohydrate_high",), ("carbohydrate_high",)),
    (("닭가슴살", "chicken breast"), ("protein_food",), ("protein_food",)),
)


_SIMPLE_UPDATE_FIELDS = (
    "recorded_date",
    "meal_type",
    "display_items",
    "amount_text",
    "user_confirmed",
    "source",
    "food_db_match_id",
    "nutrient_estimates",
    "estimated_tags",
    "rough_nutrient_axes",
)


def estimate_food_tags(display_items: list[str]) -> FoodTagEstimate:
    """Estimate coarse v1 food tags from confirmed display names."""
    text = " ".join(display_items).casefold()
    estimated_tags: list[str] = []
    rough_axes: list[str] = []
    for keywords, tags, axes in FOOD_TAG_RULES:
        if any(keyword.casefold() in text for keyword in keywords):
            estimated_tags.extend(tag for tag in tags if tag not in estimated_tags)
            rough_axes.extend(axis for axis in axes if axis not in rough_axes)
    return FoodTagEstimate(estimated_tags=estimated_tags, rough_nutrient_axes=rough_axes)


def build_food_record_snapshot(
    request: FoodRecordCreate | FoodRecordResponse,
    *,
    food_record_id: UUID | None = None,
) -> dict[str, Any]:
    """Return the `FoodRecordSnapshot v1` contract used by the chatbot."""
    estimated_tags = list(request.estimated_tags or [])
    rough_axes = list(request.rough_nutrient_axes or [])
    if not estimated_tags or not rough_axes:
        estimate = estimate_food_tags(list(request.display_items))
        estimated_tags = estimated_tags or estimate.estimated_tags
        rough_axes = rough_axes or estimate.rough_nutrient_axes
    return {
        "food_record_id": str(food_record_id) if food_record_id is not None else None,
        "recorded_date": request.recorded_date.isoformat(),
        "meal_type": request.meal_type,
        "display_items": list(request.display_items),
        "amount_text": request.amount_text,
        "estimated_tags": estimated_tags,
        "rough_nutrient_axes": rough_axes,
        "user_confirmed": request.user_confirmed,
        "source": request.source,
        "food_db_match_id": request.food_db_match_id,
        "match_confidence": request.match_confidence,
        "nutrient_estimates": request.nutrient_estimates,
    }


def food_record_to_response(record: FoodRecord) -> FoodRecordResponse:
    """Convert a saved food record row to the public response."""
    return FoodRecordResponse(
        id=record.id,
        recorded_date=record.recorded_date,
        meal_type=record.meal_type,
        display_items=list(record.display_items or []),
        amount_text=record.amount_text,
        estimated_tags=list(record.estimated_tags or []),
        rough_nutrient_axes=list(record.rough_nutrient_axes or []),
        user_confirmed=record.user_confirmed,
        source=record.source,
        food_db_match_id=record.food_db_match_id,
        match_confidence=(
            None if record.match_confidence is None else float(record.match_confidence)
        ),
        nutrient_estimates=record.nutrient_estimates,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


async def create_food_record_service(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    request: FoodRecordCreate,
) -> FoodRecordResponse:
    estimate = estimate_food_tags(request.display_items)
    record = FoodRecord(
        owner_subject_hash=hash_actor_subject(user, settings),
        recorded_date=request.recorded_date,
        meal_type=request.meal_type,
        display_items=request.display_items,
        amount_text=request.amount_text,
        estimated_tags=request.estimated_tags or estimate.estimated_tags,
        rough_nutrient_axes=request.rough_nutrient_axes or estimate.rough_nutrient_axes,
        user_confirmed=request.user_confirmed,
        source=request.source,
        food_db_match_id=request.food_db_match_id,
        match_confidence=(
            None if request.match_confidence is None else Decimal(str(request.match_confidence))
        ),
        nutrient_estimates=request.nutrient_estimates,
    )
    async with persist_scope(session):
        session.add(record)
        await session.flush()
        await session.refresh(record)
    return food_record_to_response(record)


async def list_food_records_service(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[FoodRecordResponse]:
    statement = (
        select(FoodRecord)
        .where(FoodRecord.owner_subject_hash == hash_actor_subject(user, settings))
        .order_by(FoodRecord.recorded_date.desc(), FoodRecord.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if date_from is not None:
        statement = statement.where(FoodRecord.recorded_date >= date_from)
    if date_to is not None:
        statement = statement.where(FoodRecord.recorded_date <= date_to)
    records = await session.scalars(statement)
    return [food_record_to_response(record) for record in records.all()]


async def load_recent_user_food_record_context(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Load recent saved food records as chatbot-safe FoodRecordSnapshot v1 values."""
    records = await list_food_records_service(
        session,
        user,
        settings,
        limit=limit,
    )
    return [build_food_record_snapshot(record, food_record_id=record.id) for record in records]


async def update_food_record_service(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    food_record_id: UUID,
    request: FoodRecordUpdate,
) -> FoodRecordResponse:
    record = await _get_current_user_food_record(session, user, settings, food_record_id)
    _apply_food_record_update(record, request)

    async with persist_scope(session):
        await session.flush()
        await session.refresh(record)
    return food_record_to_response(record)


async def delete_food_record_service(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    food_record_id: UUID,
) -> None:
    owner_subject_hash = hash_actor_subject(user, settings)
    async with persist_scope(session):
        result = await session.execute(
            delete(FoodRecord).where(
                FoodRecord.id == food_record_id,
                FoodRecord.owner_subject_hash == owner_subject_hash,
            )
        )
        if result.rowcount == 0:
            raise FoodRecordNotFoundError("Food record not found.")


async def _get_current_user_food_record(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    food_record_id: UUID,
) -> FoodRecord:
    record = await session.scalar(
        select(FoodRecord).where(
            FoodRecord.owner_subject_hash == hash_actor_subject(user, settings),
            FoodRecord.id == food_record_id,
        )
    )
    if record is None:
        raise FoodRecordNotFoundError("Food record not found.")
    return record


def _apply_food_record_update(record: FoodRecord, request: FoodRecordUpdate) -> None:
    for field_name in _SIMPLE_UPDATE_FIELDS:
        value = getattr(request, field_name)
        if value is not None:
            setattr(record, field_name, value)
    if request.match_confidence is not None:
        record.match_confidence = Decimal(str(request.match_confidence))
    if request.display_items is not None:
        _apply_estimated_tags(record, request)


def _apply_estimated_tags(record: FoodRecord, request: FoodRecordUpdate) -> None:
    if request.estimated_tags is not None and request.rough_nutrient_axes is not None:
        return
    estimate = estimate_food_tags(request.display_items or [])
    if request.estimated_tags is None:
        record.estimated_tags = estimate.estimated_tags
    if request.rough_nutrient_axes is None:
        record.rough_nutrient_axes = estimate.rough_nutrient_axes
