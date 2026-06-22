"""Gate supplement OCR benchmark and teacher OCR evaluation readiness.

This script reads only redacted summaries from upstream review gates. It never
reads source-image rows, manual ground-truth row payloads, OCR text, provider
payloads, LLM outputs, image bytes, or database records.

The gate separates three decisions:

* whether PII-cleared review images may become manual ground-truth templates,
* whether human-reviewed ground truth may become an OCR benchmark fixture set,
* whether external teacher OCR evaluation may run.

PaddleOCR training remains blocked here; it needs separate evaluation and
baseline-promotion gates before any model update is allowed.

References:
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://cloud.google.com/vision/docs/ocr
    https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
    https://docs.python.org/3/library/argparse.html
    https://docs.python.org/3/library/json.html
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import (  # noqa: E402
    assign_paddleocr_benchmark_splits as split_assignment,
)
from scripts import (  # noqa: E402
    build_supplement_ocr_benchmark_manifest as benchmark,
)
from scripts import (  # noqa: E402
    build_supplement_ocr_ground_truth_review_bundle as gt_bundle,
)
from scripts import preflight_supplement_ocr_ground_truth_manifest as gt_preflight  # noqa: E402
from scripts import (  # noqa: E402
    preflight_supplement_review_pii_screening_decisions as pii_preflight,
)

SCHEMA_VERSION = "supplement-ocr-benchmark-gate-v1"
PII_PREFLIGHT_SCHEMA = pii_preflight.SCHEMA_VERSION
GT_BUNDLE_SCHEMA = gt_bundle.SCHEMA_VERSION
GT_PREFLIGHT_SCHEMA = gt_preflight.SCHEMA_VERSION
BENCHMARK_SUMMARY_SCHEMA = benchmark.SCHEMA_VERSION
BENCHMARK_SPLIT_SUMMARY_SCHEMA = split_assignment.SCHEMA_VERSION
STATUS_READY = "ready_for_teacher_ocr_eval"
STATUS_BLOCKED_PII = "blocked_by_pii_screening"
STATUS_BLOCKED_NO_SAFE_ROWS = "blocked_by_no_teacher_safe_rows"
STATUS_BLOCKED_GT = "blocked_by_ground_truth_review"
STATUS_BLOCKED_BENCHMARK = "blocked_by_benchmark_manifest"
STATUS_BLOCKED_SPLIT = "blocked_by_benchmark_split_assignment"
STATUS_ERROR = "error"
REQUIRED_BENCHMARK_EXPECTED_SECTIONS = (
    "ingredient_amounts",
    "intake_method",
    "precautions",
    "allergen_warnings",
)
SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://cloud.google.com/vision/docs/ocr",
    "https://api.ncloud-docs.com/docs/en/ai-application-service-ocr",
    "https://docs.python.org/3/library/argparse.html",
    "https://docs.python.org/3/library/json.html",
)
NEXT_STEPS_BY_STATUS = {
    STATUS_BLOCKED_PII: (
        "complete_review_image_pii_screening",
        "rerun_pii_screening_decision_preflight_require_all_reviewed",
        "rerun_ocr_benchmark_gate",
    ),
    STATUS_BLOCKED_NO_SAFE_ROWS: (
        "confirm_no_review_images_are_teacher_ocr_safe",
        "collect_additional_review_images_or_adjust_pii_decisions",
        "rerun_ocr_benchmark_gate",
    ),
    STATUS_BLOCKED_GT: (
        "export_ocr_ground_truth_template",
        "complete_manual_ground_truth_review",
        "build_ocr_ground_truth_review_bundle_summary",
        "run_ocr_ground_truth_preflight_require_all_sections",
        "rerun_ocr_benchmark_gate",
    ),
    STATUS_BLOCKED_BENCHMARK: (
        "build_ocr_benchmark_manifest_from_human_reviewed_ground_truth_with_full_required_sections",
        "rerun_ocr_benchmark_gate",
    ),
    STATUS_BLOCKED_SPLIT: (
        "assign_product_group_safe_benchmark_splits",
        "verify_split_leakage_check_passed",
        "rerun_ocr_benchmark_gate",
    ),
    STATUS_READY: (
        "run_clova_google_vision_paddleocr_eval_on_benchmark_manifest",
        "build_paddleocr_improvement_candidates_from_eval",
        "keep_paddleocr_training_blocked_until_baseline_gate_passes",
    ),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pii-preflight", "--pii-decision-preflight", type=Path, required=True)
    parser.add_argument("--ground-truth-bundle-summary", type=Path, default=None)
    parser.add_argument("--ground-truth-preflight", type=Path, default=None)
    parser.add_argument("--benchmark-summary", type=Path, default=None)
    parser.add_argument("--benchmark-split-summary", type=Path, default=None)
    parser.add_argument(
        "--required-expected-section",
        action="append",
        choices=sorted(benchmark.ALLOWED_REQUIRED_EXPECTED_SECTIONS),
        default=None,
        help=(
            "Override the full-card required expected-section policy checked "
            "against the benchmark summary. Repeatable. Defaults to the four "
            "result-card sections (ingredient_amounts, intake_method, "
            "precautions, allergen_warnings)."
        ),
    )
    parser.add_argument(
        "--require-ready-for-teacher-ocr-eval",
        action="store_true",
        help=(
            "Exit non-zero after writing the redacted summary unless the gate "
            "is ready for teacher OCR evaluation."
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Write OCR benchmark gate JSON and optional Markdown.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    output_path = args.output.expanduser().resolve()
    markdown_output = (
        args.markdown_output.expanduser().resolve() if args.markdown_output is not None else None
    )
    try:
        summary = build_ocr_benchmark_gate(
            pii_preflight_path=args.pii_preflight.expanduser().resolve(),
            ground_truth_bundle_summary_path=(
                args.ground_truth_bundle_summary.expanduser().resolve()
                if args.ground_truth_bundle_summary is not None
                else None
            ),
            ground_truth_preflight_path=(
                args.ground_truth_preflight.expanduser().resolve()
                if args.ground_truth_preflight is not None
                else None
            ),
            benchmark_summary_path=(
                args.benchmark_summary.expanduser().resolve()
                if args.benchmark_summary is not None
                else None
            ),
            benchmark_split_summary_path=(
                args.benchmark_split_summary.expanduser().resolve()
                if args.benchmark_split_summary is not None
                else None
            ),
            required_expected_sections=(
                tuple(args.required_expected_section)
                if args.required_expected_section
                else REQUIRED_BENCHMARK_EXPECTED_SECTIONS
            ),
        )
        _write_json(output_path, summary)
        if markdown_output is not None:
            markdown_output.parent.mkdir(parents=True, exist_ok=True)
            markdown_output.write_text(build_markdown(summary), encoding="utf-8")
        print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
        if args.require_ready_for_teacher_ocr_eval and summary.get("status") != STATUS_READY:
            raise SystemExit(1)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(output_path=output_path, error=exc)
        _write_json(output_path, failure)
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise SystemExit(1) from None


def build_ocr_benchmark_gate(
    *,
    pii_preflight_path: Path,
    ground_truth_bundle_summary_path: Path | None = None,
    ground_truth_preflight_path: Path | None = None,
    benchmark_summary_path: Path | None = None,
    benchmark_split_summary_path: Path | None = None,
    required_expected_sections: tuple[str, ...] = REQUIRED_BENCHMARK_EXPECTED_SECTIONS,
) -> dict[str, Any]:
    """Build a redacted OCR benchmark readiness summary.

    Args:
        pii_preflight_path: Strict PII decision preflight JSON.
        ground_truth_bundle_summary_path: Optional OCR GT review bundle summary.
        ground_truth_preflight_path: Optional operator-edited OCR GT preflight summary.
        benchmark_summary_path: Optional OCR benchmark manifest summary.
        benchmark_split_summary_path: Optional product-group-safe split summary.
        required_expected_sections: Expected-section policy the benchmark summary
            must declare. Defaults to the four result-card sections.

    Returns:
        Redacted gate summary.

    Raises:
        ValueError: If an input summary is unsafe or unsupported.
    """
    pii_summary = _load_summary(pii_preflight_path, expected_schema=PII_PREFLIGHT_SCHEMA)
    pii_counts = _pii_counts(pii_summary)
    pii_strict_clear = _pii_strict_clear(pii_summary, counts=pii_counts)
    has_teacher_safe_rows = pii_counts["cleared_no_personal_data_count"] > 0

    gt_summary = (
        _load_summary(ground_truth_bundle_summary_path, expected_schema=GT_BUNDLE_SCHEMA)
        if ground_truth_bundle_summary_path is not None
        else None
    )
    gt_counts = _gt_counts(gt_summary)
    gt_review_ready = (
        gt_summary is not None
        and gt_counts["ready_for_benchmark_rows"] > 0
        and gt_counts["ready_for_benchmark_rows"] == gt_counts["ground_truth_template_row_count"]
    )
    gt_preflight_summary = (
        _load_summary(ground_truth_preflight_path, expected_schema=GT_PREFLIGHT_SCHEMA)
        if ground_truth_preflight_path is not None
        else None
    )
    gt_preflight_counts = _gt_preflight_counts(gt_preflight_summary)
    gt_preflight_ready = (
        gt_preflight_summary is not None
        and gt_preflight_summary.get("ready_for_benchmark_build") is True
        and gt_preflight_counts["ground_truth_preflight_benchmark_ready_row_count"] > 0
    )

    benchmark_summary = (
        _load_summary(benchmark_summary_path, expected_schema=BENCHMARK_SUMMARY_SCHEMA)
        if benchmark_summary_path is not None
        else None
    )
    benchmark_counts = _benchmark_counts(benchmark_summary)
    benchmark_required_sections = _benchmark_required_sections(benchmark_summary)
    missing_benchmark_required_sections = _missing_benchmark_required_sections(
        benchmark_required_sections, policy=required_expected_sections
    )
    benchmark_required_sections_ready = (
        benchmark_summary is not None and not missing_benchmark_required_sections
    )
    benchmark_ready = (
        benchmark_summary is not None
        and benchmark_counts["benchmark_fixture_count"] > 0
        and benchmark_counts["scoreable_fixture_count"]
        == benchmark_counts["benchmark_fixture_count"]
        and benchmark_required_sections_ready
    )
    split_summary = (
        _load_summary(benchmark_split_summary_path, expected_schema=BENCHMARK_SPLIT_SUMMARY_SCHEMA)
        if benchmark_split_summary_path is not None
        else None
    )
    split_counts = _split_assignment_counts(split_summary)
    split_ready = _split_assignment_ready(
        split_summary=split_summary,
        split_counts=split_counts,
        benchmark_counts=benchmark_counts,
    )

    if not pii_strict_clear:
        status = STATUS_BLOCKED_PII
    elif not has_teacher_safe_rows:
        status = STATUS_BLOCKED_NO_SAFE_ROWS
    elif not gt_review_ready or not gt_preflight_ready:
        status = STATUS_BLOCKED_GT
    elif not benchmark_ready:
        status = STATUS_BLOCKED_BENCHMARK
    elif not split_ready:
        status = STATUS_BLOCKED_SPLIT
    else:
        status = STATUS_READY

    external_teacher_eval_allowed = status == STATUS_READY
    strict_pii_review_requested = pii_summary.get("require_all_reviewed") is True
    pii_ready_for_strict_apply = pii_summary.get("ready_for_strict_apply") is True
    pii_ready_for_requested_apply = pii_summary.get("ready_for_requested_apply") is True
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "pii_preflight_name": pii_preflight_path.name,
        "pii_preflight_sha256": _sha256_file(pii_preflight_path),
        "ground_truth_bundle_summary_name": (
            ground_truth_bundle_summary_path.name
            if ground_truth_bundle_summary_path is not None
            else None
        ),
        "ground_truth_bundle_summary_sha256": (
            _sha256_file(ground_truth_bundle_summary_path)
            if ground_truth_bundle_summary_path is not None
            else None
        ),
        "ground_truth_preflight_name": (
            ground_truth_preflight_path.name if ground_truth_preflight_path is not None else None
        ),
        "ground_truth_preflight_sha256": (
            _sha256_file(ground_truth_preflight_path)
            if ground_truth_preflight_path is not None
            else None
        ),
        "benchmark_summary_name": benchmark_summary_path.name if benchmark_summary_path else None,
        "benchmark_summary_sha256": (
            _sha256_file(benchmark_summary_path) if benchmark_summary_path else None
        ),
        "benchmark_split_summary_name": (
            benchmark_split_summary_path.name if benchmark_split_summary_path else None
        ),
        "benchmark_split_summary_sha256": (
            _sha256_file(benchmark_split_summary_path) if benchmark_split_summary_path else None
        ),
        **pii_counts,
        **gt_counts,
        **gt_preflight_counts,
        **benchmark_counts,
        **split_counts,
        "benchmark_required_expected_sections": list(benchmark_required_sections),
        "benchmark_required_expected_section_policy": list(required_expected_sections),
        "benchmark_missing_required_expected_sections": list(missing_benchmark_required_sections),
        "strict_pii_review_requested": strict_pii_review_requested,
        "pii_ready_for_strict_apply": pii_ready_for_strict_apply,
        "pii_ready_for_requested_apply": pii_ready_for_requested_apply,
        "pii_strict_clear": pii_strict_clear,
        "has_teacher_safe_rows": has_teacher_safe_rows,
        "ground_truth_template_allowed": pii_strict_clear and has_teacher_safe_rows,
        "ground_truth_review_ready": gt_review_ready,
        "ground_truth_preflight_ready": gt_preflight_ready,
        "benchmark_manifest_ready": benchmark_ready,
        "benchmark_required_sections_ready": benchmark_required_sections_ready,
        "benchmark_split_ready": split_ready,
        "teacher_ocr_benchmark_allowed": external_teacher_eval_allowed,
        "external_teacher_ocr_allowed_now": external_teacher_eval_allowed,
        "external_teacher_ocr_eval_allowed": external_teacher_eval_allowed,
        "paddleocr_training_allowed_now": False,
        "paddleocr_training_allowed_after_eval_gate": False,
        "paddleocr_training_gate_required": True,
        "next_steps": list(NEXT_STEPS_BY_STATUS[status]),
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_payload(summary)
    return summary


def build_markdown(summary: Mapping[str, Any]) -> str:
    """Build a redacted Markdown gate report.

    Args:
        summary: Gate summary.

    Returns:
        Markdown report.
    """
    _reject_unsafe_payload(summary)
    next_steps = "\n".join(f"- `{_safe_token(str(step))}`" for step in summary["next_steps"])
    markdown = "\n".join(
        [
            "# Supplement OCR Benchmark Gate",
            "",
            f"Schema: `{SCHEMA_VERSION}`",
            "",
            "## Status",
            "",
            f"- Status: `{_safe_token(str(summary['status']))}`",
            f"- Ground-truth template allowed: `{_bool_text(summary['ground_truth_template_allowed'])}`",
            f"- Teacher OCR benchmark allowed: `{_bool_text(summary['teacher_ocr_benchmark_allowed'])}`",
            f"- External teacher OCR eval allowed: `{_bool_text(summary['external_teacher_ocr_eval_allowed'])}`",
            f"- PaddleOCR training allowed now: `{_bool_text(summary['paddleocr_training_allowed_now'])}`",
            "",
            "## Counts",
            "",
            f"- Candidate rows: `{_non_negative_int(summary['candidate_row_count'])}`",
            f"- Cleared no personal data: `{_non_negative_int(summary['cleared_no_personal_data_count'])}`",
            f"- Blank PII decisions: `{_non_negative_int(summary['pii_blank_decision_count'])}`",
            f"- Pending PII actions: `{_non_negative_int(summary['pii_pending_operator_action_count'])}`",
            f"- Ground-truth rows: `{_non_negative_int(summary['ground_truth_template_row_count'])}`",
            f"- Ready benchmark rows: `{_non_negative_int(summary['ready_for_benchmark_rows'])}`",
            f"- Ground-truth preflight ready: `{_bool_text(summary['ground_truth_preflight_ready'])}`",
            f"- Ground-truth preflight benchmark-ready rows: `{_non_negative_int(summary['ground_truth_preflight_benchmark_ready_row_count'])}`",
            f"- Benchmark fixtures: `{_non_negative_int(summary['benchmark_fixture_count'])}`",
            f"- Scoreable fixtures: `{_non_negative_int(summary['scoreable_fixture_count'])}`",
            f"- Benchmark required sections ready: `{_bool_text(summary['benchmark_required_sections_ready'])}`",
            f"- Split rows: `{_non_negative_int(summary['benchmark_split_row_count'])}`",
            f"- Holdout fixtures: `{_non_negative_int(summary['benchmark_holdout_fixture_count'])}`",
            f"- Test fixtures: `{_non_negative_int(summary['benchmark_test_fixture_count'])}`",
            f"- Split leakage passed: `{_bool_text(summary['benchmark_split_leakage_check_passed'])}`",
            "",
            "## Next Steps",
            "",
            next_steps,
            "",
            "## Rule",
            "",
            "CLOVA/Google Vision teacher OCR 평가는 PII strict preflight, human-reviewed GT, benchmark fixture 생성, product-group-safe split leakage check가 모두 통과한 뒤에만 허용합니다. PaddleOCR 학습은 별도 baseline gate 전까지 계속 차단합니다.",
            "",
        ]
    )
    _reject_unsafe_payload(markdown)
    return markdown


def _load_summary(path: Path | None, *, expected_schema: str) -> dict[str, Any]:
    """Load and validate one redacted summary object.

    Args:
        path: Summary path.
        expected_schema: Required schema version.

    Returns:
        Parsed summary object.
    """
    if path is None or not path.is_file():
        raise ValueError("Required OCR benchmark gate summary is missing.")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("OCR benchmark gate input must be a JSON object.")
    _reject_unsafe_payload(parsed)
    if parsed.get("schema_version") != expected_schema:
        raise ValueError("OCR benchmark gate input schema is unsupported.")
    return parsed


def _pii_counts(payload: Mapping[str, Any]) -> dict[str, int]:
    """Return normalized PII decision counts.

    Args:
        payload: PII preflight summary.

    Returns:
        Count mapping.
    """
    return {
        "candidate_row_count": _non_negative_int(payload.get("candidate_row_count")),
        "pii_decision_row_count": _non_negative_int(payload.get("decision_row_count")),
        "valid_pii_decision_count": _non_negative_int(payload.get("valid_decision_count")),
        "cleared_no_personal_data_count": _non_negative_int(
            payload.get("cleared_no_personal_data_count")
        ),
        "blocked_pii_decision_count": _non_negative_int(payload.get("blocked_decision_count")),
        "pii_blank_decision_count": _non_negative_int(payload.get("blank_decision_count")),
        "pii_invalid_decision_count": _non_negative_int(payload.get("invalid_decision_count")),
        "pii_unmatched_decision_count": _non_negative_int(payload.get("unmatched_decision_count")),
        "pii_missing_decision_count": _non_negative_int(payload.get("missing_decision_count")),
        "pii_pending_operator_action_count": _non_negative_int(
            payload.get("pending_operator_action_count")
        ),
    }


def _pii_strict_clear(payload: Mapping[str, Any], *, counts: Mapping[str, int]) -> bool:
    """Return whether PII preflight has strictly completed.

    Args:
        payload: PII preflight summary.
        counts: Normalized PII counts.

    Returns:
        True when strict PII review has no pending or invalid work.
    """
    return (
        payload.get("require_all_reviewed") is True
        and payload.get("ready_for_strict_apply") is True
        and payload.get("ready_for_requested_apply") is True
        and counts["pii_blank_decision_count"] == 0
        and counts["pii_invalid_decision_count"] == 0
        and counts["pii_unmatched_decision_count"] == 0
        and counts["pii_missing_decision_count"] == 0
        and counts["pii_pending_operator_action_count"] == 0
    )


def _gt_counts(payload: Mapping[str, Any] | None) -> dict[str, int]:
    """Return normalized ground-truth review counts.

    Args:
        payload: Optional GT review bundle summary.

    Returns:
        Count mapping.
    """
    if payload is None:
        return {
            "ground_truth_template_row_count": 0,
            "ground_truth_reviewable_row_count": 0,
            "ready_for_benchmark_rows": 0,
            "manual_ground_truth_review_required_count": 0,
        }
    return {
        "ground_truth_template_row_count": _non_negative_int(
            payload.get("ground_truth_template_row_count")
        ),
        "ground_truth_reviewable_row_count": _non_negative_int(payload.get("reviewable_row_count")),
        "ready_for_benchmark_rows": _non_negative_int(payload.get("ready_for_benchmark_rows")),
        "manual_ground_truth_review_required_count": _non_negative_int(
            payload.get("manual_review_required_count")
        ),
    }


def _gt_preflight_counts(payload: Mapping[str, Any] | None) -> dict[str, int]:
    """Return normalized manual OCR ground-truth preflight counts.

    Args:
        payload: Optional ground-truth preflight summary.

    Returns:
        Count mapping.
    """
    if payload is None:
        return {
            "ground_truth_preflight_row_count": 0,
            "ground_truth_preflight_human_reviewed_row_count": 0,
            "ground_truth_preflight_explicit_ready_flag_count": 0,
            "ground_truth_preflight_benchmark_ready_row_count": 0,
        }
    return {
        "ground_truth_preflight_row_count": _non_negative_int(payload.get("row_count")),
        "ground_truth_preflight_human_reviewed_row_count": _non_negative_int(
            payload.get("human_reviewed_row_count")
        ),
        "ground_truth_preflight_explicit_ready_flag_count": _non_negative_int(
            payload.get("explicit_ready_flag_count")
        ),
        "ground_truth_preflight_benchmark_ready_row_count": _non_negative_int(
            payload.get("benchmark_ready_row_count")
        ),
    }


def _benchmark_counts(payload: Mapping[str, Any] | None) -> dict[str, int]:
    """Return normalized OCR benchmark counts.

    Args:
        payload: Optional benchmark manifest summary.

    Returns:
        Count mapping.
    """
    if payload is None:
        return {"benchmark_fixture_count": 0, "scoreable_fixture_count": 0}
    return {
        "benchmark_fixture_count": _non_negative_int(payload.get("benchmark_fixture_count")),
        "scoreable_fixture_count": _non_negative_int(payload.get("scoreable_fixture_count")),
    }


def _benchmark_required_sections(payload: Mapping[str, Any] | None) -> tuple[str, ...]:
    """Return benchmark expected sections declared by the manifest builder.

    Args:
        payload: Optional benchmark manifest summary.

    Returns:
        Deduplicated required expected sections. Missing summaries return an
        empty tuple, so the caller can keep the benchmark blocked.

    Raises:
        ValueError: If the benchmark summary declares an unsupported section.
    """
    if payload is None:
        return ()
    value = payload.get("required_expected_sections")
    if not isinstance(value, list):
        return ()
    sections: list[str] = []
    for item in value:
        if not isinstance(item, str) or item not in benchmark.ALLOWED_REQUIRED_EXPECTED_SECTIONS:
            raise ValueError("Benchmark summary includes unsupported required expected section.")
        if item not in sections:
            sections.append(item)
    return tuple(sections)


def _missing_benchmark_required_sections(
    required_sections: tuple[str, ...],
    *,
    policy: tuple[str, ...] = REQUIRED_BENCHMARK_EXPECTED_SECTIONS,
) -> tuple[str, ...]:
    """Return policy expected sections missing from a benchmark summary.

    Args:
        required_sections: Expected sections declared by the benchmark summary.
        policy: Expected-section policy that must be covered before teacher OCR
            eval can run for the user-facing supplement result-card objective.

    Returns:
        Policy section names that the benchmark summary does not declare.
    """
    required_set = set(required_sections)
    return tuple(section for section in policy if section not in required_set)


def _split_assignment_counts(payload: Mapping[str, Any] | None) -> dict[str, int | bool]:
    """Return normalized product-group split assignment counts.

    Args:
        payload: Optional benchmark split assignment summary.

    Returns:
        Redacted split count and leakage fields.
    """
    if payload is None:
        return {
            "benchmark_split_row_count": 0,
            "benchmark_split_product_group_count": 0,
            "benchmark_train_fixture_count": 0,
            "benchmark_holdout_fixture_count": 0,
            "benchmark_test_fixture_count": 0,
            "benchmark_split_leakage_check_passed": False,
        }
    split_counts = payload.get("split_counts")
    if not isinstance(split_counts, Mapping):
        raise ValueError("Benchmark split summary must include split_counts.")
    return {
        "benchmark_split_row_count": _non_negative_int(payload.get("row_count")),
        "benchmark_split_product_group_count": _non_negative_int(
            payload.get("product_group_count")
        ),
        "benchmark_train_fixture_count": _non_negative_int(split_counts.get("train", 0)),
        "benchmark_holdout_fixture_count": _non_negative_int(split_counts.get("holdout", 0)),
        "benchmark_test_fixture_count": _non_negative_int(split_counts.get("test", 0)),
        "benchmark_split_leakage_check_passed": payload.get("leakage_check_passed") is True,
    }


def _split_assignment_ready(
    *,
    split_summary: Mapping[str, Any] | None,
    split_counts: Mapping[str, int | bool],
    benchmark_counts: Mapping[str, int],
) -> bool:
    """Return whether split assignment can support teacher OCR eval.

    Args:
        split_summary: Optional split assignment summary.
        split_counts: Normalized split counts.
        benchmark_counts: Normalized benchmark counts.

    Returns:
        True when split assignment exists, covers benchmark rows, has a held-out
        split, and passed product-group leakage checks.
    """
    return (
        split_summary is not None
        and split_summary.get("ready_for_holdout_eval") is True
        and split_counts["benchmark_split_leakage_check_passed"] is True
        and split_counts["benchmark_split_row_count"] == benchmark_counts["benchmark_fixture_count"]
        and split_counts["benchmark_holdout_fixture_count"] > 0
    )


def _non_negative_int(value: Any) -> int:
    """Return a non-negative integer.

    Args:
        value: Candidate value.

    Returns:
        Non-negative integer.

    Raises:
        ValueError: If value is not a non-negative integer.
    """
    if not isinstance(value, int) or value < 0:
        raise ValueError("Expected a non-negative integer.")
    return value


def _safe_token(value: str) -> str:
    """Return a safe non-path token.

    Args:
        value: Candidate token.

    Returns:
        Safe token.
    """
    return benchmark._safe_required_token(value, field_name="token")


def _bool_text(value: object) -> str:
    """Return a lowercase boolean string.

    Args:
        value: Candidate boolean.

    Returns:
        ``true`` or ``false``.
    """
    return "true" if value is True else "false"


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw OCR/provider payloads and local path literals.

    Args:
        value: Candidate JSON-like payload.
    """
    benchmark._reject_unsafe_payload(value)


def _sha256_file(path: Path) -> str:
    """Return SHA-256 digest for a file.

    Args:
        path: File path.

    Returns:
        Hex digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write one JSON object.

    Args:
        path: Destination path.
        payload: JSON payload.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact CLI-safe summary.

    Args:
        summary: Gate summary.

    Returns:
        CLI summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": summary["status"],
        "candidate_row_count": summary["candidate_row_count"],
        "cleared_no_personal_data_count": summary["cleared_no_personal_data_count"],
        "pii_blank_decision_count": summary["pii_blank_decision_count"],
        "ready_for_benchmark_rows": summary["ready_for_benchmark_rows"],
        "benchmark_fixture_count": summary["benchmark_fixture_count"],
        "benchmark_required_sections_ready": summary["benchmark_required_sections_ready"],
        "benchmark_split_ready": summary["benchmark_split_ready"],
        "benchmark_split_leakage_check_passed": summary["benchmark_split_leakage_check_passed"],
        "ground_truth_template_allowed": summary["ground_truth_template_allowed"],
        "teacher_ocr_benchmark_allowed": summary["teacher_ocr_benchmark_allowed"],
        "external_teacher_ocr_eval_allowed": summary["external_teacher_ocr_eval_allowed"],
        "paddleocr_training_allowed_now": False,
    }


def _failure_summary(*, output_path: Path, error: Exception) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        output_path: Planned output path.
        error: Raised exception.

    Returns:
        Redacted failure summary.
    """
    _ = error
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS_ERROR,
        "generated_at": datetime.now(UTC).isoformat(),
        "output_name": output_path.name,
        "ground_truth_template_allowed": False,
        "external_teacher_ocr_eval_allowed": False,
        "paddleocr_training_allowed_now": False,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "llm_call_performed": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "product_dir_literals_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


if __name__ == "__main__":
    main()
