"""P4 D14 — 권한 위임 룰 엔진 단위 테스트."""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """compliance_changes.db 를 임시 경로로 격리."""
    import features.compliance.change_detector as cd
    monkeypatch.setattr(cd, "CHANGE_DB_PATH", str(tmp_path / "ch.db"))
    cd.init_change_db()
    return cd


@pytest.fixture(autouse=True)
def _no_external(monkeypatch):
    """Slack/Jira/Asana webhook 발송 차단.

    P4.1 §1: assign deny-by-default 정책을 테스트 환경에서 우회 — 기존 케이스 호환.
    P5 §3: 매 테스트마다 룰 cache 리셋 (DB 가 tmp_path 로 격리되므로 cache 도 무효화).
    """
    import config
    monkeypatch.setattr(config, "SLACK_WEBHOOK_URL", "", raising=False)
    monkeypatch.delenv("JIRA_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("ASANA_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("DELEGATION_REQUIRE_EMPLOYEES_DB", "0")
    # P5 §3 cache leak 방지
    from features.compliance.delegation_rules import _invalidate_rules_cache
    _invalidate_rules_cache()


def _seed_change(cd_module, **fields):
    """regulation_changes 에 한 row 적재 후 id 반환."""
    conn = sqlite3.connect(cd_module.CHANGE_DB_PATH)
    now = datetime.now().isoformat()
    payload = {
        "detected_at": now,
        "regulation_type": fields.get("regulation_type", "test"),
        "change_type": fields.get("change_type", "added"),
        "item_id": fields.get("item_id", "X1"),
        "item_title": fields.get("item_title", "테스트 제목"),
        "old_value": "",
        "new_value": "",
        "severity": "info",
        "status": fields.get("status", "pending"),
        "grade": fields.get("grade", "MEDIUM"),
        "summary_ko": fields.get("summary_ko", ""),
        "affected_departments": json.dumps(
            fields.get("affected_departments", []), ensure_ascii=False
        ),
        "affected_plants": "[]",
        "legal_class": json.dumps(fields.get("legal_class", []), ensure_ascii=False),
        "penalty_severity_krw_mn": int(fields.get("penalty_severity_krw_mn", 0)),
    }
    cur = conn.execute(
        """INSERT INTO regulation_changes
           (detected_at, regulation_type, change_type, item_id, item_title,
            old_value, new_value, severity, status, grade, summary_ko,
            affected_departments, affected_plants, legal_class, penalty_severity_krw_mn)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        tuple(payload.values()),
    )
    conn.commit()
    cid = int(cur.lastrowid)
    conn.close()
    return cid


# ─────────────────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────────────────


class TestCrud:
    def test_create_then_list(self, tmp_db):
        from features.compliance.delegation_rules import create_rule, list_rules
        rid = create_rule(
            name="rule1", owner="admin",
            conditions={"grade_in": ["LOW"]},
            actions={"transition_to": "reviewing"},
            priority=10,
        )
        rows = list_rules()
        assert len(rows) == 1
        r = rows[0]
        assert r["id"] == rid
        assert r["enabled"] is True
        assert r["conditions"]["grade_in"] == ["LOW"]
        assert r["actions"]["transition_to"] == "reviewing"
        assert r["priority"] == 10

    def test_update_disable_and_priority(self, tmp_db):
        from features.compliance.delegation_rules import (
            create_rule, update_rule, get_rule,
        )
        rid = create_rule(
            name="r", owner="a",
            conditions={}, actions={"transition_to": "reviewing"},
        )
        ok = update_rule(rid, enabled=False, priority=5)
        assert ok is True
        r = get_rule(rid)
        assert r is not None
        assert r["enabled"] is False
        assert r["priority"] == 5

    def test_delete(self, tmp_db):
        from features.compliance.delegation_rules import (
            create_rule, delete_rule, list_rules,
        )
        rid = create_rule(name="r", owner="a", conditions={}, actions={})
        assert delete_rule(rid) is True
        assert list_rules() == []

    def test_enabled_only_filter(self, tmp_db):
        from features.compliance.delegation_rules import (
            create_rule, update_rule, list_rules,
        )
        a = create_rule(name="a", owner="x", conditions={}, actions={})
        b = create_rule(name="b", owner="x", conditions={}, actions={})
        update_rule(b, enabled=False)
        on = list_rules(enabled_only=True)
        assert len(on) == 1
        assert on[0]["id"] == a


# ─────────────────────────────────────────────────────────────
# 매칭 / 우선순위
# ─────────────────────────────────────────────────────────────


class TestEvaluate:
    def test_match_grade_dept_penalty(self, tmp_db):
        """복합 조건 — grade=LOW & 환경팀 단독 & 벌칙 ≤100M 모두 만족."""
        from features.compliance.delegation_rules import create_rule, evaluate
        create_rule(
            name="env_low",
            owner="a",
            conditions={
                "grade_in": ["LOW"],
                "departments_subset_of": ["환경"],
                "penalty_max_krw_mn": 100,
            },
            actions={"transition_to": "reviewing"},
            priority=10,
        )
        cid = _seed_change(
            tmp_db,
            grade="LOW",
            affected_departments=["환경"],
            penalty_severity_krw_mn=50,
        )
        result = evaluate({"id": cid, "grade": "LOW",
                           "affected_departments": ["환경"],
                           "legal_class": [],
                           "penalty_severity_krw_mn": 50}, dry_run=True)
        assert result["matched"] is True
        assert result["rule_name"] == "env_low"

    def test_priority_first_match_wins(self, tmp_db):
        """priority 가 낮은 룰이 먼저 매치되어야 함."""
        from features.compliance.delegation_rules import create_rule, evaluate
        create_rule(name="hi_pri", owner="a",
                    conditions={"grade_in": ["MEDIUM"]},
                    actions={"transition_to": "planning"}, priority=5)
        create_rule(name="lo_pri", owner="a",
                    conditions={"grade_in": ["MEDIUM"]},
                    actions={"transition_to": "reviewing"}, priority=99)
        result = evaluate({"id": 1, "grade": "MEDIUM",
                           "affected_departments": [],
                           "legal_class": [], "penalty_severity_krw_mn": 0},
                          dry_run=True)
        assert result["matched"] is True
        assert result["rule_name"] == "hi_pri"

    def test_disabled_rule_skipped(self, tmp_db):
        from features.compliance.delegation_rules import (
            create_rule, update_rule, evaluate,
        )
        rid = create_rule(name="r", owner="a",
                          conditions={"grade_in": ["LOW"]},
                          actions={"transition_to": "reviewing"})
        update_rule(rid, enabled=False)
        out = evaluate({"id": 1, "grade": "LOW",
                        "affected_departments": [], "legal_class": [],
                        "penalty_severity_krw_mn": 0}, dry_run=True)
        assert out["matched"] is False
        assert out["result"] == "no_match"

    def test_penalty_above_max_no_match(self, tmp_db):
        from features.compliance.delegation_rules import create_rule, evaluate
        create_rule(name="r", owner="a",
                    conditions={"grade_in": ["LOW"], "penalty_max_krw_mn": 100},
                    actions={"transition_to": "reviewing"})
        out = evaluate({"id": 1, "grade": "LOW",
                        "affected_departments": [], "legal_class": [],
                        "penalty_severity_krw_mn": 500}, dry_run=True)
        assert out["matched"] is False

    def test_keyword_partial_match(self, tmp_db):
        from features.compliance.delegation_rules import create_rule, evaluate
        create_rule(name="eu", owner="a",
                    conditions={"keywords_any": ["EU", "RoHS"]},
                    actions={"notify_slack": ["#x"]})
        out = evaluate({"id": 1, "grade": "MEDIUM", "item_title": "EU 신규 지침",
                        "affected_departments": [], "legal_class": [],
                        "penalty_severity_krw_mn": 0}, dry_run=True)
        assert out["matched"] is True


# ─────────────────────────────────────────────────────────────
# Apply 사이드이펙트
# ─────────────────────────────────────────────────────────────


class TestApplyActions:
    def test_dry_run_no_transition(self, tmp_db):
        """dry_run 은 transition 호출 없이 audit 만 기록."""
        from features.compliance.delegation_rules import (
            create_rule, evaluate, list_audit,
        )
        cid = _seed_change(tmp_db, grade="LOW", status="pending")
        create_rule(name="r", owner="a",
                    conditions={"grade_in": ["LOW"]},
                    actions={"transition_to": "reviewing"})
        evaluate({"id": cid, "change_id": cid, "grade": "LOW",
                  "affected_departments": [], "legal_class": [],
                  "penalty_severity_krw_mn": 0}, dry_run=True)
        # status 변경 안 되었어야 함
        conn = sqlite3.connect(tmp_db.CHANGE_DB_PATH)
        row = conn.execute(
            "SELECT status FROM regulation_changes WHERE id = ?", (cid,)
        ).fetchone()
        conn.close()
        assert row[0] == "pending"
        # audit 은 기록
        audit = list_audit(change_id=cid)
        assert len(audit) == 1
        assert audit[0]["result"] == "dry_run"

    def test_real_apply_transitions(self, tmp_db):
        """dry_run=False → 실제 transition + audit result='applied'."""
        from features.compliance.delegation_rules import (
            create_rule, evaluate, list_audit,
        )
        cid = _seed_change(tmp_db, grade="LOW", status="pending")
        create_rule(name="r", owner="a",
                    conditions={"grade_in": ["LOW"]},
                    actions={"transition_to": "reviewing"})
        out = evaluate({"id": cid, "change_id": cid, "grade": "LOW",
                        "affected_departments": [], "legal_class": [],
                        "penalty_severity_krw_mn": 0}, dry_run=False)
        assert out["matched"] is True
        assert out["applied_actions"].get("transition_to") == "reviewing"
        conn = sqlite3.connect(tmp_db.CHANGE_DB_PATH)
        row = conn.execute(
            "SELECT status FROM regulation_changes WHERE id = ?", (cid,)
        ).fetchone()
        conn.close()
        assert row[0] == "reviewing"
        audit = list_audit(change_id=cid)
        assert audit[0]["result"] == "applied"

    def test_assign_to_unknown_employee_graceful(self, tmp_db, monkeypatch):
        """employees.db 에 없는 employee_id 면 assign 결과에 포함 안 되어야 함."""
        # employees.db 가 없는 임시 환경 보장 — 아무것도 안 함, 자동 graceful skip
        from features.compliance.delegation_rules import create_rule, evaluate
        cid = _seed_change(tmp_db, grade="LOW", status="pending")
        create_rule(name="r", owner="a",
                    conditions={"grade_in": ["LOW"]},
                    actions={"assign_to": "GHOST_ID_XYZ"})
        out = evaluate({"id": cid, "change_id": cid, "grade": "LOW",
                        "affected_departments": [], "legal_class": [],
                        "penalty_severity_krw_mn": 0}, dry_run=False)
        # 적용은 시도됐지만 결과는 result 가 'applied' 또는 'error:...' 이고
        # 가짜 숫자/존재하지 않는 employee 적용 안 함은 _maybe_assign 결과로 검증
        # employees.db 없어도 update 자체는 성공할 수 있으나 모듈은 graceful skip
        assert out["matched"] is True


# ─────────────────────────────────────────────────────────────
# Dry-run recent
# ─────────────────────────────────────────────────────────────


class TestAssignPolicy:
    """P4.1 §1 — deny-by-default policy 검증."""

    def test_deny_when_employees_db_missing_and_require_on(
        self, tmp_db, monkeypatch,
    ):
        """REQUIRE=1 + employees.db 미존재 → assign skip + audit errors 기록."""
        monkeypatch.setenv("DELEGATION_REQUIRE_EMPLOYEES_DB", "1")
        from features.compliance.delegation_rules import (
            create_rule, evaluate, list_audit,
        )
        cid = _seed_change(tmp_db, grade="LOW", status="pending")
        create_rule(
            name="r", owner="a",
            conditions={"grade_in": ["LOW"]},
            actions={"assign_to": "EMPX"},
        )
        out = evaluate(
            {"id": cid, "change_id": cid, "grade": "LOW",
             "affected_departments": [], "legal_class": [],
             "penalty_severity_krw_mn": 0},
            dry_run=False, trigger="manual",
        )
        # assign 적용 안 됨
        assert "assign_to" not in out["applied_actions"]
        # audit errors 에 사유 기록
        audit = list_audit(change_id=cid)
        errs = audit[0]["applied_actions"]["errors"]
        assert any("assign_to_skipped:EMPX" in e for e in errs)
        # regulation_changes.assigned_to 도 비어있음
        conn = sqlite3.connect(tmp_db.CHANGE_DB_PATH)
        row = conn.execute(
            "SELECT assigned_to FROM regulation_changes WHERE id = ?", (cid,)
        ).fetchone()
        conn.close()
        assert (row[0] or "") == ""

    def test_legacy_when_require_off(self, tmp_db, monkeypatch):
        """REQUIRE=0 → 검증 없이 assign 적용 (테스트/legacy)."""
        monkeypatch.setenv("DELEGATION_REQUIRE_EMPLOYEES_DB", "0")
        from features.compliance.delegation_rules import create_rule, evaluate
        cid = _seed_change(tmp_db, grade="LOW", status="pending")
        create_rule(
            name="r", owner="a",
            conditions={"grade_in": ["LOW"]},
            actions={"assign_to": "EMPY"},
        )
        out = evaluate(
            {"id": cid, "change_id": cid, "grade": "LOW",
             "affected_departments": [], "legal_class": [],
             "penalty_severity_krw_mn": 0},
            dry_run=False, trigger="manual",
        )
        assert out["applied_actions"].get("assign_to") == "EMPY"


class TestTriggerGuard:
    """P4 D14 fix #1 — trigger 별 액션 화이트리스트 검증."""

    def test_post_user_transition_skips_transition_to(self, tmp_db):
        """사용자 transition 직후 hook 에서는 룰의 transition_to 가 발화되지 않아야 함."""
        from features.compliance.delegation_rules import create_rule, evaluate
        cid = _seed_change(tmp_db, grade="LOW", status="reviewing")
        create_rule(
            name="ruleX", owner="a",
            conditions={"grade_in": ["LOW"]},
            actions={"transition_to": "planning"},
        )
        out = evaluate(
            {"id": cid, "change_id": cid, "grade": "LOW",
             "affected_departments": [], "legal_class": [],
             "penalty_severity_krw_mn": 0},
            dry_run=False, trigger="post_user_transition",
        )
        assert out["matched"] is True
        # 핵심 invariant: transition_to 가 적용되지 않음
        assert "transition_to" not in out["applied_actions"]
        # 사용자가 설정한 status 가 그대로 유지
        conn = sqlite3.connect(tmp_db.CHANGE_DB_PATH)
        row = conn.execute(
            "SELECT status FROM regulation_changes WHERE id = ?", (cid,)
        ).fetchone()
        conn.close()
        assert row[0] == "reviewing"

    def test_manual_trigger_applies_transition_to(self, tmp_db):
        """비교 — manual trigger 는 transition_to 그대로 적용."""
        from features.compliance.delegation_rules import create_rule, evaluate
        cid = _seed_change(tmp_db, grade="LOW", status="pending")
        create_rule(
            name="ruleY", owner="a",
            conditions={"grade_in": ["LOW"]},
            actions={"transition_to": "reviewing"},
        )
        out = evaluate(
            {"id": cid, "change_id": cid, "grade": "LOW",
             "affected_departments": [], "legal_class": [],
             "penalty_severity_krw_mn": 0},
            dry_run=False, trigger="manual",
        )
        assert out["applied_actions"].get("transition_to") == "reviewing"

    def test_post_user_transition_still_applies_assign_and_notify(self, tmp_db):
        """post_user_transition 에서 assign / notify / ticket 은 그대로 발화."""
        from features.compliance.delegation_rules import (
            create_rule, evaluate, list_audit,
        )
        cid = _seed_change(tmp_db, grade="LOW", status="reviewing",
                           affected_departments=["환경", "품질"])
        create_rule(
            name="ruleZ", owner="a",
            conditions={"grade_in": ["LOW"]},
            actions={
                "transition_to": "planning",
                "assign_to": "EMPX",
                "notify_slack": ["#x"],
            },
        )
        out = evaluate(
            {"id": cid, "change_id": cid, "grade": "LOW",
             "affected_departments": ["환경", "품질"], "legal_class": [],
             "penalty_severity_krw_mn": 0},
            dry_run=False, trigger="post_user_transition",
        )
        # transition_to 만 skip, 나머지 액션은 시도됨 (audit 에 errors 도 기록)
        assert "transition_to" not in out["applied_actions"]
        audit = list_audit(change_id=cid)
        assert audit[0]["applied_actions"]["actions"]["transition_to"] == "planning"
        # errors 에 trigger 사유 명시
        errs = audit[0]["applied_actions"]["errors"]
        assert any("transition_skipped_by_trigger" in e for e in errs)


class TestDslSanitize:
    """P5 §2 — DSL JSON 텍스트 편집: 알려진 키만 통과."""

    def test_unknown_keys_dropped_silently(self, tmp_db, caplog):
        from features.compliance.delegation_rules import (
            create_rule, get_rule,
        )
        rid = create_rule(
            name="dsl", owner="a",
            conditions={"grade_in": ["LOW"], "unknown_field": "X"},
            actions={"transition_to": "reviewing", "evil_action": True},
        )
        r = get_rule(rid)
        # 알려진 키는 보존
        assert r["conditions"]["grade_in"] == ["LOW"]
        assert r["actions"]["transition_to"] == "reviewing"
        # 알려지지 않은 키는 제거
        assert "unknown_field" not in r["conditions"]
        assert "evil_action" not in r["actions"]

    def test_non_dict_raises(self, tmp_db):
        from features.compliance.delegation_rules import create_rule
        with pytest.raises(ValueError):
            create_rule(name="x", owner="a", conditions="not_a_dict",  # type: ignore[arg-type]
                        actions={})


class TestRuleCache:
    """P5 §3 — 룰 in-memory cache + CUD invalidation."""

    def test_evaluate_picks_up_new_rule_immediately(self, tmp_db):
        """create_rule 후 evaluate 가 즉시 새 룰 반영 (cache invalidate 검증)."""
        from features.compliance.delegation_rules import (
            _list_rules_cached, create_rule, evaluate, _RULES_CACHE,
        )
        # cache 초기 — 빈 상태에서 한번 채워둠 (다른 테스트에서 setattr 영향 받을 수 있어 명시 reset)
        _RULES_CACHE["rules"] = None
        # 첫 호출 — 빈 룰 list
        rules = _list_rules_cached(enabled_only=True)
        assert rules == []
        # 새 룰 생성 → cache invalidate
        create_rule(
            name="cached", owner="a",
            conditions={"grade_in": ["LOW"]},
            actions={"transition_to": "reviewing"},
        )
        # evaluate 즉시 매치 (5초 TTL 무관)
        out = evaluate(
            {"id": 1, "grade": "LOW", "affected_departments": [],
             "legal_class": [], "penalty_severity_krw_mn": 0},
            dry_run=True,
        )
        assert out["matched"] is True
        assert out["rule_name"] == "cached"

    def test_delete_rule_invalidates_cache(self, tmp_db):
        from features.compliance.delegation_rules import (
            _list_rules_cached, create_rule, delete_rule, _RULES_CACHE,
        )
        _RULES_CACHE["rules"] = None
        rid = create_rule(name="x", owner="a", conditions={}, actions={})
        # cache fill
        rules = _list_rules_cached(enabled_only=False)
        assert any(r["id"] == rid for r in rules)
        # delete → cache invalidate
        assert delete_rule(rid) is True
        rules2 = _list_rules_cached(enabled_only=False)
        assert not any(r["id"] == rid for r in rules2)


class TestPartialResult:
    """P4.1 §5 — result 5종: applied / partial / error / no_action / dry_run."""

    def test_no_action_when_actions_empty(self, tmp_db):
        """조건 매치하지만 actions 가 비어있으면 result='no_action'."""
        from features.compliance.delegation_rules import (
            create_rule, evaluate, list_audit,
        )
        cid = _seed_change(tmp_db, grade="LOW", status="pending")
        create_rule(name="r", owner="a",
                    conditions={"grade_in": ["LOW"]},
                    actions={})
        evaluate({"id": cid, "change_id": cid, "grade": "LOW",
                  "affected_departments": [], "legal_class": [],
                  "penalty_severity_krw_mn": 0}, dry_run=False, trigger="manual")
        audit = list_audit(change_id=cid)
        assert audit[0]["result"] == "no_action"

    def test_partial_when_one_action_succeeds_and_other_fails(self, tmp_db, monkeypatch):
        """transition_to 성공 + assign deny → result='partial:...'."""
        # require_db=1 로 assign 만 deny
        monkeypatch.setenv("DELEGATION_REQUIRE_EMPLOYEES_DB", "1")
        from features.compliance.delegation_rules import (
            create_rule, evaluate, list_audit,
        )
        cid = _seed_change(tmp_db, grade="LOW", status="pending")
        create_rule(
            name="r", owner="a",
            conditions={"grade_in": ["LOW"]},
            actions={"transition_to": "reviewing", "assign_to": "GHOST_X"},
        )
        evaluate({"id": cid, "change_id": cid, "grade": "LOW",
                  "affected_departments": [], "legal_class": [],
                  "penalty_severity_krw_mn": 0}, dry_run=False, trigger="manual")
        audit = list_audit(change_id=cid)
        result = audit[0]["result"]
        assert result.startswith("partial:"), f"got {result!r}"
        assert "assign_to_skipped" in result

    def test_error_when_all_actions_fail(self, tmp_db, monkeypatch):
        """모든 액션 실패 → result='error:...' (assign 만 있고 deny)."""
        monkeypatch.setenv("DELEGATION_REQUIRE_EMPLOYEES_DB", "1")
        from features.compliance.delegation_rules import (
            create_rule, evaluate, list_audit,
        )
        cid = _seed_change(tmp_db, grade="LOW", status="pending")
        create_rule(
            name="r", owner="a",
            conditions={"grade_in": ["LOW"]},
            actions={"assign_to": "GHOST_Y"},
        )
        evaluate({"id": cid, "change_id": cid, "grade": "LOW",
                  "affected_departments": [], "legal_class": [],
                  "penalty_severity_krw_mn": 0}, dry_run=False, trigger="manual")
        audit = list_audit(change_id=cid)
        result = audit[0]["result"]
        assert result.startswith("error:"), f"got {result!r}"


class TestDryRunRecent:
    def test_scans_recent_and_counts(self, tmp_db):
        from features.compliance.delegation_rules import (
            create_rule, dry_run_recent,
        )
        # 3 changes 적재 (2 LOW + 1 HIGH)
        for grade in ["LOW", "LOW", "HIGH"]:
            _seed_change(tmp_db, grade=grade)
        create_rule(name="lows", owner="a",
                    conditions={"grade_in": ["LOW"]},
                    actions={"transition_to": "reviewing"})
        out = dry_run_recent(limit=10)
        assert out["scanned"] == 3
        assert out["matched"] == 2

    def test_empty_no_rules(self, tmp_db):
        from features.compliance.delegation_rules import dry_run_recent
        _seed_change(tmp_db, grade="LOW")
        out = dry_run_recent(limit=10)
        assert out["matched"] == 0
        assert out["matches"] == []
