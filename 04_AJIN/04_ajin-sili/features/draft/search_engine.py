"""
문서 검색 엔진 v3.0 — 가중치 BM25 + Semantic 하이브리드 + 메타데이터 필터
기존 ChromaDB 벡터 검색에 BM25 가중치 조정 + 문서 메타 필터를 추가합니다.
"""
import logging
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SearchFilter:
    """문서 검색 필터"""
    doc_type: Optional[str] = None       # "8D", "ECN", "PPAP", "이메일", "회의록" 등
    department: Optional[str] = None     # 작성 부서
    context: Optional[str] = None        # "internal" / "external"
    date_from: Optional[str] = None      # ISO 날짜 (이후)
    date_to: Optional[str] = None        # ISO 날짜 (이전)
    language: Optional[str] = None       # "ko" / "en" / "ko_en"


@dataclass
class SearchResult:
    """검색 결과 단일 항목"""
    doc_id: str
    title: str
    content_preview: str
    doc_type: str
    score: float
    metadata: dict = field(default_factory=dict)
    source_file: str = ""


# ── 문서 유형별 BM25 가중치 ──
FIELD_WEIGHTS = {
    "title": 3.0,
    "doc_type": 2.5,
    "department": 2.0,
    "content": 1.0,
    "tags": 1.5,
}

# ── 문서 유형 키워드 매핑 (검색어 → 문서 유형 자동 감지) ──
DOC_TYPE_KEYWORDS = {
    "8D": ["8d", "8디", "불량", "시정조치", "corrective"],
    "ECN": ["ecn", "설계변경", "변경통보", "engineering change"],
    "PPAP": ["ppap", "양산승인", "제출", "submission"],
    "이메일": ["이메일", "email", "메일", "회신"],
    "회의록": ["회의록", "회의", "미팅", "meeting", "분기회의"],
    "SOP": ["sop", "표준", "절차서", "작업지시"],
    "품질개선": ["개선대책", "품질개선", "quality improvement"],
    "인시던트": ["인시던트", "사고", "incident", "안전"],
    "규제": ["규제", "regulation", "법규", "iso", "reach"],
}


def detect_doc_type_from_query(query: str) -> Optional[str]:
    """검색어에서 문서 유형을 자동 감지합니다."""
    q_lower = query.lower()
    for doc_type, keywords in DOC_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in q_lower:
                return doc_type
    return None


def weighted_bm25_score(
    query: str,
    document: dict,
    weights: dict = None,
) -> float:
    """
    필드별 가중치를 적용한 BM25 유사 점수를 계산합니다.
    정식 BM25가 아닌 간이 TF-IDF 가중치입니다.
    """
    if weights is None:
        weights = FIELD_WEIGHTS

    query_tokens = set(query.lower().split())
    total_score = 0.0

    for field_name, weight in weights.items():
        field_value = str(document.get(field_name, "")).lower()
        if not field_value:
            continue

        field_tokens = set(field_value.split())
        matches = len(query_tokens & field_tokens)

        if matches > 0:
            field_len = max(len(field_tokens), 1)
            tf = matches / field_len
            total_score += tf * weight

    return round(total_score, 4)


def search_documents(
    query: str,
    filters: SearchFilter = None,
    limit: int = 20,
    hybrid_alpha: float = 0.6,
) -> list[SearchResult]:
    """
    하이브리드 문서 검색을 수행합니다.

    Args:
        query: 검색어
        filters: 메타데이터 필터
        limit: 최대 결과 수
        hybrid_alpha: BM25(1.0) <-> Semantic(0.0) 비율 (0.6 = BM25 60%)

    Returns:
        정렬된 SearchResult 리스트
    """
    results = []

    # 문서 유형 자동 감지 (필터에 없으면)
    if filters is None:
        filters = SearchFilter()
    if not filters.doc_type:
        detected = detect_doc_type_from_query(query)
        if detected:
            filters.doc_type = detected

    # ── 1. ChromaDB 벡터 검색 (Semantic) ──
    semantic_results = _search_chromadb(query, filters, limit * 2)

    # ── 2. BM25 가중치 점수 계산 ──
    for item in semantic_results:
        bm25_score = weighted_bm25_score(query, item)
        semantic_score = item.get("_semantic_score", 0)

        # 하이브리드 점수 = alpha * BM25 + (1-alpha) * Semantic
        hybrid_score = hybrid_alpha * bm25_score + (1 - hybrid_alpha) * semantic_score

        results.append(SearchResult(
            doc_id=item.get("doc_id", ""),
            title=item.get("title", ""),
            content_preview=item.get("content", "")[:200],
            doc_type=item.get("doc_type", ""),
            score=round(hybrid_score, 4),
            metadata=item.get("metadata", {}),
            source_file=item.get("source_file", ""),
        ))

    # ── 3. 점수 내림차순 정렬 + 문서유형 부스트 ──
    if filters.doc_type:
        for r in results:
            if r.doc_type == filters.doc_type:
                r.score += 0.5  # 문서유형 매칭 보너스

    results.sort(key=lambda r: r.score, reverse=True)

    return results[:limit]


def _search_chromadb(
    query: str,
    filters: SearchFilter,
    limit: int,
) -> list[dict]:
    """ChromaDB에서 벡터 검색을 수행합니다."""
    try:
        import chromadb
        from pathlib import Path

        client = chromadb.PersistentClient(path="vectorstore")
        collection = client.get_collection("documents")

        where_filter = {}
        if filters.doc_type:
            where_filter["doc_type"] = {"$eq": filters.doc_type}
        if filters.department:
            where_filter["department"] = {"$eq": filters.department}

        results = collection.query(
            query_texts=[query],
            n_results=limit,
            where=where_filter if where_filter else None,
        )

        items = []
        if results and results["documents"]:
            for idx, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][idx] if results["metadatas"] else {}
                distance = results["distances"][0][idx] if results["distances"] else 1.0
                semantic_score = max(0, 1 - distance)

                items.append({
                    "doc_id": results["ids"][0][idx] if results["ids"] else "",
                    "title": meta.get("title", meta.get("source", "")),
                    "content": doc,
                    "doc_type": meta.get("doc_type", ""),
                    "department": meta.get("department", ""),
                    "metadata": meta,
                    "source_file": meta.get("source", ""),
                    "_semantic_score": semantic_score,
                })

        return items

    except Exception as e:
        logger.debug(f"ChromaDB 검색 실패 (빈 결과 반환): {e}")
        return []


def get_search_stats() -> dict:
    """검색 엔진 상태 통계"""
    try:
        import chromadb
        client = chromadb.PersistentClient(path="vectorstore")
        collection = client.get_collection("documents")
        count = collection.count()
        return {"indexed_documents": count, "status": "online"}
    except Exception:
        return {"indexed_documents": 0, "status": "offline"}
