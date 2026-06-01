"""Supabase Storage signed URL API.

AJIN JWT로 인증된 사용자에게만 signed upload/download URL을 발급한다.
브라우저에는 Supabase secret key를 내려주지 않는다.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.dependencies import get_current_user
from backend.services.supabase_storage import (
    build_object_path,
    bucket_for_type,
    create_signed_download_url,
    create_signed_upload_url,
    get_attachment,
    get_storage_object_metadata,
    record_attachment,
    record_attachment_storage_verification,
    storage_object_exists,
)

router = APIRouter(prefix="/storage", tags=["storage"])


class SignedUploadIn(BaseModel):
    """Signed upload URL request."""

    bucket_type: Literal["attachments", "draft_exports"] = "attachments"
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="", max_length=160)
    size_bytes: int = Field(default=0, ge=0)
    prefix: str = Field(default="uploads", max_length=80)


class SignedUploadOut(BaseModel):
    """Signed upload URL response."""

    attachment_id: str
    bucket: str
    object_path: str
    signed_url: str
    token: str
    method: str = "PUT"


class CompleteUploadIn(BaseModel):
    """Client notification that the signed upload finished."""

    attachment_id: str = Field(min_length=1, max_length=80)


class CompleteUploadOut(BaseModel):
    """Signed upload completion response."""

    ok: bool
    attachment_id: str
    signed_download_url: str | None = None


class SignedDownloadOut(BaseModel):
    """Signed download URL response."""

    attachment_id: str
    signed_download_url: str


def _employee_id_of(user) -> str:
    """Return a stable employee id from auth context."""
    return str(
        getattr(user, "employee_id", "")
        or getattr(user, "user_id", "")
        or getattr(user, "username", "")
        or "anonymous"
    )


def _storage_error(exc: Exception) -> HTTPException:
    """Translate storage configuration/runtime errors to API responses."""
    message = str(exc)
    if "SUPABASE_URL" in message or "supabase package" in message:
        return HTTPException(status_code=503, detail=message)
    return HTTPException(status_code=502, detail=message)


def _is_storage_admin(user) -> bool:
    """Return whether the current user can administer Storage attachments.

    Args:
        user: Current authenticated user context.

    Returns:
        bool: True for SYS_ADMIN or HR_ADMIN users.
    """
    if bool(getattr(user, "is_admin", False)):
        return True
    return str(getattr(user, "role", "") or "").upper() in {"SYS_ADMIN", "HR_ADMIN"}


def _assert_attachment_access(row: dict, user) -> None:
    """Fail closed unless the current user owns the attachment or is an admin.

    Args:
        row: Attachment metadata row from the application DB.
        user: Current authenticated user context.

    Raises:
        HTTPException: 403 when the current user cannot access the row.
    """
    owner_employee_id = str(row.get("employee_id") or "")
    if owner_employee_id and owner_employee_id == _employee_id_of(user):
        return
    if _is_storage_admin(user):
        return
    raise HTTPException(status_code=403, detail="attachment_forbidden")


def _assert_storage_object_exists(row: dict, *, missing_status: int, missing_detail: str) -> None:
    """Fail when metadata exists but the backing Storage object is missing.

    Args:
        row: Attachment metadata row from the application DB.
        missing_status: HTTP status code to return when object lookup is false.
        missing_detail: HTTP error detail for a missing object.

    Raises:
        HTTPException: When object lookup is false.
    """
    try:
        exists = storage_object_exists(
            bucket=str(row["bucket"]),
            object_path=str(row["object_path"]),
        )
    except Exception as exc:
        raise _storage_error(exc) from exc
    if not exists:
        raise HTTPException(status_code=missing_status, detail=missing_detail)


def _normalized_content_type(value: object) -> str:
    """Normalize a MIME type for equality checks.

    Args:
        value: Raw MIME type value.

    Returns:
        str: Lowercase MIME type without parameters.
    """
    return str(value or "").split(";", 1)[0].strip().lower()


def _expected_size(row: dict) -> int:
    """Return the non-negative size originally recorded for an attachment.

    Args:
        row: Attachment metadata row.

    Returns:
        int: Non-negative expected size, or 0 when no size was provided.
    """
    try:
        return max(0, int(row.get("size_bytes") or 0))
    except (TypeError, ValueError):
        return 0


def _assert_complete_upload_metadata(row: dict, *, attachment_id: str) -> None:
    """Verify uploaded object metadata before completing a signed upload.

    Args:
        row: Attachment metadata row from the application DB.
        attachment_id: Attachment id used for verification audit metadata.

    Raises:
        HTTPException: 409 when the object is missing, incomplete, or mismatched.
    """
    try:
        actual = get_storage_object_metadata(
            bucket=str(row["bucket"]),
            object_path=str(row["object_path"]),
        )
    except Exception as exc:
        raise _storage_error(exc) from exc

    if actual is None:
        raise HTTPException(status_code=409, detail="upload_not_found")

    actual_content_type = _normalized_content_type(actual.content_type)
    if actual.size_bytes is None or not actual_content_type:
        raise HTTPException(status_code=409, detail="upload_metadata_unavailable")

    expected_size = _expected_size(row)
    if expected_size > 0 and actual.size_bytes != expected_size:
        raise HTTPException(status_code=409, detail="upload_size_mismatch")

    expected_content_type = _normalized_content_type(row.get("content_type"))
    if expected_content_type and actual_content_type != expected_content_type:
        raise HTTPException(status_code=409, detail="upload_content_type_mismatch")

    record_attachment_storage_verification(
        attachment_id=attachment_id,
        actual_size_bytes=actual.size_bytes,
        actual_content_type=actual_content_type,
    )


@router.post("/signed-upload", response_model=SignedUploadOut)
async def create_storage_signed_upload(payload: SignedUploadIn, user=Depends(get_current_user)):
    """Create a Supabase signed upload URL and record attachment metadata.

    Args:
        payload: Upload request metadata.
        user: Current authenticated user.

    Returns:
        SignedUploadOut: Signed URL metadata for direct browser upload.

    Raises:
        HTTPException: 503 if Supabase Storage is not configured.
    """
    employee_id = _employee_id_of(user)
    try:
        bucket = bucket_for_type(payload.bucket_type)
        object_path = build_object_path(
            employee_id=employee_id,
            prefix=payload.prefix,
            file_name=payload.file_name,
        )
        signed = create_signed_upload_url(bucket=bucket, object_path=object_path)
        attachment_id = record_attachment(
            employee_id=employee_id,
            bucket=bucket,
            object_path=object_path,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            metadata={"original_name": payload.file_name, "bucket_type": payload.bucket_type},
        )
    except Exception as exc:
        raise _storage_error(exc) from exc
    return {
        "attachment_id": attachment_id,
        "bucket": bucket,
        "object_path": object_path,
        "signed_url": signed["signed_url"],
        "token": signed.get("token", ""),
        "method": "PUT",
    }


@router.post("/complete-upload", response_model=CompleteUploadOut)
async def complete_storage_upload(payload: CompleteUploadIn, user=Depends(get_current_user)):
    """Return a signed download URL after client-side signed upload completes.

    Args:
        payload: Upload completion request.
        user: Current authenticated user.

    Returns:
        CompleteUploadOut: Signed download URL after ownership and object checks.

    Raises:
        HTTPException: 403 if the attachment is owned by another non-admin user.
        HTTPException: 409 if the Storage object is missing.
    """
    row = get_attachment(payload.attachment_id)
    if not row:
        raise HTTPException(status_code=404, detail="attachment_not_found")
    _assert_attachment_access(row, user)
    _assert_complete_upload_metadata(row, attachment_id=payload.attachment_id)
    try:
        signed_download_url = create_signed_download_url(
            bucket=str(row["bucket"]),
            object_path=str(row["object_path"]),
            expires_in=3600,
        )
    except Exception as exc:
        raise _storage_error(exc) from exc
    return {
        "ok": True,
        "attachment_id": payload.attachment_id,
        "signed_download_url": signed_download_url,
    }


@router.get("/signed-download/{attachment_id}", response_model=SignedDownloadOut)
async def create_storage_signed_download(attachment_id: str, user=Depends(get_current_user)):
    """Create a signed download URL for an attachment.

    Args:
        attachment_id: Attachment metadata id.
        user: Current authenticated user.

    Returns:
        SignedDownloadOut: Signed URL for the requested attachment.

    Raises:
        HTTPException: 403 if the attachment is owned by another non-admin user.
        HTTPException: 404 if metadata or the backing Storage object is missing.
    """
    row = get_attachment(attachment_id)
    if not row:
        raise HTTPException(status_code=404, detail="attachment_not_found")
    _assert_attachment_access(row, user)
    _assert_storage_object_exists(
        row,
        missing_status=404,
        missing_detail="storage_object_not_found",
    )
    try:
        signed_download_url = create_signed_download_url(
            bucket=str(row["bucket"]),
            object_path=str(row["object_path"]),
            expires_in=3600,
        )
    except Exception as exc:
        raise _storage_error(exc) from exc
    return {"attachment_id": attachment_id, "signed_download_url": signed_download_url}
