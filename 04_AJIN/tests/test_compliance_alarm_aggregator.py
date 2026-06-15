"""alarm_aggregator 단위·통합 테스트 (v4.2).

기존 test_change_pipeline_mvp.py 패턴 따라 tmp_path 기반 격리 DB 사용.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════


@pytest.fixture
def tmp_change_db(monkeypatch, tmp_path):
    """격리된 compliance_changes.db. change_detector + alarm_aggregator 양쪽 패치."""
    db_path = str(tmp_path / "compliance_changes.db")

    import features.compliance.change_detector as cd
    monkeypatch.setattr(cd, "CHANGE_DB_PATH", db_path)

    # alarm_aggregator 가 모듈 로드 시점에 CHANGE_DB_PATH 를 import 했으므로 별도 패치.
    import features.compliance.alarm_aggregator as aa
    monkeypatch.setattr(aa, "CHANGE_DB_PATH", db_path)
    # _SCENARIOS_DIR 도 격리 디렉토리로 패치 — 다른 테스트와 간섭 방지.
    scen_dir = tmp_path / "scenarios"
    scen_dir.mkdir()
    monkeypatch.setattr(aa, "_SCENARIOS_DIR", scen_dir)

    cd.init_change_db()
    return db_path, scen_dir


def _insert_change(
    db_path: str,
    *,
    item_id: str = "ITEM-001",
    item_title: str = "테스트 변경",
    change_type: str = "added",
    regulation_type: str = "산안법",
    new_value: str = "본문 변경",
    summary_ko: str = "",
    grade: str = "MEDIUM",
    status: str = "pending",
    acknowledged: int = 0,
    detected_at: str | None = None,
) -> int:
    detected_at = detected_at or datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO regulation_changes
              (detected_at, regulation_type, change_type, item_id, item_title,
               old_value, new_value, severity, acknowledged,
               status, summary_ko, grade)
            VALUES (?, ?, ?, ?, ?, '', ?, 'info', ?, ?, ?, ?)
            """,
            (
                detected_at, regulation_type, change_type, item_id, item_title,
                new_value, acknowledged, status, summary_ko, grade,
            ),
        )
        conn.commit()
        return cur.lastrowid


# ═══════════════════════════════════════════════════════════
# 단위 테스트 — 순수 함수
# ═══════════════════════════════════════════════════════════


def test_compute_scenario_impact_score_high_safety():
    """severity=high + safety + 다수 시설 → ≥90."""
    from features.compliance.alarm_aggregator import _compute_scenario_impact_score

    score = _compute_scenario_impact_score({
        "severity": "high",
        "affected_facility_ids": ["A", "B", "C", "D", "E"],
        "impact_areas": ["a", "b", "c", "d"],
        "regulation": {"category": "safety"},
    })
    assert score >= 90
    assert score <= 100


def test_compute_scenario_impact_score_low():
    """severity=low + 빈 리스트 → <80."""
    from features.compliance.alarm_aggregator import _compute_scenario_impact_score

    score = _compute_scenario_impact_score({"severity": "low"})
    assert score < 80


def test_extract_effective_date():
    """new_value 텍스트에서 YYYY-MM-DD 추출."""
    from features.compliance.alarm_aggregator import _extract_effective_date

    assert _extract_effective_date("시행 2026-07-01.") == date(2026, 7, 1)
    assert _extract_effective_date(None, "no date here") is None
    # 첫 번째 매치 우선
    assert _extract_effective_date("2025-12-31에 발표, 2026-01-15 시행") == date(2025, 12, 31)


# ═══════════════════════════════════════════════════════════
# 통합 테스트 — collect_recent_alarms
# ═══════════════════════════════════════════════════════════


def test_empty_db_returns_empty(tmp_change_db):
    from features.compliance.alarm_aggregator import collect_recent_alarms

    alarms = collect_recent_alarms()
    assert alarms == []


def test_law_change_alarm_basic(tmp_change_db):
    db, _ = tmp_change_db
    rid = _insert_change(db, change_type="added", grade="HIGH", item_title="산안법 신규")

    from features.compliance.alarm_aggregator import collect_recent_alarms

    alarms = collect_recent_alarms()
    assert len(alarms) == 1
    a = alarms[0]
    assert a.source == "law_change"
    assert a.regulation_id == str(rid)
    assert a.id == f"D-law_change-{rid}"
    assert a.severity == "HIGH"  # added → HIGH base
    assert a.acknowledged is False


def test_grade_critical_overrides_severity(tmp_change_db):
    db, _ = tmp_change_db
    _insert_change(db, change_type="modified", grade="CRITICAL")

    from features.compliance.alarm_aggregator import collect_recent_alarms

    alarms = collect_recent_alarms()
    assert alarms[0].severity == "CRITICAL"


def test_dday_alarm_critical_within_7days(tmp_change_db):
    db, _ = tmp_change_db
    eff = (date.today() + timedelta(days=3)).isoformat()
    rid = _insert_change(
        db,
        change_type="modified",
        new_value=f"시행 {eff}",
        grade="MEDIUM",
    )

    from features.compliance.alarm_aggregator import collect_recent_alarms

    alarms = collect_recent_alarms()
    sources = {a.source for a in alarms}
    assert "law_change" in sources
    assert "dday" in sources
    dday_alarm = next(a for a in alarms if a.source == "dday")
    assert dday_alarm.severity == "CRITICAL"
    assert dday_alarm.effective_date == eff
    assert dday_alarm.regulation_id == str(rid)


def test_dday_alarm_high_within_30days(tmp_change_db):
    db, _ = tmp_change_db
    eff = (date.today() + timedelta(days=20)).isoformat()
    _insert_change(db, new_value=f"시행 {eff}")

    from features.compliance.alarm_aggregator import collect_recent_alarms

    dday = next(a for a in collect_recent_alarms() if a.source == "dday")
    assert dday.severity == "HIGH"


def test_dday_skips_past_dates(tmp_change_db):
    db, _ = tmp_change_db
    eff = (date.today() - timedelta(days=5)).isoformat()
    _insert_change(db, new_value=f"시행 {eff}")

    from features.compliance.alarm_aggregator import collect_recent_alarms

    alarms = collect_recent_alarms()
    assert not any(a.source == "dday" for a in alarms)


def test_acknowledged_row_excluded(tmp_change_db):
    db, _ = tmp_change_db
    _insert_change(db, acknowledged=1)

    from features.compliance.alarm_aggregator import collect_recent_alarms

    assert collect_recent_alarms() == []


def test_mark_acknowledged_flow(tmp_change_db):
    db, _ = tmp_change_db
    rid = _insert_change(db)

    from features.compliance.alarm_aggregator import collect_recent_alarms, mark_acknowledged

    alarms = collect_recent_alarms()
    target = alarms[0].id

    result = mark_acknowledged(target, actor="tester")
    assert result["alarm_id"] == target
    assert result["actor"] == "tester"

    # 재조회 시 acknowledged=True (DB ack 테이블에 기록되어 LEFT JOIN 으로 반영)
    refreshed = collect_recent_alarms()
    assert all(a.id != target or a.acknowledged for a in refreshed)


def test_mark_acknowledged_idempotent(tmp_change_db):
    db, _ = tmp_change_db
    _insert_change(db)

    from features.compliance.alarm_aggregator import collect_recent_alarms, mark_acknowledged

    target = collect_recent_alarms()[0].id
    r1 = mark_acknowledged(target, actor="user1")
    r2 = mark_acknowledged(target, actor="user2")  # 같은 alarm_id 재호출
    assert r1["alarm_id"] == r2["alarm_id"]
    assert r2["actor"] == "user2"


def test_unresolved_action_alarm(tmp_change_db):
    db, _ = tmp_change_db
    old = (datetime.now() - timedelta(days=10)).isoformat(timespec="seconds")
    _insert_change(db, status="action_required", detected_at=old)

    from features.compliance.alarm_aggregator import collect_recent_alarms

    unresolved = [a for a in collect_recent_alarms() if a.source == "unresolved"]
    assert len(unresolved) == 1
    assert unresolved[0].severity == "HIGH"


def test_unresolved_14days_critical(tmp_change_db):
    db, _ = tmp_change_db
    old = (datetime.now() - timedelta(days=20)).isoformat(timespec="seconds")
    _insert_change(db, status="action_required", detected_at=old)

    from features.compliance.alarm_aggregator import collect_recent_alarms

    unresolved = next(a for a in collect_recent_alarms() if a.source == "unresolved")
    assert unresolved.severity == "CRITICAL"


def test_impact_score_from_scenarios(tmp_change_db):
    _, scen_dir = tmp_change_db
    (scen_dir / "high.json").write_text(json.dumps({
        "scenario_id": "SCN-TEST-001",
        "title": "고영향 시나리오",
        "severity": "high",
        "affected_facility_ids": ["A", "B", "C", "D", "E"],
        "impact_areas": ["x", "y", "z", "w"],
        "regulation": {"category": "safety"},
    }, ensure_ascii=False), encoding="utf-8")
    (scen_dir / "low.json").write_text(json.dumps({
        "scenario_id": "SCN-TEST-002",
        "severity": "low",
    }, ensure_ascii=False), encoding="utf-8")

    from features.compliance.alarm_aggregator import collect_recent_alarms

    impact = [a for a in collect_recent_alarms() if a.source == "impact_score"]
    assert len(impact) == 1
    assert impact[0].regulation_id == "SCN-TEST-001"
    assert impact[0].severity in {"CRITICAL", "HIGH"}


def test_dedup_across_sources(tmp_change_db):
    """같은 regulation_id 가 law_change + dday 양쪽 트리거 시 각각 1건씩 유지 (source 가 다르므로)."""
    db, _ = tmp_change_db
    eff = (date.today() + timedelta(days=10)).isoformat()
    _insert_change(db, new_value=f"시행 {eff}")

    from features.compliance.alarm_aggregator import collect_recent_alarms

    alarms = collect_recent_alarms()
    sources = sorted(a.source for a in alarms)
    assert sources == ["dday", "law_change"]


def test_limit_caps_result(tmp_change_db):
    db, _ = tmp_change_db
    for i in range(5):
        _insert_change(db, item_id=f"ITEM-{i:03d}")

    from features.compliance.alarm_aggregator import collect_recent_alarms

    alarms = collect_recent_alarms(limit=3)
    assert len(alarms) == 3
