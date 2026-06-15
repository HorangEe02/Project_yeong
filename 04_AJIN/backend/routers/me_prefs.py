"""사용자 prefs 라우터 (v4.5) — 모바일 BottomTabBar 커스터마이즈 저장.

GET  /api/me/mobile-tab-prefs    — 현재 사용자 설정 조회
PUT  /api/me/mobile-tab-prefs    — 설정 저장 (override + custom_slots)

저장: auth.db 의 user_prefs 테이블 (JSON 컬럼). 사용자 단위 1행.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_current_user
from backend.schemas.me_prefs import MobileTabPrefs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me", tags=["me"])


def _ensure_table(conn) -> None:
    """user_prefs 테이블 멱등 생성."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_prefs (
            user_id TEXT PRIMARY KEY,
            mobile_tab_prefs TEXT DEFAULT '{}',
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
        """
    )


def _resolve_user_id(user) -> str:
    """auth user → 안정 식별자. employee_id 우선, 그 다음 username."""
    return (
        getattr(user, "employee_id", None)
        or getattr(user, "username", None)
        or getattr(user, "email", None)
        or "anonymous"
    )


@router.get("/mobile-tab-prefs", response_model=MobileTabPrefs)
async def get_mobile_tab_prefs(user=Depends(get_current_user)):
    """현재 사용자의 모바일 탭 설정. 미저장 시 기본값 (override=False, compliance/equipment)."""
    from core.auth.database import get_auth_db

    user_id = _resolve_user_id(user)
    conn = get_auth_db()
    try:
        _ensure_table(conn)
        row = conn.execute(
            "SELECT mobile_tab_prefs, updated_at FROM user_prefs WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return MobileTabPrefs()
        try:
            payload = json.loads(row[0]) if row[0] else {}
        except json.JSONDecodeError:
            logger.warning("[me_prefs] %s mobile_tab_prefs JSON parse 실패", user_id)
            payload = {}
        return MobileTabPrefs(
            override=bool(payload.get("override", False)),
            custom_slots=list(payload.get("custom_slots", ["compliance", "equipment"]))[:2],
            updated_at=row[1],
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass


@router.put("/mobile-tab-prefs", response_model=MobileTabPrefs)
async def put_mobile_tab_prefs(
    payload: MobileTabPrefs,
    user=Depends(get_current_user),
):
    """모바일 탭 설정 저장 — upsert."""
    from core.auth.database import get_auth_db

    if len(payload.custom_slots) > 2:
        raise HTTPException(status_code=422, detail="custom_slots 최대 2개")

    user_id = _resolve_user_id(user)
    now = datetime.now().isoformat(timespec="seconds")
    body_json = json.dumps(
        {"override": payload.override, "custom_slots": payload.custom_slots},
        ensure_ascii=False,
    )

    conn = get_auth_db()
    try:
        _ensure_table(conn)
        conn.execute(
            """
            INSERT INTO user_prefs (user_id, mobile_tab_prefs, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                mobile_tab_prefs = excluded.mobile_tab_prefs,
                updated_at = excluded.updated_at
            """,
            (user_id, body_json, now),
        )
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return MobileTabPrefs(
        override=payload.override,
        custom_slots=payload.custom_slots,
        updated_at=now,
    )
