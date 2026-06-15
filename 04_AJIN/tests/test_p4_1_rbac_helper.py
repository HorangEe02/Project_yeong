"""P4.1 §8 — backend.dependencies.require_role_level 단위 테스트."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class _FakeUser:
    def __init__(self, level: int):
        self.role_level = level


class _RoleOnlyUser:
    def __init__(self, role: str):
        self.role = role


def test_passes_when_level_above():
    from backend.dependencies import require_role_level
    dep = require_role_level(3)
    user = _FakeUser(5)
    out = dep(user=user)
    assert out is user


def test_passes_when_level_equal():
    from backend.dependencies import require_role_level
    dep = require_role_level(3)
    user = _FakeUser(3)
    assert dep(user=user) is user


def test_rejects_when_level_below():
    from backend.dependencies import require_role_level
    dep = require_role_level(4)
    user = _FakeUser(2)
    with pytest.raises(HTTPException) as exc:
        dep(user=user)
    assert exc.value.status_code == 403
    assert "L4" in exc.value.detail


def test_falls_back_to_role_when_role_level_missing():
    from backend.dependencies import require_role_level
    dep = require_role_level(3)

    user = _RoleOnlyUser("TEAM_LEAD")
    assert dep(user=user) is user


def test_rejects_when_role_level_and_role_are_missing():
    from backend.dependencies import require_role_level
    dep = require_role_level(3)

    class _NoRole:
        pass

    with pytest.raises(HTTPException) as exc:
        dep(user=_NoRole())
    assert exc.value.status_code == 403


def test_factory_returns_distinct_deps():
    from backend.dependencies import require_role_level
    dep3 = require_role_level(3)
    dep5 = require_role_level(5)
    user = _FakeUser(4)
    # L3 통과
    assert dep3(user=user) is user
    # L5 거부
    with pytest.raises(HTTPException):
        dep5(user=user)
