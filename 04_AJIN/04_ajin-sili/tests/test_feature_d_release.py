"""Feature D release verifier tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

import scripts.verify_feature_d_release as verifier


def test_endpoint_surface_passes_current_openapi() -> None:
    """Current OpenAPI should expose the expected D1 release surface."""

    result = verifier.verify_endpoint_surface(verifier.FeatureDConfig())

    assert result.status == "pass"
    assert result.details["counts"] == {"compliance": 19, "notifications": 6}


def test_endpoint_surface_fails_when_required_route_missing(tmp_path: Path) -> None:
    """Missing D1 routes should fail the release verifier."""

    openapi_path = tmp_path / "openapi.json"
    openapi_path.write_text(json.dumps({"paths": {}}), encoding="utf-8")

    result = verifier.verify_endpoint_surface(
        verifier.FeatureDConfig(root=tmp_path, openapi_path=openapi_path)
    )

    assert result.status == "fail"
    assert result.details["missing_counts"]
    assert "/api/feature-flags/d" in result.details["missing_required"]


def test_official_live_probe_requires_law_and_customs_credentials(monkeypatch) -> None:
    """LAW_GO_KR_OC and CUSTOMS_API_KEY are release blockers by default."""

    monkeypatch.delenv("LAW_GO_KR_OC", raising=False)
    monkeypatch.delenv("CUSTOMS_API_KEY", raising=False)
    monkeypatch.delenv("DART_API_KEY", raising=False)

    def fake_probe(probe, config):
        return verifier.ProbeOutcome(
            name=probe.name,
            status="pass",
            url=probe.url,
            http_status=200,
            method="GET",
        )

    monkeypatch.setattr(verifier, "_probe_http_url", fake_probe)

    result = verifier.verify_official_source_live_probes(verifier.FeatureDConfig())

    assert result.status == "fail"
    assert "domestic_law:missing_LAW_GO_KR_OC" in result.details["failures"]
    assert "global_trade:missing_CUSTOMS_API_KEY" in result.details["failures"]
    assert result.details["blocker_categories"]["credential_missing"] == [
        "domestic_law:missing_LAW_GO_KR_OC",
        "global_trade:missing_CUSTOMS_API_KEY",
    ]


def test_release_dotenv_loads_feature_d_local_first(tmp_path: Path, monkeypatch) -> None:
    """Feature D credentials should load from the dedicated local dotenv first."""

    monkeypatch.delenv("LAW_GO_KR_OC", raising=False)
    monkeypatch.delenv("CUSTOMS_API_KEY", raising=False)
    monkeypatch.delenv("FEATURE_D_D2_RAG", raising=False)
    (tmp_path / ".env.feature-d.local").write_text(
        "LAW_GO_KR_OC=feature-d-law\nCUSTOMS_API_KEY=feature-d-customs\n",
        encoding="utf-8",
    )
    (tmp_path / ".env.supabase.local").write_text(
        "LAW_GO_KR_OC=supabase-law\nFEATURE_D_D2_RAG=true\n",
        encoding="utf-8",
    )

    loaded = verifier._load_release_dotenv(tmp_path)

    assert loaded is True
    assert os.environ["LAW_GO_KR_OC"] == "feature-d-law"
    assert os.environ["CUSTOMS_API_KEY"] == "feature-d-customs"
    assert os.environ["FEATURE_D_D2_RAG"] == "true"


def test_probe_can_prefer_get_for_head_rejecting_sites(monkeypatch) -> None:
    """GET-first probes avoid known official sites that reject HEAD."""

    calls: list[str] = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None):
            calls.append("GET")
            return httpx.Response(
                200,
                headers={"ETag": "etag-1"},
                request=httpx.Request("GET", url),
            )

        def head(self, url, headers=None):
            calls.append("HEAD")
            return httpx.Response(400, request=httpx.Request("HEAD", url))

    monkeypatch.setattr(verifier.httpx, "Client", FakeClient)

    outcome = verifier._probe_http_url(
        verifier.OfficialProbe(
            name="apqp",
            url="https://go.aiag.org/apqp-cp",
            official_domain="aiag.org",
            prefer_get=True,
        ),
        verifier.FeatureDConfig(),
    )

    assert outcome.status == "pass"
    assert outcome.method == "GET"
    assert calls == ["GET"]


def test_probe_uses_browser_compatible_profile_for_echa_403(monkeypatch) -> None:
    """ECHA primary 403 may pass through the explicit browser-compatible profile."""

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None):
            status = 200 if "Mozilla/5.0" in (headers or {}).get("User-Agent", "") else 403
            return httpx.Response(status, request=httpx.Request("GET", url))

        def head(self, url, headers=None):
            return httpx.Response(403, request=httpx.Request("HEAD", url))

    monkeypatch.setattr(verifier.httpx, "Client", FakeClient)

    outcome = verifier._probe_http_url(
        verifier.OfficialProbe(
            name="msds",
            url="https://www.echa.europa.eu/web/guest/candidate-list-table",
            official_domain="echa.europa.eu",
            prefer_get=True,
            client_profiles=(
                verifier.CLIENT_PROFILE_CRAWLER,
                verifier.CLIENT_PROFILE_BROWSER_COMPATIBLE,
            ),
        ),
        verifier.FeatureDConfig(),
    )

    assert outcome.status == "pass"
    assert outcome.primary_http_status == 403
    assert outcome.client_profile == verifier.CLIENT_PROFILE_BROWSER_COMPATIBLE
    assert outcome.winning_url == "https://www.echa.europa.eu/web/guest/candidate-list-table"


def test_probe_fails_when_all_echa_profiles_return_403(monkeypatch) -> None:
    """ECHA remains a blocker when every official profile and URL fails."""

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None):
            return httpx.Response(403, request=httpx.Request("GET", url))

        def head(self, url, headers=None):
            return httpx.Response(403, request=httpx.Request("HEAD", url))

    monkeypatch.setattr(verifier.httpx, "Client", FakeClient)

    outcome = verifier._probe_http_url(
        verifier.OfficialProbe(
            name="msds",
            url="https://www.echa.europa.eu/web/guest/candidate-list-table",
            official_domain="echa.europa.eu",
            fallback_urls=("https://www.echa.europa.eu/en/candidate-list-table",),
            prefer_get=True,
            client_profiles=(
                verifier.CLIENT_PROFILE_CRAWLER,
                verifier.CLIENT_PROFILE_BROWSER_COMPATIBLE,
            ),
        ),
        verifier.FeatureDConfig(),
    )

    assert outcome.status == "fail"
    assert outcome.error == "HTTP_403"
    assert outcome.primary_http_status == 403


def test_probe_uses_un_ods_fallback_for_unece_403(monkeypatch) -> None:
    """UNECE direct 403 may pass through official UN ODS fallback URLs."""

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None):
            status = 200 if "docs.un.org" in url else 403
            return httpx.Response(status, request=httpx.Request("GET", url))

        def head(self, url, headers=None):
            return httpx.Response(403, request=httpx.Request("HEAD", url))

    monkeypatch.setattr(verifier.httpx, "Client", FakeClient)

    outcome = verifier._probe_http_url(
        verifier.OfficialProbe(
            name="ev_battery",
            url="https://unece.org/trans/main/welcwp29.html",
            official_domain="unece.org",
            fallback_urls=("https://docs.un.org/ECE/TRANS/WP.29/343/REV.30/ADD.2",),
            official_domains=("docs.un.org",),
            prefer_get=True,
        ),
        verifier.FeatureDConfig(),
    )

    assert outcome.status == "pass"
    assert outcome.primary_http_status == 403
    assert outcome.winning_url == "https://docs.un.org/ECE/TRANS/WP.29/343/REV.30/ADD.2"


def test_probe_rejects_unofficial_fallback_domain(monkeypatch) -> None:
    """Fallback URLs must still belong to an allowed official domain."""

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None):
            return httpx.Response(403, request=httpx.Request("GET", url))

        def head(self, url, headers=None):
            return httpx.Response(403, request=httpx.Request("HEAD", url))

    monkeypatch.setattr(verifier.httpx, "Client", FakeClient)

    outcome = verifier._probe_http_url(
        verifier.OfficialProbe(
            name="ev_battery",
            url="https://unece.org/trans/main/welcwp29.html",
            official_domain="unece.org",
            fallback_urls=("https://example.com/not-official",),
            prefer_get=True,
        ),
        verifier.FeatureDConfig(),
    )

    assert outcome.status == "fail"
    assert outcome.error == "unexpected_domain:example.com"


def test_official_live_probe_passes_when_credentials_and_http_ok(monkeypatch) -> None:
    """All probes pass when required credentials are present and HTTP succeeds."""

    monkeypatch.setenv("LAW_GO_KR_OC", "secret-not-printed")
    monkeypatch.setenv("CUSTOMS_API_KEY", "secret-not-printed")

    def fake_probe(probe, config):
        return verifier.ProbeOutcome(
            name=probe.name,
            status="pass",
            url=probe.url,
            http_status=200,
            method="GET",
            etag="abc",
        )

    monkeypatch.setattr(verifier, "_probe_http_url", fake_probe)

    result = verifier.verify_official_source_live_probes(verifier.FeatureDConfig())

    assert result.status == "pass"
    assert result.details["credential_presence"] == {
        "LAW_GO_KR_OC": True,
        "CUSTOMS_API_KEY": True,
    }
    assert "secret-not-printed" not in json.dumps(result.to_dict(), ensure_ascii=False)


def test_allow_d2_d5_requires_dart_credential(monkeypatch) -> None:
    """D5-enabled release runs include DART_API_KEY in the live probe gate."""

    monkeypatch.setenv("LAW_GO_KR_OC", "secret-not-printed")
    monkeypatch.setenv("CUSTOMS_API_KEY", "secret-not-printed")
    monkeypatch.delenv("DART_API_KEY", raising=False)

    def fake_probe(probe, config):
        return verifier.ProbeOutcome(
            name=probe.name,
            status="pass",
            url=probe.url,
            http_status=200,
            method="GET",
        )

    monkeypatch.setattr(verifier, "_probe_http_url", fake_probe)

    result = verifier.verify_official_source_live_probes(
        verifier.FeatureDConfig(allow_d2_d5=True, rollout_stage="d5")
    )

    assert result.status == "fail"
    assert "dart_d5_supply:missing_DART_API_KEY" in result.details["failures"]


def test_citation_policy_fails_missing_or_unofficial_url(tmp_path: Path, monkeypatch) -> None:
    """Crawler result items must cite official URLs."""

    data_root = tmp_path / "data" / "crawled"
    data_root.mkdir(parents=True)
    (data_root / "sample.json").write_text(
        json.dumps(
            {
                "source_type": "curated",
                "source": "curated fixture",
                "crawled_at": "2026-05-20T00:00:00",
                "errors": ["credentials not configured"],
                "data": [
                    {"regulation_id": "NO-URL"},
                    {"regulation_id": "BAD-URL", "reference_url": "https://example.com/not-official"},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(verifier, "CRAWLER_RESULT_FILES", {"sample": "sample.json"})
    monkeypatch.setattr(verifier, "CRAWLER_ITEM_FIELDS", {"sample": ("data",)})

    result = verifier.verify_citation_policy(verifier.FeatureDConfig(root=tmp_path))

    assert result.status == "fail"
    assert "sample:missing_citation:1" in result.details["failures"]
    assert "sample:unofficial_citation:1" in result.details["failures"]
    assert result.details["blocker_categories"]["citation_missing"] == [
        "sample:missing_citation:1"
    ]
    assert result.details["blocker_categories"]["citation_unofficial"] == [
        "sample:unofficial_citation:1"
    ]


def test_citation_policy_fails_missing_source_metadata(tmp_path: Path, monkeypatch) -> None:
    """Crawler outputs must declare source_type/source/crawled_at posture."""

    data_root = tmp_path / "data" / "crawled"
    data_root.mkdir(parents=True)
    (data_root / "sample.json").write_text(
        json.dumps(
            {
                "source": "fixture",
                "data": [
                    {
                        "regulation_id": "LAW-1",
                        "reference_url": "https://www.law.go.kr/법령/산업안전보건법",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(verifier, "CRAWLER_RESULT_FILES", {"sample": "sample.json"})
    monkeypatch.setattr(verifier, "CRAWLER_ITEM_FIELDS", {"sample": ("data",)})

    result = verifier.verify_citation_policy(verifier.FeatureDConfig(root=tmp_path))

    assert result.status == "fail"
    assert "sample:missing_or_invalid_source_type" in result.details["failures"]
    assert "sample:crawled_at_missing" in result.details["failures"]
    assert result.details["blocker_categories"]["crawler_output_schema_mismatch"]


def test_citation_policy_passes_official_curated_result(tmp_path: Path, monkeypatch) -> None:
    """A curated fallback with source reason and official citation passes."""

    data_root = tmp_path / "data" / "crawled"
    data_root.mkdir(parents=True)
    (data_root / "sample.json").write_text(
        json.dumps(
            {
                "source_type": "curated",
                "source": "law.go.kr OpenAPI + 큐레이트",
                "source_reason": "credential-free curated fixture",
                "crawled_at": "2026-05-20T00:00:00",
                "errors": ["credentials not configured"],
                "data": [
                    {
                        "regulation_id": "LAW-1",
                        "reference_url": "https://www.law.go.kr/법령/산업안전보건법",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(verifier, "CRAWLER_RESULT_FILES", {"sample": "sample.json"})
    monkeypatch.setattr(verifier, "CRAWLER_ITEM_FIELDS", {"sample": ("data",)})

    result = verifier.verify_citation_policy(verifier.FeatureDConfig(root=tmp_path))

    assert result.status == "pass"


def test_feature_d_flags_default_posture_passes(monkeypatch) -> None:
    """Default release posture is D1-only with D2-D5 hidden."""

    for key in verifier.FEATURE_D_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    result = verifier.verify_d2_d5_flags(verifier.FeatureDConfig())

    assert result.status == "pass"
    assert result.details["default_flags"] == verifier.EXPECTED_DEFAULT_D_FLAGS


def test_feature_d_enabled_d2_fails_without_allow(monkeypatch) -> None:
    """D2-D5 enabled flags require an explicit verifier override."""

    monkeypatch.setenv("FEATURE_D_D2_RAG", "true")
    monkeypatch.delenv("FEATURE_D_D3_WHATIF", raising=False)
    monkeypatch.delenv("FEATURE_D_D4_WORKFLOW", raising=False)
    monkeypatch.delenv("FEATURE_D_D5_SUPPLY", raising=False)

    result = verifier.verify_d2_d5_flags(verifier.FeatureDConfig())

    assert result.status == "fail"
    assert "d2_d5_enabled_without_allow" in result.details["failures"]


def test_feature_d_allow_d2_d5_requires_rollout_stage(monkeypatch) -> None:
    """`--allow-d2-d5` alone must not open every D2-D5 stage."""

    for key in verifier.FEATURE_D_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    result = verifier.verify_d2_d5_flags(verifier.FeatureDConfig(allow_d2_d5=True))

    assert result.status == "fail"
    assert "allow_d2_d5_without_rollout_stage" in result.details["failures"]


def test_feature_d_allow_d2_d5_rejects_feature_disabled(monkeypatch) -> None:
    """Allowed D2-D5 smokes still fail if a route returns feature_disabled."""

    class _Response:
        def __init__(self, status_code: int, body: dict):
            self.status_code = status_code
            self._body = body

        def json(self):
            return self._body

    class _Client:
        def get(self, path: str):
            if path == "/api/feature-flags/d":
                return _Response(200, {"flags": verifier.EXPECTED_DEFAULT_D_FLAGS})
            if path == "/api/compliance/changes/feed":
                return _Response(200, {"items": []})
            if path == "/api/compliance/glossary":
                return _Response(404, {"detail": "feature_disabled"})
            return _Response(404, {"detail": "feature_disabled"})

    monkeypatch.setattr(verifier, "_d_route_client", lambda: _Client())

    result = verifier.verify_d2_d5_flags(
        verifier.FeatureDConfig(allow_d2_d5=True, rollout_stage="d2")
    )

    assert result.status == "fail"
    assert "d2_rag:allowed_route_feature_disabled" in result.details["failures"]


def test_notification_scheduler_passes_default(monkeypatch) -> None:
    """Default notification scheduler posture should be wired through outbox."""

    monkeypatch.delenv("FEATURE_D_LEGACY_DIRECT_NOTIFY", raising=False)
    monkeypatch.delenv("SMTP_ENABLED", raising=False)

    result = verifier.verify_notification_scheduler(verifier.FeatureDConfig())

    assert result.status == "pass"
    assert result.details["adapter_posture"]["email"] == "mock"
    assert "dispatch_outbox" in result.details["schedule_keys"]


def test_notification_scheduler_fails_legacy_direct_notify(monkeypatch) -> None:
    """Legacy direct notify must remain disabled for release."""

    monkeypatch.setenv("FEATURE_D_LEGACY_DIRECT_NOTIFY", "true")

    result = verifier.verify_notification_scheduler(verifier.FeatureDConfig())

    assert result.status == "fail"
    assert "legacy_direct_notify_enabled" in result.details["failures"]
