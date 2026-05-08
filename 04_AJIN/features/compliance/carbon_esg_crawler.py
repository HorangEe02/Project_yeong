"""탄소/ESG 규제 통합 크롤러

EU CBAM, CSRD, EU Taxonomy, 한국 탄소중립기본법,
온실가스 배출권거래제(K-ETS), TCFD, SBTi, CDP 등
탄소·ESG 관련 핵심 규제를 통합 관리한다.

대상: 아진산업(자동차 부품 Tier-1, 3개 공장, 930명)
    - 현대/기아 Tier-1 공급사
    - 차체 구조물, 서브프레임, EV 배터리 케이스 제조

데이터 소스:
- European Commission (CBAM, CSRD, EU Taxonomy)
- 대한민국 법제처 / 환경부
- TCFD, SBTi, CDP 공식 사이트
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  데이터 모델
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class CarbonESGRegulation:
    """탄소/ESG 규제 정보"""
    regulation_id: str
    name: str
    name_ko: str
    issuing_org: str
    category: str                          # 탄소규제 / ESG공시 / 녹색분류 / 배출권
    effective_date: str
    compliance_deadlines: list[dict]       # [{deadline_date, description_ko, scope}]
    key_requirements_ko: list[str]
    reporting_obligations: list[dict]      # [{report_type, frequency, first_due_date, scope_ko}]
    ajin_relevance: str
    ajin_readiness: str                    # 준비완료 / 진행중 / 미착수 / 해당없음
    estimated_cost_impact_ko: str
    action_items_ko: list[str]
    crawled_at: str = ""


@dataclass
class CarbonESGCrawlResult:
    """크롤링 결과"""
    regulations: list[CarbonESGRegulation]
    crawled_at: str
    source: str
    total_count: int
    action_needed: int
    upcoming_deadlines: int
    errors: list[str] = field(default_factory=list)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  마스터 데이터 — 탄소/ESG 규제 8건
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_MASTER_DATA: list[dict] = [

    # ════════════════════════════════════════════
    #  1. EU CBAM — 탄소국경조정메커니즘
    # ════════════════════════════════════════════
    {
        "regulation_id": "CARBON-EU-CBAM-001",
        "name": "EU Carbon Border Adjustment Mechanism (CBAM)",
        "name_ko": "EU 탄소국경조정메커니즘 (CBAM)",
        "issuing_org": "European Commission",
        "category": "탄소규제",
        "effective_date": "2023-10-01",
        "compliance_deadlines": [
            {"deadline_date": "2025-12-31", "description_ko": "전환기간 종료 — 분기별 CBAM 보고서 제출 의무", "scope": "EU 수입 철강·알루미늄·시멘트·비료·전력·수소"},
            {"deadline_date": "2026-01-01", "description_ko": "본격 시행 — CBAM 인증서 구매 의무 개시", "scope": "EU 수입 CBAM 대상 품목 전체"},
            {"deadline_date": "2034-12-31", "description_ko": "EU ETS 무상할당 완전 폐지 (CBAM 완전 전환)", "scope": "EU ETS 대상 전체 산업"},
        ],
        "key_requirements_ko": [
            "EU 수입품의 내재 탄소 배출량(Embedded Emissions) 산정·보고 의무",
            "2026년부터 CBAM 인증서 구매 — EU ETS 탄소가격과 연동",
            "직접 배출(Scope 1) + 간접 배출(Scope 2, 일부 품목) 산정",
            "제3국 탄소가격 납부분 공제 가능 (한국 K-ETS 납부분 공제 대상)",
            "분기별 CBAM 보고서 제출 (전환기간 중)",
        ],
        "reporting_obligations": [
            {"report_type": "CBAM 분기 보고서", "frequency": "분기별", "first_due_date": "2024-01-31", "scope_ko": "EU 수출 철강 부품 내재 탄소 배출량"},
            {"report_type": "CBAM 연간 신고", "frequency": "연간", "first_due_date": "2027-05-31", "scope_ko": "전년도 CBAM 인증서 정산"},
        ],
        "ajin_relevance": "아진산업은 OEM 납품 구조이므로 직접 CBAM 신고 의무는 EU 수입자에게 있으나, OEM이 Scope 3 탄소 데이터를 요구할 경우 제조 공정별 탄소 배출량 데이터 제공 필요. 프레스·용접·도장 공정의 에너지 사용량 기반 탄소 발자국 산정 체계 구축 시급.",
        "ajin_readiness": "진행중",
        "estimated_cost_impact_ko": "직접 비용 영향 제한적이나, OEM 탄소 데이터 요구 대응을 위한 MRV(측정·보고·검증) 시스템 구축 비용 약 2~5억원 추정. 장기적으로 탄소 비용이 부품 단가에 반영될 가능성.",
        "action_items_ko": [
            "공장별·공정별 탄소 배출량 산정 체계(MRV) 구축",
            "EU CBAM 방법론에 따른 내재 탄소 배출량 계산 시범 적용",
            "OEM 탄소 데이터 요청 대응 프로세스 수립",
            "한국 K-ETS 배출권 구매 비용의 CBAM 공제 적용 검토",
        ],
    },

    # ════════════════════════════════════════════
    #  2. EU CSRD — 기업지속가능성보고지침
    # ════════════════════════════════════════════
    {
        "regulation_id": "ESG-EU-CSRD-001",
        "name": "EU Corporate Sustainability Reporting Directive (CSRD)",
        "name_ko": "EU 기업지속가능성보고지침 (CSRD)",
        "issuing_org": "European Commission",
        "category": "ESG공시",
        "effective_date": "2024-01-01",
        "compliance_deadlines": [
            {"deadline_date": "2025-01-01", "description_ko": "대규모 상장기업(기존 NFRD 대상) 첫 보고 의무 (2024 회계연도)", "scope": "EU 대규모 상장기업 (직원 500+)"},
            {"deadline_date": "2026-01-01", "description_ko": "대규모 비상장기업 포함 확대 (2025 회계연도)", "scope": "EU 대규모 기업 (2/3 충족: 직원 250+, 매출 40M EUR+, 자산 20M EUR+)"},
            {"deadline_date": "2029-01-01", "description_ko": "EU 역외 기업 (제3국 기업) 보고 의무 (2028 회계연도)", "scope": "EU 매출 150M EUR 이상 + EU 내 자회사/지점 보유 제3국 기업"},
        ],
        "key_requirements_ko": [
            "ESRS(European Sustainability Reporting Standards) 기준 지속가능성 보고서 작성",
            "이중 중요성(Double Materiality) 평가 — 재무적 중요성 + 환경·사회적 중요성",
            "Scope 1·2·3 온실가스 배출량 보고",
            "공급망 인권·환경 실사 결과 공시",
            "제3자 인증(Limited Assurance → Reasonable Assurance 단계적 강화)",
            "디지털 태깅(XBRL) 의무",
        ],
        "reporting_obligations": [
            {"report_type": "ESRS 지속가능성보고서", "frequency": "연간", "first_due_date": "2025-04-30", "scope_ko": "EU 상장 대기업 (1단계)"},
            {"report_type": "공급망 ESG 데이터 제공", "frequency": "연간 (OEM 요청 시)", "first_due_date": "2025-06-30", "scope_ko": "EU OEM 공급망 Tier 1 협력사"},
        ],
        "ajin_relevance": "아진산업 자체는 EU 역외 기업으로 직접 의무 대상은 2029년부터이나, EU OEM(VW, BMW, Stellantis 등)이 공급망 ESG 데이터를 요구하고 있어 사실상 간접 의무 발생. OEM의 Scope 3 보고를 위해 탄소 배출, 용수 사용, 폐기물, 인권 실사 데이터 제공 필요.",
        "ajin_readiness": "미착수",
        "estimated_cost_impact_ko": "ESG 보고 체계 구축 및 제3자 검증 비용 약 3~7억원. OEM 대응 ESG 데이터 시스템 연간 운영 1~2억원 추정.",
        "action_items_ko": [
            "ESRS 기준 중요성 평가(Materiality Assessment) 실시",
            "Scope 1·2·3 온실가스 인벤토리 구축",
            "공급망 ESG 데이터 수집·관리 시스템 도입",
            "OEM ESG 설문(SAQ) 대응 전담 조직 구성",
            "ESG 보고서 작성 로드맵 수립 (2027년 자발적 공시 목표)",
        ],
    },

    # ════════════════════════════════════════════
    #  3. EU Taxonomy — EU 녹색분류체계
    # ════════════════════════════════════════════
    {
        "regulation_id": "ESG-EU-TAXO-001",
        "name": "EU Taxonomy Regulation",
        "name_ko": "EU 녹색분류체계 (EU Taxonomy)",
        "issuing_org": "European Commission",
        "category": "녹색분류",
        "effective_date": "2020-07-12",
        "compliance_deadlines": [
            {"deadline_date": "2024-01-01", "description_ko": "기후변화 완화·적응 외 4개 환경목표 공시 의무 (전체 6개 환경목표 적용)", "scope": "CSRD 대상 기업"},
            {"deadline_date": "2026-01-01", "description_ko": "대규모 비상장기업까지 Taxonomy 적격성/정렬성 공시 확대", "scope": "CSRD 2단계 대상 기업"},
        ],
        "key_requirements_ko": [
            "6대 환경목표 기여도 평가: (1)기후변화 완화 (2)기후변화 적응 (3)수자원 (4)순환경제 (5)오염방지 (6)생물다양성",
            "경제활동별 기술심사기준(TSC) 충족 여부 판단 — Taxonomy 적격/정렬 구분",
            "DNSH(Do No Significant Harm) 원칙 — 다른 환경목표에 심각한 피해 없음 입증",
            "최소 사회적 안전장치(Minimum Safeguards) 준수 — 인권, 노동, 반부패",
            "매출(Turnover), 자본지출(CapEx), 운영지출(OpEx) Taxonomy 비율 공시",
        ],
        "reporting_obligations": [
            {"report_type": "Taxonomy 적격성/정렬성 공시", "frequency": "연간", "first_due_date": "2024-01-01", "scope_ko": "CSRD 1단계 대상 기업"},
        ],
        "ajin_relevance": "아진산업의 EV 배터리 케이스, 경량화 부품 제조는 '기후변화 완화' 목표 하 자동차 제조(NACE C29.10) 경제활동에 해당 가능. Taxonomy 정렬 입증 시 EU OEM의 녹색 공급망 인증 획득 및 녹색 금융 접근성 향상.",
        "ajin_readiness": "미착수",
        "estimated_cost_impact_ko": "Taxonomy 적격성 분석 및 정렬성 입증 컨설팅 비용 약 1~3억원. 녹색분류 정렬 시 ESG 펀드 투자 유치, 녹색채권 발행 등 긍정적 재무 효과 기대.",
        "action_items_ko": [
            "아진산업 경제활동의 EU Taxonomy 적격성(Eligibility) 분석",
            "기술심사기준(TSC) 충족 여부 갭 분석",
            "DNSH 원칙 충족을 위한 환경 데이터 정비",
            "Taxonomy CapEx 비율 산출을 위한 녹색 투자 분류 체계 수립",
        ],
    },

    # ════════════════════════════════════════════
    #  4. 한국 탄소중립기본법 — 2050 탄소중립
    # ════════════════════════════════════════════
    {
        "regulation_id": "CARBON-KR-CNBA-001",
        "name": "Framework Act on Carbon Neutrality and Green Growth",
        "name_ko": "기후위기 대응을 위한 탄소중립·녹색성장 기본법 (탄소중립기본법)",
        "issuing_org": "대한민국 환경부",
        "category": "탄소규제",
        "effective_date": "2022-03-25",
        "compliance_deadlines": [
            {"deadline_date": "2030-12-31", "description_ko": "2030 국가 온실가스 감축목표(NDC) 달성 — 2018년 대비 40% 감축", "scope": "대한민국 전체 산업"},
            {"deadline_date": "2050-12-31", "description_ko": "2050 탄소중립 달성", "scope": "대한민국 전체"},
        ],
        "key_requirements_ko": [
            "2050 탄소중립 법적 목표 명시",
            "2030 NDC: 2018년 배출량 대비 40% 감축 (산업부문 14.5% 감축)",
            "기후변화영향평가 의무 — 대규모 개발사업, 에너지 다소비 시설",
            "탄소중립도시 지정·운영",
            "기후대응기금 설치·운용",
            "온실가스 감축인지 예산제도 시행",
        ],
        "reporting_obligations": [
            {"report_type": "온실가스 배출량 명세서", "frequency": "연간", "first_due_date": "2023-03-31", "scope_ko": "온실가스 배출권거래제/목표관리제 대상 업체"},
            {"report_type": "기후변화영향평가서", "frequency": "사업별", "first_due_date": "2023-09-25", "scope_ko": "대규모 개발사업 시행자"},
        ],
        "ajin_relevance": "아진산업은 자동차 부품 제조업(에너지 다소비 업종)으로 온실가스 목표관리제 또는 배출권거래제 대상 가능. 경산·양산·김해 공장의 에너지 사용량 합산 기준 판단. 연간 온실가스 배출량 보고 및 감축 계획 수립 의무.",
        "ajin_readiness": "진행중",
        "estimated_cost_impact_ko": "온실가스 감축 설비 투자(고효율 프레스, 전기화, 재생에너지 전환) 약 50~100억원 (5개년). 배출권 구매 비용 연간 5~10억원 추정(할당 초과 시).",
        "action_items_ko": [
            "전 공장 온실가스 인벤토리(Scope 1·2) 정비 및 제3자 검증",
            "2030 감축목표 대비 감축 로드맵 수립",
            "에너지 효율 개선 투자 계획 (고효율 설비, LED 조명, 압축공기 누출 관리)",
            "재생에너지 전환 계획 수립 (PPA, 녹색프리미엄, REC 구매)",
            "공장별 탄소중립 이행 점검 KPI 수립",
        ],
    },

    # ════════════════════════════════════════════
    #  5. 한국 온실가스 배출권거래제 (K-ETS)
    # ════════════════════════════════════════════
    {
        "regulation_id": "CARBON-KR-KETS-001",
        "name": "Korea Emissions Trading Scheme (K-ETS)",
        "name_ko": "온실가스 배출권의 할당 및 거래에 관한 법률 (K-ETS)",
        "issuing_org": "대한민국 환경부",
        "category": "배출권",
        "effective_date": "2015-01-01",
        "compliance_deadlines": [
            {"deadline_date": "2025-03-31", "description_ko": "2024년도 배출량 명세서 제출 기한", "scope": "K-ETS 할당 대상 업체"},
            {"deadline_date": "2025-06-30", "description_ko": "2024년도 배출권 정산(제출) 기한", "scope": "K-ETS 할당 대상 업체"},
            {"deadline_date": "2025-09-30", "description_ko": "제4차 계획기간(2026~2030) 할당 계획 확정 예상", "scope": "K-ETS 할당 대상 업체"},
            {"deadline_date": "2026-01-01", "description_ko": "제4차 계획기간 시작 — 유상할당 비율 확대 예상", "scope": "K-ETS 할당 대상 업체"},
        ],
        "key_requirements_ko": [
            "연간 온실가스 배출량 125,000 tCO2eq 이상 업체 또는 25,000 tCO2eq 이상 사업장 — 할당 대상",
            "배출권 무상할당 + 유상할당 (3차 계획기간: 유상 10% → 4차: 확대 예상)",
            "배출량 명세서 작성 및 제3자 검증 의무 (매년)",
            "배출권 거래 — KRX 배출권 시장에서 매매",
            "초과 배출 시 과징금: 배출권 시장가 x 3배 (상한 10만원/tCO2eq)",
            "외부감축사업 크레딧(KOC) 활용 가능 (상한 5%)",
        ],
        "reporting_obligations": [
            {"report_type": "온실가스 배출량 명세서", "frequency": "연간", "first_due_date": "2025-03-31", "scope_ko": "전 사업장 Scope 1·2 배출량"},
            {"report_type": "배출권 제출 (정산)", "frequency": "연간", "first_due_date": "2025-06-30", "scope_ko": "할당 배출권 대비 실제 배출량 정산"},
            {"report_type": "모니터링 계획서", "frequency": "변경 시", "first_due_date": "2025-01-31", "scope_ko": "배출량 측정·보고·검증 방법론"},
        ],
        "ajin_relevance": "아진산업 전체 사업장(경산·양산·김해·아산 등) 합산 온실가스 배출량이 K-ETS 할당 기준(125,000 tCO2eq) 해당 여부 확인 필요. 프레스(전력), 용접(전력), 도장(가스+전력) 공정이 주요 배출원. 배출권 가격 상승 시 비용 부담 증가.",
        "ajin_readiness": "진행중",
        "estimated_cost_impact_ko": "배출권 가격 약 2만원/tCO2eq 기준, 할당 초과 시 연간 5~15억원 배출권 구매 비용. 제3자 검증 비용 연 3,000~5,000만원. EU CBAM 공제 시 이중 부담 방지 효과.",
        "action_items_ko": [
            "전 사업장 합산 배출량 기준 K-ETS 할당 대상 여부 최종 확인",
            "2024년도 배출량 명세서 작성 및 제3자 검증 완료",
            "제4차 계획기간(2026~2030) 할당량 시나리오 분석",
            "배출권 구매/판매 전략 수립 (KRX 배출권 시장)",
            "내부 탄소 가격제(ICP) 도입 검토 — 투자 의사결정에 탄소 비용 반영",
        ],
    },

    # ════════════════════════════════════════════
    #  6. TCFD — 기후 관련 재무정보 공개
    # ════════════════════════════════════════════
    {
        "regulation_id": "ESG-TCFD-001",
        "name": "Task Force on Climate-related Financial Disclosures (TCFD)",
        "name_ko": "기후 관련 재무정보 공개 태스크포스 (TCFD)",
        "issuing_org": "Financial Stability Board (FSB) → ISSB 이관",
        "category": "ESG공시",
        "effective_date": "2017-06-29",
        "compliance_deadlines": [
            {"deadline_date": "2025-01-01", "description_ko": "ISSB IFRS S2(기후 공시) 기준으로 통합 — TCFD 프레임워크 사실상 의무화 확대", "scope": "ISSB 채택국 상장기업"},
            {"deadline_date": "2026-01-01", "description_ko": "한국 KSSB 지속가능성 공시기준 도입 예정 — TCFD/ISSB 기반", "scope": "한국 코스피 상장기업 (단계적)"},
        ],
        "key_requirements_ko": [
            "4대 핵심요소 공시: (1)거버넌스 (2)전략 (3)리스크관리 (4)지표·목표",
            "기후 시나리오 분석 (2도C 이하 시나리오 포함)",
            "Scope 1·2 온실가스 배출량 공시 (Scope 3 권고)",
            "기후 관련 리스크·기회 식별 및 재무적 영향 분석",
            "전환 리스크(정책, 기술, 시장, 평판) + 물리적 리스크(급성, 만성) 평가",
        ],
        "reporting_obligations": [
            {"report_type": "TCFD 보고서 / 기후 공시", "frequency": "연간", "first_due_date": "2025-06-30", "scope_ko": "상장기업 연차보고서 또는 지속가능성 보고서 내 포함"},
        ],
        "ajin_relevance": "아진산업이 코스피 상장기업으로 KSSB 기후 공시 기준 적용 대상. OEM 고객사(현대·기아 등)의 공급망 기후 리스크 평가에도 포함. 물리적 리스크(폭염 → 공장 가동 영향, 홍수 → 공급망 차질) 및 전환 리스크(탄소 규제 강화, EV 전환) 분석 필요.",
        "ajin_readiness": "미착수",
        "estimated_cost_impact_ko": "TCFD 보고서 작성 컨설팅 비용 약 5,000만~1.5억원. 기후 시나리오 분석 도구 도입 약 3,000만원. 미공시 시 ESG 평가 등급 하락 → 기관투자자 이탈 리스크.",
        "action_items_ko": [
            "기후 거버넌스 체계 구축 (이사회 ESG 위원회 설치 또는 기능 강화)",
            "기후 리스크·기회 식별 워크숍 실시 (전환/물리적 리스크)",
            "기후 시나리오 분석 실시 (1.5도C / 2도C / BAU 시나리오)",
            "Scope 1·2·3 온실가스 배출량 산정 및 목표 설정",
            "TCFD 권고안 기반 첫 기후 공시 보고서 작성 (2026년 목표)",
        ],
    },

    # ════════════════════════════════════════════
    #  7. SBTi — 과학기반감축목표
    # ════════════════════════════════════════════
    {
        "regulation_id": "ESG-SBTI-001",
        "name": "Science Based Targets initiative (SBTi)",
        "name_ko": "과학기반감축목표 이니셔티브 (SBTi)",
        "issuing_org": "CDP, UNGC, WRI, WWF 공동 운영",
        "category": "탄소규제",
        "effective_date": "2015-06-01",
        "compliance_deadlines": [
            {"deadline_date": "2025-07-31", "description_ko": "SBTi Near-term 목표 설정 기업 — 첫 진척 보고 마감 (목표 승인 후 매년)", "scope": "SBTi 참여 기업"},
            {"deadline_date": "2026-02-28", "description_ko": "SBTi FLAG(산림·토지·농업) 목표 설정 마감 — 관련 기업", "scope": "FLAG 해당 기업"},
        ],
        "key_requirements_ko": [
            "Near-term 목표: 5~10년 내 Scope 1·2 감축목표 설정 (1.5도C 경로 정렬)",
            "Long-term 목표: 2050년 이전 Net-Zero 달성 목표 설정",
            "Scope 3 배출량이 전체의 40% 이상이면 Scope 3 목표 설정 의무",
            "목표 승인 후 매년 진척도(Annual Progress) 보고",
            "목표 유효기간: 최소 5년, 최대 10년 — 이후 재설정",
        ],
        "reporting_obligations": [
            {"report_type": "SBTi 목표 제출서", "frequency": "1회 (목표 설정 시)", "first_due_date": "미정", "scope_ko": "Scope 1·2 (필수) + Scope 3 (해당 시)"},
            {"report_type": "SBTi 연간 진척 보고", "frequency": "연간", "first_due_date": "미정", "scope_ko": "목표 대비 감축 실적"},
        ],
        "ajin_relevance": "OEM 고객사(현대자동차 SBTi 참여)의 Scope 3 감축 목표 달성을 위해 공급망 협력사의 SBTi 참여 요구 증가. 아진산업 자체 SBTi 목표 설정 시 ESG 평가 가점, OEM 공급망 평가 우위 확보. 자동차 부품 업종 SBTi Sector Guidance 적용.",
        "ajin_readiness": "미착수",
        "estimated_cost_impact_ko": "SBTi 목표 설정 컨설팅 비용 약 5,000만~1억원. 감축 이행 비용은 탄소중립 투자에 포함. SBTi 참여 자체는 무료이나, 목표 검증 수수료 약 $9,500~$14,500.",
        "action_items_ko": [
            "SBTi Commitment Letter 제출 (참여 의향 표명, 24개월 내 목표 제출)",
            "Scope 1·2·3 온실가스 배출량 기준연도 인벤토리 확정",
            "SBTi Target Setting Tool 활용 감축 경로 시뮬레이션",
            "Near-term + Long-term 목표 설정 및 SBTi 검증 제출",
            "OEM 공급망 SBTi 참여 현황 모니터링 및 벤치마킹",
        ],
    },

    # ════════════════════════════════════════════
    #  8. CDP — 탄소정보공개프로젝트
    # ════════════════════════════════════════════
    {
        "regulation_id": "ESG-CDP-001",
        "name": "Carbon Disclosure Project (CDP)",
        "name_ko": "탄소정보공개프로젝트 (CDP)",
        "issuing_org": "CDP (구 Carbon Disclosure Project)",
        "category": "ESG공시",
        "effective_date": "2000-12-01",
        "compliance_deadlines": [
            {"deadline_date": "2025-07-23", "description_ko": "2025년 CDP 기후변화 질의서 제출 마감 (예상)", "scope": "CDP 응답 요청 수신 기업"},
            {"deadline_date": "2025-11-30", "description_ko": "2025년 CDP 점수 공개 (예상)", "scope": "CDP 응답 기업"},
        ],
        "key_requirements_ko": [
            "기후변화(Climate Change) 질의서: 거버넌스, 리스크·기회, 전략, 배출량, 목표",
            "물(Water Security) 질의서: 수자원 리스크, 용수 사용량, 폐수 관리",
            "산림(Forests) 질의서: 산림파괴 관련 원자재 조달 (해당 시)",
            "공급망 프로그램(CDP Supply Chain): OEM이 요청 시 협력사 의무 응답",
            "점수 등급: A (리더십) ~ D- (공시), F (미응답)",
        ],
        "reporting_obligations": [
            {"report_type": "CDP 기후변화 질의서", "frequency": "연간", "first_due_date": "2025-07-23", "scope_ko": "기업 전체 온실가스 배출, 기후 전략, 목표"},
            {"report_type": "CDP 물 안보 질의서", "frequency": "연간", "first_due_date": "2025-07-23", "scope_ko": "사업장별 용수 사용, 폐수 배출 (요청 시)"},
            {"report_type": "CDP 공급망 질의서", "frequency": "연간 (OEM 요청 시)", "first_due_date": "2025-07-23", "scope_ko": "OEM 공급망 프로그램 참여 기업"},
        ],
        "ajin_relevance": "현대자동차그룹이 CDP Supply Chain 프로그램에 참여하여 Tier 1 협력사에 CDP 응답을 요청. 아진산업은 현대·기아 핵심 협력사로 CDP 기후변화 질의서 응답 사실상 의무. CDP 점수가 OEM 공급망 평가, ESG 평가기관 등급에 직접 반영.",
        "ajin_readiness": "진행중",
        "estimated_cost_impact_ko": "CDP 응답 작성 컨설팅 비용 약 3,000만~7,000만원. 내부 데이터 수집·관리 시스템 구축 시 추가 1~2억원. CDP A등급 획득 시 ESG 투자 유치, OEM 평가 우위.",
        "action_items_ko": [
            "2025년 CDP 기후변화 질의서 응답 작성 (7월 마감)",
            "CDP 점수 향상을 위한 갭 분석 (전년도 점수 기반)",
            "Scope 3 배출량 산정 범위 확대 (카테고리 1, 4, 9 등)",
            "CDP Water Security 질의서 응답 준비 (OEM 요청 시)",
            "CDP 응답 내용과 TCFD, CSRD 보고의 일관성 확보",
        ],
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  크롤러 클래스
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CarbonESGCrawler:
    """탄소/ESG 규제 통합 크롤러"""

    def __init__(self, crawled_dir: Path | None = None):
        if crawled_dir is None:
            crawled_dir = Path(__file__).parent.parent.parent / "data" / "crawled"
        self.crawled_dir = crawled_dir
        self.crawled_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.crawled_dir / "carbon_esg.json"
        self._regulations: list[CarbonESGRegulation] = []

    # ── 크롤링 ──

    def crawl(self) -> CarbonESGCrawlResult:
        """마스터 데이터를 기반으로 탄소/ESG 규제 크롤링을 실행한다."""
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        errors: list[str] = []
        regulations: list[CarbonESGRegulation] = []

        for item in _MASTER_DATA:
            try:
                regulations.append(CarbonESGRegulation(**item, crawled_at=now))
            except Exception as e:
                errors.append(f"파싱 오류 ({item.get('regulation_id', '?')}): {e}")

        self._regulations = regulations

        # 임박 기한 집계 (향후 2년 이내)
        upcoming = []
        cutoff = (datetime.now().year + 2)
        for reg in regulations:
            for dl in reg.compliance_deadlines:
                deadline_str = dl.get("deadline_date", "9999")
                if deadline_str <= f"{cutoff}-12-31":
                    upcoming.append(dl)

        result = CarbonESGCrawlResult(
            regulations=regulations,
            crawled_at=now,
            source="ec.europa.eu + law.go.kr + tcfdhub.org + sciencebasedtargets.org + cdp.net",
            total_count=len(regulations),
            action_needed=sum(
                1 for r in regulations if r.ajin_readiness in ("미착수", "진행중")
            ),
            upcoming_deadlines=len(upcoming),
            errors=errors,
        )
        self._save(result)
        return result

    # ── 저장 / 로드 ──

    def _save(self, result: CarbonESGCrawlResult) -> None:
        """크롤링 결과를 JSON 파일로 저장한다."""
        data = {
            "crawled_at": result.crawled_at,
            "source": result.source,
            "total_count": result.total_count,
            "action_needed": result.action_needed,
            "upcoming_deadlines": result.upcoming_deadlines,
            "regulations": [asdict(r) for r in result.regulations],
            "errors": result.errors,
        }
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("탄소/ESG 규제 데이터 저장 완료: %s", self.output_path)

    def load(self) -> list[CarbonESGRegulation]:
        """저장된 JSON 파일에서 규제 목록을 로드한다."""
        if not self.output_path.exists():
            return []
        with open(self.output_path, encoding="utf-8") as f:
            data = json.load(f)
        regs = [CarbonESGRegulation(**item) for item in data.get("regulations", [])]
        self._regulations = regs
        return regs

    # ── 조회 메서드 ──

    def get_by_category(self, category: str) -> list[CarbonESGRegulation]:
        """카테고리별 규제 목록을 반환한다.

        Args:
            category: "탄소규제" | "ESG공시" | "녹색분류" | "배출권"
        """
        if not self._regulations:
            self.crawl()
        return [r for r in self._regulations if r.category == category]

    def get_action_needed(self) -> list[CarbonESGRegulation]:
        """미착수 또는 진행중인 규제 목록을 반환한다."""
        if not self._regulations:
            self.crawl()
        return [
            r for r in self._regulations
            if r.ajin_readiness in ("미착수", "진행중")
        ]

    def get_upcoming_deadlines(self) -> list[dict]:
        """전체 규제의 컴플라이언스 기한을 날짜순으로 정렬하여 반환한다."""
        if not self._regulations:
            self.crawl()
        deadlines: list[dict] = []
        for reg in self._regulations:
            for dl in reg.compliance_deadlines:
                deadlines.append({
                    "regulation": reg.name_ko,
                    "regulation_id": reg.regulation_id,
                    "category": reg.category,
                    "ajin_readiness": reg.ajin_readiness,
                    **dl,
                })
        return sorted(deadlines, key=lambda x: x.get("deadline_date", "9999"))

    def get_summary(self) -> dict:
        """전체 현황 요약을 반환한다."""
        if not self._regulations:
            self.crawl()
        return {
            "total": len(self._regulations),
            "by_category": {
                cat: len([r for r in self._regulations if r.category == cat])
                for cat in sorted(set(r.category for r in self._regulations))
            },
            "by_readiness": {
                status: len([r for r in self._regulations if r.ajin_readiness == status])
                for status in ("준비완료", "진행중", "미착수", "해당없음")
            },
            "action_needed": len(self.get_action_needed()),
            "upcoming_deadlines": len(self.get_upcoming_deadlines()),
        }
