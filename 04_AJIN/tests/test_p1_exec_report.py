"""P1 D2 — 임원 보고서 단위 테스트."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    import features.compliance.change_detector as cd
    monkeypatch.setattr(cd, "CHANGE_DB_PATH", str(tmp_path / "ch.db"))
    cd.init_change_db()
    return cd


def _seed(cd, **overrides):
    """기본 sample change 1건 적재."""
    base = {
        "regulation_type": "test",
        "change_type": "added",
        "item_id": "X-1",
        "item_title": "관세 25% 시행",
        "old_value": "",
        "new_value": "5년 이하 징역, 1억원 이하 벌금",
        "severity": "warning",
        "summary_ko": "긴급",
        "grade": "CRITICAL",
        "affected_departments": ["구매팀"],
        "affected_plants": ["SUB-US-JOON"],
        "legal_class": ["criminal", "administrative"],
        "penalty_extract": "5년 이하 징역, 1억 이하 벌금",
        "penalty_severity_krw_mn": 100,
    }
    base.update(overrides)
    return cd.save_changes([base])


# ─────────────────────────────────────────────────────────────
# generate_report — markdown
# ─────────────────────────────────────────────────────────────
class TestMarkdownReport:
    def test_empty_period_returns_no_changes_text(self, tmp_db):
        from features.compliance.exec_report import generate_report
        body, ctype, fname = generate_report("markdown")
        text = body.decode("utf-8")
        assert "감지된" in text or "없음" in text
        assert ctype.startswith("text/markdown")
        assert fname.endswith(".md")

    def test_with_critical_includes_summary_and_recommendations(self, tmp_db):
        _seed(tmp_db)
        from features.compliance.exec_report import generate_report
        body, ctype, fname = generate_report("markdown")
        text = body.decode("utf-8")
        assert "CRITICAL" in text
        assert "관세 25%" in text
        assert "5년 이하 징역" in text
        # 권고 액션 — 형사 키워드 포함
        assert "형사" in text or "법무" in text

    def test_grade_table_present(self, tmp_db):
        _seed(tmp_db, grade="HIGH")
        _seed(tmp_db, grade="MEDIUM", item_id="X-2")
        from features.compliance.exec_report import generate_report
        body, _, _ = generate_report("markdown")
        text = body.decode("utf-8")
        assert "등급" in text
        assert "| HIGH |" in text or "HIGH" in text
        assert "| MEDIUM |" in text or "MEDIUM" in text

    def test_top_3_capped(self, tmp_db):
        for i in range(5):
            _seed(tmp_db, item_id=f"X-{i}", item_title=f"규제 {i}")
        from features.compliance.exec_report import generate_report
        body, _, _ = generate_report("markdown")
        text = body.decode("utf-8")
        # Top 3 만 노출 — 5건 중 3건만 본문에 등장 (체크: "### 4." 없음)
        assert "### 1." in text
        assert "### 3." in text
        assert "### 4." not in text


# ─────────────────────────────────────────────────────────────
# generate_report — docx
# ─────────────────────────────────────────────────────────────
class TestDocxReport:
    def test_empty_docx_valid_zip(self, tmp_db):
        from features.compliance.exec_report import generate_report
        body, ctype, fname = generate_report("docx_boon_bujang")
        assert body[:2] == b"PK"  # docx is zipped
        assert "wordprocessingml" in ctype
        assert fname.endswith(".docx")
        assert len(body) > 1000

    def test_docx_contains_critical_text(self, tmp_db):
        _seed(tmp_db)
        from features.compliance.exec_report import generate_report
        from docx import Document
        import io

        body, _, _ = generate_report("docx_boon_bujang")
        doc = Document(io.BytesIO(body))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "관세 25%" in text or "CRITICAL" in text
        assert "권고" in text or "법무" in text


# ─────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────
class TestEdges:
    def test_invalid_format_raises(self, tmp_db):
        from features.compliance.exec_report import generate_report
        with pytest.raises(ValueError):
            generate_report("pdf_executive")

    def test_brand_template_board_format(self, tmp_db):
        """P5 §12 — 이사회 양식 docx 생성 + brand 적용 확인."""
        _seed(tmp_db, item_title="이사회용 변경")
        from features.compliance.exec_report import generate_report
        body, ctype, fname = generate_report("docx_board")
        assert body.startswith(b"PK")  # docx = ZIP
        assert "wordprocessingml" in ctype
        assert "board" in fname
        import zipfile, io
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
            assert "0D47A1" in doc_xml or "0d47a1" in doc_xml  # primary color
            assert "Pretendard" in doc_xml                       # 한글 폰트
            assert "이사회" in doc_xml                          # audience label

    def test_brand_template_authority_format(self, tmp_db):
        """P5 §12 — 감독기관 양식 docx 생성."""
        _seed(tmp_db, item_title="감독기관 통보")
        from features.compliance.exec_report import generate_report
        body, ctype, fname = generate_report("docx_authority")
        assert body.startswith(b"PK")
        assert "authority" in fname
        import zipfile, io
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            doc_xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
            assert "감독" in doc_xml
            assert "AJIN" in doc_xml or "아진" in doc_xml

    def test_filtered_changes_excluded(self, tmp_db):
        # status='filtered' 항목은 보고서에서 제외
        _seed(tmp_db, status="filtered", item_title="노이즈")
        _seed(tmp_db, item_id="X-2", item_title="실질")
        from features.compliance.exec_report import generate_report
        body, _, _ = generate_report("markdown")
        text = body.decode("utf-8")
        assert "노이즈" not in text
        assert "실질" in text

    def test_custom_date_range(self, tmp_db):
        from features.compliance.exec_report import generate_report
        _seed(tmp_db)
        # 작년 기간 → 데이터 없어야 함
        body, _, fname = generate_report(
            "markdown",
            since=date(2020, 1, 1),
            until=date(2020, 12, 31),
        )
        text = body.decode("utf-8")
        assert "2020-01-01" in text
        assert "감지된" in text or "없음" in text
