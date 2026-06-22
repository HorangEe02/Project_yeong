"""Build redacted OCR manifests for Naver Tampermonkey supplement images.

The script scans the local Tampermonkey crawl directory, classifies detail-page
and review images, and writes an allowlisted JSONL manifest for the existing
OCR observation collector. It does not run OCR, persist image bytes, or write
raw OCR/provider/model payloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import random
import re
import unicodedata
import warnings
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from PIL import Image, UnidentifiedImageError

SOURCE_DOC_URLS = (
    "https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html",
    "https://api.ncloud-docs.com/docs/en/ai-application-service-ocr",
    "https://api.ncloud-docs.com/docs/en/ai-application-service-ocr-ocr",
    "https://cloud.google.com/vision/docs/ocr",
    "https://docs.ollama.com/capabilities/structured-outputs",
)
CATEGORY_TAXONOMY_SOURCE_DOC_URLS = (
    "https://ods.od.nih.gov/factsheets/list-all/",
    "https://www.nccih.nih.gov/health/using-dietary-supplements-wisely",
    "https://www.nccih.nih.gov/health/safety",
    "https://www.nccih.nih.gov/health/diabetes-and-dietary-supplements-what-you-need-to-know",
    "https://www.kidney.org/kidney-topics/vitamins-chronic-kidney-disease",
)
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATEGORY_TAXONOMY_PATH = (
    REPO_ROOT / "data" / "nutrition_reference" / "ocr_fixture_chronic_supplement_categories.json"
)
DEFAULT_SOURCE_ROOT = Path(
    os.environ.get(
        "NAVER_TAMPERMONKEY_SOURCE_ROOT",
        "data/private/naver_tampermonkey",
    )
)
DEFAULT_IMAGE_ROOT_ENV_VAR = "NAVER_TAMPERMONKEY_SOURCE_ROOT"
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})
ALLOWED_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_DECODED_PIXELS = 50_000_000
MIN_PRODUCT_PATH_PARTS = 2
SMALL_IMAGE_BYTES = 500_000
MEDIUM_IMAGE_BYTES = 5_000_000
PRODUCT_ID_PATTERN = re.compile(r"_(?P<product_id>\d{5,})$")
RAW_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "image_bytes",
        "ocr_text",
        "provider_payload",
        "raw_image",
        "raw_model_response",
        "raw_ocr_text",
        "raw_provider_payload",
        "request_headers",
        "service_key",
    }
)
LOCAL_PATH_MARKERS = (
    "/private/",
    "/Users/",
    "/Volumes/",
    "file://",
    "\\Users\\",
    "\\Volumes\\",
)
DEFAULT_MANIFEST_NAME = "manifest-detail-smoke-30.jsonl"
DEFAULT_INVENTORY_NAME = "inventory.json"
DEFAULT_CATEGORY_LABELS_NAME = "category-labels.json"

Section = Literal["detail", "review", "unknown"]
ManifestSection = Literal["detail", "review", "all"]


@dataclass(frozen=True)
class NaverImageCandidate:
    """Decoded OCR candidate from the Tampermonkey crawl tree.

    Args:
        path: Absolute local image path.
        relative_path: Path relative to the source root.
        category: Top-level category directory, NFC-normalized.
        product_dir: Product-level directory, NFC-normalized.
        product_id: Parsed trailing Naver product id when present.
        section: Detail/review/unknown section classification.
        mime_type: PIL-detected image MIME type.
        width: Decoded image width in pixels.
        height: Decoded image height in pixels.
        size_bytes: File size in bytes.
    """

    path: Path
    relative_path: Path
    category: str
    product_dir: str
    product_id: str | None
    section: Section
    mime_type: str
    width: int
    height: int
    size_bytes: int


def main() -> None:
    """Build a redacted manifest and inventory from CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest-name", default=DEFAULT_MANIFEST_NAME)
    parser.add_argument("--inventory-name", default=DEFAULT_INVENTORY_NAME)
    parser.add_argument("--category-labels-name", default=DEFAULT_CATEGORY_LABELS_NAME)
    parser.add_argument("--category-taxonomy", type=Path, default=DEFAULT_CATEGORY_TAXONOMY_PATH)
    parser.add_argument("--image-root-env-var", default=DEFAULT_IMAGE_ROOT_ENV_VAR)
    parser.add_argument("--section", choices=("detail", "review", "all"), default="detail")
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--scan-limit", type=int, default=200_000)
    parser.add_argument("--seed", type=int, default=20260522)
    parser.add_argument("--min-width", type=int, default=160)
    parser.add_argument("--min-height", type=int, default=120)
    parser.add_argument("--max-bytes", type=int, default=50_000_000)
    parser.add_argument(
        "--review-personal-data-cleared",
        action="store_true",
        help=(
            "Allow review images to be emitted with contains_personal_data=false. "
            "Without this flag, review rows are emitted for local-only PII screening "
            "with contains_personal_data=null and external_transfer_allowed=false."
        ),
    )
    args = parser.parse_args()
    try:
        summary = build_naver_tampermonkey_manifest(
            source_root=args.source_root,
            output_dir=args.output_dir,
            manifest_name=args.manifest_name,
            inventory_name=args.inventory_name,
            category_labels_name=args.category_labels_name,
            category_taxonomy_path=args.category_taxonomy,
            image_root_env_var=args.image_root_env_var,
            section=args.section,
            sample_size=args.sample_size,
            scan_limit=args.scan_limit,
            seed=args.seed,
            min_width=args.min_width,
            min_height=args.min_height,
            max_bytes=args.max_bytes,
            review_personal_data_cleared=args.review_personal_data_cleared,
        )
    except (OSError, ValueError) as exc:
        failure = _failure_summary(
            source_root=args.source_root,
            manifest_name=args.manifest_name,
            inventory_name=args.inventory_name,
            category_labels_name=args.category_labels_name,
            error=exc,
        )
        output_dir = args.output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        failure_inventory_name = _fallback_inventory_name(args.inventory_name)
        (output_dir / failure_inventory_name).write_text(
            json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from None
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def build_naver_tampermonkey_manifest(
    *,
    source_root: Path,
    output_dir: Path,
    manifest_name: str,
    inventory_name: str,
    category_labels_name: str = DEFAULT_CATEGORY_LABELS_NAME,
    category_taxonomy_path: Path | None = DEFAULT_CATEGORY_TAXONOMY_PATH,
    image_root_env_var: str = DEFAULT_IMAGE_ROOT_ENV_VAR,
    section: ManifestSection,
    sample_size: int,
    scan_limit: int,
    seed: int,
    min_width: int,
    min_height: int,
    max_bytes: int,
    review_personal_data_cleared: bool = False,
) -> dict[str, object]:
    """Scan the crawl tree and write inventory plus a sampled manifest.

    Args:
        source_root: Local Tampermonkey crawl root.
        output_dir: Destination for generated inventory and manifest files.
        manifest_name: JSONL manifest filename.
        inventory_name: JSON inventory filename.
        category_labels_name: JSON category label inventory filename.
        category_taxonomy_path: Official-source taxonomy used to map folder
            names into DB-ready fixture category labels. Pass None to emit only
            folder-derived fallback labels.
        image_root_env_var: Environment variable token used in ``image_path``
            instead of writing the operator's absolute local source path.
        section: Section to include in the manifest.
        sample_size: Maximum number of manifest rows.
        scan_limit: Maximum number of files to inspect.
        seed: Deterministic category-balanced sampling seed.
        min_width: Minimum decoded image width.
        min_height: Minimum decoded image height.
        max_bytes: Maximum file size in bytes.
        review_personal_data_cleared: Whether review images are cleared for external eligibility.

    Returns:
        Redacted summary with generated artifact filenames and counts.

    Raises:
        ValueError: If inputs are invalid.
    """
    safe_manifest_name = _safe_output_filename(manifest_name, field_name="manifest_name")
    safe_inventory_name = _safe_output_filename(inventory_name, field_name="inventory_name")
    safe_category_labels_name = _safe_output_filename(
        category_labels_name,
        field_name="category_labels_name",
    )
    _validate_options(
        source_root=source_root,
        image_root_env_var=image_root_env_var,
        sample_size=sample_size,
        scan_limit=scan_limit,
        min_width=min_width,
        min_height=min_height,
        max_bytes=max_bytes,
    )
    source_root = source_root.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    candidates, inventory = scan_naver_tampermonkey_images(
        source_root=source_root,
        scan_limit=scan_limit,
        min_width=min_width,
        min_height=min_height,
        max_bytes=max_bytes,
    )
    category_taxonomy = load_category_taxonomy(category_taxonomy_path)
    selected = select_manifest_candidates(
        candidates,
        section=section,
        sample_size=sample_size,
        seed=seed,
    )
    rows = build_manifest_rows(
        selected,
        category_taxonomy=category_taxonomy,
        image_root_env_var=image_root_env_var,
        review_personal_data_cleared=review_personal_data_cleared,
    )
    category_labels = build_category_label_inventory(
        candidates,
        category_taxonomy=category_taxonomy,
    )
    category_label_key_counts = Counter(
        str(label["category_key"]) for label in category_labels["labels"]
    )
    inventory = {
        **inventory,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_root_hash": _sha256_text(str(source_root)),
        "source_root_exists": source_root.exists(),
        "manifest_section": section,
        "manifest_sample_size": sample_size,
        "manifest_row_count": len(rows),
        "category_taxonomy_schema_version": category_taxonomy.get("schema_version"),
        "category_taxonomy_path_hash": (
            _sha256_text(str(category_taxonomy_path.expanduser().resolve()))
            if category_taxonomy_path is not None
            else None
        ),
        "category_label_count": len(category_labels["labels"]),
        "category_label_key_counts": dict(sorted(category_label_key_counts.items())),
        "unmapped_category_count": category_labels["unmapped_category_count"],
        "source_doc_urls": list(SOURCE_DOC_URLS) + list(CATEGORY_TAXONOMY_SOURCE_DOC_URLS),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(inventory)
    _reject_unsafe_payload(category_labels)
    for row in rows:
        _reject_unsafe_payload(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / safe_manifest_name
    inventory_path = output_dir / safe_inventory_name
    category_labels_path = output_dir / safe_category_labels_name
    manifest_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    category_labels_path.write_text(
        json.dumps(category_labels, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "manifest_name": safe_manifest_name,
        "inventory_name": safe_inventory_name,
        "category_labels_name": safe_category_labels_name,
        "manifest_row_count": len(rows),
        "candidate_count": len(candidates),
        "category_label_count": len(category_labels["labels"]),
        "unmapped_category_count": category_labels["unmapped_category_count"],
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "local_path_literals_stored": False,
    }


def scan_naver_tampermonkey_images(
    *,
    source_root: Path,
    scan_limit: int,
    min_width: int,
    min_height: int,
    max_bytes: int,
) -> tuple[list[NaverImageCandidate], dict[str, object]]:
    """Scan image metadata from the crawl tree.

    Args:
        source_root: Local Tampermonkey crawl root.
        scan_limit: Maximum number of files to inspect.
        min_width: Minimum decoded image width.
        min_height: Minimum decoded image height.
        max_bytes: Maximum file size in bytes.

    Returns:
        Candidate list and redacted inventory counters.
    """
    source_root = source_root.expanduser().resolve()
    counters: Counter[str] = Counter()
    section_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    extension_counts: Counter[str] = Counter()
    mime_counts: Counter[str] = Counter()
    product_groups: set[tuple[str, str]] = set()
    candidates: list[NaverImageCandidate] = []

    for path in sorted(source_root.rglob("*")):
        if counters["files_seen"] >= scan_limit:
            break
        if not path.is_file():
            counters["non_files_skipped"] += 1
            continue
        counters["files_seen"] += 1
        suffix = path.suffix.lower()
        extension_counts[suffix or "<none>"] += 1
        if suffix not in IMAGE_SUFFIXES:
            counters["unsupported_extension_skipped"] += 1
            continue
        size_bytes = path.stat().st_size
        if size_bytes > max_bytes:
            counters["oversized_skipped"] += 1
            continue
        decoded = _decode_image_metadata(path)
        if decoded is None:
            counters["decode_failed"] += 1
            continue
        mime_type, width, height = decoded
        mime_counts[mime_type] += 1
        if mime_type not in ALLOWED_MIME_TYPES:
            counters["unsupported_mime_skipped"] += 1
            continue
        if width * height > MAX_DECODED_PIXELS:
            counters["huge_image_skipped"] += 1
            continue
        if width < min_width or height < min_height:
            counters["small_image_skipped"] += 1
            continue
        relative_path = path.relative_to(source_root)
        section = _section_from_path(relative_path)
        category = _category_from_path(relative_path)
        product_dir = _product_dir_from_path(relative_path)
        section_counts[section] += 1
        category_counts[category] += 1
        product_groups.add((category, product_dir))
        candidates.append(
            NaverImageCandidate(
                path=path,
                relative_path=relative_path,
                category=category,
                product_dir=product_dir,
                product_id=_product_id_from_dir(product_dir),
                section=section,
                mime_type=mime_type,
                width=width,
                height=height,
                size_bytes=size_bytes,
            )
        )
    inventory: dict[str, object] = {
        "files_seen": counters["files_seen"],
        "candidate_count": len(candidates),
        "section_counts": dict(sorted(section_counts.items())),
        "category_count": len(category_counts),
        "product_dir_count": len(product_groups),
        "top_categories": dict(category_counts.most_common(20)),
        "extension_counts": dict(sorted(extension_counts.items())),
        "mime_counts": dict(sorted(mime_counts.items())),
        "skip_counts": {
            key: value
            for key, value in sorted(counters.items())
            if key.endswith("_skipped") or key == "decode_failed"
        },
    }
    return candidates, inventory


def select_manifest_candidates(
    candidates: list[NaverImageCandidate],
    *,
    section: ManifestSection,
    sample_size: int,
    seed: int,
) -> list[NaverImageCandidate]:
    """Select a deterministic category-balanced manifest sample.

    Args:
        candidates: Decoded candidates.
        section: Section filter.
        sample_size: Maximum selected rows.
        seed: Deterministic sampling seed.

    Returns:
        Selected candidates.
    """
    if section == "all":
        filtered = [item for item in candidates if item.section in {"detail", "review"}]
    else:
        filtered = [item for item in candidates if item.section == section]
    grouped: dict[str, list[NaverImageCandidate]] = {}
    rng = random.Random(seed)
    for candidate in filtered:
        grouped.setdefault(candidate.category, []).append(candidate)
    for group in grouped.values():
        rng.shuffle(group)
        group.sort(key=lambda item: (item.product_dir, item.relative_path.as_posix()))
    selected: list[NaverImageCandidate] = []
    seen_sha256: set[str] = set()
    while grouped and len(selected) < sample_size:
        for category in sorted(grouped):
            group = grouped[category]
            if not group:
                del grouped[category]
                continue
            candidate = group.pop(0)
            image_sha256 = _sha256_file(candidate.path)
            if image_sha256 in seen_sha256:
                continue
            seen_sha256.add(image_sha256)
            selected.append(candidate)
            if len(selected) >= sample_size:
                break
    return selected


def build_manifest_rows(
    candidates: list[NaverImageCandidate],
    *,
    category_taxonomy: dict[str, object] | None = None,
    image_root_env_var: str = DEFAULT_IMAGE_ROOT_ENV_VAR,
    review_personal_data_cleared: bool = False,
) -> list[dict[str, object]]:
    """Convert selected candidates into collector-compatible JSONL rows.

    Args:
        candidates: Selected candidates.
        category_taxonomy: Loaded chronic supplement category fixture taxonomy.
        image_root_env_var: Environment variable token used to locate the
            source root at runtime without storing its absolute path.
        review_personal_data_cleared: Whether review images are cleared as not personal data.

    Returns:
        JSON-serializable manifest rows.

    """
    rows: list[dict[str, object]] = []
    for index, candidate in enumerate(candidates, 1):
        category_label = build_category_label(
            candidate.category,
            category_taxonomy=category_taxonomy,
        )
        image_sha256 = _sha256_file(candidate.path)
        section_token = "detail" if candidate.section == "detail" else "review"
        review_pending_screening = (
            candidate.section == "review" and not review_personal_data_cleared
        )
        row = {
            "fixture_id": f"naver-tm-{section_token}-{index:06d}",
            "source": "naver_tampermonkey",
            "category": candidate.category,
            "product_dir": candidate.product_dir,
            "product_id": candidate.product_id,
            "section": section_token,
            "image_path": _tokenized_image_path(image_root_env_var, candidate.relative_path),
            "image_sha256": image_sha256,
            "file_size_bytes": candidate.size_bytes,
            "mime_type": candidate.mime_type,
            "width": candidate.width,
            "height": candidate.height,
            "size_bucket": _size_bucket(candidate.size_bytes),
            "license_status": "team_approved",
            "consent_status": "team_approved",
            "contains_personal_data": None if review_pending_screening else False,
            "pii_screening_status": (
                "not_required_detail_page"
                if candidate.section == "detail"
                else (
                    "pending_local_screening"
                    if review_pending_screening
                    else "operator_cleared_review_local_only"
                )
            ),
            "external_transfer_allowed": candidate.section == "detail",
            "local_processing_allowed": True,
            "labels": [
                "naver_tampermonkey",
                section_token,
                _strip_category_brackets(candidate.category),
                str(category_label["category_key"]),
            ],
            "fixture_labels": {
                "supplement_category": {
                    "category_key": category_label["category_key"],
                    "source_category": category_label["source_category"],
                    "display_name_ko": category_label["display_name_ko"],
                    "display_name_en": category_label["display_name_en"],
                    "source": category_label["source"],
                    "verification_status": category_label["verification_status"],
                    "requires_human_review": category_label["requires_human_review"],
                },
                "language_targets": category_label["language_targets"],
                "chronic_fixture_tags": category_label["condition_tags"],
                "caution_tags": category_label["caution_tags"],
                "is_clinical_recommendation": False,
            },
            "db_labeling": {
                "status": "pending_human_review",
                "category_key": category_label["category_key"],
                "normalized_folder_label": category_label["normalized_folder_label"],
                "language_targets": category_label["language_targets"],
                "chronic_fixture_tags": category_label["condition_tags"],
                "caution_tags": category_label["caution_tags"],
                "source_urls": category_label["source_urls"],
            },
            "source_metadata": {
                "relative_path_hash": _sha256_text(candidate.relative_path.as_posix()),
                "category": _strip_category_brackets(candidate.category),
                "category_key": category_label["category_key"],
                "product_id_present": candidate.product_id is not None,
                "section": section_token,
            },
            "expected": {},
        }
        _reject_raw_fields(row)
        rows.append(row)
    return rows


def load_category_taxonomy(path: Path | None) -> dict[str, object]:
    """Load official-source category taxonomy for fixture labeling.

    Args:
        path: JSON taxonomy path. ``None`` disables mapped taxonomy and keeps
            folder-name fallback labels only.

    Returns:
        Taxonomy payload with category entries.

    Raises:
        ValueError: If the taxonomy file is missing or malformed.
    """
    if path is None:
        return {"schema_version": None, "categories": {}}
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError("category_taxonomy_path is not a file.")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("category_taxonomy_path is not valid JSON.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("categories"), dict):
        raise ValueError("category taxonomy must contain a categories object.")
    return payload


def build_category_label_inventory(
    candidates: list[NaverImageCandidate],
    *,
    category_taxonomy: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build one DB labeling seed per folder category.

    Args:
        candidates: Decoded candidates.
        category_taxonomy: Loaded taxonomy used for category mapping.

    Returns:
        Redacted category label inventory.
    """
    category_counts: Counter[str] = Counter(candidate.category for candidate in candidates)
    product_groups: dict[str, set[str]] = {}
    for candidate in candidates:
        product_groups.setdefault(candidate.category, set()).add(candidate.product_dir)

    labels: list[dict[str, object]] = []
    for category in sorted(category_counts):
        label = build_category_label(category, category_taxonomy=category_taxonomy)
        labels.append(
            {
                **label,
                "candidate_count": category_counts[category],
                "product_dir_count": len(product_groups.get(category, set())),
            }
        )
    return {
        "schema_version": "naver-tampermonkey-folder-category-labels-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "taxonomy_schema_version": (category_taxonomy or {"schema_version": None}).get(
            "schema_version"
        ),
        "label_source": "tampermonkey_folder_name",
        "language_targets": ["ko", "en"],
        "is_clinical_recommendation": False,
        "labels": labels,
        "unmapped_category_count": sum(
            1 for label in labels if label["verification_status"] == "folder_name_only"
        ),
        "source_doc_urls": list(CATEGORY_TAXONOMY_SOURCE_DOC_URLS),
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
    }


def build_category_label(
    category: str,
    *,
    category_taxonomy: dict[str, object] | None = None,
) -> dict[str, object]:
    """Map a Tampermonkey folder name into a DB-ready fixture label.

    Args:
        category: Raw top-level folder category.
        category_taxonomy: Loaded official-source taxonomy.

    Returns:
        JSON-serializable label metadata. Unknown folders are preserved as
        folder-name-only labels with a stable hashed category key.
    """
    source_category = _normalize_path_text(category)
    display = _strip_category_brackets(source_category)
    normalized_folder_label = _normalize_category_label(display)
    taxonomy_entry = _find_category_taxonomy_entry(
        normalized_folder_label,
        category_taxonomy=category_taxonomy,
    )
    language_targets = _language_targets_for_label(display, taxonomy_entry)
    if taxonomy_entry:
        category_key = str(taxonomy_entry["category_key"])
        return {
            "source_category": source_category,
            "normalized_folder_label": normalized_folder_label,
            "category_key": category_key,
            "display_name_ko": str(taxonomy_entry.get("display_name_ko", display)),
            "display_name_en": str(taxonomy_entry.get("display_name_en", display)),
            "source": "official_taxonomy_folder_alias",
            "verification_status": "taxonomy_seeded",
            "requires_human_review": True,
            "language_targets": language_targets,
            "condition_tags": list(taxonomy_entry.get("condition_tags", [])),
            "caution_tags": list(taxonomy_entry.get("caution_tags", [])),
            "source_urls": list(taxonomy_entry.get("source_urls", [])),
        }
    return {
        "source_category": source_category,
        "normalized_folder_label": normalized_folder_label,
        "category_key": f"unmapped_tampermonkey_{_sha256_text(display)[:12]}",
        "display_name_ko": display,
        "display_name_en": display,
        "source": "tampermonkey_folder_name",
        "verification_status": "folder_name_only",
        "requires_human_review": True,
        "language_targets": language_targets,
        "condition_tags": ["general_supplement"],
        "caution_tags": ["human_review_required"],
        "source_urls": list(CATEGORY_TAXONOMY_SOURCE_DOC_URLS),
    }


def _validate_options(
    *,
    source_root: Path,
    image_root_env_var: str,
    sample_size: int,
    scan_limit: int,
    min_width: int,
    min_height: int,
    max_bytes: int,
) -> None:
    """Validate manifest build options."""
    if not source_root.expanduser().is_dir():
        raise ValueError("source_root is not a directory.")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", image_root_env_var):
        raise ValueError("image_root_env_var must be an uppercase environment variable name.")
    if sample_size < 1 or scan_limit < 1:
        raise ValueError("sample_size and scan_limit must be positive.")
    if min_width < 1 or min_height < 1 or max_bytes < 1:
        raise ValueError("min_width, min_height, and max_bytes must be positive.")


def _find_category_taxonomy_entry(
    normalized_folder_label: str,
    *,
    category_taxonomy: dict[str, object] | None,
) -> dict[str, object] | None:
    """Return a taxonomy entry by normalized folder alias."""
    if not category_taxonomy:
        return None
    categories = category_taxonomy.get("categories")
    if not isinstance(categories, dict):
        return None
    for category_key, raw_entry in categories.items():
        if not isinstance(raw_entry, dict):
            continue
        folder_aliases = raw_entry.get("folder_aliases", [])
        aliases = [str(alias) for alias in folder_aliases if str(alias).strip()]
        aliases.append(str(category_key))
        if normalized_folder_label in {_normalize_category_label(alias) for alias in aliases}:
            return {"category_key": category_key, **raw_entry}
    return None


def _language_targets_for_label(
    display: str,
    taxonomy_entry: dict[str, object] | None,
) -> list[str]:
    """Return language targets for bilingual OCR/DB labeling."""
    targets = {"ko", "en"}
    if re.search(r"[가-힣]", display):
        targets.add("ko")
    if re.search(r"[A-Za-z]", display):
        targets.add("en")
    if taxonomy_entry:
        for key in ("display_name_ko", "display_name_en"):
            if taxonomy_entry.get(key):
                targets.add("ko" if key.endswith("_ko") else "en")
    return sorted(targets)


def _normalize_category_label(value: str) -> str:
    """Return a stable key for Korean/English folder labels."""
    normalized = _strip_category_brackets(value).casefold()
    normalized = normalized.replace("&", "_and_")
    normalized = re.sub(r"[\s\-]+", "_", normalized)
    normalized = re.sub(r"[^\w가-힣]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_") or "unknown"


def _decode_image_metadata(path: Path) -> tuple[str, int, int] | None:
    """Decode MIME type and dimensions without retaining image bytes."""
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


def _section_from_path(relative_path: Path) -> Section:
    """Return detail/review section from NFC-normalized path parts."""
    parts = [_normalize_path_text(part) for part in relative_path.parts]
    if any(part == "상세페이지" for part in parts):
        return "detail"
    if any(part == "리뷰" for part in parts):
        return "review"
    return "unknown"


def _category_from_path(relative_path: Path) -> str:
    """Return the top-level category segment."""
    if not relative_path.parts:
        return "unknown"
    return _normalize_path_text(relative_path.parts[0])


def _product_dir_from_path(relative_path: Path) -> str:
    """Return the product directory before the section segment."""
    parts = [_normalize_path_text(part) for part in relative_path.parts]
    for index, part in enumerate(parts):
        if part in {"상세페이지", "리뷰"} and index > 0:
            return parts[index - 1]
    if len(parts) >= MIN_PRODUCT_PATH_PARTS:
        return parts[1]
    return "unknown"


def _product_id_from_dir(product_dir: str) -> str | None:
    """Extract a trailing Naver product id from a product directory."""
    match = PRODUCT_ID_PATTERN.search(product_dir)
    return match.group("product_id") if match else None


def _strip_category_brackets(value: str) -> str:
    """Normalize category text for report labels."""
    stripped = _normalize_path_text(value).strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return stripped[1:-1].strip() or "unknown"
    return stripped or "unknown"


def _size_bucket(size_bytes: int) -> str:
    """Return a coarse size bucket for report grouping."""
    if size_bytes < SMALL_IMAGE_BYTES:
        return "small"
    if size_bytes < MEDIUM_IMAGE_BYTES:
        return "medium"
    return "large"


def _normalize_path_text(value: str) -> str:
    """Normalize macOS decomposed Korean path segments to NFC."""
    return unicodedata.normalize("NFC", value)


def _tokenized_image_path(image_root_env_var: str, relative_path: Path) -> str:
    """Return a runtime-resolvable image path without local absolute prefixes.

    Args:
        image_root_env_var: Environment variable that points to the source root.
        relative_path: Path under the source root.

    Returns:
        ``$ENV_VAR/<relative path>`` for collector runtime expansion.
    """
    return f"${image_root_env_var}/{relative_path.as_posix()}"


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a local file."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    """Return a SHA-256 digest for path metadata."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _failure_summary(
    *,
    source_root: Path,
    manifest_name: str,
    inventory_name: str,
    category_labels_name: str,
    error: BaseException,
) -> dict[str, object]:
    """Return a redacted manifest-generation failure summary."""
    summary = {
        "schema_version": "naver-tampermonkey-ocr-manifest-failure-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "source_root_hash": _sha256_text(str(source_root.expanduser())),
        "source_root_exists": _safe_path_exists(source_root),
        "manifest_name": _safe_name_or_default(manifest_name, DEFAULT_MANIFEST_NAME),
        "inventory_name": _safe_name_or_default(inventory_name, DEFAULT_INVENTORY_NAME),
        "category_labels_name": _safe_name_or_default(
            category_labels_name,
            DEFAULT_CATEGORY_LABELS_NAME,
        ),
        "error_code": _safe_error_code(error),
        "error_message": _safe_public_error_message(error),
        "files_seen": 0,
        "candidate_count": 0,
        "manifest_row_count": 0,
        "category_label_count": 0,
        "unmapped_category_count": 0,
        "raw_artifacts_stored": False,
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    _reject_unsafe_payload(summary)
    return summary


def _safe_output_filename(value: str, *, field_name: str) -> str:
    """Return a filename that cannot escape the requested output directory."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty filename.")
    stripped = value.strip()
    if (
        stripped in {".", ".."}
        or "/" in stripped
        or "\\" in stripped
        or Path(stripped).name != stripped
        or any(marker in stripped for marker in LOCAL_PATH_MARKERS)
    ):
        raise ValueError(f"{field_name} must be a filename, not a path.")
    return stripped


def _safe_name_or_default(value: str, default: str) -> str:
    """Return a safe filename for failure summaries without raising."""
    try:
        return _safe_output_filename(value, field_name="filename")
    except ValueError:
        return default


def _fallback_inventory_name(value: str) -> str:
    """Return a safe inventory filename even when user input is invalid."""
    return _safe_name_or_default(value, DEFAULT_INVENTORY_NAME)


def _safe_path_exists(path: Path) -> bool:
    """Return whether a path exists without exposing path details."""
    try:
        return path.expanduser().exists()
    except OSError:
        return False


def _safe_error_code(exc: BaseException) -> str:
    """Return a non-sensitive CLI error code."""
    if isinstance(exc, OSError):
        return "local_file_error"
    return "validation_error"


def _safe_public_error_message(exc: BaseException) -> str:
    """Return a bounded public error message without filesystem details."""
    if isinstance(exc, OSError):
        return "Local file operation failed."
    message = str(exc).strip()
    if not message:
        return "Validation failed."
    if any(marker in message for marker in LOCAL_PATH_MARKERS):
        return "Validation failed."
    if "/" in message or "\\" in message:
        return "Validation failed."
    return message[:200]


def _reject_raw_fields(value: object) -> None:
    """Reject raw OCR/image/provider/model fields before writing artifacts."""
    _reject_unsafe_payload(value)


def _reject_unsafe_payload(value: object) -> None:
    """Reject raw fields and local path literals before writing artifacts."""
    if isinstance(value, dict):
        forbidden = RAW_FORBIDDEN_KEYS.intersection(str(key).lower() for key in value)
        if forbidden:
            raise ValueError(f"Payload contains forbidden raw field(s): {sorted(forbidden)}")
        for nested in value.values():
            _reject_unsafe_payload(nested)
    elif isinstance(value, list):
        for item in value:
            _reject_unsafe_payload(item)
    elif isinstance(value, str) and any(marker in value for marker in LOCAL_PATH_MARKERS):
        raise ValueError("Payload contains local path literal.")


if __name__ == "__main__":
    main()
