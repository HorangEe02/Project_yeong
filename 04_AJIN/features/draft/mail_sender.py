"""B6 v4.0 — 메일 발송 어댑터.

Outlook / Gmail / 사내 SMTP 와 같은 실 연동의 인터페이스를 lock-in 하고,
시연·테스트용 MockMailAdapter 를 제공한다. 실 연동 전환은 RealSmtpAdapter
(또는 GraphMailAdapter / GmailAdapter) 를 추가하고 `get_mail_adapter()` 가
환경 변수 기반으로 분기하면 된다.

본 모듈 단계의 범위:
- 인터페이스 (ABC) 확정
- Mock 구현 (audit.db 에만 기록, 실제 송신 안 함)
- 발송 결과 dataclass 표준화

실 운영 PoC 는 별도 트랙 (사내망 SMTP 인증 / Microsoft Graph 토큰 등).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MailRecipient:
    """수신자 (to / cc / bcc 어디에 들어갈지 라우터에서 결정)."""

    email: str
    name: str = ""


@dataclass
class MailMessage:
    """발송할 메일 한 통."""

    subject: str
    body: str
    body_format: str = "markdown"  # "markdown" | "html" | "text"
    to: list[MailRecipient] = field(default_factory=list)
    cc: list[MailRecipient] = field(default_factory=list)
    bcc: list[MailRecipient] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)  # 파일 경로 또는 식별자
    metadata: dict[str, Any] = field(default_factory=dict)  # doc_type 등


@dataclass
class MailSendResult:
    """발송 결과."""

    ok: bool
    message_id: str = ""
    sent_at: str = ""
    adapter: str = ""
    detail: str = ""
    # 실 연동 시 provider 측 응답 — 디버그용
    raw: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# 어댑터 인터페이스
# ─────────────────────────────────────────────────────────────


class MailAdapter(ABC):
    """메일 발송 어댑터 추상 인터페이스."""

    name: str = "abstract"

    @abstractmethod
    def send(self, message: MailMessage) -> MailSendResult:
        """단일 메일 발송. 실패 시 ok=False + detail 채워서 반환."""

    def validate(self, message: MailMessage) -> str | None:
        """발송 전 사전 검증. 문제 없으면 None, 있으면 사유 문자열."""
        if not message.subject.strip():
            return "제목이 비어 있습니다."
        if not message.body.strip():
            return "본문이 비어 있습니다."
        if not message.to:
            return "수신자가 없습니다."
        for r in [*message.to, *message.cc, *message.bcc]:
            if "@" not in r.email:
                return f"잘못된 이메일 주소: {r.email}"
        return None


# ─────────────────────────────────────────────────────────────
# Mock 구현 — audit.db 에만 기록, 실 송신 안 함
# ─────────────────────────────────────────────────────────────


class MockMailAdapter(MailAdapter):
    """시연용 mock — 실 송신 없이 결과만 반환.

    실 환경에서는 RealSmtpAdapter / GraphMailAdapter 로 교체.
    """

    name = "mock"

    def send(self, message: MailMessage) -> MailSendResult:
        problem = self.validate(message)
        if problem:
            return MailSendResult(
                ok=False,
                adapter=self.name,
                detail=f"검증 실패 — {problem}",
                sent_at=datetime.now().isoformat(timespec="seconds"),
            )

        # 시연용 가짜 message_id (실 어댑터는 SMTP/Graph 응답에서 추출)
        msg_id = f"mock-{datetime.now().strftime('%Y%m%d%H%M%S')}-{abs(hash(message.subject)) % 100000}"
        return MailSendResult(
            ok=True,
            message_id=msg_id,
            sent_at=datetime.now().isoformat(timespec="seconds"),
            adapter=self.name,
            detail=(
                f"Mock 발송 완료 — to={len(message.to)} cc={len(message.cc)} "
                f"attachments={len(message.attachments)}"
            ),
            raw={
                "to": [r.email for r in message.to],
                "cc": [r.email for r in message.cc],
                "bcc": [r.email for r in message.bcc],
                "attachments": message.attachments,
                "metadata": message.metadata,
            },
        )


# ─────────────────────────────────────────────────────────────
# 팩토리
# ─────────────────────────────────────────────────────────────

_default_adapter: MailAdapter | None = None


def get_mail_adapter() -> MailAdapter:
    """기본 어댑터 반환. Feature B Sprint 1 P0 (plan §14.2) — env 봉인.

    AJIN_MAIL_MODE:
        - mock  (기본) → MockMailAdapter
        - real  → RealSmtpAdapter (단, AJIN_MAIL_REAL_ENABLED=1 필요)

    실 SMTP 발송은 영구적으로 disabled-by-default. 운영 PoC 단계에서만
    `AJIN_MAIL_MODE=real AJIN_MAIL_REAL_ENABLED=1` 동시 지정.
    """
    import os
    global _default_adapter
    if _default_adapter is not None:
        return _default_adapter

    mode = os.getenv("AJIN_MAIL_MODE", "mock").lower()
    if mode == "mock":
        _default_adapter = MockMailAdapter()
        return _default_adapter
    if mode == "real":
        if os.getenv("AJIN_MAIL_REAL_ENABLED") != "1":
            raise RuntimeError(
                "실 SMTP 발송 비활성 — AJIN_MAIL_MODE=real 와 "
                "AJIN_MAIL_REAL_ENABLED=1 모두 설정 필요"
            )
        from features.draft.real_smtp_adapter import RealSmtpAdapter
        _default_adapter = RealSmtpAdapter()
        return _default_adapter
    raise ValueError(f"unsupported AJIN_MAIL_MODE={mode!r}. supported: mock | real")


def reset_mail_adapter() -> None:
    """테스트용 — 싱글턴 캐시 초기화."""
    global _default_adapter
    _default_adapter = None
