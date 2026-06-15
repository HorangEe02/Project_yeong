"""P4 D14 — 권한 위임 룰 엔진.

현직자·법무·실무자가 반복 transition 패턴을 룰로 자동화.

룰 모델 (JSON):
  conditions:
    grade_in: ["MEDIUM","LOW"] | None
    departments_subset_of: ["환경","품질"] | None  # change.affected_departments ⊆ this
    legal_class_in: ["administrative"] | None
    penalty_max_krw_mn: 100 | None                  # change.penalty_severity_krw_mn ≤ this
    keywords_any: ["EU","RoHS"] | None              # title 또는 summary 부분 매치
  actions:
    assign_to: "EMP1234" | None
    transition_to: "reviewing"|"planning"|"announced" | None
    notify_slack: ["#compliance"] | None
    auto_create_ticket: bool

평가 순서: enabled=1, priority ASC. 첫 매치만 적용 (단일 매치 정책).
audit: 모든 매치 (적용/dry_run/skip) 를 delegation_audit 에 기록.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# P5 §3 — 룰 in-memory cache (TTL 5초)
# transition hook 등 hot path 에서 매번 DB hit 회피.
# CUD (create/update/delete) 직후 명시적 invalidate.
_RULES_CACHE: dict[str, Any] = {"ts": 0.0, "rules": None}
_RULES_CACHE_TTL_SEC = 5.0


def _invalidate_rules_cache() -> None:
    _RULES_CACHE["rules"] = None
    _RULES_CACHE["ts"] = 0.0


def _list_rules_cached(enabled_only: bool = False) -> list[dict[str, Any]]:
    """list_rules() 의 TTL cache 버전 — evaluate hot path 용."""
    now = time.time()
    if _RULES_CACHE["rules"] is not None and (now - _RULES_CACHE["ts"]) < _RULES_CACHE_TTL_SEC:
        rules = _RULES_CACHE["rules"]
    else:
        rules = list_rules(enabled_only=False)
        _RULES_CACHE["ts"] = now
        _RULES_CACHE["rules"] = rules
    if enabled_only:
        return [r for r in rules if r.get("enabled")]
    return list(rules)


# ─────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────


def _conn() -> sqlite3.Connection:
    from features.compliance.alerts.change_detector import init_change_db, CHANGE_DB_PATH
    init_change_db()
    c = sqlite3.connect(CHANGE_DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _row_to_rule(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    try:
        d["conditions"] = json.loads(d.pop("conditions_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["conditions"] = {}
    try:
        d["actions"] = json.loads(d.pop("actions_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["actions"] = {}
    d["enabled"] = bool(d.get("enabled"))
    return d


# ─────────────────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────────────────


def list_rules(enabled_only: bool = False) -> list[dict[str, Any]]:
    c = _conn()
    sql = "SELECT * FROM delegation_rules"
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY priority ASC, id ASC"
    rows = c.execute(sql).fetchall()
    c.close()
    return [_row_to_rule(r) for r in rows]


def get_rule(rule_id: int) -> dict[str, Any] | None:
    c = _conn()
    row = c.execute("SELECT * FROM delegation_rules WHERE id = ?", (rule_id,)).fetchone()
    c.close()
    return _row_to_rule(row) if row else None


# P5 §2 — DSL JSON 검증: 알려진 키만 통과, 그 외는 logger.warning + 무시.
_KNOWN_CONDITION_KEYS = {
    "grade_in", "departments_subset_of", "legal_class_in",
    "penalty_max_krw_mn", "keywords_any",
}
_KNOWN_ACTION_KEYS = {
    "assign_to", "transition_to", "notify_slack", "auto_create_ticket",
}


def _sanitize_rule_dict(
    raw: dict[str, Any] | None,
    known_keys: set[str],
    label: str,
) -> dict[str, Any]:
    """raw dict 에서 알려진 키만 보존. 알려지지 않은 키는 warning + 제외."""
    if not isinstance(raw, dict):
        raise ValueError(f"{label} 는 dict 여야 합니다 (got {type(raw).__name__})")
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if k in known_keys:
            out[k] = v
        else:
            logger.warning("%s 알 수 없는 키 무시: %s", label, k)
    return out


def create_rule(
    name: str,
    owner: str,
    conditions: dict[str, Any],
    actions: dict[str, Any],
    enabled: bool = True,
    priority: int = 100,
) -> int:
    # P5 §2 — 알려진 키만 통과 (DSL/raw JSON 입력 안전화)
    safe_conditions = _sanitize_rule_dict(conditions or {}, _KNOWN_CONDITION_KEYS, "conditions")
    safe_actions = _sanitize_rule_dict(actions or {}, _KNOWN_ACTION_KEYS, "actions")
    now = datetime.now().isoformat()
    c = _conn()
    cur = c.execute(
        """INSERT INTO delegation_rules
           (name, owner, enabled, conditions_json, actions_json, priority, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            name[:200],
            owner[:100],
            1 if enabled else 0,
            json.dumps(safe_conditions, ensure_ascii=False),
            json.dumps(safe_actions, ensure_ascii=False),
            int(priority),
            now,
            now,
        ),
    )
    rule_id = int(cur.lastrowid)
    c.commit()
    c.close()
    _invalidate_rules_cache()
    return rule_id


def update_rule(
    rule_id: int,
    name: str | None = None,
    enabled: bool | None = None,
    conditions: dict[str, Any] | None = None,
    actions: dict[str, Any] | None = None,
    priority: int | None = None,
) -> bool:
    c = _conn()
    row = c.execute("SELECT id FROM delegation_rules WHERE id = ?", (rule_id,)).fetchone()
    if row is None:
        c.close()
        return False
    sets: list[str] = []
    params: list[Any] = []
    if name is not None:
        sets.append("name = ?")
        params.append(name[:200])
    if enabled is not None:
        sets.append("enabled = ?")
        params.append(1 if enabled else 0)
    if conditions is not None:
        # P5 §2 sanitize
        safe_conditions = _sanitize_rule_dict(
            conditions, _KNOWN_CONDITION_KEYS, "conditions",
        )
        sets.append("conditions_json = ?")
        params.append(json.dumps(safe_conditions, ensure_ascii=False))
    if actions is not None:
        safe_actions = _sanitize_rule_dict(actions, _KNOWN_ACTION_KEYS, "actions")
        sets.append("actions_json = ?")
        params.append(json.dumps(safe_actions, ensure_ascii=False))
    if priority is not None:
        sets.append("priority = ?")
        params.append(int(priority))
    if not sets:
        c.close()
        return True
    sets.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(rule_id)
    c.execute(f"UPDATE delegation_rules SET {', '.join(sets)} WHERE id = ?", params)
    c.commit()
    c.close()
    _invalidate_rules_cache()
    return True


def delete_rule(rule_id: int) -> bool:
    c = _conn()
    cur = c.execute("DELETE FROM delegation_rules WHERE id = ?", (rule_id,))
    c.commit()
    affected = cur.rowcount
    c.close()
    if affected:
        _invalidate_rules_cache()
    return bool(affected)


# ─────────────────────────────────────────────────────────────
# 평가 + 적용
# ─────────────────────────────────────────────────────────────


def _normalize_change(change: dict[str, Any]) -> dict[str, Any]:
    """change row 의 JSON 컬럼을 list/dict 로 풀고 누락 필드 default 채움."""
    out = dict(change)
    for fld in ("affected_departments", "affected_plants", "legal_class"):
        v = out.get(fld)
        if isinstance(v, str):
            try:
                out[fld] = json.loads(v) if v else []
            except json.JSONDecodeError:
                out[fld] = []
        elif v is None:
            out[fld] = []
    out.setdefault("grade", "MEDIUM")
    out.setdefault("status", "pending")
    out.setdefault("penalty_severity_krw_mn", 0)
    out.setdefault("item_title", "")
    out.setdefault("summary_ko", "")
    return out


def _matches(conditions: dict[str, Any], change: dict[str, Any]) -> bool:
    """모든 명시 조건이 통과하면 True. None/누락 조건은 무시."""
    grade_in = conditions.get("grade_in")
    if grade_in:
        if change.get("grade") not in grade_in:
            return False

    dept_subset = conditions.get("departments_subset_of")
    if dept_subset is not None:
        depts = set(change.get("affected_departments") or [])
        if not depts:
            return False
        if not depts.issubset(set(dept_subset)):
            return False

    legal_in = conditions.get("legal_class_in")
    if legal_in:
        cls = set(change.get("legal_class") or [])
        if not cls.intersection(set(legal_in)):
            return False

    penalty_max = conditions.get("penalty_max_krw_mn")
    if penalty_max is not None:
        try:
            if int(change.get("penalty_severity_krw_mn") or 0) > int(penalty_max):
                return False
        except (TypeError, ValueError):
            return False

    kws = conditions.get("keywords_any")
    if kws:
        text = (change.get("item_title") or "") + " " + (change.get("summary_ko") or "")
        if not any(k for k in kws if k and k.lower() in text.lower()):
            return False

    return True


# trigger 별 허용된 액션 — 사용자 transition 의도 침식 방지.
ALLOWED_ACTIONS_PER_TRIGGER: dict[str, set[str]] = {
    "manual": {"assign_to", "transition_to", "notify_slack", "auto_create_ticket"},
    "post_user_transition": {"assign_to", "notify_slack", "auto_create_ticket"},
    "dry_run_recent": set(),
}


def evaluate(
    change: dict[str, Any],
    *,
    dry_run: bool = False,
    trigger: str = "manual",
) -> dict[str, Any]:
    """change 에 대한 룰 평가.

    enabled=1 룰을 priority ASC 로 순회. 첫 매치만 apply_actions.
    dry_run=True 면 audit 만 기록, 실제 transition/assign 은 skip.

    trigger:
      - "manual": API 호출 / admin dry-run 등 — 모든 액션 허용
      - "post_user_transition": 사용자 transition 직후 hook — transition_to 액션 자동 skip
        (사용자 의도 우선, 룰은 보조 — assign/notify/ticket 만 발화)
      - "dry_run_recent": 최근 N개 변경 시뮬 — 모든 사이드이펙트 skip (audit 만)

    Returns:
        {matched: bool, rule_id, rule_name, applied_actions, result, trigger}
    """
    norm = _normalize_change(change)
    change_id = int(norm.get("id") or norm.get("change_id") or 0)
    # P5 §3 — cached list (TTL 5초). CUD 시 자동 invalidate.
    rules = _list_rules_cached(enabled_only=True)

    for rule in rules:
        if not _matches(rule.get("conditions", {}), norm):
            continue
        applied = apply_actions(change_id, rule, norm, dry_run=dry_run, trigger=trigger)
        return {
            "matched": True,
            "rule_id": int(rule["id"]),
            "rule_name": rule.get("name", ""),
            "applied_actions": applied.get("applied", {}),
            "result": applied.get("result", ""),
            "trigger": trigger,
        }
    return {
        "matched": False,
        "rule_id": 0,
        "rule_name": "",
        "applied_actions": {},
        "result": "no_match",
        "trigger": trigger,
    }


def apply_actions(
    change_id: int,
    rule: dict[str, Any],
    change: dict[str, Any],
    *,
    dry_run: bool = False,
    trigger: str = "manual",
) -> dict[str, Any]:
    """룰의 actions 를 change 에 적용 + audit 기록.

    actions:
      - assign_to: change.assigned_to 갱신 (employee_id 가 employees.db 에 없으면 graceful skip)
      - transition_to: change_detector.update_change_status 호출
      - notify_slack: notify_slack.route() 호출
      - auto_create_ticket: collab_ticket.create_ticket 호출 (다중 부서일 때만)

    dry_run=True 면 모든 사이드이펙트 skip, audit 에 result='dry_run' 기록.
    trigger 가 ALLOWED_ACTIONS_PER_TRIGGER 에서 허용하지 않는 액션은 skip — 사용자
    transition 직후 룰의 transition_to 가 의도를 덮어쓰는 것을 방지.
    """
    actions = rule.get("actions") or {}
    applied: dict[str, Any] = {}
    errors: list[str] = []
    allowed = ALLOWED_ACTIONS_PER_TRIGGER.get(trigger, set())

    if dry_run:
        result = "dry_run"
    else:
        result = "applied"

        # 1) assign_to
        assign_to = (actions.get("assign_to") or "").strip()
        if assign_to and "assign_to" in allowed:
            ok = _maybe_assign(change_id, assign_to)
            if ok:
                applied["assign_to"] = assign_to
            else:
                errors.append(f"assign_to_skipped:{assign_to}")

        # 2) transition_to — 사용자 transition hook 에서는 자동 skip
        transition_to = (actions.get("transition_to") or "").strip()
        if transition_to and "transition_to" in allowed:
            try:
                from features.compliance.alerts.change_detector import update_change_status
                ok = update_change_status(
                    change_id, transition_to,
                    user_id=f"rule:{rule.get('id')}",
                )
                if ok:
                    applied["transition_to"] = transition_to
                else:
                    errors.append(f"transition_failed:{transition_to}")
            except Exception as e:  # pragma: no cover — 방어
                errors.append(f"transition_error:{e}")
        elif transition_to and "transition_to" not in allowed:
            # 의도된 skip — audit 에 명시
            errors.append(f"transition_skipped_by_trigger:{trigger}")

        # 3) notify_slack
        channels = actions.get("notify_slack") or []
        if channels and "notify_slack" in allowed:
            try:
                from features.compliance.alerts.notify_slack import route as slack_route
                sent = slack_route({
                    "grade": change.get("grade", "MEDIUM"),
                    "item_title": (
                        f"[자동 위임 룰: {rule.get('name','')}] "
                        f"{change.get('item_title','')}"
                    ),
                    "summary_ko": change.get("summary_ko", ""),
                    "change_type": "delegation",
                    "affected_departments": change.get("affected_departments", []),
                }, change_id=change_id)
                applied["notify_slack"] = bool(sent)
            except Exception as e:
                errors.append(f"slack_error:{e}")

        # 4) auto_create_ticket
        if actions.get("auto_create_ticket") and "auto_create_ticket" in allowed:
            depts = change.get("affected_departments") or []
            if len(depts) >= 2:
                try:
                    from features.compliance.infra.collab_ticket import create_ticket
                    out = create_ticket(change, change_id=change_id)
                    if out.get("ok"):
                        applied["ticket_id"] = out.get("ticket_id")
                except Exception as e:
                    errors.append(f"ticket_error:{e}")

        # P4.1 §5 — result 5종: applied / partial / error / no_action / dry_run
        if errors and applied:
            result = "partial:" + ";".join(errors[:2])
        elif errors and not applied:
            result = "error:" + ";".join(errors[:2])
        elif applied:
            result = "applied"
        else:
            result = "no_action"

    # audit
    try:
        c = _conn()
        c.execute(
            """INSERT INTO delegation_audit
               (change_id, rule_id, matched_at, applied_actions_json, result)
               VALUES (?,?,?,?,?)""",
            (
                change_id,
                int(rule.get("id") or 0),
                datetime.now().isoformat(),
                json.dumps(
                    {"actions": actions, "applied": applied, "errors": errors},
                    ensure_ascii=False,
                ),
                result,
            ),
        )
        c.commit()
        c.close()
    except Exception as e:
        logger.warning("delegation_audit 기록 실패: %s", e)

    return {"applied": applied, "errors": errors, "result": result}


def _maybe_assign(change_id: int, employee_id: str) -> bool:
    """change.assigned_to 갱신. employees.db 의 검증 실패 시 deny.

    P4.1 §1 — 정책 명시화 (deny by default):
      - `DELEGATION_REQUIRE_EMPLOYEES_DB=1` (기본): employees.db 미존재 또는
        employee_id 미발견 → False (assign skip).
      - `DELEGATION_REQUIRE_EMPLOYEES_DB=0`: 검증 우회 (테스트/단순 운영).
    """
    if not employee_id:
        return False
    require_db = os.environ.get("DELEGATION_REQUIRE_EMPLOYEES_DB", "1") == "1"

    import sqlite3 as _s
    from pathlib import Path
    emp_db = Path(__file__).parent.parent.parent / "data" / "employees.db"

    if require_db:
        if not emp_db.exists():
            return False  # production: DB 없으면 검증 불가 → deny
        try:
            ec = _s.connect(str(emp_db))
            row = ec.execute(
                "SELECT employee_id FROM employees WHERE employee_id = ? LIMIT 1",
                (employee_id,),
            ).fetchone()
            ec.close()
            if row is None:
                return False
        except _s.OperationalError as e:
            # employees 테이블 스키마 불일치 — 검증 불가 → deny
            logger.warning("employees.db 검증 실패 (deny): %s", e)
            return False

    # 검증 통과 (또는 require_db=0) → UPDATE
    try:
        c = _conn()
        cur = c.execute(
            "UPDATE regulation_changes SET assigned_to = ? WHERE id = ?",
            (employee_id, change_id),
        )
        c.commit()
        affected = cur.rowcount
        c.close()
        return bool(affected)
    except Exception as e:
        logger.warning("assign_to UPDATE 실패 change_id=%s emp=%s: %s",
                       change_id, employee_id, e)
        return False


# ─────────────────────────────────────────────────────────────
# Audit 조회 (admin 화면 — 매치 이력)
# ─────────────────────────────────────────────────────────────


def list_audit(
    rule_id: int | None = None,
    change_id: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    c = _conn()
    where: list[str] = []
    params: list[Any] = []
    if rule_id is not None:
        where.append("rule_id = ?")
        params.append(rule_id)
    if change_id is not None:
        where.append("change_id = ?")
        params.append(change_id)
    sql = "SELECT * FROM delegation_audit"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, min(limit, 500)))
    rows = c.execute(sql, params).fetchall()
    c.close()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        try:
            d["applied_actions"] = json.loads(d.pop("applied_actions_json") or "{}")
        except json.JSONDecodeError:
            d["applied_actions"] = {}
        out.append(d)
    return out


# ─────────────────────────────────────────────────────────────
# Dry-run 시뮬 (admin UI 의 "최근 N개 변경에 dry-run")
# ─────────────────────────────────────────────────────────────


def dry_run_recent(limit: int = 50) -> dict[str, Any]:
    """최근 변경 N개에 대해 dry_run 평가 — 실제 적용 없음, audit 만 기록.

    trigger='dry_run_recent' 와 dry_run=True 가 모두 적용되어 사이드이펙트 0.
    """
    c = _conn()
    rows = c.execute(
        """SELECT id, item_title, summary_ko, grade, status,
                  affected_departments, legal_class, penalty_severity_krw_mn
           FROM regulation_changes
           ORDER BY id DESC LIMIT ?""",
        (max(1, min(limit, 200)),),
    ).fetchall()
    c.close()

    matches: list[dict[str, Any]] = []
    counts: dict[int, int] = {}
    for r in rows:
        ch = dict(r)
        ch["change_id"] = ch["id"]
        result = evaluate(ch, dry_run=True, trigger="dry_run_recent")
        if result["matched"]:
            matches.append({
                "change_id": int(ch["id"]),
                "item_title": ch.get("item_title") or "",
                "rule_id": result["rule_id"],
                "rule_name": result["rule_name"],
                "applied_actions": result["applied_actions"],
            })
            rid = result["rule_id"]
            counts[rid] = counts.get(rid, 0) + 1
    return {
        "scanned": len(rows),
        "matched": len(matches),
        "by_rule": counts,
        "matches": matches[:50],
    }
