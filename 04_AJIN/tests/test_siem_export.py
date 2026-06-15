"""tests/test_siem_export.py — PR-E6 SIEM Export.

8 케이스:
1. test_to_siem_json_basic              — row 1건 → Splunk HEC 구조
2. test_to_siem_json_missing_fields     — partial row
3. test_to_cef_basic                    — row 1건 → CEF 라인 RFC 형식
4. test_to_cef_extension_escapes_pipe_equal — = / | escape 검증
5. test_to_cef_severity_mapping         — info→3 / warning→6 / critical→9
6. test_to_leef_basic                   — row 1건 → LEEF 2.0 라인
7. test_to_leef_delim_consistency       — delim 구분자 일관성
8. test_endpoint_unauthorized_role      — role<5 → 403 (FastAPI TestClient)
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.audit_export import (
    _cef_extension,
    _severity_to_cef,
    to_cef,
    to_leef,
    to_siem_json,
)

# ── 공용 fixture row ──────────────────────────────────────────────────────────

_FULL_ROW = {
    "ts": "2025-05-18T10:00:00+00:00",
    "actor": "IT-0001",
    "action": "GET /api/admin/users",
    "target": "users list filtered=5",
    "result": "200",
    "ip_address": "10.0.0.1",
    "user_agent": "Mozilla/5.0",
    "metadata": {"dept": "IT전략팀"},
    "severity": "info",
}

_PARTIAL_ROW: dict = {}  # 모든 필드 누락


# ════════════════════════════════════════════════════════════
# 1. to_siem_json — 기본 구조
# ════════════════════════════════════════════════════════════


def test_to_siem_json_basic():
    result = to_siem_json([_FULL_ROW])
    assert len(result) == 1
    item = result[0]
    # Splunk HEC 최상위 필드
    assert item["source"] == "ajin.audit_log"
    assert item["sourcetype"] == "ajin:api_audit"
    assert item["host"] == "ajin-backend"
    assert item["time"] == "2025-05-18T10:00:00+00:00"
    # event 하위 필드
    ev = item["event"]
    assert ev["actor"] == "IT-0001"
    assert ev["action"] == "GET /api/admin/users"
    assert ev["ip"] == "10.0.0.1"
    assert ev["result"] == "200"


# ════════════════════════════════════════════════════════════
# 2. to_siem_json — partial row (모든 값 누락)
# ════════════════════════════════════════════════════════════


def test_to_siem_json_missing_fields():
    result = to_siem_json([_PARTIAL_ROW])
    assert len(result) == 1
    item = result[0]
    # 빠진 필드는 None / 기본값으로 처리, KeyError 없이 반환
    assert "time" in item
    assert item["source"] == "ajin.audit_log"
    ev = item["event"]
    assert ev["actor"] is None
    assert ev["ip"] is None


# ════════════════════════════════════════════════════════════
# 3. to_cef — 기본 CEF 라인 형식
# ════════════════════════════════════════════════════════════


def test_to_cef_basic():
    result = to_cef([_FULL_ROW])
    assert len(result) == 1
    line = result[0]
    # CEF 헤더: CEF:0|Vendor|Product|Version|SignatureID|Name|Severity|
    assert line.startswith("CEF:0|AJIN|AI-Assistant|4.7|")
    parts = line.split("|")
    # 최소 8 파이프 분리 필드 (헤더 7 + extension)
    assert len(parts) >= 8
    # suser 필드가 extension 에 포함
    assert "suser=" in line
    assert "IT-0001" in line


# ════════════════════════════════════════════════════════════
# 4. to_cef — = 와 | escape
# ════════════════════════════════════════════════════════════


def test_to_cef_extension_escapes_pipe_equal():
    row_with_special = {
        **_FULL_ROW,
        "actor": "user=admin|root",
        "action": "key=val|test",
    }
    result = to_cef([row_with_special])
    assert len(result) == 1
    ext_part = result[0].split("|", 7)[-1]  # extension 는 마지막 파이프 이후
    # = 와 | 가 escape 되어야 함
    assert "\\=" in ext_part or "\\|" in ext_part


def test_to_cef_extension_helper_escapes():
    """_cef_extension 단독 검증."""
    ext = _cef_extension({"k": "a=b|c"})
    assert "\\=" in ext
    assert "\\|" in ext


# ════════════════════════════════════════════════════════════
# 5. to_cef — severity 매핑
# ════════════════════════════════════════════════════════════


def test_to_cef_severity_mapping():
    assert _severity_to_cef("info") == 3
    assert _severity_to_cef("warning") == 6
    assert _severity_to_cef("critical") == 9
    assert _severity_to_cef("error") == 7
    # 알 수 없는 레벨 → 기본 3
    assert _severity_to_cef("unknown_level") == 3


# ════════════════════════════════════════════════════════════
# 6. to_leef — 기본 LEEF 2.0 라인 형식
# ════════════════════════════════════════════════════════════


def test_to_leef_basic():
    result = to_leef([_FULL_ROW])
    assert len(result) == 1
    line = result[0]
    assert line.startswith("LEEF:2.0|AJIN|AI-Assistant|4.7|")
    # usrName 필드가 extension 에 포함
    assert "usrName=IT-0001" in line
    assert "action=" in line
    assert "devTime=" in line


# ════════════════════════════════════════════════════════════
# 7. to_leef — delim 구분자 일관성
# ════════════════════════════════════════════════════════════


def test_to_leef_delim_consistency():
    result = to_leef([_FULL_ROW])
    line = result[0]
    # LEEF:2.0|Vendor|Product|Version|EventID|{delim}|Extension
    # 6번째 필드(인덱스 5)가 delim 단일 문자여야 함
    parts = line.split("|")
    assert len(parts) >= 7
    delim = parts[5]
    assert len(delim) == 1  # 단일 구분자 문자
    # extension 내부는 해당 delim 으로 분리
    ext = parts[6]
    assert delim in ext  # 여러 키=값 쌍이 delim 으로 구분됨


# ════════════════════════════════════════════════════════════
# 8. GET /audit/export/siem — role < 5 → 403
# ════════════════════════════════════════════════════════════


def test_endpoint_unauthorized_role():
    """role_level=3 (TEAM_LEAD) 사용자가 호출하면 403을 반환해야 한다."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.dependencies import get_current_user
    from backend.routers.admin import router

    # role_level=3 mock user (SYS_ADMIN=L5 미만)
    mock_user = MagicMock()
    mock_user.role = "TEAM_LEAD"
    mock_user.employee_id = "IT-0099"

    app = FastAPI()
    # router already has prefix="/admin" — mount at /api to get /api/admin/...
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: mock_user

    with patch("core.auth.rbac.get_role_level", return_value=3):
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/admin/audit/export/siem?format=json")

    assert r.status_code == 403
