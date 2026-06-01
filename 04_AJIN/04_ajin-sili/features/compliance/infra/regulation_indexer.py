"""P1 D4 — 규제 본문 ChromaDB 인덱싱.

크롤러 스냅샷 + ChangeRecord 본문을 청크 단위로 ChromaDB 에 적재해
RAG 검색 (regulation_qa.py) 에서 활용한다.

설계:
  1. ChromaDB PersistentClient (vectorstore/regulations/) — 기존 documents/employees
     컬렉션과 분리.
  2. Embedding: bge-m3 (Ollama). 미연결 시 임베딩 함수 None 으로 fallback —
     ChromaDB 가 자체 default 사용 (정확도 떨어짐, 인덱싱 자체는 동작).
  3. 청크 전략: 본문 200~500 자 단위, 한국어 형태소는 단순 줄바꿈/마침표 분리.
  4. 메타데이터: regulation_type / item_id / detected_at / grade / legal_class.
  5. Incremental — change_record id 가 metadata 에 포함, 중복 적재 시 upsert.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

VECTORSTORE_PATH = "vectorstore"
COLLECTION_NAME = "regulations_rag"

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
    logger.debug("Ollama embedding unavailable: %s", e)


# ─────────────────────────────────────────────────────────────
# 청크 분할
# ─────────────────────────────────────────────────────────────


def _chunk_text(text: str, max_chars: int = 400, overlap: int = 50) -> list[str]:
    """단순 문자 단위 청크 분할 (한국어 본문). 마침표/개행 우선 끊김.

    한국어는 띄어쓰기·형태소 단위 정확한 분할이 어려우므로, max_chars 보다
    큰 본문은 마침표·개행 경계에서 끊되, 여의치 않으면 max_chars 강제.
    """
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        end = min(i + max_chars, n)
        # 마침표 / 개행 경계 찾기 — 끝쪽 30자 안에서
        if end < n:
            for sep in ("\n", ".", "。", "다."):
                pos = text.rfind(sep, max(i, end - 30), end)
                if pos > i:
                    end = pos + len(sep)
                    break
        chunks.append(text[i:end].strip())
        i = max(end - overlap, end)  # overlap 일부
    return [c for c in chunks if c]


# ─────────────────────────────────────────────────────────────
# 인덱싱
# ─────────────────────────────────────────────────────────────


def _get_collection():
    """규제 RAG 용 ChromaDB 컬렉션 반환. ChromaDB 미설치 시 None."""
    if not CHROMA_AVAILABLE:
        return None
    client = chromadb.PersistentClient(path=VECTORSTORE_PATH)
    kwargs: dict[str, Any] = {"name": COLLECTION_NAME, "metadata": {"hnsw:space": "cosine"}}
    if _ollama_ef:
        kwargs["embedding_function"] = _ollama_ef
    return client.get_or_create_collection(**kwargs)


def index_change_record(change_id: int, change: dict) -> int:
    """단일 ChangeRecord → 청크 인덱싱. 적재된 청크 수 반환."""
    coll = _get_collection()
    if coll is None:
        return 0

    body = " ".join([
        str(change.get("item_title") or ""),
        str(change.get("summary_ko") or ""),
        str(change.get("new_value") or "")[:3000],
    ]).strip()
    if not body:
        return 0

    chunks = _chunk_text(body)
    if not chunks:
        return 0

    legal = change.get("legal_class") or []
    if isinstance(legal, str):
        try:
            legal = json.loads(legal)
        except (json.JSONDecodeError, TypeError):
            legal = []

    ids = [f"change-{change_id}-{i}" for i, _ in enumerate(chunks)]
    metadatas = [
        {
            "source": "change",
            "change_id": int(change_id),
            "regulation_type": str(change.get("regulation_type") or ""),
            "item_id": str(change.get("item_id") or ""),
            "item_title": str(change.get("item_title") or ""),
            "grade": str(change.get("grade") or "MEDIUM"),
            "legal_class": ",".join(legal) if isinstance(legal, list) else "",
            "detected_at": str(change.get("detected_at") or ""),
            "chunk_idx": i,
        }
        for i, _ in enumerate(chunks)
    ]
    coll.upsert(ids=ids, documents=chunks, metadatas=metadatas)
    return len(chunks)


def index_recent_changes(limit: int = 100) -> int:
    """compliance_changes.db 의 최근 N 건 변경을 인덱싱. 청크 총합 반환."""
    from features.compliance.alerts.change_detector import init_change_db, CHANGE_DB_PATH

    init_change_db()
    conn = sqlite3.connect(CHANGE_DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT id, regulation_type, item_id, item_title, summary_ko,
                  grade, legal_class, detected_at, new_value
           FROM regulation_changes
           WHERE status != 'filtered'
           ORDER BY detected_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()

    total = 0
    for r in rows:
        d = dict(r)
        total += index_change_record(d["id"], d)
    return total


# ─────────────────────────────────────────────────────────────
# 검색 — regulation_qa 가 호출
# ─────────────────────────────────────────────────────────────


def search(query: str, top_k: int = 5,
           legal_class: str | None = None) -> list[dict]:
    """ChromaDB 유사도 검색. metadata 필터 옵션.

    Returns:
        [{document, metadata, distance}, ...] 또는 [] (인덱스 부재 / 미설치).
    """
    coll = _get_collection()
    if coll is None or not query:
        return []

    where = None
    if legal_class:
        where = {"legal_class": {"$contains": legal_class}}

    try:
        result = coll.query(query_texts=[query], n_results=top_k, where=where)
    except Exception as e:
        logger.warning("ChromaDB query 실패: %s", e)
        return []

    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]

    return [
        {"document": d, "metadata": m, "distance": dist}
        for d, m, dist in zip(docs, metas, dists)
    ]


def collection_stats() -> dict[str, int]:
    """관리용 — 컬렉션 크기 반환. 미설치 / 비어있으면 {}."""
    coll = _get_collection()
    if coll is None:
        return {"available": 0, "count": 0}
    try:
        return {"available": 1, "count": coll.count()}
    except Exception:
        return {"available": 1, "count": 0}
