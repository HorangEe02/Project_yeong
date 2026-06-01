#!/usr/bin/env python3
"""Verify Feature D compliance monitoring release posture.

The verifier is secret-safe. It checks the currently generated D1 API surface,
official-source live reachability, crawler citation posture, D2-D5 rollout
flags, and notification scheduler wiring without printing API keys.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from features.compliance.alerts.legal_guard import COMPLIANCE_AI_DISCLAIMER
from features.compliance.crawlers.sla import CRAWLER_SLA_POLICIES

DOC_REFERENCES = (
    "https://open.law.go.kr/LSO/openApi/guideList.do",
    "https://open.law.go.kr/LSO/openApi/guideResult.do",
    "https://unipass.customs.go.kr/per/index.do",
    "https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html?locale=en",
    "https://www.echa.europa.eu/en/candidate-list-table",
    "https://echa.europa.eu/en/candidate-list-package",
    "https://unece.org/wp29-introduction",
    "https://unece.org/transport/vehicle-regulations/faq",
    "https://docs.un.org/ECE/TRANS/WP.29/343/REV.30/ADD.2",
    "https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019002",
    "https://api.slack.com/messaging/webhooks",
    "https://www.twilio.com/docs/sms/api",
    "https://api.ncloud-docs.com/docs/en/sens-overview",
    "https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html",
)

BROWSER_COMPATIBLE_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
CLIENT_PROFILE_CRAWLER = "crawler"
CLIENT_PROFILE_BROWSER_COMPATIBLE = "browser_compatible"
HTTP_METHODS = {"get", "put", "post", "delete", "patch", "options", "head"}
EXPECTED_ENDPOINT_COUNTS = {"compliance": 19, "notifications": 6}
EXPECTED_DEFAULT_D_FLAGS = {
    "d1_alerts": True,
    "d2_rag": False,
    "d3_whatif": False,
    "d4_workflow": False,
    "d5_supply": False,
}
FEATURE_D_ENV_KEYS = (
    "FEATURE_D_D1_ALERTS",
    "FEATURE_D_D2_RAG",
    "FEATURE_D_D3_WHATIF",
    "FEATURE_D_D4_WORKFLOW",
    "FEATURE_D_D5_SUPPLY",
)
D2_D5_ROLLOUT_STAGES = ("d1", "d2", "d3", "d4", "d5")
D2_D5_STAGE_FLAGS = {
    "d1": (),
    "d2": ("d2_rag",),
    "d3": ("d2_rag", "d3_whatif"),
    "d4": ("d2_rag", "d3_whatif", "d4_workflow"),
    "d5": ("d2_rag", "d3_whatif", "d4_workflow", "d5_supply"),
}
D2_D5_FLAG_TO_ENV = {
    "d2_rag": "FEATURE_D_D2_RAG",
    "d3_whatif": "FEATURE_D_D3_WHATIF",
    "d4_workflow": "FEATURE_D_D4_WORKFLOW",
    "d5_supply": "FEATURE_D_D5_SUPPLY",
}
D2_D5_SMOKE_ROUTES = {
    "d2_rag": "/api/compliance/glossary",
    "d3_whatif": "/api/compliance/risk/scores",
    "d4_workflow": "/api/compliance/tickets",
    "d5_supply": "/api/compliance/suppliers",
}
REQUIRED_COMPLIANCE_ENDPOINTS: Mapping[str, set[str]] = {
    "/api/compliance/facilities": {"get"},
    "/api/compliance/changes/recent": {"get"},
    "/api/compliance/changes/feed": {"get"},
    "/api/compliance/changes/{change_id}/acknowledge": {"post"},
    "/api/compliance/changes/{change_id}/transition": {"post"},
    "/api/compliance/changes/kpi": {"get"},
    "/api/compliance/crawl/run/{name}": {"post"},
    "/api/compliance/crawl/run-all": {"post"},
    "/api/compliance/crawl/history": {"get"},
    "/api/compliance/crawl/history/stats": {"get"},
    "/api/compliance/crawl/results": {"get"},
    "/api/compliance/crawl/results/{name}/download": {"get"},
    "/api/compliance/crawl/results/{name}": {"get"},
    "/api/compliance/scheduler/jobs": {"get"},
    "/api/compliance/scheduler/trigger/{job_id}": {"post"},
    "/api/compliance/digest/run-now": {"post"},
    "/api/compliance/alarms/recent": {"get"},
    "/api/compliance/alarms/{alarm_id}/ack": {"post"},
    "/api/compliance/alarms/stream": {"get"},
}
REQUIRED_NOTIFICATION_ENDPOINTS: Mapping[str, set[str]] = {
    "/api/notifications/me": {"get", "put"},
    "/api/notifications/test": {"post"},
    "/api/notifications/dispatch": {"post"},
    "/api/notifications/channels": {"get"},
    "/api/notifications/log": {"get"},
}
CRAWLER_RESULT_FILES = {
    "iso": "iso_standards.json",
    "apqp": "apqp_process.json",
    "msds": "msds_data.json",
    "domestic_law": "domestic_laws.json",
    "eu_regulation": "eu_regulations.json",
    "oem_quality": "oem_quality.json",
    "carbon_esg": "carbon_esg.json",
    "ev_battery": "ev_battery.json",
    "global_trade": "global_trade.json",
}
CRAWLER_ITEM_FIELDS = {
    "iso": ("standards", "data"),
    "apqp": ("phases", "data"),
    "msds": ("chemicals", "records", "data"),
    "domestic_law": ("laws", "data"),
    "eu_regulation": ("regulations", "data"),
    "oem_quality": ("standards", "data"),
    "carbon_esg": ("regulations", "data"),
    "ev_battery": ("regulations", "data"),
    "global_trade": ("regulations", "data"),
}
OFFICIAL_DOMAINS = {
    "aiag.org",
    "api.odcloud.kr",
    "cbp.gov",
    "cdp.net",
    "chinesestandard.net",
    "customs.go.kr",
    "docs.un.org",
    "documents.un.org",
    "echa.europa.eu",
    "ec.europa.eu",
    "epa.gov",
    "eur-lex.europa.eu",
    "fta.go.kr",
    "fsb-tcfd.org",
    "gm.com",
    "iatfglobaloversight.org",
    "ifrs.org",
    "irs.gov",
    "iso.org",
    "kosha.or.kr",
    "law.go.kr",
    "mee.gov.cn",
    "miit.gov.cn",
    "motie.go.kr",
    "ncis.nier.go.kr",
    "opendart.fss.or.kr",
    "sae.org",
    "sciencebasedtargets.org",
    "suppliers.hyundai.com",
    "suppliers.mobis.co.kr",
    "taxation-customs.ec.europa.eu",
    "unece.org",
    "unipass.customs.go.kr",
    "ustr.gov",
    "webshop.vda.de",
    "webstore.iec.ch",
    "vwgroupsupply.com",
}


@dataclass(frozen=True)
class CheckResult:
    """Single Feature D release check result.

    Args:
        name: Stable machine-readable check name.
        status: One of pass, warn, fail, or skip.
        summary: Human-readable secret-safe summary.
        details: Optional secret-safe metadata.
    """

    name: str
    status: str
    summary: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable check.

        Returns:
            dict[str, Any]: Result fields for reports.
        """

        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class FeatureDConfig:
    """Runtime configuration for the Feature D verifier.

    Args:
        root: Repository root.
        openapi_path: OpenAPI JSON path.
        strict: Whether fail checks should return a non-zero exit code.
        timeout_sec: HTTP timeout for official-source probes.
        retries: Number of probe attempts per source.
        allow_d2_d5: Whether D2-D5 enabled flags are acceptable for this run.
        rollout_stage: Highest D2-D5 stage allowed for this verification run.
    """

    root: Path = ROOT
    openapi_path: Path = ROOT / "docs" / "openapi.json"
    strict: bool = False
    timeout_sec: float = 8.0
    retries: int = 1
    allow_d2_d5: bool = False
    rollout_stage: str = "d1"


@dataclass(frozen=True)
class OfficialProbe:
    """Official source probe definition.

    Args:
        name: Crawler or source name.
        url: Primary public URL or API endpoint.
        official_domain: Expected official domain for the primary URL.
        fallback_urls: Additional official URLs to try after the primary URL.
        official_domains: Additional allowed official domains for fallbacks.
        credential_env: Optional required credential environment variable.
        credential_param: Query parameter name used for the credential.
        params: Non-secret query parameters for API probes.
        only_when_d2_d5_allowed: Whether this probe applies only in D5-enabled runs.
        min_rollout_stage: Minimum rollout stage required before the probe is active.
        prefer_get: Whether GET should run before HEAD for official sites that
            reject HEAD requests.
        client_profiles: HTTP client profiles to try in order.
    """

    name: str
    url: str
    official_domain: str
    fallback_urls: Sequence[str] = field(default_factory=tuple)
    official_domains: Sequence[str] = field(default_factory=tuple)
    credential_env: str = ""
    credential_param: str = ""
    params: Mapping[str, str] = field(default_factory=dict)
    only_when_d2_d5_allowed: bool = False
    min_rollout_stage: str = "d1"
    prefer_get: bool = False
    client_profiles: Sequence[str] = (CLIENT_PROFILE_CRAWLER,)


@dataclass(frozen=True)
class ProbeOutcome:
    """HTTP probe outcome with secret-safe metadata.

    Args:
        name: Source name.
        status: pass or fail.
        url: Secret-redacted URL.
        http_status: HTTP status code when available.
        method: HTTP method that returned the result.
        etag: Response ETag when available.
        last_modified: Response Last-Modified when available.
        primary_http_status: HTTP status from the primary URL/profile attempt.
        winning_url: URL that satisfied the probe when fallback succeeded.
        client_profile: HTTP client profile used for the final outcome.
        error: Secret-safe error label.
    """

    name: str
    status: str
    url: str
    http_status: int | None = None
    method: str = ""
    etag: str = ""
    last_modified: str = ""
    primary_http_status: int | None = None
    winning_url: str = ""
    client_profile: str = CLIENT_PROFILE_CRAWLER
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable probe result.

        Returns:
            dict[str, Any]: Probe metadata for reports.
        """

        return {
            "name": self.name,
            "status": self.status,
            "url": self.url,
            "http_status": self.http_status,
            "method": self.method,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "primary_http_status": self.primary_http_status,
            "winning_url": self.winning_url or self.url,
            "client_profile": self.client_profile,
            "error": self.error,
        }


OFFICIAL_PROBES = (
    OfficialProbe(
        name="iso",
        url="https://www.iso.org/standard/62085.html",
        official_domain="iso.org",
    ),
    OfficialProbe(
        name="apqp",
        url="https://go.aiag.org/apqp-cp",
        official_domain="aiag.org",
        prefer_get=True,
    ),
    OfficialProbe(
        name="msds",
        url="https://www.echa.europa.eu/web/guest/candidate-list-table",
        official_domain="echa.europa.eu",
        fallback_urls=(
            "https://www.echa.europa.eu/en/candidate-list-table",
            "https://echa.europa.eu/en/candidate-list-package",
        ),
        prefer_get=True,
        client_profiles=(CLIENT_PROFILE_CRAWLER, CLIENT_PROFILE_BROWSER_COMPATIBLE),
    ),
    OfficialProbe(
        name="domestic_law",
        url="https://www.law.go.kr/DRF/lawSearch.do",
        official_domain="law.go.kr",
        credential_env="LAW_GO_KR_OC",
        credential_param="OC",
        params={
            "target": "law",
            "type": "JSON",
            "query": "산업안전보건법",
            "display": "1",
        },
        prefer_get=True,
    ),
    OfficialProbe(
        name="eu_regulation",
        url="https://eur-lex.europa.eu/eli/reg/2023/1542/oj",
        official_domain="eur-lex.europa.eu",
    ),
    OfficialProbe(
        name="oem_quality",
        url="https://www.aiag.org/expertise-areas/quality/quality-core-tools",
        official_domain="aiag.org",
        prefer_get=True,
    ),
    OfficialProbe(
        name="carbon_esg",
        url="https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism_en",
        official_domain="taxation-customs.ec.europa.eu",
    ),
    OfficialProbe(
        name="ev_battery",
        url="https://unece.org/trans/main/welcwp29.html",
        official_domain="unece.org",
        fallback_urls=(
            "https://docs.un.org/ECE/TRANS/WP.29/343/REV.30/ADD.2",
            "https://documents.un.org/api/symbol/access?l=en&s=ECE%2FTRANS%2FWP.29%2F343%2FREV.30%2FADD.2&t=pdf",
        ),
        official_domains=("docs.un.org", "documents.un.org"),
        prefer_get=True,
    ),
    OfficialProbe(
        name="global_trade",
        url="https://unipass.customs.go.kr:38010/ext/rest/trrtQry/retrieveTrrt",
        official_domain="unipass.customs.go.kr",
        credential_env="CUSTOMS_API_KEY",
        credential_param="crkyCn",
        params={"hsSgn": "8708"},
        prefer_get=True,
    ),
    OfficialProbe(
        name="dart_d5_supply",
        url="https://opendart.fss.or.kr/api/list.json",
        official_domain="opendart.fss.or.kr",
        credential_env="DART_API_KEY",
        credential_param="crtfc_key",
        params={"corp_code": "00126308", "bgn_de": "20260101", "end_de": "20260520", "page_count": "10"},
        only_when_d2_d5_allowed=True,
        min_rollout_stage="d5",
        prefer_get=True,
    ),
)


def _truthy(value: str | None) -> bool:
    """Return whether an environment string is truthy.

    Args:
        value: Environment value.

    Returns:
        bool: True for common truthy forms.
    """

    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _stage_rank(stage: str) -> int:
    """Return a comparable Feature D rollout stage rank.

    Args:
        stage: Rollout stage name.

    Returns:
        int: Rank from D1 to D5. Unknown stages fail closed to D1.
    """

    try:
        return D2_D5_ROLLOUT_STAGES.index(stage)
    except ValueError:
        return 0


def _flags_for_stage(stage: str) -> set[str]:
    """Return Feature D subgroup flags enabled by a rollout stage.

    Args:
        stage: Rollout stage name.

    Returns:
        set[str]: Feature flag names such as ``d2_rag``.
    """

    return set(D2_D5_STAGE_FLAGS.get(stage, ()))


def _display_path(root: Path, path: Path) -> str:
    """Return a repository-relative path when possible.

    Args:
        root: Repository root.
        path: Path to display.

    Returns:
        str: Secret-safe display path.
    """

    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


@contextmanager
def _temporary_env(updates: Mapping[str, str | None]) -> Iterator[None]:
    """Temporarily update environment variables.

    Args:
        updates: Environment variable updates. ``None`` unsets a variable.

    Yields:
        None: Control while the temporary environment is active.
    """

    old_values = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _load_release_dotenv(root: Path) -> bool:
    """Load a local release dotenv file without printing values.

    Args:
        root: Repository root.

    Returns:
        bool: True when a dotenv file was loaded.
    """

    loaded = False
    for name in (".env.feature-d.local", ".env.supabase.local", ".env.local", ".env"):
        path = root / name
        if not path.exists():
            continue
        loaded = True
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    return loaded


def _load_openapi(path: Path) -> Mapping[str, Any]:
    """Load OpenAPI JSON.

    Args:
        path: OpenAPI JSON path.

    Returns:
        Mapping[str, Any]: Parsed OpenAPI document.

    Raises:
        FileNotFoundError: If the OpenAPI file is missing.
        json.JSONDecodeError: If JSON parsing fails.
    """

    return json.loads(path.read_text(encoding="utf-8"))


def _endpoint_methods(openapi: Mapping[str, Any], path: str) -> set[str]:
    """Return HTTP methods exposed for an OpenAPI path.

    Args:
        openapi: OpenAPI document.
        path: Path key.

    Returns:
        set[str]: Lowercase method names.
    """

    item = openapi.get("paths", {}).get(path, {})
    if not isinstance(item, Mapping):
        return set()
    return {method for method in item if method.lower() in HTTP_METHODS}


def _count_endpoints(openapi: Mapping[str, Any], prefix: str) -> int:
    """Count path-method operations under a prefix.

    Args:
        openapi: OpenAPI document.
        prefix: Path prefix to count.

    Returns:
        int: Number of HTTP operations, not just path keys.
    """

    total = 0
    for path in openapi.get("paths", {}):
        if path.startswith(prefix):
            total += len(_endpoint_methods(openapi, path))
    return total


def verify_endpoint_surface(config: FeatureDConfig) -> CheckResult:
    """Verify D1 OpenAPI endpoint surface and feature flag endpoint.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Endpoint surface posture.
    """

    try:
        openapi = _load_openapi(config.openapi_path)
    except Exception as exc:
        return CheckResult(
            "endpoint_surface",
            "fail",
            "OpenAPI document could not be loaded",
            {"error": type(exc).__name__, "path": _display_path(config.root, config.openapi_path)},
        )

    compliance_count = _count_endpoints(openapi, "/api/compliance/")
    notifications_count = _count_endpoints(openapi, "/api/notifications/")
    counts = {"compliance": compliance_count, "notifications": notifications_count}
    missing_counts = {
        key: {"expected": expected, "actual": counts.get(key, 0)}
        for key, expected in EXPECTED_ENDPOINT_COUNTS.items()
        if counts.get(key, 0) != expected
    }

    missing_required: dict[str, list[str]] = {}
    for path, required_methods in {
        **REQUIRED_COMPLIANCE_ENDPOINTS,
        **REQUIRED_NOTIFICATION_ENDPOINTS,
        "/api/feature-flags/d": {"get"},
    }.items():
        exposed = _endpoint_methods(openapi, path)
        missing = sorted(required_methods - exposed)
        if missing:
            missing_required[path] = missing

    details = {
        "counts": counts,
        "expected_counts": dict(EXPECTED_ENDPOINT_COUNTS),
        "missing_counts": missing_counts,
        "missing_required": missing_required,
    }
    if missing_counts or missing_required:
        return CheckResult(
            "endpoint_surface",
            "fail",
            "Feature D D1 OpenAPI surface is incomplete or has unexpected counts",
            details,
        )
    return CheckResult(
        "endpoint_surface",
        "pass",
        "Feature D exposes 19 compliance, 6 notification, and /feature-flags/d endpoints",
        details,
    )


def _probe_url(probe: OfficialProbe, url: str | None = None) -> tuple[str, str]:
    """Build actual and redacted probe URLs.

    Args:
        probe: Probe definition.
        url: Optional URL override for fallback probes.

    Returns:
        tuple[str, str]: Actual URL and secret-redacted URL.
    """

    base_url = url or probe.url
    params = dict(probe.params)
    redacted_params = dict(probe.params)
    if probe.credential_env and probe.credential_param:
        secret = os.environ.get(probe.credential_env, "").strip()
        params[probe.credential_param] = secret
        redacted_params[probe.credential_param] = "<redacted>"

    if not params:
        return base_url, base_url

    separator = "&" if "?" in base_url else "?"
    actual = base_url + separator + urlencode(params)
    redacted = base_url + separator + urlencode(redacted_params)
    return actual, redacted


def _domain_matches(host: str, official_domain: str) -> bool:
    """Return whether host is the expected domain or a subdomain.

    Args:
        host: Parsed URL host.
        official_domain: Required domain.

    Returns:
        bool: True when host matches the official domain boundary.
    """

    host = host.lower().removeprefix("www.")
    official = official_domain.lower().removeprefix("www.")
    return host == official or host.endswith(f".{official}")


def _probe_domains(probe: OfficialProbe) -> tuple[str, ...]:
    """Return all official domains accepted for a probe.

    Args:
        probe: Official source probe definition.

    Returns:
        tuple[str, ...]: Primary and fallback official domains.
    """

    return (probe.official_domain, *tuple(probe.official_domains))


def _probe_urls(probe: OfficialProbe) -> tuple[str, ...]:
    """Return primary and fallback URLs for a probe.

    Args:
        probe: Official source probe definition.

    Returns:
        tuple[str, ...]: Probe URLs in priority order.
    """

    return (probe.url, *tuple(probe.fallback_urls))


def _headers_for_client_profile(profile: str) -> dict[str, str]:
    """Build HTTP headers for a verifier client profile.

    Args:
        profile: Client profile name.

    Returns:
        dict[str, str]: Secret-free HTTP headers.
    """

    try:
        from features.compliance.infra._http import USER_AGENT as crawler_user_agent
    except Exception:
        crawler_user_agent = "AjinComplianceCrawler/1.0 (+contact@ajin.co.kr)"

    user_agent = (
        BROWSER_COMPATIBLE_USER_AGENT
        if profile == CLIENT_PROFILE_BROWSER_COMPATIBLE
        else crawler_user_agent
    )
    return {
        "Accept": "text/html,application/json,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "User-Agent": user_agent,
    }


def _probe_single_http_url(
    probe: OfficialProbe,
    config: FeatureDConfig,
    url: str,
    client_profile: str,
) -> ProbeOutcome:
    """Probe one URL/profile pair with HEAD and GET fallback.

    Args:
        probe: Official source probe definition.
        config: Verifier config.
        url: URL to probe.
        client_profile: HTTP client profile.

    Returns:
        ProbeOutcome: Secret-safe URL/profile result.
    """

    actual_url, redacted_url = _probe_url(probe, url)
    host = urlparse(actual_url).hostname or ""
    if not any(_domain_matches(host, domain) for domain in _probe_domains(probe)):
        return ProbeOutcome(
            name=probe.name,
            status="fail",
            url=redacted_url,
            winning_url=redacted_url,
            client_profile=client_profile,
            error=f"unexpected_domain:{host}",
        )

    attempts = max(1, int(config.retries))
    last_error = ""
    last_status: int | None = None
    last_method = ""
    last_etag = ""
    last_modified = ""
    headers = _headers_for_client_profile(client_profile)
    method_order = ("GET", "HEAD") if probe.prefer_get else ("HEAD", "GET")
    for attempt in range(attempts):
        if attempt:
            time.sleep(min(0.5 * attempt, 2.0))
        try:
            with httpx.Client(timeout=config.timeout_sec, follow_redirects=True) as client:
                response: httpx.Response | None = None
                method = method_order[0]
                for index, candidate in enumerate(method_order):
                    try:
                        if candidate == "HEAD":
                            response = client.head(actual_url, headers=headers)
                        else:
                            response = client.get(actual_url, headers=headers)
                        method = candidate
                    except Exception as exc:
                        last_error = f"{candidate}:{type(exc).__name__}"
                        response = None
                    if response is None:
                        continue
                    if 200 <= response.status_code < 400 or response.status_code == 304:
                        break
                    if (
                        index == 0
                        and candidate == "HEAD"
                        and response.status_code in {400, 401, 403, 405}
                    ):
                        continue
                    break
                if response is None:
                    continue
                last_status = response.status_code
                last_method = method
                last_etag = response.headers.get("ETag", "")
                last_modified = response.headers.get("Last-Modified", "")
                if 200 <= response.status_code < 400 or response.status_code == 304:
                    return ProbeOutcome(
                        name=probe.name,
                        status="pass",
                        url=redacted_url,
                        http_status=response.status_code,
                        method=method,
                        etag=last_etag,
                        last_modified=last_modified,
                        winning_url=redacted_url,
                        client_profile=client_profile,
                    )
                last_error = f"HTTP_{response.status_code}"
        except Exception as exc:
            last_error = type(exc).__name__

    return ProbeOutcome(
        name=probe.name,
        status="fail",
        url=redacted_url,
        http_status=last_status,
        method=last_method,
        etag=last_etag,
        last_modified=last_modified,
        winning_url=redacted_url,
        client_profile=client_profile,
        error=last_error or "probe_failed",
    )


def _probe_http_url(probe: OfficialProbe, config: FeatureDConfig) -> ProbeOutcome:
    """Probe one official source through primary and fallback URLs.

    Args:
        probe: Official source probe definition.
        config: Verifier config.

    Returns:
        ProbeOutcome: Secret-safe result.
    """

    primary_http_status: int | None = None
    last_outcome: ProbeOutcome | None = None
    for url_index, url in enumerate(_probe_urls(probe)):
        for profile in probe.client_profiles:
            outcome = _probe_single_http_url(probe, config, url, profile)
            if url_index == 0 and primary_http_status is None and outcome.http_status is not None:
                primary_http_status = outcome.http_status
            outcome = ProbeOutcome(
                name=outcome.name,
                status=outcome.status,
                url=outcome.url,
                http_status=outcome.http_status,
                method=outcome.method,
                etag=outcome.etag,
                last_modified=outcome.last_modified,
                primary_http_status=primary_http_status,
                winning_url=outcome.winning_url or outcome.url,
                client_profile=outcome.client_profile,
                error=outcome.error,
            )
            if outcome.status == "pass":
                return outcome
            last_outcome = outcome

    if last_outcome is not None:
        return last_outcome
    _, redacted_url = _probe_url(probe)
    return ProbeOutcome(
        name=probe.name,
        status="fail",
        url=redacted_url,
        primary_http_status=primary_http_status,
        winning_url=redacted_url,
        error="probe_not_configured",
    )


def verify_official_source_live_probes(config: FeatureDConfig) -> CheckResult:
    """Verify official source reachability and required API credentials.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Official source live probe posture.
    """

    failures: list[str] = []
    outcomes: list[dict[str, Any]] = []
    credential_presence: dict[str, bool] = {}
    blocker_categories: dict[str, list[str]] = {
        "credential_missing": [],
        "official_source_http_posture": [],
    }
    for probe in OFFICIAL_PROBES:
        if probe.only_when_d2_d5_allowed and (
            not config.allow_d2_d5
            or _stage_rank(config.rollout_stage) < _stage_rank(probe.min_rollout_stage)
        ):
            continue
        if probe.credential_env:
            present = bool(os.environ.get(probe.credential_env, "").strip())
            credential_presence[probe.credential_env] = present
            if not present:
                failure = f"{probe.name}:missing_{probe.credential_env}"
                failures.append(failure)
                blocker_categories["credential_missing"].append(failure)
                _, redacted_url = _probe_url(probe)
                outcomes.append(
                    ProbeOutcome(
                        name=probe.name,
                        status="fail",
                        url=redacted_url,
                        error=f"missing_credential:{probe.credential_env}",
                    ).to_dict()
                )
                continue
        outcome = _probe_http_url(probe, config)
        outcomes.append(outcome.to_dict())
        if outcome.status != "pass":
            failure = f"{probe.name}:{outcome.error or 'probe_failed'}"
            failures.append(failure)
            blocker_categories["official_source_http_posture"].append(failure)

    details = {
        "credential_presence": credential_presence,
        "probe_count": len(outcomes),
        "failures": failures,
        "blocker_categories": {
            key: value for key, value in blocker_categories.items() if value
        },
        "outcomes": outcomes,
    }
    if failures:
        return CheckResult(
            "official_source_live_probes",
            "fail",
            "Official source live probe failed or required credentials are missing",
            details,
        )
    return CheckResult(
        "official_source_live_probes",
        "pass",
        "All required official source live probes returned a successful HTTP status",
        details,
    )


def _load_json_file(path: Path) -> Any:
    """Load JSON from a file.

    Args:
        path: JSON path.

    Returns:
        Any: Parsed JSON.
    """

    return json.loads(path.read_text(encoding="utf-8"))


def _iter_items(data: Mapping[str, Any], keys: Iterable[str]) -> list[Mapping[str, Any]]:
    """Extract crawler items from common result fields.

    Args:
        data: Crawler result JSON.
        keys: Candidate list fields.

    Returns:
        list[Mapping[str, Any]]: Item objects.
    """

    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def _item_reference_urls(item: Mapping[str, Any]) -> list[str]:
    """Return reference URLs found on a crawler item.

    Args:
        item: Crawler result item.

    Returns:
        list[str]: HTTP URLs found in citation fields.
    """

    urls: list[str] = []
    for key in ("reference_url", "url", "full_url", "external_url"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            urls.append(value.strip())
    monitoring_urls = item.get("monitoring_urls")
    if isinstance(monitoring_urls, list):
        urls.extend(str(value).strip() for value in monitoring_urls if str(value).strip())
    references = item.get("references")
    if isinstance(references, list):
        for ref in references:
            if isinstance(ref, Mapping):
                value = ref.get("url") or ref.get("reference_url")
                if isinstance(value, str) and value.strip():
                    urls.append(value.strip())
    return [url for url in urls if url.startswith(("http://", "https://"))]


def _url_is_official(url: str) -> bool:
    """Return whether a citation URL points to an accepted official domain.

    Args:
        url: Citation URL.

    Returns:
        bool: True when the URL host matches an accepted official domain.
    """

    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return any(host == domain or host.endswith(f".{domain}") for domain in OFFICIAL_DOMAINS)


def verify_citation_policy(config: FeatureDConfig) -> CheckResult:
    """Verify crawler result source typing and official citation URLs.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Citation and source policy posture.
    """

    failures: list[str] = []
    warnings: list[str] = []
    file_summaries: dict[str, Any] = {}
    blocker_categories: dict[str, list[str]] = {
        "crawler_output_schema_mismatch": [],
        "citation_missing": [],
        "citation_unofficial": [],
    }
    data_root = config.root / "data" / "crawled"

    for crawler, filename in CRAWLER_RESULT_FILES.items():
        path = data_root / filename
        if not path.exists():
            failures.append(f"{crawler}:result_file_missing:{filename}")
            file_summaries[crawler] = {"path": _display_path(config.root, path), "exists": False}
            continue
        try:
            data = _load_json_file(path)
        except Exception as exc:
            failures.append(f"{crawler}:json_parse_failed:{type(exc).__name__}")
            continue
        if not isinstance(data, Mapping):
            failures.append(f"{crawler}:result_not_object")
            continue

        source_type = str(data.get("source_type") or "")
        source = str(data.get("source") or "")
        source_reason = str(data.get("source_reason") or data.get("reason") or "")
        crawled_at = str(data.get("crawled_at") or "")
        errors = data.get("errors") if isinstance(data.get("errors"), list) else []
        if source_type not in {"live", "curated"}:
            failure = f"{crawler}:missing_or_invalid_source_type"
            failures.append(failure)
            blocker_categories["crawler_output_schema_mismatch"].append(failure)
        if not source:
            failure = f"{crawler}:source_missing"
            failures.append(failure)
            blocker_categories["crawler_output_schema_mismatch"].append(failure)
        if not crawled_at:
            failure = f"{crawler}:crawled_at_missing"
            failures.append(failure)
            blocker_categories["crawler_output_schema_mismatch"].append(failure)
        if (
            source_type == "curated"
            and not errors
            and not source_reason
            and "curated" not in source.lower()
            and "큐레이트" not in source
        ):
            failure = f"{crawler}:curated_without_error_or_reason"
            failures.append(failure)
            blocker_categories["crawler_output_schema_mismatch"].append(failure)

        items = _iter_items(data, CRAWLER_ITEM_FIELDS[crawler])
        missing_citations: list[str] = []
        unofficial_urls: list[str] = []
        for idx, item in enumerate(items):
            urls = _item_reference_urls(item)
            if not urls:
                missing_citations.append(str(item.get("id") or item.get("law_id") or item.get("regulation_id") or idx))
                continue
            bad_urls = [url for url in urls if not _url_is_official(url)]
            unofficial_urls.extend(bad_urls)
        if missing_citations:
            failure = f"{crawler}:missing_citation:{len(missing_citations)}"
            failures.append(failure)
            blocker_categories["citation_missing"].append(failure)
        if unofficial_urls:
            failure = f"{crawler}:unofficial_citation:{len(unofficial_urls)}"
            failures.append(failure)
            blocker_categories["citation_unofficial"].append(failure)

        if not items:
            warnings.append(f"{crawler}:no_items_found")
        file_summaries[crawler] = {
            "path": _display_path(config.root, path),
            "exists": True,
            "source_type": source_type,
            "source_present": bool(source),
            "source_reason_present": bool(source_reason),
            "crawled_at_present": bool(crawled_at),
            "errors_count": len(errors),
            "items_count": len(items),
            "missing_citation_count": len(missing_citations),
            "unofficial_citation_count": len(unofficial_urls),
            "sample_unofficial_urls": unofficial_urls[:5],
        }

    details = {
        "failures": failures,
        "warnings": warnings,
        "blocker_categories": {
            key: value for key, value in blocker_categories.items() if value
        },
        "files": file_summaries,
    }
    if failures:
        return CheckResult(
            "citation_and_source_policy",
            "fail",
            "Crawler outputs have missing source typing, reasons, or official citation URLs",
            details,
        )
    if warnings:
        return CheckResult(
            "citation_and_source_policy",
            "warn",
            "Crawler outputs meet citation policy but have review warnings",
            details,
        )
    return CheckResult(
        "citation_and_source_policy",
        "pass",
        "Crawler outputs expose source_type/source/crawled_at and official citation URLs",
        details,
    )


def verify_crawler_sla_policy(config: FeatureDConfig) -> CheckResult:
    """Verify that every D1 crawler has a secret-safe SLA policy.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Crawler SLA registry posture.
    """

    del config
    failures: list[str] = []
    expected = set(CRAWLER_RESULT_FILES)
    policies = dict(CRAWLER_SLA_POLICIES)
    missing = sorted(expected - set(policies))
    extra = sorted(set(policies) - expected)
    for name in missing:
        failures.append(f"{name}:sla_policy_missing")
    for name, policy in policies.items():
        if name not in expected:
            continue
        if policy.result_file != CRAWLER_RESULT_FILES[name]:
            failures.append(f"{name}:result_file_mismatch")
        if not policy.official_source.startswith(("http://", "https://")):
            failures.append(f"{name}:official_source_missing")
        if policy.max_stale_hours <= 0:
            failures.append(f"{name}:invalid_max_stale_hours")
        if not policy.official_domain_allowlist:
            failures.append(f"{name}:official_domain_allowlist_missing")
        source_host = (urlparse(policy.official_source).hostname or "").lower().removeprefix("www.")
        if source_host and not any(
            source_host == domain or source_host.endswith(f".{domain}")
            for domain in policy.official_domain_allowlist
        ):
            failures.append(f"{name}:official_source_outside_allowlist")

    details = {
        "policy_count": len(policies),
        "expected_count": len(expected),
        "missing": missing,
        "extra": extra,
        "failures": failures,
        "policies": {
            name: {
                "cadence": policy.cadence,
                "max_stale_hours": policy.max_stale_hours,
                "credential_required": bool(policy.required_credential),
                "fallback_allowed": policy.fallback_allowed,
                "official_domains": list(policy.official_domain_allowlist),
            }
            for name, policy in sorted(policies.items())
        },
    }
    if failures:
        return CheckResult(
            "crawler_sla_policy",
            "fail",
            "Not every D1 crawler has a valid official-source SLA policy",
            details,
        )
    return CheckResult(
        "crawler_sla_policy",
        "pass",
        "Every D1 crawler has an official-source SLA policy",
        details,
    )


def verify_legal_guardrail_policy(config: FeatureDConfig) -> CheckResult:
    """Verify legal disclaimer and human-review guardrail wiring.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Legal guardrail posture.
    """

    failures: list[str] = []
    required_disclaimer_terms = ("법적 판단", "대외 통보", "담당 부서", "승인")
    if not all(term in COMPLIANCE_AI_DISCLAIMER for term in required_disclaimer_terms):
        failures.append("disclaimer_terms_missing")

    source_checks = {
        "router": config.root / "backend" / "routers" / "compliance.py",
        "dispatcher": config.root / "backend" / "services" / "notify" / "dispatcher.py",
        "exec_report": config.root / "features" / "compliance" / "learning" / "exec_report.py",
        "lms_export": config.root / "features" / "compliance" / "learning" / "lms_export.py",
    }
    snippets = {
        "router": (
            "legal_final_status_requires_l4",
            "legal_review_required",
            "legal_admin_override",
            "override_reason_required",
        ),
        "dispatcher": ("ensure_legal_disclaimer",),
        "exec_report": ("COMPLIANCE_AI_DISCLAIMER",),
        "lms_export": ("COMPLIANCE_AI_DISCLAIMER",),
    }
    checked_files: dict[str, str] = {}
    for name, path in source_checks.items():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            failures.append(f"{name}:source_missing")
            continue
        checked_files[name] = _display_path(config.root, path)
        for snippet in snippets[name]:
            if snippet not in text:
                failures.append(f"{name}:missing_{snippet}")

    details = {
        "failures": failures,
        "disclaimer": COMPLIANCE_AI_DISCLAIMER,
        "checked_files": checked_files,
    }
    if failures:
        return CheckResult(
            "legal_guardrail_policy",
            "fail",
            "Legal disclaimer or human-review transition guardrail is not fully wired",
            details,
        )
    return CheckResult(
        "legal_guardrail_policy",
        "pass",
        "Legal disclaimer and human-review transition guardrail are wired",
        details,
    )


def _d_route_client():
    """Create a minimal Feature D route TestClient.

    Returns:
        fastapi.testclient.TestClient: Test client with auth dependency override.
    """

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.dependencies import get_current_user
    from backend.routers.compliance import router as compliance_router
    from backend.routers.feature_flags import router as flags_router

    user = SimpleNamespace(
        employee_id="VERIFY-D-0001",
        user_id="VERIFY-D-0001",
        username="verify-d",
        role="SYS_ADMIN",
        role_level=5,
        department="품질보증팀",
        email="verify-d@example.invalid",
    )
    app = FastAPI()
    app.include_router(compliance_router, prefix="/api")
    app.include_router(flags_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


def _feature_disabled(response: Any) -> bool:
    """Return whether a FastAPI response is the Feature D disabled guard.

    Args:
        response: TestClient response.

    Returns:
        bool: True for 404 feature_disabled responses.
    """

    try:
        detail = response.json().get("detail")
    except Exception:
        detail = ""
    return response.status_code == 404 and detail == "feature_disabled"


def verify_d2_d5_flags(config: FeatureDConfig) -> CheckResult:
    """Verify Feature D default flags and optional D2-D5 route posture.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Feature flag rollout posture.
    """

    failures: list[str] = []
    details: dict[str, Any] = {}
    try:
        from core.feature_flags import feature_d_flags_dict
    except Exception as exc:
        return CheckResult(
            "d2_d5_flag_posture",
            "fail",
            "Feature D flags could not be imported",
            {"error": type(exc).__name__},
        )

    current_flags = feature_d_flags_dict()
    with _temporary_env({key: None for key in FEATURE_D_ENV_KEYS}):
        default_flags = feature_d_flags_dict()
        client = _d_route_client()
        flag_endpoint = client.get("/api/feature-flags/d")
        d1_response = client.get("/api/compliance/changes/feed")
        disabled_checks = {
            "d2_rag": client.get("/api/compliance/glossary"),
            "d3_whatif": client.get("/api/compliance/risk/scores"),
            "d4_workflow": client.get("/api/compliance/tickets"),
            "d5_supply": client.get("/api/compliance/suppliers"),
        }

    if default_flags != EXPECTED_DEFAULT_D_FLAGS:
        failures.append("default_flags_not_d1_only")
    if current_flags["d1_alerts"] is not True:
        failures.append("current_d1_alerts_disabled")
    enabled_d2_d5 = [name for name in ("d2_rag", "d3_whatif", "d4_workflow", "d5_supply") if current_flags.get(name)]
    if enabled_d2_d5 and not config.allow_d2_d5:
        failures.append("d2_d5_enabled_without_allow")
    stage_flags = _flags_for_stage(config.rollout_stage)
    if config.allow_d2_d5 and config.rollout_stage == "d1":
        failures.append("allow_d2_d5_without_rollout_stage")
    if config.allow_d2_d5 and config.rollout_stage not in D2_D5_ROLLOUT_STAGES:
        failures.append("unknown_rollout_stage")
    if config.allow_d2_d5:
        outside_stage = sorted(set(enabled_d2_d5) - stage_flags)
        for flag in outside_stage:
            failures.append(f"{flag}:enabled_outside_rollout_stage")
    if flag_endpoint.status_code != 200:
        failures.append(f"feature_flag_endpoint_status_{flag_endpoint.status_code}")
    if d1_response.status_code != 200:
        failures.append(f"d1_route_status_{d1_response.status_code}")
    disabled_outcomes = {
        name: {"status_code": response.status_code, "feature_disabled": _feature_disabled(response)}
        for name, response in disabled_checks.items()
    }
    if not all(item["feature_disabled"] for item in disabled_outcomes.values()):
        failures.append("default_d2_d5_routes_not_hidden")

    allowed_route_outcomes: dict[str, Any] = {}
    if config.allow_d2_d5 and config.rollout_stage != "d1":
        updates = {
            "FEATURE_D_D1_ALERTS": "true",
        }
        for flag, env_key in D2_D5_FLAG_TO_ENV.items():
            updates[env_key] = "true" if flag in stage_flags else "false"
        with _temporary_env(updates):
            client = _d_route_client()
            for name, route in D2_D5_SMOKE_ROUTES.items():
                if name not in stage_flags:
                    continue
                response = client.get(route)
                allowed_route_outcomes[name] = {
                    "route": route,
                    "status_code": response.status_code,
                    "feature_disabled": _feature_disabled(response),
                }
                if _feature_disabled(response):
                    failures.append(f"{name}:allowed_route_feature_disabled")

    details.update(
        {
            "current_flags": current_flags,
            "default_flags": default_flags,
            "enabled_d2_d5": enabled_d2_d5,
            "rollout_stage": config.rollout_stage,
            "stage_flags": sorted(stage_flags),
            "default_route_outcomes": {
                "feature_flags_d": flag_endpoint.status_code,
                "d1_changes_feed": d1_response.status_code,
                **disabled_outcomes,
            },
            "allowed_route_outcomes": allowed_route_outcomes,
            "failures": failures,
        }
    )
    if failures:
        return CheckResult(
            "d2_d5_flag_posture",
            "fail",
            "Feature D D1/D2-D5 flag posture does not meet the release baseline",
            details,
        )
    return CheckResult(
        "d2_d5_flag_posture",
        "pass",
        "D1 is enabled, D2-D5 are hidden by default, and allowed D2-D5 routes are not feature-disabled",
        details,
    )


def verify_notification_scheduler(config: FeatureDConfig) -> CheckResult:
    """Verify notification adapter posture and Celery beat schedule.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Notification and scheduler posture.
    """

    failures: list[str] = []
    warnings: list[str] = []
    if _truthy(os.environ.get("FEATURE_D_LEGACY_DIRECT_NOTIFY")):
        failures.append("legacy_direct_notify_enabled")

    try:
        from backend.celery_app import _CRAWL_STAGGER_MIN, celery_app
    except Exception as exc:
        return CheckResult(
            "notification_scheduler",
            "fail",
            "Celery schedule could not be imported",
            {"error": type(exc).__name__},
        )

    schedule = dict(celery_app.conf.beat_schedule or {})
    expected_crawl_jobs = {f"crawl_{name}" for name in CRAWLER_RESULT_FILES}
    missing_crawl_jobs = sorted(expected_crawl_jobs - set(schedule))
    for job in missing_crawl_jobs:
        failures.append(f"missing_schedule:{job}")
    for job in ("digest_daily", "dispatch_outbox"):
        if job not in schedule:
            failures.append(f"missing_schedule:{job}")
    if set(_CRAWL_STAGGER_MIN) != set(CRAWLER_RESULT_FILES):
        failures.append("crawler_stagger_set_mismatch")

    adapter_posture = {
        "email": "real" if _truthy(os.environ.get("SMTP_ENABLED")) else "mock",
        "slack": "real_per_user_webhook",
        "teams": "real_per_user_webhook",
        "legacy_direct_notify": _truthy(os.environ.get("FEATURE_D_LEGACY_DIRECT_NOTIFY")),
    }
    if adapter_posture["email"] == "real" and not os.environ.get("SMTP_HOST", "").strip():
        warnings.append("smtp_enabled_without_smtp_host")

    try:
        from backend.services.jobs.dispatch_outbox import run as dispatch_run
        from backend.services.notify.dispatcher import dispatch_pending, enqueue_for_change
    except Exception as exc:
        failures.append(f"dispatcher_import_failed:{type(exc).__name__}")
        dispatcher_symbols = {}
    else:
        dispatcher_symbols = {
            "dispatch_outbox_job": callable(dispatch_run),
            "dispatch_pending": callable(dispatch_pending),
            "enqueue_for_change": callable(enqueue_for_change),
        }
        if not all(dispatcher_symbols.values()):
            failures.append("dispatcher_symbols_not_callable")

    details = {
        "failures": failures,
        "warnings": warnings,
        "schedule_keys": sorted(schedule),
        "crawl_stagger": dict(_CRAWL_STAGGER_MIN),
        "adapter_posture": adapter_posture,
        "dispatcher_symbols": dispatcher_symbols,
    }
    if failures:
        return CheckResult(
            "notification_scheduler",
            "fail",
            "Notification dispatcher or Celery schedule does not meet release posture",
            details,
        )
    if warnings:
        return CheckResult(
            "notification_scheduler",
            "warn",
            "Notification scheduler is wired but adapter posture needs operational review",
            details,
        )
    return CheckResult(
        "notification_scheduler",
        "pass",
        "Outbox dispatcher, adapter posture, and staggered Celery schedules are wired",
        details,
    )


def summarize(checks: Sequence[CheckResult]) -> dict[str, Any]:
    """Summarize check statuses.

    Args:
        checks: Check results.

    Returns:
        dict[str, Any]: Status counts and aggregate status.
    """

    counts = {"pass": 0, "warn": 0, "fail": 0, "skip": 0}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    return {"status": status, "counts": counts, "checked_at": datetime.now(timezone.utc).isoformat()}


def run_verification(config: FeatureDConfig) -> dict[str, Any]:
    """Run all Feature D release checks.

    Args:
        config: Verifier config.

    Returns:
        dict[str, Any]: Secret-safe report payload.
    """

    checks = [
        verify_endpoint_surface(config),
        verify_official_source_live_probes(config),
        verify_citation_policy(config),
        verify_crawler_sla_policy(config),
        verify_legal_guardrail_policy(config),
        verify_d2_d5_flags(config),
        verify_notification_scheduler(config),
    ]
    return {
        "summary": summarize(checks),
        "config": {
            "strict": config.strict,
            "allow_d2_d5": config.allow_d2_d5,
            "rollout_stage": config.rollout_stage,
            "timeout_sec": config.timeout_sec,
            "retries": config.retries,
            "openapi_path": _display_path(config.root, config.openapi_path),
            "credential_presence": {
                "LAW_GO_KR_OC": bool(os.environ.get("LAW_GO_KR_OC", "").strip()),
                "CUSTOMS_API_KEY": bool(os.environ.get("CUSTOMS_API_KEY", "").strip()),
                "DART_API_KEY": bool(os.environ.get("DART_API_KEY", "").strip()),
            },
        },
        "references": list(DOC_REFERENCES),
        "checks": [check.to_dict() for check in checks],
    }


def write_markdown_report(report: Mapping[str, Any], path: Path) -> None:
    """Write a Markdown verification report.

    Args:
        report: Report payload.
        path: Destination path.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    summary = report["summary"]
    config = report["config"]
    lines = [
        "# Feature D Release Check",
        "",
        f"- Status: `{summary['status']}`",
        f"- Checked at: `{summary['checked_at']}`",
        f"- Counts: `{json.dumps(summary['counts'], ensure_ascii=False)}`",
        f"- OpenAPI path: `{config['openapi_path']}`",
        f"- Allow D2-D5 override: `{config['allow_d2_d5']}`",
        f"- Rollout stage: `{config['rollout_stage']}`",
        f"- Timeout seconds: `{config['timeout_sec']}`",
        f"- Retries: `{config['retries']}`",
        f"- Credential presence: `{json.dumps(config['credential_presence'], ensure_ascii=False)}`",
        "",
        "## Checks",
        "",
        "| Status | Check | Summary | Details |",
        "| --- | --- | --- | --- |",
    ]
    for check in report["checks"]:
        details = json.dumps(check.get("details", {}), ensure_ascii=False)
        lines.append(f"| `{check['status']}` | `{check['name']}` | {check['summary']} | `{details}` |")
    blocker_categories: dict[str, list[str]] = {}
    for check in report["checks"]:
        details = check.get("details", {})
        if not isinstance(details, Mapping):
            continue
        categories = details.get("blocker_categories", {})
        if not isinstance(categories, Mapping):
            continue
        for category, items in categories.items():
            if isinstance(items, list):
                blocker_categories.setdefault(str(category), []).extend(str(item) for item in items)
    if blocker_categories:
        lines.extend(["", "## Blocker Categories", ""])
        for category, items in sorted(blocker_categories.items()):
            lines.append(f"- `{category}`: {len(items)}")
    lines.extend(
        [
            "",
            "## Release Policy",
            "",
            "- Official source live probe is mandatory in strict release runs.",
            "- `LAW_GO_KR_OC` and `CUSTOMS_API_KEY` are required for D1 source freshness.",
            "- `DART_API_KEY` is required only when the D5 supply-chain rollout stage is explicitly allowed.",
            "- Crawler outputs must distinguish `source_type=live` and `source_type=curated` and carry official citation URLs.",
            "- D1 remains the default release surface; D2-D5 require explicit stage rollout approval.",
            "- AI summaries and recommendations are reference-only and require human legal review before external action.",
            "- `FEATURE_D_LEGACY_DIRECT_NOTIFY` must remain off; notification delivery flows through the outbox dispatcher.",
            "",
            "## References",
            "",
        ]
    )
    for ref in report["references"]:
        lines.append(f"- {ref}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _print_text_report(report: Mapping[str, Any]) -> None:
    """Print a compact text report.

    Args:
        report: Report payload.
    """

    summary = report["summary"]
    print(
        "Feature D release: "
        f"{summary['status']} "
        f"(pass={summary['counts']['pass']}, warn={summary['counts']['warn']}, "
        f"fail={summary['counts']['fail']}, skip={summary['counts']['skip']})"
    )
    for check in report["checks"]:
        print(f"[{check['status'].upper()}] {check['name']}: {check['summary']}")
        if check.get("details"):
            print(f"  details={json.dumps(check['details'], ensure_ascii=False)}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list.

    Returns:
        argparse.Namespace: Parsed arguments.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when fail checks remain.")
    parser.add_argument("--markdown", default="", help="Write a Markdown report to this path.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    parser.add_argument("--openapi", default="docs/openapi.json", help="OpenAPI JSON path.")
    parser.add_argument("--timeout-sec", type=float, default=8.0, help="HTTP timeout for live probes.")
    parser.add_argument("--retries", type=int, default=1, help="HTTP probe attempts per source.")
    parser.add_argument("--allow-d2-d5", action="store_true", help="Allow D2-D5 flags and D5 DART probe.")
    parser.add_argument(
        "--rollout-stage",
        choices=D2_D5_ROLLOUT_STAGES,
        default="d1",
        help="Highest Feature D rollout stage allowed when --allow-d2-d5 is set.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Optional argument list.

    Returns:
        int: Process exit code.
    """

    args = parse_args(argv)
    _load_release_dotenv(ROOT)
    openapi_path = Path(args.openapi)
    if not openapi_path.is_absolute():
        openapi_path = ROOT / openapi_path
    config = FeatureDConfig(
        root=ROOT,
        openapi_path=openapi_path,
        strict=bool(args.strict),
        timeout_sec=float(args.timeout_sec),
        retries=max(1, int(args.retries)),
        allow_d2_d5=bool(args.allow_d2_d5),
        rollout_stage=str(args.rollout_stage),
    )
    report = run_verification(config)
    if args.markdown:
        markdown_path = Path(args.markdown)
        if not markdown_path.is_absolute():
            markdown_path = ROOT / markdown_path
        write_markdown_report(report, markdown_path)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_text_report(report)
    if config.strict and report["summary"]["status"] == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
