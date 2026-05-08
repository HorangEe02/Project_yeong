"""기능 A 검색 파이프라인 통합 테스트

Phase 6 테스트 체크리스트 10개 시나리오.
Ollama 서버가 실행 중이어야 벡터 검색이 정상 동작한다.
BM25 검색과 규칙 기반 메타데이터 추출은 Ollama 없이도 테스트 가능하다.
"""

import asyncio
import json
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from features.search.metadata_extractor import rule_based_extract
from features.search.summarizer import format_results_for_display
from features.search.searcher import SearchResult


# ===== 메타데이터 추출 테스트 (Ollama 불필요) =====

def test_metadata_extraction():
    """규칙 기반 메타데이터 추출 테스트"""
    print("=" * 60)
    print("📋 메타데이터 추출 테스트")
    print("=" * 60)

    test_cases = [
        {
            "query": "EMP 워터펌프 8D 보고서 찾아줘",
            "expected_part": "EMP 워터펌프",
            "expected_type": "8D Report",
        },
        {
            "query": "지난 분기 현대차 클레임 문서",
            "expected_part": None,
            "expected_type": "8D Report",
            "expected_customer": "현대차",
        },
        {
            "query": "CCH 냉난방장치 설계변경 관련 문서 검색해줘",
            "expected_part": "CCH 냉난방장치",
            "expected_type": "ECN",
        },
        {
            "query": "2026년 PPAP 문서 보여줘",
            "expected_type": "PPAP",
            "expected_date_from": "2026-01-01",
        },
        {
            "query": "기아에서 온 클레임 문서",
            "expected_type": "8D Report",
            "expected_customer": "기아",
        },
        {
            "query": "B-Pillar 용접 관련 회의록",
            "expected_part": "B-Pillar",
            "expected_type": "Meeting Note",
        },
        {
            "query": "OBC 충전장치 관련 이메일",
            "expected_part": "OBC 충전장치",
            "expected_type": "Email",
        },
    ]

    passed = 0
    total = len(test_cases)

    for tc in test_cases:
        meta = rule_based_extract(tc["query"])
        ok = True

        if "expected_part" in tc and meta.part_name != tc["expected_part"]:
            ok = False
        if "expected_type" in tc and meta.doc_type != tc["expected_type"]:
            ok = False
        if "expected_customer" in tc and meta.customer != tc["expected_customer"]:
            ok = False
        if "expected_date_from" in tc and meta.date_from != tc["expected_date_from"]:
            ok = False

        status = "✅" if ok else "❌"
        if ok:
            passed += 1
        print(f"  {status} '{tc['query']}'")
        print(f"      → 부품={meta.part_name}, 유형={meta.doc_type}, "
              f"고객={meta.customer}, 기간={meta.date_from}~{meta.date_to}")

    print(f"\n  결과: {passed}/{total} 통과")
    return passed == total


# ===== 검색 결과 포맷팅 테스트 (Ollama 불필요) =====

def test_result_formatting():
    """검색 결과 포맷팅 테스트"""
    print("\n" + "=" * 60)
    print("📋 검색 결과 포맷팅 테스트")
    print("=" * 60)

    # 가짜 검색 결과
    mock_results = [
        SearchResult(
            doc_id="8D-2025-001",
            title="EMP 워터펌프 누수 클레임 대응",
            doc_type="8D Report",
            part_name="EMP 워터펌프",
            content="EMP 워터펌프 하우징-커버 접합부 실링 불량으로 인한 냉각수 누수 클레임",
            score=0.85,
            metadata={"created_date": "2025-10-15"},
        ),
        SearchResult(
            doc_id="ECN-2025-001",
            title="EMP 워터펌프 실링 소재 변경",
            doc_type="ECN",
            part_name="EMP 워터펌프",
            content="실링 소재를 NBR에서 EPDM으로 변경하여 내구성 향상",
            score=0.72,
            metadata={"created_date": "2025-10-25"},
        ),
    ]

    formatted = format_results_for_display("EMP 워터펌프 누수", mock_results)
    print(formatted)

    # 빈 결과 테스트
    empty = format_results_for_display("항공기 엔진", [])
    assert "검색 결과가 없습니다" in empty
    print("\n  ✅ 빈 결과 메시지 정상")
    print("\n  ✅ 포맷팅 테스트 통과")
    return True


# ===== 메인 =====

def main():
    print("\n🏭 AJIN AI Assistant — 기능 A 검색 테스트\n")

    all_passed = True
    all_passed &= test_metadata_extraction()
    all_passed &= test_result_formatting()

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 모든 기본 테스트 통과!")
    else:
        print("⚠️ 일부 테스트 실패. 위 결과를 확인하세요.")
    print("=" * 60)

    print("\n💡 Ollama 서버가 실행 중이면 아래 명령으로 전체 검색 테스트를 할 수 있습니다:")
    print("   python -c \"from features.search.indexer import run_indexing; run_indexing()\"")
    print("   → 인덱싱 후 벡터 검색 + BM25 하이브리드 검색 테스트 가능")


if __name__ == "__main__":
    main()
