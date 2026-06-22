"""다운샘플 매니페스트 검증 모델.

balanced_500 train 서브셋의 클래스별 선택 stem 목록을 직렬화/검증한다.
repo 도구가 별도 Python 의존성 없이 실행되도록 표준 라이브러리만 사용한다.

Reference:
    docs/superpowers/specs/2026-05-27-aihub-yolo-balanced500-yolo11s-design.md §3.3
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ClassManifest:
    """한 클래스의 다운샘플 선택 결과.

    Args:
        class_id: YOLO class id. 이 스크립트는 50클래스 데이터셋을 대상으로 하므로
            0 이상 49 이하만 허용한다.
        class_name: 클래스 이름.
        stems: 선택된 파일 stem 목록. 입력 순서와 무관하게 정렬해 저장한다.

    Raises:
        ValueError: class_id 범위가 틀리거나 class_name이 비어 있을 때.
    """

    class_id: int
    class_name: str
    stems: list[str]

    def __post_init__(self) -> None:
        """입력값을 검증하고 stems 순서를 정규화한다."""
        if not 0 <= self.class_id <= 49:
            raise ValueError("class_id must be in [0, 49]")
        if not self.class_name:
            raise ValueError("class_name must not be empty")
        object.__setattr__(self, "stems", sorted(self.stems))

    def model_dump(self) -> dict[str, Any]:
        """JSON 직렬화 가능한 dict로 변환한다.

        Returns:
            class_id, class_name, stems를 담은 dict.
        """
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "stems": self.stems,
        }


@dataclass(frozen=True)
class TrainManifest:
    """전체 train 또는 val 서브셋 매니페스트.

    Args:
        seed: 다운샘플에 사용한 random seed.
        cap_per_class: 클래스당 상한.
        classes: 클래스별 선택 결과.

    Raises:
        ValueError: cap_per_class가 0 이하이거나 class_id가 중복될 때.
    """

    seed: int
    cap_per_class: int
    classes: list[ClassManifest]

    def __post_init__(self) -> None:
        """입력값을 검증한다."""
        if self.cap_per_class <= 0:
            raise ValueError("cap_per_class must be positive")
        if not self.classes:
            raise ValueError("classes must not be empty")
        ids = [entry.class_id for entry in self.classes]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate class_id in TrainManifest.classes")

    def model_dump(self) -> dict[str, Any]:
        """JSON 직렬화 가능한 dict로 변환한다.

        Returns:
            seed, cap_per_class, classes를 담은 dict.
        """
        return {
            "seed": self.seed,
            "cap_per_class": self.cap_per_class,
            "classes": [entry.model_dump() for entry in self.classes],
        }

    def model_dump_json(self, *, indent: int | None = None) -> str:
        """기존 pydantic 호출부와 호환되는 JSON 문자열을 반환한다.

        Args:
            indent: JSON 들여쓰기 크기.

        Returns:
            UTF-8 텍스트로 저장 가능한 JSON 문자열.
        """
        return json.dumps(self.model_dump(), ensure_ascii=False, indent=indent)
