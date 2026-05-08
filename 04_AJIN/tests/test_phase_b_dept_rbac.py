"""v3.3 Phase B — 부서 컨텍스트 RBAC + 본부 경계 테스트.

검증 대상:
1. _get_division() 부서 → 본부 매핑 (DEPARTMENT_PROFILES 정합)
2. _resolve_effective_department() 권한 매트릭스
   - 비인증 / L1 / L2 / L3 (같은 본부) / L3 (타 본부) / L4 / L5
3. 경고 로그 발생 케이스 (caplog 활용)
4. 빈 req.department / 미등록 부서 / 자기 부서 일치 등 edge case
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.routers.onboarding import (
    _DEFAULT_DEPT,
    _MANAGER_LEVEL,
    _EXECUTIVE_LEVEL,
    _get_division,
    _resolve_effective_department,
)


# ──────────────────────────────────────────────
# 1. _get_division() — DEPARTMENT_PROFILES 정합
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "dept,expected_div",
    [
        # 생산본부 (5팀)
        ("품질보증팀", "생산본부"),
        ("안전보건팀", "생산본부"),
        ("생산관리팀", "생산본부"),
        ("자재관리팀", "생산본부"),
        # 생산기술본부 (8팀)
        ("생산기술팀", "생산기술본부"),
        ("자동화기술팀", "생산기술본부"),
        ("비전연구팀", "생산기술본부"),
        # 개발본부 (3팀)
        ("부품개발팀", "개발본부"),
        ("금형생산팀", "개발본부"),
        # 기술연구소 (2팀)
        ("바디선행개발팀", "기술연구소"),
        ("전장선행개발팀", "기술연구소"),
        # 관리본부 (4팀)
        ("총무인사팀", "관리본부"),
        ("ESG경영팀", "관리본부"),
        # 재경본부 (4팀)
        ("재무팀", "재경본부"),
        ("IT전략팀", "재경본부"),
        # 구매본부 (3팀)
        ("구매팀", "구매본부"),
        ("해외지원팀", "구매본부"),
        # 독립
        ("내부감사팀", "(독립)"),
    ],
)
def test_get_division_mapping(dept: str, expected_div: str):
    assert _get_division(dept) == expected_div


def test_get_division_unknown_returns_none():
    assert _get_division("미등록팀") is None
    assert _get_division("") is None


# ──────────────────────────────────────────────
# 2. _resolve_effective_department() — 권한 매트릭스
# ──────────────────────────────────────────────


def _make_user(level: int, dept: str, username: str = "test"):
    return SimpleNamespace(role_level=level, department=dept, username=username)


# 2-1. 비인증
def test_anon_uses_req_dept_or_default():
    assert _resolve_effective_department("영업팀", None) == "영업팀"
    assert _resolve_effective_department("", None) == _DEFAULT_DEPT
    assert _resolve_effective_department(None, None) == _DEFAULT_DEPT
    assert _resolve_effective_department("   ", None) == _DEFAULT_DEPT


# 2-2. L1 / L2 (EMPLOYEE) — 자기 부서 강제
@pytest.mark.parametrize("level", [1, 2])
def test_employee_dept_forced(level: int):
    u = _make_user(level, "비전연구팀")
    # 자기 부서 일치 → 그대로
    assert _resolve_effective_department("비전연구팀", u) == "비전연구팀"
    # 다른 부서 시도 → 자기 부서 강제
    assert _resolve_effective_department("영업팀", u) == "비전연구팀"
    # 빈 값 → 자기 부서
    assert _resolve_effective_department("", u) == "비전연구팀"


def test_employee_other_dept_logs_warning(caplog):
    u = _make_user(1, "비전연구팀", username="lee_l1")
    with caplog.at_level(logging.WARNING):
        _resolve_effective_department("재무팀", u)
    assert any(
        "부서 변경 시도 차단" in r.message and "lee_l1" in r.message
        for r in caplog.records
    )


def test_employee_same_dept_no_warning(caplog):
    """자기 부서 입력은 경고 없이 통과해야 한다."""
    u = _make_user(1, "비전연구팀", username="lee_l1")
    with caplog.at_level(logging.WARNING):
        _resolve_effective_department("비전연구팀", u)
    assert not any("차단" in r.message for r in caplog.records)


# 2-3. L3 (MANAGER) — 같은 본부만
def test_manager_same_division_allowed():
    u = _make_user(3, "품질보증팀")  # 생산본부
    # 같은 본부 (생산본부의 다른 팀) → 허용
    assert _resolve_effective_department("영업팀", u) == "영업팀"
    assert _resolve_effective_department("자재관리팀", u) == "자재관리팀"


def test_manager_other_division_blocked():
    u = _make_user(3, "품질보증팀")  # 생산본부
    # 타 본부 (재경본부) → 차단 + 자기 부서 fallback
    assert _resolve_effective_department("재무팀", u) == "품질보증팀"
    # 타 본부 (관리본부) → 차단
    assert _resolve_effective_department("총무인사팀", u) == "품질보증팀"


def test_manager_other_division_logs_warning(caplog):
    u = _make_user(3, "품질보증팀", username="kim_l3")
    with caplog.at_level(logging.WARNING):
        _resolve_effective_department("재무팀", u)
    assert any(
        "본부 경계 위반 차단" in r.message and "kim_l3" in r.message
        for r in caplog.records
    )


def test_manager_empty_returns_own_dept():
    u = _make_user(3, "품질보증팀")
    assert _resolve_effective_department("", u) == "품질보증팀"
    assert _resolve_effective_department(None, u) == "품질보증팀"


def test_manager_unknown_dept_blocked():
    """미등록 부서명은 본부 매핑 실패 → 차단."""
    u = _make_user(3, "품질보증팀")
    assert _resolve_effective_department("미등록팀", u) == "품질보증팀"


# 2-4. L4 (EXECUTIVE) — 전사 자유
def test_executive_full_access():
    u = _make_user(4, "품질보증팀")  # 생산본부
    # 전사 자유 — 타 본부 OK
    assert _resolve_effective_department("재무팀", u) == "재무팀"
    assert _resolve_effective_department("내부감사팀", u) == "내부감사팀"
    assert _resolve_effective_department("총무인사팀", u) == "총무인사팀"


# 2-5. L5 (SYS / HR_ADMIN) — 전사 자유
def test_sys_admin_full_access():
    u = _make_user(5, "IT전략팀")
    assert _resolve_effective_department("내부감사팀", u) == "내부감사팀"
    assert _resolve_effective_department("ESG경영팀", u) == "ESG경영팀"


def test_executive_no_warning_log(caplog):
    """L>=4 는 어떤 부서를 입력해도 경고 로그가 없어야 한다."""
    u = _make_user(5, "IT전략팀", username="sys_admin")
    with caplog.at_level(logging.WARNING):
        _resolve_effective_department("재무팀", u)
        _resolve_effective_department("총무인사팀", u)
        _resolve_effective_department("내부감사팀", u)
    rec = [r for r in caplog.records if "차단" in r.message or "위반" in r.message]
    assert not rec


# ──────────────────────────────────────────────
# 3. Edge cases — whitespace, None, missing attrs
# ──────────────────────────────────────────────


def test_resolve_strips_whitespace():
    u = _make_user(3, "품질보증팀")
    assert _resolve_effective_department("  영업팀  ", u) == "영업팀"


def test_resolve_user_without_department():
    """user.department 가 None 인 비정상 사용자도 안전하게 처리."""
    u = SimpleNamespace(role_level=1, department=None, username="x")
    assert _resolve_effective_department("재무팀", u) == _DEFAULT_DEPT


def test_resolve_user_without_role_level():
    """role_level 미설정은 0 으로 취급 (가장 보수적)."""
    u = SimpleNamespace(role_level=None, department="비전연구팀", username="x")
    # L0 (None → 0) → L<3 분기 → 자기 부서 강제
    assert _resolve_effective_department("재무팀", u) == "비전연구팀"


# ──────────────────────────────────────────────
# 4. 임계값 상수 일관성
# ──────────────────────────────────────────────


def test_constants_consistency():
    """rbac.ts 와 정합: MANAGER=3, EXECUTIVE=4."""
    assert _MANAGER_LEVEL == 3
    assert _EXECUTIVE_LEVEL == 4
    assert _MANAGER_LEVEL < _EXECUTIVE_LEVEL
    assert _DEFAULT_DEPT == "품질보증팀"
