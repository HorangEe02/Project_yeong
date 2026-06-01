"""v4.x — python-hwpx 기반 HWPX 생성기.

이전 버전(자체 OWPML XML 빌더)은 한컴오피스 macOS 빌드에서
ns0:/ns1: 임시 프리픽스 + 비표준 인코딩 이슈로 빈 페이지로 표시되는
호환성 문제가 있었다.

본 모듈은 `python-hwpx` (PyPI 2.9.1+, airmang/python-hwpx) 의
`HwpxDocument.new() + add_paragraph() + add_table()` API 로
정식 OWPML 1.4 패키지를 생성한 뒤, fix_namespaces 후처리로
한컴 표준 프리픽스(hh/hc/hp/hs) 로 정규화한다.

호환:
    한컴오피스 2018+ (Windows/macOS), 한컴 한글뷰어, rhwp 0.7+
"""

from __future__ import annotations

import re
import tempfile
from datetime import datetime
from pathlib import Path

from features.draft.fix_namespaces import fix_namespaces


class HwpxExporter:
    """마크다운 초안을 정식 OWPML HWPX 파일로 변환한다."""

    def export_bytes(
        self,
        markdown_text: str,
        doc_title: str = "",
        doc_type: str = "",
        author: str = "",
    ) -> bytes:
        """마크다운 텍스트를 OWPML 바이트로 변환한다.

        Feature B Sprint 1 P0 — footer 에 AI 워터마크 1줄 자동 부착.
        """
        from hwpx import HwpxDocument
        from features.draft.watermark import compute_watermark_id, watermark_text

        watermark_id = compute_watermark_id(markdown_text)

        doc = HwpxDocument.new()

        # ── 머리말: 회사명 + 문서 제목 ─────────────────────
        doc.add_paragraph("아진산업(주)")
        if doc_title:
            doc.add_paragraph(doc_title)
        doc.add_paragraph("")

        # ── 보고서 결재란 ──────────────────────────────────
        if doc_type.startswith("report_"):
            today = datetime.now().strftime("%Y.%m.%d")
            doc.add_paragraph(
                f"[작성: ___ / 검토: ___ / 승인: ___ / 일자: {today}]"
            )
            doc.add_paragraph("")

        # ── 본문: 마크다운 라인 파싱 ───────────────────────
        _render_markdown(doc, markdown_text)

        # ── 푸터 ───────────────────────────────────────────
        doc.add_paragraph("")
        doc.add_paragraph("─" * 50)
        doc.add_paragraph(
            "아진산업(주) | 경북 경산시 진량읍 공단8로 26길 40 | TEL 053-856-9100"
        )
        doc.add_paragraph("Confidential — 본 문서는 사내 업무용으로 작성되었습니다.")

        # AI 워터마크
        if watermark_id:
            doc.add_paragraph(watermark_text(watermark_id, author))

        # ── 임시 파일 저장 → fix_namespaces 후처리 → 바이트 ─
        with tempfile.NamedTemporaryFile(
            suffix=".hwpx", delete=False
        ) as tmp:
            tmp_path = Path(tmp.name)
        try:
            doc.save_to_path(str(tmp_path))
            fix_namespaces(tmp_path)  # ns0/ns1 → hh/hp/hs/hc
            return tmp_path.read_bytes()
        finally:
            tmp_path.unlink(missing_ok=True)

    def export(
        self,
        markdown_text: str,
        output_path: Path,
        doc_title: str = "",
        doc_type: str = "",
        author: str = "",
    ) -> Path:
        """마크다운 텍스트를 파일로 저장한다."""
        data = self.export_bytes(markdown_text, doc_title, doc_type, author=author)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
        return output_path


# ─────────────────────────────────────────────
# 마크다운 → HwpxDocument 파라그래프 렌더링
# ─────────────────────────────────────────────


def _render_markdown(doc, markdown_text: str) -> None:
    """마크다운 라인을 단락/표로 렌더링한다.

    지원:
        # / ## / ### 제목 (단락으로 평탄화)
        - / · 글머리 기호
        1. 2. 번호 목록
        | a | b | c | 마크다운 표 (HwpxDocument add_table 사용)
        --- 구분선
        그 외 일반 단락
    """
    lines = markdown_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            doc.add_paragraph("")
            i += 1
            continue

        if line.startswith("# "):
            doc.add_paragraph(line[2:].strip())
        elif line.startswith("## "):
            doc.add_paragraph(line[3:].strip())
        elif line.startswith("### "):
            doc.add_paragraph(line[4:].strip())
        elif stripped in ("---", "───", "***"):
            doc.add_paragraph("─" * 50)
        elif stripped.startswith("- ") or stripped.startswith("· "):
            doc.add_paragraph(f"• {stripped[2:]}")
        elif re.match(r"^\s*\d+\.", line):
            doc.add_paragraph(stripped)
        elif stripped.startswith("|") and stripped.endswith("|"):
            # 연속된 표 라인을 모아서 add_table 로 처리
            table_lines: list[list[str]] = []
            while i < len(lines):
                row_line = lines[i].strip()
                if not (row_line.startswith("|") and row_line.endswith("|")):
                    break
                cells = [c.strip() for c in row_line.strip("|").split("|")]
                # 구분선 행 (---|---|---) 은 스킵
                if all(re.match(r"^[\s\-:]+$", c) for c in cells):
                    i += 1
                    continue
                table_lines.append(cells)
                i += 1
            if table_lines:
                _add_table(doc, table_lines)
            continue
        else:
            doc.add_paragraph(stripped)
        i += 1


def _add_table(doc, rows: list[list[str]]) -> None:
    """마크다운 표를 HwpxDocument 표로 삽입."""
    if not rows:
        return
    n_rows = len(rows)
    n_cols = max(len(r) for r in rows)
    try:
        table = doc.add_table(rows=n_rows, cols=n_cols)
        for r, row in enumerate(rows):
            for c, cell in enumerate(row):
                if c < n_cols:
                    table.set_cell_text(r, c, cell)
    except Exception:
        # python-hwpx 버전에 따라 add_table 미지원 시 폴백: 텍스트로 표시
        for row in rows:
            doc.add_paragraph("  " + "  |  ".join(row))


__all__ = ["HwpxExporter"]
