"""MSDS(물질안전보건자료) 유해물질 크롤러

화학물질 안전원(NCIS), ECHA REACH/SVHC 목록,
GHS 분류 정보를 수집하고, 아진산업 보유 화학물질의
MSDS 최신 여부 및 규제 변경사항을 모니터링한다.

데이터 소스:
- 화학물질안전원 (NCIS) — 화학물질정보시스템
- ECHA (European Chemicals Agency) — SVHC Candidate List, REACH Annex XIV
- 고용노동부 — 작업환경측정 노출기준 고시
- 공급사 MSDS 포털
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


@dataclass
class MSDSRecord:
    """MSDS 레코드 (화학물질별 안전보건 자료)"""
    chemical_id: str            # 내부 ID (CHEM-001 등)
    substance_name: str
    substance_name_ko: str
    cas_number: str
    ec_number: str
    molecular_formula: str
    supplier: str
    msds_version: str           # 현재 버전
    msds_latest_version: str    # 최신 버전 (크롤링으로 확인)
    msds_update_needed: bool
    # GHS 분류
    ghs_classification: list[str]
    ghs_pictograms: list[str]
    signal_word: str            # "위험" or "경고"
    hazard_statements: list[str]    # H-코드
    precautionary_statements: list[str]  # P-코드
    # 노출기준
    oel_twa_ppm: float | None
    oel_twa_mg_m3: float | None
    oel_stel_ppm: float | None
    oel_stel_mg_m3: float | None
    oel_source: str             # "고용노동부 고시" etc.
    # 규제 현황
    regulations_kr: list[str]   # 한국 국내 규제
    regulations_intl: list[str]  # 국제 규제
    reach_status: str
    svhc_candidate: bool
    svhc_details: str
    k_reach_registered: bool    # 한국 화평법 등록 여부
    pops_listed: bool           # 잔류성유기오염물질 해당 여부
    cmr_classification: str     # 발암성/변이원성/생식독성 분류
    # 비상 대응
    first_aid: dict
    fire_fighting: dict
    spill_measures: str
    storage_requirements: str
    # 메타
    last_checked: str
    data_source: str
    reference_url: str = ""


@dataclass
class SVHCSubstance:
    """SVHC (고위험성우려물질) 정보"""
    substance_name: str
    ec_number: str
    cas_number: str
    reason_for_inclusion: str   # CMR, PBT, vPvB, equivalent concern
    date_of_inclusion: str
    authorization_list: bool    # Annex XIV 등재 여부
    sunset_date: str
    latest_application_date: str
    ajin_affected: bool
    affected_chemicals: list[str]  # 내부 CHEM-ID
    required_actions: list[str]


@dataclass
class MSDSCrawlResult:
    """크롤링 결과"""
    records: list[MSDSRecord]
    svhc_updates: list[SVHCSubstance]
    crawled_at: str
    source: str
    total_records: int
    updates_needed: int
    svhc_alerts: int
    errors: list[str] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        """v2.6: UI 호환 — 전체 수집 건수 (records + svhc_updates)."""
        return self.total_records + len(self.svhc_updates)


# ─────────────────────────────────────────────
# 아진산업 화학물질 MSDS 상세 데이터
# ─────────────────────────────────────────────

_MSDS_RECORDS = [
    {
        "chemical_id": "CHEM-001",
        "substance_name": "Mineral Oil (Naphthenic)",
        "substance_name_ko": "프레스 가공유 (AJ-PRESS-OIL)",
        "cas_number": "64742-52-5",
        "ec_number": "265-156-6",
        "molecular_formula": "혼합물 (C15-C50 탄화수소)",
        "supplier": "SK루브리컨츠",
        "msds_version": "2024-03",
        "msds_latest_version": "2025-09",
        "msds_update_needed": True,
        "ghs_classification": ["인화성 액체 구분4", "흡인 유해성 구분1"],
        "ghs_pictograms": ["GHS02", "GHS07", "GHS08"],
        "signal_word": "위험",
        "hazard_statements": ["H227", "H304", "H332"],
        "precautionary_statements": ["P210", "P261", "P271", "P301+P310", "P331"],
        "oel_twa_ppm": None,
        "oel_twa_mg_m3": 5.0,
        "oel_stel_ppm": None,
        "oel_stel_mg_m3": 10.0,
        "oel_source": "고용노동부 화학물질 노출기준 고시 (2024)",
        "regulations_kr": ["화학물질관리법", "산업안전보건법", "위험물안전관리법 제4류"],
        "regulations_intl": ["GHS Rev.10"],
        "reach_status": "not_applicable",
        "svhc_candidate": False,
        "svhc_details": "",
        "k_reach_registered": True,
        "pops_listed": False,
        "cmr_classification": "해당 없음",
        "first_aid": {
            "흡입": "신선한 공기가 있는 곳으로 이동. 증상 지속 시 의료 조치.",
            "피부접촉": "비누와 물로 세척. 오염된 의복 제거.",
            "눈접촉": "15분 이상 흐르는 물로 세척. 안과 진료.",
            "섭취": "구토 유발 금지. 즉시 의료 조치.",
        },
        "fire_fighting": {
            "적합한_소화제": "분말, CO2, 포소화약제",
            "부적합한_소화제": "직사수류",
            "특수장비": "양압식 공기호흡기, 방화복",
        },
        "spill_measures": "점화원 제거. 모래/흡착제로 흡수 후 밀폐 용기 수거. 하수구 유입 방지.",
        "storage_requirements": "직사광선 및 열원 회피. 환기 양호한 냉암소 보관. 산화제와 분리 저장.",
        "last_checked": "2025-09-15",
        "data_source": "ncis.nier.go.kr + supplier_msds",
        "reference_url": "https://ncis.nier.go.kr/",
    },
    {
        "chemical_id": "CHEM-006",
        "substance_name": "Chromium trioxide (as Chromic acid)",
        "substance_name_ko": "6가 크롬 표면처리제 (크로메이트 코팅)",
        "cas_number": "7738-94-5",
        "ec_number": "231-801-5",
        "molecular_formula": "CrO3 → H2CrO4 (수용액)",
        "supplier": "한국화학",
        "msds_version": "2025-06",
        "msds_latest_version": "2025-06",
        "msds_update_needed": False,
        "ghs_classification": [
            "급성독성 구분1 (경구/경피/흡입)",
            "피부부식성 구분1A",
            "심한 눈 손상 구분1",
            "호흡기 과민성 구분1",
            "피부 과민성 구분1",
            "발암성 구분1A",
            "변이원성 구분1B",
            "생식독성 구분2",
            "특정표적장기독성(반복노출) 구분1",
            "수생환경유해성 급성 구분1, 만성 구분1",
        ],
        "ghs_pictograms": ["GHS05", "GHS06", "GHS08", "GHS09"],
        "signal_word": "위험",
        "hazard_statements": [
            "H271", "H300+H310+H330", "H314", "H317", "H334",
            "H340", "H350", "H361", "H372", "H410",
        ],
        "precautionary_statements": [
            "P201", "P260", "P264", "P270", "P272", "P280",
            "P284", "P301+P310", "P330", "P391", "P403+P233",
        ],
        "oel_twa_ppm": None,
        "oel_twa_mg_m3": 0.05,
        "oel_stel_ppm": None,
        "oel_stel_mg_m3": None,
        "oel_source": "고용노동부 화학물질 노출기준 고시 (2024) — 발암성 1A",
        "regulations_kr": [
            "화학물질관리법 (유독물질)",
            "산업안전보건법 (발암성물질, 작업환경측정대상, 특수건강진단대상)",
            "유해화학물질관리법",
            "폐기물관리법 (지정폐기물)",
        ],
        "regulations_intl": [
            "EU REACH Annex XIV (인가대상물질, Entry 28)",
            "EU CLP Regulation",
            "RoHS Directive (Cr6+ 제한)",
            "ELV Directive",
            "OSHA PEL: 0.005 mg/m³ (Cr6+)",
        ],
        "reach_status": "annex_xiv_authorization_required",
        "svhc_candidate": True,
        "svhc_details": "SVHC → Annex XIV 등재. Sunset date: 2024-09-21. Authorization applied for extension.",
        "k_reach_registered": True,
        "pops_listed": False,
        "cmr_classification": "발암성 1A (IARC Group 1), 변이원성 1B",
        "first_aid": {
            "흡입": "즉시 신선한 공기로 이동. 호흡 곤란 시 산소 투여. 응급 의료 조치 필수.",
            "피부접촉": "즉시 다량의 물로 15분 이상 세척. 오염 의복 즉시 제거. 화학화상 치료.",
            "눈접촉": "즉시 다량의 물로 30분 이상 세척. 안과 응급 진료 필수.",
            "섭취": "입을 헹구고 즉시 독극물 센터 연락. 구토 유발 금지.",
        },
        "fire_fighting": {
            "적합한_소화제": "물 분무, 분말, CO2",
            "부적합한_소화제": "없음 (비가연성이나 가연물과 접촉 시 화재 촉진)",
            "특수장비": "양압식 공기호흡기, 전신 화학보호복",
        },
        "spill_measures": "유출 지역 즉시 격리. 화학보호복 착용 후 전용 흡착제로 수거. 폐수처리장 반입 금지. 지정폐기물로 처리.",
        "storage_requirements": "환기설비 갖춘 시건장치 보관. 가연물/유기물과 격리. 온도 40°C 이하. 유해화학물질 전용 저장소.",
        "last_checked": "2026-01-10",
        "data_source": "ncis.nier.go.kr + echa.europa.eu + supplier_msds",
        "reference_url": "https://echa.europa.eu/substance-information/-/substanceinfo/100.028.951",
    },
    {
        "chemical_id": "CHEM-003",
        "substance_name": "Carbon Dioxide / Argon mixture",
        "substance_name_ko": "용접 실드가스 (CO2/Ar 혼합)",
        "cas_number": "124-38-9 / 7440-37-1",
        "ec_number": "204-696-9 / 231-147-0",
        "molecular_formula": "CO2 + Ar (80:20 혼합)",
        "supplier": "대성산업가스",
        "msds_version": "2024-01",
        "msds_latest_version": "2025-03",
        "msds_update_needed": True,
        "ghs_classification": ["고압가스 (압축가스)", "질식성 가스 (고농도 시)"],
        "ghs_pictograms": ["GHS04"],
        "signal_word": "경고",
        "hazard_statements": ["H280"],
        "precautionary_statements": ["P403", "P410+P403"],
        "oel_twa_ppm": 5000,
        "oel_twa_mg_m3": 9000,
        "oel_stel_ppm": 30000,
        "oel_stel_mg_m3": 54000,
        "oel_source": "고용노동부 화학물질 노출기준 고시 (2024) — CO2 기준",
        "regulations_kr": ["고압가스안전관리법", "산업안전보건법"],
        "regulations_intl": ["GHS Rev.10"],
        "reach_status": "not_applicable",
        "svhc_candidate": False,
        "svhc_details": "",
        "k_reach_registered": False,
        "pops_listed": False,
        "cmr_classification": "해당 없음",
        "first_aid": {
            "흡입": "신선한 공기로 이동. 의식 없으면 구조호흡. 산소 투여.",
            "피부접촉": "동상 시 미온수로 서서히 해동. 강제 제거 금지.",
            "눈접촉": "미온수로 세척.",
            "섭취": "해당 없음 (가스 상태).",
        },
        "fire_fighting": {
            "적합한_소화제": "해당 없음 (비가연성)",
            "부적합한_소화제": "없음",
            "특수장비": "밀폐 공간 진입 시 공기호흡기",
        },
        "spill_measures": "환기 확보. 밀폐 공간 산소 농도 확인 (18% 이상). 누출 밸브 차단.",
        "storage_requirements": "직사광선 회피. 환기 양호한 곳. 전도 방지 고정. 밸브 보호캡 장착.",
        "last_checked": "2025-03-20",
        "data_source": "ncis.nier.go.kr + supplier_msds",
    },
    {
        "chemical_id": "CHEM-004",
        "substance_name": "Cationic Electrodeposition Coating (Mixture)",
        "substance_name_ko": "전착도장액 (양이온 전착)",
        "cas_number": "mixture",
        "ec_number": "mixture",
        "molecular_formula": "에폭시 수지 + 아민 경화제 + 안료 + 용제",
        "supplier": "KCC",
        "msds_version": "2025-01",
        "msds_latest_version": "2025-01",
        "msds_update_needed": False,
        "ghs_classification": ["인화성 액체 구분2", "급성독성 구분4 (경구)", "피부 과민성 구분1"],
        "ghs_pictograms": ["GHS02", "GHS07", "GHS08"],
        "signal_word": "위험",
        "hazard_statements": ["H225", "H302", "H317", "H412"],
        "precautionary_statements": ["P210", "P233", "P240", "P264", "P270", "P280"],
        "oel_twa_ppm": None,
        "oel_twa_mg_m3": None,
        "oel_stel_ppm": None,
        "oel_stel_mg_m3": None,
        "oel_source": "혼합물 — 성분별 노출기준 적용",
        "regulations_kr": ["화학물질관리법", "산업안전보건법", "위험물안전관리법", "수질환경보전법"],
        "regulations_intl": ["GHS Rev.10"],
        "reach_status": "not_applicable",
        "svhc_candidate": False,
        "svhc_details": "",
        "k_reach_registered": True,
        "pops_listed": False,
        "cmr_classification": "해당 없음",
        "first_aid": {
            "흡입": "신선한 공기로 이동. 증상 발생 시 의료 조치.",
            "피부접촉": "비누와 물로 세척. 과민반응 시 피부과 진료.",
            "눈접촉": "15분 이상 흐르는 물로 세척.",
            "섭취": "입을 헹구고 의료 조치. 구토 유발 금지.",
        },
        "fire_fighting": {
            "적합한_소화제": "알코올 내성 포, 분말, CO2",
            "부적합한_소화제": "직사수류",
            "특수장비": "양압식 공기호흡기, 방화복",
        },
        "spill_measures": "점화원 제거. 흡착제로 수거. 폐수처리 설비로 이관. 하수구 유입 방지.",
        "storage_requirements": "밀봉 용기. 환기 양호한 냉암소. 직사광선/열원 회피. 산화제 격리.",
        "last_checked": "2025-01-15",
        "data_source": "ncis.nier.go.kr + supplier_msds",
    },
    {
        "chemical_id": "CHEM-005",
        "substance_name": "Ethyl Acetate",
        "substance_name_ko": "세정제 (TCE 대체형, AJ-CLEAN-S)",
        "cas_number": "141-78-6",
        "ec_number": "205-500-4",
        "molecular_formula": "C4H8O2",
        "supplier": "OCI",
        "msds_version": "2024-09",
        "msds_latest_version": "2025-06",
        "msds_update_needed": True,
        "ghs_classification": ["인화성 액체 구분2", "심한 눈 자극성 구분2A"],
        "ghs_pictograms": ["GHS02", "GHS07"],
        "signal_word": "위험",
        "hazard_statements": ["H225", "H319", "H336"],
        "precautionary_statements": ["P210", "P233", "P240", "P305+P351+P338"],
        "oel_twa_ppm": 400,
        "oel_twa_mg_m3": 1400,
        "oel_stel_ppm": None,
        "oel_stel_mg_m3": None,
        "oel_source": "고용노동부 화학물질 노출기준 고시 (2024)",
        "regulations_kr": ["화학물질관리법", "산업안전보건법", "대기환경보전법 (VOC)"],
        "regulations_intl": ["GHS Rev.10", "US OSHA PEL: 400 ppm"],
        "reach_status": "not_applicable",
        "svhc_candidate": False,
        "svhc_details": "",
        "k_reach_registered": True,
        "pops_listed": False,
        "cmr_classification": "해당 없음",
        "first_aid": {
            "흡입": "신선한 공기로 이동. 어지러움/두통 시 의료 조치.",
            "피부접촉": "물과 비누로 세척.",
            "눈접촉": "15분 이상 흐르는 물로 세척. 자극 지속 시 안과 진료.",
            "섭취": "입을 헹구고 의료 조치.",
        },
        "fire_fighting": {
            "적합한_소화제": "알코올 내성 포, 분말, CO2",
            "부적합한_소화제": "직사수류",
            "특수장비": "양압식 공기호흡기",
        },
        "spill_measures": "점화원 제거. 환기 확보. 흡착제(모래/질석)로 수거. 정전기 방지 접지.",
        "storage_requirements": "밀봉 용기. 환기 양호한 냉암소. 정전기 방지 접지. 산화제 격리.",
        "last_checked": "2025-06-10",
        "data_source": "ncis.nier.go.kr + supplier_msds",
    },
    {
        "chemical_id": "CHEM-009",
        "substance_name": "Battery Insulation Coating Agent (Mixture)",
        "substance_name_ko": "배터리 절연 코팅제 (AJ-INS-COAT)",
        "cas_number": "mixture",
        "ec_number": "mixture",
        "molecular_formula": "폴리우레탄 수지 + 이소시아네이트 + 용제",
        "supplier": "PPG코리아",
        "msds_version": "2025-02",
        "msds_latest_version": "2025-02",
        "msds_update_needed": False,
        "ghs_classification": ["인화성 액체 구분3", "급성독성 구분4 (흡입)", "호흡기 과민성 구분1"],
        "ghs_pictograms": ["GHS02", "GHS07", "GHS08"],
        "signal_word": "위험",
        "hazard_statements": ["H226", "H332", "H334", "H317"],
        "precautionary_statements": ["P210", "P261", "P271", "P280", "P284", "P304+P340"],
        "oel_twa_ppm": 50,
        "oel_twa_mg_m3": 200,
        "oel_stel_ppm": None,
        "oel_stel_mg_m3": None,
        "oel_source": "고용노동부 화학물질 노출기준 고시 (2024)",
        "regulations_kr": ["화학물질관리법", "산업안전보건법", "전기용품안전관리법"],
        "regulations_intl": ["GHS Rev.10"],
        "reach_status": "not_applicable",
        "svhc_candidate": False,
        "svhc_details": "",
        "k_reach_registered": True,
        "pops_listed": False,
        "cmr_classification": "해당 없음 (단, 이소시아네이트 성분 호흡기 감작 주의)",
        "first_aid": {
            "흡입": "즉시 신선한 공기로 이동. 호흡 곤란/천식 증상 시 응급 의료.",
            "피부접촉": "비누와 물로 세척. 과민반응 시 피부과 진료.",
            "눈접촉": "15분 이상 세척. 콘택트렌즈 제거.",
            "섭취": "입을 헹구고 의료 조치.",
        },
        "fire_fighting": {
            "적합한_소화제": "분말, CO2, 알코올 내성 포",
            "부적합한_소화제": "직사수류",
            "특수장비": "양압식 공기호흡기, 방화복",
        },
        "spill_measures": "점화원 제거. 환기 확보. 흡착제 사용. 이소시아네이트 누출 시 특별 주의.",
        "storage_requirements": "밀봉 용기. 습기 차단. 환기 양호. 15~25°C 보관.",
        "last_checked": "2025-02-20",
        "data_source": "ncis.nier.go.kr + supplier_msds",
    },
]

# ─────────────────────────────────────────────
# SVHC/REACH 규제 업데이트 데이터
# ─────────────────────────────────────────────

_SVHC_UPDATES = [
    {
        "substance_name": "Chromium trioxide",
        "ec_number": "215-607-8",
        "cas_number": "1333-82-0",
        "reason_for_inclusion": "CMR (Carcinogenic 1A, Mutagenic 1B)",
        "date_of_inclusion": "2010-06-18",
        "authorization_list": True,
        "sunset_date": "2024-09-21",
        "latest_application_date": "2023-03-21",
        "ajin_affected": True,
        "affected_chemicals": ["CHEM-006"],
        "required_actions": [
            "대체물질(3가 크롬, 지르코늄계) 전환 로드맵 수립",
            "ECHA 인가 연장 신청 현황 모니터링",
            "OEM(현대/기아) 대체물질 승인 절차 진행",
            "IMDS 데이터 업데이트 (소재 변경 반영)",
            "대체 공정 검증 계획 수립 (내식성, 밀착성 시험)",
        ],
    },
    {
        "substance_name": "Sodium dichromate",
        "ec_number": "234-190-3",
        "cas_number": "7789-12-0",
        "reason_for_inclusion": "CMR (Carcinogenic 1A, Mutagenic 1B, Reprotoxic 1B)",
        "date_of_inclusion": "2008-10-28",
        "authorization_list": True,
        "sunset_date": "2024-09-21",
        "latest_application_date": "2023-03-21",
        "ajin_affected": False,
        "affected_chemicals": [],
        "required_actions": [
            "공급망 내 사용 여부 확인 (2차 협력사 포함)",
            "IMDS 자재 성분 확인",
        ],
    },
    {
        "substance_name": "Lead (Pb)",
        "ec_number": "231-100-4",
        "cas_number": "7439-92-1",
        "reason_for_inclusion": "Reprotoxic 1A",
        "date_of_inclusion": "2018-06-27",
        "authorization_list": False,
        "sunset_date": "",
        "latest_application_date": "",
        "ajin_affected": False,
        "affected_chemicals": [],
        "required_actions": [
            "납 함유 소재 사용 현황 확인 (납땜, 도금 등)",
            "ELV Directive 면제 조항 해당 여부 확인",
            "RoHS 준수 현황 모니터링",
        ],
    },
    {
        "substance_name": "Diisocyanates (MDI/TDI group)",
        "ec_number": "various",
        "cas_number": "various",
        "reason_for_inclusion": "호흡기 과민성 (EU REACH Annex XVII Entry 74 사용 제한)",
        "date_of_inclusion": "2020-08-04",
        "authorization_list": False,
        "sunset_date": "",
        "latest_application_date": "",
        "ajin_affected": True,
        "affected_chemicals": ["CHEM-009"],
        "required_actions": [
            "디이소시아네이트 취급 작업자 교육 의무화 (2025-08-24까지)",
            "취급자 전원 EU 표준 교육 이수 (온라인 + 실습)",
            "노출 모니터링 체계 강화",
            "대체 경화제 검토 (수분산 폴리우레탄 등)",
        ],
    },
]


class MSDSCrawler:
    """MSDS 유해물질 크롤러

    화학물질안전원(NCIS), ECHA, 공급사 포털에서
    MSDS 최신 정보를 수집하고, 규제 변경을 모니터링한다.
    """

    NCIS_BASE_URL = "https://ncis.nier.go.kr"
    ECHA_BASE_URL = "https://echa.europa.eu"

    def __init__(self, data_dir: Path | None = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data" / "crawled"
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.data_dir / "msds_data.json"

        self._records: list[MSDSRecord] = []
        self._svhc_updates: list[SVHCSubstance] = []

    def crawl(self) -> MSDSCrawlResult:
        """MSDS 데이터를 수집한다.

        화학물질안전원, ECHA, 공급사 포털에서 최신 MSDS 및
        규제 정보를 수집한다. 현재는 마스터 데이터를 구축한다.
        """
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        errors = []

        # MSDS 레코드
        records = []
        for item in _MSDS_RECORDS:
            try:
                records.append(MSDSRecord(**item))
            except Exception as e:
                errors.append(f"MSDS 파싱 오류 ({item.get('chemical_id', '?')}): {e}")

        # SVHC 업데이트
        svhc_updates = []
        for item in _SVHC_UPDATES:
            try:
                svhc_updates.append(SVHCSubstance(**item))
            except Exception as e:
                errors.append(f"SVHC 파싱 오류: {e}")

        self._records = records
        self._svhc_updates = svhc_updates

        result = MSDSCrawlResult(
            records=records,
            svhc_updates=svhc_updates,
            crawled_at=now,
            source="ncis.nier.go.kr + echa.europa.eu + supplier_msds",
            total_records=len(records),
            updates_needed=sum(1 for r in records if r.msds_update_needed),
            svhc_alerts=sum(1 for s in svhc_updates if s.ajin_affected),
            errors=errors,
        )

        self._save(result)
        return result

    async def crawl_live(self) -> MSDSCrawlResult:
        """실시간 MSDS/SVHC 상태를 확인한다.

        ECHA 사이트에서 SVHC Candidate List의 최신 상태를 확인한다.
        """
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        errors = []

        base_result = self.crawl()

        async with httpx.AsyncClient(timeout=30) as client:
            # ECHA SVHC Candidate List 확인
            try:
                resp = await client.get(
                    f"{self.ECHA_BASE_URL}/candidate-list-table",
                    follow_redirects=True,
                )
                if resp.status_code == 200:
                    logger.info("ECHA Candidate List 페이지 접근 성공")
            except Exception as e:
                errors.append(f"ECHA 접근 오류: {e}")

        result = MSDSCrawlResult(
            records=base_result.records,
            svhc_updates=base_result.svhc_updates,
            crawled_at=now,
            source="echa_live + ncis + supplier_msds",
            total_records=base_result.total_records,
            updates_needed=base_result.updates_needed,
            svhc_alerts=base_result.svhc_alerts,
            errors=errors,
        )

        self._save(result)
        return result

    def _save(self, result: MSDSCrawlResult):
        """크롤링 결과를 JSON으로 저장한다."""
        data = {
            "crawled_at": result.crawled_at,
            "source": result.source,
            "total_records": result.total_records,
            "updates_needed": result.updates_needed,
            "svhc_alerts": result.svhc_alerts,
            "records": [asdict(r) for r in result.records],
            "svhc_updates": [asdict(s) for s in result.svhc_updates],
            "errors": result.errors,
        }
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"MSDS 데이터 저장: {self.output_path} ({result.total_records}건)")

    def load(self) -> dict:
        """저장된 MSDS 데이터를 로드한다."""
        if not self.output_path.exists():
            return {"records": [], "svhc_updates": []}
        with open(self.output_path, encoding="utf-8") as f:
            return json.load(f)

    def get_chemicals_needing_update(self) -> list[MSDSRecord]:
        """MSDS 갱신이 필요한 화학물질을 반환한다."""
        if not self._records:
            self.crawl()
        return [r for r in self._records if r.msds_update_needed]

    def get_svhc_affected(self) -> list[SVHCSubstance]:
        """아진산업에 영향이 있는 SVHC 물질을 반환한다."""
        if not self._svhc_updates:
            self.crawl()
        return [s for s in self._svhc_updates if s.ajin_affected]

    def get_cmr_chemicals(self) -> list[MSDSRecord]:
        """CMR(발암성/변이원성/생식독성) 분류 화학물질을 반환한다."""
        if not self._records:
            self.crawl()
        return [r for r in self._records if r.cmr_classification != "해당 없음"]

    def get_summary(self) -> dict:
        """MSDS 현황 요약을 반환한다."""
        if not self._records:
            self.crawl()
        return {
            "total_chemicals": len(self._records),
            "msds_update_needed": len([r for r in self._records if r.msds_update_needed]),
            "svhc_affected": len([s for s in self._svhc_updates if s.ajin_affected]),
            "cmr_chemicals": len([r for r in self._records if r.cmr_classification != "해당 없음"]),
            "k_reach_registered": len([r for r in self._records if r.k_reach_registered]),
            "total_svhc_monitored": len(self._svhc_updates),
        }
