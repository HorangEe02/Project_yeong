"""Firestore audit_logs 컬렉션 — 로그인 이벤트 legacy shadow.

H7 마이그레이션: auth.db `login_history` SQLite 핫패스를 Firestore 로 이전한다.
Cloud Run 컨테이너 휘발 + 멀티 인스턴스 일관성 문제 해결.

설계:
  - 컬렉션: audit_logs
  - 인덱스: (action, timestamp DESC) / (employee_id, success, timestamp DESC)
  - TTL: 180일 (Firestore TTL 자동 정리)
  - write: FIREBASE_WRITE_ENABLED=true 이고 FIRESTORE_AUDIT_ENABLED=true 일 때만 수행
  - read: FIREBASE_READ_FALLBACK_ENABLED=true 이고 FIRESTORE_AUDIT_ENABLED=true 일 때만 수행

P0 Firebase 비용 차단 후 Postgres audit 전환 전까지의 fallback 모듈이다.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from core.feature_flags import firebase_read_fallback_enabled, firebase_writes_enabled

logger = logging.getLogger(__name__)

_COLLECTION = "audit_logs"


def _enabled() -> bool:
    """v4.8 F — env 토글. 기본 false. 비활성 시 모든 write 가 no-op.

    read_* 함수는 _get_db() 가 활성 검증을 하므로 RuntimeError 가 자연 발생.
    """
    return (
        firebase_writes_enabled()
        and os.getenv("FIRESTORE_AUDIT_ENABLED", "false").lower() == "true"
    )


def _read_enabled() -> bool:
    """Firestore audit read fallback 활성 여부를 반환한다.

    Returns:
        bool: read fallback과 audit env가 모두 켜진 경우 True.
    """
    return (
        firebase_read_fallback_enabled()
        and os.getenv("FIRESTORE_AUDIT_ENABLED", "false").lower() == "true"
    )

# I-2: TTL 보존 기간 (180일). expires_at 필드에 만료 시각 기록 →
# Firestore TTL 정책이 백그라운드로 자동 삭제 (gcloud firestore fields ttls update).
_TTL_DAYS = 180


def _get_db():
    """firestore client 획득. firebase_admin 미초기화 시 RuntimeError."""
    from firebase_admin import firestore  # type: ignore
    import firebase_admin

    if not firebase_admin._apps:
        try:
            from firebase_admin import credentials  # type: ignore

            cred_path = os.getenv("FIREBASE_ADMIN_CREDENTIALS_JSON")
            if not cred_path:
                raise RuntimeError("FIREBASE_ADMIN_CREDENTIALS_JSON is empty")
            firebase_admin.initialize_app(credentials.Certificate(cred_path))
        except Exception as e:
            raise RuntimeError(f"firebase_admin not initialized: {e}")
    return firestore.client()


def write_login_event(
    user_id: int,
    employee_id: str,
    success: bool,
    ip_address: str = "",
    user_agent: str = "",
    department: str = "",
    role_level: int = 0,
) -> Optional[str]:
    """audit_logs 컬렉션에 로그인 이벤트 1건 기록.

    Returns:
        성공 시 새 doc id, 실패 시 None (호출자는 SQLite 단독으로 계속).
        FIRESTORE_AUDIT_ENABLED=false (기본) 일 때는 무조건 None 반환 — no-op.
    """
    if not _enabled():
        return None
    try:
        from firebase_admin import firestore  # type: ignore
        db = _get_db()
        # I-2 TTL: expires_at = now + 180d. Firestore TTL 정책이 자동 정리.
        expires_at = datetime.now(timezone.utc) + timedelta(days=_TTL_DAYS)
        _, doc = db.collection(_COLLECTION).add({
            "user_id": user_id,
            "employee_id": employee_id,
            "action": "login",
            "success": success,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "department": department,
            "role_level": role_level,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "expires_at": expires_at,
        })
        return doc.id
    except Exception as e:
        logger.warning("[audit_logs] write_login_event 실패: %s", e)
        return None


def read_recent_logins(limit: int = 50) -> list[dict]:
    """최근 로그인 이력. action='login', timestamp DESC."""
    if not _read_enabled():
        raise RuntimeError("firestore audit read fallback disabled")
    from firebase_admin import firestore  # type: ignore
    db = _get_db()
    q = (
        db.collection(_COLLECTION)
        .where("action", "==", "login")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    rows = []
    for d in q.stream():
        data = d.to_dict()
        ts = data.get("timestamp")
        rows.append({
            "id": d.id,
            "user_id": data.get("user_id"),
            "employee_id": data.get("employee_id", ""),
            "action": data.get("action", "login"),
            "success": int(bool(data.get("success", True))),
            "ip_address": data.get("ip_address", ""),
            "user_agent": data.get("user_agent", ""),
            "timestamp": ts.isoformat() if ts else "",
        })
    return rows


def read_hour_distribution(days: int = 30) -> dict[int, int]:
    """0~23 hour bucket. days 일 이내 성공 로그인 만."""
    if not _read_enabled():
        raise RuntimeError("firestore audit read fallback disabled")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = _get_db()
    q = (
        db.collection(_COLLECTION)
        .where("action", "==", "login")
        .where("success", "==", True)
        .where("timestamp", ">=", cutoff)
    )
    buckets: dict[int, int] = {h: 0 for h in range(24)}
    for d in q.stream():
        ts = d.to_dict().get("timestamp")
        if ts:
            buckets[ts.hour] += 1
    return buckets


def read_login_stats(days: int = 30) -> dict:
    """일정 기간 로그인 통계 — 성공/실패/성공률/고유 사용자."""
    if not _read_enabled():
        raise RuntimeError("firestore audit read fallback disabled")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = _get_db()
    q = (
        db.collection(_COLLECTION)
        .where("action", "==", "login")
        .where("timestamp", ">=", cutoff)
    )
    total = success = 0
    unique_users: set[int] = set()
    for d in q.stream():
        data = d.to_dict()
        total += 1
        if data.get("success"):
            success += 1
        uid = data.get("user_id")
        if uid is not None:
            unique_users.add(uid)
    return {
        "total": total,
        "success": success,
        "failed": total - success,
        "success_rate": success / total if total else 0.0,
        "unique_users": len(unique_users),
    }


def read_brute_force_candidates(
    hours: int = 24,
    min_fails: int = 3,
) -> list[dict]:
    """hours 시간 이내 실패 ≥ min_fails 인 employee_id 목록.

    Firestore 는 native GROUP BY 미지원이라 클라이언트 측 집계.
    """
    if not _read_enabled():
        raise RuntimeError("firestore audit read fallback disabled")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    db = _get_db()
    q = (
        db.collection(_COLLECTION)
        .where("action", "==", "login")
        .where("success", "==", False)
        .where("timestamp", ">=", cutoff)
    )
    by_emp: dict[str, list[dict]] = {}
    for d in q.stream():
        data = d.to_dict()
        emp = data.get("employee_id", "")
        if not emp:
            continue
        by_emp.setdefault(emp, []).append(data)

    out: list[dict] = []
    for emp, rows in by_emp.items():
        if len(rows) < min_fails:
            continue
        last_ts = max(r["timestamp"] for r in rows if r.get("timestamp"))
        ips = sorted({r.get("ip_address", "") for r in rows if r.get("ip_address")})
        out.append({
            "employee_id": emp,
            "fail_count": len(rows),
            "last_attempt": last_ts.isoformat() if last_ts else "",
            "ip_addresses": ips,
        })
    out.sort(key=lambda x: x["fail_count"], reverse=True)
    return out


def is_available() -> bool:
    """Firestore audit 가 호출 가능한 상태인지 확인 (lifespan / health check 용).

    v4.8 F — FIRESTORE_AUDIT_ENABLED=false 시 즉시 False (no-op 보장).
    """
    if not _read_enabled():
        return False
    try:
        _get_db()
        return True
    except Exception:
        return False
