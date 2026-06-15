"""기능 A 검색 파이프라인 통합 테스트

Phase 6 테스트 체크리스트 10개 시나리오.
Ollama 서버가 실행 중이어야 벡터 검색이 정상 동작한다.
BM25 검색과 규칙 기반 메타데이터 추출은 Ollama 없이도 테스트 가능하다.
"""

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.dependencies import get_current_user
from backend.routers import search as search_router
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
    assert passed == total


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


# ===== API 가시성/감사 로그 테스트 =====


def _user(role_level: int = 1, department: str = "품질보증팀", role: str = "EMPLOYEE"):
    """Create a minimal authenticated user for router tests."""
    return SimpleNamespace(
        user_id=1,
        employee_id="E001",
        name="tester",
        username="tester",
        department=department,
        division="품질본부",
        position="사원",
        role=role,
        role_level=role_level,
    )


def _search_client(user=None) -> TestClient:
    """Create a router-only search API client."""
    app = FastAPI()
    app.include_router(search_router.router, prefix="/api")
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


class _FakeSearcher:
    """Fake searcher returning same-department and cross-department results."""

    def search(self, **_kwargs):
        """Return two deterministic search results."""
        return [
            SimpleNamespace(
                doc_id="DOC-SAME",
                title="same dept",
                doc_type="8D Report",
                part_name="EWP",
                content="same",
                score=0.9,
                metadata={
                    "department": "품질보증팀",
                    "file_path": "/internal/same.pdf",
                    "data_class": "real",
                    "source_system": "erp_dms",
                    "source_label": "DMS",
                },
            ),
            SimpleNamespace(
                doc_id="DOC-OTHER",
                title="other dept",
                doc_type="ECN",
                part_name="CCH",
                content="other",
                score=0.7,
                metadata={
                    "department": "생산기술팀",
                    "file_path": "/internal/other.pdf",
                    "data_class": "synthetic",
                    "source_system": "seed_docs",
                    "source_label": "DEMO",
                },
            ),
        ]


def test_search_documents_masks_cross_department_metadata_and_audits(monkeypatch) -> None:
    """Search documents should hide internal paths for cross-department users."""
    audit_rows: list[dict] = []
    monkeypatch.setattr(search_router, "log_api_access", lambda **kwargs: audit_rows.append(kwargs))
    client = _search_client(_user(role_level=1, department="품질보증팀"))
    client.app.dependency_overrides[search_router.get_searcher] = lambda: _FakeSearcher()

    response = client.post("/api/search/documents", json={"query": "민감 검색어", "k": 3})

    assert response.status_code == 200
    payload = response.json()
    by_id = {item["doc_id"]: item for item in payload["results"]}
    assert by_id["DOC-SAME"]["metadata"]["visibility"] == "full"
    assert by_id["DOC-SAME"]["metadata"]["file_path"] == "/internal/same.pdf"
    assert by_id["DOC-OTHER"]["metadata"]["visibility"] == "partial"
    assert "file_path" not in by_id["DOC-OTHER"]["metadata"]
    assert by_id["DOC-OTHER"]["metadata"]["data_class"] == "synthetic"
    assert audit_rows[-1]["endpoint"] == "/api/search/documents"
    assert audit_rows[-1]["result_count"] == 2
    assert "민감 검색어" not in audit_rows[-1]["detail"]
    assert "query_len=6" in audit_rows[-1]["detail"]


def test_search_documents_l4_can_see_cross_department_metadata(monkeypatch) -> None:
    """L4+ users can see full metadata across departments."""
    monkeypatch.setattr(search_router, "log_api_access", lambda **_kwargs: None)
    client = _search_client(_user(role_level=4, department="품질보증팀", role="HR_ADMIN"))
    client.app.dependency_overrides[search_router.get_searcher] = lambda: _FakeSearcher()

    response = client.post("/api/search/documents", json={"query": "품질", "k": 3})

    assert response.status_code == 200
    by_id = {item["doc_id"]: item for item in response.json()["results"]}
    assert by_id["DOC-OTHER"]["metadata"]["visibility"] == "full"
    assert by_id["DOC-OTHER"]["metadata"]["file_path"] == "/internal/other.pdf"


def test_search_drawings_preserves_lineage_and_masks_paths(monkeypatch) -> None:
    """Drawing search should preserve lineage while masking cross-department file paths."""
    audit_rows: list[dict] = []
    monkeypatch.setattr(search_router, "log_api_access", lambda **kwargs: audit_rows.append(kwargs))

    from features.equipment import drawing_search

    monkeypatch.setattr(drawing_search, "search_by_number", lambda _q: [])
    monkeypatch.setattr(
        drawing_search,
        "search_by_keyword",
        lambda *_args, **_kwargs: [
            {
                "id": 7,
                "drawing_number": "DWG-7",
                "part_number": "P-7",
                "part_name": "part",
                "department": "생산기술팀",
                "file_path": "drawings/secret.pdf",
                "bom_info": "{\"secret\": true}",
                "data_class": "real",
                "source_system": "drawing_db",
                "source_label": "DRAWING",
            }
        ],
    )
    client = _search_client(_user(role_level=1, department="품질보증팀"))

    response = client.get("/api/search/drawings", params={"q": "DWG"})

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["visibility"] == "partial"
    assert item["file_path"] == ""
    assert item["bom_info"] == ""
    assert item["data_class"] == "real"
    assert item["source_system"] == "drawing_db"
    assert audit_rows[-1]["endpoint"] == "/api/search/drawings"
    assert "DWG" not in audit_rows[-1]["detail"]


def test_vision_query_disabled_is_audited_without_raw_text(monkeypatch) -> None:
    """Vision query disabled path should still create a safe audit row."""
    audit_rows: list[dict] = []
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(search_router, "log_api_access", lambda **kwargs: audit_rows.append(kwargs))
    client = _search_client(_user())
    client.app.dependency_overrides[search_router.get_searcher] = lambda: None

    response = client.post(
        "/api/search/vision-query",
        files={"image": ("drawing.png", b"image", "image/png")},
    )

    assert response.status_code == 403
    assert audit_rows[-1]["endpoint"] == "/api/search/vision-query"
    assert audit_rows[-1]["status_code"] == 403
    assert audit_rows[-1]["result_count"] == 0


# ===== 메인 =====

def main():
    print("\n🏭 AJIN AI Assistant — 기능 A 검색 테스트\n")

    all_passed = True
    test_metadata_extraction()
    test_result_formatting()

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
