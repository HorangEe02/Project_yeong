"""
Few-shot RAG 파이프라인 -- 사내 문서 샘플 기반 스타일 학습
- 문서유형별 ChromaDB 컬렉션에 기존 문서 청킹/인덱싱
- 생성 시 동일 유형 상위 2~3건을 Few-shot 예시로 프롬프트에 주입
"""

from typing import List, Dict
from pathlib import Path
import logging

try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

logger = logging.getLogger(__name__)

COLLECTION_NAME = "draft_fewshot_samples"
SAMPLE_DIR = Path("data/documents")
TEMPLATE_DIR = Path("data/templates")

DOC_TYPE_TAGS = {
    "사내 이메일": "email_internal",
    "회의록": "meeting_note",
    "8D 보고서": "8d_report",
    "ECN 변경통보": "ecn_notice",
    "품질문제 개선대책서": "quality_improvement",
    "안전 인시던트 리포트": "incident_report",
    "OEM 이메일": "email_oem",
    "협력사 이메일": "email_supplier",
    "해외법인 이메일": "email_overseas",
    "HMGMA 이메일": "email_hmgma",
    "납입용기 규격 설정서": "container_spec",
    "사급 반출 요청서": "supply_dispatch",
    "PPAP 체크리스트": "ppap_checklist",
}

# Ollama 임베딩 (시맨틱 검색용)
_embedding_fn = None
try:
    from langchain_ollama import OllamaEmbeddings
    from chromadb.utils.embedding_functions import create_langchain_embedding
    from config import OLLAMA_BASE_URL, EMBEDDING_MODEL
    _lc_embed = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)
    _embedding_fn = create_langchain_embedding(_lc_embed)
except Exception:
    pass


def _chunk_document(text: str, max_chars: int = 1500) -> List[str]:
    """문서를 청크로 분할"""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    section_markers = ["## ", "### ", "---", "\n\n\n"]
    current_chunk = ""

    for line in text.split("\n"):
        if any(line.strip().startswith(m.strip()) for m in section_markers):
            if current_chunk and len(current_chunk) > 100:
                chunks.append(current_chunk.strip())
                current_chunk = ""
        current_chunk += line + "\n"
        if len(current_chunk) >= max_chars:
            chunks.append(current_chunk.strip())
            current_chunk = ""

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text[:max_chars]]


def index_document_samples() -> int:
    """data/documents/ + data/templates/ 내 모든 문서를 ChromaDB에 인덱싱"""
    if not CHROMA_AVAILABLE:
        return 0

    client = chromadb.PersistentClient(path="vectorstore")
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=_embedding_fn,
    )

    documents = []
    metadatas = []
    ids = []
    doc_counter = 0

    # data/documents/ 하위 파일
    if SAMPLE_DIR.exists():
        for filepath in SAMPLE_DIR.rglob("*"):
            if filepath.suffix in (".md", ".txt", ".j2"):
                try:
                    text = filepath.read_text(encoding="utf-8")
                except Exception:
                    continue
                if len(text.strip()) < 50:
                    continue

                doc_tag = _infer_doc_type_tag(filepath)
                chunks = _chunk_document(text)
                for i, chunk in enumerate(chunks):
                    doc_counter += 1
                    documents.append(chunk)
                    metadatas.append({
                        "source_file": str(filepath.relative_to(SAMPLE_DIR)) if filepath.is_relative_to(SAMPLE_DIR) else filepath.name,
                        "doc_type_tag": doc_tag,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                    })
                    ids.append(f"doc_{doc_counter}")

    # Jinja2 템플릿
    if TEMPLATE_DIR.exists():
        for filepath in TEMPLATE_DIR.rglob("*.j2"):
            try:
                text = filepath.read_text(encoding="utf-8")
            except Exception:
                continue
            if len(text.strip()) < 30:
                continue

            doc_tag = _infer_doc_type_tag(filepath)
            doc_counter += 1
            documents.append(text)
            metadatas.append({
                "source_file": f"template/{filepath.name}",
                "doc_type_tag": doc_tag,
                "chunk_index": 0,
                "total_chunks": 1,
                "is_template": "true",
            })
            ids.append(f"doc_{doc_counter}")

    if documents:
        BATCH_SIZE = 50
        for i in range(0, len(documents), BATCH_SIZE):
            collection.add(
                documents=documents[i:i+BATCH_SIZE],
                metadatas=metadatas[i:i+BATCH_SIZE],
                ids=ids[i:i+BATCH_SIZE],
            )

    logger.info(f"Few-shot RAG 인덱싱 완료: {len(documents)}건")
    return len(documents)


def _infer_doc_type_tag(filepath: Path) -> str:
    """파일 경로/이름에서 문서유형 태그 추론"""
    name_lower = filepath.name.lower()
    path_str = str(filepath).lower()

    tag_keywords = {
        "8d": "8d_report", "ecn": "ecn_notice", "ppap": "ppap_checklist",
        "meeting": "meeting_note", "회의록": "meeting_note",
        "email": "email_internal", "이메일": "email_internal",
        "quality": "quality_improvement", "품질": "quality_improvement",
        "incident": "incident_report", "안전": "incident_report",
        "oem": "email_oem", "supplier": "email_supplier",
        "overseas": "email_overseas", "container": "container_spec",
        "dispatch": "supply_dispatch", "fmea": "fmea", "sop": "sop",
    }

    for keyword, tag in tag_keywords.items():
        if keyword in name_lower or keyword in path_str:
            return tag
    return "general"


def _ensure_indexed() -> bool:
    """인덱싱 여부 확인, 없으면 자동 인덱싱"""
    if not CHROMA_AVAILABLE:
        return False
    try:
        client = chromadb.PersistentClient(path="vectorstore")
        col = client.get_collection(COLLECTION_NAME, embedding_function=_embedding_fn)
        if col.count() > 0:
            return True
    except Exception:
        pass
    count = index_document_samples()
    return count > 0


def retrieve_fewshot_samples(
    doc_type: str,
    user_query: str = "",
    top_k: int = 3,
    max_total_chars: int = 3000,
) -> List[Dict]:
    """문서유형 기반 Few-shot 샘플 검색"""
    if not CHROMA_AVAILABLE or not _ensure_indexed():
        return []

    try:
        client = chromadb.PersistentClient(path="vectorstore")
        collection = client.get_collection(COLLECTION_NAME, embedding_function=_embedding_fn)
    except Exception:
        return []

    doc_tag = DOC_TYPE_TAGS.get(doc_type, "general")
    query_text = f"{doc_type} {user_query}".strip()

    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=min(top_k * 2, collection.count()),
            where={"doc_type_tag": doc_tag} if doc_tag != "general" else None,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        try:
            results = collection.query(
                query_texts=[query_text],
                n_results=min(top_k, collection.count()),
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            return []

    if not results or not results["ids"] or not results["ids"][0]:
        return []

    samples = []
    total_chars = 0

    for i, doc_id in enumerate(results["ids"][0]):
        text = results["documents"][0][i]
        metadata = results["metadatas"][0][i]

        if total_chars + len(text) > max_total_chars:
            remaining = max_total_chars - total_chars
            if remaining > 200:
                text = text[:remaining] + "..."
            else:
                break

        samples.append({
            "text": text,
            "source": metadata.get("source_file", "unknown"),
            "doc_type_tag": metadata.get("doc_type_tag", ""),
            "is_template": metadata.get("is_template", "false") == "true",
        })
        total_chars += len(text)

        if len(samples) >= top_k:
            break

    return samples


def build_fewshot_prompt_section(samples: List[Dict]) -> str:
    """Few-shot 샘플을 LLM 프롬프트 섹션으로 포매팅"""
    if not samples:
        return ""

    parts = ["\n--- 참고: 아진산업 기존 문서 양식 ---"]
    for i, s in enumerate(samples, 1):
        label = "양식 템플릿" if s.get("is_template") else "기존 문서 예시"
        parts.append(f"\n[{label} {i}] (출처: {s['source']})")
        parts.append(s["text"])

    parts.append("\n--- 위 양식과 톤/구조를 참고하여 새 문서를 작성하세요 ---\n")
    return "\n".join(parts)
