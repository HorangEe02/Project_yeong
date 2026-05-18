"""``LLMAdapter`` / ``VisionAdapter`` ABC 계약 검증 — D1 수리 결과 포함.

검증 항목:
    - 추상 클래스는 직접 인스턴스화 불가 (``TypeError``).
    - ``VisionAdapter.detect_regions`` 의 반환이 ``list[LabeledBoundingBox]`` (D1).
    - ``LabeledBoundingBox`` 가 ``@dataclass(frozen=True)`` 로 불변.

Reference:
    /Users/yeong/.claude/plans/ocr-yolo-sprightly-neumann.md §3.1 D1
    /Users/yeong/.claude/plans/lemon-track-b/phase-00-bootstrap.md Step 6
"""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError

import pytest
from src.llm.base import LLMAdapter
from src.vision.base import LabeledBoundingBox, VisionAdapter


def test_llm_adapter_is_abstract() -> None:
    """``LLMAdapter`` 는 직접 인스턴스화할 수 없다."""
    with pytest.raises(TypeError):
        LLMAdapter()  # type: ignore[abstract]


def test_vision_adapter_is_abstract() -> None:
    """``VisionAdapter`` 는 직접 인스턴스화할 수 없다."""
    with pytest.raises(TypeError):
        VisionAdapter()  # type: ignore[abstract]


def test_vision_adapter_detect_regions_returns_list_of_labeled() -> None:
    """D1 수리: ``detect_regions`` 의 반환 시그니처가 ``list[LabeledBoundingBox]``."""
    sig = inspect.signature(VisionAdapter.detect_regions)
    ret_str = str(sig.return_annotation)
    assert "list" in ret_str
    assert "LabeledBoundingBox" in ret_str


def test_vision_adapter_has_no_detect_label_region_method() -> None:
    """D1 수리: 기존 단수 ``detect_label_region`` 메서드는 제거되었다."""
    assert not hasattr(VisionAdapter, "detect_label_region")


def test_labeled_bounding_box_is_frozen() -> None:
    """``LabeledBoundingBox`` 는 frozen — 속성 할당 차단."""
    box = LabeledBoundingBox(
        x=0,
        y=0,
        width=10,
        height=10,
        confidence=0.9,
        kind="brand",
    )
    with pytest.raises(FrozenInstanceError):
        box.x = 1  # type: ignore[misc]


def test_labeled_bounding_box_accepts_all_literal_kinds() -> None:
    """``kind`` 는 6개 Literal 값 모두에 대해 인스턴스화 가능해야 한다."""
    for kind in (
        "brand",
        "ingredients_table",
        "dosage",
        "warning",
        "expiry",
        "other",
    ):
        box = LabeledBoundingBox(
            x=0,
            y=0,
            width=1,
            height=1,
            confidence=0.5,
            kind=kind,
        )
        assert box.kind == kind
