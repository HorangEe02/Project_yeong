"""F10 — 단일 크롤러 잡 헬퍼.

D3 Celery beat 가 9 크롤러를 5분 간격으로 스태거 호출할 때 각 cron 슬롯이
이 함수를 통해 단일 크롤러를 실행한다. crawl_audit 자동 기록 + http_meta 보장.

페르소나 가치:
- 시니어: 외부 사이트(ECHA/USTR/UNECE) 동시 hit 회피 → 차단 클레임 ↓
- 신입: cron 스케줄이 보이는 학습 자료 — 02:00~02:40 KST 9개가 차례로 돈다
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


def run(crawler_name: str, trigger_source: str = "cron") -> dict[str, Any]:
    """단일 크롤러를 sync 컨텍스트에서 실행 (Celery worker 용)."""
    from backend.routers.compliance import _run_one_crawler, _CRAWLER_KEYS

    if crawler_name not in _CRAWLER_KEYS:
        logger.warning("unknown crawler: %s", crawler_name)
        return {"name": crawler_name, "error": "unknown_crawler"}

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            res = loop.run_until_complete(
                _run_one_crawler(crawler_name, trigger_source=trigger_source)
            )
        finally:
            loop.close()
        return {
            "name": res.name,
            "ok": not res.errors,
            "updates_found": res.updates_found or 0,
            "errors": res.errors or [],
        }
    except Exception as e:
        logger.exception("crawl_one.run failed (%s): %s", crawler_name, e)
        return {"name": crawler_name, "error": str(e)[:200]}
