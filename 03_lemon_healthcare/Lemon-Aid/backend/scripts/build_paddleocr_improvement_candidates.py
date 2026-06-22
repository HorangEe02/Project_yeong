"""Build redacted PaddleOCR improvement candidate manifests.

This script consumes human-reviewed OCR benchmark fixtures after provider
observations have been attached. It does not call OCR providers, does not write
to the database, and does not train PaddleOCR. Its only job is to separate
PaddleOCR failures into manual-review buckets that can later become
``paddleocr_detection`` or ``paddleocr_recognition`` learning dataset items.

References:
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/model_train/finetune.html
    https://cloud.google.com/vision/docs/ocr
    https://api.ncloud-docs.com/docs/en/ai-application-service-ocr
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "supplement-paddleocr-improvement-manifest-v1"
ROW_SCHEMA_VERSION = "supplement-paddleocr-improvement-candidate-v1"
EXPECTED_BENCHMARK_ROW_SCHEMA_VERSION = "supplement-ocr-provider-benchmark-fixture-v1"
TARGET_PROVIDER = "paddleocr_local"
TEACHER_PROVIDERS = frozenset({"clova_ocr", "google_vision_document"})
MAX_EXPECTED_INGREDIENTS = 80
MAX_TEXT_LENGTH = 512
AMOUNT_MATCH_TOLERANCE = 1e-6
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
SAFE_TOKEN_PATTERN = re.compile(r"^[0-9A-Za-z가-힣_.:-]{1,160}$")
SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/model_train/finetune.html",
    "https://cloud.google.com/vision/docs/ocr",
    "https://api.ncloud-docs.com/docs/en/ai-application-service-ocr",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed namespace.
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
    parser.add_argument("--source-run-id", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Run the CLI entrypoint.

    Args:
        argv: Optional argument list for tests.
    """
    args = parse_args(argv)
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    try:
        rows, summary = build_paddleocr_improvement_candidates(
            benchmark_manifest=args.benchmark_manifest,
            source_run_id=args.source_run_id,
        )
        _reject_unsafe_payload({"rows": rows, "summary": summary})
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure = _failure_summary(
            benchmark_manifest=args.benchmark_manifest,
            output_path=output_path,
            error=exc,
        )
        try:
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(
                json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None


def build_paddleocr_improvement_candidates(
    *,
    benchmark_manifest: Path,
    source_run_id: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build PaddleOCR improvement candidates from benchmark observations.

    Args:
        benchmark_manifest: JSONL benchmark fixture manifest that contains
            human-reviewed ``expected`` fields and provider observations.
        source_run_id: Optional operator run id for traceability.

    Returns:
        Candidate rows and a redacted summary.

    Raises:
        ValueError: If an input row is unsafe or malformed.
    """
    safe_source_run_id = _safe_optional_token(source_run_id) if source_run_id is not None else None
    if source_run_id is not None and safe_source_run_id is None:
        raise ValueError("source_run_id must be a safe token.")
    rows = _read_jsonl(benchmark_manifest)
    candidates: list[dict[str, Any]] = []
    skip_reasons: Counter[str] = Counter()
    failure_counts: Counter[str] = Counter()
    next_step_counts: Counter[str] = Counter()
    task_counts: Counter[str] = Counter()

    for row in rows:
        _reject_unsafe_payload(row)
        if row.get("schema_version") != EXPECTED_BENCHMARK_ROW_SCHEMA_VERSION:
            skip_reasons["unsupported_schema_version"] += 1
            continue
        expected = row.get("expected")
        if not _is_human_reviewed_expected(expected):
            skip_reasons["expected_not_human_reviewed"] += 1
            continue
        paddle_observation = _provider_observation(row, TARGET_PROVIDER)
        if paddle_observation is None:
            skip_reasons["missing_paddleocr_observation"] += 1
            continue
        issue = _classify_paddleocr_issue(row=row, observation=paddle_observation)
        if not issue["failure_codes"]:
            skip_reasons["paddleocr_no_improvement_issue"] += 1
            continue
        candidate = _candidate_row(
            row=row,
            issue=issue,
            source_run_id=safe_source_run_id,
        )
        candidates.append(candidate)
        for code in candidate["failure_codes"]:
            failure_counts[str(code)] += 1
        next_step_counts[str(candidate["recommended_next_step"])] += 1
        for task_type in candidate["training_task_suggestions"]:
            task_counts[str(task_type)] += 1

    summary = _summary(
        benchmark_manifest=benchmark_manifest,
        source_run_id=safe_source_run_id,
        input_count=len(rows),
        candidates=candidates,
        skip_reasons=skip_reasons,
        failure_counts=failure_counts,
        next_step_counts=next_step_counts,
        task_counts=task_counts,
    )
    _reject_unsafe_payload({"rows": candidates, "summary": summary})
    return candidates, summary


def _classify_paddleocr_issue(
    *,
    row: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    """Classify one PaddleOCR observation into improvement buckets.

    Args:
        row: Benchmark fixture row.
        observation: PaddleOCR observation row.

    Returns:
        Issue classification with failure codes, task suggestions, and counts.
    """
    expected = row["expected"]
    expected_ingredients = _ingredient_facts(expected.get("ingredients"))
    observed_ingredients = _ingredient_facts(observation.get("parsed_ingredients"))
    expected_names = {fact["name"] for fact in expected_ingredients}
    observed_names = {fact["name"] for fact in observed_ingredients}
    expected_sections = _section_types(expected.get("label_sections"))
    observed_sections = _section_types(observation.get("label_sections"))

    failure_codes: list[str] = []
    task_suggestions: set[str] = set()

    if observation.get("status") == "error" or observation.get("error") is True:
        failure_codes.append("paddleocr_runtime_error")
    if observation.get("text_non_empty") is not True:
        failure_codes.append("paddleocr_empty_text")
        task_suggestions.add("paddleocr_detection")
    if observation.get("parser_success") is False and observation.get("text_non_empty") is True:
        failure_codes.append("paddleocr_parser_failed")

    missed_names = sorted(expected_names.difference(observed_names))
    if missed_names:
        failure_codes.append("ingredient_name_miss")
        task_suggestions.add("paddleocr_recognition")

    amount_unit_miss_count = _amount_unit_miss_count(expected_ingredients, observed_ingredients)
    if amount_unit_miss_count:
        failure_codes.append("ingredient_amount_unit_miss")
        task_suggestions.add("paddleocr_recognition")

    unexpected_count = len(observed_names.difference(expected_names)) if observed_names else 0
    if unexpected_count:
        failure_codes.append("unexpected_ingredient_candidate")

    if _intake_method_present(expected.get("intake_method")) and not _intake_method_present(
        observation.get("intake_method")
    ):
        failure_codes.append("intake_method_miss")
        task_suggestions.add("paddleocr_recognition")

    if _nonempty_text_rows(expected.get("precautions")) and not _nonempty_text_rows(
        observation.get("precautions")
    ):
        failure_codes.append("precaution_miss")
        task_suggestions.add("paddleocr_recognition")

    section_miss_count = len(expected_sections.difference(observed_sections))
    if section_miss_count:
        failure_codes.append("section_type_miss")
        task_suggestions.add("paddleocr_detection")

    if not task_suggestions and (
        "paddleocr_parser_failed" in failure_codes
        or "unexpected_ingredient_candidate" in failure_codes
    ):
        task_suggestions.add("postprocessing_rule_review")

    if "paddleocr_runtime_error" in failure_codes and len(failure_codes) == 1:
        task_suggestions.add("provider_runtime_triage")

    return {
        "failure_codes": sorted(set(failure_codes)),
        "training_task_suggestions": sorted(task_suggestions),
        "recommended_next_step": _recommended_next_step(failure_codes, task_suggestions),
        "score_snapshot": {
            "expected_ingredient_count": len(expected_ingredients),
            "observed_ingredient_count": len(observed_ingredients),
            "missed_ingredient_count": len(missed_names),
            "unexpected_ingredient_count": unexpected_count,
            "amount_unit_miss_count": amount_unit_miss_count,
            "expected_section_count": len(expected_sections),
            "observed_section_count": len(observed_sections),
            "section_miss_count": section_miss_count,
            "teacher_expected_match_count": _teacher_expected_match_count(row, expected_names),
        },
    }


def _candidate_row(
    *,
    row: dict[str, Any],
    issue: dict[str, Any],
    source_run_id: str | None,
) -> dict[str, Any]:
    """Return one improvement candidate row.

    Args:
        row: Benchmark fixture row.
        issue: Issue classification from ``_classify_paddleocr_issue``.
        source_run_id: Optional operator run id.

    Returns:
        Redacted candidate row. Human-reviewed expected values are included in
        the row artifact because they are the source of future labels, but they
        are intentionally omitted from the summary and stdout.
    """
    candidate = {
        "schema_version": ROW_SCHEMA_VERSION,
        "source_run_id": source_run_id,
        "fixture_id": _safe_required_token(row.get("fixture_id"), field_name="fixture_id"),
        "source_ref": _safe_required_token(row.get("source_ref"), field_name="source_ref"),
        "image_ref_hash": _safe_required_sha256(row.get("image_ref_hash")),
        "image_sha256": _safe_required_sha256(row.get("image_sha256")),
        "category_key": _safe_required_token(row.get("category_key"), field_name="category_key"),
        "source_kind": "review",
        "target_provider": TARGET_PROVIDER,
        "teacher_providers": sorted(TEACHER_PROVIDERS),
        "expected": _sanitized_expected(row.get("expected")),
        "failure_codes": issue["failure_codes"],
        "score_snapshot": issue["score_snapshot"],
        "training_task_suggestions": issue["training_task_suggestions"],
        "recommended_next_step": issue["recommended_next_step"],
        "requires_manual_review": True,
        "ready_for_training_export": False,
        "manual_review_instruction": (
            "Create reviewed paddleocr_detection or paddleocr_recognition dataset items "
            "only after checking the private fixture against this expected snapshot."
        ),
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
    }
    image_path = _safe_relative_image_path(row.get("image_path"))
    if image_path is not None:
        candidate["image_path"] = image_path
    _reject_unsafe_payload(candidate)
    return candidate


def _recommended_next_step(failure_codes: list[str], task_suggestions: set[str]) -> str:
    """Return the highest-signal next action for one candidate.

    Args:
        failure_codes: Failure code list.
        task_suggestions: Candidate task suggestions.

    Returns:
        Stable next-step token.
    """
    if "paddleocr_runtime_error" in failure_codes and len(failure_codes) == 1:
        return "provider_runtime_triage"
    if "paddleocr_detection" in task_suggestions:
        return "paddleocr_detection_manual_review"
    if "paddleocr_recognition" in task_suggestions:
        return "paddleocr_recognition_manual_review"
    return "postprocessing_rule_review"


def _teacher_expected_match_count(row: dict[str, Any], expected_names: set[str]) -> int:
    """Count teacher observations that matched all expected ingredient names.

    Args:
        row: Benchmark fixture row.
        expected_names: Expected ingredient names.

    Returns:
        Number of teacher providers with complete expected-name coverage.
    """
    if not expected_names:
        return 0
    count = 0
    for observation in _observations(row):
        provider = observation.get("provider")
        if provider not in TEACHER_PROVIDERS:
            continue
        observed_names = {
            fact["name"] for fact in _ingredient_facts(observation.get("parsed_ingredients"))
        }
        if expected_names.issubset(observed_names):
            count += 1
    return count


def _provider_observation(row: dict[str, Any], provider_name: str) -> dict[str, Any] | None:
    """Return the first observation for a provider.

    Args:
        row: Benchmark fixture row.
        provider_name: Provider name.

    Returns:
        Observation row or ``None``.
    """
    for observation in _observations(row):
        if observation.get("provider") == provider_name:
            _reject_unsafe_payload(observation)
            return observation
    return None


def _observations(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Return sanitized observation rows from a benchmark fixture.

    Args:
        row: Benchmark fixture row.

    Returns:
        List of observation dictionaries.
    """
    raw_observations = row.get("observations")
    if not isinstance(raw_observations, list):
        return []
    observations = [item for item in raw_observations if isinstance(item, dict)]
    _reject_unsafe_payload(observations)
    return observations


def _is_human_reviewed_expected(value: Any) -> bool:
    """Return whether expected values are human-reviewed.

    Args:
        value: Expected payload.

    Returns:
        True when benchmark expected values are reviewed and can guide labels.
    """
    if not isinstance(value, dict):
        return False
    return value.get("verification_status") in {"human_reviewed", "verified", "approved"}


def _sanitized_expected(value: Any) -> dict[str, Any]:
    """Return bounded human-reviewed expected values for candidate rows.

    Args:
        value: Benchmark expected payload.

    Returns:
        Expected fields needed for later manual label creation.

    Raises:
        ValueError: If expected fields are missing or unsafe.
    """
    if not isinstance(value, dict):
        raise ValueError("Expected payload must be an object.")
    expected = {
        "verification_status": "human_reviewed",
        "product_name": _safe_optional_text(value.get("product_name")),
        "manufacturer": _safe_optional_text(value.get("manufacturer")),
        "ingredients": _expected_ingredient_rows(value.get("ingredients")),
        "intake_method": _expected_intake_method(value.get("intake_method")),
        "precautions": _expected_text_rows(value.get("precautions")),
        "functional_claims": _expected_text_rows(value.get("functional_claims")),
        "label_sections": _expected_label_sections(value.get("label_sections")),
    }
    _reject_unsafe_payload(expected)
    return expected


def _expected_ingredient_rows(value: Any) -> list[dict[str, Any]]:
    """Return bounded ingredient rows from expected data.

    Args:
        value: Expected ingredient list.

    Returns:
        Sanitized ingredient rows.
    """
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value[:MAX_EXPECTED_INGREDIENTS]:
        if not isinstance(item, dict):
            continue
        name = _safe_optional_text(
            item.get("display_name") or item.get("name") or item.get("normalized_name")
        )
        if not name:
            continue
        row: dict[str, Any] = {"display_name": name}
        amount = _safe_optional_number(item.get("amount"))
        unit = _safe_optional_text(item.get("unit"), max_length=24)
        if amount is not None:
            row["amount"] = amount
        if unit is not None:
            row["unit"] = unit
        rows.append(row)
    return rows


def _expected_intake_method(value: Any) -> dict[str, Any]:
    """Return bounded intake-method expected data.

    Args:
        value: Expected intake method payload.

    Returns:
        Sanitized intake method object.
    """
    if not isinstance(value, dict):
        return {}
    text = _safe_optional_text(value.get("text"), max_length=MAX_TEXT_LENGTH)
    return {"text": text} if text else {}


def _expected_text_rows(value: Any) -> list[dict[str, str]]:
    """Return bounded text rows from expected data.

    Args:
        value: Expected list of text rows.

    Returns:
        Sanitized rows with ``text`` keys.
    """
    if not isinstance(value, list):
        return []
    rows = []
    for item in value:
        text = item.get("text") if isinstance(item, dict) else item
        sanitized = _safe_optional_text(text, max_length=MAX_TEXT_LENGTH)
        if sanitized:
            rows.append({"text": sanitized})
    return rows


def _expected_label_sections(value: Any) -> list[dict[str, str]]:
    """Return expected label-section rows.

    Args:
        value: Expected label section list.

    Returns:
        Sanitized section rows.
    """
    return [{"section_type": section} for section in sorted(_section_types(value))]


def _ingredient_facts(value: Any) -> list[dict[str, Any]]:
    """Return normalized ingredient facts from an expected or observation row.

    Args:
        value: Ingredient list.

    Returns:
        Ingredient facts with normalized name, amount, and unit.
    """
    if not isinstance(value, list):
        return []
    facts: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = item.get("display_name") or item.get("normalized_name") or item.get("name")
        normalized_name = _normalize_token(name)
        if not normalized_name:
            continue
        facts.append(
            {
                "name": normalized_name,
                "amount": _safe_optional_number(item.get("amount")),
                "unit": _normalize_token(item.get("unit")),
            }
        )
    return facts


def _amount_unit_miss_count(
    expected: list[dict[str, Any]],
    observed: list[dict[str, Any]],
) -> int:
    """Return expected ingredient facts without matching amount/unit observations.

    Args:
        expected: Expected ingredient facts.
        observed: Observed ingredient facts.

    Returns:
        Count of expected amount/unit facts not found in observations.
    """
    count = 0
    for expected_fact in expected:
        if expected_fact["amount"] is None or expected_fact["unit"] is None:
            continue
        if not any(
            _amount_unit_matches(expected_fact, observed_fact) for observed_fact in observed
        ):
            count += 1
    return count


def _amount_unit_matches(expected: dict[str, Any], observed: dict[str, Any]) -> bool:
    """Return whether ingredient name, amount, and unit match exactly.

    Args:
        expected: Expected ingredient fact.
        observed: Observed ingredient fact.

    Returns:
        True when name, amount, and unit match.
    """
    return (
        expected["name"] == observed["name"]
        and expected["amount"] is not None
        and observed["amount"] is not None
        and abs(float(expected["amount"]) - float(observed["amount"])) <= AMOUNT_MATCH_TOLERANCE
        and expected["unit"] == observed["unit"]
    )


def _intake_method_present(value: Any) -> bool:
    """Return whether an intake method contains expected content.

    Args:
        value: Intake method payload.

    Returns:
        True when text or structured fields are non-empty.
    """
    if not isinstance(value, dict):
        return False
    text = value.get("text")
    if isinstance(text, str) and text.strip():
        return True
    structured = value.get("structured")
    if not isinstance(structured, dict):
        return False
    frequency = structured.get("frequency")
    return isinstance(frequency, str) and bool(frequency.strip())


def _nonempty_text_rows(value: Any) -> bool:
    """Return whether a text row list has at least one non-empty row.

    Args:
        value: Candidate list of text rows.

    Returns:
        True when any text row is present.
    """
    if not isinstance(value, list):
        return False
    return any(
        isinstance(item, dict) and isinstance(item.get("text"), str) and bool(item["text"].strip())
        for item in value
    )


def _section_types(value: Any) -> set[str]:
    """Return safe section type tokens from a row.

    Args:
        value: Candidate label section rows.

    Returns:
        Set of normalized section tokens.
    """
    if not isinstance(value, list):
        return set()
    sections: set[str] = set()
    for item in value:
        section = item.get("section_type") if isinstance(item, dict) else item
        token = _safe_optional_token(section)
        if token:
            sections.add(token)
    return sections


def _safe_relative_image_path(value: Any) -> str | None:
    """Return a safe relative image fixture path.

    Args:
        value: Candidate image path.

    Returns:
        Relative image path or ``None``.

    Raises:
        ValueError: If the path is absolute, URL-like, or contains traversal.
    """
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("image_path must be a relative string.")
    if value.startswith("/") or "://" in value or ".." in value:
        raise ValueError("image_path must be a relative fixture path.")
    if any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("image_path must not contain a local path literal.")
    return value


def _safe_required_token(value: Any, *, field_name: str) -> str:
    """Return a required safe token.

    Args:
        value: Candidate value.
        field_name: Field name for error messages.

    Returns:
        Safe token string.

    Raises:
        ValueError: If the value is missing or unsafe.
    """
    token = _safe_optional_token(value)
    if token is None:
        raise ValueError(f"{field_name} must be a safe token.")
    return token


def _safe_optional_token(value: Any) -> str | None:
    """Return an optional safe token.

    Args:
        value: Candidate value.

    Returns:
        Safe token or ``None``.
    """
    if not isinstance(value, str):
        return None
    token = value.strip()
    if not token or not SAFE_TOKEN_PATTERN.fullmatch(token):
        return None
    return token


def _safe_required_sha256(value: Any) -> str:
    """Return a required SHA-256 hex string.

    Args:
        value: Candidate value.

    Returns:
        SHA-256 hex string.

    Raises:
        ValueError: If the value is malformed.
    """
    if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
        return value
    raise ValueError("Expected SHA-256 hex string.")


def _safe_optional_text(value: Any, *, max_length: int = 160) -> str | None:
    """Return bounded text without path or raw-artifact markers.

    Args:
        value: Candidate value.
        max_length: Maximum output length.

    Returns:
        Bounded text or ``None``.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    text = text[:max_length]
    _reject_unsafe_payload(text)
    return text


def _safe_optional_number(value: Any) -> float | None:
    """Return a non-negative number when present.

    Args:
        value: Candidate value.

    Returns:
        Float or ``None``.
    """
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        return None
    return float(value)


def _normalize_token(value: Any) -> str:
    """Normalize text for exact-match comparisons.

    Args:
        value: Candidate value.

    Returns:
        Lower-cased normalized token.
    """
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value.casefold().strip())


def _summary(
    *,
    benchmark_manifest: Path,
    source_run_id: str | None,
    input_count: int,
    candidates: list[dict[str, Any]],
    skip_reasons: Counter[str],
    failure_counts: Counter[str],
    next_step_counts: Counter[str],
    task_counts: Counter[str],
) -> dict[str, Any]:
    """Return redacted run summary.

    Args:
        benchmark_manifest: Input manifest path.
        source_run_id: Optional operator run id.
        input_count: Number of input rows.
        candidates: Output candidate rows.
        skip_reasons: Skip reason counts.
        failure_counts: Failure code counts.
        next_step_counts: Recommended next-step counts.
        task_counts: Training task suggestion counts.

    Returns:
        Summary without expected text, source refs, image paths, or raw payloads.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "source_run_id": source_run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "benchmark_manifest_name": benchmark_manifest.name,
        "benchmark_manifest_hash": _sha256_text(str(benchmark_manifest.expanduser())),
        "input_fixture_count": input_count,
        "improvement_candidate_count": len(candidates),
        "skip_reason_counts": dict(sorted(skip_reasons.items())),
        "failure_code_counts": dict(sorted(failure_counts.items())),
        "recommended_next_step_counts": dict(sorted(next_step_counts.items())),
        "training_task_suggestion_counts": dict(sorted(task_counts.items())),
        "target_provider": TARGET_PROVIDER,
        "teacher_providers": sorted(TEACHER_PROVIDERS),
        "requires_manual_review_before_training": True,
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "expected_text_printed": False,
        "source_ref_printed": False,
        "image_path_printed": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


def _failure_summary(
    *,
    benchmark_manifest: Path,
    output_path: Path,
    error: Exception,
) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        benchmark_manifest: Input manifest path.
        output_path: Planned output path.
        error: Failure exception.

    Returns:
        JSON-safe failure summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "benchmark_manifest_name": benchmark_manifest.name,
        "benchmark_manifest_hash": _sha256_text(str(benchmark_manifest.expanduser())),
        "output_name": output_path.name,
        "output_hash": _sha256_text(str(output_path.expanduser())),
        "error_code": type(error).__name__,
        "error_message": "PaddleOCR improvement candidate build failed.",
        "db_write_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "expected_text_printed": False,
        "source_ref_printed": False,
        "image_path_printed": False,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL object rows.

    Args:
        path: Input JSONL path.

    Returns:
        JSON object rows.

    Raises:
        ValueError: If a row is not a JSON object.
    """
    rows: list[dict[str, Any]] = []
    with path.expanduser().open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if not isinstance(row, dict):
                raise ValueError(f"JSONL row {line_number} must be an object.")
            rows.append(row)
    return rows


def _sha256_text(value: str) -> str:
    """Return SHA-256 digest for a string.

    Args:
        value: Text to hash.

    Returns:
        SHA-256 hex digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _reject_unsafe_payload(value: Any) -> None:
    """Reject raw keys, local paths, URLs, or raw provider artifacts.

    Args:
        value: Payload candidate.

    Raises:
        ValueError: If unsafe content is detected.
    """
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for marker in LOCAL_PATH_MARKERS:
        if marker in serialized:
            raise ValueError("PaddleOCR improvement manifest contains a local path literal.")
    _reject_raw_keys(value)


def _reject_raw_keys(value: Any) -> None:
    """Recursively reject raw OCR/provider key names.

    Args:
        value: Payload candidate.

    Raises:
        ValueError: If an unsafe key appears.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in RAW_FORBIDDEN_KEYS:
                raise ValueError(f"PaddleOCR improvement manifest contains raw key: {key}")
            _reject_raw_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_raw_keys(child)


if __name__ == "__main__":
    main()
