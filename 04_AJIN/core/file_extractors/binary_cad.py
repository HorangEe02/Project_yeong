"""v3.3 Phase G-1 — 바이너리 CAD 파일 (.sldprt, .sldasm, .prt, .catpart, .catproduct).

이 형식들은 회사별 폐쇄 포맷이라 텍스트 추출이 불가능하다.
첨부 자체는 허용하되 메타(파일명·크기·MIME)만 LLM 컨텍스트에 전달.
사용자가 도면 핵심 사항을 텍스트로 부연 설명하도록 안내한다.
"""

from __future__ import annotations

from pathlib import Path

_FORMAT_LABEL = {
    ".sldprt":     "SolidWorks Part",
    ".sldasm":     "SolidWorks Assembly",
    ".prt":        "Creo / NX Part",
    ".catpart":    "CATIA Part",
    ".catproduct": "CATIA Product (Assembly)",
}


def extract(data: bytes, filename: str = "") -> dict:
    """바이너리 CAD — 메타만 반환 + 사용자에게 텍스트 부연 요청 안내."""
    ext = Path(filename).suffix.lower()
    label = _FORMAT_LABEL.get(ext, "3D 부품 파일")
    size_mb = len(data) / (1024 * 1024)
    size_kb = len(data) / 1024

    size_str = f"{size_mb:.1f}MB" if size_mb >= 1 else f"{size_kb:.1f}KB"
    summary = f"{label} · {size_str} (바이너리 — 텍스트 추출 불가)"

    text = (
        f"[3D 부품 파일 첨부]\n"
        f"형식: {label}\n"
        f"파일명: {filename}\n"
        f"크기: {size_str}\n\n"
        f"이 형식은 폐쇄 바이너리 포맷이라 자동 텍스트 추출이 불가능합니다. "
        f"필요 시 도면의 핵심 사항(부품번호, 치수, 재질 등)을 텍스트로 함께 입력해 주세요."
    )

    return {
        "text": text,
        "metadata": {
            "format": label,
            "size_bytes": len(data),
            "summary": summary,
            "extracted_chars": len(text),
            "binary_only": True,
        },
        "preview_image_b64": "",
    }
