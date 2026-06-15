"""P5 §6 — Jira 양방향 sync 단위 테스트."""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """compliance_changes.db 격리."""
    import features.compliance.change_detector as cd
    monkeypatch.setattr(cd, "CHANGE_DB_PATH", str(tmp_path / "ch.db"))
    cd.init_change_db()
    return cd


@pytest.fixture(autouse=True)
def _no_external(monkeypatch):
    """기본적으로 Jira 자격증명 비활성 — 개별 테스트가 명시 enable."""
    import config
    monkeypatch.setattr(config, "SLACK_WEBHOOK_URL", "", raising=False)
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    monkeypatch.delenv("JIRA_USER_EMAIL", raising=False)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    monkeypatch.delenv("JIRA_DEFAULT_PROJECT_KEY", raising=False)


def _enable_jira(monkeypatch, project_key: str = "ADP"):
    monkeypatch.setenv("JIRA_BASE_URL", "https://example.atlassian.net")
    monkeypatch.setenv("JIRA_USER_EMAIL", "tester@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "fake-token")
    monkeypatch.setenv("JIRA_DEFAULT_PROJECT_KEY", project_key)


class _FakeResp:
    def __init__(self, body=None, status_code=200, text=""):
        self._body = body or {}
        self.status_code = status_code
        self.text = text or json.dumps(self._body)

    def json(self):
        return self._body


# ─────────────────────────────────────────────────────────────
# jira_enabled / parse_webhook_status
# ─────────────────────────────────────────────────────────────


class TestEnabled:
    def test_disabled_when_no_env(self):
        from features.compliance.jira_sync import jira_enabled
        assert jira_enabled() is False

    def test_enabled_when_all_env_set(self, monkeypatch):
        _enable_jira(monkeypatch)
        from features.compliance.jira_sync import jira_enabled
        assert jira_enabled() is True

    def test_disabled_when_one_missing(self, monkeypatch):
        monkeypatch.setenv("JIRA_BASE_URL", "https://x.atlassian.net")
        monkeypatch.setenv("JIRA_USER_EMAIL", "a@b.c")
        # JIRA_API_TOKEN 누락
        from features.compliance.jira_sync import jira_enabled
        assert jira_enabled() is False


class TestWebhookParse:
    def test_in_progress_maps_to_reviewing(self):
        from features.compliance.jira_sync import parse_webhook_status
        payload = {"issue": {"key": "ADP-1",
                              "fields": {"status": {"name": "In Progress"}}}}
        assert parse_webhook_status(payload) == ("ADP-1", "reviewing")

    def test_done_maps_to_done(self):
        from features.compliance.jira_sync import parse_webhook_status
        payload = {"issue": {"key": "ADP-2",
                              "fields": {"status": {"name": "Done"}}}}
        assert parse_webhook_status(payload) == ("ADP-2", "done")

    def test_unknown_status_returns_empty_our_status(self):
        from features.compliance.jira_sync import parse_webhook_status
        payload = {"issue": {"key": "ADP-3",
                              "fields": {"status": {"name": "Approved"}}}}
        assert parse_webhook_status(payload) == ("ADP-3", "")

    def test_empty_payload_safe(self):
        from features.compliance.jira_sync import parse_webhook_status
        assert parse_webhook_status({}) == ("", "")
        assert parse_webhook_status(None) == ("", "")  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────
# create_issue (httpx mock)
# ─────────────────────────────────────────────────────────────


class TestCreateIssue:
    def test_skips_when_disabled(self):
        from features.compliance.jira_sync import create_issue
        out = create_issue("title")
        assert out == {"ok": False, "error": "jira_disabled"}

    def test_missing_project_key(self, monkeypatch):
        monkeypatch.setenv("JIRA_BASE_URL", "https://x.atlassian.net")
        monkeypatch.setenv("JIRA_USER_EMAIL", "a@b.c")
        monkeypatch.setenv("JIRA_API_TOKEN", "t")
        from features.compliance.jira_sync import create_issue
        out = create_issue("title")
        assert out["error"] == "missing_project_key"

    def test_create_success(self, monkeypatch):
        _enable_jira(monkeypatch)
        captured = {}

        def _fake_post(url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            return _FakeResp(body={"key": "ADP-42", "id": "10042"}, status_code=201)

        import httpx
        monkeypatch.setattr(httpx, "post", _fake_post)
        from features.compliance.jira_sync import create_issue
        out = create_issue("새 변경 — 환경팀 단독 LOW", description="HS 8708 관세")
        assert out["ok"] is True
        assert out["issue_key"] == "ADP-42"
        assert out["issue_url"].endswith("/browse/ADP-42")
        # body 검증 — ADF + project key + summary
        body = captured["json"]
        assert body["fields"]["project"]["key"] == "ADP"
        assert body["fields"]["summary"].startswith("새 변경")
        assert body["fields"]["description"]["type"] == "doc"

    def test_http_404_returns_error(self, monkeypatch):
        _enable_jira(monkeypatch, project_key="GHOST")

        def _fake_post(url, headers=None, json=None, timeout=None):
            return _FakeResp(body={"errorMessages": ["No project"]},
                             status_code=404, text='{"errorMessages":["No project"]}')

        import httpx
        monkeypatch.setattr(httpx, "post", _fake_post)
        from features.compliance.jira_sync import create_issue
        out = create_issue("x")
        assert out["ok"] is False
        assert "http_404" in out["error"]

    def test_http_401_returns_error(self, monkeypatch):
        _enable_jira(monkeypatch)

        def _fake_post(url, headers=None, json=None, timeout=None):
            return _FakeResp(status_code=401, text="Unauthorized")

        import httpx
        monkeypatch.setattr(httpx, "post", _fake_post)
        from features.compliance.jira_sync import create_issue
        out = create_issue("x")
        assert out["error"].startswith("http_401")


# ─────────────────────────────────────────────────────────────
# transition_issue
# ─────────────────────────────────────────────────────────────


class TestTransitionIssue:
    def test_skip_when_disabled(self):
        from features.compliance.jira_sync import transition_issue
        out = transition_issue("ADP-1", "Done")
        assert out["error"] == "jira_disabled"

    def test_transition_success(self, monkeypatch):
        _enable_jira(monkeypatch)
        captured = {}

        def _fake_get(url, headers=None, timeout=None):
            return _FakeResp(body={
                "transitions": [
                    {"id": "11", "to": {"name": "To Do"}},
                    {"id": "21", "to": {"name": "In Progress"}},
                    {"id": "31", "to": {"name": "Done"}},
                ],
            })

        def _fake_post(url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            return _FakeResp(status_code=204)

        import httpx
        monkeypatch.setattr(httpx, "get", _fake_get)
        monkeypatch.setattr(httpx, "post", _fake_post)
        from features.compliance.jira_sync import transition_issue
        out = transition_issue("ADP-7", "Done")
        assert out["ok"] is True
        assert out["transition_id"] == "31"
        assert captured["json"] == {"transition": {"id": "31"}}

    def test_unknown_target_status(self, monkeypatch):
        _enable_jira(monkeypatch)

        def _fake_get(url, headers=None, timeout=None):
            return _FakeResp(body={"transitions": [
                {"id": "11", "to": {"name": "To Do"}},
            ]})

        import httpx
        monkeypatch.setattr(httpx, "get", _fake_get)
        from features.compliance.jira_sync import transition_issue
        out = transition_issue("ADP-7", "Approved")
        assert out["ok"] is False
        assert out["error"].startswith("transition_not_found")


# ─────────────────────────────────────────────────────────────
# create_ticket (P3 D9) outbound 통합 — Jira 활성/비활성 분기
# ─────────────────────────────────────────────────────────────


class TestOutboundFromCollabTicket:
    def test_skips_jira_when_disabled(self, tmp_db):
        """Jira 자격 미설정 — collab_ticket.create_ticket 정상 동작 + Jira call 0."""
        from features.compliance.collab_ticket import create_ticket
        out = create_ticket(
            {"item_title": "다중 부서", "affected_departments": ["A팀", "B팀"]},
            change_id=1,
        )
        assert out["ok"] is True
        # external_id 비어있음 (Jira 미사용)
        assert out.get("external_id", "") == ""

    def test_creates_jira_when_enabled(self, tmp_db, monkeypatch):
        """Jira 자격 설정 + create_issue mock 성공 → external_id 채워짐."""
        _enable_jira(monkeypatch)
        # find_dept_owners → 빈 dict 로 graceful (employees.db 미존재 환경)

        def _fake_post(url, headers=None, json=None, timeout=None):
            if "/rest/api/3/issue" in url:
                return _FakeResp(body={"key": "ADP-99"}, status_code=201)
            return _FakeResp(status_code=200)

        import httpx
        monkeypatch.setattr(httpx, "post", _fake_post)
        from features.compliance.collab_ticket import create_ticket
        out = create_ticket(
            {"item_title": "다중 부서 변경",
             "affected_departments": ["환경", "품질"],
             "grade": "MEDIUM", "summary_ko": "..."},
            change_id=42,
        )
        assert out["ok"] is True
        assert out["external_id"] == "ADP-99"
        assert out["external_url"].endswith("/browse/ADP-99")

        # DB 에도 반영됐는지 확인
        conn = sqlite3.connect(tmp_db.CHANGE_DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT external_id, external_url, jira_last_sync_at FROM collab_tickets "
            "WHERE id = ?",
            (out["ticket_id"],),
        ).fetchone()
        conn.close()
        assert row["external_id"] == "ADP-99"
        assert row["jira_last_sync_at"] != ""


# ─────────────────────────────────────────────────────────────
# /jira/webhook endpoint (직접 핸들러 호출)
# ─────────────────────────────────────────────────────────────


class TestWebhookEndpoint:
    def test_unmapped_event_returns_ok_with_note(self, tmp_db):
        import asyncio
        from backend.routers.compliance import receive_jira_webhook
        from backend.schemas.compliance import JiraWebhookEvent
        # 빈 payload — issue 없음
        ev = JiraWebhookEvent(webhookEvent="jira:issue_deleted")
        out = asyncio.get_event_loop().run_until_complete(
            receive_jira_webhook(ev),
        )
        assert out.ok is True
        assert "unsupported_event" in out.note

    def test_no_matching_ticket(self, tmp_db):
        import asyncio
        from backend.routers.compliance import receive_jira_webhook
        from backend.schemas.compliance import JiraWebhookEvent
        ev = JiraWebhookEvent(
            webhookEvent="jira:issue_updated",
            issue={"key": "GHOST-1",
                   "fields": {"status": {"name": "Done"}}},
        )
        out = asyncio.get_event_loop().run_until_complete(
            receive_jira_webhook(ev),
        )
        assert out.ok is True
        assert out.note == "no_matching_ticket"

    def test_syncs_existing_ticket(self, tmp_db):
        import asyncio
        from backend.routers.compliance import receive_jira_webhook
        from backend.schemas.compliance import JiraWebhookEvent
        # collab_ticket 사전 생성 (external_id = JIRA-1 매칭)
        conn = sqlite3.connect(tmp_db.CHANGE_DB_PATH)
        conn.execute(
            """INSERT INTO collab_tickets
               (change_id, title, departments, status, external_id, created_at)
               VALUES (?,?,?,?,?,?)""",
            (1, "T", "[]", "created", "ADP-7", datetime.now().isoformat()),
        )
        conn.commit()
        ticket_id = conn.execute(
            "SELECT id FROM collab_tickets WHERE external_id = 'ADP-7'"
        ).fetchone()[0]
        conn.close()

        ev = JiraWebhookEvent(
            webhookEvent="jira:issue_updated",
            issue={"key": "ADP-7", "fields": {"status": {"name": "Done"}}},
        )
        out = asyncio.get_event_loop().run_until_complete(
            receive_jira_webhook(ev),
        )
        assert out.ok is True
        assert out.synced_ticket_id == ticket_id
        assert out.new_status == "done"
        assert out.note == "synced"

        # ticket status 도 업데이트
        conn = sqlite3.connect(tmp_db.CHANGE_DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT status, jira_last_sync_at FROM collab_tickets WHERE id = ?",
            (ticket_id,),
        ).fetchone()
        conn.close()
        assert row["status"] == "resolved"  # done → resolved
        assert row["jira_last_sync_at"] != ""
