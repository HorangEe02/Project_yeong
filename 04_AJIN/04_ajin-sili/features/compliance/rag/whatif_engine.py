"""P3 D10 — What-if 시뮬레이션 엔진.

임원·현직자 자연어 질문 → 5 default scenarios 시뮬레이션.

지원 시나리오:
  1. tariff      — 관세율 % 입력 (P2 D6 cost_simulator 재사용)
  2. fx          — KRW/USD 변동률 (수출입 가격 영향)
  3. chemical    — 화학물질 사용 제한 (P2 D6 chemical_substitution)
  4. labor       — 최저시급 인상률 (인건비 영향)
  5. carbon      — 탄소세 톤당 KRW (배출량 추정 × 세율)

자연어 라우팅 — Gemini/Ollama 로 scenario_type + params 추출.
LLM 미가용 시 정규식 fallback.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import sys
from typing import Any

import httpx

logger = logging.getLogger(__name__)

VALID_SCENARIOS = {"tariff", "fx", "chemical", "labor", "carbon", "natural_language"}


# ─────────────────────────────────────────────────────────────
# P4 D17 — financial baseline 어댑터
# ─────────────────────────────────────────────────────────────


def _get_baseline():
    """financial_baseline.get_baseline() — 단일 진입점.

    실패 / 미구성 시 hardcoded fallback (confidence=0.30) 보장.
    """
    try:
        from features.compliance.rag.financial_baseline import get_baseline
        return get_baseline()
    except Exception as e:
        logger.warning("financial_baseline.get_baseline() 예외 — hardcoded 사용: %s", e)
        from features.compliance.rag.financial_baseline import HARDCODED, Baseline
        return Baseline(**HARDCODED.to_dict())


def _baseline_meta(baseline) -> dict[str, Any]:
    return {
        "data_source": baseline.data_source,
        "confidence": baseline.confidence,
        "as_of": baseline.as_of,
        "corp_code": baseline.corp_code,
    }


# P4.1 §3 — falsy fallback 제거: 0/음수/None 만 hardcoded 로 교체, 양수는 실값 사용.
HARDCODED_REV = 100_000
HARDCODED_COGS = 70_000
HARDCODED_COGS_CHEMICAL = 50_000


def _safe_baseline_value(value: Any, default: int) -> int:
    """baseline 값이 양수일 때만 실값 사용. 0/음수/None 은 hardcoded default.

    `value or default` 패턴은 0이 진짜 값일 때 silent 으로 default 로 떨어지는 문제가
    있어 명시적 비교로 교체.
    """
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return v if v > 0 else default


# ─────────────────────────────────────────────────────────────
# 시나리오별 시뮬레이션
# ─────────────────────────────────────────────────────────────


def simulate(scenario_type: str, params: dict[str, Any],
              change_id: int | None = None) -> dict[str, Any]:
    """단일 시뮬레이션 실행. scenario_type 별 분기.

    Returns:
        {
          "scenario_type": str,
          "params": dict,
          "baseline_kpi": dict,        # 매출/원가/영업이익/위험도 (현재)
          "new_kpi": dict,             # scenario 적용 후
          "delta": dict,               # 차이
          "delta_pct": dict,           # 변화율
          "by_dimension": list[dict],  # 차원별 breakdown
          "note": str,                 # 안내·주의 문구
        }
    """
    if scenario_type == "natural_language":
        return _route_natural_language(params)
    if scenario_type not in VALID_SCENARIOS or scenario_type == "natural_language":
        return _safe_response(
            scenario_type=scenario_type,
            params=params,
            note=f"지원되지 않는 시나리오: {scenario_type}",
        )

    handlers = {
        "tariff": _simulate_tariff,
        "fx": _simulate_fx,
        "chemical": _simulate_chemical,
        "labor": _simulate_labor,
        "carbon": _simulate_carbon,
    }
    return handlers[scenario_type](params, change_id)


def _safe_response(scenario_type: str, params: dict, note: str = "") -> dict:
    """baseline 데이터 부재 또는 시뮬 실패 시 0 반환 — 가짜 숫자 X."""
    return {
        "scenario_type": scenario_type,
        "params": params,
        "baseline_kpi": {"revenue_krw_mn": 0, "cogs_krw_mn": 0, "operating_profit_krw_mn": 0, "risk_score": 0},
        "new_kpi": {"revenue_krw_mn": 0, "cogs_krw_mn": 0, "operating_profit_krw_mn": 0, "risk_score": 0},
        "delta": {"revenue_krw_mn": 0, "cogs_krw_mn": 0, "operating_profit_krw_mn": 0, "risk_score": 0},
        "delta_pct": {},
        "by_dimension": [],
        "note": note or "추정치 — 실제 회계 영향은 재무팀 검토 후 확정",
        "meta": {"data_source": "none", "confidence": 0.0, "as_of": "", "corp_code": ""},
    }


# ─────────────────────────────────────────────────────────────
# 1. 관세 (P2 D6 재사용)
# ─────────────────────────────────────────────────────────────


def _simulate_tariff(params: dict[str, Any], change_id: int | None) -> dict:
    rate_pct = float(params.get("rate_pct", 25.0))
    hs_codes = params.get("hs_codes")  # 선택적 HS 코드 list
    from features.compliance.rag.cost_simulator import simulate_tariff_impact

    # change_id 가 있으면 그 변경 본문 활용, 없으면 임의 HS 만 시뮬
    if change_id:
        from features.compliance.alerts.change_detector import init_change_db, CHANGE_DB_PATH
        init_change_db()
        conn = sqlite3.connect(CHANGE_DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT item_title, summary_ko, new_value FROM regulation_changes WHERE id = ?",
            (change_id,),
        ).fetchone()
        conn.close()
        if row:
            change_dict = dict(row)
        else:
            change_dict = {"item_title": "user query", "new_value": " ".join(hs_codes or [])}
    else:
        change_dict = {
            "item_title": "user query",
            "new_value": " ".join(hs_codes or ["8708"]),
        }

    result = simulate_tariff_impact(change_dict, scenario_rate_pct=rate_pct)

    baseline_cogs = result["baseline_cost_krw_mn"]
    new_cogs = result["new_cost_krw_mn"]
    delta_cogs = result["delta_krw_mn"]

    # 매출은 가정: baseline 수입원가의 약 1.4배 (조립 후 판매 가정 — 산업 평균)
    baseline_rev = int(baseline_cogs * 1.4)
    new_rev = baseline_rev  # 가격 전가 안 한다고 가정
    op_profit_delta = -delta_cogs

    return {
        "scenario_type": "tariff",
        "params": {"rate_pct": rate_pct, "hs_codes": hs_codes or result["applicable_hs"]},
        "baseline_kpi": {
            "revenue_krw_mn": baseline_rev,
            "cogs_krw_mn": baseline_cogs,
            "operating_profit_krw_mn": baseline_rev - baseline_cogs,
            "risk_score": min(100, int(rate_pct * 1.5)),
        },
        "new_kpi": {
            "revenue_krw_mn": new_rev,
            "cogs_krw_mn": new_cogs,
            "operating_profit_krw_mn": new_rev - new_cogs,
            "risk_score": min(100, int(rate_pct * 2.5)),
        },
        "delta": {
            "revenue_krw_mn": 0,
            "cogs_krw_mn": delta_cogs,
            "operating_profit_krw_mn": op_profit_delta,
            "risk_score": min(100, int(rate_pct)),
        },
        "delta_pct": {"cogs": result["delta_pct"]},
        "by_dimension": result["by_supplier"][:5],
        "note": (
            "추정치 — 매출은 가격 전가 X 가정. 실제 영향은 재무팀 검토 후 확정. "
            "(영향 협력사 P2 D6 cost_simulator 재사용)"
        ),
        "meta": _baseline_meta(_get_baseline()),
    }


# ─────────────────────────────────────────────────────────────
# 2. 환율 (KRW/USD 변동)
# ─────────────────────────────────────────────────────────────


def _simulate_fx(params: dict[str, Any], change_id: int | None) -> dict:
    delta_pct = float(params.get("krw_usd_change_pct", -10.0))  # 음수 = 원화 강세

    # P4 D17 — financial_baseline 우선, P4.1 §3 — falsy 대신 명시 비교
    baseline = _get_baseline()
    baseline_rev = _safe_baseline_value(baseline.revenue_krw_mn, HARDCODED_REV)
    baseline_cogs = _safe_baseline_value(baseline.cogs_krw_mn, HARDCODED_COGS)

    # 가정 — 자동차 부품 산업 평균: 매출의 30% 가 수출 (USD), 원가의 50% 가 수입 (USD)
    export_share = 0.30
    import_share = 0.50

    rev_delta_pct = export_share * delta_pct  # 원화 강세 → 수출 매출 감소
    cogs_delta_pct = import_share * delta_pct  # 원화 강세 → 수입 원가 감소

    new_rev = int(baseline_rev * (1 + rev_delta_pct / 100))
    new_cogs = int(baseline_cogs * (1 + cogs_delta_pct / 100))

    return {
        "scenario_type": "fx",
        "params": {"krw_usd_change_pct": delta_pct},
        "baseline_kpi": {
            "revenue_krw_mn": baseline_rev,
            "cogs_krw_mn": baseline_cogs,
            "operating_profit_krw_mn": baseline_rev - baseline_cogs,
            "risk_score": min(100, abs(int(delta_pct * 2))),
        },
        "new_kpi": {
            "revenue_krw_mn": new_rev,
            "cogs_krw_mn": new_cogs,
            "operating_profit_krw_mn": new_rev - new_cogs,
            "risk_score": min(100, abs(int(delta_pct * 2.5))),
        },
        "delta": {
            "revenue_krw_mn": new_rev - baseline_rev,
            "cogs_krw_mn": new_cogs - baseline_cogs,
            "operating_profit_krw_mn": (new_rev - new_cogs) - (baseline_rev - baseline_cogs),
            "risk_score": min(100, abs(int(delta_pct * 0.5))),
        },
        "delta_pct": {"revenue": rev_delta_pct, "cogs": cogs_delta_pct},
        "by_dimension": [
            {"name": "수출 (USD)", "share": export_share, "delta_pct": rev_delta_pct},
            {"name": "수입 (USD)", "share": import_share, "delta_pct": cogs_delta_pct},
        ],
        "note": (
            "추정치 — 산업 평균 가정 (수출 30% / 수입 50%). "
            "정확한 영향은 재무팀의 환헤지 정책 + 부서별 매출원가 분석 필요."
        ),
        "meta": _baseline_meta(baseline),
    }


# ─────────────────────────────────────────────────────────────
# 3. 화학물질 (P2 D6 재사용)
# ─────────────────────────────────────────────────────────────


def _simulate_chemical(params: dict[str, Any], change_id: int | None) -> dict:
    substance = str(params.get("substance", "")).strip()
    if not substance:
        return _safe_response("chemical", params,
                              "substance 파라미터 필요 (예: '6가 크롬', '납')")

    from features.compliance.rag.cost_simulator import simulate_chemical_substitution
    body_change = {"item_title": substance, "new_value": f"{substance} 사용 제한"}
    result = simulate_chemical_substitution(body_change)
    delta_pct = result["estimated_delta_pct"]

    # P4 D17 — financial_baseline 우선 (화학물질 영향분 — 매출원가의 일부 가정)
    # P4.1 §3 — falsy 대신 명시 비교
    baseline = _get_baseline()
    baseline_cogs = _safe_baseline_value(baseline.cogs_krw_mn, HARDCODED_COGS_CHEMICAL)
    new_cogs = int(baseline_cogs * (1 + delta_pct / 100))

    return {
        "scenario_type": "chemical",
        "params": {"substance": substance},
        "baseline_kpi": {
            "revenue_krw_mn": int(baseline_cogs * 1.4),
            "cogs_krw_mn": baseline_cogs,
            "operating_profit_krw_mn": int(baseline_cogs * 0.4),
            "risk_score": min(100, int(delta_pct * 1.5)),
        },
        "new_kpi": {
            "revenue_krw_mn": int(baseline_cogs * 1.4),
            "cogs_krw_mn": new_cogs,
            "operating_profit_krw_mn": int(baseline_cogs * 1.4 - new_cogs),
            "risk_score": min(100, int(delta_pct * 2)),
        },
        "delta": {
            "revenue_krw_mn": 0,
            "cogs_krw_mn": new_cogs - baseline_cogs,
            "operating_profit_krw_mn": -(new_cogs - baseline_cogs),
            "risk_score": min(100, int(delta_pct)),
        },
        "delta_pct": {"cogs": delta_pct},
        "by_dimension": result["by_substance"],
        "note": result.get("note", ""),
        "meta": _baseline_meta(baseline),
    }


# ─────────────────────────────────────────────────────────────
# 4. 노동 비용 (최저시급 변동)
# ─────────────────────────────────────────────────────────────


def _simulate_labor(params: dict[str, Any], change_id: int | None) -> dict:
    increase_pct = float(params.get("min_wage_increase_pct", 5.0))
    # P4 D17 — financial_baseline 우선; P4.1 §3 — falsy 대신 명시 비교
    baseline = _get_baseline()
    labor_share = baseline.labor_share if (baseline.labor_share and baseline.labor_share > 0) else 0.25
    baseline_cogs = _safe_baseline_value(baseline.cogs_krw_mn, HARDCODED_COGS)

    labor_baseline = int(baseline_cogs * labor_share)
    labor_new = int(labor_baseline * (1 + increase_pct / 100))
    cogs_delta = labor_new - labor_baseline
    new_cogs = baseline_cogs + cogs_delta

    return {
        "scenario_type": "labor",
        "params": {"min_wage_increase_pct": increase_pct},
        "baseline_kpi": {
            "revenue_krw_mn": int(baseline_cogs * 1.4),
            "cogs_krw_mn": baseline_cogs,
            "operating_profit_krw_mn": int(baseline_cogs * 0.4),
            "risk_score": min(100, int(increase_pct * 4)),
        },
        "new_kpi": {
            "revenue_krw_mn": int(baseline_cogs * 1.4),
            "cogs_krw_mn": new_cogs,
            "operating_profit_krw_mn": int(baseline_cogs * 1.4 - new_cogs),
            "risk_score": min(100, int(increase_pct * 5)),
        },
        "delta": {
            "revenue_krw_mn": 0,
            "cogs_krw_mn": cogs_delta,
            "operating_profit_krw_mn": -cogs_delta,
            "risk_score": min(100, int(increase_pct)),
        },
        "delta_pct": {"labor_cost": increase_pct},
        "by_dimension": [
            {"name": "인건비", "baseline_krw_mn": labor_baseline, "new_krw_mn": labor_new},
        ],
        "note": (
            f"추정치 — labor_share {labor_share:.2f} 가정. "
            "공장별 자동화 비율에 따라 실제 영향 다름."
        ),
        "meta": _baseline_meta(baseline),
    }


# ─────────────────────────────────────────────────────────────
# 5. 탄소세
# ─────────────────────────────────────────────────────────────


def _simulate_carbon(params: dict[str, Any], change_id: int | None) -> dict:
    krw_per_ton = float(params.get("krw_per_ton", 30000.0))  # 기본: 톤당 30,000원

    # P4 D17 — financial_baseline + Scope 1/2/3 분리; P4.1 §3 — falsy 대신 명시 비교
    baseline = _get_baseline()
    baseline_cogs = _safe_baseline_value(baseline.cogs_krw_mn, HARDCODED_COGS)

    # scope 선택: P4 신규. None / [] 일 때 [1,2] default (Scope 3 미수집 보호)
    scope_raw = params.get("scope")
    scopes: list[int] | None = (
        [int(s) for s in scope_raw if int(s) in (1, 2, 3)]
        if isinstance(scope_raw, list) else None
    )

    # annual_tons 우선순위:
    #   1) params 로 명시 받은 값 (P3 호환 — 기존 테스트 유지)
    #   2) scope 선택이 있으면 baseline.emissions 합산
    #   3) baseline emissions Scope 1+2 default
    #   4) 50_000 (legacy)
    if "annual_tons" in params and params["annual_tons"] is not None:
        annual_tons = float(params["annual_tons"])
        scopes_used: list[int] = scopes or []
    else:
        from features.compliance.rag.financial_baseline import total_emissions_tons
        annual_tons = float(total_emissions_tons(baseline, scopes))
        scopes_used = scopes or [1, 2]
        if annual_tons == 0:
            annual_tons = 50_000.0

    tax_new = int(annual_tons * krw_per_ton / 1_000_000)  # 백만원
    new_cogs = baseline_cogs + tax_new

    by_scope: list[dict[str, Any]] = []
    for s in (scopes_used or [1, 2]):
        key = f"scope_{s}"
        emission = baseline.emissions.get(key) if baseline.emissions else None
        if emission is None:
            by_scope.append({"name": f"Scope {s}", "tons": 0, "missing": True})
        else:
            by_scope.append({"name": f"Scope {s}", "tons": int(emission), "missing": False})

    note_parts = [
        f"추정치 — 연간 배출량 {int(annual_tons):,}톤 가정.",
    ]
    if scopes is not None:
        note_parts.append(f"Scope {scopes_used} 합산.")
    if baseline.emissions and baseline.emissions.get("scope_3") is None:
        note_parts.append("Scope 3 미수집.")

    return {
        "scenario_type": "carbon",
        "params": {
            "krw_per_ton": krw_per_ton,
            "annual_tons": annual_tons,
            "scope": scopes_used,
        },
        "baseline_kpi": {
            "revenue_krw_mn": int(baseline_cogs * 1.4),
            "cogs_krw_mn": baseline_cogs,
            "operating_profit_krw_mn": int(baseline_cogs * 0.4),
            "risk_score": 30,
        },
        "new_kpi": {
            "revenue_krw_mn": int(baseline_cogs * 1.4),
            "cogs_krw_mn": new_cogs,
            "operating_profit_krw_mn": int(baseline_cogs * 1.4 - new_cogs),
            "risk_score": min(100, 30 + int(tax_new / baseline_cogs * 100)),
        },
        "delta": {
            "revenue_krw_mn": 0,
            "cogs_krw_mn": tax_new,
            "operating_profit_krw_mn": -tax_new,
            "risk_score": min(100, int(tax_new / baseline_cogs * 100)),
        },
        "delta_pct": {"cogs": (tax_new / max(baseline_cogs, 1)) * 100},
        "by_dimension": [
            {"name": "탄소세", "annual_tons": annual_tons,
             "krw_per_ton": krw_per_ton, "tax_krw_mn": tax_new},
            *by_scope,
        ],
        "note": " ".join(note_parts),
        "meta": _baseline_meta(baseline),
    }


# ─────────────────────────────────────────────────────────────
# 자연어 라우팅 (Ollama LLM, 정규식 fallback)
# ─────────────────────────────────────────────────────────────


def _route_natural_language(params: dict[str, Any]) -> dict:
    query = (params.get("query") or "").strip()
    if not query:
        return _safe_response("natural_language", params, "query 파라미터 필요")

    # 1) 정규식 fallback — LLM 무관 결정론적
    extracted = _regex_extract(query)
    if extracted:
        return simulate(extracted["scenario_type"], extracted["params"])

    # 2) LLM 추출 (Ollama 사용 — 미가용 시 안전 응답)
    llm_extracted = _llm_extract(query)
    if llm_extracted and llm_extracted.get("scenario_type") in VALID_SCENARIOS:
        return simulate(llm_extracted["scenario_type"], llm_extracted.get("params", {}))

    return _safe_response(
        "natural_language",
        params,
        f"'{query}' 자연어 추출 실패 — 5 시나리오 중 직접 선택해 주세요 (tariff/fx/chemical/labor/carbon)",
    )


def _regex_extract(query: str) -> dict | None:
    """정규식 fallback — 간단한 패턴 매칭."""
    # tariff: "관세 25%" / "tariff 25%"
    m = re.search(r"(?:관세|tariff)\s*(\d+(?:\.\d+)?)\s*%?", query, re.IGNORECASE)
    if m:
        return {"scenario_type": "tariff", "params": {"rate_pct": float(m.group(1))}}

    # fx: "환율 -10%", "원화 강세 5%"
    m = re.search(r"(?:환율|krw|원화)\s*(-?\d+(?:\.\d+)?)\s*%", query, re.IGNORECASE)
    if m:
        return {"scenario_type": "fx", "params": {"krw_usd_change_pct": float(m.group(1))}}

    # chemical: "6가 크롬", "납", "REACH"
    for sub in ("6가 크롬", "크로메이트", "납", "PFOS", "PFOA", "프탈레이트", "수은", "카드뮴"):
        if sub in query:
            return {"scenario_type": "chemical", "params": {"substance": sub}}

    # labor: "최저시급 10%"
    m = re.search(r"(?:최저\s*시급|시급|인건비)\s*(\d+(?:\.\d+)?)\s*%", query)
    if m:
        return {"scenario_type": "labor", "params": {"min_wage_increase_pct": float(m.group(1))}}

    # carbon: "탄소세 톤당 5만원"
    m = re.search(r"(?:탄소세|탄소).*?(\d+(?:\.\d+)?)\s*(?:만원|원)", query)
    if m:
        amt = float(m.group(1))
        if "만원" in query:
            amt *= 10000
        return {"scenario_type": "carbon", "params": {"krw_per_ton": amt}}

    return None


def _llm_extract(query: str) -> dict | None:
    """Ollama 호출로 시나리오 추출. 실패 시 None.

    Phase 2: feature="whatif_nl_route" 라우팅 — large 모델 풀 사용.
    """
    from features.compliance.rag.regulation_qa import _call_llm

    prompt = (
        "다음 자연어 질문에서 what-if 시뮬레이션 파라미터를 JSON 으로 추출하세요. "
        "scenario_type 은 tariff / fx / chemical / labor / carbon 중 하나여야 합니다. "
        "추출이 불가능하면 {}만 반환하세요.\n\n"
        f"질문: {query}\n\n"
        "JSON 응답 (예: {\"scenario_type\":\"tariff\",\"params\":{\"rate_pct\":25}}):"
    )
    text = _call_llm(
        prompt,
        timeout=10.0,
        feature="whatif_nl_route",
        format="json",
        temperature=0.1,
        num_predict=200,
    )
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and parsed.get("scenario_type"):
            return parsed
    except (json.JSONDecodeError, KeyError) as e:
        logger.debug("LLM what-if 응답 파싱 실패: %s", e)
    return None
