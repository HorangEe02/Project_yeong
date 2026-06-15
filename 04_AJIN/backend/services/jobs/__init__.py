"""D3 — Celery 잡 모듈 (동기 호출 + Celery task 양쪽에서 동일 동작).

sync trigger:
    backend.services.jobs.trigger_job(<id>)

Celery task:
    celery -A backend.celery_app 가 import 하여 4 task 등록.
"""
from __future__ import annotations

from typing import Any


_CRAWL_STAGGER = {
    "iso": 0, "apqp": 5, "msds": 10, "domestic_law": 15, "eu_regulation": 20,
    "oem_quality": 25, "carbon_esg": 30, "ev_battery": 35, "global_trade": 40,
}

JOBS = (
    {"id": "crawl_all", "cron": "manual / api",
     "description": "9 크롤러 일괄 실행 — 수동 트리거"},
    *(
        {
            "id": f"crawl_{name}",
            "cron": f"0 2:{offset:02d} * * mon-fri (KST)",
            "description": f"{name} 크롤러 — F10 stagger",
        }
        for name, offset in _CRAWL_STAGGER.items()
    ),
    {"id": "digest_daily", "cron": "0 * * * mon-fri",
     "description": "사용자 digest_hour_kst 매칭 시 다이제스트 큐잉"},
    {"id": "dispatch_outbox", "cron": "*/2 * * * *",
     "description": "outbox 대기 메시지 발송 (2분마다)"},
    {"id": "fts_reindex", "cron": "0 3 * * *",
     "description": "D1 FTS5 인덱스 일일 재구축"},
)


def list_jobs() -> list[dict[str, Any]]:
    return list(JOBS)


def trigger_job(job_id: str) -> dict[str, Any]:
    """API 에서 호출하는 동기 트리거 — Celery 미설치 환경에서도 동작."""
    if job_id == "crawl_all":
        from backend.services.jobs.crawl_all import run
        return run()
    if job_id.startswith("crawl_") and job_id[6:] in _CRAWL_STAGGER:
        from backend.services.jobs.crawl_one import run
        return run(job_id[6:], trigger_source="api_trigger")
    if job_id == "digest_daily":
        from backend.services.jobs.digest import run
        return run(force_all_users=True)
    if job_id == "dispatch_outbox":
        from backend.services.jobs.dispatch_outbox import run
        return run()
    if job_id == "fts_reindex":
        from backend.services.jobs.fts_reindex import run
        return run()
    raise ValueError(f"알 수 없는 job_id: {job_id}")
