"""Feature B export watermark traceability tests."""

from __future__ import annotations

import asyncio
import io
import zipfile

from backend.routers.draft import export_draft
from backend.schemas.draft import DraftExportRequest
from features.draft.watermark import compute_watermark_id


def _export(content: str, fmt: str):
    """Run the async export route directly.

    Args:
        content: Draft body.
        fmt: Export format.

    Returns:
        fastapi.responses.Response: Export response.
    """

    return asyncio.run(
        export_draft(
            DraftExportRequest(content=content, doc_type="oem_email", format=fmt),
            user=None,
        )
    )


def _zip_text_contains(data: bytes, needle: str) -> bool:
    """Search text-like ZIP entries for a marker.

    Args:
        data: ZIP bytes.
        needle: Expected text.

    Returns:
        bool: True when any XML/text entry contains the marker.
    """

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if name.endswith((".xml", ".rels")) or name in {"mimetype", "docProps/core.xml"}:
                if needle in zf.read(name).decode("utf-8", errors="replace"):
                    return True
    return False


def test_export_response_exposes_watermark_headers() -> None:
    """Export responses should carry a stable watermark id header."""

    content = "# Header\n\nBody"
    response = _export(content, "txt")

    assert response.headers["X-AJIN-Watermark-Id"] == compute_watermark_id(content)
    assert response.headers["X-AJIN-AI-Assisted"] == "true"


def test_txt_and_csv_exports_embed_watermark_marker() -> None:
    """Plain text-like exports should include a visible AI marker."""

    content = "# Header\n\nBody"
    expected = compute_watermark_id(content)

    for fmt in ("txt", "csv"):
        response = _export(content, fmt)
        body = response.body.decode("utf-8-sig")
        assert expected in body
        assert "AI 보조 작성" in body


def test_docx_hwpx_and_odt_exports_embed_watermark_marker() -> None:
    """ZIP-based document exports should preserve the watermark marker."""

    content = "# Header\n\nBody"
    expected = compute_watermark_id(content)

    for fmt in ("docx", "hwpx", "odt"):
        response = _export(content, fmt)
        assert _zip_text_contains(response.body, expected)
        assert _zip_text_contains(response.body, "AI 보조 작성")


def test_xlsx_export_stores_watermark_in_core_properties() -> None:
    """XLSX exports should store the watermark in workbook metadata."""

    from openpyxl import load_workbook

    content = "# Header\n\nBody"
    response = _export(content, "xlsx")
    wb = load_workbook(io.BytesIO(response.body))

    assert compute_watermark_id(content) in (wb.properties.description or "")
    assert wb.properties.keywords == "AJIN_AI_ASSISTED"
