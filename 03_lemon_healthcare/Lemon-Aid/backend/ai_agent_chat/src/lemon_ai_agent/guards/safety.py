from __future__ import annotations

import re
from dataclasses import dataclass

FORBIDDEN_TERMS = (
    "diagnose",
    "diagnosis",
    "diabetes",
    "cure",
    "treats",
    "prescribe",
    "take this medicine",
    "진단",
    "치료",
    "처방",
    "복용해도 됩니다",
    "먹어도 됩니다",
    "함께 먹어도 됩니다",
    "같이 먹어도 됩니다",
    "복용량을 바꾸",
    "약을 중단",
    "약을 끊",
    "약을 줄이",
    "혈압약을 줄이",
    "용량을 늘리",
    "용량을 줄이",
    "당뇨입니다",
    "고혈압입니다",
    "신장질환입니다",
    "완전히 금지",
    "절대 먹지",
    "절대 금지",
    "먹으면 안 된다",
    "먹으면 안 돼",
    "먹는 것은 안 돼",
    "먹으면 안 됩니다",
    "안 돼요",
    "먹지 않아야",
    "먹지 말아야",
    "먹지 마세요",
    "take more of this medicine",
    "stop taking your medicine",
)

PRODUCT_PROMOTION_TERMS = (
    "buy ",
    "purchase ",
    "brand",
    "제품을 구매",
    "브랜드",
)

UNSUPPORTED_EVIDENCE_TERMS = (
    "연구에 따르면",
    "임상시험",
    "논문",
    "입증",
    "근거가 확실",
    "혈압을 낮춥니다",
    "혈당을 낮춥니다",
    "콜레스테롤을 낮춥니다",
    "reduces blood pressure",
    "clinically proven",
    "study shows",
)

NUMERIC_MEDICAL_CLAIM_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?(?:\s*(?:-|~|\u2013|\u2014|to|에서|부터)\s*\d+(?:\.\d+)?)?"
    r"\s*(?:mg/dl|mg|mcg|µg|ug|iu|g|kcal|mmhg|%)(?=\b|[^A-Za-z0-9_]|$)",
    re.IGNORECASE,
)


def _compact_numeric_text(text: str) -> str:
    """Normalize cosmetic spacing so supplied numeric facts can be repeated."""
    return re.sub(r"\s+", "", text.casefold().replace("µ", "u"))


@dataclass(frozen=True)
class SafetyCheckResult:
    allowed: bool
    warnings: list[str]


@dataclass(frozen=True)
class SafetyEnvelopeResult:
    allowed: bool
    text: str
    warnings: tuple[str, ...]


class SafetyGuard:
    """Policy guard for health-management coaching text."""

    def check_text(self, text: str) -> SafetyCheckResult:
        lowered = text.lower()
        warnings: list[str] = []

        for term in FORBIDDEN_TERMS:
            if term.lower() in lowered:
                warnings.append("Forbidden medical expression detected")

        for term in PRODUCT_PROMOTION_TERMS:
            if term.lower() in lowered:
                warnings.append("Product-promotion expression detected")

        return SafetyCheckResult(allowed=not warnings, warnings=warnings)

    def check_grounding(self, text: str, allowed_context: str) -> SafetyCheckResult:
        """Block unsupported evidence or effect claims absent from grounding context."""
        lowered_text = text.lower()
        lowered_context = allowed_context.lower()
        warnings: list[str] = []

        for term in UNSUPPORTED_EVIDENCE_TERMS:
            lowered_term = term.lower()
            if lowered_term in lowered_text and lowered_term not in lowered_context:
                warnings.append("Unsupported medical fact detected")

        compact_context = _compact_numeric_text(lowered_context)
        for claim in NUMERIC_MEDICAL_CLAIM_PATTERN.findall(text):
            if _compact_numeric_text(claim) not in compact_context:
                warnings.append("Unsupported numeric medical claim detected")
                break

        return SafetyCheckResult(allowed=not warnings, warnings=warnings)

    def check_forbidden_phrases(
        self,
        text: str,
        forbidden_phrases: tuple[str, ...],
    ) -> SafetyCheckResult:
        """Block answer-card-specific phrases that must never be user-facing."""
        lowered = text.lower()
        warnings: list[str] = []
        for phrase in forbidden_phrases:
            if phrase and phrase.lower() in lowered:
                warnings.append("Answer card forbidden phrase detected")
                break
        return SafetyCheckResult(allowed=not warnings, warnings=warnings)

    def sanitize_or_raise(self, text: str) -> str:
        result = self.check_text(text)
        if not result.allowed:
            raise ValueError("; ".join(result.warnings))
        return text

    def sanitize_trace(self, trace: list[str]) -> tuple[list[str], list[str]]:
        safe_trace: list[str] = []
        warnings: list[str] = []

        for item in trace:
            result = self.check_text(item)
            if result.allowed:
                safe_trace.append(item)
                continue

            safe_trace.append("trace item withheld by policy guard")
            warnings.extend(f"Trace text blocked: {warning}" for warning in result.warnings)

        return safe_trace, warnings


class SafetyEnvelope:
    """Applies user-facing safety checks in caller-safe combinations."""

    def __init__(self, guard: SafetyGuard | None = None) -> None:
        self._guard = guard or SafetyGuard()

    def screen_llm_output(
        self,
        text: str,
        grounding_context: str,
    ) -> SafetyEnvelopeResult:
        warnings: list[str] = []

        text_check = self._guard.check_text(text)
        warnings.extend(text_check.warnings)

        grounding_check = self._guard.check_grounding(text, grounding_context)
        warnings.extend(grounding_check.warnings)

        allowed = text_check.allowed and grounding_check.allowed
        return SafetyEnvelopeResult(
            allowed=allowed,
            text=text if allowed else "",
            warnings=tuple(warnings),
        )

    def screen_text(
        self,
        text: str,
        *,
        replacement: str = "text withheld by policy guard",
    ) -> SafetyEnvelopeResult:
        check = self._guard.check_text(text)
        return SafetyEnvelopeResult(
            allowed=check.allowed,
            text=text if check.allowed else replacement,
            warnings=tuple(check.warnings),
        )

    def screen_trace(self, trace: list[str]) -> tuple[list[str], tuple[str, ...]]:
        safe_trace, warnings = self._guard.sanitize_trace(trace)
        return safe_trace, tuple(warnings)
