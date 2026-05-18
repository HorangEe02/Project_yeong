"""Supplements API — 사진 업로드 + 등록.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-05-api-integration.md Step 8
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile

from src.api.deps import (
    check_register_rate_limit,
    get_current_user,
    get_supplement_service,
)
from src.models.db.user import User
from src.models.schemas.supplement import SupplementRegisterResponse
from src.services.supplement_service import SupplementService

router = APIRouter(tags=["supplements"])


@router.post(
    "/register",
    response_model=SupplementRegisterResponse,
    summary="영양제 사진 등록 + 분석",
    description=(
        "영양제 라벨 사진을 업로드하면 OCR + Ollama LLM 으로 성분을 추출하고, "
        "사용자 KDRIs 와 비교해 부족·과다·위험 진단 + 면책 고지를 반환합니다."
    ),
    dependencies=[Depends(check_register_rate_limit)],
)
async def register_supplement(
    request: Request,
    image: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SupplementService, Depends(get_supplement_service)],
) -> SupplementRegisterResponse:
    """multipart/form-data ``image`` 필드를 받아 등록."""
    image_bytes = await image.read()
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return await service.register(
        image_bytes=image_bytes,
        content_type=image.content_type or "",
        user=current_user,
        ip_address=ip,
        user_agent=ua,
    )
