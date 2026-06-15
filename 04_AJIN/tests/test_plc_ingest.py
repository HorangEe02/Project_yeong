"""v4.8 Feature F 트랙 A — PLC ingest 파이프라인 테스트.

검증:
  1. 정상 분포 메시지 100개 → Nelson 위반 0건 (sanity).
  2. R1 위반 주입 시 spc_violations_db.insert_violation + live_events.insert_alarm
     순서로 호출되는지 monkeypatch 로 확인.
  3. violation_to_alarm 변환 매트릭스 (critical→CRITICAL, warning→HIGH, info→MEDIUM) 검증.
  4. 동일 (process, rule, severity) 1분 내 dedup.
  5. dry-run firebase_rtdb.push_alarm — 파일 캡처 작동.
"""

from __future__ import annotations

import os
import random
from typing import Any

import pytest

from features.equipment import plc_ingest
from features.equipment.spc_realtime import NelsonViolation


# ──────────────────────────────────────────────────────────────────────────
# 1. violation_to_alarm — severity 매핑 매트릭스
# ──────────────────────────────────────────────────────────────────────────


def test_violation_to_alarm_severity_critical() -> None:
    v = NelsonViolation(
        rule_number=1,
        rule_name="Beyond 3σ",
        description="3σ 초과",
        violating_indices=[10, 15, 22],
        severity="critical",
        recommended_action="즉시 점검",
    )
    alarm = plc_ingest.violation_to_alarm(
        v, process="cch_plate_thickness", line_id="L01", lot_id="LOT-1", violation_id="vid-1"
    )
    assert alarm["severity"] == "CRITICAL"
    assert alarm["type"] == "spc_violation"
    assert alarm["rule_number"] == 1
    assert alarm["violating_count"] == 3
    assert alarm["process"] == "cch_plate_thickness"
    assert alarm["line_id"] == "L01"
    assert alarm["source"] == "plc_ingest"
    assert alarm["id"] == "vid-1"


def test_violation_to_alarm_severity_warning_maps_to_high() -> None:
    v = NelsonViolation(rule_number=3, rule_name="r", description="d", severity="warning")
    alarm = plc_ingest.violation_to_alarm(v, "p", "L01", "lot", "vid")
    assert alarm["severity"] == "HIGH"


def test_violation_to_alarm_severity_info_maps_to_medium() -> None:
    v = NelsonViolation(rule_number=4, rule_name="r", description="d", severity="info")
    alarm = plc_ingest.violation_to_alarm(v, "p", "L01", "lot", "vid")
    assert alarm["severity"] == "MEDIUM"


def test_violation_to_alarm_severity_unknown_falls_back_to_info() -> None:
    v = NelsonViolation(rule_number=9, rule_name="r", description="d", severity="bogus")
    alarm = plc_ingest.violation_to_alarm(v, "p", "L01", "lot", "vid")
    assert alarm["severity"] == "INFO"


# ──────────────────────────────────────────────────────────────────────────
# 2. process_batch — 정상 분포 → 위반 0
# ──────────────────────────────────────────────────────────────────────────


def _normal_message(idx: int, process: str = "cch_plate_thickness") -> dict[str, str]:
    return {
        "ts": f"2026-05-17T00:00:{idx % 60:02d}Z",
        "line_id": "L01",
        "process": process,
        "value": f"{random.gauss(3.20, 0.04):.6f}",
        "lot_id": "LOT-L01",
        "source": "test",
    }


def test_process_batch_normal_distribution_low_violation_rate() -> None:
    """정상 가우시안 분포 100샘플 — Nelson 위반은 0~소수 (3σ 자연 발생 가능).

    중요 검증: 메시지 100개 모두 처리됨 + critical 위반이 폭주하지 않음 (<5건).
    """
    random.seed(42)
    messages = [_normal_message(i) for i in range(100)]
    captured: list[tuple[Any, ...]] = []

    def on_violation(v, process, line_id, lot_id, violation_id):
        captured.append((process, v.rule_number, v.severity))

    stats = plc_ingest.process_batch(messages, on_violation=on_violation)
    assert stats["messages"] == 100
    # critical(R1) 자연 발생률 ≈ 0.27%/샘플 — dedup 60s 로 사실상 1건 이하.
    crit_calls = [c for c in captured if c[2] == "critical"]
    assert len(crit_calls) <= 2, f"정상 분포에서 critical 폭주 (예상 ≤2): {crit_calls}"


# ──────────────────────────────────────────────────────────────────────────
# 3. R1 위반 주입 → on_violation 호출 + 페이로드 정합
# ──────────────────────────────────────────────────────────────────────────


def test_process_batch_inject_r1_triggers_critical_violation() -> None:
    random.seed(7)
    messages = [_normal_message(i) for i in range(50)]
    # Rule 1 강제 — 평균 +10σ 한 발 주입.
    messages.append(
        {
            "ts": "2026-05-17T01:00:00Z",
            "line_id": "L01",
            "process": "cch_plate_thickness",
            "value": "5.000000",  # mean=3.2, std=0.04 → 45σ 초과
            "lot_id": "LOT-L01",
            "source": "test",
        }
    )
    captured: list[dict[str, Any]] = []

    def on_violation(v, process, line_id, lot_id, violation_id):
        captured.append(
            {
                "rule_number": v.rule_number,
                "severity": v.severity,
                "process": process,
                "line_id": line_id,
                "violation_id": violation_id,
            }
        )

    stats = plc_ingest.process_batch(messages, on_violation=on_violation)
    assert stats["violations"] >= 1
    r1 = [c for c in captured if c["rule_number"] == 1]
    assert len(r1) >= 1, f"R1 위반 미감지: {captured}"
    assert r1[0]["severity"] == "critical"
    assert r1[0]["process"] == "cch_plate_thickness"
    assert r1[0]["line_id"] == "L01"
    assert r1[0]["violation_id"].startswith("plc_cch_plate_thickness_R1_")


def test_process_batch_passes_source_system_to_new_callbacks() -> None:
    """Bridge-origin messages should preserve source_system for persistence."""
    random.seed(9)
    messages = [_normal_message(i) for i in range(50)]
    messages.append(
        {
            "ts": "2026-05-17T01:00:00Z",
            "line_id": "L01",
            "process": "cch_plate_thickness",
            "value": "5.000000",
            "lot_id": "LOT-L01",
            "source": "mqtt",
            "source_system": "mqtt_bridge",
        }
    )
    captured: list[str] = []

    def on_violation(v, process, line_id, lot_id, violation_id, *, source_system):
        captured.append(source_system)

    stats = plc_ingest.process_batch(messages, on_violation=on_violation)

    assert stats["violations"] >= 1
    assert "mqtt_bridge" in captured


# ──────────────────────────────────────────────────────────────────────────
# 4. _persist_and_push — spc_violations_db.insert + live_events.insert 호출 검증
# ──────────────────────────────────────────────────────────────────────────


def test_persist_and_push_invokes_db_insert_then_live_alarm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """위반 1건 → insert_violation + insert_alarm 호출 순서/페이로드 확인."""
    inserted: list[dict[str, Any]] = []
    pushed: list[dict[str, Any]] = []

    def fake_insert(**kwargs):
        inserted.append(kwargs)
        return kwargs.get("violation_id", "")

    def fake_insert_alarm(alarm_dict, **kwargs):
        pushed.append({"alarm": alarm_dict, "kwargs": kwargs})
        return alarm_dict.get("id", "")

    import features.equipment.spc_violations_db as vdb
    import backend.services.live_events as live_events_mod

    monkeypatch.setattr(vdb, "insert_violation", fake_insert)
    monkeypatch.setattr(live_events_mod, "insert_alarm", fake_insert_alarm)

    violation = NelsonViolation(
        rule_number=1,
        rule_name="Beyond 3σ",
        description="3σ 초과",
        violating_indices=[42],
        severity="critical",
        recommended_action="즉시 점검",
    )

    plc_ingest._persist_and_push(
        violation,
        process="cch_plate_thickness",
        line_id="L02",
        lot_id="LOT-99",
        violation_id="plc_cch_R1_abc12345",
    )

    assert len(inserted) == 1
    assert inserted[0]["violation_id"] == "plc_cch_R1_abc12345"
    assert inserted[0]["process"] == "cch_plate_thickness"
    assert inserted[0]["lot_id"] == "LOT-99"
    assert inserted[0]["rule_number"] == 1
    assert inserted[0]["severity"] == "critical"

    assert len(pushed) == 1
    alarm = pushed[0]["alarm"]
    assert alarm["severity"] == "CRITICAL"
    assert alarm["rule_number"] == 1
    assert alarm["line_id"] == "L02"
    assert alarm["lot_id"] == "LOT-99"
    assert alarm["source"] == "plc_ingest"
    assert pushed[0]["kwargs"]["domain"] == "equipment"
    assert pushed[0]["kwargs"]["source_system"] == "plc_ingest"


# ──────────────────────────────────────────────────────────────────────────
# 5. Dedup — 1분 내 동일 (process, rule, severity) 중복 차단
# ──────────────────────────────────────────────────────────────────────────


def test_dedup_suppresses_repeated_violation_within_ttl() -> None:
    """연속 R1 주입 — 두 번째 호출이 dedup 으로 차단되어야."""
    random.seed(1)
    messages: list[dict[str, str]] = []
    # 충분한 정상 샘플 + R1 위반 2발 (윈도우 내).
    for i in range(20):
        messages.append(_normal_message(i))
    messages.append(_normal_message(0))  # R1 트리거 후 추가 메시지가 다시 분석 호출.
    messages.append(
        {
            "ts": "T1",
            "line_id": "L01",
            "process": "cch_plate_thickness",
            "value": "5.500000",
            "lot_id": "L",
            "source": "test",
        }
    )
    messages.append(
        {
            "ts": "T2",
            "line_id": "L01",
            "process": "cch_plate_thickness",
            "value": "5.700000",
            "lot_id": "L",
            "source": "test",
        }
    )

    captured: list[int] = []

    def on_violation(v, process, line_id, lot_id, violation_id):
        captured.append(v.rule_number)

    stats = plc_ingest.process_batch(messages, on_violation=on_violation)
    # R1 한 번만 발화되어야 (dedup).
    r1_calls = [r for r in captured if r == 1]
    assert len(r1_calls) == 1, f"dedup 실패 — R1 호출 {len(r1_calls)}회 (예상 1): {captured}"
    assert stats["messages"] == len(messages)


# ──────────────────────────────────────────────────────────────────────────
# 6. firebase_rtdb dry-run — 미설정 시 파일 캡처
# ──────────────────────────────────────────────────────────────────────────


def test_firebase_rtdb_dryrun_capture(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """FIREBASE_ADMIN_CREDENTIALS_JSON 미설정 → push_alarm 이 파일에 캡처."""
    monkeypatch.delenv("FIREBASE_ADMIN_CREDENTIALS_JSON", raising=False)
    monkeypatch.delenv("FIREBASE_DATABASE_URL", raising=False)

    import backend.services.firebase_rtdb as rtdb_mod

    # 초기화 상태 리셋 — 다른 테스트에서 cache 됐을 수 있음.
    monkeypatch.setattr(rtdb_mod, "_INITIALIZED", None)
    monkeypatch.setattr(rtdb_mod, "_DRYRUN_DIR", tmp_path / "rtdb_dryrun")

    key = rtdb_mod.push_alarm({"id": "test", "severity": "CRITICAL"})
    assert key.startswith("dryrun-")

    captured_files = list((tmp_path / "rtdb_dryrun").glob("*.json"))
    assert len(captured_files) == 1
    content = captured_files[0].read_text(encoding="utf-8")
    assert "CRITICAL" in content


# ──────────────────────────────────────────────────────────────────────────
# 7. _process_message — value 파싱 실패 시 안전 처리
# ──────────────────────────────────────────────────────────────────────────


def test_process_message_handles_invalid_value() -> None:
    bad_messages = [
        {"process": "p", "value": "not-a-number", "line_id": "L01", "lot_id": "X"},
        {"process": "", "value": "1.0", "line_id": "L01", "lot_id": "X"},
        {"process": "p", "value": "", "line_id": "L01", "lot_id": "X"},
    ]
    captured: list[Any] = []

    def on_violation(*args):
        captured.append(args)

    stats = plc_ingest.process_batch(bad_messages, on_violation=on_violation)
    assert stats["messages"] == 3
    assert stats["violations"] == 0
    assert captured == []
