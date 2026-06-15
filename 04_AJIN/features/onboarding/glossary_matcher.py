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
    citation_id: str = ""
    owner_department: str = ""
    reviewed_at: str = ""
    effective_date: str = ""
    version: str = ""
    status: str = "published"
    source_path: str = ""


# 한국어 조사 목록 (긴 것부터 매칭)
PARTICLES = [
    "에서는", "이란게", "이란건", "이란거",
    "에서", "에게", "으로", "이란", "이라는",
    "뭐야", "뭔가요", "알려줘", "설명해줘", "가르쳐줘",
    "은", "는", "이", "가", "을", "를", "의", "도", "에",
    "란", "요", "좀",
]


# v2.0: 용어 별칭(alias) — 구어체/약어/영어를 정식 용어명으로 매핑 (80+항목)
# Feature C Sprint 1 P0 (plan §27) — 별칭 외부화.
# 정의는 별도 JSON, 별칭은 data/knowledge_base/glossary_aliases/aliases.json.
# admin 편집 직후 다음 호출에서 반영 (mtime 캐싱).

import threading as _threading

_ALIASES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge_base" / "glossary_aliases" / "aliases.json"
_ALIASES_CACHE: dict[str, str] | None = None
_ALIASES_MTIME: float = 0.0
_ALIASES_LOCK = _threading.Lock()


def _load_aliases() -> dict[str, str]:
    """aliases.json 로드 (mtime 캐싱). 파일 부재 시 빈 dict."""
    global _ALIASES_CACHE, _ALIASES_MTIME
    with _ALIASES_LOCK:
        if not _ALIASES_PATH.exists():
            _ALIASES_CACHE = {}
            return _ALIASES_CACHE
        mtime = _ALIASES_PATH.stat().st_mtime
        if _ALIASES_CACHE is not None and mtime == _ALIASES_MTIME:
            return _ALIASES_CACHE
        try:
            data = json.loads(_ALIASES_PATH.read_text(encoding="utf-8"))
            _ALIASES_CACHE = {str(k): str(v) for k, v in data.items()}
        except json.JSONDecodeError:
            _ALIASES_CACHE = {}
        _ALIASES_MTIME = mtime
        return _ALIASES_CACHE


def __getattr__(name):
    """PEP 562 — TERM_ALIASES lazy lookup. 호출자 zero touch."""
    if name == "TERM_ALIASES":
        return _load_aliases()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")




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
                    if entry.status != "published":
                        continue
                    self.entries[entry.term] = entry
                except TypeError:
                    # 필드 불일치 — 부분 매핑 시도
                    entry = self._make_entry_flexible(item)
                    if entry and entry.status == "published":
                        self.entries[entry.term] = entry
                except Exception:
                    continue  # v2.6: 개별 항목 실패 시 스킵 (전체 중단 방지)

        # 2단계: 키 등록 (다른 용어명과 충돌하는 태그 제외)
        all_term_names = {t.lower() for t in self.entries}
        for entry in self.entries.values():
            self._register_keys(entry, all_term_names)

        # v1.6: alias 등록 — 구어체/약어를 정식 용어로 매핑
        # NOTE: 모듈 전역 `TERM_ALIASES`는 PEP 562 `__getattr__`로 노출되나
        # 모듈 자체 함수 본문에서는 자동 해석되지 않으므로 직접 로더 호출.
        for alias, term in _load_aliases().items():
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
            inherited = {
                k: data.get(k)
                for k in (
                    "citation_id",
                    "owner_department",
                    "reviewed_at",
                    "effective_date",
                    "version",
                    "status",
                    "source_path",
                )
                if data.get(k)
            }
            # Type C: terms가 리스트 [{"term": ...}, ...]
            if isinstance(terms, list):
                return [
                    {**inherited, **item} if isinstance(item, dict) else item
                    for item in terms
                ]
            # v2.6 Type D: terms가 딕셔너리 {"용어": "설명문자열", ...}
            if isinstance(terms, dict):
                items = []
                for key, val in terms.items():
                    if isinstance(val, str):
                        items.append({**inherited, "term": key, "definition": val})
                    elif isinstance(val, dict):
                        if "term" not in val:
                            val["term"] = key
                        items.append({**inherited, **val})
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
            citation_id=item.get("citation_id", ""),
            owner_department=item.get("owner_department", ""),
            reviewed_at=item.get("reviewed_at", ""),
            effective_date=item.get("effective_date", ""),
            version=item.get("version", ""),
            status=item.get("status", "published"),
            source_path=item.get("source_path", ""),
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
