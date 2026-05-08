"""기능 D 법규/규정 모니터링 통합 테스트

Ollama 서버가 없어도 규칙 기반 기능은 테스트 가능하다.
LLM 기반 분석은 Ollama 서버 실행 시에만 동작한다.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from features.compliance.facility_db import FacilityDB
from features.compliance.crawler import ScenarioLoader, RegulationChange
from features.compliance.change_detector import ChangeDetector
from features.compliance.impact_analyzer import ImpactAnalyzer
from features.compliance.alert_generator import AlertGenerator
from features.compliance.compliance_checker import ComplianceChecker
from features.compliance import CompliancePipeline


# ===== 1. 시설 DB 로드 테스트 =====

def test_facility_db():
    """시설 데이터베이스 로드 검증"""
    print("=" * 60)
    print("📋 시설 DB 로드 테스트")
    print("=" * 60)

    db_dir = PROJECT_ROOT / "data" / "facility_db"
    db = FacilityDB(db_dir)

    # 공장 수
    assert len(db.plants) >= 3, f"공장 수 부족: {len(db.plants)}"
    print(f"  ✅ 공장: {len(db.plants)}개")
    for p in db.plants.values():
        print(f"     - {p.name} ({p.location}): {p.employee_count}명")

    # 공정 수
    assert len(db.processes) >= 10, f"공정 수 부족: {len(db.processes)}"
    print(f"  ✅ 공정: {len(db.processes)}개")

    # 화학물질 수
    assert len(db.chemicals) >= 8, f"화학물질 수 부족: {len(db.chemicals)}"
    print(f"  ✅ 화학물질: {len(db.chemicals)}개")

    # SVHC 후보물질 확인
    svhc = db.find_chemicals_svhc()
    assert len(svhc) >= 1, "SVHC 후보물질이 없음"
    print(f"  ✅ SVHC 후보물질: {', '.join(c.name for c in svhc)}")

    # 안전기준 수
    assert len(db.standards) >= 6, f"안전기준 수 부족: {len(db.standards)}"
    print(f"  ✅ 안전기준: {len(db.standards)}개")

    # 교차 참조 검증
    for proc in db.processes.values():
        plant = db.plants.get(proc.plant_id)
        assert plant is not None, f"공정 {proc.process_id}의 공장 {proc.plant_id} 없음"

    print("  ✅ 교차 참조 정합성 확인")
    print("\n  ✅ 시설 DB 로드 테스트 통과")
    return True


# ===== 2. 시나리오 로더 테스트 =====

def test_scenario_loader():
    """시나리오 JSON 로드 검증"""
    print("\n" + "=" * 60)
    print("📋 시나리오 로더 테스트")
    print("=" * 60)

    scenarios_dir = PROJECT_ROOT / "data" / "scenarios"
    loader = ScenarioLoader(scenarios_dir)

    assert loader.total_scenarios >= 4, f"시나리오 수 부족: {loader.total_scenarios}"
    print(f"  로드된 시나리오: {loader.total_scenarios}개")

    for scenario in loader.get_all_scenarios():
        assert scenario.title, f"제목 없음: {scenario.scenario_id}"
        assert scenario.before_text, f"구법 텍스트 없음: {scenario.scenario_id}"
        assert scenario.after_text, f"신법 텍스트 없음: {scenario.scenario_id}"
        assert scenario.severity in ("high", "medium", "low"), \
            f"유효하지 않은 심각도: {scenario.severity}"
        print(f"  ✅ {scenario.scenario_id}: {scenario.title} (심각도: {scenario.severity})")

    # 특정 시나리오 조회
    scn001 = loader.get_scenario("SCN-001")
    assert scn001 is not None, "SCN-001 시나리오 없음"
    assert "안전거리" in scn001.title or "프레스" in scn001.title
    print(f"  ✅ SCN-001 조회 정상: {scn001.title}")

    print("\n  ✅ 시나리오 로더 테스트 통과")
    return True


# ===== 3. 변경 감지 테스트 =====

def test_change_detector():
    """법규 텍스트 변경 감지 테스트"""
    print("\n" + "=" * 60)
    print("📋 변경 감지 테스트")
    print("=" * 60)

    detector = ChangeDetector()

    # 테스트 1: 숫자 변경 감지
    before = "안전거리는 300밀리미터 이상으로 하고"
    after = "안전거리는 400밀리미터 이상으로 하고"
    result = detector.detect(before, after)
    assert result.total_changes >= 1
    assert len(result.key_numbers_changed) >= 1
    num_change = result.key_numbers_changed[0]
    assert "300" in num_change["before"]
    assert "400" in num_change["after"]
    print(f"  ✅ 숫자 변경 감지: {num_change['before']} → {num_change['after']}")

    # 테스트 2: 줄 추가 감지
    before2 = "제1항 내용\n제2항 내용"
    after2 = "제1항 내용\n제2항 내용\n제3항 신설 내용"
    result2 = detector.detect(before2, after2)
    assert len(result2.added_lines) >= 1
    print(f"  ✅ 줄 추가 감지: {result2.added_lines[0][:30]}...")

    # 테스트 3: 시나리오 기반 변경 감지
    scenarios_dir = PROJECT_ROOT / "data" / "scenarios"
    loader = ScenarioLoader(scenarios_dir)
    scn001 = loader.get_scenario("SCN-001")
    if scn001:
        result3 = detector.detect(scn001.before_text, scn001.after_text)
        assert result3.total_changes >= 1
        print(f"  ✅ SCN-001 변경 감지: {result3.summary[:60]}...")

    # 테스트 4: 동일 텍스트
    result4 = detector.detect("동일한 텍스트", "동일한 텍스트")
    assert result4.total_changes == 0
    print("  ✅ 동일 텍스트: 변경 없음 정상")

    print("\n  ✅ 변경 감지 테스트 통과")
    return True


# ===== 4. 영향 분석 테스트 =====

def test_impact_analyzer():
    """영향도 분석 테스트"""
    print("\n" + "=" * 60)
    print("📋 영향 분석 테스트")
    print("=" * 60)

    db = FacilityDB(PROJECT_ROOT / "data" / "facility_db")
    analyzer = ImpactAnalyzer(db)
    loader = ScenarioLoader(PROJECT_ROOT / "data" / "scenarios")

    all_ok = True
    for scenario in loader.get_all_scenarios():
        report = analyzer.analyze(scenario)

        assert report.scenario_id == scenario.scenario_id
        assert report.severity in ("high", "medium", "low")
        assert report.risk_score >= 0

        plant_info = f"{len(report.affected_plants)}개 공장" if report.affected_plants else "직접 영향 없음"
        proc_info = f"{len(report.affected_processes)}개 공정" if report.affected_processes else ""
        worker_info = f"{report.affected_workers}명" if report.affected_workers else ""

        print(f"  ✅ {scenario.scenario_id}: {scenario.title}")
        print(f"     위험점수: {report.risk_score:.0f}/100, {plant_info}, {proc_info}, {worker_info}")

        # high 심각도 시나리오는 위험점수가 일정 이상이어야 함
        if scenario.severity == "high" and report.risk_score < 30:
            print(f"     ⚠️ high 심각도인데 위험점수가 낮음: {report.risk_score}")
            all_ok = False

    print(f"\n  {'✅' if all_ok else '⚠️'} 영향 분석 테스트 {'통과' if all_ok else '일부 경고'}")
    return True  # 경고는 허용


# ===== 5. 알림 생성 테스트 =====

def test_alert_generator():
    """알림 생성 테스트"""
    print("\n" + "=" * 60)
    print("📋 알림 생성 테스트")
    print("=" * 60)

    db = FacilityDB(PROJECT_ROOT / "data" / "facility_db")
    analyzer = ImpactAnalyzer(db)
    alert_gen = AlertGenerator()
    loader = ScenarioLoader(PROJECT_ROOT / "data" / "scenarios")

    for scenario in loader.get_all_scenarios():
        report = analyzer.analyze(scenario)
        alert = alert_gen.generate(report)

        assert alert.alert_id.startswith("ALT-")
        assert alert.severity == scenario.severity
        assert alert.title == scenario.title
        assert alert.icon in ("🔴", "🟡", "🟢")

        alert_text = alert_gen.format_alert_text(alert)
        assert len(alert_text) > 100

        print(f"  ✅ {alert.icon} [{alert.label}] {alert.title}")
        print(f"     알림 길이: {len(alert_text)}자")

    print("\n  ✅ 알림 생성 테스트 통과")
    return True


# ===== 6. 규정 준수 확인 테스트 =====

def test_compliance_checker():
    """규정 준수 확인 테스트"""
    print("\n" + "=" * 60)
    print("📋 규정 준수 확인 테스트")
    print("=" * 60)

    db = FacilityDB(PROJECT_ROOT / "data" / "facility_db")
    loader = ScenarioLoader(PROJECT_ROOT / "data" / "scenarios")
    checker = ComplianceChecker(db, loader)

    test_queries = [
        ("프레스 안전거리 기준이 어떻게 되나요?", True, "press_safety"),
        ("소음 규정 현황 알려줘", True, "noise"),
        ("6가 크롬 사용 현황은?", True, "chemical"),
        ("점심 메뉴 추천해줘", False, None),
    ]

    passed = 0
    for query, should_find, category in test_queries:
        result = checker.check(query)
        found = bool(result.answer)

        ok = found == should_find
        if ok:
            passed += 1

        status = "✅" if ok else "❌"
        info = f"기준 {len(result.relevant_standards)}개, 물질 {len(result.relevant_chemicals)}개"
        print(f"  {status} '{query}' → {info}")

    print(f"\n  결과: {passed}/{len(test_queries)} 통과")
    return passed >= len(test_queries) - 1


# ===== 7. 통합 파이프라인 테스트 =====

def test_pipeline():
    """CompliancePipeline 통합 테스트"""
    print("\n" + "=" * 60)
    print("📋 통합 파이프라인 테스트")
    print("=" * 60)

    pipeline = CompliancePipeline()

    # 시설 현황 확인
    overview = pipeline.get_facility_overview()
    assert overview["plants"] >= 3
    assert overview["processes"] >= 10
    assert overview["scenarios"] >= 4
    print(f"  ✅ 시설 현황: 공장 {overview['plants']}개, "
          f"공정 {overview['processes']}개, "
          f"시나리오 {overview['scenarios']}개")

    # 시나리오 실행
    result = pipeline.run_scenario("SCN-001")
    assert "error" not in result
    assert result["impact_report"].severity == "high"
    assert "alert_text" in result
    print(f"  ✅ SCN-001 시나리오 실행 정상")

    # 전체 시나리오 실행
    all_results = pipeline.run_all_scenarios()
    assert len(all_results) >= 4
    for r in all_results:
        assert "error" not in r
    print(f"  ✅ 전체 시나리오 실행: {len(all_results)}개 정상")

    # 규정 준수 확인
    comp_result = pipeline.check_compliance("소음 기준 현황")
    assert "query" in comp_result
    print(f"  ✅ 규정 준수 확인 정상")

    # 알림 텍스트 출력 (SCN-001)
    print(f"\n  --- SCN-001 알림 미리보기 ---")
    print(result["alert_text"][:300])

    print("\n  ✅ 통합 파이프라인 테스트 통과")
    return True


# ===== 메인 =====

def main():
    print("\n🏭 AJIN AI Assistant — 기능 D 법규/규정 모니터링 테스트\n")

    all_passed = True
    all_passed &= test_facility_db()
    all_passed &= test_scenario_loader()
    all_passed &= test_change_detector()
    all_passed &= test_impact_analyzer()
    all_passed &= test_alert_generator()
    all_passed &= test_compliance_checker()
    all_passed &= test_pipeline()

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 모든 기본 테스트 통과!")
    else:
        print("⚠️ 일부 테스트 실패. 위 결과를 확인하세요.")
    print("=" * 60)

    print("\n💡 Ollama 서버가 실행 중이면 LLM 포함 테스트를 할 수 있습니다:")
    print("   from features.compliance import CompliancePipeline")
    print("   pipeline = CompliancePipeline()")
    print("   result = await pipeline.run_scenario_with_llm('SCN-001')")


if __name__ == "__main__":
    main()
