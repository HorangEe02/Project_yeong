from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, TypedDict


class LLMMode(StrEnum):
    CHAT = "chat"
    CHAT_KOREAN = "chat_korean"
    VISION = "vision"
    DRAFT = "draft"
    SUMMARY = "summary"
    INTENT = "intent"
    EMBEDDING = "embedding"
    JSON = "json"


# 폴백 체인이 모드 → 프로바이더 → 모델로 풀어야 하므로
# Literal 대신 StrEnum 의 .value 비교로 사용한다.


class StreamEvent(TypedDict):
    type: Literal["token", "metadata", "error", "done"]
    content: str | None
    metadata: dict[str, Any] | None


class StreamRequest(TypedDict, total=False):
    prompt: str
    mode: LLMMode
    image_bytes: bytes | None
    history: list[dict[str, Any]]
    max_tokens: int
    temperature: float
    response_format: Literal["text", "json"]


class RouterError(Exception):
    """LLM 라우팅 단계에서 발생하는 모든 예외의 베이스."""


class ProviderUnavailable(RouterError):
    """프로바이더가 미등록 또는 health_check 실패."""


class ProviderResponseError(RouterError):
    """프로바이더 호출 중 비정상 응답 (HTTP 5xx, 타임아웃, 인증 실패 등)."""


class UnsupportedModeError(RouterError):
    """현재 프로바이더 + 모델 조합이 모드를 지원하지 않음."""
