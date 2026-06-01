"""v3.3 Phase G-1 — IGES (.igs / .iges) 추출기.

IGES 는 80-컬럼 고정폭 ASCII 형식. 컬럼 73 이 섹션 식별자:
- S (Start)     — 사람이 읽는 헤더 (자유 형식)
- G (Global)    — 글로벌 파라미터 (제품명, 단위 등)
- D (Directory) — 엔티티 디렉토리 (2 라인 × 엔티티)
- P (Parameter) — 엔티티 파라미터
- T (Terminate) — 종료
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def extract(data: bytes) -> dict:
    """IGES S(Start) + G(Global) 섹션 추출."""
    metadata: dict = {
        "format": "IGES",
        "size_bytes": len(data),
    }

    try:
        text = data.decode("ascii", errors="replace")
    except Exception:
        text = data.decode("latin-1", errors="replace")

    lines = text.splitlines()
    if not lines:
        return {
            "text": "",
            "metadata": {**metadata, "summary": "빈 파일", "extracted_chars": 0,
                         "error": "empty"},
            "preview_image_b64": "",
        }

    # 컬럼 73 으로 섹션 분류 (1-indexed → Python 72)
    sections: dict[str, list[str]] = {"S": [], "G": [], "D": [], "P": [], "T": []}
    for line in lines:
        if len(line) < 73:
            continue
        sec = line[72:73].upper()
        if sec in sections:
            content = line[:72].rstrip()
            sections[sec].append(content)

    if not sections["S"] and not sections["G"]:
        return {
            "text": "",
            "metadata": {
                **metadata,
                "summary": "IGES 섹션 식별자(S/G) 부재 — 형식 손상 또는 비표준",
                "extracted_chars": 0,
                "error": "not_iges",
            },
            "preview_image_b64": "",
        }

    text_parts = ["[IGES 메타]"]

    # S 섹션 — 헤더 (사람 읽는 텍스트)
    if sections["S"]:
        s_text = "\n".join(sections["S"][:20])
        text_parts.append(f"S(Start) 섹션 ({len(sections['S'])} 라인):")
        text_parts.append(s_text)

    # G 섹션 — 글로벌 파라미터 (제품명, 단위, 작성자 등)
    if sections["G"]:
        g_text = "".join(sections["G"][:10])
        text_parts.append(f"\nG(Global) 섹션 ({len(sections['G'])} 라인):")
        # G 섹션은 콤마로 구분된 파라미터들. 첫 N개만 가독성 있게.
        params = g_text.split(",")[:18]
        text_parts.append("파라미터: " + " | ".join(p.strip() for p in params if p.strip()))

    # D / P / T 카운트만
    text_parts.append(
        f"\nD(Directory) 라인: {len(sections['D'])} | "
        f"P(Parameter) 라인: {len(sections['P'])} | "
        f"T(Terminate) 라인: {len(sections['T'])}"
    )

    extracted = "\n".join(text_parts)
    # IGES 디렉토리 라인은 엔티티당 2 라인 → 엔티티 수 추정
    entity_count = len(sections["D"]) // 2

    summary = (
        f"IGES {len(data) / 1024:.1f}KB · 엔티티 ~{entity_count} · "
        f"S={len(sections['S'])} G={len(sections['G'])} D={len(sections['D'])}"
    )

    return {
        "text": extracted,
        "metadata": {
            **metadata,
            "summary": summary,
            "extracted_chars": len(extracted),
            "entity_count": entity_count,
            "section_counts": {k: len(v) for k, v in sections.items()},
        },
        "preview_image_b64": "",
    }
