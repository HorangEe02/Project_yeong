"""Reminder preference service tests (persist_scope transaction-ownership contract)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from src.api.v1.notifications import (
    ReminderPreferenceNotFoundError,
    create_reminder_preference_service,
    disable_reminder_preference_service,
    update_reminder_preference_service,
)
from src.db.tx import REQUEST_MANAGED_TX
from src.models.db.notification import ReminderPreference
from src.models.schemas.notification import (
    ReminderCategory,
    ReminderPreferenceCreate,
    ReminderPreferenceUpdate,
)
from src.security.auth import AuthenticatedUser

# ambient-tx Step 4: under a request-managed (RLS) session the reminder write
# services must PARTICIPATE (flush only, never commit) so the transaction-local
# owner GUCs survive to the dependency's commit-on-exit; under a legacy session
# they must OWN the transaction (commit exactly once).


def _populate_server_side(obj: ReminderPreference) -> None:
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
        scalar_result: ReminderPreference | None = None,
    ) -> None:
        self.info: dict[str, object] = {REQUEST_MANAGED_TX: True} if request_managed else {}
        self.calls: list[str] = []
        self._scalar_result = scalar_result
        self._added: list[ReminderPreference] = []

    def add(self, obj: ReminderPreference) -> None:
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

    async def refresh(self, obj: ReminderPreference) -> None:
        self.calls.append("refresh")
        _populate_server_side(obj)

    async def scalar(self, _statement: object) -> ReminderPreference | None:
        self.calls.append("scalar")
        return self._scalar_result


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(subject="local-dev-user", issuer="local")


def _create_request() -> ReminderPreferenceCreate:
    return ReminderPreferenceCreate(
        category=ReminderCategory.SUPPLEMENT_REMINDER,
        time_of_day="09:00",
        timezone="Asia/Seoul",
        enabled=True,
        message="영양제 기록 시간을 확인해 주세요.",
    )


def _existing_record() -> ReminderPreference:
    record = ReminderPreference(
        owner_subject="local::local-dev-user",
        category=ReminderCategory.SUPPLEMENT_REMINDER.value,
        time_of_day="09:00",
        timezone="Asia/Seoul",
        enabled=True,
        message="영양제 기록 시간을 확인해 주세요.",
        preference_metadata={},
        disabled_at=None,
    )
    record.id = uuid4()
    record.created_at = datetime.now(UTC)
    record.updated_at = datetime.now(UTC)
    return record


@pytest.mark.asyncio
async def test_create_reminder_participates_without_commit_when_request_managed() -> None:
    session = _FakeWriteSession(request_managed=True)
    response = await create_reminder_preference_service(session, _user(), _create_request())
    assert "commit" not in session.calls  # GUCs must survive to the dependency commit
    assert "flush" in session.calls
    assert response.created_at is not None


@pytest.mark.asyncio
async def test_create_reminder_commits_once_in_legacy_own_mode() -> None:
    session = _FakeWriteSession(request_managed=False)
    await create_reminder_preference_service(session, _user(), _create_request())
    assert session.calls.count("commit") == 1


@pytest.mark.asyncio
async def test_update_reminder_participates_without_commit_when_request_managed() -> None:
    session = _FakeWriteSession(request_managed=True, scalar_result=_existing_record())
    response = await update_reminder_preference_service(
        session, _user(), uuid4(), ReminderPreferenceUpdate(message="저녁 기록 확인")
    )
    assert "commit" not in session.calls
    assert "flush" in session.calls
    assert response.message == "저녁 기록 확인"


@pytest.mark.asyncio
async def test_update_reminder_commits_once_in_legacy_own_mode() -> None:
    session = _FakeWriteSession(request_managed=False, scalar_result=_existing_record())
    await update_reminder_preference_service(
        session, _user(), uuid4(), ReminderPreferenceUpdate(time_of_day="20:30")
    )
    assert session.calls.count("commit") == 1


@pytest.mark.asyncio
async def test_update_missing_reminder_raises_and_never_commits() -> None:
    session = _FakeWriteSession(request_managed=False, scalar_result=None)
    with pytest.raises(ReminderPreferenceNotFoundError):
        await update_reminder_preference_service(
            session, _user(), uuid4(), ReminderPreferenceUpdate(enabled=False)
        )
    assert "commit" not in session.calls


@pytest.mark.asyncio
async def test_disable_reminder_participates_without_commit_when_request_managed() -> None:
    session = _FakeWriteSession(request_managed=True, scalar_result=_existing_record())
    response = await disable_reminder_preference_service(session, _user(), uuid4())
    assert "commit" not in session.calls
    assert "flush" in session.calls
    assert response.enabled is False


@pytest.mark.asyncio
async def test_disable_reminder_commits_once_in_legacy_own_mode() -> None:
    session = _FakeWriteSession(request_managed=False, scalar_result=_existing_record())
    await disable_reminder_preference_service(session, _user(), uuid4())
    assert session.calls.count("commit") == 1
