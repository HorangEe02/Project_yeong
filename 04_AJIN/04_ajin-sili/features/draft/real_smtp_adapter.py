"""Real SMTP mail adapter — Feature B Sprint 1 P0 (skeleton, plan §14.2).

운영 PoC 단계에서만 활성화. mail_sender.get_mail_adapter() 가
`AJIN_MAIL_MODE=real AJIN_MAIL_REAL_ENABLED=1` 동시 지정 시에만 로딩한다.

설계 의도:
  - skeleton 만 — Sprint 1 범위 외 (`send()` 는 `NotImplementedError`).
  - Sprint 6+ 에서 실 SMTP 설정 (`AJIN_SMTP_HOST/PORT/USER/PASSWORD/USE_TLS`) 결정 후 구현.
  - mail_guard 의 모든 검증은 어댑터와 무관하게 항상 동작 — skeleton 이라도 가드는 통과해야 함.
"""

from __future__ import annotations

import logging

from features.draft.mail_sender import MailAdapter, MailMessage, MailSendResult

logger = logging.getLogger(__name__)


class RealSmtpAdapter(MailAdapter):
    """실 SMTP 발송 어댑터. Sprint 6+ 에서 구현."""

    def __init__(self):
        # Sprint 6+ 구현 시 env 로드:
        #   AJIN_SMTP_HOST, AJIN_SMTP_PORT, AJIN_SMTP_USER, AJIN_SMTP_PASSWORD,
        #   AJIN_SMTP_USE_TLS, AJIN_MAIL_FROM_ADDRESS
        logger.warning(
            "RealSmtpAdapter loaded — skeleton 단계. send() 호출 시 NotImplementedError."
        )

    def send(self, msg: MailMessage) -> MailSendResult:
        raise NotImplementedError(
            "RealSmtpAdapter.send() 미구현 — Sprint 6+ 에서 smtplib 연결 추가 예정. "
            "현 단계는 AJIN_MAIL_MODE=mock 사용 필수."
        )
