"""기능 B 초안 자동 작성 통합 테스트

Ollama 서버가 실행 중이어야 LLM 기반 테스트가 정상 동작한다.
분류기, 템플릿 렌더링, .docx 출력은 Ollama 없이도 테스트 가능하다.
"""

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from features.draft.classifier import (
    DocType,
    DraftRequest,
    rule_based_classify,
    TEMPLATE_MAP,
)
from features.draft.template_renderer import TemplateRenderer
from features.draft.docx_exporter import DocxExporter


# ===== 1. 분류기 테스트 (Ollama 불필요) =====

def test_classifier():
    """규칙 기반 분류기 테스트"""
    print("=" * 60)
    print("📋 분류기 테스트")
    print("=" * 60)

    test_cases = [
        {
            "query": "현대차 구매팀에 A-Panel 납기 1주 지연 회신 메일 작성해줘",
            "expected_type": DocType.EMAIL_OEM,
            "expected_part": "A-Panel",
            "expected_situation": "납기지연",
        },
        {
            "query": "기아 광주에 보낼 클레임 대응 메일",
            "expected_type": DocType.EMAIL_OEM,
            "expected_situation": "클레임대응",
        },
        {
            "query": "한국실링에 EPDM 실링 긴급 납품 요청 메일",
            "expected_type": DocType.EMAIL_SUPPLIER,
            "expected_situation": "협조요청",
        },
        {
            "query": "생산기술팀에 다음 주 금형 보수 일정 공유 메일 써줘",
            "expected_type": DocType.EMAIL_INTERNAL,
            "expected_situation": "업무연락",
        },
        {
            "query": "EMP 워터펌프 누수 클레임 8D Report 초안 만들어줘",
            "expected_type": DocType.REPORT_8D,
            "expected_part": "EMP 워터펌프",
            "expected_situation": "클레임대응",
        },
        {
            "query": "A-Panel 두께 공차 변경 ECN 작성해줘",
            "expected_type": DocType.REPORT_ECN,
            "expected_part": "A-Panel",
            "expected_situation": "설계변경",
        },
        {
            "query": "B-Pillar 용접 크랙 원인분석 회의록 작성",
            "expected_type": DocType.REPORT_MEETING,
            "expected_part": "B-Pillar",
            "expected_situation": "품질회의",
        },
        {
            "query": "해외 법인에 납기 변경 안내 영문 메일",
            "expected_type": DocType.EMAIL_OVERSEAS,
            "expected_situation": "납기지연",
        },
        {
            "query": "OBC 충전장치 방열 구조 개선 ECN",
            "expected_type": DocType.REPORT_ECN,
            "expected_part": "OBC 충전장치",
        },
        {
            "query": "CCH 냉난방장치 블로워 소음 클레임 대응 보고서",
            "expected_type": DocType.REPORT_8D,
            "expected_part": "CCH 냉난방장치",
        },
    ]

    passed = 0
    total = len(test_cases)

    for tc in test_cases:
        req = rule_based_classify(tc["query"])
        ok = True

        if req.doc_type != tc["expected_type"]:
            ok = False
        if "expected_part" in tc and req.part_name != tc["expected_part"]:
            ok = False
        if "expected_situation" in tc and req.situation_type != tc["expected_situation"]:
            ok = False

        status = "✅" if ok else "❌"
        if ok:
            passed += 1
        print(f"  {status} '{tc['query']}'")
        print(f"      → 유형={req.doc_type.value}, 부품={req.part_name}, "
              f"상황={req.situation_type}, 템플릿={req.template_key}")
        if not ok:
            print(f"      ⚠ 기대: 유형={tc['expected_type'].value}, "
                  f"부품={tc.get('expected_part')}, "
                  f"상황={tc.get('expected_situation')}")

    print(f"\n  결과: {passed}/{total} 통과")
    return passed == total


# ===== 2. 템플릿 렌더링 테스트 (Ollama 불필요) =====

def test_template_rendering():
    """Jinja2 템플릿 렌더링 테스트"""
    print("\n" + "=" * 60)
    print("📋 템플릿 렌더링 테스트")
    print("=" * 60)

    templates_dir = PROJECT_ROOT / "data" / "templates"
    renderer = TemplateRenderer(templates_dir)

    # 완성차 이메일 렌더링
    oem_request = DraftRequest(
        doc_type=DocType.EMAIL_OEM,
        template_key="email/to_oem.j2",
        recipient_company="현대자동차",
        recipient_department="구매팀",
        part_name="A-Panel",
        part_number="AJ-AP-001",
        situation_type="납기지연",
        situation_summary="A-Panel 납기 1주 지연",
        reference_search_query="A-Panel 납기지연",
    )

    oem_vars = {
        "customer_name": "현대자동차",
        "department": "구매팀",
        "recipient_name": "김구매",
        "recipient_title": "과장님",
        "sender_department": "품질관리팀",
        "sender_name": "박품질",
        "sender_title": "대리",
        "subject": "A-Panel 납기 조정 요청의 건",
        "opening_paragraph": "금번 A-Panel 부품 납기 관련하여 아래와 같이 조정 요청 드리오니 검토 부탁드립니다.",
        "structured_items": [
            {"label": "대상 부품", "value": "A-Panel (품번: AJ-AP-001)"},
            {"label": "당초 납기", "value": "2026.04.10"},
            {"label": "조정 납기", "value": "2026.04.17 (1주 지연)"},
            {"label": "사유", "value": "프레스 금형 정기 보수 일정에 따른 생산 지연"},
        ],
        "main_body": "금형 보수 완료 후 2교대 증산 편성으로 잔여 물량 조기 납품을 추진하겠습니다.",
        "action_items": ["금형 보수: 4/7~4/10 완료 예정", "증산 편성: 4/11~4/14 (2교대)"],
        "closing_paragraph": "납기 준수를 위해 최선을 다하겠습니다.",
    }

    rendered = renderer.render(oem_request, oem_vars)
    assert "현대자동차" in rendered
    assert "A-Panel" in rendered
    assert "김구매" in rendered
    assert "■" in rendered
    print("  ✅ 완성차 이메일 렌더링 성공")
    print(f"     → 길이: {len(rendered)}자")

    # 8D Report 렌더링
    report_request = DraftRequest(
        doc_type=DocType.REPORT_8D,
        template_key="report/8d_report.j2",
        part_name="EMP 워터펌프",
        part_number="AJ-EMP-W100",
        situation_type="클레임대응",
        situation_summary="EMP 워터펌프 누수",
        reference_search_query="EMP 워터펌프 누수",
    )

    report_vars = {
        "doc_number": "8D-2026-TEST",
        "author": "박품질",
        "part_name": "EMP 워터펌프",
        "part_number": "AJ-EMP-W100",
        "customer": "현대자동차 울산공장",
        "claim_date": "2026-03-15",
        "defect_summary": "하우징-커버 접합부 냉각수 누수",
        "d1_team": [
            {"role": "팀장", "name": "이관리", "department": "품질관리팀"},
            {"role": "공정 담당", "name": "최공정", "department": "생산기술팀"},
            {"role": "설계 담당", "name": "김설계", "department": "연구소"},
        ],
        "d2_problem": "EMP 워터펌프 하우징-커버 접합부에서 냉각수가 누수되는 현상 발생",
        "d2_5w1h": {
            "what": "하우징-커버 접합부 냉각수 누수",
            "when": "2026년 3월 중순",
            "where": "현대차 울산공장 엔진 조립라인",
            "who": "품질검사원",
            "why": "실링 불량으로 냉각수 유출 시 엔진 과열 위험",
            "how": "NBR 소재 O-ring의 내열성 저하로 경화/수축 발생",
        },
        "d3_containment": "출하 보류 및 전수 검사 실시. 고객 재고분 선별 작업 진행.",
        "d3_actions": [
            {"description": "출하 보류", "owner": "박품질", "due_date": "2026-03-16", "status": "완료"},
            {"description": "전수 검사", "owner": "김검사", "due_date": "2026-03-18", "status": "진행중"},
        ],
        "d4_root_cause": "NBR 소재 O-ring의 내열성 저하가 근본 원인. 5Why 분석 결과 확인.",
        "d5_corrective": "실링 소재를 NBR에서 EPDM으로 변경",
        "d6_implementation": "EPDM O-ring 시작품 제작 및 내구 시험 진행 중",
        "d6_schedule": [
            {"action": "EPDM 시작품 제작", "owner": "김설계", "start": "2026-03-20", "end": "2026-03-25", "status": "진행중"},
        ],
        "d7_prevention": "SOP 개정, 입고 검사 기준 강화, 유사 부품 수평 전개",
        "d8_closure": "시정 조치 유효성 검증 완료 후 종료 예정",
    }

    rendered_8d = renderer.render(report_request, report_vars)
    assert "8D REPORT" in rendered_8d
    assert "D1. 팀 구성" in rendered_8d
    assert "D7. 재발 방지" in rendered_8d
    assert "EMP 워터펌프" in rendered_8d
    print("  ✅ 8D Report 렌더링 성공")
    print(f"     → 길이: {len(rendered_8d)}자")

    # ECN 렌더링
    ecn_request = DraftRequest(
        doc_type=DocType.REPORT_ECN,
        template_key="report/ecn_notice.j2",
        part_name="A-Panel",
        part_number="AJ-AP-001",
        situation_type="설계변경",
        situation_summary="두께 공차 변경",
        reference_search_query="A-Panel 설계변경",
    )

    ecn_vars = {
        "doc_number": "ECN-2026-TEST",
        "part_name": "A-Panel",
        "part_number": "AJ-AP-001",
        "change_type": "치수변경",
        "vehicle_model": "NE1 (아이오닉5 후속)",
        "change_origin": "품질 개선 (8D-2025-003 후속 조치)",
        "author": "김설계",
        "before_description": "두께 공차: 1.2mm ±0.3mm",
        "after_description": "두께 공차: 1.2mm ±0.2mm (공차 강화)",
        "change_reason": "홀 피치 치수 불량 재발 방지를 위한 공차 강화",
        "impact_scope": "프레스 금형 셋업 재조정, 검사 기준 변경",
        "schedule": [
            {"phase": "ECN 발행", "date": "2026-03-21", "note": ""},
            {"phase": "시작품 제작", "date": "2026-04-01", "note": "10EA"},
            {"phase": "양산 적용", "date": "2026-05-01", "note": "고객 승인 후"},
        ],
        "department_actions": [
            {"department": "생산기술팀", "action": "프레스 금형 공차 재설정"},
            {"department": "품질관리팀", "action": "검사 기준서 개정"},
        ],
        "reviewer": "이검토",
        "approver": "박승인",
    }

    rendered_ecn = renderer.render(ecn_request, ecn_vars)
    assert "설계변경통보서" in rendered_ecn
    assert "변경 전" in rendered_ecn
    assert "변경 후" in rendered_ecn
    print("  ✅ ECN 렌더링 성공")
    print(f"     → 길이: {len(rendered_ecn)}자")

    print("\n  ✅ 모든 템플릿 렌더링 테스트 통과")
    return True


# ===== 3. 프롬프트 파일 검증 =====

def test_prompts_exist():
    """시스템 프롬프트 파일 존재 및 내용 검증"""
    print("\n" + "=" * 60)
    print("📋 시스템 프롬프트 파일 검증")
    print("=" * 60)

    prompts_dir = PROJECT_ROOT / "features" / "draft" / "prompts"
    expected_files = [
        "email_to_oem.txt",
        "email_to_supplier.txt",
        "email_to_internal.txt",
        "email_to_overseas.txt",
        "report_8d.txt",
        "report_ecn.txt",
        "report_meeting.txt",
    ]

    all_ok = True
    for fname in expected_files:
        fpath = prompts_dir / fname
        if not fpath.exists():
            print(f"  ❌ 누락: {fname}")
            all_ok = False
            continue

        content = fpath.read_text(encoding="utf-8")
        ok = True

        if len(content) < 200:
            print(f"  ❌ 내용 부족: {fname} ({len(content)}자)")
            ok = False
        if "{reference_docs}" not in content:
            print(f"  ❌ 참조문서 변수 누락: {fname}")
            ok = False
        if "{user_request}" not in content:
            print(f"  ❌ 사용자요청 변수 누락: {fname}")
            ok = False

        if ok:
            print(f"  ✅ {fname}: {len(content)}자")
        else:
            all_ok = False

    if all_ok:
        print("\n  ✅ 모든 프롬프트 파일 검증 통과")
    return all_ok


# ===== 4. .docx 출력 테스트 =====

def test_docx_export():
    """마크다운 → .docx 변환 테스트"""
    print("\n" + "=" * 60)
    print("📋 .docx 출력 테스트")
    print("=" * 60)

    exporter = DocxExporter()

    test_md = """# [아진산업] A-Panel 납기 조정 요청의 건

| 항목 | 내용 |
|---|---|
| 수신 | 현대자동차 구매팀 김구매 과장님 |
| 발신 | 아진산업 품질관리팀 박품질 대리 |
| 일자 | 2026-03-21 |

---

안녕하십니까, 아진산업 품질관리팀 박품질입니다.

금번 A-Panel 부품 납기 관련하여 아래와 같이 조정 요청 드리오니 검토 부탁드립니다.

■ 대상 부품: A-Panel (품번: AJ-AP-001)
■ 당초 납기: 2026.04.10
■ 조정 납기: 2026.04.17 (1주 지연)
■ 사유: 프레스 금형 정기 보수 일정에 따른 생산 지연

## 향후 조치 계획

1. 금형 보수: 4/7~4/10 완료 예정
2. 증산 편성: 4/11~4/14 (2교대)
3. 잔여 물량 조기 납품 추진

불편을 끼쳐드려 죄송하며, 추가 문의사항이 있으시면 연락 주시기 바랍니다.

감사합니다.
"""

    output_path = PROJECT_ROOT / "output" / "test_email.docx"
    result = exporter.export(
        markdown_text=test_md,
        output_path=output_path,
        doc_title="A-Panel 납기 조정 요청",
    )

    assert result.exists(), f".docx 파일 생성 실패: {result}"
    file_size = result.stat().st_size
    assert file_size > 1000, f".docx 파일이 너무 작음: {file_size}bytes"

    print(f"  ✅ .docx 파일 생성 완료: {result}")
    print(f"     → 파일 크기: {file_size:,} bytes")

    # 8D Report docx 테스트
    test_8d_md = """# 8D REPORT

| 항목 | 내용 |
|---|---|
| 문서번호 | 8D-2026-TEST |
| 대상 부품 | EMP 워터펌프 (품번: AJ-EMP-W100) |
| 고객사 | 현대자동차 울산공장 |

---

## D1. 팀 구성

| 역할 | 이름 | 부서 |
|---|---|---|
| 팀장 | 이관리 | 품질관리팀 |
| 공정 담당 | 최공정 | 생산기술팀 |

## D2. 문제 정의

하우징-커버 접합부에서 냉각수가 누수되는 현상 발생

## D3. 긴급 대응 조치

출하 보류 및 전수 검사 실시.

- **품질관리팀**: 출하 보류 조치
- **생산기술팀**: 공정 점검

## D4. 근본 원인 분석

NBR 소재 O-ring의 내열성 저하가 근본 원인
"""

    output_8d = PROJECT_ROOT / "output" / "test_8d_report.docx"
    result_8d = exporter.export(
        markdown_text=test_8d_md,
        output_path=output_8d,
        doc_title="8D Report - EMP 워터펌프",
    )

    assert result_8d.exists()
    print(f"  ✅ 8D .docx 파일 생성 완료: {result_8d}")
    print(f"     → 파일 크기: {result_8d.stat().st_size:,} bytes")

    print("\n  ✅ .docx 출력 테스트 통과")
    return True


# ===== 5. 분류기 → 템플릿 매핑 일관성 테스트 =====

def test_template_mapping():
    """모든 DocType에 대응하는 템플릿 파일이 존재하는지 확인"""
    print("\n" + "=" * 60)
    print("📋 템플릿 매핑 일관성 테스트")
    print("=" * 60)

    templates_dir = PROJECT_ROOT / "data" / "templates"
    all_ok = True

    for doc_type, template_key in TEMPLATE_MAP.items():
        template_path = templates_dir / template_key
        if template_path.exists():
            print(f"  ✅ {doc_type.value} → {template_key}")
        else:
            print(f"  ❌ {doc_type.value} → {template_key} (파일 없음)")
            all_ok = False

    if all_ok:
        print("\n  ✅ 모든 템플릿 매핑 검증 통과")
    return all_ok


# ===== 메인 =====

def main():
    print("\n🏭 AJIN AI Assistant — 기능 B 초안 작성 테스트\n")

    all_passed = True
    all_passed &= test_classifier()
    all_passed &= test_template_rendering()
    all_passed &= test_prompts_exist()
    all_passed &= test_docx_export()
    all_passed &= test_template_mapping()

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 모든 기본 테스트 통과!")
    else:
        print("⚠️ 일부 테스트 실패. 위 결과를 확인하세요.")
    print("=" * 60)

    print("\n💡 Ollama 서버가 실행 중이면 전체 초안 생성 테스트를 할 수 있습니다:")
    print("   from features.draft import DraftPipeline")
    print("   pipeline = DraftPipeline(searcher=None)")
    print("   rendered, session = await pipeline.create_draft('현대차에 납기 지연 메일 써줘')")


if __name__ == "__main__":
    main()
