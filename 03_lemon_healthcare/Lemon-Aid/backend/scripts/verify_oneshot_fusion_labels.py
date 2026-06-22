"""End-to-end verification harness for one-shot multi-image OCR fusion.

Drives the live ``POST /api/v1/supplements/analyze-multi`` route against real
multi-image supplement label sets and produces an A/B comparison report between
``merge_strategy=single_product`` (the one-shot fusion path) and
``merge_strategy=distinct_products`` (the legacy per-image path).

It answers the open follow-up: "does one-shot fusion actually improve the four
target fields (product name / ingredient+amount / bilingual naming / intake +
precautions) on real cylindrical labels split across several photos?"

Prerequisites (the route uses the real configured OCR + parser adapters):
    * Backend running with ``SUPPLEMENT_ONE_SHOT_FUSION_ENABLED=true`` (the flag
      is dark-launched / default False), e.g. set it in the backend container
      env and recreate, or pass it to the process.
    * A bearer token for a user that holds ``supplement:write`` plus the
      external-OCR / data-retention consents the route gates on (otherwise the
      route returns 403 ``consent_required``).
    * Images laid out one product per subfolder under ``--images-root``::

          labels/
            vitamin-d-cylinder/
              01-front.jpg
              02-facts.jpg
              03-intake.jpg
              roles.json        # optional: {"01-front.jpg": "front_label", ...}
            omega-3/
              ...

Privacy: the report contains parsed label content (product names, ingredients)
— that IS the verification target. Write it under ``outputs/`` (gitignored) and
do not commit it. No raw OCR text is requested or stored by the route.

Usage::

    .venv/bin/python scripts/verify_oneshot_fusion_labels.py \
        --base-url http://localhost:8000 \
        --token "$SUPPLEMENT_WRITE_TOKEN" \
        --images-root ./labels \
        --out outputs/oneshot-fusion-verification.md
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

ANALYZE_MULTI_PATH = "/api/v1/supplements/analyze-multi"
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})
ROLE_SIDECAR_NAME = "roles.json"
STRATEGIES = ("single_product", "distinct_products")
# Bilingual ``한글 (English)`` detection: a Hangul block followed by a
# parenthesized Latin block, e.g. "비타민 D (Vitamin D)".
_HANGUL_RANGE = range(0xAC00, 0xD7A4)


@dataclass(frozen=True)
class LabelSet:
    """One product photographed across several images."""

    product_dir: Path
    images: tuple[Path, ...]
    roles: tuple[str | None, ...]

    @property
    def name(self) -> str:
        return self.product_dir.name


@dataclass
class Ingredient:
    """Sanitized ingredient view extracted from a preview."""

    display_name: str
    original_name: str | None
    amount: float | None
    unit: str | None

    @property
    def has_amount(self) -> bool:
        return self.amount is not None

    @property
    def is_bilingual(self) -> bool:
        """True when both a Korean and a Latin/English name are present.

        Either via separate ``display_name``/``original_name`` fields or via the
        inline ``한글 (English)`` convention inside ``display_name``.
        """
        if self.original_name and _has_hangul(self.display_name) and _has_latin(self.original_name):
            return True
        return _has_hangul(self.display_name) and _has_parenthesized_latin(self.display_name)


@dataclass
class PreviewMetrics:
    """Field-level metrics extracted from one strategy's response."""

    result_count: int
    product_name: str | None
    ingredients: list[Ingredient] = field(default_factory=list)
    intake_method: str | None = None
    precautions: list[str] = field(default_factory=list)
    missing_required_sections: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def ingredient_count(self) -> int:
        return len(self.ingredients)

    @property
    def amount_count(self) -> int:
        return sum(1 for ing in self.ingredients if ing.has_amount)

    @property
    def bilingual_count(self) -> int:
        return sum(1 for ing in self.ingredients if ing.is_bilingual)

    @property
    def bilingual_pct(self) -> float:
        if not self.ingredients:
            return 0.0
        return 100.0 * self.bilingual_count / len(self.ingredients)


def _has_hangul(text: str) -> bool:
    return any(ord(ch) in _HANGUL_RANGE for ch in text)


def _has_latin(text: str) -> bool:
    return any(("a" <= ch.lower() <= "z") for ch in text)


def _has_parenthesized_latin(text: str) -> bool:
    start = text.find("(")
    end = text.find(")", start + 1)
    if start == -1 or end == -1:
        return False
    return _has_latin(text[start + 1 : end])


def discover_label_sets(images_root: Path) -> list[LabelSet]:
    """Find one label set per immediate subfolder of ``images_root``."""
    sets: list[LabelSet] = []
    for product_dir in sorted(p for p in images_root.iterdir() if p.is_dir()):
        images = tuple(
            sorted(
                p
                for p in product_dir.iterdir()
                if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
            )
        )
        if not images:
            continue
        roles = _resolve_roles(product_dir, images)
        sets.append(LabelSet(product_dir=product_dir, images=images, roles=roles))
    return sets


def _resolve_roles(product_dir: Path, images: tuple[Path, ...]) -> tuple[str | None, ...]:
    """Read optional ``roles.json`` sidecar mapping filename -> role."""
    sidecar = product_dir / ROLE_SIDECAR_NAME
    if not sidecar.is_file():
        return tuple(None for _ in images)
    try:
        mapping = json.loads(sidecar.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return tuple(None for _ in images)
    if not isinstance(mapping, dict):
        return tuple(None for _ in images)
    return tuple(mapping.get(image.name) for image in images)


def analyze(
    client: httpx.Client,
    *,
    label_set: LabelSet,
    strategy: str,
    ocr_provider: str,
) -> dict[str, Any] | str:
    """POST one label set under one strategy. Returns parsed JSON or an error string."""
    files = [
        (
            "images",
            (image.name, image.read_bytes(), _guess_mime(image)),
        )
        for image in label_set.images
    ]
    data: dict[str, str] = {"merge_strategy": strategy, "ocr_provider": ocr_provider}
    if any(role is not None for role in label_set.roles):
        roles = [role or "unknown" for role in label_set.roles]
        data["image_roles_json"] = json.dumps(roles, ensure_ascii=False)
    try:
        response = client.post(ANALYZE_MULTI_PATH, files=files, data=data)
    except httpx.HTTPError as exc:  # network / timeout
        return f"request_error: {exc}"
    if response.status_code != httpx.codes.ACCEPTED:
        return f"http_{response.status_code}: {response.text[:300]}"
    try:
        return response.json()
    except json.JSONDecodeError:
        return "invalid_json_response"


def _guess_mime(image: Path) -> str:
    mime, _ = mimetypes.guess_type(image.name)
    return mime or "image/jpeg"


def extract_metrics(payload: dict[str, Any] | str, *, strategy: str) -> PreviewMetrics:
    """Reduce a response payload to field-level metrics."""
    if isinstance(payload, str):
        return PreviewMetrics(result_count=0, product_name=None, error=payload)
    previews = payload.get("previews") or []
    if strategy == "single_product":
        merged = payload.get("merged_preview")
        source = merged if isinstance(merged, dict) else (previews[0] if previews else {})
        result_count = 1 if isinstance(merged, dict) else len(previews)
        metrics = _metrics_from_preview(source)
        metrics.result_count = result_count
    else:
        # Distinct path: aggregate across per-image previews to reflect what the
        # user effectively sees after the legacy late-merge.
        metrics = _aggregate_previews(previews)
        metrics.result_count = len(previews)
    raw_missing = payload.get("missing_required_sections")
    if isinstance(raw_missing, list):
        metrics.missing_required_sections = [str(item) for item in raw_missing]
    return metrics


def _metrics_from_preview(preview: dict[str, Any]) -> PreviewMetrics:
    """Extract fields from one preview dict (defensive about exact nesting)."""
    snapshot = preview.get("parsed_snapshot") if isinstance(preview, dict) else None
    source = snapshot if isinstance(snapshot, dict) else preview
    parsed_product = source.get("parsed_product")
    product_name = (
        str(parsed_product.get("product_name"))
        if isinstance(parsed_product, dict) and parsed_product.get("product_name")
        else None
    )
    ingredients = _parse_ingredients(source.get("ingredient_candidates"))
    intake = source.get("intake_method")
    intake_text = _coerce_intake_text(intake)
    precautions = _coerce_str_list(source.get("precautions"))
    return PreviewMetrics(
        result_count=1,
        product_name=product_name,
        ingredients=ingredients,
        intake_method=intake_text,
        precautions=precautions,
    )


def _aggregate_previews(previews: list[Any]) -> PreviewMetrics:
    """Union ingredients and pick first non-empty fields across per-image previews."""
    aggregate = PreviewMetrics(result_count=len(previews), product_name=None)
    seen_ingredients: set[tuple[str, str | None, float | None, str | None]] = set()
    for preview in previews:
        if not isinstance(preview, dict):
            continue
        item = _metrics_from_preview(preview)
        if aggregate.product_name is None and item.product_name:
            aggregate.product_name = item.product_name
        if aggregate.intake_method is None and item.intake_method:
            aggregate.intake_method = item.intake_method
        for precaution in item.precautions:
            if precaution not in aggregate.precautions:
                aggregate.precautions.append(precaution)
        for ing in item.ingredients:
            key = (ing.display_name, ing.original_name, ing.amount, ing.unit)
            if key not in seen_ingredients:
                seen_ingredients.add(key)
                aggregate.ingredients.append(ing)
    return aggregate


def _parse_ingredients(raw: Any) -> list[Ingredient]:
    if not isinstance(raw, list):
        return []
    parsed: list[Ingredient] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        display = item.get("display_name")
        if not isinstance(display, str) or not display.strip():
            continue
        amount = item.get("amount")
        parsed.append(
            Ingredient(
                display_name=display.strip(),
                original_name=(
                    str(item["original_name"]).strip()
                    if isinstance(item.get("original_name"), str) and item["original_name"].strip()
                    else None
                ),
                amount=float(amount) if isinstance(amount, (int, float)) else None,
                unit=(
                    str(item["unit"]).strip()
                    if isinstance(item.get("unit"), str) and item["unit"].strip()
                    else None
                ),
            )
        )
    return parsed


def _coerce_intake_text(intake: Any) -> str | None:
    if isinstance(intake, str) and intake.strip():
        return intake.strip()
    if isinstance(intake, dict):
        text = intake.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return None


def _coerce_str_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip():
            out.append(item["text"].strip())
    return out


def render_report(results: list[tuple[LabelSet, dict[str, PreviewMetrics]]]) -> str:
    """Render a markdown A/B comparison report."""
    lines: list[str] = []
    lines.append("# One-shot fusion — real-label verification report")
    lines.append("")
    lines.append(f"- Label sets: {len(results)}")
    lines.append("- Strategies: single_product (fusion) vs distinct_products (legacy per-image)")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        "| Product | Images | Strategy | Results | Ingredients | w/ amount | "
        "Bilingual % | Missing sections | Error |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for label_set, by_strategy in results:
        for strategy in STRATEGIES:
            metrics = by_strategy.get(strategy)
            if metrics is None:
                continue
            missing = ", ".join(metrics.missing_required_sections) or "—"
            lines.append(
                f"| {label_set.name} | {len(label_set.images)} | {strategy} | "
                f"{metrics.result_count} | {metrics.ingredient_count} | {metrics.amount_count} | "
                f"{metrics.bilingual_pct:.0f}% | {missing} | {metrics.error or '—'} |"
            )
    lines.append("")
    lines.append("## Per-product detail")
    lines.append("")
    for label_set, by_strategy in results:
        lines.append(f"### {label_set.name}")
        lines.append("")
        for strategy in STRATEGIES:
            metrics = by_strategy.get(strategy)
            if metrics is None:
                continue
            lines.append(f"**{strategy}**")
            lines.append("")
            if metrics.error:
                lines.append(f"- ⚠️ error: `{metrics.error}`")
                lines.append("")
                continue
            lines.append(f"- result_count: {metrics.result_count}")
            lines.append(f"- product_name: {metrics.product_name or '∅'}")
            lines.append(f"- intake_method: {'✓' if metrics.intake_method else '∅'}")
            lines.append(f"- precautions: {len(metrics.precautions)}")
            lines.append(
                f"- ingredients: {metrics.ingredient_count} "
                f"({metrics.amount_count} with amount, {metrics.bilingual_count} bilingual)"
            )
            for ing in metrics.ingredients:
                amount = f"{ing.amount:g} {ing.unit}" if ing.has_amount else "—"
                original = f" / {ing.original_name}" if ing.original_name else ""
                lines.append(f"    - {ing.display_name}{original}: {amount}")
            lines.append("")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--token", required=True, help="Bearer token with supplement:write.")
    parser.add_argument("--images-root", required=True, type=Path)
    parser.add_argument("--ocr-provider", default="configured")
    parser.add_argument("--out", type=Path, default=None, help="Markdown report output path.")
    parser.add_argument("--timeout", type=float, default=120.0, help="Per-request timeout seconds.")
    parser.add_argument(
        "--strategies",
        default=",".join(STRATEGIES),
        help="Comma-separated subset of strategies to run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    images_root: Path = args.images_root
    if not images_root.is_dir():
        print(f"error: images-root not found: {images_root}", file=sys.stderr)
        return 2
    strategies = [s.strip() for s in args.strategies.split(",") if s.strip() in STRATEGIES]
    if not strategies:
        print("error: no valid strategies selected", file=sys.stderr)
        return 2
    label_sets = discover_label_sets(images_root)
    if not label_sets:
        print(f"error: no label-set subfolders with images under {images_root}", file=sys.stderr)
        return 2

    results: list[tuple[LabelSet, dict[str, PreviewMetrics]]] = []
    headers = {"Authorization": f"Bearer {args.token}"}
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=args.timeout) as client:
        for label_set in label_sets:
            by_strategy: dict[str, PreviewMetrics] = {}
            for strategy in strategies:
                payload = analyze(
                    client,
                    label_set=label_set,
                    strategy=strategy,
                    ocr_provider=args.ocr_provider,
                )
                metrics = extract_metrics(payload, strategy=strategy)
                by_strategy[strategy] = metrics
                status = metrics.error or (
                    f"results={metrics.result_count} ingredients={metrics.ingredient_count}"
                )
                print(f"[{label_set.name}] {strategy}: {status}")
            results.append((label_set, by_strategy))

    report = render_report(results)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"\nReport written to {args.out}")
    else:
        print("\n" + report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
