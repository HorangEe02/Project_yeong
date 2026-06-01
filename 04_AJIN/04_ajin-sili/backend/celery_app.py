"""D3 — Celery 애플리케이션 정의 + Beat 스케줄.

기동 (별도 프로세스, FastAPI 와 무관):
    celery -A backend.celery_app worker --beat -l info
    celery -A backend.celery_app flower --port=5555

Broker/Backend: Redis (REDIS_URL env, default redis://localhost:6379/0)

이 모듈은 Celery 워커 프로세스만 import 한다. FastAPI 앱은 import 하지 않으므로
celery 패키지 미설치 환경에서 FastAPI 기동에는 영향이 없다.
API 라우터는 backend.services.jobs 의 sync trigger 를 사용.
"""
from __future__ import annotations

import os
from typing import Any

from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "ajin_compliance",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.celery_app"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Seoul",
    enable_utc=False,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# Beat 스케줄 — 평일 KST.
# F10 — 9 크롤러를 02:00~02:40 KST 5분 간격으로 분산. 외부 사이트 동시 hit 회피.
_CRAWL_STAGGER_MIN = {
    "iso": 0, "apqp": 5, "msds": 10, "domestic_law": 15, "eu_regulation": 20,
    "oem_quality": 25, "carbon_esg": 30, "ev_battery": 35, "global_trade": 40,
}

_per_crawler_schedule = {
    f"crawl_{name}": {
        "task": f"ajin.jobs.crawl_one.{name}",
        "schedule": crontab(hour=2, minute=offset, day_of_week="mon-fri"),
    }
    for name, offset in _CRAWL_STAGGER_MIN.items()
}

celery_app.conf.beat_schedule = {
    # F10 — per-crawler stagger (default).
    **_per_crawler_schedule,
    # 수동 트리거 / 단일 호출용 (beat 비활성).
    "digest_daily": {
        "task": "ajin.jobs.digest",
        "schedule": crontab(minute=0, day_of_week="mon-fri"),
    },
    "dispatch_outbox": {
        "task": "ajin.jobs.dispatch_outbox",
        "schedule": crontab(minute="*/2"),
    },
    "fts_reindex": {
        "task": "ajin.jobs.fts_reindex",
        "schedule": crontab(hour=3, minute=0),
    },
    # 부록 6 P4-1+P4-3 — draft history 부서/개인 aggregation (매일 04:00 KST)
    "draft_dept_aggregate": {
        "task": "ajin.jobs.draft_dept_aggregate",
        "schedule": crontab(hour=4, minute=0),
    },
    # v4.2 P4 — D 컴플라이언스 시나리오 영향점수 일일 재계산 (03:15 KST, fts_reindex 직후)
    "compliance_scenario_scores": {
        "task": "ajin.jobs.compliance_scenario_scores",
        "schedule": crontab(hour=3, minute=15),
    },
    # v4.x — D 컴플라이언스 알람 RTDB dispatch (매 5분).
    # alarm_aggregator.collect_recent_alarms → firebase_rtdb.push_alarm 체인.
    # F SPC 와 같은 /live_alarms path 공유 + module="D" 필드로 구분.
    # frontend useComplianceRTDB 가 module=D 필터로 구독.
    "compliance_alarm_dispatch": {
        "task": "ajin.jobs.compliance_alarm_dispatch",
        "schedule": crontab(minute="*/5"),
    },
    # v4.7 C-4 — 게이미피케이션 배지 일괄 평가 (streak/누적 배지)
    "gamification_daily_eval": {
        "task": "ajin.jobs.gamification_daily_eval",
        "schedule": crontab(hour=6, minute=0),
    },
    # v4.7 C-4 — 주간 부서 리더보드 스냅샷 (월요일 06:00)
    "gamification_weekly_leaderboard": {
        "task": "ajin.jobs.gamification_weekly_leaderboard",
        "schedule": crontab(hour=6, minute=0, day_of_week="mon"),
    },
    # v4.7 C-4 — 월간 부서 1위 (department_pioneer) — 매월 말일 23:00 근접 (Celery 의 last-day-of-month)
    "gamification_monthly_pioneer": {
        "task": "ajin.jobs.gamification_monthly_pioneer",
        "schedule": crontab(hour=23, minute=0, day_of_month="28-31"),
    },
    # v4.7 PR-E2 — 야간 user_cache 정합성 검증 (compliance crawler 02:00 직전)
    "user_cache_nightly_reconcile": {
        "task": "ajin.jobs.user_cache.reconcile",
        "schedule": crontab(hour=1, minute=30, day_of_week="mon-fri"),
    },
    # v4.7 PR-E7 — 권한 변경 결재 24h+ escalation (매 4 시간)
    "permission_escalation_check": {
        "task": "ajin.jobs.permission.escalation",
        "schedule": crontab(minute=0, hour="*/4"),
    },
    # Postmortem 2026-05-27 — compliance.db 일일 백업 (04:30 KST, fts_reindex 03:00 직후).
    # data/compliance.db 가 SQLite 가 아닌 손상 데이터로 변형된 incident 의 재발 방지 sink.
    "compliance_db_backup_daily": {
        "task": "ajin.jobs.compliance_db_backup",
        "schedule": crontab(hour=4, minute=30),
    },
}


@celery_app.task(name="ajin.jobs.crawl_all")
def t_crawl_all() -> dict[str, Any]:
    from backend.services.jobs.crawl_all import run
    return run()


# F10 — per-crawler tasks. 각 task 가 단일 크롤러를 cron 시각에 트리거.
def _make_crawl_task(crawler_name: str):
    def _t() -> dict[str, Any]:
        from backend.services.jobs.crawl_one import run
        return run(crawler_name, trigger_source="cron")
    # __name__은 데코레이터 적용 전에 raw 함수에 설정 (Celery Task 인스턴스에는 setter 없음)
    _t.__name__ = f"t_crawl_{crawler_name}"
    return celery_app.task(name=f"ajin.jobs.crawl_one.{crawler_name}")(_t)


for _cn in _CRAWL_STAGGER_MIN.keys():
    _make_crawl_task(_cn)


@celery_app.task(name="ajin.jobs.digest")
def t_digest() -> dict[str, Any]:
    from backend.services.jobs.digest import run
    return run(force_all_users=False)


@celery_app.task(name="ajin.jobs.dispatch_outbox")
def t_dispatch_outbox() -> dict[str, Any]:
    from backend.services.jobs.dispatch_outbox import run
    return run()


@celery_app.task(name="ajin.jobs.fts_reindex")
def t_fts_reindex() -> dict[str, int]:
    from backend.services.jobs.fts_reindex import run
    return run()


@celery_app.task(name="ajin.jobs.draft_dept_aggregate")
def t_draft_dept_aggregate() -> dict[str, Any]:
    """부록 6 P4-1+P4-3 — Firestore draft history → SQLite aggregation."""
    from backend.services.draft_dept_agg import run_aggregation
    return run_aggregation()


@celery_app.task(name="ajin.jobs.compliance_scenario_scores")
def t_compliance_scenario_scores() -> dict[str, Any]:
    """v4.2 P4 — D 알람 소스 2 (impact_score) 캐시 재계산.

    매일 03:15 KST 실행 (fts_reindex 03:00 직후). 1h TTL 보다 짧은 일관 갱신.
    수동 트리거는 POST /api/compliance/alarms/refresh-scenario-scores (role≥5).
    """
    from features.compliance.alarm_aggregator import refresh_all_scenario_scores
    return refresh_all_scenario_scores()


@celery_app.task(name="ajin.jobs.compliance_alarm_dispatch")
def t_compliance_alarm_dispatch() -> dict[str, Any]:
    """v4.x — D 컴플라이언스 알람을 firebase_rtdb /live_alarms 로 dispatch.

    alarm_aggregator.collect_recent_alarms() 의 5종 source 통합 결과를
    `push_alarm()` 으로 RTDB push. F SPC 알람과 동일 통로 + `module="D"` 구분.
    dedup state(`data/_d1_alert_rtdb_pushed.db`) 로 중복 push 방지.
    """
    from features.compliance.d1_alert.pipeline import dispatch_compliance_alarms_to_rtdb
    return dispatch_compliance_alarms_to_rtdb()


# v4.7 C-4 — 게이미피케이션 작업들 ────────────────────────────────────────────
@celery_app.task(name="ajin.jobs.gamification_daily_eval")
def t_gamification_daily_eval() -> dict[str, Any]:
    from backend.services.jobs.gamification_jobs import run_daily_eval
    return run_daily_eval()


@celery_app.task(name="ajin.jobs.gamification_weekly_leaderboard")
def t_gamification_weekly_leaderboard() -> dict[str, Any]:
    from backend.services.jobs.gamification_jobs import run_weekly_leaderboard
    return run_weekly_leaderboard()


@celery_app.task(name="ajin.jobs.gamification_monthly_pioneer")
def t_gamification_monthly_pioneer() -> dict[str, Any]:
    from backend.services.jobs.gamification_jobs import run_monthly_pioneer
    return run_monthly_pioneer()


# v4.7 PR-E2 — user_cache 야간 reconcile ─────────────────────────────────────
@celery_app.task(name="ajin.jobs.user_cache.reconcile")
def t_user_cache_reconcile() -> dict[str, int]:
    """IdP 와 캐시 mismatch 검출 (야간). IDP_PROVIDER=disabled 시 no-op."""
    from backend.services.jobs.user_cache_reconcile import run_reconcile
    return run_reconcile()


# v4.7 PR-E7 — 권한 변경 결재 escalation ────────────────────────────────────
@celery_app.task(name="ajin.jobs.permission.escalation")
def t_permission_escalation() -> dict[str, Any]:
    """24h+ pending 권한 변경 요청 알림 (매 4 시간)."""
    from backend.services.jobs.permission_escalation_job import run_escalation
    return run_escalation()


# Postmortem 2026-05-27 — compliance.db 일일 백업 ────────────────────────────
@celery_app.task(name="ajin.jobs.compliance_db_backup")
def t_compliance_db_backup() -> dict[str, Any]:
    """data/compliance.db SQLite Online Backup API atomic dump + 7일 보존.

    2026-05-27 incident (compliance.db 파일 손상으로 D 모듈 500) 의 재발 방지
    sink. data/backup/compliance.db.YYYYMMDD 생성, 무결성 quick_check 후
    7일 이상 오래된 파일 정리.
    """
    from backend.services.jobs.compliance_db_backup import run
    return run()
