"""P3-2 — Module B 템플릿 추천 (TF-IDF cosine).

DocTypeMeta 의 (name_ko + name_en + usage_hint + dept_recommend) 를 코퍼스로 빌드.
사용자 자유 입력 → TF-IDF 변환 → cosine similarity → top-k 추천.

lifespan 1회 빌드 + 메모리 캐시. DocTypes 변경 시 `invalidate()` 호출 필요.
페르소나: 실무자 정확한 매칭, 신입 어휘 다양성 학습.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_vectorizer = None
_matrix = None
_doc_type_ids: list[str] = []

# 부록 6 P4-2 — kiwipiepy 형태소 토크나이저 (한국어 정확도 ↑)
_kiwi = None
_kiwi_init_failed = False
# 매칭 가치 있는 품사: 명사 / 동사 / 형용사 (recall 우선)
_KIWI_TARGET_POS = {"NNG", "NNP", "VV", "VA", "VX", "XR"}


def _ensure_kiwi():
    """kiwipiepy.Kiwi 싱글톤 — module 처음 호출 시 1회 init (~500ms)."""
    global _kiwi, _kiwi_init_failed
    if _kiwi is not None or _kiwi_init_failed:
        return _kiwi
    try:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
        logger.info("kiwipiepy.Kiwi 초기화 완료")
    except Exception as e:
        _kiwi_init_failed = True
        logger.warning("kiwipiepy 초기화 실패 — sklearn 기본 토크나이저 사용: %s", e)
    return _kiwi


def _kiwi_tokenize(text: str) -> list[str]:
    """kiwipiepy 형태소 분석 → 명사/동사/형용사 토큰 리스트."""
    kiwi = _ensure_kiwi()
    if kiwi is None:
        # kiwipiepy 미가용 시 정당화된 분기: 한국어 어절 단위 정규식 (서비스 가용성 우선)
        import re
        return re.findall(r"\b\w\w+\b", text or "")
    try:
        result = kiwi.tokenize(text or "")
        return [tok.form for tok in result if tok.tag in _KIWI_TARGET_POS]
    except Exception as e:
        logger.debug("kiwipiepy tokenize 실패: %s", e)
        import re
        return re.findall(r"\b\w\w+\b", text or "")


def _build_corpus(doc_types: list[dict]) -> tuple[list[str], list[str]]:
    """각 docType 의 문서 텍스트를 만든다. (ids, texts) 반환."""
    ids: list[str] = []
    texts: list[str] = []
    for d in doc_types:
        parts = [
            d.get("name_ko") or "",
            d.get("name_en") or "",
            d.get("usage_hint") or "",
        ]
        depts = d.get("dept_recommend") or []
        if isinstance(depts, list):
            parts.append(" ".join(str(x) for x in depts))
        text = " ".join(p for p in parts if p)
        if text.strip():
            ids.append(d.get("id") or "")
            texts.append(text)
    return ids, texts


def build_index(doc_types: list[dict]) -> int:
    """TF-IDF 인덱스를 빌드. 호출 결과 doc 수 반환."""
    global _vectorizer, _matrix, _doc_type_ids
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError:
        logger.warning("sklearn 미설치 — TF-IDF 추천 비활성")
        return 0

    ids, texts = _build_corpus(doc_types)
    if not texts:
        return 0
    with _lock:
        _ensure_kiwi()  # 초기 1회 init
        vec = TfidfVectorizer(
            tokenizer=_kiwi_tokenize,
            sublinear_tf=True,
            ngram_range=(1, 2),
            token_pattern=None,  # tokenizer 사용 시 token_pattern 무시 — 명시
        )
        mat = vec.fit_transform(texts)
        _vectorizer = vec
        _matrix = mat
        _doc_type_ids = ids
        return len(ids)


def invalidate() -> None:
    global _vectorizer, _matrix, _doc_type_ids
    with _lock:
        _vectorizer = None
        _matrix = None
        _doc_type_ids = []


def recommend(query: str, top_k: int = 2, threshold: float = 0.1) -> dict[str, Any]:
    """사용자 query 에 가장 가까운 docType id top-k 반환."""
    if not query or not query.strip():
        return {"doc_type_ids": [], "scores": []}

    if _vectorizer is None or _matrix is None or not _doc_type_ids:
        return {"doc_type_ids": [], "scores": [], "warning": "index not built"}

    try:
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        return {"doc_type_ids": [], "scores": [], "warning": "sklearn missing"}

    with _lock:
        try:
            qv = _vectorizer.transform([query])
            sim = cosine_similarity(qv, _matrix)[0]
        except Exception as e:
            logger.warning("TF-IDF transform 실패: %s", e)
            return {"doc_type_ids": [], "scores": []}

        # top-k 인덱스 추출 (score 내림차순)
        ranked = sorted(enumerate(sim.tolist()), key=lambda x: x[1], reverse=True)
        picks: list[tuple[str, float]] = []
        for idx, score in ranked:
            if score < threshold:
                break
            picks.append((_doc_type_ids[idx], float(score)))
            if len(picks) >= top_k:
                break
        return {
            "doc_type_ids": [p[0] for p in picks],
            "scores": [round(p[1], 4) for p in picks],
        }
