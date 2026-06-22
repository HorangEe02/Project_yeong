"""Helpers for preserving deterministic slots during LLM polish."""

from __future__ import annotations

import re

_SLOT_DELIMITER_RE = re.compile(r"[;,/·\n]+")
_DISPLAY_SUFFIXES = (
    "부터 확인하세요",
    "부터 확인",
    "확인하세요",
    "확인해 주세요",
    "확인해보세요",
    "확인해 보세요",
    "확인",
)


def build_deterministic_slot_contract(
    *,
    source_basis: str,
    specific_examples: list[str],
    caution_conditions: list[str],
    expert_check_points: list[str],
) -> str:
    """Return the compact slot contract shown to the polish model."""
    return "\n".join(
        (
            f"source_basis={source_basis}",
            "specific_examples=" + "; ".join(specific_examples),
            "caution_conditions=" + "; ".join(caution_conditions),
            "expert_check_points=" + "; ".join(expert_check_points),
        )
    )


def slot_values_are_preserved(
    candidate_values: list[str],
    deterministic_values: list[str],
) -> bool:
    """Return true when LLM-proposed slot values are a subset of deterministic values."""
    deterministic_text = " ".join(_normalize_slot_value(value) for value in deterministic_values)
    return all(
        value in deterministic_text for value in _normalized_candidate_slot_values(candidate_values)
    )


def slot_value_sets_match(
    candidate_values: list[str],
    deterministic_values: list[str],
) -> bool:
    """Return true when LLM-proposed slot values preserve the full deterministic set."""
    candidate_set = set(_normalized_candidate_slot_values(candidate_values))
    deterministic_set = set(_normalized_candidate_slot_values(deterministic_values))
    return bool(candidate_set) and candidate_set == deterministic_set


def _normalized_candidate_slot_values(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        for part in _SLOT_DELIMITER_RE.split(value):
            normalized_value = _normalize_slot_value(part)
            if normalized_value:
                normalized.append(normalized_value)
    return normalized


def _normalize_slot_value(value: str) -> str:
    normalized = " ".join(value.casefold().split())
    for suffix in _DISPLAY_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
            break
    return normalized
