"""v3.3 Phase G-1 — STEP (.step / .stp, ISO 10303) 추출기.

STEP 은 텍스트 기반 — HEADER 섹션 + DATA 섹션 (수만~수백만 줄).
DATA 섹션 전체는 너무 크므로:
- HEADER 섹션 전체 추출 (FILE_DESCRIPTION, FILE_NAME, FILE_SCHEMA)
- DATA 섹션에서 PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE / APPLICATION_PROTOCOL_DEFINITION
  같은 메타 라인만 정규식으로 추출
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# STEP 파일은 ISO 8859-1 (Latin-1) 인코딩이 표준
_STEP_ENCODING = "latin-1"

# 메타 라인 추출 정규식 — DATA 섹션 안의 PRODUCT, APPLICATION_PROTOCOL 등
_META_PATTERNS = [
    re.compile(r"FILE_DESCRIPTION\s*\([^)]*\)", re.IGNORECASE),
    re.compile(r"FILE_NAME\s*\([^)]*\)", re.IGNORECASE),
    re.compile(r"FILE_SCHEMA\s*\([^)]*\)", re.IGNORECASE),
    re.compile(r"APPLICATION_PROTOCOL_DEFINITION\s*\([^)]*\)", re.IGNORECASE),
    re.compile(r"PRODUCT\s*\([^)]*\)", re.IGNORECASE),
    re.compile(r"PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE\s*\([^)]*\)", re.IGNORECASE),
]


def extract(data: bytes) -> dict:
    """STEP 헤더 + 메타 라인 추출."""
    metadata: dict = {
        "format": "STEP",
        "size_bytes": len(data),
    }

    try:
        text = data.decode(_STEP_ENCODING, errors="replace")
    except Exception as e:
        logger.warning("STEP 디코딩 실패: %s", e)
        return {
            "text": "",
            "metadata": {**metadata, "summary": "디코딩 실패", "extracted_chars": 0,
                         "error": "decode_failed"},
            "preview_image_b64": "",
        }

    # ISO-10303-21 헤더 검증
    if not text.lstrip().startswith("ISO-10303-21"):
        return {
            "text": "",
            "metadata": {
                **metadata,
                "summary": "STEP 형식이 아님 (ISO-10303-21 헤더 부재)",
                "extracted_chars": 0,
                "error": "not_step",
            },
            "preview_image_b64": "",
        }

    # HEADER 섹션 추출
    header_match = re.search(r"HEADER\s*;\s*(.*?)\s*ENDSEC\s*;", text, re.DOTALL | re.IGNORECASE)
    header_section = header_match.group(1).strip() if header_match else ""

    # DATA 섹션에서 메타 라인 추출 (전체 DATA 본문은 무시)
    data_match = re.search(r"DATA\s*;\s*(.*?)\s*ENDSEC\s*;", text, re.DOTALL | re.IGNORECASE)
    data_meta_lines: list[str] = []
    if data_match:
        data_section = data_match.group(1)
        for pat in _META_PATTERNS[3:]:  # FILE_* 는 HEADER 에서 처리됨
            for m in pat.finditer(data_section):
                line = m.group(0)
                if len(line) <= 300:  # 너무 긴 라인은 스킵
                    data_meta_lines.append(line)
                if len(data_meta_lines) >= 10:
                    break
            if len(data_meta_lines) >= 10:
                break

    # DATA 라인 총 카운트 (대략적)
    data_line_count = 0
    if data_match:
        data_line_count = data_match.group(1).count("\n")

    text_parts = ["[STEP 메타]"]
    if header_section:
        # HEADER 는 보통 200~600 chars
        text_parts.append("HEADER:")
        text_parts.append(header_section[:1000])
    if data_meta_lines:
        text_parts.append(f"\nDATA 메타 라인 ({len(data_meta_lines)}건):")
        text_parts.extend(data_meta_lines)
    if data_line_count:
        text_parts.append(f"\nDATA 섹션 총 라인 수: ~{data_line_count}")

    extracted = "\n".join(text_parts)
    summary = (
        f"STEP {len(data) / 1024:.1f}KB · DATA 라인 ~{data_line_count} · 메타 {len(data_meta_lines)}건"
    )

    return {
        "text": extracted,
        "metadata": {
            **metadata,
            "summary": summary,
            "extracted_chars": len(extracted),
            "data_line_count": data_line_count,
            "meta_line_count": len(data_meta_lines),
        },
        "preview_image_b64": "",
    }
