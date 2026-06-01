"""P4.1 §0 — DART corp_code 조회 스크립트 단위 테스트."""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


_SAMPLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<result>
  <list>
    <corp_code>00126380</corp_code>
    <corp_name>\xec\x82\xbc\xec\x84\xb1\xec\xa0\x84\xec\x9e\x90</corp_name>
    <corp_eng_name>SAMSUNG ELECTRONICS CO., LTD.</corp_eng_name>
    <stock_code>005930</stock_code>
    <modify_date>20240101</modify_date>
  </list>
  <list>
    <corp_code>01234567</corp_code>
    <corp_name>\xec\x95\x84\xec\xa7\x84\xec\x82\xb0\xec\x97\x85</corp_name>
    <corp_eng_name>AJIN INDUSTRIAL CO., LTD.</corp_eng_name>
    <stock_code>002990</stock_code>
    <modify_date>20240515</modify_date>
  </list>
  <list>
    <corp_code>09876543</corp_code>
    <corp_name>\xec\xa3\xbc\xec\x8b\x9d\xed\x9a\x8c\xec\x82\xac \xec\x95\x84\xec\xa7\x84</corp_name>
    <corp_eng_name>ajin corp.</corp_eng_name>
    <stock_code></stock_code>
    <modify_date>20231220</modify_date>
  </list>
</result>
""".decode("unicode_escape").encode("utf-8")  # 안전한 한글 인코딩


def _make_zip(xml_bytes: bytes) -> bytes:
    """XML 을 ZIP 으로 패킹 (DART corpCode.xml 응답 형식 모사)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("CORPCODE.xml", xml_bytes)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────
# parse_corp_code_xml
# ─────────────────────────────────────────────────────────────


class TestParse:
    def test_parses_three_rows(self):
        # _SAMPLE_XML 가 직접 한글 문자열로 잘못 인코딩될 수 있어 명시 구성
        xml = (
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<result>"
            "<list><corp_code>00126380</corp_code>"
            "<corp_name>삼성전자</corp_name>"
            "<corp_eng_name>SAMSUNG ELECTRONICS CO., LTD.</corp_eng_name>"
            "<stock_code>005930</stock_code>"
            "<modify_date>20240101</modify_date></list>"
            "<list><corp_code>01234567</corp_code>"
            "<corp_name>아진산업</corp_name>"
            "<corp_eng_name>AJIN INDUSTRIAL CO., LTD.</corp_eng_name>"
            "<stock_code>002990</stock_code>"
            "<modify_date>20240515</modify_date></list>"
            "</result>"
        ).encode("utf-8")
        from scripts.lookup_dart_corp_code import parse_corp_code_xml
        rows = parse_corp_code_xml(_make_zip(xml))
        assert len(rows) == 2
        assert rows[0]["corp_code"] == "00126380"
        assert rows[0]["corp_name"] == "삼성전자"
        assert rows[1]["corp_eng_name"] == "AJIN INDUSTRIAL CO., LTD."

    def test_empty_zip_raises(self):
        from scripts.lookup_dart_corp_code import parse_corp_code_xml
        empty_zip = io.BytesIO()
        with zipfile.ZipFile(empty_zip, "w") as _:
            pass
        with pytest.raises(ValueError, match="XML"):
            parse_corp_code_xml(empty_zip.getvalue())


# ─────────────────────────────────────────────────────────────
# search
# ─────────────────────────────────────────────────────────────


class TestSearch:
    @pytest.fixture
    def rows(self):
        return [
            {"corp_code": "00126380", "corp_name": "삼성전자",
             "corp_eng_name": "SAMSUNG ELECTRONICS CO., LTD.",
             "stock_code": "005930", "modify_date": "20240101"},
            {"corp_code": "01234567", "corp_name": "아진산업",
             "corp_eng_name": "AJIN INDUSTRIAL CO., LTD.",
             "stock_code": "002990", "modify_date": "20240515"},
            {"corp_code": "09876543", "corp_name": "주식회사 아진",
             "corp_eng_name": "ajin corp.", "stock_code": "",
             "modify_date": "20231220"},
        ]

    def test_korean_partial(self, rows):
        from scripts.lookup_dart_corp_code import search
        out = search("아진", rows)
        assert len(out) == 2
        # 두 개 모두 '아진' 포함 (아진산업 + 주식회사 아진)
        ids = {r["corp_code"] for r in out}
        assert {"01234567", "09876543"}.issubset(ids)

    def test_english_partial_case_insensitive(self, rows):
        from scripts.lookup_dart_corp_code import search
        out = search("ajin", rows)
        assert len(out) == 2

    def test_stock_code(self, rows):
        from scripts.lookup_dart_corp_code import search
        out = search("005930", rows)
        assert len(out) == 1
        assert out[0]["corp_code"] == "00126380"

    def test_corp_code_8digit_direct(self, rows):
        from scripts.lookup_dart_corp_code import search
        out = search("01234567", rows)
        assert len(out) == 1
        assert out[0]["corp_name"] == "아진산업"

    def test_no_match(self, rows):
        from scripts.lookup_dart_corp_code import search
        assert search("XYZ존재안함", rows) == []

    def test_empty_query(self, rows):
        from scripts.lookup_dart_corp_code import search
        assert search("", rows) == []
        assert search("   ", rows) == []


# ─────────────────────────────────────────────────────────────
# fetch_corp_code_zip — JSON 에러 응답 처리
# ─────────────────────────────────────────────────────────────


class TestFetch:
    def test_no_api_key_raises(self):
        from scripts.lookup_dart_corp_code import fetch_corp_code_zip
        with pytest.raises(ValueError, match="DART_API_KEY"):
            fetch_corp_code_zip("")


# ─────────────────────────────────────────────────────────────
# write_corp_code_to_env
# ─────────────────────────────────────────────────────────────


class TestWriteEnv:
    def test_appends_when_missing(self, tmp_path):
        from scripts.lookup_dart_corp_code import write_corp_code_to_env
        env = tmp_path / ".env"
        env.write_text("OTHER_KEY=value\n", encoding="utf-8")
        updated = write_corp_code_to_env("00126380", env_path=env)
        assert updated is True
        assert "DART_CORP_CODE=00126380" in env.read_text(encoding="utf-8")

    def test_replaces_existing(self, tmp_path):
        from scripts.lookup_dart_corp_code import write_corp_code_to_env
        env = tmp_path / ".env"
        env.write_text(
            "OTHER=v\nDART_CORP_CODE=00000000\nMORE=z\n",
            encoding="utf-8",
        )
        updated = write_corp_code_to_env("99999999", env_path=env)
        assert updated is True
        text = env.read_text(encoding="utf-8")
        assert "DART_CORP_CODE=99999999" in text
        assert "DART_CORP_CODE=00000000" not in text
        assert "MORE=z" in text  # 다른 라인 보존

    def test_idempotent_same_value(self, tmp_path):
        from scripts.lookup_dart_corp_code import write_corp_code_to_env
        env = tmp_path / ".env"
        env.write_text("DART_CORP_CODE=00126380\n", encoding="utf-8")
        updated = write_corp_code_to_env("00126380", env_path=env)
        assert updated is False
