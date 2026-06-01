"""D 컴플라이언스 알람 집계 서비스 (v4.2 Phase 1).

5종 소스 통합 → `ComplianceAlarm` 리스트. dashboard.tsx 가 polling 으로 소비.

Phase 1: 활성 — `_law_change_alarms`, `_dday_imminent_alarms`
Phase 3: 활성 예정 — `_impact_score_alarms`, `_unresolved_action_alarms`, `_trend_spike_alarms`

ack 영속화: `compliance_alarm_acks` 테이블 (이 모듈이 멱등 생성).
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from backend.schemas.compliance_alarm import (
    AlarmSeverity,
    AlarmSource,
    ComplianceAlarm,
)
from features.compliance.alerts.change_detector import CHANGE_DB_PATH

logger = logging.getLogger(__name__)

# 프로젝트 루트 기반 scenarios 디렉토리 — CHANGE_DB_PATH 가 'data/...' 상대 경로이므로 동일 기준 사용.
_SCENARIOS_DIR = Path(CHANGE_DB_PATH).parent / "scenarios"

# new_value / summary_ko 에서 시행일(YYYY-MM-DD) 휴리스틱 추출.
_DATE_RE = re.compile(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})")

# 소스 1 — change_type 별 severity 매핑.
_LAW_CHANGE_SEVERITY: dict[str, AlarmSeverity] = {
    "added": "HIGH",
    "new": "HIGH",
    "modified": "MEDIUM",
    "removed": "MEDIUM",
}


# ═══════════════════════════════════════════════════════════
# 영속화 테이블 — ack + scenario score 캐시
# ═══════════════════════════════════════════════════════════

# scenario score 캐시 TTL — 1시간 (3600초). 시나리오 JSON 변경은 드물기에 보수적 설정.
SCENARIO_SCORE_TTL_SEC = 3600


def _ensure_aggregator_tables(conn: sqlite3.Connection) -> None:
    """알람 집계용 테이블 2종 멱등 생성."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS compliance_alarm_acks (
            alarm_id TEXT PRIMARY KEY,
            acknowledged_at TEXT NOT NULL,
            actor TEXT NOT NULL,
            note TEXT DEFAULT ''
        )
        """
    )
    # v4.2 M3-4: 시나리오 영향점수 캐시 — 매 GET 마다 JSON 재계산 회피.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scenario_impact_scores (
            scenario_id TEXT PRIMARY KEY,
            impact_score INTEGER NOT NULL,
            computed_at TEXT NOT NULL,
            severity TEXT DEFAULT '',
            n_facilities INTEGER DEFAULT 0,
            n_impact_areas INTEGER DEFAULT 0
        )
        """
    )


def _load_ack_set(conn: sqlite3.Connection) -> set[str]:
    _ensure_aggregator_tables(conn)
    rows = conn.execute("SELECT alarm_id FROM compliance_alarm_acks").fetchall()
    return {r[0] for r in rows}


def _load_cached_scores(conn: sqlite3.Connection) -> dict[str, tuple[int, datetime]]:
    """캐시된 (scenario_id → score, computed_at) 매핑 반환. 만료 row 도 포함 — 호출자가 필터."""
    _ensure_aggregator_tables(conn)
    rows = conn.execute(
        "SELECT scenario_id, impact_score, computed_at FROM scenario_impact_scores"
    ).fetchall()
    out: dict[str, tuple[int, datetime]] = {}
    for sid, score, ts in rows:
        parsed = _parse_iso(ts) if ts else None
        if parsed is not None:
            out[sid] = (score, parsed)
    return out


def _persist_score(conn: sqlite3.Connection, scenario: dict[str, Any], score: int) -> None:
    sid = scenario.get("scenario_id") or scenario.get("id")
    if not sid:
        return
    conn.execute(
        """
        INSERT INTO scenario_impact_scores
          (scenario_id, impact_score, computed_at, severity, n_facilities, n_impact_areas)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(scenario_id) DO UPDATE SET
          impact_score = excluded.impact_score,
          computed_at = excluded.computed_at,
          severity = excluded.severity,
          n_facilities = excluded.n_facilities,
          n_impact_areas = excluded.n_impact_areas
        """,
        (
            sid,
            score,
            _now_iso(),
            (scenario.get("severity") or "").lower(),
            len(scenario.get("affected_facility_ids") or []),
            len(scenario.get("impact_areas") or []),
        ),
    )


def refresh_all_scenario_scores() -> dict[str, Any]:
    """모든 시나리오 점수 강제 재계산 + 캐시 갱신. 관리자/Celery 트리거용."""
    db_path = Path(CHANGE_DB_PATH)
    if not db_path.exists():
        raise RuntimeError(f"DB 없음: {db_path}")

    count = 0
    high_count = 0
    with sqlite3.connect(db_path) as conn:
        _ensure_aggregator_tables(conn)
        for sc in _iter_scenarios():
            score = _compute_scenario_impact_score(sc)
            _persist_score(conn, sc, score)
            count += 1
            if score >= 80:
                high_count += 1
        conn.commit()
    return {"refreshed": count, "high_severity": high_count, "computed_at": _now_iso()}


# ═══════════════════════════════════════════════════════════
# 헬퍼
# ═══════════════════════════════════════════════════════════


def _build_id(source: AlarmSource, regulation_id: str | int) -> str:
    return f"D-{source}-{regulation_id}"


def _extract_effective_date(*texts: Optional[str]) -> Optional[date]:
    for text in texts:
        if not text:
            continue
        m = _DATE_RE.search(text)
        if not m:
            continue
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ═══════════════════════════════════════════════════════════
# 소스 1 — 법규 변경 신규 발견
# ═══════════════════════════════════════════════════════════


def _matches_department(affected_json: str | None, department: str | None) -> bool:
    """affected_departments JSON 리스트 ↔ 사용자 부서 매칭. 빈/없음 = 전사 = 매칭."""
    if not department:
        return True
    if not affected_json:
        return True
    try:
        affected = json.loads(affected_json)
    except (json.JSONDecodeError, TypeError):
        return True
    if not isinstance(affected, list) or not affected:
        return True
    return department in affected


def _law_change_alarms(
    conn: sqlite3.Connection,
    ack_set: set[str],
    department: str | None = None,
) -> list[ComplianceAlarm]:
    rows = conn.execute(
        """
        SELECT id, detected_at, regulation_type, change_type,
               item_title, new_value, severity, grade, summary_ko,
               affected_departments
        FROM regulation_changes
        WHERE acknowledged = 0
        ORDER BY detected_at DESC
        LIMIT 100
        """
    ).fetchall()
    rows = [r for r in rows if _matches_department(r[9], department)]

    out: list[ComplianceAlarm] = []
    for r in rows:
        rid, detected_at, reg_type, change_type, title, new_value, _sev, grade, summary, _dept = r
        alarm_id = _build_id("law_change", rid)
        sev = _LAW_CHANGE_SEVERITY.get(change_type, "MEDIUM")
        # grade=CRITICAL 이면 한 단계 상향.
        if grade == "CRITICAL":
            sev = "CRITICAL"
        elif grade == "HIGH" and sev == "MEDIUM":
            sev = "HIGH"

        display_title = title or f"{reg_type} {change_type}"
        detail_parts = []
        if summary:
            detail_parts.append(summary)
        elif new_value:
            detail_parts.append(new_value[:120])
        detail_parts.append(f"[{reg_type}/{change_type}]")
        detail = " · ".join(p for p in detail_parts if p)

        out.append(ComplianceAlarm(
            id=alarm_id,
            severity=sev,
            title=display_title,
            detail=detail,
            source="law_change",
            regulation_id=str(rid),
            timestamp=detected_at or _now_iso(),
            acknowledged=alarm_id in ack_set,
        ))
    return out


# ═══════════════════════════════════════════════════════════
# 소스 3 — 시행일 D-day 임박
# ═══════════════════════════════════════════════════════════


def _dday_imminent_alarms(
    conn: sqlite3.Connection,
    ack_set: set[str],
    department: str | None = None,
) -> list[ComplianceAlarm]:
    rows = conn.execute(
        """
        SELECT id, detected_at, regulation_type, item_title, new_value, summary_ko,
               affected_departments
        FROM regulation_changes
        WHERE acknowledged = 0
        """
    ).fetchall()
    rows = [r for r in rows if _matches_department(r[6], department)]

    today = date.today()
    out: list[ComplianceAlarm] = []
    for r in rows:
        rid, detected_at, reg_type, title, new_value, summary, _dept = r
        ed = _extract_effective_date(new_value, summary)
        if ed is None:
            continue
        delta = (ed - today).days
        if delta < 0 or delta > 30:
            continue

        if delta <= 7:
            sev: AlarmSeverity = "CRITICAL"
        else:
            sev = "HIGH"

        alarm_id = _build_id("dday", rid)
        display_title = f"{title or reg_type} 시행 D-{delta}"
        detail = (
            f"시행일 {ed.isoformat()}"
            + (f" · {summary}" if summary else "")
        )
        out.append(ComplianceAlarm(
            id=alarm_id,
            severity=sev,
            title=display_title,
            detail=detail,
            source="dday",
            regulation_id=str(rid),
            effective_date=ed.isoformat(),
            timestamp=detected_at or _now_iso(),
            acknowledged=alarm_id in ack_set,
        ))
    return out


# ═══════════════════════════════════════════════════════════
# 소스 2 — 영향분석 점수 ≥80 (시나리오 JSON 기반 derive)
# ═══════════════════════════════════════════════════════════


def _compute_scenario_impact_score(scenario: dict[str, Any]) -> int:
    """
    JSON 시나리오에서 0-100 영향 점수 derive.

    가중치 (조정: SCN-001 산안법 ≥90 트리거 가능하도록):
    - severity: high=50 / medium=30 / low=15
    - affected_facility_ids: 1당 +8, 최대 +35
    - impact_areas: 1당 +5, 최대 +25
    - regulation.category in {safety, environmental, trade}: +15
    """
    sev = (scenario.get("severity") or "").lower()
    score = {"high": 50, "medium": 30, "low": 15}.get(sev, 0)

    n_facilities = len(scenario.get("affected_facility_ids") or [])
    score += min(n_facilities * 8, 35)

    n_areas = len(scenario.get("impact_areas") or [])
    score += min(n_areas * 5, 25)

    reg_cat = ((scenario.get("regulation") or {}).get("category") or "").lower()
    if reg_cat in {"safety", "environmental", "trade"}:
        score += 15

    return min(score, 100)


def _iter_scenarios() -> Iterable[dict[str, Any]]:
    """data/scenarios/*.json 을 순회. us_trade 처럼 list 컨테이너도 평탄화."""
    if not _SCENARIOS_DIR.exists():
        return
    for path in sorted(_SCENARIOS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("[alarm_aggregator] scenario %s 읽기 실패: %s", path.name, e)
            continue
        if isinstance(data, dict) and "scenarios" in data and isinstance(data["scenarios"], list):
            yield from data["scenarios"]
        elif isinstance(data, dict):
            yield data
        elif isinstance(data, list):
            yield from data


def _impact_score_alarms(conn: sqlite3.Connection, ack_set: set[str]) -> list[ComplianceAlarm]:
    """
    소스 2: scenario impact_score ≥80.

    v4.2 M3-4 — 캐시 우선:
    - `scenario_impact_scores` 테이블에서 ≤1h 캐시 hit 면 그대로 사용
    - miss 또는 stale 이면 JSON 재계산 + 캐시 갱신
    """
    now = _now_iso()
    cache = _load_cached_scores(conn)
    cache_cutoff = datetime.now(timezone.utc).astimezone() - timedelta(seconds=SCENARIO_SCORE_TTL_SEC)
    out: list[ComplianceAlarm] = []
    for sc in _iter_scenarios():
        scenario_id = sc.get("scenario_id") or sc.get("id")
        if not scenario_id:
            continue
        # 캐시 hit + fresh?
        cached = cache.get(scenario_id)
        if cached is not None and cached[1] >= cache_cutoff:
            score = cached[0]
        else:
            score = _compute_scenario_impact_score(sc)
            _persist_score(conn, sc, score)
        if score < 80:
            continue
        sev: AlarmSeverity = "CRITICAL" if score >= 90 else "HIGH"
        alarm_id = _build_id("impact_score", scenario_id)
        title = sc.get("title") or scenario_id
        impact_areas = sc.get("impact_areas") or []
        affected = sc.get("affected_facility_ids") or []
        detail = (
            f"영향점수 {score} · 영역 {len(impact_areas)}종 · 설비 {len(affected)}대"
            + (f" — {', '.join(impact_areas[:3])}" if impact_areas else "")
        )
        change_detail = sc.get("change_detail") or {}
        after = change_detail.get("after") if isinstance(change_detail, dict) else None
        eff = (after or {}).get("effective_date") if isinstance(after, dict) else None
        out.append(ComplianceAlarm(
            id=alarm_id,
            severity=sev,
            title=title,
            detail=detail,
            source="impact_score",
            regulation_id=str(scenario_id),
            effective_date=eff,
            timestamp=now,
            acknowledged=alarm_id in ack_set,
        ))
    return out


# ═══════════════════════════════════════════════════════════
# 소스 4 — 미해결 조치 7일 초과
# ═══════════════════════════════════════════════════════════


def _unresolved_action_alarms(
    conn: sqlite3.Connection,
    ack_set: set[str],
    department: str | None = None,
) -> list[ComplianceAlarm]:
    """소스 4: status='action_required' AND detected_at 으로부터 7일 초과."""
    rows = conn.execute(
        """
        SELECT id, detected_at, regulation_type, item_title, summary_ko, grade,
               CAST(julianday('now') - julianday(detected_at) AS INTEGER) AS days_old,
               assigned_to, affected_departments
        FROM regulation_changes
        WHERE status = 'action_required'
          AND julianday('now') - julianday(detected_at) >= 7
        ORDER BY days_old DESC
        LIMIT 50
        """
    ).fetchall()
    rows = [r for r in rows if _matches_department(r[8], department)]

    out: list[ComplianceAlarm] = []
    for r in rows:
        rid, detected_at, reg_type, title, summary, grade, days_old, assigned, _dept = r
        if days_old is None:
            continue
        # 14일+ 는 CRITICAL, 7-13일은 HIGH
        sev: AlarmSeverity = "CRITICAL" if days_old >= 14 else "HIGH"
        alarm_id = _build_id("unresolved", rid)
        display_title = f"미조치 {days_old}일 — {title or reg_type}"
        detail_parts = [f"필요 조치 미완 ({days_old}일)"]
        if assigned:
            detail_parts.append(f"담당 {assigned}")
        if summary:
            detail_parts.append(summary)
        out.append(ComplianceAlarm(
            id=alarm_id,
            severity=sev,
            title=display_title,
            detail=" · ".join(detail_parts),
            source="unresolved",
            regulation_id=str(rid),
            timestamp=detected_at or _now_iso(),
            acknowledged=alarm_id in ack_set,
        ))
    return out


# ═══════════════════════════════════════════════════════════
# 소스 5 — 트렌드 급증 (7일 일별 카운트 대비 ≥2σ)
# ═══════════════════════════════════════════════════════════


def _trend_spike_alarms(conn: sqlite3.Connection, ack_set: set[str]) -> list[ComplianceAlarm]:
    """
    소스 5: 최근 7일 일별 변경 건수가 28일 평균 + 2σ 초과하면 트리거.

    DB 의 detected_at (TEXT, ISO) 을 SQLite date() 로 그룹화해 일별 카운트 계산.
    """
    # 최근 28일 일별 카운트
    rows = conn.execute(
        """
        SELECT date(detected_at) AS d, COUNT(*) AS n
        FROM regulation_changes
        WHERE julianday('now') - julianday(detected_at) <= 28
        GROUP BY date(detected_at)
        ORDER BY d ASC
        """
    ).fetchall()
    if len(rows) < 8:
        return []  # 통계 의미 없음

    counts = [r[1] for r in rows[:-7]]  # baseline (앞쪽 21일)
    recent = rows[-7:]  # 최근 7일

    if len(counts) < 4:
        return []

    try:
        mean = statistics.mean(counts)
        stdev = statistics.pstdev(counts) or 1.0
    except statistics.StatisticsError:
        return []

    threshold = mean + 2 * stdev
    spike_days = [r for r in recent if r[1] >= threshold and r[1] >= mean + 1]
    if not spike_days:
        return []

    # 최신 spike 1건만 알람 — 동일 spike 가 며칠 연속이어도 통합.
    latest_day, latest_n = spike_days[-1]
    alarm_id = f"D-trend-{latest_day}"
    detail = (
        f"{latest_day} 변경 {latest_n}건 "
        f"(28일 평균 {mean:.1f} · σ {stdev:.1f}) — 평소보다 활발한 법규 활동"
    )
    sev: AlarmSeverity = "MEDIUM"
    return [ComplianceAlarm(
        id=alarm_id,
        severity=sev,
        title=f"법규 변경 급증 — {latest_day}",
        detail=detail,
        source="trend",
        regulation_id=None,
        timestamp=f"{latest_day}T00:00:00",
        acknowledged=alarm_id in ack_set,
    )]


# ═══════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════


def _dedup(alarms: Iterable[ComplianceAlarm]) -> list[ComplianceAlarm]:
    """(regulation_id, source) 조합 최신 1건 유지 — timestamp DESC 기준."""
    seen: dict[tuple[str, str], ComplianceAlarm] = {}
    for a in sorted(alarms, key=lambda x: x.timestamp, reverse=True):
        key = (a.regulation_id or a.id, a.source)
        if key not in seen:
            seen[key] = a
    return list(seen.values())


def collect_recent_alarms(
    limit: int = 50,
    since_ts: int = 0,
    department: str | None = None,
) -> list[ComplianceAlarm]:
    """
    5종 소스 통합 → timestamp DESC, dedup, limit.

    department: 부서명 지정 시 소스 1·3·4 의 affected_departments JSON 매칭만 반환.
    소스 2 (impact_score) 와 5 (trend) 는 전사 signal 이므로 부서와 무관하게 노출.
    """
    db_path = Path(CHANGE_DB_PATH)
    if not db_path.exists():
        logger.warning("[alarm_aggregator] DB 없음: %s", db_path)
        return []

    with sqlite3.connect(f"file:{db_path}?mode=rw", uri=True) as conn:
        ack_set = _load_ack_set(conn)
        all_alarms: list[ComplianceAlarm] = []
        # 부서 필터 적용 (소스 1·3·4)
        for collector in (
            _law_change_alarms,
            _dday_imminent_alarms,
            _unresolved_action_alarms,
        ):
            try:
                all_alarms.extend(collector(conn, ack_set, department=department))
            except sqlite3.Error as e:
                logger.warning("[alarm_aggregator] %s 실패: %s", collector.__name__, e)
        # 전사 signal (소스 2·5) — 부서 무관
        for collector in (_impact_score_alarms, _trend_spike_alarms):
            try:
                all_alarms.extend(collector(conn, ack_set))
            except sqlite3.Error as e:
                logger.warning("[alarm_aggregator] %s 실패: %s", collector.__name__, e)

    deduped = _dedup(all_alarms)
    deduped.sort(key=lambda a: a.timestamp, reverse=True)

    if since_ts > 0:
        # since_ts (epoch sec) 보다 새로운 알람만.
        cutoff = datetime.fromtimestamp(since_ts, tz=timezone.utc)
        deduped = [
            a for a in deduped
            if _parse_iso(a.timestamp) is None or _parse_iso(a.timestamp) >= cutoff  # type: ignore[operator]
        ]

    return deduped[:limit]


def _parse_iso(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def mark_acknowledged(alarm_id: str, actor: str, note: str = "") -> dict:
    """알람 ack 영속화. 멱등 — 동일 alarm_id 두 번째 호출은 actor/note 만 업데이트."""
    db_path = Path(CHANGE_DB_PATH)
    if not db_path.exists():
        raise RuntimeError(f"DB 없음: {db_path}")

    now = _now_iso()
    with sqlite3.connect(db_path) as conn:
        _ensure_aggregator_tables(conn)
        conn.execute(
            """
            INSERT INTO compliance_alarm_acks (alarm_id, acknowledged_at, actor, note)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(alarm_id) DO UPDATE SET
                acknowledged_at = excluded.acknowledged_at,
                actor = excluded.actor,
                note = excluded.note
            """,
            (alarm_id, now, actor, note),
        )
        conn.commit()
    return {"alarm_id": alarm_id, "acknowledged_at": now, "actor": actor}
