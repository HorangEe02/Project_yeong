"""Run sanitized supplement OCR provider smoke requests.

This operator tool posts one local image to `/api/v1/supplements/analyze` for
selected OCR providers and prints JSON lines with provider labels, counts, and
status flags only. It never prints raw OCR text, provider payloads, image bytes,
object URIs, bearer tokens, gateway tokens, or public tunnel URLs.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

DEV_GATEWAY_TOKEN_HEADER = "X-Lemon-Dev-Gateway-Token"
DEFAULT_PROVIDERS = ("configured", "paddleocr", "google_vision", "clova")
OCR_IMAGE_CONSENT = "ocr_image_processing"
EXTERNAL_OCR_CONSENT = "external_ocr_processing"
HTTP_ERROR_STATUS_MIN = 400
CLIENT_REQUEST_ID_MAX_LENGTH = 80
CLIENT_REQUEST_RANDOM_HEX_LENGTH = 12


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument(
        "--providers",
        default=",".join(DEFAULT_PROVIDERS),
        help="Comma-separated provider selectors.",
    )
    parser.add_argument("--client-request-prefix", default="ocr-smoke")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument(
        "--grant-consents",
        action="store_true",
        help="Grant OCR/external OCR consents for AUTH_MODE=disabled local smoke.",
    )
    parser.add_argument("--gateway-token-env", default="LEMON_DEV_GATEWAY_TOKEN")
    parser.add_argument("--bearer-token-env", default="LEMON_API_TOKEN")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run provider smoke requests and print sanitized JSON lines.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code. Returns 1 when any provider request fails before a
        preview response is produced.
    """
    args = parse_args(argv)
    providers = parse_providers(args.providers)
    image_path = args.image.expanduser().resolve()
    if not image_path.is_file():
        raise SystemExit(f"image is not a file: {image_path}")

    headers = build_headers(
        gateway_token_env=args.gateway_token_env,
        bearer_token_env=args.bearer_token_env,
    )
    api_base_url = args.api_base_url.rstrip("/")
    exit_code = 0
    with httpx.Client(timeout=args.timeout_seconds, headers=headers) as client:
        if args.grant_consents:
            consent_summary = grant_required_consents(client, api_base_url)
            print(json.dumps(consent_summary, ensure_ascii=False, sort_keys=True))
        for provider in providers:
            summary = run_provider_smoke(
                client=client,
                api_base_url=api_base_url,
                image_path=image_path,
                provider=provider,
                client_request_prefix=args.client_request_prefix,
            )
            if (
                int(summary.get("http_status", 0) or 0) >= HTTP_ERROR_STATUS_MIN
                or "exception_class" in summary
            ):
                exit_code = 1
            print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return exit_code


def parse_providers(value: str) -> tuple[str, ...]:
    """Parse and validate provider selectors.

    Args:
        value: Comma-separated provider selector string.

    Returns:
        Provider selectors in request order.

    Raises:
        SystemExit: If an unsupported provider selector is present.
    """
    providers = tuple(token.strip() for token in value.split(",") if token.strip())
    unsupported = sorted(set(providers).difference(DEFAULT_PROVIDERS))
    if unsupported:
        raise SystemExit(f"unsupported providers: {', '.join(unsupported)}")
    return providers


def build_headers(*, gateway_token_env: str, bearer_token_env: str) -> dict[str, str]:
    """Build request headers from environment variables without printing values.

    Args:
        gateway_token_env: Environment variable containing the dev gateway token.
        bearer_token_env: Environment variable containing an optional bearer token.

    Returns:
        HTTP headers for smoke requests.
    """
    headers: dict[str, str] = {}
    gateway_token = os.environ.get(gateway_token_env, "").strip()
    bearer_token = os.environ.get(bearer_token_env, "").strip()
    if gateway_token:
        headers[DEV_GATEWAY_TOKEN_HEADER] = gateway_token
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    return headers


def grant_required_consents(client: httpx.Client, api_base_url: str) -> dict[str, object]:
    """Grant local smoke consents and return only status codes.

    Args:
        client: HTTP client.
        api_base_url: API base URL ending in `/api/v1`.

    Returns:
        Sanitized consent status summary.
    """
    statuses: dict[str, int | None] = {}
    for consent in (OCR_IMAGE_CONSENT, EXTERNAL_OCR_CONSENT):
        try:
            response = client.post(f"{api_base_url}/me/privacy/consents/{consent}")
            statuses[consent] = int(response.status_code)
        except httpx.HTTPError:
            statuses[consent] = None
    return {"type": "consent_grants", "statuses": statuses}


def run_provider_smoke(
    *,
    client: httpx.Client,
    api_base_url: str,
    image_path: Path,
    provider: str,
    client_request_prefix: str,
) -> dict[str, object]:
    """Post one image to the supplement analyze endpoint.

    Args:
        client: HTTP client.
        api_base_url: API base URL ending in `/api/v1`.
        image_path: Local image path. The bytes are sent but never printed.
        provider: OCR provider selector.
        client_request_prefix: Prefix for the idempotency key.

    Returns:
        Sanitized provider smoke summary.
    """
    summary: dict[str, object] = {"type": "provider_smoke", "requested_provider": provider}
    try:
        with image_path.open("rb") as image_file:
            response = client.post(
                f"{api_base_url}/supplements/analyze",
                data={
                    "client_request_id": build_client_request_id(
                        client_request_prefix,
                        provider,
                    ),
                    "ocr_provider": provider,
                },
                files={"image": (image_path.name, image_file, content_type_for_path(image_path))},
            )
    except OSError as exc:
        summary["exception_class"] = exc.__class__.__name__
        return summary
    except httpx.HTTPError as exc:
        summary["exception_class"] = exc.__class__.__name__
        return summary

    summary["http_status"] = int(response.status_code)
    body = parse_json_object(response)
    if response.status_code >= HTTP_ERROR_STATUS_MIN:
        summary.update(summarize_error(body))
        return summary
    summary.update(summarize_preview(body))
    return summary


def build_client_request_id(client_request_prefix: str, provider: str) -> str:
    """Build a route-safe client request id for one smoke request.

    Args:
        client_request_prefix: Operator-provided smoke prefix.
        provider: OCR provider selector.

    Returns:
        Client request id capped to the API field length.
    """
    normalized_prefix = client_request_prefix.strip() or "ocr-smoke"
    request_token = uuid4().hex[:CLIENT_REQUEST_RANDOM_HEX_LENGTH]
    suffix = f"{provider}-{request_token}"
    max_prefix_length = max(CLIENT_REQUEST_ID_MAX_LENGTH - len(suffix) - 1, 0)
    prefix = normalized_prefix[:max_prefix_length].strip("-") or "ocr"
    return f"{prefix}-{suffix}"[:CLIENT_REQUEST_ID_MAX_LENGTH]


def parse_json_object(response: httpx.Response) -> dict[str, Any]:
    """Parse a JSON object response safely.

    Args:
        response: HTTP response.

    Returns:
        JSON object, or an empty object when parsing fails or the top-level shape differs.
    """
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def summarize_error(body: dict[str, Any]) -> dict[str, object]:
    """Summarize an API error without echoing raw details.

    Args:
        body: Parsed JSON object response.

    Returns:
        Sanitized error summary.
    """
    detail = body.get("detail")
    if isinstance(detail, dict):
        return {
            "error_code": detail.get("code"),
            "requested_ocr_provider": detail.get("requested_ocr_provider"),
        }
    return {"error_shape": detail.__class__.__name__}


def summarize_preview(body: dict[str, Any]) -> dict[str, object]:
    """Summarize a supplement analysis preview without raw OCR text.

    Args:
        body: Parsed preview response.

    Returns:
        Sanitized preview summary.
    """
    metadata = body.get("pipeline_metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "preview_status": body.get("status"),
        "ocr_provider": metadata.get("ocr_provider"),
        "llm_parser_used": metadata.get("llm_parser_used"),
        "vision_roi_used": metadata.get("vision_roi_used"),
        "ingredient_count": count_list(body.get("ingredient_candidates")),
        "section_count": count_list(body.get("label_sections")),
        "warning_count": count_list(body.get("warnings")),
        "layout_available": body.get("layout_available"),
        "action_required": body.get("action_required"),
    }


def count_list(value: object) -> int:
    """Return the length of a list-like JSON field.

    Args:
        value: Candidate JSON value.

    Returns:
        List length, or 0 when the value is not a list.
    """
    return len(value) if isinstance(value, list) else 0


def content_type_for_path(path: Path) -> str:
    """Return the accepted image content type for a local path.

    Args:
        path: Image path.

    Returns:
        MIME type used for multipart upload.
    """
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


if __name__ == "__main__":
    raise SystemExit(main())
