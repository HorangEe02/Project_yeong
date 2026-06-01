"""v3.3 Phase D — Quick Questions 시스템 정책 테스트.

검증 대상:
1. _load_all() — 데이터 풀 로드 (35 파일 / 199 질문)
2. get_quick_questions() — 직급 × 부서 매트릭스
3. 6 슬롯 한도 + ID 중복 제거 + 직급 범위 필터링
4. fallback 동작 (DEPARTMENT_PROFILES 등록 부서 + 데이터 풀 부재)
5. 박부장형 안전망 (악성 데이터 주입 시 차단)
6. 라우터 — Cache-Control 헤더 + RBAC 부서 강제 (Phase B 재사용)
7. _has_personal_name() 정규식 정확성
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from features.onboarding.quick_questions import (
    TARGET_SLOT_COUNT,
    _generate_fallback_questions,
    _has_personal_name,
    _load_all,
    get_quick_questions,
    invalidate_cache,
)


# ──────────────────────────────────────────────
# 1. _load_all() — 데이터 풀 로드
# ──────────────────────────────────────────────


def test_load_all_returns_expected_keys():
    invalidate_cache()
    data = _load_all()
    assert set(data.keys()) == {"common", "by_level", "by_dept"}


def test_load_all_common_has_3_questions():
    invalidate_cache()
    assert len(_load_all()["common"]) == 3


def test_load_all_levels_1_to_5():
    invalidate_cache()
    levels = _load_all()["by_level"]
    assert set(levels.keys()) == {1, 2, 3, 4, 5}
    for lvl in range(1, 6):
        assert isinstance(levels[lvl], list)
        assert len(levels[lvl]) >= 1, f"L{lvl} 데이터 없음"


def test_load_all_levels_4_5_share_data():
    """L4_5.json 단일 파일 → L4 / L5 동일 데이터 참조."""
    invalidate_cache()
    levels = _load_all()["by_level"]
    assert levels[4] == levels[5]


def test_load_all_30_departments():
    invalidate_cache()
    depts = _load_all()["by_dept"]
    assert len(depts) == 30, f"30 부서 데이터 풀 — 실제 {len(depts)}"


# ──────────────────────────────────────────────
# 2. get_quick_questions() — 6 슬롯 + 매트릭스
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "department,role_level",
    [
        # 5 본부 × 3 직급 = 15 매트릭스 (대표 부서)
        ("품질보증팀", 1),  # 생산본부 + 신입
        ("품질보증팀", 3),
        ("품질보증팀", 5),
        ("비전연구팀", 1),  # 생산기술본부
        ("비전연구팀", 3),
        ("비전연구팀", 5),
        ("기술영업팀", 1),  # 개발본부
        ("기술영업팀", 3),
        ("기술영업팀", 5),
        ("재무팀", 1),  # 재경본부
        ("재무팀", 3),
        ("재무팀", 5),
        ("내부감사팀", 1),  # 독립
        ("내부감사팀", 3),
        ("내부감사팀", 5),
    ],
)
def test_get_quick_questions_matrix_returns_6(department: str, role_level: int):
    """30/30 데이터 풀 완비 — 모든 부서 × 직급에서 6 슬롯 채워야 한다."""
    invalidate_cache()
    result = get_quick_questions(department, role_level)
    assert len(result) == TARGET_SLOT_COUNT, (
        f"{department} × L{role_level} → {len(result)}개 (목표 {TARGET_SLOT_COUNT})"
    )


def test_get_quick_questions_returns_dict_items():
    """반환 항목은 dict — 필수 필드 존재 확인."""
    invalidate_cache()
    result = get_quick_questions("품질보증팀", 1)
    for q in result:
        for field in ("id", "label", "promptText", "category"):
            assert field in q, f"필수 필드 누락: {field}"


def test_get_quick_questions_unique_ids():
    """6 슬롯 안에서 ID 중복 0건."""
    invalidate_cache()
    result = get_quick_questions("비전연구팀", 3)
    ids = [q["id"] for q in result]
    assert len(ids) == len(set(ids))


def test_get_quick_questions_unknown_dept_falls_back_to_common_level():
    """미등록 부서 + DEPARTMENT_PROFILES 미등록 → 공통(3) + 직급(2) = 5개."""
    invalidate_cache()
    result = get_quick_questions("미등록XYZ팀", 1)
    # 공통 3 + L1 2 = 5 (부서 0)
    assert len(result) == 5


def test_get_quick_questions_clamps_role_level_below_1():
    """role_level=0 (비인증) → L1 으로 클램프."""
    invalidate_cache()
    r0 = get_quick_questions("품질보증팀", 0)
    r1 = get_quick_questions("품질보증팀", 1)
    # 동일 결과 (clamp)
    assert [q["id"] for q in r0] == [q["id"] for q in r1]


def test_get_quick_questions_clamps_role_level_above_5():
    """role_level=99 → L5 로 클램프."""
    invalidate_cache()
    r99 = get_quick_questions("품질보증팀", 99)
    r5 = get_quick_questions("품질보증팀", 5)
    assert [q["id"] for q in r99] == [q["id"] for q in r5]


def test_get_quick_questions_respects_min_max_level():
    """min_level/max_level 범위 외 질문은 노출되지 않아야 한다."""
    invalidate_cache()
    # L1 사용자에게 lv45-* (L4/L5 전용) 질문이 노출되면 안 됨
    result = get_quick_questions("품질보증팀", 1)
    forbidden_ids = {q["id"] for q in result if q["id"].startswith("lv45-")}
    assert not forbidden_ids


def test_get_quick_questions_l1_includes_l1_specific():
    """L1 사용자에게는 lv1-* 질문이 포함되어야 한다."""
    invalidate_cache()
    result = get_quick_questions("품질보증팀", 1)
    l1_ids = [q["id"] for q in result if q["id"].startswith("lv1-")]
    assert l1_ids


def test_get_quick_questions_l5_includes_l45():
    """L5 사용자에게는 lv45-* (L4_5.json) 질문이 포함되어야 한다."""
    invalidate_cache()
    result = get_quick_questions("품질보증팀", 5)
    l45_ids = [q["id"] for q in result if q["id"].startswith("lv45-")]
    assert l45_ids


# ──────────────────────────────────────────────
# 3. fallback (_generate_fallback_questions)
# ──────────────────────────────────────────────


def test_fallback_generates_from_core_responsibilities():
    """DEPARTMENT_PROFILES 등록 부서면 4개 fallback 생성."""
    fb = _generate_fallback_questions("품질보증팀", take=4)
    assert len(fb) == 4
    for q in fb:
        assert q["id"].startswith("auto-품질보증팀-")
        assert "fallback" in q.get("tags", [])
        assert q["category"] == "general"


def test_fallback_unknown_dept_returns_empty():
    """DEPARTMENT_PROFILES 에 없는 부서 → 빈 리스트."""
    assert _generate_fallback_questions("미등록XYZ팀", take=4) == []


def test_fallback_take_zero():
    """take=0 → 빈 리스트."""
    assert _generate_fallback_questions("품질보증팀", take=0) == []


def test_fallback_integrated_when_dept_data_missing():
    """데이터 풀에 부서 JSON 이 없을 때 fallback 이 슬롯을 채운다."""
    invalidate_cache()
    # 정상 데이터 로드 후 by_dept 에서 한 부서를 의도적으로 제거
    real_data = _load_all()
    fake_data = {
        "common": real_data["common"],
        "by_level": real_data["by_level"],
        "by_dept": {k: v for k, v in real_data["by_dept"].items() if k != "품질보증팀"},
    }
    with patch(
        "features.onboarding.quick_questions._load_all", return_value=fake_data
    ):
        result = get_quick_questions("품질보증팀", 1)
        # 6 슬롯 모두 채워져야 함 (공통3 + L1 2 + fallback 4 → 트림 6)
        assert len(result) == TARGET_SLOT_COUNT
        # fallback 항목이 일부 포함
        auto_ids = [q for q in result if q["id"].startswith("auto-품질보증팀-")]
        assert auto_ids, "fallback 미동작"


# ──────────────────────────────────────────────
# 4. 박부장형 안전망 (_has_personal_name)
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,is_personal",
    [
        ("김민수 부장 어디?", True),
        ("박성훈 차장 연락처", True),
        ("이지영 과장님", True),
        ("최영수전무", True),
        ("홍길동 이사", True),
        # 일반 명사 — false
        ("신입사원 온보딩", False),
        ("정규대리 평가", False),
        ("PPAP 양식 어디?", False),
        ("프레스 트라이 SOP", False),
        ("우리 팀 KPI", False),
        ("", False),
    ],
)
def test_has_personal_name(text: str, is_personal: bool):
    assert _has_personal_name(text) is is_personal


def test_get_quick_questions_filters_injected_personal_name():
    """악성 데이터 주입 시 박부장형 안전망 동작."""
    invalidate_cache()
    real_data = _load_all()
    poisoned = real_data["by_dept"]["품질보증팀"] + [
        {
            "id": "qa-evil-personal",
            "label": "박부장 검색",
            "promptText": "박부장 어디?",
            "category": "action",
            "min_level": 1,
            "max_level": 5,
        }
    ]
    fake_data = {
        "common": real_data["common"],
        "by_level": real_data["by_level"],
        "by_dept": {**real_data["by_dept"], "품질보증팀": poisoned},
    }
    with patch(
        "features.onboarding.quick_questions._load_all", return_value=fake_data
    ):
        result = get_quick_questions("품질보증팀", 1)
        evil_ids = [q for q in result if q["id"] == "qa-evil-personal"]
        assert not evil_ids, "박부장형 안전망 미동작"


# ──────────────────────────────────────────────
# 5. invalidate_cache()
# ──────────────────────────────────────────────


def test_invalidate_cache_clears_lru():
    invalidate_cache()
    _ = _load_all()
    info_before = _load_all.cache_info()
    assert info_before.hits >= 1 or info_before.currsize == 1
    invalidate_cache()
    info_after = _load_all.cache_info()
    assert info_after.currsize == 0


# ──────────────────────────────────────────────
# 6. 라우터 통합 — TestClient
# ──────────────────────────────────────────────


@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.routers.onboarding import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_endpoint_returns_200(client):
    r = client.get("/onboarding/quick-questions?department=품질보증팀")
    assert r.status_code == 200


def test_endpoint_response_schema(client):
    r = client.get("/onboarding/quick-questions?department=비전연구팀")
    body = r.json()
    assert set(body.keys()) >= {"items", "department", "role_level", "total"}
    assert isinstance(body["items"], list)
    assert body["total"] == len(body["items"])


def test_endpoint_cache_control_header(client):
    r = client.get("/onboarding/quick-questions?department=품질보증팀")
    cc = r.headers.get("cache-control", "")
    assert "private" in cc
    assert "max-age=300" in cc


def test_endpoint_anon_default_dept(client):
    r = client.get("/onboarding/quick-questions")
    body = r.json()
    # 비인증 → 비인증의 fallback 동작 (Phase B `_resolve_effective_department`)
    assert body["department"]
    assert body["role_level"] >= 1
    assert body["total"] >= 5  # 공통3 + L1 2 = 최소 5 (부서 0이어도)


def test_endpoint_anon_unknown_dept_graceful(client):
    r = client.get("/onboarding/quick-questions?department=미등록XYZ팀")
    body = r.json()
    assert r.status_code == 200
    assert body["total"] >= 5  # 공통+직급만으로 최소 5
    # fallback 도 빈 리스트 — DEPARTMENT_PROFILES 에 미등록


def test_endpoint_total_matches_items_length(client):
    """total 필드가 실제 items 길이와 일치해야 한다."""
    for dept in ("품질보증팀", "비전연구팀", "재무팀", "내부감사팀"):
        r = client.get(f"/onboarding/quick-questions?department={dept}")
        body = r.json()
        assert body["total"] == len(body["items"]), f"{dept} total ≠ len(items)"


# ──────────────────────────────────────────────
# 7. 6 슬롯 한도
# ──────────────────────────────────────────────


def test_target_slot_count_constant():
    assert TARGET_SLOT_COUNT == 6


def test_get_quick_questions_never_exceeds_target():
    """모든 부서 × 직급 조합에서 6 슬롯 초과 0건."""
    from features.onboarding.department_router import DEPARTMENT_PROFILES

    invalidate_cache()
    for dept in DEPARTMENT_PROFILES.keys():
        for lvl in range(1, 6):
            result = get_quick_questions(dept, lvl)
            assert len(result) <= TARGET_SLOT_COUNT, (
                f"{dept} × L{lvl} → {len(result)}개 (한도 {TARGET_SLOT_COUNT})"
            )
