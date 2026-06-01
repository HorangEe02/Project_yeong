"""Feature D crawler SLA policy tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone


def test_crawler_sla_registry_covers_release_crawlers() -> None:
    """Every release crawler must have a matching SLA policy."""

    import scripts.verify_feature_d_release as verifier
    from features.compliance.crawlers.sla import CRAWLER_SLA_POLICIES

    assert set(CRAWLER_SLA_POLICIES) == set(verifier.CRAWLER_RESULT_FILES)
    result = verifier.verify_crawler_sla_policy(verifier.FeatureDConfig())
    assert result.status == "pass"


def test_verifier_fails_when_crawler_sla_policy_is_missing(monkeypatch) -> None:
    """The release verifier must fail closed on incomplete SLA coverage."""

    import scripts.verify_feature_d_release as verifier

    policies = dict(verifier.CRAWLER_SLA_POLICIES)
    policies.pop("iso")
    monkeypatch.setattr(verifier, "CRAWLER_SLA_POLICIES", policies)

    result = verifier.verify_crawler_sla_policy(verifier.FeatureDConfig())

    assert result.status == "fail"
    assert "iso:sla_policy_missing" in result.details["failures"]


def test_crawl_history_stats_reports_fresh_stale_and_missing_credential(monkeypatch, tmp_path) -> None:
    """Crawl stats should expose SLA status without leaking credentials."""

    from backend.services import crawl_audit

    data_dir = tmp_path / "data"
    crawled_dir = data_dir / "crawled"
    crawled_dir.mkdir(parents=True)
    monkeypatch.setattr(crawl_audit, "DATA_DIR", data_dir)
    monkeypatch.setattr(crawl_audit, "DB_PATH", tmp_path / "crawl_runs.db")
    monkeypatch.delenv("LAW_GO_KR_OC", raising=False)
    monkeypatch.delenv("CUSTOMS_API_KEY", raising=False)

    (crawled_dir / "iso_standards.json").write_text(
        json.dumps({"source_type": "live"}),
        encoding="utf-8",
    )
    (crawled_dir / "eu_regulations.json").write_text(
        json.dumps({"source_type": "live"}),
        encoding="utf-8",
    )

    now = datetime.now(timezone.utc).replace(microsecond=0)
    old = now - timedelta(days=10)
    crawl_audit.record_run(
        crawler_name="iso",
        started_at=now.isoformat(),
        elapsed_ms=10,
        ok=True,
        http_status=200,
        http_etag="etag-iso",
    )
    crawl_audit.record_run(
        crawler_name="eu_regulation",
        started_at=old.isoformat(),
        elapsed_ms=10,
        ok=True,
        http_status=200,
    )

    stats = crawl_audit.stats_24h()

    assert stats["sla"]["iso"]["status"] == "fresh"
    assert stats["sla"]["iso"]["last_http_etag"] == "etag-iso"
    assert stats["sla"]["eu_regulation"]["status"] == "stale"
    assert stats["sla"]["domestic_law"]["status"] == "missing_credential"
    assert stats["sla"]["domestic_law"]["credential_required"] is True
    assert stats["sla"]["domestic_law"]["credential_present"] is False
