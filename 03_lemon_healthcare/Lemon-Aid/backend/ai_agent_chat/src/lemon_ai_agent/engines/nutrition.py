from __future__ import annotations

from collections import defaultdict

from lemon_ai_agent.schemas import (
    DailyIntake,
    FindingLevel,
    NutrientAmount,
    NutrientFinding,
    ReferenceRange,
)

NUTRIENT_ALIASES = {
    "vitamin d": "vitamin d",
    "vitamin-d": "vitamin d",
    "비타민d": "vitamin d",
    "비타민 d": "vitamin d",
}

UNIT_ALIASES = {
    "g": "g",
    "gram": "g",
    "grams": "g",
    "mg": "mg",
    "milligram": "mg",
    "milligrams": "mg",
    "mcg": "mcg",
    "μg": "mcg",
    "µg": "mcg",
    "ug": "mcg",
    "iu": "iu",
}

UNIT_TO_MCG = {
    "g": 1_000_000.0,
    "mg": 1_000.0,
    "mcg": 1.0,
}

LOW_RATIO_THRESHOLD = 0.7
HIGH_RATIO_THRESHOLD = 1.3


class NutritionEngine:
    """Deterministic nutrition aggregation and reference comparison."""

    def __init__(self, references: list[ReferenceRange]) -> None:
        self._references = {
            self._canonical_nutrient_name(item.nutrient): item for item in references
        }

    def evaluate(self, intake: DailyIntake) -> list[NutrientFinding]:
        totals = self._aggregate(intake)
        findings: list[NutrientFinding] = []

        for nutrient_name, amount in sorted(totals.items()):
            reference = self._references.get(nutrient_name)
            if reference is None:
                findings.append(
                    NutrientFinding(
                        nutrient=nutrient_name,
                        total_amount=amount.amount,
                        unit=amount.unit,
                        ratio_to_target=None,
                        level=FindingLevel.ADEQUATE,
                        message="Reference range is not configured.",
                    )
                )
                continue

            ratio = amount.amount / reference.target if reference.target > 0 else None
            level = self._classify(amount.amount, reference)
            findings.append(
                NutrientFinding(
                    nutrient=reference.nutrient,
                    total_amount=round(amount.amount, 3),
                    unit=self._canonical_unit(reference.unit),
                    ratio_to_target=round(ratio, 3) if ratio is not None else None,
                    level=level,
                    message=self._message(reference.nutrient, level, ratio),
                )
            )

        return findings

    def _aggregate(self, intake: DailyIntake) -> dict[str, NutrientAmount]:
        totals: dict[tuple[str, str], float] = defaultdict(float)
        for food in intake.foods:
            for nutrient in food.nutrients:
                name, amount, unit = self._normalize_amount(nutrient)
                totals[(name, unit)] += amount
        for supplement in intake.supplements:
            multiplier = max(supplement.times_per_day, 1)
            for ingredient in supplement.ingredients:
                name, amount, unit = self._normalize_amount(ingredient)
                totals[(name, unit)] += amount * multiplier
        return {
            name: NutrientAmount(name=name, amount=amount, unit=unit)
            for (name, unit), amount in totals.items()
        }

    def _normalize_amount(self, nutrient: NutrientAmount) -> tuple[str, float, str]:
        name = self._canonical_nutrient_name(nutrient.name)
        unit = self._canonical_unit(nutrient.unit)
        reference = self._references.get(name)
        if reference is None:
            return name, nutrient.amount, unit

        target_unit = self._canonical_unit(reference.unit)
        converted = self._convert_amount(name, nutrient.amount, unit, target_unit)
        if converted is None:
            return f"{name} [{unit}]", nutrient.amount, unit
        return name, converted, target_unit

    def _canonical_nutrient_name(self, name: str) -> str:
        lowered = " ".join(name.strip().lower().split())
        return NUTRIENT_ALIASES.get(lowered, lowered)

    def _canonical_unit(self, unit: str) -> str:
        lowered = unit.strip().lower()
        return UNIT_ALIASES.get(lowered, lowered)

    def _convert_amount(
        self, nutrient_name: str, amount: float, source_unit: str, target_unit: str
    ) -> float | None:
        if source_unit == target_unit:
            return amount

        source_mcg = self._to_mcg(nutrient_name, amount, source_unit)
        if source_mcg is None:
            return None
        return self._from_mcg(source_mcg, target_unit)

    def _to_mcg(self, nutrient_name: str, amount: float, source_unit: str) -> float | None:
        if source_unit in UNIT_TO_MCG:
            return amount * UNIT_TO_MCG[source_unit]
        if nutrient_name == "vitamin d" and source_unit == "iu":
            return amount / 40.0
        return None

    def _from_mcg(self, amount_mcg: float, target_unit: str) -> float | None:
        if target_unit in UNIT_TO_MCG:
            return amount_mcg / UNIT_TO_MCG[target_unit]
        return None

    def _classify(self, amount: float, reference: ReferenceRange) -> FindingLevel:
        if reference.upper_limit is not None and amount > reference.upper_limit:
            return FindingLevel.RISKY
        ratio = amount / reference.target if reference.target > 0 else 1.0
        if ratio < LOW_RATIO_THRESHOLD:
            return FindingLevel.LOW
        if ratio > HIGH_RATIO_THRESHOLD:
            return FindingLevel.HIGH
        return FindingLevel.ADEQUATE

    def _message(self, nutrient: str, level: FindingLevel, ratio: float | None) -> str:
        if ratio is None:
            return f"{nutrient} could not be compared with a target."
        pct = round(ratio * 100)
        if level == FindingLevel.LOW:
            return f"{nutrient} intake is about {pct}% of the target."
        if level == FindingLevel.HIGH:
            return f"{nutrient} intake is above the target range."
        if level == FindingLevel.RISKY:
            return f"{nutrient} intake is above the configured upper limit."
        return f"{nutrient} intake is within the target range."
