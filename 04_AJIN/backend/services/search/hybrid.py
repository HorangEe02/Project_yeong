"""D1 — FTS5 + ChromaDB 하이브리드 검색 머지.

가중치: FTS5 BM25 0.7 / ChromaDB cosine 0.3 (실험 가능).
ChromaDB 미가용 시 FTS5 단독, FTS5 빈 결과 시 ChromaDB 단독.
"""
from __future__ import annotations

import time
from typing import Any

from backend.services.search import fts_index


def _normalize_bm25(rank: float) -> float:
    # FTS5 BM25 는 음수가 좋은 점수(작을수록 더 관련). 0~1 로 정규화.
    return max(0.0, min(1.0, 1.0 / (1.0 + abs(rank))))


def _normalize_distance(distance: float) -> float:
    return max(0.0, min(1.0, 1.0 - distance))


def search(
    query: str,
    limit: int = 20,
    offset: int = 0,
    doc_type: str | None = None,
) -> dict[str, Any]:
    """하이브리드 검색.

    Returns:
        {query, total, elapsed_ms, hits[ComplianceSearchHit], available}
    """
    started = time.perf_counter()

    fts_hits = fts_index.query(query, limit=limit * 2, offset=0, doc_type=doc_type)
    sem_hits: list[dict[str, Any]] = []
    try:
        from features.compliance.regulation_indexer import search as chroma_search
        sem_hits = chroma_search(query, top_k=limit) or []
    except Exception:
        sem_hits = []

    # reg_id 키 머지.
    merged: dict[str, dict[str, Any]] = {}
    for h in fts_hits:
        rid = h.get("reg_id") or ""
        merged[rid] = {
            "id": rid,
            "index": "regulations",
            "title": h.get("name_ko") or h.get("name") or rid,
            "snippet": h.get("snippet") or "",
            "score": 0.7 * _normalize_bm25(h.get("rank", 0.0)),
            "payload": {
                "doc_type": h.get("doc_type"),
                "authority": h.get("authority"),
                "name": h.get("name"),
                "name_ko": h.get("name_ko"),
                "source": "fts5",
            },
        }
    for h in sem_hits:
        meta = h.get("metadata") or {}
        rid = str(meta.get("regulation_type") or meta.get("change_id") or meta.get("item_id") or "")
        if not rid:
            continue
        sem_score = 0.3 * _normalize_distance(h.get("distance", 1.0))
        if rid in merged:
            merged[rid]["score"] = (merged[rid]["score"] or 0.0) + sem_score
            merged[rid]["payload"]["source"] = "fts5+chromadb"
        else:
            merged[rid] = {
                "id": rid,
                "index": "regulations",
                "title": meta.get("item_title") or rid,
                "snippet": (h.get("document") or "")[:200],
                "score": sem_score,
                "payload": {
                    "regulation_type": meta.get("regulation_type"),
                    "grade": meta.get("grade"),
                    "source": "chromadb",
                },
            }

    hits = sorted(merged.values(), key=lambda x: x.get("score") or 0.0, reverse=True)
    hits = hits[offset : offset + limit]

    elapsed = int((time.perf_counter() - started) * 1000)
    return {
        "query": query,
        "total": len(merged),
        "elapsed_ms": elapsed,
        "hits": hits,
        "available": True,
    }


def health() -> dict[str, Any]:
    fts_count = fts_index.index_count()
    chroma_count = 0
    chroma_available = False
    try:
        from features.compliance.regulation_indexer import collection_stats
        st = collection_stats()
        chroma_available = bool(st.get("available"))
        chroma_count = int(st.get("count", 0))
    except Exception:
        pass

    return {
        "meili_status": "fts5+chromadb",
        "available": fts_count > 0 or chroma_count > 0,
        "counts": {
            "regulations_fts": fts_count,
            "regulations_chromadb": chroma_count,
        },
        "is_indexing": False,
    }
