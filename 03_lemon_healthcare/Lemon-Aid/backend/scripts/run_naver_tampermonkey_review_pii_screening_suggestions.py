"""Run local Ollama vision PII screening suggestions for Naver review images.

This runner reads the local-only review PII screening manifest, sends review
images only to a localhost Ollama Chat API, and writes model-generated
suggestions in the non-importable suggestion input schema. It does not write raw
image bytes, raw model responses, request payloads, local paths, free-text notes,
operator decisions, or reviewer attestations.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts import (  # noqa: E402
    build_naver_tampermonkey_review_pii_screening_manifest as pii_manifest,
)
from scripts import (  # noqa: E402
    export_naver_tampermonkey_review_pii_screening_suggestions as suggestion_exporter,
)

SCHEMA_VERSION = "naver-tampermonkey-review-pii-screening-suggestion-run-v1"
SUGGESTION_INPUT_FIELD = suggestion_exporter.SUGGESTION_FIELD
EXPECTED_MANIFEST_SCHEMA_VERSION = pii_manifest.SCHEMA_VERSION
DEFAULT_MODEL = "gemma4:e4b"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
LOCAL_OLLAMA_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
ALLOWED_IMAGE_PATH_ENV_VARS = frozenset({"NAVER_TAMPERMONKEY_SOURCE_ROOT"})
ENV_IMAGE_PATH_PATTERN = re.compile(r"^\$(?P<name>[A-Z][A-Z0-9_]*)(?:/(?P<path>.*))?$")
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
RAW_FORBIDDEN_KEYS = pii_manifest.RAW_FORBIDDEN_KEYS
MAX_IMAGE_BYTES = 15_000_000
MAX_ROWS_DEFAULT = 0
MAX_UNCONFIRMED_RUN_ROWS = 100

STATUS_SUGGESTIONS = tuple(sorted(suggestion_exporter.ALLOWED_SUGGESTION_STATUSES))
CONFIDENCE_BUCKETS = tuple(sorted(suggestion_exporter.ALLOWED_CONFIDENCE_BUCKETS))
EVIDENCE_CODE_OPTIONS = (
    "face_visible",
    "name_visible",
    "order_or_receipt_visible",
    "phone_or_address_visible",
    "product_only",
    "profile_or_account_visible",
    "uncertain",
    "unreadable",
)
REASON_CODE_OPTIONS = (
    "likely_product_only",
    "possible_personal_data_visible",
    "operator_required",
    "image_unreadable",
    "local_model_uncertain",
)
ALLOWED_MODEL_RESPONSE_KEYS = frozenset(
    {
        "status_suggestion",
        "confidence_bucket",
        "evidence_codes",
        "reason_codes",
    }
)

SYSTEM_PROMPT = """
You are a local privacy screening assistant for supplement review images.
Classify whether the image appears safe for a human/operator to review for OCR
handoff. Do not transcribe visible text. Do not output names, phone numbers,
addresses, order numbers, account handles, or any other personal data. Do not
make medical, nutrition, product, or purchase recommendations. Return only JSON
matching the provided schema.
""".strip()

USER_PROMPT = """
Screen this review image for possible personal data. Use only the allowed enum
values in the JSON schema. If uncertain, choose needs_operator_review with low
confidence and reason_codes including operator_required. Never include OCR text,
personal data, explanations, or free-text notes.
""".strip()


class _HTTPResponse(Protocol):
    """Small response protocol used by the runner."""

    def raise_for_status(self) -> Any:
        """Raise when the HTTP response is unsuccessful."""

    def json(self) -> Any:
        """Return decoded JSON."""


class _PostClient(Protocol):
    """Small HTTP client protocol for tests and real Ollama calls."""

    def post(
        self,
        url: str,
        *,
        json: Mapping[str, Any],
        timeout: float,
    ) -> _HTTPResponse:
        """Submit a JSON POST request."""


@dataclass(frozen=True)
class RunResult:
    """In-memory result for a PII suggestion run."""

    rows: list[dict[str, object]]
    summary: dict[str, object]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for local Ollama PII suggestion generation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Optional summary JSON path. Defaults to <output>.summary.json.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--ollama-base-url", default=DEFAULT_OLLAMA_BASE_URL)
    parser.add_argument("--timeout-sec", type=float, default=120.0)
    parser.add_argument(
        "--limit",
        type=int,
        default=MAX_ROWS_DEFAULT,
        help="Maximum rows to process. Use 0 to process every manifest row.",
    )
    parser.add_argument("--max-image-bytes", type=int, default=MAX_IMAGE_BYTES)
    parser.add_argument(
        "--allow-large-run",
        action="store_true",
        help=("Required for non-dry-run processing above " f"{MAX_UNCONFIRMED_RUN_ROWS} rows."),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run local Ollama PII suggestions and write redacted artifacts."""
    args = parse_args()
    output_path = args.output.expanduser().resolve()
    summary_path = (
        args.summary.expanduser().resolve()
        if args.summary
        else output_path.with_suffix(output_path.suffix + ".summary.json")
    )
    try:
        result = run_review_pii_screening_suggestions(
            manifest_path=args.manifest.expanduser().resolve(),
            model=args.model,
            ollama_base_url=args.ollama_base_url,
            timeout_sec=args.timeout_sec,
            limit=args.limit,
            max_image_bytes=args.max_image_bytes,
            allow_large_run=args.allow_large_run,
            dry_run=args.dry_run,
        )
    except (httpx.HTTPError, OSError, ValueError) as exc:
        failure = _failure_summary(
            manifest_path=args.manifest,
            model=args.model,
            ollama_base_url=args.ollama_base_url,
            error=exc,
        )
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in result.rows),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True))


def run_review_pii_screening_suggestions(
    *,
    manifest_path: Path,
    model: str = DEFAULT_MODEL,
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL,
    timeout_sec: float = 120.0,
    limit: int = MAX_ROWS_DEFAULT,
    max_image_bytes: int = MAX_IMAGE_BYTES,
    allow_large_run: bool = False,
    dry_run: bool = False,
    http_client: _PostClient | None = None,
) -> RunResult:
    """Generate non-importable PII screening suggestions with local Ollama.

    Args:
        manifest_path: Local-only review PII screening manifest.
        model: Local Ollama vision model tag.
        ollama_base_url: Ollama API base URL. Must point to localhost.
        timeout_sec: HTTP timeout per image.
        limit: Maximum manifest rows to process; ``0`` means all rows.
        max_image_bytes: Per-image byte ceiling.
        allow_large_run: Explicit approval for non-dry-run batches above the
            unconfirmed row threshold.
        dry_run: Whether to build only the redacted plan.
        http_client: Optional sync test client.

    Returns:
        Generated safe suggestion rows and summary.

    Raises:
        ValueError: If runtime settings, manifest rows, or model output violate
            the local-only privacy contract.
    """
    _validate_runner_options(
        model=model,
        ollama_base_url=ollama_base_url,
        timeout_sec=timeout_sec,
        limit=limit,
        max_image_bytes=max_image_bytes,
    )
    manifest_rows = _read_manifest_rows(manifest_path)
    selected_rows = manifest_rows if limit == 0 else manifest_rows[:limit]
    _validate_large_run_approval(
        selected_row_count=len(selected_rows),
        allow_large_run=allow_large_run,
        dry_run=dry_run,
    )
    endpoint = _ollama_endpoint(ollama_base_url)
    schema = _suggestion_response_schema()
    rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    error_counts: Counter[str] = Counter()

    if dry_run:
        summary = _summary(
            manifest_path=manifest_path,
            model=model,
            ollama_base_url=ollama_base_url,
            manifest_rows=manifest_rows,
            selected_rows=selected_rows,
            rows=rows,
            status_counts=status_counts,
            error_counts=error_counts,
            dry_run=True,
            allow_large_run=allow_large_run,
        )
        return RunResult(rows=rows, summary=summary)

    active_client = http_client or httpx.Client()
    should_close = http_client is None
    try:
        for manifest_row in selected_rows:
            image_bytes = _read_token_image_bytes(
                _required_str(manifest_row, "image_path"),
                max_image_bytes=max_image_bytes,
            )
            suggestion = _call_ollama_for_suggestion(
                client=active_client,
                endpoint=endpoint,
                model=model,
                image_bytes=image_bytes,
                schema=schema,
                timeout_sec=timeout_sec,
            )
            status_counts[str(suggestion["status_suggestion"])] += 1
            rows.append(
                {
                    "fixture_id": _required_str(manifest_row, "fixture_id"),
                    SUGGESTION_INPUT_FIELD: suggestion,
                }
            )
    except (httpx.HTTPError, ValueError, OSError) as exc:
        error_counts[_safe_error_code(exc)] += 1
        raise
    finally:
        if should_close:
            active_client.close()

    _reject_unsafe_payload(rows)
    summary = _summary(
        manifest_path=manifest_path,
        model=model,
        ollama_base_url=ollama_base_url,
        manifest_rows=manifest_rows,
        selected_rows=selected_rows,
        rows=rows,
        status_counts=status_counts,
        error_counts=error_counts,
        dry_run=False,
        allow_large_run=allow_large_run,
    )
    _reject_unsafe_payload(summary)
    return RunResult(rows=rows, summary=summary)


def _call_ollama_for_suggestion(
    *,
    client: _PostClient,
    endpoint: str,
    model: str,
    image_bytes: bytes,
    schema: dict[str, object],
    timeout_sec: float,
) -> dict[str, object]:
    """Call local Ollama and return a safe suggestion input object."""
    payload = _ollama_payload(
        model=model,
        image_bytes=image_bytes,
        schema=schema,
    )
    response = client.post(endpoint, json=payload, timeout=timeout_sec)
    response.raise_for_status()
    decoded = response.json()
    content = _extract_ollama_message_content(decoded)
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("Ollama PII suggestion response must be a JSON object.")
    _reject_unsafe_payload(parsed)
    _reject_unexpected_model_response_keys(parsed)
    suggestion = {
        "model_id": model,
        "generated_at": datetime.now(UTC).isoformat(),
        "status_suggestion": _required_choice(
            parsed,
            "status_suggestion",
            allowed=suggestion_exporter.ALLOWED_SUGGESTION_STATUSES,
        ),
        "confidence_bucket": _required_choice(
            parsed,
            "confidence_bucket",
            allowed=suggestion_exporter.ALLOWED_CONFIDENCE_BUCKETS,
        ),
        "evidence_codes": _safe_token_list(parsed.get("evidence_codes")),
        "reason_codes": _safe_token_list(parsed.get("reason_codes")),
    }
    suggestion_exporter._validate_suggestion(suggestion)
    return suggestion


def _ollama_payload(
    *,
    model: str,
    image_bytes: bytes,
    schema: dict[str, object],
) -> dict[str, object]:
    """Build a local Ollama Chat API payload without persisting it."""
    image_payload = base64.b64encode(image_bytes).decode("ascii")
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT, "images": [image_payload]},
        ],
        "stream": False,
        "think": False,
        "format": schema,
        "options": {"temperature": 0},
    }


def _summary(
    *,
    manifest_path: Path,
    model: str,
    ollama_base_url: str,
    manifest_rows: Sequence[dict[str, object]],
    selected_rows: Sequence[dict[str, object]],
    rows: Sequence[dict[str, object]],
    status_counts: Counter[str],
    error_counts: Counter[str],
    dry_run: bool,
    allow_large_run: bool,
) -> dict[str, object]:
    """Return a redacted run summary."""
    parsed = urlparse(ollama_base_url)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "manifest_name": manifest_path.name,
        "manifest_row_count": len(manifest_rows),
        "selected_row_count": len(selected_rows),
        "suggestion_row_count": len(rows),
        "dry_run": dry_run,
        "large_run_threshold": MAX_UNCONFIRMED_RUN_ROWS,
        "large_run_approved": allow_large_run,
        "model": model,
        "ollama_base_host": parsed.hostname or "",
        "status_suggestion_counts": dict(sorted(status_counts.items())),
        "error_counts": dict(sorted(error_counts.items())),
        "decision_importable_rows": 0,
        "operator_decision_required_rows": len(rows),
        "external_transfer_allowed_rows": 0,
        "db_write_performed": False,
        "external_transfer_performed": False,
        "raw_artifacts_stored": False,
        "raw_image_stored": False,
        "request_payload_stored": False,
        "raw_model_response_stored": False,
        "free_text_notes_stored": False,
        "local_path_literals_stored": False,
    }


def _failure_summary(
    *,
    manifest_path: Path,
    model: str,
    ollama_base_url: str,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted failure summary for CLI errors."""
    parsed = urlparse(ollama_base_url)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "manifest_name": manifest_path.name,
        "model": model,
        "ollama_base_host": parsed.hostname or "",
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "suggestion_row_count": 0,
        "decision_importable_rows": 0,
        "operator_decision_required_rows": 0,
        "external_transfer_allowed_rows": 0,
        "db_write_performed": False,
        "external_transfer_performed": False,
        "raw_artifacts_stored": False,
        "raw_image_stored": False,
        "request_payload_stored": False,
        "raw_model_response_stored": False,
        "free_text_notes_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _read_manifest_rows(path: Path) -> list[dict[str, object]]:
    """Read local-only review PII screening manifest rows."""
    rows = _read_jsonl_objects(path)
    for row in rows:
        if row.get("schema_version") != EXPECTED_MANIFEST_SCHEMA_VERSION:
            raise ValueError("PII screening manifest rows use an unsupported schema.")
        if row.get("section") != "review" or row.get("external_transfer_allowed") is not False:
            raise ValueError("PII screening rows must remain local-only review rows.")
        if row.get("local_processing_allowed") is not True:
            raise ValueError("PII screening rows must allow local processing.")
        _required_str(row, "fixture_id")
        _required_str(row, "image_path")
    return rows


def _read_jsonl_objects(path: Path) -> list[dict[str, object]]:
    """Read JSONL object rows and reject unsafe payloads."""
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("JSONL rows must be objects.")
        _reject_unsafe_payload(row)
        rows.append(row)
    return rows


def _read_token_image_bytes(image_path: str, *, max_image_bytes: int) -> bytes:
    """Resolve a tokenized local image path and read bounded bytes."""
    resolved = _resolve_token_image_path(image_path)
    size_bytes = resolved.stat().st_size
    if size_bytes <= 0 or size_bytes > max_image_bytes:
        raise ValueError("Review image size is outside the local processing bounds.")
    return resolved.read_bytes()


def _resolve_token_image_path(image_path: str) -> Path:
    """Resolve an allowlisted env-token image path under its source root."""
    match = ENV_IMAGE_PATH_PATTERN.fullmatch(image_path)
    if not match or match.group("name") not in ALLOWED_IMAGE_PATH_ENV_VARS:
        raise ValueError("Review image_path must use an allowlisted env token.")
    env_root = os.environ.get(match.group("name"))
    if not env_root:
        raise ValueError("Review image root env is not set.")
    relative_path = PurePosixPath(match.group("path") or "")
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError("Review image path must stay under token root.")
    root = Path(env_root).expanduser().resolve()
    resolved = (root / Path(*relative_path.parts)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Review image path resolves outside token root.") from exc
    if not resolved.is_file():
        raise ValueError("Review image file is missing.")
    return resolved


def _extract_ollama_message_content(value: object) -> str:
    """Extract message content from an Ollama Chat API response object."""
    if not isinstance(value, Mapping):
        raise ValueError("Local Ollama response must be a JSON object.")
    message = value.get("message")
    if not isinstance(message, Mapping):
        raise ValueError("Local Ollama response is missing message.")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Local Ollama response content is empty.")
    _reject_unsafe_payload(content)
    return content


def _validate_runner_options(
    *,
    model: str,
    ollama_base_url: str,
    timeout_sec: float,
    limit: int,
    max_image_bytes: int,
) -> None:
    """Validate runner options before reading image bytes."""
    _safe_token(model)
    parsed = urlparse(ollama_base_url)
    if parsed.scheme != "http" or parsed.hostname not in LOCAL_OLLAMA_HOSTS:
        raise ValueError("Ollama PII screening must use a localhost HTTP base URL.")
    if timeout_sec <= 0:
        raise ValueError("timeout_sec must be positive.")
    if limit < 0:
        raise ValueError("limit must be zero or positive.")
    if max_image_bytes <= 0:
        raise ValueError("max_image_bytes must be positive.")


def _validate_large_run_approval(
    *,
    selected_row_count: int,
    allow_large_run: bool,
    dry_run: bool,
) -> None:
    """Require an explicit operator opt-in before large non-dry-run batches."""
    if dry_run or allow_large_run or selected_row_count <= MAX_UNCONFIRMED_RUN_ROWS:
        return
    raise ValueError("Large PII suggestion runs require --allow-large-run or a smaller --limit.")


def _ollama_endpoint(base_url: str) -> str:
    """Return the local Ollama Chat endpoint."""
    return f"{base_url.rstrip('/')}/api/chat"


def _suggestion_response_schema() -> dict[str, object]:
    """Return JSON Schema for the local model response."""
    token_array_schema = {
        "type": "array",
        "items": {"type": "string", "enum": list(EVIDENCE_CODE_OPTIONS)},
        "maxItems": 8,
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status_suggestion": {"type": "string", "enum": list(STATUS_SUGGESTIONS)},
            "confidence_bucket": {"type": "string", "enum": list(CONFIDENCE_BUCKETS)},
            "evidence_codes": token_array_schema,
            "reason_codes": {
                "type": "array",
                "items": {"type": "string", "enum": list(REASON_CODE_OPTIONS)},
                "maxItems": 8,
            },
        },
        "required": [
            "status_suggestion",
            "confidence_bucket",
            "evidence_codes",
            "reason_codes",
        ],
    }


def _required_choice(
    row: dict[str, object],
    key: str,
    *,
    allowed: frozenset[str],
) -> str:
    """Return a required safe token from an allowed set."""
    value = _required_safe_token(row, key)
    if value not in allowed:
        raise ValueError(f"Unsupported PII suggestion {key}: {value}")
    return value


def _reject_unexpected_model_response_keys(row: dict[str, object]) -> None:
    """Reject model output fields outside the suggestion schema."""
    unexpected = sorted({str(key).lower() for key in row} - ALLOWED_MODEL_RESPONSE_KEYS)
    if unexpected:
        raise ValueError(
            f"Ollama PII suggestion response contains unsupported field: {unexpected[0]}"
        )


def _required_str(row: Mapping[str, object], key: str) -> str:
    """Return a required bounded string field."""
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Row requires string field: {key}")
    stripped = value.strip()
    if any(marker in stripped for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
    return stripped


def _required_safe_token(row: dict[str, object], key: str) -> str:
    """Return a required safe token field."""
    token = _safe_token(row.get(key))
    if token is None:
        raise ValueError(f"Row requires safe token field: {key}")
    return token


def _safe_token(value: object) -> str | None:
    """Return a bounded token or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    stripped = value.strip()
    if any(marker in stripped for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")
    if not SAFE_TOKEN_PATTERN.fullmatch(stripped):
        raise ValueError(f"Unsafe token value: {stripped[:80]}")
    return stripped


def _safe_token_list(value: object) -> list[str]:
    """Return a safe token list."""
    if not isinstance(value, list):
        raise ValueError("Token lists must be arrays.")
    tokens: list[str] = []
    seen: set[str] = set()
    for item in value:
        token = _safe_token(item)
        if token is None:
            raise ValueError("Token lists require non-empty safe string values.")
        if token in seen:
            continue
        tokens.append(token)
        seen.add(token)
    return tokens


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw keys, product directory literals, and local paths."""
    if isinstance(value, dict):
        keys = {str(key).lower() for key in value}
        forbidden = RAW_FORBIDDEN_KEYS.intersection(keys)
        if forbidden:
            raise ValueError(f"Payload contains forbidden raw field(s): {sorted(forbidden)}")
        if "product_dir" in keys:
            raise ValueError("Payload must not store product_dir literals.")
        for nested in value.values():
            _reject_unsafe_payload(nested)
    elif isinstance(value, list | tuple):
        for item in value:
            _reject_unsafe_payload(item)
    elif isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")


def _safe_error_code(exc: BaseException) -> str:
    """Return a non-sensitive error code for summaries."""
    if isinstance(exc, httpx.HTTPStatusError):
        return "ollama_http_status_error"
    if isinstance(exc, httpx.HTTPError):
        return "ollama_client_error"
    if isinstance(exc, OSError):
        return "local_image_read_error"
    return "validation_error"


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a bounded public error message without filesystem details."""
    if isinstance(exc, httpx.HTTPError):
        return "Local Ollama request failed."
    if isinstance(exc, OSError):
        return "Local image read failed."
    message = str(exc).strip()
    if not message:
        return "Validation failed."
    if any(marker in message for marker in LOCAL_PATH_MARKERS):
        return "Validation failed."
    if "/" in message or "\\" in message:
        return "Validation failed."
    return message[:200]


if __name__ == "__main__":
    main()
