"""P5 §7 — 자체 결재 워크플로 단위 테스트."""
from __future__ import annotations

import sqlite3
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


@pytest.fixture(autouse=True)
def _no_external(monkeypatch):
    """Slack 발송 차단."""
    import config
    monkeypatch.setattr(config, "SLACK_WEBHOOK_URL", "", raising=False)


# ─────────────────────────────────────────────────────────────
# start_chain
# ─────────────────────────────────────────────────────────────


class TestStartChain:
    def test_creates_chain_with_steps(self, tmp_db):
        from features.compliance.approval_workflow import start_chain, get_chain_detail
        cid = start_chain(
            change_id=42, name="규제 변경 결재", requested_by="REQ1",
            steps=[
                {"approver_id": "EMP_A", "role_label": "차장"},
                {"approver_id": "EMP_B", "role_label": "팀장"},
                {"approver_id": "EMP_C", "role_label": "임원"},
            ],
        )
        d = get_chain_detail(cid)
        assert d["status"] == "pending"
        assert d["current_step"] == 1
        assert len(d["steps"]) == 3
        assert d["steps"][0]["approver_id"] == "EMP_A"
        assert d["steps"][2]["role_label"] == "임원"

    def test_empty_steps_raises(self, tmp_db):
        from features.compliance.approval_workflow import start_chain
        with pytest.raises(ValueError):
            start_chain(change_id=1, name="x", requested_by="R", steps=[])

    def test_missing_approver_id_raises(self, tmp_db):
        from features.compliance.approval_workflow import start_chain
        with pytest.raises(ValueError):
            start_chain(change_id=1, name="x", requested_by="R",
                        steps=[{"approver_id": "", "role_label": "차장"}])


# ─────────────────────────────────────────────────────────────
# act_on_step
# ─────────────────────────────────────────────────────────────


class TestActOnStep:
    def _make_chain(self, tmp_db):
        from features.compliance.approval_workflow import (
            start_chain, get_chain_detail,
        )
        cid = start_chain(
            change_id=1, name="결재", requested_by="REQ",
            steps=[
                {"approver_id": "A", "role_label": "차장"},
                {"approver_id": "B", "role_label": "팀장"},
                {"approver_id": "C", "role_label": "임원"},
            ],
        )
        return cid, get_chain_detail(cid)

    def test_approval_chain_complete_in_order(self, tmp_db):
        from features.compliance.approval_workflow import (
            act_on_step, get_chain_detail,
        )
        cid, d = self._make_chain(tmp_db)
        s1, s2, s3 = d["steps"]
        # step 1 approve
        out1 = act_on_step(s1["id"], "approved", actor="A")
        assert out1["new_chain_status"] == "pending"
        assert out1["next_step_order"] == 2
        # step 2 approve
        out2 = act_on_step(s2["id"], "approved", actor="B")
        assert out2["next_step_order"] == 3
        # step 3 approve → 전체 승인
        out3 = act_on_step(s3["id"], "approved", actor="C", comment="OK")
        assert out3["new_chain_status"] == "approved"
        assert out3["next_step_order"] == 0
        d2 = get_chain_detail(cid)
        assert d2["status"] == "approved"
        assert d2["completed_at"] != ""

    def test_rejection_terminates_chain_immediately(self, tmp_db):
        from features.compliance.approval_workflow import (
            act_on_step, get_chain_detail,
        )
        cid, d = self._make_chain(tmp_db)
        s1, s2, s3 = d["steps"]
        out = act_on_step(s1["id"], "rejected", actor="A", comment="문제 있음")
        assert out["new_chain_status"] == "rejected"
        d2 = get_chain_detail(cid)
        assert d2["status"] == "rejected"
        # 후속 step 들은 pending 그대로 (활성 안 됨)
        assert d2["steps"][1]["decision"] == "pending"
        assert d2["steps"][2]["decision"] == "pending"

    def test_wrong_approver_rejected(self, tmp_db):
        from features.compliance.approval_workflow import act_on_step
        cid, d = self._make_chain(tmp_db)
        s1 = d["steps"][0]
        out = act_on_step(s1["id"], "approved", actor="WRONG")
        assert out["ok"] is False
        assert out["error"].startswith("not_assigned")

    def test_out_of_order_rejected(self, tmp_db):
        """1단계 미결인데 2단계가 act 시도 → out_of_order."""
        from features.compliance.approval_workflow import act_on_step
        cid, d = self._make_chain(tmp_db)
        s2 = d["steps"][1]
        out = act_on_step(s2["id"], "approved", actor="B")
        assert out["ok"] is False
        assert out["error"].startswith("out_of_order")

    def test_double_decision_rejected(self, tmp_db):
        from features.compliance.approval_workflow import act_on_step
        cid, d = self._make_chain(tmp_db)
        s1 = d["steps"][0]
        # 정상 결재
        act_on_step(s1["id"], "approved", actor="A")
        # 같은 step 다시 결재 시도
        out = act_on_step(s1["id"], "rejected", actor="A")
        assert out["ok"] is False
        assert out["error"].startswith("already_decided")

    def test_invalid_decision(self, tmp_db):
        from features.compliance.approval_workflow import act_on_step
        cid, d = self._make_chain(tmp_db)
        s1 = d["steps"][0]
        out = act_on_step(s1["id"], "yes_please", actor="A")
        assert out["ok"] is False
        assert "invalid decision" in out["error"]


# ─────────────────────────────────────────────────────────────
# my_pending_steps
# ─────────────────────────────────────────────────────────────


class TestMyPending:
    def test_returns_only_current_active_step(self, tmp_db):
        from features.compliance.approval_workflow import (
            my_pending_steps, start_chain,
        )
        start_chain(
            change_id=1, name="ch1", requested_by="R",
            steps=[
                {"approver_id": "A", "role_label": "차장"},
                {"approver_id": "B", "role_label": "팀장"},
            ],
        )
        a_pending = my_pending_steps("A")
        b_pending = my_pending_steps("B")
        assert len(a_pending) == 1
        assert len(b_pending) == 0  # 아직 1단계 활성, 2단계 대기
        assert a_pending[0]["chain_name"] == "ch1"

    def test_pending_skips_completed_chains(self, tmp_db):
        from features.compliance.approval_workflow import (
            act_on_step, get_chain_detail, my_pending_steps, start_chain,
        )
        cid = start_chain(
            change_id=1, name="ch", requested_by="R",
            steps=[{"approver_id": "X", "role_label": "차장"}],
        )
        d = get_chain_detail(cid)
        act_on_step(d["steps"][0]["id"], "approved", actor="X")
        # X 의 pending list 는 비어야 함
        assert my_pending_steps("X") == []
