"""
규제 변경 자동 감지 엔진 (v3.1, v3.5 인코딩 수정)
- 크롤링 전후 JSON diff 비교
- 신규/변경/삭제 항목 자동 감지
- 변경 이력 SQLite 영구 저장

NOTE: 기존 텍스트 diff 기능은 text_change_detector.py로 이동됨
"""

import json
import sqlite3
from datetime import datetime
from typing import List, Dict
from pathlib import Path

CHANGE_DB_PATH = "data/compliance_changes.db"


def _safe_truncate(text: str, max_chars: int = 500) -> str:
    """v3.5: 멀티바이트 문자 안전 잘림.

    Python 문자열 슬라이싱은 코드포인트 단위이므로 대부분 안전하지만,
    합성 이모지/조합형 글자 중간 절단을 방지하기 위해 UTF-8 바이트 수 기반으로 제한한다.
    """
    if len(text) <= max_chars:
        return text
    # 문자 단위로 max_chars 만큼 자른 후 UTF-8 인코딩 크기가 과도하면 줄임
    truncated = text[:max_chars]
    # 유니코드 서로게이트 쌍 중간 절단 방지
    try:
        truncated.encode("utf-8")
    except UnicodeEncodeError:
        truncated = truncated[:-1]
    return truncated


def init_change_db():
    """변경 이력 DB 초기화 (v3.5: UTF-8 PRAGMA 추가, MVP: workflow + AI enrich 컬럼).

    멱등 마이그레이션 — 이미 존재하는 컬럼은 OperationalError 무시.
    """
    conn = sqlite3.connect(CHANGE_DB_PATH)
    conn.execute("PRAGMA encoding='UTF-8'")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS regulation_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detected_at TEXT NOT NULL,
            regulation_type TEXT NOT NULL,
            change_type TEXT NOT NULL,
            item_id TEXT,
            item_title TEXT,
            old_value TEXT,
            new_value TEXT,
            severity TEXT DEFAULT 'info',
            acknowledged INTEGER DEFAULT 0,
            acknowledged_by TEXT,
            acknowledged_at TEXT
        )
    """)

    # MVP 마이그레이션 — 신규 컬럼 7개 (멱등). 기존 row 는 default 값 사용.
    # P1 D1 — 법무 분류 + 벌칙 컬럼 3개 추가.
    _MVP_COLUMNS = [
        ("status", "TEXT DEFAULT 'pending'"),                 # pending / reviewing / planning / announced / done / filtered
        ("assigned_to", "TEXT DEFAULT ''"),                   # 책임자 사용자 ID
        ("audit_trail", "TEXT DEFAULT '[]'"),                 # JSON list[{ts, user, action, from, to}]
        ("summary_ko", "TEXT DEFAULT ''"),                    # Stage 3 LLM 1줄 요약
        ("grade", "TEXT DEFAULT 'MEDIUM'"),                   # Stage 5 — CRITICAL/HIGH/MEDIUM/LOW
        ("affected_departments", "TEXT DEFAULT '[]'"),        # Stage 4 영향 부서 (JSON)
        ("affected_plants", "TEXT DEFAULT '[]'"),             # Stage 4 영향 공장 (JSON)
        # P1 D1 — 법무 5분류 + 벌칙
        ("legal_class", "TEXT DEFAULT '[]'"),                 # JSON list — criminal/administrative/civil/contract/standardization
        ("penalty_extract", "TEXT DEFAULT ''"),               # 한 줄 (예: '5년 이하 징역, 1억 이하 벌금')
        ("penalty_severity_krw_mn", "INTEGER DEFAULT 0"),     # 정렬·집계용 (백만원 단위, 벌금 max)
        # v4.x — 과거/현재 전문 + diff + 사내 영향 분석 (Issue 3: 보고서 enrichment)
        ("before_text", "TEXT DEFAULT ''"),                   # 이전 조항 전문 (full)
        ("after_text", "TEXT DEFAULT ''"),                    # 현재 조항 전문 (full)
        ("diff_html", "TEXT DEFAULT ''"),                     # TextChangeDetector unified diff (HTML)
        ("impact_json", "TEXT DEFAULT '{}'"),                 # ImpactAnalyzer 결과 (affected_plants/processes/workers/risk_score/recommended_action)
    ]
    for col_name, col_def in _MVP_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE regulation_changes ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            # 이미 존재 — 무시
            pass

    # MVP — grade / status 인덱스 (피드 필터·KPI 집계용)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_changes_grade ON regulation_changes(grade)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_changes_status ON regulation_changes(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_changes_detected_at ON regulation_changes(detected_at)")

    # P2 D5 — Feedback Loop: 사용자 수정 이벤트 누적 (재학습 데이터 시드)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS change_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            change_id INTEGER REFERENCES regulation_changes(id),
            field TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            user_id TEXT,
            user_role TEXT,
            corrected_at TEXT NOT NULL,
            note TEXT DEFAULT ''
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_corrections_change ON change_corrections(change_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_corrections_field ON change_corrections(field)")

    # P3 D9 — 협업 티켓 (다중 부서 영향 변경의 책임자 자동 매핑)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS collab_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            change_id INTEGER REFERENCES regulation_changes(id),
            title TEXT NOT NULL,
            departments TEXT NOT NULL,
            owners TEXT DEFAULT '[]',
            status TEXT DEFAULT 'created',
            external_id TEXT DEFAULT '',
            external_url TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            resolved_at TEXT DEFAULT ''
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_change ON collab_tickets(change_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON collab_tickets(status)")

    # P5 §6 — Jira 양방향 sync audit (멱등 ALTER)
    try:
        conn.execute(
            "ALTER TABLE collab_tickets ADD COLUMN jira_last_sync_at TEXT DEFAULT ''"
        )
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise

    # P4 D15 — 신입 학습경로 큐레이션
    conn.execute("""
        CREATE TABLE IF NOT EXISTS learning_paths (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            owner_employee_id TEXT NOT NULL,
            assignee_employee_id TEXT NOT NULL,
            week_count INTEGER DEFAULT 4,
            curriculum_json TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lpath_assignee ON learning_paths(assignee_employee_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lpath_owner ON learning_paths(owner_employee_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS learning_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path_id INTEGER NOT NULL,
            week INTEGER NOT NULL,
            change_id INTEGER NOT NULL,
            read_at TEXT DEFAULT '',
            quiz_score INTEGER DEFAULT -1,
            quiz_attempts INTEGER DEFAULT 0,
            mentor_review TEXT DEFAULT '',
            mentor_comment TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lprog_path ON learning_progress(path_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lprog_review ON learning_progress(mentor_review)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS learning_quiz (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            change_id INTEGER NOT NULL UNIQUE,
            question TEXT NOT NULL,
            choices_json TEXT NOT NULL,
            answer_index INTEGER NOT NULL,
            generated_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    # P4.1 §4 — owner(사수) 의 시뮬 응시는 별도 컬럼에 기록 — assignee 점수 보호.
    try:
        conn.execute(
            "ALTER TABLE learning_progress ADD COLUMN mentor_dryrun_score INTEGER DEFAULT -1"
        )
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise

    # P5 §7 — 자체 결재 워크플로
    conn.execute("""
        CREATE TABLE IF NOT EXISTS approval_chains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            change_id INTEGER REFERENCES regulation_changes(id),
            name TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            current_step INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            completed_at TEXT DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_approval_chain_change ON approval_chains(change_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_approval_chain_status ON approval_chains(status)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS approval_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chain_id INTEGER NOT NULL,
            step_order INTEGER NOT NULL,
            approver_id TEXT NOT NULL,
            role_label TEXT DEFAULT '',
            decision TEXT DEFAULT 'pending',
            comment TEXT DEFAULT '',
            decided_at TEXT DEFAULT '',
            UNIQUE(chain_id, step_order)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_approval_step_chain ON approval_steps(chain_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_approval_step_approver ON approval_steps(approver_id, decision)"
    )

    # P4 D14 — 권한 위임 룰 엔진
    conn.execute("""
        CREATE TABLE IF NOT EXISTS delegation_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            owner TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            conditions_json TEXT NOT NULL,
            actions_json TEXT NOT NULL,
            priority INTEGER DEFAULT 100,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_delegation_priority ON delegation_rules(priority, enabled)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS delegation_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            change_id INTEGER NOT NULL,
            rule_id INTEGER NOT NULL,
            matched_at TEXT NOT NULL,
            applied_actions_json TEXT NOT NULL,
            result TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_delegation_audit_change ON delegation_audit(change_id)"
    )

    conn.commit()
    conn.close()


def detect_changes(
    regulation_type: str,
    old_data: List[Dict],
    new_data: List[Dict],
    id_field: str = "id",
    compare_fields: List[str] = None,
) -> List[Dict]:
    """두 데이터셋 간 변경 사항 감지"""
    changes = []

    old_map = {str(item.get(id_field, i)): item for i, item in enumerate(old_data)}
    new_map = {str(item.get(id_field, i)): item for i, item in enumerate(new_data)}

    old_ids = set(old_map.keys())
    new_ids = set(new_map.keys())

    for item_id in new_ids - old_ids:
        item = new_map[item_id]
        changes.append({
            "regulation_type": regulation_type,
            "change_type": "added",
            "item_id": item_id,
            "item_title": item.get("title", item.get("name", item.get("name_ko", str(item_id)))),
            "old_value": None,
            "new_value": _safe_truncate(json.dumps(item, ensure_ascii=False), 500),
            "severity": "warning",
        })

    for item_id in old_ids - new_ids:
        item = old_map[item_id]
        changes.append({
            "regulation_type": regulation_type,
            "change_type": "removed",
            "item_id": item_id,
            "item_title": item.get("title", item.get("name", item.get("name_ko", str(item_id)))),
            "old_value": _safe_truncate(json.dumps(item, ensure_ascii=False), 500),
            "new_value": None,
            "severity": "info",
        })

    for item_id in old_ids & new_ids:
        old_item = old_map[item_id]
        new_item = new_map[item_id]
        fields = compare_fields or list(set(old_item.keys()) | set(new_item.keys()))
        diffs = []
        for field in fields:
            old_val = str(old_item.get(field, ""))
            new_val = str(new_item.get(field, ""))
            if old_val != new_val:
                diffs.append(f"{field}: '{_safe_truncate(old_val, 50)}' -> '{_safe_truncate(new_val, 50)}'")
        if diffs:
            # v4.x — 전문 텍스트 추출 (보고서 diff 용)
            before_text = _extract_full_text(old_item)
            after_text = _extract_full_text(new_item)
            changes.append({
                "regulation_type": regulation_type,
                "change_type": "modified",
                "item_id": item_id,
                "item_title": new_item.get("title", new_item.get("name", new_item.get("name_ko", str(item_id)))),
                "old_value": "; ".join(diffs[:5]),
                "new_value": _safe_truncate(json.dumps(new_item, ensure_ascii=False), 500),
                "severity": "warning" if len(diffs) >= 3 else "info",
                "before_text": before_text,
                "after_text": after_text,
            })

    return changes


def _extract_full_text(item: Dict) -> str:
    """규제 항목 dict 에서 본문 전문을 추출한다.

    크롤러별로 본문 필드명이 상이하므로 우선순위 매칭:
    full_text > content > text > description > body > summary
    """
    for key in ("full_text", "content", "text", "description", "body", "summary"):
        val = item.get(key)
        if val and isinstance(val, str) and val.strip():
            return val
    return ""


def save_changes(changes: List[Dict]) -> List[int]:
    """변경 사항 DB 저장. 신규 row id 리스트 반환 (Slack 라우팅 등 후속 단계용).

    MVP: change dict 의 enrich 필드 (summary_ko, grade, affected_departments,
    affected_plants, status) 도 함께 적재. 미존재 시 default.
    """
    if not changes:
        return []
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    now = datetime.now().isoformat()
    new_ids: List[int] = []
    for ch in changes:
        depts = ch.get("affected_departments", [])
        plants = ch.get("affected_plants", [])
        legal_classes = ch.get("legal_class", [])
        impact = ch.get("impact_json", {})
        cur = conn.execute(
            """INSERT INTO regulation_changes
               (detected_at, regulation_type, change_type, item_id, item_title,
                old_value, new_value, severity,
                summary_ko, grade, affected_departments, affected_plants, status,
                legal_class, penalty_extract, penalty_severity_krw_mn,
                before_text, after_text, diff_html, impact_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                now,
                ch["regulation_type"],
                ch["change_type"],
                ch.get("item_id", ""),
                ch.get("item_title", ""),
                ch.get("old_value"),
                ch.get("new_value"),
                ch.get("severity", "info"),
                ch.get("summary_ko", ""),
                ch.get("grade", "MEDIUM"),
                json.dumps(depts, ensure_ascii=False) if not isinstance(depts, str) else depts,
                json.dumps(plants, ensure_ascii=False) if not isinstance(plants, str) else plants,
                ch.get("status", "pending"),
                json.dumps(legal_classes, ensure_ascii=False) if not isinstance(legal_classes, str) else legal_classes,
                ch.get("penalty_extract", ""),
                int(ch.get("penalty_severity_krw_mn", 0) or 0),
                ch.get("before_text", ""),
                ch.get("after_text", ""),
                ch.get("diff_html", ""),
                json.dumps(impact, ensure_ascii=False) if not isinstance(impact, str) else impact,
            ),
        )
        new_ids.append(int(cur.lastrowid))
    conn.commit()
    conn.close()

    # D2 — post-persist 훅: HIGH/CRITICAL 즉시 알림 큐잉.
    try:
        from backend.services.notify.dispatcher import post_persist_hook
        for cid, ch in zip(new_ids, changes):
            post_persist_hook(cid, ch)
    except Exception:
        # 알림 실패가 변경 저장을 막아서는 안 된다.
        pass

    return new_ids


# ─────────────────────────────────────────────────────────────
# MVP — 워크플로우 상태 전환 + audit trail
# ─────────────────────────────────────────────────────────────

# 워크플로우 4단계 + filtered (노이즈 자동 archive 용)
_VALID_STATUS = {"pending", "reviewing", "planning", "announced", "done", "filtered"}


def update_change_status(change_id: int, new_status: str, user_id: str = "") -> bool:
    """변경 row 의 status 전환 + audit_trail JSON list append.

    Returns:
        True 성공 / False 미존재 또는 invalid status.
    """
    if new_status not in _VALID_STATUS:
        return False

    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        "SELECT status, audit_trail FROM regulation_changes WHERE id = ?", (change_id,)
    ).fetchone()
    if row is None:
        conn.close()
        return False

    prev_status = row["status"] or "pending"
    try:
        trail = json.loads(row["audit_trail"] or "[]")
        if not isinstance(trail, list):
            trail = []
    except json.JSONDecodeError:
        trail = []

    trail.append({
        "ts": datetime.now().isoformat(),
        "user": user_id,
        "action": "transition",
        "from": prev_status,
        "to": new_status,
    })

    conn.execute(
        "UPDATE regulation_changes SET status = ?, audit_trail = ? WHERE id = ?",
        (new_status, json.dumps(trail, ensure_ascii=False), change_id),
    )
    conn.commit()
    conn.close()
    return True


def get_extended_trend(window_days: int = 180) -> Dict:
    """P3 D13 — 확장 트렌드 (90/180일).

    Returns:
        {
          "window_days": int,
          "monthly_grade_trend": [{month, CRITICAL, HIGH, MEDIUM, LOW}],
          "by_dept_handling_hours": [{department, avg_hours, count}],
          "by_legal_class": {criminal: int, ...},
          "total": int,
        }
    """
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    conn.row_factory = sqlite3.Row

    from datetime import timedelta
    today = datetime.now()
    window_start = (today - timedelta(days=window_days)).isoformat()

    # 월별 등급 trend
    monthly_rows = conn.execute(
        """SELECT substr(detected_at, 1, 7) as month, grade, COUNT(*) as n
           FROM regulation_changes
           WHERE detected_at >= ? AND status != 'filtered'
           GROUP BY month, grade
           ORDER BY month""",
        (window_start,),
    ).fetchall()
    monthly_trend: Dict[str, Dict[str, int]] = {}
    for r in monthly_rows:
        monthly_trend.setdefault(r["month"], {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0})
        if r["grade"] in monthly_trend[r["month"]]:
            monthly_trend[r["month"]][r["grade"]] = r["n"]

    # 부서별 평균 처리 시간 (status='done' row 의 audit_trail 기준)
    done_rows = conn.execute(
        """SELECT detected_at, audit_trail, affected_departments
           FROM regulation_changes
           WHERE status = 'done' AND detected_at >= ?""",
        (window_start,),
    ).fetchall()
    dept_hours: Dict[str, list[float]] = {}
    for r in done_rows:
        try:
            trail = json.loads(r["audit_trail"] or "[]")
            done_event = next(
                (e for e in reversed(trail) if e.get("to") == "done"), None
            )
            if not done_event:
                continue
            t0 = datetime.fromisoformat(r["detected_at"])
            t1 = datetime.fromisoformat(done_event["ts"])
            hours = (t1 - t0).total_seconds() / 3600.0

            depts = json.loads(r["affected_departments"] or "[]")
            for d in depts:
                dept_hours.setdefault(d, []).append(hours)
        except (ValueError, KeyError, TypeError):
            continue

    by_dept = [
        {
            "department": d,
            "avg_hours": round(sum(hrs) / len(hrs), 1),
            "count": len(hrs),
        }
        for d, hrs in dept_hours.items()
    ]
    by_dept.sort(key=lambda x: -x["count"])

    # 법무 5분류 분포
    legal_rows = conn.execute(
        """SELECT legal_class FROM regulation_changes
           WHERE detected_at >= ? AND status != 'filtered'""",
        (window_start,),
    ).fetchall()
    by_legal_class: Dict[str, int] = {}
    for r in legal_rows:
        try:
            classes = json.loads(r["legal_class"] or "[]")
            for c in (classes if isinstance(classes, list) else []):
                by_legal_class[c] = by_legal_class.get(c, 0) + 1
        except (json.JSONDecodeError, TypeError):
            continue

    # Total
    total = conn.execute(
        "SELECT COUNT(*) as n FROM regulation_changes WHERE detected_at >= ? AND status != 'filtered'",
        (window_start,),
    ).fetchone()["n"]

    conn.close()
    return {
        "window_days": window_days,
        "monthly_grade_trend": [
            {"month": m, **counts}
            for m, counts in sorted(monthly_trend.items())
        ],
        "by_dept_handling_hours": by_dept[:10],  # top 10 by count
        "by_legal_class": by_legal_class,
        "total": int(total),
    }


def get_change_kpi(window_days: int = 30) -> Dict:
    """임원 KPI — 등급별 카운트 + 미해결 + 평균 처리시간 + 오늘 신규 + 30일 trend."""
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    conn.row_factory = sqlite3.Row

    # 이번달 등급별 카운트
    today = datetime.now()
    month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    grade_rows = conn.execute(
        """SELECT grade, COUNT(*) as n FROM regulation_changes
           WHERE detected_at >= ? GROUP BY grade""",
        (month_start,),
    ).fetchall()
    by_grade = {r["grade"]: r["n"] for r in grade_rows}

    # 미해결 누적 (status not in done/filtered)
    open_count = conn.execute(
        """SELECT COUNT(*) as n FROM regulation_changes
           WHERE status NOT IN ('done', 'filtered')"""
    ).fetchone()["n"]

    # 평균 처리시간 — done 상태인 변경의 audit_trail 첫·마지막 timestamp 차이 (시간 단위)
    done_rows = conn.execute(
        "SELECT detected_at, audit_trail FROM regulation_changes WHERE status = 'done'"
    ).fetchall()
    durations: List[float] = []
    for r in done_rows:
        try:
            trail = json.loads(r["audit_trail"] or "[]")
            done_event = next(
                (e for e in reversed(trail) if e.get("to") == "done"), None
            )
            if done_event:
                t0 = datetime.fromisoformat(r["detected_at"])
                t1 = datetime.fromisoformat(done_event["ts"])
                durations.append((t1 - t0).total_seconds() / 3600.0)
        except (ValueError, KeyError, TypeError):
            continue
    avg_hours = round(sum(durations) / len(durations), 1) if durations else 0.0

    # 오늘 신규
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    today_new = conn.execute(
        "SELECT COUNT(*) as n FROM regulation_changes WHERE detected_at >= ?",
        (today_start,),
    ).fetchone()["n"]

    # 30일 trend — 일자별 등급 카운트
    from datetime import timedelta
    window_start = (today - timedelta(days=window_days)).isoformat()
    trend_rows = conn.execute(
        """SELECT substr(detected_at, 1, 10) as day, grade, COUNT(*) as n
           FROM regulation_changes
           WHERE detected_at >= ?
           GROUP BY day, grade
           ORDER BY day""",
        (window_start,),
    ).fetchall()
    trend: Dict[str, Dict[str, int]] = {}
    for r in trend_rows:
        trend.setdefault(r["day"], {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0})
        if r["grade"] in trend[r["day"]]:
            trend[r["day"]][r["grade"]] = r["n"]

    conn.close()
    return {
        "month_critical": by_grade.get("CRITICAL", 0),
        "month_high": by_grade.get("HIGH", 0),
        "month_medium": by_grade.get("MEDIUM", 0),
        "month_low": by_grade.get("LOW", 0),
        "open_count": open_count,
        "avg_hours_to_done": avg_hours,
        "today_new": today_new,
        "trend": [{"day": d, **counts} for d, counts in sorted(trend.items())],
    }


def get_recent_changes(limit: int = 20, unacknowledged_only: bool = False) -> List[Dict]:
    """최근 변경 이력 조회"""
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM regulation_changes"
    if unacknowledged_only:
        query += " WHERE acknowledged = 0"
    query += " ORDER BY detected_at DESC LIMIT ?"
    rows = conn.execute(query, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def acknowledge_change(change_id: int, user_id: str = ""):
    """변경 확인 처리"""
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    conn.execute(
        "UPDATE regulation_changes SET acknowledged=1, acknowledged_by=?, acknowledged_at=? WHERE id=?",
        (user_id, datetime.now().isoformat(), change_id),
    )
    conn.commit()
    conn.close()


def get_change_stats() -> Dict:
    """변경 통계"""
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM regulation_changes").fetchone()[0]
    unack = conn.execute("SELECT COUNT(*) FROM regulation_changes WHERE acknowledged=0").fetchone()[0]
    added = conn.execute("SELECT COUNT(*) FROM regulation_changes WHERE change_type='added'").fetchone()[0]
    modified = conn.execute("SELECT COUNT(*) FROM regulation_changes WHERE change_type='modified'").fetchone()[0]
    removed = conn.execute("SELECT COUNT(*) FROM regulation_changes WHERE change_type='removed'").fetchone()[0]
    conn.close()
    return {"total": total, "unacknowledged": unack, "added": added, "modified": modified, "removed": removed}


def detect_crawl_changes(regulation_type: str, old_json_path: str, new_json_path: str, id_field: str = "id", items_key: str = None) -> List[Dict]:
    """크롤링 JSON 파일 비교 편의 함수"""
    old_path, new_path = Path(old_json_path), Path(new_json_path)
    if not old_path.exists() or not new_path.exists():
        return []
    try:
        old_data = json.loads(old_path.read_text(encoding="utf-8"))
        new_data = json.loads(new_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if items_key:
        old_data = old_data.get(items_key, old_data) if isinstance(old_data, dict) else old_data
        new_data = new_data.get(items_key, new_data) if isinstance(new_data, dict) else new_data
    if not isinstance(old_data, list):
        old_data = [old_data]
    if not isinstance(new_data, list):
        new_data = [new_data]
    return detect_changes(regulation_type, old_data, new_data, id_field=id_field)
