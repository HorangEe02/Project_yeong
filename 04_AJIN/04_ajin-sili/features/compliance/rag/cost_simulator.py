"""P2 D6 — 원가 영향 시뮬레이션.

변경 (관세 / 화학물질 사용 제한 등) → 협력사 단가 시나리오 시뮬레이션.

지원 시뮬레이션:
  1. simulate_tariff_impact — 관세 변동 시 baseline vs new cost
  2. simulate_chemical_substitution — 화학물질 대체 시 단가 % 증가 (룰 기반)
"""
from __future__ import annotations

import logging
import re
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


def _connect():
    from features.compliance.supply.supplier_compliance import init_suppliers_db, DB_PATH
    init_suppliers_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _extract_hs_codes(text: str) -> list[str]:
    return re.findall(r"\b\d{4}(?:\.\d{2}(?:\.\d{2,3})?)?\b", text or "")


# ─────────────────────────────────────────────────────────────
# 관세 시뮬레이션
# ─────────────────────────────────────────────────────────────


def simulate_tariff_impact(change: dict[str, Any], scenario_rate_pct: float) -> dict[str, Any]:
    """관세 변동 시 baseline vs new annual cost 시뮬레이션.

    Args:
        change: ChangeRecord (item_title / new_value 에서 HS 추출)
        scenario_rate_pct: 추가 적용 관세율 (예: 25.0 = 25%)

    Returns:
        {
            "baseline_cost_krw_mn": int,   # 현재 (관세 0% 가정) 연간 원가
            "new_cost_krw_mn": int,        # scenario_rate_pct 적용 후
            "delta_krw_mn": int,           # 증가분
            "delta_pct": float,            # 증가율
            "by_supplier": [...],          # 협력사별 breakdown
            "applicable_hs": list[str],    # 매칭 HS
        }
    """
    body = " ".join([
        str(change.get("item_title") or ""),
        str(change.get("summary_ko") or ""),
        str(change.get("new_value") or "")[:1000],
    ])
    hs_codes = _extract_hs_codes(body)
    if not hs_codes:
        return {
            "baseline_cost_krw_mn": 0,
            "new_cost_krw_mn": 0,
            "delta_krw_mn": 0,
            "delta_pct": 0.0,
            "by_supplier": [],
            "applicable_hs": [],
        }

    conn = _connect()
    rate = max(0.0, float(scenario_rate_pct)) / 100.0

    # HS 매칭 + supplier join
    by_supplier: dict[str, dict[str, Any]] = {}
    for hs in hs_codes:
        rows = conn.execute(
            """SELECT sc.supplier_id, sc.component_code, sc.hs_code,
                      sc.unit_price_krw, sc.qty_per_year,
                      s.name, s.country
               FROM supplier_components sc
               JOIN suppliers s ON sc.supplier_id = s.supplier_id
               WHERE sc.hs_code LIKE ?""",
            (f"{hs}%",),
        ).fetchall()
        for r in rows:
            sid = r["supplier_id"]
            annual_baseline_krw = int(r["unit_price_krw"] or 0) * int(r["qty_per_year"] or 0)
            tariff_addition_krw = int(annual_baseline_krw * rate)
            entry = by_supplier.setdefault(
                sid,
                {
                    "supplier_id": sid,
                    "name": r["name"],
                    "country": r["country"],
                    "components": [],
                    "baseline_krw_mn": 0,
                    "additional_tariff_krw_mn": 0,
                },
            )
            entry["components"].append({
                "component_code": r["component_code"],
                "hs_code": r["hs_code"],
                "annual_baseline_krw": annual_baseline_krw,
                "tariff_addition_krw": tariff_addition_krw,
            })
            entry["baseline_krw_mn"] += annual_baseline_krw // 1_000_000
            entry["additional_tariff_krw_mn"] += tariff_addition_krw // 1_000_000

    conn.close()

    baseline = sum(s["baseline_krw_mn"] for s in by_supplier.values())
    additional = sum(s["additional_tariff_krw_mn"] for s in by_supplier.values())
    delta_pct = (additional / baseline * 100.0) if baseline > 0 else 0.0

    return {
        "baseline_cost_krw_mn": baseline,
        "new_cost_krw_mn": baseline + additional,
        "delta_krw_mn": additional,
        "delta_pct": round(delta_pct, 2),
        "by_supplier": sorted(
            by_supplier.values(),
            key=lambda x: -x["additional_tariff_krw_mn"],
        ),
        "applicable_hs": list(set(hs_codes)),
        "scenario_rate_pct": scenario_rate_pct,
    }


# ─────────────────────────────────────────────────────────────
# 화학물질 대체 시뮬레이션 (룰베이스 추정)
# ─────────────────────────────────────────────────────────────

# 알려진 화학물질 → 대체재 단가 영향률 (% 증가, 산업 평균 추정)
_SUBSTITUTION_DELTA_PCT = {
    "6가 크롬": 30.0,        # 3가 크롬으로 대체 시 약 30% 단가 상승
    "크로메이트": 30.0,
    "납": 15.0,              # 무납 대체 (유리 / 솔더)
    "PFOS": 25.0,
    "PFOA": 25.0,
    "프탈레이트": 10.0,
    "DEHP": 10.0,
    "수은": 50.0,
    "카드뮴": 35.0,
}


def simulate_chemical_substitution(change: dict[str, Any]) -> dict[str, Any]:
    """변경 본문에서 제한 화학물질 키워드 → 대체재 단가 영향 추정.

    Returns:
        {
            "substances_detected": list[str],
            "estimated_delta_pct": float,   # 가중 평균
            "by_substance": [{name, delta_pct}],
            "note": "룰베이스 추정치 — 정확한 견적은 협력사 자가진단 필요",
        }
    """
    body = " ".join([
        str(change.get("item_title") or ""),
        str(change.get("summary_ko") or ""),
        str(change.get("new_value") or "")[:1500],
    ])

    detected: list[str] = []
    by_substance: list[dict[str, Any]] = []
    for sub, delta in _SUBSTITUTION_DELTA_PCT.items():
        if sub in body:
            detected.append(sub)
            by_substance.append({"name": sub, "delta_pct": delta})

    avg_delta = (
        sum(b["delta_pct"] for b in by_substance) / len(by_substance)
        if by_substance else 0.0
    )

    return {
        "substances_detected": detected,
        "estimated_delta_pct": round(avg_delta, 1),
        "by_substance": by_substance,
        "note": "룰베이스 추정치 — 정확한 견적은 협력사 자가진단 필요",
    }
