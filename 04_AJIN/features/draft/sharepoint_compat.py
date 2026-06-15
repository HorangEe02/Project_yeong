"""Microsoft Graph request-shape checks for SharePoint draft export uploads.

This module does not perform network I/O and never handles Microsoft Graph
tokens. It only prepares and validates the request shape that a future adapter
can send after operational approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import quote


SMALL_UPLOAD_MAX_BYTES = 250 * 1024 * 1024
UPLOAD_SESSION_CHUNK_GRANULARITY = 320 * 1024
UPLOAD_SESSION_MAX_CHUNK_BYTES = 60 * 1024 * 1024


@dataclass(frozen=True)
class SharePointUploadRequest:
    """Offline Microsoft Graph upload request description.

    Args:
        mode: ``single_put`` for small uploads or ``upload_session`` for large files.
        method: HTTP method to use.
        path: Microsoft Graph v1.0 path without host.
        headers: Secret-free request headers.
        json_body: Optional JSON body for upload-session creation.
        chunk_size_bytes: Optional chunk size for upload-session PUT requests.
    """

    mode: Literal["single_put", "upload_session"]
    method: Literal["PUT", "POST"]
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    json_body: dict[str, Any] | None = None
    chunk_size_bytes: int | None = None


def _require_graph_segment(value: str, name: str) -> str:
    """Validate a path segment used in a Graph request.

    Args:
        value: Segment value.
        name: Human-readable field name for errors.

    Returns:
        str: Stripped segment value.

    Raises:
        ValueError: If the segment is empty or contains path separators.
    """

    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"{name}_required")
    if "/" in cleaned or "\\" in cleaned:
        raise ValueError(f"{name}_invalid_path_segment")
    return cleaned


def validate_upload_session_chunk_size(chunk_size_bytes: int) -> None:
    """Validate the Microsoft Graph upload-session chunk size rule.

    Args:
        chunk_size_bytes: Proposed chunk size.

    Raises:
        ValueError: If the chunk size is not a positive 320KiB multiple or exceeds 60MiB.
    """

    if chunk_size_bytes <= 0:
        raise ValueError("chunk_size_must_be_positive")
    if chunk_size_bytes > UPLOAD_SESSION_MAX_CHUNK_BYTES:
        raise ValueError("chunk_size_exceeds_60mib")
    if chunk_size_bytes % UPLOAD_SESSION_CHUNK_GRANULARITY != 0:
        raise ValueError("chunk_size_must_be_320kib_multiple")


def plan_sharepoint_upload(
    *,
    drive_id: str,
    parent_id: str,
    filename: str,
    size_bytes: int,
    content_type: str,
    conflict_behavior: Literal["fail", "replace", "rename"] = "fail",
    chunk_size_bytes: int = 10 * 1024 * 1024,
) -> SharePointUploadRequest:
    """Build an offline Microsoft Graph upload request shape.

    Args:
        drive_id: Microsoft Graph drive id.
        parent_id: Parent driveItem id.
        filename: Destination filename.
        size_bytes: File size in bytes.
        content_type: MIME type to use for small upload PUT.
        conflict_behavior: Microsoft Graph conflict behavior.
        chunk_size_bytes: Upload-session chunk size for large files.

    Returns:
        SharePointUploadRequest: Secret-free request metadata.

    Raises:
        ValueError: If required fields or upload-session chunk size are invalid.
    """

    drive = _require_graph_segment(drive_id, "drive_id")
    parent = _require_graph_segment(parent_id, "parent_id")
    name = _require_graph_segment(filename, "filename")
    if size_bytes < 0:
        raise ValueError("size_bytes_must_be_non_negative")
    mime = (content_type or "").strip() or "application/octet-stream"
    quoted_name = quote(name, safe="")

    if size_bytes <= SMALL_UPLOAD_MAX_BYTES:
        return SharePointUploadRequest(
            mode="single_put",
            method="PUT",
            path=f"/drives/{drive}/items/{parent}:/{quoted_name}:/content",
            headers={"Content-Type": mime},
        )

    validate_upload_session_chunk_size(chunk_size_bytes)
    return SharePointUploadRequest(
        mode="upload_session",
        method="POST",
        path=f"/drives/{drive}/items/{parent}:/{quoted_name}:/createUploadSession",
        headers={"Content-Type": "application/json"},
        json_body={
            "item": {
                "@microsoft.graph.conflictBehavior": conflict_behavior,
                "name": name,
                "fileSize": size_bytes,
            }
        },
        chunk_size_bytes=chunk_size_bytes,
    )

