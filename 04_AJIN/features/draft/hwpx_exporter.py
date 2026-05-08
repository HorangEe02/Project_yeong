"""v3.6 — 정식 OWPML HWPX 생성기.

이전 버전(ODT를 .hwpx 확장자로 위장)은 rhwp 뷰어 등에서
"필수 파일 누락: Contents/content.hpf" 오류로 거부되었다.

본 모듈은 Hancom OWPML 1.4 사양에 맞춰 최소 유효 HWPX 패키지를 생성한다.
패키지 구조:
    mimetype                          (application/hwp+zip, 비압축, 첫 엔트리)
    META-INF/container.xml            (rootfile 지정 → Contents/content.hpf)
    Contents/content.hpf              (OPF 패키지 매니페스트)
    Contents/header.xml               (문서 속성)
    Contents/section0.xml             (본문)
    settings.xml                      (옵션 설정)
    version.xml                       (버전)

호환:
    한컴오피스 2018+, rhwp 0.7+, 한컴 한글뷰어, LibreOffice(부분 지원)
"""
from __future__ import annotations

import re
import zipfile
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path


# OWPML XML 네임스페이스 — Hancom 사양 기준
_NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"
_NS_HS = "http://www.hancom.co.kr/hwpml/2011/section"
_NS_OPF = "http://www.idpf.org/2007/opf/"
_NS_DC = "http://purl.org/dc/elements/1.1/"
_NS_OOXMLSCHEMAS = "http://www.hancom.co.kr/schemas/2018/version"
_NS_CONTAINER = "urn:hwpx:names:tc:opendocument:xmlns:container"


class HwpxExporter:
    """마크다운 초안을 정식 OWPML HWPX 파일로 변환한다."""

    def export_bytes(
        self,
        markdown_text: str,
        doc_title: str = "",
        doc_type: str = "",
    ) -> bytes:
        """마크다운 텍스트를 OWPML 바이트로 변환한다."""
        buffer = BytesIO()

        # 1. mimetype — 반드시 비압축 + ZIP 첫 번째 엔트리 (OWPML 사양)
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zf:
            zf.writestr("mimetype", "application/hwp+zip")

        # 2. 나머지 파일 — DEFLATE 압축
        with zipfile.ZipFile(buffer, "a", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("META-INF/container.xml", self._build_container())
            zf.writestr("Contents/content.hpf", self._build_content_hpf(doc_title))
            zf.writestr("Contents/header.xml", self._build_header())
            zf.writestr(
                "Contents/section0.xml",
                self._build_section(markdown_text, doc_title, doc_type),
            )
            zf.writestr("settings.xml", self._build_settings())
            zf.writestr("version.xml", self._build_version())

        return buffer.getvalue()

    def export(
        self,
        markdown_text: str,
        output_path: Path,
        doc_title: str = "",
        doc_type: str = "",
    ) -> Path:
        """마크다운 텍스트를 파일로 저장한다."""
        data = self.export_bytes(markdown_text, doc_title, doc_type)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
        return output_path

    # ─────────────────────────────────────────────
    # 패키지 메타 파일
    # ─────────────────────────────────────────────

    def _build_container(self) -> str:
        """META-INF/container.xml — rootfile 위치 선언."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<container xmlns="{_NS_CONTAINER}">
  <rootfiles>
    <rootfile full-path="Contents/content.hpf" media-type="application/hwpml-package+xml"/>
  </rootfiles>
</container>
"""

    def _build_content_hpf(self, title: str) -> str:
        """Contents/content.hpf — OPF 매니페스트 (필수 파일).

        rhwp v0.7.7 가 검증할 때 가장 먼저 확인하는 파일.
        """
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        doc_id = f"hwpx-{uuid.uuid4().hex[:12]}"
        safe_title = _esc(title or "AJIN AI Assistant Document")
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<opf:package xmlns:opf="{_NS_OPF}" version="1.4" unique-identifier="hwpx-id">
  <opf:metadata xmlns:dc="{_NS_DC}" xmlns:opf2="{_NS_OPF}">
    <opf:meta opf:name="title" opf:content="{safe_title}"/>
    <dc:title>{safe_title}</dc:title>
    <dc:language>ko</dc:language>
    <dc:creator>AJIN AI Assistant</dc:creator>
    <dc:identifier opf:id="hwpx-id" opf:scheme="UUID">{doc_id}</dc:identifier>
    <dc:date>{now}</dc:date>
    <opf:meta opf:name="generator" opf:content="AJIN AI Assistant v3.6"/>
  </opf:metadata>
  <opf:manifest>
    <opf:item id="header" href="header.xml" media-type="application/xml"/>
    <opf:item id="section0" href="section0.xml" media-type="application/xml"/>
  </opf:manifest>
  <opf:spine>
    <opf:itemref idref="section0" linear="yes"/>
  </opf:spine>
</opf:package>
"""

    def _build_version(self) -> str:
        """version.xml — OWPML 버전 표기."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<hv:HWPVersion xmlns:hv="{_NS_OOXMLSCHEMAS}"
               targetApplication="WORDPROCESSOR"
               major="5" minor="1" micro="0" buildNumber="0"/>
"""

    def _build_settings(self) -> str:
        """settings.xml — 보기/페이지 설정."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<ha:HWPApplicationSetting xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app"/>
"""

    # ─────────────────────────────────────────────
    # 본문 콘텐츠
    # ─────────────────────────────────────────────

    def _build_header(self) -> str:
        """Contents/header.xml — 문서 속성 (폰트/스타일/단락) 헤더."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<hh:head xmlns:hh="{_NS_HH}" version="1.4" secCnt="1">
  <hh:beginNum page="1" footnote="1" endnote="1" pic="1" tbl="1" equation="1"/>
  <hh:refList>
    <hh:fontfaces itemCnt="1">
      <hh:fontface lang="HANGUL" fontCnt="1">
        <hh:font id="0" face="맑은 고딕" type="TTF" isEmbedded="0"/>
      </hh:fontface>
    </hh:fontfaces>
    <hh:borderFills itemCnt="1">
      <hh:borderFill id="1" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">
        <hh:slash type="NONE" Crooked="0" isCounter="0"/>
        <hh:backSlash type="NONE" Crooked="0" isCounter="0"/>
        <hh:leftBorder type="SOLID" width="0.1mm" color="#000000"/>
        <hh:rightBorder type="SOLID" width="0.1mm" color="#000000"/>
        <hh:topBorder type="SOLID" width="0.1mm" color="#000000"/>
        <hh:bottomBorder type="SOLID" width="0.1mm" color="#000000"/>
        <hh:diagonal type="SOLID" width="0.1mm" color="#000000"/>
      </hh:borderFill>
    </hh:borderFills>
    <hh:charProperties itemCnt="1">
      <hh:charPr id="0" height="1000" textColor="#000000" shadeColor="none" useFontSpace="0" useKerning="0">
        <hh:fontRef hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>
        <hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>
        <hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>
        <hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>
        <hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>
      </hh:charPr>
    </hh:charProperties>
    <hh:paraProperties itemCnt="1">
      <hh:paraPr id="0" tabPrIDRef="0" condense="0" fontLineHeight="0" snapToGrid="1" suppressLineNumbers="0" checked="0">
        <hh:align horizontal="JUSTIFY" vertical="BASELINE"/>
        <hh:heading type="NONE" idRef="0" level="0"/>
        <hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" widowOrphan="0" keepWithNext="0" keepLines="0" pageBreakBefore="0" lineWrap="BREAK"/>
        <hh:margin>
          <hh:intent value="0"/>
          <hh:left value="0"/>
          <hh:right value="0"/>
          <hh:prev value="0"/>
          <hh:next value="0"/>
        </hh:margin>
        <hh:lineSpacing type="PERCENT" value="160" unit="HWPUNIT"/>
        <hh:border borderFillIDRef="1" offsetLeft="0" offsetRight="0" offsetTop="0" offsetBottom="0" connect="0" ignoreMargin="0"/>
      </hh:paraPr>
    </hh:paraProperties>
    <hh:styles itemCnt="1">
      <hh:style id="0" type="PARA" name="바탕글" engName="Normal" paraPrIDRef="0" charPrIDRef="0" nextStyleIDRef="0" langID="1042" lockForm="0"/>
    </hh:styles>
  </hh:refList>
</hh:head>
"""

    def _build_section(self, markdown_text: str, title: str, doc_type: str) -> str:
        """Contents/section0.xml — 본문 섹션."""
        paras: list[str] = []

        # 회사명
        paras.append(_para("아진산업(주)", bold=True, size=1600))
        if title:
            paras.append(_para(title, bold=True, size=1800))
        paras.append(_para(""))

        # 결재란 (보고서 유형) — 단순 4컬럼 표 대신 단락으로 표기 (테이블 OWPML 복잡)
        if doc_type.startswith("report_"):
            today = datetime.now().strftime("%Y.%m.%d")
            paras.append(_para(f"[작성: ___ / 검토: ___ / 승인: ___ / 일자: {today}]"))
            paras.append(_para(""))

        # 본문 파싱
        lines = markdown_text.split("\n")
        for line in lines:
            stripped = line.strip()
            if not stripped:
                paras.append(_para(""))
                continue
            if line.startswith("# "):
                paras.append(_para(line[2:].strip(), bold=True, size=1600))
            elif line.startswith("## "):
                paras.append(_para(line[3:].strip(), bold=True, size=1400))
            elif line.startswith("### "):
                paras.append(_para(line[4:].strip(), bold=True, size=1200))
            elif stripped in ("---", "───", "***"):
                paras.append(_para("─" * 50))
            elif stripped.startswith("- ") or stripped.startswith("· "):
                paras.append(_para(f"• {stripped[2:]}"))
            elif re.match(r"^\s*\d+\.", line):
                paras.append(_para(stripped))
            elif stripped.startswith("|") and stripped.endswith("|"):
                # 마크다운 표 — 단순 텍스트로 변환 (OWPML 표는 별도 작업)
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                # 구분선 행 (---|---|---) 은 스킵
                if all(re.match(r"^[\s\-:]+$", c) for c in cells):
                    continue
                paras.append(_para("  " + "  |  ".join(cells)))
            else:
                paras.append(_para(stripped))

        # 푸터
        paras.append(_para(""))
        paras.append(_para("─" * 50))
        paras.append(_para(
            "아진산업(주) | 경북 경산시 진량읍 공단8로 26길 40 | TEL 053-856-9100"
        ))
        paras.append(_para("Confidential — 본 문서는 사내 업무용으로 작성되었습니다."))

        body = "\n".join(paras)

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="{_NS_HS}" xmlns:hp="{_NS_HP}" xmlns:hh="{_NS_HH}">
{body}
</hs:sec>
"""


# ─────────────────────────────────────────────
# 단락 빌더
# ─────────────────────────────────────────────

def _para(text: str, *, bold: bool = False, size: int = 1000) -> str:
    """OWPML 단락 1개.

    Args:
        text: 단락 텍스트
        bold: 굵게 여부
        size: HWP 단위 글자 크기 (1pt = 100, 10pt = 1000)
    """
    escaped = _esc(text)
    # 인라인 굵게 (**...**)
    escaped = re.sub(
        r"\*\*(.+?)\*\*",
        r'</hp:t><hp:t><hp:bold>\1</hp:bold></hp:t><hp:t>',
        escaped,
    )
    bold_attr = f' <hp:bold>1</hp:bold>' if bold else ""
    return (
        '  <hp:p paraPrIDRef="0" styleIDRef="0">\n'
        f'    <hp:run charPrIDRef="0">{bold_attr}\n'
        f"      <hp:t>{escaped}</hp:t>\n"
        "    </hp:run>\n"
        "    <hp:linesegarray>\n"
        '      <hp:lineseg textpos="0" vertpos="0" vertsize="' + str(size) + '" textheight="' + str(size) + '" baseline="' + str(int(size * 0.85)) + '" spacing="600" horzpos="0" horzsize="42520" flags="393216"/>\n'
        "    </hp:linesegarray>\n"
        "  </hp:p>"
    )


def _esc(text: str) -> str:
    """XML 특수문자 이스케이프."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
