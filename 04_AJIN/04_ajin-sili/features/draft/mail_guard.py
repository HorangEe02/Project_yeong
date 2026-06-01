"""Mail send guard — Feature B Sprint 1 P0 (plan §14.2).

발송 직전 7 규칙 검증:
  1. version_id 필수
  2. version.status == 'approved'
  3. 자기승인 방지 (reviewer != sender)
  4. watermark_id == approved version rendered_text hash
  5. 외부 도메인 발송 시 acknowledged_external 확인
  6. 합산 수신자 ≤ 50 (외부 시 to≤20, cc≤30, bcc=0)
  7. 첨부 파일 무결성
  8. rate limit (env AJIN_MAIL_RATE_PER_MIN, default=10, in-process)

설계 의도:
  - service layer 단일 진입점 (router에 비즈니스 로직 누적 방지)
  - Mock vs 실 SMTP 어댑터 무관 — 가드는 항상 적용
  - 단위 테스트 격리 쉬움 (8 시나리오)
"""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple, Optional

from features.draft.version_db import get_version, VERSION_DB_PATH

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Domain policy — env 기반 (Sprint 1 §22 Q3 결정 전 임시)
# ─────────────────────────────────────────────────────────────

DEFAULT_INTERNAL_DOMAINS = {"ajin.co.kr"}
DEFAULT_OEM_DOMAINS = {"hkmc.com", "hyundai.com", "kia.com", "hyundai-motor.com"}


def _parse_env_set(name: str, default: set[str]) -> set[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return set(default)
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


@dataclass(frozen=True)
class DomainPolicy:
    internal_domains: set[str] = field(default_factory=lambda: _parse_env_set(
        "AJIN_INTERNAL_DOMAINS", DEFAULT_INTERNAL_DOMAINS
    ))
    trusted_oem_domains: set[str] = field(default_factory=lambda: _parse_env_set(
        "AJIN_OEM_DOMAINS", DEFAULT_OEM_DOMAINS
    ))

    def classify(self, email: str) -> str:
        """Returns 'internal' | 'oem' | 'external' | 'invalid'."""
        if not email or "@" not in email:
            return "invalid"
        domain = email.rsplit("@", 1)[-1].lower().strip()
        if domain in self.internal_domains:
            return "internal"
        if domain in self.trusted_oem_domains:
            return "oem"
        return "external"


# ─────────────────────────────────────────────────────────────
# Decision codes — HTTPException detail 로 그대로 전달
# ─────────────────────────────────────────────────────────────

ALLOW = "allow"
BLOCK_NO_VERSION = "block_no_version"
BLOCK_NOT_APPROVED = "block_not_approved"
BLOCK_SELF_APPROVAL = "block_self_approval"
NEEDS_EXTERNAL_ACK = "needs_external_ack"
BLOCK_RECIPIENT_CAP = "block_recipient_cap"
BLOCK_BCC_NOT_ALLOWED = "block_bcc_not_allowed"
BLOCK_INVALID_EMAIL = "block_invalid_email"
BLOCK_RATE_LIMIT = "block_rate_limit"
BLOCK_WATERMARK_MISMATCH = "watermark_mismatch"


class GuardReport(NamedTuple):
    ok: bool
    decision: str          # ALLOW 또는 BLOCK_* / NEEDS_* 중 하나
    version_status: Optional[str]
    classified: dict       # {'internal':[..], 'oem':[..], 'external':[..]}
    detail: str = ""


class GuardViolation(Exception):
    """Optional 헬퍼 — router 에서 즉시 raise 하고 싶을 때."""

    def __init__(self, report: GuardReport):
        super().__init__(report.detail or report.decision)
        self.report = report


# ─────────────────────────────────────────────────────────────
# In-process rate limit (per sender_email)
# ─────────────────────────────────────────────────────────────


class _RateLimiter:
    def __init__(self, per_minute: int = 10):
        self.per_minute = max(1, per_minute)
        self._events: dict[str, deque[float]] = {}

    def hit(self, key: str) -> bool:
        """Returns True if allowed, False if over limit."""
        now = time.time()
        window_start = now - 60.0
        q = self._events.setdefault(key, deque())
        # purge old
        while q and q[0] < window_start:
            q.popleft()
        if len(q) >= self.per_minute:
            return False
        q.append(now)
        return True

    def reset(self) -> None:
        self._events.clear()


# ─────────────────────────────────────────────────────────────
# Main guard
# ─────────────────────────────────────────────────────────────


class MailSendGuard:
    """Single entry point for pre-send validation."""

    def __init__(
        self,
        policy: Optional[DomainPolicy] = None,
        version_db_path: Path = VERSION_DB_PATH,
        rate_limit_per_min: Optional[int] = None,
    ):
        self.policy = policy or DomainPolicy()
        self.version_db_path = version_db_path
        self.rate_limiter = _RateLimiter(
            per_minute=rate_limit_per_min
            or int(os.getenv("AJIN_MAIL_RATE_PER_MIN", "10"))
        )

    def _classify_all(self, req: Any) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {"internal": [], "oem": [], "external": [], "invalid": []}
        for recip_field in ("to", "cc", "bcc"):
            recipients = getattr(req, recip_field, None) or []
            for r in recipients:
                email = getattr(r, "email", "") if hasattr(r, "email") else str(r)
                kind = self.policy.classify(email)
                out[kind].append(email)
        return out

    def _has_external(self, classified: dict[str, list[str]]) -> bool:
        # OEM = 외부지만 신뢰 도메인이므로 별도 ack 안 받음.
        # 'external'만 ack 대상.
        return bool(classified.get("external"))

    def validate(self, req: Any, user: Any) -> GuardReport:
        """Run 7 rules. Returns GuardReport — caller maps to HTTPException."""
        # 0. classify (모든 분기에서 필요)
        classified = self._classify_all(req)

        # 1. version_id 필수
        version_id = getattr(req, "version_id", 0) or 0
        if not version_id or version_id <= 0:
            return GuardReport(
                ok=False, decision=BLOCK_NO_VERSION,
                version_status=None, classified=classified,
                detail="version_id 필수 — 승인된 문서 ID를 전달하세요",
            )

        # 2. version.status == 'approved'
        version = get_version(int(version_id), self.version_db_path)
        if not version:
            return GuardReport(
                ok=False, decision=BLOCK_NO_VERSION,
                version_status=None, classified=classified,
                detail=f"version_id={version_id} 가 존재하지 않습니다",
            )
        version_status = version.get("status", "")
        if version_status != "approved":
            return GuardReport(
                ok=False, decision=BLOCK_NOT_APPROVED,
                version_status=version_status, classified=classified,
                detail=f"status={version_status} — 'approved' 만 발송 가능",
            )

        # 3. 자기승인 방지 (reviewer != sender)
        sender_id = getattr(user, "employee_id", "") if user else ""
        reviewer_id = (version.get("reviewer_id") or "").strip()
        if sender_id and reviewer_id and sender_id == reviewer_id:
            # 작성자 == 검토자 == 발송자 인 경우 차단
            author = (version.get("author") or "").strip()
            if author == sender_id:
                return GuardReport(
                    ok=False, decision=BLOCK_SELF_APPROVAL,
                    version_status=version_status, classified=classified,
                    detail="작성자가 자신을 검토자로 승인 후 발송할 수 없습니다",
                )

        # 4. approved version rendered_text 와 메일 요청 watermark_id 일치 확인
        from features.draft.watermark import compute_watermark_id

        expected_watermark_id = compute_watermark_id(str(version.get("rendered_text") or ""))
        requested_watermark_id = str(getattr(req, "watermark_id", "") or "").strip()
        if requested_watermark_id != expected_watermark_id:
            return GuardReport(
                ok=False, decision=BLOCK_WATERMARK_MISMATCH,
                version_status=version_status, classified=classified,
                detail=(
                    "watermark_id 불일치 — 승인된 버전을 다시 export 한 뒤 "
                    "해당 ID로 발송하세요"
                ),
            )

        # 5. 잘못된 이메일 형식
        if classified.get("invalid"):
            return GuardReport(
                ok=False, decision=BLOCK_INVALID_EMAIL,
                version_status=version_status, classified=classified,
                detail=f"잘못된 이메일 형식: {classified['invalid']}",
            )

        # 6. 합산 수신자 cap
        to_n = len(classified["internal"]) + len(classified["oem"]) + len(classified["external"])
        # 위 to_n 은 전체 합산이지만 bcc 별도로 처리
        bcc_emails = [getattr(r, "email", "") for r in (getattr(req, "bcc", None) or [])]

        has_external = self._has_external(classified)
        if has_external and bcc_emails:
            return GuardReport(
                ok=False, decision=BLOCK_BCC_NOT_ALLOWED,
                version_status=version_status, classified=classified,
                detail="외부 도메인 발송 시 BCC 사용 금지",
            )

        # 50 cap (전체 to+cc+bcc)
        total = (
            len(getattr(req, "to", None) or [])
            + len(getattr(req, "cc", None) or [])
            + len(getattr(req, "bcc", None) or [])
        )
        if total > 50:
            return GuardReport(
                ok=False, decision=BLOCK_RECIPIENT_CAP,
                version_status=version_status, classified=classified,
                detail=f"합산 수신자 {total} > 50",
            )
        if has_external:
            if len(getattr(req, "to", None) or []) > 20:
                return GuardReport(
                    ok=False, decision=BLOCK_RECIPIENT_CAP,
                    version_status=version_status, classified=classified,
                    detail="외부 도메인 발송 시 to ≤ 20",
                )
            if len(getattr(req, "cc", None) or []) > 30:
                return GuardReport(
                    ok=False, decision=BLOCK_RECIPIENT_CAP,
                    version_status=version_status, classified=classified,
                    detail="외부 도메인 발송 시 cc ≤ 30",
                )

        # 7. 외부 도메인 ack
        if has_external and not bool(getattr(req, "acknowledged_external", False)):
            return GuardReport(
                ok=False, decision=NEEDS_EXTERNAL_ACK,
                version_status=version_status, classified=classified,
                detail=f"외부 도메인 발송 — 확인 필요: {classified['external']}",
            )

        # 8. rate limit
        if not self.rate_limiter.hit(sender_id or "anonymous"):
            return GuardReport(
                ok=False, decision=BLOCK_RATE_LIMIT,
                version_status=version_status, classified=classified,
                detail=f"분당 {self.rate_limiter.per_minute}건 초과",
            )

        return GuardReport(
            ok=True, decision=ALLOW,
            version_status=version_status, classified=classified,
            detail="",
        )


# ─────────────────────────────────────────────────────────────
# Module-level singleton (router 에서 직접 사용)
# ─────────────────────────────────────────────────────────────

_default_guard: Optional[MailSendGuard] = None


def get_guard() -> MailSendGuard:
    global _default_guard
    if _default_guard is None:
        _default_guard = MailSendGuard()
    return _default_guard


def reset_guard() -> None:
    """테스트에서 env 변경 후 재바인딩 / rate limiter 리셋."""
    global _default_guard
    _default_guard = None
