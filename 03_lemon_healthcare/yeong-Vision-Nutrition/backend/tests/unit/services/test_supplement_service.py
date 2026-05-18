"""``SupplementService`` 단위 테스트 — 핵심 분기 (image validation + consent gate).

전체 happy path 는 integration 에서 검증한다. 본 파일은 mock 비용이 작은 분기만.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from src.services.supplement_service import (
    ALLOWED_CONTENT_TYPES,
    MAX_IMAGE_SIZE_BYTES,
    SupplementService,
)


def _make_service() -> SupplementService:
    return SupplementService(
        ocr_pipeline=AsyncMock(),
        llm=AsyncMock(),
        session=AsyncMock(),
        consent_service=AsyncMock(),
        audit_service=AsyncMock(),
    )


def _make_user_with_profile(*, diseases: list[str] | None = None) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.profile = MagicMock()
    user.profile.age = 30
    user.profile.sex = "male"
    user.profile.is_pregnant = False
    user.profile.is_lactating = False
    user.profile.chronic_diseases = diseases or []
    user.profile.medications = []
    return user


class TestValidateImage:
    def test_disallowed_content_type_raises_400(self) -> None:
        service = _make_service()
        with pytest.raises(HTTPException) as exc_info:
            service._validate_image(b"x" * 100, "text/plain")
        assert exc_info.value.status_code == 400

    def test_empty_bytes_raises_400(self) -> None:
        service = _make_service()
        with pytest.raises(HTTPException) as exc_info:
            service._validate_image(b"", "image/jpeg")
        assert exc_info.value.status_code == 400

    def test_oversized_raises_400(self) -> None:
        service = _make_service()
        big = b"x" * (MAX_IMAGE_SIZE_BYTES + 1)
        with pytest.raises(HTTPException) as exc_info:
            service._validate_image(big, "image/jpeg")
        assert exc_info.value.status_code == 400

    def test_allowed_content_type_passes(self) -> None:
        service = _make_service()
        for ct in ALLOWED_CONTENT_TYPES:
            service._validate_image(b"x" * 100, ct)


class TestEnforceConsents:
    @pytest.mark.asyncio
    async def test_no_disease_no_meds_requires_baseline(self) -> None:
        service = _make_service()
        user = _make_user_with_profile(diseases=[])
        user.profile.medications = []
        await service._enforce_consents(user)
        call = service._consent.require.await_args
        required = call.args[1] if len(call.args) > 1 else call.kwargs.get("required")
        assert required == {"service_terms", "general_profile"}

    @pytest.mark.asyncio
    async def test_with_chronic_disease_requires_chronic_consent(self) -> None:
        service = _make_service()
        user = _make_user_with_profile(diseases=["diabetes"])
        await service._enforce_consents(user)
        call = service._consent.require.await_args
        required = call.args[1] if len(call.args) > 1 else call.kwargs.get("required")
        assert "chronic_disease" in required

    @pytest.mark.asyncio
    async def test_with_medications_requires_medication_consent(self) -> None:
        service = _make_service()
        user = _make_user_with_profile()
        user.profile.medications = [{"name": "metformin"}]
        await service._enforce_consents(user)
        call = service._consent.require.await_args
        required = call.args[1] if len(call.args) > 1 else call.kwargs.get("required")
        assert "medications" in required
