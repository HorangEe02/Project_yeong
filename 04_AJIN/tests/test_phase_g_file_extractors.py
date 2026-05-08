"""v3.3 Phase G — CAD / HWP 파일 추출기 종합 테스트.

검증 대상:
1. _compress_text() — head/tail 압축 매트릭스 (한도/경계/마커 검증)
2. 5종 추출기 단위 (HWP / DXF / STEP / IGES / Binary CAD) — graceful fallback
3. extract_with_meta() dispatcher 라우팅 (확장자별)
4. extract_with_meta() 압축 자동 적용 (큰 텍스트 → truncated 메타)
5. /upload 엔드포인트 통합:
   - FEATURE_C_CAD_UPLOAD ON/OFF 화이트리스트 게이트
   - 20MB 한도
   - 415 거부 응답
   - 응답 metadata + preview_image_b64 필드
6. SUPPORTED_EXTENSIONS 정합 (백엔드 _ALLOWED_EXTENSIONS 와 매칭)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.file_extractors import (
    BINARY_CAD_EXTENSIONS,
    HWP_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    TEXT_CAD_EXTENSIONS,
    _compress_text,
    extract_with_meta,
)
from core.file_extractors import binary_cad as binary_cad_mod
from core.file_extractors import hwp as hwp_mod
from core.file_extractors import iges as iges_mod
from core.file_extractors import step as step_mod


# ════════════════════════════════════════════════════════════
# 1. _compress_text — 압축 매트릭스
# ════════════════════════════════════════════════════════════


def test_compress_short_text_no_truncation():
    text = "hello world"
    out, meta = _compress_text(text)
    assert out == text
    assert meta["truncated"] is False
    assert meta["original_chars"] == 11
    assert meta["skipped_chars"] == 0


def test_compress_at_threshold_no_truncation():
    """한도(16KB) 정확히 — 압축 안 됨."""
    text = "X" * (16 * 1024)
    out, meta = _compress_text(text)
    assert out == text
    assert meta["truncated"] is False


def test_compress_above_threshold_truncates():
    """한도 +1 → 압축."""
    text = "X" * (16 * 1024 + 1)
    out, meta = _compress_text(text)
    assert meta["truncated"] is True
    assert "[FILE_HEAD]" in out
    assert "[SKIPPED" in out
    assert "[FILE_TAIL]" in out


def test_compress_preserves_head_and_tail():
    """head 8KB + tail 4KB 보존."""
    head = "A" * 8000
    middle = "B" * 5000
    tail = "C" * 6000
    text = head + middle + tail
    out, meta = _compress_text(text)
    assert meta["truncated"] is True
    # head 영역에 A 가 충분히 보존
    assert out[:100].count("A") + out[:200].count("A") > 100
    # tail 영역에 C 가 충분히 보존
    assert out[-100:].count("C") > 50
    # B (중간) 는 잘림
    skipped_marker = "[SKIPPED"
    assert skipped_marker in out


def test_compress_skipped_count_accurate():
    text = "A" * 8000 + "B" * 5000 + "C" * 6000  # 19000
    out, meta = _compress_text(text)
    assert meta["original_chars"] == 19000
    # skipped = 19000 - 8192 (head) - 4096 (tail) = 6712
    assert meta["skipped_chars"] == 19000 - 8 * 1024 - 4 * 1024


# ════════════════════════════════════════════════════════════
# 2. 5종 추출기 단위 — graceful fallback
# ════════════════════════════════════════════════════════════


# 2-1. HWP


def test_hwp_extract_invalid_data_graceful():
    """OLE 형식 아닌 바이트 → graceful error 메타."""
    result = hwp_mod.extract(b"random bytes not ole")
    assert "metadata" in result
    assert result["metadata"]["format"] == "HWP"
    # olefile 미설치 또는 not_ole 둘 중 하나
    err = result["metadata"].get("error")
    assert err in ("not_ole", "olefile_not_installed", None)


def test_hwp_extract_empty_data():
    result = hwp_mod.extract(b"")
    assert result["metadata"]["format"] == "HWP"
    assert result["metadata"]["size_bytes"] == 0


# 2-2. DXF


def test_dxf_extract_no_library_graceful():
    """ezdxf 미설치 시 graceful (실제 환경에서는 설치된 경우 정상 파싱)."""
    result = extract_with_meta(b"random", filename="test.dxf")
    assert result["metadata"]["format"] == "DXF"
    # 라이브러리 미설치 또는 파싱 실패 둘 중 하나
    err = result["metadata"].get("error")
    assert err in ("ezdxf_not_installed", "dxf_parse_failed", None)


# 2-3. STEP


def test_step_extract_valid_minimal():
    """최소 STEP 헤더 파싱."""
    fake = (
        b"ISO-10303-21;\n"
        b"HEADER;\n"
        b"FILE_DESCRIPTION(('demo'),'2;1');\n"
        b"FILE_NAME('test.stp','2026-04-29',('me'),('AJIN'),'STEP AP203','','');\n"
        b"FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));\n"
        b"ENDSEC;\n"
        b"DATA;\n"
        b"PRODUCT('PART-001','PART-001','',(.MECHANICAL.));\n"
        b"ENDSEC;\n"
        b"END-ISO-10303-21;\n"
    )
    result = step_mod.extract(fake)
    assert result["metadata"]["format"] == "STEP"
    assert "[STEP 메타]" in result["text"]
    assert "FILE_DESCRIPTION" in result["text"]
    assert result["metadata"]["meta_line_count"] >= 1


def test_step_extract_not_iso():
    """ISO-10303-21 헤더 없으면 not_step."""
    result = step_mod.extract(b"this is not step")
    assert result["metadata"]["error"] == "not_step"
    assert result["text"] == ""


# 2-4. IGES


def test_iges_extract_valid_minimal():
    """80-컬럼 고정폭 — S/G 섹션 파싱.

    IGES 형식: 0..71 = content, 72 = section ID, 73..79 = sequence number.
    """
    def line(content: str, sec: str, seq: int) -> str:
        # content 를 정확히 72 자로 (왼쪽 정렬), 73 번째에 sec, 그 뒤에 7자리 sequence
        return content[:72].ljust(72) + sec + f"{seq:07d}"

    fake = (
        line("IGES sample header line 1", "S", 1) + "\n" +
        line("1H,,1H;,4HSLOR,4HSLOR,", "G", 1) + "\n" +
        line("", "T", 1) + "\n"
    ).encode("ascii")

    # 정합 검증 — 각 라인이 정확히 80 자
    for ln in fake.decode("ascii").splitlines():
        assert len(ln) == 80, f"라인 길이 {len(ln)} (80 기대): {ln!r}"

    result = iges_mod.extract(fake)
    assert result["metadata"]["format"] == "IGES"
    sec_counts = result["metadata"]["section_counts"]
    assert sec_counts["S"] >= 1
    assert sec_counts["G"] >= 1
    assert sec_counts["T"] >= 1


def test_iges_extract_empty():
    result = iges_mod.extract(b"")
    assert result["metadata"]["error"] == "empty"


def test_iges_extract_no_section_id():
    """73 컬럼이 없으면 not_iges."""
    result = iges_mod.extract(b"random short content")
    assert result["metadata"]["error"] in ("not_iges", "empty")


# 2-5. Binary CAD


def test_binary_cad_extract_returns_meta_only():
    """sldprt → 텍스트 추출 불가 안내 + 메타."""
    result = binary_cad_mod.extract(b"\x00" * 5000, filename="part.sldprt")
    assert result["metadata"]["format"] == "SolidWorks Part"
    assert result["metadata"]["binary_only"] is True
    assert "텍스트 추출 불가" in result["metadata"]["summary"]
    assert "3D 부품 파일 첨부" in result["text"]


@pytest.mark.parametrize(
    "ext,expected_format",
    [
        (".sldprt", "SolidWorks Part"),
        (".sldasm", "SolidWorks Assembly"),
        (".prt", "Creo / NX Part"),
        (".catpart", "CATIA Part"),
        (".catproduct", "CATIA Product (Assembly)"),
    ],
)
def test_binary_cad_format_labels(ext: str, expected_format: str):
    result = binary_cad_mod.extract(b"\x00" * 100, filename=f"x{ext}")
    assert result["metadata"]["format"] == expected_format


# ════════════════════════════════════════════════════════════
# 3. extract_with_meta dispatcher
# ════════════════════════════════════════════════════════════


def test_dispatcher_routes_dxf():
    result = extract_with_meta(b"random dxf content", filename="x.dxf")
    assert result["metadata"]["format"] == "DXF"


def test_dispatcher_routes_step():
    result = extract_with_meta(b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;", filename="x.stp")
    assert result["metadata"]["format"] == "STEP"


def test_dispatcher_routes_iges():
    fake = ("X" * 72 + "S0000001\n").encode("ascii")
    result = extract_with_meta(fake, filename="x.iges")
    assert result["metadata"]["format"] == "IGES"


def test_dispatcher_routes_binary_cad():
    result = extract_with_meta(b"\x00" * 100, filename="x.sldprt")
    assert result["metadata"]["binary_only"] is True


def test_dispatcher_routes_hwp():
    result = extract_with_meta(b"not ole", filename="x.hwp")
    assert result["metadata"]["format"] == "HWP"


def test_dispatcher_unsupported_extension():
    """미지원 확장자 → unsupported_extension error."""
    result = extract_with_meta(b"x", filename="x.exe")
    assert result["metadata"]["error"] == "unsupported_extension"
    assert result["text"] == ""


def test_dispatcher_no_extension():
    result = extract_with_meta(b"x", filename="noext")
    assert result["metadata"]["error"] == "unsupported_extension"


# ════════════════════════════════════════════════════════════
# 4. dispatcher 압축 자동 적용
# ════════════════════════════════════════════════════════════


def test_dispatcher_applies_compression_to_extracted_text():
    """추출 텍스트가 16KB 초과 시 dispatcher 가 자동으로 압축."""
    # 가짜 STEP — DATA 섹션을 거대하게
    big_data = b"PRODUCT('X','Y','Z',(.MECHANICAL.));\n" * 5000  # ~200KB
    fake = (
        b"ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION((),'2;1');\nENDSEC;\n"
        b"DATA;\n" + big_data + b"ENDSEC;\nEND-ISO-10303-21;"
    )
    result = extract_with_meta(fake, filename="big.stp")
    # truncated 메타 존재
    assert "truncated" in result["metadata"]


def test_dispatcher_short_text_not_truncated():
    """짧은 추출 결과는 압축 안 됨."""
    result = extract_with_meta(b"\x00" * 1000, filename="part.sldprt")
    assert result["metadata"]["truncated"] is False


# ════════════════════════════════════════════════════════════
# 5. SUPPORTED_EXTENSIONS 정합
# ════════════════════════════════════════════════════════════


def test_supported_extensions_complete():
    expected = TEXT_CAD_EXTENSIONS | BINARY_CAD_EXTENSIONS | HWP_EXTENSIONS
    assert SUPPORTED_EXTENSIONS == expected


def test_text_cad_count():
    """텍스트 CAD 5종 + 바이너리 CAD 5종 + HWP 1종 = 11."""
    assert len(TEXT_CAD_EXTENSIONS) == 5
    assert len(BINARY_CAD_EXTENSIONS) == 5
    assert len(HWP_EXTENSIONS) == 1
    assert len(SUPPORTED_EXTENSIONS) == 11


# ════════════════════════════════════════════════════════════
# 6. /upload 엔드포인트 통합 (TestClient)
# ════════════════════════════════════════════════════════════


@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.routers.onboarding import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_upload_pdf_always_allowed(client):
    """기존 PDF 는 CAD 플래그와 무관하게 항상 허용."""
    r = client.post("/onboarding/upload", files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "doc.pdf"


def test_upload_cad_flag_on_dxf(client):
    """FEATURE_C_CAD_UPLOAD=true 시 DXF 통과 + metadata 필드 포함."""
    with patch.dict(os.environ, {"FEATURE_C_CAD_UPLOAD": "true"}):
        r = client.post(
            "/onboarding/upload",
            files={"file": ("x.dxf", b"random dxf", "application/dxf")},
        )
    assert r.status_code == 200
    body = r.json()
    assert "metadata" in body
    assert "preview_image_b64" in body
    assert body["metadata"]["format"] == "DXF"


def test_upload_cad_flag_off_dxf_blocked(client):
    """플래그 OFF → CAD 415 거부."""
    with patch.dict(os.environ, {"FEATURE_C_CAD_UPLOAD": "false"}):
        r = client.post(
            "/onboarding/upload",
            files={"file": ("x.dxf", b"random dxf", "application/dxf")},
        )
    assert r.status_code == 415


def test_upload_cad_flag_off_step_blocked(client):
    with patch.dict(os.environ, {"FEATURE_C_CAD_UPLOAD": "false"}):
        r = client.post(
            "/onboarding/upload",
            files={"file": ("x.stp", b"step", "application/step")},
        )
    assert r.status_code == 415


def test_upload_cad_flag_off_binary_cad_blocked(client):
    with patch.dict(os.environ, {"FEATURE_C_CAD_UPLOAD": "false"}):
        r = client.post(
            "/onboarding/upload",
            files={"file": ("part.sldprt", b"\x00", "application/octet-stream")},
        )
    assert r.status_code == 415


def test_upload_cad_flag_off_hwp_still_allowed(client):
    """HWP 는 Phase 0 이전부터 지원 — CAD 플래그 OFF 에서도 통과."""
    with patch.dict(os.environ, {"FEATURE_C_CAD_UPLOAD": "false"}):
        r = client.post(
            "/onboarding/upload",
            files={"file": ("doc.hwp", b"fake hwp", "application/x-hwp")},
        )
    assert r.status_code == 200


def test_upload_unknown_extension_415(client):
    """화이트리스트 외 확장자는 415."""
    r = client.post("/onboarding/upload", files={"file": ("x.exe", b"x", "application/octet-stream")})
    assert r.status_code == 415


def test_upload_oversize_413(client):
    """20MB 초과 → 413."""
    big = b"X" * (21 * 1024 * 1024)
    r = client.post("/onboarding/upload", files={"file": ("big.pdf", big, "application/pdf")})
    assert r.status_code == 413


def test_upload_cad_response_includes_summary(client):
    """CAD 응답 metadata 에 summary 필드."""
    with patch.dict(os.environ, {"FEATURE_C_CAD_UPLOAD": "true"}):
        r = client.post(
            "/onboarding/upload",
            files={"file": ("part.sldprt", b"\x00" * 500, "application/octet-stream")},
        )
    body = r.json()
    assert body["metadata"]["format"] == "SolidWorks Part"
    assert "summary" in body["metadata"]
    assert "텍스트 추출 불가" in body["metadata"]["summary"]


def test_upload_cad_response_truncated_field(client):
    """G-3 압축 메타 필드(truncated/original_chars)가 응답에 포함."""
    with patch.dict(os.environ, {"FEATURE_C_CAD_UPLOAD": "true"}):
        r = client.post(
            "/onboarding/upload",
            files={"file": ("part.sldprt", b"\x00" * 500, "application/octet-stream")},
        )
    body = r.json()
    assert "truncated" in body["metadata"]
    assert body["metadata"]["truncated"] is False  # 짧은 텍스트 — 압축 안 됨


def test_upload_legacy_response_shape(client):
    """기존 PDF 응답은 metadata 필드 없이 (backward compat)."""
    r = client.post("/onboarding/upload", files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")})
    body = r.json()
    # 기존 필드 보존
    assert "filename" in body
    assert "is_image" in body
    assert "text" in body
    # CAD 전용 필드는 없음 (backward compat)
    assert "metadata" not in body
