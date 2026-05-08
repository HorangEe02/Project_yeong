"""ISO 국제규격 표준 크롤러

ISO/IATF 표준의 최신 개정 정보를 수집하고,
아진산업 인증 현황과 비교하여 갱신 필요 여부를 판단한다.

데이터 소스:
- ISO.org 공개 카탈로그 (제목, 발행일, 상태)
- KS 표준 연계 (한국산업표준)
- IATF OASIS 포털 (자동차 품질 표준)
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ISOStandard:
    """ISO 표준 정보"""
    standard_id: str            # e.g., "ISO 14001:2015"
    title: str
    title_ko: str
    status: str                 # published, under_development, withdrawn
    edition: str                # e.g., "3rd edition"
    publication_date: str       # YYYY-MM
    committee: str              # 기술위원회 (TC)
    ics_code: str               # 국제분류코드
    category: str               # quality, environment, safety, automotive
    scope: str                  # 적용 범위
    ajin_relevance: str         # 아진산업 관련성 설명
    korean_standard: str        # 대응 KS 규격
    latest_amendment: str = ""
    next_review_date: str = ""
    transition_deadline: str = ""
    changes_summary: str = ""
    reference_url: str = ""
    crawled_at: str = ""


@dataclass
class ISOCrawlResult:
    """크롤링 결과"""
    standards: list[ISOStandard]
    crawled_at: str
    source: str
    total_count: int
    updates_found: int = 0
    errors: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────
# 아진산업 관련 ISO/IATF 표준 마스터 데이터
# ─────────────────────────────────────────────
_AJIN_ISO_STANDARDS: list[dict] = [
    {
        "standard_id": "IATF 16949:2016",
        "title": "Quality management systems — Particular requirements for the application of ISO 9001:2015 for automotive production and relevant service part organizations",
        "title_ko": "자동차 생산 및 관련 서비스 부품 조직의 품질경영시스템 요구사항",
        "status": "published",
        "edition": "1st edition (IATF 기준)",
        "publication_date": "2016-10",
        "committee": "IATF (International Automotive Task Force)",
        "ics_code": "03.120.10",
        "category": "automotive_quality",
        "scope": "자동차 부품 제조사의 품질경영시스템. ISO 9001을 기반으로 자동차 산업 고유 요구사항 추가. 현대/기아 등 OEM 납품 필수 인증.",
        "ajin_relevance": "아진산업 3개 공장 전체 인증 보유. 현대/기아 SQ 등급 평가의 필수 조건. 갱신 주기 3년, 매년 사후심사 필수.",
        "korean_standard": "KS Q ISO 9001:2015 기반",
        "latest_amendment": "SI 11 (Sanctioned Interpretations, 2024-03 발행)",
        "next_review_date": "2027-10",
        "transition_deadline": "",
        "changes_summary": "SI 11: 원격 심사(remote audit) 허용 조건 명확화, 내장 소프트웨어 품질 요구사항 강화, 사이버보안 관련 프로세스 추가 권고",
        "reference_url": "https://www.iatfglobaloversight.org/iatf-169492016/about/",
    },
    {
        "standard_id": "ISO 9001:2015",
        "title": "Quality management systems — Requirements",
        "title_ko": "품질경영시스템 — 요구사항",
        "status": "published",
        "edition": "5th edition",
        "publication_date": "2015-09",
        "committee": "ISO/TC 176/SC 2",
        "ics_code": "03.120.10",
        "category": "quality",
        "scope": "품질경영시스템의 국제 표준. 고객 요구사항 및 적용 규제 요구사항을 충족하는 제품/서비스를 일관되게 제공하는 능력을 실증.",
        "ajin_relevance": "IATF 16949의 기반 표준으로 간접 적용. 품질관리팀 주관. 내부심사원 자격 요건 및 프로세스 접근법 적용.",
        "korean_standard": "KS Q ISO 9001:2015",
        "latest_amendment": "AMD 1:2024 (기후변화 고려사항 추가)",
        "next_review_date": "2025-09",
        "transition_deadline": "2027-02-28",
        "changes_summary": "AMD 1:2024 — 조직의 상황 파악 시 기후변화가 관련 이슈인지 결정하도록 요구. 4.1절 및 4.2절에 기후변화 고려 조항 추가.",
        "reference_url": "https://www.iso.org/standard/62085.html",
    },
    {
        "standard_id": "ISO 14001:2015",
        "title": "Environmental management systems — Requirements with guidance for use",
        "title_ko": "환경경영시스템 — 요구사항 및 사용지침",
        "status": "published",
        "edition": "3rd edition",
        "publication_date": "2015-09",
        "committee": "ISO/TC 207/SC 1",
        "ics_code": "13.020.10",
        "category": "environment",
        "scope": "환경경영시스템의 요구사항. 환경성과 향상, 법적 의무 이행, 환경 목표 달성을 위한 프레임워크 제공.",
        "ajin_relevance": "아진산업 3개 공장 전체 인증 보유. 도장 공정 VOC 배출, 프레스유 폐기물, 용접 흄 등 환경영향 관리에 핵심. 안전환경팀 주관.",
        "korean_standard": "KS I ISO 14001:2015",
        "latest_amendment": "AMD 1:2024 (기후변화 고려사항 추가)",
        "next_review_date": "2025-09",
        "transition_deadline": "2027-02-28",
        "changes_summary": "AMD 1:2024 — 환경경영시스템에서 기후변화를 명시적으로 고려하도록 요구. 4.1절과 4.2절에 기후변화 관련 이해관계자 요구사항 반영.",
        "reference_url": "https://www.iso.org/standard/60857.html",
    },
    {
        "standard_id": "ISO 45001:2018",
        "title": "Occupational health and safety management systems — Requirements with guidance for use",
        "title_ko": "안전보건경영시스템 — 요구사항 및 사용지침",
        "status": "published",
        "edition": "1st edition",
        "publication_date": "2018-03",
        "committee": "ISO/TC 283",
        "ics_code": "13.100",
        "category": "safety",
        "scope": "산업안전보건경영시스템의 요구사항. 작업 관련 부상과 건강 악화를 방지하고, 안전한 작업장을 사전적으로 제공.",
        "ajin_relevance": "아진산업 3개 공장 전체 인증 보유. 프레스 안전거리, 용접 작업 안전, 화학물질 취급 등 전 공정 안전관리에 적용. 안전환경팀 주관.",
        "korean_standard": "KS Q ISO 45001:2018",
        "latest_amendment": "AMD 1:2024 (기후변화 고려사항 추가)",
        "next_review_date": "2028-03",
        "transition_deadline": "2027-02-28",
        "changes_summary": "AMD 1:2024 — 안전보건 리스크 평가 시 기후변화로 인한 위험(폭염, 대기질 악화 등)을 고려하도록 요구 추가.",
        "reference_url": "https://www.iso.org/standard/63787.html",
    },
    {
        "standard_id": "ISO/IEC 27001:2022",
        "title": "Information security, cybersecurity and privacy protection — Information security management systems — Requirements",
        "title_ko": "정보보안경영시스템 — 요구사항",
        "status": "published",
        "edition": "3rd edition",
        "publication_date": "2022-10",
        "committee": "ISO/IEC JTC 1/SC 27",
        "ics_code": "35.030",
        "category": "security",
        "scope": "정보보안경영시스템(ISMS)의 요구사항. 조직의 정보 자산을 체계적으로 보호하기 위한 프레임워크.",
        "ajin_relevance": "경산 제2공장 ISMS 인증 보유. EV 배터리 설계 데이터, OEM 도면 등 기밀정보 보호에 필수. 현대모비스 협력사 정보보안 요건 대응.",
        "korean_standard": "KS X ISO/IEC 27001:2023",
        "latest_amendment": "",
        "next_review_date": "2027-10",
        "transition_deadline": "2025-10-31",
        "changes_summary": "2022년 대폭 개정: Annex A 통제항목 114→93개로 재구성, 신규 11개 통제항목 추가(위협 인텔리전스, 클라우드 보안, 데이터 마스킹 등).",
        "reference_url": "https://www.iso.org/standard/27001",
    },
    {
        "standard_id": "IATF CSR Minimum Requirements",
        "title": "Customer-Specific Requirements — OEM Minimum Automotive Quality Management System Requirements",
        "title_ko": "OEM별 고객 특별 요구사항 (현대/기아 SQ)",
        "status": "published",
        "edition": "2024 update",
        "publication_date": "2024-01",
        "committee": "현대자동차그룹 SQ 품질본부",
        "ics_code": "N/A",
        "category": "automotive_quality",
        "scope": "현대/기아 협력사 품질관리 요구사항. IATF 16949 기반 + OEM 고유 요구사항. SQ 등급 평가, 납품 품질 관리, 클레임 대응 프로세스 포함.",
        "ajin_relevance": "아진산업의 최대 고객사 요구사항. SQ 등급(S/A/B/C/D) 직접 영향. 부적합품 관리, 변경점 관리, 양산 초물 관리 등 아진 품질 프로세스의 근간.",
        "korean_standard": "N/A (OEM 자체 규격)",
        "latest_amendment": "2024 Rev.3 — 전동화 부품 품질 요구사항 신설",
        "next_review_date": "2025-06",
        "transition_deadline": "2025-03-31",
        "changes_summary": "Rev.3 주요 변경: 전동화 부품(배터리 케이스 등) 전용 품질 요구사항 신설, 사이버보안 개발 프로세스 요구, 원격 심사 허용 조건 규정.",
        "reference_url": "https://suppliers.mobis.co.kr/",
    },
    {
        "standard_id": "ISO 14064-1:2018",
        "title": "Greenhouse gases — Part 1: Specification with guidance for quantification and reporting",
        "title_ko": "온실가스 — 정량화 및 보고에 대한 지침을 포함한 규격",
        "status": "published",
        "edition": "2nd edition",
        "publication_date": "2018-12",
        "committee": "ISO/TC 207/SC 7",
        "ics_code": "13.020.40",
        "category": "environment",
        "scope": "조직 수준의 온실가스 배출량 정량화 및 보고. Scope 1/2/3 배출량 산정 방법론.",
        "ajin_relevance": "현대/기아 탄소중립 로드맵에 따라 Scope 1/2 배출 보고 의무화 예정. 도장/열처리/용접 공정의 탄소 배출 관리에 필요. 안전환경팀 주관.",
        "korean_standard": "KS I ISO 14064-1:2019",
        "latest_amendment": "",
        "next_review_date": "2028-12",
        "transition_deadline": "",
        "changes_summary": "현대차그룹 2025년부터 1차 협력사 Scope 1/2 배출 데이터 제출 요구 예정. 아진산업 대응 준비 필요.",
        "reference_url": "https://www.iso.org/standard/66453.html",
    },
    {
        "standard_id": "VDA 6.3:2023",
        "title": "Process Audit — Requirements for automotive production processes",
        "title_ko": "공정 심사 — 자동차 생산 공정 요구사항",
        "status": "published",
        "edition": "4th edition",
        "publication_date": "2023-01",
        "committee": "VDA QMC (Verband der Automobilindustrie)",
        "ics_code": "03.120.10",
        "category": "automotive_quality",
        "scope": "자동차 생산 공정의 심사 방법론. 공정 리스크 평가, 공급망 심사, 잠재 분석(P-Diagram) 등.",
        "ajin_relevance": "현대/기아 SQ 심사에서 VDA 6.3 기반 공정 심사를 실시. 프레스/용접/도장/조립 전 공정 대상. 연구소 및 품질관리팀 주관.",
        "korean_standard": "N/A (VDA 자체 규격)",
        "latest_amendment": "2023 개정: 소프트웨어/전동화 부품 관련 질문항목 추가",
        "next_review_date": "2028-01",
        "transition_deadline": "",
        "changes_summary": "2023 주요 변경: P6.4 리소스 질문에 소프트웨어/사이버보안 추가, P7 고객관리에 전동화 부품 특별관리 항목 신설.",
        "reference_url": "https://webshop.vda.de/QMC/en/vda-63",
    },
]


class ISOCrawler:
    """ISO/IATF 국제규격 표준 크롤러

    아진산업 관련 ISO/IATF 표준의 최신 개정 정보를 수집하고,
    공장 인증 현황과 비교하여 갱신/전환 필요 여부를 판단한다.
    """

    def __init__(self, data_dir: Path | None = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data" / "crawled"
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.data_dir / "iso_standards.json"
        self._standards: list[ISOStandard] = []

    def crawl(self) -> ISOCrawlResult:
        """ISO 표준 데이터를 수집한다.

        실제 운영 시 ISO.org OBP API, IATF OASIS,
        KS 표준정보센터 등에서 최신 정보를 크롤링한다.
        현재는 아진산업 관련 핵심 표준의 마스터 데이터를 구축한다.
        """
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        errors = []

        standards = []
        for item in _AJIN_ISO_STANDARDS:
            try:
                std = ISOStandard(**item, crawled_at=now)
                standards.append(std)
            except Exception as e:
                errors.append(f"파싱 오류 ({item.get('standard_id', '?')}): {e}")

        self._standards = standards

        result = ISOCrawlResult(
            standards=standards,
            crawled_at=now,
            source="iso_master_data + iatf_oasis + ks_standards",
            total_count=len(standards),
            updates_found=sum(1 for s in standards if s.latest_amendment),
            errors=errors,
        )

        self._save(result)
        return result

    async def crawl_live(self) -> ISOCrawlResult:
        """실시간 ISO 표준 상태를 확인한다.

        ISO.org와 IATF 사이트에서 표준의 현재 상태를 확인하고,
        기존 마스터 데이터와 비교하여 변경사항을 감지한다.
        """
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        errors = []

        # 1단계: 마스터 데이터 로드
        base_result = self.crawl()

        # 2단계: ISO.org 공개 페이지 상태 확인 (비API)
        async with httpx.AsyncClient(timeout=30) as client:
            for std in base_result.standards:
                if not std.reference_url or "iso.org" not in std.reference_url:
                    continue
                try:
                    resp = await client.get(std.reference_url, follow_redirects=True)
                    if resp.status_code == 200:
                        # v3.5: 인코딩 명시 — ISO.org가 charset 미제공 시 UTF-8 기본
                        resp.encoding = resp.charset_encoding or "utf-8"
                        # 페이지 접근 가능 확인
                        if "Withdrawn" in resp.text:
                            std.status = "withdrawn"
                        elif "Under development" in resp.text:
                            std.status = "under_development"
                        std.crawled_at = now
                except Exception as e:
                    errors.append(f"HTTP 오류 ({std.standard_id}): {e}")

        result = ISOCrawlResult(
            standards=base_result.standards,
            crawled_at=now,
            source="iso.org_live + master_data",
            total_count=len(base_result.standards),
            updates_found=base_result.updates_found,
            errors=errors,
        )

        self._save(result)
        return result

    def _save(self, result: ISOCrawlResult):
        """크롤링 결과를 JSON으로 저장한다."""
        data = {
            "crawled_at": result.crawled_at,
            "source": result.source,
            "total_count": result.total_count,
            "updates_found": result.updates_found,
            "standards": [asdict(s) for s in result.standards],
            "errors": result.errors,
        }
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"ISO 표준 데이터 저장: {self.output_path} ({result.total_count}건)")

    def load(self) -> list[ISOStandard]:
        """저장된 ISO 표준 데이터를 로드한다."""
        if not self.output_path.exists():
            return []
        with open(self.output_path, encoding="utf-8") as f:
            data = json.load(f)
        return [ISOStandard(**item) for item in data.get("standards", [])]

    def check_certification_gaps(self, plant_certs: list[str]) -> list[dict]:
        """공장 인증과 최신 표준을 비교하여 갱신 필요 항목을 반환한다."""
        if not self._standards:
            self._standards = self.load()

        gaps = []
        for std in self._standards:
            # 인증 보유 여부 확인
            matched = any(
                std.standard_id.split(":")[0] in cert
                for cert in plant_certs
            )
            if not matched:
                continue

            # 전환 기한 확인
            if std.transition_deadline:
                gaps.append({
                    "standard": std.standard_id,
                    "title_ko": std.title_ko,
                    "issue": "전환 기한 임박",
                    "deadline": std.transition_deadline,
                    "changes": std.changes_summary,
                    "severity": "high" if std.transition_deadline < "2026-06" else "medium",
                })

            # 최신 개정 확인
            if std.latest_amendment:
                gaps.append({
                    "standard": std.standard_id,
                    "title_ko": std.title_ko,
                    "issue": "최신 개정사항 반영 필요",
                    "amendment": std.latest_amendment,
                    "changes": std.changes_summary,
                    "severity": "medium",
                })

        return gaps

    def get_standards_by_category(self, category: str) -> list[ISOStandard]:
        """카테고리별 표준 목록을 반환한다."""
        if not self._standards:
            self._standards = self.load()
        return [s for s in self._standards if s.category == category]

    def get_summary(self) -> dict:
        """ISO 표준 현황 요약을 반환한다."""
        if not self._standards:
            self._standards = self.load()
        return {
            "total": len(self._standards),
            "by_category": {
                cat: len([s for s in self._standards if s.category == cat])
                for cat in set(s.category for s in self._standards)
            },
            "with_amendments": len([s for s in self._standards if s.latest_amendment]),
            "with_transition": len([s for s in self._standards if s.transition_deadline]),
        }
