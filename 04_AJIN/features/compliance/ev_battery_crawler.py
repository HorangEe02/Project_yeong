"""EV 배터리 안전 규격 크롤러

UN GTR 20, UN R100, IEC 62660, SAE J2464, GB/T 38031 등
전기차 배터리 안전 시험 규격 및 국내 기준을 통합 관리한다.

데이터 소스:
- UNECE (UN 차량 규정)
- IEC Webstore (국제전기기술위원회)
- SAE International
- 중국 GB 표준 데이터베이스
- 국가기술표준원 (K-BESS)
- 고용노동부 (산업안전보건기준)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EVBatteryStandard:
    """EV 배터리 안전 규격 정보"""
    standard_id: str              # e.g., "UN-GTR-20"
    name: str
    name_ko: str
    issuing_org: str              # 발행 기관
    category: str                 # UN_GTR, UN_R, IEC, SAE, GB, 국내기준
    version: str
    effective_date: str
    transition_deadline: str
    test_requirements: list[dict]  # [{test_id, test_name_ko, test_type, pass_criteria_ko}]
    ajin_relevance: str
    ajin_compliance_status: str    # 충족 / 부분충족 / 미충족 / 평가중
    key_changes_ko: str
    action_items_ko: list[str]
    reference_url: str = ""
    crawled_at: str = ""


@dataclass
class EVBatteryCrawlResult:
    """크롤링 결과"""
    standards: list[EVBatteryStandard]
    crawled_at: str
    source: str
    total_count: int
    action_needed: int
    upcoming_deadlines: int
    errors: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────
# EV 배터리 안전 규격 마스터 데이터
# ─────────────────────────────────────────────
_MASTER_DATA: list[dict] = [
    # ── UN GTR 20 ──
    {
        "standard_id": "UN-GTR-20",
        "name": "Global Technical Regulation on Electric Vehicle Safety (EVS)",
        "name_ko": "전기차 안전에 관한 국제기술규정",
        "issuing_org": "UNECE WP.29 (World Forum for Harmonization of Vehicle Regulations)",
        "category": "UN_GTR",
        "version": "Phase 2 (2023)",
        "effective_date": "2018-03",
        "transition_deadline": "2026-06-30",
        "test_requirements": [
            {
                "test_id": "GTR20-T01",
                "test_name_ko": "REESS 진동 시험 (전기에너지저장시스템)",
                "test_type": "기계적",
                "pass_criteria_ko": "진동 후 절연저항 100Ω/V 이상, 전해액 누출 없음, 외관 변형/파손 없음",
            },
            {
                "test_id": "GTR20-T02",
                "test_name_ko": "열 충격 및 열 사이클 시험",
                "test_type": "열적",
                "pass_criteria_ko": "-40℃~+60℃ 열 사이클 후 절연저항 기준 유지, 누출·화재·폭발 없음",
            },
            {
                "test_id": "GTR20-T03",
                "test_name_ko": "외부 단락 시험",
                "test_type": "전기적",
                "pass_criteria_ko": "외부 단락 후 1시간 관찰 — 폭발·화재 없음",
            },
            {
                "test_id": "GTR20-T04",
                "test_name_ko": "과충전 보호 시험",
                "test_type": "전기적",
                "pass_criteria_ko": "과충전 상태에서 화재·폭발 없음, 보호 장치 정상 작동",
            },
            {
                "test_id": "GTR20-T05",
                "test_name_ko": "열 전파 시험 (Thermal Propagation)",
                "test_type": "열적",
                "pass_criteria_ko": "단일 셀 열폭주 발생 후 승객 대피 시간(5분) 확보, 외부 화염 없음",
            },
        ],
        "ajin_relevance": "배터리 케이스/팩 구조물의 기계적 강도, 방수 밀봉 성능이 UN GTR 20 시험 통과에 직접 영향. "
                          "특히 열 전파(Thermal Propagation) 시험에서 케이스의 열 차단 및 가스 배출 구조 설계가 핵심.",
        "ajin_compliance_status": "부분충족",
        "key_changes_ko": "Phase 2(2023) 주요 변경: 열 전파(Thermal Propagation) 시험 신설 — 단일 셀 열폭주 시 "
                          "승객 대피 시간 확보 요구. In-use 성능 요구사항 강화. 침수 시험 조건 구체화.",
        "action_items_ko": [
            "열 전파 시험 대응 — 케이스 내부 열 차단 격벽(barrier) 설계 검증",
            "가스 배출(venting) 구조 시험 데이터 확보",
            "Phase 2 요구사항 대비 배터리 팩 구조 강도 재검증",
        ],
        "reference_url": "https://unece.org/transport/vehicle-regulations/wp29/global-technical-regulations-gtrs",
    },
    # ── UN R100 ──
    {
        "standard_id": "UN-R100",
        "name": "Regulation No 100 — Uniform provisions concerning the approval of vehicles with regard to specific requirements for the electric power train",
        "name_ko": "전기 동력 장치의 안전에 관한 규정",
        "issuing_org": "UNECE WP.29",
        "category": "UN_R",
        "version": "Rev.3 (2023)",
        "effective_date": "2013-01",
        "transition_deadline": "2025-09-01",
        "test_requirements": [
            {
                "test_id": "R100-T01",
                "test_name_ko": "감전 보호 시험 (직접/간접 접촉)",
                "test_type": "전기적",
                "pass_criteria_ko": "노출 도전부 접근 불가, 절연저항 500Ω/V 이상 (AC), 100Ω/V (DC)",
            },
            {
                "test_id": "R100-T02",
                "test_name_ko": "REESS 안전 시험 (진동, 열 충격, 기계적 충격)",
                "test_type": "기계적",
                "pass_criteria_ko": "누출·화재·폭발 없음, 절연저항 기준 유지",
            },
            {
                "test_id": "R100-T03",
                "test_name_ko": "침수(Water Immersion) 시험",
                "test_type": "환경",
                "pass_criteria_ko": "IPX7 기준 침수 후 절연저항 100Ω/V 이상 유지",
            },
            {
                "test_id": "R100-T04",
                "test_name_ko": "고전압 차단 시 잔류 에너지 시험",
                "test_type": "전기적",
                "pass_criteria_ko": "고전압 차단 후 1초 이내 60V DC 이하 또는 에너지 0.2J 이하",
            },
        ],
        "ajin_relevance": "배터리 케이스의 IP 등급(방수/방진), 절연 구조, 고전압 커넥터 보호 설계에 직접 적용. "
                          "경산 제2공장 배터리 케이스 제품 형식승인 필수 요건.",
        "ajin_compliance_status": "충족",
        "key_changes_ko": "Rev.3 주요 변경: 수소 배출 시험 조건 명확화, 침수 시험 심도/시간 강화, "
                          "충전 중 안전 요구사항 추가 (AC/DC 충전 시 절연 모니터링).",
        "action_items_ko": [
            "Rev.3 침수 시험 강화 조건 대비 IP67 → IP68 등급 검토",
            "충전 중 절연 모니터링 관련 커넥터 하우징 설계 확인",
        ],
        "reference_url": "https://unece.org/transport/documents/2021/02/standards/un-regulation-no-100",
    },
    # ── IEC 62660 시리즈 ──
    {
        "standard_id": "IEC-62660",
        "name": "IEC 62660 series — Secondary lithium-ion cells for the propulsion of electric road vehicles",
        "name_ko": "전기차 구동용 리튬이온 이차전지 시리즈",
        "issuing_org": "IEC TC 21 (Secondary cells and batteries)",
        "category": "IEC",
        "version": "62660-1 Ed.2 (2018), 62660-2 Ed.2 (2018), 62660-3 Ed.1 (2016)",
        "effective_date": "2018-12",
        "transition_deadline": "",
        "test_requirements": [
            {
                "test_id": "IEC62660-1-T01",
                "test_name_ko": "셀 성능 시험 (용량, 에너지, 출력)",
                "test_type": "전기적",
                "pass_criteria_ko": "정격 용량의 95% 이상 방전 용량 확인, 출력 밀도 규격 충족",
            },
            {
                "test_id": "IEC62660-2-T01",
                "test_name_ko": "셀 기계적 시험 (진동, 충격, 압축)",
                "test_type": "기계적",
                "pass_criteria_ko": "진동/충격/압축 후 화재·폭발 없음, 전해액 누출 없음",
            },
            {
                "test_id": "IEC62660-2-T02",
                "test_name_ko": "셀 열적 시험 (열 충격, 고온 방치)",
                "test_type": "열적",
                "pass_criteria_ko": "130℃ 고온 방치 시 화재·폭발 없음 (1시간 유지)",
            },
            {
                "test_id": "IEC62660-2-T03",
                "test_name_ko": "셀 외부 단락 시험",
                "test_type": "전기적",
                "pass_criteria_ko": "외부 단락 후 화재·폭발 없음",
            },
            {
                "test_id": "IEC62660-3-T01",
                "test_name_ko": "셀 안전성 시험 (과충전, 강제방전, 못 관통)",
                "test_type": "전기적",
                "pass_criteria_ko": "못 관통(Nail Penetration) 시 화재·폭발 없음 (제조사 기준)",
            },
        ],
        "ajin_relevance": "셀 레벨 시험 규격이나, 배터리 팩/케이스 설계가 셀 안전성에 영향. "
                          "셀 진동·충격 시험 시 케이스 고정 구조(브라켓, 클램프)의 체결력이 시험 결과에 직접 영향.",
        "ajin_compliance_status": "평가중",
        "key_changes_ko": "Ed.2(2018) 주요 변경: 시험 조건 구체화, 셀 크기별 시험 파라미터 세분화, "
                          "리튬-이온 폴리머 셀 시험 절차 추가.",
        "action_items_ko": [
            "OEM 셀 공급사 시험 데이터 연계 — 케이스 설계 조건 확인",
            "셀 고정 구조(브라켓/클램프) 체결 토크 기준 IEC 62660-2 시험 조건 반영",
        ],
        "reference_url": "https://webstore.iec.ch/en/publication/32898",
    },
    # ── IEC 62619 ──
    {
        "standard_id": "IEC-62619",
        "name": "IEC 62619 — Secondary cells and batteries containing alkaline or other non-acid electrolytes — Safety requirements for secondary lithium cells and batteries, for use in industrial applications",
        "name_ko": "산업용 리튬 이차전지 안전 요구사항",
        "issuing_org": "IEC TC 21",
        "category": "IEC",
        "version": "Ed.1 (2022)",
        "effective_date": "2022-05",
        "transition_deadline": "",
        "test_requirements": [
            {
                "test_id": "IEC62619-T01",
                "test_name_ko": "배터리 시스템 안전성 시험 (과충전/과방전 보호)",
                "test_type": "전기적",
                "pass_criteria_ko": "BMS 보호 기능 정상 작동, 과충전/과방전 시 차단 확인",
            },
            {
                "test_id": "IEC62619-T02",
                "test_name_ko": "외부 단락 시험 (시스템 레벨)",
                "test_type": "전기적",
                "pass_criteria_ko": "시스템 레벨 외부 단락 시 퓨즈/차단기 정상 작동, 화재·폭발 없음",
            },
            {
                "test_id": "IEC62619-T03",
                "test_name_ko": "기능 안전성 시험 (BMS 고장 모드)",
                "test_type": "전기적",
                "pass_criteria_ko": "BMS 단일 고장 시 안전 상태 진입 확인",
            },
            {
                "test_id": "IEC62619-T04",
                "test_name_ko": "낙하 시험",
                "test_type": "기계적",
                "pass_criteria_ko": "1m 높이 낙하 후 화재·폭발 없음, 외관 육안 검사 통과",
            },
        ],
        "ajin_relevance": "ESS(에너지저장장치) 등 산업용 배터리 시스템에 적용. 아진산업이 ESS용 배터리 케이스 "
                          "사업 확장 시 직접 적용 규격. 현재는 EV용 배터리 케이스에 간접 참조.",
        "ajin_compliance_status": "평가중",
        "key_changes_ko": "Ed.1(2022) 최초 발행. 기존 IEC 62133 대비 산업용 대형 배터리에 특화된 시험 요구사항 신설. "
                          "BMS 기능 안전성 시험 포함.",
        "action_items_ko": [
            "ESS 배터리 케이스 사업 진입 시 IEC 62619 인증 요건 사전 분석",
            "ESS용 케이스 설계 시 낙하 시험 충격 흡수 구조 반영",
        ],
        "reference_url": "https://webstore.iec.ch/en/publication/64073",
    },
    # ── SAE J2464 ──
    {
        "standard_id": "SAE-J2464",
        "name": "SAE J2464 — Electric and Hybrid Electric Vehicle Rechargeable Energy Storage System (RESS) Safety and Abuse Testing",
        "name_ko": "전기/하이브리드차 충전식 에너지 저장 시스템 안전 및 남용 시험",
        "issuing_org": "SAE International",
        "category": "SAE",
        "version": "Revised 2021-07",
        "effective_date": "2021-07",
        "transition_deadline": "",
        "test_requirements": [
            {
                "test_id": "J2464-T01",
                "test_name_ko": "기계적 충격 시험 (Mechanical Shock)",
                "test_type": "기계적",
                "pass_criteria_ko": "25g~50g 충격 후 화재·폭발 없음, 전해액 누출 기준 이내",
            },
            {
                "test_id": "J2464-T02",
                "test_name_ko": "압축(Crush) 시험",
                "test_type": "기계적",
                "pass_criteria_ko": "100kN 하중 인가 후 화재·폭발 없음",
            },
            {
                "test_id": "J2464-T03",
                "test_name_ko": "못 관통(Nail Penetration) 시험",
                "test_type": "기계적",
                "pass_criteria_ko": "3mm 스틸 못 관통 후 폭발 없음 (화재 발생 가능, 단 확산 방지)",
            },
            {
                "test_id": "J2464-T04",
                "test_name_ko": "열 안정성 시험 (Thermal Stability)",
                "test_type": "열적",
                "pass_criteria_ko": "분당 5℃ 승온, 열폭주 온도 및 에너지 방출량 측정",
            },
            {
                "test_id": "J2464-T05",
                "test_name_ko": "과충전 남용 시험",
                "test_type": "전기적",
                "pass_criteria_ko": "200% SOC 과충전 시 폭발 없음, 화재 발생 시 자연 소화",
            },
        ],
        "ajin_relevance": "북미 OEM(GM, Ford 등) 납품 시 SAE J2464 시험 요구. 배터리 케이스의 기계적 충격 흡수 성능, "
                          "압축 강도가 시험 결과에 직접 영향. 현대/기아 북미 수출 차량에도 참조 적용.",
        "ajin_compliance_status": "부분충족",
        "key_changes_ko": "2021 개정: 열 전파(Thermal Propagation) 시험 절차 추가, 대형 배터리 팩 전용 시험 조건 신설, "
                          "시험 데이터 기록 형식 표준화.",
        "action_items_ko": [
            "압축(Crush) 시험 대비 케이스 측면 보강 구조 검증",
            "열 전파 시험 대응 — 셀 간 열 차단 설계 OEM 협의",
            "북미 수출 차량 대응 시험 성적서 확보",
        ],
        "reference_url": "https://www.sae.org/standards/content/j2464_202107/",
    },
    # ── GB/T 38031 ──
    {
        "standard_id": "GB-T-38031",
        "name": "GB/T 38031 — Electric vehicles traction battery safety requirements",
        "name_ko": "중국 전기차 동력 배터리 안전 요구사항",
        "issuing_org": "SAC (중국 국가표준화관리위원회)",
        "category": "GB",
        "version": "GB/T 38031-2020",
        "effective_date": "2021-01-01",
        "transition_deadline": "2025-12-31",
        "test_requirements": [
            {
                "test_id": "GB38031-T01",
                "test_name_ko": "열 전파 시험 (Thermal Propagation)",
                "test_type": "열적",
                "pass_criteria_ko": "단일 셀 열폭주 유도 후 5분 이내 경고, 외부 화염 없음 — 승객 대피 시간 확보",
            },
            {
                "test_id": "GB38031-T02",
                "test_name_ko": "침수(Immersion) 시험",
                "test_type": "환경",
                "pass_criteria_ko": "수심 1m, 30분 침수 후 절연저항 기준 유지, 화재·폭발 없음",
            },
            {
                "test_id": "GB38031-T03",
                "test_name_ko": "진동 시험 (도로 주행 시뮬레이션)",
                "test_type": "기계적",
                "pass_criteria_ko": "X/Y/Z 3축 진동 후 누출·변형·절연 저하 없음",
            },
            {
                "test_id": "GB38031-T04",
                "test_name_ko": "기계적 충격 시험",
                "test_type": "기계적",
                "pass_criteria_ko": "50g, 6ms 반파장 충격 후 화재·폭발·누출 없음",
            },
            {
                "test_id": "GB38031-T05",
                "test_name_ko": "압축(Squeeze) 시험",
                "test_type": "기계적",
                "pass_criteria_ko": "100kN 또는 변형률 30% 중 먼저 달성 시까지 — 화재·폭발 없음",
            },
        ],
        "ajin_relevance": "중국 수출 차량 필수 인증. 현대/기아 중국 공장 납품 부품에 직접 적용. "
                          "GB/T 38031은 열 전파 시험을 세계 최초로 의무화한 규격으로 글로벌 기준 선도.",
        "ajin_compliance_status": "부분충족",
        "key_changes_ko": "2020 개정: 열 전파(Thermal Propagation) 시험 세계 최초 의무화, "
                          "배터리 팩 레벨 시험 강화, 승객 경고 시간 5분 요구 신설.",
        "action_items_ko": [
            "열 전파 시험 대응 — 케이스 열 차단 성능 시험 데이터 확보",
            "중국 CCC 인증 갱신 시 GB/T 38031-2020 기준 적용 확인",
            "현대/기아 중국 공장 납품분 시험 성적서 업데이트",
        ],
        "reference_url": "https://www.chinesestandard.net/PDF/English.aspx/GBT38031-2020",
    },
    # ── K-BESS ──
    {
        "standard_id": "K-BESS",
        "name": "Korean Battery Safety Evaluation Standards (K-BESS)",
        "name_ko": "한국 배터리 안전성 평가 기준 (K-BESS)",
        "issuing_org": "산업통상자원부 / 한국교통안전공단 / 국가기술표준원",
        "category": "국내기준",
        "version": "2024년 개정",
        "effective_date": "2024-01-01",
        "transition_deadline": "2026-01-01",
        "test_requirements": [
            {
                "test_id": "KBESS-T01",
                "test_name_ko": "배터리 팩 열 전파 시험",
                "test_type": "열적",
                "pass_criteria_ko": "UN GTR 20 기반 열 전파 시험 + 국내 추가 요구사항 (경고 시간 5분 이상)",
            },
            {
                "test_id": "KBESS-T02",
                "test_name_ko": "배터리 팩 침수 시험",
                "test_type": "환경",
                "pass_criteria_ko": "IP67 이상, 침수 30분 후 절연저항 100Ω/V 이상",
            },
            {
                "test_id": "KBESS-T03",
                "test_name_ko": "배터리 시스템 화재 시험",
                "test_type": "열적",
                "pass_criteria_ko": "외부 화재 노출 시 폭발 없음, 화재 확산 지연 시간 기준 충족",
            },
            {
                "test_id": "KBESS-T04",
                "test_name_ko": "충전 안전성 시험",
                "test_type": "전기적",
                "pass_criteria_ko": "급속/완속 충전 중 이상 상황 시 안전 차단 확인",
            },
        ],
        "ajin_relevance": "국내 배터리 EV 형식승인의 근거 기준. 아진산업 배터리 케이스의 국내 시험 인증에 직접 적용. "
                          "K-BESS는 UN GTR 20 기반에 국내 추가 요구사항을 반영한 규격.",
        "ajin_compliance_status": "부분충족",
        "key_changes_ko": "2024 개정: UN GTR 20 Phase 2 반영, 열 전파 시험 의무화, "
                          "급속 충전(400V/800V) 안전 시험 추가, 배터리 화재 안전 등급 제도 도입.",
        "action_items_ko": [
            "2024 개정 기준 대비 배터리 케이스 시험 항목 매핑 완료",
            "열 전파 시험 국내 시험기관(KTC, KATRI) 시험 일정 확보",
            "급속 충전 안전 시험 대응 — 800V 시스템 케이스 절연 설계 검증",
        ],
        "reference_url": "https://www.motie.go.kr/",
    },
    # ── 고전압 작업 안전 규정 ──
    {
        "standard_id": "KOSHA-HV",
        "name": "Regulations on Occupational Safety and Health Standards — High Voltage Work Safety",
        "name_ko": "산업안전보건기준에 관한 규칙 (고전압 작업 안전)",
        "issuing_org": "고용노동부 / 한국산업안전보건공단 (KOSHA)",
        "category": "국내기준",
        "version": "2024년 개정 (고용노동부령 제418호)",
        "effective_date": "2024-07-01",
        "transition_deadline": "2025-06-30",
        "test_requirements": [
            {
                "test_id": "KOSHA-HV-T01",
                "test_name_ko": "고전압(60V DC 이상) 활선 작업 안전 절차 이행",
                "test_type": "전기적",
                "pass_criteria_ko": "절연용 보호구 착용, 활선 작업 허가서 발행, 감전 방지 대책 수립",
            },
            {
                "test_id": "KOSHA-HV-T02",
                "test_name_ko": "고전압 설비 절연 저항 측정 (정기 검사)",
                "test_type": "전기적",
                "pass_criteria_ko": "절연저항 1MΩ 이상 (사용전압 400V 기준), 접지저항 10Ω 이하",
            },
            {
                "test_id": "KOSHA-HV-T03",
                "test_name_ko": "감전 위험 작업 시 특별안전교육 이수",
                "test_type": "전기적",
                "pass_criteria_ko": "고전압 작업자 연 16시간 이상 특별안전교육 이수, 자격 보유 확인",
            },
            {
                "test_id": "KOSHA-HV-T04",
                "test_name_ko": "비상 시 고전압 차단 절차 (LOTO)",
                "test_type": "전기적",
                "pass_criteria_ko": "Lock-Out/Tag-Out 절차 이행, 잔류 에너지 방전 확인",
            },
        ],
        "ajin_relevance": "경산 제2공장 EV 배터리 팩 조립 라인의 고전압(400V/800V) 작업에 직접 적용. "
                          "작업자 감전 방지, 절연 보호구 관리, LOTO 절차 이행이 핵심. "
                          "중대재해처벌법 대상 — 고전압 감전 사고 시 경영 책임 발생.",
        "ajin_compliance_status": "부분충족",
        "key_changes_ko": "2024 개정: EV 배터리 고전압(DC 60V 이상) 작업 안전 기준 구체화, "
                          "800V 시스템 작업 시 추가 보호 조치 요구, 감전 사고 시 응급 대응 절차 강화.",
        "action_items_ko": [
            "800V 배터리 라인 작업자 전원 특별안전교육 이수 확인 (연 16시간)",
            "고전압 절연 보호구(장갑, 매트, 차폐복) 정기 검사 일정 수립",
            "LOTO 절차서 800V 시스템 대응 개정",
            "감전 응급 대응 키트 배치 및 응급 처치 교육 시행",
        ],
        "reference_url": "https://www.kosha.or.kr/",
    },
]


class EVBatteryCrawler:
    """EV 배터리 안전 규격 크롤러

    UN GTR 20, UN R100, IEC 62660, SAE J2464, GB/T 38031 등
    전기차 배터리 관련 안전 시험 규격을 수집하고
    아진산업 배터리 케이스 제품의 규격 준수 현황을 관리한다.
    """

    def __init__(self, crawled_dir: Path | None = None):
        if crawled_dir is None:
            crawled_dir = Path(__file__).parent.parent.parent / "data" / "crawled"
        self.crawled_dir = crawled_dir
        self.crawled_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.crawled_dir / "ev_battery.json"
        self._standards: list[EVBatteryStandard] = []

    # ── crawl ──────────────────────────────────
    def crawl(self) -> EVBatteryCrawlResult:
        """EV 배터리 안전 규격 데이터를 수집한다.

        실제 운영 시 UNECE, IEC Webstore, SAE, 국가기술표준원 등에서
        최신 정보를 크롤링한다.
        현재는 아진산업 관련 핵심 규격의 마스터 데이터를 구축한다.
        """
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        errors: list[str] = []

        standards: list[EVBatteryStandard] = []
        for item in _MASTER_DATA:
            try:
                standards.append(EVBatteryStandard(**item, crawled_at=now))
            except Exception as e:
                errors.append(f"파싱 오류 ({item.get('standard_id', '?')}): {e}")

        self._standards = standards

        action_needed = sum(
            1 for s in standards
            if s.ajin_compliance_status in ("미충족", "부분충족")
        )
        upcoming = sum(
            1 for s in standards
            if s.transition_deadline and s.transition_deadline >= now[:10]
        )

        result = EVBatteryCrawlResult(
            standards=standards,
            crawled_at=now,
            source="unece.org + iec.ch + sae.org + chinesestandard.net + motie.go.kr + kosha.or.kr",
            total_count=len(standards),
            action_needed=action_needed,
            upcoming_deadlines=upcoming,
            errors=errors,
        )

        self._save(result)
        return result

    # ── _save ──────────────────────────────────
    def _save(self, result: EVBatteryCrawlResult) -> None:
        """크롤링 결과를 JSON으로 저장한다."""
        data = {
            "crawled_at": result.crawled_at,
            "source": result.source,
            "total_count": result.total_count,
            "action_needed": result.action_needed,
            "upcoming_deadlines": result.upcoming_deadlines,
            "standards": [asdict(s) for s in result.standards],
            "errors": result.errors,
        }
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(
            "EV 배터리 규격 데이터 저장: %s (%d건)", self.output_path, result.total_count
        )

    # ── load ───────────────────────────────────
    def load(self) -> list[EVBatteryStandard]:
        """저장된 EV 배터리 규격 데이터를 로드한다."""
        if not self.output_path.exists():
            return []
        with open(self.output_path, encoding="utf-8") as f:
            data = json.load(f)
        self._standards = [
            EVBatteryStandard(**item) for item in data.get("standards", [])
        ]
        return self._standards

    # ── get_by_category ────────────────────────
    def get_by_category(self, category: str) -> list[EVBatteryStandard]:
        """카테고리별 규격 목록을 반환한다.

        Args:
            category: "UN_GTR", "UN_R", "IEC", "SAE", "GB", "국내기준"
        """
        if not self._standards:
            self.load()
        return [s for s in self._standards if s.category == category]

    # ── get_action_needed ──────────────────────
    def get_action_needed(self) -> list[EVBatteryStandard]:
        """조치가 필요한(미충족/부분충족) 규격 목록을 반환한다."""
        if not self._standards:
            self.load()
        return [
            s for s in self._standards
            if s.ajin_compliance_status in ("미충족", "부분충족")
        ]

    # ── get_upcoming_deadlines ─────────────────
    def get_upcoming_deadlines(self) -> list[dict]:
        """전환 기한이 설정된 규격 목록을 날짜순으로 반환한다."""
        if not self._standards:
            self.load()
        deadlines = []
        for s in self._standards:
            if s.transition_deadline:
                deadlines.append({
                    "standard_id": s.standard_id,
                    "name_ko": s.name_ko,
                    "transition_deadline": s.transition_deadline,
                    "compliance_status": s.ajin_compliance_status,
                    "action_items_ko": s.action_items_ko,
                })
        return sorted(deadlines, key=lambda x: x["transition_deadline"])

    # ── get_summary ────────────────────────────
    def get_summary(self) -> dict:
        """EV 배터리 규격 현황 요약을 반환한다."""
        if not self._standards:
            self.load()
        return {
            "total": len(self._standards),
            "by_category": {
                cat: len([s for s in self._standards if s.category == cat])
                for cat in sorted(set(s.category for s in self._standards))
            },
            "by_compliance_status": {
                status: len([s for s in self._standards if s.ajin_compliance_status == status])
                for status in ("충족", "부분충족", "미충족", "평가중")
            },
            "action_needed": len(self.get_action_needed()),
            "with_deadline": len([s for s in self._standards if s.transition_deadline]),
            "total_action_items": sum(len(s.action_items_ko) for s in self._standards),
        }
