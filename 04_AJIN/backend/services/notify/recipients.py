"""D2 — 알림 수신자 해석 (notification_preferences 조회 + 필터)."""
from __future__ import annotations

import json
from typing import Any

from backend.services.notify.base import _connect, ensure_tables, severity_meets_threshold


def resolve_recipients(change_row: dict[str, Any]) -> list[dict[str, Any]]:
    """변경 1건 → 수신자 prefs 리스트.

    필터 룰:
      - prefs.enabled == 1
      - severity (= grade) >= prefs.severity_threshold
      - prefs.plant_filter 가 비어있거나, change.affected_plants 와 교집합
      - prefs.department_filter 가 비어있거나, change.affected_departments 에 포함
    """
    ensure_tables()
    grade = (change_row.get("grade") or change_row.get("severity") or "MEDIUM").upper()

    affected_plants = change_row.get("affected_plants") or []
    if isinstance(affected_plants, str):
        try:
            affected_plants = json.loads(affected_plants)
        except Exception:
            affected_plants = [affected_plants]
    affected_depts = change_row.get("affected_departments") or []
    if isinstance(affected_depts, str):
        try:
            affected_depts = json.loads(affected_depts)
        except Exception:
            affected_depts = [affected_depts]

    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM notification_preferences WHERE enabled = 1"
        ).fetchall()
    finally:
        conn.close()

    out: list[dict[str, Any]] = []
    for r in rows:
        prefs = dict(r)
        if not severity_meets_threshold(grade, prefs.get("severity_threshold", "MEDIUM")):
            continue
        plant_filter_raw = prefs.get("plant_filter_json") or "[]"
        try:
            plant_filter = json.loads(plant_filter_raw)
        except Exception:
            plant_filter = []
        if plant_filter and affected_plants:
            if not (set(plant_filter) & set(affected_plants)):
                continue
        dept_filter = (prefs.get("department_filter") or "").strip()
        if dept_filter and affected_depts:
            if dept_filter not in affected_depts:
                continue
        out.append(prefs)
    return out
