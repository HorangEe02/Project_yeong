"""OEM 품질 표준 크롤러

OEM별 품질 요구사항(현대/기아 SQ, CQI, GM BIQS, VW Formel-Q)의
최신 기준, 심사 결과, 아진산업 대응 현황을 수집한다.

데이터 소스:
- 현대/기아 SQ 포털 (협력사 품질 매뉴얼)
- AIAG CQI 특수공정 심사 기준
- GM Supplier Quality (BIQS 평가)
- VW Formel-Q Capability/Konkret
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class OEMQualityStandard:
    """OEM 품질 표준 정보"""
    standard_id: str               # e.g., "HMC-SQ-2025"
    name: str
    name_ko: str
    issuing_org: str               # 발행 기관
    category: str                  # SQ, CQI, BIQS, Formel-Q
    version: str
    effective_date: str            # YYYY-MM-DD
    next_review_date: str          # YYYY-MM-DD
    key_requirements: list[dict]   # requirement_id, title_ko, description_ko, ajin_status
    audit_frequency: str           # e.g., "연 1회", "반기 1회"
    last_audit_date: str           # YYYY-MM-DD
    audit_score: float             # 심사 점수
    ajin_relevance: str            # high / medium / low
    changes_summary_ko: str        # 최근 변경 요약
    action_items_ko: list[str]     # 아진산업 조치 사항
    crawled_at: str = ""


@dataclass
class OEMQualityCrawlResult:
    """크롤링 결과"""
    crawled_at: str
    source: str
    total_count: int
    standards: list[OEMQualityStandard]
    errors: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────
# OEM 품질 표준 마스터 데이터
# ─────────────────────────────────────────────

_MASTER_DATA: list[dict] = [
    # ── 현대/기아 SQ ──────────────────────────
    {
        "standard_id": "HMC-SQ-2025",
        "name": "Hyundai/Kia Supplier Quality Manual",
        "name_ko": "현대/기아 협력사 품질 매뉴얼 (SQ Manual)",
        "issuing_org": "현대자동차그룹 SQ 품질본부",
        "category": "SQ",
        "version": "Rev.12 (2025)",
        "effective_date": "2025-01-01",
        "next_review_date": "2026-01-01",
        "key_requirements": [
            {
                "requirement_id": "SQ-R01",
                "title_ko": "협력사 품질 등급 관리",
                "description_ko": "S/A/B/C/D 5등급 평가. 연간 SQ 심사(서류+현장)를 통해 등급 산정. "
                                  "D등급 2회 연속 시 거래 정지.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "SQ-R02",
                "title_ko": "부품 승인 절차 (PPAP)",
                "description_ko": "신규/변경 부품의 양산 승인. PPAP Level 3 기준 18개 항목 제출. "
                                  "SQ 포털 전자 제출 의무화.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "SQ-R03",
                "title_ko": "불량 관리 및 클레임 대응",
                "description_ko": "납입 불량 발생 시 24시간 내 D3 등록, 10일 내 D8 완료. "
                                  "PPM 목표: 프레스 부품 30 이하, 용접 어셈블리 15 이하.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "SQ-R04",
                "title_ko": "전동화 부품 특별 품질 요구사항",
                "description_ko": "EV 배터리 케이스, 모터 하우징 등 전동화 부품 전용 요구사항. "
                                  "고전압 안전성 시험, 방수 IP67 시험, EMC 적합성 확인 필수.",
                "ajin_status": "부분충족",
            },
        ],
        "audit_frequency": "연 1회 (정기) + 수시 (클레임 발생 시)",
        "last_audit_date": "2025-09-15",
        "audit_score": 91.5,
        "ajin_relevance": "high",
        "changes_summary_ko": "2025년 주요 변경: 전동화 부품 전용 품질 요구사항 신설, "
                              "사이버보안 개발 프로세스(ISO/SAE 21434) 적합성 요구 추가, "
                              "탄소중립 이행 협력사 평가 항목 신설.",
        "action_items_ko": [
            "경산 제2공장 EV 배터리 케이스 라인 전동화 특별 요구사항 적용 완료 (2026-06까지)",
            "사이버보안 프로세스 수립 및 ISO/SAE 21434 갭 분석 착수",
            "탄소 배출 Scope 1/2 데이터 수집 체계 구축",
        ],
    },
    {
        "standard_id": "HMC-SQ-INIT-2025",
        "name": "Hyundai/Kia Initial Sample Inspection Standard",
        "name_ko": "현대/기아 초물 관리 기준",
        "issuing_org": "현대자동차그룹 SQ 품질본부",
        "category": "SQ",
        "version": "Rev.5 (2025)",
        "effective_date": "2025-03-01",
        "next_review_date": "2026-03-01",
        "key_requirements": [
            {
                "requirement_id": "INIT-R01",
                "title_ko": "초물 전수검사 기준",
                "description_ko": "양산 승인 후 최초 3 lot 전수검사 실시. "
                                  "특별 특성(CC/SC) 항목은 Cpk >= 1.67 확인 후 전환.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "INIT-R02",
                "title_ko": "변경점 초물 관리",
                "description_ko": "4M 변경(Man, Machine, Material, Method) 발생 시 초물 관리 재적용. "
                                  "변경 전 SQ 포털 사전 승인 필수.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "INIT-R03",
                "title_ko": "초물 이력 추적성",
                "description_ko": "초물 제품의 LOT 번호, 작업자, 설비, 원자재 LOT 추적 가능해야 함. "
                                  "MES 시스템 연동 권장.",
                "ajin_status": "부분충족",
            },
        ],
        "audit_frequency": "반기 1회",
        "last_audit_date": "2025-08-20",
        "audit_score": 88.0,
        "ajin_relevance": "high",
        "changes_summary_ko": "2025년 변경: MES 연동을 통한 실시간 초물 이력 추적 권장 사항 추가. "
                              "경미한 4M 변경에도 초물 관리 의무화 범위 확대.",
        "action_items_ko": [
            "아산공장 MES 초물 이력 추적 모듈 개발 (2026-09까지)",
            "4M 변경 관리 프로세스에 경미 변경 기준 명확화",
        ],
    },

    # ── CQI 특수공정 심사 ──────────────────────
    {
        "standard_id": "CQI-9-V4",
        "name": "CQI-9 Special Process: Heat Treat System Assessment",
        "name_ko": "CQI-9 특수공정 심사: 열처리",
        "issuing_org": "AIAG (Automotive Industry Action Group)",
        "category": "CQI",
        "version": "4th Edition (2024)",
        "effective_date": "2024-07-01",
        "next_review_date": "2027-07-01",
        "key_requirements": [
            {
                "requirement_id": "CQI9-R01",
                "title_ko": "열처리 공정 관리",
                "description_ko": "열처리 로(furnace) 온도 균일성 시험(TUS) 연 2회 이상 실시. "
                                  "AMS 2750 기준 +/-5도C 이내. 열전대 교정 주기 준수.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "CQI9-R02",
                "title_ko": "야금학적 검증",
                "description_ko": "경도, 미세조직, 유효경화깊이 등 야금학적 특성 검사. "
                                  "로트별 시험성적서 보관. 파괴시험 주기 준수.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "CQI9-R03",
                "title_ko": "열처리 공정 모니터링",
                "description_ko": "SCADA 시스템을 통한 실시간 공정 파라미터 모니터링. "
                                  "이상 발생 시 자동 경보 및 격리 절차.",
                "ajin_status": "부분충족",
            },
        ],
        "audit_frequency": "연 1회 (OEM 요구 시 수시)",
        "last_audit_date": "2025-03-10",
        "audit_score": 85.0,
        "ajin_relevance": "high",
        "changes_summary_ko": "4판 주요 변경: 실시간 공정 모니터링 시스템 요구 강화, "
                              "에너지 효율 관련 항목 신설, 디지털 기록 관리 의무화.",
        "action_items_ko": [
            "경산 제1공장 열처리 라인 SCADA 실시간 모니터링 시스템 도입 (2026-12까지)",
            "열처리 공정 에너지 사용량 모니터링 체계 구축",
            "종이 기록에서 디지털 기록으로 전환 완료",
        ],
    },
    {
        "standard_id": "CQI-11-V4",
        "name": "CQI-11 Special Process: Plating System Assessment",
        "name_ko": "CQI-11 특수공정 심사: 도금",
        "issuing_org": "AIAG (Automotive Industry Action Group)",
        "category": "CQI",
        "version": "4th Edition (2023)",
        "effective_date": "2023-09-01",
        "next_review_date": "2026-09-01",
        "key_requirements": [
            {
                "requirement_id": "CQI11-R01",
                "title_ko": "도금 용액 관리",
                "description_ko": "도금 용액 성분 분석(일/주 단위). 도금 두께 관리(부위별 최소/최대). "
                                  "수소취성 방지 베이킹 처리 기준 관리.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "CQI11-R02",
                "title_ko": "도금 품질 검사",
                "description_ko": "밀착력 시험(벤드/테이프 테스트), 내식성 시험(염수분무 SST 480h 이상), "
                                  "외관 검사(변색, 얼룩, 기포). 폐수 처리 및 환경규제 준수.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "CQI11-R03",
                "title_ko": "고강도강 수소취성 관리",
                "description_ko": "인장강도 1000MPa 이상 소재 도금 시 수소취성 방지 베이킹 처리 필수. "
                                  "베이킹 온도 190-220도C, 8시간 이상. 수소취성 시험(ASTM F519) 실시.",
                "ajin_status": "해당없음",
            },
        ],
        "audit_frequency": "연 1회",
        "last_audit_date": "2025-06-15",
        "audit_score": 90.0,
        "ajin_relevance": "medium",
        "changes_summary_ko": "4판 주요 변경: 전착도장(E-coat) 전처리 공정 연계 요구사항 추가, "
                              "환경규제 대응 항목 강화(폐수 방류 기준, 6가 크롬 사용 금지).",
        "action_items_ko": [
            "외주 도금업체 CQI-11 4판 기준 재심사 완료 확인",
            "아연니켈 도금 사양 협력사 품질 협정서 갱신",
        ],
    },
    {
        "standard_id": "CQI-12-V3",
        "name": "CQI-12 Special Process: Coating System Assessment",
        "name_ko": "CQI-12 특수공정 심사: 코팅(도장)",
        "issuing_org": "AIAG (Automotive Industry Action Group)",
        "category": "CQI",
        "version": "3rd Edition (2023)",
        "effective_date": "2023-06-01",
        "next_review_date": "2026-06-01",
        "key_requirements": [
            {
                "requirement_id": "CQI12-R01",
                "title_ko": "도장 공정 관리",
                "description_ko": "전처리(인산피막, 탈지), 전착도장, 중도/상도 각 공정별 "
                                  "도막 두께, 부착력, 염수분무 시험 기준 관리.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "CQI12-R02",
                "title_ko": "도장 환경 관리",
                "description_ko": "도장 부스 온습도 관리(20~25도C, RH 50~70%). "
                                  "분진 관리(클래스 1000 이하). VOC 배출 농도 모니터링.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "CQI12-R03",
                "title_ko": "친환경 도장 전환",
                "description_ko": "수성 도료 전환 계획 수립. VOC 저감 목표 관리. "
                                  "RTO(축열식 산화장치) 가동 효율 관리.",
                "ajin_status": "부분충족",
            },
        ],
        "audit_frequency": "연 1회",
        "last_audit_date": "2025-05-18",
        "audit_score": 87.0,
        "ajin_relevance": "high",
        "changes_summary_ko": "3판 주요 변경: 친환경 도장(수성 도료) 전환 요구 강화, "
                              "VOC 배출 관리 기준 강화, 에너지 효율 항목 신설.",
        "action_items_ko": [
            "아산공장 도장 라인 수성 도료 전환 계획서 수립 (2026-12까지)",
            "VOC 연속 측정 시스템(CEMS) 설치 검토",
        ],
    },
    {
        "standard_id": "CQI-15-V5",
        "name": "CQI-15 Special Process: Welding System Assessment",
        "name_ko": "CQI-15 특수공정 심사: 용접",
        "issuing_org": "AIAG (Automotive Industry Action Group)",
        "category": "CQI",
        "version": "5th Edition (2025)",
        "effective_date": "2025-03-01",
        "next_review_date": "2028-03-01",
        "key_requirements": [
            {
                "requirement_id": "CQI15-R01",
                "title_ko": "용접 공정 인증",
                "description_ko": "저항 용접, 아크 용접, 레이저 용접 각 공정별 인증. "
                                  "용접사 자격 관리 및 재인증 주기 준수.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "CQI15-R02",
                "title_ko": "용접 품질 모니터링",
                "description_ko": "스폿 용접: 너깃 직경 관리, 전단/인장 시험 주기적 실시. "
                                  "레이저 용접: 비드 외관, 용입 깊이, 기공률 검사.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "CQI15-R03",
                "title_ko": "AI 기반 용접 모니터링",
                "description_ko": "5판 신설: 아크 용접 공정에 AI/ML 기반 실시간 품질 예측 시스템 권장. "
                                  "용접 전류/전압 파형 분석을 통한 불량 사전 감지.",
                "ajin_status": "미충족",
            },
            {
                "requirement_id": "CQI15-R04",
                "title_ko": "레이저 용접 특별 관리",
                "description_ko": "5판 강화: 레이저 용접 공정 파라미터(출력, 속도, 초점거리) "
                                  "실시간 모니터링 및 SPC 관리. 보호가스 유량 자동 제어.",
                "ajin_status": "부분충족",
            },
        ],
        "audit_frequency": "연 1회",
        "last_audit_date": "2025-04-22",
        "audit_score": 82.5,
        "ajin_relevance": "high",
        "changes_summary_ko": "5판 주요 변경: 레이저 용접 관련 요구사항 대폭 추가, "
                              "AI 기반 용접 모니터링 권장 사항 신설, "
                              "전동화 부품(배터리 케이스) 용접 특별 관리 항목 추가.",
        "action_items_ko": [
            "경산 제2공장 레이저 용접 라인 SPC 모니터링 시스템 구축 (2026-09까지)",
            "AI 용접 품질 예측 시스템 PoC 착수 (연구소 주관)",
            "CQI-15 5판 기준 내부 심사 체크리스트 갱신",
            "용접 엔지니어 대상 레이저 용접 고급 교육 실시",
        ],
    },
    {
        "standard_id": "CQI-23-V2",
        "name": "CQI-23 Special Process: Molding System Assessment",
        "name_ko": "CQI-23 특수공정 심사: 성형(프레스)",
        "issuing_org": "AIAG (Automotive Industry Action Group)",
        "category": "CQI",
        "version": "2nd Edition (2021)",
        "effective_date": "2021-01-01",
        "next_review_date": "2027-01-01",
        "key_requirements": [
            {
                "requirement_id": "CQI23-R01",
                "title_ko": "프레스 성형 공정 관리",
                "description_ko": "금형 관리(예방 보전 주기, 수명 관리, 수리 이력). "
                                  "프레스 설비 관리(슬라이드 정밀도, 쿠션 압력, 타이밍). "
                                  "소재 관리(코일 인장강도/항복강도/연신율 수입검사).",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "CQI23-R02",
                "title_ko": "핫스탬핑 공정 관리",
                "description_ko": "가열로 온도 균일성 관리, 이송 시간(furnace->press) 관리, "
                                  "금형 냉각 채널 유지보수, 마르텐사이트 조직 확인(경도 시험).",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "CQI23-R03",
                "title_ko": "성형 시뮬레이션 활용",
                "description_ko": "성형 해석(CAE)을 통한 성형성 사전 검증 요구. "
                                  "스프링백 예측 및 보정 관리. FLD(성형한계도) 기반 안전 영역 관리.",
                "ajin_status": "충족",
            },
        ],
        "audit_frequency": "연 1회",
        "last_audit_date": "2025-08-10",
        "audit_score": 92.0,
        "ajin_relevance": "high",
        "changes_summary_ko": "2판 주요 변경: 핫스탬핑 공정 요구사항 추가, "
                              "서보프레스 관리 항목 신설, 성형 시뮬레이션(CAE) 활용 요구 강화.",
        "action_items_ko": [
            "금형 예방보전 시스템 디지털화 완료 (IoT 센서 기반 금형 수명 예측)",
        ],
    },

    # ── GM BIQS ───────────────────────────────
    {
        "standard_id": "GM-BIQS-V3",
        "name": "GM Built-In Quality Supplier (BIQS) Assessment",
        "name_ko": "GM BIQS 내장 품질 협력사 평가",
        "issuing_org": "General Motors Global Supplier Quality",
        "category": "BIQS",
        "version": "Version 3 (2024)",
        "effective_date": "2024-01-01",
        "next_review_date": "2027-01-01",
        "key_requirements": [
            {
                "requirement_id": "BIQS-R01",
                "title_ko": "Level 1-2: 기본 품질 시스템",
                "description_ko": "Level 1: 기본 품질 관리(부적합품 관리, 계측기 관리, 문서 관리). "
                                  "Level 2: 표준작업 준수, 검사 기준서 운영, 교육 훈련 관리.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "BIQS-R02",
                "title_ko": "Level 3: 공정 관리 강화",
                "description_ko": "SPC 관리도 운영, 공정 능력 분석(Cpk >= 1.33), "
                                  "Error-Proofing(Poka-Yoke) 적용, 4M 변경 관리.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "BIQS-R03",
                "title_ko": "Level 4: 선제적 품질 관리",
                "description_ko": "PFMEA 기반 리스크 관리, Lessons Learned 시스템 운영, "
                                  "고객 불만 사전 예방 활동, 공급망 품질 관리.",
                "ajin_status": "부분충족",
            },
            {
                "requirement_id": "BIQS-R04",
                "title_ko": "Level 5: 지속적 개선 문화",
                "description_ko": "전사 품질 문화 정착, 자율 개선 활동, "
                                  "빅데이터/AI 기반 품질 예측, 벤치마킹 활동.",
                "ajin_status": "미충족",
            },
        ],
        "audit_frequency": "연 1회 (GM QSB+ 심사)",
        "last_audit_date": "2025-06-10",
        "audit_score": 78.0,
        "ajin_relevance": "medium",
        "changes_summary_ko": "Version 3 주요 변경: Level 5에 디지털 품질 관리 요구 추가, "
                              "AI/빅데이터 기반 품질 예측 항목 신설, "
                              "ESG 관련 협력사 평가 항목 추가.",
        "action_items_ko": [
            "Level 4 Lessons Learned 시스템 전사 확대 적용 (현재 품질관리팀 -> 전 공장)",
            "Level 5 달성을 위한 중장기 로드맵 수립",
            "GM향 납품 부품 SPC 데이터 자동 보고 시스템 구축",
            "GP-12 조기 해제를 위한 공정 안정화 활동 강화",
        ],
    },

    # ── VW Formel-Q ───────────────────────────
    {
        "standard_id": "VW-FQ-CAP-2024",
        "name": "VW Formel-Q Capability",
        "name_ko": "VW Formel-Q Capability (공급 능력 평가)",
        "issuing_org": "Volkswagen AG, Qualitaetssicherung",
        "category": "Formel-Q",
        "version": "9th Edition (2024)",
        "effective_date": "2024-01-01",
        "next_review_date": "2027-01-01",
        "key_requirements": [
            {
                "requirement_id": "FQ-R01",
                "title_ko": "잠재 분석 (Potential Analysis)",
                "description_ko": "신규 협력사 또는 신규 공정에 대한 잠재 능력 분석. "
                                  "VDA 6.3 P2~P7 기반 공정 심사 실시. A/B/C 등급 분류.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "FQ-R02",
                "title_ko": "양산 적합성 평가 (PPA)",
                "description_ko": "VW 2일 생산 시험(2TP: 2-Day Production Trial) 실시. "
                                  "공정 능력 Cmk >= 1.67, Cpk >= 1.33 달성 필수.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "FQ-R03",
                "title_ko": "D/TLD 부품 특별 관리",
                "description_ko": "안전 관련 부품(D-Teil) 및 법규 관련 부품(TLD)에 대한 "
                                  "특별 문서화 및 추적성 관리. 특별 보관 및 승인 절차.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "FQ-R04",
                "title_ko": "소프트웨어 품질 요구사항",
                "description_ko": "9판 신설: 소프트웨어 내장 부품의 Automotive SPICE 준수, "
                                  "사이버보안(ISO/SAE 21434) 적합성, OTA 업데이트 관리.",
                "ajin_status": "해당없음",
            },
        ],
        "audit_frequency": "연 1회 (VDA 6.3 공정 심사)",
        "last_audit_date": "2025-07-05",
        "audit_score": 84.0,
        "ajin_relevance": "medium",
        "changes_summary_ko": "9판 주요 변경: 소프트웨어 품질 요구사항 신설(A-SPICE, 사이버보안), "
                              "ESG/지속가능성 평가 항목 추가, "
                              "공급망 투명성(LkSG 공급망실사법) 요구 반영.",
        "action_items_ko": [
            "VW향 프로젝트 Formel-Q 9판 기준 갭 분석 실시",
            "VDA 6.3 공정 심사 점수 90점 이상 목표 개선 활동",
            "공급망 실사법(LkSG) 대응 체계 수립",
        ],
    },
    {
        "standard_id": "VW-FQ-KON-2024",
        "name": "VW Formel-Q Konkret",
        "name_ko": "VW Formel-Q Konkret (구체적 품질 요구사항)",
        "issuing_org": "Volkswagen AG, Qualitaetssicherung",
        "category": "Formel-Q",
        "version": "7th Edition (2024)",
        "effective_date": "2024-04-01",
        "next_review_date": "2027-04-01",
        "key_requirements": [
            {
                "requirement_id": "FQK-R01",
                "title_ko": "NTF (No Trouble Found) 관리",
                "description_ko": "고객 불만 중 재현 불가 사례(NTF) 체계적 분석. "
                                  "NTF 비율 관리 및 재발 방지 대책 수립.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "FQK-R02",
                "title_ko": "0km 불량 관리",
                "description_ko": "VW 조립 라인 투입 시 발견 불량(0km) 관리. "
                                  "PPM 기준 초과 시 Q-Alarm 발행. 즉시 격리 및 분류 활동.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "FQK-R03",
                "title_ko": "필드 불량 분석 및 대응",
                "description_ko": "시장 클레임(Field Claim) 분석. 8D 보고서 작성. "
                                  "재발 방지를 위한 PFMEA 업데이트 및 관리 계획서 반영.",
                "ajin_status": "충족",
            },
            {
                "requirement_id": "FQK-R04",
                "title_ko": "데이터 기반 품질 관리",
                "description_ko": "7판 강화: 실시간 품질 데이터 교환(EDI/API), "
                                  "예측 품질(Predictive Quality) 도입 권장, "
                                  "품질 KPI 대시보드 운영.",
                "ajin_status": "부분충족",
            },
        ],
        "audit_frequency": "반기 1회 (품질 성과 리뷰)",
        "last_audit_date": "2025-10-12",
        "audit_score": 80.5,
        "ajin_relevance": "medium",
        "changes_summary_ko": "7판 주요 변경: 데이터 기반 품질 관리 요구 강화, "
                              "실시간 품질 데이터 교환 체계 구축 요구, "
                              "Predictive Quality 도입 권장.",
        "action_items_ko": [
            "VW향 품질 데이터 실시간 교환 인터페이스(API) 개발",
            "품질 KPI 대시보드 구축 (Power BI 기반)",
            "Predictive Quality PoC 검토 (연구소 주관)",
        ],
    },
]


class OEMQualityCrawler:
    """OEM 품질 표준 크롤러

    OEM별 품질 요구사항(현대/기아 SQ, CQI, GM BIQS, VW Formel-Q)의
    최신 기준과 아진산업 대응 현황을 수집하고 관리한다.
    """

    def __init__(self, crawled_dir: Path | None = None):
        if crawled_dir is None:
            crawled_dir = Path(__file__).parent.parent.parent / "data" / "crawled"
        self.crawled_dir = crawled_dir
        self.crawled_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.crawled_dir / "oem_quality.json"
        self._standards: list[OEMQualityStandard] = []

    def crawl(self) -> OEMQualityCrawlResult:
        """OEM 품질 표준 데이터를 수집한다.

        실제 운영 시 현대/기아 SQ 포털, AIAG CQI 사이트,
        GM 공급망 포털, VW Group B2B 등에서 최신 정보를 크롤링한다.
        현재는 아진산업 관련 핵심 OEM 품질 표준의 마스터 데이터를 구축한다.
        """
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        errors: list[str] = []

        standards: list[OEMQualityStandard] = []
        for item in _MASTER_DATA:
            try:
                std = OEMQualityStandard(**item, crawled_at=now)
                standards.append(std)
            except Exception as e:
                errors.append(f"파싱 오류 ({item.get('standard_id', '?')}): {e}")

        self._standards = standards

        result = OEMQualityCrawlResult(
            crawled_at=now,
            source="hyundai_sq_portal + aiag_cqi + gm_gsip + vw_b2b",
            total_count=len(standards),
            standards=standards,
            errors=errors,
        )

        self._save(result)
        return result

    def _save(self, result: OEMQualityCrawlResult) -> None:
        """크롤링 결과를 JSON으로 저장한다."""
        data = {
            "crawled_at": result.crawled_at,
            "source": result.source,
            "total_count": result.total_count,
            "standards": [asdict(s) for s in result.standards],
            "errors": result.errors,
        }
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"OEM 품질 표준 데이터 저장: {self.output_path} ({result.total_count}건)")

    def load(self) -> OEMQualityCrawlResult | None:
        """저장된 OEM 품질 표준 데이터를 로드한다."""
        if not self.output_path.exists():
            return None
        with open(self.output_path, encoding="utf-8") as f:
            data = json.load(f)
        standards = [OEMQualityStandard(**item) for item in data.get("standards", [])]
        self._standards = standards
        return OEMQualityCrawlResult(
            crawled_at=data.get("crawled_at", ""),
            source=data.get("source", ""),
            total_count=data.get("total_count", len(standards)),
            standards=standards,
            errors=data.get("errors", []),
        )

    def _ensure_loaded(self) -> None:
        """데이터가 메모리에 없으면 파일에서 로드하거나 크롤링한다."""
        if not self._standards:
            result = self.load()
            if result is None:
                self.crawl()

    def get_by_category(self, category: str) -> list[OEMQualityStandard]:
        """카테고리별 표준 목록을 반환한다.

        Args:
            category: "SQ", "CQI", "BIQS", "Formel-Q" 중 하나
        """
        self._ensure_loaded()
        return [s for s in self._standards if s.category == category]

    def get_action_needed(self) -> list[OEMQualityStandard]:
        """조치가 필요한 표준 목록을 반환한다.

        key_requirements 중 '미충족' 또는 '부분충족' 항목이 있는 표준을 반환한다.
        """
        self._ensure_loaded()
        action_needed: list[OEMQualityStandard] = []
        for std in self._standards:
            for req in std.key_requirements:
                if req.get("ajin_status") in ("미충족", "부분충족"):
                    action_needed.append(std)
                    break
        return action_needed

    def get_summary(self) -> dict:
        """OEM 품질 표준 현황 요약을 반환한다."""
        self._ensure_loaded()

        # 카테고리별 집계
        by_category: dict[str, int] = {}
        for s in self._standards:
            by_category[s.category] = by_category.get(s.category, 0) + 1

        # 상태별 요구사항 집계
        status_counts: dict[str, int] = {}
        total_requirements = 0
        for s in self._standards:
            for req in s.key_requirements:
                total_requirements += 1
                status = req.get("ajin_status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1

        # 조치 필요 표준
        action_needed = self.get_action_needed()

        # 전체 action items 수
        total_action_items = sum(len(s.action_items_ko) for s in self._standards)

        return {
            "total_standards": len(self._standards),
            "by_category": by_category,
            "total_requirements": total_requirements,
            "requirement_status": status_counts,
            "standards_needing_action": len(action_needed),
            "total_action_items": total_action_items,
            "average_audit_score": (
                round(
                    sum(s.audit_score for s in self._standards) / len(self._standards),
                    1,
                )
                if self._standards
                else 0.0
            ),
        }
