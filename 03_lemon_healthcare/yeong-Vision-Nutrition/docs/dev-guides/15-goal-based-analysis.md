# dev-guides/15 — 목적별 분석 (눈/간/피로)

> **Phase**: 3 | **선행 작업**: [`06-deficient-nutrient-diagnosis.md`](./06-deficient-nutrient-diagnosis.md) | **예상 소요**: 3~4시간

---

## 🎯 작업 목표

5종 출력 중 마지막 ⑤ 목적별 분석을 구현한다. 사용자가 "눈 건강", "간 건강", "피로 회복" 등 목적을 선택하면 관련 영양소 섭취 상태를 분석하고 식약처 인정 기능성 표시 기반 정보를 제공한다.

---

## 📋 산출물

```
backend/
├── src/nutrition/
│   ├── goal_analysis.py            # 목적별 분석 엔진
│   └── goal_definitions.py         # 목적·영양소 매핑
├── data/
│   └── reference/
│       └── health_goals.json       # 7가지 목적 정의
└── tests/
    ├── unit/nutrition/
    │   ├── test_goal_analysis.py
    │   └── test_goal_definitions.py
    └── integration/
        └── test_goal_analysis_integration.py
```

---

## 📐 알고리즘 명세

> 🔍 **출처**: [docs/07-core-algorithm.md §4.4](../07-core-algorithm.md), [docs/13-algorithm-literature-evidence.md](../13-algorithm-literature-evidence.md), 식약처·식품안전나라 건강기능식품 인정 기능성

### 근거 보강

| 항목 | 근거 수준 | 적용 방식 |
|------|----------|----------|
| 식약처 인정 기능성 문구 | A | 사용자 화면 문구의 1차 기준으로 사용한다. |
| AREDS2, 비타민 D, 오메가-3 등 논문 | B | 영양소-목적 매핑의 배경 근거로 사용하되 질병 예방·치료 주장으로 쓰지 않는다. 비타민 D와 감염 예방처럼 최신 근거가 혼재된 영역은 "면역 기능 유지에 필요" 수준으로 제한한다. |
| 목적별 weight 값 | C | 개인 맞춤 UX 점수 산출용 프로젝트 가중치다. 자문 전에는 효과 순위처럼 표현하지 않는다. |

> 기능성 원료는 "도움을 줄 수 있음" 수준의 문구로 제한한다. 사용자 질환, 약물, 임신·수유, 흡연 상태에 따라 주의 문구와 전문가 상담 안내를 표시한다.

### 7가지 목적 카테고리 (Phase 3 범위)

| 목적 | 코드 | 핵심 영양소 (식약처 인정) |
|------|------|----------------------|
| **눈 건강** | `eye_health` | 루테인, 지아잔틴, 비타민 A, DHA |
| **간 건강** | `liver_health` | 밀크씨슬, 비타민 B군, 비타민 E |
| **피로 회복** | `fatigue_recovery` | 비타민 B1, B2, B6, B12, 철분 |
| **면역력** | `immunity` | 비타민 C, 비타민 D, 아연, 셀레늄 |
| **혈행 개선** | `blood_circulation` | 오메가-3, 비타민 E, 코엔자임 Q10 |
| **장 건강** | `gut_health` | 식이섬유, 프로바이오틱스 |
| **뼈 건강** | `bone_health` | 칼슘, 비타민 D, 마그네슘, 비타민 K |

### 분석 흐름

```
입력:
  - 사용자가 선택한 목적 코드 (e.g., "eye_health")
  - 사용자 영양소 섭취 정보 (NutrientIntake 리스트)
  - 사용자 프로필 (KDRIs 컨텍스트)

처리:
  1. 목적 → 핵심 영양소 매핑 조회
  2. 각 핵심 영양소에 대해 부족 영양소 진단(06번) 호출
  3. 우선순위: 부족·결핍 > 부족 > 적정 순으로 표시
  4. 식약처 인정 기능성 표시 (의료법 표현 가이드 적용)
  5. 일반 식품 권장 (영양제 X)

출력:
  GoalAnalysisResult {
    goal_code, goal_name_ko,
    related_nutrients: [{ ...진단, recommended_foods }],
    summary_message_ko,
    food_recommendations: [...],
  }
```

### 식약처 인정 기능성 표시 예시

```
✅ 권장 표현 (식약처 인정 기능성):
  "루테인은 노화로 인해 감소될 수 있는 황반색소밀도를 유지하는 데 도움을 줄 수 있음"
  "비타민 C는 결합조직 형성과 기능 유지에 필요"

❌ 금지 표현:
  "이 영양소는 시력을 회복시킵니다"
  "간 질환을 치료합니다"
  "피로를 100% 없앱니다"
```

---

## 🔧 구현 명세

### 1. `data/reference/health_goals.json`

```json
{
  "eye_health": {
    "name_ko": "눈 건강",
    "name_en": "Eye Health",
    "description_ko": "장시간 화면 사용·노화로 인한 눈 피로 관리",
    "core_nutrients": [
      {
        "code": "lutein_mg",
        "weight": 1.0,
        "mfds_function_ko": "루테인은 노화로 인해 감소될 수 있는 황반색소밀도를 유지하는 데 도움을 줄 수 있음"
      },
      {
        "code": "vitamin_a_ug_rae",
        "weight": 0.8,
        "mfds_function_ko": "비타민 A는 어두운 곳에서 시각 적응에 필요"
      },
      {
        "code": "dha_mg",
        "weight": 0.6,
        "mfds_function_ko": "DHA는 망막 기능 유지에 필요"
      }
    ],
    "food_recommendations_ko": [
      "시금치, 케일 등 진한 녹색 잎채소 (루테인)",
      "당근, 고구마 (베타카로틴 → 비타민 A)",
      "고등어, 연어 등 등푸른생선 (DHA)"
    ]
  },
  "liver_health": {
    "name_ko": "간 건강",
    "name_en": "Liver Health",
    "description_ko": "간 기능 유지를 위한 영양 관리",
    "core_nutrients": [
      {
        "code": "vitamin_e_mg_ate",
        "weight": 0.8,
        "mfds_function_ko": "비타민 E는 유해산소로부터 세포 보호에 필요"
      },
      {
        "code": "vitamin_b1_mg",
        "weight": 0.7,
        "mfds_function_ko": "비타민 B1은 탄수화물·에너지 대사에 필요"
      },
      {
        "code": "vitamin_b2_mg",
        "weight": 0.7,
        "mfds_function_ko": "비타민 B2는 체내 에너지 생성에 필요"
      }
    ],
    "food_recommendations_ko": [
      "견과류 (비타민 E)",
      "통곡물 (비타민 B군)",
      "녹황색 채소"
    ]
  },
  "fatigue_recovery": {
    "name_ko": "피로 회복",
    "name_en": "Fatigue Recovery",
    "description_ko": "에너지 대사와 산소 운반에 필요한 영양 관리",
    "core_nutrients": [
      {
        "code": "vitamin_b1_mg",
        "weight": 1.0,
        "mfds_function_ko": "비타민 B1은 에너지 생산에 필요"
      },
      {
        "code": "vitamin_b6_mg",
        "weight": 0.8,
        "mfds_function_ko": "비타민 B6은 단백질·아미노산 대사에 필요"
      },
      {
        "code": "vitamin_b12_ug",
        "weight": 0.8,
        "mfds_function_ko": "비타민 B12는 정상적인 엽산 대사에 필요"
      },
      {
        "code": "iron_mg",
        "weight": 0.9,
        "mfds_function_ko": "철은 체내 산소 운반과 혈액 생성에 필요"
      }
    ],
    "food_recommendations_ko": [
      "현미, 통밀 (비타민 B1)",
      "바나나, 닭고기 (비타민 B6)",
      "달걀, 우유 (비타민 B12)",
      "시금치, 콩, 적색육 (철분)"
    ]
  },
  "immunity": { ... },
  "blood_circulation": { ... },
  "gut_health": { ... },
  "bone_health": { ... }
}
```

### 2. `src/nutrition/goal_definitions.py`

```python
"""목적별 분석 정의 로딩."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field


GOALS_PATH: Final[Path] = Path("data/reference/health_goals.json")


class GoalNutrient(BaseModel):
    """목적과 연관된 영양소.

    Attributes:
        code: 영양소 표준 코드.
        weight: 목적 내 가중치 (0.0~1.0, 핵심도).
        mfds_function_ko: 식약처 인정 기능성 표시 (한국어).
    """

    model_config = ConfigDict(frozen=True)

    code: str
    weight: float = Field(..., ge=0, le=1)
    mfds_function_ko: str


class HealthGoal(BaseModel):
    """건강 목적 정의.

    Attributes:
        code: 목적 코드.
        name_ko: 한국어명.
        name_en: 영어명.
        description_ko: 설명.
        core_nutrients: 핵심 영양소 리스트.
        food_recommendations_ko: 권장 식품.
    """

    model_config = ConfigDict(frozen=True)

    code: str
    name_ko: str
    name_en: str
    description_ko: str
    core_nutrients: list[GoalNutrient]
    food_recommendations_ko: list[str]


@lru_cache(maxsize=1)
def load_health_goals() -> dict[str, HealthGoal]:
    """건강 목적 정의 로드.

    Returns:
        {목적 코드: HealthGoal}.

    Raises:
        FileNotFoundError: JSON이 없는 경우.
    """
    if not GOALS_PATH.exists():
        raise FileNotFoundError(f"Health goals JSON not found: {GOALS_PATH}")
    with GOALS_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        code: HealthGoal(code=code, **goal_data)
        for code, goal_data in data.items()
    }


def get_goal(code: str) -> HealthGoal:
    """목적 코드로 정의 조회.

    Args:
        code: 목적 코드 (e.g., "eye_health").

    Returns:
        HealthGoal.

    Raises:
        ValueError: 정의되지 않은 코드인 경우.
    """
    goals = load_health_goals()
    if code not in goals:
        raise ValueError(f"Unknown goal code: {code}")
    return goals[code]


def list_goals() -> list[HealthGoal]:
    """모든 목적 리스트.

    Returns:
        HealthGoal 리스트.
    """
    return list(load_health_goals().values())
```

### 3. `src/nutrition/goal_analysis.py`

```python
"""목적별 영양 분석."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.models.schemas.nutrition import (
    NutrientDiagnosis,
    NutrientIntake,
    NutrientStatus,
    UserKDRIsContext,
)
from src.nutrition.diagnosis import diagnose
from src.nutrition.goal_definitions import GoalNutrient, HealthGoal, get_goal


class GoalNutrientAnalysis(BaseModel):
    """목적별 영양소 분석 항목.

    Attributes:
        diagnosis: 영양소 진단 (06번 결과).
        weight: 이 목적에서의 가중치.
        mfds_function_ko: 식약처 인정 기능성 표시.
    """

    model_config = ConfigDict(frozen=True)

    diagnosis: NutrientDiagnosis
    weight: float
    mfds_function_ko: str


class GoalAnalysisResult(BaseModel):
    """목적별 분석 전체 결과.

    Attributes:
        goal: 분석된 목적.
        related_nutrients: 핵심 영양소 분석 (가중치 정렬).
        deficient_count: 부족한 영양소 수.
        adequate_count: 적정 영양소 수.
        summary_message_ko: 사용자 메시지.
        food_recommendations_ko: 권장 식품.
    """

    model_config = ConfigDict(frozen=True)

    goal: HealthGoal
    related_nutrients: list[GoalNutrientAnalysis]
    deficient_count: int = Field(..., ge=0)
    adequate_count: int = Field(..., ge=0)
    summary_message_ko: str
    food_recommendations_ko: list[str]


def analyze_goal(
    goal_code: str,
    intakes: list[NutrientIntake],
    user: UserKDRIsContext,
) -> GoalAnalysisResult:
    """특정 목적과 관련된 영양소 섭취 상태 분석.

    Args:
        goal_code: 분석할 목적 코드.
        intakes: 사용자 섭취 정보.
        user: 사용자 KDRIs 컨텍스트.

    Returns:
        GoalAnalysisResult.

    Raises:
        ValueError: goal_code가 정의되지 않은 경우.

    Examples:
        >>> intakes = [...]
        >>> user = UserKDRIsContext(age=50, sex="female")
        >>> result = analyze_goal("fatigue_recovery", intakes, user)
        >>> result.goal.name_ko
        '피로 회복'
    """
    goal = get_goal(goal_code)

    # 1. 전체 진단 실행 (06번 모듈 활용)
    full_diagnosis = diagnose(intakes, user)
    diagnosis_by_code = {d.code: d for d in full_diagnosis.diagnoses}

    # 2. 핵심 영양소만 필터링
    related: list[GoalNutrientAnalysis] = []
    for goal_nutrient in goal.core_nutrients:
        diagnosis = diagnosis_by_code.get(goal_nutrient.code)
        if diagnosis is None:
            # 사용자가 섭취 X → 결핍으로 간주 (intake=0)
            # 또는 KDRIs 룩업 실패 시 스킵
            continue
        related.append(GoalNutrientAnalysis(
            diagnosis=diagnosis,
            weight=goal_nutrient.weight,
            mfds_function_ko=goal_nutrient.mfds_function_ko,
        ))

    # 3. 우선순위 정렬: 가중치 높은 + 부족한 영양소 우선
    related.sort(key=lambda x: (
        _status_priority(x.diagnosis.status),
        -x.weight,
    ))

    # 4. 통계
    deficient_count = sum(
        1 for r in related
        if r.diagnosis.status in (NutrientStatus.DEFICIENT, NutrientStatus.LOW)
    )
    adequate_count = sum(
        1 for r in related
        if r.diagnosis.status == NutrientStatus.ADEQUATE
    )

    # 5. 요약 메시지
    summary = _generate_summary(goal, deficient_count, len(related))

    return GoalAnalysisResult(
        goal=goal,
        related_nutrients=related,
        deficient_count=deficient_count,
        adequate_count=adequate_count,
        summary_message_ko=summary,
        food_recommendations_ko=goal.food_recommendations_ko,
    )


def analyze_multiple_goals(
    goal_codes: list[str],
    intakes: list[NutrientIntake],
    user: UserKDRIsContext,
) -> list[GoalAnalysisResult]:
    """여러 목적 일괄 분석.

    Args:
        goal_codes: 목적 코드 리스트.
        intakes: 섭취 정보.
        user: 사용자 컨텍스트.

    Returns:
        각 목적의 분석 결과.
    """
    return [
        analyze_goal(code, intakes, user)
        for code in goal_codes
    ]


def _status_priority(status: NutrientStatus) -> int:
    """상태별 우선순위 (낮을수록 우선)."""
    order = {
        NutrientStatus.RISKY: 0,
        NutrientStatus.DEFICIENT: 1,
        NutrientStatus.LOW: 2,
        NutrientStatus.EXCESSIVE: 3,
        NutrientStatus.ADEQUATE: 4,
    }
    return order[status]


def _generate_summary(
    goal: HealthGoal,
    deficient_count: int,
    total: int,
) -> str:
    """목적별 요약 메시지 생성 (의료법 표현 준수)."""
    if total == 0:
        return f"{goal.name_ko}와 관련된 영양소 정보가 부족합니다."

    if deficient_count == 0:
        return (
            f"{goal.name_ko}와 관련된 핵심 영양소 {total}종이 "
            f"권장 범위에 있습니다."
        )

    return (
        f"{goal.name_ko}와 관련된 영양소 {total}종 중 "
        f"{deficient_count}종이 부족합니다. "
        f"권장 식품 섭취를 늘리는 것을 고려해보세요."
    )
```

---

## 🧪 테스트 (4-Tier)

### Tier 1: 단위 테스트

#### `test_goal_definitions.py`

| 테스트 | 검증 |
|-------|------|
| `test_load_returns_seven_goals` | 7개 목적 로드 |
| `test_get_eye_health` | 눈 건강 정의 조회 |
| `test_get_unknown_raises` | "unknown" → ValueError |
| `test_core_nutrients_weights_in_range` | 모든 weight 0~1 |
| `test_mfds_function_text_no_diagnose` | 모든 기능성 표시에 "진단", "치료" 없음 |

#### `test_goal_analysis.py`

| 테스트 | 검증 |
|-------|------|
| `test_eye_health_with_no_lutein` | 루테인 0 섭취 → DEFICIENT 진단 |
| `test_fatigue_full_b_complex` | B군 모두 충족 → adequate_count 4 |
| `test_priority_deficient_first` | 부족 영양소가 우선순위 상위 |
| `test_summary_no_deficient` | "권장 범위" 메시지 |
| `test_summary_with_deficient` | "부족합니다" 메시지 |
| `test_summary_no_diagnose_word` | 메시지에 "진단", "처방" 없음 |
| `test_multiple_goals` | 3개 목적 동시 분석 |

### Tier 2: 통합 테스트

```python
"""실제 KDRIs + 목적 정의 통합."""

@pytest.mark.integration
class TestGoalAnalysisIntegration:
    def test_persona_b_chronic_fatigue(self, loaded_kdris):
        """페르소나 B (만성질환자) 피로 회복 분석."""
        intakes = [
            # 비타민 B군 부족, 철분 부족 시나리오
            NutrientIntake(code="vitamin_b1_mg", amount=0.5, unit="mg"),
            NutrientIntake(code="iron_mg", amount=5, unit="mg"),
        ]
        user = UserKDRIsContext(age=52, sex="male")

        result = analyze_goal("fatigue_recovery", intakes, user)

        # 부족 영양소가 발견되어야
        assert result.deficient_count >= 2
        # 식품 권장이 포함되어야
        assert any("시금치" in f or "현미" in f for f in result.food_recommendations_ko)

    def test_eye_health_no_data_summary(self, loaded_kdris):
        """관련 영양소 데이터 없을 때 적절한 메시지."""
        intakes = []  # 빈 섭취
        user = UserKDRIsContext(age=30, sex="male")

        result = analyze_goal("eye_health", intakes, user)
        assert "정보가 부족" in result.summary_message_ko
```

### Tier 3: E2E 테스트

```python
"""사용자 시나리오: 영양제 등록 → 목적별 분석."""

@pytest.mark.e2e
class TestGoalAnalysisE2E:
    @pytest.mark.asyncio
    async def test_register_then_analyze_goal(self):
        """영양제 등록 후 즉시 목적별 분석."""
        # 1. 영양제 등록 (POST /api/v1/supplements/register)
        # 2. 사용자가 목적 선택 (POST /api/v1/nutrition/goal-analysis)
        # 3. 응답에 식약처 기능성 표시 + 권장 식품 포함
        ...
```

### Tier 4: 컴플라이언스 테스트

```python
"""의료법 표현 가이드 준수 자동 검증."""

class TestComplianceValidation:
    """모든 데이터·메시지의 표현 가이드 준수."""

    def test_no_forbidden_terms_in_definitions(self):
        """모든 목적 정의에 금지 단어 없음."""
        goals = list_goals()
        forbidden = {"진단", "처방", "치료", "확실히", "완치"}
        for goal in goals:
            for nutrient in goal.core_nutrients:
                for term in forbidden:
                    assert term not in nutrient.mfds_function_ko, (
                        f"Forbidden term '{term}' in {goal.code}/{nutrient.code}"
                    )

    def test_food_recommendations_no_supplement_brand(self):
        """식품 권장에 영양제 브랜드명 없음."""
        goals = list_goals()
        for goal in goals:
            for food in goal.food_recommendations_ko:
                # 영양제 브랜드 표현 (예: "센트룸", "GNC") 금지
                assert "센트룸" not in food
                assert "GNC" not in food
                # 일반 식품명만 허용
```

---

## ✅ Definition of Done

- [ ] `data/reference/health_goals.json` — 7가지 목적 완전 정의
- [ ] `src/nutrition/goal_definitions.py` — 모델 + 로더
- [ ] `src/nutrition/goal_analysis.py` — analyze_goal, analyze_multiple_goals
- [ ] 모든 함수 Google-style docstring + Examples
- [ ] 모든 함수 타입 힌트
- [ ] 단위 테스트 (정의 + 분석) 20+
- [ ] 통합 테스트 (KDRIs + 정의 통합)
- [ ] E2E 테스트 (등록 → 분석 흐름)
- [ ] **컴플라이언스 테스트 — 의료법 표현 가이드 준수 자동 검증**
- [ ] `mypy src/nutrition --strict` 통과
- [ ] `pytest tests` 통과 + 커버리지 ≥ 90%

---

## 💡 구현 팁

### 식약처 인정 기능성 표시 출처

식품안전나라 건강기능식품 원료별 정보에서 인정된 표현만 사용. 직접 만든 표현은 의료법·표시광고 규정 위반 위험이 있다.

### JSON 스키마 검증

JSON 로드 후 Pydantic 모델로 검증하면 잘못된 데이터 자동 차단:

```python
# 빈약한 검증 ❌
goal = HealthGoal(**data)  # 알 수 없는 필드 무시

# 엄격한 검증 ✅
class HealthGoal(BaseModel):
    model_config = ConfigDict(extra="forbid")  # 추가 필드 금지
```

### 가중치 활용 (UI에서)

`weight` 가 1.0인 영양소는 "필수", 0.5 미만은 "보조" 정도로 UI에서 시각적 차별화 가능.

---

## 🚫 이 작업에서 하지 말 것

- ❌ "이 영양소가 X 질병을 예방한다" 표현
- ❌ 영양제 브랜드 추천 (식품·성분만)
- ❌ 식약처 인정 외 기능성 주장
- ❌ 정량적 효과 보장 ("3주 만에 ...")

---

## 🔗 관련 문서

- [`/docs/07-core-algorithm.md §4.4`](../07-core-algorithm.md)
- [`/docs/13-algorithm-literature-evidence.md`](../13-algorithm-literature-evidence.md)
- [`/docs/10-compliance-checklist.md §10`](../10-compliance-checklist.md)
- 이전: [`14-hall-dynamic-model.md`](./14-hall-dynamic-model.md)
- 다음: [`16-meal-recognition.md`](./16-meal-recognition.md)

## 📚 사용 근거

- 식품안전나라. 루테인/지아잔틴복합추출물 원료별 정보. https://www.foodsafetykorea.go.kr/portal/board/boardDetail.do?bbs_no=bbs987&menu_grp=MENU_NEW01&menu_no=2660&ntctxt_no=21540
- AREDS2 Research Group. Lutein + zeaxanthin and omega-3 fatty acids for age-related macular degeneration. JAMA. 2013. https://pubmed.ncbi.nlm.nih.gov/23644932/
- Martineau AR, et al. Vitamin D supplementation to prevent acute respiratory tract infections. BMJ. 2017. https://www.bmj.com/content/356/bmj.i6583.abstract
- Jolliffe DA, et al. Vitamin D supplementation to prevent acute respiratory infections. The Lancet Diabetes & Endocrinology. 2025. https://pubmed.ncbi.nlm.nih.gov/39993397/
- Bernasconi AA, et al. Effect of Omega-3 Dosage on Cardiovascular Outcomes. Mayo Clinic Proceedings. 2021. https://pubmed.ncbi.nlm.nih.gov/32951855/
