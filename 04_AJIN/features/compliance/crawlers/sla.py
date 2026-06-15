"""Feature D crawler SLA policy registry.

The registry is intentionally static and secret-safe: it records which
official source each crawler is expected to use and whether a credential must
be configured, but it never exposes credential values.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class CrawlerSlaPolicy:
    """Operational freshness policy for one compliance crawler.

    Args:
        crawler_name: Stable crawler key used by the API and audit table.
        result_file: JSON file written under ``data/crawled``.
        official_source: Primary official source URL or API endpoint.
        cadence: Human-readable expected monitoring cadence.
        max_stale_hours: Maximum acceptable age of the latest successful live
            result before the source is considered stale.
        fallback_allowed: Whether curated fallback data is allowed as a
            degraded operating mode.
        official_domain_allowlist: Accepted official citation domains.
        required_credential: Optional environment variable name required for
            live official-source access.
    """

    crawler_name: str
    result_file: str
    official_source: str
    cadence: str
    max_stale_hours: int
    fallback_allowed: bool
    official_domain_allowlist: tuple[str, ...]
    required_credential: str | None = None


CRAWLER_SLA_POLICIES: Mapping[str, CrawlerSlaPolicy] = MappingProxyType({
    "iso": CrawlerSlaPolicy(
        crawler_name="iso",
        result_file="iso_standards.json",
        official_source="https://www.iso.org/standard/62085.html",
        cadence="quarterly",
        max_stale_hours=24 * 120,
        fallback_allowed=True,
        official_domain_allowlist=("iso.org", "iatfglobaloversight.org"),
    ),
    "apqp": CrawlerSlaPolicy(
        crawler_name="apqp",
        result_file="apqp_process.json",
        official_source="https://go.aiag.org/apqp-cp",
        cadence="quarterly",
        max_stale_hours=24 * 120,
        fallback_allowed=True,
        official_domain_allowlist=("aiag.org",),
    ),
    "msds": CrawlerSlaPolicy(
        crawler_name="msds",
        result_file="msds_data.json",
        official_source="https://www.echa.europa.eu/en/candidate-list-table",
        cadence="weekly",
        max_stale_hours=24 * 7,
        fallback_allowed=True,
        official_domain_allowlist=("echa.europa.eu", "kosha.or.kr", "ncis.nier.go.kr"),
    ),
    "domestic_law": CrawlerSlaPolicy(
        crawler_name="domestic_law",
        result_file="domestic_laws.json",
        official_source="https://www.law.go.kr/DRF/lawSearch.do",
        cadence="daily",
        max_stale_hours=24,
        fallback_allowed=True,
        official_domain_allowlist=("law.go.kr", "open.law.go.kr"),
        required_credential="LAW_GO_KR_OC",
    ),
    "eu_regulation": CrawlerSlaPolicy(
        crawler_name="eu_regulation",
        result_file="eu_regulations.json",
        official_source="https://eur-lex.europa.eu/eli/reg/2023/1542/oj",
        cadence="weekly",
        max_stale_hours=24 * 7,
        fallback_allowed=True,
        official_domain_allowlist=("eur-lex.europa.eu", "ec.europa.eu"),
    ),
    "oem_quality": CrawlerSlaPolicy(
        crawler_name="oem_quality",
        result_file="oem_quality.json",
        official_source="https://www.aiag.org/expertise-areas/quality/quality-core-tools",
        cadence="on_change",
        max_stale_hours=24 * 30,
        fallback_allowed=True,
        official_domain_allowlist=("aiag.org", "suppliers.hyundai.com", "suppliers.mobis.co.kr"),
    ),
    "carbon_esg": CrawlerSlaPolicy(
        crawler_name="carbon_esg",
        result_file="carbon_esg.json",
        official_source="https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism_en",
        cadence="weekly",
        max_stale_hours=24 * 7,
        fallback_allowed=True,
        official_domain_allowlist=("taxation-customs.ec.europa.eu", "ifrs.org", "cdp.net"),
    ),
    "ev_battery": CrawlerSlaPolicy(
        crawler_name="ev_battery",
        result_file="ev_battery.json",
        official_source="https://docs.un.org/ECE/TRANS/WP.29/343/REV.30/ADD.2",
        cadence="quarterly",
        max_stale_hours=24 * 120,
        fallback_allowed=True,
        official_domain_allowlist=("unece.org", "docs.un.org", "documents.un.org"),
    ),
    "global_trade": CrawlerSlaPolicy(
        crawler_name="global_trade",
        result_file="global_trade.json",
        official_source="https://unipass.customs.go.kr:38010/ext/rest/trrtQry/retrieveTrrt",
        cadence="weekly",
        max_stale_hours=24 * 7,
        fallback_allowed=True,
        official_domain_allowlist=("unipass.customs.go.kr", "customs.go.kr", "fta.go.kr"),
        required_credential="CUSTOMS_API_KEY",
    ),
})


def missing_sla_policy_names(crawler_names: set[str]) -> list[str]:
    """Return crawler names that are not covered by the SLA registry.

    Args:
        crawler_names: Crawler keys that must have a policy.

    Returns:
        list[str]: Missing crawler keys sorted for stable test output.
    """

    return sorted(crawler_names - set(CRAWLER_SLA_POLICIES))
