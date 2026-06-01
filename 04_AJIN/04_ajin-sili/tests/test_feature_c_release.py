"""Feature C release verifier tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import scripts.verify_feature_c_release as verifier


def test_endpoint_surface_passes_current_openapi() -> None:
    """Current OpenAPI should expose the expected Feature C surface."""

    result = verifier.verify_endpoint_surface(verifier.FeatureCConfig())

    assert result.status == "pass"
    assert result.details["counts"] == {
        "onboarding": 31,
        "scenarios": 5,
        "feature_flags": 3,
    }


def test_endpoint_surface_fails_when_required_route_missing(tmp_path: Path) -> None:
    """Missing core routes should fail before release."""

    openapi = {"paths": {"/api/onboarding/health": {"get": {}}}}
    openapi_path = tmp_path / "openapi.json"
    openapi_path.write_text(json.dumps(openapi), encoding="utf-8")

    result = verifier.verify_endpoint_surface(
        verifier.FeatureCConfig(root=tmp_path, openapi_path=openapi_path)
    )

    assert result.status == "fail"
    assert "missing_counts" in result.details
    assert result.details["missing_required"]


def test_paid_llm_primary_fails_without_override(monkeypatch) -> None:
    """Gemini key with non-Ollama primary is a release blocker by default."""

    monkeypatch.setenv("GEMINI_API_KEY", "secret-value-not-printed")
    monkeypatch.setenv("LLM_ROUTER_PRIMARY", "gemini")
    monkeypatch.delenv("FEATURE_C_COMPARE_MODE", raising=False)

    result = verifier.verify_llm_cost_posture(verifier.FeatureCConfig())

    assert result.status == "fail"
    assert result.details["gemini_api_key_present"] is True
    assert "gemini_key_present_with_non_ollama_primary" in result.details["blockers"]
    assert "secret-value-not-printed" not in json.dumps(result.to_dict(), ensure_ascii=False)


def test_ollama_primary_passes_with_gemini_key(monkeypatch) -> None:
    """A present Gemini key is acceptable when Feature C routes Ollama first."""

    monkeypatch.setenv("GEMINI_API_KEY", "secret-value-not-printed")
    monkeypatch.setenv("LLM_ROUTER_PRIMARY", "ollama")
    monkeypatch.delenv("FEATURE_C_COMPARE_MODE", raising=False)

    result = verifier.verify_llm_cost_posture(verifier.FeatureCConfig())

    assert result.status == "pass"


def test_compare_mode_fails_without_paid_llm_override(monkeypatch) -> None:
    """Compare mode doubles model calls and must be explicit for release."""

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_ROUTER_PRIMARY", "ollama")
    monkeypatch.setenv("FEATURE_C_COMPARE_MODE", "true")

    result = verifier.verify_llm_cost_posture(verifier.FeatureCConfig())

    assert result.status == "fail"
    assert "feature_c_compare_mode_enabled" in result.details["blockers"]


def test_paid_llm_override_turns_blocker_into_warn(monkeypatch) -> None:
    """Canary/demo runs can explicitly allow paid LLM risk as a warning."""

    monkeypatch.setenv("GEMINI_API_KEY", "secret-value-not-printed")
    monkeypatch.setenv("LLM_ROUTER_PRIMARY", "gemini")
    monkeypatch.setenv("FEATURE_C_COMPARE_MODE", "1")

    result = verifier.verify_llm_cost_posture(
        verifier.FeatureCConfig(allow_paid_llm=True)
    )

    assert result.status == "warn"
    assert len(result.details["allowed_risks"]) == 2


def test_release_dotenv_is_loaded_without_secret_value_leak(tmp_path: Path, monkeypatch) -> None:
    """CLI dotenv loading should affect posture without exposing secret values."""

    secret = "test-secret-not-printed"
    (tmp_path / ".env").write_text(
        "\n".join([
            f"GEMINI_API_KEY={secret}",
            "LLM_ROUTER_PRIMARY=ollama",
        ]),
        encoding="utf-8",
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_ROUTER_PRIMARY", raising=False)

    assert verifier._load_release_dotenv(tmp_path) is True
    result = verifier.verify_llm_cost_posture(verifier.FeatureCConfig(root=tmp_path))

    assert result.status == "pass"
    assert result.details["gemini_api_key_present"] is True
    assert result.details["llm_router_primary"] == "ollama"
    assert secret not in json.dumps(result.to_dict(), ensure_ascii=False)


def test_llm_failure_posture_passes() -> None:
    """Fallback, circuit, metrics, and runtime guard smoke should pass."""

    result = verifier.verify_llm_failure_posture(verifier.FeatureCConfig())

    assert result.status == "pass"
    assert result.details["final_provider"] == "ollama"
    assert result.details["guard_actual"]["/api/onboarding/chat"] is True
    assert result.details["guard_actual"]["/api/onboarding/health"] is False


def test_llm_failure_posture_restores_cost_environment(monkeypatch) -> None:
    """Failure smoke imports should not mutate the cost posture environment."""

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_ROUTER_PRIMARY", "ollama")
    monkeypatch.delenv("FEATURE_C_COMPARE_MODE", raising=False)
    before = {key: os.environ.get(key) for key in verifier.ENV_POSTURE_KEYS}

    result = verifier.verify_llm_failure_posture(verifier.FeatureCConfig())
    after = {key: os.environ.get(key) for key in verifier.ENV_POSTURE_KEYS}

    assert result.status == "pass"
    assert after == before


def test_feature_flag_rollout_passes_after_frontend_wiring() -> None:
    """Feature C flags should be defined and key frontend flags consumed."""

    result = verifier.verify_feature_flag_rollout(verifier.FeatureCConfig())

    assert result.status == "pass"
    assert "multi_llm" in result.details["flag_keys"]
    assert result.details["missing_frontend_markers"] == []


def test_content_assets_fail_when_directories_missing(tmp_path: Path) -> None:
    """Broken content roots should fail the release gate."""

    result = verifier.verify_content_assets(verifier.FeatureCConfig(root=tmp_path))

    assert result.status == "fail"
    assert "quick_questions_dir_missing" in result.details["failures"]


def test_content_signoff_fails_without_business_file() -> None:
    """Human department signoff is a release blocker when no file is provided."""

    result = verifier.verify_content_signoff(verifier.FeatureCConfig())

    assert result.status == "fail"


def test_docker_slim_packages_feature_c_content() -> None:
    """Cloud Run slim images should include runtime Feature C training assets."""

    result = verifier.verify_docker_slim_content_packaging(verifier.FeatureCConfig())

    assert result.status == "pass"
    assert result.details["full_knowledge_base_copy"] is True


def test_docker_slim_packaging_fails_when_assets_are_missing(tmp_path: Path) -> None:
    """A slim image with only draft templates should fail the Feature C gate."""

    (tmp_path / "Dockerfile").write_text(
        "\n".join([
            "FROM python:3.11-slim AS base",
            "FROM base AS slim",
            "COPY data/knowledge_base/templates/ ./data/knowledge_base/templates/",
            "FROM slim AS default",
        ]),
        encoding="utf-8",
    )

    result = verifier.verify_docker_slim_content_packaging(
        verifier.FeatureCConfig(root=tmp_path)
    )

    assert result.status == "fail"
    assert "sops" in result.details["missing_assets"]
    assert "quick_questions" in result.details["missing_assets"]


def test_content_signoff_passes_with_business_file(tmp_path: Path) -> None:
    """A signoff file should turn the human content review posture to pass."""

    signoff = tmp_path / "feature-c-signoff.md"
    signoff.write_text("# Feature C content signoff\n", encoding="utf-8")

    result = verifier.verify_content_signoff(
        verifier.FeatureCConfig(root=tmp_path, content_signoff_path=signoff)
    )

    assert result.status == "pass"


def test_run_verification_fails_for_signoff_by_default(monkeypatch) -> None:
    """Default local posture should block release until human signoff exists."""

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_ROUTER_PRIMARY", "ollama")
    monkeypatch.delenv("FEATURE_C_COMPARE_MODE", raising=False)

    report = verifier.run_verification(verifier.FeatureCConfig())
    statuses = {check["name"]: check["status"] for check in report["checks"]}

    assert statuses["feature_c_endpoint_surface"] == "pass"
    assert statuses["llm_cost_posture"] == "pass"
    assert statuses["llm_failure_posture"] == "pass"
    assert statuses["feature_c_flag_rollout"] == "pass"
    assert statuses["feature_c_content_assets"] in {"pass", "warn"}
    assert statuses["feature_c_content_signoff"] == "fail"
    assert report["summary"]["status"] == "fail"
