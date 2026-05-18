"""``src.nutrition.kdris`` 단위 테스트 — 실제 ``data/kdris/kdris_2020.csv`` 사용.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-03-nutrition-data.md Step 7
"""

from __future__ import annotations

import pytest
from src.models.schemas.nutrition import UserKDRIsContext
from src.nutrition.kdris import KDRIsCoverageError, _load_rows, lookup_kdris


class TestLookupKdrisBasics:
    def test_male_30_returns_male_rows(self) -> None:
        table = lookup_kdris(UserKDRIsContext(age=30, sex="male"))
        # 핵심 영양소가 포함되어야 한다
        for code in ("vitamin_c_mg", "calcium_mg", "iron_mg"):
            assert code in table
        # 남성 비타민 C RDA = 100
        assert table["vitamin_c_mg"]["rda"] == 100

    def test_female_30_uses_female_rda(self) -> None:
        table = lookup_kdris(UserKDRIsContext(age=30, sex="female"))
        # 여성 19-49 철 RDA = 14
        assert table["iron_mg"]["rda"] == 14

    def test_male_60_uses_50_plus_calcium(self) -> None:
        """남성 60세는 50+ 칼슘 RDA = 750."""
        table = lookup_kdris(UserKDRIsContext(age=60, sex="male"))
        assert table["calcium_mg"]["rda"] == 750

    def test_returns_none_for_undefined_values(self) -> None:
        """비타민 D 같이 RDA가 None 인 영양소도 정상 포함."""
        table = lookup_kdris(UserKDRIsContext(age=30, sex="male"))
        assert "vitamin_d_ug" in table
        assert table["vitamin_d_ug"]["rda"] is None
        assert table["vitamin_d_ug"]["ai"] == 10


class TestLookupKdrisPregnantAndLactating:
    def test_pregnant_woman_gets_pregnant_folate(self) -> None:
        """임신부 엽산 RDA = 620 (일반 여성 400 보다 높음)."""
        ctx = UserKDRIsContext(age=30, sex="female", is_pregnant=True)
        table = lookup_kdris(ctx)
        assert table["vitamin_b9_ug_dfe"]["rda"] == 620

    def test_lactating_woman_gets_lactating_folate(self) -> None:
        """수유부 엽산 RDA = 550."""
        ctx = UserKDRIsContext(age=30, sex="female", is_lactating=True)
        table = lookup_kdris(ctx)
        assert table["vitamin_b9_ug_dfe"]["rda"] == 550

    def test_pregnant_iron_higher_than_general(self) -> None:
        """임신부 철 RDA = 24."""
        ctx = UserKDRIsContext(age=30, sex="female", is_pregnant=True)
        table = lookup_kdris(ctx)
        assert table["iron_mg"]["rda"] == 24


class TestLookupKdrisCoverageError:
    def test_raises_when_no_rows_match(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """데이터셋이 비어 있으면 ``KDRIsCoverageError``."""
        from src.nutrition import kdris as module

        _load_rows.cache_clear()
        monkeypatch.setattr(module, "_load_rows", lambda: [])
        with pytest.raises(KDRIsCoverageError):
            lookup_kdris(UserKDRIsContext(age=30, sex="male"))
        _load_rows.cache_clear()


class TestAllRowsHaveValidStructure:
    def test_every_row_has_rda_or_ai_or_ear_or_ul(self) -> None:
        """모든 row에는 RDA/AI/EAR/UL 중 최소 하나가 있어야 한다."""
        _load_rows.cache_clear()
        rows = _load_rows()
        for row in rows:
            has_value = any(row[key] is not None for key in ("rda", "ai", "ear", "ul"))
            assert has_value, f"row missing all reference values: {row['code']}"
