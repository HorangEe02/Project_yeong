"""Phase 3: 용어 사전 정확 매칭기

JSON 기반 용어 사전을 메모리에 로드하고,
사용자 질의에서 용어를 정확히 매칭하여 즉시 응답한다.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GlossaryEntry:
    """용어 사전 엔트리"""
    term: str
    full_name: str
    korean_name: str
    category: str
    definition: str
    ajin_context: str
    example: str
    related_terms: list[str] = field(default_factory=list)
    departments_involved: list[str] = field(default_factory=list)
    difficulty: str = "basic"
    tags: list[str] = field(default_factory=list)


# 한국어 조사 목록 (긴 것부터 매칭)
PARTICLES = [
    "에서는", "이란게", "이란건", "이란거",
    "에서", "에게", "으로", "이란", "이라는",
    "뭐야", "뭔가요", "알려줘", "설명해줘", "가르쳐줘",
    "은", "는", "이", "가", "을", "를", "의", "도", "에",
    "란", "요", "좀",
]


# v2.0: 용어 별칭(alias) — 구어체/약어/영어를 정식 용어명으로 매핑 (80+항목)
TERM_ALIASES: dict[str, str] = {
    # ── EV 부품 ──
    "워터펌프": "EWP", "전동워터펌프": "EWP", "water pump": "EWP",
    "쿨링채널": "CCH", "냉각채널": "CCH", "cooling channel": "CCH",
    "충전기": "OBC", "온보드차저": "OBC",
    "배터리관리": "BMS", "배터리시스템": "BMS",
    # ── 글로벌 ──
    "조지아": "JOON INC", "조지아공장": "JOON INC", "준": "JOON INC", "georgia": "JOON INC",
    "메타플랜트": "HMGMA", "현대메타플랜트": "HMGMA", "metaplant": "HMGMA",
    "앨라배마": "AJIN USA", "alabama": "AJIN USA",
    "인플레이션감축법": "IRA", "감축법": "IRA",
    # ── 경량화 ──
    "탄소섬유": "CFRP", "carbon fiber": "CFRP",
    "프리프레그": "Prepreg",
    # ── 품질 (dept_quality_terms) ──
    "공정능력": "Cpk", "공정능력지수": "Cpk",
    "위험우선순위": "RPN", "알피엔": "RPN",
    "부품제출보증서": "PSW", "피에스더블유": "PSW",
    "측정시스템분석": "MSA", "엠에스에이": "MSA",
    "팔디": "8D", "8디": "8D", "에잇디": "8D",
    "피피엠": "PPM", "불량률": "PPM",
    "씨피케이": "Cpk", "공정능력치": "Cpk",
    "초물검사": "초물", "첫물": "초물",
    "전수검사": "전검",
    "리워크": "리워크", "재작업": "리워크",
    "스크랩": "스크랩", "폐기": "스크랩",
    "합부판정": "양불 판정", "양부판정": "양불 판정",
    # ── 생산 (dept_production_terms) ──
    "사이클": "C/T", "사이클타임": "C/T", "씨티": "C/T",
    "택트": "택타임", "tact time": "택타임",
    "간판": "칸반", "kanban": "칸반",
    "가동율": "가동률",
    "오이이": "OEE", "설비종합효율": "OEE",
    "작업지시서": "작지", "워크오더": "작지",
    "포카요케": "포카요케", "실수방지": "포카요케",
    "안돈": "안돈", "이상알림": "안돈",
    # ── 생산기술 (dept_production_engineering_terms) ──
    "트라이": "T/O", "트라이아웃": "T/O", "tryout": "T/O",
    "탄성회복": "스프링백", "springback": "스프링백",
    "버": "바리", "burr": "바리",
    "에스엠이디": "SMED", "싱글교체": "SMED",
    "치구": "지그", "jig": "지그",
    "캐파": "CAPA", "시정예방": "CAPA",
    # ── 구매 (dept_purchasing_terms) ──
    "최소발주": "MOQ", "엠오큐": "MOQ",
    "발주서": "PO", "피오": "PO",
    "리드타임": "L/T", "엘티": "L/T",
    "공급사": "벤더", "vendor": "벤더",
    "원가절감": "VA/VE", "코스트다운": "코스트 다운",
    "소모품": "MRO",
    # ── 영업 (dept_sales_terms) ──
    "견적요청": "RFQ", "알에프큐": "RFQ",
    "완성차": "OEM", "오이엠": "OEM",
    "수요예측": "포캐스트", "forecast": "포캐스트",
    "신규개발": "NPI",
    "양산개시": "SOP",
    "생산종료": "EOP",
    # ── R&D (dept_rnd_terms) ──
    "설변요청": "ECR", "설계변경요청": "ECR",
    "설변통보": "ECN", "설계변경통보": "ECN",
    "기하공차": "GD&T", "지디앤티": "GD&T",
    "시제품": "시작품", "prototype": "시작품",
    "바디인화이트": "BIW", "비아이더블유": "BIW",
    "설계검증": "DVPR", "디비피알": "DVPR",
    # ── 안전 (dept_safety_terms) ──
    "산안": "산안법", "산업안전보건법": "산안법",
    "티비엠": "TBM", "툴박스미팅": "TBM",
    "니어미스": "아차사고", "near miss": "아차사고",
    "잠금태그": "LOTO", "lockout tagout": "LOTO",
    "보호구": "PPE", "피피이": "PPE",
    "중대재해법": "중대재해",
    # ── 관리 (dept_management_terms) ──
    "이알피": "ERP", "사프": "ERP",
    "엠이에스": "MES", "생산실행": "MES",
    "핵심지표": "KPI", "케이피아이": "KPI",
    "결재라인": "결재 라인",
    "품의": "품의서",
    # ── 공통 (dept_common_terms) ──
    "포엠": "4M 변경", "4M변경": "4M 변경",
    "카이젠": "개선", "kaizen": "개선",
    "오에스": "3정 5S", "5에스": "3정 5S",
    "수평전개": "수평전개", "요코텐": "수평전개",
}


class GlossaryMatcher:
    """용어 사전 정확 매칭기"""

    def __init__(self, glossary_dir: Path):
        self.glossary_dir = glossary_dir  # v2.6: file_count 프로퍼티에서 참조
        self.entries: dict[str, GlossaryEntry] = {}
        self._lookup: dict[str, str] = {}  # 검색키 → 원본 term
        self._load_all(glossary_dir)

    def _load_all(self, glossary_dir: Path):
        """모든 JSON 파일을 로드하고 다양한 검색 키를 등록한다.

        v2.0: 3종 JSON 구조 호환
          - Type A (Array): [{"term": ...}, ...]
          - Type B (Dict): {"TERM": {"definition": ...}, ...}
          - Type C (Dict+metadata): {"category": ..., "terms": [...]}
        """
        # 1단계: 모든 용어를 먼저 로드
        for json_file in glossary_dir.glob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            items = self._extract_terms(data)
            for item in items:
                try:
                    entry = GlossaryEntry(**item)
                    self.entries[entry.term] = entry
                except TypeError:
                    # 필드 불일치 — 부분 매핑 시도
                    entry = self._make_entry_flexible(item)
                    if entry:
                        self.entries[entry.term] = entry
                except Exception:
                    continue  # v2.6: 개별 항목 실패 시 스킵 (전체 중단 방지)

        # 2단계: 키 등록 (다른 용어명과 충돌하는 태그 제외)
        all_term_names = {t.lower() for t in self.entries}
        for entry in self.entries.values():
            self._register_keys(entry, all_term_names)

        # v1.6: alias 등록 — 구어체/약어를 정식 용어로 매핑
        for alias, term in TERM_ALIASES.items():
            if term in self.entries and alias.lower() not in self._lookup:
                self._lookup[alias.lower()] = term

    @staticmethod
    def _extract_terms(data) -> list[dict]:
        """JSON 데이터에서 용어 리스트를 추출한다 (4종 구조 호환).

        v2.6: Type D 추가 — {"terms": {"용어": "설명문자열", ...}}
        """
        # Type C/D: {"category": ..., "terms": ...}
        if isinstance(data, dict) and "terms" in data:
            terms = data["terms"]
            # Type C: terms가 리스트 [{"term": ...}, ...]
            if isinstance(terms, list):
                return terms
            # v2.6 Type D: terms가 딕셔너리 {"용어": "설명문자열", ...}
            if isinstance(terms, dict):
                items = []
                for key, val in terms.items():
                    if isinstance(val, str):
                        items.append({"term": key, "definition": val})
                    elif isinstance(val, dict):
                        if "term" not in val:
                            val["term"] = key
                        items.append(val)
                return items
            return []

        # Type A: [{"term": ...}, ...]
        if isinstance(data, list):
            return data

        # Type B: {"TERM_KEY": {"definition": ...}, ...}
        if isinstance(data, dict):
            items = []
            for key, val in data.items():
                if isinstance(val, dict):
                    if "term" not in val:
                        val["term"] = key
                    items.append(val)
            return items

        return []

    @staticmethod
    def _make_entry_flexible(item: dict) -> "GlossaryEntry | None":
        """다양한 필드명을 가진 JSON 항목을 GlossaryEntry로 변환한다."""
        term = item.get("term", "")
        if not term:
            return None

        return GlossaryEntry(
            term=term,
            full_name=item.get("full_name", ""),
            korean_name=item.get("korean_name", item.get("name_ko", "")),
            category=item.get("category", ""),
            definition=item.get("definition", ""),
            ajin_context=item.get("ajin_context", item.get("usage_example", "")),
            example=item.get("example", ""),
            related_terms=item.get("related_terms", []),
            departments_involved=item.get("departments_involved", item.get("department", [])),
            difficulty=item.get("difficulty", "basic"),
            tags=item.get("tags", item.get("aliases", [])),
        )

    def _register_keys(self, entry: GlossaryEntry, all_term_names: set[str] = None):
        """하나의 용어에 대해 다양한 검색 키를 등록한다."""
        if all_term_names is None:
            all_term_names = set()

        primary_keys = set()  # 우선 등록 (term, full_name, korean_name)
        tag_keys = set()      # 태그 (충돌 체크 필요)

        # 원본 term
        primary_keys.add(entry.term)
        primary_keys.add(entry.term.lower())

        # 영문 정식명
        if entry.full_name:
            primary_keys.add(entry.full_name)
            primary_keys.add(entry.full_name.lower())

        # 한국어 정식명
        if entry.korean_name:
            primary_keys.add(entry.korean_name)

        # 괄호 안 내용 추출 (예: "설비예방보전(PM)" → "PM", "설비예방보전")
        paren_match = re.match(r"(.+?)\((.+?)\)", entry.term)
        if paren_match:
            primary_keys.add(paren_match.group(1))
            primary_keys.add(paren_match.group(2))
            primary_keys.add(paren_match.group(2).lower())

        # 공백 제거 변형
        no_space = entry.term.replace(" ", "")
        if no_space != entry.term:
            primary_keys.add(no_space)

        # 태그 (다른 용어명과 충돌하면 제외)
        for tag in entry.tags:
            tag_lower = tag.lower()
            if tag_lower not in all_term_names or tag_lower == entry.term.lower():
                tag_keys.add(tag)
                tag_keys.add(tag_lower)

        # 우선 키 먼저 등록 (덮어쓰기 가능)
        for key in primary_keys:
            if key and len(key) >= 2:
                self._lookup[key] = entry.term

        # 태그는 기존 키가 없을 때만 등록
        for key in tag_keys:
            if key and len(key) >= 2 and key not in self._lookup:
                self._lookup[key] = entry.term

    def match(self, query: str) -> GlossaryEntry | None:
        """사용자 질의에서 용어를 매칭한다.

        2단계 매칭:
        1) 질의에 용어가 포함되어 있는지 확인 (긴 키부터)
        2) 한국어 조사 제거 후 재시도
        """
        # 1단계: 원본 질의에서 매칭
        result = self._find_in_query(query)
        if result:
            return result

        # 2단계: 조사 제거 후 재시도
        cleaned = self._remove_particles(query)
        if cleaned != query:
            result = self._find_in_query(cleaned)
            if result:
                return result

        return None

    def _find_in_query(self, query: str) -> GlossaryEntry | None:
        """질의 텍스트에서 등록된 키를 찾는다 (긴 키 우선).

        영문 키는 단어 경계를 체크하여 부분 매칭을 방지한다.
        예: "PPAP"는 매칭하되, "PP"가 "PPAP" 안에서 매칭되지 않도록.
        """
        query_lower = query.lower()

        # 긴 키부터 매칭 (정확도 향상)
        sorted_keys = sorted(self._lookup.keys(), key=len, reverse=True)

        for key in sorted_keys:
            key_lower = key.lower()
            # 영문/숫자로만 된 키는 단어 경계 체크
            if key.isascii() and len(key) <= 4:
                pattern = re.compile(r'(?<![A-Za-z0-9])' + re.escape(key) + r'(?![A-Za-z0-9])', re.IGNORECASE)
                if pattern.search(query):
                    term = self._lookup[key]
                    return self.entries.get(term)
            else:
                if key in query or key_lower in query_lower:
                    term = self._lookup[key]
                    return self.entries.get(term)

        return None

    def _remove_particles(self, text: str) -> str:
        """한국어 조사와 질문 표현을 제거한다."""
        result = text
        for particle in PARTICLES:
            result = result.replace(particle, "")
        result = re.sub(r"\s+", " ", result).strip()
        result = result.rstrip("?？ ")
        return result

    def get_related_entries(
        self, entry: GlossaryEntry | None
    ) -> list[GlossaryEntry]:
        """관련 용어의 GlossaryEntry 목록을 반환한다."""
        if not entry:
            return []

        related = []
        for term_name in entry.related_terms:
            if term_name in self.entries:
                related.append(self.entries[term_name])
            else:
                # 대소문자 무시 검색
                for key, val in self._lookup.items():
                    if key.lower() == term_name.lower() and val in self.entries:
                        related.append(self.entries[val])
                        break
        return related

    def search_by_department(self, department: str) -> list[GlossaryEntry]:
        """특정 부서가 관련된 용어 목록을 반환한다."""
        return [
            entry for entry in self.entries.values()
            if department in entry.departments_involved
        ]

    @property
    def total_terms(self) -> int:
        return len(self.entries)

    @property
    def file_count(self) -> int:
        """로드된 용어 JSON 파일 수."""
        if self.glossary_dir and self.glossary_dir.is_dir():
            return len(list(self.glossary_dir.glob("*.json")))
        return 0


# ── 모듈 레벨 캐시 함수 (dashboard/onboarding 등에서 공유) ──
import functools

@functools.lru_cache(maxsize=1)
def get_glossary_stats() -> tuple[int, int]:
    """(총 용어 수, 파일 수) 튜플을 캐시하여 반환한다."""
    try:
        from config import GLOSSARY_DIR
        matcher = GlossaryMatcher(GLOSSARY_DIR)
        return matcher.total_terms, matcher.file_count
    except Exception:
        return 0, 0
