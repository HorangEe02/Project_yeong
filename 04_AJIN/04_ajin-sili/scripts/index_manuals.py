"""
설비 매뉴얼 인덱싱 + 에러코드 시드
사용법: python -m scripts.index_manuals
"""
from pathlib import Path
from features.equipment.manual_rag import index_manuals
from features.equipment.error_code_db import init_error_db, bulk_import_from_json, lookup_error, get_error_stats

if __name__ == "__main__":
    print("=" * 50)
    print("  기능 F -- 설비 매뉴얼 인덱싱")
    print("=" * 50)

    # 1. 매뉴얼 ChromaDB 인덱싱
    print("\n[1] 매뉴얼 인덱싱...")
    count = index_manuals()
    print(f"  {count}건 청크 인덱싱 완료")

    # 2. 에러코드 시드
    print("\n[2] 에러코드 시드...")
    init_error_db()
    error_files = list(Path("data/equipment/error_codes").glob("*.json"))
    total_errors = 0
    for ef in error_files:
        n = bulk_import_from_json(str(ef))
        print(f"  {ef.name}: {n}건")
        total_errors += n
    print(f"  총 {total_errors}건 에러코드 등록")

    # 3. 통계
    stats = get_error_stats()
    print(f"\n[3] 에러코드 통계:")
    print(f"  총: {stats['total']}건")
    for eq_type, cnt in stats["by_type"].items():
        print(f"  - {eq_type}: {cnt}건")
    for sev, cnt in stats["by_severity"].items():
        print(f"  - {sev}: {cnt}건")

    # 4. 검증
    print("\n[4] 검증...")
    results = lookup_error("E-001")
    for r in results:
        print(f"  {r['error_code']} | {r['error_name']} | {r['severity']} | {r['equipment_type']}")

    print("\n Phase 1 인덱싱 완료")
