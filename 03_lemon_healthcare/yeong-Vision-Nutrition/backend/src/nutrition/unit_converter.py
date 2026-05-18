"""IU ↔ 질량 단위 환산 (지방용성 비타민 A·D·E).

KDRIs 표준 단위(μg RAE / μg / mg α-TE)에 맞춰 영양제 라벨의 IU 값을 환산한다.
지원되지 않는 영양소나 단위에는 ``UnitConversionError`` 를 raise한다.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-03-nutrition-data.md Step 8
    data/mfds/unit_conversions.json
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

UNIT_CONVERSIONS_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "mfds" / "unit_conversions.json"
)


class UnitConversionError(ValueError):
    """단위 환산을 지원하지 않거나 입력이 유효하지 않은 경우."""


# nutrient_code → unit_conversions.json 의 그룹 key 매핑.
_CODE_TO_GROUP: Final[dict[str, str]] = {
    "vitamin_a_ug_rae": "vitamin_a",
    "vitamin_d_ug": "vitamin_d",
    "vitamin_e_mg_ate": "vitamin_e",
}


@lru_cache(maxsize=1)
def _load_table() -> dict[str, dict[str, Any]]:
    with UNIT_CONVERSIONS_PATH.open("r", encoding="utf-8") as f:
        data: dict[str, dict[str, Any]] = json.load(f)
    return data


def convert_iu(amount_iu: float, nutrient_code: str) -> tuple[float, str]:
    """IU 수치를 영양소별 target_unit 으로 환산한다.

    Args:
        amount_iu: 입력 IU 수치 (≥ 0).
        nutrient_code: 표준 영양소 코드.

    Returns:
        ``(converted_amount, target_unit)`` — 변환된 수치와 단위.

    Raises:
        UnitConversionError: 음수 입력이거나 지원되지 않는 영양소 코드.

    Examples:
        >>> convert_iu(1000, "vitamin_d_ug")
        (25.0, 'μg')
        >>> convert_iu(2000, "vitamin_a_ug_rae")
        (600.0, 'μg RAE')
    """
    if amount_iu < 0:
        raise UnitConversionError(f"amount_iu must be non-negative, got {amount_iu}")
    group = _CODE_TO_GROUP.get(nutrient_code)
    if group is None:
        raise UnitConversionError(
            f"IU conversion not supported for nutrient_code={nutrient_code!r}"
        )
    entry = _load_table().get(group)
    if entry is None:
        raise UnitConversionError(f"Missing conversion entry for group {group!r}")
    factor = float(entry["iu_to_target"])
    target_unit = str(entry["target_unit"])
    return (round(amount_iu * factor, 6), target_unit)
