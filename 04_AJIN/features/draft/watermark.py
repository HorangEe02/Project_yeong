"""AI watermark utility — Feature B Sprint 1 P0 (plan §14.2).

docx/pdf/hwpx exporter 3종에서 공통 사용.
컨텐츠 SHA1 8자 + 텍스트 1줄로 "AI 보조 작성"을 명시한다.

OEM 평가자에게 인간 작성으로 오인되는 위험을 차단하고,
mail_audit_log.watermark_id 와 발송 추적을 1:1 매칭한다.
"""

from __future__ import annotations

import hashlib

WATERMARK_PREFIX = "WMK-"


def compute_watermark_id(content: str) -> str:
    """컨텐츠의 SHA1 첫 8자 → 'WMK-xxxxxxxx'.

    동일 컨텐츠 → 동일 ID (재export 시 추적 가능).
    """
    if not content:
        return WATERMARK_PREFIX + "00000000"
    digest = hashlib.sha1(content.encode("utf-8")).hexdigest()
    return f"{WATERMARK_PREFIX}{digest[:8]}"


def watermark_text(watermark_id: str, reviewer: str = "") -> str:
    """문서 footer / OWPML inline 에 부착될 한 줄 텍스트.

    예: 'AI 보조 작성 · WMK-abc12345 · 검토: kim'
        'AI 보조 작성 · WMK-abc12345 · 검토 미완'
    """
    reviewer_label = f"검토: {reviewer}" if reviewer else "검토 미완"
    return f"AI 보조 작성 · {watermark_id} · {reviewer_label}"


__all__ = ["compute_watermark_id", "watermark_text", "WATERMARK_PREFIX"]
