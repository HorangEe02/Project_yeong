"""v3.3 Phase G — 파일 추출기 패키지.

CAD/HWP 등 제조업 특화 형식의 텍스트 추출 + 메타 + 미리보기.
기존 ``core/llm_client.extract_text_from_file`` 와 별개의 확장 dispatcher.

사용:
    from core.file_extractors import extract_with_meta, SUPPORTED_EXTENSIONS

    result = extract_with_meta(file_bytes, filename="drawing.dxf")
    # result = {"text": str, "metadata": {...}, "preview_image_b64": str}
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Phase G-1 지원 확장자 매트릭스
TEXT_CAD_EXTENSIONS = {".dxf", ".step", ".stp", ".igs", ".iges"}
BINARY_CAD_EXTENSIONS = {".sldprt", ".sldasm", ".prt", ".catpart", ".catproduct"}
HWP_EXTENSIONS = {".hwp"}  # .hwpx 는 ZIP/XML 형식이라 기존 _extract_hwpx (llm_client.py) 처리

SUPPORTED_EXTENSIONS = TEXT_CAD_EXTENSIONS | BINARY_CAD_EXTENSIONS | HWP_EXTENSIONS

# v3.3 Phase G-3 — LLM 컨텍스트 보호 한도.
# 16KB 초과 시 head 8KB + tail 4KB + 중간 [SKIPPED] 마커로 압축.
# 마커는 LLM 이 잘림을 인식할 수 있도록 명시적 텍스트 사용.
_TEXT_COMPRESSION_THRESHOLD = 16 * 1024
_HEAD_SIZE = 8 * 1024
_TAIL_SIZE = 4 * 1024


def _compress_text(text: str) -> tuple[str, dict]:
    """추출 텍스트가 한도를 넘으면 head/tail 만 남기고 중간을 [SKIPPED] 마커로 치환.

    Returns:
        (압축된_텍스트, {"truncated": bool, "original_chars": int, "skipped_chars": int})
    """
    n = len(text)
    if n <= _TEXT_COMPRESSION_THRESHOLD:
        return text, {"truncated": False, "original_chars": n, "skipped_chars": 0}

    head = text[:_HEAD_SIZE]
    tail = text[-_TAIL_SIZE:]
    skipped = n - _HEAD_SIZE - _TAIL_SIZE
    compressed = (
        f"[FILE_HEAD]\n{head}\n\n"
        f"[SKIPPED {skipped:,} chars — 파일이 너무 커서 head/tail 만 LLM 컨텍스트에 주입됨]\n\n"
        f"[FILE_TAIL]\n{tail}"
    )
    return compressed, {
        "truncated": True,
        "original_chars": n,
        "skipped_chars": skipped,
    }


def extract_with_meta(data: bytes, filename: str = "") -> dict:
    """확장자 기반 dispatcher — 적절한 추출기 호출.

    Returns:
        {
            "text": str,                  # LLM 컨텍스트에 주입할 텍스트
            "metadata": dict,             # format / size_bytes / summary / extracted_chars / ...
            "preview_image_b64": str,     # PNG base64 (DXF 등 — 없으면 빈 문자열)
        }

    지원 외 확장자 / 미지원 라이브러리: 빈 결과 + error 메타.
    """
    ext = Path(filename).suffix.lower()
    raw: dict | None = None

    if ext == ".dxf":
        from core.file_extractors import dxf
        raw = dxf.extract(data)
    elif ext in (".step", ".stp"):
        from core.file_extractors import step
        raw = step.extract(data)
    elif ext in (".igs", ".iges"):
        from core.file_extractors import iges
        raw = iges.extract(data)
    elif ext in BINARY_CAD_EXTENSIONS:
        from core.file_extractors import binary_cad
        raw = binary_cad.extract(data, filename=filename)
    elif ext == ".hwp":
        from core.file_extractors import hwp
        raw = hwp.extract(data)

    if raw is not None:
        # v3.3 Phase G-3 — LLM 컨텍스트 보호: 16KB 초과 시 head/tail 압축
        compressed, trunc_meta = _compress_text(raw.get("text", ""))
        return {
            "text": compressed,
            "metadata": {**raw.get("metadata", {}), **trunc_meta},
            "preview_image_b64": raw.get("preview_image_b64", ""),
        }

    # 미지원 확장자
    return {
        "text": "",
        "metadata": {
            "format": ext.upper().lstrip(".") if ext else "UNKNOWN",
            "size_bytes": len(data),
            "summary": f"미지원 확장자: {ext}",
            "extracted_chars": 0,
            "error": "unsupported_extension",
        },
        "preview_image_b64": "",
    }
