"""v4.7 Sprint 2 P0 (축 ③) — SPC 위반 → 메일 초안 prefill 단위 테스트.

검증:
  1. spc_violations.db 스키마 초기화 + insert + get_by_id 라운드트립.
  2. enrich_violations 가 action_suggestions 컬럼을 추가한다.
  3. prefill_template('spc_violation', context_id) 가 subject/body 를 채운다.
  4. 메일 초안 발송 후 mark_draft_created 가 draft_created=1 로 표시한다.
"""

from __future__ import annotations

import importlib
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import pytest


@pytest.fixture()
def _isolated_db(monkeypatch: pytest.MonkeyPatch) -> Path:
    """spc_violations.db 를 임시 디렉토리로 격리."""
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "spc_violations.db"

    import features.equipment.spc_violations_db as mod

    monkeypatch.setattr(mod, "DB_PATH", db_path)
    return db_path


def test_init_db_creates_table(_isolated_db: Path) -> None:
    from features.equipment import spc_violations_db as mod

    mod.init_db()
    assert _isolated_db.exists()


def test_insert_and_get_by_id(_isolated_db: Path) -> None:
    from features.equipment import spc_violations_db as mod

    vid = mod.insert_violation(
        violation_id="v-001",
        process="F-Line",
        lot_id="LOT-2026-0501",
        rule_number=1,
        rule_name="Beyond 3σ",
        violating_count=2,
        severity="critical",
        recommended_action="즉시 생산 중지 → 특수 원인 조사",
        detected_at="2026-05-01T10:00:00+00:00",
        alarm_id="alarm-1",
    )
    assert vid == "v-001"

    row = mod.get_by_id("v-001")
    assert row is not None
    assert row["process"] == "F-Line"
    assert row["lot_id"] == "LOT-2026-0501"
    assert row["rule_number"] == 1
    assert row["severity"] == "critical"
    assert row["draft_created"] == 0
    assert row["data_class"] == "real"
    assert row["source_system"] == "plc_ingest"


def test_enrich_violations_adds_action_suggestions() -> None:
    from features.equipment.spc_realtime import NelsonViolation, enrich_violations

    v = NelsonViolation(
        rule_number=1,
        rule_name="Beyond 3σ",
        description="3σ 초과",
        violating_indices=[10, 12],
        severity="critical",
        recommended_action="즉시 점검",
    )
    enriched = enrich_violations([v])
    assert len(enriched) == 1
    assert "action_suggestions" in enriched[0]
    assert "mail_to_dept" in enriched[0]["action_suggestions"]
    assert "guide" in enriched[0]


def test_prefill_template_spc_violation(_isolated_db: Path) -> None:
    from features.equipment import spc_violations_db as svdb
    from features.draft.prefill_engine import prefill_template

    svdb.insert_violation(
        violation_id="v-002",
        process="E-Line",
        lot_id="LOT-2026-0510",
        rule_number=3,
        rule_name="Trend of 6",
        violating_count=6,
        severity="warning",
        recommended_action="공구 마모 점검",
        detected_at="2026-05-10T08:30:00+00:00",
    )

    payload = prefill_template("spc_violation", "v-002")
    assert payload is not None
    assert payload["subject"] == "[긴급] E-Line 라인 Nelson Rule 3 위반 — Lot LOT-2026-0510"
    assert "Nelson Rule 3 — Trend of 6" in payload["body"]
    assert "공구 마모 점검" in payload["body"]
    assert "v-002" in payload["body"]
    assert isinstance(payload["to"], list)
    assert isinstance(payload["cc"], list)


def test_prefill_template_missing_violation_returns_none(_isolated_db: Path) -> None:
    from features.draft.prefill_engine import prefill_template

    assert prefill_template("spc_violation", "nonexistent") is None


def test_prefill_template_unknown_id_returns_none() -> None:
    from features.draft.prefill_engine import prefill_template

    assert prefill_template("not_a_template", "x") is None


def test_mark_draft_created_updates_row(_isolated_db: Path) -> None:
    from features.equipment import spc_violations_db as mod

    mod.insert_violation(
        violation_id="v-003",
        process="F-Line",
        lot_id="LOT-X",
        rule_number=2,
        rule_name="Run of 9",
        violating_count=9,
        severity="warning",
        recommended_action="점검",
    )
    mod.mark_draft_created("v-003", draft_id="draft-7")
    row = mod.get_by_id("v-003")
    assert row is not None
    assert row["draft_created"] == 1
    assert row["draft_id"] == "draft-7"


def test_yaml_template_loaded_via_catalog() -> None:
    """find_template_by_id('spc_violation') 가 YAML 메타를 반환한다."""
    from features.draft.template_catalog import find_template_by_id

    meta = find_template_by_id("spc_violation")
    assert meta is not None
    assert meta.get("template_id") == "spc_violation"
    assert meta.get("category") == "incident_report"
    assert "subject_template" in meta
    assert "body_template" in meta
