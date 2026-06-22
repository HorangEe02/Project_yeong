"""Repair the clipped title on page 1 of enterprise-task-service-proposal.pdf."""

from __future__ import annotations

import io
import shutil
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path("/Users/yeong/99_me/00_github/03_lemon_healthcare")
PDF_PATH = ROOT / "records/meetings/mentoring-01/enterprise-task-service-proposal.pdf"
BACKUP_PATH = ROOT / "records/meetings/mentoring-01/enterprise-task-service-proposal.original.pdf"
TMP_PATH = ROOT / "outputs/generated/manual-20260513-enterprise-pdf-fix/enterprise-task-service-proposal.fixed.pdf"
FONT_PATH = Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf")


def build_title_overlay(width: float, height: float) -> PdfReader:
    """Create a single-page overlay that covers the clipped title and redraws it.

    Args:
        width: Source page width in PDF points.
        height: Source page height in PDF points.

    Returns:
        A PdfReader containing one overlay page.

    Raises:
        FileNotFoundError: If the Korean system font is unavailable.
    """
    if not FONT_PATH.exists():
        raise FileNotFoundError(f"Korean font not found: {FONT_PATH}")

    pdfmetrics.registerFont(TTFont("AppleGothic", str(FONT_PATH)))
    packet = io.BytesIO()
    overlay = canvas.Canvas(packet, pagesize=(width, height))

    # Cover the clipped title and subtitle area only; leave the content grid untouched.
    overlay.setFillColor(colors.HexColor("#FCFCFF"))
    overlay.rect(0, height - 120, width, 120, fill=1, stroke=0)

    overlay.setFillColor(colors.HexColor("#111827"))
    overlay.setFont("AppleGothic", 29)
    overlay.drawString(40, height - 54, "Lemon Aid 1주차 프로젝트 브리핑")

    overlay.setFillColor(colors.HexColor("#536174"))
    overlay.setFont("AppleGothic", 13.5)
    overlay.drawString(40, height - 88, "기업 과제 수행 방향과 서비스화 관점을 파트별 산출물 중심으로 정리한 발표용 통합 문서입")
    overlay.drawString(40, height - 111, "니다.")

    overlay.save()
    packet.seek(0)
    return PdfReader(packet)


def repair_pdf() -> None:
    """Backup the original PDF, replace page 1's clipped title, and save in place."""
    if not BACKUP_PATH.exists():
        shutil.copy2(PDF_PATH, BACKUP_PATH)

    source_path = BACKUP_PATH if BACKUP_PATH.exists() else PDF_PATH
    reader = PdfReader(str(source_path))
    writer = PdfWriter()
    if reader.metadata:
        writer.add_metadata({key: str(value) for key, value in reader.metadata.items() if value is not None})

    first_page = reader.pages[0]
    width = float(first_page.mediabox.width)
    height = float(first_page.mediabox.height)
    title_overlay = build_title_overlay(width, height)
    first_page.merge_page(title_overlay.pages[0])
    writer.add_page(first_page)

    for page in reader.pages[1:]:
        writer.add_page(page)

    TMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TMP_PATH.open("wb") as handle:
        writer.write(handle)
    shutil.copy2(TMP_PATH, PDF_PATH)


if __name__ == "__main__":
    repair_pdf()
