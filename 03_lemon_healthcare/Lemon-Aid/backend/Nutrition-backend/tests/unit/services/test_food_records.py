"""Food record service and tagger tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from src.config import get_settings
from src.db.tx import REQUEST_MANAGED_TX
from src.models.db.food_record import FoodRecord
from src.models.schemas.food_record import FoodRecordCreate, FoodRecordUpdate
from src.security.auth import AuthenticatedUser
from src.services.food_records import (
    FoodRecordNotFoundError,
    build_food_record_snapshot,
    create_food_record_service,
    delete_food_record_service,
    estimate_food_tags,
    update_food_record_service,
)


def test_estimate_food_tags_uses_korean_food_name_rules() -> None:
    ramen = estimate_food_tags(["라면"])
    rice = estimate_food_tags(["흰쌀밥"])
    chicken = estimate_food_tags(["닭가슴살"])

    assert ramen.estimated_tags == ["sodium_high", "refined_carb", "soup_or_stew"]
    assert ramen.rough_nutrient_axes == ["sodium_high", "carbohydrate_high"]
    assert rice.estimated_tags == ["carbohydrate_high"]
    assert rice.rough_nutrient_axes == ["carbohydrate_high"]
    assert chicken.estimated_tags == ["protein_food"]
    assert chicken.rough_nutrient_axes == ["protein_food"]


def test_food_record_snapshot_v1_keeps_future_food_db_fields_nullable() -> None:
    request = FoodRecordCreate(
        recorded_date="2026-05-31",
        meal_type="lunch",
        display_items=["라면"],
        amount_text="1그릇",
        source="manual",
    )

    snapshot = build_food_record_snapshot(request)

    assert snapshot["food_record_id"] is None
    assert snapshot["recorded_date"] == "2026-05-31"
    assert snapshot["meal_type"] == "lunch"
    assert snapshot["display_items"] == ["라면"]
    assert snapshot["estimated_tags"] == ["sodium_high", "refined_carb", "soup_or_stew"]
    assert snapshot["rough_nutrient_axes"] == ["sodium_high", "carbohydrate_high"]
    assert snapshot["food_db_match_id"] is None
    assert snapshot["match_confidence"] is None
    assert snapshot["nutrient_estimates"] is None


# --- persist_scope transaction-ownership contract (ambient-tx Step 3) ----------
#
# Under the request-managed (RLS) session the write services must PARTICIPATE
# (flush only, never commit) so the transaction-local owner GUCs survive to the
# dependency's commit-on-exit; under a legacy session they must OWN the
# transaction (commit exactly once), reproducing today's add+commit behavior.


def _populate_server_side(obj: FoodRecord) -> None:
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
        scalar_result: FoodRecord | None = None,
        delete_rowcount: int = 1,
    ) -> None:
        self.info: dict[str, object] = {REQUEST_MANAGED_TX: True} if request_managed else {}
        self.calls: list[str] = []
        self._scalar_result = scalar_result
        self._delete_rowcount = delete_rowcount
        self._added: list[FoodRecord] = []

    def add(self, obj: FoodRecord) -> None:
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

    async def refresh(self, obj: FoodRecord) -> None:
        self.calls.append("refresh")
        _populate_server_side(obj)

    async def scalar(self, _statement: object) -> FoodRecord | None:
        self.calls.append("scalar")
        return self._scalar_result

    async def execute(self, _statement: object) -> SimpleNamespace:
        self.calls.append("execute")
        return SimpleNamespace(rowcount=self._delete_rowcount)


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(subject="local-dev-user", issuer="local")


def _create_request() -> FoodRecordCreate:
    return FoodRecordCreate(
        recorded_date=date(2026, 5, 31),
        meal_type="lunch",
        display_items=["라면"],
        amount_text="1그릇",
        source="manual",
    )


def _existing_record() -> FoodRecord:
    record = FoodRecord(
        owner_subject_hash="owner-hash",
        recorded_date=date(2026, 5, 31),
        meal_type="lunch",
        display_items=["라면"],
        amount_text="1그릇",
        estimated_tags=["sodium_high"],
        rough_nutrient_axes=["sodium_high"],
        user_confirmed=True,
        source="manual",
    )
    record.id = uuid4()
    record.created_at = datetime.now(UTC)
    record.updated_at = datetime.now(UTC)
    return record


@pytest.mark.asyncio
async def test_create_food_record_participates_without_commit_when_request_managed() -> None:
    session = _FakeWriteSession(request_managed=True)
    response = await create_food_record_service(session, _user(), get_settings(), _create_request())
    assert "commit" not in session.calls  # GUCs must survive to the dependency commit
    assert "flush" in session.calls
    assert response.estimated_tags == ["sodium_high", "refined_carb", "soup_or_stew"]
    assert response.created_at is not None


@pytest.mark.asyncio
async def test_create_food_record_commits_once_in_legacy_own_mode() -> None:
    session = _FakeWriteSession(request_managed=False)
    await create_food_record_service(session, _user(), get_settings(), _create_request())
    assert session.calls.count("commit") == 1


@pytest.mark.asyncio
async def test_update_food_record_participates_without_commit_when_request_managed() -> None:
    session = _FakeWriteSession(request_managed=True, scalar_result=_existing_record())
    response = await update_food_record_service(
        session,
        _user(),
        get_settings(),
        uuid4(),
        FoodRecordUpdate(display_items=["닭가슴살"], estimated_tags=["protein_food"]),
    )
    assert "commit" not in session.calls
    assert "flush" in session.calls
    assert response.display_items == ["닭가슴살"]


@pytest.mark.asyncio
async def test_update_food_record_commits_once_in_legacy_own_mode() -> None:
    session = _FakeWriteSession(request_managed=False, scalar_result=_existing_record())
    await update_food_record_service(
        session, _user(), get_settings(), uuid4(), FoodRecordUpdate(amount_text="2그릇")
    )
    assert session.calls.count("commit") == 1


@pytest.mark.asyncio
async def test_delete_food_record_participates_without_commit_when_request_managed() -> None:
    session = _FakeWriteSession(request_managed=True, delete_rowcount=1)
    await delete_food_record_service(session, _user(), get_settings(), uuid4())
    assert "commit" not in session.calls


@pytest.mark.asyncio
async def test_delete_food_record_commits_once_in_legacy_own_mode() -> None:
    session = _FakeWriteSession(request_managed=False, delete_rowcount=1)
    await delete_food_record_service(session, _user(), get_settings(), uuid4())
    assert session.calls.count("commit") == 1


@pytest.mark.asyncio
async def test_delete_missing_food_record_raises_and_never_commits() -> None:
    session = _FakeWriteSession(request_managed=False, delete_rowcount=0)
    with pytest.raises(FoodRecordNotFoundError):
        await delete_food_record_service(session, _user(), get_settings(), uuid4())
    assert "commit" not in session.calls


@pytest.mark.asyncio
async def test_delete_missing_food_record_request_managed_leaves_rollback_to_dependency() -> None:
    session = _FakeWriteSession(request_managed=True, delete_rowcount=0)
    with pytest.raises(FoodRecordNotFoundError):
        await delete_food_record_service(session, _user(), get_settings(), uuid4())
    assert "commit" not in session.calls
    assert "rollback" not in session.calls
