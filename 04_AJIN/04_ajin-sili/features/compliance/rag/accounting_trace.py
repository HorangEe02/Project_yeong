"""P4 D17 — 시뮬 결과 → P&L line item 매핑.

What-if 시뮬레이션의 delta(매출/원가/영업이익/by_dimension) 를 회계 라인 아이템에
매핑해 재무팀이 분개 단위 검토 가능하게 한다. 매핑은 line item 만 — 분개 자동
생성은 하지 않음 (재무팀 검토 필수).
"""
from __future__ import annotations

from typing import Any


SCENARIO_LINE_MAP: dict[str, list[dict[str, str]]] = {
    "tariff": [
        {"line": "매출원가", "type": "increase", "explain": "관세율 인상 → 수입원가 증가"},
        {"line": "매출총이익", "type": "decrease", "explain": "원가 증가의 직접 영향"},
    ],
    "fx": [
        {"line": "매출원가", "type": "variable", "explain": "수입원가 환율 변동"},
        {"line": "외환차손익", "type": "variable",
         "explain": "환율 변동에 따른 평가손익"},
    ],
    "chemical": [
        {"line": "매출원가", "type": "increase",
         "explain": "대체 화학물질 원가 인상"},
        {"line": "연구개발비", "type": "increase",
         "explain": "대체재 검증·인증 비용"},
    ],
    "labor": [
        {"line": "급여 (제조)", "type": "increase",
         "explain": "최저시급 인상의 인건비 영향"},
        {"line": "급여 (판관비)", "type": "increase",
         "explain": "사무직 영향분"},
    ],
    "carbon": [
        {"line": "세금과공과", "type": "increase",
         "explain": "탄소세 부과 — Scope 1/2/3 합산 × 세율"},
        {"line": "영업이익", "type": "decrease", "explain": "세금 증가의 직접 영향"},
    ],
}


def map_to_pnl(whatif_result: dict[str, Any]) -> list[dict[str, Any]]:
    """시뮬 결과 → P&L line item 영향 list.

    Args:
      whatif_result: whatif_engine.simulate() 결과 dict
    Returns:
      [{line, delta_krw_mn, direction, explain, scenario_type, confidence}]
    """
    scenario = str(whatif_result.get("scenario_type") or "").strip()
    delta = whatif_result.get("delta") or {}
    meta = whatif_result.get("meta") or {}
    confidence = float(meta.get("confidence") or 0)

    lines = SCENARIO_LINE_MAP.get(scenario, [])
    out: list[dict[str, Any]] = []
    for line in lines:
        # delta 매핑: line 명에 따라 어떤 delta 필드 사용할지 결정
        if line["line"] == "매출원가":
            amt = int(delta.get("cogs_krw_mn") or 0)
        elif line["line"] in ("매출총이익", "영업이익"):
            amt = int(delta.get("operating_profit_krw_mn") or 0)
        elif line["line"] == "외환차손익":
            amt = int(delta.get("operating_profit_krw_mn") or 0)
        elif line["line"].startswith("급여"):
            amt = int(delta.get("cogs_krw_mn") or 0)
        elif line["line"] == "세금과공과":
            amt = int(delta.get("cogs_krw_mn") or 0)
        elif line["line"] == "연구개발비":
            amt = int(delta.get("cogs_krw_mn") or 0) // 10  # 추정 — 보수적
        else:
            amt = 0

        direction = "increase" if amt > 0 else ("decrease" if amt < 0 else "neutral")
        out.append({
            "line": line["line"],
            "delta_krw_mn": amt,
            "direction": direction,
            "explain": line["explain"],
            "scenario_type": scenario,
            "confidence": confidence,
        })
    return out
