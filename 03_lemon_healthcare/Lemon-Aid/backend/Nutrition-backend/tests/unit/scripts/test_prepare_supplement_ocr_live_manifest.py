"""Tests for live supplement OCR manifest preparation."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from scripts import prepare_supplement_ocr_live_manifest as prepare


def _write_image(path: Path, *, size: tuple[int, int] = (800, 600)) -> None:
    """Write a deterministic test image.

    Args:
        path: Destination image path.
        size: Image size.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "white").save(path, format="PNG")


def test_prepare_live_manifest_selects_private_redacted_images(tmp_path: Path) -> None:
    """Verify external images are copied into a private redacted fixture manifest."""
    source_root = tmp_path / "source"
    detail_image = source_root / "[비타민C]" / "제품A_123" / "상세페이지" / "영양성분표_상세.png"
    review_image = source_root / "[오메가3]" / "제품B_456" / "리뷰" / "review_label.png"
    _write_image(detail_image)
    _write_image(review_image, size=(820, 600))
    (source_root / "[오메가3]" / "제품B_456" / "리뷰" / "note.txt").write_text(
        "not image",
        encoding="utf-8",
    )
    work_dir = tmp_path / "data" / "private" / "supplement_ocr_live" / "2026-05-17"

    summary = prepare.prepare_live_manifest(
        source_root=source_root,
        work_dir=work_dir,
        sample_size=2,
        scan_limit=20,
        seed=7,
        min_width=320,
        min_height=240,
        max_bytes=1_000_000,
        min_label_score=2,
    )

    manifest_path = Path(str(summary["manifest"]))
    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert summary["selected_count"] == 2
    assert parsed["expected_policy"] == "google_vision_auto_seed_provisional"
    assert parsed["source_root_hash"]
    assert "source_root" not in parsed
    assert len(parsed["cases"]) == 2
    first_case = parsed["cases"][0]
    assert first_case["fixture_id"] == "naver-live-0001"
    assert first_case["license_status"] == "consented"
    assert first_case["consent_status"] == "consented"
    assert first_case["contains_personal_data"] is False
    assert first_case["expected"]["expected_source"] == "pending_google_vision_auto_seed"
    assert first_case["expected"]["verification_status"] == "provisional"
    assert (work_dir / first_case["image_path"]).exists()
    metadata = first_case["source_metadata"]
    assert "source_path_hash" in metadata
    assert "product_group_hash" in metadata
    assert "original_path" not in metadata
    dumped = json.dumps(parsed, ensure_ascii=False)
    assert "raw_ocr_text" not in dumped
    assert "provider_payload" not in dumped


def test_scan_image_candidates_rejects_non_images_and_small_images(tmp_path: Path) -> None:
    """Verify scanner filters decode failures and undersized images."""
    source_root = tmp_path / "source"
    _write_image(source_root / "[비타민D]" / "제품" / "상세페이지" / "성분표.png")
    _write_image(
        source_root / "[비타민D]" / "제품" / "상세페이지" / "작은성분표.png",
        size=(100, 60),
    )
    bad_image = source_root / "[비타민D]" / "제품" / "상세페이지" / "broken.jpg"
    bad_image.parent.mkdir(parents=True, exist_ok=True)
    bad_image.write_bytes(b"not an image")

    candidates, summary = prepare.scan_image_candidates(
        source_root=source_root,
        scan_limit=10,
        min_width=320,
        min_height=240,
        max_bytes=1_000_000,
        min_label_score=2,
    )

    assert len(candidates) == 1
    assert summary["decode_failed"] == 1
    assert summary["small_image_skipped"] == 1


def _make_candidate(category: str) -> prepare.ImageCandidate:
    """단위 테스트용 ImageCandidate 헬퍼."""
    return prepare.ImageCandidate(
        path=Path(f"/tmp/{category}_dummy.png"),
        relative_path=Path(f"[{category}]") / "dummy.png",
        category_label=f"[{category}]",
        source_kind="detail_page",
        mime_type="image/png",
        width=800,
        height=600,
        size_bytes=1024,
        label_score=4,
    )


class TestFilterByCategory:
    """카테고리 필터 테스트."""

    def test_filter_keeps_only_allowed(self) -> None:
        """allowed 에 있는 카테고리만 남는다."""
        candidates = [
            _make_candidate("오메가3"),
            _make_candidate("코엔자임Q10"),
            _make_candidate("BCAA_EAA"),
        ]
        filtered = prepare._filter_by_category(candidates, {"오메가3", "코엔자임Q10"})
        labels = [prepare._strip_category_brackets(c.category_label) for c in filtered]
        assert "오메가3" in labels
        assert "코엔자임Q10" in labels
        assert "BCAA_EAA" not in labels

    def test_filter_empty_allowed_returns_empty(self) -> None:
        """빈 set 입력 → 빈 리스트."""
        candidates = [_make_candidate("오메가3")]
        assert prepare._filter_by_category(candidates, set()) == []


class TestFilterByChronicDiseasePriority:
    """만성질환 우선 필터 테스트 (매트릭스 사용)."""

    def test_avoid_for_chronic_categories_removed(self) -> None:
        """카페인_각성, 프리워크아웃, 크레아틴 (avoid_for_chronic) 카테고리가 제거된다."""
        candidates = [
            _make_candidate("오메가3"),
            _make_candidate("카페인_각성"),
            _make_candidate("프리워크아웃"),
            _make_candidate("크레아틴"),
            _make_candidate("코엔자임Q10"),
        ]
        filtered = prepare._filter_by_chronic_disease_priority(candidates)
        labels = {prepare._strip_category_brackets(c.category_label) for c in filtered}
        assert "오메가3" in labels
        assert "코엔자임Q10" in labels
        assert "카페인_각성" not in labels
        assert "프리워크아웃" not in labels
        assert "크레아틴" not in labels

    def test_avoid_for_ckd_category_removed(self) -> None:
        """단백질_프로틴 (avoid_for_ckd) 카테고리도 제거된다."""
        candidates = [
            _make_candidate("오메가3"),
            _make_candidate("단백질_프로틴"),
        ]
        filtered = prepare._filter_by_chronic_disease_priority(candidates)
        labels = {prepare._strip_category_brackets(c.category_label) for c in filtered}
        assert "단백질_프로틴" not in labels

    def test_unknown_category_kept_as_neutral(self) -> None:
        """매트릭스에 없는 카테고리는 기본 유지된다."""
        candidates = [_make_candidate("__no_such_category__")]
        filtered = prepare._filter_by_chronic_disease_priority(candidates)
        assert len(filtered) == 1
