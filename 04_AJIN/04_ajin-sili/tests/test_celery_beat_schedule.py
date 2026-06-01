"""Celery beat 스케줄 — entry 등록 단위 테스트 (v4.2 P5).

celery_app 모듈 import 만으로 beat_schedule dict 의 entry 가 올바르게 정의되었는지 확인.
실제 Celery worker 가동 없이 검증 가능.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_compliance_scenario_scores_schedule_registered():
    """v4.2 P4 — 03:15 KST 일일 갱신 entry 검증."""
    from backend.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    assert "compliance_scenario_scores" in schedule, (
        "compliance_scenario_scores beat entry 가 등록되지 않음"
    )

    entry = schedule["compliance_scenario_scores"]
    assert entry["task"] == "ajin.jobs.compliance_scenario_scores"

    cron = entry["schedule"]
    # crontab(hour=3, minute=15) — _orig_hour / _orig_minute 또는 hour/minute 속성
    assert getattr(cron, "hour", None) == {3}, f"hour={cron.hour}"
    assert getattr(cron, "minute", None) == {15}, f"minute={cron.minute}"


def test_compliance_scenario_scores_task_callable():
    """Celery task 가 호출 가능한 함수로 등록되어 있는지 확인."""
    from backend.celery_app import celery_app, t_compliance_scenario_scores

    assert callable(t_compliance_scenario_scores)
    # Celery 가 task 등록을 했는지
    tasks = celery_app.tasks
    assert "ajin.jobs.compliance_scenario_scores" in tasks


def test_schedule_does_not_collide_with_existing():
    """다른 beat entry 와 시간 충돌이 없는지 (단일 분 단위 비교)."""
    from backend.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    target = schedule["compliance_scenario_scores"]["schedule"]
    target_hm = (sorted(target.hour)[0], sorted(target.minute)[0])

    collisions = []
    for name, entry in schedule.items():
        if name == "compliance_scenario_scores":
            continue
        cron = entry["schedule"]
        if not (hasattr(cron, "hour") and hasattr(cron, "minute")):
            continue
        hours = sorted(cron.hour) if cron.hour else []
        minutes = sorted(cron.minute) if cron.minute else []
        if not hours or not minutes:
            continue
        # 우리 시각과 모든 hour/minute 가 같은 경우만 충돌
        if target_hm in {(h, m) for h in hours for m in minutes}:
            collisions.append(name)
    assert not collisions, f"03:15 충돌: {collisions}"
