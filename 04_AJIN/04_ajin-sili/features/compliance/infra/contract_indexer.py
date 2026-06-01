"""P2 D7 — 계약 영향 분석.

PDF/docx 계약을 조항 단위로 split → SQLite + ChromaDB 적재.
ChangeRecord → 영향 계약 자동 매핑 (유사 조항 검색 + 키워드 overlap).

DB:
  data/contracts.db
    contracts(contract_id, counterparty, type, effective_date, expiry_date,
              annual_value_krw_mn, status, file_path)
    contract_clauses(id, contract_id, clause_no, title, body, keywords)

ChromaDB collection: contracts_rag
"""
from __future__ import annotations

import io
import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "contracts.db"
VECTORSTORE_PATH = "vectorstore"
COLLECTION_NAME = "contracts_rag"


# ─────────────────────────────────────────────────────────────
# DB 초기화
# ─────────────────────────────────────────────────────────────


def init_contracts_db():
    """contracts.db 초기화 (멱등)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS contracts (
            contract_id TEXT PRIMARY KEY,
            counterparty TEXT,
            type TEXT,
            effective_date TEXT,
            expiry_date TEXT,
            annual_value_krw_mn INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            file_path TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS contract_clauses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id TEXT REFERENCES contracts(contract_id),
            clause_no TEXT,
            title TEXT,
            body TEXT,
            keywords TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_clauses_contract ON contract_clauses(contract_id);
        CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
    """)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────
# 조항 분리
# ─────────────────────────────────────────────────────────────

# 한국어/영문 계약 조항 헤더 패턴
_CLAUSE_HEADER_RE = re.compile(
    r"^\s*(제\s*\d+\s*조(?:의?\s*\d+)?|Article\s*\d+(?:\.\d+)?|Section\s*\d+)\s*[.:\-]?\s*(.{0,80})?",
    re.MULTILINE,
)

# 키워드 추출 — 도메인 사전 (계약 영향 매핑용 키)
_KEYWORD_PATTERNS = (
    "관세", "납기", "단가", "가격", "원산지", "RoHS", "REACH", "안전",
    "환경", "인증", "ISO", "IATF", "PPAP", "보증", "위약금", "해지",
    "납품 중단", "리콜", "결함", "품질", "영업비밀", "지적재산",
)


def split_into_clauses(text: str) -> list[dict[str, str]]:
    """본문 텍스트 → 조항 단위 분리.

    매 조항 헤더 (예: "제5조 (안전기준)") 위치를 기준으로 split.
    헤더가 0개면 전체 본문을 single clause 로 처리.
    """
    text = (text or "").strip()
    if not text:
        return []

    matches = list(_CLAUSE_HEADER_RE.finditer(text))
    if not matches:
        return [{"clause_no": "", "title": "", "body": text[:5000]}]

    clauses: list[dict[str, str]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()[:3000]
        clauses.append({
            "clause_no": m.group(1).strip(),
            "title": (m.group(2) or "").strip()[:80],
            "body": body,
        })
    return clauses


def extract_keywords(text: str) -> list[str]:
    """본문 → 도메인 키워드 매칭."""
    found: list[str] = []
    for kw in _KEYWORD_PATTERNS:
        if kw in text:
            found.append(kw)
    return found


# ─────────────────────────────────────────────────────────────
# 본문 추출 (PDF / docx / txt)
# ─────────────────────────────────────────────────────────────


def extract_text_from_file(file_path: str | Path) -> str:
    """확장자별 텍스트 추출. PDF / docx / txt 지원.

    실패 시 RuntimeError raise — 호출자가 처리.
    """
    p = Path(file_path)
    if not p.exists():
        raise RuntimeError(f"파일 미존재: {file_path}")
    suf = p.suffix.lower()

    if suf == ".txt":
        return p.read_text(encoding="utf-8", errors="replace")

    if suf == ".pdf":
        try:
            import pypdf  # type: ignore
        except ImportError as e:
            raise RuntimeError(f"pypdf 미설치 — PDF 파싱 불가: {e}")
        reader = pypdf.PdfReader(str(p))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    if suf in (".docx", ".doc"):
        try:
            from docx import Document
        except ImportError as e:
            raise RuntimeError(f"python-docx 미설치 — docx 파싱 불가: {e}")
        doc = Document(str(p))
        return "\n".join(par.text for par in doc.paragraphs)

    raise RuntimeError(f"지원되지 않는 확장자: {suf}")


# ─────────────────────────────────────────────────────────────
# Ingest
# ─────────────────────────────────────────────────────────────


def ingest_contract(
    file_path: str | Path,
    contract_id: str,
    counterparty: str = "",
    contract_type: str = "OEM",
    effective_date: str = "",
    expiry_date: str = "",
    annual_value_krw_mn: int = 0,
) -> dict[str, Any]:
    """계약 파일 → DB + ChromaDB 적재.

    Returns:
        {ok: bool, clause_count: int, contract_id: str, error?: str}
    """
    init_contracts_db()
    try:
        text = extract_text_from_file(file_path)
    except RuntimeError as e:
        return {"ok": False, "error": str(e), "contract_id": contract_id, "clause_count": 0}

    clauses = split_into_clauses(text)
    if not clauses:
        return {"ok": False, "error": "본문 비어있음", "contract_id": contract_id, "clause_count": 0}

    # SQLite 적재
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """INSERT OR REPLACE INTO contracts
           (contract_id, counterparty, type, effective_date, expiry_date,
            annual_value_krw_mn, status, file_path, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (contract_id, counterparty, contract_type, effective_date, expiry_date,
         int(annual_value_krw_mn or 0), "active", str(file_path),
         datetime.now().isoformat()),
    )
    conn.execute("DELETE FROM contract_clauses WHERE contract_id = ?", (contract_id,))
    for cl in clauses:
        keywords = extract_keywords(cl["body"])
        conn.execute(
            """INSERT INTO contract_clauses
               (contract_id, clause_no, title, body, keywords)
               VALUES (?,?,?,?,?)""",
            (contract_id, cl["clause_no"], cl["title"], cl["body"],
             ",".join(keywords)),
        )
    conn.commit()
    conn.close()

    # ChromaDB 적재 (선택 — 미가용 시 SQLite-only 검색)
    try:
        _index_to_chroma(contract_id, counterparty, clauses)
    except Exception as e:
        logger.warning("ChromaDB 적재 실패 contract_id=%s: %s", contract_id, e)

    return {"ok": True, "clause_count": len(clauses), "contract_id": contract_id}


def _index_to_chroma(contract_id: str, counterparty: str, clauses: list[dict]):
    """ChromaDB contracts_rag 컬렉션에 조항 적재."""
    try:
        import chromadb
    except ImportError:
        return
    try:
        from langchain_ollama import OllamaEmbeddings
        from chromadb.utils.embedding_functions import create_langchain_embedding
        from config import OLLAMA_BASE_URL, EMBEDDING_MODEL
        ef = create_langchain_embedding(
            OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)
        )
    except Exception:
        ef = None

    client = chromadb.PersistentClient(path=VECTORSTORE_PATH)
    kwargs: dict[str, Any] = {"name": COLLECTION_NAME, "metadata": {"hnsw:space": "cosine"}}
    if ef:
        kwargs["embedding_function"] = ef
    coll = client.get_or_create_collection(**kwargs)

    ids = [f"{contract_id}-c{i}" for i, _ in enumerate(clauses)]
    documents = [(c["title"] + " " + c["body"]).strip()[:1500] for c in clauses]
    metadatas = [
        {
            "contract_id": contract_id,
            "counterparty": counterparty,
            "clause_no": c.get("clause_no", ""),
            "title": c.get("title", "")[:80],
            "keywords": ",".join(extract_keywords(c["body"])),
        }
        for c in clauses
    ]
    coll.upsert(ids=ids, documents=documents, metadatas=metadatas)


# ─────────────────────────────────────────────────────────────
# 영향 매핑
# ─────────────────────────────────────────────────────────────


def match_contracts(change: dict[str, Any], top_k: int = 5) -> list[dict[str, Any]]:
    """ChangeRecord → 영향 계약 list (조항 단위 매칭).

    1. ChromaDB 유사 조항 top-k 검색 (의미적 매칭)
    2. SQLite 키워드 overlap 보조 (룰 기반)
    """
    init_contracts_db()
    query_text = " ".join([
        str(change.get("item_title") or ""),
        str(change.get("summary_ko") or ""),
        str(change.get("new_value") or "")[:500],
    ]).strip()
    if not query_text:
        return []

    chroma_hits = _chroma_search(query_text, top_k=top_k)

    # SQLite — 키워드 overlap (의미 검색 폴백/보강)
    change_keywords = set(extract_keywords(query_text))
    sql_hits: list[dict[str, Any]] = []
    if change_keywords:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT cl.contract_id, cl.clause_no, cl.title, cl.body, cl.keywords,
                      c.counterparty, c.type
               FROM contract_clauses cl
               JOIN contracts c ON cl.contract_id = c.contract_id
               WHERE c.status = 'active'"""
        ).fetchall()
        conn.close()
        for r in rows:
            row_kws = set((r["keywords"] or "").split(","))
            overlap = change_keywords & row_kws
            if overlap:
                sql_hits.append({
                    "contract_id": r["contract_id"],
                    "counterparty": r["counterparty"],
                    "type": r["type"],
                    "clause_no": r["clause_no"],
                    "title": r["title"],
                    "body_excerpt": (r["body"] or "")[:200],
                    "match_keywords": sorted(overlap),
                    "source": "keyword",
                })

    # 통합 — chroma 우선, 같은 (contract_id, clause_no) dedupe
    seen: set[tuple[str, str]] = set()
    merged: list[dict[str, Any]] = []
    for h in chroma_hits + sql_hits:
        key = (h["contract_id"], h.get("clause_no", ""))
        if key in seen:
            continue
        seen.add(key)
        merged.append(h)
    return merged[:top_k]


def _chroma_search(query: str, top_k: int) -> list[dict[str, Any]]:
    try:
        import chromadb
        client = chromadb.PersistentClient(path=VECTORSTORE_PATH)
        coll = client.get_or_create_collection(
            name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )
        result = coll.query(query_texts=[query], n_results=top_k)
    except Exception as e:
        logger.debug("contracts ChromaDB 미가용: %s", e)
        return []

    metas = (result.get("metadatas") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]

    out = []
    for m, d, dist in zip(metas, docs, dists):
        sim = max(0.0, 1.0 - float(dist))
        if sim < 0.55:  # 계약 매칭은 임계값 낮춤 (단어 다양성 큼)
            continue
        out.append({
            "contract_id": m.get("contract_id", ""),
            "counterparty": m.get("counterparty", ""),
            "clause_no": m.get("clause_no", ""),
            "title": m.get("title", ""),
            "body_excerpt": (d or "")[:200],
            "similarity": round(sim, 3),
            "source": "vector",
        })
    return out


def list_contracts(limit: int = 50, search: str = "") -> list[dict[str, Any]]:
    """계약 목록 — UI 검색·필터용."""
    init_contracts_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM contracts WHERE 1=1"
    params: list[Any] = []
    if search:
        sql += " AND (counterparty LIKE ? OR contract_id LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(max(1, min(limit, 500)))
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
