"""기존 ChromaDB 인덱스를 Gemini text-embedding-004 로 재구축 (1회성).

⚠️ 차원 호환성:
  - 현재 인덱스: bge-m3 (1024 dims) — Ollama 임베딩으로 빌드
  - 신규 인덱스: text-embedding-004 (768 dims) — Gemini API
  - **차원 다르므로 기존 컬렉션 삭제 후 재생성 필수**.

전제:
  - GEMINI_API_KEY 환경변수 설정
  - data/documents/ , data/knowledge_base/ 등 원문 자산 보유

실행:
  python scripts/reembed_to_gemini.py --dry-run            # 통계만
  python scripts/reembed_to_gemini.py                      # 실제 재인덱싱
  python scripts/reembed_to_gemini.py --collection glossary  # 단일 컬렉션
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
VECTORSTORE_DIR = PROJECT_ROOT / "vectorstore"


def list_collections(persist_dir: Path) -> list[str]:
    """vectorstore/ 하위의 chroma 컬렉션 디렉토리 목록."""
    if not persist_dir.exists():
        return []
    return sorted([p.name for p in persist_dir.iterdir() if p.is_dir() and not p.name.startswith(".")])


def reembed_collection(name: str, dry_run: bool = False):
    """단일 컬렉션 재인덱싱 — 기존 chunk 메타데이터 보존, 임베딩만 새로 계산."""
    sys.path.insert(0, str(PROJECT_ROOT))
    os.environ["EMBEDDING_BACKEND"] = "gemini"

    from langchain_chroma import Chroma  # type: ignore
    from core.embedding_client import get_embeddings, GeminiEmbeddings

    persist_dir = VECTORSTORE_DIR / name
    if not persist_dir.exists():
        print(f"⚠️ 컬렉션 없음: {persist_dir}")
        return

    print(f"\n=== 컬렉션: {name} ===")

    # 1. 기존 chunks 추출 (Ollama 임베딩으로 로드 시 차원 mismatch 발생할 수 있어
    #    metadata/text 만 dump 한 뒤 새 컬렉션으로 다시 add)
    print("  기존 chunks 덤프 중...")
    try:
        old_db = Chroma(collection_name=name, persist_directory=str(persist_dir))
        col = old_db._collection
        existing = col.get(include=["documents", "metadatas"])
        n = len(existing.get("ids") or [])
        print(f"  → {n} chunks")
    except Exception as e:
        print(f"  ✗ 기존 인덱스 읽기 실패: {e}")
        return

    if dry_run:
        print(f"  --dry-run: 재인덱싱 스킵")
        return

    if n == 0:
        print(f"  컬렉션 비어 있음 — 스킵")
        return

    # 2. 기존 컬렉션 삭제 (차원 mismatch 방지)
    print("  기존 컬렉션 삭제...")
    import shutil
    shutil.rmtree(persist_dir)

    # 3. 새 컬렉션 (Gemini 임베딩) 생성
    print("  Gemini 임베딩으로 재구축...")
    new_db = Chroma(
        collection_name=name,
        persist_directory=str(persist_dir),
        embedding_function=get_embeddings(),
    )

    docs = existing["documents"]
    metas = existing["metadatas"]

    # batch 단위 add (Gemini API 호출 분산)
    BATCH = 50
    for i in range(0, len(docs), BATCH):
        new_db.add_texts(texts=docs[i:i+BATCH], metadatas=metas[i:i+BATCH])
        print(f"    {i+BATCH}/{len(docs)}...")

    print(f"  ✓ {len(docs)} chunks 재인덱싱 완료")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--collection", help="단일 컬렉션 (생략 시 전체)")
    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        print("✗ GEMINI_API_KEY 환경변수가 필요합니다.")
        sys.exit(1)

    if args.collection:
        reembed_collection(args.collection, dry_run=args.dry_run)
    else:
        cols = list_collections(VECTORSTORE_DIR)
        print(f"발견된 컬렉션: {cols}")
        for name in cols:
            reembed_collection(name, dry_run=args.dry_run)

    print("\n완료.")


if __name__ == "__main__":
    main()
