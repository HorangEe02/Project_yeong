"""Validate the supplement-label ground-truth expected/ directory.

Iterates over every ``*.snapshot_v2.json`` / ``*.snapshot_v3.json`` under the
expected/ directory, validates each against the corresponding Pydantic schema,
and reports overall progress toward the Stage 0 gate of ≥30 human-labeled
fixtures.

A snapshot counts as ``human_labeled`` when it has at least one ingredient
candidate whose ``source`` is ``manual`` or ``user_confirmed`` and the file
does **not** carry the ``ground_truth_pending_human_review`` warning.

Usage:
    .venv/bin/python scripts/validate_ground_truth.py \\
      --expected-dir ../Nutrition-backend/tests/fixtures/supplement_labels/expected/ \\
      --target-count 30

Reference:
    outputs/todo-list/2026-05-21/project-status-report.md §6 P0-2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = SCRIPT_DIR.parent / "Nutrition-backend"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from pydantic import ValidationError  # noqa: E402
from src.models.schemas.supplement_snapshot import (  # noqa: E402
    SupplementParsedSnapshotV2,
    SupplementParsedSnapshotV3,
)

PENDING_REVIEW_WARNING = "ground_truth_pending_human_review"
"""사람 검수가 아직 끝나지 않은 fixture에 붙는 경고 토큰."""

AUTO_SEED_INGREDIENT_SOURCES = frozenset({"ocr_llm_preview"})
"""자동 시드된 (사람 검수 전) ingredient candidate 의 source 값들."""

HUMAN_CONFIRMED_INGREDIENT_SOURCES = frozenset({"manual", "user_confirmed"})
"""사람 검수가 완료된 ingredient candidate 의 source 값들."""

DEFAULT_TARGET = 30
"""Stage 0 게이트의 기본 라벨링 목표 수."""


@dataclass
class ValidationSummary:
    """Aggregate validation results.

    Attributes:
        v2_total: V2 snapshot 파일 총 수.
        v2_valid: schema validation 을 통과한 V2 파일 수.
        v2_human_labeled: 사람 검수가 완료된 V2 파일 수.
        v3_total: V3 snapshot 파일 총 수.
        v3_valid: schema validation 을 통과한 V3 파일 수.
        v3_human_labeled: 사람 검수가 완료된 V3 파일 수.
        errors: ``(file_ref, error_message)`` 형식의 오류 리스트. ``file_ref`` 는
            로컬 절대경로 대신 파일명과 path hash 만 담는다.
    """

    v2_total: int = 0
    v2_valid: int = 0
    v2_human_labeled: int = 0
    v3_total: int = 0
    v3_valid: int = 0
    v3_human_labeled: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)


def _is_human_labeled(snapshot: dict[str, object]) -> bool:
    """Snapshot 이 사람 검수가 완료된 상태인지 판정한다.

    Args:
        snapshot: V2 또는 V3 snapshot 사전.

    Returns:
        ``True`` 이면 human-confirmed, ``False`` 이면 auto-seed/pending review.
    """
    warnings = snapshot.get("warnings")
    if isinstance(warnings, list) and PENDING_REVIEW_WARNING in warnings:
        return False
    ingredients_v2 = snapshot.get("ingredient_candidates")
    ingredients_v3 = snapshot.get("ingredients")
    ingredients = ingredients_v2 if isinstance(ingredients_v2, list) else ingredients_v3
    if not isinstance(ingredients, list) or not ingredients:
        return False
    for candidate in ingredients:
        if not isinstance(candidate, dict):
            continue
        source = candidate.get("source")
        if isinstance(source, str) and source in HUMAN_CONFIRMED_INGREDIENT_SOURCES:
            return True
    return False


def _validate_file(path: Path, summary: ValidationSummary) -> None:
    """단일 snapshot 파일을 검증해 ``summary`` 에 반영한다.

    Args:
        path: V2 또는 V3 snapshot 파일 경로.
        summary: 누적 결과 컨테이너.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        summary.errors.append((_redacted_path_ref(path), _redacted_read_error(exc)))
        return
    if not isinstance(payload, dict):
        summary.errors.append((_redacted_path_ref(path), "top-level JSON must be an object"))
        return
    is_v3 = path.name.endswith(".snapshot_v3.json")
    if is_v3:
        summary.v3_total += 1
    else:
        summary.v2_total += 1
    try:
        if is_v3:
            SupplementParsedSnapshotV3.model_validate(payload)
            summary.v3_valid += 1
        else:
            SupplementParsedSnapshotV2.model_validate(payload)
            summary.v2_valid += 1
    except ValidationError as exc:
        summary.errors.append((_redacted_path_ref(path), _redacted_validation_error(exc)))
        return
    if _is_human_labeled(payload):
        if is_v3:
            summary.v3_human_labeled += 1
        else:
            summary.v2_human_labeled += 1


def validate_directory(expected_dir: Path) -> ValidationSummary:
    """``expected_dir`` 아래 모든 snapshot 파일을 검증한다.

    Args:
        expected_dir: V2/V3 snapshot 들이 위치한 디렉토리.

    Returns:
        검증 결과 요약.
    """
    summary = ValidationSummary()
    if not expected_dir.exists():
        summary.errors.append((_redacted_path_ref(expected_dir), "directory_not_found"))
        return summary
    for path in sorted(expected_dir.glob("*.snapshot_v*.json")):
        _validate_file(path, summary)
    return summary


def _redacted_path_ref(path: Path) -> str:
    """Return a stable non-sensitive path reference.

    Args:
        path: Local path that may contain user, volume, or temporary directory
            names.

    Returns:
        File or directory basename plus a short hash of the expanded path.
    """
    name = path.name or "path"
    path_hash = hashlib.sha256(str(path.expanduser()).encode("utf-8")).hexdigest()[:12]
    return f"{name} [path_hash={path_hash}]"


def _redacted_read_error(exc: OSError | json.JSONDecodeError) -> str:
    """Return a read/parse error without embedding local paths.

    Args:
        exc: Exception raised while reading or parsing JSON.

    Returns:
        Bounded error summary safe for CLI output and reports.
    """
    if isinstance(exc, json.JSONDecodeError):
        return (
            f"read_or_parse_error: JSONDecodeError:{exc.msg} " f"line={exc.lineno} col={exc.colno}"
        )
    return f"read_or_parse_error: {type(exc).__name__}"


def _redacted_validation_error(exc: ValidationError) -> str:
    """Return schema validation details without raw input values.

    Args:
        exc: Pydantic validation error.

    Returns:
        Error type and location details for at most three validation issues.
    """
    details: list[dict[str, object]] = []
    for error in exc.errors()[:3]:
        loc = ".".join(str(part) for part in error.get("loc", ()))
        details.append(
            {
                "type": error.get("type", "unknown"),
                "loc": loc,
            }
        )
    return f"schema_validation: {details}"


def _format_progress_line(human_labeled: int, target: int) -> str:
    """라벨링 진행률을 한 줄 문자열로 포맷한다.

    Args:
        human_labeled: 사람 검수 완료 fixture 수.
        target: 목표 fixture 수.

    Returns:
        ``"3/30 (10.0%)"`` 같은 진행률 문자열.
    """
    percent = (100.0 * human_labeled / target) if target > 0 else 0.0
    return f"{human_labeled}/{target} ({percent:.1f}%)"


def render_report(summary: ValidationSummary, target_count: int) -> str:
    """검증 결과 요약을 사람이 읽기 좋게 정리한다.

    Args:
        summary: 검증 결과.
        target_count: Stage 0 게이트 목표 수.

    Returns:
        멀티라인 보고서 문자열.
    """
    lines = [
        "Validation summary:",
        f"  V2 files: {summary.v2_total}",
        f"  V2 schema valid: {summary.v2_valid}/{summary.v2_total}",
        f"  V2 human-labeled: {summary.v2_human_labeled}/{summary.v2_total}",
        f"  V3 files: {summary.v3_total}",
        f"  V3 schema valid: {summary.v3_valid}/{summary.v3_total}",
        f"  V3 human-labeled: {summary.v3_human_labeled}/{summary.v3_total}",
        "",
        f"Stage 0 gate progress (V2): {_format_progress_line(summary.v2_human_labeled, target_count)}",
    ]
    if summary.errors:
        lines.append("")
        lines.append("Errors:")
        for path, message in summary.errors:
            lines.append(f"  - {path}: {message}")
    return "\n".join(lines)


def main() -> None:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected-dir",
        required=True,
        type=Path,
        help="Directory containing *.snapshot_v2.json / *.snapshot_v3.json files",
    )
    parser.add_argument(
        "--target-count",
        type=int,
        default=DEFAULT_TARGET,
        help=f"Target number of human-labeled fixtures (default {DEFAULT_TARGET})",
    )
    args = parser.parse_args()

    summary = validate_directory(args.expected_dir)
    print(render_report(summary, args.target_count))
    if summary.errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
