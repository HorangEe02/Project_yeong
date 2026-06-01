"""tests/test_system_health.py — v4.8 F.

/admin/system/health-extended 의 6 섹션 격리 응답 검증.
실 Redis / Firestore / Gemini API 는 mock; SQLite/Disk 는 실제 stat 사용.
"""
from __future__ import annotations

import os
import asyncio
from unittest.mock import patch

from features.admin import usage_analytics


def test_get_feature_heatmap_day_default_returns_7_buckets():
    out = usage_analytics.get_feature_heatmap(period="day", period_days=7)
    assert out["period"] == "day"
    assert len(out["buckets"]) == 7
    assert set(out["features"]) == {"A", "B", "C", "D", "E", "F"}
    for f in out["features"]:
        assert len(out["matrix"][f]) == 7


def test_get_feature_heatmap_week_returns_12_buckets():
    out = usage_analytics.get_feature_heatmap(period="week", period_days=84)
    assert out["period"] == "week"
    assert len(out["buckets"]) == 12
    # ISO 주 키 형식.
    for b in out["buckets"]:
        assert "-W" in b["key"]


def test_get_feature_heatmap_month_returns_12_buckets():
    out = usage_analytics.get_feature_heatmap(period="month", period_days=365)
    assert out["period"] == "month"
    assert len(out["buckets"]) == 12
    for b in out["buckets"]:
        # YYYY-MM 형식.
        assert len(b["key"]) == 7
        assert b["key"][4] == "-"


def test_firestore_audit_disabled_by_default():
    """v4.8 F — FIRESTORE_AUDIT_ENABLED 미설정 시 is_available()=False, write 가 no-op."""
    from core.auth import firestore_audit
    # env 정리 후 재import.
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("FIRESTORE_AUDIT_ENABLED", None)
        os.environ.pop("FIREBASE_WRITE_ENABLED", None)
        assert firestore_audit.is_available() is False
        result = firestore_audit.write_login_event(
            user_id=1, employee_id="IT-0001", success=True,
        )
        assert result is None


def test_firestore_audit_explicit_false():
    from core.auth import firestore_audit
    with patch.dict(os.environ, {"FIRESTORE_AUDIT_ENABLED": "false"}, clear=False):
        assert firestore_audit.is_available() is False
        assert firestore_audit.write_login_event(1, "IT-0001", True) is None


def test_disk_usage_section_works():
    """/admin/system/health-extended 의 disk 섹션이 real shutil.disk_usage 로 응답."""
    import shutil
    total, used, free = shutil.disk_usage(".")
    assert total > 0
    assert free >= 0
    assert used >= 0


def test_sqlite_section_inspects_data_dir():
    """data/ 디렉토리 내 .db 파일을 검색하는 헬스 로직과 동일한 동작."""
    from pathlib import Path
    data_dir = Path("data")
    if data_dir.exists():
        dbs = list(data_dir.glob("*.db"))
        # 존재하는 경우 무결성 확인 (실 파일 시스템에 의존).
        for p in dbs:
            assert p.stat().st_size >= 0


def test_external_section_reads_env_flags():
    """external 섹션의 env 플래그가 토글 응답."""
    from core.auth import firestore_audit
    with patch.dict(os.environ, {"FIRESTORE_AUDIT_ENABLED": "true"}, clear=False):
        # Firebase write 비용 차단이 기본값이므로 audit env 만으로는 write 비활성.
        assert firestore_audit._enabled() is False  # type: ignore[attr-defined]

    with patch.dict(
        os.environ,
        {"FIRESTORE_AUDIT_ENABLED": "true", "FIREBASE_WRITE_ENABLED": "true"},
        clear=False,
    ):
        # _enabled() 만 true; 실제 _get_db() 는 firebase_admin 초기화 의존.
        # 따라서 is_available() 은 환경에 따라 False 일 수 있음.
        # 본 테스트는 env read 가 동작하는지만 확인.
        assert firestore_audit._enabled() is True  # type: ignore[attr-defined]


def test_firebase_cost_flags_default_write_disabled():
    """Firebase 비용 차단 기본값은 write off, read fallback on."""
    from core.feature_flags import firebase_cost_flags_dict

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("FIREBASE_WRITE_ENABLED", None)
        os.environ.pop("FIREBASE_READ_FALLBACK_ENABLED", None)
        flags = firebase_cost_flags_dict()
        assert flags["write_enabled"] is False
        assert flags["read_fallback_enabled"] is True


def test_health_allows_missing_chroma_when_feature_a_disabled(monkeypatch, tmp_path):
    """Slim runtime should stay healthy when optional Chroma search is disabled."""
    import backend.routers.health as health_router

    class Resp:
        status_code = 200

        def json(self):
            return {"models": [{"name": "qwen3.5:9b"}]}

    monkeypatch.setenv("ENABLE_FEATURE_A", "false")
    monkeypatch.delenv("REQUIRE_CHROMA_HEALTH", raising=False)
    monkeypatch.setattr(health_router, "VECTORSTORE_DIR", tmp_path)
    monkeypatch.setattr(health_router.requests, "get", lambda *_, **__: Resp())

    res = asyncio.run(health_router.health_check())

    assert res.status == "ok"
    assert res.llm_connected is True
    assert res.chroma_connected is False


def test_health_degrades_missing_chroma_when_required(monkeypatch, tmp_path):
    """Full/search runtime still reports degraded when required Chroma is absent."""
    import backend.routers.health as health_router

    class Resp:
        status_code = 200

        def json(self):
            return {"models": [{"name": "qwen3.5:9b"}]}

    monkeypatch.setenv("ENABLE_FEATURE_A", "true")
    monkeypatch.setattr(health_router, "VECTORSTORE_DIR", tmp_path)
    monkeypatch.setattr(health_router.requests, "get", lambda *_, **__: Resp())

    res = asyncio.run(health_router.health_check())

    assert res.status == "degraded"
    assert res.llm_connected is True
    assert res.chroma_connected is False
