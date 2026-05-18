"""Ollama Local API 기반 LLM Adapter.

환자 개인정보와 민감 건강정보가 외부 LLM 서버로 전송되지 않도록 FastAPI 백엔드에서
로컬 Ollama API만 호출한다.

설계 메모 — ``base.LLMAdapter`` 와의 관계:
    트랙 B의 ``OllamaAdapter`` 는 supplement-domain 메서드(``parse_supplement``)만
    제공한다. ``src/llm/base.py`` 의 ``LLMAdapter`` ABC 는 generic
    ``analyze_text`` / ``analyze_multimodal`` 인터페이스를 정의하지만, 트랙 B에서는
    호출처가 ``OllamaAdapter`` 인스턴스를 직접 받는다. 일반 텍스트 분석이
    필요해지면 별도 어댑터가 ``LLMAdapter`` 를 구현한다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-02-ollama-llm-safety.md Step 5
    docs/12-local-llm-ollama-migration.md
    docs/dev-guides/08-llm-supplement-parsing.md §5
"""

from __future__ import annotations

import logging
from typing import Final

from ollama import AsyncClient, ResponseError
from pydantic import ValidationError

from src.llm.exceptions import LLMApiError, LLMParseError
from src.llm.prompts import SUPPLEMENT_PARSING_SYSTEM, wrap_ocr_text
from src.llm.schemas import ParsedSupplement
from src.safety.forbidden_terms import assert_no_forbidden_terms

logger = logging.getLogger(__name__)

DEFAULT_HOST: Final[str] = "http://127.0.0.1:11434"
DEFAULT_MODEL: Final[str] = "qwen3.5:9b"
DEFAULT_TIMEOUT_SEC: Final[float] = 60.0


class OllamaAdapter:
    """Ollama 로컬 LLM Adapter (supplement-domain).

    Examples:
        >>> adapter = OllamaAdapter(model="qwen3.5:9b")  # doctest: +SKIP
        >>> result = await adapter.parse_supplement(ocr_text)  # doctest: +SKIP
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        client: AsyncClient | None = None,
    ) -> None:
        """Adapter 초기화.

        Args:
            model: 사용할 Ollama 모델 태그 (예: ``qwen3.5:9b``).
            host: Ollama API host. 기본값 로컬 루프백 ``127.0.0.1:11434``.
            timeout_sec: 요청 제한 시간 (초).
            client: 의존성 주입용 클라이언트. ``None`` 이면 새 ``AsyncClient`` 생성.
        """
        self._model = model
        self._host = host
        self._timeout_sec = timeout_sec
        self._client = client or AsyncClient(host=host, timeout=timeout_sec)

    @property
    def engine_name(self) -> str:
        """``"ollama:<model>"`` 형식의 엔진 식별자."""
        return f"ollama:{self._model}"

    async def parse_supplement(self, ocr_text: str) -> ParsedSupplement:
        """OCR 텍스트를 구조화된 영양제 정보로 파싱한다.

        흐름:
            1. system prompt (S1 sandbox 토큰 설명) + user 메시지
               (``wrap_ocr_text`` 로 격리된 OCR 텍스트) 로 ``chat`` 호출.
            2. S2 ①: raw content에 forbidden term 검사.
            3. ``ParsedSupplement.model_validate_json`` 으로 스키마 검증.
            4. S2 ②: 파싱된 필드 값(``product_name``, ``manufacturer``,
               ingredient names, ``warnings``) 평탄화 후 한 번 더 검사.
            5. ``raw_text``, ``engine`` 필드 채워 반환.

        Args:
            ocr_text: OCR이 추출한 영양제 라벨 텍스트.

        Returns:
            검증을 통과한 ``ParsedSupplement``.

        Raises:
            LLMApiError: Ollama 서버 연결 / 모델 호출 실패.
            LLMParseError: JSON 디코드 / 스키마 검증 실패.
            LLMRefusalError: S2 게이트 — forbidden term 발견.
        """
        try:
            response = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": SUPPLEMENT_PARSING_SYSTEM},
                    {"role": "user", "content": wrap_ocr_text(ocr_text)},
                ],
                format=ParsedSupplement.model_json_schema(),
                stream=False,
                options={"temperature": 0},
            )
        except ResponseError as exc:
            raise LLMApiError(self.engine_name, str(exc)) from exc
        except (TimeoutError, ConnectionError) as exc:
            raise LLMApiError(self.engine_name, str(exc)) from exc

        content = response.message.content
        if not content:
            raise LLMParseError(f"{self.engine_name} returned empty content")

        # S2 ① raw content 검사
        assert_no_forbidden_terms(content, context=self.engine_name)

        try:
            parsed = ParsedSupplement.model_validate_json(content)
        except ValidationError as exc:
            raise LLMParseError(f"Schema validation failed: {exc}") from exc
        except ValueError as exc:
            raise LLMParseError(f"Invalid JSON response: {exc}") from exc

        # S2 ② 파싱된 필드 평탄화 후 재검사 (스키마 통과해도 값에 금지 표현 가능)
        flattened_parts: list[str] = [
            parsed.product_name or "",
            parsed.manufacturer or "",
            *(ing.name_ko for ing in parsed.ingredients),
            *((ing.name_en or "") for ing in parsed.ingredients),
            *parsed.warnings,
        ]
        flattened = " ".join(part for part in flattened_parts if part)
        if flattened:
            assert_no_forbidden_terms(
                flattened,
                context=f"{self.engine_name}:fields",
            )

        logger.info(
            "Ollama parsed supplement",
            extra={
                "engine": self.engine_name,
                "ingredient_count": len(parsed.ingredients),
            },
        )

        return parsed.model_copy(update={"raw_text": ocr_text, "engine": self.engine_name})
