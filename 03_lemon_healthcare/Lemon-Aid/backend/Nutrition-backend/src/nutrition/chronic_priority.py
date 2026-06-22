"""Source-backed chronic-condition nutrient priority lookup."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.nutrition.kdris import NUTRITION_REFERENCE_ROOT

DEFAULT_CHRONIC_PRIORITY_TABLE = (
    NUTRITION_REFERENCE_ROOT / "nutrient" / "chronic_nutrient_priorities.json"
)
DEFAULT_PRIORITY_MESSAGE = "현재 입력과 만성질환 정보를 함께 볼 때 우선 확인 대상입니다."


class ChronicPrioritySource(BaseModel):
    """Evidence source metadata for a chronic-condition priority rule.

    Attributes:
        title: Human-readable source title.
        url: Official source URL.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    url: str


class ChronicPriorityRule(BaseModel):
    """Priority boost rule for one nutrient under one condition.

    Attributes:
        nutrient_code: Internal nutrient code.
        boost: Relative sorting boost applied only after DEFICIENT/LOW classification.
        message_key: Safe user-message template key.
        source_ids: Evidence source IDs backing the rule.
    """

    model_config = ConfigDict(extra="forbid")

    nutrient_code: str = Field(min_length=1, max_length=64)
    boost: int = Field(gt=0, le=100)
    message_key: str = Field(default="priority_review", min_length=1, max_length=64)
    source_ids: list[str] = Field(default_factory=list)


class ChronicCautionRule(BaseModel):
    """Caution-only nutrient record that must not create a priority boost.

    Attributes:
        nutrient_code: Internal nutrient code.
        source_ids: Evidence source IDs backing the caution.
        note: Internal reviewer note explaining why the nutrient is not boosted.
    """

    model_config = ConfigDict(extra="forbid")

    nutrient_code: str = Field(min_length=1, max_length=64)
    source_ids: list[str] = Field(default_factory=list)
    note: str


class ChronicConditionPriority(BaseModel):
    """Priority and caution rules for one canonical chronic-condition code.

    Attributes:
        aliases: Alternate condition codes accepted from user profiles.
        priority_nutrients: Nutrients that may receive sorting boost when already low.
        caution_nutrients: Nutrients explicitly not boosted because care plans vary.
    """

    model_config = ConfigDict(extra="forbid")

    aliases: list[str] = Field(default_factory=list)
    priority_nutrients: list[ChronicPriorityRule] = Field(default_factory=list)
    caution_nutrients: list[ChronicCautionRule] = Field(default_factory=list)


class ChronicPriorityTable(BaseModel):
    """Source-backed chronic-condition priority table.

    Attributes:
        schema_version: Data schema version.
        review_status: Review status label.
        message_templates: Safe message templates keyed by rule message_key.
        conditions: Canonical condition-code priority records.
        sources: Source metadata keyed by source ID.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    review_status: str
    message_templates: dict[str, str] = Field(default_factory=dict)
    conditions: dict[str, ChronicConditionPriority]
    sources: dict[str, ChronicPrioritySource]

    @model_validator(mode="after")
    def validate_source_references(self) -> Self:
        """Validate rule source IDs and message template references.

        Returns:
            Validated table.

        Raises:
            ValueError: If any rule references an unknown source or message template.
        """
        source_ids = set(self.sources)
        message_keys = set(self.message_templates)
        for condition in self.conditions.values():
            for rule in condition.priority_nutrients:
                missing_sources = set(rule.source_ids) - source_ids
                if missing_sources:
                    raise ValueError(
                        f"Unknown chronic priority source IDs: {sorted(missing_sources)}"
                    )
                if rule.message_key not in message_keys:
                    raise ValueError(f"Unknown chronic priority message key: {rule.message_key}")
            for caution_rule in condition.caution_nutrients:
                missing_sources = set(caution_rule.source_ids) - source_ids
                if missing_sources:
                    raise ValueError(
                        f"Unknown chronic caution source IDs: {sorted(missing_sources)}"
                    )
        return self


@dataclass(frozen=True)
class ChronicPriorityMatch:
    """Matched chronic-condition boost context for one nutrient.

    Attributes:
        boost_score: Total source-backed priority boost.
        condition_codes: Canonical condition codes that matched.
        source_ids: Source IDs backing the match.
        message: Safe user-visible message.
    """

    boost_score: int
    condition_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    message: str


def normalize_condition_code(condition_code: str) -> str:
    """Normalize user-provided chronic condition code text.

    Args:
        condition_code: Raw user profile condition code.

    Returns:
        Lowercase snake-case condition code.
    """
    return "_".join(
        token for token in re.split(r"[^a-z0-9]+", condition_code.strip().lower()) if token
    )


@lru_cache(maxsize=1)
def load_chronic_priority_table(
    table_path: Path = DEFAULT_CHRONIC_PRIORITY_TABLE,
) -> ChronicPriorityTable:
    """Load the chronic-condition priority table.

    Args:
        table_path: JSON table path.

    Returns:
        Validated priority table.
    """
    with table_path.open(encoding="utf-8") as handle:
        raw_table = json.load(handle)
    return ChronicPriorityTable.model_validate(raw_table)


def canonicalize_conditions(
    chronic_diseases: Sequence[str],
    table: ChronicPriorityTable | None = None,
) -> tuple[str, ...]:
    """Resolve user profile disease codes to canonical condition codes.

    Args:
        chronic_diseases: Raw disease codes from ``UserProfile.chronic_diseases``.
        table: Optional already loaded priority table.

    Returns:
        Deduplicated canonical condition codes. Unknown codes are ignored.
    """
    if table is None:
        table = load_chronic_priority_table()

    alias_map: dict[str, str] = {}
    for condition_code, condition in table.conditions.items():
        canonical = normalize_condition_code(condition_code)
        alias_map[canonical] = condition_code
        for alias in condition.aliases:
            alias_map[normalize_condition_code(alias)] = condition_code

    canonical_codes: list[str] = []
    seen_codes: set[str] = set()
    for disease in chronic_diseases:
        resolved_code = alias_map.get(normalize_condition_code(disease))
        if resolved_code is None or resolved_code in seen_codes:
            continue
        canonical_codes.append(resolved_code)
        seen_codes.add(resolved_code)
    return tuple(canonical_codes)


def get_chronic_priority_match(
    nutrient_code: str,
    chronic_diseases: Sequence[str],
    table: ChronicPriorityTable | None = None,
) -> ChronicPriorityMatch | None:
    """Return priority boost context for one nutrient and profile condition set.

    Args:
        nutrient_code: Internal nutrient code from the analysis result.
        chronic_diseases: Raw disease codes from ``UserProfile.chronic_diseases``.
        table: Optional already loaded priority table.

    Returns:
        Priority match when the nutrient has a source-backed boost, otherwise None.
    """
    if table is None:
        table = load_chronic_priority_table()

    condition_codes = canonicalize_conditions(chronic_diseases, table)
    matched_conditions: list[str] = []
    source_ids: list[str] = []
    boost_score = 0
    message = DEFAULT_PRIORITY_MESSAGE

    for condition_code in condition_codes:
        condition = table.conditions[condition_code]
        for rule in condition.priority_nutrients:
            if rule.nutrient_code != nutrient_code:
                continue
            boost_score += rule.boost
            matched_conditions.append(condition_code)
            source_ids.extend(rule.source_ids)
            message = table.message_templates.get(rule.message_key, DEFAULT_PRIORITY_MESSAGE)

    if boost_score <= 0:
        return None

    return ChronicPriorityMatch(
        boost_score=boost_score,
        condition_codes=tuple(dict.fromkeys(matched_conditions)),
        source_ids=tuple(dict.fromkeys(source_ids)),
        message=message,
    )
