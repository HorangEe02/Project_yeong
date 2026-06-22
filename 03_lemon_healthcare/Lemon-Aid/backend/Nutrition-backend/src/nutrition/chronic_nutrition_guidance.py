"""Condition-specific nutrition guide routing.

The guide router is intentionally narrow: it surfaces reviewed public guideline
families for user-visible routing and does not calculate disease-specific
targets from labs, medications, or clinician care plans.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.models.schemas.nutrition import ConditionNutritionGuide
from src.nutrition.chronic_priority import normalize_condition_code


@dataclass(frozen=True)
class _GuideDefinition:
    """Internal guide metadata.

    Attributes:
        guide_key: Stable response key.
        guide_label: Human-readable guide label.
        source_id: Stable source identifier.
        source_title: Official source title.
        source_url: Official public source URL.
        focus_nutrients: Nutrients or nutrition themes to surface for review.
        user_message: Safe user-facing route message.
        referral_required: Whether general KDRIs auto-analysis should be paused.
    """

    guide_key: str
    guide_label: str
    source_id: str
    source_title: str
    source_url: str
    focus_nutrients: tuple[str, ...]
    user_message: str
    referral_required: bool = False


_GUIDES: dict[str, _GuideDefinition] = {
    "ada_diabetes_nutrition": _GuideDefinition(
        guide_key="ada_diabetes_nutrition",
        guide_label="ADA diabetes nutrition guidance",
        source_id="ada_standards_of_care",
        source_title="ADA Standards of Care in Diabetes",
        source_url="https://professional.diabetes.org/standards-of-care",
        focus_nutrients=("fiber_g", "carbohydrate_quality", "meal_pattern"),
        user_message=(
            "당뇨 관련 입력이 있어 ADA 영양 관리 자료 기준으로 식이섬유와 "
            "탄수화물 품질 확인을 함께 표시합니다."
        ),
    ),
    "dash_hypertension": _GuideDefinition(
        guide_key="dash_hypertension",
        guide_label="NHLBI DASH eating plan",
        source_id="nhlbi_dash",
        source_title="NHLBI DASH Eating Plan",
        source_url="https://www.nhlbi.nih.gov/health/dash-eating-plan",
        focus_nutrients=("sodium_mg", "potassium_mg", "calcium_mg", "magnesium_mg", "fiber_g"),
        user_message=(
            "고혈압 또는 심혈관 관련 입력이 있어 DASH 식사 패턴 기준으로 "
            "나트륨, 칼륨, 칼슘, 마그네슘, 식이섬유 확인을 함께 표시합니다."
        ),
    ),
    "kdoqi_ckd_nutrition": _GuideDefinition(
        guide_key="kdoqi_ckd_nutrition",
        guide_label="KDOQI nutrition in CKD",
        source_id="kdoqi_nutrition_ckd_2020",
        source_title="KDOQI Clinical Practice Guideline for Nutrition in CKD: 2020 Update",
        source_url=(
            "https://www.kidney.org/professionals/kdoqi/"
            "guidelines-and-commentaries/nutrition-ckd"
        ),
        focus_nutrients=("protein_g", "sodium_mg", "potassium_mg", "phosphorus_mg"),
        user_message=(
            "신장질환 관련 입력이 있어 KDOQI CKD nutrition guide 기준으로 "
            "단백질, 나트륨, 칼륨, 인은 개인 검사값과 상담 후 확인해야 합니다."
        ),
        referral_required=True,
    ),
    "easl_liver_nutrition": _GuideDefinition(
        guide_key="easl_liver_nutrition",
        guide_label="EASL chronic liver disease nutrition guidance",
        source_id="easl_chronic_liver_nutrition",
        source_title="EASL Clinical Practice Guidelines on nutrition in chronic liver disease",
        source_url=(
            "https://easl.eu/wp-content/uploads/2018/10/"
            "EASL-CPG-nutrition-in-chronic-liver-disease.pdf"
        ),
        focus_nutrients=("protein_g", "energy_intake", "muscle_mass", "sodium_mg"),
        user_message=(
            "간질환 관련 입력이 있어 EASL chronic liver disease nutrition guide 기준으로 "
            "체중, 근육량, 단백질 섭취 검토를 상담 우선으로 안내합니다."
        ),
        referral_required=True,
    ),
}

_ALIAS_TO_GUIDE: dict[str, tuple[str, str]] = {
    "diabetes": ("ada_diabetes_nutrition", "diabetes"),
    "type2_diabetes": ("ada_diabetes_nutrition", "diabetes"),
    "type_2_diabetes": ("ada_diabetes_nutrition", "diabetes"),
    "diabetes_t2": ("ada_diabetes_nutrition", "diabetes"),
    "t2dm": ("ada_diabetes_nutrition", "diabetes"),
    "prediabetes": ("ada_diabetes_nutrition", "diabetes"),
    "hypertension": ("dash_hypertension", "hypertension"),
    "htn": ("dash_hypertension", "hypertension"),
    "high_blood_pressure": ("dash_hypertension", "hypertension"),
    "cardiovascular": ("dash_hypertension", "cardiovascular"),
    "cvd": ("dash_hypertension", "cardiovascular"),
    "cad": ("dash_hypertension", "cardiovascular"),
    "heart_disease": ("dash_hypertension", "cardiovascular"),
    "ckd": ("kdoqi_ckd_nutrition", "chronic_kidney_disease"),
    "chronic_kidney_disease": ("kdoqi_ckd_nutrition", "chronic_kidney_disease"),
    "kidney_disease": ("kdoqi_ckd_nutrition", "chronic_kidney_disease"),
    "renal_failure": ("kdoqi_ckd_nutrition", "chronic_kidney_disease"),
    "dialysis": ("kdoqi_ckd_nutrition", "chronic_kidney_disease"),
    "cirrhosis": ("easl_liver_nutrition", "liver_disease"),
    "liver_cirrhosis": ("easl_liver_nutrition", "liver_disease"),
    "liver_disease": ("easl_liver_nutrition", "liver_disease"),
    "chronic_liver_disease": ("easl_liver_nutrition", "liver_disease"),
}


def get_condition_nutrition_guides(
    chronic_diseases: Sequence[str],
) -> list[ConditionNutritionGuide]:
    """Return condition-specific nutrition guide routes for profile diseases.

    Args:
        chronic_diseases: User-provided chronic condition codes.

    Returns:
        Deduplicated guide routes sorted in a stable order.
    """
    matched_conditions: dict[str, list[str]] = {}
    for disease in chronic_diseases:
        guide_match = _ALIAS_TO_GUIDE.get(normalize_condition_code(disease))
        if guide_match is None:
            continue
        guide_key, condition_code = guide_match
        matched_conditions.setdefault(guide_key, [])
        if condition_code not in matched_conditions[guide_key]:
            matched_conditions[guide_key].append(condition_code)

    guides: list[ConditionNutritionGuide] = []
    for guide_key, definition in _GUIDES.items():
        condition_codes = matched_conditions.get(guide_key)
        if not condition_codes:
            continue
        guides.append(
            ConditionNutritionGuide(
                condition_codes=condition_codes,
                guide_key=definition.guide_key,  # type: ignore[arg-type]
                guide_label=definition.guide_label,
                source_id=definition.source_id,
                source_title=definition.source_title,
                source_url=definition.source_url,
                focus_nutrients=list(definition.focus_nutrients),
                referral_required=definition.referral_required,
                user_message=definition.user_message,
            )
        )
    return guides
