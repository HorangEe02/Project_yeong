"""Export MEDICAL-WIKI eval inputs as raw-free LangSmith-compatible JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = BACKEND_ROOT.parents[1]

DEFAULT_CLAIM_EVAL_INPUTS = (
    WORKSPACE_ROOT / "MEDICAL-WIKI" / "manifest" / "chatbot_answer_eval_inputs.jsonl"
)
DEFAULT_EVIDENCE_BUNDLE_FIXTURES = (
    WORKSPACE_ROOT / "MEDICAL-WIKI" / "manifest" / "evidence_bundle_adapter_fixtures.jsonl"
)
DEFAULT_OUT = WORKSPACE_ROOT / "MEDICAL-WIKI" / "manifest" / "langsmith_eval_export.jsonl"

FORBIDDEN_EXPORT_MARKERS = (
    "raw prompt",
    "raw_prompt",
    "raw llm response",
    "raw_llm_response",
    "raw ocr",
    "raw_ocr",
    "raw_ocr_text",
    "provider payload",
    "provider_payload",
    "debug trace",
    "debug_trace",
    "user health",
    "user_health",
    "user_health_context",
    "user context",
    "user_context",
    "raw question",
    "raw_question",
    "raw_user_question",
    "query",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kind",
        choices=("claims", "evidence-bundles"),
        default="claims",
        help="Which MEDICAL-WIKI eval source to export.",
    )
    parser.add_argument("--claims", type=Path, default=DEFAULT_CLAIM_EVAL_INPUTS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_EVIDENCE_BUNDLE_FIXTURES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no} is not a JSON object")
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def build_claim_eval_dataset(path: Path) -> list[dict[str, Any]]:
    return [_claim_eval_row(row) for row in read_jsonl(path)]


def build_evidence_bundle_dataset(path: Path) -> list[dict[str, Any]]:
    return [_evidence_bundle_row(row) for row in read_jsonl(path)]


def evaluate_export_rows(rows: list[dict[str, Any]]) -> dict[str, object]:
    hits = _forbidden_marker_hits(rows)
    raw_fields_stored = any(bool(row.get("metadata", {}).get("raw_fields_stored")) for row in rows)
    upload_allowed_count = sum(
        1 for row in rows if bool(row.get("metadata", {}).get("upload_allowed"))
    )
    missing_required_ids = sum(1 for row in rows if _row_missing_required_ids(row))
    return {
        "status": (
            "pass"
            if not hits
            and not raw_fields_stored
            and upload_allowed_count == 0
            and missing_required_ids == 0
            else "fail"
        ),
        "row_count": len(rows),
        "forbidden_marker_hits": len(hits),
        "raw_fields_stored": raw_fields_stored,
        "upload_allowed_count": upload_allowed_count,
        "missing_required_ids": missing_required_ids,
    }


def _claim_eval_row(row: dict[str, Any]) -> dict[str, Any]:
    case_id = str(row.get("test_id", ""))
    expected_claim_id = str(row.get("must_retrieve_claim_id", ""))
    source_ids = [str(source_id) for source_id in row.get("source_ids", [])]
    must_not_do = [str(item) for item in row.get("must_not_do", [])]
    return {
        "dataset": "medical_wiki_claim_boundary_eval",
        "example_id": case_id,
        "inputs": {
            "case_id": case_id,
            "expected_claim_id": expected_claim_id,
        },
        "reference_outputs": {
            "answerability": str(row.get("expected_answerability", "")),
            "claim_ids": [expected_claim_id] if expected_claim_id else [],
            "source_ids": source_ids,
            "must_not_do": must_not_do,
        },
        "metadata": {
            "upload_allowed": False,
            "raw_fields_stored": False,
            "phi_free_review_required": True,
            "cloud_or_self_hosted_gate_required": True,
        },
    }


def _evidence_bundle_row(row: dict[str, Any]) -> dict[str, Any]:
    adapter_input = row.get("adapter_input", {})
    expected_contract = row.get("expected_adapter_contract", {})
    if not isinstance(adapter_input, dict) or not isinstance(expected_contract, dict):
        raise ValueError("EvidenceBundle fixture row is missing adapter contract")
    case_id = str(row.get("fixture_id", ""))
    source_ids = [
        str(source_id) for source_id in expected_contract.get("source_ids_must_be_preserved", [])
    ]
    return {
        "dataset": "medical_wiki_evidence_bundle_eval",
        "example_id": case_id,
        "inputs": {
            "case_id": case_id,
            "expected_renderer_route": str(row.get("expected_renderer_route", "")),
        },
        "reference_outputs": {
            "source_ids": source_ids,
            "claim_ids": [str(adapter_input.get("safety_anchor", {}).get("claim_id", ""))],
            "safety_anchor_claim_id": str(
                adapter_input.get("safety_anchor", {}).get("claim_id", "")
            ),
            "blocked_actions": [str(item) for item in adapter_input.get("blocked_actions", [])],
        },
        "metadata": {
            "upload_allowed": False,
            "raw_fields_stored": False,
            "phi_free_review_required": True,
            "cloud_or_self_hosted_gate_required": True,
        },
    }


def _forbidden_marker_hits(rows: list[dict[str, Any]]) -> list[str]:
    serialized = json.dumps(rows, ensure_ascii=False).casefold()
    return [marker for marker in FORBIDDEN_EXPORT_MARKERS if marker in serialized]


def _row_missing_required_ids(row: dict[str, Any]) -> bool:
    if not str(row.get("example_id", "")).strip():
        return True

    reference_outputs = row.get("reference_outputs")
    if not isinstance(reference_outputs, dict):
        return True

    claim_ids = reference_outputs.get("claim_ids")
    source_ids = reference_outputs.get("source_ids")
    return not _has_non_empty_id(claim_ids) or not _has_non_empty_id(source_ids)


def _has_non_empty_id(value: object) -> bool:
    if not isinstance(value, list):
        return False
    return any(str(item).strip() for item in value)


def main() -> int:
    args = parse_args()
    if args.kind == "claims":
        rows = build_claim_eval_dataset(args.claims)
    else:
        rows = build_evidence_bundle_dataset(args.fixtures)
    summary = evaluate_export_rows(rows)
    if not args.dry_run:
        write_jsonl(args.out, rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
