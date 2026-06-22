"""Prepare a private live supplement OCR fixture manifest.

This operator tool scans a consented external image tree, selects a bounded
sample for live OCR comparison, copies only the selected images into a
gitignored private workspace, and writes a redacted fixture manifest. It does
not run OCR and it does not persist raw OCR text or provider payloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import random
import shutil
import sys
import unicodedata
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from PIL import Image, UnidentifiedImageError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.utils.chronic_disease_matrix import load_matrix  # noqa: E402

CHRONIC_DISEASE_AVOID_RECOMMENDATIONS = frozenset({"avoid_for_chronic", "avoid_for_ckd"})
"""B형 페르소나에서 sampling 시 제외할 카테고리 권장 등급."""

SOURCE_DOC_URLS = (
    "https://cloud.google.com/vision/docs/ocr",
    "https://cloud.google.com/vision/docs/reference/rest/v1/Feature",
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://api.ncloud-docs.com/docs/en/ai-application-service-ocr",
)
ALLOWED_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_DECODED_PIXELS = 50_000_000
MIN_REASONABLE_ASPECT_RATIO = 0.15
MAX_REASONABLE_ASPECT_RATIO = 8.0
MIN_HIGH_QUALITY_WIDTH = 600
MIN_HIGH_QUALITY_HEIGHT = 400
MIME_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
LABEL_KEYWORDS = (
    "supplement",
    "nutrition",
    "facts",
    "ingredient",
    "label",
    "성분",
    "영양",
    "기능",
    "원재료",
    "섭취",
    "표시",
    "상세",
)
SourceKind = Literal["detail_page", "review", "unknown"]


@dataclass(frozen=True)
class ImageCandidate:
    """A decoded image candidate from the external source tree.

    Args:
        path: Absolute source image path.
        relative_path: Source path relative to the operator-provided root.
        category_label: Top-level category directory when present.
        source_kind: Whether the path comes from detail page, review, or unknown area.
        mime_type: PIL-detected MIME type.
        width: Decoded image width in pixels.
        height: Decoded image height in pixels.
        size_bytes: Source file size.
        label_score: Deterministic label-likelihood score.
    """

    path: Path
    relative_path: Path
    category_label: str
    source_kind: SourceKind
    mime_type: str
    width: int
    height: int
    size_bytes: int
    label_score: int


def main() -> None:
    """Run the live fixture manifest preparer from CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--scan-limit", type=int, default=50_000)
    parser.add_argument("--seed", type=int, default=20260517)
    parser.add_argument("--min-width", type=int, default=320)
    parser.add_argument("--min-height", type=int, default=240)
    parser.add_argument("--max-bytes", type=int, default=20_000_000)
    parser.add_argument("--min-label-score", type=int, default=2)
    parser.add_argument("--manifest-name", default="manifest.json")
    parser.add_argument(
        "--category-filter",
        default=None,
        help='Comma-separated category names to keep (e.g. "오메가3,코엔자임Q10"). '
        "Other categories are dropped before sampling.",
    )
    parser.add_argument(
        "--chronic-disease-priority",
        action="store_true",
        help="Drop categories tagged as avoid_for_chronic in the chronic-disease matrix "
        "(e.g. 카페인_각성, 프리워크아웃, 크레아틴, 단백질_프로틴 for CKD).",
    )
    args = parser.parse_args()

    category_filter: set[str] | None = None
    if args.category_filter:
        category_filter = {
            token.strip() for token in args.category_filter.split(",") if token.strip()
        }

    summary = prepare_live_manifest(
        source_root=args.source_root,
        work_dir=args.work_dir,
        sample_size=args.sample_size,
        scan_limit=args.scan_limit,
        seed=args.seed,
        min_width=args.min_width,
        min_height=args.min_height,
        max_bytes=args.max_bytes,
        min_label_score=args.min_label_score,
        manifest_name=args.manifest_name,
        category_filter=category_filter,
        chronic_disease_priority=args.chronic_disease_priority,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def prepare_live_manifest(
    *,
    source_root: Path,
    work_dir: Path,
    sample_size: int,
    scan_limit: int,
    seed: int,
    min_width: int,
    min_height: int,
    max_bytes: int,
    min_label_score: int,
    manifest_name: str = "manifest.json",
    category_filter: set[str] | None = None,
    chronic_disease_priority: bool = False,
) -> dict[str, object]:
    """Scan, select, copy, and manifest live OCR fixture images.

    Args:
        source_root: Consented external image directory to scan read-only.
        work_dir: Private gitignored destination for selected images and manifest.
        sample_size: Maximum number of selected fixtures.
        scan_limit: Maximum files to inspect before selection.
        seed: Deterministic sampling seed.
        min_width: Minimum decoded image width.
        min_height: Minimum decoded image height.
        max_bytes: Maximum source file size accepted for live OCR.
        min_label_score: Minimum deterministic label-likelihood score.
        manifest_name: Manifest filename written under ``work_dir``.

    Returns:
        Redacted JSON-serializable preparation summary.

    Raises:
        ValueError: If the path or numeric options are invalid.
    """
    if sample_size < 1:
        raise ValueError("sample_size must be positive.")
    if scan_limit < 1:
        raise ValueError("scan_limit must be positive.")
    if min_width < 1 or min_height < 1 or max_bytes < 1:
        raise ValueError("min_width, min_height, and max_bytes must be positive.")
    source_root = source_root.expanduser().resolve()
    work_dir = work_dir.expanduser().resolve()
    if not source_root.is_dir():
        raise ValueError(f"source_root is not a directory: {source_root}")

    candidates, scan_summary = scan_image_candidates(
        source_root=source_root,
        scan_limit=scan_limit,
        min_width=min_width,
        min_height=min_height,
        max_bytes=max_bytes,
        min_label_score=min_label_score,
    )
    if category_filter:
        candidates = _filter_by_category(candidates, category_filter)
        scan_summary["category_filtered_kept"] = len(candidates)
    if chronic_disease_priority:
        candidates = _filter_by_chronic_disease_priority(candidates)
        scan_summary["chronic_disease_priority_kept"] = len(candidates)
    selected = select_candidates(
        candidates,
        sample_size=min(len(candidates), sample_size * 3),
        seed=seed,
    )
    manifest = build_manifest(
        source_root=source_root,
        work_dir=work_dir,
        selected=selected,
        sample_size=sample_size,
        seed=seed,
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = work_dir / manifest_name
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest_cases = manifest.get("cases", [])
    return {
        "manifest": str(manifest_path),
        "selected_count": len(manifest_cases) if isinstance(manifest_cases, list) else 0,
        "candidate_count": len(candidates),
        "scan_summary": scan_summary,
        "repo_image_copy_only": True,
        "full_text_artifact_stored": False,
        "provider_artifact_stored": False,
    }


def scan_image_candidates(
    *,
    source_root: Path,
    scan_limit: int,
    min_width: int,
    min_height: int,
    max_bytes: int,
    min_label_score: int,
) -> tuple[list[ImageCandidate], dict[str, int]]:
    """Scan an external image tree and return decoded image candidates.

    Args:
        source_root: Root directory to scan.
        scan_limit: Maximum files to inspect.
        min_width: Minimum decoded width.
        min_height: Minimum decoded height.
        max_bytes: Maximum file size in bytes.
        min_label_score: Minimum label-likelihood score.

    Returns:
        Candidate list and redacted scan counters.
    """
    summary = {
        "files_seen": 0,
        "non_files_skipped": 0,
        "oversized_skipped": 0,
        "huge_image_skipped": 0,
        "decode_failed": 0,
        "unsupported_mime_skipped": 0,
        "small_image_skipped": 0,
        "low_label_score_skipped": 0,
    }
    candidates: list[ImageCandidate] = []
    for path in sorted(source_root.rglob("*")):
        if summary["files_seen"] >= scan_limit:
            break
        if not path.is_file():
            summary["non_files_skipped"] += 1
            continue
        summary["files_seen"] += 1
        size_bytes = path.stat().st_size
        if size_bytes > max_bytes:
            summary["oversized_skipped"] += 1
            continue
        decoded = _decode_image_metadata(path)
        if decoded is None:
            summary["decode_failed"] += 1
            continue
        mime_type, width, height = decoded
        if width * height > MAX_DECODED_PIXELS:
            summary["huge_image_skipped"] += 1
            continue
        if mime_type not in ALLOWED_MIME_TYPES:
            summary["unsupported_mime_skipped"] += 1
            continue
        if width < min_width or height < min_height:
            summary["small_image_skipped"] += 1
            continue
        relative_path = path.relative_to(source_root)
        source_kind = _source_kind(relative_path)
        label_score = _label_likelihood_score(relative_path, source_kind, width, height)
        if label_score < min_label_score:
            summary["low_label_score_skipped"] += 1
            continue
        candidates.append(
            ImageCandidate(
                path=path,
                relative_path=relative_path,
                category_label=_category_label(relative_path),
                source_kind=source_kind,
                mime_type=mime_type,
                width=width,
                height=height,
                size_bytes=size_bytes,
                label_score=label_score,
            )
        )
    return candidates, summary


def select_candidates(
    candidates: list[ImageCandidate],
    *,
    sample_size: int,
    seed: int,
) -> list[ImageCandidate]:
    """Select a deterministic category-balanced sample.

    Args:
        candidates: Decoded candidate images.
        sample_size: Maximum selected count.
        seed: Deterministic sampling seed.

    Returns:
        Selected image candidates, preferring detail pages over reviews.
    """
    rng = random.Random(seed)
    detail_candidates = [item for item in candidates if item.source_kind == "detail_page"]
    review_candidates = [item for item in candidates if item.source_kind == "review"]
    unknown_candidates = [item for item in candidates if item.source_kind == "unknown"]
    selected: list[ImageCandidate] = []
    seen_paths: set[Path] = set()
    for group in (detail_candidates, review_candidates, unknown_candidates):
        for candidate in _balanced_order(group, rng=rng):
            if len(selected) >= sample_size:
                return selected
            if candidate.path in seen_paths:
                continue
            seen_paths.add(candidate.path)
            selected.append(candidate)
    return selected


def build_manifest(
    *,
    source_root: Path,
    work_dir: Path,
    selected: list[ImageCandidate],
    sample_size: int,
    seed: int,
) -> dict[str, object]:
    """Copy selected images and build a redacted OCR fixture manifest.

    Args:
        source_root: External source root.
        work_dir: Private destination directory.
        selected: Selected image candidates.
        sample_size: Maximum fixture rows after duplicate removal.
        seed: Sampling seed.

    Returns:
        Fixture manifest object.
    """
    image_dir = work_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    seen_sha256: set[str] = set()
    cases: list[dict[str, object]] = []
    for candidate in selected:
        if len(cases) >= sample_size:
            break
        image_sha256 = _sha256_file(candidate.path)
        if image_sha256 in seen_sha256:
            continue
        seen_sha256.add(image_sha256)
        fixture_id = f"naver-live-{len(cases) + 1:04d}"
        suffix = MIME_SUFFIXES.get(candidate.mime_type) or candidate.path.suffix.lower()
        copied_image = image_dir / f"{fixture_id}{suffix}"
        shutil.copy2(candidate.path, copied_image)
        product_group = _product_group_path(candidate.relative_path)
        cases.append(
            {
                "fixture_id": fixture_id,
                "image_path": copied_image.relative_to(work_dir).as_posix(),
                "image_sha256": image_sha256,
                "license_status": "consented",
                "consent_status": "consented",
                "contains_personal_data": False,
                "labels": [
                    "live_naver",
                    candidate.source_kind,
                    _strip_category_brackets(candidate.category_label),
                ],
                "expected": {
                    "expected_source": "pending_google_vision_auto_seed",
                    "verification_status": "provisional",
                    "ingredients": [],
                    "warnings": ["expected_not_seeded_yet"],
                },
                "source_metadata": {
                    "source_path_hash": _sha256_text(candidate.relative_path.as_posix()),
                    "product_group_hash": _sha256_text(product_group.as_posix()),
                    "category_label": _strip_category_brackets(candidate.category_label),
                    "source_kind": candidate.source_kind,
                    "mime_type": candidate.mime_type,
                    "width": candidate.width,
                    "height": candidate.height,
                    "size_bytes": candidate.size_bytes,
                    "label_score": candidate.label_score,
                },
            }
        )
    return {
        "version": "supplement-ocr-live-manifest-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "selection_policy": "detail_page_first_category_balanced_then_review_fallback",
        "sample_seed": seed,
        "source_root_hash": _sha256_text(str(source_root)),
        "expected_policy": "google_vision_auto_seed_provisional",
        "source_doc_urls": list(SOURCE_DOC_URLS),
        "cases": cases,
    }


def _decode_image_metadata(path: Path) -> tuple[str, int, int] | None:
    """Decode image metadata with Pillow.

    Args:
        path: Candidate image path.

    Returns:
        MIME type, width, and height, or None when decoding fails.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                width, height = image.size
                mime_type = Image.MIME.get(image.format or "")
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError):
        return None
    if not mime_type:
        guessed_type, _ = mimetypes.guess_type(path.name)
        mime_type = guessed_type or "application/octet-stream"
    return mime_type, width, height


def _filter_by_category(
    candidates: list[ImageCandidate],
    allowed: set[str],
) -> list[ImageCandidate]:
    """카테고리 화이트리스트에 속하는 후보만 남긴다.

    카테고리명은 ``_strip_category_brackets`` 로 정규화한 뒤 비교한다.

    Args:
        candidates: 스캔된 candidate 리스트.
        allowed: 허용 카테고리 set (예: ``{"오메가3", "코엔자임Q10"}``).

    Returns:
        매칭된 candidate 리스트. ``allowed`` 가 비어 있으면 빈 리스트.
    """
    return [
        candidate
        for candidate in candidates
        if _strip_category_brackets(candidate.category_label) in allowed
    ]


def _filter_by_chronic_disease_priority(
    candidates: list[ImageCandidate],
) -> list[ImageCandidate]:
    """만성질환 매트릭스 권장 등급이 ``avoid_for_*`` 인 카테고리를 제외한다.

    매트릭스에 등재되지 않은 카테고리는 기본 유지 (neutral 취급).

    Args:
        candidates: 스캔된 candidate 리스트.

    Returns:
        제외 권장 카테고리를 빼고 남은 candidate 리스트.
    """
    matrix = load_matrix()
    kept: list[ImageCandidate] = []
    for candidate in candidates:
        normalized = _strip_category_brackets(candidate.category_label)
        profile = matrix.categories.get(normalized)
        if profile is None:
            kept.append(candidate)
            continue
        if profile.persona_recommendation in CHRONIC_DISEASE_AVOID_RECOMMENDATIONS:
            continue
        kept.append(candidate)
    return kept


def _balanced_order(
    candidates: list[ImageCandidate], *, rng: random.Random
) -> list[ImageCandidate]:
    """Return candidates ordered by category balance and deterministic shuffle.

    Args:
        candidates: Candidate images.
        rng: Deterministic random generator.

    Returns:
        Ordered candidates.
    """
    grouped: dict[str, list[ImageCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.category_label, []).append(candidate)
    for group in grouped.values():
        rng.shuffle(group)
        group.sort(key=lambda item: (-item.label_score, item.relative_path.as_posix()))
    ordered: list[ImageCandidate] = []
    while grouped:
        for category in sorted(grouped):
            group = grouped[category]
            if not group:
                del grouped[category]
                continue
            ordered.append(group.pop(0))
    return ordered


def _source_kind(relative_path: Path) -> SourceKind:
    """Classify a source path by known Tampermonkey directory names.

    Args:
        relative_path: Path relative to the scan root.

    Returns:
        Source kind.
    """
    parts = [_normalize_path_text(part) for part in relative_path.parts]
    if any("상세페이지" in part for part in parts):
        return "detail_page"
    if any("리뷰" in part for part in parts):
        return "review"
    return "unknown"


def _category_label(relative_path: Path) -> str:
    """Return the top-level category label for a relative source path.

    Args:
        relative_path: Path relative to the scan root.

    Returns:
        Category label or ``unknown``.
    """
    if not relative_path.parts:
        return "unknown"
    return _normalize_path_text(relative_path.parts[0])


def _product_group_path(relative_path: Path) -> Path:
    """Return a stable product-level path without review/detail filenames.

    Args:
        relative_path: Source path relative to the scan root.

    Returns:
        Product group path.
    """
    parts = list(relative_path.parts)
    for marker in ("상세페이지", "리뷰"):
        for index, part in enumerate(parts):
            if marker in _normalize_path_text(part):
                return Path(*parts[:index]) if index else Path("unknown")
    return relative_path.parent


def _label_likelihood_score(
    relative_path: Path,
    source_kind: SourceKind,
    width: int,
    height: int,
) -> int:
    """Compute a deterministic label-likelihood score.

    Args:
        relative_path: Candidate path.
        source_kind: Classified source kind.
        width: Image width.
        height: Image height.

    Returns:
        Integer score used for filtering and ranking.
    """
    normalized_path = _normalize_path_text(relative_path.as_posix()).casefold()
    score = 3 if source_kind == "detail_page" else 1 if source_kind == "review" else 0
    score += sum(2 for keyword in LABEL_KEYWORDS if keyword.casefold() in normalized_path)
    aspect_ratio = width / max(height, 1)
    if MIN_REASONABLE_ASPECT_RATIO <= aspect_ratio <= MAX_REASONABLE_ASPECT_RATIO:
        score += 1
    if width >= MIN_HIGH_QUALITY_WIDTH and height >= MIN_HIGH_QUALITY_HEIGHT:
        score += 1
    return score


def _strip_category_brackets(value: str) -> str:
    """Normalize a category label for redacted manifest labels.

    Args:
        value: Source category directory name.

    Returns:
        Category without surrounding square brackets.
    """
    stripped = _normalize_path_text(value).strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return stripped[1:-1].strip() or "unknown"
    return stripped or "unknown"


def _normalize_path_text(value: str) -> str:
    """Normalize decomposed Korean macOS path text to NFC.

    Args:
        value: Path text.

    Returns:
        NFC-normalized text.
    """
    return unicodedata.normalize("NFC", value)


def _sha256_file(path: Path) -> str:
    """Hash a file without loading unrelated provider data.

    Args:
        path: File path.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    """Hash local path metadata before writing manifest fields.

    Args:
        value: Text value.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()
