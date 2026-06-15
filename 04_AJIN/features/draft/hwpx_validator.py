"""Local HWPX compatibility validator for Feature B exports.

The validator is intentionally offline. It checks the HWPX ZIP package shape
that AJIN generates before any SharePoint or mail workflow is allowed to trust
the exported artifact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from xml.etree import ElementTree
import zipfile


REQUIRED_HWPX_ENTRIES = (
    "mimetype",
    "META-INF/container.xml",
    "Contents/content.hpf",
    "Contents/header.xml",
    "Contents/section0.xml",
    "settings.xml",
    "version.xml",
)


@dataclass(frozen=True)
class HwpxValidationResult:
    """Result from a local HWPX package validation.

    Args:
        ok: Whether no validation errors were found.
        errors: Stable error codes for failed checks.
        warnings: Non-blocking observations.
        entries: ZIP entry names seen in the package.
    """

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    entries: list[str] = field(default_factory=list)


def validate_hwpx_bytes(
    file_bytes: bytes,
    expected_watermark_id: str = "",
) -> HwpxValidationResult:
    """Validate a generated HWPX byte stream.

    Args:
        file_bytes: HWPX ZIP package bytes.
        expected_watermark_id: Optional watermark that must appear in section0.xml.

    Returns:
        HwpxValidationResult: Offline compatibility result.
    """

    errors: list[str] = []
    warnings: list[str] = []

    try:
        with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
            entries = zf.namelist()
            if not entries:
                return HwpxValidationResult(False, ["empty_zip"], warnings, entries)

            if entries[0] != "mimetype":
                errors.append("mimetype_not_first")
            if "mimetype" in entries:
                mimetype_info = zf.getinfo("mimetype")
                if mimetype_info.compress_type != zipfile.ZIP_STORED:
                    errors.append("mimetype_compressed")
                mimetype = zf.read("mimetype").decode("utf-8", errors="replace").strip()
                if mimetype != "application/hwp+zip":
                    errors.append("invalid_mimetype")

            for entry in REQUIRED_HWPX_ENTRIES:
                if entry not in entries:
                    errors.append(f"missing_entry:{entry}")

            for entry in REQUIRED_HWPX_ENTRIES:
                if entry == "mimetype" or entry not in entries:
                    continue
                try:
                    ElementTree.fromstring(zf.read(entry))
                except ElementTree.ParseError:
                    errors.append(f"invalid_xml:{entry}")

            if "Contents/section0.xml" in entries:
                section_xml = zf.read("Contents/section0.xml").decode("utf-8", errors="replace")
                if "AI 보조 작성" not in section_xml:
                    errors.append("missing_ai_watermark_text")
                if expected_watermark_id and expected_watermark_id not in section_xml:
                    errors.append("missing_watermark_id")

            return HwpxValidationResult(not errors, errors, warnings, entries)
    except zipfile.BadZipFile:
        return HwpxValidationResult(False, ["invalid_zip"], warnings, [])

