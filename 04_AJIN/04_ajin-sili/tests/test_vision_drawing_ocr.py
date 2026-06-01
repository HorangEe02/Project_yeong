"""v4.8 Feature F 트랙 A — 도면 Vision OCR 파일럿 테스트.

검증:
  1. GEMINI_API_KEY 미설정 → RuntimeError("vision_disabled").
  2. Gemini API mock → 응답 텍스트에서 부품 번호 regex 추출.
  3. 빈 image_bytes → 빈 리스트.
  4. 중복 부품 번호는 1회만 반환 (순서 보존).
  5. SDK 미설치(가짜 ImportError) → RuntimeError("vision_failed").
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.dependencies import get_current_user
from backend.routers import equipment as equipment_router
from features.equipment import drawing_search


# ──────────────────────────────────────────────────────────────────────────
# 1. GEMINI_API_KEY 미설정 → vision_disabled
# ──────────────────────────────────────────────────────────────────────────


def test_extract_part_numbers_without_api_key_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc:
        drawing_search.extract_part_numbers(b"fake-image-bytes")
    assert str(exc.value) == "vision_disabled"


def test_extract_part_numbers_empty_bytes_returns_empty() -> None:
    # API key 가 있어도 빈 바이트는 즉시 [] (API 호출 없음).
    assert drawing_search.extract_part_numbers(b"") == []


# ──────────────────────────────────────────────────────────────────────────
# 2. Gemini mock — 응답에서 부품 번호 3개 추출
# ──────────────────────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModel:
    def __init__(self, _name: str) -> None:
        pass

    def generate_content(self, _payload: Any) -> _FakeResponse:
        return _FakeResponse(
            "KOR-2024-001\n"
            "USA-2023-456\n"
            "AJ-EWP-001\n"  # 형식 미일치 (4자리 연도 + 일련번호 패턴 아님)
            "JPN-2025-7890\n"
        )


def _install_fake_genai(monkeypatch: pytest.MonkeyPatch, response_text: str | None = None) -> dict:
    """가짜 google.generativeai 모듈을 sys.modules 에 주입."""
    call_log: dict[str, Any] = {"configured_with": None, "prompts": []}

    fake = types.ModuleType("google.generativeai")

    def configure(api_key: str) -> None:
        call_log["configured_with"] = api_key

    class _Model:
        def __init__(self, model_name: str) -> None:
            call_log["model_name"] = model_name

        def generate_content(self, payload: list) -> _FakeResponse:
            call_log["prompts"].append(payload)
            return _FakeResponse(response_text or "default")

    fake.configure = configure  # type: ignore[attr-defined]
    fake.GenerativeModel = _Model  # type: ignore[attr-defined]

    # google 네임스페이스 패키지도 등록.
    google_mod = types.ModuleType("google")
    google_mod.generativeai = fake  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.generativeai", fake)
    return call_log


def test_extract_part_numbers_with_mock_gemini_returns_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-xyz")
    log = _install_fake_genai(
        monkeypatch,
        response_text=(
            "발견된 부품 번호:\n"
            "KOR-2024-001\n"
            "USA-2023-4567\n"
            "JPN-2025-789\n"
        ),
    )

    result = drawing_search.extract_part_numbers(b"binary-image-bytes")

    assert log["configured_with"] == "test-key-xyz"
    assert log["model_name"] == "gemini-2.5-pro"
    assert len(result) >= 1
    assert "KOR-2024-001" in result
    assert "USA-2023-4567" in result
    assert "JPN-2025-789" in result
    # AJ-EWP-001 형태는 4자리 연도 미포함 → 패턴 불일치.
    assert "AJ-EWP-001" not in result


def test_extract_part_numbers_deduplicates_and_preserves_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    _install_fake_genai(
        monkeypatch,
        response_text="KOR-2024-001 USA-2023-456 KOR-2024-001 JPN-2025-789 USA-2023-456",
    )
    result = drawing_search.extract_part_numbers(b"img")
    assert result == ["KOR-2024-001", "USA-2023-456", "JPN-2025-789"]


def test_extract_part_numbers_returns_empty_when_no_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    _install_fake_genai(monkeypatch, response_text="이 도면에서 부품 번호를 발견할 수 없습니다.")
    assert drawing_search.extract_part_numbers(b"img") == []


# ──────────────────────────────────────────────────────────────────────────
# 3. SDK 미설치(import 실패) → vision_failed
# ──────────────────────────────────────────────────────────────────────────


def test_extract_part_numbers_sdk_missing_raises_vision_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "k")

    # google.generativeai import 가 실패하도록.
    monkeypatch.setitem(sys.modules, "google.generativeai", None)

    # 다음 import 호출 시 ImportError 발동을 위해 finder 가 None 을 응답 → 그대로 raise.
    # Python: setting sys.modules[name] = None → "import name" 시 ImportError.

    with pytest.raises(RuntimeError) as exc:
        drawing_search.extract_part_numbers(b"img")
    assert str(exc.value) == "vision_failed"


def test_extract_part_numbers_gemini_call_failure_raises_vision_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gemini 호출 도중 예외 → vision_failed 변환."""
    monkeypatch.setenv("GEMINI_API_KEY", "k")

    fake = types.ModuleType("google.generativeai")

    def configure(api_key: str) -> None:
        pass

    class _BadModel:
        def __init__(self, name: str) -> None:
            pass

        def generate_content(self, payload):  # noqa: ARG002
            raise RuntimeError("upstream 503")

    fake.configure = configure  # type: ignore[attr-defined]
    fake.GenerativeModel = _BadModel  # type: ignore[attr-defined]

    google_mod = types.ModuleType("google")
    google_mod.generativeai = fake  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.generativeai", fake)

    with pytest.raises(RuntimeError) as exc:
        drawing_search.extract_part_numbers(b"img")
    assert str(exc.value) == "vision_failed"


# ──────────────────────────────────────────────────────────────────────────
# 4. 도면 OCR 라우터 — 허용 base directory 내부 파일만 읽기
# ──────────────────────────────────────────────────────────────────────────


def _equipment_user() -> SimpleNamespace:
    """Create a user allowed to run drawing OCR."""
    return SimpleNamespace(
        user_id="E001",
        employee_id="E001",
        username="E001",
        role="EMPLOYEE",
        role_level=3,
        department="생산기술팀",
    )


def _equipment_client() -> TestClient:
    """Create a router-only equipment TestClient with auth override."""
    app = FastAPI()
    app.include_router(equipment_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: _equipment_user()
    return TestClient(app, raise_server_exceptions=False)


def _set_drawing_ocr_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    """Point drawing OCR allowlist roots at temporary directories."""
    drawings_dir = tmp_path / "data" / "equipment" / "drawings"
    sample_dir = tmp_path / "data" / "equipment" / "drawings_samples"
    drawings_dir.mkdir(parents=True)
    sample_dir.mkdir(parents=True)
    monkeypatch.setattr(
        equipment_router,
        "_DRAWING_OCR_ALLOWED_BASE_DIRS",
        (drawings_dir, sample_dir),
    )
    monkeypatch.setattr(equipment_router, "_DRAWING_OCR_SAMPLE_DIR", sample_dir)
    return drawings_dir, sample_dir


def _patch_drawing_search(
    monkeypatch: pytest.MonkeyPatch,
    file_path: str,
    call_log: dict[str, Any] | None = None,
) -> None:
    """Patch drawing lookup and OCR extraction for router tests."""
    monkeypatch.setattr(
        drawing_search,
        "get_drawing",
        lambda drawing_id: {"id": drawing_id, "file_path": file_path},
    )

    def extract(image_bytes: bytes) -> list[str]:
        if call_log is not None:
            call_log["image_bytes"] = image_bytes
        return ["KOR-2024-001"]

    monkeypatch.setattr(drawing_search, "extract_part_numbers", extract)


def test_drawing_ocr_reads_allowed_image_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Drawing OCR reads PNG/JPG files only inside allowed base directories."""
    drawings_dir, _sample_dir = _set_drawing_ocr_dirs(monkeypatch, tmp_path)
    image_path = drawings_dir / "ok.png"
    image_path.write_bytes(b"allowed-image")
    call_log: dict[str, Any] = {}
    _patch_drawing_search(monkeypatch, str(image_path), call_log)

    response = _equipment_client().post("/api/equipment/drawing/1/ocr")

    assert response.status_code == 200
    assert response.json()["part_numbers"] == ["KOR-2024-001"]
    assert call_log["image_bytes"] == b"allowed-image"


def test_drawing_ocr_env_allowlist_reads_mounted_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """EQUIPMENT_DRAWING_OCR_ALLOWED_DIRS can add an operator-approved mount."""
    mount_dir = tmp_path / "mounted_drawings"
    mount_dir.mkdir()
    image_path = mount_dir / "mounted.jpg"
    image_path.write_bytes(b"mounted-image")
    call_log: dict[str, Any] = {}
    monkeypatch.setenv("EQUIPMENT_DRAWING_OCR_ALLOWED_DIRS", str(mount_dir))
    _patch_drawing_search(monkeypatch, str(image_path), call_log)

    response = _equipment_client().post("/api/equipment/drawing/1/ocr")

    assert response.status_code == 200
    assert call_log["image_bytes"] == b"mounted-image"


def test_drawing_ocr_blocks_absolute_path_outside_allowlist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Drawing OCR rejects absolute file paths outside allowed roots."""
    _set_drawing_ocr_dirs(monkeypatch, tmp_path)
    outside_path = tmp_path / "outside.png"
    outside_path.write_bytes(b"outside")
    _patch_drawing_search(monkeypatch, str(outside_path))

    response = _equipment_client().post("/api/equipment/drawing/1/ocr")

    assert response.status_code == 403
    assert response.json()["detail"] == "drawing_file_forbidden"


def test_drawing_ocr_blocks_traversal_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Drawing OCR rejects stored paths containing traversal segments."""
    drawings_dir, _sample_dir = _set_drawing_ocr_dirs(monkeypatch, tmp_path)
    _patch_drawing_search(monkeypatch, str(drawings_dir / ".." / "outside.png"))

    response = _equipment_client().post("/api/equipment/drawing/1/ocr")

    assert response.status_code == 403
    assert response.json()["detail"] == "drawing_file_forbidden"


def test_drawing_ocr_blocks_symlink_escape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Drawing OCR rejects symlinks that resolve outside allowed roots."""
    drawings_dir, _sample_dir = _set_drawing_ocr_dirs(monkeypatch, tmp_path)
    outside_path = tmp_path / "outside.png"
    outside_path.write_bytes(b"outside")
    link_path = drawings_dir / "link.png"
    link_path.symlink_to(outside_path)
    _patch_drawing_search(monkeypatch, str(link_path))

    response = _equipment_client().post("/api/equipment/drawing/1/ocr")

    assert response.status_code == 403
    assert response.json()["detail"] == "drawing_file_forbidden"


def test_drawing_ocr_missing_allowed_image_returns_404(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Drawing OCR reports missing images under allowed roots as not found."""
    drawings_dir, _sample_dir = _set_drawing_ocr_dirs(monkeypatch, tmp_path)
    _patch_drawing_search(monkeypatch, str(drawings_dir / "missing.png"))

    response = _equipment_client().post("/api/equipment/drawing/1/ocr")

    assert response.status_code == 404
    assert response.json()["detail"] == "drawing_image_not_found"


def test_drawing_ocr_unsupported_allowed_file_returns_404(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Drawing OCR does not read non-image files even inside allowed roots."""
    drawings_dir, _sample_dir = _set_drawing_ocr_dirs(monkeypatch, tmp_path)
    pdf_path = drawings_dir / "drawing.pdf"
    pdf_path.write_bytes(b"%PDF")
    _patch_drawing_search(monkeypatch, str(pdf_path))

    response = _equipment_client().post("/api/equipment/drawing/1/ocr")

    assert response.status_code == 404
    assert response.json()["detail"] == "drawing_image_not_found"
