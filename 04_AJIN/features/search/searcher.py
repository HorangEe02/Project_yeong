"""Phase 3: 하이브리드 검색 엔진

BM25 키워드 검색 + ChromaDB 벡터 검색을 RRF로 결합.
kiwipiepy 기반 한국어 형태소 분석을 적용한다.

v2: 필터를 검색 전에 적용하여 정확도 향상.
"""

from __future__ import annotations  # type annotation lazy evaluation — Chroma=None 시 runtime TypeError 방지

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from rank_bm25 import BM25Okapi

try:
    from langchain_chroma import Chroma  # type: ignore[import-untyped]
except ImportError:
    # Slim image 에서는 langchain_chroma 미설치 — BM25 단독 fallback.
    # ADR-0008 (ChromaDB → Supabase pgvector) 마이그레이션 기간 동안 image 양쪽 지원.
    Chroma = None  # type: ignore[assignment, misc]

from config import RERANKER_TOP_K_INPUT, RRF_K, TOP_K, USE_KIWI, VECTORSTORE_DIR
from core.embedding_client import get_embeddings
from features.search.reranker import get_reranker
from features.search.vector_store import SupabasePgvectorStore

logger = logging.getLogger("ajin.search")


# ---------------------------------------------------------------------------
# 한국어 토크나이저
# ---------------------------------------------------------------------------

class KoreanTokenizer:
    """kiwipiepy 기반 한국어 형태소 분석 토크나이저"""

    def __init__(self):
        if USE_KIWI:
            from kiwipiepy import Kiwi
            self.kiwi = Kiwi()
            self._add_custom_dict()
        else:
            self.kiwi = None

    def _add_custom_dict(self):
        """아진산업 도메인 전문 용어를 사용자 사전에 추가한다."""
        custom_words = [
            ("워터펌프", "NNP"), ("냉난방장치", "NNP"), ("핫스탬핑", "NNP"),
            ("스팟용접", "NNP"), ("프레스금형", "NNP"), ("임펠러", "NNP"),
            ("너깃", "NNP"), ("실링", "NNP"), ("블랭킹", "NNP"),
            ("헤밍", "NNP"), ("아진산업", "NNP"), ("냉각수히터", "NNP"),
            ("충전장치", "NNP"), ("브레이징", "NNP"), ("솔더링", "NNP"),
            # 차체 부품 (조직 참조 문서 반영)
            ("쿼터패널", "NNP"), ("대시패널", "NNP"), ("리어플로어", "NNP"),
            ("카울멤버", "NNP"), ("웨더스트립", "NNP"), ("도어실링", "NNP"),
        ]
        for word, tag in custom_words:
            self.kiwi.add_user_word(word, tag)

    def tokenize(self, text: str) -> list[str]:
        """텍스트를 형태소 분석하여 검색에 유용한 토큰만 추출한다."""
        if self.kiwi is None:
            return text.split()

        tokens = []
        for token in self.kiwi.tokenize(text):
            if token.tag in ("NNG", "NNP", "NNB", "VV", "VA", "SL", "SN"):
                tokens.append(token.form)
        return tokens


# ---------------------------------------------------------------------------
# 검색 결과 데이터 클래스
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """검색 결과 단일 항목"""
    doc_id: str
    title: str
    doc_type: str
    part_name: str
    content: str
    score: float
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 하이브리드 검색 엔진
# ---------------------------------------------------------------------------

class HybridSearcher:
    """BM25 + 벡터 검색 + RRF 결합 하이브리드 검색 엔진"""

    def __init__(
        self,
        vectorstore: Chroma | None = None,
        corpus_chunks: list[dict] | None = None,
        pgvector_store: SupabasePgvectorStore | None = None,
    ):
        self.tokenizer = KoreanTokenizer()
        # ADR-0008 완료: ChromaDB → Supabase pgvector 마이그레이션. 기본 postgres.
        # 환경에 따라 명시적으로 'chroma' 설정 시 레거시 경로 유지.
        self.vector_read_mode = os.getenv("VECTOR_READ_MODE", "postgres").strip().lower()
        if self.vector_read_mode not in {"chroma", "postgres"}:
            logger.warning("Invalid VECTOR_READ_MODE=%s; using postgres", self.vector_read_mode)
            self.vector_read_mode = "postgres"
        self.pgvector_store = None

        # 벡터스토어 로드
        if self.vector_read_mode == "postgres":
            try:
                self.pgvector_store = pgvector_store or SupabasePgvectorStore()
            except Exception as e:
                logger.warning(f"Supabase pgvector store 로드 실패 (검색 결과 없음): {e}")
            self.vectorstore = None
        elif vectorstore is not None:
            self.vectorstore = vectorstore
        elif Chroma is not None:
            try:
                self.vectorstore = Chroma(
                    persist_directory=str(VECTORSTORE_DIR / "documents"),
                    embedding_function=get_embeddings(),
                    collection_name="ajin_documents",
                )
            except Exception as e:
                logger.warning(f"ChromaDB 로드 실패 (BM25 전용 모드): {e}")
                self.vectorstore = None
        else:
            # langchain_chroma 미설치 (slim image) — BM25 단독 운영.
            self.vectorstore = None

        # BM25 코퍼스 로드 (JSON — pickle RCE 위험 제거)
        if corpus_chunks is not None:
            self.corpus_chunks = corpus_chunks
        else:
            corpus_path = VECTORSTORE_DIR / "bm25_corpus.json"
            legacy_pkl = VECTORSTORE_DIR / "bm25_corpus.pkl"
            if corpus_path.exists():
                import json as _json
                with open(corpus_path, "r", encoding="utf-8") as f:
                    self.corpus_chunks = _json.load(f)
            elif legacy_pkl.exists():
                import pickle as _pickle  # noqa: S403
                with open(legacy_pkl, "rb") as f:
                    self.corpus_chunks = _pickle.load(f)  # noqa: S301
                import json as _json
                with open(corpus_path, "w", encoding="utf-8") as f:
                    _json.dump(self.corpus_chunks, f, ensure_ascii=False)
                legacy_pkl.unlink()
            else:
                self.corpus_chunks = []

        # 전체 BM25 인덱스 구축
        self._build_bm25_index(self.corpus_chunks)

        # v4.x — BGE cross-encoder reranker (config.RERANKER_ENABLED=true 일 때만 로드)
        # 출처: docs/RAG_ENHANCEMENT_PLAN.md §2.1, §4 Phase 1
        # lazy: 첫 search 호출 시 모델 다운로드 (~600MB). env 비활성 시 None.
        self.reranker = get_reranker()
        if self.reranker is None:
            logger.info("Reranker 비활성 — RRF 결과 그대로 반환")
        else:
            logger.info("Reranker 활성: model=%s (lazy load)", self.reranker.model_name)

    def _build_bm25_index(self, chunks: list[dict]):
        """BM25 인덱스를 구축한다."""
        if chunks:
            tokenized = [self.tokenizer.tokenize(c["content"]) for c in chunks]
            self.bm25 = BM25Okapi(tokenized)
        else:
            self.bm25 = None

    def search(
        self,
        query: str,
        k: int = TOP_K,
        doc_type_filter: str | None = None,
        part_name_filter: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[SearchResult]:
        """하이브리드 검색을 수행한다.

        v2: 필터가 있으면 필터링된 코퍼스에서 BM25를 재구축하여
        해당 유형/기간의 문서만 대상으로 검색한다.
        v4.x: 검색어가 비어있고 필터가 있으면 metadata-only 모드로 동작 —
              문서 유형/부품명 드롭다운만 선택해도 결과 노출 (점수 0).
        """
        normalized_query = (query or "").strip()
        has_filters = any([doc_type_filter, part_name_filter, date_from, date_to])

        # v4.x — 검색어가 없는 경우
        if not normalized_query:
            if not has_filters:
                return []
            return self._list_by_filter(
                k=k,
                doc_type_filter=doc_type_filter,
                part_name_filter=part_name_filter,
                date_from=date_from,
                date_to=date_to,
            )

        if self.vector_read_mode == "postgres":
            return self._pgvector_search(
                query=normalized_query,
                k=k,
                doc_type_filter=doc_type_filter,
                part_name_filter=part_name_filter,
                date_from=date_from,
                date_to=date_to,
            )

        if has_filters:
            return self._filtered_search(
                normalized_query, k, doc_type_filter, part_name_filter, date_from, date_to
            )
        else:
            return self._unfiltered_search(normalized_query, k)

    def _list_by_filter(
        self,
        k: int,
        doc_type_filter: str | None,
        part_name_filter: str | None,
        date_from: str | None,
        date_to: str | None,
    ) -> list[SearchResult]:
        """검색어 없이 doc_type / part_name 필터만으로 결과를 반환한다.

        pgvector 모드: SupabasePgvectorStore.list_documents_by_metadata 사용.
        chroma 모드: BM25 코퍼스에서 metadata 필터만 적용.
        """
        if self.vector_read_mode == "postgres" and self.pgvector_store is not None:
            try:
                rows = self.pgvector_store.list_documents_by_metadata(
                    match_count=k,
                    doc_type_filter=doc_type_filter,
                    part_name_filter=part_name_filter,
                )
            except Exception as e:
                logger.warning("list_documents_by_metadata failed: %s", e)
                return []

            results: list[SearchResult] = []
            for row in rows:
                metadata = dict(row.get("metadata") or {})
                results.append(
                    SearchResult(
                        doc_id=str(row.get("source_doc_id") or metadata.get("doc_id") or ""),
                        title=str(row.get("title") or metadata.get("title") or ""),
                        doc_type=str(metadata.get("doc_type") or doc_type_filter or ""),
                        part_name=str(metadata.get("part_name") or part_name_filter or ""),
                        content=str(row.get("content") or "")[:300],
                        score=float(row.get("score") or 0.0),
                        metadata=metadata,
                    )
                )
            return self._apply_post_filters(results, part_name_filter, date_from, date_to)[:k]

        # chroma 모드 — corpus_chunks 직접 필터링
        filtered = self._filter_corpus(
            self.corpus_chunks, doc_type_filter, part_name_filter, date_from, date_to
        )
        results: list[SearchResult] = []
        for chunk in filtered[:k]:
            results.append(
                SearchResult(
                    doc_id=str(chunk.get("doc_id") or ""),
                    title=str(chunk.get("title") or ""),
                    doc_type=str(chunk.get("doc_type") or doc_type_filter or ""),
                    part_name=str(chunk.get("part_name") or part_name_filter or ""),
                    content=str(chunk.get("content") or "")[:300],
                    score=0.0,
                    metadata=dict(chunk.get("metadata") or {}),
                )
            )
        return results

    def _unfiltered_search(self, query: str, k: int) -> list[SearchResult]:
        """필터 없는 일반 검색 — RRF 후 reranker 재정렬 (있을 때)."""
        bm25_results = self._bm25_search(query, self.corpus_chunks, k=k * 3)
        vector_results = self._vector_search(query, k=k * 3)
        rrf_out_k = RERANKER_TOP_K_INPUT if self.reranker is not None else k * 2
        merged = self._rrf_merge(bm25_results, vector_results, self.corpus_chunks, k=rrf_out_k)
        reranked = self._rerank(query, merged, top_k=k)
        return self._deduplicate(reranked, k)

    def _filtered_search(
        self,
        query: str,
        k: int,
        doc_type: str | None,
        part_name: str | None,
        date_from: str | None,
        date_to: str | None,
    ) -> list[SearchResult]:
        """필터를 검색 전에 적용하여 정확도를 높인다.

        1. 코퍼스를 필터 조건으로 먼저 걸러낸다.
        2. 필터링된 코퍼스로 BM25 인덱스를 임시 구축한다.
        3. 벡터 검색도 ChromaDB where 필터를 사용한다.
        4. RRF 결합 후 반환한다.
        """
        # 1. BM25 코퍼스 필터링
        filtered_chunks = self._filter_corpus(
            self.corpus_chunks, doc_type, part_name, date_from, date_to
        )

        if not filtered_chunks:
            # 필터 후 코퍼스가 없으면 벡터 검색만 시도
            vector_results = self._vector_search(
                query, k=k * 3, doc_type_filter=doc_type
            )
            merged = self._vector_only_results(vector_results, k)
            return self._apply_post_filters(merged, part_name, date_from, date_to)

        # 2. 필터링된 코퍼스로 임시 BM25 구축
        bm25_results = self._bm25_search_on(query, filtered_chunks, k=k * 3)

        # 3. 벡터 검색 (ChromaDB where 필터)
        vector_results = self._vector_search(
            query, k=k * 3, doc_type_filter=doc_type
        )

        # 4. RRF 결합 — reranker 있으면 더 많은 후보를 모아 cross-encoder 재정렬
        rrf_out_k = RERANKER_TOP_K_INPUT if self.reranker is not None else k * 2
        merged = self._rrf_merge(bm25_results, vector_results, filtered_chunks, k=rrf_out_k)

        # 5. 추가 필터 (part_name, date — 벡터 결과에서 온 항목 보정)
        post_filtered = self._apply_post_filters(merged, part_name, date_from, date_to)

        # 6. Reranker 재정렬 (post-filter 후) → top-K
        reranked = self._rerank(query, post_filtered, top_k=k)

        return self._deduplicate(reranked, k)

    # ----- BM25 검색 -----

    def _bm25_search(
        self, query: str, chunks: list[dict], k: int
    ) -> list[tuple[int, float]]:
        """전체 코퍼스 기반 BM25 검색."""
        if self.bm25 is None:
            return []
        tokens = self.tokenizer.tokenize(query)
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:k]
        return [(idx, scores[idx]) for idx in top_indices if scores[idx] > 0]

    def _bm25_search_on(
        self, query: str, chunks: list[dict], k: int
    ) -> list[tuple[int, float]]:
        """필터링된 코퍼스로 임시 BM25 검색."""
        if not chunks:
            return []
        tokens = self.tokenizer.tokenize(query)
        if not tokens:
            return []
        tokenized = [self.tokenizer.tokenize(c["content"]) for c in chunks]
        temp_bm25 = BM25Okapi(tokenized)
        scores = temp_bm25.get_scores(tokens)
        top_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:k]
        return [(idx, scores[idx]) for idx in top_indices if scores[idx] > 0]

    # ----- 벡터 검색 -----

    def _vector_search(
        self, query: str, k: int, doc_type_filter: str | None = None
    ) -> list[tuple[str, float, dict]]:
        """벡터 검색. ChromaDB where 필터를 지원한다."""
        try:
            kwargs = {"query": query, "k": k}

            # ChromaDB metadata 필터
            if doc_type_filter:
                kwargs["filter"] = {"doc_type": doc_type_filter}

            results = self.vectorstore.similarity_search_with_relevance_scores(
                **kwargs
            )
            return [
                (doc.metadata.get("doc_id", ""), score, doc.metadata)
                for doc, score in results
            ]
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

    def _pgvector_search(
        self,
        query: str,
        k: int,
        doc_type_filter: str | None = None,
        part_name_filter: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[SearchResult]:
        """Supabase pgvector RPC 기반 문서 검색을 수행한다.

        Args:
            query: 사용자 검색어.
            k: 최대 결과 수.
            doc_type_filter: 문서 유형 필터.
            part_name_filter: 부품명 필터.
            date_from: 생성일 시작 필터.
            date_to: 생성일 종료 필터.

        Returns:
            list[SearchResult]: 기존 API 응답 schema에 맞춘 검색 결과.
        """

        if self.pgvector_store is None:
            return []
        # reranker 있으면 더 많은 후보를 가져온 후 cross-encoder 재정렬 (RAG_ENHANCEMENT_PLAN §2.1)
        candidate_k = RERANKER_TOP_K_INPUT if self.reranker is not None else k
        try:
            embedding = get_embeddings().embed_query(query)
            rows = self.pgvector_store.hybrid_search_documents(
                query_text=query,
                query_embedding=embedding,
                match_count=candidate_k,
                doc_type_filter=doc_type_filter,
                part_name_filter=part_name_filter,
            )
        except Exception as e:
            logger.warning("Supabase pgvector search failed: %s", e)
            return []

        results: list[SearchResult] = []
        for row in rows:
            metadata = dict(row.get("metadata") or {})
            result = SearchResult(
                doc_id=str(row.get("source_doc_id") or metadata.get("doc_id") or ""),
                title=str(row.get("title") or metadata.get("title") or ""),
                doc_type=str(metadata.get("doc_type") or doc_type_filter or ""),
                part_name=str(metadata.get("part_name") or part_name_filter or ""),
                content=str(row.get("content") or "")[:300],
                score=float(row.get("score") or row.get("similarity") or 0.0),
                metadata=metadata,
            )
            results.append(result)

        # post-filter 후 reranker 재정렬 → top-K (cross-encoder)
        filtered = self._apply_post_filters(results, part_name_filter, date_from, date_to)
        return self._rerank(query, filtered, top_k=k)

    # ----- BGE Reranker 재정렬 (cross-encoder) -----

    def _rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """BGE cross-encoder 로 results 재정렬 후 top_k 반환.

        reranker None (env 비활성 또는 import 실패) 또는 score 산출 실패 시 RRF 순서 유지.
        결과 SearchResult.score 는 rerank_score 로 덮어쓰고, 원래 RRF 점수는
        metadata["rrf_score"] 로 보존.
        """
        if not results or self.reranker is None:
            return results[:top_k]

        texts = [r.content for r in results]
        scores = self.reranker.compute_scores(query, texts)
        if scores is None:
            # 모델 로드 실패 — RRF 순서 유지 (slim image 등 호환)
            return results[:top_k]

        for r, s in zip(results, scores):
            rrf_score = r.score
            r.score = float(s)
            r.metadata = {
                **r.metadata,
                "rerank_score": float(s),
                "rrf_score": float(rrf_score),
            }
        return sorted(results, key=lambda r: r.score, reverse=True)[:top_k]

    # ----- RRF 결합 -----

    def _rrf_merge(
        self,
        bm25_results: list[tuple[int, float]],
        vector_results: list[tuple[str, float, dict]],
        chunks: list[dict],
        k: int,
        rrf_k: int = RRF_K,
    ) -> list[SearchResult]:
        """RRF (Reciprocal Rank Fusion)로 결합한다."""
        rrf_scores: dict[str, float] = {}
        doc_meta: dict[str, dict] = {}
        doc_content: dict[str, str] = {}

        # BM25 결과
        for rank, (idx, _) in enumerate(bm25_results):
            if idx < len(chunks):
                chunk = chunks[idx]
                doc_id = chunk["doc_id"]
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (rrf_k + rank + 1)
                if doc_id not in doc_meta:
                    doc_meta[doc_id] = chunk["metadata"]
                    doc_content[doc_id] = chunk["content"]

        # 벡터 결과
        for rank, (doc_id, _, meta) in enumerate(vector_results):
            if not doc_id:
                continue
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (rrf_k + rank + 1)
            if doc_id not in doc_meta:
                doc_meta[doc_id] = meta
                doc_content[doc_id] = ""

        sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:k]

        results = []
        for doc_id in sorted_ids:
            meta = doc_meta.get(doc_id, {})
            results.append(SearchResult(
                doc_id=doc_id,
                title=meta.get("title", ""),
                doc_type=meta.get("doc_type", ""),
                part_name=meta.get("part_name", ""),
                content=doc_content.get(doc_id, "")[:300],
                score=rrf_scores[doc_id],
                metadata=meta,
            ))
        return results

    def _vector_only_results(
        self, vector_results: list[tuple[str, float, dict]], k: int
    ) -> list[SearchResult]:
        """벡터 검색 결과만으로 SearchResult를 생성한다."""
        results = []
        for doc_id, score, meta in vector_results[:k]:
            if not doc_id:
                continue
            results.append(SearchResult(
                doc_id=doc_id,
                title=meta.get("title", ""),
                doc_type=meta.get("doc_type", ""),
                part_name=meta.get("part_name", ""),
                content="",
                score=score,
                metadata=meta,
            ))
        return results

    # ----- 필터링 유틸리티 -----

    def _filter_corpus(
        self,
        chunks: list[dict],
        doc_type: str | None,
        part_name: str | None,
        date_from: str | None,
        date_to: str | None,
    ) -> list[dict]:
        """코퍼스를 메타데이터 조건으로 필터링한다."""
        filtered = chunks
        if doc_type:
            # Frontend snake_case (예: "8d_report") ↔ corpus 표기 ("8D Report") 매칭 정규화.
            target = doc_type.lower().replace("_", " ").strip()
            filtered = [
                c for c in filtered
                if c.get("metadata", {}).get("doc_type", "").lower() == target
            ]
        if part_name:
            filtered = [
                c for c in filtered
                if part_name in c.get("metadata", {}).get("part_name", "")
            ]
        if date_from:
            filtered = [
                c for c in filtered
                if c.get("metadata", {}).get("created_date", "") >= date_from
            ]
        if date_to:
            filtered = [
                c for c in filtered
                if c.get("metadata", {}).get("created_date", "") <= date_to
            ]
        return filtered

    def _apply_post_filters(
        self,
        results: list[SearchResult],
        part_name: str | None,
        date_from: str | None,
        date_to: str | None,
    ) -> list[SearchResult]:
        """벡터 검색 결과에 대한 후처리 필터 (doc_type은 이미 적용됨)."""
        filtered = results
        if part_name:
            filtered = [r for r in filtered if part_name in r.part_name]
        if date_from:
            filtered = [
                r for r in filtered
                if r.metadata.get("created_date", "") >= date_from
            ]
        if date_to:
            filtered = [
                r for r in filtered
                if r.metadata.get("created_date", "") <= date_to
            ]
        return filtered

    def _deduplicate(self, results: list[SearchResult], k: int) -> list[SearchResult]:
        """같은 doc_id 중복 제거 → 최고 점수 1건만."""
        seen = set()
        deduped = []
        for r in results:
            if r.doc_id not in seen:
                seen.add(r.doc_id)
                deduped.append(r)
        return deduped[:k]
