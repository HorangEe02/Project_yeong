"""Statistical-discipline helpers for OCR/extraction gate decisions.

Implements the 0.85/0.90 gate "Step 0" measurement rule from
``docs/ocr_baseline_reports/2026-06-19-paddleocr-085-090-gate-redesign-guideline.md``:

- ``wilson_lower_bound`` / ``wilson_interval``: a metric measured on ``n`` held-out
  fixtures cannot be *certified* at a threshold unless its Wilson score-interval
  LOWER bound clears the threshold. At ``n=41`` a point estimate of ~0.78 has a
  lower bound near 0.63, so the whole "+0.07..0.10 gap" is inside the noise band.
- ``paired_mcnemar``: accept a strategy as "better" only when an exact two-sided
  McNemar test on per-fixture pass/fail of the SAME fixtures is significant.

Caveat (documented, not a bug): ``field_match_ratio_macro`` is a mean of per-product
ratios, so treating it as a single Bernoulli proportion is an APPROXIMATION. The
binomial Wilson interval is reported as a conservative screening bound; the
directional "n is too small to certify" conclusion holds regardless.

This module is pure-Python (stdlib only), privacy-safe (operates on counts, never
on raw OCR text / labels / images), and importable by gate scripts and tests.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# 95% two-sided normal quantile (z_{0.975}).
Z_95 = 1.959963984540054


def wilson_interval(successes: float, n: int, z: float = Z_95) -> tuple[float, float]:
    """Return the Wilson score interval ``(lower, upper)`` for a proportion.

    Args:
        successes: Number of "passing" fixtures (may be fractional when a
            mean-of-ratios metric is approximated as ``metric * n``).
        n: Number of fixtures the metric was measured on.
        z: Normal quantile (default 95% two-sided).

    Returns:
        ``(lower, upper)`` clamped to ``[0.0, 1.0]``. Returns ``(0.0, 1.0)`` when
        ``n <= 0`` (no information).
    """
    if n <= 0:
        return (0.0, 1.0)
    p = max(0.0, min(1.0, successes / n))
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))
    lower = center - margin
    upper = center + margin
    return (max(0.0, lower), min(1.0, upper))


def wilson_lower_bound(successes: float, n: int, z: float = Z_95) -> float:
    """Return only the Wilson score-interval lower bound (the certification bound)."""
    return wilson_interval(successes, n, z)[0]


@dataclass(frozen=True)
class MetricDecision:
    """A gate decision for one metric under the Wilson-lower-bound rule.

    Attributes:
        metric: Metric name.
        point: Observed point estimate.
        n: Fixture count.
        threshold: Required threshold.
        lower_bound: Wilson lower bound at the configured confidence.
        upper_bound: Wilson upper bound.
        point_met: Whether the point estimate clears the threshold.
        certified: Whether the LOWER bound clears the threshold (the real gate).
    """

    metric: str
    point: float
    n: int
    threshold: float
    lower_bound: float
    upper_bound: float
    point_met: bool
    certified: bool


def metric_decision(
    metric: str,
    point: float,
    n: int,
    threshold: float,
    z: float = Z_95,
) -> MetricDecision:
    """Build a :class:`MetricDecision` for one metric.

    Args:
        metric: Metric name.
        point: Observed point estimate in ``[0, 1]``.
        n: Number of held-out fixtures.
        threshold: Required threshold (e.g. 0.85).
        z: Normal quantile.

    Returns:
        A populated :class:`MetricDecision`. ``certified`` is the honest gate:
        only ``True`` when the Wilson lower bound clears ``threshold``.
    """
    lower, upper = wilson_interval(point * n, n, z)
    return MetricDecision(
        metric=metric,
        point=point,
        n=n,
        threshold=threshold,
        lower_bound=lower,
        upper_bound=upper,
        point_met=point >= threshold,
        certified=lower >= threshold,
    )


@dataclass(frozen=True)
class McNemarResult:
    """Exact two-sided McNemar test result for a paired comparison.

    Attributes:
        b: Discordant fixtures where strategy A passed and B failed.
        c: Discordant fixtures where strategy B passed and A failed.
        p_value: Exact two-sided binomial p-value over the discordant pairs.
        significant: Whether ``p_value < alpha``.
        better: ``"a"`` / ``"b"`` / ``"tie"`` — which strategy won more discordants.
    """

    b: int
    c: int
    p_value: float
    significant: bool
    better: str


def paired_mcnemar(b: int, c: int, alpha: float = 0.05) -> McNemarResult:
    """Exact two-sided McNemar test on discordant-pair counts.

    Uses the exact binomial test (correct for the small discordant counts typical
    of a ~41-fixture holdout) rather than the chi-square approximation.

    Args:
        b: Count where A passed, B failed.
        c: Count where B passed, A failed.
        alpha: Significance level.

    Returns:
        A :class:`McNemarResult`. With no discordant pairs the p-value is 1.0.

    Raises:
        ValueError: If ``b`` or ``c`` is negative.
    """
    if b < 0 or c < 0:
        raise ValueError("Discordant counts must be non-negative.")
    n = b + c
    if n == 0:
        return McNemarResult(b=b, c=c, p_value=1.0, significant=False, better="tie")
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) * (0.5**n)
    p_value = min(1.0, 2.0 * tail)
    better = "a" if b > c else "b" if c > b else "tie"
    return McNemarResult(
        b=b,
        c=c,
        p_value=p_value,
        significant=p_value < alpha,
        better=better,
    )


def paired_mcnemar_from_pass(
    a_pass: list[bool],
    b_pass: list[bool],
    alpha: float = 0.05,
) -> McNemarResult:
    """McNemar test from two aligned per-fixture pass/fail vectors.

    Args:
        a_pass: Per-fixture pass/fail for strategy A.
        b_pass: Per-fixture pass/fail for strategy B (same fixtures, same order).
        alpha: Significance level.

    Returns:
        A :class:`McNemarResult`.

    Raises:
        ValueError: If the two vectors differ in length.
    """
    if len(a_pass) != len(b_pass):
        raise ValueError("Pass/fail vectors must be the same length and aligned.")
    b = sum(1 for a, bb in zip(a_pass, b_pass, strict=True) if a and not bb)
    c = sum(1 for a, bb in zip(a_pass, b_pass, strict=True) if bb and not a)
    return paired_mcnemar(b, c, alpha)
