from __future__ import annotations

from collections import defaultdict

from lemon_ai_agent.schemas import DailyIntake, SupplementDailyTotal


class SupplementEngine:
    """Deterministic supplement ingredient total calculation."""

    def evaluate(self, intake: DailyIntake) -> list[SupplementDailyTotal]:
        totals: dict[tuple[str, str], float] = defaultdict(float)
        products: dict[tuple[str, str], set[str]] = defaultdict(set)

        for supplement in intake.supplements:
            multiplier = max(supplement.times_per_day, 1)
            for ingredient in supplement.ingredients:
                key = (ingredient.name.lower(), ingredient.unit)
                totals[key] += ingredient.amount * multiplier
                products[key].add(supplement.product_name)

        return [
            SupplementDailyTotal(
                ingredient=name,
                total_amount=round(amount, 3),
                unit=unit,
                product_names=sorted(products[(name, unit)]),
            )
            for (name, unit), amount in sorted(totals.items())
        ]
