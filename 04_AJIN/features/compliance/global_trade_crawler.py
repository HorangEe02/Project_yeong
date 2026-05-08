"""글로벌 통상규제 크롤러 (미국/중국)

미국 IRA, TSCA, UFLPA, Section 301, USMCA와
중국 REACH, NEV 규정, 한-미/한-EU FTA 등
글로벌 통상·관세·공급망 규제를 통합 관리한다.

데이터 소스:
- US: congress.gov, ustr.gov, epa.gov, cbp.gov
- China: mee.gov.cn, miit.gov.cn
- Korea: fta.go.kr, motie.go.kr
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class GlobalTradeRegulation:
    """글로벌 통상규제 정보"""
    regulation_id: str
    name: str
    name_ko: str
    country: str                        # US, CN, US/MX/CA, KR/US, KR/EU
    issuing_org: str
    category: str                       # 통상규제, 화학물질, 공급망, 관세, FTA
    effective_date: str
    key_deadlines: list[dict]           # [{date, description_ko}]
    key_requirements_ko: list[str]
    tariff_impact: dict                 # {rate, affected_products_ko, estimated_annual_cost_ko}
    supply_chain_requirements_ko: list[str]
    ajin_relevance: str
    ajin_compliance_status: str         # 충족, 부분충족, 미충족, 모니터링중
    action_items_ko: list[str]
    crawled_at: str = ""


@dataclass
class GlobalTradeCrawlResult:
    """크롤링 결과"""
    regulations: list[GlobalTradeRegulation]
    crawled_at: str
    source: str
    total_count: int
    action_needed: int
    tariff_affected: int
    errors: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# 마스터 데이터
# ─────────────────────────────────────────────────────────────

_MASTER_DATA = [
    # ── US IRA (인플레이션 감축법) ──
    {
        "regulation_id": "US-IRA-001",
        "name": "Inflation Reduction Act (IRA) - EV Tax Credit",
        "name_ko": "인플레이션 감축법 (IRA) — EV 세액공제·배터리 부품 요건",
        "country": "US",
        "issuing_org": "US Congress / IRS / DOE",
        "category": "통상규제",
        "effective_date": "2022-08-16",
        "key_deadlines": [
            {"date": "2024-01-01", "description_ko": "배터리 부품 요건 60% 이상 북미 제조·조립"},
            {"date": "2025-01-01", "description_ko": "배터리 부품 요건 70%, 핵심 광물 요건 50%"},
            {"date": "2026-01-01", "description_ko": "배터리 부품 요건 80%, 핵심 광물 요건 60%"},
            {"date": "2027-01-01", "description_ko": "배터리 부품 요건 90%, 핵심 광물 요건 70%"},
            {"date": "2029-01-01", "description_ko": "배터리 부품 요건 100%, 핵심 광물 요건 80%"},
        ],
        "key_requirements_ko": [
            "EV 세액공제($7,500) 수령 조건: 배터리 부품 북미 제조·조립 비율 충족",
            "FEOC(해외 우려 기업) 규정: 중국 등 우려국 기업 부품·광물 사용 시 세액공제 제외",
            "배터리 부품(battery component) 가치 기준 북미 비율 단계적 상향",
            "핵심 광물(critical mineral) 가치 기준 미국 FTA 체결국 또는 북미 가공 비율 충족",
            "최종 조립(final assembly) 북미 수행 필수",
        ],
        "tariff_impact": {
            "rate": "세액공제 $7,500 (미충족 시 OEM 판매 경쟁력 저하)",
            "affected_products_ko": "EV 배터리 케이스, 배터리 트레이, 관련 서브어셈블리",
            "estimated_annual_cost_ko": "OEM 세액공제 미수령 시 대당 $3,750~$7,500 경쟁력 손실 → 아진 물량 영향",
        },
        "supply_chain_requirements_ko": [
            "배터리 부품 공급망에서 FEOC(중국 등) 기업 배제 또는 비율 관리",
            "핵심 광물 원산지 추적: 한-미 FTA 체결국 가공·정제 증빙",
            "북미 제조·조립 비율 산정을 위한 BOM(자재 명세서) 원산지 관리",
            "OEM 요청에 따른 부품별 원산지·제조지 증명서 제출",
        ],
        "ajin_relevance": "경산 제2공장 EV 배터리 케이스가 직접 해당. 현대차그룹 미국 조지아 공장(HMGMA) 납품 물량의 IRA 세액공제 충족 여부에 핵심 영향. 아진 미국 법인(AJIN USA, Alabama) 생산분은 북미 제조 인정.",
        "ajin_compliance_status": "부분충족",
        "action_items_ko": [
            "배터리 케이스 BOM 원산지 분석 완료 및 OEM 제출 (2025 Q2)",
            "FEOC 규정 해당 여부 공급사별 확인 — 중국산 원자재 비율 점검",
            "AJIN USA 생산 이관 가능 품목 검토 (IRA 충족률 향상)",
            "OEM(현대차) IRA 대응 TF 정기 참여 및 데이터 제출",
        ],
    },
    # ── US TSCA (유해화학물질 관리) ──
    {
        "regulation_id": "US-TSCA-001",
        "name": "Toxic Substances Control Act (TSCA)",
        "name_ko": "독성물질관리법 (TSCA)",
        "country": "US",
        "issuing_org": "US EPA",
        "category": "화학물질",
        "effective_date": "1976-10-11",
        "key_deadlines": [
            {"date": "2025-03-31", "description_ko": "PBT 5종 최종 규칙 시행 (DecaBDE 등) — 자동차 부품 면제 종료 검토"},
            {"date": "2025-12-31", "description_ko": "TSCA 리스크 평가 대상 고우선순위 물질(20종) 최종 결정"},
            {"date": "2026-06-30", "description_ko": "석면(asbestos) 전면 금지 규칙 완전 시행"},
        ],
        "key_requirements_ko": [
            "TSCA Inventory 등재 화학물질만 미국 내 제조·수입·사용 가능",
            "신규 화학물질(PMN) 사전 신고: 제조·수입 90일 전 EPA 신고",
            "기존 화학물질 리스크 평가: 고우선순위 물질 사용 제한·금지 가능",
            "PBT(잔류성·생물농축성·독성) 물질 5종 규제: DecaBDE, PIP(3:1) 등",
            "TSCA Section 6 최종 규칙에 따른 특정 용도 금지/제한",
        ],
        "tariff_impact": {},
        "supply_chain_requirements_ko": [
            "미국 수출 부품에 포함된 화학물질 TSCA Inventory 등재 여부 확인",
            "PBT 규제 물질(DecaBDE 등) 함유 여부 공급사 확인",
            "화학물질 사용 정보 EPA CDR(Chemical Data Reporting) 보고 대응",
        ],
        "ajin_relevance": "AJIN USA(Alabama) 현지 생산 및 한국 → 미국 수출 부품에 적용. 도장·표면처리에 사용되는 화학물질 TSCA 준수 여부 확인 필요. PBT 규제 물질 DecaBDE는 난연제로 일부 소재에 포함 가능.",
        "ajin_compliance_status": "모니터링중",
        "action_items_ko": [
            "미국 수출 부품 내 TSCA 규제 화학물질 목록 대조 점검",
            "PBT 규제 물질(DecaBDE, PIP(3:1)) 소재 함유 여부 공급사 조회",
            "AJIN USA 현지 화학물질 사용 TSCA 준수 현황 연간 감사",
        ],
    },
    # ── US UFLPA (위구르 강제노동 방지법) ──
    {
        "regulation_id": "US-UFLPA-001",
        "name": "Uyghur Forced Labor Prevention Act (UFLPA)",
        "name_ko": "위구르 강제노동 방지법 (UFLPA)",
        "country": "US",
        "issuing_org": "US CBP (관세국경보호청) / DHS",
        "category": "공급망",
        "effective_date": "2022-06-21",
        "key_deadlines": [
            {"date": "2022-06-21", "description_ko": "UFLPA 시행 — 신장위구르자치구 관련 수입품 반증 추정(rebuttable presumption) 적용"},
            {"date": "2025-06-30", "description_ko": "UFLPA Entity List 지속 업데이트 — 알루미늄, 철강 공급망 확대 검토"},
        ],
        "key_requirements_ko": [
            "신장위구르자치구에서 전부 또는 일부 생산된 제품 미국 수입 금지 (반증 추정)",
            "UFLPA Entity List 등재 기업과의 거래 시 WRO(통관보류명령) 발동",
            "수입자가 강제노동 무관함을 입증할 책임 (반증 입증)",
            "공급망 실사(Supply Chain Due Diligence) 체계 구축 권고",
            "철강, 알루미늄, 다결정 실리콘 등 우선 집행 분야",
        ],
        "tariff_impact": {
            "rate": "수입 금지 (통관 보류/거부)",
            "affected_products_ko": "신장 지역 연계 원자재 포함 전 제품 — 알루미늄, 철강, 면화, 다결정실리콘",
            "estimated_annual_cost_ko": "통관 거부 시 납기 지연 및 대체 소싱 비용 발생",
        },
        "supply_chain_requirements_ko": [
            "Tier 1~3 공급사의 신장위구르자치구 연관 여부 실사",
            "UFLPA Entity List 등재 기업과의 직·간접 거래 여부 확인",
            "원자재(철강, 알루미늄) 원산지 추적 체계 구축",
            "강제노동 무관 증빙 문서 체계적 관리 (공급사 서약서, 감사 보고서)",
            "CBP 통관보류 대응 절차 수립",
        ],
        "ajin_relevance": "AJIN USA 납품분 및 한국 → 미국 수출 부품 적용. 철강·알루미늄 원자재의 중국 공급망(특히 신장 지역) 연관 여부 확인 필요. 현대차그룹 ESG 공급망 실사 요구와 연동.",
        "ajin_compliance_status": "부분충족",
        "action_items_ko": [
            "철강·알루미늄 원자재 Tier 2~3 공급사 원산지 매핑 실시",
            "UFLPA Entity List 대조 점검 (분기별 업데이트)",
            "공급사 강제노동 금지 서약서(Code of Conduct) 수령 현황 점검",
            "OEM 공급망 실사 요청 대응 체계 정비",
        ],
    },
    # ── 중국 REACH (China RoHS / China REACH) ──
    {
        "regulation_id": "CN-REACH-001",
        "name": "China REACH (MEE Order 12) / China RoHS 2",
        "name_ko": "중국 화학물질 환경 위험 평가 및 관리 / 중국 RoHS 2",
        "country": "CN",
        "issuing_org": "중국 생태환경부(MEE) / 공업정보화부(MIIT)",
        "category": "화학물질",
        "effective_date": "2021-01-01",
        "key_deadlines": [
            {"date": "2024-01-01", "description_ko": "신화학물질 등록 관리 강화 (MEE Order 12 전면 시행)"},
            {"date": "2025-06-30", "description_ko": "China RoHS 2 달성관리 목록 확대 — 자동차 전장부품 포함 검토"},
            {"date": "2026-01-01", "description_ko": "중국 신 유해화학물질 관리조례 시행 예정"},
        ],
        "key_requirements_ko": [
            "China REACH(MEE Order 12): 신규 화학물질 중국 내 제조·수입 시 등록/신고 의무",
            "기존 화학물질 위험성 평가 및 우선 관리 화학물질 목록 관리",
            "China RoHS 2: 전기전자제품 유해물질 사용 제한 (납, 수은, 카드뮴, 6가크롬, PBB, PBDE)",
            "적합성 평가: 달성관리 목록(Catalog) 등재 제품 CCC 인증 또는 자발적 인증",
            "유해물질 함유 표시(SJ/T 11364) 의무",
        ],
        "tariff_impact": {},
        "supply_chain_requirements_ko": [
            "중국 수출 부품 내 화학물질 China REACH 등록 확인",
            "China RoHS 유해물질 6종 함유량 검사 성적서 구비",
            "중국 현지 대리인(AR) 지정 또는 수입자 등록 체계 확인",
            "소재 성적서(ICP 분석) 중국 기준 양식으로 관리",
        ],
        "ajin_relevance": "중국 완성차 OEM 납품(상해, 충칭 등) 부품 직접 적용. 특히 EV 배터리 케이스, 전장 관련 부품의 China RoHS 적합성 확인 필요. 6가 크롬(CHEM-006) 사용 부품 주의.",
        "ajin_compliance_status": "모니터링중",
        "action_items_ko": [
            "중국 수출 부품 목록 및 China RoHS 해당 여부 확인",
            "소재 유해물질 분석 성적서 중국 기준 양식 정비",
            "중국 현지 대리인(AR) 계약 현황 점검",
        ],
    },
    # ── 중국 NEV 규정 ──
    {
        "regulation_id": "CN-NEV-001",
        "name": "China NEV (New Energy Vehicle) Regulations",
        "name_ko": "중국 신에너지 자동차(NEV) 규제",
        "country": "CN",
        "issuing_org": "중국 공업정보화부(MIIT) / 국가발전개혁위원회(NDRC)",
        "category": "통상규제",
        "effective_date": "2021-01-01",
        "key_deadlines": [
            {"date": "2025-01-01", "description_ko": "NEV 크레딧 비율 28% 달성 의무 (2025년)"},
            {"date": "2025-06-30", "description_ko": "NEV 기술 로드맵 2.0 중간 점검 — 배터리 안전 기준 강화"},
            {"date": "2027-01-01", "description_ko": "NEV 판매 비율 40% 이상 목표 (정책 가이드라인)"},
            {"date": "2030-01-01", "description_ko": "NEV 크레딧 비율 추가 상향 예상"},
        ],
        "key_requirements_ko": [
            "NEV 크레딧(적분제): 완성차 기업 연간 NEV 생산/수입 비율 의무 충족",
            "배터리 안전 기술 기준(GB 38031): 열 확산(thermal propagation) 시험 강화",
            "EV 부품 현지화율 요구: 중국 현지 생산 또는 인증된 공급사 부품 우대",
            "NEV 보조금 정책: 2023년 국가 보조금 종료, 지방 보조금 잔존",
            "배터리 재활용 관리 규정: 배터리 회수·재활용 책임 확대",
        ],
        "tariff_impact": {
            "rate": "크레딧 미충족 시 벌금 또는 생산 제한",
            "affected_products_ko": "EV 배터리 케이스, 배터리 하우징, EV 전용 서브프레임",
            "estimated_annual_cost_ko": "중국 현지 OEM 납품 물량 확대 시 현지화 요구 대응 비용",
        },
        "supply_chain_requirements_ko": [
            "중국 현지 생산 부품의 GB 표준 적합성 인증 확보",
            "배터리 안전 기준(GB 38031) 충족을 위한 케이스 설계 기준 반영",
            "현지 공급사 인증 및 품질 관리 체계 구축",
            "배터리 재활용 추적을 위한 부품 이력 관리 시스템 연동",
        ],
        "ajin_relevance": "중국 완성차 OEM(현대차 북경공장 등) 납품 시 적용. EV 배터리 케이스 GB 38031 안전 기준 충족 필요. 중국 NEV 시장 급성장에 따른 현지 생산 확대 검토.",
        "ajin_compliance_status": "모니터링중",
        "action_items_ko": [
            "중국 GB 38031 배터리 안전 기준 대비 케이스 설계 적합성 검토",
            "중국 현지 납품 부품 품질 인증(CCC 등) 현황 점검",
            "중국 현지 생산 거점 확대 타당성 검토 (현지화율 대응)",
        ],
    },
    # ── US Section 301 관세 ──
    {
        "regulation_id": "US-S301-001",
        "name": "US Section 301 Tariffs on Chinese Goods",
        "name_ko": "미국 Section 301 관세 — 중국산 자동차 부품 관세",
        "country": "US",
        "issuing_org": "USTR (미국 무역대표부) / US CBP",
        "category": "관세",
        "effective_date": "2018-07-06",
        "key_deadlines": [
            {"date": "2024-09-27", "description_ko": "Section 301 관세 4년 재검토 — 중국산 EV·배터리 관세 100% 인상 확정"},
            {"date": "2025-01-01", "description_ko": "중국산 EV 관세 100%, 배터리 부품 관세 25% 적용 개시"},
            {"date": "2026-01-01", "description_ko": "중국산 반도체, 특정 광물 관세 50% 적용 예정"},
        ],
        "key_requirements_ko": [
            "중국산(Made in China) 자동차 부품 HS Code 기준 25% 추가 관세 부과",
            "2025년부터 중국산 EV 100%, 리튬이온 배터리 25%, 배터리 부품 25% 관세",
            "원산지 판정: 실질적 변형(Substantial Transformation) 기준",
            "관세 면제(Exclusion) 신청 절차: USTR 면제 신청 → 심사 → 한시적 면제",
            "중국 경유 우회 수출 단속 강화 (transshipment enforcement)",
        ],
        "tariff_impact": {
            "rate": "25% 추가 관세 (자동차 부품 List 3), EV/배터리 부품 25~100%",
            "affected_products_ko": "중국산 원자재·중간재 사용 자동차 부품, 중국에서 직접 수입하는 자동차 부품",
            "estimated_annual_cost_ko": "중국산 원자재 비율에 따라 연간 수억 원 관세 추가 부담 가능 (OEM 전가 협상 필요)",
        },
        "supply_chain_requirements_ko": [
            "중국산 원자재·중간재 사용 비율 파악 및 원산지 증명 관리",
            "HS Code별 Section 301 대상 여부 확인 (List 1~4)",
            "대체 소싱 검토: 중국산 → 한국산/동남아산 원자재 전환",
            "관세 면제(Exclusion) 해당 여부 확인 및 신청 검토",
        ],
        "ajin_relevance": "직접 영향은 제한적(한국산 부품은 비대상)이나, 중국산 원자재(철강, 알루미늄 등) 사용 비율에 따라 간접 영향. AJIN USA 현지 생산 시 중국산 부품/원자재 조달분에 관세 적용. OEM의 중국 공급망 회피 전략에 따른 아진 물량 변동 가능.",
        "ajin_compliance_status": "모니터링중",
        "action_items_ko": [
            "AJIN USA 조달 원자재 중 중국산 비율 파악 및 관세 영향 분석",
            "중국산 원자재 대체 소싱 로드맵 수립 (OEM 승인 포함)",
            "Section 301 관세 면제 해당 품목 확인 및 신청 검토",
            "OEM 원가 협상 시 관세 비용 반영 전략 수립",
        ],
    },
    # ── USMCA ──
    {
        "regulation_id": "US-USMCA-001",
        "name": "United States-Mexico-Canada Agreement (USMCA)",
        "name_ko": "미국-멕시코-캐나다 협정 (USMCA) — 자동차 원산지 규정",
        "country": "US/MX/CA",
        "issuing_org": "USTR / CBP / 멕시코 경제부 / 캐나다 국경서비스청",
        "category": "FTA",
        "effective_date": "2020-07-01",
        "key_deadlines": [
            {"date": "2023-07-01", "description_ko": "자동차 원산지 규정 완전 시행 (RVC 75%)"},
            {"date": "2026-07-01", "description_ko": "USMCA 6년 재검토(Joint Review) — 자동차 원산지 규정 재협상 가능"},
        ],
        "key_requirements_ko": [
            "완성차 역내가치비율(RVC) 75% 이상 충족 시 무관세 혜택",
            "자동차 핵심 부품(core parts) RVC 75% 개별 충족 의무",
            "철강·알루미늄 북미산 70% 이상 사용 의무",
            "노동가치비율(LVC): 시급 $16 이상 지역에서 40~45% 생산",
            "원산지 증명: USMCA 원산지 인증서(Certificate of Origin) 자율 발급",
        ],
        "tariff_impact": {
            "rate": "USMCA 충족 시 무관세, 미충족 시 MFN 관세 2.5% (승용차)",
            "affected_products_ko": "북미 수출 차체 구조물, 서브프레임, 배터리 케이스",
            "estimated_annual_cost_ko": "USMCA 원산지 미충족 시 OEM 관세 부담 → 아진 부품 납품 경쟁력 저하",
        },
        "supply_chain_requirements_ko": [
            "부품별 역내가치비율(RVC) 산정: 순원가법(Net Cost) 또는 거래가격법",
            "BOM 기반 원산지 판정: 한국산 원자재의 USMCA 역내산 불인정 고려",
            "AJIN USA 현지 생산분의 RVC 산정 및 원산지 인증 관리",
            "철강·알루미늄 역내산 비율 증빙: 용해(melting & pouring) 기준",
        ],
        "ajin_relevance": "AJIN USA(Alabama) 생산분이 USMCA 적용 대상. 한국에서 수입하는 반제품·부품은 역외산으로 RVC 계산 시 불리. 현지 소싱 비율 확대 또는 한-미 FTA 활용 병행 검토 필요.",
        "ajin_compliance_status": "부분충족",
        "action_items_ko": [
            "AJIN USA 생산 부품별 USMCA RVC 산정 현황 점검",
            "한국 수입 반제품의 역외산 비율이 RVC에 미치는 영향 분석",
            "현지 소싱 확대 방안 검토 (북미산 철강·알루미늄 조달)",
            "USMCA 원산지 인증서 발급·관리 절차 정비",
        ],
    },
    # ── 한-미 FTA ──
    {
        "regulation_id": "FTA-KORUS-001",
        "name": "Korea-US Free Trade Agreement (KORUS FTA)",
        "name_ko": "한-미 자유무역협정 (KORUS FTA) — 자동차 부품 원산지",
        "country": "KR/US",
        "issuing_org": "산업통상자원부 / USTR",
        "category": "FTA",
        "effective_date": "2012-03-15",
        "key_deadlines": [
            {"date": "2012-03-15", "description_ko": "한-미 FTA 발효 — 자동차 부품 관세 단계적 철폐"},
            {"date": "2016-01-01", "description_ko": "자동차 부품 대부분 관세 철폐 완료"},
            {"date": "2026-03-15", "description_ko": "FTA 15년차 — 이행 점검 및 개정 논의 가능"},
        ],
        "key_requirements_ko": [
            "자동차 부품 원산지 기준: HS Code별 세번변경기준(CTC) 또는 부가가치기준(RVC 35~55%)",
            "원산지 증명서: 수출자 또는 생산자 자율 발급 (FTA 원산지 인증수출자 제도 활용)",
            "직접 운송 원칙: 제3국 경유 시 원산지 유지 조건 충족",
            "관세 환급 제한: 역내 가공 후 수출 시 원자재 관세 환급 제한 규정",
            "원산지 검증: 미국 CBP의 서면 검증 요청 시 증빙 서류 제출 의무",
        ],
        "tariff_impact": {
            "rate": "FTA 충족 시 무관세 (MFN 관세 2.5% 면제)",
            "affected_products_ko": "한국 → 미국 수출 차체 구조물, 서브프레임, 프레스 부품",
            "estimated_annual_cost_ko": "FTA 활용 시 연간 관세 절감 약 2~5억 원 추정 (수출 규모 기준)",
        },
        "supply_chain_requirements_ko": [
            "HS Code별 원산지 결정기준 충족 여부 확인",
            "FTA 원산지 인증수출자 자격 취득·유지",
            "원산지 소명서 및 증빙 서류 5년 보관 의무",
            "BOM 기반 원산지 판정: 수입산 원자재 비율 관리",
        ],
        "ajin_relevance": "한국 → 미국 수출 자동차 부품에 KORUS FTA 특혜 관세 적용. 원산지 인증수출자 자격 유지 필수. USMCA와 병행 활용하여 AJIN USA 수입 원자재의 관세 최적화 가능.",
        "ajin_compliance_status": "충족",
        "action_items_ko": [
            "FTA 원산지 인증수출자 자격 갱신 일정 확인 (유효기간 관리)",
            "수출 품목별 원산지 판정서 최신화 (HS Code 변경 시 재판정)",
            "원산지 검증 대응 서류 체계 점검 (BOM, 제조공정도, 원가 자료)",
            "KORUS FTA 관세 절감 실적 연간 정산 보고",
        ],
    },
    # ── 한-EU FTA ──
    {
        "regulation_id": "FTA-KOREU-001",
        "name": "Korea-EU Free Trade Agreement",
        "name_ko": "한-EU 자유무역협정 — 자동차 부품 원산지 규정",
        "country": "KR/EU",
        "issuing_org": "산업통상자원부 / European Commission",
        "category": "FTA",
        "effective_date": "2011-07-01",
        "key_deadlines": [
            {"date": "2011-07-01", "description_ko": "한-EU FTA 잠정 발효"},
            {"date": "2016-07-01", "description_ko": "자동차 부품 관세 철폐 완료 (5년 단계적)"},
            {"date": "2026-07-01", "description_ko": "FTA 15주년 — 이행 평가 및 개정 논의"},
        ],
        "key_requirements_ko": [
            "자동차 부품 원산지 기준: 세번변경기준(CTH) 또는 부가가치기준(공장도가격의 50%)",
            "인증수출자(Approved Exporter) 제도: 연간 수출 실적 기준 자격 취득",
            "EUR.1 증명서 또는 인증수출자 원산지 신고 (Invoice Declaration)",
            "양자 누적(Bilateral Cumulation): 한-EU 원산지 재료 상호 인정",
            "역내 가공 불충분(Insufficient Processing) 조건 확인",
        ],
        "tariff_impact": {
            "rate": "FTA 충족 시 무관세 (MFN 관세 3~4.5% 면제)",
            "affected_products_ko": "한국 → EU 수출 차체 구조물, 서브프레임, 프레스 부품",
            "estimated_annual_cost_ko": "FTA 활용 시 연간 관세 절감 약 1~3억 원 추정 (EU 수출 규모 기준)",
        },
        "supply_chain_requirements_ko": [
            "HS Code별 원산지 결정기준 충족 확인 (CTH 또는 RVC 50%)",
            "인증수출자(Approved Exporter) 자격 유지 — 관세청 정기 심사 대응",
            "원산지 증빙 서류 5년 보관 (BOM, 수입 신고서, 원가 자료)",
            "EU 세관 검증(Verification) 요청 시 30일 내 회신 체계 구축",
        ],
        "ajin_relevance": "한국 → EU 수출 자동차 부품에 한-EU FTA 무관세 적용. 현대·기아 EU 판매 차량용 부품 해당. 인증수출자 자격 유지 필수. EU CBAM과 별도로 관세 혜택 관리.",
        "ajin_compliance_status": "충족",
        "action_items_ko": [
            "인증수출자(Approved Exporter) 자격 갱신 및 관세청 심사 대응",
            "EU 수출 품목 원산지 판정서 최신화",
            "EU 세관 검증 대응 매뉴얼 정비 (30일 회신 체계)",
            "한-EU FTA 관세 절감 실적 연간 보고",
        ],
    },
]


# ─────────────────────────────────────────────────────────────
# 크롤러
# ─────────────────────────────────────────────────────────────

class GlobalTradeCrawler:
    """글로벌 통상규제 크롤러 (미국/중국)"""

    def __init__(self, crawled_dir: Path | None = None):
        if crawled_dir is None:
            crawled_dir = Path(__file__).parent.parent.parent / "data" / "crawled"
        self.crawled_dir = crawled_dir
        self.crawled_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.crawled_dir / "global_trade.json"
        self._regulations: list[GlobalTradeRegulation] = []

    # ── crawl ──
    def crawl(self) -> GlobalTradeCrawlResult:
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        errors: list[str] = []
        regulations: list[GlobalTradeRegulation] = []

        for item in _MASTER_DATA:
            try:
                regulations.append(GlobalTradeRegulation(**item, crawled_at=now))
            except Exception as e:
                errors.append(f"파싱 오류 ({item.get('regulation_id', '?')}): {e}")

        self._regulations = regulations

        result = GlobalTradeCrawlResult(
            regulations=regulations,
            crawled_at=now,
            source="congress.gov + ustr.gov + epa.gov + cbp.gov + mee.gov.cn + miit.gov.cn + fta.go.kr",
            total_count=len(regulations),
            action_needed=sum(
                1 for r in regulations
                if r.ajin_compliance_status in ("미충족", "부분충족")
            ),
            tariff_affected=sum(1 for r in regulations if r.tariff_impact),
            errors=errors,
        )
        self._save(result)
        return result

    # ── persistence ──
    def _save(self, result: GlobalTradeCrawlResult) -> None:
        data = {
            "crawled_at": result.crawled_at,
            "source": result.source,
            "total_count": result.total_count,
            "action_needed": result.action_needed,
            "tariff_affected": result.tariff_affected,
            "regulations": [asdict(r) for r in result.regulations],
            "errors": result.errors,
        }
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> list[GlobalTradeRegulation]:
        if not self.output_path.exists():
            return []
        with open(self.output_path, encoding="utf-8") as f:
            data = json.load(f)
        regs: list[GlobalTradeRegulation] = []
        for item in data.get("regulations", []):
            try:
                regs.append(GlobalTradeRegulation(**item))
            except Exception as e:
                logger.warning("로드 오류: %s", e)
        return regs

    # ── queries ──
    def get_by_country(self, country: str) -> list[GlobalTradeRegulation]:
        """국가 코드로 규제 필터링 (예: 'US', 'CN', 'KR/US')"""
        if not self._regulations:
            self.crawl()
        return [r for r in self._regulations if country in r.country]

    def get_action_needed(self) -> list[GlobalTradeRegulation]:
        """조치 필요 규제 목록 (미충족 또는 부분충족)"""
        if not self._regulations:
            self.crawl()
        return [
            r for r in self._regulations
            if r.ajin_compliance_status in ("미충족", "부분충족")
        ]

    def get_tariff_impact_summary(self) -> dict:
        """관세 영향 요약"""
        if not self._regulations:
            self.crawl()
        impacts: list[dict] = []
        for r in self._regulations:
            if r.tariff_impact:
                impacts.append({
                    "regulation_id": r.regulation_id,
                    "name_ko": r.name_ko,
                    "country": r.country,
                    "rate": r.tariff_impact.get("rate", ""),
                    "affected_products_ko": r.tariff_impact.get("affected_products_ko", ""),
                    "estimated_annual_cost_ko": r.tariff_impact.get("estimated_annual_cost_ko", ""),
                })
        return {
            "total_with_tariff_impact": len(impacts),
            "details": impacts,
        }

    def get_summary(self) -> dict:
        """전체 요약"""
        if not self._regulations:
            self.crawl()
        regs = self._regulations
        return {
            "total": len(regs),
            "by_country": {
                c: len([r for r in regs if c in r.country])
                for c in sorted({r.country for r in regs})
            },
            "by_category": {
                cat: len([r for r in regs if r.category == cat])
                for cat in sorted({r.category for r in regs})
            },
            "by_status": {
                s: len([r for r in regs if r.ajin_compliance_status == s])
                for s in ("충족", "부분충족", "미충족", "모니터링중")
            },
            "action_needed": len(self.get_action_needed()),
            "tariff_affected": sum(1 for r in regs if r.tariff_impact),
            "upcoming_deadlines": sum(len(r.key_deadlines) for r in regs),
        }
