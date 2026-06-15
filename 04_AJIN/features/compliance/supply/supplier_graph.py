"""P4 D16 — 2차/3차 협력사 그래프.

`suppliers.parent_supplier_id` 컬럼 (D16 마이그레이션) 을 사용해 트리 트래버설.
- traverse(supplier_id, max_depth, direction='down'|'up') — 자식/부모 체인
- affected_suppliers_multi_tier(change, max_depth) — P2 D6 매칭에 cascading 추가
- cycle 방어, 빈 graph 안전 응답.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


def _conn() -> sqlite3.Connection:
    from features.compliance.supply.supplier_compliance import init_suppliers_db, DB_PATH
    init_suppliers_db()
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _row_to_node(row: sqlite3.Row, depth: int) -> dict[str, Any]:
    d = dict(row)
    d["tier_depth"] = int(d.get("tier_depth") or 1)
    d["depth_from_origin"] = depth
    d["parent_supplier_id"] = d.get("parent_supplier_id") or ""
    d["relation_type"] = d.get("relation_type") or "direct"
    return d


def traverse(
    supplier_id: str,
    *,
    max_depth: int = 3,
    direction: str = "down",
) -> list[dict[str, Any]]:
    """트리 트래버설 — P4.1 §7: 1회 fetch + 메모리 BFS (N+1 SQL 제거).

    direction='down' — supplier_id 의 자식 (parent_supplier_id == supplier_id)
    direction='up'   — supplier_id 의 부모 체인 (root 까지)

    Returns: list of supplier dict + depth_from_origin (origin=0)
    cycle 감지: BFS 방문 set 사용. 발견 시 끊고 경고 log.
    """
    if direction not in ("down", "up"):
        raise ValueError("direction 은 'down' 또는 'up'")
    max_depth = max(1, min(int(max_depth), 5))

    c = _conn()
    rows = c.execute("SELECT * FROM suppliers").fetchall()
    c.close()
    by_id = {r["supplier_id"]: r for r in rows if r["supplier_id"]}
    by_parent: dict[str, list[Any]] = {}
    for r in rows:
        parent = r["parent_supplier_id"] or ""
        by_parent.setdefault(parent, []).append(r)

    out: list[dict[str, Any]] = []
    cycles: list[str] = []
    visited: set[str] = set()

    origin = by_id.get(supplier_id)
    if origin is None:
        return []

    out.append(_row_to_node(origin, 0))
    visited.add(supplier_id)

    if direction == "down":
        # BFS: queue = [(sid, depth_from_origin)]
        queue: list[tuple[str, int]] = [(supplier_id, 0)]
        while queue:
            sid, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for ch in by_parent.get(sid, []):
                cid = ch["supplier_id"]
                if not cid or cid == sid:
                    continue
                if cid in visited:
                    cycles.append(cid)
                    continue
                visited.add(cid)
                out.append(_row_to_node(ch, depth + 1))
                queue.append((cid, depth + 1))
    else:  # up — 부모 체인 (단일 chain, BFS 불필요)
        cur_sid = supplier_id
        for depth in range(max_depth):
            row = by_id.get(cur_sid)
            if row is None:
                break
            parent_sid = row["parent_supplier_id"] or ""
            if not parent_sid:
                break
            if parent_sid in visited:
                cycles.append(parent_sid)
                break
            parent_row = by_id.get(parent_sid)
            if parent_row is None:
                break
            visited.add(parent_sid)
            out.append(_row_to_node(parent_row, depth + 1))
            cur_sid = parent_sid

    if cycles:
        logger.warning("supplier_graph cycle 감지 — supplier_ids=%s", cycles[:5])
    return out


def detect_cycles() -> list[list[str]]:
    """전체 supplier 그래프에서 cycle 감지 (CSV import 전 검증용)."""
    c = _conn()
    rows = c.execute(
        "SELECT supplier_id, parent_supplier_id FROM suppliers"
    ).fetchall()
    c.close()
    parent_of = {
        r["supplier_id"]: (r["parent_supplier_id"] or "")
        for r in rows
    }

    cycles: list[list[str]] = []
    for sid in parent_of:
        seen: list[str] = []
        cur = sid
        for _ in range(20):
            if cur in seen:
                cycles.append(seen + [cur])
                break
            seen.append(cur)
            cur = parent_of.get(cur) or ""
            if not cur:
                break
    # 중복 제거 (cycle 들은 회전 중복)
    unique: list[list[str]] = []
    seen_sets: set[frozenset[str]] = set()
    for cyc in cycles:
        s = frozenset(cyc)
        if s not in seen_sets:
            seen_sets.add(s)
            unique.append(cyc)
    return unique


def _node_matches_change(
    supplier_id: str,
    change_hs_codes: list[str],
    change_keywords: list[str],
) -> bool:
    """P5 §1 — cascade 후보 노드의 components/country 가 변경 HS·keyword 와 부분 일치?

    매치 축 (any one):
      1. supplier_components.hs_code 가 변경 HS 의 prefix 매치
      2. supplier_components.component_code 가 keyword 부분 포함
      3. suppliers.country 가 keyword 와 매칭 (US/EU/CN 등)
    """
    if not change_hs_codes and not change_keywords:
        return False
    from features.compliance.supply.supplier_compliance import init_suppliers_db, DB_PATH
    init_suppliers_db()
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    try:
        # 1) HS 코드 prefix 매치
        for hs in change_hs_codes:
            row = c.execute(
                "SELECT 1 FROM supplier_components WHERE supplier_id = ? AND hs_code LIKE ? LIMIT 1",
                (supplier_id, f"{hs}%"),
            ).fetchone()
            if row:
                return True
        # 2) component_code keyword 부분 매치
        if change_keywords:
            comps = c.execute(
                "SELECT component_code FROM supplier_components WHERE supplier_id = ?",
                (supplier_id,),
            ).fetchall()
            for r in comps:
                code = (r["component_code"] or "").lower()
                if any(kw.lower() in code for kw in change_keywords if kw):
                    return True
        # 3) country 매치
        sup_row = c.execute(
            "SELECT country FROM suppliers WHERE supplier_id = ?", (supplier_id,),
        ).fetchone()
        if sup_row:
            country = (sup_row["country"] or "").upper()
            for kw in change_keywords:
                if kw.upper() == country:
                    return True
    finally:
        c.close()
    return False


def affected_suppliers_multi_tier(
    change: dict[str, Any],
    *,
    max_depth: int = 3,
    top_k: int = 50,
) -> list[dict[str, Any]]:
    """P2 D6 의 1차 매칭에 cascading 추가.

    P5 §1 (v2) — `match_method` 필드로 primary / cascade 구분:
      1) `match_suppliers(change)` — 1차 매치는 그대로 `match_method='primary'`
      2) 각 1차의 children 중 `_node_matches_change` 통과한 것만 `match_method='cascade'`
         keyword/HS/country 매칭 안 되는 child 는 결과에서 제외 (false positive 제거)

    호출처 가이드: 자가진단 폼 자동 발송 등 액션 트리거는 `match_method == 'primary'`
    만 사용. cascade 항목은 UI 시각화용 (tree 뷰).
    """
    from features.compliance.supply.supplier_compliance import (
        match_suppliers, _extract_hs_codes, _extract_supplier_keywords,
    )
    primary = match_suppliers(change, top_k=top_k)

    primary_records = [
        dict(s,
             tier_depth=int(s.get("tier") or s.get("tier_depth") or 1),
             cascade_path=[s["supplier_id"]],
             depth_from_match=0,
             match_method="primary")
        for s in primary
    ]
    if max_depth <= 1 or not primary:
        return primary_records

    # change body 에서 keyword + HS 추출 (cascade 필터에 사용)
    body = " ".join([
        str(change.get("item_title") or ""),
        str(change.get("summary_ko") or ""),
        str(change.get("new_value") or "")[:1000],
    ])
    change_hs = _extract_hs_codes(body)
    change_kw = _extract_supplier_keywords(body)

    seen: set[str] = {p["supplier_id"] for p in primary}
    out: list[dict[str, Any]] = list(primary_records)

    for p in primary:
        sid = p["supplier_id"]
        try:
            tree = traverse(sid, max_depth=max_depth, direction="down")
        except Exception as e:
            logger.debug("traverse 실패 supplier_id=%s: %s", sid, e)
            continue
        for node in tree:
            cid = node["supplier_id"]
            if cid == sid or cid in seen:
                continue
            # P5 §1 — keyword/HS/country 매치 통과한 자식만 cascade 결과에 포함
            if not _node_matches_change(cid, change_hs, change_kw):
                continue
            seen.add(cid)
            out.append(dict(
                node,
                tier_depth=int(node.get("tier_depth") or 1),
                cascade_path=[sid, cid],
                depth_from_match=node.get("depth_from_origin", 1),
                match_method="cascade",
            ))
    return out
