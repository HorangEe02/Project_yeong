"""v2.5: 공장-규제 자동 매핑 — 규제 유형별로 적용 대상 공장을 자동 결정

규제의 doc_type, category, country 등과 공장의 location, certifications,
main_products 등을 매칭하여 적용 대상 공장을 자동으로 매핑한다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent.parent / "data"


# ── 규제 유형 → 적용 대상 공장 규칙 ──
# "ALL_DOMESTIC": 국내 전체, "ALL_OVERSEAS": 해외 전체, "ALL": 전체
# 또는 specific plant_id 리스트

_REGULATION_PLANT_RULES: dict[str, dict] = {
    # ISO/IATF 국제규격 → 인증 보유 전체 공장
    "ISO": {
        "scope": "ALL",
        "description": "ISO/IATF 국제규격 — 인증 보유 전체 사업장",
        "filter": lambda plant: any("ISO" in c or "IATF" in c for c in plant.get("certifications", [])),
    },
    # APQP → 자사 제조 공장
    "APQP": {
        "scope": "ALL",
        "description": "APQP 프로세스 — 제조 공장 전체",
        "filter": lambda plant: True,  # 모든 제조 공장
    },
    # MSDS → 화학물질 취급 전체
    "MSDS": {
        "scope": "ALL",
        "description": "MSDS 유해물질 — 화학물질 사용 전체 사업장",
        "filter": lambda plant: True,
    },
    # 국내법규 → 국내 공장만
    "DomesticLaw": {
        "scope": "ALL_DOMESTIC",
        "description": "국내법규 — 국내 사업장만 적용",
        "filter": lambda plant: _is_domestic(plant),
    },
    # EU 규제 → EU 수출 관련 공장
    "EU": {
        "scope": "ALL",
        "description": "EU 규제 — EU 수출 관련 전체 사업장 (유럽 수출품 생산)",
        "filter": lambda plant: any(
            k in str(plant.get("major_customers", [])).lower()
            for k in ["현대", "기아", "hyundai", "kia"]
        ) or True,  # 아진산업은 현대/기아 전체 납품이므로 전체 적용
    },
    # OEM 품질기준 → OEM 납품 공장
    "OEM": {
        "scope": "ALL",
        "description": "OEM 품질기준 — 완성차 납품 전체 사업장",
        "filter": lambda plant: True,
    },
    # 탄소/ESG → 전체 (글로벌 추세)
    "ESG": {
        "scope": "ALL",
        "description": "탄소/ESG 규제 — 전체 사업장 (글로벌 ESG 대응)",
        "filter": lambda plant: True,
    },
    # EV 배터리 → EV 부품 생산 공장
    "EV": {
        "scope": "ALL",
        "description": "EV 배터리 안전 — EV 관련 부품 생산 사업장",
        "filter": lambda plant: any(
            k in str(plant.get("main_products", plant.get("main_business", []))).lower()
            for k in ["ewp", "cch", "전기", "ev", "배터리", "워터펌프", "냉각", "히터"]
        ),
    },
    # 미국/중국 무역규제 → 해외법인 + 수출 공장
    "Trade": {
        "scope": "ALL",
        "description": "미국/중국 무역규제 — 해외 거래 관련 전체 사업장",
        "filter": lambda plant: _is_overseas(plant) or _is_export_plant(plant),
    },
}


def get_applicable_plants(doc_type: str) -> list[dict]:
    """특정 규제 유형에 적용되는 공장 목록을 반환한다.

    Returns:
        [{"plant_id": ..., "name": ..., "category": ..., "location": ...}, ...]
    """
    all_plants = _load_all_plants()
    rule = _REGULATION_PLANT_RULES.get(doc_type)

    if not rule:
        return all_plants  # 규칙 없으면 전체 적용

    filter_fn = rule.get("filter", lambda p: True)
    return [p for p in all_plants if filter_fn(p)]


def get_plant_regulations(plant_id: str) -> list[dict]:
    """특정 공장에 적용되는 규제 유형 목록을 반환한다.

    Returns:
        [{"doc_type": "ISO", "description": "...", "scope": "ALL"}, ...]
    """
    all_plants = _load_all_plants()
    plant = next((p for p in all_plants if p.get("plant_id") == plant_id), None)

    if not plant:
        return []

    applicable = []
    for doc_type, rule in _REGULATION_PLANT_RULES.items():
        filter_fn = rule.get("filter", lambda p: True)
        if filter_fn(plant):
            applicable.append({
                "doc_type": doc_type,
                "description": rule.get("description", ""),
                "scope": rule.get("scope", ""),
            })

    return applicable


def get_regulation_mapping_summary() -> dict[str, list[str]]:
    """모든 규제 유형 → 적용 공장 이름 매핑 요약을 반환한다.

    Returns:
        {"ISO": ["경산 본사", "경산 제2공장", ...], "DomesticLaw": [...], ...}
    """
    summary = {}
    for doc_type in _REGULATION_PLANT_RULES:
        plants = get_applicable_plants(doc_type)
        summary[doc_type] = [p.get("name", p.get("plant_id", "")) for p in plants]
    return summary


def _load_all_plants() -> list[dict]:
    """plants.json에서 모든 공장을 로드한다."""
    plants_path = DATA_DIR / "facility_db" / "plants.json"
    if not plants_path.exists():
        return []

    try:
        with open(plants_path, encoding="utf-8") as f:
            data = json.load(f)

        all_plants = []
        for p in data.get("plants", []):
            p["_category"] = "자사"
            all_plants.append(p)
        for p in data.get("subsidiaries_domestic", []):
            p["_category"] = "국내 계열사"
            all_plants.append(p)
        for p in data.get("subsidiaries_overseas", []):
            p["_category"] = "해외법인"
            all_plants.append(p)

        return all_plants
    except Exception:
        return []


def _is_domestic(plant: dict) -> bool:
    """국내 공장인지 판별한다."""
    return plant.get("_category") in ("자사", "국내 계열사")


def _is_overseas(plant: dict) -> bool:
    """해외법인인지 판별한다."""
    return plant.get("_category") == "해외법인"


def _is_export_plant(plant: dict) -> bool:
    """수출 관련 공장인지 판별한다 (현대/기아 납품 → 글로벌 수출)."""
    customers = str(plant.get("major_customers", []))
    return any(k in customers.lower() for k in ["현대", "기아", "hyundai", "kia", "hmma", "hmgma"])
