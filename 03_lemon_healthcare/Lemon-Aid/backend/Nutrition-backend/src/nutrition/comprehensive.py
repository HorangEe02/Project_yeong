"""5-card 종합 분석 산출 로직.

OCR 으로 추출된 ingredient + 사용자 프로필을 받아 KDRIs 권장량/상한과 비교하고
만성질환 매트릭스(`chronic_disease_supplement_matrix.json`)와 교차하여 5-card
UI 의 5종 카드를 모두 채울 수 있는 데이터를 계산한다.

KDRIs 권장량/상한은 정식 KDRIs 모듈(`src/nutrition/kdris.py`)에서 조회하여
`KDRIS_DATA_VERSION`(2020 샘플 / 2025 공식)에 따라 버전 스위치된 값을 사용한다.
공식 데이터셋에 스칼라 기준이 없는 영양소(예: 오메가-3)는 인라인 baseline으로
안전하게 폴백한다.

Reference:
    docs/Nutrition-docs/09-data-catalog.md (KDRIs)
    data/nutrition_reference/chronic_disease_supplement_matrix.json
"""

from __future__ import annotations

import logging
from typing import Literal, TypedDict

from src.models.schemas.chronic_disease_matrix import ChronicCondition
from src.models.schemas.supplement_comprehensive import (
    CautionaryComponent,
    ComprehensiveAnalysisRequest,
    ComprehensiveIngredient,
    DeficientNutrient,
    ExcessiveNutrient,
    PersonaTag,
    PurposeTarget,
    ScoreLabel,
    SupplementComprehensiveAnalysis,
    UserProfileInput,
    WellnessGoal,
    WellnessGoalTarget,
)
from src.nutrition.kdris import lookup_kdris_reference
from src.utils.chronic_disease_matrix import (
    category_to_conditions,
    load_matrix,
)

logger = logging.getLogger(__name__)

ALGORITHM_VERSION = "comprehensive-v1"
"""5-card 산출 로직 버전 (회귀 추적용)."""

_DEFICIT_NOISE_THRESHOLD = 0.05
"""5% 미만 부족은 노이즈로 무시한다."""

_MAX_NUTRIENTS_PER_CARD = 5
"""카드당 최대 항목 수 (UX: 한 화면에 너무 많은 정보 회피)."""

_MAX_CAUTIONS_PER_CARD = 8
"""안전 경고는 일반 매트릭스 경고에 밀리지 않도록 약간 더 넉넉히 유지한다."""

_SCORE_EXCELLENT = 90
_SCORE_GOOD = 75
_SCORE_MODERATE = 55
_SCORE_WARNING = 35
"""diet_score 라벨링 임계값."""

_SCORE_PENALTY_DEFICIENT = 5.0
_SCORE_PENALTY_EXCESSIVE = 8.0
_SCORE_PENALTY_CAUTION_HIGH = 12.0
_SCORE_PENALTY_CAUTION_MEDIUM = 6.0
_SCORE_PENALTY_CAUTION_LOW = 2.0
_PERSONA_B_CAUTION_WEIGHT = 1.2
"""diet_score 산출 가중치."""

_USER_CONDITION_BOOST = 0.15
"""사용자가 명시한 chronic_condition 의 relevance_score 가중치."""
_CURRENT_SMOKING_STATUSES = {"current_light", "current_heavy"}
_SMOKER_VITAMIN_C_ADDITIONAL_MG = 35.0
_SMOKER_BETA_CAROTENE_WARNING_MG = 6.0
_VITAMIN_A_UL_UG = 3000.0
_ADULT_PREGNANCY_VITAMIN_A_MIN_AGE = 19
_ADOLESCENT_PREGNANCY_PREFORMED_VITAMIN_A_UL_UG = 2800.0
_AUDIT_KR_RISK_CUTOFF = 3
_AUDIT_KR_DEPENDENCE_MALE = 10
_AUDIT_KR_DEPENDENCE_FEMALE = 8
_HIGH_RISK_DRUGS = {
    "warfarin",
    "levothyroxine",
    "methotrexate",
    "chemo",
    "bisphosphonate",
    "maoi",
    "ssri",
    "statin",
    "metformin",
    "acetaminophen",
}
_MIN_HIGH_DOSE_OMEGA3_MG = 1000.0
_MIN_HIGH_DOSE_VITAMIN_E_MG = 100.0
_MIN_HIGH_DOSE_BETA_CAROTENE_MG = 20.0
_BINDING_NUTRIENT_CODES = {"calcium_mg", "iron_mg", "magnesium_mg"}
_WARFARIN_BOTANICAL_BLEEDING_CODES = {"ginkgo_mg", "ginkgo_biloba_mg", "garlic_mg"}
_WARFARIN_BOTANICAL_BLEEDING_KEYWORDS = (
    "ginkgo",
    "ginkgo biloba",
    "은행잎",
    "은행",
    "garlic",
    "마늘",
)
_CKD_CAUTION_NUTRIENT_CODES = {
    "magnesium_mg",
    "potassium_mg",
    "vitamin_a_ug",
    "vitamin_d_ug",
    "vitamin_k_ug",
}

_GOAL_LABELS: dict[WellnessGoal, str] = {
    "eye_health": "눈 건강",
    "liver_health": "간 건강",
    "fatigue_recovery": "피로 회복",
    "immune_support": "면역 기능",
    "sleep_support": "수면·긴장 완화",
    "gut_health": "장 건강",
}


class _KdrisEntry:
    """KDRIs 단일 영양소 권장량/상한 (MVP inline 룩업)."""

    __slots__ = ("display_name", "recommended", "unit", "upper_limit")

    def __init__(
        self,
        display_name: str,
        unit: str,
        recommended: float,
        upper_limit: float,
    ) -> None:
        self.display_name = display_name
        self.unit = unit
        self.recommended = recommended
        self.upper_limit = upper_limit


# 분석기가 다루는 핵심 영양소 13종의 baseline (일반 성인 19~64세 기준).
# 우선순위는 `kdris.py`의 버전 스위치된 공식 값이며, 이 테이블은 공식 데이터셋에
# 스칼라 기준이 없을 때(예: 오메가-3)의 폴백으로만 사용한다.
_KDRIS_TABLE: dict[str, _KdrisEntry] = {
    "vitamin_a_ug": _KdrisEntry("비타민 A", "ug", 750, 3000),
    "vitamin_b1_mg": _KdrisEntry("비타민 B1", "mg", 1.2, 1000),
    "vitamin_b6_mg": _KdrisEntry("비타민 B6", "mg", 1.4, 100),
    "vitamin_b12_ug": _KdrisEntry("비타민 B12", "ug", 2.4, 2000),
    "vitamin_c_mg": _KdrisEntry("비타민 C", "mg", 100, 2000),
    "vitamin_d_ug": _KdrisEntry("비타민 D", "ug", 10, 100),
    "vitamin_e_mg": _KdrisEntry("비타민 E", "mg", 12, 540),
    "vitamin_k_ug": _KdrisEntry("비타민 K", "ug", 75, 1000),
    "calcium_mg": _KdrisEntry("칼슘", "mg", 800, 2500),
    "magnesium_mg": _KdrisEntry("마그네슘", "mg", 350, 350),
    "iron_mg": _KdrisEntry("철분", "mg", 10, 45),
    "zinc_mg": _KdrisEntry("아연", "mg", 10, 35),
    "omega3_mg": _KdrisEntry("오메가-3", "mg", 1000, 3000),
}


# KDRIs 2025 CSV는 비타민 B1을 `thiamin_mg` 코드로 보관한다. 그 외 12개 코드는 1:1 일치.
_KDRIS_CODE_ALIAS: dict[str, str] = {"vitamin_b1_mg": "thiamin_mg"}


def _resolve_kdris_entry(code: str, user: UserProfileInput) -> _KdrisEntry:
    """버전 스위치된 공식 KDRIs 모듈에서 단일 영양소 기준값을 해석한다.

    `src/nutrition/kdris.py`(KDRIS_DATA_VERSION 적용)에서 사용자 연령·성별·임신
    상태에 맞는 기준값을 조회한다. 공식 데이터셋에 스칼라 기준이 없는 영양소
    (예: 오메가-3 — KDRIs는 EPA+DHA/ALA로 분리)나 조회 실패 시에는 인라인
    baseline으로 안전하게 폴백한다.

    Args:
        code: 분석기 내부 nutrient_code.
        user: 조회 기준이 되는 사용자 프로필.

    Returns:
        해석된 KDRIs 항목. 표시명·단위는 분석기 baseline을 유지하고 권장량/상한만
        공식 값으로 대체한다.
    """
    inline = _KDRIS_TABLE[code]
    pregnancy_status = "pregnant" if user.is_pregnant else "none"
    try:
        reference = lookup_kdris_reference(
            nutrient_code=_KDRIS_CODE_ALIAS.get(code, code),
            age=user.age,
            sex=user.sex,
            pregnancy_status=pregnancy_status,
        )
    except Exception:  # pragma: no cover - 데이터셋 로드 실패는 baseline으로 폴백
        logger.warning("KDRIs lookup failed for %s; using inline baseline.", code, exc_info=True)
        return inline
    if reference is None or reference.reference_amount is None:
        return inline
    # 코드 접미사(mg/ug)가 단위를 결정한다. KDRIs 한정자("ug RAE", "mg alpha-TE",
    # "mg supplemental")는 접두가 같아 스케일이 동일하므로 단위 변환 없이 사용하고,
    # 접두가 다르면(데이터 드리프트) baseline으로 폴백한다.
    if not (reference.reference_unit or "").startswith(inline.unit):
        return inline
    # 상한(UL): KDRIs UL이 없으면 0(과다 카드에서 제외). 마그네슘 등 일부 영양소의 KDRIs
    # UL은 "보충제 한정(mg supplemental)"이지만 분석기는 인라인과 동일하게 총섭취량과
    # 비교한다(기존 동작 보존 — 보충제 출처별 분리는 unit_converter.py:98 TODO에서 추적).
    if reference.ul_amount is None:
        upper_limit = 0.0
    elif (reference.ul_unit or "").startswith(inline.unit):
        upper_limit = reference.ul_amount
    else:
        upper_limit = inline.upper_limit
    return _KdrisEntry(
        display_name=inline.display_name,
        unit=inline.unit,
        recommended=reference.reference_amount,
        upper_limit=upper_limit,
    )


def _resolve_kdris_entries(user: UserProfileInput) -> dict[str, _KdrisEntry]:
    """분석기가 다루는 13개 영양소 기준값을 요청당 1회 해석한다.

    Args:
        user: 조회 기준이 되는 사용자 프로필.

    Returns:
        nutrient_code 키 → 해석된 KDRIs 항목 매핑.
    """
    return {code: _resolve_kdris_entry(code, user) for code in _KDRIS_TABLE}


def _compute_intake_by_code(
    ingredients: list[ComprehensiveIngredient],
) -> dict[str, tuple[float, str, str]]:
    """ingredient 리스트를 nutrient_code 별 (intake, unit, display_name) 으로 집계.

    같은 nutrient_code 가 여러 번 등장하면 amount 를 합산한다 (단위 충돌 시 첫 단위 유지).

    Args:
        ingredients: 요청에서 받은 ingredient 리스트.

    Returns:
        nutrient_code 키 → (총 섭취량, 단위, 표시명) 매핑.
    """
    aggregated: dict[str, list[float]] = {}
    metadata: dict[str, tuple[str, str]] = {}
    for ing in ingredients:
        if not ing.nutrient_code or ing.amount is None:
            continue
        aggregated.setdefault(ing.nutrient_code, []).append(ing.amount)
        metadata.setdefault(
            ing.nutrient_code,
            (ing.unit or "", ing.display_name),
        )
    return {
        code: (sum(values), metadata[code][0], metadata[code][1])
        for code, values in aggregated.items()
    }


def _compute_deficient(
    intake_by_code: dict[str, tuple[float, str, str]],
    user: UserProfileInput,
    kdris_entries: dict[str, _KdrisEntry],
) -> list[DeficientNutrient]:
    """KDRIs 권장량 대비 부족 영양소를 산출한다.

    Args:
        intake_by_code: nutrient_code 키 → (총 섭취량, 단위, 표시명) 매핑.
        user: 흡연 등 생활습관 기준 보정을 적용할 사용자 프로필.
        kdris_entries: 프로필별로 해석된 KDRIs 기준값 매핑.

    Returns:
        부족 비율 기준으로 정렬된 부족 영양소 목록.
    """
    deficient: list[DeficientNutrient] = []
    for code, kdris in kdris_entries.items():
        current, _unit, display = intake_by_code.get(code, (0.0, kdris.unit, kdris.display_name))
        recommended = _recommended_intake_for_user(kdris, nutrient_code=code, user=user)
        if current >= recommended:
            continue
        ratio = 1.0 - (current / recommended) if recommended > 0 else 0.0
        if ratio < _DEFICIT_NOISE_THRESHOLD:
            continue  # 5% 미만 부족은 노이즈로 간주
        deficient.append(
            DeficientNutrient(
                nutrient_code=code,
                display_name=display,
                current_intake=round(current, 2),
                recommended_intake=recommended,
                unit=kdris.unit,
                deficit_ratio=round(min(ratio, 1.0), 4),
            )
        )
    # 가장 부족한 순으로 정렬, 상위 5개만 반환
    deficient.sort(key=lambda d: d.deficit_ratio, reverse=True)
    return deficient[:_MAX_NUTRIENTS_PER_CARD]


def _recommended_intake_for_user(
    kdris: _KdrisEntry,
    *,
    nutrient_code: str,
    user: UserProfileInput,
) -> float:
    """사용자 생활습관에 따른 종합 카드 기준 섭취량을 반환한다.

    Args:
        kdris: 기본 KDRIs inline 항목.
        nutrient_code: 보정 대상 nutrient_code.
        user: 사용자 프로필.

    Returns:
        종합 카드에서 사용할 기준 섭취량.
    """
    if nutrient_code == "vitamin_c_mg" and user.smoking_status in _CURRENT_SMOKING_STATUSES:
        return kdris.recommended + _SMOKER_VITAMIN_C_ADDITIONAL_MG
    return kdris.recommended


def _compute_excessive(
    intake_by_code: dict[str, tuple[float, str, str]],
    kdris_entries: dict[str, _KdrisEntry],
) -> list[ExcessiveNutrient]:
    """KDRIs 상한 대비 과다 섭취 영양소를 산출한다.

    Args:
        intake_by_code: nutrient_code 키 → (총 섭취량, 단위, 표시명) 매핑.
        kdris_entries: 프로필별로 해석된 KDRIs 기준값 매핑.

    Returns:
        과다 비율 기준으로 정렬된 과다 섭취 영양소 목록.
    """
    excessive: list[ExcessiveNutrient] = []
    for code, (current, _unit, display) in intake_by_code.items():
        kdris = kdris_entries.get(code)
        if kdris is None or kdris.upper_limit <= 0:
            continue
        if current <= kdris.upper_limit:
            continue
        ratio = current / kdris.upper_limit
        excessive.append(
            ExcessiveNutrient(
                nutrient_code=code,
                display_name=display,
                current_intake=round(current, 2),
                upper_limit=kdris.upper_limit,
                unit=kdris.unit,
                excess_ratio=round(ratio, 2),
            )
        )
    excessive.sort(key=lambda e: e.excess_ratio, reverse=True)
    return excessive[:5]


def _ingredient_to_category_hint(display_name: str) -> str | None:
    """ingredient display_name 으로 chronic disease matrix 의 카테고리 키를 추정한다.

    MVP: 단순 substring 매칭. 추후 nutrient_code → matrix 카테고리 정식 매핑으로 교체.
    """
    text = display_name.casefold()
    candidates = [
        ("오메가3", ["omega", "오메가", "epa", "dha", "fish oil"]),
        ("코엔자임Q10", ["coenzyme", "coq10", "ubiquinol", "유비퀴놀"]),
        ("혈관_낫토_폴리코사놀", ["폴리코사놀", "policosanol", "낫토", "natto"]),
        ("식이섬유", ["식이섬유", "fiber", "psyllium", "차전자"]),
        ("비타민D", ["비타민 d", "vitamin d", "vitamin_d"]),
        ("비타민K", ["비타민 k", "vitamin k", "vitamin_k"]),
        ("마그네슘", ["마그네슘", "magnesium"]),
        ("강황_커큐민", ["강황", "커큐민", "curcumin", "turmeric"]),
        ("칼슘", ["칼슘", "calcium"]),
        ("밀크씨슬_간", ["밀크씨슬", "milk thistle", "silymarin", "실리마린"]),
        ("뇌_은행잎", ["은행잎", "ginkgo"]),
        ("수면_멜라토닌", ["멜라토닌", "melatonin"]),
        ("스트레스_아쉬와간다", ["아쉬와간다", "ashwagandha"]),
        ("아르기닌_시트룰린", ["아르기닌", "arginine", "시트룰린", "citrulline"]),
        ("비타민B", ["비타민 b", "vitamin b", "thiamin", "리보플라빈"]),
        ("비타민C", ["비타민 c", "vitamin c"]),
        ("유산균_프로바이오틱", ["유산균", "프로바이오틱", "lactobacillus", "bifido"]),
        ("철분", ["철분", "iron", "철"]),
        ("아연", ["아연", "zinc"]),
        ("루테인_눈", ["루테인", "lutein"]),
    ]
    for category, keywords in candidates:
        if any(k in text for k in keywords):
            return category
    return None


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    """텍스트가 키워드 중 하나를 포함하는지 확인한다.

    Args:
        text: Case-folded 검사 대상 텍스트.
        keywords: Case-folded 키워드 목록.

    Returns:
        키워드 포함 여부.
    """
    return any(keyword in text for keyword in keywords)


def _ingredient_matches(
    ingredient: ComprehensiveIngredient,
    *,
    codes: set[str] | None = None,
    keywords: tuple[str, ...] = (),
) -> bool:
    """성분 코드와 표시명을 함께 사용해 안전 분기 대상을 식별한다.

    Args:
        ingredient: 분석 대상 성분.
        codes: 내부 nutrient_code 후보.
        keywords: 표시명 기반 키워드 후보.

    Returns:
        코드 또는 표시명 중 하나가 일치하면 True.
    """
    code = (ingredient.nutrient_code or "").casefold()
    name = ingredient.display_name.casefold()
    return (codes is not None and code in codes) or _contains_any(name, keywords)


class _ConditionInfo(TypedDict):
    """`_compute_chronic_indications_and_targets` 내부 임시 매핑."""

    evidence_level: str
    notes: str
    category: str


def _compute_chronic_indications_and_targets(
    ingredients: list[ComprehensiveIngredient],
    user: UserProfileInput,
) -> tuple[list[ChronicCondition], list[PurposeTarget]]:
    """매트릭스를 통해 chronic_disease_indications + purpose_targets 산출."""
    matrix = load_matrix()
    seen_conditions: dict[ChronicCondition, _ConditionInfo] = {}
    for ing in ingredients:
        category = _ingredient_to_category_hint(ing.display_name)
        if category is None:
            continue
        for target in category_to_conditions(category, matrix=matrix, min_evidence="weak"):
            existing = seen_conditions.get(target.condition)
            if existing is None or _evidence_rank(target.evidence_level) > _evidence_rank(
                existing["evidence_level"]
            ):
                seen_conditions[target.condition] = _ConditionInfo(
                    evidence_level=target.evidence_level,
                    notes=target.notes,
                    category=category,
                )

    indications: list[ChronicCondition] = sorted(seen_conditions.keys())

    purpose_targets: list[PurposeTarget] = []
    for condition, info in seen_conditions.items():
        relevance = _RELEVANCE_BY_EVIDENCE.get(info["evidence_level"], 0.3)
        is_user_target = condition in user.chronic_conditions
        if is_user_target:
            relevance = min(1.0, relevance + 0.15)
        message = _build_purpose_message(condition, info["evidence_level"], is_user_target)
        evidence_level_value = info["evidence_level"]
        assert evidence_level_value in {"strong", "moderate", "weak", "insufficient"}
        purpose_targets.append(
            PurposeTarget(
                condition=condition,
                relevance_score=round(relevance, 2),
                evidence_level=evidence_level_value,  # type: ignore[arg-type]
                message=message,
            )
        )
    purpose_targets.sort(key=lambda t: t.relevance_score, reverse=True)
    return indications, purpose_targets


def _compute_wellness_goal_targets(
    ingredients: list[ComprehensiveIngredient],
) -> list[WellnessGoalTarget]:
    """목적별 분석 매트릭스의 일반 웰니스 목적 적합도를 산출한다.

    Args:
        ingredients: 분석 대상 영양제 성분.

    Returns:
        목적별 적합도 목록. 같은 목적이 여러 성분에서 잡히면 가장 높은 적합도를 사용한다.
    """
    targets: dict[WellnessGoal, WellnessGoalTarget] = {}

    def add(
        goal: WellnessGoal,
        score: float,
        evidence: str,
        message: str,
    ) -> None:
        existing = targets.get(goal)
        if existing is not None and existing.relevance_score >= score:
            return
        assert evidence in {"strong", "moderate", "weak", "insufficient"}
        targets[goal] = WellnessGoalTarget(
            goal=goal,
            relevance_score=score,
            evidence_level=evidence,  # type: ignore[arg-type]
            message=message,
        )

    for ingredient in ingredients:
        if _ingredient_matches(
            ingredient,
            codes={"lutein_mg", "zeaxanthin_mg"},
            keywords=("lutein", "zeaxanthin", "루테인", "지아잔틴"),
        ):
            add(
                "eye_health",
                0.75,
                "moderate",
                "루테인·지아잔틴은 눈 건강 목적 성분으로 분류됩니다.",
            )
        if _ingredient_matches(
            ingredient,
            codes={"omega3_mg"},
            keywords=("omega", "오메가", "epa", "dha", "fish oil"),
        ):
            add(
                "eye_health",
                0.35,
                "insufficient",
                "오메가-3는 눈 건강 목적에서는 보조 근거로만 표시합니다.",
            )
        if _ingredient_matches(
            ingredient,
            keywords=("milk thistle", "silymarin", "밀크씨슬", "실리마린"),
        ):
            add(
                "liver_health",
                0.55,
                "weak",
                "밀크씨슬은 기능성 표시 범위에서만 간 건강 목적을 표시합니다.",
            )
        if _ingredient_matches(
            ingredient,
            codes={"vitamin_b1_mg", "vitamin_b6_mg", "vitamin_b12_ug", "magnesium_mg"},
            keywords=("vitamin b", "비타민 b", "thiamin", "coq10", "coenzyme", "마그네슘"),
        ):
            add("fatigue_recovery", 0.6, "weak", "피로 관련 성분은 결핍 보완 중심으로 안내합니다.")
        if _ingredient_matches(
            ingredient,
            codes={"vitamin_c_mg", "vitamin_d_ug", "zinc_mg"},
            keywords=("vitamin c", "vitamin d", "비타민 c", "비타민 d", "zinc", "아연"),
        ):
            add(
                "immune_support",
                0.55,
                "weak",
                "면역 목적은 결핍 확인과 기능성 표시 범위에서 안내합니다.",
            )
        if _ingredient_matches(
            ingredient,
            codes={"magnesium_mg"},
            keywords=("magnesium", "마그네슘", "theanine", "테아닌", "gaba", "가바"),
        ):
            add(
                "sleep_support",
                0.45,
                "weak",
                "수면 목적은 긴장 완화·영양 균형 보조로만 표시합니다.",
            )
        if _ingredient_matches(
            ingredient,
            keywords=(
                "probiotic",
                "lactobacillus",
                "bifido",
                "fiber",
                "psyllium",
                "유산균",
                "프로바이오틱",
                "식이섬유",
            ),
        ):
            add("gut_health", 0.6, "weak", "장 건강 목적은 균주·식이섬유 특성을 확인해 안내합니다.")

    return sorted(
        targets.values(),
        key=lambda target: (-target.relevance_score, _GOAL_LABELS[target.goal]),
    )


_RELEVANCE_BY_EVIDENCE: dict[str, float] = {
    "strong": 0.85,
    "moderate": 0.65,
    "weak": 0.4,
    "insufficient": 0.2,
}


def _evidence_rank(level: str) -> int:
    """증거 등급의 정수 순위."""
    order = {"insufficient": 0, "weak": 1, "moderate": 2, "strong": 3}
    return order.get(level, 0)


def _build_purpose_message(
    condition: ChronicCondition,
    evidence_level: str,
    is_user_target: bool,
) -> str:
    """만성질환별 한국어 안내문."""
    condition_label = _CONDITION_LABELS.get(condition, condition)
    evidence_label = _EVIDENCE_LABELS.get(evidence_level, evidence_level)
    if is_user_target:
        return f"{condition_label} 관리에 ({evidence_label}) 도움이 될 수 있어요."
    return f"{condition_label} 관련성은 {evidence_label} 단계 근거로 표시합니다."


_CONDITION_LABELS: dict[str, str] = {
    "diabetes": "당뇨 관련 영양 균형",
    "hypertension": "고혈압 관련 영양 균형",
    "dyslipidemia": "이상지질혈증 관련 영양 균형",
    "cardiovascular": "심혈관 건강",
    "osteoporosis": "골다공증·뼈 건강",
    "chronic_kidney_disease": "신장 기능 보조",
    "liver_disease": "간 건강",
    "cognitive_decline": "인지·기억 건강",
}

_EVIDENCE_LABELS: dict[str, str] = {
    "strong": "강한 근거",
    "moderate": "중간 근거",
    "weak": "제한적 근거",
    "insufficient": "근거 부족",
}


def _compute_cautions(
    ingredients: list[ComprehensiveIngredient],
    user: UserProfileInput,
) -> list[CautionaryComponent]:
    """매트릭스의 cautions 필드와 사용자 만성질환을 교차해 주의 성분 산출."""
    matrix = load_matrix()
    matrix_cautions: list[CautionaryComponent] = []
    for ing in ingredients:
        category = _ingredient_to_category_hint(ing.display_name)
        if category is None:
            continue
        profile = matrix.categories.get(category)
        if profile is None:
            continue
        for caution in profile.cautions:
            severity: Literal["low", "medium", "high"] = "medium"
            if any(
                token in caution.lower()
                for token in ("출혈", "bleeding", "fatal", "심각", "회피", "절대")
            ):
                severity = "high"
            elif any(
                token in caution.lower() for token in ("주의", "monitor", "상호작용", "interaction")
            ):
                severity = "medium"
            else:
                severity = "low"
            matrix_cautions.append(
                CautionaryComponent(
                    component=f"{ing.display_name} ({category})",
                    reason=caution,
                    severity=severity,
                    message=_format_caution_message(caution, ing.display_name),
                )
            )
        # 회피 권장 페르소나일 때 추가 경고
        if profile.persona_recommendation in {"avoid_for_chronic", "avoid_for_ckd"}:
            matrix_cautions.append(
                CautionaryComponent(
                    component=ing.display_name,
                    reason=f"persona_avoid:{profile.persona_recommendation}",
                    severity="high",
                    message=f"{ing.display_name}은(는) 만성질환자에게 일반적으로 권장되지 않아요.",
                )
            )

    profile_cautions = _compute_profile_safety_cautions(ingredients, user)
    return _dedupe_and_rank_cautions(profile_cautions + matrix_cautions)[:_MAX_CAUTIONS_PER_CARD]


def _dedupe_and_rank_cautions(
    cautions: list[CautionaryComponent],
) -> list[CautionaryComponent]:
    """중복 경고를 제거하고 안전 우선순위로 정렬한다.

    Args:
        cautions: 후보 경고 목록.

    Returns:
        심각도와 입력 순서를 반영한 경고 목록.
    """
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    indexed: list[tuple[int, CautionaryComponent]] = []
    seen_keys: set[tuple[str, str]] = set()
    for index, caution in enumerate(cautions):
        key = (caution.component.casefold(), caution.reason.casefold())
        if key in seen_keys:
            continue
        seen_keys.add(key)
        indexed.append((index, caution))
    indexed.sort(key=lambda item: (severity_rank[item[1].severity], item[0]))
    return [caution for _index, caution in indexed]


def _compute_profile_safety_cautions(
    ingredients: list[ComprehensiveIngredient],
    user: UserProfileInput,
) -> list[CautionaryComponent]:
    """사용자 흡연·음주·약물 프로필 기반 P0 안전 경고를 산출한다.

    Args:
        ingredients: 분석 대상 성분.
        user: 사용자 프로필.

    Returns:
        추가 안전 경고 목록.
    """
    cautions: list[CautionaryComponent] = []
    is_smoker = user.smoking_status in {"former_lt_1y", "current_light", "current_heavy"}
    has_alcohol_risk = (
        user.audit_kr_score is not None and user.audit_kr_score >= _AUDIT_KR_RISK_CUTOFF
    )
    medication_codes = {medication.casefold() for medication in user.medications}
    chronic_conditions = {condition.casefold() for condition in user.chronic_conditions}

    for ingredient in ingredients:
        cautions.extend(
            _compute_lifestyle_cautions_for_ingredient(
                ingredient=ingredient,
                is_smoker=is_smoker,
                has_alcohol_risk=has_alcohol_risk,
                is_pregnant=user.is_pregnant,
                user_age=user.age,
            )
        )
        cautions.extend(
            _compute_drug_cautions_for_ingredient(
                ingredient=ingredient,
                medication_codes=medication_codes,
            )
        )
        cautions.extend(
            _compute_condition_cautions_for_ingredient(
                ingredient=ingredient,
                chronic_conditions=chronic_conditions,
            )
        )

    cautions.extend(
        _compute_profile_summary_cautions(
            user=user,
            has_alcohol_risk=has_alcohol_risk,
            medication_codes=medication_codes,
        )
    )
    return cautions


def _compute_lifestyle_cautions_for_ingredient(
    *,
    ingredient: ComprehensiveIngredient,
    is_smoker: bool,
    has_alcohol_risk: bool,
    is_pregnant: bool,
    user_age: int,
) -> list[CautionaryComponent]:
    """흡연·음주·임신 상태에 따른 성분별 안전 경고를 산출한다.

    Args:
        ingredient: 분석 대상 성분.
        is_smoker: 현재 또는 최근 흡연 여부.
        has_alcohol_risk: AUDIT-KR 위험 음주 여부.
        is_pregnant: 임신 여부.
        user_age: 만 나이.

    Returns:
        성분별 생활습관 안전 경고.
    """
    cautions: list[CautionaryComponent] = []
    amount = ingredient.amount or 0.0
    vitamin_a_mcg_rae = _vitamin_a_amount_mcg_rae(ingredient)
    is_beta_carotene = _is_beta_carotene(ingredient)
    is_vitamin_a = _is_vitamin_a(ingredient)
    is_preformed_vitamin_a = _is_preformed_vitamin_a(ingredient)
    is_liver_supplement = _is_liver_support_supplement(ingredient)

    if is_smoker and (
        (is_beta_carotene and amount >= _SMOKER_BETA_CAROTENE_WARNING_MG)
        or (is_vitamin_a and vitamin_a_mcg_rae >= _VITAMIN_A_UL_UG)
    ):
        cautions.append(
            _build_caution(
                ingredient,
                "smoker_beta_carotene_vitamin_a_risk",
                "high",
                "흡연자는 베타카로틴 또는 고함량 비타민 A 보충제 섭취 전 전문가 상담이 필요합니다.",
            )
        )
    pregnancy_vitamin_a_ul = _pregnancy_preformed_vitamin_a_ul_ug(user_age)
    if is_pregnant and is_preformed_vitamin_a and vitamin_a_mcg_rae >= pregnancy_vitamin_a_ul:
        cautions.append(
            _build_caution(
                ingredient,
                "pregnancy_vitamin_a_ul_risk",
                "high",
                "임신 중 고함량 레티놀형 비타민 A는 전문가 확인 전 추가 섭취를 피해야 합니다.",
            )
        )
    elif (
        is_pregnant
        and is_vitamin_a
        and not is_beta_carotene
        and vitamin_a_mcg_rae >= pregnancy_vitamin_a_ul
    ):
        cautions.append(
            _build_caution(
                ingredient,
                "pregnancy_vitamin_a_form_review",
                "medium",
                "임신 중 비타민 A 함량이 높으면 라벨의 레티놀·레티닐 비율 확인이 필요합니다.",
            )
        )
    if has_alcohol_risk and is_vitamin_a and vitamin_a_mcg_rae >= _VITAMIN_A_UL_UG:
        cautions.append(
            _build_caution(
                ingredient,
                "alcohol_vitamin_a_liver_risk",
                "high",
                "음주 위험이 있으면 고함량 비타민 A는 간 안전성 확인이 필요합니다.",
            )
        )
    if has_alcohol_risk and is_beta_carotene and amount >= _MIN_HIGH_DOSE_BETA_CAROTENE_MG:
        cautions.append(
            _build_caution(
                ingredient,
                "alcohol_beta_carotene_liver_risk",
                "high",
                "음주 위험이 있으면 고함량 베타카로틴 보충은 간 안전성 확인이 필요합니다.",
            )
        )
    if has_alcohol_risk and is_liver_supplement:
        cautions.append(
            _build_caution(
                ingredient,
                "alcohol_liver_supplement_consult",
                "medium",
                "음주 위험이 있으면 간 건강 보조제는 자가 판단보다 의사·약사 상담 후 선택해야 합니다.",
            )
        )
    if _is_nac(ingredient):
        cautions.append(
            _build_caution(
                ingredient,
                "nac_medicine_class_review",
                "medium",
                "NAC는 건강기능식품 추천이 아니라 의약품 상담 영역으로 분리해 확인하세요.",
            )
        )
    return cautions


def _compute_drug_cautions_for_ingredient(
    *,
    ingredient: ComprehensiveIngredient,
    medication_codes: set[str],
) -> list[CautionaryComponent]:
    """약물-영양제 상호작용 경고를 산출한다.

    Args:
        ingredient: 분석 대상 성분.
        medication_codes: Case-folded 약물 코드 집합.

    Returns:
        약물 상호작용 경고 목록.
    """
    cautions: list[CautionaryComponent] = []
    code = (ingredient.nutrient_code or "").casefold()
    amount = ingredient.amount or 0.0
    if "warfarin" in medication_codes:
        cautions.extend(_compute_warfarin_cautions(ingredient=ingredient, code=code, amount=amount))
    if medication_codes & {"levothyroxine", "bisphosphonate"} and code in _BINDING_NUTRIENT_CODES:
        drug_code = "levothyroxine" if "levothyroxine" in medication_codes else "bisphosphonate"
        drug_label = "레보티록신" if drug_code == "levothyroxine" else "비스포스포네이트"
        cautions.append(
            _build_caution(
                ingredient,
                f"drug_absorption_spacing:{drug_code}",
                "high",
                f"{drug_label} 복용 중에는 칼슘·철분·마그네슘 보충제와 복용 간격을 전문가 지시에 맞춰 분리해야 합니다.",
            )
        )
    if "metformin" in medication_codes and code == "vitamin_b12_ug":
        cautions.append(
            _build_caution(
                ingredient,
                "metformin_b12_monitoring",
                "medium",
                "메트포르민 장기 복용자는 B12 상태 확인을 함께 권장합니다.",
            )
        )
    if medication_codes & {"maoi", "ssri"} and _ingredient_matches(
        ingredient,
        keywords=("st john", "st. john", "hypericum", "세인트존스", "서양고추나물"),
    ):
        cautions.append(
            _build_caution(
                ingredient,
                "serotonergic_st_johns_wort_risk",
                "high",
                "MAOI/SSRI 복용 중 세인트존스워트는 상호작용 위험이 있어 전문가 상담이 필요합니다.",
            )
        )
    if "statin" in medication_codes and _ingredient_matches(
        ingredient,
        keywords=("red yeast", "홍국", "grapefruit", "자몽"),
    ):
        cautions.append(
            _build_caution(
                ingredient,
                "statin_red_yeast_grapefruit_risk",
                "high",
                "스타틴 복용 중 홍국·자몽 성분은 상호작용 검토가 필요합니다.",
            )
        )
    if medication_codes & {"chemo", "methotrexate"} and code in {"vitamin_c_mg", "vitamin_e_mg"}:
        cautions.append(
            _build_caution(
                ingredient,
                "oncology_high_dose_antioxidant_review",
                "high",
                "항암제·면역억제제 사용 중 고용량 항산화제는 의료진 확인 후 결정해야 합니다.",
            )
        )
    return cautions


def _compute_condition_cautions_for_ingredient(
    *,
    ingredient: ComprehensiveIngredient,
    chronic_conditions: set[str],
) -> list[CautionaryComponent]:
    """만성질환별 보충제 안전 경고를 산출한다.

    Args:
        ingredient: 분석 대상 성분.
        chronic_conditions: Case-folded 만성질환 코드 집합.

    Returns:
        만성질환 안전 경고 목록.
    """
    cautions: list[CautionaryComponent] = []
    code = (ingredient.nutrient_code or "").casefold()
    if "chronic_kidney_disease" in chronic_conditions and code in _CKD_CAUTION_NUTRIENT_CODES:
        cautions.append(
            _build_caution(
                ingredient,
                "ckd_supplement_accumulation_review",
                "high",
                "신장질환이 있으면 축적·전해질 위험을 의료진과 확인해야 합니다.",
            )
        )
    if "liver_disease" in chronic_conditions and (
        _is_liver_support_supplement(ingredient) or _is_vitamin_a(ingredient)
    ):
        cautions.append(
            _build_caution(
                ingredient,
                "liver_disease_supplement_consult",
                "high",
                "간질환이 있으면 간 건강 보조제와 고함량 지용성 비타민은 전문가 상담이 우선입니다.",
            )
        )
    return cautions


def _compute_profile_summary_cautions(
    *,
    user: UserProfileInput,
    has_alcohol_risk: bool,
    medication_codes: set[str],
) -> list[CautionaryComponent]:
    """성분과 무관한 사용자 프로필 수준 안전 경고를 산출한다.

    Args:
        user: 사용자 프로필.
        has_alcohol_risk: AUDIT-KR 위험 음주 여부.
        medication_codes: Case-folded 약물 코드 집합.

    Returns:
        프로필 수준 경고 목록.
    """
    cautions: list[CautionaryComponent] = []
    if has_alcohol_risk and "acetaminophen" in medication_codes:
        cautions.append(
            CautionaryComponent(
                component="acetaminophen",
                reason="alcohol_acetaminophen_liver_risk",
                severity="high",
                message="음주 위험이 있으면 아세트아미노펜 성분 약물과 보충제 선택 전 전문가 상담이 필요합니다.",
            )
        )
    if medication_codes & _HIGH_RISK_DRUGS:
        cautions.append(
            CautionaryComponent(
                component="user_medications",
                reason="drug_supplement_interaction_review",
                severity="high",
                message="입력된 약물과 보충제 간 상호작용 가능성이 있어 약사 또는 의사 상담을 권장합니다.",
            )
        )
    if user.audit_kr_score is not None:
        dependence_cutoff = (
            _AUDIT_KR_DEPENDENCE_MALE if user.sex == "male" else _AUDIT_KR_DEPENDENCE_FEMALE
        )
        if user.audit_kr_score >= dependence_cutoff:
            cautions.append(
                CautionaryComponent(
                    component="audit_kr",
                    reason="audit_kr_dependence_cutoff",
                    severity="high",
                    message=(
                        "AUDIT-KR 점수가 높아 영양제 자동 추천보다 1577-0199 또는 "
                        "중독관리통합지원센터 상담 연결이 우선입니다."
                    ),
                )
            )
    return cautions


def _compute_warfarin_cautions(
    *,
    ingredient: ComprehensiveIngredient,
    code: str,
    amount: float,
) -> list[CautionaryComponent]:
    """와파린 관련 영양소 경고를 산출한다.

    Args:
        ingredient: 분석 대상 성분.
        code: Case-folded nutrient_code.
        amount: 성분량.

    Returns:
        와파린 관련 경고 목록.
    """
    cautions: list[CautionaryComponent] = []
    if code == "vitamin_k_ug":
        cautions.append(
            _build_caution(
                ingredient,
                "warfarin_vitamin_k_consistency_review",
                "high",
                "와파린 복용 중에는 비타민 K 섭취량을 임의로 크게 바꾸지 말고 의료진과 일관성을 확인해야 합니다.",
            )
        )
    if code == "omega3_mg" and amount >= _MIN_HIGH_DOSE_OMEGA3_MG:
        cautions.append(
            _build_caution(
                ingredient,
                "warfarin_omega3_bleeding_risk",
                "high",
                "와파린 복용 중 고함량 오메가-3는 출혈 위험 검토가 필요합니다.",
            )
        )
    if code == "vitamin_e_mg" and amount >= _MIN_HIGH_DOSE_VITAMIN_E_MG:
        cautions.append(
            _build_caution(
                ingredient,
                "warfarin_vitamin_e_bleeding_risk",
                "high",
                "와파린 복용 중 고함량 비타민 E는 출혈 위험 검토가 필요합니다.",
            )
        )
    if _ingredient_matches(
        ingredient,
        codes=_WARFARIN_BOTANICAL_BLEEDING_CODES,
        keywords=_WARFARIN_BOTANICAL_BLEEDING_KEYWORDS,
    ):
        cautions.append(
            _build_caution(
                ingredient,
                "warfarin_botanical_bleeding_risk",
                "high",
                "와파린 복용 중 은행잎·마늘 보충제는 출혈 위험 검토가 필요합니다.",
            )
        )
    return cautions


def _build_caution(
    ingredient: ComprehensiveIngredient,
    reason: str,
    severity: Literal["low", "medium", "high"],
    message_suffix: str,
) -> CautionaryComponent:
    """성분명 prefix를 포함한 안전 경고 객체를 생성한다.

    Args:
        ingredient: 분석 대상 성분.
        reason: 표준 경고 token.
        severity: 심각도.
        message_suffix: 성분명 뒤에 붙일 사용자 메시지.

    Returns:
        주의 성분 경고.
    """
    return CautionaryComponent(
        component=ingredient.display_name,
        reason=reason,
        severity=severity,
        message=f"{ingredient.display_name}: {message_suffix}",
    )


def _is_beta_carotene(ingredient: ComprehensiveIngredient) -> bool:
    """베타카로틴 성분 여부를 판별한다."""
    return _ingredient_matches(
        ingredient,
        codes={"beta_carotene_mg"},
        keywords=("beta", "베타카로틴"),
    )


def _is_vitamin_a(ingredient: ComprehensiveIngredient) -> bool:
    """비타민 A 성분 여부를 판별한다."""
    return _ingredient_matches(
        ingredient,
        codes={"vitamin_a_ug", "vitamin_a_retinol_ug", "retinol_ug"},
        keywords=("vitamin a", "비타민 a"),
    )


def _is_preformed_vitamin_a(ingredient: ComprehensiveIngredient) -> bool:
    """Preformed vitamin A(retinol/retinyl ester) 성분 여부를 판별한다."""
    return _ingredient_matches(
        ingredient,
        codes={"vitamin_a_retinol_ug", "retinol_ug", "retinyl_palmitate_ug"},
        keywords=(
            "preformed vitamin a",
            "retinol",
            "retinyl",
            "retinyl palmitate",
            "retinyl acetate",
            "레티놀",
            "레티닐",
        ),
    )


def _vitamin_a_amount_mcg_rae(ingredient: ComprehensiveIngredient) -> float:
    """비타민 A 표기량을 mcg RAE로 환산한다.

    Args:
        ingredient: 분석 대상 성분.

    Returns:
        mcg RAE 기준 비타민 A 함량. 단위가 없거나 이미 mcg/ug 계열이면 원 값을 사용한다.
    """
    amount = ingredient.amount or 0.0
    unit = (ingredient.unit or "").casefold().replace("µ", "u")
    if "iu" in unit:
        return amount * 0.3
    return amount


def _pregnancy_preformed_vitamin_a_ul_ug(user_age: int) -> float:
    """임신 중 preformed vitamin A 상한 기준을 반환한다.

    Args:
        user_age: 만 나이.

    Returns:
        mcg RAE 기준 상한. 14~18세 구간은 더 낮은 기준을 적용한다.
    """
    if user_age < _ADULT_PREGNANCY_VITAMIN_A_MIN_AGE:
        return _ADOLESCENT_PREGNANCY_PREFORMED_VITAMIN_A_UL_UG
    return _VITAMIN_A_UL_UG


def _is_nac(ingredient: ComprehensiveIngredient) -> bool:
    """NAC 성분 여부를 판별한다."""
    return _ingredient_matches(
        ingredient,
        keywords=("nac", "n-acetylcysteine", "acetylcysteine", "아세틸시스테인"),
    )


def _is_liver_support_supplement(ingredient: ComprehensiveIngredient) -> bool:
    """간 건강 보조제 상담 분기 대상인지 판별한다."""
    return _is_nac(ingredient) or _ingredient_matches(
        ingredient,
        keywords=("milk thistle", "silymarin", "밀크씨슬", "실리마린"),
    )


def _format_caution_message(caution_token: str, display_name: str) -> str:
    """매트릭스의 raw caution 문자열을 한국어 사용자 친화 메시지로 변환."""
    mapping: dict[str, str] = {
        "high_dose_atrial_fibrillation_risk": "고용량 시 부정맥 위험이 있어요.",
        "anticoagulant_bleeding_risk": "항응고제(와파린 등) 복용 시 출혈 위험이 커요.",
        "drug_interaction:warfarin": "와파린(혈액 응고 억제제) 복용 시 작용에 영향이 있어요.",
    }
    msg = mapping.get(caution_token)
    if msg:
        return f"{display_name}: {msg}"
    # token 형식 cleanup
    cleaned = caution_token.replace("_", " ").replace(":", " — ")
    cleaned = (
        cleaned.replace("효능", "작용")
        .replace("치료", "관리")
        .replace("처방", "전문가 지시")
        .replace("진단", "확인")
    )
    return f"{display_name}: {cleaned}"


def _compute_diet_score(
    deficient: list[DeficientNutrient],
    excessive: list[ExcessiveNutrient],
    cautions: list[CautionaryComponent],
    persona: PersonaTag,
) -> tuple[int, ScoreLabel, str]:
    """간단한 가중치 기반 식단/영양제 점수 (0~100).

    Baseline 100 에서 deficient(-5), excessive(-8), high-severity caution(-12),
    medium-severity caution(-6) 만큼 감점한다. 페르소나 B 는 만성질환자라 caution
    영향이 더 크다 (가중치 1.2x).
    """
    score = 100.0
    score -= 5.0 * len(deficient)
    score -= 8.0 * len(excessive)
    caution_weight = 1.2 if persona == "B" else 1.0
    for caution in cautions:
        if caution.severity == "high":
            score -= 12.0 * caution_weight
        elif caution.severity == "medium":
            score -= 6.0 * caution_weight
        else:
            score -= 2.0 * caution_weight
    score = max(0.0, min(100.0, score))
    final = round(score)
    label, message = _score_to_label(final, persona)
    return final, label, message


def _score_to_label(score: int, persona: PersonaTag) -> tuple[ScoreLabel, str]:
    """점수 → 라벨 + 한국어 메시지."""
    if score >= _SCORE_EXCELLENT:
        return "excellent", "균형 잡힌 선택이에요. 잘하고 있어요!"
    if score >= _SCORE_GOOD:
        return "good", "양호한 구성이에요. 일부 영양소만 보완해보세요."
    if score >= _SCORE_MODERATE:
        return "moderate", "보완이 필요한 영양소가 보여요. 가이드를 확인해주세요."
    if score >= _SCORE_WARNING:
        persona_extra = " 만성질환자에게는 권장 구성이 아니에요." if persona == "B" else ""
        return "warning", f"주의가 필요한 항목이 많아요.{persona_extra}"
    persona_extra = "" if persona == "A" else " 전문가 상담을 권장해요."
    return "critical", f"전반적 검토가 필요해요.{persona_extra}"


def compute_comprehensive(
    request: ComprehensiveAnalysisRequest,
) -> SupplementComprehensiveAnalysis:
    """요청을 받아 5-card 종합 분석을 산출한다.

    Args:
        request: 검증된 요청 본문.

    Returns:
        모든 카드를 채울 수 있는 종합 분석 결과.
    """
    warnings: list[str] = []
    intake_by_code = _compute_intake_by_code(request.ingredients)
    if not intake_by_code:
        warnings.append("no_recognized_nutrient_codes")
    dependence_cutoff = (
        _AUDIT_KR_DEPENDENCE_MALE
        if request.user_profile.sex == "male"
        else _AUDIT_KR_DEPENDENCE_FEMALE
    )
    if (
        request.user_profile.audit_kr_score is not None
        and request.user_profile.audit_kr_score >= dependence_cutoff
    ):
        warnings.append("supplement_recommendation_paused_audit_kr")

    if request.user_profile.smoking_status in _CURRENT_SMOKING_STATUSES:
        warnings.append("smoker_vitamin_c_reference_iom_plus_35mg")

    kdris_entries = _resolve_kdris_entries(request.user_profile)
    deficient = _compute_deficient(intake_by_code, request.user_profile, kdris_entries)
    excessive = _compute_excessive(intake_by_code, kdris_entries)
    cautions = _compute_cautions(request.ingredients, request.user_profile)
    indications, purpose_targets = _compute_chronic_indications_and_targets(
        request.ingredients,
        request.user_profile,
    )
    wellness_goal_targets = _compute_wellness_goal_targets(request.ingredients)

    score, score_label, score_message = _compute_diet_score(
        deficient=deficient,
        excessive=excessive,
        cautions=cautions,
        persona=request.persona,
    )

    return SupplementComprehensiveAnalysis(
        analysis_id=request.analysis_id,
        persona=request.persona,
        deficient_nutrients=deficient,
        excessive_nutrients=excessive,
        cautionary_components=cautions,
        diet_score=score,
        diet_score_label=score_label,
        diet_score_message=score_message,
        purpose_targets=purpose_targets,
        wellness_goal_targets=wellness_goal_targets,
        chronic_disease_indications=indications,
        algorithm_version=ALGORITHM_VERSION,
        warnings=warnings,
    )
