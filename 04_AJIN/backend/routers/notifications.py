"""D2 — 알림 환경설정 + 테스트 발송 라우터.

프론트 `frontend/src/api/notifications.ts` (이미 존재) 와 1:1 매핑:
  GET  /notifications/me        → fetchMyPrefs
  PUT  /notifications/me        → updateMyPrefs
  POST /notifications/test      → sendTestNotification
  POST /notifications/dispatch  → 수동 outbox 발송 (admin/디버깅용)
  GET  /notifications/channels  → 활성 채널 + Mock/Real 모드 표시
"""
from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_current_user
from backend.services.notify.base import (
    _connect, ensure_tables, get_prefs, upsert_prefs,
)
from backend.services.notify.dispatcher import (
    dispatch_pending, enqueue_for_change,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _user_id_of(user) -> str:
    return str(getattr(user, "user_id", "") or getattr(user, "username", "") or "anonymous")


def _user_email_of(user) -> str:
    return str(getattr(user, "email", "") or "")


def _prefs_to_response(prefs: dict[str, Any]) -> dict[str, Any]:
    """DB row → 프론트가 기대하는 NotificationPrefsOut 형태로 변환."""
    plant_filter_raw = prefs.get("plant_filter_json") or "[]"
    try:
        plant_filter = json.loads(plant_filter_raw)
    except Exception:
        plant_filter = []
    return {
        "user_id": prefs.get("user_id", ""),
        "email": prefs.get("email", ""),
        "enabled": bool(prefs.get("enabled", 1)),
        "channel_email": bool(prefs.get("channel_email", 1)),
        "channel_slack": bool(prefs.get("channel_slack", 0)),
        "channel_teams": bool(prefs.get("channel_teams", 0)),
        "severity_threshold": prefs.get("severity_threshold", "MEDIUM"),
        "digest_enabled": bool(prefs.get("digest_enabled", 1)),
        "digest_hour_kst": int(prefs.get("digest_hour_kst", 8)),
        "plant_filter": plant_filter,
        "department_filter": prefs.get("department_filter", "") or None,
    }


@router.get("/me")
async def get_my_prefs(user=Depends(get_current_user)):
    ensure_tables()
    user_id = _user_id_of(user)
    prefs = get_prefs(user_id)
    if not prefs:
        prefs = upsert_prefs(user_id, {}, email=_user_email_of(user))
    return _prefs_to_response(prefs)


@router.put("/me")
async def update_my_prefs(payload: dict, user=Depends(get_current_user)):
    user_id = _user_id_of(user)
    prefs = upsert_prefs(user_id, payload, email=_user_email_of(user))
    return _prefs_to_response(prefs)


@router.post("/test")
async def send_test_notification(payload: dict | None = None, user=Depends(get_current_user)):
    """현재 사용자에게 가짜 변경 1건을 큐잉하고 즉시 dispatch."""
    user_id = _user_id_of(user)
    prefs = get_prefs(user_id)
    if not prefs:
        upsert_prefs(user_id, {}, email=_user_email_of(user))

    fake_change = {
        "regulation_type": "TEST",
        "change_type": "modified",
        "item_title": "[테스트] 알림 채널 동작 확인",
        "summary_ko": "이 메시지는 사용자 채널 설정의 동작을 확인하기 위한 테스트입니다.",
        "grade": "HIGH",
        "affected_departments": ["테스트팀"],
        "affected_plants": [],
    }
    inserted = enqueue_for_change(change_id=0, change_row=fake_change)
    counts = dispatch_pending(batch_size=10)
    return {"queued": inserted > 0, "queued_count": inserted, "dispatched": counts}


@router.post("/dispatch")
async def trigger_dispatch(user=Depends(get_current_user)):
    """수동 outbox 발송 (관리자/디버깅용)."""
    return dispatch_pending(batch_size=100)


@router.get("/channels")
async def list_active_channels(user=Depends(get_current_user)):
    """현재 환경에서 활성된 어댑터 모드 (Mock/Real) 정보."""
    smtp_enabled = os.environ.get("SMTP_ENABLED", "false").strip().lower() in (
        "true", "1", "yes", "on"
    )
    return {
        "email": "real" if smtp_enabled else "mock",
        "slack": "real_per_user_webhook",
        "teams": "real_per_user_webhook",
        "captures_dir": "data/captures",
    }


@router.get("/log")
async def list_log(limit: int = 50, user=Depends(get_current_user)):
    """현재 사용자의 알림 발송 로그."""
    ensure_tables()
    user_id = _user_id_of(user)
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM notification_log WHERE user_id=? ORDER BY sent_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return {"logs": [dict(r) for r in rows], "total": len(rows)}
    finally:
        conn.close()
