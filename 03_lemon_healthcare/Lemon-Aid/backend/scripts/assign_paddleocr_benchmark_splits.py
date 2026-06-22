"""Assign leakage-safe dataset splits to PaddleOCR OCR benchmark fixtures.

The script consumes a redacted human-reviewed OCR benchmark manifest and writes
the same rows with deterministic ``train``/``holdout``/``test`` split metadata.
Rows are grouped by ``product_dir_hash`` so images from the same source product
cannot appear in multiple splits. It does not read images, call OCR providers,
write database rows, train PaddleOCR, or emit product literals, raw OCR text,
provider payloads, local source paths, image bytes, credentials, or request
headers.

References:
    https://docs.python.org/3/library/hashlib.html
    https://docs.python.org/3/library/json.html
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "paddleocr-benchmark-split-assignment-v1"
SUPPORTED_ROW_SCHEMA_VERSION = "supplement-ocr-provider-benchmark-fixture-v1"
DEFAULT_SEED = "lemon-aid-paddleocr-v1"
DEFAULT_HOLDOUT_RATIO = 0.2
DEFAULT_TEST_RATIO = 0.1
DEFAULT_MIN_HOLDOUT_FIXTURES = 30
DEFAULT_MIN_TEST_FIXTURES = 0
SPLITS = ("train", "holdout", "test")
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
RAW_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "image_bytes",
        "local_path",
        "ocr_text",
        "provider_payload",
        "raw_image",
        "raw_model_response",
        "raw_ocr_text",
        "raw_provider_payload",
        "request_headers",
        "secret",
        "service_key",
    }
)
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
SECRET_LIKE_MARKERS = (
    "bearer ",
    "ngrok-free.dev",
    "sb_secret_",
    "service_role",
    "aws_secret_access_key",
    "-----begin",
)
SOURCE_DOC_URLS = (
    "https://docs.python.org/3/library/hashlib.html",
    "https://docs.python.org/3/library/json.html",
)


class PaddleOCRBenchmarkSplitError(ValueError):
    """Raised when benchmark split assignment cannot be trusted."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--holdout-ratio", type=float, default=DEFAULT_HOLDOUT_RATIO)
    parser.add_argument("--test-ratio", type=float, default=DEFAULT_TEST_RATIO)
    parser.add_argument(
        "--min-holdout-fixtures",
        type=int,
        default=DEFAULT_MIN_HOLDOUT_FIXTURES,
    )
    parser.add_argument(
        "--min-test-fixtures",
        type=int,
        default=DEFAULT_MIN_TEST_FIXTURES,
    )
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Run split assignment and write redacted artifacts.

    Args:
        argv: Optional argument list for tests.

    Returns:
        ``0`` when assignment artifacts were written, otherwise ``1``.
    """
    args = parse_args(argv)
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    try:
        rows, summary = assign_paddleocr_benchmark_splits(
            benchmark_manifest=args.benchmark_manifest,
            seed=args.seed,
            holdout_ratio=args.holdout_ratio,
            test_ratio=args.test_ratio,
            min_holdout_fixtures=args.min_holdout_fixtures,
            min_test_fixtures=args.min_test_fixtures,
        )
        _write_jsonl(output_path, rows)
        _write_json(summary_path, summary)
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, PaddleOCRBenchmarkSplitError, ValueError) as exc:
        summary = _error_summary(error=exc, manifest_name=args.benchmark_manifest.name)
        _write_json(summary_path, summary)
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
        return 1


def assign_paddleocr_benchmark_splits(
    *,
    benchmark_manifest: Path,
    seed: str = DEFAULT_SEED,
    holdout_ratio: float = DEFAULT_HOLDOUT_RATIO,
    test_ratio: float = DEFAULT_TEST_RATIO,
    min_holdout_fixtures: int = DEFAULT_MIN_HOLDOUT_FIXTURES,
    min_test_fixtures: int = DEFAULT_MIN_TEST_FIXTURES,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Assign deterministic, product-group-safe splits.

    Args:
        benchmark_manifest: Redacted human-reviewed OCR benchmark JSONL.
        seed: Stable seed used only for deterministic group ordering.
        holdout_ratio: Desired holdout row ratio in ``0..1``.
        test_ratio: Desired test row ratio in ``0..1``.
        min_holdout_fixtures: Minimum holdout rows expected by later gates.
        min_test_fixtures: Minimum test rows expected by later gates.

    Returns:
        Split-assigned rows and a redacted summary.

    Raises:
        PaddleOCRBenchmarkSplitError: If rows are malformed or unsafe.
        ValueError: If split ratio arguments are invalid.
    """
    seed = _safe_token(seed, field_name="seed")
    _validate_ratios(holdout_ratio=holdout_ratio, test_ratio=test_ratio)
    if min_holdout_fixtures < 0 or min_test_fixtures < 0:
        raise ValueError("minimum fixture counts must be non-negative.")

    rows = _read_jsonl(benchmark_manifest)
    groups = _rows_by_product_group(rows)
    assignments = _assign_groups(
        groups=groups,
        seed=seed,
        holdout_ratio=holdout_ratio,
        test_ratio=test_ratio,
    )
    assigned_rows = _apply_assignments(rows=rows, assignments=assignments, seed=seed)
    summary = _summary(
        benchmark_manifest=benchmark_manifest,
        rows=assigned_rows,
        groups=groups,
        holdout_ratio=holdout_ratio,
        test_ratio=test_ratio,
        min_holdout_fixtures=min_holdout_fixtures,
        min_test_fixtures=min_test_fixtures,
        seed=seed,
    )
    _reject_unsafe_payload({"rows": assigned_rows, "summary": summary})
    return assigned_rows, summary


def _rows_by_product_group(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Return benchmark rows grouped by product hash.

    Args:
        rows: Benchmark rows.

    Returns:
        Mapping from product hash to rows.

    Raises:
        PaddleOCRBenchmarkSplitError: If any row lacks a safe product hash.
    """
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        _reject_unsafe_payload(row)
        schema_version = row.get("schema_version")
        if schema_version != SUPPORTED_ROW_SCHEMA_VERSION:
            raise PaddleOCRBenchmarkSplitError("benchmark row schema is not supported.")
        product_hash = _sha256(row.get("product_dir_hash"), field_name="product_dir_hash")
        groups[product_hash].append(row)
    return dict(groups)


def _assign_groups(
    *,
    groups: Mapping[str, list[dict[str, Any]]],
    seed: str,
    holdout_ratio: float,
    test_ratio: float,
) -> dict[str, str]:
    """Assign product groups to splits using deterministic hashed order.

    Args:
        groups: Product-hash groups.
        seed: Stable seed.
        holdout_ratio: Desired holdout row ratio.
        test_ratio: Desired test row ratio.

    Returns:
        Mapping from product hash to split.
    """
    row_count = sum(len(rows) for rows in groups.values())
    desired_test_count = round(row_count * test_ratio)
    desired_holdout_count = round(row_count * holdout_ratio)
    ordered_groups = sorted(
        groups,
        key=lambda product_hash: _stable_sort_key(seed=seed, product_hash=product_hash),
    )
    assignments: dict[str, str] = {}
    split_counts: Counter[str] = Counter()

    for product_hash in ordered_groups:
        group_size = len(groups[product_hash])
        if split_counts["test"] < desired_test_count:
            split = "test"
        elif split_counts["holdout"] < desired_holdout_count:
            split = "holdout"
        else:
            split = "train"
        assignments[product_hash] = split
        split_counts[split] += group_size
    return assignments


def _apply_assignments(
    *,
    rows: list[dict[str, Any]],
    assignments: Mapping[str, str],
    seed: str,
) -> list[dict[str, Any]]:
    """Return rows with split and leakage metadata attached.

    Args:
        rows: Benchmark rows.
        assignments: Product hash to split mapping.
        seed: Assignment seed.

    Returns:
        New row dictionaries.
    """
    seed_hash = _sha256_text(seed)
    assigned: list[dict[str, Any]] = []
    for row in rows:
        product_hash = _sha256(row.get("product_dir_hash"), field_name="product_dir_hash")
        split = assignments[product_hash]
        updated = dict(row)
        updated.update(
            {
                "split": split,
                "leakage_group_hash": product_hash,
                "leakage_check_passed": True,
                "split_assignment_method": "deterministic_product_dir_hash_group_split",
                "split_assignment_seed_hash": seed_hash,
            }
        )
        assigned.append(updated)
    return assigned


def _summary(
    *,
    benchmark_manifest: Path,
    rows: list[dict[str, Any]],
    groups: Mapping[str, list[dict[str, Any]]],
    holdout_ratio: float,
    test_ratio: float,
    min_holdout_fixtures: int,
    min_test_fixtures: int,
    seed: str,
) -> dict[str, Any]:
    """Return a redacted split assignment summary.

    Args:
        benchmark_manifest: Input manifest path.
        rows: Split-assigned rows.
        groups: Product-hash groups.
        holdout_ratio: Requested holdout ratio.
        test_ratio: Requested test ratio.
        min_holdout_fixtures: Minimum holdout rows expected by later gates.
        min_test_fixtures: Minimum test rows expected by later gates.
        seed: Assignment seed.

    Returns:
        Redacted summary.
    """
    split_counts: Counter[str] = Counter(str(row["split"]) for row in rows)
    group_split_counts = _group_split_counts(rows)
    leakage_check_passed = _leakage_check_passed(rows)
    checks = {
        "has_rows": len(rows) > 0,
        "has_product_groups": len(groups) > 0,
        "all_groups_in_single_split": leakage_check_passed,
        "holdout_minimum_met": split_counts["holdout"] >= min_holdout_fixtures,
        "test_minimum_met": split_counts["test"] >= min_test_fixtures,
    }
    status = (
        "ready_for_holdout_eval" if all(checks.values()) else "assigned_but_eval_minimum_not_met"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "benchmark_manifest_name": benchmark_manifest.name,
        "benchmark_manifest_hash": _sha256_text(str(benchmark_manifest.expanduser())),
        "row_count": len(rows),
        "product_group_count": len(groups),
        "split_counts": {split: split_counts.get(split, 0) for split in SPLITS},
        "product_group_split_counts": {split: group_split_counts.get(split, 0) for split in SPLITS},
        "holdout_ratio": round(holdout_ratio, 6),
        "test_ratio": round(test_ratio, 6),
        "train_ratio": round(1 - holdout_ratio - test_ratio, 6),
        "min_holdout_fixtures": min_holdout_fixtures,
        "min_test_fixtures": min_test_fixtures,
        "checks": checks,
        "status": status,
        "ready_for_holdout_eval": status == "ready_for_holdout_eval",
        "leakage_check_passed": leakage_check_passed,
        "split_assignment_method": "deterministic_product_dir_hash_group_split",
        "split_assignment_seed_hash": _sha256_text(seed),
        "db_write_performed": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _group_split_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    """Count product groups per split.

    Args:
        rows: Split-assigned rows.

    Returns:
        Split to group count mapping.
    """
    seen: set[str] = set()
    counts: Counter[str] = Counter()
    for row in rows:
        group_hash = _sha256(row.get("leakage_group_hash"), field_name="leakage_group_hash")
        if group_hash in seen:
            continue
        seen.add(group_hash)
        counts[str(row["split"])] += 1
    return counts


def _leakage_check_passed(rows: list[dict[str, Any]]) -> bool:
    """Return whether no product group appears in multiple splits.

    Args:
        rows: Split-assigned rows.

    Returns:
        True when product-group split assignment has no leakage.
    """
    group_splits: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        group_hash = _sha256(row.get("leakage_group_hash"), field_name="leakage_group_hash")
        split = _split(row.get("split"))
        group_splits[group_hash].add(split)
    return all(len(splits) == 1 for splits in group_splits.values())


def _validate_ratios(*, holdout_ratio: float, test_ratio: float) -> None:
    """Validate split ratios.

    Args:
        holdout_ratio: Desired holdout ratio.
        test_ratio: Desired test ratio.

    Raises:
        ValueError: If ratios are outside supported ranges.
    """
    for name, value in (("holdout_ratio", holdout_ratio), ("test_ratio", test_ratio)):
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{name} must be numeric.")
        if value < 0 or value >= 1:
            raise ValueError(f"{name} must be in 0..1.")
    if holdout_ratio + test_ratio >= 1:
        raise ValueError("holdout_ratio plus test_ratio must be less than 1.")


def _stable_sort_key(*, seed: str, product_hash: str) -> str:
    """Return a deterministic sort key for a product group.

    Args:
        seed: Stable seed.
        product_hash: Product group hash.

    Returns:
        SHA-256 hex digest.
    """
    return _sha256_text(f"{seed}:{product_hash}")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL object rows.

    Args:
        path: JSONL path.

    Returns:
        Parsed object rows.

    Raises:
        PaddleOCRBenchmarkSplitError: If any line is not a JSON object.
    """
    if not path.is_file():
        raise PaddleOCRBenchmarkSplitError("benchmark manifest does not exist.")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise PaddleOCRBenchmarkSplitError(f"JSONL line {line_number} must be an object.")
        rows.append(parsed)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write JSONL rows.

    Args:
        path: Destination path.
        rows: JSON rows.
    """
    _reject_unsafe_payload(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a JSON summary.

    Args:
        path: Destination path.
        payload: JSON payload.
    """
    _reject_unsafe_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _safe_token(value: Any, *, field_name: str) -> str:
    """Return a safe bounded token.

    Args:
        value: Candidate value.
        field_name: Diagnostic field name.

    Returns:
        Safe token.

    Raises:
        ValueError: If the value is not a token.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    token = value.strip()
    if not SAFE_TOKEN_PATTERN.fullmatch(token):
        raise ValueError(f"{field_name} must be a stable token.")
    return token


def _sha256(value: Any, *, field_name: str) -> str:
    """Return a SHA-256 digest value.

    Args:
        value: Candidate value.
        field_name: Diagnostic field name.

    Returns:
        Lowercase SHA-256 hex digest.

    Raises:
        PaddleOCRBenchmarkSplitError: If the value is not a SHA-256 digest.
    """
    if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
        raise PaddleOCRBenchmarkSplitError(f"{field_name} must be a SHA-256 digest.")
    return value.lower()


def _split(value: Any) -> str:
    """Return a supported split token.

    Args:
        value: Candidate split value.

    Returns:
        Split token.

    Raises:
        PaddleOCRBenchmarkSplitError: If split is unsupported.
    """
    if value not in SPLITS:
        raise PaddleOCRBenchmarkSplitError("split is not supported.")
    return str(value)


def _sha256_text(value: str) -> str:
    """Return SHA-256 digest of text.

    Args:
        value: Input text.

    Returns:
        Hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return safe stdout summary.

    Args:
        summary: Full split assignment summary.

    Returns:
        Redacted CLI summary.
    """
    return {
        "schema_version": "paddleocr-benchmark-split-assignment-cli-v1",
        "status": summary.get("status", "error"),
        "row_count": summary.get("row_count", 0),
        "product_group_count": summary.get("product_group_count", 0),
        "split_counts": summary.get("split_counts", {}),
        "leakage_check_passed": summary.get("leakage_check_passed") is True,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
    }


def _error_summary(*, error: Exception, manifest_name: str) -> dict[str, Any]:
    """Return redacted failure summary.

    Args:
        error: Error that stopped split assignment.
        manifest_name: Input manifest basename.

    Returns:
        Redacted summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "benchmark_manifest_name": manifest_name,
        "status": "error",
        "error_type": type(error).__name__,
        "error_message": "PaddleOCR benchmark split assignment failed.",
        "row_count": 0,
        "product_group_count": 0,
        "split_counts": dict.fromkeys(SPLITS, 0),
        "leakage_check_passed": False,
        "db_write_performed": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw OCR, provider payloads, local paths, and secrets.

    Args:
        value: JSON-like payload.

    Raises:
        ValueError: If unsafe content is found.
    """
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if key_text in RAW_FORBIDDEN_KEYS:
                raise ValueError(key_text)
            _reject_unsafe_payload(child)
        return
    if isinstance(value, list | tuple):
        for child in value:
            _reject_unsafe_payload(child)
        return
    if isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in SECRET_LIKE_MARKERS):
            raise ValueError("secret-like marker")
        if any(marker in value for marker in LOCAL_PATH_MARKERS):
            raise ValueError("local path literal")


if __name__ == "__main__":
    raise SystemExit(run_cli())
