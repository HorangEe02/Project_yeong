"""P2 D5 — Feedback Loop (사람 수정 → 모델 재학습 시드).

ChangeFeed UI 에서 사용자가 AI 추천을 수정하면 그 이벤트를
`change_corrections` 테이블에 적재. 월 1회 누적 분석으로:
  - `impact_network.REGULATION_DEPT_MAP` 에 새 키워드↔부서 매핑 자동 추가
  - 5분류 LLM fewshot 사례 자동 dump

설계:
  1. record_correction() — change row 의 해당 field 도 즉시 업데이트 (UI 일관성)
  2. aggregate_corrections() — N일 누적 통계 (정확도 metric, P3 자동 재학습 시드)
  3. dump_fewshot_examples() — 사용자가 수정한 5분류 사례 → JSON fixture
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

VALID_FIELDS = {
    "affected_departments",   # JSON list[str]
    "affected_plants",        # JSON list[str]
    "legal_class",            # JSON list[str]
    "grade",                  # str (CRITICAL / HIGH / MEDIUM / LOW)
    "summary_ko",             # str
    "penalty_extract",        # str
}


def record_correction(
    change_id: int,
    field: str,
    new_value: Any,
    user_id: str = "",
    user_role: str = "",
    note: str = "",
) -> dict[str, Any]:
    """수정 이벤트 적재 + change row 의 해당 field 즉시 갱신.

    Returns:
        {ok: bool, correction_id: int, error?: str}
    """
    if field not in VALID_FIELDS:
        return {"ok": False, "error": f"invalid field: {field}. Must be one of {sorted(VALID_FIELDS)}"}

    from features.compliance.alerts.change_detector import init_change_db, CHANGE_DB_PATH
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    conn.row_factory = sqlite3.Row

    # 기존 값 조회
    row = conn.execute(
        f"SELECT {field} FROM regulation_changes WHERE id = ?", (change_id,)
    ).fetchone()
    if row is None:
        conn.close()
        return {"ok": False, "error": f"change_id={change_id} 미존재"}

    old_value = row[field]

    # 새 값 직렬화 (JSON list 필드는 자동 변환)
    if field in ("affected_departments", "affected_plants", "legal_class"):
        new_serialized = (
            json.dumps(new_value, ensure_ascii=False)
            if not isinstance(new_value, str)
            else new_value
        )
    else:
        new_serialized = str(new_value)

    now = datetime.now().isoformat()

    # change row 업데이트
    conn.execute(
        f"UPDATE regulation_changes SET {field} = ? WHERE id = ?",
        (new_serialized, change_id),
    )

    # correction 적재
    cur = conn.execute(
        """INSERT INTO change_corrections
           (change_id, field, old_value, new_value, user_id, user_role, corrected_at, note)
           VALUES (?,?,?,?,?,?,?,?)""",
        (change_id, field, old_value, new_serialized, user_id, user_role, now, note),
    )

    # audit_trail 에도 기록 (P1 워크플로우와 일관)
    audit_row = conn.execute(
        "SELECT audit_trail FROM regulation_changes WHERE id = ?", (change_id,)
    ).fetchone()
    try:
        trail = json.loads(audit_row["audit_trail"] or "[]")
        if not isinstance(trail, list):
            trail = []
    except (json.JSONDecodeError, TypeError):
        trail = []
    trail.append({
        "ts": now,
        "user": user_id,
        "action": "correction",
        "field": field,
    })
    conn.execute(
        "UPDATE regulation_changes SET audit_trail = ? WHERE id = ?",
        (json.dumps(trail, ensure_ascii=False), change_id),
    )

    conn.commit()
    correction_id = int(cur.lastrowid)
    conn.close()
    return {"ok": True, "correction_id": correction_id}


def aggregate_corrections(window_days: int = 30) -> dict[str, Any]:
    """N일 누적 수정 통계 — 정확도 metric + 키워드↔부서 패턴 추출.

    Returns:
        {
            "total": int,                        # 총 수정 건수
            "by_field": {field: count},          # 필드별 수정 빈도
            "by_role": {role: count},            # 사용자 역할별
            "frequent_dept_changes": [...],      # 자주 추가된 부서 (rule dict 보강 후보)
            "accuracy_signal": {                 # field 별 변경 률 (낮을수록 AI 정확)
                "affected_departments": float,
                ...
            },
        }
    """
    from features.compliance.alerts.change_detector import init_change_db, CHANGE_DB_PATH
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    conn.row_factory = sqlite3.Row

    from datetime import timedelta
    since = (datetime.now() - timedelta(days=window_days)).isoformat()

    rows = conn.execute(
        "SELECT * FROM change_corrections WHERE corrected_at >= ?", (since,)
    ).fetchall()

    by_field: dict[str, int] = {}
    by_role: dict[str, int] = {}
    dept_additions: dict[str, int] = {}  # 사용자가 새로 추가한 부서

    for r in rows:
        by_field[r["field"]] = by_field.get(r["field"], 0) + 1
        role = r["user_role"] or "unknown"
        by_role[role] = by_role.get(role, 0) + 1

        # 부서 매핑 수정에서 새로 추가된 부서 추출 (재학습 시드)
        if r["field"] == "affected_departments":
            try:
                old = set(json.loads(r["old_value"] or "[]"))
                new = set(json.loads(r["new_value"] or "[]"))
                for d in new - old:
                    dept_additions[d] = dept_additions.get(d, 0) + 1
            except (json.JSONDecodeError, TypeError):
                continue

    # 정확도 metric — 같은 기간 변경 총수 대비 수정 비율
    total_changes = conn.execute(
        "SELECT COUNT(*) as n FROM regulation_changes WHERE detected_at >= ?", (since,)
    ).fetchone()["n"]
    conn.close()

    accuracy_signal = {}
    if total_changes > 0:
        for fld in VALID_FIELDS:
            corrections = by_field.get(fld, 0)
            accuracy_signal[fld] = round(1 - (corrections / total_changes), 3)

    return {
        "total": len(rows),
        "by_field": by_field,
        "by_role": by_role,
        "frequent_dept_changes": sorted(
            dept_additions.items(), key=lambda x: -x[1]
        )[:10],
        "accuracy_signal": accuracy_signal,
        "window_days": window_days,
    }


def apply_aggregated_rules(
    window_days: int = 30,
    min_occurrences: int = 5,
    dry_run: bool = True,
) -> dict[str, Any]:
    """P3 D12 — 누적 수정 데이터 → 룰 dict / fewshot 자동 보강.

    Args:
        window_days: 분석 윈도우
        min_occurrences: 자동 적용 최소 횟수 (false positive 차단)
        dry_run: True 면 제안만, False 면 `data/learned_rules.json` 갱신

    Returns:
        {
            "dry_run": bool,
            "window_days": int,
            "min_occurrences": int,
            "added_dept_mappings": [{keyword, departments_added: list[str], occurrences: int}],
            "fewshot_added": int,
            "audit_log_path": str (commit 시),
        }
    """
    from pathlib import Path
    from datetime import datetime as _dt

    agg = aggregate_corrections(window_days=window_days)

    # 1) 부서 매핑 자동 보강 후보 — frequent_dept_changes 에서 min_occurrences 이상인 것
    candidates: list[dict[str, Any]] = []
    for dept, cnt in agg.get("frequent_dept_changes", []):
        if cnt >= min_occurrences:
            candidates.append({
                "department": dept,
                "occurrences": cnt,
                # 어떤 키워드 / 변경 본문에서 나왔는지 추적은 P4 — 현재는 누적 패턴만
            })

    # 2) Fewshot 사례 dump (legal_class 우선)
    fewshot = dump_fewshot_examples("legal_class", n=20)

    out = {
        "dry_run": dry_run,
        "window_days": window_days,
        "min_occurrences": min_occurrences,
        "added_dept_mappings": candidates,
        "fewshot_added": len(fewshot),
        "audit_log_path": "",
    }

    if dry_run or (not candidates and not fewshot):
        return out

    # 3) Commit — JSON 파일에 추가 (Python 코드 직접 수정 X — 안전)
    # NOTE: __file__ = features/compliance/infra/feedback_loop.py 이므로
    # 프로젝트 루트는 parents[3] (features → 루트).
    learned_rules_path = Path(__file__).resolve().parents[3] / "data" / "learned_rules.json"
    learned_rules_path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {}
    if learned_rules_path.exists():
        try:
            existing = json.loads(learned_rules_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    # frequent_dept_changes 를 누적 적재 — 다음 실행에서 중복 가산 방지
    existing.setdefault("auto_added_departments", [])
    for c in candidates:
        existing["auto_added_departments"].append({
            "department": c["department"],
            "occurrences": c["occurrences"],
            "applied_at": _dt.now().isoformat(),
        })

    existing["fewshot_legal_class"] = fewshot
    existing["last_updated_at"] = _dt.now().isoformat()
    existing["window_days"] = window_days

    learned_rules_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 4) Audit log
    audit_dir = Path(__file__).resolve().parents[3] / "data"
    audit_path = audit_dir / "feedback_loop_audit.json"
    audit_entries: list[dict[str, Any]] = []
    if audit_path.exists():
        try:
            audit_entries = json.loads(audit_path.read_text(encoding="utf-8"))
            if not isinstance(audit_entries, list):
                audit_entries = []
        except json.JSONDecodeError:
            audit_entries = []

    audit_entries.append({
        "ts": _dt.now().isoformat(),
        "window_days": window_days,
        "min_occurrences": min_occurrences,
        "candidates_added": len(candidates),
        "fewshot_dumped": len(fewshot),
    })
    audit_path.write_text(
        json.dumps(audit_entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    out["audit_log_path"] = str(audit_path)
    return out


def dump_fewshot_examples(field: str = "legal_class", n: int = 20) -> list[dict[str, Any]]:
    """사용자 수정 사례 → LLM fewshot fixture (재학습 시드).

    P3 의 자동 재학습이 이 fixture 를 prompt 에 주입.
    """
    from features.compliance.alerts.change_detector import init_change_db, CHANGE_DB_PATH
    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """SELECT c.field, c.old_value, c.new_value, c.note,
                  r.item_title, r.summary_ko
           FROM change_corrections c
           JOIN regulation_changes r ON c.change_id = r.id
           WHERE c.field = ?
           ORDER BY c.corrected_at DESC LIMIT ?""",
        (field, n),
    ).fetchall()
    conn.close()

    return [
        {
            "input": {
                "item_title": r["item_title"],
                "summary": r["summary_ko"],
            },
            "ai_recommendation": r["old_value"],
            "human_correction": r["new_value"],
            "note": r["note"] or "",
        }
        for r in rows
    ]
