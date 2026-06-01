"""Feature B HWPX and SharePoint compatibility checks."""

from __future__ import annotations

import io
import zipfile

import pytest

from features.draft.hwpx_exporter import HwpxExporter
from features.draft.hwpx_validator import validate_hwpx_bytes
from features.draft.sharepoint_compat import plan_sharepoint_upload
from features.draft.watermark import compute_watermark_id


def test_hwpx_validator_accepts_generated_package() -> None:
    """Generated HWPX should satisfy the local compatibility gate."""

    content = "# HWPX\n\n본문"
    data = HwpxExporter().export_bytes(content, doc_title="HWPX", author="park")
    result = validate_hwpx_bytes(data, expected_watermark_id=compute_watermark_id(content))

    assert result.ok
    assert "Contents/section0.xml" in result.entries


def test_hwpx_validator_rejects_missing_required_entry() -> None:
    """A package missing required OWPML entries should fail closed."""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("mimetype", "application/hwp+zip")
    result = validate_hwpx_bytes(buffer.getvalue())

    assert not result.ok
    assert "missing_entry:Contents/content.hpf" in result.errors


def test_hwpx_validator_rejects_missing_watermark() -> None:
    """A package without the expected watermark id should fail validation."""

    content = "# HWPX\n\n본문"
    data = HwpxExporter().export_bytes(content, doc_title="HWPX", author="park")
    result = validate_hwpx_bytes(data, expected_watermark_id="WMK-deadbeef")

    assert not result.ok
    assert "missing_watermark_id" in result.errors


def test_sharepoint_small_upload_request_shape() -> None:
    """Files at or below 250MB should use a single PUT request shape."""

    req = plan_sharepoint_upload(
        drive_id="drive123",
        parent_id="parent123",
        filename="draft.hwpx",
        size_bytes=1024,
        content_type="application/vnd.hancom.hwpx",
    )

    assert req.mode == "single_put"
    assert req.method == "PUT"
    assert req.path == "/drives/drive123/items/parent123:/draft.hwpx:/content"
    assert req.headers["Content-Type"] == "application/vnd.hancom.hwpx"


def test_sharepoint_large_upload_session_request_shape() -> None:
    """Files larger than 250MB should use an upload-session request shape."""

    req = plan_sharepoint_upload(
        drive_id="drive123",
        parent_id="parent123",
        filename="large draft.hwpx",
        size_bytes=251 * 1024 * 1024,
        content_type="application/vnd.hancom.hwpx",
        chunk_size_bytes=10 * 1024 * 1024,
    )

    assert req.mode == "upload_session"
    assert req.method == "POST"
    assert req.path.endswith(":/large%20draft.hwpx:/createUploadSession")
    assert req.json_body is not None
    assert req.json_body["item"]["fileSize"] == 251 * 1024 * 1024


def test_sharepoint_rejects_invalid_chunk_size() -> None:
    """Upload-session chunk size must be a 320KiB multiple."""

    with pytest.raises(ValueError, match="chunk_size_must_be_320kib_multiple"):
        plan_sharepoint_upload(
            drive_id="drive123",
            parent_id="parent123",
            filename="bad.hwpx",
            size_bytes=251 * 1024 * 1024,
            content_type="application/vnd.hancom.hwpx",
            chunk_size_bytes=123,
        )

