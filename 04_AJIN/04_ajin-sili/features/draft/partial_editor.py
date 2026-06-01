"""B3 — 대화형 부분 수정 (Partial Edit).

본문에서 명시적 섹션 마커(예: ## 1., ### D3., [Section: A], 8D Step 3)를
정규식으로 분리해 사용자가 지정한 단일 섹션만 LLM 으로 재생성한다.

전체 재생성 대비:
- 토큰 비용 ~50% 절감 (해당 섹션 + 인근 컨텍스트만 LLM 입력)
- 응답 시간 단축
- 다른 단락의 톤/내용 보존 (사용자가 다듬은 부분 유지)

설계 원칙: LLM 에 섹션 식별을 맡기지 않는다. 명시적 마커 파싱으로
예측 가능성·재현성 확보.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# 명시적 섹션 마커 패턴 (우선순위 순서)
# 각 패턴은 한 줄 매칭 + 섹션 헤더로 인식할 라인 식별.
SECTION_MARKERS = [
    # Markdown 헤더 (#, ##, ### 등) — 가장 흔한 케이스
    re.compile(r"^(?P<marker>#{1,6})\s+(?P<title>.+?)\s*$", re.MULTILINE),
    # 8D 단계 — D1. ~ D8. (한국어/영어 혼용)
    re.compile(r"^(?P<marker>D[1-8])\.\s+(?P<title>.+?)\s*$", re.MULTILINE),
    # [Section: X] 또는 [섹션: X]
    re.compile(r"^\[(?:Section|섹션):\s*(?P<title>[^\]]+)\]\s*$", re.MULTILINE),
    # 8D Step N
    re.compile(r"^(?P<marker>8D Step \d+)\s*[:\-—]?\s*(?P<title>.*?)\s*$", re.MULTILINE),
    # 번호 매김 — "1. " "2. " 등 (라인 시작)
    re.compile(r"^(?P<marker>\d+)\.\s+(?P<title>.+?)\s*$", re.MULTILINE),
]


@dataclass
class Section:
    """본문의 한 섹션."""

    index: int           # 0-based
    marker: str          # "##", "D3", "1." 등
    title: str           # 헤더 텍스트
    start: int           # 본문 내 시작 char offset (헤더 라인 시작)
    end: int             # 본문 내 끝 char offset (다음 섹션 시작 또는 EOF)
    content: str         # 헤더 포함 섹션 전체 텍스트


@dataclass
class PartialEditContext:
    """부분 수정 LLM 입력 컨텍스트."""

    target_section: Section
    prev_section_excerpt: str = ""   # 직전 섹션 마지막 ~200 chars (문맥 유지)
    next_section_excerpt: str = ""   # 다음 섹션 첫 ~200 chars
    full_doc_summary: str = ""       # (옵션) 전체 문서 한 줄 요약
    instruction: str = ""            # 사용자 명령 ("조금 더 정중하게")
    metadata: dict = field(default_factory=dict)  # doc_type, tone 등


def find_sections(body: str) -> list[Section]:
    """본문에서 명시적 섹션 마커를 찾아 Section 리스트 반환.

    여러 패턴이 매칭되면 라인 번호 순으로 정렬. 동일 라인에 두 패턴이
    매칭되면 우선순위(SECTION_MARKERS 등록 순서) 기준 첫 번째만 채택.
    """
    if not body:
        return []

    # (start_offset, end_of_line_offset, marker, title)
    candidates: list[tuple[int, int, str, str]] = []
    seen_starts: set[int] = set()

    for pattern in SECTION_MARKERS:
        for m in pattern.finditer(body):
            line_start = m.start()
            if line_start in seen_starts:
                continue
            seen_starts.add(line_start)
            marker = m.groupdict().get("marker", "")
            title = m.groupdict().get("title", "").strip()
            candidates.append((line_start, m.end(), marker, title))

    # 시작 오프셋 순 정렬
    candidates.sort(key=lambda t: t[0])

    sections: list[Section] = []
    for i, (start, _line_end, marker, title) in enumerate(candidates):
        end = candidates[i + 1][0] if i + 1 < len(candidates) else len(body)
        sections.append(
            Section(
                index=i,
                marker=marker or "",
                title=title or "",
                start=start,
                end=end,
                content=body[start:end].rstrip() + "\n",
            )
        )
    return sections


def build_partial_edit_context(
    body: str,
    target_section_index: int,
    instruction: str,
    metadata: dict | None = None,
) -> PartialEditContext | None:
    """타겟 섹션 + 인근 컨텍스트를 묶어 LLM 입력 준비."""
    sections = find_sections(body)
    if not sections:
        return None
    if target_section_index < 0 or target_section_index >= len(sections):
        return None

    target = sections[target_section_index]
    prev_excerpt = ""
    next_excerpt = ""
    if target_section_index > 0:
        prev_excerpt = sections[target_section_index - 1].content[-220:]
    if target_section_index + 1 < len(sections):
        next_excerpt = sections[target_section_index + 1].content[:220]

    return PartialEditContext(
        target_section=target,
        prev_section_excerpt=prev_excerpt,
        next_section_excerpt=next_excerpt,
        instruction=instruction,
        metadata=metadata or {},
    )


def render_partial_edit_prompt(ctx: PartialEditContext) -> str:
    """LLM 인스트럭션 + 컨텍스트로 프롬프트 합성.

    명시적 instruction 우선. 직전/다음 섹션을 컨텍스트로 보여주고 변경 금지를
    명확히 한다 (LLM 이 다른 섹션도 재작성하는 사고 방지).
    """
    doc_type = ctx.metadata.get("doc_type", "문서")
    tone = ctx.metadata.get("tone", "표준")

    lines: list[str] = []
    lines.append(f"당신은 {doc_type} 작성을 돕는 어시스턴트입니다.")
    lines.append(f"어조: {tone}")
    lines.append("")
    lines.append("아래는 사용자가 작성 중인 문서의 일부입니다.")
    lines.append("**오직 타겟 섹션만 다시 작성**하세요. 직전/다음 섹션은 변경하지 마세요.")
    lines.append("")
    if ctx.prev_section_excerpt:
        lines.append("=== 직전 섹션 (참고만, 변경 금지) ===")
        lines.append(ctx.prev_section_excerpt.strip())
        lines.append("")
    lines.append("=== 타겟 섹션 (이 부분만 재작성) ===")
    lines.append(ctx.target_section.content.strip())
    lines.append("")
    if ctx.next_section_excerpt:
        lines.append("=== 다음 섹션 (참고만, 변경 금지) ===")
        lines.append(ctx.next_section_excerpt.strip())
        lines.append("")
    lines.append("=== 사용자 명령 ===")
    lines.append(ctx.instruction)
    lines.append("")
    lines.append("=== 출력 ===")
    lines.append("재작성된 타겟 섹션 (헤더 포함, 마크다운 형식 유지):")
    return "\n".join(lines)


def replace_section(body: str, section: Section, new_content: str) -> str:
    """본문에서 한 섹션을 새 내용으로 교체."""
    new_content = new_content.rstrip() + "\n"
    return body[: section.start] + new_content + body[section.end :]
