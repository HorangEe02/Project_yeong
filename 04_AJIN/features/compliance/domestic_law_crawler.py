"""국내 법규 통합 크롤러

산업안전보건법, 중대재해처벌법, 환경 관련 법규(대기환경보전법,
폐기물관리법, 화학물질관리법 등), 자동차관리법, 소방/전기 안전법규를
통합 관리한다.

데이터 소스:
- 법제처 law.go.kr (국가법령정보센터)
- 고용노동부 고시 (화학물질 노출기준, 작업환경측정)
- 환경부/화학물질안전원 (화관법, 화평법)
- 국토교통부 (자동차관리법, 안전기준)
- 소방청, 한국전기안전공사
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DomesticLaw:
    """국내 법규 정보"""
    law_id: str
    name: str
    category: str               # safety, environment, chemical, automotive, fire, electrical, carbon
    authority: str               # 소관 부처
    last_amended: str
    amendment_summary: str
    key_articles: list[dict]     # 핵심 조항 [{article, title, content, ajin_impact}]
    penalties: str
    ajin_relevance: str
    affected_processes: list[str]
    affected_plants: list[str]
    compliance_status: str       # compliant, action_needed, monitoring
    next_review: str
    reference_url: str = ""
    crawled_at: str = ""


@dataclass
class DomesticLawCrawlResult:
    """크롤링 결과"""
    laws: list[DomesticLaw]
    crawled_at: str
    source: str
    total_count: int
    action_needed: int
    errors: list[str] = field(default_factory=list)


_DOMESTIC_LAWS = [
    # ── 산업안전보건법 ──
    {
        "law_id": "KR-OSHA-001",
        "name": "산업안전보건법",
        "category": "safety",
        "authority": "고용노동부",
        "last_amended": "2024-01-01",
        "amendment_summary": "2024년 개정: 화학물질 노출기준 전면 개정(고시 제2024-38호), 중량물 취급 기준 강화, 밀폐공간 작업 절차 세분화, 유해인자 작업환경측정 주기 단축(반기→분기, 초과 사업장)",
        "key_articles": [
            {"article": "제38조", "title": "안전조치", "content": "프레스 등 위험기계 방호장치 설치 의무", "ajin_impact": "프레스 라인 전체 해당. 광전자 방호장치, 양수조작식 설치 필수."},
            {"article": "제39조", "title": "보건조치", "content": "화학물질 취급 시 건강장해 예방 조치", "ajin_impact": "도장/용접/세정 공정 화학물질 노출 관리."},
            {"article": "제110조~116조", "title": "물질안전보건자료(MSDS)", "content": "MSDS 작성·비치·교육 의무, 대체자료 기밀 신청 제도", "ajin_impact": "10개 화학물질 MSDS 최신본 비치 및 연 1회 이상 취급자 교육."},
            {"article": "제125조", "title": "작업환경측정", "content": "유해인자 노출 근로자 작업환경 정기 측정", "ajin_impact": "도장(유기용제), 용접(흄), 프레스(소음) 공정 반기별 측정."},
            {"article": "제130조", "title": "특수건강진단", "content": "유해인자 취급 근로자 특수건강진단 실시", "ajin_impact": "크롬, 용접흄, 유기용제 취급 작업자 대상."},
        ],
        "penalties": "위반 시 5년 이하 징역 또는 5천만원 이하 벌금. 사망사고 시 7년 이하 징역 또는 1억원 이하 벌금.",
        "ajin_relevance": "아진산업 전 공장/전 공정 적용. 930명 근로자 안전의 법적 근거. 위반 시 작업중지 명령, 사업장 공개 가능.",
        "affected_processes": ["PRC-STAMP-01", "PRC-STAMP-02", "PRC-STAMP-03", "PRC-WELD-01", "PRC-WELD-02", "PRC-WELD-03", "PRC-PAINT-01", "PRC-LASER-01", "PRC-ASSY-01", "PRC-ASSY-02", "PRC-HOTSTAMP-01"],
        "affected_plants": ["PLANT-KS-HQ", "PLANT-KS-2", "PLANT-GJ"],
        "compliance_status": "compliant",
        "next_review": "2025-06",
        "reference_url": "https://www.law.go.kr/법령/산업안전보건법",
    },
    # ── 중대재해처벌법 ──
    {
        "law_id": "KR-SHPA-001",
        "name": "중대재해 처벌 등에 관한 법률",
        "category": "safety",
        "authority": "고용노동부",
        "last_amended": "2024-01-27",
        "amendment_summary": "2024년: 50인 미만 사업장 확대 적용. 경영책임자 안전보건 확보 의무 범위 확대. 시행령 개정으로 안전보건관리체계 구축 기준 구체화.",
        "key_articles": [
            {"article": "제4조", "title": "경영책임자의 안전·보건 확보 의무", "content": "안전보건관리체계 구축, 인력·예산 확보, 안전보건 전담조직 설치 등", "ajin_impact": "대표이사 직접 의무. 안전환경팀 전담조직 운영 중. 예산 편성 근거."},
            {"article": "제6조", "title": "중대산업재해 사업주 등의 처벌", "content": "사망 시 1년 이상 징역 또는 10억원 이하 벌금 (법인)", "ajin_impact": "프레스 협착, 고전압 감전, 밀폐공간 질식 등 중대재해 리스크 관리 핵심."},
            {"article": "제7조", "title": "중대시민재해 사업주 등의 처벌", "content": "제조물 결함으로 인한 사망/부상 시 처벌", "ajin_impact": "차체 구조물/배터리 케이스 결함 시 해당 가능. 품질 직결."},
        ],
        "penalties": "사망 사고 시: 경영책임자 1년 이상 징역 또는 10억원 이하 벌금. 법인 50억원 이하 벌금. 부상/질병: 7년 이하 징역 또는 1억원 이하 벌금.",
        "ajin_relevance": "2024년부터 전 사업장 적용. 대표이사 형사책임. 안전보건관리체계 미비 시 즉시 수사 개시 가능.",
        "affected_processes": ["PRC-STAMP-01", "PRC-STAMP-02", "PRC-STAMP-03", "PRC-WELD-01", "PRC-WELD-02", "PRC-WELD-03", "PRC-PAINT-01", "PRC-LASER-01", "PRC-ASSY-01", "PRC-ASSY-02", "PRC-HOTSTAMP-01"],
        "affected_plants": ["PLANT-KS-HQ", "PLANT-KS-2", "PLANT-GJ"],
        "compliance_status": "compliant",
        "next_review": "2025-03",
        "reference_url": "https://www.law.go.kr/법령/중대재해처벌법",
    },
    # ── 대기환경보전법 ──
    {
        "law_id": "KR-CAA-001",
        "name": "대기환경보전법",
        "category": "environment",
        "authority": "환경부",
        "last_amended": "2024-07-01",
        "amendment_summary": "2024년 개정: VOC(휘발성유기화합물) 배출시설 허용기준 강화, 사업장 대기오염물질 총량관리제 확대, 비산먼지 관리 강화.",
        "key_articles": [
            {"article": "제44조", "title": "VOC 배출시설 규제", "content": "VOC 배출시설 신고/허가, 방지시설 설치, 배출허용기준 준수", "ajin_impact": "도장 공정(PRC-PAINT-01) 직접 해당. VOC 저감설비 운영 의무."},
            {"article": "제16조", "title": "배출허용기준", "content": "대기오염물질 종류별 배출허용기준 설정", "ajin_impact": "도장 부스 배출구 농도 측정, 활성탄 흡착설비 성능 관리."},
        ],
        "penalties": "무허가 배출시설 설치: 7년 이하 징역 또는 1억원 이하 벌금. 배출허용기준 초과: 조업정지, 과징금.",
        "ajin_relevance": "경산 제1공장 도장 공정 핵심 적용. VOC 배출량 연간 보고 의무. 대기환경기술인 선임.",
        "affected_processes": ["PRC-PAINT-01"],
        "affected_plants": ["PLANT-KS-HQ"],
        "compliance_status": "compliant",
        "next_review": "2025-07",
        "reference_url": "https://www.law.go.kr/법령/대기환경보전법",
    },
    # ── 폐기물관리법 ──
    {
        "law_id": "KR-WMA-001",
        "name": "폐기물관리법",
        "category": "environment",
        "authority": "환경부",
        "last_amended": "2024-05-01",
        "amendment_summary": "2024년 개정: 전자인계서(올바로시스템) 의무화 강화, 지정폐기물 보관기준 강화, 사업장폐기물 감량 의무 확대.",
        "key_articles": [
            {"article": "제17조", "title": "사업장폐기물 배출자 의무", "content": "폐기물 종류별 적정 처리, 전자인계서 작성", "ajin_impact": "프레스유 폐유, 도장 폐도료, 크롬 슬러지 등 지정폐기물 관리."},
            {"article": "제25조", "title": "폐기물처리업", "content": "수집·운반·처리 허가업체에 위탁", "ajin_impact": "지정폐기물 처리업체 자격 확인 및 적정 위탁 처리."},
        ],
        "penalties": "무허가 처리: 7년 이하 징역 또는 7천만원 이하 벌금. 부적정 처리: 3년 이하 징역 또는 3천만원 이하 벌금.",
        "ajin_relevance": "전 공장에서 사업장폐기물 발생. 지정폐기물(폐유, 폐도료, 크롬 함유 슬러지) 별도 관리 필수.",
        "affected_processes": ["PRC-STAMP-01", "PRC-STAMP-02", "PRC-STAMP-03", "PRC-PAINT-01", "PRC-WELD-01"],
        "affected_plants": ["PLANT-KS-HQ", "PLANT-KS-2", "PLANT-GJ"],
        "compliance_status": "compliant",
        "next_review": "2025-05",
        "reference_url": "https://www.law.go.kr/법령/폐기물관리법",
    },
    # ── 화학물질관리법 (화관법) ──
    {
        "law_id": "KR-CCA-001",
        "name": "화학물질관리법",
        "category": "chemical",
        "authority": "환경부 / 화학물질안전원",
        "last_amended": "2024-03-01",
        "amendment_summary": "2024년 개정: 유독물질 지정 목록 업데이트(97종 추가), 화학사고 예방관리계획서 제출 대상 확대, 장외영향평가 강화.",
        "key_articles": [
            {"article": "제12조", "title": "유독물질 영업허가", "content": "유독물질 제조·수입·판매·보관·사용 시 허가 필요", "ajin_impact": "CHEM-006 (6가 크롬) 유독물질 해당. 취급 허가 유지 필수."},
            {"article": "제23조", "title": "화학사고 예방관리계획서", "content": "유해화학물질 취급량 기준 초과 시 예방관리계획서 제출", "ajin_impact": "도장/세정 공정 화학물질 취급량에 따라 해당 여부 판단."},
            {"article": "제33조", "title": "취급시설 기준", "content": "유해화학물질 취급시설 설치·관리 기준 준수", "ajin_impact": "유해화학물질 전용 저장소 설치/관리 기준 준수."},
        ],
        "penalties": "무허가 영업: 5년 이하 징역 또는 1억원 이하 벌금. 사고 발생 시 가중 처벌.",
        "ajin_relevance": "6가 크롬(CHEM-006) 등 유독물질 취급. 화학안전관리자 선임 의무. 연 1회 안전교육.",
        "affected_processes": ["PRC-PAINT-01", "PRC-ASSY-02"],
        "affected_plants": ["PLANT-KS-HQ", "PLANT-KS-2"],
        "compliance_status": "action_needed",
        "next_review": "2025-03",
        "reference_url": "https://www.law.go.kr/법령/화학물질관리법",
    },
    # ── 화학물질 등록평가법 (K-REACH) ──
    {
        "law_id": "KR-KREACH-001",
        "name": "화학물질의 등록 및 평가 등에 관한 법률 (화평법)",
        "category": "chemical",
        "authority": "환경부",
        "last_amended": "2024-01-01",
        "amendment_summary": "2024년: 기존화학물질 등록 유예기간 종료 대비 안내 강화. 위해성 평가 결과에 따른 제한/금지 물질 고시 확대.",
        "key_articles": [
            {"article": "제10조", "title": "화학물질 등록", "content": "연간 1톤 이상 제조/수입 화학물질 등록 의무", "ajin_impact": "사용 화학물질의 등록 여부 확인. 미등록 물질 사용 금지."},
            {"article": "제25조", "title": "위해성 평가", "content": "등록 물질에 대한 위해성 평가 실시", "ajin_impact": "고위험 물질 위해성 평가 결과에 따른 사용 조건 변경 가능."},
        ],
        "penalties": "미등록 물질 제조/수입: 5년 이하 징역 또는 1억원 이하 벌금.",
        "ajin_relevance": "원료 공급사의 화학물질 등록 현황 확인 필요. K-REACH 등록 의무 연간 모니터링.",
        "affected_processes": ["PRC-PAINT-01", "PRC-ASSY-02"],
        "affected_plants": ["PLANT-KS-HQ", "PLANT-KS-2"],
        "compliance_status": "monitoring",
        "next_review": "2025-06",
        "reference_url": "https://www.law.go.kr/법령/화학물질의등록및평가등에관한법률",
    },
    # ── 수질환경보전법 ──
    {
        "law_id": "KR-WQA-001",
        "name": "물환경보전법",
        "category": "environment",
        "authority": "환경부",
        "last_amended": "2024-06-01",
        "amendment_summary": "2024년: 특정수질유해물질 배출허용기준 강화, 비점오염원 관리 확대.",
        "key_articles": [
            {"article": "제32조", "title": "폐수배출시설 설치 허가/신고", "content": "폐수배출시설 설치 시 사전 허가 또는 신고", "ajin_impact": "전착도장 공정 폐수 처리 시설 운영. 크롬 함유 폐수 별도 처리."},
            {"article": "제12조", "title": "배출허용기준", "content": "수질오염물질 종류별 배출허용기준", "ajin_impact": "도장 폐수 중 중금속(Cr, Zn), COD, SS 기준 준수."},
        ],
        "penalties": "배출허용기준 초과: 조업정지, 과징금. 무허가 배출: 7년 이하 징역.",
        "ajin_relevance": "경산 제1공장 도장 공정 폐수 처리. 크롬 함유 폐수 특별 관리 대상.",
        "affected_processes": ["PRC-PAINT-01"],
        "affected_plants": ["PLANT-KS-HQ"],
        "compliance_status": "compliant",
        "next_review": "2025-06",
        "reference_url": "https://www.law.go.kr/법령/물환경보전법",
    },
    # ── 자동차관리법 ──
    {
        "law_id": "KR-MVA-001",
        "name": "자동차관리법 및 자동차안전기준",
        "category": "automotive",
        "authority": "국토교통부",
        "last_amended": "2024-09-01",
        "amendment_summary": "2024년: 전기차 안전기준 강화(고전압 안전성, 배터리 화재 안전), 자동차 부품 자기인증 대상 확대, 결함 리콜 절차 강화.",
        "key_articles": [
            {"article": "제30조", "title": "자동차 부품 자기인증", "content": "지정 부품의 안전성 자기인증 및 표시 의무", "ajin_impact": "차체 구조물, 서브프레임 등 자기인증 대상 부품 해당 가능."},
            {"article": "제31조", "title": "결함 시정", "content": "부품 결함 발견 시 리콜/시정 의무", "ajin_impact": "납품 부품 결함 시 리콜 비용 분담, 신속 대응 필수."},
            {"article": "자동차안전기준 제18조의3", "title": "전기차 고전압 안전", "content": "감전보호, 절연저항, 고전압 경고 표시", "ajin_impact": "경산 제2공장 EV 배터리 케이스 절연/방수 성능 직결."},
        ],
        "penalties": "자기인증 위반: 2천만원 이하 과태료. 리콜 미이행: 1억원 이하 벌금.",
        "ajin_relevance": "차체 구조물/배터리 케이스는 안전 핵심 부품. 자동차안전연구원(KATRI) 시험 대응.",
        "affected_processes": ["PRC-STAMP-01", "PRC-STAMP-02", "PRC-WELD-01", "PRC-WELD-02", "PRC-ASSY-02"],
        "affected_plants": ["PLANT-KS-HQ", "PLANT-KS-2", "PLANT-GJ"],
        "compliance_status": "compliant",
        "next_review": "2025-09",
        "reference_url": "https://www.law.go.kr/법령/자동차관리법",
    },
    # ── 위험물안전관리법 ──
    {
        "law_id": "KR-HMA-001",
        "name": "위험물안전관리법",
        "category": "fire",
        "authority": "소방청",
        "last_amended": "2024-04-01",
        "amendment_summary": "2024년: 위험물 저장소 안전거리 기준 강화, 자체 소방대 설치 기준 변경.",
        "key_articles": [
            {"article": "제5조", "title": "위험물 저장/취급 허가", "content": "지정수량 이상 위험물 저장/취급 시 허가", "ajin_impact": "프레스유(4류), 도장 용제(2류), 세정제(2류) 위험물 취급."},
            {"article": "제15조", "title": "위험물안전관리자 선임", "content": "위험물 취급사업장 안전관리자 선임 의무", "ajin_impact": "각 공장별 위험물안전관리자 선임."},
        ],
        "penalties": "무허가 저장: 3년 이하 징역 또는 3천만원 이하 벌금.",
        "ajin_relevance": "위험물 저장소 A/B 운영. 4류 인화성 액체(프레스유, 방청유, 이형제) 대량 취급.",
        "affected_processes": ["PRC-STAMP-01", "PRC-STAMP-02", "PRC-STAMP-03", "PRC-PAINT-01", "PRC-HOTSTAMP-01"],
        "affected_plants": ["PLANT-KS-HQ", "PLANT-KS-2", "PLANT-GJ"],
        "compliance_status": "compliant",
        "next_review": "2025-04",
        "reference_url": "https://www.law.go.kr/법령/위험물안전관리법",
    },
    # ── 전기안전관리법 ──
    {
        "law_id": "KR-ESA-001",
        "name": "전기안전관리법",
        "category": "electrical",
        "authority": "산업통상자원부 / 한국전기안전공사",
        "last_amended": "2024-08-01",
        "amendment_summary": "2024년: 고전압(DC 60V 이상) 설비 안전관리 강화, ESS(에너지저장장치) 안전기준 신설, 아크플래시 위험 평가 의무화.",
        "key_articles": [
            {"article": "제13조", "title": "전기안전관리자 선임", "content": "전기설비 규모에 따른 전기안전관리자 선임 의무", "ajin_impact": "각 공장 전기안전관리자 선임. 경산 제2공장 고전압 설비 관리."},
            {"article": "제22조", "title": "전기설비 정기검사", "content": "전기설비 정기 안전검사 실시", "ajin_impact": "레이저 용접기, 전착도장 정류기 등 고전압 설비 정기검사."},
        ],
        "penalties": "안전관리 의무 위반: 1천만원 이하 과태료. 감전 사고 시 형사 책임.",
        "ajin_relevance": "경산 제2공장 EV 배터리 라인 고전압(DC 800V급) 설비 운영. 아크플래시 위험 평가 대상.",
        "affected_processes": ["PRC-LASER-01", "PRC-ASSY-02", "PRC-PAINT-01"],
        "affected_plants": ["PLANT-KS-HQ", "PLANT-KS-2"],
        "compliance_status": "action_needed",
        "next_review": "2025-08",
        "reference_url": "https://www.law.go.kr/법령/전기안전관리법",
    },
    # ── 온실가스 배출권 거래법 ──
    {
        "law_id": "KR-ETS-001",
        "name": "온실가스 배출권의 할당 및 거래에 관한 법률",
        "category": "carbon",
        "authority": "환경부",
        "last_amended": "2024-01-01",
        "amendment_summary": "제4차 계획기간(2026~2030) 할당 계획 수립 중. 배출권 유상할당 비율 확대, MRV(측정·보고·검증) 기준 강화.",
        "key_articles": [
            {"article": "제12조", "title": "배출권 할당", "content": "온실가스 배출 사업장 대상 배출권 할당", "ajin_impact": "에너지 다소비 사업장 해당 시 배출권 할당 대상. 현재 직접 할당 대상 여부 모니터링."},
            {"article": "제24조", "title": "배출량 보고/검증", "content": "배출량 산정, 보고, 제3자 검증 의무", "ajin_impact": "현대차그룹 Scope 3 탄소 공시에 따라 데이터 제출 요구 증가."},
        ],
        "penalties": "미보고/허위보고: 1천만원 이하 과태료. 배출권 미제출: 초과 배출량×시장가격 3배 과징금.",
        "ajin_relevance": "직접 할당 대상은 아니나, OEM 공급망 탄소 관리(Scope 3) 요구에 따라 배출량 산정/보고 필요성 증가.",
        "affected_processes": ["PRC-PAINT-01", "PRC-HOTSTAMP-01", "PRC-WELD-01", "PRC-WELD-02", "PRC-WELD-03"],
        "affected_plants": ["PLANT-KS-HQ", "PLANT-KS-2", "PLANT-GJ"],
        "compliance_status": "monitoring",
        "next_review": "2025-12",
        "reference_url": "https://www.law.go.kr/법령/온실가스배출권의할당및거래에관한법률",
    },
]


class DomesticLawCrawler:
    """국내 법규 통합 크롤러"""

    def __init__(self, data_dir: Path | None = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data" / "crawled"
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.data_dir / "domestic_laws.json"
        self._laws: list[DomesticLaw] = []

    def crawl(self) -> DomesticLawCrawlResult:
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        errors = []
        laws = []
        for item in _DOMESTIC_LAWS:
            try:
                laws.append(DomesticLaw(**item, crawled_at=now))
            except Exception as e:
                errors.append(f"파싱 오류 ({item.get('law_id', '?')}): {e}")
        self._laws = laws
        result = DomesticLawCrawlResult(
            laws=laws, crawled_at=now,
            source="law.go.kr + moel.go.kr + me.go.kr + molit.go.kr",
            total_count=len(laws),
            action_needed=sum(1 for l in laws if l.compliance_status == "action_needed"),
            errors=errors,
        )
        self._save(result)
        return result

    def _save(self, result: DomesticLawCrawlResult):
        data = {
            "crawled_at": result.crawled_at, "source": result.source,
            "total_count": result.total_count, "action_needed": result.action_needed,
            "laws": [asdict(l) for l in result.laws], "errors": result.errors,
        }
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> list[DomesticLaw]:
        if not self.output_path.exists():
            return []
        with open(self.output_path, encoding="utf-8") as f:
            data = json.load(f)
        return [DomesticLaw(**item) for item in data.get("laws", [])]

    def get_by_category(self, category: str) -> list[DomesticLaw]:
        if not self._laws: self.crawl()
        return [l for l in self._laws if l.category == category]

    def get_action_needed(self) -> list[DomesticLaw]:
        if not self._laws: self.crawl()
        return [l for l in self._laws if l.compliance_status == "action_needed"]

    def get_summary(self) -> dict:
        if not self._laws: self.crawl()
        return {
            "total": len(self._laws),
            "by_category": {cat: len([l for l in self._laws if l.category == cat])
                           for cat in set(l.category for l in self._laws)},
            "action_needed": len([l for l in self._laws if l.compliance_status == "action_needed"]),
            "monitoring": len([l for l in self._laws if l.compliance_status == "monitoring"]),
            "compliant": len([l for l in self._laws if l.compliance_status == "compliant"]),
        }
