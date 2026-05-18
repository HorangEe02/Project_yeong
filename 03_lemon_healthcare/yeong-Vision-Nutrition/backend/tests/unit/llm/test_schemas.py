"""``src.llm.schemas`` Pydantic v2 모델 단위 테스트."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from src.llm.schemas import ParsedIngredient, ParsedServingSize, ParsedSupplement


class TestParsedIngredient:
    def test_minimal_valid(self) -> None:
        ing = ParsedIngredient(name_ko="비타민 C", amount=1000, unit="mg")
        assert ing.name_ko == "비타민 C"
        assert ing.name_en is None

    def test_with_english_name(self) -> None:
        ing = ParsedIngredient(
            name_ko="비타민 C",
            name_en="Vitamin C",
            amount=1000,
            unit="mg",
        )
        assert ing.name_en == "Vitamin C"

    def test_negative_amount_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ParsedIngredient(name_ko="x", amount=-1, unit="mg")

    def test_empty_name_ko_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ParsedIngredient(name_ko="", amount=1, unit="mg")

    def test_empty_unit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ParsedIngredient(name_ko="x", amount=1, unit="")

    def test_frozen_immutable(self) -> None:
        ing = ParsedIngredient(name_ko="x", amount=1, unit="mg")
        with pytest.raises(ValidationError):
            ing.amount = 2  # type: ignore[misc]


class TestParsedServingSize:
    def test_all_allowed_units(self) -> None:
        for unit in ("tablet", "capsule", "ml", "g"):
            assert ParsedServingSize(amount=1, unit=unit).unit == unit

    def test_invalid_unit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ParsedServingSize(amount=1, unit="oz")


class TestParsedSupplement:
    def test_default_empty_collections(self) -> None:
        s = ParsedSupplement()
        assert s.ingredients == []
        assert s.warnings == []
        assert s.engine == ""
        assert s.raw_text == ""

    def test_round_trip_via_model_validate(self) -> None:
        data = {
            "product_name": "종합비타민",
            "ingredients": [
                {"name_ko": "비타민 C", "amount": 1000, "unit": "mg"},
                {"name_ko": "비타민 D", "amount": 25, "unit": "μg"},
            ],
        }
        s = ParsedSupplement.model_validate(data)
        assert s.product_name == "종합비타민"
        assert len(s.ingredients) == 2
        assert s.ingredients[0].name_ko == "비타민 C"

    def test_json_schema_extractable_for_ollama_format(self) -> None:
        """``model_json_schema()`` 는 Ollama ``format=`` 인자로 전달 가능."""
        schema = ParsedSupplement.model_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "ingredients" in schema["properties"]

    def test_model_copy_updates_engine_and_raw_text(self) -> None:
        s = ParsedSupplement(product_name="x")
        copied = s.model_copy(update={"engine": "ollama:test", "raw_text": "abc"})
        assert copied.engine == "ollama:test"
        assert copied.raw_text == "abc"
        # 원본은 불변
        assert s.engine == ""
        assert s.raw_text == ""
