"""Create a V2 ground-truth snapshot skeleton for human labeling.

Generates a ``*.snapshot_v2.json`` file matching ``SupplementParsedSnapshotV2``
schema with empty / TBD placeholders so the user can fill in fields by hand.
Optionally bootstraps ``ingredient_candidates`` from a comma-separated list of
known display names supplied on the CLI, marking them with ``source =
"auto_seed_pending_review"`` and a warning so the validator can tell them apart
from human-confirmed labels.

Raw OCR text and raw images are never persisted by this script; the generated
JSON only contains the placeholder structure required by the schema.

Usage:
    .venv/bin/python scripts/label_ground_truth.py \\
      --fixture-id naver-live-0015 \\
      --category 비타민A \\
      --output ../Nutrition-backend/tests/fixtures/supplement_labels/expected/naver-live-0015.snapshot_v2.json

Reference:
    outputs/todo-list/2026-05-21/project-status-report.md §6 P0-2
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from uuid import UUID, uuid5

SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = SCRIPT_DIR.parent / "Nutrition-backend"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from src.models.schemas.supplement_snapshot import (  # noqa: E402
    SupplementParsedSnapshotV2,
    SupplementParsedSnapshotV3,
)

ALLOWED_CHRONIC_CONDITIONS = frozenset(
    {
        "diabetes",
        "hypertension",
        "dyslipidemia",
        "cardiovascular",
        "osteoporosis",
        "chronic_kidney_disease",
        "liver_disease",
        "cognitive_decline",
    }
)
"""``SupplementParsedSnapshotV3.chronic_disease_indications`` 허용 토큰."""

PENDING_REVIEW_WARNING = "ground_truth_pending_human_review"
"""사람 검수가 아직 끝나지 않은 fixture에 붙는 경고 토큰."""

AUTO_SEED_INGREDIENT_SOURCE = "ocr_llm_preview"
"""자동 시드된 ingredient candidate 의 source 값. Schema literal 과 호환."""

HUMAN_CONFIRMED_INGREDIENT_SOURCE = "manual"
"""사람 검수가 끝난 ingredient candidate 의 source 값."""

_FIXTURE_NAMESPACE = UUID("00000000-0000-4000-8000-000000000000")
"""``analysis_id`` 생성을 위한 결정론적 UUID namespace."""


def _normalize_name(display_name: str) -> str:
    """라벨링 정규화 규칙: 소문자, 공백 단일화.

    Args:
        display_name: 원본 표시명.

    Returns:
        정규화된 이름.
    """
    return " ".join(display_name.casefold().split())


def _parse_ingredient_seed(raw: str) -> list[dict[str, object]]:
    """쉼표로 구분된 ingredient seed 문자열을 candidate 사전 리스트로 변환한다.

    Args:
        raw: ``"비타민 A, 비타민 D, 칼슘"`` 형태의 문자열.

    Returns:
        ``ingredient_candidates`` 항목으로 사용 가능한 사전 리스트.
    """
    candidates: list[dict[str, object]] = []
    for token in re.split(r"[,\n]", raw):
        display = token.strip()
        if not display:
            continue
        candidates.append(
            {
                "display_name": display,
                "normalized_name": _normalize_name(display),
                "nutrient_code_candidates": [],
                "amount": None,
                "unit": None,
                "daily_amount": None,
                "confidence": 0.0,
                "source": AUTO_SEED_INGREDIENT_SOURCE,
                "evidence_refs": [],
            }
        )
    return candidates


def _parse_chronic_disease_targets(raw: str) -> list[str]:
    """``--chronic-disease-targets`` CLI 입력을 검증된 토큰 리스트로 변환한다.

    Args:
        raw: ``"cardiovascular,dyslipidemia"`` 형태의 문자열.

    Returns:
        ``ALLOWED_CHRONIC_CONDITIONS`` 멤버만 남긴 중복 제거 리스트.

    Raises:
        ValueError: 정의되지 않은 condition 이 포함된 경우.
    """
    targets: list[str] = []
    for token in raw.split(","):
        normalized = token.strip()
        if not normalized:
            continue
        if normalized not in ALLOWED_CHRONIC_CONDITIONS:
            raise ValueError(
                f"Unknown chronic condition: {normalized!r}. "
                f"Allowed: {sorted(ALLOWED_CHRONIC_CONDITIONS)}"
            )
        if normalized not in targets:
            targets.append(normalized)
    return targets


def build_skeleton(
    fixture_id: str,
    category: str,
    seed_ingredients: list[dict[str, object]],
) -> dict[str, object]:
    """V2 snapshot skeleton 사전을 만든다.

    Args:
        fixture_id: ``naver-live-0015`` 같은 고유 식별자.
        category: ``비타민A`` 같은 fixture 카테고리 (warnings 에 기록).
        seed_ingredients: 자동 시드된 ingredient candidate 리스트 (없으면 빈 리스트).

    Returns:
        ``SupplementParsedSnapshotV2`` schema 와 호환되는 사전.
    """
    analysis_uuid = uuid5(_FIXTURE_NAMESPACE, fixture_id)
    return {
        "schema_version": "supplement-parsed-snapshot-v2",
        "requires_user_confirmation": True,
        "source": {
            "analysis_id": str(analysis_uuid),
            "ocr_provider": "manual",
            "ocr_confidence": None,
            "layout_available": False,
            "raw_image_stored": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
        },
        "product": {
            "product_name": "TBD",
            "manufacturer": None,
            "barcode_text": None,
            "barcode_format": None,
        },
        "serving": {
            "serving_size_text": "TBD",
            "serving_amount": None,
            "serving_unit": None,
            "daily_servings": None,
            "evidence_refs": [],
        },
        "label_sections": [],
        "ingredient_candidates": seed_ingredients,
        "intake_method": {
            "text": None,
            "structured": {
                "frequency": "unknown",
                "time_of_day": [],
                "with_food": "unknown",
            },
            "evidence_refs": [],
        },
        "precautions": [],
        "functional_claims": [],
        "low_confidence_fields": [],
        "warnings": [
            PENDING_REVIEW_WARNING,
            f"category:{category}",
            "labels:live_naver,detail_page",
        ],
    }


def build_v3_skeleton(
    fixture_id: str,
    category: str,
    seed_ingredients: list[dict[str, object]],
    chronic_disease_targets: list[str],
) -> dict[str, object]:
    """V3 snapshot skeleton 사전을 만든다.

    V2 skeleton 의 모든 placeholder 필드를 V3 구조로 옮기고
    ``chronic_disease_indications`` 초기값을 함께 채운다.

    Args:
        fixture_id: 고유 식별자.
        category: fixture 카테고리.
        seed_ingredients: 자동 시드 ingredient 리스트.
        chronic_disease_targets: V3 ``chronic_disease_indications`` 초기값.

    Returns:
        ``SupplementParsedSnapshotV3`` schema 와 호환되는 사전.
    """
    analysis_uuid = uuid5(_FIXTURE_NAMESPACE, fixture_id)
    return {
        "schema_version": "supplement-parsed-snapshot-v3",
        "requires_user_confirmation": True,
        "source": {
            "analysis_id": str(analysis_uuid),
            "ocr_provider": "manual",
            "ocr_confidence": None,
            "layout_available": False,
            "raw_image_stored": False,
            "raw_ocr_text_stored": False,
            "raw_provider_payload_stored": False,
            "raw_model_response_stored": False,
            "parser_schema_version": "supplement-parser-output-v2",
        },
        "product": {
            "product_name": "TBD",
            "manufacturer": None,
            "barcode_candidates": [],
            "evidence_refs": [],
        },
        "serving": {
            "serving_size_text": "TBD",
            "serving_amount": None,
            "serving_unit": None,
            "daily_servings": None,
            "evidence_refs": [],
        },
        "ingredients": seed_ingredients,
        "label_sections": [],
        "intake_method": {
            "text": None,
            "structured": {
                "frequency": "unknown",
                "time_of_day": [],
                "with_food": "unknown",
            },
            "evidence_refs": [],
        },
        "precautions": [],
        "functional_claims": [],
        "evidence_spans": [],
        "domain_correction_audit": [],
        "low_confidence_fields": [],
        "warnings": [
            PENDING_REVIEW_WARNING,
            f"category:{category}",
            "labels:live_naver,detail_page",
        ],
        "chronic_disease_indications": chronic_disease_targets,
    }


def write_skeleton(
    output_path: Path,
    fixture_id: str,
    category: str,
    seed_ingredients: list[dict[str, object]],
    overwrite: bool,
    chronic_disease_targets: list[str] | None = None,
) -> bool:
    """Skeleton 을 ``output_path`` 에 JSON 으로 저장한다.

    출력 경로의 확장자가 ``.snapshot_v3.json`` 으로 끝나면 V3 skeleton 을,
    그 외에는 V2 skeleton 을 저장한다. ``chronic_disease_targets`` 는 V3 에서만
    의미가 있고 V2 skeleton 에서는 무시된다 (V2 schema 에 필드 없음).

    Args:
        output_path: V2 / V3 snapshot 저장 경로.
        fixture_id: fixture 식별자.
        category: fixture 카테고리.
        seed_ingredients: 자동 시드 ingredient 리스트.
        overwrite: True 면 기존 파일을 덮어쓴다.
        chronic_disease_targets: V3 ``chronic_disease_indications`` 초기값.

    Returns:
        새로 저장됐으면 ``True``, 이미 파일이 있어 skip 했으면 ``False``.
    """
    if output_path.exists() and not overwrite:
        return False
    is_v3 = output_path.name.endswith(".snapshot_v3.json")
    if is_v3:
        skeleton = build_v3_skeleton(
            fixture_id,
            category,
            seed_ingredients,
            chronic_disease_targets or [],
        )
        SupplementParsedSnapshotV3.model_validate(skeleton)
    else:
        skeleton = build_skeleton(fixture_id, category, seed_ingredients)
        SupplementParsedSnapshotV2.model_validate(skeleton)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(skeleton, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return True


def main() -> None:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-id",
        required=True,
        help="Fixture identifier, e.g. naver-live-0015",
    )
    parser.add_argument(
        "--category",
        required=True,
        help="Fixture category, e.g. 비타민A or 멀티비타민",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output path for the V2 snapshot skeleton",
    )
    parser.add_argument(
        "--seed-ingredients",
        default="",
        help='Comma-separated ingredient display names to pre-fill, e.g. "비타민 A, 비타민 D"',
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing file at --output",
    )
    parser.add_argument(
        "--chronic-disease-targets",
        default="",
        help=(
            "Comma-separated chronic-disease indications for V3 snapshots, e.g. "
            '"cardiovascular,dyslipidemia". Allowed tokens: '
            "diabetes, hypertension, dyslipidemia, cardiovascular, osteoporosis, "
            "chronic_kidney_disease, liver_disease, cognitive_decline. "
            "Only honored when --output ends with .snapshot_v3.json."
        ),
    )
    args = parser.parse_args()

    seeds = _parse_ingredient_seed(args.seed_ingredients) if args.seed_ingredients else []
    chronic_targets = (
        _parse_chronic_disease_targets(args.chronic_disease_targets)
        if args.chronic_disease_targets
        else []
    )
    created = write_skeleton(
        output_path=args.output,
        fixture_id=args.fixture_id,
        category=args.category,
        seed_ingredients=seeds,
        overwrite=args.overwrite,
        chronic_disease_targets=chronic_targets,
    )
    if created:
        print(f"Wrote skeleton: {args.output}")
    else:
        print(f"Skipped existing: {args.output} (use --overwrite to replace)")


if __name__ == "__main__":
    main()
