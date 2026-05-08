"""
Employee 시맨틱 하이브리드 검색 엔진
- ChromaDB에 직원 정보 임베딩 저장
- FTS5 키워드 점수 + 시맨틱 유사도 점수를 RRF(Reciprocal Rank Fusion)로 결합
- 오타/유사어/자연어 쿼리 대응
"""

import sqlite3
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import logging

try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

_ollama_ef = None
try:
    from langchain_ollama import OllamaEmbeddings
    from chromadb.utils.embedding_functions import create_langchain_embedding
    from config import OLLAMA_BASE_URL, EMBEDDING_MODEL
    _langchain_embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)
    _ollama_ef = create_langchain_embedding(_langchain_embeddings)
except Exception:
    pass

logger = logging.getLogger(__name__)

DB_PATH = Path("data/employees.db")
VECTORSTORE_PATH = "vectorstore"
COLLECTION_NAME = "employee_profiles"


# ──────────────────────────────────────────────
# 1. 직원 데이터 ChromaDB 인덱싱
# ──────────────────────────────────────────────

def _build_employee_document(row: dict) -> str:
    """직원 정보를 검색 최적화 텍스트로 변환"""
    parts = [
        f"이름: {row.get('name', '')}",
        f"부서: {row.get('department', '')}",
        f"본부: {row.get('division', '')}",
        f"직급: {row.get('position', '')}",
        f"사업장: {row.get('plant', '')}",
        f"이메일: {row.get('email', '')}",
        f"내선: {row.get('extension', '')}",
    ]
    if row.get('overseas_assignment'):
        parts.append(f"해외파견: {row['overseas_assignment']}")
    if row.get('language_skills'):
        parts.append(f"언어: {row['language_skills']}")
    return " | ".join(parts)


def index_employees_to_chroma(db_path: str = None) -> int:
    """employees.db 전체를 ChromaDB에 인덱싱"""
    if not CHROMA_AVAILABLE:
        return 0

    db_path = db_path or str(DB_PATH)
    client = chromadb.PersistentClient(path=VECTORSTORE_PATH)

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=_ollama_ef,
    )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM employees WHERE is_active = 1 OR is_active IS NULL"
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    if not rows:
        return 0

    documents = []
    metadatas = []
    ids = []

    for row in rows:
        doc = _build_employee_document(row)
        documents.append(doc)
        metadatas.append({
            "employee_id": str(row.get("employee_id", row.get("id", ""))),
            "name": row.get("name", ""),
            "department": row.get("department", ""),
            "division": row.get("division", ""),
            "position": row.get("position", ""),
            "plant": row.get("plant", ""),
        })
        ids.append(f"emp_{row.get('id', row.get('employee_id', ''))}")

    BATCH_SIZE = 100
    for i in range(0, len(documents), BATCH_SIZE):
        collection.add(
            documents=documents[i:i+BATCH_SIZE],
            metadatas=metadatas[i:i+BATCH_SIZE],
            ids=ids[i:i+BATCH_SIZE],
        )

    logger.info(f"Employee ChromaDB 인덱싱 완료: {len(documents)}건")
    return len(documents)


def _ensure_indexed() -> bool:
    """인덱싱 여부 확인, 없으면 자동 인덱싱"""
    if not CHROMA_AVAILABLE:
        return False
    try:
        client = chromadb.PersistentClient(path=VECTORSTORE_PATH)
        collection = client.get_collection(COLLECTION_NAME, embedding_function=_ollama_ef)
        if collection.count() > 0:
            return True
    except Exception:
        pass

    count = index_employees_to_chroma()
    return count > 0


# ──────────────────────────────────────────────
# 2. 하이브리드 검색 (FTS5 + Semantic + RRF)
# ──────────────────────────────────────────────

def hybrid_search(
    query: str,
    db_path: str = None,
    top_k: int = 20,
    fts_weight: float = 0.4,
    semantic_weight: float = 0.6,
) -> List[Dict]:
    """
    FTS5 키워드 검색 + ChromaDB 시맨틱 검색 결합
    RRF(Reciprocal Rank Fusion) 방식으로 스코어 통합
    """
    db_path = db_path or str(DB_PATH)
    k_constant = 60

    # FTS5 검색
    fts_results = _fts5_search(query, db_path, top_k=top_k * 2)

    # 시맨틱 검색
    semantic_results = _semantic_search(query, top_k=top_k * 2)

    # RRF 스코어 통합
    rrf_scores = {}
    employee_data = {}

    for rank, row in enumerate(fts_results):
        emp_id = str(row.get("employee_id", row.get("id", "")))
        rrf_scores[emp_id] = rrf_scores.get(emp_id, 0) + \
            fts_weight * (1.0 / (k_constant + rank + 1))
        employee_data[emp_id] = row

    for rank, (emp_id, metadata, distance) in enumerate(semantic_results):
        rrf_scores[emp_id] = rrf_scores.get(emp_id, 0) + \
            semantic_weight * (1.0 / (k_constant + rank + 1))
        if emp_id not in employee_data:
            full_row = _get_employee_by_id(emp_id, db_path)
            if full_row:
                employee_data[emp_id] = full_row

    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    results = []
    for emp_id in sorted_ids[:top_k]:
        if emp_id in employee_data:
            row = employee_data[emp_id]
            row["_rrf_score"] = round(rrf_scores[emp_id], 4)
            row["_search_method"] = "hybrid"
            results.append(row)

    return results


def _fts5_search(query: str, db_path: str, top_k: int = 40) -> List[Dict]:
    """FTS5 검색"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    safe_query = query.replace('"', '').replace("'", "").strip()
    results = []

    try:
        # FTS5: 각 단어를 OR로 결합
        words = safe_query.split()
        if words:
            fts_query = " OR ".join(words)
            cursor = conn.execute(
                """SELECT e.* FROM employees e
                   JOIN employees_fts fts ON e.rowid = fts.rowid
                   WHERE employees_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (fts_query, top_k)
            )
            results = [dict(r) for r in cursor.fetchall()]
    except Exception:
        pass

    # FTS5 결과 부족 시 LIKE 보충
    if len(results) < 3:
        try:
            existing_ids = {r.get("employee_id", r.get("id")) for r in results}
            like_conditions = []
            like_params = []
            for word in safe_query.split():
                for col in ("name", "department", "position", "division", "plant", "email", "extension"):
                    like_conditions.append(f"{col} LIKE ?")
                    like_params.append(f"%{word}%")

            if like_conditions:
                cursor = conn.execute(
                    f"SELECT * FROM employees WHERE {' OR '.join(like_conditions)} LIMIT ?",
                    like_params + [top_k]
                )
                for r in cursor.fetchall():
                    row = dict(r)
                    rid = row.get("employee_id", row.get("id"))
                    if rid not in existing_ids:
                        results.append(row)
                        existing_ids.add(rid)
        except Exception:
            pass

    conn.close()
    return results[:top_k]


def _semantic_search(query: str, top_k: int = 40) -> List[Tuple[str, dict, float]]:
    """ChromaDB 시맨틱 검색"""
    if not CHROMA_AVAILABLE or not _ensure_indexed():
        return []

    try:
        client = chromadb.PersistentClient(path=VECTORSTORE_PATH)
        collection = client.get_collection(COLLECTION_NAME, embedding_function=_ollama_ef)
        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, collection.count()),
            include=["metadatas", "distances"],
        )

        output = []
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                emp_id = results["metadatas"][0][i].get("employee_id", "")
                metadata = results["metadatas"][0][i]
                distance = results["distances"][0][i] if results["distances"] else 0
                output.append((emp_id, metadata, distance))
        return output
    except Exception:
        return []


def _get_employee_by_id(employee_id: str, db_path: str) -> Optional[Dict]:
    """employee_id로 직원 정보 조회"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT * FROM employees WHERE employee_id = ?",
            (employee_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()
