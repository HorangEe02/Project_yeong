"""P2 D8 — 외부 판례 corpus 인덱싱 (대법원 종합법률정보 OpenAPI).

법무 5분류 결과 → 유사 판례 자동 검색을 위해 외부 판례 corpus 를
ChromaDB 의 별도 컬렉션 (case_law_rag) 에 인덱싱.

데이터 소스:
  대법원 종합법률정보 OpenAPI:
    https://www.law.go.kr/DRF/lawSearch.do?OC=<OC>&target=prec&type=JSON&query=<keyword>

설계:
  1. LAW_GO_KR_OC 환경변수 재사용 (Phase 1 의 domestic_law 와 동일 키).
  2. 키워드별 fetch — 산안법·화관법·관세 등 핵심 키워드 기반 정기 cron.
  3. ChromaDB 컬렉션 분리 (case_law_rag) — regulations_rag 와 검색 도메인 격리.
  4. 미설정·외부 실패 시 graceful skip, 검색 단에서 "외부 자료 미가용" 안전 응답.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

VECTORSTORE_PATH = "vectorstore"
COLLECTION_NAME = "case_law_rag"

# 정기 인덱싱 키워드 (사내 핵심 도메인)
DEFAULT_KEYWORDS: tuple[str, ...] = (
    "산업안전보건법",
    "화학물질관리법",
    "대기환경보전법",
    "관세",
    "REACH",
    "프레스 안전",
    "중대재해",
    "산업재해",
)

LAW_API_URL = "https://www.law.go.kr/DRF/lawSearch.do"

CHROMA_AVAILABLE = False
try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    pass

_ollama_ef = None
try:
    from langchain_ollama import OllamaEmbeddings
    from chromadb.utils.embedding_functions import create_langchain_embedding
    from config import OLLAMA_BASE_URL, EMBEDDING_MODEL
    _langchain_embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)
    _ollama_ef = create_langchain_embedding(_langchain_embeddings)
except Exception as e:
    logger.debug("Ollama embedding unavailable for case_law: %s", e)


# ─────────────────────────────────────────────────────────────
# Fetch — 대법원 종합법률정보
# ─────────────────────────────────────────────────────────────


def fetch_cases_for_keyword(keyword: str, display: int = 20) -> list[dict[str, Any]]:
    """단일 키워드 → 판례 메타 list. 외부 API 호출 실패 시 빈 list.

    응답 정규화:
        {case_id, court, date, title, summary, full_url}
    """
    try:
        from config import LAW_GO_KR_OC
    except ImportError:
        return []
    if not LAW_GO_KR_OC:
        logger.debug("LAW_GO_KR_OC 미설정 — case_law fetch skip")
        return []

    try:
        from features.compliance.infra._http import fetch_json
    except ImportError:
        return []

    params = {
        "OC": LAW_GO_KR_OC,
        "target": "prec",
        "type": "JSON",
        "query": keyword,
        "display": str(max(1, min(display, 100))),
    }
    url = LAW_API_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())

    try:
        data = fetch_json(url)
    except Exception as e:
        logger.warning("대법원 판례 fetch 실패 (%s): %s", keyword, e)
        return []

    # 응답 형태: {"PrecSearch": {"prec": [...]}}
    raw = data.get("PrecSearch", {}).get("prec") or []
    if isinstance(raw, dict):
        raw = [raw]

    out: list[dict[str, Any]] = []
    for r in raw:
        case_id = str(r.get("판례일련번호") or r.get("판례정보일련번호") or "")
        if not case_id:
            continue
        out.append({
            "case_id": case_id,
            "court": str(r.get("법원명") or ""),
            "date": _format_yyyymmdd(r.get("선고일자") or r.get("판시일자")),
            "title": str(r.get("사건명") or r.get("판례명") or "")[:200],
            "summary": str(r.get("판례내용") or r.get("판시사항") or "")[:1000],
            "full_url": str(r.get("판례상세링크") or
                            f"https://www.law.go.kr/DRF/lawService.do?OC={LAW_GO_KR_OC}"
                            f"&target=prec&type=JSON&ID={case_id}"),
            "keyword": keyword,
        })
    return out


def _format_yyyymmdd(s: Any) -> str:
    if not s:
        return ""
    s = str(s).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


# ─────────────────────────────────────────────────────────────
# 인덱싱 — ChromaDB
# ─────────────────────────────────────────────────────────────


def _get_collection():
    if not CHROMA_AVAILABLE:
        return None
    client = chromadb.PersistentClient(path=VECTORSTORE_PATH)
    kwargs: dict[str, Any] = {"name": COLLECTION_NAME, "metadata": {"hnsw:space": "cosine"}}
    if _ollama_ef:
        kwargs["embedding_function"] = _ollama_ef
    return client.get_or_create_collection(**kwargs)


def index_cases(cases: list[dict[str, Any]]) -> int:
    """판례 list → ChromaDB 적재. 적재 건수 반환.

    upsert — 같은 case_id 재인덱싱 시 갱신.
    """
    coll = _get_collection()
    if coll is None or not cases:
        return 0

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for c in cases:
        body = " ".join([
            c.get("title", ""),
            c.get("summary", ""),
        ]).strip()
        if not body:
            continue
        ids.append(f"case-{c['case_id']}")
        documents.append(body)
        metadatas.append({
            "case_id": str(c.get("case_id") or ""),
            "court": str(c.get("court") or ""),
            "date": str(c.get("date") or ""),
            "title": str(c.get("title") or "")[:200],
            "full_url": str(c.get("full_url") or ""),
            "keyword": str(c.get("keyword") or ""),
        })

    if not ids:
        return 0
    coll.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


def index_default_keywords(display_per_keyword: int = 10) -> dict[str, int]:
    """DEFAULT_KEYWORDS 일괄 인덱싱. 키워드별 적재 건수 반환."""
    out: dict[str, int] = {}
    for kw in DEFAULT_KEYWORDS:
        cases = fetch_cases_for_keyword(kw, display=display_per_keyword)
        out[kw] = index_cases(cases)
    return out


def collection_stats() -> dict[str, int]:
    coll = _get_collection()
    if coll is None:
        return {"available": 0, "count": 0}
    try:
        return {"available": 1, "count": coll.count()}
    except Exception:
        return {"available": 1, "count": 0}


# ─────────────────────────────────────────────────────────────
# 검색 — change_classifier / UI 호출
# ─────────────────────────────────────────────────────────────


SIMILARITY_THRESHOLD = 0.7  # cosine distance < 0.3 ≈ similarity > 0.7 (적당히 유사)


def find_similar(query: str, top_k: int = 3,
                 min_similarity: float = SIMILARITY_THRESHOLD) -> list[dict[str, Any]]:
    """change 본문 → 유사 판례 top-k.

    similarity threshold 미달 결과는 제외 (법무가 무관한 판례 보고 시간 낭비 방지).

    Returns:
        [{case_id, court, date, title, summary_excerpt, similarity, full_url}, ...]
        또는 [] (인덱스 부재 / 매칭 없음).
    """
    coll = _get_collection()
    if coll is None or not query:
        return []

    try:
        result = coll.query(query_texts=[query], n_results=top_k)
    except Exception as e:
        logger.warning("case_law 검색 실패: %s", e)
        return []

    metas = (result.get("metadatas") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]

    out: list[dict[str, Any]] = []
    for m, d, dist in zip(metas, docs, dists):
        # cosine distance → similarity (1 - dist)
        sim = max(0.0, 1.0 - float(dist))
        if sim < min_similarity:
            continue
        out.append({
            "case_id": m.get("case_id", ""),
            "court": m.get("court", ""),
            "date": m.get("date", ""),
            "title": m.get("title", ""),
            "summary_excerpt": (d or "")[:300],
            "similarity": round(sim, 3),
            "full_url": m.get("full_url", ""),
        })
    return out


def find_similar_for_change(change: dict[str, Any], top_k: int = 3) -> list[dict[str, Any]]:
    """ChangeRecord → 유사 판례 검색. legal_class·키워드 활용.

    검색 query 는 (item_title + summary_ko + new_value 일부) 결합.
    """
    parts = [
        str(change.get("item_title") or ""),
        str(change.get("summary_ko") or ""),
        str(change.get("new_value") or "")[:500],
    ]
    query = " ".join(p for p in parts if p).strip()
    if not query:
        return []
    return find_similar(query, top_k=top_k)
