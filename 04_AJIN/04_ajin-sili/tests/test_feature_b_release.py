"""Feature B release verifier tests."""

from __future__ import annotations

from pathlib import Path

import scripts.verify_feature_b_release as verifier


def _write_valid_signoff(path: Path) -> None:
    """Write a complete secret-free Feature B business signoff fixture."""

    import json

    payload = {
        "templates": [
            {
                "template_id": template_id,
                "owner_department": "Quality Assurance",
                "reviewer": "B-REVIEWER",
                "approved_at": "2026-05-21",
                "version": "v1",
                "doc_types": ["8d_report", "ecn", "oem_email", "internal_email"],
            }
            for template_id in verifier.PRIORITY_TEMPLATE_IDS
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_storage_ownership_smoke_passes() -> None:
    """Storage ownership smoke should enforce owner/admin/other behavior."""

    result = verifier.verify_storage_ownership()

    assert result.status == "pass"
    assert result.details["outcomes"]["owner"] == "allow"
    assert result.details["outcomes"]["other"] == "deny_403"
    assert result.details["outcomes"]["missing_object"] == "deny_409"


def test_mail_guard_operational_smoke_passes(monkeypatch) -> None:
    """Mail guard release smoke should pass with default sealed adapter."""

    monkeypatch.delenv("AJIN_MAIL_MODE", raising=False)
    monkeypatch.delenv("AJIN_MAIL_REAL_ENABLED", raising=False)

    result = verifier.verify_mail_guard()

    assert result.status == "pass"
    assert result.details["decisions"]["external_ack_required"] == "needs_external_ack"
    assert result.details["decisions"]["external_ack_allow"] == "allow"


def test_mail_guard_fails_when_real_smtp_enabled(monkeypatch) -> None:
    """Real SMTP mode should fail until the adapter is implemented."""

    monkeypatch.setenv("AJIN_MAIL_MODE", "real")
    monkeypatch.setenv("AJIN_MAIL_REAL_ENABLED", "1")

    result = verifier.verify_mail_guard()

    assert result.status == "fail"
    assert "RealSmtpAdapter" in result.summary


def test_priority_templates_render() -> None:
    """Priority templates should render with strict sample contexts."""

    result = verifier.verify_priority_templates(verifier.FeatureBConfig())

    assert result.status == "pass"
    assert result.details["rendered_count"] == 8


def test_run_verification_fails_without_business_signoff(monkeypatch) -> None:
    """Release verification should fail closed when business signoff is absent."""

    monkeypatch.delenv("AJIN_MAIL_MODE", raising=False)
    monkeypatch.delenv("AJIN_MAIL_REAL_ENABLED", raising=False)

    report = verifier.run_verification(verifier.FeatureBConfig())
    statuses = {check["name"]: check["status"] for check in report["checks"]}

    assert statuses["storage_ownership_smoke"] == "pass"
    assert statuses["mail_guard_operational_smoke"] == "pass"
    assert statuses["draft_template_render_smoke"] == "pass"
    assert statuses["template_business_signoff"] == "fail"
    assert statuses["draft_export_compatibility"] == "pass"
    assert report["summary"]["status"] == "fail"


def test_run_verification_passes_with_business_signoff(tmp_path: Path, monkeypatch) -> None:
    """A signoff file should turn the business review posture to pass."""

    monkeypatch.delenv("AJIN_MAIL_MODE", raising=False)
    monkeypatch.delenv("AJIN_MAIL_REAL_ENABLED", raising=False)
    signoff = tmp_path / "feature-b-signoff.json"
    _write_valid_signoff(signoff)

    report = verifier.run_verification(verifier.FeatureBConfig(signoff_path=signoff))
    statuses = {check["name"]: check["status"] for check in report["checks"]}

    assert statuses["template_business_signoff"] == "pass"
    assert statuses["draft_export_compatibility"] == "pass"
    assert report["summary"]["status"] == "pass"


def test_business_signoff_rejects_incomplete_file(tmp_path: Path) -> None:
    """A signoff file must cover every priority template with required fields."""

    signoff = tmp_path / "feature-b-signoff.json"
    signoff.write_text('{"templates": [{"template_id": "kb_8d_report"}]}', encoding="utf-8")

    result = verifier.verify_template_business_signoff(
        verifier.FeatureBConfig(signoff_path=signoff),
    )

    assert result.status == "fail"
    assert "catalog_oem_email" in result.details["missing_templates"]


def test_export_compatibility_passes() -> None:
    """HWPX package and SharePoint request-shape smoke checks should pass."""

    result = verifier.verify_export_compatibility()

    assert result.status == "pass"
    assert result.details["outcomes"]["sharepoint_small"] == "PUT:single_put"
