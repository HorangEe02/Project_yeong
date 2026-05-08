"""기능 C 온보딩 챗봇 통합 테스트

Ollama 서버가 실행 중이어야 LLM 기반 답변 생성이 정상 동작한다.
용어 사전 매칭, 부서별 라우팅, 대화 관리는 Ollama 없이도 테스트 가능하다.
"""

import json
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from features.onboarding.glossary_matcher import GlossaryMatcher
from features.onboarding.department_router import DepartmentRouter, DEPARTMENT_PROFILES
from features.onboarding.conversation_manager import ConversationManager, ConversationSession


# ===== 1. 용어 사전 데이터 검증 =====

def test_glossary_data():
    """용어 사전 JSON 파일 검증"""
    print("=" * 60)
    print("📋 용어 사전 데이터 검증")
    print("=" * 60)

    glossary_dir = PROJECT_ROOT / "data" / "knowledge_base" / "glossary"
    expected_files = [
        "quality_terms.json",
        "process_terms.json",
        "part_terms.json",
        "abbreviation_terms.json",
        "practice_terms.json",
    ]

    total = 0
    all_ok = True

    for fname in expected_files:
        fpath = glossary_dir / fname
        if not fpath.exists():
            print(f"  ❌ 누락: {fname}")
            all_ok = False
            continue

        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)

        terms = data.get("terms", [])
        ok = True

        for t in terms:
            if len(t.get("ajin_context", "")) < 30:
                print(f"  ⚠ ajin_context 짧음: {t['term']} ({len(t.get('ajin_context', ''))}자)")
                ok = False
            if len(t.get("related_terms", [])) < 2:
                print(f"  ⚠ related_terms 부족: {t['term']}")

        total += len(terms)
        status = "✅" if ok else "⚠️"
        print(f"  {status} {fname}: {len(terms)}개")
        if not ok:
            all_ok = False

    print(f"\n  총 용어: {total}개 (목표: 85개)")
    result = total >= 80  # 약간의 여유
    if result:
        print("  ✅ 용어 수 충족")
    else:
        print("  ❌ 용어 수 부족")
    return result


# ===== 2. 용어 사전 매칭 테스트 =====

def test_glossary_matcher():
    """용어 사전 정확 매칭 테스트"""
    print("\n" + "=" * 60)
    print("📋 용어 사전 매칭 테스트")
    print("=" * 60)

    glossary_dir = PROJECT_ROOT / "data" / "knowledge_base" / "glossary"
    matcher = GlossaryMatcher(glossary_dir)

    print(f"  로드된 용어 수: {matcher.total_terms}")

    test_cases = [
        ("PPAP가 뭐야?", True, "PPAP"),
        ("Cpk 기준이 어떻게 돼?", True, "Cpk"),
        ("스팟용접 조건 알려줘", True, "스팟용접"),
        ("핫스탬핑이 뭔가요?", True, "핫스탬핑"),
        ("SPC에서 관리도란?", True, None),  # SPC 또는 관리도
        ("점심 뭐 먹지?", False, None),
        ("오늘 날씨 어때?", False, None),
        ("EMP워터펌프 설명해줘", True, None),
        ("FMEA 작성 방법", True, "FMEA"),
        ("너깃 직경 기준", True, "너깃"),
    ]

    passed = 0
    total = len(test_cases)

    for query, should_match, expected_term in test_cases:
        result = matcher.match(query)
        matched = result is not None
        ok = matched == should_match

        if ok and expected_term and result:
            # 특정 용어 매칭 확인 (선택적)
            ok = expected_term.lower() in result.term.lower() or expected_term in result.term

        status = "✅" if ok else "❌"
        if ok:
            passed += 1
        term_info = f"→ {result.term}" if result else "→ None"
        print(f"  {status} '{query}' {term_info}")

    print(f"\n  결과: {passed}/{total} 통과")
    return passed >= total - 2  # 2개까지 허용


# ===== 3. 부서별 라우팅 테스트 =====

def test_department_router():
    """부서별 맞춤 응답 라우터 테스트"""
    print("\n" + "=" * 60)
    print("📋 부서별 라우팅 테스트")
    print("=" * 60)

    router = DepartmentRouter()

    all_ok = True
    for dept in ["품질보증팀", "생산기술팀", "영업팀", "연구소"]:
        profile = router.get_profile(dept)
        if not profile:
            print(f"  ❌ 프로필 없음: {dept}")
            all_ok = False
            continue

        perspective = router.get_perspective(dept)
        context = router.get_department_context(dept)

        assert len(profile.core_responsibilities) >= 3
        assert len(perspective) > 20
        assert dept in context

        print(f"  ✅ {dept}: 업무 {len(profile.core_responsibilities)}개, "
              f"시스템 {len(profile.key_systems)}개")

    # 미등록 부서 테스트
    unknown = router.get_profile("총무팀")
    assert unknown is None
    print("  ✅ 미등록 부서(총무팀) → None 반환")

    print("\n  ✅ 부서별 라우팅 테스트 통과")
    return all_ok


# ===== 4. 대화 관리 테스트 =====

def test_conversation_manager():
    """멀티턴 대화 관리 테스트"""
    print("\n" + "=" * 60)
    print("📋 대화 관리 테스트")
    print("=" * 60)

    manager = ConversationManager()

    # 세션 생성
    session = manager.get_or_create_session("test-001", "품질보증팀")
    assert session.session_id == "test-001"
    assert session.department == "품질보증팀"
    print("  ✅ 세션 생성 정상")

    # 대화 추가
    session.add_turn("user", "PPAP가 뭐야?")
    session.add_turn("assistant", "PPAP는 생산부품승인절차입니다.")
    session.add_turn("user", "Cpk랑 뭐가 달라?")
    session.add_turn("assistant", "Cpk는 공정능력지수입니다.")
    assert len(session.history) == 4
    print("  ✅ 대화 이력 관리 정상")

    # 최근 이력 가져오기
    recent = session.get_recent_history(max_turns=2)
    assert len(recent) == 2
    print("  ✅ 최근 이력 제한 정상")

    # 용어 중복 방지
    session.record_asked_term("PPAP")
    session.record_suggested_terms(["APQP", "FMEA"])
    assert not session.should_suggest("PPAP")   # 이미 질문함
    assert not session.should_suggest("APQP")   # 이미 추천함
    assert session.should_suggest("SPC")         # 새 용어
    print("  ✅ 용어 중복 방지 정상")

    # FAQ 카운터
    manager.record_question("PPAP가 뭐야?")
    manager.record_question("PPAP가 뭐야?")
    manager.record_question("Cpk 기준?")
    faqs = manager.get_top_faqs(2)
    assert faqs[0][0] == "PPAP가 뭐야"
    assert faqs[0][1] == 2
    print("  ✅ FAQ 카운터 정상")

    print("\n  ✅ 대화 관리 테스트 통과")
    return True


# ===== 5. SOP/가이드 문서 존재 검증 =====

def test_knowledge_documents():
    """SOP/가이드 문서 존재 및 길이 검증"""
    print("\n" + "=" * 60)
    print("📋 SOP/가이드 문서 검증")
    print("=" * 60)

    kb_dir = PROJECT_ROOT / "data" / "knowledge_base"

    expected_files = {
        "sop/ppap_process.md": 800,
        "sop/8d_process.md": 800,
        "sop/ecn_process.md": 800,
        "sop/incoming_inspection.md": 800,
        "sop/press_operation.md": 800,
        "sop/welding_operation.md": 800,
        "department_guides/quality_team.md": 1000,
        "department_guides/production_tech.md": 1000,
        "department_guides/sales_team.md": 1000,
        "collaboration/quality_sales.md": 800,
        "collaboration/quality_production.md": 800,
        "collaboration/rnd_quality.md": 800,
    }

    all_ok = True
    for filepath, min_chars in expected_files.items():
        fpath = kb_dir / filepath
        if not fpath.exists():
            print(f"  ❌ 누락: {filepath}")
            all_ok = False
            continue

        content = fpath.read_text(encoding="utf-8")
        char_count = len(content)
        if char_count < min_chars:
            print(f"  ⚠ 내용 부족: {filepath} ({char_count}자 < {min_chars}자)")
            all_ok = False
        else:
            print(f"  ✅ {filepath}: {char_count}자")

    if all_ok:
        print("\n  ✅ 모든 문서 검증 통과")
    return all_ok


# ===== 6. 시스템 프롬프트 검증 =====

def test_system_prompt():
    """시스템 프롬프트 파일 검증"""
    print("\n" + "=" * 60)
    print("📋 시스템 프롬프트 검증")
    print("=" * 60)

    prompt_path = PROJECT_ROOT / "features" / "onboarding" / "prompts" / "onboarding_system.txt"
    assert prompt_path.exists(), "시스템 프롬프트 파일 없음"

    content = prompt_path.read_text(encoding="utf-8")
    required_vars = [
        "{department_context}",
        "{glossary_info}",
        "{rag_context}",
        "{conversation_history}",
        "{user_query}",
    ]

    all_ok = True
    for var in required_vars:
        if var in content:
            print(f"  ✅ 변수 포함: {var}")
        else:
            print(f"  ❌ 변수 누락: {var}")
            all_ok = False

    print(f"  프롬프트 길이: {len(content)}자")
    if all_ok:
        print("\n  ✅ 시스템 프롬프트 검증 통과")
    return all_ok


# ===== 메인 =====

def main():
    print("\n🏭 AJIN AI Assistant — 기능 C 온보딩 챗봇 테스트\n")

    all_passed = True
    all_passed &= test_glossary_data()
    all_passed &= test_glossary_matcher()
    all_passed &= test_department_router()
    all_passed &= test_conversation_manager()
    all_passed &= test_knowledge_documents()
    all_passed &= test_system_prompt()

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 모든 기본 테스트 통과!")
    else:
        print("⚠️ 일부 테스트 실패. 위 결과를 확인하세요.")
    print("=" * 60)

    print("\n💡 Ollama 서버가 실행 중이면 전체 온보딩 챗봇 테스트를 할 수 있습니다:")
    print("   from features.onboarding import OnboardingPipeline")
    print("   pipeline = OnboardingPipeline()")
    print("   result = await pipeline.chat('PPAP가 뭐야?', 'session-1', '품질관리팀')")


if __name__ == "__main__":
    main()
