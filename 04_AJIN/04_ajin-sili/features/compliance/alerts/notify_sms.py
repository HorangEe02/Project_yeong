"""P1 D3 — SMS 직보 (CRITICAL 임원 알림).

Provider abstraction: Naver Cloud SENS (한국 기본) / Twilio (해외).
Slack 라우팅과 별개 — `notify.py` 통합 라우터에서 둘 다 호출.

설계:
  1. Provider 미설정 시 silently skip (파이프라인 차단 안 함).
  2. Rate limit — 임원 1명 시간당 3건 (in-memory dict).
  3. 80자 이내 단문. 디테일은 SMS 본문의 변경 피드 deeplink 로.
  4. role_level >= 4 (본부장+) 사용자만 발송 대상.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from collections import defaultdict
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Rate limit — 임원 1명당 시간당 3건
# ─────────────────────────────────────────────────────────────

_RATE_LIMIT_PER_HOUR = 3
_rate_log: dict[str, list[float]] = defaultdict(list)


def _rate_limit_ok(phone: str) -> bool:
    """phone 별 발송 횟수가 시간당 N건 이하인지 확인 + 카운터 갱신."""
    now = time.time()
    window_start = now - 3600
    history = _rate_log[phone] = [t for t in _rate_log[phone] if t > window_start]
    if len(history) >= _RATE_LIMIT_PER_HOUR:
        return False
    history.append(now)
    return True


# ─────────────────────────────────────────────────────────────
# Provider — Naver Cloud SENS
# ─────────────────────────────────────────────────────────────


def _send_via_sens(phone: str, message: str, timeout: float = 5.0) -> bool:
    """Naver Cloud SENS REST API — SMS 발송."""
    from config import SENS_ACCESS_KEY, SENS_SECRET_KEY, SENS_SERVICE_ID, SENS_FROM_NUMBER

    if not all([SENS_ACCESS_KEY, SENS_SECRET_KEY, SENS_SERVICE_ID, SENS_FROM_NUMBER]):
        logger.debug("SENS 키 미설정 — skip")
        return True  # graceful skip — 호출자에게 false 안 줌 (의도된 미설정)

    url = f"https://sens.apigw.ntruss.com/sms/v2/services/{SENS_SERVICE_ID}/messages"
    timestamp = str(int(time.time() * 1000))
    method = "POST"
    uri = f"/sms/v2/services/{SENS_SERVICE_ID}/messages"

    sign_str = f"{method} {uri}\n{timestamp}\n{SENS_ACCESS_KEY}"
    signature = base64.b64encode(
        hmac.new(SENS_SECRET_KEY.encode(), sign_str.encode(), hashlib.sha256).digest()
    ).decode()

    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "x-ncp-apigw-timestamp": timestamp,
        "x-ncp-iam-access-key": SENS_ACCESS_KEY,
        "x-ncp-apigw-signature-v2": signature,
    }
    body = {
        "type": "SMS",
        "from": SENS_FROM_NUMBER,
        "content": message[:80],  # 80자 이내 SMS
        "messages": [{"to": phone}],
    }

    try:
        r = httpx.post(url, headers=headers, json=body, timeout=timeout)
        r.raise_for_status()
        return True
    except httpx.HTTPError as e:
        logger.warning("SENS 발송 실패 phone=%s: %s", phone[-4:], e)
        return False


# ─────────────────────────────────────────────────────────────
# Provider — Twilio
# ─────────────────────────────────────────────────────────────


def _send_via_twilio(phone: str, message: str, timeout: float = 5.0) -> bool:
    """Twilio REST API — 해외 임원 발송."""
    from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM

    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM]):
        logger.debug("Twilio 키 미설정 — skip")
        return True

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    data = {"To": phone, "From": TWILIO_FROM, "Body": message[:160]}

    try:
        r = httpx.post(url, data=data, auth=auth, timeout=timeout)
        r.raise_for_status()
        return True
    except httpx.HTTPError as e:
        logger.warning("Twilio 발송 실패 phone=%s: %s", phone[-4:], e)
        return False


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────


def send_sms(phone: str, message: str) -> bool:
    """단일 phone 으로 SMS 발송. Provider env 에 따라 sens/twilio 자동 라우팅.

    Returns:
        True — 발송 성공 또는 의도적 skip (provider 미설정).
        False — 발송 시도했으나 실패.
    """
    if not phone or not message:
        return True  # 빈 입력은 의도적 skip

    if not _rate_limit_ok(phone):
        logger.info("rate limit hit phone=%s — skip", phone[-4:])
        return True

    from config import SMS_PROVIDER
    provider = (SMS_PROVIDER or "sens").lower()

    if provider == "twilio":
        return _send_via_twilio(phone, message)
    return _send_via_sens(phone, message)


def get_executive_phones() -> list[str]:
    """role_level >= 4 임원 사용자의 phone 리스트.

    employees.db 에서 조회. 미존재 / 빈 phone 은 제외.
    """
    try:
        from features.search.employee.database import EmployeeDatabase
    except ImportError:
        return []

    try:
        db = EmployeeDatabase()
        # employees 테이블 — position_level >= 4 (이사·상무·전무·부사장·대표)
        rows = db.execute_query(
            "SELECT phone FROM employees WHERE position_level >= 4 AND phone != ''"
        ) if hasattr(db, "execute_query") else []
        return [str(r.get("phone", "")).strip() for r in rows if r.get("phone")]
    except Exception as e:
        logger.warning("get_executive_phones 실패: %s", e)
        return []


def broadcast_critical(change: dict, change_id: int | None = None,
                       frontend_base_url: str = "https://ajin-cb.web.app") -> dict[str, int]:
    """CRITICAL 변경을 임원 SMS 일괄 발송.

    Returns:
        {sent, skipped, failed}
    """
    title = change.get("item_title") or "(제목 없음)"
    summary = change.get("summary_ko") or title
    deeplink = f"{frontend_base_url}/compliance"
    if change_id:
        deeplink += f"?change_id={change_id}"

    message = f"[AJIN 긴급] {summary[:50]} {deeplink}"

    counts = {"sent": 0, "skipped": 0, "failed": 0}
    phones = get_executive_phones()
    if not phones:
        counts["skipped"] = 1
        return counts

    for phone in phones:
        if send_sms(phone, message):
            counts["sent"] += 1
        else:
            counts["failed"] += 1
    return counts
