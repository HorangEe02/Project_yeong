"""
SPC 보고서 생성 — OEM 제출용 DOCX/PDF 보고서 자동 생성
"""
from datetime import datetime
from features.equipment.spc_analyzer import SPCResult


def generate_spc_report_markdown(
    result: SPCResult,
    part_name: str = "",
    part_number: str = "",
    process_name: str = "",
    machine: str = "",
    operator: str = "",
    inspector: str = "",
) -> str:
    """
    SPC 분석 결과를 마크다운 보고서로 변환합니다.
    DOCX/PDF 변환의 입력으로 사용됩니다.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    grade_text = {
        "A": "A등급 (Cpk >= 1.67) - 우수",
        "B": "B등급 (Cpk >= 1.33) - 양호",
        "C": "C등급 (Cpk >= 1.00) - 주의",
        "D": "D등급 (Cpk < 1.00) - 개선 필요",
    }.get(result.grade, "미판정")

    verdict = "합격" if result.is_capable and result.is_stable else "조치 필요"
    verdict_icon = "PASS" if verdict == "합격" else "FAIL"
    verdict_detail = (
        "공정이 안정적이며 규격을 충족합니다."
        if result.is_capable and result.is_stable
        else "공정 능력 개선이 필요합니다. 산포 감소 또는 평균 조정을 검토하세요."
    )

    report = f"""# SPC 공정 능력 분석 보고서

**작성일**: {now}
**작성자**: {operator or '미지정'}

---

## 1. 분석 개요

| 항목 | 내용 |
|------|------|
| 부품명 | {part_name or '-'} |
| 부품 번호 | {part_number or '-'} |
| 공정명 | {process_name or '-'} |
| 설비 | {machine or '-'} |
| 검사자 | {inspector or '-'} |
| 데이터 수 | {result.n}개 |
| 분석 일시 | {now} |

## 2. 규격 정보

| 항목 | 값 |
|------|-----|
| 상한 규격 (USL) | {result.usl if result.usl is not None else '-'} |
| 하한 규격 (LSL) | {result.lsl if result.lsl is not None else '-'} |
| 목표값 (Target) | {result.target if result.target is not None else '-'} |

## 3. 기본 통계

| 항목 | 값 |
|------|-----|
| 평균 (X-bar) | {result.mean:.4f} |
| 표준편차 (sigma 전체) | {result.std:.4f} |
| 표준편차 (sigma 군내) | {result.std_within:.4f} |
| 최소값 | {result.minimum:.4f} |
| 최대값 | {result.maximum:.4f} |
| 평균범위 (R-bar) | {result.range_avg:.4f} |

## 4. 공정 능력 지수

| 지수 | 값 | 판정 |
|------|-----|------|
| Cp | {result.cp if result.cp is not None else '-'} | {'양호' if (result.cp or 0) >= 1.33 else '부족'} |
| **Cpk** | **{result.cpk if result.cpk is not None else '-'}** | **{grade_text}** |
| Pp | {result.pp if result.pp is not None else '-'} | |
| Ppk | {result.ppk if result.ppk is not None else '-'} | |

## 5. 관리도 분석

### X-bar 관리도
- 중심선 (CL): {result.xbar_cl:.4f}
- 상한 관리선 (UCL): {result.xbar_ucl:.4f}
- 하한 관리선 (LCL): {result.xbar_lcl:.4f}
- 관리 이탈: **{len(result.out_of_control)}건**

### R 관리도
- 중심선 (CL): {result.r_cl:.4f}
- 상한 관리선 (UCL): {result.r_ucl:.4f}

## 6. 이상 항목

- 규격 이탈: **{len(result.out_of_spec)}건**
- 관리 이탈: **{len(result.out_of_control)}건**

## 7. 종합 판정

**[{verdict_icon}] {verdict}** - {grade_text}

{verdict_detail}

---

**아진산업(주)** | 품질보증팀 | SPC 자동 분석 보고서
"""
    return report
