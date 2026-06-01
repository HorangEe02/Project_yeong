"""
Few-shot RAG 문서 재인덱싱 스크립트 (v3.4)

data/documents/ (36건) + data/templates/ (13건)을 ChromaDB에 재인덱싱한다.
Ollama 임베딩 서버(BGE-M3)가 실행 중이어야 한다.

사용법:
    python scripts/reindex_fewshot_rag.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    print("Few-shot RAG 문서 재인덱싱 시작...")
    print()

    # 1. 문서 파일 확인
    doc_dir = Path("data/documents")
    tmpl_dir = Path("data/templates")

    doc_count = len(list(doc_dir.rglob("*.md"))) + len(list(doc_dir.rglob("*.txt"))) if doc_dir.exists() else 0
    tmpl_count = len(list(tmpl_dir.rglob("*.j2"))) if tmpl_dir.exists() else 0
    print(f"  문서 파일: {doc_count}건 (data/documents/)")
    print(f"  템플릿 파일: {tmpl_count}건 (data/templates/)")

    if doc_count == 0 and tmpl_count == 0:
        print("\n[오류] 인덱싱 대상 파일이 없습니다.")
        return

    # 2. 기존 인덱스 삭제 후 재생성
    try:
        from features.draft.fewshot_rag import index_document_samples
        count = index_document_samples()
        print(f"\n인덱싱 완료: {count}건 청크 생성")
    except Exception as e:
        print(f"\n[오류] 인덱싱 실패: {e}")
        print("Ollama 서버가 실행 중인지 확인하세요: ollama serve")
        print("BGE-M3 모델이 설치되어 있는지 확인하세요: ollama pull bge-m3")


if __name__ == "__main__":
    main()
