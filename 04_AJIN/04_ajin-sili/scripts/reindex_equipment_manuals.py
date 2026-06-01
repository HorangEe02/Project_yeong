"""
장비 매뉴얼 ChromaDB 재인덱싱 스크립트 (v3.4)

data/equipment/manuals/ 의 MD/TXT/PDF 파일을 ChromaDB에 인덱싱한다.
Ollama 임베딩 서버(BGE-M3)가 실행 중이어야 한다.

사용법:
    python scripts/reindex_equipment_manuals.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    manuals_dir = Path("data/equipment/manuals")

    if not manuals_dir.exists():
        print(f"[오류] 매뉴얼 디렉토리가 없습니다: {manuals_dir}")
        return

    files = list(manuals_dir.glob("*.md")) + list(manuals_dir.glob("*.txt")) + list(manuals_dir.glob("*.pdf"))
    print(f"장비 매뉴얼 인덱싱 시작... ({len(files)}건)")
    for f in files:
        print(f"  - {f.name} ({f.stat().st_size / 1024:.1f} KB)")

    try:
        from features.equipment.manual_rag import index_manuals
        count = index_manuals()
        print(f"\n인덱싱 완료: {count}건 청크 생성")
    except Exception as e:
        print(f"\n[오류] 인덱싱 실패: {e}")
        print("Ollama 서버가 실행 중인지 확인하세요: ollama serve")


if __name__ == "__main__":
    main()
