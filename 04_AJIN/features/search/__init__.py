"""Phase 6: 통합 검색 파이프라인

사용자 질의를 받아 메타데이터 추출 → 하이브리드 검색 → 결과 포맷팅을
하나의 함수로 묶는다.

v3.6.1 — top-level import 제거(lazy import).
이전엔 `from features.search.searcher import HybridSearcher` 가 여기서 unconditional
실행되어, slim 배포 컨테이너처럼 `rank_bm25` / `langchain-chroma` 가 빠진 환경에서
*어떤 모듈이라도* `features.search` 패키지 경로를 거쳐 import 하면 ImportError 가
연쇄 발생했다 (예: `features.search.employee.analytics` 호출 시 부모 init 실행 →
admin/HR Stats 라우트가 500 폭발).

본 패키지는 search_documents() 호출 시점에만 실제 검색 의존성을 lazy 로 끌어온다.
type hint 정합성은 `from __future__ import annotations` + TYPE_CHECKING 으로 보존.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 정적 분석/타입 체크 시에만 import. 런타임에는 실행되지 않으므로 BM25/Chroma
    # 미설치 환경에서도 패키지 import 가 깨지지 않는다.
    from features.search.searcher import HybridSearcher, SearchResult


async def search_documents(
    query: str,
    searcher: "HybridSearcher",
    use_llm_extraction: bool = False,
) -> "tuple[str, list[SearchResult]]":
    """사용자 질의를 받아 전체 검색 파이프라인을 실행한다.

    Args:
        query: 사용자의 자연어 검색 질의
        searcher: HybridSearcher 인스턴스
        use_llm_extraction: True이면 LLM으로 메타데이터 추출

    Returns:
        (포맷팅된 결과 텍스트, SearchResult 리스트)
    """
    # Lazy import — 본 함수가 실제로 호출될 때만 검색 의존성을 끌어온다.
    from features.search.metadata_extractor import extract_metadata
    from features.search.summarizer import format_results_for_display

    # 1. 질의에서 메타데이터 추출
    metadata = await extract_metadata(query, use_llm=use_llm_extraction)

    # 2. 하이브리드 검색 (메타데이터 필터 적용)
    results = searcher.search(
        query=metadata.search_query,
        k=5,
        doc_type_filter=metadata.doc_type,
        part_name_filter=metadata.part_name,
        date_from=metadata.date_from,
        date_to=metadata.date_to,
    )

    # 3. 결과 포맷팅
    formatted = format_results_for_display(query, results)

    return formatted, results
