"""Build redacted OCR text metric observations from private raw-text inputs.

The input file is intentionally private: it may contain human ground-truth text
and provider OCR text needed to compute extraction quality. This script writes a
redacted benchmark manifest that contains only numeric text metrics and safe
metadata. It never persists raw OCR text, provider payloads, image bytes,
database rows, or local source-image paths.

The output rows are compatible with
``build_paddleocr_text_extraction_eval_summary.py`` and then
``gate_paddleocr_text_extraction_target.py``.

References:
    https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html
    https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html
    https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "supplement-paddleocr-text-metric-manifest-v1"
ROW_SCHEMA_VERSION = "supplement-paddleocr-text-metric-fixture-v1"
TARGET_PROVIDER = "paddleocr_local"
ALLOWED_EVAL_SPLITS = frozenset({"holdout", "test"})
HUMAN_REVIEWED_STATUSES = frozenset({"human_reviewed", "verified", "approved"})
MAX_NORMALIZED_CHARS = 12000
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://paddlepaddle.github.io/PaddleOCR/main/en/version2.x/ppocr/model_train/detection.html",
    "https://paddlepaddle.github.io/PaddleOCR/v2.10.0/en/ppocr/model_train/recognition.html",
)
RAW_FORBIDDEN_OUTPUT_KEYS = frozenset(
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
        "text",
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


class PaddleOCRTextMetricManifestError(ValueError):
    """Raised when private OCR text metrics cannot be safely materialized."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-text-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument(
        "--provider",
        default=TARGET_PROVIDER,
        help="Provider to score. Use 'all' to score every provider observation.",
    )
    parser.add_argument("--eval-split", required=True, choices=sorted(ALLOWED_EVAL_SPLITS))
    parser.add_argument(
        "--leakage-check-passed",
        action="store_true",
        help="Explicit assertion that the private split passed leakage validation.",
    )
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """Run the metric manifest builder and write redacted artifacts.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else args.output.expanduser().resolve().with_suffix(args.output.suffix + ".summary.json")
    )
    try:
        rows, summary = build_paddleocr_text_metric_manifest(
            private_text_manifest=args.private_text_manifest,
            provider=args.provider,
            eval_split=args.eval_split,
            leakage_check_passed=args.leakage_check_passed,
        )
    except (OSError, json.JSONDecodeError, PaddleOCRTextMetricManifestError) as exc:
        rows = []
        summary = _error_summary(error=exc, provider=args.provider, eval_split=args.eval_split)
        exit_code = 1
    else:
        exit_code = 0

    _write_jsonl(args.output, rows)
    _write_json(summary_path, summary)
    print(json.dumps(_cli_summary(summary), ensure_ascii=False, sort_keys=True))
    return exit_code


def build_paddleocr_text_metric_manifest(
    *,
    private_text_manifest: Path,
    provider: str = TARGET_PROVIDER,
    eval_split: str,
    leakage_check_passed: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build redacted metric rows from private OCR text observations.

    Args:
        private_text_manifest: JSONL file containing private expected/provider
            text. The input is read only in process memory.
        provider: Provider id to score, or ``"all"`` for every observation.
        eval_split: Evaluation split to materialize.
        leakage_check_passed: Explicit leakage validation assertion.

    Returns:
        Redacted metric fixture rows and summary.

    Raises:
        PaddleOCRTextMetricManifestError: If input rows are malformed or text
            is too large for deterministic exact LCS scoring.
    """
    provider = _provider_filter(provider)
    if eval_split not in ALLOWED_EVAL_SPLITS:
        raise PaddleOCRTextMetricManifestError("eval_split must be holdout or test.")
    rows = _read_jsonl(private_text_manifest)
    output_rows: list[dict[str, Any]] = []
    skip_reasons: Counter[str] = Counter()
    observation_counts: Counter[str] = Counter()
    text_source_counts: Counter[str] = Counter()

    for row in rows:
        row_split = row.get("eval_split") or row.get("split")
        if row_split is not None and row_split != eval_split:
            skip_reasons["split_mismatch"] += 1
            continue
        expected = row.get("expected")
        if not _expected_is_human_reviewed(expected):
            skip_reasons["expected_not_human_reviewed"] += 1
            continue
        reference_text, text_source = _expected_reference_text(row)
        if not reference_text:
            skip_reasons["expected_text_missing"] += 1
            continue
        text_source_counts[text_source] += 1
        scored_observations = _scored_observations(
            row=row, provider=provider, reference_text=reference_text
        )
        if not scored_observations:
            skip_reasons["provider_observation_missing"] += 1
            continue
        for observation in scored_observations:
            observation_counts[str(observation["provider"])] += 1
        row_leakage_check = (
            leakage_check_passed and row.get("leakage_check_passed", True) is not False
        )
        output_rows.append(
            {
                "schema_version": ROW_SCHEMA_VERSION,
                "fixture_id": _safe_token(row.get("fixture_id"), field_name="fixture_id"),
                "split": eval_split,
                "leakage_check_passed": row_leakage_check,
                "expected": {
                    "verification_status": "human_reviewed",
                    "text_ground_truth_present": True,
                    "text_source": text_source,
                },
                "observations": scored_observations,
                "db_write_performed": False,
                "source_rows_read": False,
                "source_image_read_performed": False,
                "ocr_provider_call_performed": False,
                "paddleocr_training_performed": False,
                "raw_ocr_text_stored": False,
                "raw_provider_payload_stored": False,
                "absolute_paths_stored": False,
            }
        )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "private_text_manifest_name": private_text_manifest.name,
        "provider_filter": provider,
        "eval_split": eval_split,
        "input_fixture_count": len(rows),
        "output_fixture_count": len(output_rows),
        "observation_count_by_provider": dict(sorted(observation_counts.items())),
        "expected_text_source_counts": dict(sorted(text_source_counts.items())),
        "skip_reason_counts": dict(sorted(skip_reasons.items())),
        "leakage_check_passed": leakage_check_passed,
        "db_write_performed": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }
    _reject_unsafe_output({"rows": output_rows, "summary": summary})
    return output_rows, summary


def _scored_observations(
    *,
    row: Mapping[str, Any],
    provider: str,
    reference_text: str,
) -> list[dict[str, Any]]:
    """Return redacted scored observations for one fixture.

    Args:
        row: Private input row.
        provider: Provider filter or ``"all"``.
        reference_text: Human ground-truth text.

    Returns:
        Observation rows with numeric metrics only.
    """
    raw_observations = row.get("observations")
    if not isinstance(raw_observations, list):
        return []
    scored: list[dict[str, Any]] = []
    for raw_observation in raw_observations:
        if not isinstance(raw_observation, Mapping):
            continue
        observation_provider = _safe_token(
            raw_observation.get("provider"),
            field_name="observation.provider",
        )
        if provider not in {"all", observation_provider}:
            continue
        hypothesis_text = _observation_text(raw_observation)
        if hypothesis_text is None:
            scored.append(
                {
                    "provider": observation_provider,
                    "status": "missing_text",
                    "text_non_empty": False,
                    "metric_source": "private_text_manifest",
                    "raw_ocr_text_stored": False,
                    "raw_provider_payload_stored": False,
                }
            )
            continue
        metrics = _normalized_text_metrics(reference=reference_text, hypothesis=hypothesis_text)
        scored.append(
            {
                "provider": observation_provider,
                "status": str(raw_observation.get("status") or "completed"),
                "text_non_empty": bool(_normalize_for_lcs(hypothesis_text)),
                "metric_source": "private_text_manifest",
                "matched_char_count": metrics["matched_char_count"],
                "reference_char_count": metrics["reference_char_count"],
                "hypothesis_char_count": metrics["hypothesis_char_count"],
                "normalized_text_precision": metrics["normalized_text_precision"],
                "normalized_text_recall": metrics["normalized_text_recall"],
                "normalized_text_f1": metrics["normalized_text_f1"],
                "raw_ocr_text_stored": False,
                "raw_provider_payload_stored": False,
            }
        )
    return scored


def _normalized_text_metrics(*, reference: str, hypothesis: str) -> dict[str, Any]:
    """Return normalized LCS precision, recall, and F1.

    Args:
        reference: Human ground-truth text.
        hypothesis: Provider OCR text.

    Returns:
        Redacted numeric metric dictionary.

    Raises:
        PaddleOCRTextMetricManifestError: If text is too long for exact scoring.
    """
    reference_chars = _normalize_for_lcs(reference)
    hypothesis_chars = _normalize_for_lcs(hypothesis)
    if not reference_chars:
        raise PaddleOCRTextMetricManifestError("reference text is empty after normalization.")
    if len(reference_chars) > MAX_NORMALIZED_CHARS or len(hypothesis_chars) > MAX_NORMALIZED_CHARS:
        raise PaddleOCRTextMetricManifestError("normalized text exceeds exact scoring limit.")
    matched = _lcs_length(reference_chars, hypothesis_chars)
    precision = _safe_rate(matched, len(hypothesis_chars))
    recall = _safe_rate(matched, len(reference_chars))
    f1 = _f1(precision=precision, recall=recall)
    return {
        "matched_char_count": matched,
        "reference_char_count": len(reference_chars),
        "hypothesis_char_count": len(hypothesis_chars),
        "normalized_text_precision": _round_metric(precision),
        "normalized_text_recall": _round_metric(recall),
        "normalized_text_f1": _round_metric(f1),
    }


def _lcs_length(reference: str, hypothesis: str) -> int:
    """Return exact longest common subsequence length.

    Args:
        reference: Normalized reference string.
        hypothesis: Normalized OCR hypothesis string.

    Returns:
        LCS character count.
    """
    if not reference or not hypothesis:
        return 0
    previous = [0] * (len(hypothesis) + 1)
    for reference_char in reference:
        current = [0]
        diagonal = 0
        for index, hypothesis_char in enumerate(hypothesis, 1):
            above = previous[index]
            left = current[index - 1]
            value = diagonal + 1 if reference_char == hypothesis_char else max(above, left)
            current.append(value)
            diagonal = above
        previous = current
    return previous[-1]


def _normalize_for_lcs(value: str) -> str:
    """Normalize OCR text before character-level extraction scoring.

    Args:
        value: Raw private text.

    Returns:
        Lowercase NFKC text containing only letters and numbers.
    """
    normalized = unicodedata.normalize("NFKC", value).lower()
    return "".join(char for char in normalized if char.isalnum())


def _expected_reference_text(row: Mapping[str, Any]) -> tuple[str | None, str]:
    """Return human ground-truth text and source type.

    Args:
        row: Private input row.

    Returns:
        ``(text, source)``. Text is ``None`` when unavailable.
    """
    for key in ("expected_text", "ground_truth_text"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value, key
    expected = row.get("expected")
    if not isinstance(expected, Mapping):
        return None, "missing"
    for key in ("text", "full_text", "normalized_text", "ground_truth_text"):
        value = expected.get(key)
        if isinstance(value, str) and value.strip():
            return value, f"expected.{key}"
    section_text = _section_text(expected)
    if section_text:
        return section_text, "expected.structured_sections"
    return None, "missing"


def _section_text(expected: Mapping[str, Any]) -> str | None:
    """Return structured expected text fallback.

    Args:
        expected: Expected object.

    Returns:
        Space-joined structured text, or ``None``.
    """
    parts: list[str] = []
    _append_text_value(parts, expected.get("product_name"))
    _append_text_value(parts, expected.get("manufacturer"))
    for item in _list_items(expected.get("ingredients")):
        if isinstance(item, Mapping):
            _append_text_value(
                parts,
                item.get("display_name") or item.get("name") or item.get("original_name"),
            )
            _append_text_value(parts, item.get("amount"))
            _append_text_value(parts, item.get("unit"))
    intake_method = expected.get("intake_method")
    if isinstance(intake_method, Mapping):
        _append_text_value(parts, intake_method.get("text"))
    else:
        _append_text_value(parts, intake_method)
    for key in ("precautions", "allergen_warnings", "functional_claims", "label_sections"):
        for item in _list_items(expected.get(key)):
            if isinstance(item, Mapping):
                _append_text_value(parts, item.get("text"))
                _append_text_value(parts, item.get("section_type"))
            else:
                _append_text_value(parts, item)
    return " ".join(parts) if parts else None


def _append_text_value(parts: list[str], value: Any) -> None:
    """Append a scalar text value to a private in-memory list.

    Args:
        parts: Mutable text part list.
        value: Candidate value.
    """
    if isinstance(value, str) and value.strip():
        parts.append(value.strip())
    elif isinstance(value, int | float) and not isinstance(value, bool):
        parts.append(str(value))


def _list_items(value: Any) -> list[Any]:
    """Return list items from a candidate value.

    Args:
        value: Candidate list.

    Returns:
        List value or an empty list.
    """
    return value if isinstance(value, list) else []


def _observation_text(observation: Mapping[str, Any]) -> str | None:
    """Return provider OCR text from private observation payload.

    Args:
        observation: Private provider observation.

    Returns:
        OCR text, or ``None``.
    """
    for key in ("text", "ocr_text", "raw_ocr_text", "full_text"):
        value = observation.get(key)
        if isinstance(value, str):
            return value
    return None


def _provider_filter(value: Any) -> str:
    """Return a safe provider filter token.

    Args:
        value: Provider filter candidate.

    Returns:
        Provider token or ``"all"``.
    """
    return _safe_token(value, field_name="provider")


def _expected_is_human_reviewed(expected: Any) -> bool:
    """Return whether expected text can be treated as ground truth.

    Args:
        expected: Expected fixture object.

    Returns:
        True when status is human-reviewed.
    """
    if not isinstance(expected, Mapping):
        return False
    status = expected.get("verification_status") or expected.get("ground_truth_status")
    return status in HUMAN_REVIEWED_STATUSES


def _safe_token(value: Any, *, field_name: str) -> str:
    """Return a stable token suitable for redacted output.

    Args:
        value: Candidate value.
        field_name: Diagnostic field name.

    Returns:
        Safe token.

    Raises:
        PaddleOCRTextMetricManifestError: If token is missing or unsafe.
    """
    if not isinstance(value, str) or not value.strip():
        raise PaddleOCRTextMetricManifestError(f"{field_name} must be a non-empty string.")
    token = value.strip()
    if token != "all" and not TOKEN_PATTERN.fullmatch(token):
        raise PaddleOCRTextMetricManifestError(f"{field_name} must be a stable token.")
    return token


def _safe_rate(numerator: int, denominator: int) -> Decimal:
    """Return a Decimal rate.

    Args:
        numerator: Matched count.
        denominator: Total count.

    Returns:
        Rate in ``0..1``. Empty denominator returns zero.
    """
    if denominator <= 0:
        return Decimal("0")
    return Decimal(numerator) / Decimal(denominator)


def _f1(*, precision: Decimal, recall: Decimal) -> Decimal:
    """Return harmonic mean of precision and recall.

    Args:
        precision: Precision rate.
        recall: Recall rate.

    Returns:
        F1 rate.
    """
    if precision + recall == 0:
        return Decimal("0")
    return (Decimal("2") * precision * recall) / (precision + recall)


def _round_metric(value: Decimal) -> float:
    """Round a metric to four decimals for stable artifacts.

    Args:
        value: Decimal metric.

    Returns:
        Rounded float.
    """
    return float(value.quantize(Decimal("0.0001")))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL object rows.

    Args:
        path: JSONL path.

    Returns:
        Parsed row objects.

    Raises:
        PaddleOCRTextMetricManifestError: If a line is not a JSON object.
    """
    if not path.is_file():
        raise PaddleOCRTextMetricManifestError("private text manifest does not exist.")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise PaddleOCRTextMetricManifestError(f"JSONL line {line_number} must be an object.")
        rows.append(parsed)
    return rows


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    """Write redacted JSONL rows.

    Args:
        path: Destination path.
        rows: Redacted row objects.
    """
    _reject_unsafe_output(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a redacted JSON object.

    Args:
        path: Destination path.
        payload: Redacted JSON object.
    """
    _reject_unsafe_output(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _reject_unsafe_output(value: Any) -> None:
    """Reject raw text, local paths, provider payloads, and secrets in output.

    Args:
        value: JSON-like output value.

    Raises:
        ValueError: If unsafe output content is detected.
    """
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if key_text in RAW_FORBIDDEN_OUTPUT_KEYS:
                raise ValueError(key_text)
            _reject_unsafe_output(child)
        return
    if isinstance(value, list | tuple):
        for child in value:
            _reject_unsafe_output(child)
        return
    if isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in SECRET_LIKE_MARKERS):
            raise ValueError("secret-like marker")
        if any(marker in value for marker in LOCAL_PATH_MARKERS):
            raise ValueError("local path literal")


def _cli_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return a stdout-safe summary.

    Args:
        summary: Redacted summary artifact.

    Returns:
        Compact CLI status without metric values or local paths.
    """
    return {
        "schema_version": "paddleocr-text-metric-manifest-cli-v1",
        "status": summary.get("status", "ok"),
        "provider_filter": summary.get("provider_filter"),
        "eval_split": summary.get("eval_split"),
        "output_fixture_count": summary.get("output_fixture_count", 0),
        "metric_values_printed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
    }


def _error_summary(*, error: Exception, provider: str, eval_split: str) -> dict[str, Any]:
    """Return a redacted failure summary.

    Args:
        error: Exception that blocked metric generation.
        provider: Requested provider filter.
        eval_split: Requested evaluation split.

    Returns:
        Safe failure summary.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "error_type": type(error).__name__,
        "provider_filter": provider,
        "eval_split": eval_split,
        "input_fixture_count": 0,
        "output_fixture_count": 0,
        "observation_count_by_provider": {},
        "skip_reason_counts": {},
        "leakage_check_passed": False,
        "db_write_performed": False,
        "source_rows_read": False,
        "source_image_read_performed": False,
        "ocr_provider_call_performed": False,
        "paddleocr_training_performed": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "absolute_paths_stored": False,
        "source_doc_urls": list(SOURCE_DOC_URLS),
    }


if __name__ == "__main__":
    raise SystemExit(run_cli())
