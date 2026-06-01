"""v4.8 Feature F 트랙 A — Firebase RTDB Admin SDK legacy 통합.

backend → RTDB push 경로. P0 비용 차단 기본값에서는 실제 RTDB write를
수행하지 않고 dry-run capture 또는 disabled pseudo-key만 반환한다.

환경 변수:
    FIREBASE_WRITE_ENABLED: true 일 때만 실제 RTDB write 허용
    FIREBASE_ADMIN_CREDENTIALS_JSON: 서비스 계정 JSON 경로
    FIREBASE_DATABASE_URL: RTDB 인스턴스 URL
    (둘 중 하나라도 비어있으면 dry-run 모드)
    FIREBASE_DRYRUN_CAPTURE_ENABLED: true 일 때 로컬 dry-run 파일 기록

미설정 시 `push_alarm` 은 `data/captures/rtdb_dryrun/<ts>.json` 으로 저장 후 가짜 key 반환.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.feature_flags import load_firebase_cost_flags

logger = logging.getLogger(__name__)

_INIT_LOCK = threading.Lock()
_INITIALIZED: bool | None = None  # None=unknown, True=admin_sdk, False=dry_run

_DRYRUN_DIR = Path("data/captures/rtdb_dryrun")


def _is_configured() -> bool:
    if not load_firebase_cost_flags().write_enabled:
        return False
    return bool(
        os.environ.get("FIREBASE_ADMIN_CREDENTIALS_JSON")
        and os.environ.get("FIREBASE_DATABASE_URL")
    )


def _dryrun_enabled() -> bool:
    """RTDB dry-run capture 허용 여부를 반환한다."""
    return load_firebase_cost_flags().dryrun_capture_enabled


def _init_admin() -> bool:
    """firebase-admin SDK 초기화 (idempotent). 성공 시 True."""
    global _INITIALIZED
    with _INIT_LOCK:
        if not load_firebase_cost_flags().write_enabled:
            _INITIALIZED = False
            logger.info("Firebase RTDB write 비활성 — dry-run 모드 진입")
            return False
        if _INITIALIZED is not None:
            return _INITIALIZED

        if not _is_configured():
            _INITIALIZED = False
            logger.info("Firebase Admin SDK write 비활성 또는 미설정 — dry-run 모드 진입")
            return False

        try:
            import firebase_admin  # type: ignore
            from firebase_admin import credentials  # type: ignore
        except ImportError as e:
            logger.warning(f"firebase-admin 미설치: {e} — dry-run 모드")
            _INITIALIZED = False
            return False

        try:
            cred_path = os.environ["FIREBASE_ADMIN_CREDENTIALS_JSON"]
            db_url = os.environ["FIREBASE_DATABASE_URL"]
            if not firebase_admin._apps:  # type: ignore[attr-defined]
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, {"databaseURL": db_url})
            _INITIALIZED = True
            logger.info(f"Firebase Admin SDK 초기화 완료 — db={db_url}")
            return True
        except Exception as e:
            logger.error(f"Firebase Admin 초기화 실패: {e}")
            _INITIALIZED = False
            return False


def _dryrun_write(alarm_dict: dict[str, Any]) -> str:
    """드라이런 모드 — 로컬 파일로 alarm 캡처."""
    if not _dryrun_enabled():
        fake_key = f"disabled-{uuid.uuid4().hex[:12]}"
        logger.info("[disabled] RTDB alarm write skipped")
        return fake_key
    _DRYRUN_DIR.mkdir(parents=True, exist_ok=True)
    fake_key = f"dryrun-{uuid.uuid4().hex[:12]}"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = _DRYRUN_DIR / f"{ts}_{fake_key}.json"
    out.write_text(
        json.dumps({"key": fake_key, "data": alarm_dict}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"[dry-run] alarm 캡처 → {out}")
    return fake_key


def push_alarm(alarm_dict: dict[str, Any], path: str = "/live_alarms") -> str:
    """RTDB `/live_alarms` 경로에 alarm 을 push.

    Returns: 생성된 RTDB key 또는 dry-run pseudo-key.
    """
    if not _init_admin():
        return _dryrun_write(alarm_dict)

    try:
        from firebase_admin import db  # type: ignore

        ref = db.reference(path)
        new_ref = ref.push(alarm_dict)
        key = new_ref.key or ""
        logger.info(f"RTDB push → {path}/{key}")
        return key
    except Exception as e:
        logger.error(f"RTDB push 실패 (fallback dry-run): {e}")
        return _dryrun_write(alarm_dict)


def is_live() -> bool:
    """현재 RTDB 가 라이브 모드(실제 push)인지 여부."""
    return _init_admin()
