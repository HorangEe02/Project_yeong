from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class ChatTurn:
    role: Literal["user", "assistant"]
    content: str
    created_at: str


@dataclass(frozen=True)
class ChatbotRequest:
    request_id: str
    user_id: str
    message: str
    conversation: list[ChatTurn] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatbotResponse:
    request_id: str
    message: str
    provider: str
    used_tools: list[str] = field(default_factory=list)
    safety_warnings: list[str] = field(default_factory=list)
    source_families: list[str] = field(default_factory=list)
    answerability: str = "answerable"
    sources: list[dict[str, str]] = field(default_factory=list)
    requires_user_approval: bool = False
    ctas: list[str] = field(default_factory=list)
    analysis_snapshot: dict[str, Any] = field(default_factory=dict)
    today_analysis: dict[str, Any] = field(default_factory=dict)
    smart_analysis: dict[str, Any] = field(default_factory=dict)
    checklist_candidates: list[dict[str, Any]] = field(default_factory=list)
    approval_preview: dict[str, Any] = field(default_factory=dict)
