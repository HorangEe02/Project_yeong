"""P3 D13 — 확장 트렌드 KPI 단위 테스트."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    import features.compliance.change_detector as cd
    monkeypatch.setattr(cd, "CHANGE_DB_PATH", str(tmp_path / "ch.db"))
    cd.init_change_db()
    return cd


class TestExtendedTrend:
    def test_empty_returns_zeros(self, tmp_db):
        from features.compliance.change_detector import get_extended_trend
        out = get_extended_trend(window_days=180)
        assert out["total"] == 0
        assert out["window_days"] == 180
        assert out["monthly_grade_trend"] == []
        assert out["by_dept_handling_hours"] == []
        assert out["by_legal_class"] == {}

    def test_aggregates_legal_class_distribution(self, tmp_db):
        from features.compliance.change_detector import get_extended_trend, save_changes

        save_changes([
            {
                "regulation_type": "t", "change_type": "added",
                "item_id": "X-1", "item_title": "산안법", "old_value": "", "new_value": "",
                "severity": "info", "grade": "HIGH",
                "affected_departments": [], "affected_plants": [],
                "legal_class": ["criminal", "administrative"],
            },
            {
                "regulation_type": "t", "change_type": "added",
                "item_id": "X-2", "item_title": "REACH", "old_value": "", "new_value": "",
                "severity": "info", "grade": "MEDIUM",
                "affected_departments": [], "affected_plants": [],
                "legal_class": ["administrative"],
            },
        ])

        out = get_extended_trend(window_days=30)
        assert out["total"] == 2
        # criminal=1, administrative=2
        assert out["by_legal_class"]["criminal"] == 1
        assert out["by_legal_class"]["administrative"] == 2

    def test_dept_handling_hours_only_done_status(self, tmp_db):
        """status='done' 인 변경의 affected_departments 만 평균 시간 산출."""
        from features.compliance.change_detector import (
            get_extended_trend, save_changes, update_change_status,
        )

        ids = save_changes([
            {
                "regulation_type": "t", "change_type": "added",
                "item_id": "X-1", "item_title": "법규",
                "old_value": "", "new_value": "",
                "severity": "info", "grade": "HIGH",
                "affected_departments": ["A팀"], "affected_plants": [],
                "legal_class": [],
            },
            {
                "regulation_type": "t", "change_type": "added",
                "item_id": "X-2", "item_title": "법규2",
                "old_value": "", "new_value": "",
                "severity": "info", "grade": "MEDIUM",
                "affected_departments": ["B팀"], "affected_plants": [],
                "legal_class": [],
            },
        ])
        # X-1 만 done 처리
        update_change_status(ids[0], "reviewing", "u1")
        update_change_status(ids[0], "done", "u1")

        out = get_extended_trend(window_days=30)
        depts = {d["department"]: d["count"] for d in out["by_dept_handling_hours"]}
        # A팀 만 등장 (B팀 은 done 안 됨)
        assert "A팀" in depts
        assert "B팀" not in depts

    def test_filtered_changes_excluded(self, tmp_db):
        """status='filtered' (자동 archive) 는 trend 에 포함 안 됨."""
        from features.compliance.change_detector import get_extended_trend, save_changes

        save_changes([
            {
                "regulation_type": "t", "change_type": "modified",
                "item_id": "X-1", "item_title": "노이즈",
                "old_value": "", "new_value": "",
                "severity": "info", "grade": "LOW",
                "affected_departments": [], "affected_plants": [],
                "legal_class": [], "status": "filtered",
            },
            {
                "regulation_type": "t", "change_type": "added",
                "item_id": "X-2", "item_title": "실질",
                "old_value": "", "new_value": "",
                "severity": "info", "grade": "HIGH",
                "affected_departments": [], "affected_plants": [],
                "legal_class": [],
            },
        ])

        out = get_extended_trend(window_days=30)
        assert out["total"] == 1  # filtered 1건 제외
