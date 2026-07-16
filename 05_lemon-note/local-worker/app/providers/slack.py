"""Slack Incoming Webhook 전송 Provider (stdlib urllib 사용, 추가 의존성 없음).

주의(문서 검토 finding #11): Incoming Webhook은 URL에 고정된 단일 채널로만 전송된다.
요청의 channel_label 은 실제 전송 대상을 바꾸지 못하며 표시용 라벨일 뿐이다.
데모에서는 Webhook 미설정 시 SLACK_SIMULATE=1 이면 성공한 것처럼 시뮬레이션한다.
"""
import json
import urllib.error
import urllib.request

from .. import config


def send_summary(text: str, webhook_url: str = None) -> dict:
    url = (webhook_url or config.SLACK_WEBHOOK_URL).strip()
    if not url:
        if config.SLACK_SIMULATE:
            return {"status": "sent", "http_status": 200,
                    "body": "[simulated] Webhook 미설정 — 데모 시뮬레이션 전송",
                    "simulated": True}
        return {"status": "failed", "http_status": None,
                "body": "webhook_not_configured", "simulated": False}

    data = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", "ignore")
            return {"status": "sent", "http_status": resp.status,
                    "body": body, "simulated": False}
    except urllib.error.HTTPError as e:
        return {"status": "failed", "http_status": e.code,
                "body": e.read().decode("utf-8", "ignore")[:500], "simulated": False}
    except Exception as e:  # noqa: BLE001
        return {"status": "failed", "http_status": None,
                "body": str(e)[:500], "simulated": False}
