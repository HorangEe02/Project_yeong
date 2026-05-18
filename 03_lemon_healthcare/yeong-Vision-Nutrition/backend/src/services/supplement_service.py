"""SupplementService — 영양제 등록 orchestration.

흐름:
    1. 이미지 검증 (content_type / 크기 / 빈 바이트)
    2. 동의 게이트 (``service_terms`` + ``general_profile``;
       만성질환·복약 정보 있으면 추가 동의 강제)
    3. OCR (``OCRSecurityError`` → 400 + audit, 기타 ``OCRError`` → 422)
    4. LLM (``LLMRefusalError`` → 422 + audit, 기타 ``LLMError`` → 422)
    5. MFDS 매칭 (매칭 0건 → 422)
    6. KDRIs 진단
    7. DB 저장 + 감사 로그
    8. Response 조립 + ``response_filter`` 안전 게이트
    9. ``disclaimer`` / ``emergency_resources`` / 전문가 상담 안내 주입

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-05-api-integration.md Step 7
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from typing import Final

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.llm.exceptions import LLMError, LLMRefusalError
from src.llm.ollama import OllamaAdapter
from src.llm.schemas import ParsedSupplement
from src.models.db.supplement import Supplement
from src.models.db.user import User
from src.models.schemas.nutrition import UserKDRIsContext
from src.models.schemas.supplement import (
    IngredientResponse,
    SupplementRegisterResponse,
)
from src.nutrition.diagnosis import diagnose
from src.nutrition.kdris import KDRIsCoverageError
from src.nutrition.mfds_matcher import to_nutrient_intakes
from src.ocr.base import OCRResult
from src.ocr.exceptions import OCRError, OCRSecurityError
from src.ocr.pipeline import OCRPipeline
from src.safety.disclaimer import (
    CONSULT_PROFESSIONAL_MESSAGE_KO,
    EMERGENCY_RESOURCES_KO,
    MAIN_DISCLAIMER_KO,
    SUPPLEMENT_DISCLAIMER_KO,
)
from src.safety.response_filter import ResponseFilterError, assert_response_safe
from src.services.audit_service import AuditService
from src.services.consent_service import ConsentService

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE_BYTES: Final[int] = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES: Final[frozenset[str]] = frozenset({"image/jpeg", "image/png", "image/jpg"})


class SupplementService:
    """``POST /api/v1/supplements/register`` 본체."""

    def __init__(
        self,
        ocr_pipeline: OCRPipeline,
        llm: OllamaAdapter,
        session: AsyncSession,
        consent_service: ConsentService,
        audit_service: AuditService,
    ) -> None:
        self._ocr = ocr_pipeline
        self._llm = llm
        self._session = session
        self._consent = consent_service
        self._audit = audit_service

    async def register(
        self,
        *,
        image_bytes: bytes,
        content_type: str,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SupplementRegisterResponse:
        """영양제 사진 → OCR → LLM → 매칭 → 진단 → DB 저장 → 면책 응답."""
        start = time.perf_counter()

        self._validate_image(image_bytes, content_type)
        await self._enforce_consents(user)

        ocr_result = await self._run_ocr(
            image_bytes,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        parsed = await self._run_llm(
            ocr_result.text,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        intakes, unmatched = to_nutrient_intakes(parsed.ingredients)
        if not intakes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="라벨에서 인식 가능한 성분을 찾지 못했습니다.",
            )

        if user.profile is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="사용자 프로필이 설정되지 않았습니다.",
            )
        ctx = UserKDRIsContext(
            age=user.profile.age,
            sex=user.profile.sex,  # type: ignore[arg-type]
            is_pregnant=user.profile.is_pregnant,
            is_lactating=user.profile.is_lactating,
        )
        try:
            diagnosis_result = diagnose(intakes, ctx)
        except KDRIsCoverageError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="영양 기준 데이터 결손",
            ) from exc

        image_hash = hashlib.sha256(image_bytes).hexdigest()[:12]
        supplement = Supplement(
            id=uuid.uuid4(),
            user_id=user.id,
            product_name=parsed.product_name,
            manufacturer=parsed.manufacturer,
            ingredients=[i.model_dump() for i in intakes],
            ocr_engine=ocr_result.engine,
            llm_engine=parsed.engine,
            image_hash=image_hash,
        )
        self._session.add(supplement)
        await self._audit.log(
            actor_user_id=user.id,
            action="supplement.register.success",
            resource_type="supplement",
            resource_id=str(supplement.id),
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )
        await self._session.commit()
        await self._session.refresh(supplement)

        ingredient_responses = [
            IngredientResponse(
                code=intake.code,
                name_ko=next(
                    (d.name_ko for d in diagnosis_result.diagnoses if d.code == intake.code),
                    intake.code,
                ),
                amount=intake.amount,
                unit=intake.unit,
            )
            for intake in intakes
        ]
        elapsed_ms = (time.perf_counter() - start) * 1000

        try:
            assert_response_safe(
                parsed.product_name or "",
                parsed.manufacturer or "",
                diagnosis_result.summary_message_ko,
                *(d.message_ko for d in diagnosis_result.diagnoses),
                *(d.name_ko for d in diagnosis_result.diagnoses),
                *(i.name_ko for i in ingredient_responses),
            )
        except ResponseFilterError as exc:
            logger.error("Response filter blocked: %s", exc.terms)
            await self._audit.log(
                actor_user_id=user.id,
                action="supplement.register.response_blocked",
                resource_type="supplement",
                resource_id=str(supplement.id),
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_code=",".join(exc.terms[:5]),
            )
            await self._session.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="응답 안전 검증에 실패했습니다.",
            ) from exc

        return SupplementRegisterResponse(
            supplement_id=supplement.id,
            product_name=parsed.product_name,
            manufacturer=parsed.manufacturer,
            ingredients=ingredient_responses,
            unmatched_ingredient_names=unmatched,
            diagnosis=diagnosis_result,
            ocr_engine=ocr_result.engine,
            llm_engine=parsed.engine,
            elapsed_ms=elapsed_ms,
            disclaimers=[MAIN_DISCLAIMER_KO, SUPPLEMENT_DISCLAIMER_KO],
            emergency_resources=EMERGENCY_RESOURCES_KO,
            consult_professional_message_ko=CONSULT_PROFESSIONAL_MESSAGE_KO,
        )

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _validate_image(self, image_bytes: bytes, content_type: str) -> None:
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"지원하지 않는 형식: {content_type}",
            )
        if not image_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="빈 이미지")
        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            mb = len(image_bytes) / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"이미지 크기 초과: {mb:.1f}MB > 5MB",
            )

    async def _enforce_consents(self, user: User) -> None:
        required: set[str] = {"service_terms", "general_profile"}
        if user.profile is not None:
            if user.profile.chronic_diseases:
                required.add("chronic_disease")
            if user.profile.medications:
                required.add("medications")
        await self._consent.require(user.id, required)

    async def _run_ocr(
        self,
        image_bytes: bytes,
        *,
        user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> OCRResult:
        try:
            result = await self._ocr.extract(image_bytes)
        except OCRSecurityError as exc:
            await self._audit.log(
                actor_user_id=user.id,
                action="supplement.register.security_blocked",
                resource_type="supplement",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_code="security",
            )
            await self._session.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미지가 보안 정책을 위반했습니다.",
            ) from exc
        except OCRError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="이미지에서 텍스트를 인식하지 못했습니다.",
            ) from exc

        if not result.text.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="라벨에서 텍스트를 추출할 수 없습니다.",
            )
        return result

    async def _run_llm(
        self,
        ocr_text: str,
        *,
        user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> ParsedSupplement:
        try:
            return await self._llm.parse_supplement(ocr_text)
        except LLMRefusalError as exc:
            await self._audit.log(
                actor_user_id=user.id,
                action="supplement.register.llm_refusal",
                resource_type="supplement",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_code=",".join(exc.terms[:5]) if exc.terms else "refusal",
            )
            await self._session.commit()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="영양제 정보 처리에 실패했습니다. 다른 사진을 시도해 주세요.",
            ) from exc
        except LLMError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="영양제 정보 파싱에 실패했습니다.",
            ) from exc
