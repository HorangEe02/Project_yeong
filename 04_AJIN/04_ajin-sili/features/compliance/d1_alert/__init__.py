"""Feature D D1 Alert — 변경 감지 + 알림 17 모듈 (MVP).

Sprint 1 P0 (plan §40): namespace re-export. 옛 경로 zero-touch.
- 6 active crawler (iso/msds/domestic_law/eu_regulation/ev_battery/global_trade/carbon_esg)
- base_crawler (폴백 메커니즘 — _curated_fallback)
- change_detector + 분류기 + alert/notify 파이프라인

Sprint 2 신규: review_workflow (인간 검토 게이트) 가 _common 에 추가됨.

v4.7 D mv: 파일 물리 이동 후 새 경로 (`features.compliance.<sub>`) 로 import.
"""

from features.compliance.crawlers import (
    base_crawler,
    crawler,
    iso_crawler,
    msds_crawler,
    domestic_law_crawler,
    eu_regulation_crawler,
    ev_battery_crawler,
    global_trade_crawler,
    carbon_esg_crawler,
)
from features.compliance.alerts import (
    change_detector,
    text_change_detector,
    regulation_classifier,
    change_classifier,
    alert_generator,
    notify,
    notify_slack,
    notify_sms,
)

__all__ = [
    "base_crawler", "crawler",
    "iso_crawler", "msds_crawler", "domestic_law_crawler",
    "eu_regulation_crawler", "ev_battery_crawler",
    "global_trade_crawler", "carbon_esg_crawler",
    "change_detector", "text_change_detector",
    "regulation_classifier", "change_classifier",
    "alert_generator", "notify", "notify_slack", "notify_sms",
]
