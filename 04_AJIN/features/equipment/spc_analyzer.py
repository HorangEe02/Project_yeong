"""
SPC 분석 엔진 — Cpk/Ppk 자동 계산 + 관리도 데이터 생성

지원 분석:
  1. 기본 통계 (평균, 표준편차, 범위)
  2. 공정 능력 지수 (Cp, Cpk, Pp, Ppk)
  3. X-bar R 관리도 데이터
  4. 이상 포인트 감지
  5. LLM 자연어 해석
"""
import math
import logging
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SPCResult:
    """SPC 분석 결과"""
    n: int = 0
    mean: float = 0.0
    std: float = 0.0
    std_within: float = 0.0
    range_avg: float = 0.0
    minimum: float = 0.0
    maximum: float = 0.0

    usl: Optional[float] = None
    lsl: Optional[float] = None
    target: Optional[float] = None

    cp: Optional[float] = None
    cpk: Optional[float] = None
    pp: Optional[float] = None
    ppk: Optional[float] = None

    xbar_values: list = field(default_factory=list)
    r_values: list = field(default_factory=list)
    xbar_ucl: float = 0.0
    xbar_lcl: float = 0.0
    xbar_cl: float = 0.0
    r_ucl: float = 0.0
    r_cl: float = 0.0

    out_of_spec: list = field(default_factory=list)
    out_of_control: list = field(default_factory=list)

    is_capable: bool = False
    is_stable: bool = False
    grade: str = ""

    raw_data: list = field(default_factory=list)


# ── SPC 상수 (서브그룹 크기별) ──
SPC_CONSTANTS = {
    2: {"A2": 1.880, "d2": 1.128, "D3": 0, "D4": 3.267},
    3: {"A2": 1.023, "d2": 1.693, "D3": 0, "D4": 2.575},
    4: {"A2": 0.729, "d2": 2.059, "D3": 0, "D4": 2.282},
    5: {"A2": 0.577, "d2": 2.326, "D3": 0, "D4": 2.115},
    6: {"A2": 0.483, "d2": 2.534, "D3": 0, "D4": 2.004},
    7: {"A2": 0.419, "d2": 2.704, "D3": 0.076, "D4": 1.924},
    8: {"A2": 0.373, "d2": 2.847, "D3": 0.136, "D4": 1.864},
    9: {"A2": 0.337, "d2": 2.970, "D3": 0.184, "D4": 1.816},
    10: {"A2": 0.308, "d2": 3.078, "D3": 0.223, "D4": 1.777},
}


def analyze_spc(
    data: list[float],
    usl: float = None,
    lsl: float = None,
    target: float = None,
    subgroup_size: int = 5,
) -> SPCResult:
    """
    SPC 분석을 수행합니다.

    Args:
        data: 측정 데이터 리스트
        usl: 상한 규격
        lsl: 하한 규격
        target: 목표값
        subgroup_size: 서브그룹 크기 (기본 5)

    Returns:
        SPCResult 객체
    """
    result = SPCResult(raw_data=data, usl=usl, lsl=lsl, target=target)

    if not data or len(data) < subgroup_size:
        return result

    result.n = len(data)
    result.mean = sum(data) / len(data)
    result.minimum = min(data)
    result.maximum = max(data)

    # 전체 표준편차
    variance = sum((x - result.mean) ** 2 for x in data) / (len(data) - 1)
    result.std = math.sqrt(variance) if variance > 0 else 0

    # 서브그룹 계산
    constants = SPC_CONSTANTS.get(subgroup_size, SPC_CONSTANTS[5])
    subgroups = _make_subgroups(data, subgroup_size)

    if subgroups:
        result.xbar_values = [sum(sg) / len(sg) for sg in subgroups]
        result.r_values = [max(sg) - min(sg) for sg in subgroups]
        result.range_avg = sum(result.r_values) / len(result.r_values)

        d2 = constants["d2"]
        result.std_within = result.range_avg / d2 if d2 > 0 else result.std

        a2 = constants["A2"]
        d4 = constants["D4"]

        xbar_grand = sum(result.xbar_values) / len(result.xbar_values)
        result.xbar_cl = xbar_grand
        result.xbar_ucl = xbar_grand + a2 * result.range_avg
        result.xbar_lcl = xbar_grand - a2 * result.range_avg

        result.r_cl = result.range_avg
        result.r_ucl = d4 * result.range_avg

    # ── 공정 능력 지수 ──
    if usl is not None and lsl is not None:
        spec_range = usl - lsl

        if result.std_within > 0:
            result.cp = round(spec_range / (6 * result.std_within), 3)

        if result.std_within > 0:
            cpu = (usl - result.mean) / (3 * result.std_within)
            cpl = (result.mean - lsl) / (3 * result.std_within)
            result.cpk = round(min(cpu, cpl), 3)

        if result.std > 0:
            result.pp = round(spec_range / (6 * result.std), 3)

        if result.std > 0:
            ppu = (usl - result.mean) / (3 * result.std)
            ppl = (result.mean - lsl) / (3 * result.std)
            result.ppk = round(min(ppu, ppl), 3)

    elif usl is not None:
        if result.std_within > 0:
            result.cpk = round((usl - result.mean) / (3 * result.std_within), 3)

    elif lsl is not None:
        if result.std_within > 0:
            result.cpk = round((result.mean - lsl) / (3 * result.std_within), 3)

    # ── 이상 포인트 감지 ──
    if usl is not None:
        result.out_of_spec.extend([i for i, v in enumerate(data) if v > usl])
    if lsl is not None:
        result.out_of_spec.extend([i for i, v in enumerate(data) if v < lsl])

    for i, xb in enumerate(result.xbar_values):
        if xb > result.xbar_ucl or xb < result.xbar_lcl:
            result.out_of_control.append(i)

    # ── 판정 ──
    result.is_capable = (result.cpk or 0) >= 1.33
    result.is_stable = len(result.out_of_control) == 0

    cpk_val = result.cpk or 0
    if cpk_val >= 1.67:
        result.grade = "A"
    elif cpk_val >= 1.33:
        result.grade = "B"
    elif cpk_val >= 1.00:
        result.grade = "C"
    else:
        result.grade = "D"

    return result


def _make_subgroups(data: list, size: int) -> list[list]:
    """데이터를 서브그룹으로 분할합니다."""
    groups = []
    for i in range(0, len(data) - size + 1, size):
        groups.append(data[i:i + size])
    return groups


def generate_xbar_r_chart_data(result: SPCResult) -> dict:
    """Plotly 차트용 데이터를 생성합니다."""
    n_groups = len(result.xbar_values)
    x_labels = [f"G{i+1}" for i in range(n_groups)]

    return {
        "xbar": {
            "x": x_labels,
            "y": result.xbar_values,
            "ucl": result.xbar_ucl,
            "cl": result.xbar_cl,
            "lcl": result.xbar_lcl,
            "ooc": result.out_of_control,
        },
        "r": {
            "x": x_labels,
            "y": result.r_values,
            "ucl": result.r_ucl,
            "cl": result.r_cl,
        },
    }


def interpret_spc_result(result: SPCResult, llm_client=None) -> str:
    """SPC 결과를 자연어로 해석합니다."""
    lines = []

    grade_icons = {"A": "🟢", "B": "🔵", "C": "🟡", "D": "🔴"}
    icon = grade_icons.get(result.grade, "⚪")

    lines.append(f"{icon} **공정 능력 등급: {result.grade}**")

    if result.cpk is not None:
        lines.append(f"- Cpk = {result.cpk} {'(양호 >= 1.33)' if result.is_capable else '(부족 < 1.33)'}")
    if result.cp is not None:
        lines.append(f"- Cp = {result.cp}")
    if result.ppk is not None:
        lines.append(f"- Ppk = {result.ppk}")

    lines.append(f"- 데이터 수: {result.n}개")
    lines.append(f"- 평균: {result.mean:.4f}")
    lines.append(f"- 표준편차(군내): {result.std_within:.4f}")

    if result.out_of_spec:
        lines.append(f"- 규격 이탈: **{len(result.out_of_spec)}건**")
    if result.out_of_control:
        lines.append(f"- 관리 이탈(X-bar): **{len(result.out_of_control)}건**")
    if result.is_stable and result.is_capable:
        lines.append("- 공정 안정 + 공정 능력 충분")

    basic_interpretation = "\n".join(lines)

    if llm_client:
        try:
            prompt = f"""아래 SPC 분석 결과를 제조 현장 엔지니어에게 설명하세요.
개선 방향도 제안하세요.

{basic_interpretation}

규격: USL={result.usl}, LSL={result.lsl}
평균: {result.mean:.4f}, 표준편차: {result.std:.4f}
규격 이탈: {len(result.out_of_spec)}건
관리 이탈: {len(result.out_of_control)}건

간결하게 3~5문장으로 해석하세요."""

            llm_response = llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
                temperature=0.2,
                stream=False,
            )
            return basic_interpretation + f"\n\n### AI 분석\n{llm_response.strip()}"
        except Exception:
            pass

    return basic_interpretation


def parse_csv_data(csv_content: str, column: int = 0, skip_header: bool = True) -> list[float]:
    """CSV 문자열에서 측정 데이터를 추출합니다."""
    lines = csv_content.strip().split("\n")
    data = []
    for i, line in enumerate(lines):
        if skip_header and i == 0:
            continue
        parts = line.strip().split(",")
        if len(parts) > column:
            try:
                val = float(parts[column].strip())
                data.append(val)
            except ValueError:
                continue
    return data
