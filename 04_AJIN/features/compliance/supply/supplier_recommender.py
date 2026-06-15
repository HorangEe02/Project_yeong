"""P2 D6 — 대체 협력사 추천.

같은 부품·다른 협력사 + 컴플라이언스 점수·가격·납기·연간 거래액 다차원 비교.

설계:
  1. 입력 supplier_id 의 supplier_components 와 같은 hs_code 또는 component_code
     를 가진 다른 supplier 후보 추출.
  2. 다차원 점수 — compliance_score (40%) + 단가 (30%) + 거래량 (20%) +
     country diversity (10%, 기존과 다른 국가면 가산).
  3. top-3 + breakdown 반환.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


def _connect():
    from features.compliance.supply.supplier_compliance import init_suppliers_db, DB_PATH
    init_suppliers_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def recommend_alternatives(
    supplier_id: str,
    hs_code: str | None = None,
    component_code: str | None = None,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """같은 부품·다른 협력사 후보 top-k.

    매칭 우선순위:
      1. 같은 component_code (정확 매칭)
      2. 같은 hs_code (HS prefix 매칭)
    명시적으로 hs_code 또는 component_code 가 주어지면 그 기준으로,
    아니면 supplier_id 의 components 전체에서 자동 추출.
    """
    conn = _connect()

    base = conn.execute(
        "SELECT * FROM suppliers WHERE supplier_id = ?", (supplier_id,)
    ).fetchone()
    if base is None:
        conn.close()
        return []
    base_country = base["country"]

    # 후보 부품 — supplier_id 의 components 또는 명시 인자 사용
    if hs_code or component_code:
        target_hs = [hs_code] if hs_code else []
        target_codes = [component_code] if component_code else []
    else:
        rows = conn.execute(
            "SELECT DISTINCT hs_code, component_code FROM supplier_components WHERE supplier_id = ?",
            (supplier_id,),
        ).fetchall()
        target_hs = [r["hs_code"] for r in rows if r["hs_code"]]
        target_codes = [r["component_code"] for r in rows if r["component_code"]]

    if not target_hs and not target_codes:
        conn.close()
        return []

    # 후보 supplier 추출 — 같은 component_code 우선
    candidate_ids: set[str] = set()
    for code in target_codes:
        rows = conn.execute(
            "SELECT DISTINCT supplier_id FROM supplier_components WHERE component_code = ? AND supplier_id != ?",
            (code, supplier_id),
        ).fetchall()
        for r in rows:
            candidate_ids.add(r["supplier_id"])
    for hs in target_hs:
        rows = conn.execute(
            "SELECT DISTINCT supplier_id FROM supplier_components WHERE hs_code LIKE ? AND supplier_id != ?",
            (f"{hs[:4]}%", supplier_id),  # HS 4-digit prefix
        ).fetchall()
        for r in rows:
            candidate_ids.add(r["supplier_id"])

    # 다차원 점수 산출
    scored: list[dict[str, Any]] = []
    for cid in candidate_ids:
        c = conn.execute(
            "SELECT * FROM suppliers WHERE supplier_id = ?", (cid,)
        ).fetchone()
        if c is None:
            continue
        comp = conn.execute(
            """SELECT AVG(unit_price_krw) as avg_price, MIN(unit_price_krw) as min_price
               FROM supplier_components
               WHERE supplier_id = ? AND (component_code IN (
                 SELECT component_code FROM supplier_components WHERE supplier_id = ?
               ) OR hs_code LIKE ?)""",
            (cid, supplier_id, f"{(target_hs[0] if target_hs else '')[:4]}%"),
        ).fetchone()

        # compliance_score 0~100 → 40점
        cscore = (c["compliance_score"] or 0) / 100.0 * 40

        # 거래량 — 1억(100백만) 이상이면 만점, 그 이하 비례 → 20점
        vscore = min(20.0, (c["annual_volume_krw_mn"] or 0) / 100.0 * 20)

        # 단가 — 후보 평균가 < 요청 협력사 평균가 면 가산. 단순 비교
        base_price_row = conn.execute(
            """SELECT AVG(unit_price_krw) as avg FROM supplier_components
               WHERE supplier_id = ?""",
            (supplier_id,),
        ).fetchone()
        base_avg = float(base_price_row["avg"] or 0)
        cand_avg = float(comp["avg_price"] or 0) if comp else 0.0
        if base_avg > 0 and cand_avg > 0:
            ratio = cand_avg / base_avg
            # ratio < 1 (싸면) → 30점, ratio > 1.5 (50%↑ 비싸면) → 0
            pscore = max(0.0, min(30.0, 30.0 * (1.5 - ratio)))
        else:
            pscore = 15.0  # 정보 부족 시 중간값

        # 국가 다변화 — 다른 국가면 +10
        dscore = 10.0 if c["country"] != base_country else 0.0

        total = cscore + vscore + pscore + dscore
        scored.append({
            "supplier_id": cid,
            "name": c["name"],
            "tier": c["tier"],
            "country": c["country"],
            "compliance_score": c["compliance_score"],
            "annual_volume_krw_mn": c["annual_volume_krw_mn"],
            "avg_unit_price_krw": int(cand_avg),
            "score_total": round(total, 1),
            "score_breakdown": {
                "compliance": round(cscore, 1),
                "volume": round(vscore, 1),
                "price": round(pscore, 1),
                "diversification": round(dscore, 1),
            },
        })

    conn.close()
    scored.sort(key=lambda x: -x["score_total"])
    return scored[:top_k]
