"""Phase 3: 하이브리드 검색 엔진

BM25 키워드 검색 + ChromaDB 벡터 검색을 RRF로 결합.
kiwipiepy 기반 한국어 형태소 분석을 적용한다.

v2: 필터를 검색 전에 적용하여 정확도 향상.
"""

from dataclasses import dataclass, field
from pathlib import Path

from rank_bm25 import BM25Okapi
from langchain_chroma import Chroma

from config import VECTORSTORE_DIR, RRF_K, TOP_K, USE_KIWI
from core.embedding_client import get_embeddings


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
    ):
        self.tokenizer = KoreanTokenizer()

        # 벡터스토어 로드
        if vectorstore is not None:
            self.vectorstore = vectorstore
        else:
            try:
                self.vectorstore = Chroma(
                    persist_directory=str(VECTORSTORE_DIR / "documents"),
                    embedding_function=get_embeddings(),
                    collection_name="ajin_documents",
                )
            except Exception as e:
                import logging
                logging.getLogger("ajin.search").warning(f"ChromaDB 로드 실패 (BM25 전용 모드): {e}")
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
        """
        has_filters = any([doc_type_filter, part_name_filter, date_from, date_to])

        if has_filters:
            return self._filtered_search(
                query, k, doc_type_filter, part_name_filter, date_from, date_to
            )
        else:
            return self._unfiltered_search(query, k)

    def _unfiltered_search(self, query: str, k: int) -> list[SearchResult]:
        """필터 없는 일반 검색"""
        bm25_results = self._bm25_search(query, self.corpus_chunks, k=k * 3)
        vector_results = self._vector_search(query, k=k * 3)
        merged = self._rrf_merge(bm25_results, vector_results, self.corpus_chunks, k=k * 2)
        return self._deduplicate(merged, k)

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

        # 4. RRF 결합
        merged = self._rrf_merge(bm25_results, vector_results, filtered_chunks, k=k * 2)

        # 5. 추가 필터 (part_name, date — 벡터 결과에서 온 항목 보정)
        post_filtered = self._apply_post_filters(merged, part_name, date_from, date_to)

        return self._deduplicate(post_filtered, k)

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
            import logging
            logging.getLogger("ajin.search").warning(f"Vector search failed: {e}")
            return []

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
            filtered = [
                c for c in filtered
                if c.get("metadata", {}).get("doc_type", "") == doc_type
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
