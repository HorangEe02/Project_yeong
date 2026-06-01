"""Issue 1 — Supabase pgvector 문서 인덱싱 스크립트.

기존 reindex_v16.py / reindex_fewshot_rag.py 가 ChromaDB 를 사용했던 자리에
Supabase pgvector (document_chunks + document_embeddings) 로 직접 적재한다.

대상 디렉토리 (멀티 소스 통합):
    data/documents/**/*.md, *.txt    — 사내 문서 (8D/ECN/PPAP 샘플 등)
    data/glossary/*.json             — 용어집
    data/knowledge_base/**/*.j2      — 보고서 템플릿

임베딩: bge-m3 (Ollama) — `core/embedding_client.py` 의 `get_embeddings().embed_query()`
업서트: SupabasePgvectorStore.upsert_document_chunks()

사용법:
    cd ajin-ai-assistant-react
    python -m scripts.reindex_pgvector_documents
    python -m scripts.reindex_pgvector_documents --dry-run    # 임베딩 없이 chunk 수만 출력
    python -m scripts.reindex_pgvector_documents --limit 50   # 처음 50건만 (테스트용)

환경변수:
    DATABASE_URL              — Supabase Postgres DSN
    OLLAMA_BASE_URL           — bge-m3 호출용
    VECTOR_EMBEDDING_MODEL    — 기본 bge-m3
    VECTOR_EMBEDDING_DIM      — 기본 1024
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def iter_document_files() -> list[tuple[str, str, Path, str]]:
    """(source_doc_id, doc_type, path, content) 리스트 반환."""
    out: list[tuple[str, str, Path, str]] = []

    docs_dir = ROOT / "data" / "documents"
    if docs_dir.exists():
        for p in sorted(docs_dir.rglob("*")):
            if p.is_file() and p.suffix.lower() in {".md", ".txt"}:
                rel = p.relative_to(docs_dir).as_posix()
                doc_type = rel.split("/", 1)[0] if "/" in rel else "general"
                try:
                    content = p.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                out.append((f"doc::{rel}", doc_type, p, content))

    glossary_dir = ROOT / "data" / "glossary"
    if glossary_dir.exists():
        for p in sorted(glossary_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            entries = data if isinstance(data, list) else data.get("terms", [])
            for i, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    continue
                term = entry.get("term") or entry.get("name") or f"entry-{i}"
                desc = entry.get("definition") or entry.get("description") or ""
                if not desc.strip():
                    continue
                content = f"{term}: {desc}"
                out.append((f"glossary::{p.stem}::{term}", "glossary", p, content))

    kb_dir = ROOT / "data" / "knowledge_base"
    if kb_dir.exists():
        for p in sorted(kb_dir.rglob("*.j2")):
            try:
                content = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            rel = p.relative_to(kb_dir).as_posix()
            out.append((f"template::{rel}", "template", p, content))

    return out


def chunk_content(content: str, max_chars: int = 1500) -> list[str]:
    """단순 길이 기반 청크 분할 — 단락 경계 우선, 최대 max_chars."""
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0
    for para in paragraphs:
        if buf_len + len(para) + 2 > max_chars and buf:
            chunks.append("\n\n".join(buf))
            buf = [para]
            buf_len = len(para)
        else:
            buf.append(para)
            buf_len += len(para) + 2
    if buf:
        chunks.append("\n\n".join(buf))
    if not chunks:
        return [content[:max_chars]] if content.strip() else []
    return chunks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="임베딩 없이 chunk 수만 출력")
    parser.add_argument("--limit", type=int, default=0, help="처음 N개 문서만 처리 (테스트용)")
    args = parser.parse_args()

    files = iter_document_files()
    if args.limit:
        files = files[: args.limit]

    print(f"[reindex-pgvector] 문서 수집: {len(files)}건")
    if not files:
        print("[reindex-pgvector] 대상 파일 없음 — data/{documents,glossary,knowledge_base} 확인")
        return 1

    total_chunks = 0
    chunked_items: list[tuple[str, str, str, int, str, Path]] = []
    for source_doc_id, doc_type, path, content in files:
        for i, chunk in enumerate(chunk_content(content)):
            chunked_items.append((source_doc_id, doc_type, path.name, i, chunk, path))
            total_chunks += 1

    print(f"[reindex-pgvector] 총 청크 수: {total_chunks}")

    if args.dry_run:
        print("[reindex-pgvector] dry-run 종료")
        return 0

    print("[reindex-pgvector] 임베딩 + 업서트 시작...")

    from core.embedding_client import get_embeddings
    from features.search.vector_store import SupabasePgvectorStore
    from features.search.vector_store.pgvector import DocumentChunkInput

    embedder = get_embeddings()
    store = SupabasePgvectorStore()

    batch: list[DocumentChunkInput] = []
    BATCH = 32
    processed = 0
    for source_doc_id, doc_type, title, chunk_index, chunk_text, path in chunked_items:
        try:
            embedding = embedder.embed_query(chunk_text)
        except Exception as e:
            print(f"  [SKIP] embed 실패 {source_doc_id}#{chunk_index}: {e}")
            continue

        batch.append(
            DocumentChunkInput(
                source_doc_id=source_doc_id,
                chunk_index=chunk_index,
                content=chunk_text,
                embedding=embedding,
                metadata={"path": str(path), "title": title},
                title=title,
                doc_type=doc_type,
                source_path=str(path),
            )
        )

        if len(batch) >= BATCH:
            n = store.upsert_document_chunks(batch)
            processed += n
            batch.clear()
            print(f"  [BATCH] upsert {n} — 누적 {processed}")

    if batch:
        n = store.upsert_document_chunks(batch)
        processed += n
        print(f"  [BATCH] upsert {n} — 누적 {processed} (final)")

    print(f"[reindex-pgvector] 완료. 총 {processed} 청크 적재.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
