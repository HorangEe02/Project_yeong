"""P2 Feature D D1 MVP 게이트 테스트."""

from __future__ import annotations

from types import SimpleNamespace


def _client_with_compliance_router(monkeypatch, tmp_path):
    """인증과 change DB를 격리한 compliance router TestClient를 만든다.

    Args:
        monkeypatch: pytest monkeypatch fixture.
        tmp_path: pytest tmp_path fixture.

    Returns:
        fastapi.testclient.TestClient: compliance router가 mount된 테스트 클라이언트.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.dependencies import get_current_user
    from backend.routers.compliance import router
    import features.compliance.change_detector as change_detector
    import features.compliance.alarm_aggregator as alarm_aggregator

    db_path = str(tmp_path / "compliance_changes.db")
    monkeypatch.setattr(change_detector, "CHANGE_DB_PATH", db_path)
    monkeypatch.setattr(alarm_aggregator, "CHANGE_DB_PATH", db_path)

    mock_user = SimpleNamespace(
        employee_id="QA-0001",
        user_id="QA-0001",
        username="qa",
        role="TEAM_LEAD",
        role_level=3,
    )
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    return TestClient(app, raise_server_exceptions=False)


def test_feature_d_flags_default_to_d1_only(monkeypatch):
    """기본 env에서는 D1만 활성이고 D2~D5는 봉인된다."""
    for key in (
        "FEATURE_D_D1_ALERTS",
        "FEATURE_D_D2_RAG",
        "FEATURE_D_D3_WHATIF",
        "FEATURE_D_D4_WORKFLOW",
        "FEATURE_D_D5_SUPPLY",
    ):
        monkeypatch.delenv(key, raising=False)

    from core.feature_flags import feature_d_flags_dict

    assert feature_d_flags_dict() == {
        "d1_alerts": True,
        "d2_rag": False,
        "d3_whatif": False,
        "d4_workflow": False,
        "d5_supply": False,
    }


def test_feature_d_flags_endpoint_default(monkeypatch):
    """GET /api/feature-flags/d가 백엔드 런타임 기본값을 반환한다."""
    for key in (
        "FEATURE_D_D1_ALERTS",
        "FEATURE_D_D2_RAG",
        "FEATURE_D_D3_WHATIF",
        "FEATURE_D_D4_WORKFLOW",
        "FEATURE_D_D5_SUPPLY",
    ):
        monkeypatch.delenv(key, raising=False)

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.routers.feature_flags import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    res = TestClient(app).get("/api/feature-flags/d")

    assert res.status_code == 200
    assert res.json() == {
        "version": "p2-d1-mvp",
        "feature": "D",
        "flags": {
            "d1_alerts": True,
            "d2_rag": False,
            "d3_whatif": False,
            "d4_workflow": False,
            "d5_supply": False,
        },
    }


def test_compliance_router_hides_d2_by_default(monkeypatch, tmp_path):
    """기본 env에서 D1 endpoint는 열리고 D2 endpoint는 404로 숨겨진다."""
    monkeypatch.delenv("FEATURE_D_D2_RAG", raising=False)
    client = _client_with_compliance_router(monkeypatch, tmp_path)

    d1 = client.get("/api/compliance/changes/feed")
    assert d1.status_code == 200
    assert d1.json()["items"] == []

    d2 = client.get("/api/compliance/glossary")
    assert d2.status_code == 404
    assert d2.json()["detail"] == "feature_disabled"


def test_compliance_router_reopens_d2_when_flag_enabled(monkeypatch, tmp_path):
    """FEATURE_D_D2_RAG=true이면 D2 endpoint가 runtime gate를 통과한다."""
    monkeypatch.setenv("FEATURE_D_D2_RAG", "true")
    client = _client_with_compliance_router(monkeypatch, tmp_path)

    res = client.get("/api/compliance/glossary")
    assert res.status_code == 200
    assert "terms" in res.json()
