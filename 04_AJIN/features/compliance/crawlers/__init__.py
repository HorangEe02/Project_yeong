"""features.compliance.crawlers — v4.7 D mv 신 경로.

12 크롤러 모듈 + 베이스 + 시나리오 로더.
"""

from features.compliance.crawlers import (
    base_crawler,
    crawler,
    iso_crawler,
    apqp_crawler,
    msds_crawler,
    domestic_law_crawler,
    eu_regulation_crawler,
    ev_battery_crawler,
    global_trade_crawler,
    oem_quality_crawler,
    carbon_esg_crawler,
    us_trade_crawler,
)
from features.compliance.crawlers.base_crawler import BaseCrawler
from features.compliance.crawlers.crawler import (
    ScenarioLoader,
    LawCrawler,
    RegulationChange,
)
from features.compliance.crawlers.iso_crawler import ISOCrawler
from features.compliance.crawlers.apqp_crawler import APQPCrawler
from features.compliance.crawlers.msds_crawler import MSDSCrawler
from features.compliance.crawlers.domestic_law_crawler import DomesticLawCrawler
from features.compliance.crawlers.eu_regulation_crawler import EURegulationCrawler
from features.compliance.crawlers.ev_battery_crawler import EVBatteryCrawler
from features.compliance.crawlers.global_trade_crawler import GlobalTradeCrawler
from features.compliance.crawlers.oem_quality_crawler import OEMQualityCrawler
from features.compliance.crawlers.carbon_esg_crawler import CarbonESGCrawler

__all__ = [
    "base_crawler", "crawler",
    "iso_crawler", "apqp_crawler", "msds_crawler",
    "domestic_law_crawler", "eu_regulation_crawler",
    "ev_battery_crawler", "global_trade_crawler",
    "oem_quality_crawler", "carbon_esg_crawler", "us_trade_crawler",
    "BaseCrawler",
    "ScenarioLoader", "LawCrawler", "RegulationChange",
    "ISOCrawler", "APQPCrawler", "MSDSCrawler",
    "DomesticLawCrawler", "EURegulationCrawler",
    "EVBatteryCrawler", "GlobalTradeCrawler",
    "OEMQualityCrawler", "CarbonESGCrawler",
]
