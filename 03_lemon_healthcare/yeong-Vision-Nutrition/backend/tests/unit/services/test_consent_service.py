"""``ConsentService`` 단위 테스트 — ``AsyncSession`` 은 ``AsyncMock``."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from src.services.consent_service import ConsentService


def _mock_session_with_active_consents(types: list[str]) -> AsyncMock:
    """``session.execute(...).all()`` 가 ``[(type,), ...]`` 를 반환하도록 mock."""
    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = [(t,) for t in types]
    session.execute.return_value = result
    return session


class TestRequire:
    @pytest.mark.asyncio
    async def test_all_required_active_passes(self) -> None:
        session = _mock_session_with_active_consents(["service_terms", "general_profile"])
        service = ConsentService(session)
        await service.require(uuid.uuid4(), {"service_terms", "general_profile"})

    @pytest.mark.asyncio
    async def test_missing_consent_raises_403(self) -> None:
        session = _mock_session_with_active_consents(["service_terms"])
        service = ConsentService(session)
        with pytest.raises(HTTPException) as exc_info:
            await service.require(uuid.uuid4(), {"service_terms", "general_profile"})
        assert exc_info.value.status_code == 403
        detail = exc_info.value.detail
        assert isinstance(detail, dict)
        assert "general_profile" in detail["missing"]


class TestAccept:
    @pytest.mark.asyncio
    async def test_unknown_consent_type_raises_400(self) -> None:
        session = AsyncMock()
        service = ConsentService(session)
        with pytest.raises(HTTPException) as exc_info:
            await service.accept(uuid.uuid4(), "totally_unknown_type")
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_accept_adds_record_to_session(self) -> None:
        session = AsyncMock()
        service = ConsentService(session)
        record = await service.accept(uuid.uuid4(), "service_terms")
        session.add.assert_called_once_with(record)
        assert record.consent_type == "service_terms"
        assert record.revoked_at is None


class TestRevoke:
    @pytest.mark.asyncio
    async def test_no_active_consent_raises_404(self) -> None:
        session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session.execute.return_value = result
        service = ConsentService(session)
        with pytest.raises(HTTPException) as exc_info:
            await service.revoke(uuid.uuid4(), "service_terms")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_revoke_sets_revoked_at_on_all_active(self) -> None:
        session = AsyncMock()
        rec1 = MagicMock(revoked_at=None)
        rec2 = MagicMock(revoked_at=None)
        result = MagicMock()
        result.scalars.return_value.all.return_value = [rec1, rec2]
        session.execute.return_value = result
        service = ConsentService(session)
        count = await service.revoke(uuid.uuid4(), "image_history")
        assert count == 2
        assert rec1.revoked_at is not None
        assert rec2.revoked_at is not None
