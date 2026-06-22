"""Tests for PaddleOCR benchmark split assignment."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

splitter = importlib.import_module("scripts.assign_paddleocr_benchmark_splits")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    """Write JSONL rows.

    Args:
        path: Destination path.
        rows: JSON rows.

    Returns:
        Written path.
    """
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _sha(index: int) -> str:
    """Return a deterministic SHA-like fixture hash.

    Args:
        index: Numeric fixture index.

    Returns:
        SHA-256 hex string.
    """
    return f"{index:064x}"


def _benchmark_row(*, fixture_id: str, product_hash: str, image_hash: str) -> dict[str, Any]:
    """Build one redacted benchmark fixture row.

    Args:
        fixture_id: Fixture id.
        product_hash: Product group hash.
        image_hash: Image hash.

    Returns:
        Benchmark row.
    """
    return {
        "schema_version": "supplement-ocr-provider-benchmark-fixture-v1",
        "fixture_id": fixture_id,
        "source_ref": f"review:{image_hash[:32]}",
        "image_ref_hash": image_hash,
        "image_sha256": image_hash,
        "product_dir_hash": product_hash,
        "category_key": "omega3",
        "source_kind": "review",
        "expected": {
            "verification_status": "human_reviewed",
            "ingredients": [{"display_name": "EPA", "amount": 180, "unit": "mg"}],
        },
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
    }


def test_assign_splits_keeps_same_product_group_in_one_split(tmp_path: Path) -> None:
    """Verify product-level grouping prevents train/eval leakage."""
    repeated_product_hash = _sha(10)
    rows = [
        _benchmark_row(
            fixture_id="fixture-a", product_hash=repeated_product_hash, image_hash=_sha(1)
        ),
        _benchmark_row(
            fixture_id="fixture-b", product_hash=repeated_product_hash, image_hash=_sha(2)
        ),
    ]
    rows.extend(
        _benchmark_row(
            fixture_id=f"fixture-{index}",
            product_hash=_sha(100 + index),
            image_hash=_sha(200 + index),
        )
        for index in range(20)
    )
    manifest = _write_jsonl(tmp_path / "benchmark.jsonl", rows)

    assigned, summary = splitter.assign_paddleocr_benchmark_splits(
        benchmark_manifest=manifest,
        holdout_ratio=0.25,
        test_ratio=0.25,
        min_holdout_fixtures=1,
        min_test_fixtures=1,
    )

    repeated_splits = {
        row["split"] for row in assigned if row["product_dir_hash"] == repeated_product_hash
    }
    assert len(repeated_splits) == 1
    assert summary["leakage_check_passed"] is True
    assert summary["checks"]["all_groups_in_single_split"] is True
    assert sum(summary["split_counts"].values()) == len(rows)
    assert all(row["leakage_check_passed"] is True for row in assigned)


def test_assign_splits_is_deterministic_for_same_seed(tmp_path: Path) -> None:
    """Verify repeated runs with the same seed produce stable splits."""
    rows = [
        _benchmark_row(
            fixture_id=f"fixture-{index}",
            product_hash=_sha(index),
            image_hash=_sha(100 + index),
        )
        for index in range(12)
    ]
    manifest = _write_jsonl(tmp_path / "benchmark.jsonl", rows)

    first, first_summary = splitter.assign_paddleocr_benchmark_splits(
        benchmark_manifest=manifest,
        seed="stable-seed",
        min_holdout_fixtures=1,
    )
    second, second_summary = splitter.assign_paddleocr_benchmark_splits(
        benchmark_manifest=manifest,
        seed="stable-seed",
        min_holdout_fixtures=1,
    )

    assert [(row["fixture_id"], row["split"]) for row in first] == [
        (row["fixture_id"], row["split"]) for row in second
    ]
    assert (
        first_summary["split_assignment_seed_hash"] == second_summary["split_assignment_seed_hash"]
    )


def test_assign_splits_rejects_rows_without_product_hash(tmp_path: Path) -> None:
    """Verify missing product group hash fails before split assignment."""
    row = _benchmark_row(fixture_id="fixture-1", product_hash=_sha(1), image_hash=_sha(2))
    row.pop("product_dir_hash")
    manifest = _write_jsonl(tmp_path / "benchmark.jsonl", [row])

    with pytest.raises(splitter.PaddleOCRBenchmarkSplitError, match="product_dir_hash"):
        splitter.assign_paddleocr_benchmark_splits(benchmark_manifest=manifest)


def test_assign_splits_rejects_candidate_manifest_schema(tmp_path: Path) -> None:
    """Verify raw candidate manifests cannot be split as scoreable benchmark rows."""
    manifest = _write_jsonl(
        tmp_path / "candidate.jsonl",
        [
            {
                "schema_version": "supplement-review-ocr-ground-truth-candidate-v1",
                "fixture_id": "candidate-1",
                "product_dir_hash": _sha(1),
                "raw_ocr_text_stored": False,
                "raw_provider_payload_stored": False,
            }
        ],
    )

    with pytest.raises(splitter.PaddleOCRBenchmarkSplitError, match="schema"):
        splitter.assign_paddleocr_benchmark_splits(benchmark_manifest=manifest)


def test_assign_splits_output_omits_paths_product_literals_and_raw_payloads(
    tmp_path: Path,
) -> None:
    """Verify split artifacts remain operator-safe and redacted."""
    rows = [
        _benchmark_row(
            fixture_id=f"fixture-{index}",
            product_hash=_sha(index),
            image_hash=_sha(100 + index),
        )
        for index in range(10)
    ]
    manifest = _write_jsonl(tmp_path / "benchmark.jsonl", rows)

    assigned, summary = splitter.assign_paddleocr_benchmark_splits(
        benchmark_manifest=manifest,
        min_holdout_fixtures=1,
    )
    dumped = json.dumps({"assigned": assigned, "summary": summary}, ensure_ascii=False)

    assert "나우푸드 오메가3_123456" not in dumped
    assert str(tmp_path) not in dumped
    assert "/Volumes/" not in dumped
    assert '"raw_ocr_text":' not in dumped
    assert '"provider_payload":' not in dumped
    assert summary["raw_ocr_text_stored"] is False
    assert summary["raw_provider_payload_stored"] is False
    assert summary["absolute_paths_stored"] is False


def test_cli_writes_split_rows_and_redacted_summary(tmp_path: Path, capsys: Any) -> None:
    """Verify CLI writes JSONL rows and prints only safe aggregate status."""
    rows = [
        _benchmark_row(
            fixture_id=f"fixture-{index}",
            product_hash=_sha(index),
            image_hash=_sha(100 + index),
        )
        for index in range(12)
    ]
    manifest = _write_jsonl(tmp_path / "benchmark.jsonl", rows)
    output = tmp_path / "split.jsonl"
    summary_output = tmp_path / "summary.json"

    exit_code = splitter.run_cli(
        [
            "--benchmark-manifest",
            str(manifest),
            "--output",
            str(output),
            "--summary",
            str(summary_output),
            "--min-holdout-fixtures",
            "1",
        ]
    )

    stdout = capsys.readouterr().out
    written_rows = [
        json.loads(line) for line in output.read_text(encoding="utf-8").splitlines() if line
    ]
    written_summary = json.loads(summary_output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert len(written_rows) == len(rows)
    assert written_summary["leakage_check_passed"] is True
    assert str(tmp_path) not in stdout
    assert "raw text must stay private" not in stdout
