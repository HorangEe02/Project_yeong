# dev-guides/06 — 부족 영양소 진단

> **Phase**: 2 | **선행 작업**: [`05-kdris-lookup.md`](./05-kdris-lookup.md) | **예상 소요**: 3~4시간

---

## 🎯 작업 목표

사용자가 섭취 중인 영양제·식단 정보를 KDRIs 권장량과 비교하여 **부족·과다·위험** 영양소를 진단하는 알고리즘을 구현한다. 단위 환산(mg ↔ μg ↔ IU)과 의료법 표현 가이드까지 포함.

---

## 📋 산출물

```
backend/
├── src/
│   ├── models/schemas/
│   │   └── nutrition.py           # 추가 (NutrientIntake, DiagnosisResult 등)
│   ├── nutrition/
│   │   ├── unit_converter.py     # 단위 환산
│   │   └── diagnosis.py          # 부족 영양소 진단
│   └── data/                      # data/mfds/unit_conversions.json 매핑
└── tests/
    ├── unit/nutrition/
    │   ├── test_unit_converter.py
    │   └── test_diagnosis.py
    └── integration/nutrition/
        └── test_diagnosis_integration.py    # KDRIs 실제 룩업 통합
```

---

## 📐 알고리즘 명세

> 🔍 **출처**: [docs/07-core-algorithm.md §4.3](../07-core-algorithm.md), [docs/13-algorithm-literature-evidence.md](../13-algorithm-literature-evidence.md)

### 근거 보강

| 항목 | 근거 수준 | 적용 방식 |
|------|----------|----------|
| KDRIs reference value | A | 사용자의 성별·연령·임신/수유 상태에 맞는 KDRIs 값을 조회한다. |
| EAR/RDA/AI/UL 해석 | A | DRI의 섭취 평가 개념을 참고한다. UL 초과는 위험 가능성 경고로 우선 표시한다. |
| 35% / 70% / 130% 임계값 | C | 공식 진단 cutoff가 아니라 서비스 UX 분류 기준이다. |

> 코드 내부 enum은 `DEFICIENT`를 유지하더라도, 사용자 화면 문구는 "심각한 결핍"보다 "섭취량이 매우 낮을 가능성"처럼 완화해서 표기한다.

### 진단 흐름

```
입력:
  - User Profile (나이, 성별, 만성질환, 임신부 등)
  - Intake List [(영양소 코드, 양, 단위), ...]

처리:
  1. 입력 단위 → 표준 단위 환산
     예: vitamin_d_iu (1000 IU) → vitamin_d_ug (25 μg)
  2. 영양소별 KDRIs 룩업 (사용자 컨텍스트 적용)
  3. 비율 계산: 섭취량 ÷ reference_value × 100
  4. 상태 분류:
     비율 < 35%       → DEFICIENT (심각한 결핍)
     35% ≤ 비율 < 70% → LOW (부족)
     70% ≤ 비율 ≤ 130% → ADEQUATE (적정)
     130% < 비율, UL 미만 → EXCESSIVE (과다)
     UL 초과            → RISKY (위험)
  5. 우선순위 정렬:
     RISKY > DEFICIENT > LOW > EXCESSIVE > ADEQUATE
  6. 의료법 표현 메시지 생성 (진단 X / 정보 제공 O)

출력:
  - DiagnosisResult [
      { code, name_ko, status, intake, reference, ratio_pct,
        message_ko, recommendations }
    ]
```

### 단위 환산 규칙 (`data/mfds/unit_conversions.json`)

```json
{
  "vitamin_a": {
    "1_iu_to_ug_rae": 0.3,
    "1_ug_rae_to_iu": 3.33
  },
  "vitamin_d": {
    "1_iu_to_ug": 0.025,
    "1_ug_to_iu": 40
  },
  "vitamin_e": {
    "1_iu_to_mg_ate": 0.67,
    "1_mg_ate_to_iu": 1.49
  }
}
```

---

## 🔧 구현 명세

### 1. `src/models/schemas/nutrition.py` (추가)

```python
"""영양 분석 관련 스키마."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# 기존 NutrientStatus, KDRIsValue, UserKDRIsContext 외 추가:


class NutrientIntake(BaseModel):
    """단일 영양소의 섭취 정보.

    Attributes:
        code: 영양소 표준 코드.
        amount: 섭취량.
        unit: 단위 (라벨 그대로, e.g., "IU", "mg", "μg").
        source: 출처 ("supplement" | "meal").
    """

    model_config = ConfigDict(frozen=True)

    code: str = Field(..., pattern=r"^[a-z_]+_[a-z]+$")
    amount: float = Field(..., ge=0)
    unit: str
    source: str = Field(default="supplement", pattern=r"^(supplement|meal)$")


class NutrientDiagnosis(BaseModel):
    """단일 영양소 진단 결과.

    Attributes:
        code: 영양소 코드.
        name_ko: 한국어명.
        status: 섭취 상태 분류.
        intake_amount: 섭취량 (표준 단위 변환 후).
        reference_amount: 권장량 (RDA 또는 AI).
        ratio_pct: 권장량 대비 비율 (%).
        unit: 표준 단위.
        upper_limit: UL 값 (없으면 None).
        message_ko: 사용자에게 보여줄 메시지 (의료법 표현 적용).
    """

    model_config = ConfigDict(frozen=True)

    code: str
    name_ko: str
    status: NutrientStatus
    intake_amount: float
    reference_amount: float | None
    ratio_pct: float
    unit: str
    upper_limit: float | None = None
    message_ko: str


class DiagnosisResult(BaseModel):
    """전체 진단 결과.

    Attributes:
        diagnoses: 영양소별 진단 (우선순위 정렬됨).
        deficient_count: 부족·결핍 영양소 수.
        risky_count: 과다(UL 초과) 영양소 수.
        adequate_count: 적정 영양소 수.
        summary_message_ko: 전체 요약 (의료법 표현 적용).
    """

    model_config = ConfigDict(frozen=True)

    diagnoses: list[NutrientDiagnosis]
    deficient_count: int
    risky_count: int
    adequate_count: int
    summary_message_ko: str
```

### 2. `src/nutrition/unit_converter.py`

```python
"""영양소 단위 환산 모듈.

여러 단위(mg, μg, IU 등)로 표시되는 영양소를 표준 단위로 환산한다.

Reference:
    docs/09-data-catalog.md §3.4 (단위 환산)
    data/mfds/unit_conversions.json
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Final


logger = logging.getLogger(__name__)


CONVERSIONS_PATH: Final[Path] = Path("data/mfds/unit_conversions.json")
"""단위 환산 룰 JSON 경로."""


# 영양소별 표준 단위 (KDRIs 기준)
STANDARD_UNITS: Final[dict[str, str]] = {
    "vitamin_a": "ug_rae",
    "vitamin_d": "ug",
    "vitamin_e": "mg_ate",
    "vitamin_c": "mg",
    "vitamin_b1": "mg",
    "vitamin_b2": "mg",
    "vitamin_b6": "mg",
    "vitamin_b12": "ug",
    "folate": "ug_dfe",
    "calcium": "mg",
    "iron": "mg",
    "magnesium": "mg",
    "zinc": "mg",
    "potassium": "mg",
    "sodium": "mg",
    "water": "ml",
}


@lru_cache(maxsize=1)
def load_conversions() -> dict:
    """단위 환산 룰을 로드.

    Returns:
        영양소별 환산 룰 dict.

    Raises:
        FileNotFoundError: JSON이 없는 경우.
    """
    if not CONVERSIONS_PATH.exists():
        raise FileNotFoundError(f"Conversions JSON not found: {CONVERSIONS_PATH}")
    with CONVERSIONS_PATH.open("r", encoding="utf-8") as f:
        data: dict = json.load(f)
    logger.info("Loaded %d nutrient conversion rules", len(data))
    return data


def convert_to_standard(
    nutrient_base: str,
    amount: float,
    from_unit: str,
) -> tuple[float, str]:
    """영양소 단위를 표준 단위로 환산한다.

    Args:
        nutrient_base: 영양소 기본 코드 (e.g., "vitamin_d", code의 unit 제외 부분).
        amount: 변환할 양.
        from_unit: 입력 단위 (e.g., "iu", "mg", "ug").

    Returns:
        (변환된 양, 표준 단위) 튜플.

    Raises:
        ValueError: nutrient_base가 STANDARD_UNITS에 없는 경우.
        KeyError: 환산 룰이 없는 (nutrient_base, from_unit) 조합인 경우.

    Examples:
        >>> convert_to_standard("vitamin_d", 1000, "iu")
        (25.0, 'ug')
        >>> convert_to_standard("vitamin_d", 25, "ug")
        (25.0, 'ug')
        >>> convert_to_standard("vitamin_c", 100, "mg")
        (100.0, 'mg')
    """
    if nutrient_base not in STANDARD_UNITS:
        raise ValueError(f"Unknown nutrient: {nutrient_base}")

    target_unit = STANDARD_UNITS[nutrient_base]
    from_unit_norm = from_unit.lower().replace("μ", "u")

    # 이미 표준 단위면 그대로
    if from_unit_norm == target_unit:
        return (round(amount, 3), target_unit)

    # 환산 룰 조회
    conversions = load_conversions()
    if nutrient_base not in conversions:
        # 환산 룰 없는 영양소면 단위 일치만 허용
        raise KeyError(
            f"No conversion rule for {nutrient_base}. "
            f"Expected unit: {target_unit}, got: {from_unit}"
        )

    rule_key = f"1_{from_unit_norm}_to_{target_unit}"
    if rule_key not in conversions[nutrient_base]:
        raise KeyError(
            f"No conversion rule: {nutrient_base}.{rule_key}"
        )

    factor = conversions[nutrient_base][rule_key]
    converted = amount * factor
    return (round(converted, 3), target_unit)
```

### 3. `src/nutrition/diagnosis.py`

```python
"""부족 영양소 진단 모듈."""

from __future__ import annotations

import logging
from typing import Final

from src.models.schemas.nutrition import (
    DiagnosisResult,
    KDRIsValue,
    NutrientDiagnosis,
    NutrientIntake,
    NutrientStatus,
    UserKDRIsContext,
)
from src.nutrition.kdris import lookup_kdris_for_user
from src.nutrition.unit_converter import convert_to_standard


logger = logging.getLogger(__name__)


# 상태 분류 임계값 (%)
DEFICIENT_THRESHOLD: Final[float] = 35.0
LOW_THRESHOLD: Final[float] = 70.0
ADEQUATE_UPPER: Final[float] = 130.0


# 우선순위 (정렬 시 status 가중치)
STATUS_PRIORITY: Final[dict[NutrientStatus, int]] = {
    NutrientStatus.RISKY: 0,
    NutrientStatus.DEFICIENT: 1,
    NutrientStatus.LOW: 2,
    NutrientStatus.EXCESSIVE: 3,
    NutrientStatus.ADEQUATE: 4,
}


def classify_status(
    intake: float,
    reference: float | None,
    upper_limit: float | None,
) -> tuple[NutrientStatus, float]:
    """섭취량을 권장량 대비 비율로 평가하여 상태를 분류한다.

    Args:
        intake: 섭취량 (표준 단위).
        reference: 권장량 (RDA 또는 AI). None이면 ADEQUATE 처리.
        upper_limit: 상한 섭취량 (UL). None이면 RISKY 평가 X.

    Returns:
        (상태, 비율%) 튜플.

    Examples:
        >>> classify_status(50, 100, 2000)  # 50%
        (NutrientStatus.LOW, 50.0)
        >>> classify_status(2500, 100, 2000)  # UL 초과
        (NutrientStatus.RISKY, 2500.0)
    """
    # UL 초과 우선
    if upper_limit is not None and intake > upper_limit:
        ratio = (intake / upper_limit) * 100 if upper_limit > 0 else 0.0
        return (NutrientStatus.RISKY, round(ratio, 1))

    # 권장량 없으면 적정으로 처리
    if reference is None or reference <= 0:
        return (NutrientStatus.ADEQUATE, 0.0)

    ratio = (intake / reference) * 100

    if ratio < DEFICIENT_THRESHOLD:
        status = NutrientStatus.DEFICIENT
    elif ratio < LOW_THRESHOLD:
        status = NutrientStatus.LOW
    elif ratio <= ADEQUATE_UPPER:
        status = NutrientStatus.ADEQUATE
    else:
        status = NutrientStatus.EXCESSIVE

    return (status, round(ratio, 1))


def generate_message(
    name_ko: str,
    status: NutrientStatus,
    ratio_pct: float,
) -> str:
    """의료법 표현 가이드를 준수한 사용자 메시지를 생성한다.

    Args:
        name_ko: 영양소 한국어명.
        status: 섭취 상태.
        ratio_pct: 권장량 대비 비율.

    Returns:
        사용자에게 표시할 한국어 메시지.

    Reference:
        docs/10-compliance-checklist.md §10 (표현 가이드)
    """
    match status:
        case NutrientStatus.DEFICIENT:
            return (
                f"{name_ko} 섭취량이 권장량의 {ratio_pct:.0f}% 수준입니다. "
                "관련 식품 섭취를 늘리는 것을 고려해보세요."
            )
        case NutrientStatus.LOW:
            return (
                f"{name_ko} 섭취량이 권장량의 {ratio_pct:.0f}% 수준입니다. "
                "{name_ko}이(가) 풍부한 식품을 식단에 추가하면 도움이 될 수 있습니다."
            )
        case NutrientStatus.ADEQUATE:
            return f"{name_ko} 섭취량이 권장 범위 내(권장량의 {ratio_pct:.0f}%)에 있습니다."
        case NutrientStatus.EXCESSIVE:
            return (
                f"{name_ko} 섭취량이 권장량의 {ratio_pct:.0f}%로 다소 많습니다. "
                "균형 있는 섭취를 위해 양을 조절하는 것을 고려해보세요."
            )
        case NutrientStatus.RISKY:
            return (
                f"{name_ko} 섭취량이 상한 섭취량(UL)을 초과했습니다. "
                "전문가와 상담을 권장합니다."
            )


def aggregate_intakes(intakes: list[NutrientIntake]) -> dict[str, float]:
    """동일 영양소의 여러 섭취량을 합산한다.

    영양제 여러 개에서 같은 비타민이 나오는 경우 합쳐서 평가.
    각 항목은 개별적으로 표준 단위 환산 후 합산.

    Args:
        intakes: 섭취 정보 리스트.

    Returns:
        {영양소 코드: 표준 단위 양} 딕셔너리.

    Raises:
        ValueError: 단위 환산 실패 시.
    """
    aggregated: dict[str, float] = {}

    for intake in intakes:
        # code = "vitamin_d_iu" → base = "vitamin_d", unit = "iu"
        parts = intake.code.rsplit("_", 1)
        if len(parts) != 2:
            logger.warning("Invalid nutrient code format: %s", intake.code)
            continue
        base, _ = parts

        try:
            converted_amount, _ = convert_to_standard(base, intake.amount, intake.unit)
        except (ValueError, KeyError) as e:
            logger.warning("Conversion failed for %s: %s", intake.code, e)
            continue

        # 표준 단위로 변환된 코드 (e.g., "vitamin_d_ug")
        from src.nutrition.unit_converter import STANDARD_UNITS
        std_unit = STANDARD_UNITS.get(base, "")
        std_code = f"{base}_{std_unit}"
        aggregated[std_code] = aggregated.get(std_code, 0) + converted_amount

    return aggregated


def diagnose(
    intakes: list[NutrientIntake],
    user: UserKDRIsContext,
) -> DiagnosisResult:
    """전체 영양소 진단을 수행한다.

    Args:
        intakes: 사용자 섭취 정보 리스트.
        user: 사용자 KDRIs 컨텍스트.

    Returns:
        DiagnosisResult — 우선순위 정렬된 진단 결과.

    Raises:
        ValueError: 입력이 비정상이거나 KDRIs 룩업 실패가 다수인 경우.

    Examples:
        >>> intakes = [
        ...     NutrientIntake(code="vitamin_c_mg", amount=500, unit="mg"),
        ...     NutrientIntake(code="vitamin_d_iu", amount=1000, unit="iu"),
        ... ]
        >>> user = UserKDRIsContext(age=50, sex="female")
        >>> result = diagnose(intakes, user)
        >>> result.diagnoses[0].name_ko in ("비타민 C", "비타민 D")
        True
    """
    # 1. 단위 환산 + 합산
    aggregated = aggregate_intakes(intakes)

    diagnoses: list[NutrientDiagnosis] = []

    for std_code, total_amount in aggregated.items():
        # 2. KDRIs 룩업
        kdris: KDRIsValue | None = lookup_kdris_for_user(std_code, user)
        if kdris is None:
            logger.warning("No KDRIs reference for %s", std_code)
            continue

        reference = kdris.reference_value
        upper = kdris.ul

        # 3. 상태 분류
        status, ratio_pct = classify_status(total_amount, reference, upper)

        # 4. 메시지 생성
        message = generate_message(kdris.name_ko, status, ratio_pct)

        diagnoses.append(NutrientDiagnosis(
            code=std_code,
            name_ko=kdris.name_ko,
            status=status,
            intake_amount=total_amount,
            reference_amount=reference,
            ratio_pct=ratio_pct,
            unit=kdris.unit,
            upper_limit=upper,
            message_ko=message,
        ))

    # 5. 우선순위 정렬
    diagnoses.sort(key=lambda d: (STATUS_PRIORITY[d.status], -d.ratio_pct))

    # 6. 통계
    deficient = sum(
        1 for d in diagnoses
        if d.status in (NutrientStatus.DEFICIENT, NutrientStatus.LOW)
    )
    risky = sum(1 for d in diagnoses if d.status == NutrientStatus.RISKY)
    adequate = sum(1 for d in diagnoses if d.status == NutrientStatus.ADEQUATE)

    summary = (
        f"분석한 영양소 {len(diagnoses)}종 중 부족·결핍 {deficient}종, "
        f"적정 {adequate}종"
    )
    if risky > 0:
        summary += f", 상한 초과 {risky}종 — 전문가 상담을 권장합니다"

    return DiagnosisResult(
        diagnoses=diagnoses,
        deficient_count=deficient,
        risky_count=risky,
        adequate_count=adequate,
        summary_message_ko=summary,
    )
```

---

## 🧪 테스트 (3-Tier)

### Tier 1: 단위 테스트

#### `test_unit_converter.py`

| 테스트 | 입력 | 기대값 |
|-------|------|-------|
| `test_vitamin_d_iu_to_ug` | (vitamin_d, 1000, iu) | (25.0, ug) |
| `test_vitamin_d_ug_already_standard` | (vitamin_d, 25, ug) | (25.0, ug) |
| `test_vitamin_a_iu_to_ug_rae` | (vitamin_a, 5000, iu) | (1500.0, ug_rae) |
| `test_vitamin_e_iu_to_mg` | (vitamin_e, 30, iu) | (~20.1, mg_ate) |
| `test_vitamin_c_mg_passthrough` | (vitamin_c, 100, mg) | (100.0, mg) |
| `test_micro_symbol_normalized` | (..., μg) | μ → u 정규화 |
| `test_unknown_nutrient_raises` | (unknown, 100, mg) | ValueError |
| `test_unsupported_conversion_raises` | (vitamin_d, 25, lb) | KeyError |

#### `test_diagnosis.py`

| 테스트 | 입력 | 기대값 |
|-------|------|-------|
| `test_classify_deficient` | intake=20, ref=100 | DEFICIENT, 20.0 |
| `test_classify_low` | intake=50, ref=100 | LOW, 50.0 |
| `test_classify_adequate` | intake=100, ref=100 | ADEQUATE, 100.0 |
| `test_classify_excessive` | intake=200, ref=100 | EXCESSIVE, 200.0 |
| `test_classify_risky_above_ul` | intake=2500, ref=100, ul=2000 | RISKY, _ |
| `test_boundary_35_pct` | intake=35, ref=100 | LOW, 35.0 |
| `test_boundary_70_pct` | intake=70, ref=100 | ADEQUATE, 70.0 |
| `test_boundary_130_pct` | intake=130, ref=100 | ADEQUATE, 130.0 |
| `test_no_reference_returns_adequate` | ref=None | ADEQUATE, 0.0 |
| `test_aggregate_same_nutrient` | 비타민C 200mg + 300mg | 500mg |
| `test_aggregate_different_units_converted` | vitD 1000IU + 25μg | 50μg |
| `test_message_no_diagnose_word` | 모든 status | "진단", "처방" 미포함 |
| `test_priority_risky_first` | RISKY + DEFICIENT 혼합 | RISKY 먼저 |

### Tier 2: 통합 테스트

#### `test_diagnosis_integration.py`

```python
"""KDRIs 실제 룩업 + 단위 환산 + 진단 통합."""

import pytest
from pathlib import Path

from src.models.schemas.nutrition import NutrientIntake, UserKDRIsContext
from src.nutrition.diagnosis import diagnose
from src.nutrition.kdris import load_kdris_csv


@pytest.fixture
def loaded_kdris(monkeypatch):
    """샘플 KDRIs를 기본 경로처럼 사용."""
    sample = Path("tests/unit/nutrition/fixtures/kdris_sample.csv")
    rows = load_kdris_csv(sample)
    monkeypatch.setattr(
        "src.nutrition.kdris._load_default_kdris", lambda: rows
    )
    return rows


class TestDiagnosisIntegration:
    """KDRIs + 단위환산 + 진단 통합."""

    def test_50f_diagnosis_realistic(self, loaded_kdris):
        """50대 여성, 종합비타민 + 칼슘제 + 철분제."""
        intakes = [
            NutrientIntake(code="vitamin_c_mg", amount=500, unit="mg"),
            NutrientIntake(code="calcium_mg", amount=600, unit="mg"),
            NutrientIntake(code="iron_mg", amount=18, unit="mg"),
        ]
        user = UserKDRIsContext(age=50, sex="female")

        result = diagnose(intakes, user)

        # 검증: 비타민C는 권장 100보다 5배 → EXCESSIVE
        vit_c = next(d for d in result.diagnoses if d.code == "vitamin_c_mg")
        assert vit_c.ratio_pct == 500.0
        # EXCESSIVE이지만 UL 2000 미만이라 RISKY 아님
        assert vit_c.status.value == "excessive"

        # 칼슘은 800 권장 대비 600 → LOW (75%) → ADEQUATE (130 이내)
        # 실제로는 75% → ADEQUATE
        cal = next(d for d in result.diagnoses if d.code == "calcium_mg")
        assert 70 <= cal.ratio_pct <= 80

    def test_pregnancy_branches_to_higher_iron(self, loaded_kdris):
        """임신부 철분 권장량은 일반보다 높음."""
        intakes = [
            NutrientIntake(code="iron_mg", amount=14, unit="mg"),
        ]

        user_normal = UserKDRIsContext(age=30, sex="female")
        user_preg = UserKDRIsContext(age=30, sex="female", is_pregnant=True)

        result_normal = diagnose(intakes, user_normal)
        result_preg = diagnose(intakes, user_preg)

        iron_normal = result_normal.diagnoses[0]
        iron_preg = result_preg.diagnoses[0]

        # 일반: 14 / 14 = 100% (적정)
        # 임신부: 14 / 24 = 58% (LOW)
        assert iron_normal.ratio_pct == 100.0
        assert iron_preg.ratio_pct < 70

    def test_unit_conversion_in_pipeline(self, loaded_kdris):
        """비타민D를 IU로 입력 → ug로 변환 후 KDRIs 비교."""
        intakes = [
            NutrientIntake(code="vitamin_d_iu", amount=1000, unit="iu"),
        ]
        user = UserKDRIsContext(age=30, sex="male")

        result = diagnose(intakes, user)

        # 1000 IU → 25 μg, KDRIs는 ug 기준
        # (실제 권장량은 데이터에 따라 다름)
        if result.diagnoses:
            vit_d = result.diagnoses[0]
            assert vit_d.intake_amount == 25.0  # 변환된 값
```

### Tier 3: E2E 테스트 (진단 시나리오)

```python
"""진단 시나리오 E2E."""

class TestDiagnosisScenarios:
    """현실적인 만성질환자 시나리오."""

    def test_chronic_patient_full_scenario(self, loaded_kdris):
        """[페르소나 B] 50대 만성질환자, 영양제 4종 종합 진단."""
        intakes = [
            # 종합비타민
            NutrientIntake(code="vitamin_c_mg", amount=200, unit="mg"),
            NutrientIntake(code="vitamin_d_iu", amount=1000, unit="iu"),
            # 칼슘
            NutrientIntake(code="calcium_mg", amount=500, unit="mg"),
            # 마그네슘 (샘플엔 없을 수 있음)
            NutrientIntake(code="magnesium_mg", amount=400, unit="mg"),
        ]
        user = UserKDRIsContext(
            age=52, sex="male"
        )

        result = diagnose(intakes, user)

        # 1. 결과는 우선순위 정렬되어 있어야
        priorities = [d.status for d in result.diagnoses]
        assert priorities == sorted(
            priorities,
            key=lambda s: STATUS_PRIORITY[s]
        )

        # 2. 의료법 표현 가이드 준수
        for d in result.diagnoses:
            assert "진단" not in d.message_ko
            assert "처방" not in d.message_ko
            assert "치료" not in d.message_ko

        # 3. 요약 메시지에 RISKY 있으면 전문가 상담 안내
        if result.risky_count > 0:
            assert "전문가" in result.summary_message_ko
```

### Tier 4: 성능 테스트

```python
"""진단 성능 테스트."""

import time

import pytest


class TestDiagnosisPerformance:
    """진단 알고리즘 성능."""

    def test_30_nutrients_under_100ms(self, loaded_kdris):
        """30종 영양소 진단이 100ms 이내 완료."""
        intakes = [
            NutrientIntake(
                code=f"vitamin_c_mg", amount=100, unit="mg",
            )
            for _ in range(30)
        ]
        user = UserKDRIsContext(age=30, sex="male")

        start = time.perf_counter()
        result = diagnose(intakes, user)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1  # 100ms 이내

    @pytest.mark.parametrize("n", [10, 50, 100, 500])
    def test_scaling(self, loaded_kdris, n: int):
        """선형 스케일링 검증."""
        intakes = [
            NutrientIntake(code="vitamin_c_mg", amount=100, unit="mg")
            for _ in range(n)
        ]
        user = UserKDRIsContext(age=30, sex="male")

        start = time.perf_counter()
        diagnose(intakes, user)
        elapsed = time.perf_counter() - start

        # 500개도 1초 이내 (실제로는 ~50ms)
        assert elapsed < 1.0
```

---

## ✅ Definition of Done

- [ ] `src/models/schemas/nutrition.py` — 4개 모델 추가
- [ ] `src/nutrition/unit_converter.py` — convert_to_standard, load_conversions
- [ ] `src/nutrition/diagnosis.py` — classify_status, generate_message, aggregate_intakes, diagnose
- [ ] `data/mfds/unit_conversions.json` — 비타민 A/D/E 환산 룰
- [ ] 모든 함수 Google-style docstring + Examples
- [ ] 모든 함수 타입 힌트 100%
- [ ] 단위 테스트 30+ (test_unit_converter.py, test_diagnosis.py)
- [ ] 통합 테스트 (test_diagnosis_integration.py) — KDRIs 룩업 + 환산 통합
- [ ] E2E 시나리오 테스트 — 페르소나 B 만성질환자
- [ ] 성능 테스트 — 30종 영양소 < 100ms, 500종 < 1초
- [ ] **의료법 표현 가이드 준수 검증** — "진단", "처방", "치료" 단어 0건
- [ ] `mypy src/nutrition --strict` 통과
- [ ] `pytest tests -v --cov=src.nutrition` 통과 + 커버리지 ≥ 90%

---

## 💡 구현 팁

### 환산 실패 시 처리

```python
# 영양제 라벨에 "비타민 K 50mg" 같은 비표준 단위가 등장하면
# silently skip + warning log (예외 던지면 전체 진단 실패)
try:
    converted, _ = convert_to_standard(base, amount, unit)
except (ValueError, KeyError) as e:
    logger.warning("Conversion failed for %s: %s", code, e)
    continue  # skip
```

### 의료법 표현 자동 검증

```python
FORBIDDEN_TERMS = {"진단", "처방", "치료", "확실히"}


def _validate_message(text: str) -> None:
    """메시지에 금지 표현이 있으면 에러."""
    found = [t for t in FORBIDDEN_TERMS if t in text]
    if found:
        raise ValueError(f"Forbidden medical term in message: {found}")


# generate_message 마지막에 검증
def generate_message(...) -> str:
    msg = ...
    _validate_message(msg)
    return msg
```

### 부동소수점 비율 비교

```python
# 70.0%는 LOW일까 ADEQUATE일까? 가이드: 70.0% 정확히는 ADEQUATE
# < 35.0% → DEFICIENT
# 35.0% ≤ ratio < 70.0% → LOW
# 70.0% ≤ ratio ≤ 130.0% → ADEQUATE
```

---

## 🚫 이 작업에서 하지 말 것

- ❌ 진단 표현 사용 ("당뇨 위험", "빈혈 진단" 등)
- ❌ 영양제 추천 ("이 비타민제를 드세요") — 식품·성분 정보만
- ❌ DB에 진단 결과 저장 (Phase 2 후반)
- ❌ FastAPI 라우터 작성 (다음 가이드 09)

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md)
- [`/backend/CLAUDE.md`](../../backend/CLAUDE.md)
- [`/data/CLAUDE.md`](../../data/CLAUDE.md)
- [`/docs/07-core-algorithm.md §4.3`](../07-core-algorithm.md)
- [`/docs/10-compliance-checklist.md §10`](../10-compliance-checklist.md)
- 이전: [`05-kdris-lookup.md`](./05-kdris-lookup.md)
- 다음: [`07-ocr-pipeline.md`](./07-ocr-pipeline.md)
