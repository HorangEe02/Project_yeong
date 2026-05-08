"""협업 시나리오 CRUD + 매칭 + 변경 이력.

DB(scenarios.db) 우선, 비어있으면 코드 시드 fallback.
모든 변경(create/update/reset/deactivate/restore) 은 scenario_history 에 기록.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Optional

from core.scenarios.database import get_scenarios_db

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────
# 헬퍼
# ────────────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict[str, Any]:
    """sqlite Row → 사용자/관리자 응답용 dict (JSON 필드는 디코딩)."""
    if row is None:
        return {}
    return {
        "scenario_id": row["scenario_id"],
        "is_system_default": bool(row["is_system_default"]),
        "trigger_keywords": json.loads(row["trigger_keywords"] or "[]"),
        "situation": row["situation"] or "",
        "requesting_dept": row["requesting_dept"] or "",
        "my_actions": json.loads(row["my_actions"] or "[]"),
        "hand_off_to": row["hand_off_to"] or "",
        "hand_off_items": json.loads(row["hand_off_items"] or "[]"),
        "deadline_info": row["deadline_info"] or "",
        "related_sop_id": row["related_sop_id"] or "",
        "tips": json.loads(row["tips"] or "[]"),
        "priority": int(row["priority"] or 100),
        "scope_division": row["scope_division"] or "",
        "lang": row["lang"] or "ko",
        "created_by": row["created_by"] or "",
        "updated_by": row["updated_by"] or "",
        "created_at": row["created_at"] or "",
        "updated_at": row["updated_at"] or "",
        "is_active": bool(row["is_active"]),
    }


def _record_history(
    conn,
    scenario_id: str,
    action: str,
    changed_by: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    conn.execute(
        """INSERT INTO scenario_history (scenario_id, action, changed_by, before_json, after_json)
           VALUES (?, ?, ?, ?, ?)""",
        (
            scenario_id,
            action,
            changed_by or "",
            json.dumps(before or {}, ensure_ascii=False),
            json.dumps(after or {}, ensure_ascii=False),
        ),
    )


# ────────────────────────────────────────────────────────────────
# 조회
# ────────────────────────────────────────────────────────────────

def list_all(*, include_inactive: bool = False) -> list[dict[str, Any]]:
    conn = get_scenarios_db()
    where = "" if include_inactive else " WHERE is_active = 1"
    rows = conn.execute(
        f"SELECT * FROM collaboration_scenarios{where} ORDER BY priority, scenario_id"
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def list_for_user(division: str = "", lang: str = "ko") -> list[dict[str, Any]]:
    """사용자 부서/언어에 맞춰 활성 시나리오를 정렬해 반환.

    Phase 2 우선순위:
      1. 같은 부서 한정 + 언어 일치
      2. 전사 + 언어 일치
      3. 같은 부서 + lang fallback
      4. 전사 + lang fallback
    """
    conn = get_scenarios_db()
    rows = conn.execute(
        """SELECT * FROM collaboration_scenarios
           WHERE is_active = 1
             AND (scope_division = '' OR scope_division = ?)
           ORDER BY
             CASE WHEN scope_division = ? THEN 0 ELSE 1 END,
             CASE WHEN lang = ? THEN 0 ELSE 1 END,
             priority,
             scenario_id""",
        (division or "", division or "", lang or "ko"),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get(scenario_id: str) -> Optional[dict[str, Any]]:
    conn = get_scenarios_db()
    row = conn.execute(
        "SELECT * FROM collaboration_scenarios WHERE scenario_id = ?",
        (scenario_id,),
    ).fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def get_history(scenario_id: str, limit: int = 50) -> list[dict[str, Any]]:
    conn = get_scenarios_db()
    rows = conn.execute(
        """SELECT id, scenario_id, action, changed_by, changed_at, before_json, after_json
             FROM scenario_history
            WHERE scenario_id = ?
            ORDER BY changed_at DESC, id DESC
            LIMIT ?""",
        (scenario_id, limit),
    ).fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "scenario_id": r["scenario_id"],
            "action": r["action"],
            "changed_by": r["changed_by"] or "",
            "changed_at": r["changed_at"] or "",
            "before": json.loads(r["before_json"] or "{}"),
            "after": json.loads(r["after_json"] or "{}"),
        }
        for r in rows
    ]


# ────────────────────────────────────────────────────────────────
# 매칭
# ────────────────────────────────────────────────────────────────

def match(query: str, division: str = "", lang: str = "ko") -> Optional[dict[str, Any]]:
    """사용자 질문 → 가장 일치도 높은 시나리오 1개. LLM 미호출.

    매칭 규칙:
    - 트리거 키워드 부분 일치 (lowercase)
    - 같은 부서 한정 시나리오 우선 (Phase 2)
    - 매칭 시나리오가 여럿이면 priority 가 낮은(우선순위 높은) 것 선택
    """
    if not query or not query.strip():
        return None
    q_lower = query.lower()

    # DB 비어있으면 코드 시드 fallback (DB 부팅 실패 시 안전)
    candidates = list_for_user(division=division, lang=lang)
    if not candidates:
        from features.onboarding.collaboration_guide import COLLABORATION_SCENARIOS

        for sc in COLLABORATION_SCENARIOS:
            for kw in sc.trigger_keywords:
                if kw.lower() in q_lower:
                    return {
                        "scenario_id": sc.id,
                        "is_system_default": True,
                        "trigger_keywords": list(sc.trigger_keywords),
                        "situation": sc.situation,
                        "requesting_dept": sc.requesting_dept,
                        "my_actions": list(sc.my_actions),
                        "hand_off_to": sc.hand_off_to,
                        "hand_off_items": list(sc.hand_off_items),
                        "deadline_info": sc.deadline_info,
                        "related_sop_id": sc.related_sop_id,
                        "tips": list(sc.tips),
                        "priority": 100,
                        "scope_division": "",
                        "lang": "ko",
                        "is_active": True,
                    }
        return None

    best: Optional[dict[str, Any]] = None
    for sc in candidates:
        for kw in sc.get("trigger_keywords") or []:
            if kw and kw.lower() in q_lower:
                # candidates 는 이미 부서/언어/priority 정렬되어 있으므로 첫 매치가 best
                if best is None:
                    best = sc
                break
        if best:
            break
    return best


def record_usage(scenario_id: str, matched_by: str = "", query_text: str = "") -> None:
    """매칭 발생 시 통계용 행 기록 (Phase 3)."""
    try:
        conn = get_scenarios_db()
        conn.execute(
            "INSERT INTO scenario_usage (scenario_id, matched_by, query_text) VALUES (?, ?, ?)",
            (scenario_id, matched_by or "", (query_text or "")[:500]),
        )
        conn.commit()
        conn.close()
    except Exception as e:  # noqa: BLE001
        logger.warning("scenario_usage insert 실패: %s", e)


# ────────────────────────────────────────────────────────────────
# CUD
# ────────────────────────────────────────────────────────────────

def create(payload: dict[str, Any], actor: str) -> dict[str, Any]:
    """신규 시나리오 추가 (사용자 추가분, is_system_default=0)."""
    scenario_id = (payload.get("scenario_id") or "").strip()
    if not scenario_id:
        raise ValueError("scenario_id 가 필요합니다.")

    conn = get_scenarios_db()
    if conn.execute(
        "SELECT 1 FROM collaboration_scenarios WHERE scenario_id = ?", (scenario_id,)
    ).fetchone():
        conn.close()
        raise ValueError(f"이미 존재하는 scenario_id: {scenario_id}")

    conn.execute(
        """INSERT INTO collaboration_scenarios
             (scenario_id, is_system_default, trigger_keywords, situation,
              requesting_dept, my_actions, hand_off_to, hand_off_items,
              deadline_info, related_sop_id, tips, priority,
              scope_division, lang, created_by, updated_by, is_active)
           VALUES (?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        (
            scenario_id,
            json.dumps(payload.get("trigger_keywords") or [], ensure_ascii=False),
            payload.get("situation") or "",
            payload.get("requesting_dept") or "",
            json.dumps(payload.get("my_actions") or [], ensure_ascii=False),
            payload.get("hand_off_to") or "",
            json.dumps(payload.get("hand_off_items") or [], ensure_ascii=False),
            payload.get("deadline_info") or "",
            payload.get("related_sop_id") or "",
            json.dumps(payload.get("tips") or [], ensure_ascii=False),
            int(payload.get("priority") or 100),
            payload.get("scope_division") or "",
            payload.get("lang") or "ko",
            actor or "",
            actor or "",
        ),
    )
    after = get(scenario_id) or {}
    _record_history(conn, scenario_id, "create", actor, None, after)
    conn.commit()
    conn.close()
    return after


def update(scenario_id: str, patch: dict[str, Any], actor: str) -> dict[str, Any]:
    """기존 시나리오 수정. 시드/사용자 추가분 모두 가능 (변경 이력 기록)."""
    conn = get_scenarios_db()
    before_row = conn.execute(
        "SELECT * FROM collaboration_scenarios WHERE scenario_id = ?", (scenario_id,)
    ).fetchone()
    if not before_row:
        conn.close()
        raise ValueError(f"존재하지 않는 scenario_id: {scenario_id}")

    before = _row_to_dict(before_row)

    sets: list[str] = []
    params: list[Any] = []
    field_map = {
        "trigger_keywords": True,
        "situation": False,
        "requesting_dept": False,
        "my_actions": True,
        "hand_off_to": False,
        "hand_off_items": True,
        "deadline_info": False,
        "related_sop_id": False,
        "tips": True,
        "priority": False,
        "scope_division": False,
        "lang": False,
        "is_active": False,
    }
    for key, is_json in field_map.items():
        if key in patch:
            value = patch[key]
            if is_json:
                params.append(json.dumps(value or [], ensure_ascii=False))
            elif key == "is_active":
                params.append(1 if value else 0)
            elif key == "priority":
                params.append(int(value) if value is not None else 100)
            else:
                params.append(value or "")
            sets.append(f"{key} = ?")

    if not sets:
        conn.close()
        return before

    sets.append("updated_by = ?")
    params.append(actor or "")
    sets.append("updated_at = datetime('now')")
    params.append(scenario_id)

    conn.execute(
        f"UPDATE collaboration_scenarios SET {', '.join(sets)} WHERE scenario_id = ?",
        params,
    )
    after = _row_to_dict(
        conn.execute(
            "SELECT * FROM collaboration_scenarios WHERE scenario_id = ?",
            (scenario_id,),
        ).fetchone()
    )
    _record_history(conn, scenario_id, "update", actor, before, after)
    conn.commit()
    conn.close()
    return after


def reset_to_default(scenario_id: str, actor: str) -> dict[str, Any]:
    """시드 기본값으로 복구. 시드(is_system_default=1) 만 가능."""
    from features.onboarding.collaboration_guide import COLLABORATION_SCENARIOS

    seed = next((s for s in COLLABORATION_SCENARIOS if s.id == scenario_id), None)
    if seed is None:
        raise ValueError(f"기본값이 없는 scenario_id: {scenario_id} — Reset 불가")

    conn = get_scenarios_db()
    before_row = conn.execute(
        "SELECT * FROM collaboration_scenarios WHERE scenario_id = ?", (scenario_id,)
    ).fetchone()
    before = _row_to_dict(before_row) if before_row else None

    payload = {
        "trigger_keywords": list(seed.trigger_keywords),
        "situation": seed.situation,
        "requesting_dept": seed.requesting_dept,
        "my_actions": list(seed.my_actions),
        "hand_off_to": seed.hand_off_to,
        "hand_off_items": list(seed.hand_off_items),
        "deadline_info": seed.deadline_info,
        "related_sop_id": seed.related_sop_id,
        "tips": list(seed.tips),
        "priority": 100,
        "scope_division": "",
        "lang": "ko",
        "is_active": True,
    }

    conn.execute(
        """UPDATE collaboration_scenarios
              SET trigger_keywords=?, situation=?, requesting_dept=?,
                  my_actions=?, hand_off_to=?, hand_off_items=?,
                  deadline_info=?, related_sop_id=?, tips=?,
                  priority=?, scope_division=?, lang=?, is_active=?,
                  updated_by=?, updated_at=datetime('now')
            WHERE scenario_id=?""",
        (
            json.dumps(payload["trigger_keywords"], ensure_ascii=False),
            payload["situation"],
            payload["requesting_dept"],
            json.dumps(payload["my_actions"], ensure_ascii=False),
            payload["hand_off_to"],
            json.dumps(payload["hand_off_items"], ensure_ascii=False),
            payload["deadline_info"],
            payload["related_sop_id"],
            json.dumps(payload["tips"], ensure_ascii=False),
            payload["priority"],
            payload["scope_division"],
            payload["lang"],
            1,
            actor or "",
            scenario_id,
        ),
    )
    after = get(scenario_id) or {}
    _record_history(conn, scenario_id, "reset", actor, before, after)
    conn.commit()
    conn.close()
    return after


def delete_scenario(scenario_id: str, actor: str) -> dict[str, Any]:
    """삭제 — 사용자 추가분(is_system_default=0)은 hard delete, 시드는 soft (is_active=0)."""
    conn = get_scenarios_db()
    row = conn.execute(
        "SELECT * FROM collaboration_scenarios WHERE scenario_id = ?", (scenario_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"존재하지 않는 scenario_id: {scenario_id}")
    before = _row_to_dict(row)

    if before["is_system_default"]:
        # 시드는 soft delete 만 (영구 삭제 차단)
        conn.execute(
            "UPDATE collaboration_scenarios SET is_active=0, updated_by=?, updated_at=datetime('now') WHERE scenario_id=?",
            (actor or "", scenario_id),
        )
        action = "deactivate"
    else:
        # 사용자 추가분은 hard delete + 즐겨찾기 cascade
        conn.execute("DELETE FROM scenario_favorites WHERE scenario_id=?", (scenario_id,))
        conn.execute("DELETE FROM collaboration_scenarios WHERE scenario_id=?", (scenario_id,))
        action = "deactivate"  # 통합 액션명

    _record_history(conn, scenario_id, action, actor, before, None)
    conn.commit()
    conn.close()

    return {"action": action, "scenario_id": scenario_id, "is_system_default": before["is_system_default"]}


def restore_version(scenario_id: str, history_id: int, actor: str) -> dict[str, Any]:
    """변경 이력의 특정 버전(after_json) 으로 복구."""
    conn = get_scenarios_db()
    h = conn.execute(
        "SELECT * FROM scenario_history WHERE id=? AND scenario_id=?",
        (history_id, scenario_id),
    ).fetchone()
    if not h:
        conn.close()
        raise ValueError(f"history_id {history_id} 가 scenario_id {scenario_id} 에 없습니다.")

    target = json.loads(h["after_json"] or "{}")
    if not target:
        conn.close()
        raise ValueError("복구할 데이터(after_json)가 비어있습니다.")

    # 현재 행이 없으면 INSERT, 있으면 UPDATE — update() 헬퍼는 patch 의 일부만 받으므로 직접 처리
    before_row = conn.execute(
        "SELECT * FROM collaboration_scenarios WHERE scenario_id=?", (scenario_id,)
    ).fetchone()
    before = _row_to_dict(before_row) if before_row else None

    fields = [
        "trigger_keywords", "situation", "requesting_dept", "my_actions",
        "hand_off_to", "hand_off_items", "deadline_info", "related_sop_id",
        "tips", "priority", "scope_division", "lang", "is_active",
    ]
    json_fields = {"trigger_keywords", "my_actions", "hand_off_items", "tips"}

    if before_row:
        sets = ", ".join(f"{f}=?" for f in fields) + ", updated_by=?, updated_at=datetime('now')"
        params: list[Any] = []
        for f in fields:
            v = target.get(f)
            if f in json_fields:
                params.append(json.dumps(v or [], ensure_ascii=False))
            elif f == "is_active":
                params.append(1 if v else 0)
            elif f == "priority":
                params.append(int(v) if v is not None else 100)
            else:
                params.append(v or "")
        params.append(actor or "")
        params.append(scenario_id)
        conn.execute(
            f"UPDATE collaboration_scenarios SET {sets} WHERE scenario_id=?",
            params,
        )

    after = get(scenario_id) or {}
    _record_history(conn, scenario_id, "restore", actor, before, after)
    conn.commit()
    conn.close()
    return after


# ────────────────────────────────────────────────────────────────
# Phase 3 — 즐겨찾기 / 통계
# ────────────────────────────────────────────────────────────────

def add_favorite(employee_id: str, scenario_id: str, note: str = "") -> dict[str, Any]:
    conn = get_scenarios_db()
    conn.execute(
        """INSERT INTO scenario_favorites (employee_id, scenario_id, note)
           VALUES (?, ?, ?)
           ON CONFLICT(employee_id, scenario_id) DO UPDATE SET note=excluded.note""",
        (employee_id, scenario_id, note or ""),
    )
    conn.commit()
    conn.close()
    return {"employee_id": employee_id, "scenario_id": scenario_id, "note": note}


def remove_favorite(employee_id: str, scenario_id: str) -> int:
    conn = get_scenarios_db()
    cur = conn.execute(
        "DELETE FROM scenario_favorites WHERE employee_id=? AND scenario_id=?",
        (employee_id, scenario_id),
    )
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n


def update_favorite_note(employee_id: str, scenario_id: str, note: str) -> dict[str, Any]:
    return add_favorite(employee_id, scenario_id, note)


def list_favorites(employee_id: str) -> list[dict[str, Any]]:
    conn = get_scenarios_db()
    rows = conn.execute(
        """SELECT f.scenario_id, f.note, f.created_at, s.situation, s.requesting_dept,
                  s.deadline_info, s.is_active
             FROM scenario_favorites f
             LEFT JOIN collaboration_scenarios s ON f.scenario_id = s.scenario_id
            WHERE f.employee_id = ?
            ORDER BY f.created_at DESC""",
        (employee_id,),
    ).fetchall()
    conn.close()
    return [
        {
            "scenario_id": r["scenario_id"],
            "note": r["note"] or "",
            "created_at": r["created_at"] or "",
            "situation": r["situation"] or "",
            "requesting_dept": r["requesting_dept"] or "",
            "deadline_info": r["deadline_info"] or "",
            "is_active": bool(r["is_active"]) if r["is_active"] is not None else False,
        }
        for r in rows
    ]


def usage_stats(days: int = 30) -> dict[str, Any]:
    """시나리오별 매칭 횟수 + TOP/제로 매칭 시나리오."""
    conn = get_scenarios_db()
    cutoff = datetime.now(timezone.utc).isoformat()  # SQLite datetime('now') 비교를 위해 UTC iso
    rows = conn.execute(
        """SELECT u.scenario_id,
                  COUNT(*) AS hits,
                  s.situation, s.requesting_dept
             FROM scenario_usage u
             LEFT JOIN collaboration_scenarios s ON u.scenario_id = s.scenario_id
            WHERE u.matched_at >= datetime('now', ?)
            GROUP BY u.scenario_id
            ORDER BY hits DESC""",
        (f"-{int(days)} days",),
    ).fetchall()

    # 매칭 0회 시나리오 (개선 우선순위 후보)
    zero_rows = conn.execute(
        """SELECT scenario_id, situation, requesting_dept
             FROM collaboration_scenarios
            WHERE is_active = 1
              AND scenario_id NOT IN (
                SELECT DISTINCT scenario_id FROM scenario_usage
                WHERE matched_at >= datetime('now', ?)
              )""",
        (f"-{int(days)} days",),
    ).fetchall()

    conn.close()
    return {
        "days": days,
        "cutoff": cutoff,
        "by_scenario": [
            {
                "scenario_id": r["scenario_id"],
                "hits": int(r["hits"]),
                "situation": r["situation"] or "",
                "requesting_dept": r["requesting_dept"] or "",
            }
            for r in rows
        ],
        "zero_match": [
            {
                "scenario_id": r["scenario_id"],
                "situation": r["situation"] or "",
                "requesting_dept": r["requesting_dept"] or "",
            }
            for r in zero_rows
        ],
    }
