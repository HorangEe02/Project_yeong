"""Current-user medication service tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from src.config import get_settings
from src.db.tx import REQUEST_MANAGED_TX
from src.models.db.user_medication import UserMedication
from src.models.schemas.user_medication import UserMedicationCreate, UserMedicationUpdate
from src.security.auth import AuthenticatedUser
from src.services.user_medications import (
    UserMedicationNotFoundError,
    create_user_medication_service,
    deactivate_user_medication_service,
    update_user_medication_service,
    user_medication_to_response,
)

# --- persist_scope transaction-ownership contract (ambient-tx Step 4) ----------
#
# Under the request-managed (RLS) session the write services must PARTICIPATE
# (flush only, never commit) so the transaction-local owner GUCs survive to the
# dependency's commit-on-exit; under a legacy session they must OWN the
# transaction (commit exactly once), reproducing today's add+commit behavior.


def _populate_server_side(obj: UserMedication) -> None:
    """Simulate the server-default id/timestamp load a real flush/refresh does."""
    now = datetime.now(UTC)
    if getattr(obj, "id", None) is None:
        obj.id = uuid4()
    if getattr(obj, "created_at", None) is None:
        obj.created_at = now
    obj.updated_at = now


class _FakeWriteSession:
    """Records flush/commit/rollback and carries an ``.info`` dict like a real session."""

    def __init__(
        self,
        *,
        request_managed: bool = False,
        scalar_result: UserMedication | None = None,
    ) -> None:
        self.info: dict[str, object] = {REQUEST_MANAGED_TX: True} if request_managed else {}
        self.calls: list[str] = []
        self._scalar_result = scalar_result
        self._added: list[UserMedication] = []

    def add(self, obj: UserMedication) -> None:
        self.calls.append("add")
        self._added.append(obj)

    async def flush(self) -> None:
        self.calls.append("flush")
        for obj in self._added:
            _populate_server_side(obj)

    async def commit(self) -> None:
        self.calls.append("commit")

    async def rollback(self) -> None:
        self.calls.append("rollback")

    async def refresh(self, obj: UserMedication) -> None:
        self.calls.append("refresh")
        _populate_server_side(obj)

    async def scalar(self, _statement: object) -> UserMedication | None:
        self.calls.append("scalar")
        return self._scalar_result

    async def execute(self, _statement: object) -> SimpleNamespace:
        self.calls.append("execute")
        return SimpleNamespace(rowcount=1)


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(subject="local-dev-user", issuer="local")


def _create_request() -> UserMedicationCreate:
    return UserMedicationCreate(
        display_name="amlodipine",
        medication_class="calcium_channel_blocker",
        condition_tags=["hypertension"],
    )


def _existing_record() -> UserMedication:
    record = UserMedication(
        owner_subject_hash="owner-hash",
        display_name="amlodipine",
        normalized_name="amlodipine",
        medication_class="calcium_channel_blocker",
        condition_tags=["hypertension"],
        confirmation_status="user_confirmed",
        is_active=True,
        last_confirmed_at=datetime.now(UTC),
    )
    record.id = uuid4()
    record.created_at = datetime.now(UTC)
    record.updated_at = datetime.now(UTC)
    return record


def test_user_medication_to_response_hides_owner_hash() -> None:
    response = user_medication_to_response(_existing_record())
    serialized = response.model_dump(mode="json")
    assert "owner_subject_hash" not in serialized
    assert response.display_name == "amlodipine"


@pytest.mark.asyncio
async def test_create_user_medication_participates_without_commit_when_request_managed() -> None:
    session = _FakeWriteSession(request_managed=True)
    response = await create_user_medication_service(
        session, _user(), get_settings(), _create_request()
    )
    assert "commit" not in session.calls  # GUCs must survive to the dependency commit
    assert "flush" in session.calls
    assert response.display_name == "amlodipine"
    assert response.created_at is not None


@pytest.mark.asyncio
async def test_create_user_medication_commits_once_in_legacy_own_mode() -> None:
    session = _FakeWriteSession(request_managed=False)
    await create_user_medication_service(session, _user(), get_settings(), _create_request())
    assert session.calls.count("commit") == 1


@pytest.mark.asyncio
async def test_update_user_medication_participates_without_commit_when_request_managed() -> None:
    session = _FakeWriteSession(request_managed=True, scalar_result=_existing_record())
    response = await update_user_medication_service(
        session,
        _user(),
        get_settings(),
        uuid4(),
        UserMedicationUpdate(display_name="losartan", medication_class="arb"),
    )
    assert "commit" not in session.calls
    assert "flush" in session.calls
    assert response.display_name == "losartan"


@pytest.mark.asyncio
async def test_update_user_medication_commits_once_in_legacy_own_mode() -> None:
    session = _FakeWriteSession(request_managed=False, scalar_result=_existing_record())
    await update_user_medication_service(
        session, _user(), get_settings(), uuid4(), UserMedicationUpdate(is_active=False)
    )
    assert session.calls.count("commit") == 1


@pytest.mark.asyncio
async def test_update_missing_user_medication_raises_and_never_commits() -> None:
    session = _FakeWriteSession(request_managed=False, scalar_result=None)
    with pytest.raises(UserMedicationNotFoundError):
        await update_user_medication_service(
            session, _user(), get_settings(), uuid4(), UserMedicationUpdate(is_active=False)
        )
    assert "commit" not in session.calls


@pytest.mark.asyncio
async def test_deactivate_user_medication_participates_without_commit_when_request_managed() -> (
    None
):
    session = _FakeWriteSession(request_managed=True, scalar_result=_existing_record())
    response = await deactivate_user_medication_service(session, _user(), get_settings(), uuid4())
    assert "commit" not in session.calls
    assert "flush" in session.calls
    assert response.is_active is False


@pytest.mark.asyncio
async def test_deactivate_user_medication_commits_once_in_legacy_own_mode() -> None:
    session = _FakeWriteSession(request_managed=False, scalar_result=_existing_record())
    await deactivate_user_medication_service(session, _user(), get_settings(), uuid4())
    assert session.calls.count("commit") == 1
