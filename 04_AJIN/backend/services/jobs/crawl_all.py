"""D3 job — 전체 크롤러 일괄 실행."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


_CRAWLERS = (
    ("iso", "features.compliance.iso_crawler", "ISOCrawler"),
    ("msds", "features.compliance.msds_crawler", "MSDSCrawler"),
    ("eu_regulation", "features.compliance.eu_regulation_crawler", "EuRegulationCrawler"),
    ("domestic_law", "features.compliance.domestic_law_crawler", "DomesticLawCrawler"),
    ("us_trade", "features.compliance.us_trade_crawler", "UsTradeCrawler"),
    ("apqp", "features.compliance.apqp_crawler", "ApqpCrawler"),
    ("oem_quality", "features.compliance.oem_quality_crawler", "OemQualityCrawler"),
    ("ev_battery", "features.compliance.ev_battery_crawler", "EvBatteryCrawler"),
    ("carbon_esg", "features.compliance.carbon_esg_crawler", "CarbonEsgCrawler"),
    ("global_trade", "features.compliance.global_trade_crawler", "GlobalTradeCrawler"),
)


def run() -> dict[str, Any]:
    """모든 크롤러를 순차 실행. mock 크롤러는 정적 JSON 로드, 실HTTP는 ISO/MSDS."""
    results: dict[str, Any] = {}
    for slug, mod_path, cls_name in _CRAWLERS:
        try:
            import importlib
            mod = importlib.import_module(mod_path)
            cls = getattr(mod, cls_name, None)
            if cls is None:
                results[slug] = {"ok": False, "error": f"{cls_name} not found"}
                continue
            inst = cls()
            res = inst.crawl() if hasattr(inst, "crawl") else None
            results[slug] = {"ok": True, "result_size": _size_hint(res)}
        except Exception as e:
            results[slug] = {"ok": False, "error": str(e)[:200]}
            logger.warning("crawler %s 실패: %s", slug, e)

    return {
        "ran": len(_CRAWLERS),
        "ok_count": sum(1 for v in results.values() if v.get("ok")),
        "results": results,
    }


def _size_hint(obj: Any) -> int:
    if obj is None:
        return 0
    try:
        return len(obj)  # type: ignore[arg-type]
    except Exception:
        return 1
