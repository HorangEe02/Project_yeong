"""Current-user medication profile services."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.db.tx import persist_scope
from src.models.db.user_medication import UserMedication
from src.models.schemas.user_medication import (
    UserMedicationCreate,
    UserMedicationResponse,
    UserMedicationUpdate,
)
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject


class UserMedicationNotFoundError(ValueError):
    """Raised when a current-user medication row does not exist."""


def user_medication_to_response(record: UserMedication) -> UserMedicationResponse:
    """Convert a saved medication row to the public response."""
    return UserMedicationResponse(
        id=record.id,
        display_name=record.display_name,
        normalized_name=record.normalized_name,
        medication_class=record.medication_class,
        condition_tags=list(record.condition_tags or []),
        confirmation_status=record.confirmation_status,
        is_active=record.is_active,
        last_confirmed_at=record.last_confirmed_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


async def create_user_medication_service(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    request: UserMedicationCreate,
) -> UserMedicationResponse:
    """Persist a user-confirmed medication name."""
    now = datetime.now(UTC)
    record = UserMedication(
        owner_subject_hash=hash_actor_subject(user, settings),
        display_name=request.display_name,
        normalized_name=request.normalized_name or request.display_name.casefold(),
        medication_class=request.medication_class,
        condition_tags=request.condition_tags,
        confirmation_status="user_confirmed",
        is_active=request.is_active,
        last_confirmed_at=now,
    )
    async with persist_scope(session):
        session.add(record)
        await session.flush()
        await session.refresh(record)
    return user_medication_to_response(record)


async def list_user_medications_service(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
) -> list[UserMedicationResponse]:
    """List current-user medication rows."""
    owner_subject_hash = hash_actor_subject(user, settings)
    result = await session.scalars(
        select(UserMedication)
        .where(UserMedication.owner_subject_hash == owner_subject_hash)
        .order_by(UserMedication.is_active.desc(), UserMedication.updated_at.desc())
    )
    return [user_medication_to_response(record) for record in result.all()]


async def update_user_medication_service(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    medication_id: UUID,
    request: UserMedicationUpdate,
) -> UserMedicationResponse:
    """Update a current-user medication row."""
    record = await _get_current_user_medication(session, user, settings, medication_id)
    now = datetime.now(UTC)
    if request.display_name is not None:
        record.display_name = request.display_name
        if request.normalized_name is None:
            record.normalized_name = request.display_name.casefold()
    if request.normalized_name is not None:
        record.normalized_name = request.normalized_name
    if request.medication_class is not None:
        record.medication_class = request.medication_class
    if request.condition_tags is not None:
        record.condition_tags = request.condition_tags
    if request.is_active is not None:
        record.is_active = request.is_active
    record.confirmation_status = "user_confirmed"
    record.last_confirmed_at = now
    async with persist_scope(session):
        await session.flush()
        await session.refresh(record)
    return user_medication_to_response(record)


async def deactivate_user_medication_service(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    medication_id: UUID,
) -> UserMedicationResponse:
    """Deactivate a current-user medication row."""
    record = await _get_current_user_medication(session, user, settings, medication_id)
    record.is_active = False
    async with persist_scope(session):
        await session.flush()
        await session.refresh(record)
    return user_medication_to_response(record)


async def load_active_user_medication_context(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
) -> dict[str, object]:
    """Return sanitized active medication context for chatbot grounding."""
    owner_subject_hash = hash_actor_subject(user, settings)
    result = await session.scalars(
        select(UserMedication)
        .where(
            UserMedication.owner_subject_hash == owner_subject_hash,
            UserMedication.is_active.is_(True),
        )
        .order_by(UserMedication.updated_at.desc())
    )
    details: list[dict[str, object]] = []
    names: list[str] = []
    for record in result.all():
        if record.display_name not in names:
            names.append(record.display_name)
        details.append(
            {
                "display_name": record.display_name,
                "normalized_name": record.normalized_name,
                "medication_class": record.medication_class,
                "condition_tags": list(record.condition_tags or []),
                "confirmation_status": record.confirmation_status,
            }
        )
    return {"medications": names, "medication_details": details}


async def _get_current_user_medication(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    medication_id: UUID,
) -> UserMedication:
    """Load one current-user medication row or raise."""
    record = await session.scalar(
        select(UserMedication).where(
            UserMedication.owner_subject_hash == hash_actor_subject(user, settings),
            UserMedication.id == medication_id,
        )
    )
    if record is None:
        raise UserMedicationNotFoundError("User medication not found.")
    return record
