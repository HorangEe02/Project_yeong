"""v3.3 Phase 0 — Feature C 피처 플래그 테스트.

검증 대상:
1. 8 플래그가 모두 정의되어 있고 dict() 변환 OK
2. 기본값은 모두 False (안전한 점진 활성화)
3. 환경변수 truthy 파싱 (true / 1 / yes / on / True)
4. 부분 활성화 — 일부 플래그만 켜져도 다른 플래그는 영향 없음
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

from core.feature_flags import (
    FeatureCFlags,
    feature_c_flags_dict,
    load_feature_c_flags,
)


# ──────────────────────────────────────────────
# 1. 플래그 8종 모두 정의
# ──────────────────────────────────────────────


EXPECTED_FLAGS = [
    "multi_llm",
    "compare_mode",
    "dept_lock",
    "division_boundary",
    "work_fullscreen",
    "quick_questions_v2",
    "inline_actions",
    "cad_upload",
]


def test_feature_c_flags_has_all_eight():
    """FeatureCFlags dataclass 에 8 필드 모두 존재."""
    flags = FeatureCFlags(
        multi_llm=False,
        compare_mode=False,
        dept_lock=False,
        division_boundary=False,
        work_fullscreen=False,
        quick_questions_v2=False,
        inline_actions=False,
        cad_upload=False,
    )
    for name in EXPECTED_FLAGS:
        assert hasattr(flags, name), f"missing flag: {name}"


def test_feature_c_flags_dict_keys():
    """dict 변환 결과 키 완전성."""
    with patch.dict(os.environ, {}, clear=False):
        for k in [f"FEATURE_C_{n.upper()}" for n in EXPECTED_FLAGS]:
            os.environ.pop(k, None)
        d = feature_c_flags_dict()
    assert sorted(d.keys()) == sorted(EXPECTED_FLAGS)
    assert all(v is False for v in d.values())


# ──────────────────────────────────────────────
# 2. 환경변수 truthy 파싱
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("YES", True),
        ("on", True),
        ("ON", True),
        ("false", False),
        ("False", False),
        ("0", False),
        ("no", False),
        ("off", False),
        ("", False),
        ("anything", False),
    ],
)
def test_truthy_env_parsing(value: str, expected: bool):
    with patch.dict(os.environ, {"FEATURE_C_MULTI_LLM": value}, clear=False):
        flags = load_feature_c_flags()
        assert flags.multi_llm is expected


# ──────────────────────────────────────────────
# 3. 부분 활성화 — 격리성
# ──────────────────────────────────────────────


def test_partial_activation_isolation():
    """일부 플래그만 켜져도 다른 플래그는 기본값(False) 유지."""
    with patch.dict(
        os.environ,
        {
            "FEATURE_C_MULTI_LLM": "true",
            "FEATURE_C_DEPT_LOCK": "1",
            "FEATURE_C_CAD_UPLOAD": "on",
        },
        clear=False,
    ):
        # 다른 플래그는 명시적으로 unset
        for k in (
            "FEATURE_C_COMPARE_MODE",
            "FEATURE_C_DIVISION_BOUNDARY",
            "FEATURE_C_WORK_FULLSCREEN",
            "FEATURE_C_QUICK_QUESTIONS_V2",
            "FEATURE_C_INLINE_ACTIONS",
        ):
            os.environ.pop(k, None)
        flags = load_feature_c_flags()

    # 켜진 것
    assert flags.multi_llm is True
    assert flags.dept_lock is True
    assert flags.cad_upload is True
    # 꺼진 것
    assert flags.compare_mode is False
    assert flags.division_boundary is False
    assert flags.work_fullscreen is False
    assert flags.quick_questions_v2 is False
    assert flags.inline_actions is False


def test_default_all_false():
    """env 완전 비어 있을 때 모두 False."""
    with patch.dict(os.environ, {}, clear=False):
        for n in EXPECTED_FLAGS:
            os.environ.pop(f"FEATURE_C_{n.upper()}", None)
        flags = load_feature_c_flags()

    for n in EXPECTED_FLAGS:
        assert getattr(flags, n) is False


# ──────────────────────────────────────────────
# 4. dataclass 불변성 (frozen=True)
# ──────────────────────────────────────────────


def test_feature_c_flags_frozen():
    """FeatureCFlags 는 frozen — 재할당 시 FrozenInstanceError."""
    from dataclasses import FrozenInstanceError

    flags = load_feature_c_flags()
    with pytest.raises(FrozenInstanceError):
        flags.multi_llm = True  # type: ignore[misc]
