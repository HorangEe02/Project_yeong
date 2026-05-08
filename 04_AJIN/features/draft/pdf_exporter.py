"""Phase 6: PDF 출력 모듈

렌더링된 마크다운 텍스트를 PDF로 출력한다.
fpdf2 기반 경량 PDF 생성 (시스템 의존성 없음).
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from io import BytesIO

from fpdf import FPDF


# 한국어 폰트 경로
# Plan v1.0 §4.4 — 1순위: 프로젝트 동봉 AjinSans (uiux Design System v2)
# 동봉 폰트는 시스템 의존성이 없어 Cloud Run / Docker 등 환경에서도 안정 동작.
_PROJECT_FONT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "fonts"

_FONT_PATHS = [
    _PROJECT_FONT_DIR / "AjinSans-Regular.ttf",                                  # 동봉 (1순위)
    Path.home() / "Library/Fonts/malgun.ttf",                                    # macOS user
    Path.home() / "Library/Fonts/NanumGothic.ttf",                               # macOS user
    Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),                  # macOS system
    Path("/System/Library/Fonts/Supplemental/NotoSansGothic-Regular.ttf"),       # macOS system
    Path("C:/Windows/Fonts/malgun.ttf"),                                          # Windows
    Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),                     # Ubuntu
    Path("/usr/share/fonts/truetype/malgun/malgun.ttf"),                         # Linux alt
]

_FONT_BOLD_PATHS = [
    _PROJECT_FONT_DIR / "AjinSans-Bold.ttf",                                     # 동봉 (1순위)
    Path.home() / "Library/Fonts/malgunbd.ttf",                                  # macOS user
    Path.home() / "Library/Fonts/NanumGothicBold.ttf",                           # macOS user
]

_BRAND_NAVY = (0, 51, 102)
_BRAND_GOLD = (180, 140, 50)
_GRAY = (100, 100, 100)
_LIGHT_GRAY = (200, 200, 200)


class PdfExporter:
    """마크다운 초안을 PDF로 변환한다."""

    def export_bytes(self, markdown_text: str, doc_title: str = "") -> bytes:
        """마크다운 텍스트를 PDF 바이트로 변환한다."""
        pdf = _AjinPDF(doc_title)
        pdf.add_page()

        # 결재란
        pdf._draw_approval_table()
        pdf.ln(8)

        # 본문
        pdf._render_markdown(markdown_text)

        # 하단 회사 정보
        pdf._draw_company_footer()

        buffer = BytesIO()
        pdf.output(buffer)
        return buffer.getvalue()

    def export(self, markdown_text: str, output_path: Path, doc_title: str = "") -> Path:
        """마크다운 텍스트를 PDF 파일로 저장한다."""
        pdf_bytes = self.export_bytes(markdown_text, doc_title)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_bytes)
        return output_path


class _AjinPDF(FPDF):
    """아진산업 브랜드 PDF 클래스"""

    def __init__(self, title: str = ""):
        super().__init__()
        self._doc_title = title
        self._setup_fonts()
        self.set_auto_page_break(auto=True, margin=25)

    def _setup_fonts(self):
        """한국어 폰트를 등록한다."""
        self._kr_font = "helvetica"  # 기본 폴백

        # Regular 폰트
        regular_path = None
        for font_path in _FONT_PATHS:
            if font_path.exists():
                regular_path = font_path
                break

        if regular_path is None:
            return

        try:
            self.add_font("korean", "", str(regular_path), uni=True)
            self._kr_font = "korean"

            # Bold 폰트 (있으면 등록, 없으면 regular로 대체)
            bold_path = None
            for bp in _FONT_BOLD_PATHS:
                if bp.exists():
                    bold_path = bp
                    break
            self.add_font("korean", "B", str(bold_path or regular_path), uni=True)
        except Exception:
            pass

    def header(self):
        """페이지 헤더"""
        # 회사명 (첫 페이지)
        self.set_font(self._kr_font, "B", 18)
        self.set_text_color(*_BRAND_NAVY)
        self.cell(0, 12, "아진산업(주)", align="C", new_x="LMARGIN", new_y="NEXT")

        if self._doc_title:
            self.set_font(self._kr_font, "B", 13)
            self.set_text_color(30, 30, 30)
            self.cell(0, 10, self._doc_title, align="C", new_x="LMARGIN", new_y="NEXT")

        # 구분선
        self.set_draw_color(*_BRAND_GOLD)
        self.set_line_width(0.5)
        self.line(self.l_margin, self.get_y() + 2, self.w - self.r_margin, self.get_y() + 2)
        self.ln(6)

        # 우측 상단 회사 텍스트 (헤더 영역)
        self.set_font(self._kr_font, "", 7)
        self.set_text_color(*_GRAY)

    def footer(self):
        """페이지 푸터"""
        self.set_y(-20)
        self.set_draw_color(*_LIGHT_GRAY)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

        self.set_font(self._kr_font, "", 7)
        self.set_text_color(*_GRAY)
        self.cell(0, 4, f"Page {self.page_no()}/{{nb}}", align="C", new_x="LMARGIN", new_y="NEXT")

    def _draw_approval_table(self):
        """결재란"""
        today = datetime.now().strftime("%Y.%m.%d")
        col_w = [20, 30, 30, 30]
        start_x = self.w - self.r_margin - sum(col_w)

        saved_x = self.get_x()
        self.set_x(start_x)

        # 헤더
        self.set_font(self._kr_font, "B", 8)
        self.set_fill_color(*_BRAND_NAVY)
        self.set_text_color(255, 255, 255)
        for i, label in enumerate(["구분", "작성", "검토", "승인"]):
            self.cell(col_w[i], 7, label, border=1, align="C", fill=True)
        self.ln()

        # 서명란
        self.set_x(start_x)
        self.set_font(self._kr_font, "", 7)
        self.set_text_color(*_GRAY)
        self.set_fill_color(255, 255, 255)
        self.cell(col_w[0], 14, "서명", border=1, align="C")
        for i in range(1, 4):
            self.cell(col_w[i], 14, "", border=1, align="C")
        self.ln()

        # 일자란
        self.set_x(start_x)
        self.cell(col_w[0], 7, "일자", border=1, align="C")
        self.cell(col_w[1], 7, today, border=1, align="C")
        self.cell(col_w[2], 7, "", border=1, align="C")
        self.cell(col_w[3], 7, "", border=1, align="C")
        self.ln()

        # 본문 색상 복원
        self.set_text_color(0, 0, 0)

    def _render_markdown(self, text: str):
        """마크다운을 PDF 요소로 변환"""
        lines = text.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]

            # 표
            if line.strip().startswith("|"):
                table_lines = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    table_lines.append(lines[i])
                    i += 1
                self._draw_table(table_lines)
                continue

            # H1
            if line.startswith("# "):
                self.ln(4)
                self.set_font(self._kr_font, "B", 14)
                self.set_text_color(*_BRAND_NAVY)
                self.cell(0, 8, line[2:].strip(), new_x="LMARGIN", new_y="NEXT")
                self.set_draw_color(*_LIGHT_GRAY)
                self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
                self.ln(3)
                self.set_text_color(0, 0, 0)
                i += 1
                continue

            # H2
            if line.startswith("## "):
                self.ln(3)
                self.set_font(self._kr_font, "B", 12)
                self.set_text_color(*_BRAND_NAVY)
                self.cell(0, 7, line[3:].strip(), new_x="LMARGIN", new_y="NEXT")
                self.ln(1)
                self.set_text_color(0, 0, 0)
                i += 1
                continue

            # H3
            if line.startswith("### "):
                self.ln(2)
                self.set_font(self._kr_font, "B", 11)
                self.set_text_color(60, 60, 60)
                self.cell(0, 6, line[4:].strip(), new_x="LMARGIN", new_y="NEXT")
                self.ln(1)
                self.set_text_color(0, 0, 0)
                i += 1
                continue

            # 구분선
            if line.strip() in ("---", "───", "***"):
                self.ln(2)
                self.set_draw_color(*_LIGHT_GRAY)
                self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
                self.ln(4)
                i += 1
                continue

            # 목록 (비순서)
            if line.strip().startswith("- ") or line.strip().startswith("· "):
                self.set_font(self._kr_font, "", 10)
                content = line.strip()[2:]
                self.cell(6, 5, "  •")
                self.multi_cell(0, 5, f" {content}", new_x="LMARGIN", new_y="NEXT")
                i += 1
                continue

            # 목록 (순서)
            if re.match(r"^\s*(\d+)\.", line):
                self.set_font(self._kr_font, "", 10)
                num_match = re.match(r"^\s*(\d+)\.\s*(.*)", line)
                if num_match:
                    num = num_match.group(1)
                    content = num_match.group(2)
                    self.cell(8, 5, f"  {num}.")
                    self.multi_cell(0, 5, f" {content}", new_x="LMARGIN", new_y="NEXT")
                i += 1
                continue

            # 일반 텍스트
            if line.strip():
                self.set_font(self._kr_font, "", 10)
                self.set_text_color(0, 0, 0)
                self.multi_cell(0, 5, line.strip(), new_x="LMARGIN", new_y="NEXT")

            i += 1

    def _draw_table(self, table_lines: list[str]):
        """마크다운 표를 PDF 테이블로 렌더링"""
        data_lines = [
            line for line in table_lines
            if not re.match(r"^\|[\s\-:|]+\|$", line)
        ]
        if not data_lines:
            return

        rows = []
        for line in data_lines:
            cells = [c.strip() for c in line.strip("|").split("|")]
            rows.append(cells)

        if not rows:
            return

        num_cols = len(rows[0])
        available_w = self.w - self.l_margin - self.r_margin
        col_w = available_w / num_cols

        self.ln(3)

        for r_idx, row in enumerate(rows):
            # 헤더
            if r_idx == 0:
                self.set_font(self._kr_font, "B", 9)
                self.set_fill_color(232, 238, 244)
            else:
                self.set_font(self._kr_font, "", 9)
                self.set_fill_color(255, 255, 255)

            for c_idx, cell_text in enumerate(row[:num_cols]):
                self.cell(col_w, 7, cell_text, border=1, align="C", fill=True)
            self.ln()

        self.ln(3)

    def _draw_company_footer(self):
        """문서 하단 회사 정보"""
        self.ln(10)
        self.set_draw_color(*_LIGHT_GRAY)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

        self.set_font(self._kr_font, "", 7)
        self.set_text_color(*_GRAY)
        self.cell(0, 4, "아진산업(주) | 경북 경산시 진량읍 공단8로 26길 40 | TEL 053-856-9100",
                  align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 4, "Confidential — 본 문서는 사내 업무용으로 작성되었습니다.",
                  align="C", new_x="LMARGIN", new_y="NEXT")
