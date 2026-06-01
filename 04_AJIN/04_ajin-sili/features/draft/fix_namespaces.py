"""HWPX 네임스페이스 표준화 후처리.

python-hwpx 가 생성한 HWPX 파일의 XML 안에는 라이브러리가 자동으로 매긴
`ns0:`, `ns1:` 등 임시 프리픽스가 섞여 들어가는 경우가 있다. 한컴오피스
(특히 macOS 빌드)는 이 임시 프리픽스를 인식하지 못해 빈 페이지로 표시한다.

본 모듈은 HWPX ZIP 패키지를 열어 모든 XML 엔트리의 임시 프리픽스를
한컴 OWPML 표준 프리픽스로 치환한다.

참고: github.com/Canine89/gonggong_hwpxskills (SKILL.md fix_namespaces 패턴)
"""

from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from pathlib import Path

# 한컴 OWPML 표준 프리픽스 매핑 (네임스페이스 URI → 표준 prefix)
_STANDARD_PREFIXES: dict[str, str] = {
    "http://www.hancom.co.kr/hwpml/2011/head": "hh",
    "http://www.hancom.co.kr/hwpml/2011/core": "hc",
    "http://www.hancom.co.kr/hwpml/2011/paragraph": "hp",
    "http://www.hancom.co.kr/hwpml/2011/section": "hs",
}

# 임시 프리픽스 패턴 (python-hwpx 가 자동 부여하는 ns0:, ns1: 등)
_TEMP_PREFIX_RE = re.compile(r"\bns\d+:")
_TEMP_XMLNS_RE = re.compile(r'xmlns:ns\d+="([^"]+)"')

# mimetype / META-INF/container.xml 같은 비-OWPML 엔트리 (수정 불필요)
_SKIP_ENTRIES = {"mimetype", "META-INF/container.xml"}


def fix_namespaces(hwpx_path: str | Path) -> Path:
    """HWPX 파일의 XML 네임스페이스를 한컴 표준 프리픽스로 정규화한다.

    Args:
        hwpx_path: 수정할 HWPX 파일 경로 (in-place 수정).

    Returns:
        수정된 파일의 Path.
    """
    hwpx_path = Path(hwpx_path)
    if not hwpx_path.exists():
        raise FileNotFoundError(f"HWPX 파일 없음: {hwpx_path}")

    # 1) 원본 파일을 임시 디렉토리에 풀어서 각 XML 수정
    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)

        with zipfile.ZipFile(hwpx_path, "r") as src_zip:
            entries = src_zip.namelist()
            for name in entries:
                src_zip.extract(name, tmpdir)

        for name in entries:
            if name in _SKIP_ENTRIES or not name.lower().endswith(".xml"):
                continue
            entry_path = tmpdir / name
            try:
                text = entry_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            new_text = _normalize_xml_namespaces(text)
            if new_text != text:
                entry_path.write_text(new_text, encoding="utf-8")

        # 2) 새 ZIP 으로 재패키징 (mimetype 은 반드시 비압축 + 첫 엔트리)
        tmp_out = Path(tempfile.mkstemp(suffix=".hwpx")[1])
        try:
            mimetype_entry = "mimetype"
            mimetype_path = tmpdir / mimetype_entry

            with zipfile.ZipFile(tmp_out, "w") as out_zip:
                if mimetype_path.exists():
                    out_zip.write(
                        mimetype_path,
                        mimetype_entry,
                        compress_type=zipfile.ZIP_STORED,
                    )

                for name in entries:
                    if name == mimetype_entry:
                        continue
                    entry_path = tmpdir / name
                    if entry_path.is_file():
                        out_zip.write(entry_path, name, compress_type=zipfile.ZIP_DEFLATED)

            # 원본 자리에 교체
            shutil.move(str(tmp_out), str(hwpx_path))
        except Exception:
            if tmp_out.exists():
                tmp_out.unlink(missing_ok=True)
            raise

    return hwpx_path


def _normalize_xml_namespaces(xml_text: str) -> str:
    """XML 본문 안의 임시 프리픽스(ns0:, ns1:)를 표준으로 교체."""

    # (a) xmlns:nsN="URI" 선언을 표준 prefix 선언으로 변환하면서 매핑 수집
    prefix_remap: dict[str, str] = {}

    def _replace_xmlns(match: re.Match[str]) -> str:
        uri = match.group(1)
        full_attr = match.group(0)  # xmlns:nsN="URI"
        # 원래 prefix 추출 — xmlns:nsN
        original_prefix_match = re.match(r'xmlns:(ns\d+)=', full_attr)
        if not original_prefix_match:
            return full_attr
        original_prefix = original_prefix_match.group(1)

        if uri in _STANDARD_PREFIXES:
            std_prefix = _STANDARD_PREFIXES[uri]
            prefix_remap[original_prefix] = std_prefix
            return f'xmlns:{std_prefix}="{uri}"'
        return full_attr

    xml_text = _TEMP_XMLNS_RE.sub(_replace_xmlns, xml_text)

    # (b) 본문 안의 nsN:tag → std_prefix:tag 치환
    if prefix_remap:
        def _replace_tag(match: re.Match[str]) -> str:
            token = match.group(0)  # 예: "ns0:"
            original = token.rstrip(":")
            std = prefix_remap.get(original)
            if std:
                return f"{std}:"
            return token

        xml_text = _TEMP_PREFIX_RE.sub(_replace_tag, xml_text)

    return xml_text


__all__ = ["fix_namespaces"]
