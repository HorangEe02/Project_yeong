"""v3.3 Phase G-1 — HWP 5.0 (한컴 한글 바이너리) 텍스트 추출기.

HWP 5.0 은 OLE Compound Document 형식 (Microsoft 의 .doc 와 동일 컨테이너).
- 1차: olefile 로 ``PrvText`` 스트림(미리보기 텍스트, UTF-16LE) 시도.
- 2차: ``BodyText/Section0`` 등 본문 스트림 — 압축 해제 + 레코드 파싱이 복잡해
       완전한 본문 추출은 pyhwp / hwp5 라이브러리에 위임 (옵션).
- 3차: 둘 다 실패 시 안내 메시지.

올바른 출력 시그니처:
    {"text": str, "metadata": {format, summary, extracted_chars, ...}, "preview_image_b64": ""}
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


def extract(data: bytes) -> dict:
    """HWP 5.0 본문/미리보기 텍스트 추출."""
    metadata: dict = {
        "format": "HWP",
        "size_bytes": len(data),
    }
    text = ""

    # 1) olefile 1차 — PrvText 미리보기 (UTF-16LE)
    try:
        import olefile  # type: ignore
    except ImportError:
        logger.info("olefile 미설치 — HWP 추출 불가")
        return {
            "text": "",
            "metadata": {
                **metadata,
                "summary": "HWP 추출 라이브러리(olefile) 미설치",
                "extracted_chars": 0,
                "error": "olefile_not_installed",
            },
            "preview_image_b64": "",
        }

    try:
        if not olefile.isOleFile(io.BytesIO(data)):
            return {
                "text": "",
                "metadata": {
                    **metadata,
                    "summary": "OLE 형식이 아닌 파일 (손상 또는 비표준 HWP)",
                    "extracted_chars": 0,
                    "error": "not_ole",
                },
                "preview_image_b64": "",
            }

        ole = olefile.OleFileIO(io.BytesIO(data))
        try:
            # PrvText — 가장 안정적. 보통 100~500자 미리보기.
            if ole.exists("PrvText"):
                with ole.openstream("PrvText") as stream:
                    raw = stream.read()
                # HWP 5.0 의 PrvText 는 UTF-16LE 인코딩 (BOM 없음)
                text = raw.decode("utf-16-le", errors="replace").rstrip("\x00").strip()
        finally:
            ole.close()
    except Exception as e:
        logger.warning("HWP olefile 추출 실패: %s", e)

    # 2) pyhwp 폴백 (옵션) — 본문 전체 시도
    if not text:
        try:
            from hwp5.proc import importhook  # type: ignore  # noqa: F401
            from hwp5.dataio import ParseError  # type: ignore  # noqa: F401

            # pyhwp 는 file path 기반이므로 임시 파일 우회 — 환경에 따라 호환성 이슈
            # 본 단계에서는 PrvText 만 1차 활용; 본문은 사용자가 PDF 로 변환해 업로드 권장
            metadata["pyhwp_available"] = True
        except ImportError:
            metadata["pyhwp_available"] = False

    chars = len(text)
    summary = (
        f"HWP {len(data) / 1024:.1f}KB · 미리보기 {chars}자"
        if chars > 0
        else f"HWP {len(data) / 1024:.1f}KB · 본문 추출 실패 (PDF 변환 후 재업로드 권장)"
    )
    return {
        "text": text,
        "metadata": {
            **metadata,
            "summary": summary,
            "extracted_chars": chars,
        },
        "preview_image_b64": "",
    }
