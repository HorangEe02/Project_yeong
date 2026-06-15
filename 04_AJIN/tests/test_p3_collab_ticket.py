"""P3 D9 — 협업 티켓 단위 테스트."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    import features.compliance.change_detector as cd
    monkeypatch.setattr(cd, "CHANGE_DB_PATH", str(tmp_path / "ch.db"))
    cd.init_change_db()
    return cd


@pytest.fixture(autouse=True)
def _no_slack(monkeypatch):
    """Slack/외부 webhook 발송 안 되도록."""
    import config
    monkeypatch.setattr(config, "SLACK_WEBHOOK_URL", "")
    monkeypatch.delenv("JIRA_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("ASANA_WEBHOOK_URL", raising=False)


# ─────────────────────────────────────────────────────────────
# create_ticket
# ─────────────────────────────────────────────────────────────
class TestCreateTicket:
    def test_single_dept_does_not_create(self, tmp_db):
        from features.compliance.collab_ticket import create_ticket
        out = create_ticket(
            {"item_title": "단일 부서", "affected_departments": ["A팀"]},
            change_id=1,
        )
        assert out["ok"] is False
        assert "다중 부서" in out["error"]

    def test_multi_dept_creates_ticket(self, tmp_db):
        from features.compliance.collab_ticket import create_ticket
        out = create_ticket(
            {
                "item_title": "관세 25% — 다중 부서 영향",
                "affected_departments": ["구매팀", "해외지원팀", "영업팀"],
                "grade": "CRITICAL",
            },
            change_id=42,
        )
        assert out["ok"] is True
        assert out["ticket_id"] > 0
        assert out["departments"] == ["구매팀", "해외지원팀", "영업팀"]

    def test_empty_departments_fail(self, tmp_db):
        from features.compliance.collab_ticket import create_ticket
        out = create_ticket(
            {"item_title": "test", "affected_departments": []},
            change_id=1,
        )
        assert out["ok"] is False

    def test_string_departments_parsed(self, tmp_db):
        """affected_departments 가 JSON 문자열로 들어와도 처리."""
        from features.compliance.collab_ticket import create_ticket
        out = create_ticket(
            {
                "item_title": "test",
                "affected_departments": json.dumps(["A팀", "B팀"]),
            },
            change_id=1,
        )
        assert out["ok"] is True


# ─────────────────────────────────────────────────────────────
# list_tickets + update_ticket_status
# ─────────────────────────────────────────────────────────────
class TestListAndTransition:
    def test_list_filters_by_status(self, tmp_db):
        from features.compliance.collab_ticket import (
            create_ticket, list_tickets, update_ticket_status,
        )

        # 2 티켓 생성
        out1 = create_ticket(
            {"item_title": "T1", "affected_departments": ["A", "B"]},
            change_id=1,
        )
        out2 = create_ticket(
            {"item_title": "T2", "affected_departments": ["C", "D"]},
            change_id=2,
        )

        # T1 만 resolved
        update_ticket_status(out1["ticket_id"], "resolved")

        all_lst = list_tickets()
        assert len(all_lst) == 2

        resolved = list_tickets(status="resolved")
        assert len(resolved) == 1
        assert resolved[0]["id"] == out1["ticket_id"]

        created = list_tickets(status="created")
        assert len(created) == 1
        assert created[0]["id"] == out2["ticket_id"]

    def test_list_filters_by_department(self, tmp_db):
        from features.compliance.collab_ticket import create_ticket, list_tickets
        create_ticket({"item_title": "T1", "affected_departments": ["안전보건팀", "법무팀"]}, change_id=1)
        create_ticket({"item_title": "T2", "affected_departments": ["구매팀", "해외지원팀"]}, change_id=2)

        legal = list_tickets(department="법무팀")
        assert len(legal) == 1

    def test_invalid_status_rejected(self, tmp_db):
        from features.compliance.collab_ticket import create_ticket, update_ticket_status
        out = create_ticket({"item_title": "t", "affected_departments": ["a", "b"]}, change_id=1)
        assert update_ticket_status(out["ticket_id"], "invalid_status") is False

    def test_resolved_sets_resolved_at(self, tmp_db):
        from features.compliance.collab_ticket import (
            create_ticket, list_tickets, update_ticket_status,
        )
        out = create_ticket({"item_title": "t", "affected_departments": ["a", "b"]}, change_id=1)
        update_ticket_status(out["ticket_id"], "resolved")

        ts = list_tickets()
        assert ts[0]["resolved_at"]  # not empty
        # acknowledged 후엔 resolved_at 비어있음
        out2 = create_ticket({"item_title": "t2", "affected_departments": ["a", "b"]}, change_id=2)
        update_ticket_status(out2["ticket_id"], "acknowledged")
        ts2 = list_tickets(status="acknowledged")
        assert ts2[0]["resolved_at"] == ""


# ─────────────────────────────────────────────────────────────
# find_dept_owners — graceful when employees.db absent or missing data
# ─────────────────────────────────────────────────────────────
class TestFindDeptOwners:
    def test_returns_dict(self, tmp_db):
        from features.compliance.collab_ticket import find_dept_owners
        out = find_dept_owners(["존재하지 않는팀"])
        assert isinstance(out, dict)
