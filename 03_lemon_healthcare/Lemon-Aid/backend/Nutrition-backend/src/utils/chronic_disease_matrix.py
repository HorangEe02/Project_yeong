"""만성질환-영양제 매트릭스 로더 유틸리티.

``data/nutrition_reference/chronic_disease_supplement_matrix.json`` 을 읽어
schema 검증 후 캐시한다. 추천 / 평가 / 라벨링 코드에서 카테고리 → 만성질환
또는 만성질환 → 카테고리 매핑을 일관되게 조회한다.

Reference:
    outputs/todo-list/2026-05-21/chronic-disease-category-brainstorming.md §5
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from src.config import resolve_nutrition_reference_root
from src.models.schemas.chronic_disease_matrix import (
    CategoryProfile,
    ChronicCondition,
    ChronicDiseaseSupplementMatrix,
    ChronicDiseaseTarget,
    EvidenceLevel,
)

_EVIDENCE_RANK: dict[EvidenceLevel, int] = {
    "insufficient": 0,
    "weak": 1,
    "moderate": 2,
    "strong": 3,
}
"""``EvidenceLevel`` 순서 비교를 위한 정수 매핑."""

_DEFAULT_MATRIX_PATH = resolve_nutrition_reference_root() / "chronic_disease_supplement_matrix.json"
"""기본 매트릭스 JSON 위치.

레포(``Lemon-Aid/data/nutrition_reference``)와 컨테이너(``/app/data/nutrition_reference``)
의 디렉터리 깊이가 달라 고정 ``parents[N]`` 오프셋이 한쪽에서 어긋나므로,
:func:`src.config.resolve_nutrition_reference_root` 로 마커 기반 탐색한다.
"""


@lru_cache(maxsize=4)
def load_matrix(path: Path | None = None) -> ChronicDiseaseSupplementMatrix:
    """매트릭스 JSON 을 읽어 schema 검증 후 캐시 반환한다.

    Args:
        path: 매트릭스 파일 경로. ``None`` 이면 기본 위치를 사용한다.

    Returns:
        검증된 ``ChronicDiseaseSupplementMatrix`` 인스턴스.

    Raises:
        FileNotFoundError: 매트릭스 파일이 존재하지 않을 때.
        pydantic.ValidationError: schema 검증 실패 시.
    """
    target = path if path is not None else _DEFAULT_MATRIX_PATH
    if not target.exists():
        raise FileNotFoundError(f"Chronic-disease matrix not found: {target}")
    payload = json.loads(target.read_text(encoding="utf-8"))
    return ChronicDiseaseSupplementMatrix.model_validate(payload)


def category_to_conditions(
    category: str,
    *,
    matrix: ChronicDiseaseSupplementMatrix | None = None,
    min_evidence: EvidenceLevel = "weak",
) -> list[ChronicDiseaseTarget]:
    """카테고리명을 만성질환 인디케이션 리스트로 매핑한다.

    Args:
        category: 영양제 카테고리명 (예: ``"오메가3"``).
        matrix: 사전 로드된 매트릭스. ``None`` 이면 기본 매트릭스를 로드한다.
        min_evidence: 이 등급 이상만 반환 (``insufficient`` < ``weak`` < ``moderate`` < ``strong``).

    Returns:
        조건에 부합하는 ``ChronicDiseaseTarget`` 리스트. 카테고리가 없거나 매핑이
        비어 있으면 빈 리스트.

    Examples:
        >>> targets = category_to_conditions("오메가3", min_evidence="strong")
        >>> [t.condition for t in targets]
        ['cardiovascular', 'dyslipidemia']
    """
    data = matrix if matrix is not None else load_matrix()
    profile = data.categories.get(category)
    if profile is None:
        return []
    threshold = _EVIDENCE_RANK[min_evidence]
    return [
        target
        for target in profile.chronic_disease_targets
        if _EVIDENCE_RANK[target.evidence_level] >= threshold
    ]


def conditions_to_categories(
    condition: ChronicCondition,
    *,
    matrix: ChronicDiseaseSupplementMatrix | None = None,
    min_evidence: EvidenceLevel = "weak",
) -> list[str]:
    """단일 만성질환에 권장되는 카테고리명 리스트를 반환한다.

    Args:
        condition: 만성질환 인디케이션.
        matrix: 사전 로드된 매트릭스. ``None`` 이면 기본 매트릭스를 로드한다.
        min_evidence: 이 등급 이상만 포함.

    Returns:
        해당 condition 을 가진 카테고리명 리스트. 카테고리는 사전식으로 정렬된다.

    Examples:
        >>> categories = conditions_to_categories("dyslipidemia", min_evidence="strong")
        >>> sorted(categories)
        ['식이섬유', '오메가3', '혈관_낫토_폴리코사놀']
    """
    data = matrix if matrix is not None else load_matrix()
    threshold = _EVIDENCE_RANK[min_evidence]
    matched: list[str] = []
    for name, profile in data.categories.items():
        for target in profile.chronic_disease_targets:
            if target.condition != condition:
                continue
            if _EVIDENCE_RANK[target.evidence_level] >= threshold:
                matched.append(name)
                break
    return sorted(matched)


def persona_priority_categories(
    priority: str,
    *,
    matrix: ChronicDiseaseSupplementMatrix | None = None,
) -> list[str]:
    """페르소나 권장 등급으로 카테고리를 필터링한다.

    Args:
        priority: ``"prioritize_for_chronic"`` 등의 권장 등급.
        matrix: 사전 로드된 매트릭스. ``None`` 이면 기본 매트릭스를 로드한다.

    Returns:
        해당 권장 등급을 가진 카테고리명 리스트 (사전식 정렬).

    Examples:
        >>> sorted(persona_priority_categories("avoid_for_chronic"))
        ['카페인_각성', '크레아틴', '프리워크아웃']
    """
    data = matrix if matrix is not None else load_matrix()
    return sorted(
        name
        for name, profile in data.categories.items()
        if profile.persona_recommendation == priority
    )


def category_profile(
    category: str,
    *,
    matrix: ChronicDiseaseSupplementMatrix | None = None,
) -> CategoryProfile | None:
    """단일 카테고리의 전체 프로필을 반환한다.

    Args:
        category: 영양제 카테고리명.
        matrix: 사전 로드된 매트릭스. ``None`` 이면 기본 매트릭스를 로드한다.

    Returns:
        ``CategoryProfile`` 또는 카테고리가 없으면 ``None``.
    """
    data = matrix if matrix is not None else load_matrix()
    return data.categories.get(category)
