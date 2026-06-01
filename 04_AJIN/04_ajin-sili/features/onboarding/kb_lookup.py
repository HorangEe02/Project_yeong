"""C5 v4.0 — Quick Question 의 promptText 와 매칭되는 KB 자료 자동 prepend.

흐름:
1. 사용자가 QuickPrompts 버튼 클릭 → 그 질문의 promptText 가 /chat 에 전송됨
2. 본 모듈이 dept 의 quick_questions JSON 을 읽어 promptText == req.query 매칭 항목 탐색
3. 매칭 항목에 `kb_doc_path` 가 있으면 해당 markdown 파일을 읽어 prompt 컨텍스트로 주입

자동 감지라 프론트 수정 불필요 — 일반 채팅에도 동일 promptText 면 KB 가 작동.

Feature C Sprint 1 P0 (plan §27.2) — `load_kb_context()` 가 `KBContext` TypedDict 반환.
Sprint 2 citation_enforcer 가 `citation_id` 로 출처 검증.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional, TypedDict

KB_BASE = Path("data/knowledge_base")
QQ_DIR = KB_BASE / "quick_questions"


class KBContext(TypedDict):
    """KB 매칭 결과 — Sprint 2 citation_enforcer 의 retrieved_docs entry."""
    text: str
    citation_id: str
    source_path: str


# YAML-like frontmatter 추출: `---\ncitation_id: XXX\n...\n---\n`
_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL
)
# frontmatter 내 `citation_id: VALUE` 추출
_CITATION_RE = re.compile(
    r"^citation_id:\s*([A-Za-z0-9_\-]+)\s*$", re.MULTILINE
)


def _extract_citation_id(content: str, default: str) -> str:
    """markdown 본문에서 citation_id 추출.

    1. YAML frontmatter 의 `citation_id: ...` 우선
    2. 없으면 default (보통 파일명 stem)
    """
    m = _FRONTMATTER_RE.match(content)
    if m:
        meta_block = m.group(1)
        cm = _CITATION_RE.search(meta_block)
        if cm:
            return cm.group(1).strip()
    return default


def _strip_frontmatter(content: str) -> str:
    """frontmatter 블록 제거 — 본문만 반환."""
    m = _FRONTMATTER_RE.match(content)
    if m:
        return content[m.end():]
    return content


def _load_quick_questions(department: str) -> list[dict]:
    """{department}.json + _common.json 합쳐서 반환. 파일 없으면 빈 리스트."""
    items: list[dict] = []
    paths = [
        QQ_DIR / f"{department}.json",
        QQ_DIR / "_common.json",
    ]
    for p in paths:
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        items.extend(data.get("questions", []))
    return items


def _localized_path(path: Path, language: str) -> Path:
    """v4.7 C-2 — 영문 페어(*.en.md)가 존재하면 그 경로, 없으면 원본 KO 경로.

    예: data/knowledge_base/department_guides/총무인사팀_복리후생.md
        → language='en' 이면 같은 폴더의 총무인사팀_복리후생.en.md 사용 (존재 시).
    """
    if language != "en":
        return path
    # path.with_suffix 는 .md.en 으로 잘못 만들어지므로 stem 직접 조작
    en_path = path.with_name(f"{path.stem}.en{path.suffix}")
    if en_path.exists():
        return en_path
    return path


def find_kb_doc_for_query(query: str, department: str, language: str = "ko") -> Optional[Path]:
    """query 가 quick_questions 의 promptText 와 일치하면 kb_doc_path 반환.

    매칭 우선순위:
    1. 정확 일치 (strip 후 동일)
    2. 부분 포함 (kb 항목의 promptText 가 query 의 substring 또는 반대)

    v4.7 C-2: language='en' 이면 동일 이름의 *.en.md 우선 사용 (없으면 ko 사용).
    """
    q = query.strip()
    if not q:
        return None

    items = _load_quick_questions(department)
    if not items:
        return None

    # 1) 정확 일치
    for it in items:
        pt = (it.get("promptText") or "").strip()
        kb = it.get("kb_doc_path")
        if not kb:
            continue
        if pt == q:
            path = KB_BASE / kb
            if path.exists():
                return _localized_path(path, language)

    # 2) 부분 포함 (양방향)
    for it in items:
        pt = (it.get("promptText") or "").strip()
        kb = it.get("kb_doc_path")
        if not kb or not pt:
            continue
        if pt in q or q in pt:
            path = KB_BASE / kb
            if path.exists():
                return _localized_path(path, language)

    return None


def load_kb_context(
    query: str, department: str, max_chars: int = 4000, language: str = "ko"
) -> Optional[KBContext]:
    """매칭 KB 자료가 있으면 `KBContext` 반환. 없으면 None.

    Feature C Sprint 1 P0 — 반환 타입 변경:
      - 기존: `str` (빈 문자열 = no-match)
      - 신규: `Optional[KBContext]` (None = no-match)

    citation_id 추출:
      1. markdown frontmatter `---\\ncitation_id: XXX\\n---` 우선
      2. 없으면 파일명 stem 을 fallback citation_id 로 사용 (legacy markdown 호환)

    잘림 시 끝부분에 "(이하 생략)" 마커 추가.
    """
    path = find_kb_doc_for_query(query, department, language=language)
    if path is None:
        return None
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return None

    citation_id = _extract_citation_id(content, default=path.stem.replace(".en", ""))
    body = _strip_frontmatter(content)
    if len(body) > max_chars:
        truncation_marker = (
            "\n\n…(이하 생략, 사내 인트라넷 또는 인사관리팀 문의)"
            if language != "en"
            else "\n\n…(truncated — see intranet or contact HR)"
        )
        body = body[:max_chars] + truncation_marker

    return {
        "text": body,
        "citation_id": citation_id,
        "source_path": str(path.relative_to(KB_BASE.parent)) if KB_BASE.parent in path.parents else str(path),
    }
