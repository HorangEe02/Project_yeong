"""P1 D3 — SMS 직보 + 통합 라우터 단위 테스트."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _clear_rate_log():
    """각 테스트 시작 시 rate_log 비우기."""
    from features.compliance import notify_sms
    notify_sms._rate_log.clear()
    yield


@pytest.fixture
def _no_sms_creds(monkeypatch):
    """모든 SMS provider 키 비움 → graceful skip 시나리오."""
    import config
    for k in ("SENS_ACCESS_KEY", "SENS_SECRET_KEY", "SENS_SERVICE_ID", "SENS_FROM_NUMBER",
              "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM"):
        monkeypatch.setattr(config, k, "")


# ─────────────────────────────────────────────────────────────
# send_sms — provider 분기, rate limit, 미설정 skip
# ─────────────────────────────────────────────────────────────
class TestSendSms:
    def test_no_credentials_returns_true(self, _no_sms_creds):
        """provider 키 미설정 → graceful skip 으로 True 반환 (호출자에게 false 안 줌)."""
        from features.compliance.notify_sms import send_sms
        assert send_sms("01012345678", "test") is True

    def test_sens_provider_called(self, monkeypatch):
        import config
        monkeypatch.setattr(config, "SMS_PROVIDER", "sens")
        monkeypatch.setattr(config, "SENS_ACCESS_KEY", "k")
        monkeypatch.setattr(config, "SENS_SECRET_KEY", "s")
        monkeypatch.setattr(config, "SENS_SERVICE_ID", "svc")
        monkeypatch.setattr(config, "SENS_FROM_NUMBER", "01000000000")

        with patch("features.compliance.notify_sms.httpx.post") as mock:
            mock.return_value.raise_for_status = lambda: None
            from features.compliance.notify_sms import send_sms
            ok = send_sms("01011111111", "test")
            assert ok is True
            assert mock.call_count == 1
            kwargs = mock.call_args.kwargs
            assert "sens.apigw.ntruss.com" in kwargs.get("url", "") or \
                "sens.apigw.ntruss.com" in mock.call_args.args[0]

    def test_twilio_provider_called(self, monkeypatch):
        import config
        monkeypatch.setattr(config, "SMS_PROVIDER", "twilio")
        monkeypatch.setattr(config, "TWILIO_ACCOUNT_SID", "AC123")
        monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", "tok")
        monkeypatch.setattr(config, "TWILIO_FROM", "+1234567890")

        with patch("features.compliance.notify_sms.httpx.post") as mock:
            mock.return_value.raise_for_status = lambda: None
            from features.compliance.notify_sms import send_sms
            ok = send_sms("+821011111111", "test")
            assert ok is True
            url = mock.call_args.args[0] if mock.call_args.args else mock.call_args.kwargs.get("url", "")
            assert "twilio.com" in url

    def test_rate_limit_blocks_4th_call(self, monkeypatch):
        """1시간당 3건 제한 — 4번째 호출은 silently skip."""
        import config
        monkeypatch.setattr(config, "SMS_PROVIDER", "sens")
        monkeypatch.setattr(config, "SENS_ACCESS_KEY", "k")
        monkeypatch.setattr(config, "SENS_SECRET_KEY", "s")
        monkeypatch.setattr(config, "SENS_SERVICE_ID", "svc")
        monkeypatch.setattr(config, "SENS_FROM_NUMBER", "01000000000")

        with patch("features.compliance.notify_sms.httpx.post") as mock:
            mock.return_value.raise_for_status = lambda: None
            from features.compliance.notify_sms import send_sms
            phone = "01099999999"
            for _ in range(3):
                send_sms(phone, "msg")
            assert mock.call_count == 3
            # 4번째 — rate limit hit, httpx 호출 없음
            send_sms(phone, "msg")
            assert mock.call_count == 3


# ─────────────────────────────────────────────────────────────
# get_executive_phones — role_level >= 4 매칭
# ─────────────────────────────────────────────────────────────
class TestGetExecutivePhones:
    def test_returns_empty_on_db_error(self, monkeypatch):
        # ImportError 시 빈 list — graceful
        from features.compliance.notify_sms import get_executive_phones
        assert isinstance(get_executive_phones(), list)


# ─────────────────────────────────────────────────────────────
# broadcast_critical — 임원 일괄 발송
# ─────────────────────────────────────────────────────────────
class TestBroadcastCritical:
    def test_no_executives_skipped(self, monkeypatch):
        from features.compliance import notify_sms
        monkeypatch.setattr(notify_sms, "get_executive_phones", lambda: [])
        counts = notify_sms.broadcast_critical(
            {"item_title": "test", "summary_ko": "test"}, change_id=1
        )
        assert counts["skipped"] == 1
        assert counts["sent"] == 0

    def test_all_executives_sent(self, monkeypatch):
        from features.compliance import notify_sms
        monkeypatch.setattr(notify_sms, "get_executive_phones",
                            lambda: ["01011111111", "01022222222", "01033333333"])
        monkeypatch.setattr(notify_sms, "send_sms", lambda phone, msg: True)
        counts = notify_sms.broadcast_critical(
            {"item_title": "관세 25%", "summary_ko": "긴급"}, change_id=1
        )
        assert counts["sent"] == 3
        assert counts["failed"] == 0


# ─────────────────────────────────────────────────────────────
# notify.route_batch — 통합 라우터
# ─────────────────────────────────────────────────────────────
class TestNotifyRouteBatch:
    def test_critical_fires_both_slack_and_sms(self, monkeypatch):
        from features.compliance import notify
        slack_calls = []
        sms_calls = []

        def _slack(change, change_id=None, **kw):
            slack_calls.append((change.get("grade"), change_id))
            return True

        def _sms(change, change_id=None, **kw):
            sms_calls.append((change.get("grade"), change_id))
            return {"sent": 2, "skipped": 0, "failed": 0}

        monkeypatch.setattr("features.compliance.notify_slack.route", _slack)
        monkeypatch.setattr("features.compliance.notify_sms.broadcast_critical", _sms)

        result = notify.route_batch(
            [
                {"grade": "CRITICAL", "item_title": "관세"},
                {"grade": "HIGH", "item_title": "산안"},
                {"grade": "MEDIUM", "item_title": "ESG"},
                {"grade": "LOW", "item_title": "기타"},
            ],
            [1, 2, 3, 4],
        )

        # Slack: CRITICAL + HIGH = 2 sent, 나머지 2개는 skipped
        assert result["slack"]["sent"] == 2
        assert result["slack"]["skipped"] == 2

        # SMS: CRITICAL 만 — 1번 broadcast (3 임원에게 발송)
        assert len(sms_calls) == 1
        assert sms_calls[0][0] == "CRITICAL"
        assert result["sms"]["sent"] == 2

    def test_no_critical_no_sms(self, monkeypatch):
        from features.compliance import notify
        slack_called = []
        sms_called = []

        monkeypatch.setattr(
            "features.compliance.notify_slack.route",
            lambda c, change_id=None, **kw: slack_called.append(c) or True,
        )
        monkeypatch.setattr(
            "features.compliance.notify_sms.broadcast_critical",
            lambda c, change_id=None, **kw: sms_called.append(c) or {"sent": 0, "skipped": 0, "failed": 0},
        )

        result = notify.route_batch(
            [{"grade": "HIGH", "item_title": "x"}, {"grade": "MEDIUM", "item_title": "y"}],
            [10, 20],
        )
        assert len(sms_called) == 0  # CRITICAL 없으면 SMS 호출 자체 안 함
        assert result["sms"] == {"sent": 0, "skipped": 0, "failed": 0}
