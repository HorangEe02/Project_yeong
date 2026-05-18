"""``AuditService`` 단위 테스트."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from src.services.audit_service import AuditService, hash_ip


class TestHashIp:
    def test_returns_64_hex_chars(self) -> None:
        result = hash_ip("192.168.0.1", salt="test-salt")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_input_same_output(self) -> None:
        a = hash_ip("10.0.0.1", salt="s")
        b = hash_ip("10.0.0.1", salt="s")
        assert a == b

    def test_different_salt_different_output(self) -> None:
        a = hash_ip("10.0.0.1", salt="s1")
        b = hash_ip("10.0.0.1", salt="s2")
        assert a != b

    def test_different_ip_different_output(self) -> None:
        a = hash_ip("10.0.0.1", salt="s")
        b = hash_ip("10.0.0.2", salt="s")
        assert a != b


class TestAuditServiceLog:
    @pytest.mark.asyncio
    async def test_log_adds_entry_to_session(self) -> None:
        session = AsyncMock()
        service = AuditService(session)
        entry = await service.log(
            actor_user_id=uuid.uuid4(),
            action="supplement.register.success",
            resource_type="supplement",
            resource_id=str(uuid.uuid4()),
            ip_address="192.168.0.1",
            user_agent="curl/8",
        )
        session.add.assert_called_once_with(entry)
        assert entry.success is True
        assert entry.action == "supplement.register.success"

    @pytest.mark.asyncio
    async def test_ip_is_hashed_not_raw(self) -> None:
        session = AsyncMock()
        service = AuditService(session)
        entry = await service.log(
            actor_user_id=None,
            action="anonymous.attempt",
            resource_type="supplement",
            ip_address="203.0.113.7",
        )
        assert entry.ip_address_hash is not None
        assert "203.0.113.7" not in entry.ip_address_hash
        assert len(entry.ip_address_hash) == 64

    @pytest.mark.asyncio
    async def test_user_agent_truncated_to_255(self) -> None:
        session = AsyncMock()
        service = AuditService(session)
        long_ua = "a" * 500
        entry = await service.log(
            actor_user_id=None,
            action="x",
            resource_type="r",
            user_agent=long_ua,
        )
        assert entry.user_agent is not None
        assert len(entry.user_agent) == 255

    @pytest.mark.asyncio
    async def test_no_ip_no_hash(self) -> None:
        session = AsyncMock()
        service = AuditService(session)
        entry = await service.log(
            actor_user_id=None,
            action="x",
            resource_type="r",
            ip_address=None,
        )
        assert entry.ip_address_hash is None
