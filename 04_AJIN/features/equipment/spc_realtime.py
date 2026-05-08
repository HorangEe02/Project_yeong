"""
SPC 실시간 이상 감지 -- Nelson 8 Rules
- 관리도 데이터에 Nelson 8가지 규칙 적용
- 위반 포인트 식별 + 심각도 판정 + 권장 조치
- Plotly 관리도 시각화 (위반 하이라이트)
"""

import numpy as np
import plotly.graph_objects as go
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NelsonViolation:
    """Nelson Rule 위반 항목"""
    rule_number: int
    rule_name: str
    description: str
    violating_indices: List[int] = field(default_factory=list)
    severity: str = "info"           # critical / warning / info
    recommended_action: str = ""


@dataclass
class NelsonAnalysisResult:
    """Nelson Rule 분석 결과"""
    process_name: str = ""
    mean: float = 0.0
    std: float = 0.0
    ucl: float = 0.0                 # +3σ
    lcl: float = 0.0                 # -3σ
    sigma_1_upper: float = 0.0       # +1σ
    sigma_1_lower: float = 0.0       # -1σ
    sigma_2_upper: float = 0.0       # +2σ
    sigma_2_lower: float = 0.0       # -2σ
    violations: List[NelsonViolation] = field(default_factory=list)
    total_points: int = 0
    out_of_control: bool = False
    violation_count: int = 0


# Nelson Rule별 권장 조치 (한국어)
NELSON_ACTIONS = {
    1: "즉시 생산 중지 → 특수 원인 조사 (공구 파손, 재료 로트 변경, 측정 오류 확인)",
    2: "공정 평균 이동 의심 → 설정값/기준점 재확인, 공구 마모 점검",
    3: "연속 추세 감지 → 공구 마모, 온도 drift, 소재 변화 확인",
    4: "과잉 조정 의심 → 작업자 조정 패턴 확인, SOP 재교육",
    5: "산포 증가 시작 → 공정 변동 원인 조사, 장비 정밀도 점검",
    6: "산포 지속 증가 → 긴급 공정 점검, 장비 캘리브레이션 필요",
    7: "과소 산포 (데이터 조작 의심) → 측정 시스템 분석(MSA) 재실시",
    8: "혼합 모집단 감지 → 소재 로트, 작업 교대, 장비 간 차이 확인",
}


# ── v3.4: Nelson Rule별 상세 원인 추정 + 조치 가이드 ──
NELSON_RULE_GUIDE = {
    1: {
        "name": "관리 한계 이탈",
        "description": "1개 이상의 점이 UCL 또는 LCL을 벗어남",
        "severity": "HIGH",
        "probable_causes": [
            "설비 고장 또는 급격한 조건 변화",
            "소재 불량 (로트 변경, 이물질 혼입)",
            "측정 장비 오류 (캘리브레이션 필요)",
            "작업자 실수 (셋업 오류, 잘못된 프로그램)",
        ],
        "recommended_actions": [
            "해당 시점의 설비 파라미터 즉시 확인",
            "소재 로트 번호 확인 및 변경 여부 추적",
            "측정 게이지 교정 상태 확인 (MSA)",
            "해당 제품 격리 및 선별 검사 실시",
        ],
        "chart_annotation": "관리 한계 이탈 — 즉시 원인 조사 필요",
    },
    2: {
        "name": "9점 연속 한쪽 편향",
        "description": "9개 연속 점이 중심선(CL) 한쪽에 위치",
        "severity": "MEDIUM",
        "probable_causes": [
            "공구/금형 마모 진행 중 (점진적 치수 변화)",
            "소재 로트 변경 (새 로트의 평균값 편차)",
            "설비 온도 드리프트 (열 팽창에 의한 치수 변화)",
            "측정 기준점 미세 이동",
        ],
        "recommended_actions": [
            "공구/금형 마모 상태 점검",
            "최근 소재 로트 변경 이력 확인",
            "설비 예열 상태 및 주변 온도 확인",
            "Control Plan 재검토 (관리 기준 적정성)",
        ],
        "chart_annotation": "9점 연속 편향 — 공구 마모 또는 소재 로트 변경 확인",
    },
    3: {
        "name": "6점 연속 증가/감소",
        "description": "6개 연속 점이 지속적으로 증가 또는 감소",
        "severity": "MEDIUM",
        "probable_causes": [
            "공구 마모 진행 (절삭 공구, 프레스 금형)",
            "설비 열 팽창 (가동 초기 워밍업 구간)",
            "냉각액/윤활유 성능 저하",
            "소재 특성 변화 (코일 끝부분 등)",
        ],
        "recommended_actions": [
            "공구 잔여 수명 확인 (교체 필요 여부 판단)",
            "설비 워밍업 후 재측정 실시",
            "냉각액 농도/유량 점검",
            "트렌드 지속 시 공정 조건 보정 실시",
        ],
        "chart_annotation": "6점 연속 추세 — 공구 마모 진행 의심",
    },
    4: {
        "name": "14점 교대 상승/하강",
        "description": "14개 연속 점이 번갈아 증가·감소를 반복",
        "severity": "LOW",
        "probable_causes": [
            "2개 설비/금형의 교대 가동 (설비 간 미세 편차)",
            "2개 측정 장비 교대 사용",
            "주/야간 교대 시 셋업 차이",
            "과도한 보정 (Over-adjustment) 반복",
        ],
        "recommended_actions": [
            "설비/금형별 데이터 층별화(Stratification) 분석",
            "측정 장비 간 R&R(재현성/반복성) 비교",
            "교대조별 셋업 절차 표준화 확인",
            "불필요한 보정 중단 검토",
        ],
        "chart_annotation": "14점 교대 패턴 — 설비/금형 간 편차 또는 과보정 확인",
    },
    5: {
        "name": "3점 중 2점이 2σ 이상",
        "description": "연속 3점 중 2점 이상이 2σ 경고 구간에 위치",
        "severity": "MEDIUM",
        "probable_causes": [
            "간헐적 외란 요인 (진동, 전압 변동 등)",
            "소재 내부 품질 불균일 (경도 편차 등)",
            "설비 유격 증가 (베어링, 가이드 마모)",
            "클램핑/고정 불안정",
        ],
        "recommended_actions": [
            "외란 요인 점검 (주변 설비 진동, 전원 품질)",
            "소재 수입검사 데이터 확인",
            "설비 유격 점검 (주축 런아웃, 슬라이드 클리어런스)",
            "지그/클램프 고정력 확인",
        ],
        "chart_annotation": "2σ 경고 빈발 — 간헐적 외란 또는 설비 유격 점검",
    },
    6: {
        "name": "5점 중 4점이 1σ 이상",
        "description": "연속 5점 중 4점 이상이 1σ 밖에 위치",
        "severity": "LOW",
        "probable_causes": [
            "공정 산포 증가 추세",
            "소재 산포 증가 (로트 간 편차)",
            "설비 정밀도 저하 (노후화)",
            "환경 조건 변동 (온도, 습도)",
        ],
        "recommended_actions": [
            "최근 Cpk 추세 확인 (하락 중인지)",
            "소재 입고 검사 데이터 산포 확인",
            "설비 정기 보전 실시 여부 확인",
            "작업 환경 조건 모니터링 강화",
        ],
        "chart_annotation": "산포 확대 경고 — 공정 능력 저하 추세 확인",
    },
    7: {
        "name": "15점 연속 1σ 이내",
        "description": "15개 연속 점이 모두 ±1σ 이내에 위치 (혼합 패턴)",
        "severity": "LOW",
        "probable_causes": [
            "데이터 조작 의심 (측정값 필터링/수정)",
            "측정 해상도 부족 (계측기 정밀도 한계)",
            "여러 공정 스트림의 데이터가 혼합됨",
            "관리 한계 설정이 과도하게 넓음",
        ],
        "recommended_actions": [
            "측정 데이터 원본 확인 (수기 기록 대조)",
            "계측기 해상도(최소 눈금) 확인",
            "데이터 층별화 (설비/금형/교대조별 분리 분석)",
            "관리 한계 재계산 검토",
        ],
        "chart_annotation": "과도한 안정 — 데이터 혼합 또는 계측기 해상도 확인",
    },
    8: {
        "name": "8점 연속 1σ 밖",
        "description": "8개 연속 점이 모두 ±1σ 밖에 위치 (층화 패턴)",
        "severity": "MEDIUM",
        "probable_causes": [
            "2개 이상 공정 스트림의 혼합 (2대 설비, 2종 소재)",
            "주기적 설비 조건 변동",
            "소재 특성의 양극화 (2개 로트 교차 사용)",
            "측정 위치 변동",
        ],
        "recommended_actions": [
            "설비별/금형별/소재 로트별 층별화 분석 실시",
            "설비 가동 조건의 주기적 변동 요인 확인",
            "소재 사용 순서 및 로트 추적",
            "측정 SOP 준수 여부 확인",
        ],
        "chart_annotation": "층화 패턴 — 복수 공정 스트림 혼합 의심",
    },
}


def get_rule_guide(rule_number: int) -> dict:
    """Nelson Rule 번호에 해당하는 원인 추정 + 조치 가이드 반환 (v3.4)"""
    return NELSON_RULE_GUIDE.get(rule_number, {})


def enrich_violations(violations: List["NelsonViolation"]) -> list:
    """Nelson Rule 위반 결과 리스트에 원인 추정 정보를 첨부 (v3.4)

    Parameters:
        violations: analyze_nelson_rules() 결과의 violations 리스트

    Returns:
        각 violation에 guide 정보가 추가된 dict 리스트
    """
    from dataclasses import asdict

    enriched = []
    for v in violations:
        v_dict = asdict(v) if hasattr(v, "__dataclass_fields__") else dict(v)
        guide = get_rule_guide(v_dict.get("rule_number", 0))
        v_dict["guide"] = guide
        enriched.append(v_dict)
    return enriched


def analyze_nelson_rules(
    values: list,
    spec_upper: float = None,
    spec_lower: float = None,
    process_name: str = "",
) -> NelsonAnalysisResult:
    """
    Nelson 8 Rules 적용하여 관리도 이상 감지

    Args:
        values: 측정값 리스트
        spec_upper/lower: 규격 상/하한 (Cpk 계산용, 필수 아님)
        process_name: 공정명

    Returns:
        NelsonAnalysisResult
    """
    arr = np.array(values, dtype=float)
    n = len(arr)

    if n < 10:
        return NelsonAnalysisResult(process_name=process_name, total_points=n)

    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1))

    if std == 0:
        std = 1e-10

    ucl = mean + 3 * std
    lcl = mean - 3 * std
    s1u = mean + 1 * std
    s1l = mean - 1 * std
    s2u = mean + 2 * std
    s2l = mean - 2 * std

    violations = []

    # Rule 1: 1점이 ±3σ 초과
    r1_idx = [i for i in range(n) if arr[i] > ucl or arr[i] < lcl]
    if r1_idx:
        violations.append(NelsonViolation(
            rule_number=1, rule_name="Beyond 3σ",
            description="1개 이상의 포인트가 ±3σ를 초과",
            violating_indices=r1_idx, severity="critical",
            recommended_action=NELSON_ACTIONS[1],
        ))

    # Rule 2: 9연속 같은 쪽 (평균 위 또는 아래)
    r2_idx = _detect_run(arr, mean, run_length=9)
    if r2_idx:
        violations.append(NelsonViolation(
            rule_number=2, rule_name="Run of 9",
            description="9개 연속 포인트가 평균의 같은 쪽",
            violating_indices=r2_idx, severity="warning",
            recommended_action=NELSON_ACTIONS[2],
        ))

    # Rule 3: 6연속 증가 또는 감소
    r3_idx = _detect_trend(arr, trend_length=6)
    if r3_idx:
        violations.append(NelsonViolation(
            rule_number=3, rule_name="Trend of 6",
            description="6개 연속 증가 또는 감소 추세",
            violating_indices=r3_idx, severity="warning",
            recommended_action=NELSON_ACTIONS[3],
        ))

    # Rule 4: 14연속 교대 증감
    r4_idx = _detect_alternating(arr, alt_length=14)
    if r4_idx:
        violations.append(NelsonViolation(
            rule_number=4, rule_name="Alternating 14",
            description="14개 연속 교대 증가/감소 반복",
            violating_indices=r4_idx, severity="info",
            recommended_action=NELSON_ACTIONS[4],
        ))

    # Rule 5: 3중 2가 ±2σ 초과 (같은 쪽)
    r5_idx = _detect_n_of_m_beyond(arr, mean, std, n_points=2, m_window=3, sigma=2)
    if r5_idx:
        violations.append(NelsonViolation(
            rule_number=5, rule_name="2 of 3 beyond 2σ",
            description="3개 중 2개가 ±2σ를 초과 (같은 쪽)",
            violating_indices=r5_idx, severity="warning",
            recommended_action=NELSON_ACTIONS[5],
        ))

    # Rule 6: 5중 4가 ±1σ 초과 (같은 쪽)
    r6_idx = _detect_n_of_m_beyond(arr, mean, std, n_points=4, m_window=5, sigma=1)
    if r6_idx:
        violations.append(NelsonViolation(
            rule_number=6, rule_name="4 of 5 beyond 1σ",
            description="5개 중 4개가 ±1σ를 초과 (같은 쪽)",
            violating_indices=r6_idx, severity="warning",
            recommended_action=NELSON_ACTIONS[6],
        ))

    # Rule 7: 15연속 ±1σ 이내
    r7_idx = _detect_within_sigma(arr, mean, std, run_length=15, sigma=1)
    if r7_idx:
        violations.append(NelsonViolation(
            rule_number=7, rule_name="15 within 1σ",
            description="15개 연속 ±1σ 이내 (과소 산포)",
            violating_indices=r7_idx, severity="info",
            recommended_action=NELSON_ACTIONS[7],
        ))

    # Rule 8: 8연속 ±1σ 양쪽 초과
    r8_idx = _detect_beyond_sigma_both(arr, mean, std, run_length=8, sigma=1)
    if r8_idx:
        violations.append(NelsonViolation(
            rule_number=8, rule_name="8 beyond 1σ both",
            description="8개 연속 ±1σ 밖 (양쪽 모두)",
            violating_indices=r8_idx, severity="warning",
            recommended_action=NELSON_ACTIONS[8],
        ))

    has_critical = any(v.severity == "critical" for v in violations)
    all_violation_idx = set()
    for v in violations:
        all_violation_idx.update(v.violating_indices)

    return NelsonAnalysisResult(
        process_name=process_name,
        mean=mean, std=std,
        ucl=ucl, lcl=lcl,
        sigma_1_upper=s1u, sigma_1_lower=s1l,
        sigma_2_upper=s2u, sigma_2_lower=s2l,
        violations=violations,
        total_points=n,
        out_of_control=has_critical,
        violation_count=len(all_violation_idx),
    )


# ──────────────────────────────────────────────
# Nelson Rule 감지 함수
# ──────────────────────────────────────────────

def _detect_run(arr, mean, run_length=9) -> List[int]:
    """Rule 2: 연속 N개가 같은 쪽"""
    indices = []
    above = arr > mean
    count = 1
    for i in range(1, len(arr)):
        if above[i] == above[i - 1]:
            count += 1
        else:
            count = 1
        if count >= run_length:
            indices.extend(range(i - run_length + 1, i + 1))
    return sorted(set(indices))


def _detect_trend(arr, trend_length=6) -> List[int]:
    """Rule 3: 연속 N개 증가 또는 감소"""
    indices = []
    inc, dec = 1, 1
    for i in range(1, len(arr)):
        inc = inc + 1 if arr[i] > arr[i - 1] else 1
        dec = dec + 1 if arr[i] < arr[i - 1] else 1
        if inc >= trend_length:
            indices.extend(range(i - trend_length + 1, i + 1))
        if dec >= trend_length:
            indices.extend(range(i - trend_length + 1, i + 1))
    return sorted(set(indices))


def _detect_alternating(arr, alt_length=14) -> List[int]:
    """Rule 4: 연속 N개 교대 증감"""
    if len(arr) < 3:
        return []
    indices = []
    count = 1
    for i in range(2, len(arr)):
        if (arr[i] - arr[i - 1]) * (arr[i - 1] - arr[i - 2]) < 0:
            count += 1
        else:
            count = 1
        if count >= alt_length - 1:
            indices.extend(range(i - alt_length + 1, i + 1))
    return sorted(set(indices))


def _detect_n_of_m_beyond(arr, mean, std, n_points, m_window, sigma) -> List[int]:
    """Rule 5/6: M개 중 N개가 같은 쪽 Nσ 초과"""
    indices = []
    upper = mean + sigma * std
    lower = mean - sigma * std

    for i in range(m_window - 1, len(arr)):
        window = arr[i - m_window + 1: i + 1]
        above_count = sum(1 for v in window if v > upper)
        below_count = sum(1 for v in window if v < lower)
        if above_count >= n_points or below_count >= n_points:
            indices.extend(range(i - m_window + 1, i + 1))
    return sorted(set(indices))


def _detect_within_sigma(arr, mean, std, run_length=15, sigma=1) -> List[int]:
    """Rule 7: 연속 N개가 ±Nσ 이내"""
    indices = []
    upper = mean + sigma * std
    lower = mean - sigma * std
    count = 0
    for i in range(len(arr)):
        if lower <= arr[i] <= upper:
            count += 1
        else:
            count = 0
        if count >= run_length:
            indices.extend(range(i - run_length + 1, i + 1))
    return sorted(set(indices))


def _detect_beyond_sigma_both(arr, mean, std, run_length=8, sigma=1) -> List[int]:
    """Rule 8: 연속 N개가 ±Nσ 밖 (양쪽 모두)"""
    indices = []
    upper = mean + sigma * std
    lower = mean - sigma * std
    count = 0
    for i in range(len(arr)):
        if arr[i] > upper or arr[i] < lower:
            count += 1
        else:
            count = 0
        if count >= run_length:
            indices.extend(range(i - run_length + 1, i + 1))
    return sorted(set(indices))


# ──────────────────────────────────────────────
# Plotly 관리도 시각화
# ──────────────────────────────────────────────

def build_nelson_chart(
    values: list,
    result: NelsonAnalysisResult,
    process_name: str = "",
) -> go.Figure:
    """Nelson Rule 위반이 표시된 관리도 차트"""

    x = list(range(len(values)))
    arr = np.array(values)

    # 위반 인덱스 수집
    violation_idx = set()
    for v in result.violations:
        violation_idx.update(v.violating_indices)

    normal_x = [i for i in x if i not in violation_idx]
    normal_y = [values[i] for i in normal_x]
    viol_x = [i for i in x if i in violation_idx]
    viol_y = [values[i] for i in viol_x]

    fig = go.Figure()

    # ±1σ/±2σ 배경 밴드
    fig.add_hrect(y0=result.sigma_2_lower, y1=result.sigma_2_upper,
                  fillcolor="rgba(76,175,80,0.08)", line_width=0)
    fig.add_hrect(y0=result.sigma_1_lower, y1=result.sigma_1_upper,
                  fillcolor="rgba(76,175,80,0.12)", line_width=0)

    # UCL/CL/LCL
    fig.add_hline(y=result.ucl, line=dict(color="#D32F2F", dash="dash", width=1),
                  annotation_text="UCL (3σ)", annotation_position="top right")
    fig.add_hline(y=result.mean, line=dict(color="#1976D2", width=1),
                  annotation_text="CL (Mean)", annotation_position="top right")
    fig.add_hline(y=result.lcl, line=dict(color="#D32F2F", dash="dash", width=1),
                  annotation_text="LCL (-3σ)", annotation_position="bottom right")

    # 정상 포인트
    fig.add_trace(go.Scatter(
        x=normal_x, y=normal_y, mode="markers+lines",
        marker=dict(color="#1976D2", size=5),
        line=dict(color="#1976D2", width=1),
        name="정상", hovertemplate="Point %{x}: %{y:.4f}<extra></extra>",
    ))

    # 위반 포인트
    if viol_x:
        fig.add_trace(go.Scatter(
            x=viol_x, y=viol_y, mode="markers",
            marker=dict(color="#D32F2F", size=10, symbol="x"),
            name="위반", hovertemplate="VIOLATION Point %{x}: %{y:.4f}<extra></extra>",
        ))

    title = f"Nelson Rule 관리도"
    if process_name:
        title += f" — {process_name}"
    if result.violations:
        title += f" (위반 {result.violation_count}건)"

    fig.update_layout(
        title=dict(text=title, font=dict(size=13)),
        xaxis_title="Sample #",
        yaxis_title="Value",
        height=350,
        margin=dict(l=10, r=10, t=40, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )

    try:
        from ui.plotly_theme import apply_theme
        apply_theme(fig)
    except Exception:
        pass

    return fig
