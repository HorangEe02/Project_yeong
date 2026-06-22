"""Export safe human-review templates for chronic ingredient expected labels.

The output is an operator review contract, not an importable label batch. It
contains bounded current expected ingredients and structured OCR/LLM candidate
hints only. It never stores raw OCR text, provider payloads, request headers,
image bytes, local paths, free-text notes, or secrets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = "chronic-ingredient-review-template-v1"
DEFAULT_FIXTURE_PREFIX = "naver-chronic-"
DEFAULT_SNAPSHOT_VERSION = "v3"
DEFAULT_MAX_CANDIDATES = 12
MAX_CANDIDATES_LIMIT = 50
MAX_TEXT_LENGTH = 160
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
RAW_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "image_bytes",
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
PENDING_REVIEW_WARNINGS = frozenset(
    {
        "auto_expected_requires_human_verification",
        "ground_truth_pending_human_review",
    }
)
REVIEW_DECISION_CONTRACT = {
    "decision_batch_importable": False,
    "requires_human_review": True,
    "free_text_notes_allowed": False,
    "raw_ocr_text_allowed": False,
    "provider_payload_allowed": False,
    "local_path_literals_allowed": False,
    "required_decision_fields": [
        "fixture_id",
        "reviewer_id",
        "reviewed_at",
        "verification_status",
        "verified_ingredients",
        "attestations",
    ],
    "allowed_verification_statuses": [
        "verified",
        "needs_changes",
        "not_scoreable",
    ],
    "verified_ingredient_fields": [
        "display_name",
        "normalized_name",
        "amount",
        "unit",
    ],
    "required_attestations": [
        "human_verified_from_local_fixture",
        "no_raw_ocr_text_copied",
        "no_provider_payload_copied",
        "no_secret_or_local_path_copied",
    ],
}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Optional redacted manifest-with-observations JSONL.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument("--fixture-prefix", default=DEFAULT_FIXTURE_PREFIX)
    parser.add_argument("--snapshot-version", default=DEFAULT_SNAPSHOT_VERSION)
    parser.add_argument("--max-candidates", type=int, default=DEFAULT_MAX_CANDIDATES)
    return parser.parse_args()


def main() -> None:
    """Write review templates and a redacted summary."""
    args = parse_args()
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary is not None
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    expected_dir = args.expected_dir.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve() if args.manifest is not None else None

    try:
        rows, summary = export_review_template_rows(
            expected_dir=expected_dir,
            manifest_path=manifest_path,
            fixture_prefix=args.fixture_prefix,
            snapshot_version=args.snapshot_version,
            max_candidates=args.max_candidates,
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
            expected_dir=expected_dir,
            manifest_path=manifest_path,
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


def export_review_template_rows(
    *,
    expected_dir: Path,
    manifest_path: Path | None = None,
    fixture_prefix: str = DEFAULT_FIXTURE_PREFIX,
    snapshot_version: str = DEFAULT_SNAPSHOT_VERSION,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Return safe review template rows for chronic expected snapshots.

    Args:
        expected_dir: Directory containing expected snapshot JSON files.
        manifest_path: Optional redacted manifest with provider observations.
        fixture_prefix: Fixture id prefix to include.
        snapshot_version: Snapshot version suffix, usually ``"v3"``.
        max_candidates: Maximum expected/observation hints per fixture.

    Returns:
        Template rows and redacted summary.

    Raises:
        ValueError: If inputs are malformed or unsafe.
    """
    candidate_limit = _candidate_limit(max_candidates)
    observation_rows = _read_manifest_rows(manifest_path) if manifest_path is not None else {}
    snapshot_paths = _snapshot_paths(
        expected_dir=expected_dir,
        fixture_prefix=fixture_prefix,
        snapshot_version=snapshot_version,
    )
    rows = [
        _template_row(
            path=path,
            observation_row=_observation_row_for_fixture(
                observation_rows,
                _fixture_id_from_snapshot_name(path.name),
            ),
            max_candidates=candidate_limit,
            snapshot_version=snapshot_version,
        )
        for path in snapshot_paths
    ]
    pending_review_count = sum(
        1 for row in rows if row["expected_status"]["pending_human_review"] is True  # type: ignore[index]
    )
    rows_with_observation_hints = sum(
        1 for row in rows if row["observation_context"]["ingredient_hints"]  # type: ignore[index]
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "expected_dir_name": expected_dir.name,
        "expected_dir_path_hash": _sha256_text(str(expected_dir.expanduser())),
        "manifest_name": manifest_path.name if manifest_path is not None else None,
        "manifest_path_hash": (
            _sha256_text(str(manifest_path.expanduser())) if manifest_path is not None else None
        ),
        "fixture_prefix": fixture_prefix,
        "snapshot_version": snapshot_version,
        "row_count": len(rows),
        "pending_human_review_count": pending_review_count,
        "rows_with_observation_hints": rows_with_observation_hints,
        "max_candidates_per_row": candidate_limit,
        "decision_batch_importable": False,
        "requires_human_review": True,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "free_text_review_notes_stored": False,
    }
    _reject_unsafe_payload({"rows": rows, "summary": summary})
    return rows, summary


def _snapshot_paths(
    *,
    expected_dir: Path,
    fixture_prefix: str,
    snapshot_version: str,
) -> list[Path]:
    """Return expected snapshot paths for the requested fixture subset."""
    if not expected_dir.exists():
        raise ValueError("Expected directory does not exist.")
    if not SAFE_TOKEN_PATTERN.fullmatch(fixture_prefix.rstrip("-")):
        raise ValueError("Fixture prefix must be a bounded token.")
    if not SAFE_TOKEN_PATTERN.fullmatch(snapshot_version):
        raise ValueError("Snapshot version must be a bounded token.")
    pattern = f"{fixture_prefix}*.snapshot_{snapshot_version}.json"
    return sorted(path for path in expected_dir.glob(pattern) if path.is_file())


def _template_row(
    *,
    path: Path,
    observation_row: dict[str, object] | None,
    max_candidates: int,
    snapshot_version: str,
) -> dict[str, object]:
    """Return one safe review template row."""
    snapshot = _read_json_object(path)
    fixture_id = _fixture_id_from_snapshot_name(path.name)
    warnings = _warning_codes(snapshot.get("warnings"))
    current_expected = _ingredient_hints(snapshot.get("ingredients"), max_candidates=max_candidates)
    observation_context = _observation_context(observation_row, max_candidates=max_candidates)
    row = {
        "schema_version": SCHEMA_VERSION,
        "fixture_id": fixture_id,
        "snapshot_name": path.name,
        "snapshot_version": snapshot_version,
        "review_decision_contract": REVIEW_DECISION_CONTRACT,
        "expected_status": {
            "verification_status": _optional_safe_token(snapshot.get("verification_status")),
            "pending_human_review": _is_pending_human_review(snapshot),
            "warning_codes": warnings,
            "current_expected_ingredient_count": len(current_expected),
        },
        "chronic_disease_indications": _safe_token_list(
            snapshot.get("chronic_disease_indications")
        ),
        "current_expected_ingredients": current_expected,
        "observation_context": observation_context,
    }
    _reject_unsafe_payload(row)
    return row


def _read_manifest_rows(path: Path | None) -> dict[str, dict[str, object]]:
    """Read a redacted manifest JSONL keyed by fixture id."""
    if path is None:
        return {}
    rows: dict[str, dict[str, object]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"Manifest line {line_number} must be an object.")
        _reject_unsafe_payload(row)
        fixture_id = row.get("fixture_id")
        if isinstance(fixture_id, str) and fixture_id:
            rows[fixture_id] = row
    return rows


def _observation_row_for_fixture(
    rows: dict[str, dict[str, object]],
    fixture_id: str,
) -> dict[str, object] | None:
    """Return a matching observation row for chronic or live fixture ids."""
    for lookup_id in _observation_lookup_ids(fixture_id):
        row = rows.get(lookup_id)
        if row is not None:
            return row
    return None


def _observation_lookup_ids(fixture_id: str) -> tuple[str, ...]:
    """Return supported observation fixture-id aliases.

    The chronic expected snapshots are named ``naver-chronic-NNNN`` while the
    original live fixture images and observations use ``naver-live-NNNN``.
    """
    if fixture_id.startswith("naver-chronic-"):
        suffix = fixture_id.removeprefix("naver-chronic-")
        return (fixture_id, f"naver-live-{suffix}")
    return (fixture_id,)


def _read_json_object(path: Path) -> dict[str, object]:
    """Read a JSON object and reject raw-data fields."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Snapshot JSON must be an object.")
    _reject_unsafe_payload(payload)
    return payload


def _fixture_id_from_snapshot_name(name: str) -> str:
    """Return fixture id from a snapshot file name."""
    if ".snapshot_" not in name:
        raise ValueError("Snapshot file name must include .snapshot_.")
    fixture_id = name.split(".snapshot_", 1)[0]
    if not SAFE_TOKEN_PATTERN.fullmatch(fixture_id):
        raise ValueError("Snapshot fixture id must be a bounded token.")
    return fixture_id


def _is_pending_human_review(snapshot: dict[str, object]) -> bool:
    """Return whether a snapshot still requires human review."""
    if snapshot.get("verification_status") == "provisional":
        return True
    return bool(PENDING_REVIEW_WARNINGS.intersection(_warning_codes(snapshot.get("warnings"))))


def _warning_codes(value: object) -> list[str]:
    """Return bounded warning code tokens."""
    if not isinstance(value, list):
        return []
    return [
        item
        for item in value
        if isinstance(item, str) and SAFE_TOKEN_PATTERN.fullmatch(item.replace(",", "."))
    ]


def _safe_token_list(value: object) -> list[str]:
    """Return bounded token list."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and SAFE_TOKEN_PATTERN.fullmatch(item)]


def _observation_context(
    row: dict[str, object] | None,
    *,
    max_candidates: int,
) -> dict[str, object]:
    """Return bounded provider observation context for one fixture."""
    if row is None:
        return {
            "observation_count": 0,
            "providers": [],
            "status_counts": {},
            "error_code_counts": {},
            "parser_success_count": 0,
            "ingredient_hints": [],
        }
    observations = row.get("observations")
    if not isinstance(observations, list):
        observations = []
    providers: set[str] = set()
    status_counts: Counter[str] = Counter()
    error_code_counts: Counter[str] = Counter()
    parser_success_count = 0
    ingredient_hints: list[dict[str, object]] = []
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        provider = _optional_safe_token(observation.get("provider"))
        if provider is not None:
            providers.add(provider)
        status = _optional_safe_token(observation.get("status"))
        if status is not None:
            status_counts[status] += 1
        error_code = _optional_safe_token(observation.get("error_code"))
        if error_code is not None:
            error_code_counts[error_code] += 1
        if observation.get("parser_success") is True:
            parser_success_count += 1
        _extend_observation_ingredient_hints(
            ingredient_hints,
            observation.get("parsed_ingredients"),
            provider=provider,
            source="ocr_regex",
            max_candidates=max_candidates,
        )
        _extend_observation_ingredient_hints(
            ingredient_hints,
            observation.get("llm_parsed_ingredients"),
            provider=provider,
            source="ollama_structured",
            max_candidates=max_candidates,
        )
    return {
        "observation_count": len(observations),
        "providers": sorted(providers),
        "status_counts": dict(sorted(status_counts.items())),
        "error_code_counts": dict(sorted(error_code_counts.items())),
        "parser_success_count": parser_success_count,
        "ingredient_hints": ingredient_hints[:max_candidates],
    }


def _extend_observation_ingredient_hints(
    destination: list[dict[str, object]],
    value: object,
    *,
    provider: str | None,
    source: str,
    max_candidates: int,
) -> None:
    """Append bounded observation ingredient hints."""
    if not isinstance(value, list):
        return
    seen_names = {
        (item.get("display_name"), item.get("source"))
        for item in destination
        if isinstance(item, dict)
    }
    for item in value:
        if len(destination) >= max_candidates:
            return
        if not isinstance(item, dict):
            continue
        display_name = _optional_text(
            item.get("display_name") or item.get("normalized_name") or item.get("name")
        )
        if display_name is None or (display_name, source) in seen_names:
            continue
        hint = {
            "display_name": display_name,
            "normalized_name": _optional_text(item.get("normalized_name")),
            "amount": _optional_non_negative_number(item.get("amount")),
            "unit": _optional_text(item.get("unit"), max_length=40),
            "confidence": _optional_confidence(item.get("confidence")),
            "source": source,
            "provider": provider,
        }
        destination.append({key: val for key, val in hint.items() if val is not None})
        seen_names.add((display_name, source))


def _ingredient_hints(value: object, *, max_candidates: int) -> list[dict[str, object]]:
    """Return bounded current expected ingredient hints."""
    if not isinstance(value, list):
        return []
    hints: list[dict[str, object]] = []
    for item in value:
        if len(hints) >= max_candidates:
            break
        if not isinstance(item, dict):
            continue
        display_name = _optional_text(
            item.get("display_name") or item.get("normalized_name") or item.get("name")
        )
        if display_name is None:
            continue
        hint = {
            "display_name": display_name,
            "normalized_name": _optional_text(item.get("normalized_name")),
            "amount": _optional_non_negative_number(item.get("amount")),
            "unit": _optional_text(item.get("unit"), max_length=40),
            "confidence": _optional_confidence(item.get("confidence")),
            "source": _optional_safe_token(item.get("source")),
        }
        hints.append({key: val for key, val in hint.items() if val is not None})
    return hints


def _optional_text(value: object, *, max_length: int = MAX_TEXT_LENGTH) -> str | None:
    """Return a bounded non-path text value."""
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text or len(text) > max_length or _contains_local_path(text):
        return None
    return text


def _optional_safe_token(value: object) -> str | None:
    """Return a bounded token value."""
    if not isinstance(value, str):
        return None
    token = value.strip()
    if not SAFE_TOKEN_PATTERN.fullmatch(token) or _contains_local_path(token):
        return None
    return token


def _optional_non_negative_number(value: object) -> int | float | None:
    """Return a non-negative numeric value."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float) and value >= 0:
        return value
    return None


def _optional_confidence(value: object) -> float | None:
    """Return a bounded confidence value."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float) and 0 <= float(value) <= 1:
        return round(float(value), 4)
    return None


def _candidate_limit(value: int) -> int:
    """Return a safe candidate limit."""
    if value < 1 or value > MAX_CANDIDATES_LIMIT:
        raise ValueError("max-candidates must be between 1 and 50.")
    return value


def _failure_summary(
    *,
    expected_dir: Path,
    manifest_path: Path | None,
    output_path: Path,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted failure summary."""
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "expected_dir_name": expected_dir.name,
        "expected_dir_path_hash": _sha256_text(str(expected_dir.expanduser())),
        "manifest_name": manifest_path.name if manifest_path is not None else None,
        "manifest_path_hash": (
            _sha256_text(str(manifest_path.expanduser())) if manifest_path is not None else None
        ),
        "output_name": output_path.name,
        "output_path_hash": _sha256_text(str(output_path.expanduser())),
        "error_code": type(error).__name__,
        "error_message": _safe_public_error_message(error),
        "row_count": 0,
        "decision_batch_importable": False,
        "requires_human_review": True,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
        "free_text_review_notes_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _safe_public_error_message(error: BaseException) -> str:
    """Return a bounded error message without local paths."""
    message = str(error).strip()
    if not message or _contains_local_path(message) or "/" in message or "\\" in message:
        return "Validation failed."
    return message[:200]


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw keys and local path literals recursively."""
    if isinstance(value, dict):
        forbidden = RAW_FORBIDDEN_KEYS.intersection(str(key).lower() for key in value)
        if forbidden:
            raise ValueError(f"Payload contains forbidden raw field(s): {sorted(forbidden)}")
        for nested in value.values():
            _reject_unsafe_payload(nested)
    elif isinstance(value, list):
        for item in value:
            _reject_unsafe_payload(item)
    elif isinstance(value, str) and _contains_local_path(value):
        raise ValueError("Payload contains local path literal.")


def _contains_local_path(value: str) -> bool:
    """Return whether text contains a local path marker."""
    return any(marker in value for marker in LOCAL_PATH_MARKERS)


def _sha256_text(value: str) -> str:
    """Return SHA-256 hash for redacted path references."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
