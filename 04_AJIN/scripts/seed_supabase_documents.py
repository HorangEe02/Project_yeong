#!/usr/bin/env python3
"""아진산업 AJIN Supabase document_chunks + document_embeddings 시드 스크립트.

기본은 --dry-run (청킹만, 임베딩·DB 업서트 없음).
--apply 플래그로 실제 Ollama 임베딩 생성 + Supabase 업서트를 실행한다.

사용 예:
    python3 scripts/seed_supabase_documents.py --dry-run
    python3 scripts/seed_supabase_documents.py --apply
    python3 scripts/seed_supabase_documents.py --apply --limit=5 --batch-size=8
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------

@dataclass
class Document:
    doc_id: str
    title: str
    doc_type: str
    content: str
    source_path: str
    part_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 청킹
# ---------------------------------------------------------------------------

import re


def chunk_korean(text: str, size: int = 500, overlap: int = 100) -> list[str]:
    """한국어 단락 우선 분할 후 슬라이딩 윈도우로 길이 기준 분할.

    사전 계획 §2 알고리즘 그대로 구현.

    Args:
        text: 분할할 원문 텍스트.
        size: 최대 청크 크기 (문자 수).
        overlap: 슬라이딩 윈도우 overlap 크기 (문자 수).

    Returns:
        50자 이상 청크 리스트.
    """
    paragraphs = re.split(r"\n\n+", text)
    chunks: list[str] = []
    buffer = ""

    for p in paragraphs:
        if len(buffer) + len(p) <= size:
            buffer = buffer + "\n\n" + p if buffer else p
        else:
            if buffer:
                chunks.append(buffer)
            if len(p) > size:
                # 길이 초과 단락 → 슬라이딩 윈도우
                for i in range(0, len(p), size - overlap):
                    chunk = p[i : i + size]
                    if chunk:
                        chunks.append(chunk)
                buffer = ""
            else:
                buffer = p

    if buffer:
        chunks.append(buffer)

    return [c.strip() for c in chunks if len(c.strip()) >= 50]


# ---------------------------------------------------------------------------
# 문서 로딩
# ---------------------------------------------------------------------------

def load_documents(source_path: str | Path, limit: int | None = None) -> list[Document]:
    """JSON 시드 파일을 읽어 Document 객체 리스트로 반환.

    Args:
        source_path: seed_documents.json 경로 (절대 또는 repo 루트 기준 상대).
        limit: 최대 문서 수 (None이면 전체).

    Returns:
        Document 리스트.
    """
    path = Path(source_path)
    if not path.is_absolute():
        path = ROOT / path

    raw: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"seed_documents.json은 배열이어야 합니다: {path}")

    docs: list[Document] = []
    for item in raw:
        doc = Document(
            doc_id=item["doc_id"],
            title=item["title"],
            doc_type=item["doc_type"],
            content=item["content"],
            source_path=item.get("source_path", ""),
            part_name=item.get("part_name"),
            metadata=item.get("metadata", {}),
        )
        docs.append(doc)
        if limit is not None and len(docs) >= limit:
            break

    return docs


# ---------------------------------------------------------------------------
# 임베딩 (Ollama bge-m3)
# ---------------------------------------------------------------------------

async def embed_batch_async(
    texts: list[str],
    ollama_url: str = "http://localhost:11434",
    model: str = "bge-m3",
) -> list[list[float]]:
    """Ollama /api/embed 엔드포인트로 배치 임베딩 생성.

    사전 계획 §3 API 호출 패턴 그대로 구현.

    Args:
        texts: 임베딩할 텍스트 리스트.
        ollama_url: Ollama 서버 URL.
        model: 임베딩 모델명.

    Returns:
        1024차원 float 리스트의 리스트.

    Raises:
        RuntimeError: Ollama 요청 실패 또는 차원 불일치 시.
    """
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("httpx 패키지가 필요합니다: pip install httpx") from exc

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{ollama_url.rstrip('/')}/api/embed",
            json={"model": model, "input": texts},
        )
        resp.raise_for_status()
        data = resp.json()

    embeddings: list[list[float]] = data.get("embeddings", [])
    if not embeddings:
        raise RuntimeError(f"Ollama 응답에 embeddings 키가 없습니다: {list(data.keys())}")

    # 차원 검증
    for i, emb in enumerate(embeddings):
        if len(emb) != 1024:
            raise RuntimeError(
                f"임베딩 차원 불일치: texts[{i}]의 차원={len(emb)}, 기대=1024"
            )

    return embeddings


def embed_batch_sync(
    texts: list[str],
    ollama_url: str = "http://localhost:11434",
    model: str = "bge-m3",
) -> list[list[float]]:
    """embed_batch_async의 동기 래퍼."""
    return asyncio.run(embed_batch_async(texts, ollama_url, model))


# ---------------------------------------------------------------------------
# Supabase 업서트
# ---------------------------------------------------------------------------

def _sha256_text(text: str) -> str:
    """텍스트 SHA-256 해시 (hex)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _mask_secret(value: str) -> str:
    """시크릿 값 마스킹 (앞 8자 + ***)."""
    if not value:
        return "***"
    return value[:8] + "***"


def upsert_chunks(
    sb_client: Any,
    doc: Document,
    chunks: list[str],
) -> list[str]:
    """document_chunks 테이블에 청크를 업서트하고 UUID 리스트 반환.

    사전 계획 §4 업서트 흐름 그대로 구현.

    Args:
        sb_client: supabase-py 클라이언트.
        doc: 원본 Document.
        chunks: 청크 텍스트 리스트.

    Returns:
        업서트된 청크 UUID 리스트.
    """
    rows = [
        {
            "source_doc_id": doc.doc_id,
            "source_path": doc.source_path,
            "title": doc.title,
            "doc_type": doc.doc_type,
            "part_name": doc.part_name,
            "chunk_index": i,
            "content": chunk,
            "content_hash": _sha256_text(chunk),
            "metadata": doc.metadata,
            "data_class": "demo",
        }
        for i, chunk in enumerate(chunks)
    ]

    # 배치 50행씩 업서트
    chunk_ids: list[str] = []
    batch_size = 50
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        result = (
            sb_client.table("document_chunks")
            .upsert(batch, on_conflict="source_doc_id,chunk_index")
            .execute()
        )
        if result.data:
            chunk_ids.extend(row["id"] for row in result.data)

    return chunk_ids


def upsert_embeddings(
    sb_client: Any,
    chunk_ids: list[str],
    embeddings: list[list[float]],
) -> int:
    """document_embeddings 테이블에 임베딩 업서트.

    Args:
        sb_client: supabase-py 클라이언트.
        chunk_ids: 청크 UUID 리스트.
        embeddings: 1024차원 임베딩 리스트.

    Returns:
        업서트 성공 행 수.
    """
    if len(chunk_ids) != len(embeddings):
        raise ValueError(
            f"chunk_ids({len(chunk_ids)})와 embeddings({len(embeddings)}) 길이 불일치"
        )

    rows = [
        {
            "chunk_id": chunk_id,
            "embedding": embedding,
            "embedding_model": "bge-m3",
            "embedding_dim": 1024,
            "embedding_version": "v1",
        }
        for chunk_id, embedding in zip(chunk_ids, embeddings)
    ]

    success_count = 0
    batch_size = 50
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        result = (
            sb_client.table("document_embeddings")
            .upsert(batch, on_conflict="chunk_id")
            .execute()
        )
        if result.data:
            success_count += len(result.data)

    return success_count


# ---------------------------------------------------------------------------
# 진행 저장 (부분 진척)
# ---------------------------------------------------------------------------

PROGRESS_FILE = Path("/tmp/seed_progress.json")


def _load_progress() -> dict[str, Any]:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_progress(progress: dict[str, Any]) -> None:
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# 메인 시드 흐름
# ---------------------------------------------------------------------------

def seed_main(args: argparse.Namespace) -> int:
    """시드 메인 흐름.

    Args:
        args: argparse 파싱 결과.

    Returns:
        종료 코드 (0=성공).
    """
    try:
        from tqdm import tqdm
    except ImportError:
        # tqdm 없을 경우 passthrough
        class tqdm:  # type: ignore[no-redef]
            def __init__(self, iterable=None, **kwargs):
                self._it = iter(iterable) if iterable is not None else iter([])
                self.n = 0
                desc = kwargs.get("desc", "")
                total = kwargs.get("total", "?")
                print(f"[진행] {desc} (total={total})")

            def __iter__(self):
                return self

            def __next__(self):
                val = next(self._it)
                self.n += 1
                return val

            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def set_postfix_str(self, s: str):
                print(f"  {s}")

    # --- 환경변수 로딩 ---
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SECRET_KEY", "")
    ollama_url = args.ollama_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    if args.apply:
        if not supabase_url:
            print("[오류] SUPABASE_URL 환경변수가 설정되지 않았습니다.", file=sys.stderr)
            return 1
        if not supabase_key:
            print("[오류] SUPABASE_SECRET_KEY 환경변수가 설정되지 않았습니다.", file=sys.stderr)
            return 1
        print(f"[정보] Supabase URL: {supabase_url}")
        print(f"[정보] Supabase KEY: {_mask_secret(supabase_key)}")
        print(f"[정보] Ollama URL: {ollama_url}")

    # --- 문서 로딩 ---
    print(f"\n[1/4] 문서 로딩: {args.source}")
    docs = load_documents(args.source, limit=args.limit)
    print(f"  로딩 완료: {len(docs)}개 문서")

    # --- 청킹 ---
    print("\n[2/4] 청킹 (chunk_size=500, overlap=100)")
    doc_chunks: list[tuple[Document, list[str]]] = []
    total_chunks = 0

    for doc in tqdm(docs, desc="청킹"):
        chunks = chunk_korean(doc.content, size=500, overlap=100)
        doc_chunks.append((doc, chunks))
        total_chunks += len(chunks)

    # 타입별 통계
    type_stats: dict[str, dict[str, int]] = {}
    for doc, chunks in doc_chunks:
        s = type_stats.setdefault(doc.doc_type, {"docs": 0, "chunks": 0})
        s["docs"] += 1
        s["chunks"] += len(chunks)

    print(f"\n  청킹 결과 요약:")
    print(f"  {'doc_type':<15} {'문서 수':>6} {'청크 수':>8}")
    print(f"  {'-'*35}")
    for dt, stat in sorted(type_stats.items()):
        print(f"  {dt:<15} {stat['docs']:>6} {stat['chunks']:>8}")
    print(f"  {'-'*35}")
    print(f"  {'합계':<15} {len(docs):>6} {total_chunks:>8}")

    if args.dry_run:
        print("\n[dry-run 완료] --apply 없이 청킹만 수행했습니다.")
        print(f"  총 문서: {len(docs)}, 총 청크: {total_chunks}")
        _print_sample_chunks(doc_chunks)
        return 0

    # --- Supabase 클라이언트 생성 ---
    print("\n[3/4] Supabase 클라이언트 초기화")
    try:
        from supabase import create_client
    except ImportError as exc:
        print(
            "[오류] supabase 패키지가 필요합니다: pip install supabase",
            file=sys.stderr,
        )
        return 1

    sb = create_client(supabase_url, supabase_key)
    print("  클라이언트 생성 완료")

    # --- 임베딩 + 업서트 ---
    print(f"\n[4/4] 임베딩 (bge-m3) + DB 업서트 (batch_size={args.batch_size})")

    progress = _load_progress()
    stats = {
        "docs_success": 0,
        "docs_failed": 0,
        "chunks_success": 0,
        "embed_success": 0,
        "embed_failed": 0,
    }
    failed_docs: list[str] = []

    for doc, chunks in tqdm(doc_chunks, desc="업서트"):
        doc_id = doc.doc_id

        # 이미 처리된 doc_id 스킵
        if progress.get(doc_id) == "done":
            print(f"  [스킵] {doc_id} (이미 완료)")
            stats["docs_success"] += 1
            stats["chunks_success"] += len(chunks)
            continue

        try:
            # 배치 단위 임베딩
            all_embeddings: list[list[float]] = []
            for batch_start in range(0, len(chunks), args.batch_size):
                batch_texts = chunks[batch_start : batch_start + args.batch_size]
                batch_embs = embed_batch_sync(batch_texts, ollama_url)
                all_embeddings.extend(batch_embs)
                time.sleep(0.05)  # 과부하 방지

            # 청크 업서트
            chunk_ids = upsert_chunks(sb, doc, chunks)
            if len(chunk_ids) != len(chunks):
                raise RuntimeError(
                    f"청크 업서트 수 불일치: 기대={len(chunks)}, 실제={len(chunk_ids)}"
                )

            # 임베딩 업서트
            embed_count = upsert_embeddings(sb, chunk_ids, all_embeddings)

            stats["docs_success"] += 1
            stats["chunks_success"] += len(chunk_ids)
            stats["embed_success"] += embed_count

            progress[doc_id] = "done"
            _save_progress(progress)

        except Exception as exc:
            print(f"\n  [실패] {doc_id}: {exc}", file=sys.stderr)
            stats["docs_failed"] += 1
            stats["embed_failed"] += len(chunks)
            failed_docs.append(doc_id)
            progress[doc_id] = f"failed: {exc}"
            _save_progress(progress)

    # --- 최종 결과 출력 ---
    print("\n" + "=" * 50)
    print("[시드 완료]")
    print(f"  문서 성공: {stats['docs_success']}")
    print(f"  문서 실패: {stats['docs_failed']}")
    print(f"  청크 업서트: {stats['chunks_success']}")
    print(f"  임베딩 업서트: {stats['embed_success']}")
    if failed_docs:
        print(f"  실패 문서: {', '.join(failed_docs)}")
    print(f"  진행 기록: {PROGRESS_FILE}")
    print("=" * 50)

    return 1 if stats["docs_failed"] > 0 else 0


def _print_sample_chunks(
    doc_chunks: list[tuple[Document, list[str]]],
    max_docs: int = 3,
    max_chunks_per_doc: int = 2,
) -> None:
    """dry-run 시 샘플 청크 출력."""
    print("\n  === 샘플 청크 (dry-run 미리보기) ===")
    for doc, chunks in doc_chunks[:max_docs]:
        print(f"\n  [문서] {doc.doc_id} | {doc.title}")
        print(f"  청크 수: {len(chunks)}")
        for i, chunk in enumerate(chunks[:max_chunks_per_doc]):
            preview = chunk[:120].replace("\n", " ")
            print(f"    청크[{i}] ({len(chunk)}자): {preview}...")


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="청킹만 수행, 임베딩·DB 업서트 없음 (기본값)",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="실제 Ollama 임베딩 + Supabase 업서트 실행",
    )

    parser.add_argument(
        "--source",
        default="data/demo_documents/seed_documents.json",
        help="시드 JSON 경로 (repo 루트 기준, 기본: data/demo_documents/seed_documents.json)",
    )
    parser.add_argument(
        "--ollama-url",
        default=None,
        help="Ollama 서버 URL (기본: http://localhost:11434 또는 OLLAMA_BASE_URL 환경변수)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="임베딩 배치 크기 (기본: 16)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="처리할 최대 문서 수 (기본: 전체)",
    )

    args = parser.parse_args()

    # --apply 지정 시 dry_run=False
    if args.apply:
        args.dry_run = False

    return args


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    raise SystemExit(seed_main(parse_args()))
