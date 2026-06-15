"""
관세 시뮬레이터 -- 품목별 원가 영향 실시간 산출
- 관세율 슬라이더 연동
- 복수 품목 동시 시뮬레이션
- 연간 총 영향액 자동 계산
"""

from dataclasses import dataclass
from typing import List, Dict


@dataclass
class ProductItem:
    """수출 품목 정보"""
    name: str
    annual_volume: int           # 연간 수량
    unit_cost_usd: float         # 단가 (USD)
    description: str = ""
    plant: str = ""              # 생산 공장
    destination: str = "USA"     # 수출 대상국


@dataclass
class TariffSimResult:
    """관세 시뮬레이션 결과"""
    product: str
    tariff_rate: float           # 관세율 (%)
    unit_tariff: float           # 개당 관세 (USD)
    annual_tariff: float         # 연간 관세 총액 (USD)
    annual_tariff_krw: float     # 연간 관세 총액 (원)
    cost_increase_pct: float     # 원가 상승률 (%)


# 아진산업 HMGMA 납품 품목 (추정)
AJIN_EXPORT_PRODUCTS = [
    ProductItem("EWP (전자식 워터펌프)", 300_000, 85, "전기차 냉각 핵심 부품", "JOON INC", "USA"),
    ProductItem("CCH (냉각수 가열 히터)", 200_000, 120, "전기차 열관리 부품", "JOON INC", "USA"),
    ProductItem("OBC (온보드 차저 케이스)", 150_000, 95, "충전 시스템 하우징", "JOON INC", "USA"),
    ProductItem("DASH COMPL (대시보드 구조물)", 250_000, 65, "차체 구조 부품", "AJIN USA (AL)", "USA"),
    ProductItem("서브프레임", 180_000, 150, "차량 하체 구조물", "AJIN USA (AL)", "USA"),
    ProductItem("범퍼빔", 200_000, 45, "충돌 안전 부품", "JOON INC", "USA"),
]

EXCHANGE_RATE = 1_380  # USD/KRW


def simulate_tariff(
    products: List[ProductItem] = None,
    tariff_rate: float = 25.0,
    exchange_rate: float = EXCHANGE_RATE,
) -> Dict:
    """
    관세 시뮬레이션 실행

    Returns:
        {
            "results": [TariffSimResult, ...],
            "total_annual_usd": 총 연간 관세 (USD),
            "total_annual_krw": 총 연간 관세 (원),
            "avg_cost_increase": 평균 원가 상승률,
        }
    """
    if products is None:
        products = AJIN_EXPORT_PRODUCTS

    rate = tariff_rate / 100.0
    results = []
    total_usd = 0

    for prod in products:
        unit_tariff = prod.unit_cost_usd * rate
        annual = unit_tariff * prod.annual_volume
        annual_krw = annual * exchange_rate
        cost_pct = rate * 100

        results.append(TariffSimResult(
            product=prod.name,
            tariff_rate=tariff_rate,
            unit_tariff=round(unit_tariff, 2),
            annual_tariff=round(annual, 0),
            annual_tariff_krw=round(annual_krw, 0),
            cost_increase_pct=round(cost_pct, 1),
        ))
        total_usd += annual

    return {
        "results": results,
        "total_annual_usd": round(total_usd, 0),
        "total_annual_krw": round(total_usd * exchange_rate, 0),
        "avg_cost_increase": round(tariff_rate, 1),
        "tariff_rate": tariff_rate,
        "exchange_rate": exchange_rate,
    }


def compare_scenarios(rates: List[float]) -> List[Dict]:
    """복수 관세율 시나리오 비교"""
    return [simulate_tariff(tariff_rate=r) for r in rates]
