"""Postmortem 2026-05-27 후속 — compliance.db 일일 백업 + 7일 보존.

매일 04:30 KST 에 data/compliance.db 를 data/backup/compliance.db.YYYYMMDD 로
SQLite Online Backup API 로 atomic dump. 무결성 검증 후 7일 이상 오래된 백업
자동 정리.

Celery task 등록: backend/celery_app.py 의 `ajin.jobs.compliance_db_backup`.
수동 실행:
    docker exec ajin-compliance-backend-1 python -c \
        "from backend.services.jobs.compliance_db_backup import run; print(run())"

배경: 2026-05-27 호스트 data/compliance.db 가 SQLite 가 아닌 손상 데이터로
변형되어 /api/compliance/crawl/history/stats 가 500 응답. `.gitignore: data/**/*.db`
이라 git 으로 추적 불가, 백업 sink 없어 복구 어려울 뻔함. 본 job 으로 일일 백업
sink 확보.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from config import DATA_DIR

logger = logging.getLogger(__name__)

BACKUP_RETENTION_DAYS = 7
SOURCE_DB = DATA_DIR / "compliance.db"
BACKUP_DIR = DATA_DIR / "backup"


def run() -> dict[str, Any]:
    """매일 04:30 KST 트리거. data/compliance.db → data/backup/compliance.db.YYYYMMDD"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    if not SOURCE_DB.exists():
        logger.error("compliance.db source not found at %s", SOURCE_DB)
        return {"status": "error", "reason": "source_missing", "source": str(SOURCE_DB)}

    today = datetime.now().strftime("%Y%m%d")
    backup_path = BACKUP_DIR / f"compliance.db.{today}"

    # SQLite Online Backup API — atomic, write lock 안전 (다른 프로세스 write 중에도 안전).
    src = sqlite3.connect(SOURCE_DB)
    dst = sqlite3.connect(backup_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    # 백업 무결성 검증 — quick_check 는 integrity_check 보다 빠르고 일반적 손상 모두 잡음.
    verify = sqlite3.connect(backup_path)
    try:
        cur = verify.execute("PRAGMA quick_check;")
        check_result = cur.fetchone()[0]
    finally:
        verify.close()

    if check_result != "ok":
        logger.error("backup quick_check failed: %s", check_result)
        backup_path.unlink(missing_ok=True)
        return {
            "status": "error",
            "reason": "integrity_check_failed",
            "detail": check_result,
        }

    size_mb = round(backup_path.stat().st_size / (1024 * 1024), 2)
    cleaned = _cleanup_old_backups()
    logger.info(
        "compliance.db backup OK: %s (%.2f MB), cleaned %d old backups",
        backup_path.name, size_mb, cleaned,
    )

    return {
        "status": "ok",
        "backup_path": str(backup_path),
        "size_mb": size_mb,
        "cleaned_old": cleaned,
        "retention_days": BACKUP_RETENTION_DAYS,
    }


def _cleanup_old_backups() -> int:
    """7일 이상 오래된 백업 삭제. 삭제된 파일 수 반환."""
    cutoff = datetime.now() - timedelta(days=BACKUP_RETENTION_DAYS)
    cleaned = 0
    for backup in BACKUP_DIR.glob("compliance.db.*"):
        date_str = backup.suffix.lstrip(".")
        if len(date_str) != 8 or not date_str.isdigit():
            continue
        try:
            file_date = datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            continue
        if file_date < cutoff:
            backup.unlink(missing_ok=True)
            cleaned += 1
    return cleaned
