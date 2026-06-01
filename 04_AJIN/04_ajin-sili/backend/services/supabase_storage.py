"""Supabase Storage signed URL helpers.

브라우저에 service role key를 노출하지 않기 위해 FastAPI가 signed upload
URL과 signed download URL을 발급하고, 업로드 메타데이터는 `attachments`
테이블에 기록한다.
"""

from __future__ import annotations

import os
import posixpath
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa

from core.data_lineage import lineage_values
from core.db import create_sqlalchemy_engine

_METADATA = sa.MetaData()

_ATTACHMENTS = sa.Table(
    "attachments",
    _METADATA,
    sa.Column("id", sa.String(80), primary_key=True),
    sa.Column("employee_id", sa.String(80), nullable=False),
    sa.Column("bucket", sa.String(120), nullable=False),
    sa.Column("object_path", sa.Text, nullable=False),
    sa.Column("content_type", sa.String(160), nullable=False, server_default=""),
    sa.Column("size_bytes", sa.Integer, nullable=False, server_default="0"),
    sa.Column("metadata", sa.JSON, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("data_class", sa.String(32), nullable=False, server_default="real"),
    sa.Column("source_system", sa.String(80), nullable=False, server_default="supabase_storage"),
    sa.Column("source_label", sa.String(255), nullable=False, server_default=""),
    sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
)


@dataclass(frozen=True)
class SupabaseStorageSettings:
    """Supabase Storage runtime settings.

    Attributes:
        url: Supabase project URL.
        service_key: Secret key used only by the backend.
        attachments_bucket: Private bucket for user attachments.
        draft_exports_bucket: Private bucket for draft exports.
    """

    url: str
    service_key: str
    attachments_bucket: str
    draft_exports_bucket: str


@dataclass(frozen=True)
class StorageObjectMetadata:
    """Normalized Supabase Storage object metadata.

    Attributes:
        size_bytes: Object size in bytes when Supabase exposes it.
        content_type: Object MIME type when Supabase exposes it.
        raw: Original Storage object metadata item for troubleshooting.
    """

    size_bytes: int | None
    content_type: str
    raw: dict[str, Any]


def get_storage_settings(required: bool = False) -> SupabaseStorageSettings:
    """Load Supabase Storage settings.

    Args:
        required: Raise if the project URL or secret key is missing.

    Returns:
        SupabaseStorageSettings: Runtime Storage settings.

    Raises:
        RuntimeError: When required settings are missing.
    """
    settings = SupabaseStorageSettings(
        url=os.getenv("SUPABASE_URL", "").strip().rstrip("/"),
        service_key=os.getenv("SUPABASE_SECRET_KEY", "").strip(),
        attachments_bucket=os.getenv(
            "SUPABASE_STORAGE_BUCKET_ATTACHMENTS",
            "ajin-attachments",
        ).strip(),
        draft_exports_bucket=os.getenv(
            "SUPABASE_STORAGE_BUCKET_DRAFT_EXPORTS",
            "ajin-draft-exports",
        ).strip(),
    )
    if required and (not settings.url or not settings.service_key):
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
    return settings


def bucket_for_type(bucket_type: str) -> str:
    """Resolve a logical bucket type to a Supabase bucket name.

    Args:
        bucket_type: `attachments` or `draft_exports`.

    Returns:
        str: Supabase Storage bucket name.

    Raises:
        ValueError: If the bucket type is unsupported.
    """
    settings = get_storage_settings(required=True)
    if bucket_type == "attachments":
        return settings.attachments_bucket
    if bucket_type == "draft_exports":
        return settings.draft_exports_bucket
    raise ValueError("bucket_type must be attachments or draft_exports")


def _client():
    """Create a Supabase Python client lazily.

    Raises:
        RuntimeError: If `supabase-py` is not installed or settings are missing.
    """
    settings = get_storage_settings(required=True)
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError("supabase package is required for Storage signed URLs") from exc
    return create_client(settings.url, settings.service_key)


def _engine():
    """Create the configured application DB engine."""
    return create_sqlalchemy_engine()


def _ensure_sqlite_table(engine) -> None:
    """Create fallback SQLite table for local development and tests.

    Args:
        engine: SQLAlchemy engine returned by `core.db`.
    """
    if engine.dialect.name == "sqlite":
        _METADATA.create_all(engine, tables=[_ATTACHMENTS])


def _safe_segment(value: str, fallback: str) -> str:
    """Return a path-safe segment."""
    cleaned = re.sub(r"[^A-Za-z0-9._=-]+", "_", value.strip())
    return cleaned.strip("._/") or fallback


def build_object_path(*, employee_id: str, prefix: str, file_name: str) -> str:
    """Build a safe object path relative to the target bucket.

    Args:
        employee_id: Current user or employee id.
        prefix: Logical folder such as `uploads` or `images`.
        file_name: Original file name.

    Returns:
        str: Bucket-relative object path.
    """
    date_part = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    safe_prefix = _safe_segment(prefix, "uploads")
    safe_employee = _safe_segment(employee_id, "anonymous")
    safe_name = _safe_segment(file_name[-120:], f"file-{uuid.uuid4().hex[:8]}")
    unique = uuid.uuid4().hex[:12]
    return posixpath.join(safe_prefix, safe_employee, date_part, f"{unique}_{safe_name}")


def _extract_signed_upload(data: Any) -> dict[str, str]:
    """Normalize Supabase signed upload URL response shapes.

    Args:
        data: Response returned by supabase-py.

    Returns:
        dict[str, str]: `signed_url`, `token`, and `path`.

    Raises:
        RuntimeError: If the response does not contain a signed URL.
    """
    raw = data
    if hasattr(raw, "model_dump"):
        raw = raw.model_dump()
    elif hasattr(raw, "dict"):
        raw = raw.dict()
    if hasattr(raw, "data"):
        raw = raw.data
    if not isinstance(raw, dict):
        raise RuntimeError("Supabase signed upload response is not a mapping")

    signed_url = str(raw.get("signedUrl") or raw.get("signedURL") or raw.get("signed_url") or "")
    token = str(raw.get("token") or "")
    path = str(raw.get("path") or "")
    if not signed_url:
        raise RuntimeError("Supabase signed upload URL was not returned")
    if not signed_url.startswith("http"):
        settings = get_storage_settings(required=True)
        url_path = signed_url if signed_url.startswith("/") else "/" + signed_url
        signed_url = f"{settings.url}/storage/v1{url_path}"
    return {"signed_url": signed_url, "token": token, "path": path}


def _extract_signed_download(data: Any) -> str:
    """Normalize Supabase signed download URL response shapes."""
    raw = data
    if hasattr(raw, "model_dump"):
        raw = raw.model_dump()
    elif hasattr(raw, "dict"):
        raw = raw.dict()
    if hasattr(raw, "data"):
        raw = raw.data
    if isinstance(raw, str):
        signed_url = raw
    elif isinstance(raw, dict):
        signed_url = str(
            raw.get("signedUrl")
            or raw.get("signedURL")
            or raw.get("signed_url")
            or ""
        )
    else:
        signed_url = ""
    if not signed_url:
        raise RuntimeError("Supabase signed download URL was not returned")
    if signed_url.startswith("http"):
        return signed_url
    settings = get_storage_settings(required=True)
    path = signed_url if signed_url.startswith("/") else "/" + signed_url
    return f"{settings.url}/storage/v1{path}"


def _signed_upload_options(upsert: bool) -> Any:
    """Build signed-upload options for the installed Supabase Storage client.

    Args:
        upsert: Whether the signed upload URL should allow overwriting.

    Returns:
        Any: Options accepted by storage3. The current runtime reads an
        `upsert` attribute, while Supabase examples show a plain mapping.
    """
    upsert_value = str(upsert).lower()

    class SignedUploadOptions(dict):
        """Mapping with attribute access for storage3 signed-upload options."""

        upsert: str

        def __init__(self, value: str) -> None:
            """Initialize the option wrapper.

            Args:
                value: Lowercase string representation of the upsert flag.
            """
            super().__init__(upsert=value)
            self.upsert = value

    return SignedUploadOptions(upsert_value)


def create_signed_upload_url(
    *,
    bucket: str,
    object_path: str,
    upsert: bool = False,
) -> dict[str, str]:
    """Create a Supabase signed upload URL.

    Args:
        bucket: Supabase bucket name.
        object_path: Bucket-relative object path.
        upsert: Whether the signed URL should allow overwriting.

    Returns:
        dict[str, str]: Signed upload URL metadata.
    """
    response = (
        _client()
        .storage
        .from_(bucket)
        .create_signed_upload_url(object_path, options=_signed_upload_options(upsert))
    )
    return _extract_signed_upload(response)


def create_signed_download_url(*, bucket: str, object_path: str, expires_in: int = 3600) -> str:
    """Create a temporary signed download URL.

    Args:
        bucket: Supabase bucket name.
        object_path: Bucket-relative object path.
        expires_in: URL expiration in seconds.

    Returns:
        str: Absolute signed download URL.
    """
    response = _client().storage.from_(bucket).create_signed_url(object_path, expires_in)
    return _extract_signed_download(response)


def _storage_not_found(exc: Exception) -> bool:
    """Return whether a Supabase Storage exception represents a missing object.

    Args:
        exc: Exception raised by the Supabase Storage client.

    Returns:
        bool: True when the error is a 404 or not-found style response.
    """
    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if response is not None:
        status_code = getattr(response, "status_code", status_code)
    if status_code == 404:
        return True

    message = str(exc).lower()
    return "404" in message or "not found" in message or "not_found" in message


def _list_response_items(data: Any) -> list[dict[str, Any]]:
    """Normalize Supabase Storage list response shapes.

    Args:
        data: Response returned by `storage.from_(bucket).list(...)`.

    Returns:
        list[dict[str, Any]]: Storage object metadata dictionaries.
    """
    raw = data
    if hasattr(raw, "model_dump"):
        raw = raw.model_dump()
    elif hasattr(raw, "dict"):
        raw = raw.dict()
    if hasattr(raw, "data"):
        raw = raw.data
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict) and isinstance(raw.get("data"), list):
        return [item for item in raw["data"] if isinstance(item, dict)]
    return []


def _coerce_int(value: Any) -> int | None:
    """Convert Storage metadata values to an integer size when possible.

    Args:
        value: Raw Supabase metadata value.

    Returns:
        int | None: Parsed non-negative integer or None when unavailable.
    """
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _first_mapping_value(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return the first non-empty value from a mapping.

    Args:
        mapping: Source mapping.
        keys: Candidate keys in priority order.

    Returns:
        Any: First non-empty value, otherwise None.
    """
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def _metadata_mapping(item: dict[str, Any]) -> dict[str, Any]:
    """Return the nested Storage metadata mapping if it exists.

    Args:
        item: One object item returned by Supabase Storage list.

    Returns:
        dict[str, Any]: Metadata mapping or an empty dict.
    """
    metadata = item.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _normalize_storage_object_metadata(item: dict[str, Any]) -> StorageObjectMetadata:
    """Normalize one Supabase Storage object list item.

    Args:
        item: One exact-name object item from Supabase Storage list.

    Returns:
        StorageObjectMetadata: Normalized size and content type.
    """
    metadata = _metadata_mapping(item)
    http_metadata = metadata.get("httpMetadata")
    if not isinstance(http_metadata, dict):
        http_metadata = {}

    size = _coerce_int(_first_mapping_value(metadata, ("size", "contentLength", "content_length")))
    if size is None:
        size = _coerce_int(_first_mapping_value(item, ("size", "contentLength", "content_length")))
    content_type = str(
        _first_mapping_value(
            metadata,
            ("mimetype", "mime_type", "contentType", "content_type"),
        )
        or _first_mapping_value(http_metadata, ("contentType", "content_type"))
        or _first_mapping_value(item, ("mimetype", "mime_type", "contentType", "content_type"))
        or ""
    ).strip()
    return StorageObjectMetadata(size_bytes=size, content_type=content_type, raw=dict(item))


def get_storage_object_metadata(
    *,
    bucket: str,
    object_path: str,
) -> StorageObjectMetadata | None:
    """Load object metadata from Supabase Storage using the list API.

    Args:
        bucket: Supabase bucket name.
        object_path: Bucket-relative object path.

    Returns:
        StorageObjectMetadata | None: Metadata for the exact object, or None if
        Supabase reports the object as missing.

    Raises:
        RuntimeError: If Supabase Storage is not configured.
        Exception: For non-404 Storage errors that should surface to the API.
    """
    storage_bucket = _client().storage.from_(bucket)
    parent, file_name = posixpath.split(object_path)
    try:
        items = _list_response_items(
            storage_bucket.list(
                parent or "",
                {"limit": 100, "offset": 0, "search": file_name},
            )
        )
    except Exception as exc:
        if _storage_not_found(exc):
            return None
        raise

    for item in items:
        if str(item.get("name") or "") == file_name:
            return _normalize_storage_object_metadata(item)
    return None


def storage_object_exists(*, bucket: str, object_path: str) -> bool:
    """Return whether an object exists in Supabase Storage.

    Args:
        bucket: Supabase bucket name.
        object_path: Bucket-relative object path.

    Returns:
        bool: True when the object exists, False when Supabase returns not found.

    Raises:
        RuntimeError: If Supabase Storage is not configured.
        Exception: For non-404 Storage errors that should surface to the API.
    """
    storage_bucket = _client().storage.from_(bucket)
    exists = getattr(storage_bucket, "exists", None)
    if callable(exists):
        try:
            return bool(exists(object_path))
        except Exception as exc:
            if _storage_not_found(exc):
                return False
            raise

    parent, file_name = posixpath.split(object_path)
    try:
        items = _list_response_items(
            storage_bucket.list(
                parent or "",
                {"limit": 100, "offset": 0, "search": file_name},
            )
        )
    except Exception as exc:
        if _storage_not_found(exc):
            return False
        raise
    return any(str(item.get("name") or "") == file_name for item in items)


def record_attachment(
    *,
    employee_id: str,
    bucket: str,
    object_path: str,
    content_type: str,
    size_bytes: int,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Record attachment metadata in the application DB.

    Args:
        employee_id: Current user or employee id.
        bucket: Supabase bucket name.
        object_path: Bucket-relative object path.
        content_type: File MIME type.
        size_bytes: File size in bytes.
        metadata: Additional JSON metadata.

    Returns:
        str: Attachment id.
    """
    now = datetime.now(timezone.utc)
    attachment_id = f"att-{uuid.uuid4().hex[:12]}"
    lineage = lineage_values("real", "supabase_storage", bucket)
    row = {
        "id": attachment_id,
        "employee_id": employee_id or "anonymous",
        "bucket": bucket,
        "object_path": object_path,
        "content_type": content_type or "",
        "size_bytes": max(0, int(size_bytes or 0)),
        "metadata": metadata or {},
        "created_at": now,
        "data_class": lineage["data_class"],
        "source_system": lineage["source_system"],
        "source_label": lineage["source_label"],
        "source_updated_at": now,
    }
    engine = _engine()
    _ensure_sqlite_table(engine)
    with engine.begin() as conn:
        conn.execute(_ATTACHMENTS.insert().values(**row))
    return attachment_id


def get_attachment(attachment_id: str) -> dict[str, Any] | None:
    """Load one attachment metadata row.

    Args:
        attachment_id: Attachment id.

    Returns:
        dict[str, Any] | None: Attachment row or None.
    """
    engine = _engine()
    _ensure_sqlite_table(engine)
    stmt = sa.select(_ATTACHMENTS).where(_ATTACHMENTS.c.id == attachment_id)
    with engine.connect() as conn:
        row = conn.execute(stmt).mappings().first()
    return dict(row) if row else None


def record_attachment_storage_verification(
    *,
    attachment_id: str,
    actual_size_bytes: int,
    actual_content_type: str,
) -> None:
    """Persist successful Supabase Storage metadata verification.

    Args:
        attachment_id: Attachment metadata id.
        actual_size_bytes: Size read from Supabase Storage metadata.
        actual_content_type: Content type read from Supabase Storage metadata.
    """
    row = get_attachment(attachment_id)
    if not row:
        return

    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata = dict(metadata)
    metadata.update(
        {
            "storage_verified_at": datetime.now(timezone.utc).isoformat(),
            "actual_size_bytes": actual_size_bytes,
            "actual_content_type": actual_content_type,
        }
    )

    engine = _engine()
    _ensure_sqlite_table(engine)
    stmt = (
        _ATTACHMENTS.update()
        .where(_ATTACHMENTS.c.id == attachment_id)
        .values(metadata=metadata, source_updated_at=datetime.now(timezone.utc))
    )
    with engine.begin() as conn:
        conn.execute(stmt)
