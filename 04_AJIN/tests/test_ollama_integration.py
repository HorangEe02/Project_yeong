"""실제 Ollama 연동 통합 테스트

모든 4개 기능(A~D)에 대해 실제 LLM 호출을 검증한다.
Ollama 서버가 실행 중이고, 모델이 설치되어 있어야 한다.
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import LLM_MODEL, EMBEDDING_MODEL, OLLAMA_BASE_URL


# ===== 0. Ollama 서버 연결 확인 =====

def test_ollama_connection():
    """Ollama 서버 연결 및 모델 확인"""
    print("=" * 60)
    print("📋 Ollama 서버 연결 테스트")
    print("=" * 60)

    import httpx

    # 서버 연결
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        assert resp.status_code == 200
        models = [m["name"] for m in resp.json().get("models", [])]
        print(f"  ✅ Ollama 서버 연결 성공: {OLLAMA_BASE_URL}")
        print(f"     설치된 모델: {len(models)}개")
    except Exception as e:
        print(f"  ❌ Ollama 서버 연결 실패: {e}")
        return False

    # LLM 모델 확인
    llm_found = any(LLM_MODEL in m for m in models)
    embed_found = any(EMBEDDING_MODEL in m for m in models)

    if llm_found:
        print(f"  ✅ LLM 모델 확인: {LLM_MODEL}")
    else:
        print(f"  ❌ LLM 모델 없음: {LLM_MODEL}")
        print(f"     사용 가능: {models}")

    if embed_found:
        print(f"  ✅ 임베딩 모델 확인: {EMBEDDING_MODEL}")
    else:
        print(f"  ❌ 임베딩 모델 없음: {EMBEDDING_MODEL}")

    return llm_found and embed_found


# ===== 1. 기능 A: 하이브리드 검색 =====

def test_feature_a_search():
    """기능 A: 실제 벡터 + BM25 하이브리드 검색"""
    print("\n" + "=" * 60)
    print("📋 기능 A: 하이브리드 검색 테스트")
    print("=" * 60)

    from features.search.searcher import HybridSearcher

    try:
        searcher = HybridSearcher()
        print(f"  ✅ HybridSearcher 초기화 성공")
    except Exception as e:
        print(f"  ❌ HybridSearcher 초기화 실패: {e}")
        return False

    test_queries = [
        ("EMP 워터펌프 누수 클레임", "8D Report"),
        ("EPDM 실링 소재 변경", "ECN"),
        ("현대차 품질 이메일", None),
    ]

    all_ok = True
    for query, expected_type in test_queries:
        try:
            results = searcher.search(query, k=3)
            if results:
                top = results[0]
                print(f"  ✅ '{query}'")
                print(f"     → {len(results)}건, Top: {top.doc_id} ({top.doc_type}), "
                      f"Score: {top.score:.3f}")
                if expected_type and top.doc_type != expected_type:
                    print(f"     ⚠ 기대 유형: {expected_type}, 실제: {top.doc_type}")
            else:
                print(f"  ⚠ '{query}' → 결과 없음")
        except Exception as e:
            print(f"  ❌ '{query}' → 오류: {e}")
            all_ok = False

    return all_ok


# ===== 2. 기능 B: LLM 초안 생성 =====

def test_feature_b_draft():
    """기능 B: 실제 LLM을 사용한 초안 생성"""
    print("\n" + "=" * 60)
    print("📋 기능 B: LLM 초안 생성 테스트")
    print("=" * 60)

    from features.draft.classifier import rule_based_classify
    from features.draft.generator import DraftGenerator
    from features.draft.template_renderer import TemplateRenderer

    prompts_dir = PROJECT_ROOT / "features" / "draft" / "prompts"
    templates_dir = PROJECT_ROOT / "data" / "templates"

    generator = DraftGenerator(searcher=None, prompts_dir=prompts_dir)
    renderer = TemplateRenderer(templates_dir)

    test_query = "현대차 품질팀에 EMP 워터펌프 누수 클레임 대응 보고 이메일 작성해줘"

    # 분류
    request = rule_based_classify(test_query)
    print(f"  분류 결과: {request.doc_type.value}, 부품={request.part_name}")

    # LLM으로 변수 생성
    try:
        template_vars = asyncio.run(generator.generate(request, test_query))
        print(f"  ✅ LLM 변수 생성 성공: {len(template_vars)}개 변수")
        for key in list(template_vars.keys())[:5]:
            val = str(template_vars[key])[:60]
            print(f"     {key}: {val}...")
    except Exception as e:
        print(f"  ❌ LLM 변수 생성 실패: {e}")
        return False

    # 템플릿 렌더링
    try:
        rendered = renderer.render(request, template_vars)
        assert len(rendered) > 100
        print(f"  ✅ 초안 렌더링 성공: {len(rendered)}자")
        # 첫 3줄 미리보기
        preview = "\n".join(rendered.split("\n")[:3])
        print(f"     미리보기: {preview}")
    except Exception as e:
        print(f"  ❌ 렌더링 실패: {e}")
        return False

    return True


# ===== 3. 기능 C: 온보딩 챗봇 =====

def test_feature_c_onboarding():
    """기능 C: 실제 LLM을 사용한 온보딩 챗봇"""
    print("\n" + "=" * 60)
    print("📋 기능 C: 온보딩 챗봇 테스트")
    print("=" * 60)

    from features.onboarding.onboarding_bot import OnboardingBot

    glossary_dir = PROJECT_ROOT / "data" / "knowledge_base" / "glossary"
    bot = OnboardingBot(glossary_dir=glossary_dir)

    test_queries = [
        ("PPAP가 뭐야?", "품질관리팀"),
        ("8D 보고서는 어떻게 작성해?", "품질관리팀"),
        ("Cpk와 Ppk의 차이가 뭐야?", "생산기술팀"),
    ]

    all_ok = True
    for query, dept in test_queries:
        try:
            result = asyncio.run(bot.answer(query, department=dept))
            answer = result["answer"]
            source = result["source"]
            glossary = result.get("glossary_entry")

            assert len(answer) > 50, f"답변이 너무 짧음: {len(answer)}자"
            print(f"  ✅ '{query}'")
            print(f"     → 소스: {source}, 용어매칭: {'있음' if glossary else '없음'}")
            print(f"     → 답변 길이: {len(answer)}자")
            print(f"     → 미리보기: {answer[:80]}...")
        except Exception as e:
            print(f"  ❌ '{query}' → 오류: {e}")
            all_ok = False

    return all_ok


# ===== 4. 기능 D: 규정 준수 분석 =====

def test_feature_d_compliance():
    """기능 D: 실제 LLM을 사용한 규정 준수 분석"""
    print("\n" + "=" * 60)
    print("📋 기능 D: 규정 준수 분석 테스트")
    print("=" * 60)

    from features.compliance.compliance_checker import ComplianceChecker
    from features.compliance.facility_db import FacilityDB
    from features.compliance.crawler import ScenarioLoader

    facility_db = FacilityDB(PROJECT_ROOT / "data" / "facility_db")

    # 시설 DB 로드 확인
    plants = list(facility_db.plants.values())
    chemicals = list(facility_db.chemicals.values())
    print(f"  시설 DB: 공장 {len(plants)}개, 화학물질 {len(chemicals)}개")

    # 규칙 기반 확인
    checker = ComplianceChecker(facility_db=facility_db)

    test_query = "경산 1공장 프레스 라인의 현재 안전거리가 산업안전보건법 개정안의 400mm 기준을 충족하는지 확인해줘"

    try:
        result = checker.check(test_query)
        print(f"  ✅ 규칙 기반 확인 성공")
        print(f"     → 상태: {result.compliance_status}")
        print(f"     → 관련 기준: {result.relevant_standards}")
        if result.answer:
            print(f"     → 미리보기: {result.answer[:120]}...")
    except Exception as e:
        print(f"  ❌ 규칙 기반 확인 실패: {e}")
        return False

    # LLM 기반 상세 분석
    try:
        llm_result = asyncio.run(checker.check_with_llm(test_query))
        assert len(llm_result.answer) > 50, f"LLM 분석 결과가 너무 짧음"
        print(f"  ✅ LLM 규정 준수 분석 성공")
        print(f"     → 소스: {llm_result.source}")
        print(f"     → 답변 길이: {len(llm_result.answer)}자")
        print(f"     → 미리보기: {llm_result.answer[:120]}...")
    except Exception as e:
        print(f"  ❌ LLM 규정 준수 분석 실패: {e}")
        return False

    # 시나리오 영향 분석 (규칙 기반)
    from features.compliance.impact_analyzer import ImpactAnalyzer
    from features.compliance.crawler import ScenarioLoader

    scenarios_dir = PROJECT_ROOT / "data" / "scenarios"
    loader = ScenarioLoader(scenarios_dir)
    analyzer = ImpactAnalyzer(facility_db=facility_db)

    try:
        scenarios = loader.get_all_scenarios()
        if scenarios:
            change = scenarios[0]
            report = analyzer.analyze(change)
            print(f"  ✅ 시나리오 영향 분석 성공: {report.scenario_id}")
            print(f"     → 영향 공장: {report.affected_plants}")
            print(f"     → 영향 공정: {report.affected_processes}")
            print(f"     → 위험 점수: {report.risk_score:.1f}/100")

            # LLM 상세 분석
            llm_report = asyncio.run(analyzer.analyze_with_llm(change))
            if len(llm_report.llm_analysis) > 0:
                print(f"  ✅ LLM 영향 분석 성공: {len(llm_report.llm_analysis)}자")
                print(f"     → 미리보기: {llm_report.llm_analysis[:120]}...")
            else:
                print(f"  ⚠ LLM 영향 분석 응답 비어있음 (thinking 모드 이슈 가능)")
        else:
            print(f"  ⚠ 시나리오 파일 없음 — 건너뜀")
    except Exception as e:
        print(f"  ❌ 시나리오 영향 분석 실패: {e}")
        return False

    return True


# ===== 5. LLM 직접 호출 테스트 =====

def test_llm_direct():
    """LLM 직접 호출 (한국어 응답 품질 확인)"""
    print("\n" + "=" * 60)
    print("📋 LLM 직접 호출 테스트 (qwen3.5:9b)")
    print("=" * 60)

    from core.llm_client import get_llm

    llm = get_llm(temperature=0.3)

    test_prompt = (
        "아진산업은 자동차 부품(실링, 스탬핑 등)을 생산하는 한국 제조 기업입니다. "
        "다음 질문에 한국어로 간결하게 답변해주세요.\n\n"
        "질문: PPAP (Production Part Approval Process)란 무엇이며, "
        "아진산업과 같은 자동차 부품 제조사에서 왜 중요한가요?"
    )

    try:
        response = llm.invoke(test_prompt)
        answer = response.content
        assert len(answer) > 100, f"응답이 너무 짧음: {len(answer)}자"
        print(f"  ✅ LLM 응답 성공: {len(answer)}자")
        print(f"  모델: {LLM_MODEL}")
        print(f"  ---")
        # 미리보기 (최대 300자)
        print(f"  {answer[:300]}...")
        print(f"  ---")
    except Exception as e:
        print(f"  ❌ LLM 호출 실패: {e}")
        return False

    return True


# ===== 메인 =====

def main():
    print("\n" + "=" * 60)
    print("🏭 AJIN AI Assistant — 실제 Ollama 연동 통합 테스트")
    print(f"   LLM: {LLM_MODEL}")
    print(f"   Embedding: {EMBEDDING_MODEL}")
    print(f"   Server: {OLLAMA_BASE_URL}")
    print("=" * 60)

    results = {}

    # 0. 연결 확인
    ok = test_ollama_connection()
    results["0. Ollama 연결"] = ok
    if not ok:
        print("\n❌ Ollama 서버 연결 실패. 테스트를 중단합니다.")
        print("   ollama serve 실행 후 다시 시도하세요.")
        return

    # 5. LLM 직접 호출 (먼저 실행 — 기본 동작 확인)
    results["5. LLM 직접 호출"] = test_llm_direct()

    # 1. 기능 A: 검색
    results["1. 기능 A 검색"] = test_feature_a_search()

    # 2. 기능 B: 초안 생성
    results["2. 기능 B 초안"] = test_feature_b_draft()

    # 3. 기능 C: 온보딩
    results["3. 기능 C 온보딩"] = test_feature_c_onboarding()

    # 4. 기능 D: 규정 준수
    results["4. 기능 D 규정준수"] = test_feature_d_compliance()

    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)

    passed = 0
    total = len(results)
    for name, ok in results.items():
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}  {name}")
        if ok:
            passed += 1

    print(f"\n  결과: {passed}/{total} 통과")
    print("=" * 60)

    if passed == total:
        print("🎉 모든 Ollama 연동 테스트 통과!")
    else:
        print("⚠️ 일부 테스트 실패. 위 결과를 확인하세요.")


if __name__ == "__main__":
    main()
