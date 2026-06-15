"""D2 — 알림 디스패처 (enqueue + dispatch_pending)."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from backend.services.notify.base import (
    DispatchResult, NotificationContext, _connect, ensure_tables,
)
from backend.services.notify.recipients import resolve_recipients
from backend.services.notify.slack_adapter import get_slack_adapter
from backend.services.notify.smtp_adapter import get_email_adapter
from backend.services.notify.teams_adapter import get_teams_adapter
from features.compliance.alerts.legal_guard import ensure_legal_disclaimer

logger = logging.getLogger(__name__)


def _build_change_alert_text(change_row: dict[str, Any]) -> tuple[str, str]:
    """change_alert 템플릿 — (subject, body_text). 단순 텍스트, 외부 deps 없음."""
    grade = (change_row.get("grade") or "MEDIUM").upper()
    title = change_row.get("item_title") or "(제목 없음)"
    summary = change_row.get("summary_ko") or change_row.get("new_value") or ""
    type_label = {"added": "신설", "removed": "폐지", "modified": "개정"}.get(
        change_row.get("change_type", ""), change_row.get("change_type", "")
    )
    subject = f"[{grade}] {type_label} — {title[:60]}"

    deps = change_row.get("affected_departments") or []
    if isinstance(deps, str):
        try:
            deps = json.loads(deps)
        except Exception:
            deps = [deps]
    plants = change_row.get("affected_plants") or []
    if isinstance(plants, str):
        try:
            plants = json.loads(plants)
        except Exception:
            plants = [plants]

    body = (
        f"등급: {grade}\n"
        f"유형: {type_label}\n"
        f"제목: {title}\n"
        f"요약: {summary[:300]}\n"
        f"영향 부서: {', '.join(deps[:5]) if deps else '—'}\n"
        f"영향 사업장: {', '.join(plants[:5]) if plants else '—'}\n"
    )
    return subject, ensure_legal_disclaimer(body)


def _build_digest_text(changes: list[dict[str, Any]]) -> tuple[str, str]:
    today = datetime.now().strftime("%Y-%m-%d")
    subject = f"[Daily Digest] {today} — 변경 {len(changes)}건 요약"

    lines = [f"AJIN 법규 변경 일일 다이제스트 — {today}", ""]

    if changes:
        by_grade: dict[str, list[dict[str, Any]]] = {}
        for ch in changes:
            g = (ch.get("grade") or "MEDIUM").upper()
            by_grade.setdefault(g, []).append(ch)

        for grade in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            items = by_grade.get(grade, [])
            if not items:
                continue
            lines.append(f"[{grade}] {len(items)}건")
            for ch in items[:5]:
                lines.append(f"  - {ch.get('item_title', '(제목 없음)')[:80]}")
            lines.append("")
    else:
        lines.append("지난 24시간 동안 감지된 규제 변경이 없습니다.")
        lines.append("")

    # F12 부속 — 크롤 실행 현황 (지난 24h)
    try:
        from backend.services.crawl_audit import stats_24h
        s = stats_24h()
        lines.append("─" * 40)
        lines.append(f"[크롤 현황 24h] 총 {s['total_runs']}회 실행 / 실패 {s['failed_runs']}회")
        if s.get("per_crawler"):
            top = sorted(s["per_crawler"], key=lambda x: x.get("cnt", 0), reverse=True)[:5]
            for row in top:
                ok_cnt = row.get("ok_cnt") or 0
                cnt = row.get("cnt") or 0
                lines.append(
                    f"  - {row.get('crawler_name', '?'):20s} "
                    f"실행 {cnt}회 (성공 {ok_cnt}, 실패 {cnt - ok_cnt})"
                )
    except Exception as e:
        logger.debug("digest crawl_audit 첨부 skip: %s", e)

    return subject, ensure_legal_disclaimer("\n".join(lines))


def enqueue_for_change(change_id: int, change_row: dict[str, Any]) -> int:
    """변경 1건 → 수신자별 outbox 행 INSERT. 신규 row 수 반환."""
    ensure_tables()
    recipients = resolve_recipients(change_row)
    if not recipients:
        return 0

    subject, body = _build_change_alert_text(change_row)
    conn = _connect()
    inserted = 0
    try:
        for prefs in recipients:
            user_id = prefs["user_id"]
            channels: list[str] = []
            if prefs.get("channel_email"):
                channels.append("email")
            if prefs.get("channel_slack"):
                channels.append("slack")
            if prefs.get("channel_teams"):
                channels.append("teams")
            for ch_name in channels:
                # 이미 같은 (user, change, template, channel) log 가 있으면 skip.
                exists = conn.execute(
                    "SELECT 1 FROM notification_log WHERE user_id=? AND change_id=? "
                    "AND template='change_alert' AND channel=? LIMIT 1",
                    (user_id, change_id, ch_name),
                ).fetchone()
                if exists:
                    continue
                payload = {
                    "subject": subject,
                    "body": body,
                    "change_id": change_id,
                    "slack_webhook_url": prefs.get("slack_webhook_url", ""),
                    "teams_webhook_url": prefs.get("teams_webhook_url", ""),
                    "email": prefs.get("email", ""),
                }
                conn.execute(
                    "INSERT INTO notification_outbox(user_id, channel, template, subject, payload_json, status) "
                    "VALUES (?, ?, 'change_alert', ?, ?, 'pending')",
                    (user_id, ch_name, subject, json.dumps(payload, ensure_ascii=False)),
                )
                inserted += 1
        conn.commit()
        return inserted
    finally:
        conn.close()


def enqueue_digest_for_user(user_id: str, prefs: dict[str, Any], changes: list[dict[str, Any]]) -> int:
    ensure_tables()
    if not prefs.get("digest_enabled"):
        return 0
    subject, body = _build_digest_text(changes)
    conn = _connect()
    try:
        channels: list[str] = []
        if prefs.get("channel_email"):
            channels.append("email")
        if prefs.get("channel_slack"):
            channels.append("slack")
        if prefs.get("channel_teams"):
            channels.append("teams")
        inserted = 0
        for ch_name in channels:
            payload = {
                "subject": subject,
                "body": body,
                "change_count": len(changes),
                "slack_webhook_url": prefs.get("slack_webhook_url", ""),
                "teams_webhook_url": prefs.get("teams_webhook_url", ""),
                "email": prefs.get("email", ""),
            }
            conn.execute(
                "INSERT INTO notification_outbox(user_id, channel, template, subject, payload_json, status) "
                "VALUES (?, ?, 'digest', ?, ?, 'pending')",
                (user_id, ch_name, subject, json.dumps(payload, ensure_ascii=False)),
            )
            inserted += 1
        conn.commit()
        return inserted
    finally:
        conn.close()


def _send_one(row: dict[str, Any]) -> DispatchResult:
    payload = json.loads(row.get("payload_json") or "{}")
    ctx = NotificationContext(
        user_id=row["user_id"],
        user_email=payload.get("email", ""),
        channel=row["channel"],
        template=row["template"],
        subject=row.get("subject") or payload.get("subject", ""),
        body_text=payload.get("body", ""),
        payload=payload,
        change_id=payload.get("change_id"),
    )
    if ctx.channel == "email":
        return get_email_adapter().send(ctx)
    if ctx.channel == "slack":
        return get_slack_adapter(payload.get("slack_webhook_url", "")).send(ctx)
    if ctx.channel == "teams":
        return get_teams_adapter(payload.get("teams_webhook_url", "")).send(ctx)
    return DispatchResult(success=False, detail=f"알 수 없는 채널: {ctx.channel}")


def dispatch_pending(batch_size: int = 50) -> dict[str, int]:
    """outbox.status='pending' 행을 배치 발송. 결과 카운트 반환."""
    ensure_tables()
    counts = {"sent": 0, "failed": 0}
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM notification_outbox WHERE status='pending' "
            "ORDER BY created_at ASC LIMIT ?",
            (batch_size,),
        ).fetchall()
    finally:
        conn.close()

    for r in rows:
        row = dict(r)
        result = _send_one(row)
        conn = _connect()
        try:
            now = datetime.now().isoformat(timespec="seconds")
            new_status = "sent" if result.success else "failed"
            if result.detail == "sent_mock":
                new_status = "sent_mock"
            conn.execute(
                "UPDATE notification_outbox SET status=?, sent_at=?, attempts=attempts+1, last_error=? WHERE id=?",
                (new_status, now if result.success else None, result.detail or "", row["id"]),
            )
            payload = json.loads(row.get("payload_json") or "{}")
            change_id = payload.get("change_id")
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO notification_log(outbox_id, user_id, change_id, "
                    "template, channel, success, detail) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        row["id"], row["user_id"], change_id, row["template"],
                        row["channel"], 1 if result.success else 0, result.detail or "",
                    ),
                )
            except Exception as e:
                logger.warning("notification_log insert 실패: %s", e)
            conn.commit()
        finally:
            conn.close()
        if result.success:
            counts["sent"] += 1
        else:
            counts["failed"] += 1
    return counts


def post_persist_hook(change_id: int, change_row: dict[str, Any]) -> None:
    """change_detector.save_changes() 직후 호출되는 훅.
    HIGH/CRITICAL 만 즉시 큐잉. MEDIUM/LOW 는 다이제스트 cron 이 처리.
    """
    grade = (change_row.get("grade") or "MEDIUM").upper()
    if grade not in ("HIGH", "CRITICAL"):
        return
    try:
        n = enqueue_for_change(change_id, change_row)
        if n:
            logger.info("D2 post_persist enqueued %d outbox rows for change_id=%s", n, change_id)
    except Exception as e:
        logger.warning("D2 post_persist 실패 change_id=%s: %s", change_id, e)
