"""Feature F release hardening verifier and RBAC tests."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import scripts.verify_feature_f_release as verifier
from backend.dependencies import get_current_user
from backend.routers import equipment as equipment_router
from backend.routers import live_alarms as live_alarms_router
from features.equipment import dashboard_data


def _user(role_level: int = 1, department: str = "생산관리팀", role: str = "EMPLOYEE"):
    """Create a minimal authenticated user context for dependency overrides."""

    return SimpleNamespace(
        user_id=1,
        employee_id="TEST-0001",
        username="테스트사용자",
        email="test@example.com",
        department=department,
        role_level=role_level,
        role=role,
    )


def _equipment_client(user=None) -> TestClient:
    """Create a minimal Feature F app with optional auth override."""

    app = FastAPI()
    app.include_router(equipment_router.router, prefix="/api")
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


def _live_alarm_client(user=None) -> TestClient:
    """Create a minimal live-alarm app with optional auth override."""

    app = FastAPI()
    app.include_router(live_alarms_router.router, prefix="/api")
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


def test_endpoint_surface_passes_current_openapi() -> None:
    """Current OpenAPI should expose the expected Feature F surface."""

    result = verifier.verify_endpoint_surface(verifier.FeatureFConfig())

    assert result.status == "pass"
    assert result.details["counts"] == {"equipment": 19, "live-alarms": 2}


def test_plc_contract_verifier_passes() -> None:
    """PLC stream contract and persistence wiring should be release-ready."""

    result = verifier.verify_plc_contract(verifier.FeatureFConfig())

    assert result.status == "pass"
    assert result.details["batch_stats"]["messages"] == 12


def test_adapter_registry_verifier_passes() -> None:
    """OPC-UA/MQTT/MES adapter registry should be contract-ready."""

    result = verifier.verify_adapter_registry(verifier.FeatureFConfig())

    assert result.status == "pass"
    assert "mes_adapter" in result.details["source_systems"]


def test_ml_engine_status_detects_release_artifacts(tmp_path, monkeypatch) -> None:
    """The 7 Feature F engine status keys should reflect deployable artifacts."""

    (tmp_path / "data/equipment").mkdir(parents=True)
    (tmp_path / "data/equipment/error_codes.db").write_bytes(b"")
    (tmp_path / "data/equipment/manuals").mkdir(parents=True)
    (tmp_path / "data/equipment/manuals/press_manual.md").write_text("프레스 베어링 교체 절차", encoding="utf-8")
    (tmp_path / "data/spc_ml").mkdir(parents=True)
    (tmp_path / "data/spc_ml/sample.csv").write_text("value\n1.0\n", encoding="utf-8")
    (tmp_path / "data/mold_ml").mkdir(parents=True)
    (tmp_path / "data/mold_ml/mold_training_data.csv").write_text("usage_ratio,remaining_life\n0.1,90000\n", encoding="utf-8")
    (tmp_path / "data/markov_ml").mkdir(parents=True)
    (tmp_path / "data/markov_ml/event_sequences.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    status = dashboard_data.get_ml_status()

    expected = {
        "error_tfidf",
        "spc_anomaly",
        "mold_xgboost",
        "markov",
        "rf_mtbf",
        "causality",
        "manual_rag",
    }
    assert expected <= set(status)
    assert all(status[key] is True for key in expected)


def test_ml_engines_endpoint_reports_current_7_engines() -> None:
    """ML inventory should use actual Feature F engines and avoid fake metrics."""

    client = _equipment_client(_user(role_level=4, department="생산기술팀"))

    response = client.get("/api/equipment/ml-engines/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["online_count"] == 7
    assert [engine["id"] for engine in payload["engines"]] == [
        "tfidf_error_search",
        "isolation_forest",
        "xgboost_mold",
        "markov",
        "rf_mtbf",
        "causality",
        "manual_rag",
    ]
    assert all(engine["accuracy"] is None for engine in payload["engines"])


def test_offline_queue_wiring_verifier_passes() -> None:
    """Field mode should call direct submit, enqueue, pending count, and flush."""

    result = verifier.verify_offline_queue_wiring(verifier.FeatureFConfig())

    assert result.status == "pass"


def test_data_lineage_wiring_verifier_passes() -> None:
    """Feature F responses and UI should expose lineage labels."""

    result = verifier.verify_data_lineage_wiring(verifier.FeatureFConfig())

    assert result.status == "pass"
    assert result.details["data_classes"] == ["real", "synthetic", "system", "unknown"]


def test_drawing_ocr_allowlist_verifier_passes() -> None:
    """Drawing OCR should be constrained to drawing_id and allowlisted roots."""

    result = verifier.verify_drawing_ocr_allowlist(verifier.FeatureFConfig())

    assert result.status == "pass"


def test_rbac_wiring_verifier_passes() -> None:
    """Feature F routers should use department+level guards."""

    result = verifier.verify_rbac_wiring(verifier.FeatureFConfig())

    assert result.status == "pass"


def test_live_plc_default_is_warning_not_blocker() -> None:
    """Actual OPC-UA bridge connectivity is not a default release blocker."""

    result = verifier.verify_live_plc_status(verifier.FeatureFConfig())

    assert result.status == "warn"


def test_equipment_read_requires_authentication() -> None:
    """Feature F read endpoints should reject unauthenticated requests."""

    client = _equipment_client()

    response = client.get("/api/equipment/dashboard/overview")

    assert response.status_code == 401


def test_equipment_read_allows_equipment_department() -> None:
    """Allowed equipment-facing departments can read dashboard data."""

    client = _equipment_client(_user(role_level=1, department="품질보증팀"))

    response = client.get("/api/equipment/dashboard/overview")

    assert response.status_code == 200


def test_equipment_read_rejects_non_equipment_department() -> None:
    """Non-equipment departments below L4 should be denied."""

    client = _equipment_client(_user(role_level=3, department="총무인사팀"))

    response = client.get("/api/equipment/dashboard/overview")

    assert response.status_code == 403
    assert response.json()["detail"] == "equipment_department_required"


def test_equipment_read_allows_l4_cross_department_override() -> None:
    """L4+ users should have cross-department Feature F read access."""

    client = _equipment_client(_user(role_level=4, department="총무인사팀", role="HR_ADMIN"))

    response = client.get("/api/equipment/dashboard/overview")

    assert response.status_code == 200


def test_field_submit_requires_l2_with_equipment_department() -> None:
    """Field submit should require at least L2 inside the equipment domain."""

    denied = _equipment_client(_user(role_level=1, department="생산관리팀")).post(
        "/api/equipment/inspection/submit",
        json={},
    )
    allowed_to_validate = _equipment_client(_user(role_level=2, department="생산관리팀")).post(
        "/api/equipment/inspection/submit",
        json={},
    )

    assert denied.status_code == 403
    assert allowed_to_validate.status_code == 422


def test_live_alarm_ack_requires_l3_with_equipment_department() -> None:
    """Live alarm ack should require an L3 equipment-domain operator."""

    denied = _live_alarm_client(_user(role_level=2, department="안전환경팀")).post(
        "/api/live-alarms/alarm-1/ack",
    )
    allowed_to_lookup = _live_alarm_client(_user(role_level=3, department="안전환경팀")).post(
        "/api/live-alarms/alarm-1/ack",
    )

    assert denied.status_code == 403
    assert allowed_to_lookup.status_code == 404
