"""
설비 매뉴얼 RAG — PDF/MD 매뉴얼을 ChromaDB에 인덱싱하고 자연어로 검색
기존 기능 C의 RAG 파이프라인과 동일한 구조를 재사용합니다.
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MANUAL_COLLECTION = "equipment_manuals"
MANUALS_DIR = Path("data/equipment/manuals")


class ManualRAG:
    """설비 매뉴얼 RAG 검색 엔진"""

    def __init__(self, vectorstore_path: str = "vectorstore"):
        self.vectorstore_path = Path(vectorstore_path)

    def _get_collection(self):
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(self.vectorstore_path))
            return client.get_collection(MANUAL_COLLECTION)
        except Exception as e:
            logger.debug(f"매뉴얼 컬렉션 없음: {e}")
            return None

    def search(
        self,
        query: str,
        equipment_type: str = None,
        n_results: int = 5,
    ) -> list[dict]:
        """
        매뉴얼에서 관련 내용을 검색합니다.

        Args:
            query: 자연어 질의 (예: "프레스 압력 이상 시 조치")
            equipment_type: 설비 유형 필터 (선택)
            n_results: 최대 결과 수

        Returns:
            [{"content": str, "metadata": dict, "relevance": float}, ...]
        """
        collection = self._get_collection()
        if not collection:
            return []

        try:
            where_filter = None
            if equipment_type:
                where_filter = {"equipment_type": {"$eq": equipment_type}}

            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter if where_filter else None,
            )

            items = []
            if results and results["documents"]:
                for idx, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][idx] if results["metadatas"] else {}
                    distance = results["distances"][0][idx] if results["distances"] else 1.0
                    relevance = max(0, 1 - distance)

                    items.append({
                        "content": doc,
                        "metadata": meta,
                        "relevance": round(relevance, 3),
                    })

            return items

        except Exception as e:
            logger.warning(f"매뉴얼 검색 실패: {e}")
            return []

    def answer_with_context(
        self,
        query: str,
        llm_client,
        equipment_type: str = None,
        error_code_context: str = "",
    ) -> str:
        """
        매뉴얼 검색 결과를 LLM 컨텍스트로 주입하여 답변을 생성합니다.
        """
        results = self.search(query, equipment_type, n_results=3)

        context_parts = []

        if error_code_context:
            context_parts.append(f"[에러코드 정보]\n{error_code_context}")

        if results:
            context_parts.append("[설비 매뉴얼 참고]")
            for i, r in enumerate(results, 1):
                source = r["metadata"].get("source", "매뉴얼")
                page = r["metadata"].get("page", "")
                page_info = f" (p.{page})" if page else ""
                context_parts.append(
                    f"--- 참고 {i}{page_info} [{source}] ---\n{r['content'][:800]}"
                )

        context = "\n\n".join(context_parts)

        system = """당신은 아진산업의 설비 유지보수 전문가입니다.
제조 현장 엔지니어에게 설비 매뉴얼 기반으로 정확하고 실용적인 답변을 제공합니다.

## 응답 규칙
- 매뉴얼 내용을 기반으로 정확히 답변하세요
- 안전 주의사항이 있으면 반드시 먼저 언급하세요
- 단계별 절차가 있으면 번호를 매겨 정리하세요
- 일본어/영어 원문 용어가 있으면 한국어 번역을 병기하세요
- 매뉴얼에 없는 내용이면 "매뉴얼에서 확인되지 않았습니다" 라고 안내하세요
- 심각한 설비 이상은 "즉시 라인 정지 후 담당자에게 연락하세요"를 포함하세요
"""

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"{context}\n\n질문: {query}"},
        ]

        try:
            response = llm_client.generate(
                messages=messages,
                max_tokens=2048,
                temperature=0.2,
                stream=False,
            )
            return response.strip()
        except Exception as e:
            logger.error(f"매뉴얼 답변 생성 실패: {e}")
            return "답변 생성에 실패했습니다. 매뉴얼을 직접 확인해 주세요."


def index_manuals(
    manuals_dir: str = str(MANUALS_DIR),
    vectorstore_path: str = "vectorstore",
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> int:
    """
    data/equipment/manuals/ 하위 파일을 ChromaDB에 인덱싱합니다.

    지원 형식: .md, .txt, .pdf (pypdf)
    청킹: chunk_size 글자 단위, chunk_overlap 겹침
    """
    import chromadb

    client = chromadb.PersistentClient(path=vectorstore_path)
    collection = client.get_or_create_collection(
        name=MANUAL_COLLECTION,
        metadata={"description": "아진산업 설비 매뉴얼"},
    )

    manuals_path = Path(manuals_dir)
    if not manuals_path.exists():
        manuals_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"매뉴얼 디렉토리 생성: {manuals_path}")
        return 0

    count = 0

    for file_path in sorted(manuals_path.iterdir()):
        if file_path.suffix not in (".md", ".txt", ".pdf"):
            continue

        text = _extract_text(file_path)
        if not text or len(text) < 20:
            continue

        equipment_type = _infer_equipment_type(file_path.stem)
        chunks = _split_text(text, chunk_size, chunk_overlap)

        for i, chunk in enumerate(chunks):
            doc_id = f"{file_path.stem}_chunk_{i:04d}"

            try:
                existing = collection.get(ids=[doc_id])
                if existing and existing["ids"]:
                    continue
            except Exception:
                pass

            try:
                collection.add(
                    documents=[chunk],
                    ids=[doc_id],
                    metadatas=[{
                        "source": file_path.name,
                        "equipment_type": equipment_type,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "page": str(i + 1),
                    }],
                )
                count += 1
            except Exception as e:
                logger.warning(f"청크 인덱싱 실패 {doc_id}: {e}")

    logger.info(f"매뉴얼 인덱싱 완료: {count}건")
    return count


def _extract_text(file_path: Path) -> str:
    """파일에서 텍스트를 추출합니다."""
    if file_path.suffix in (".md", ".txt"):
        return file_path.read_text(encoding="utf-8")

    elif file_path.suffix == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(pages)
        except Exception as e:
            logger.warning(f"PDF 텍스트 추출 실패 {file_path.name}: {e}")
            return ""

    return ""


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """텍스트를 청크로 분할합니다."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    return chunks


def _infer_equipment_type(filename: str) -> str:
    """파일명에서 설비 유형을 추론합니다."""
    name_lower = filename.lower()
    type_map = {
        "press": "프레스", "프레스": "프레스",
        "welder": "용접기", "용접": "용접기", "weld": "용접기",
        "robot": "로봇", "로봇": "로봇",
        "cnc": "CNC", "machining": "CNC",
        "conveyor": "컨베이어", "컨베이어": "컨베이어",
        "injection": "사출기", "사출": "사출기",
        "paint": "도장설비", "도장": "도장설비",
        "assembly": "조립설비", "조립": "조립설비",
    }
    for keyword, equip_type in type_map.items():
        if keyword in name_lower:
            return equip_type
    return "기타"
