"""P5 §10 — 2차 협력사 자동 발굴 (DART 공시 데이터 기반).

전략: 외부 데이터 ML 분석 없이 가벼운 휴리스틱 — DART industry_filings 에 적재된
동종업계 corp_name 들 ⊖ 우리 suppliers DB → 미등록 후보 list.

사용자가 admin UI 에서 "supplier 로 promote" 클릭 → suppliers DB 에 자동 import
(default tier=2, country='KR'). 자동 발굴이라기보단 **제안 큐** — 가짜 supplier 가
무단 등록되지 않도록 사용자 확인 단계 보장.

자격증명: DART_API_KEY (P3 D11 와 동일, 이미 .env 설정).
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def discover_candidates(
    *,
    limit: int = 50,
    min_filings: int = 1,
) -> list[dict[str, Any]]:
    """우리 suppliers DB 에 미등록인 DART 공시 회사들을 후보로 반환.

    Args:
      limit: 최대 후보 수
      min_filings: 최소 공시 건수 (잡음 노이즈 회사 필터)

    Returns:
      [{corp_code, corp_name, filing_count, latest_rcept_dt, suggested_tier}]
      filing_count 내림차순 정렬 (활동 많은 회사 우선).
    """
    # 1) DART industry_filings 의 corp_code/corp_name 집계
    try:
        from features.compliance.supply.industry_trend import init_industry_db, DB_PATH as IND_DB
    except ImportError:
        return []
    try:
        init_industry_db()
    except Exception as e:
        logger.warning("industry_db init 실패: %s", e)
        return []

    ind_conn = sqlite3.connect(str(IND_DB))
    ind_conn.row_factory = sqlite3.Row
    rows = ind_conn.execute(
        """SELECT corp_code, corp_name, COUNT(*) AS filing_count,
                  MAX(rcept_dt) AS latest_rcept_dt
           FROM industry_filings
           GROUP BY corp_code, corp_name
           HAVING filing_count >= ?
           ORDER BY filing_count DESC, latest_rcept_dt DESC""",
        (max(1, int(min_filings)),),
    ).fetchall()
    ind_conn.close()
    if not rows:
        return []

    # 2) 우리 suppliers DB 의 등록된 corp_code 집합 (또는 corp_name)
    from features.compliance.supply.supplier_compliance import init_suppliers_db, DB_PATH as SUP_DB
    init_suppliers_db()
    sup_conn = sqlite3.connect(str(SUP_DB))
    sup_conn.row_factory = sqlite3.Row
    # supplier_id 가 corp_code 와 일치하는지 OR name 부분일치
    existing_ids = {r["supplier_id"] for r in
                    sup_conn.execute("SELECT supplier_id FROM suppliers").fetchall()}
    existing_names = {r["name"].strip().lower() for r in
                      sup_conn.execute("SELECT name FROM suppliers").fetchall()
                      if r["name"]}
    sup_conn.close()

    # 3) 차집합 — 미등록만
    candidates: list[dict[str, Any]] = []
    for r in rows:
        cc = r["corp_code"]
        nm = r["corp_name"]
        if cc in existing_ids:
            continue
        if (nm or "").strip().lower() in existing_names:
            continue
        candidates.append({
            "corp_code": cc,
            "corp_name": nm,
            "filing_count": int(r["filing_count"] or 0),
            "latest_rcept_dt": r["latest_rcept_dt"] or "",
            "suggested_tier": 2,  # 동종업계 공시 = 2차 협력사 후보 default
        })
        if len(candidates) >= limit:
            break
    return candidates


def promote_to_supplier(
    corp_code: str,
    *,
    name_override: str | None = None,
    tier: int = 2,
    relation_type: str = "sub_assembly",
    parent_supplier_id: str = "",
) -> dict[str, Any]:
    """DART 공시 회사를 suppliers 에 자동 import.

    supplier_id = corp_code, name = corp_name (또는 override), tier_depth = tier.
    이미 등록돼 있으면 skip. 사용자 confirm 후 admin endpoint 가 호출.
    """
    if not corp_code or not corp_code.strip():
        return {"ok": False, "error": "missing_corp_code"}
    cc = corp_code.strip()

    # industry_filings 에서 corp_name 조회
    try:
        from features.compliance.supply.industry_trend import (
            init_industry_db, DB_PATH as IND_DB,
        )
        init_industry_db()
        ind_conn = sqlite3.connect(str(IND_DB))
        ind_conn.row_factory = sqlite3.Row
        row = ind_conn.execute(
            "SELECT corp_name FROM industry_filings WHERE corp_code = ? LIMIT 1",
            (cc,),
        ).fetchone()
        ind_conn.close()
    except Exception as e:
        logger.warning("industry_filings 조회 실패: %s", e)
        row = None

    name = (
        name_override
        or (row["corp_name"] if row else "")
        or f"DART_{cc}"
    ).strip()

    from features.compliance.supply.supplier_compliance import init_suppliers_db, DB_PATH as SUP_DB
    init_suppliers_db()
    sup_conn = sqlite3.connect(str(SUP_DB))
    existing = sup_conn.execute(
        "SELECT supplier_id FROM suppliers WHERE supplier_id = ?", (cc,),
    ).fetchone()
    if existing is not None:
        sup_conn.close()
        return {"ok": False, "error": "already_exists", "supplier_id": cc}

    sup_conn.execute(
        """INSERT INTO suppliers
           (supplier_id, name, tier, country, parent_supplier_id, tier_depth,
            relation_type)
           VALUES (?,?,?,?,?,?,?)""",
        (
            cc,
            name[:200],
            int(tier),
            "KR",  # DART 는 한국 회사 한정
            parent_supplier_id or "",
            int(tier),
            relation_type,
        ),
    )
    sup_conn.commit()
    sup_conn.close()
    return {
        "ok": True,
        "supplier_id": cc,
        "name": name,
        "tier_depth": int(tier),
        "imported_at": datetime.now().isoformat(),
    }
