"""Tests for the eval statistical-discipline helpers (Step-0 gate rule)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

stats = importlib.import_module("scripts.eval_statistics")


def test_wilson_lower_bound_n41_matches_guideline() -> None:
    """field_macro 0.78 at n=41 has a Wilson lower bound near 0.63 (cannot certify 0.85)."""
    lower = stats.wilson_lower_bound(32, 41)
    assert 0.62 < lower < 0.65
    assert lower < 0.85  # the whole +0.07..0.10 gap is inside the noise band


def test_wilson_interval_contains_point() -> None:
    """The interval brackets the point estimate and stays within [0, 1]."""
    lower, upper = stats.wilson_interval(32, 41)
    assert 0.0 <= lower < 32 / 41 < upper <= 1.0


def test_wilson_zero_fixtures_is_no_information() -> None:
    """With no fixtures the interval is the whole [0, 1] (no certification possible)."""
    assert stats.wilson_interval(0, 0) == (0.0, 1.0)
    assert stats.wilson_lower_bound(0, 0) == 0.0


def test_wilson_perfect_score_lower_bound_below_one() -> None:
    """A perfect 41/41 still cannot certify 1.0; its lower bound is high but < 1."""
    lower = stats.wilson_lower_bound(41, 41)
    assert 0.85 < lower < 1.0


def test_metric_decision_point_above_but_not_certified() -> None:
    """A point estimate above threshold can still fail certification at small n."""
    decision = stats.metric_decision("field_match_ratio_macro", 0.92, 41, 0.90)
    assert decision.point_met is True
    assert decision.certified is False  # Wilson lower bound < 0.90 at n=41
    assert decision.lower_bound < 0.90


def test_metric_decision_below_threshold() -> None:
    """A point estimate below threshold is neither met nor certified."""
    decision = stats.metric_decision("ingredient_recall", 0.747, 41, 0.85)
    assert decision.point_met is False
    assert decision.certified is False
    assert 0.59 < decision.lower_bound < 0.63


def test_mcnemar_significant_when_one_sided_discordants() -> None:
    """All discordant pairs favoring A is significant."""
    result = stats.paired_mcnemar(10, 0)
    assert result.significant is True
    assert result.better == "a"
    assert result.p_value < 0.05


def test_mcnemar_not_significant_when_balanced() -> None:
    """Balanced discordants are not significant (p clamped to 1.0)."""
    result = stats.paired_mcnemar(5, 5)
    assert result.significant is False
    assert result.p_value == pytest.approx(1.0)
    assert result.better == "tie"


def test_mcnemar_no_discordant_pairs() -> None:
    """No discordant pairs => not significant, p-value 1.0."""
    result = stats.paired_mcnemar(0, 0)
    assert result.significant is False
    assert result.p_value == 1.0


def test_mcnemar_rejects_negative_counts() -> None:
    """Negative discordant counts are rejected."""
    with pytest.raises(ValueError):
        stats.paired_mcnemar(-1, 2)


def test_mcnemar_from_pass_vectors() -> None:
    """Per-fixture pass/fail vectors produce the correct discordant counts."""
    a_pass = [True, True, False, False, True]
    b_pass = [True, False, False, True, True]
    result = stats.paired_mcnemar_from_pass(a_pass, b_pass)
    assert result.b == 1  # idx1: A pass, B fail
    assert result.c == 1  # idx3: B pass, A fail
    assert result.better == "tie"


def test_mcnemar_from_pass_length_mismatch() -> None:
    """Misaligned vectors are rejected."""
    with pytest.raises(ValueError):
        stats.paired_mcnemar_from_pass([True], [True, False])
