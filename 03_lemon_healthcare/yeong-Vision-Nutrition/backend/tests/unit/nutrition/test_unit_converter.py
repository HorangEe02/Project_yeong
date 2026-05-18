"""``src.nutrition.unit_converter`` 단위 테스트."""

from __future__ import annotations

import pytest
from src.nutrition.unit_converter import UnitConversionError, convert_iu


class TestConvertIuVitaminD:
    def test_1000_iu_equals_25_ug(self) -> None:
        """1000 IU vitamin D = 25 μg cholecalciferol."""
        amount, unit = convert_iu(1000, "vitamin_d_ug")
        assert amount == 25.0
        assert unit == "μg"

    def test_zero_iu_returns_zero(self) -> None:
        amount, _ = convert_iu(0, "vitamin_d_ug")
        assert amount == 0.0


class TestConvertIuVitaminA:
    def test_2000_iu_equals_600_ug_rae(self) -> None:
        """2000 IU vitamin A = 600 μg RAE."""
        amount, unit = convert_iu(2000, "vitamin_a_ug_rae")
        assert amount == 600.0
        assert unit == "μg RAE"


class TestConvertIuVitaminE:
    def test_100_iu_equals_67_mg_ate(self) -> None:
        amount, unit = convert_iu(100, "vitamin_e_mg_ate")
        assert amount == 67.0
        assert unit == "mg α-TE"


class TestConvertIuErrors:
    def test_negative_input_raises(self) -> None:
        with pytest.raises(UnitConversionError):
            convert_iu(-1, "vitamin_d_ug")

    def test_unsupported_code_raises(self) -> None:
        """비타민 C 같이 IU 단위가 없는 영양소는 환산 불가."""
        with pytest.raises(UnitConversionError):
            convert_iu(100, "vitamin_c_mg")

    def test_unknown_code_raises(self) -> None:
        with pytest.raises(UnitConversionError):
            convert_iu(100, "totally_unknown_nutrient")
