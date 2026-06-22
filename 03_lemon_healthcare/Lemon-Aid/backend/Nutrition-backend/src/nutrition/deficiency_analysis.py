"""KDRIs 기준 섭취 상태 분석."""

from __future__ import annotations

from src.models.schemas.nutrition import (
    KDRIReference,
    NutrientAnalysisResult,
    NutrientIntake,
    NutrientStatus,
    NutritionAnalysisResponse,
)
from src.models.schemas.user import UserProfile
from src.nutrition.chronic_nutrition_guidance import get_condition_nutrition_guides
from src.nutrition.chronic_priority import get_chronic_priority_match
from src.nutrition.kdris import get_kdris_dataset_context, get_kdris_for_profile
from src.nutrition.unit_converter import convert_amount

LOW_THRESHOLD = 0.70
NEAR_UL_THRESHOLD = 0.80
SMOKER_VITAMIN_C_ADDITIONAL_MG = 35.0
AUDIT_KR_RISK_CUTOFF = 3
RATIO_DECIMALS = 2
AMOUNT_DECIMALS = 3
HIGH_CALCIUM_MAGNESIUM_RATIO = 2.5
ZINC_COPPER_REVIEW_THRESHOLD_MG = 50.0
CALCIUM_IRON_REVIEW_THRESHOLD_MG = 300.0
FORBIDDEN_TERMS = ("진단", "치료", "처방", "복용량 변경")
NUTRITION_ANALYSIS_ALGORITHM_VERSION = "nutrition-v1.0.0"
ADULT_NUTRITION_ANALYSIS_MIN_AGE = 19
HIGH_RISK_NUTRITION_ROUTE_FLAGS = {
    "ckd",
    "chronic_kidney_disease",
    "cirrhosis",
    "liver_disease",
    "heart_failure",
    "chf",
    "thyroid",
    "hypothyroidism",
    "hyperthyroidism",
    "cancer",
    "ibd",
}
REFERENCE_TYPE_RECOMMENDED = {"RNI", "RDA"}
REFERENCE_TYPE_AI = "AI"
REFERENCE_TYPE_EAR = "EAR"
CURRENT_SMOKING_STATUSES = {"current_light", "current_heavy"}
AUDIT_KR_SUPPORT_NUTRIENTS = {"thiamin_mg", "folate_ug", "magnesium_mg", "zinc_mg"}
LOW_NUTRIENT_STATUSES = {
    NutrientStatus.AT_RISK_INADEQUATE,
    NutrientStatus.BELOW_RDA,
    NutrientStatus.DEFICIENT,
    NutrientStatus.LOW,
}
HIGH_OR_ADEQUATE_NUTRIENT_STATUSES = {
    NutrientStatus.ADEQUATE,
    NutrientStatus.EXCESSIVE_NEAR_UL,
    NutrientStatus.EXCESSIVE,
    NutrientStatus.RISKY,
}


def _message_for_status(status: NutrientStatus) -> str:
    """섭취 상태에 맞는 안전 문구를 반환한다.

    Args:
        status: 영양소 섭취 상태.

    Returns:
        사용자 노출용 문구.
    """
    messages = {
        NutrientStatus.AT_RISK_INADEQUATE: "평균 필요량 기준으로 낮은 섭취 가능성이 있어 확인이 필요합니다.",
        NutrientStatus.BELOW_RDA: "권장섭취량보다 낮아 식사 구성을 확인해보세요.",
        NutrientStatus.DEFICIENT: "부족 가능성이 높아 섭취량 확인이 필요합니다.",
        NutrientStatus.LOW: "섭취량이 낮을 가능성이 있어 우선 확인 대상입니다.",
        NutrientStatus.ADEQUATE: "현재 입력 기준으로 적정 범위에 가깝습니다.",
        NutrientStatus.EXCESSIVE_NEAR_UL: "상한 섭취량에 가까워 추가 섭취 여부 확인이 필요합니다.",
        NutrientStatus.EXCESSIVE: "섭취량이 기준보다 많아 조정 여부 확인이 필요합니다.",
        NutrientStatus.RISKY: "상한 섭취량을 초과할 수 있어 전문가 상담 권장 대상입니다.",
        NutrientStatus.REFERRAL_REQUIRED: "일반 기준 자동 평가보다 전문가 상담이 우선입니다.",
    }
    return messages[status]


def _normalized_diseases(profile: UserProfile) -> set[str]:
    """사용자 질환 코드를 안전 라우팅 비교용으로 정규화한다.

    Args:
        profile: 사용자 프로필.

    Returns:
        Case-folded disease code set.
    """
    return {disease.casefold() for disease in profile.chronic_diseases}


def _requires_referral_route(profile: UserProfile) -> bool:
    """일반 KDRIs 자동 평가 대신 referral 상태를 반환해야 하는지 판단한다.

    Args:
        profile: 사용자 프로필.

    Returns:
        고위험 질환 flag가 있으면 True.
    """
    return bool(_normalized_diseases(profile) & HIGH_RISK_NUTRITION_ROUTE_FLAGS) or any(
        guide.referral_required
        for guide in get_condition_nutrition_guides(profile.chronic_diseases)
    )


def _referral_route_messages(profile: UserProfile) -> list[str]:
    """일반 KDRIs 자동 평가를 보류해야 하는 프로필 수준 사유를 반환한다.

    Args:
        profile: 사용자 프로필.

    Returns:
        Referral route가 필요하면 사용자 노출용 안전 메시지 목록, 아니면 빈 목록.
    """
    messages: list[str] = []
    if _requires_referral_route(profile):
        messages.append("등록된 건강 상태에서는 일반 KDRIs 자동 평가보다 전문가 상담이 우선입니다.")
    if profile.pregnancy_status in {"pregnant", "lactating"}:
        messages.append(
            "임신·수유 상태에서는 추가 필요량과 상한 확인을 위해 전문가 상담이 우선입니다."
        )
    if profile.age < ADULT_NUTRITION_ANALYSIS_MIN_AGE:
        messages.append(
            "소아·청소년은 성장 단계별 기준과 보호자·전문가 확인이 필요해 일반 성인 자동 평가를 보류합니다."
        )
    if profile.medications:
        messages.append(
            "복용 약물이 있으면 영양소 평가 전에 약물-영양소 상호작용 확인이 필요합니다."
        )
    return messages


def _is_current_smoker(profile: UserProfile) -> bool:
    """현재 흡연자 비타민 C 참고 기준을 적용할지 판단한다.

    Args:
        profile: 사용자 프로필.

    Returns:
        현재 흡연 상태이면 True.
    """
    return profile.smoking_status in CURRENT_SMOKING_STATUSES


def _analysis_reference_amount(reference: KDRIReference, profile: UserProfile) -> float:
    """사용자 프로필에 맞는 분석 기준 섭취량을 반환한다.

    Args:
        reference: 선택된 KDRIs 기준값.
        profile: 사용자 프로필.

    Returns:
        분석 기준 섭취량. 현재 흡연자의 비타민 C는 IOM/NIH ODS 참고치(+35mg)를 더한다.

    Raises:
        ValueError: 기준량이 없는 경우.
    """
    if reference.reference_amount is None:
        raise ValueError(
            f"KDRIs scalar reference not available for analysis: {reference.nutrient_code}"
        )
    amount = reference.reference_amount
    if reference.nutrient_code == "vitamin_c_mg" and _is_current_smoker(profile):
        return amount + SMOKER_VITAMIN_C_ADDITIONAL_MG
    return amount


def _select_reference_pair(
    references: list[KDRIReference],
    nutrient_code: str,
) -> tuple[KDRIReference, KDRIReference | None]:
    """분석 표시 기준과 EAR 기준을 함께 선택한다.

    Args:
        references: 프로필에 맞는 KDRIs 기준값 목록.
        nutrient_code: 내부 영양소 코드.

    Returns:
        표시 기준(RNI/RDA 우선, 없으면 AI)과 EAR 기준.

    Raises:
        ValueError: 기준값이 없는 경우.
    """
    matches = [reference for reference in references if reference.nutrient_code == nutrient_code]
    if not matches:
        raise ValueError(f"KDRIs reference not found: {nutrient_code}")
    recommended = next(
        (
            reference
            for reference in matches
            if reference.reference_type in REFERENCE_TYPE_RECOMMENDED
            and reference.reference_amount is not None
        ),
        None,
    )
    if recommended is None:
        recommended = next(
            (
                reference
                for reference in matches
                if reference.reference_type == REFERENCE_TYPE_AI
                and reference.reference_amount is not None
            ),
            None,
        )
    if recommended is None:
        recommended = next(
            (reference for reference in matches if reference.reference_amount is not None),
            None,
        )
    if recommended is None:
        raise ValueError(f"KDRIs scalar reference not available for analysis: {nutrient_code}")
    ear = next(
        (
            reference
            for reference in matches
            if reference.reference_type == REFERENCE_TYPE_EAR
            and reference.reference_amount is not None
        ),
        None,
    )
    return recommended, ear


def _classify_status(
    actual_amount: float,
    reference_amount: float,
    ul_amount: float | None,
    *,
    reference_type: str,
    ear_amount: float | None,
) -> NutrientStatus:
    """실제 섭취량을 EAR/RDA/AI/UL 기준과 비교해 상태를 분류한다.

    Args:
        actual_amount: 기준 단위로 환산된 실제 섭취량.
        reference_amount: 기준 섭취량.
        ul_amount: 상한 섭취량.
        reference_type: 표시 기준 유형.
        ear_amount: 평균 필요량. 없으면 AI 또는 RDA fallback을 사용한다.

    Returns:
        섭취 상태.
    """
    status = NutrientStatus.ADEQUATE
    if ul_amount is not None and actual_amount > ul_amount:
        status = NutrientStatus.RISKY
    elif ul_amount is not None and actual_amount >= ul_amount * NEAR_UL_THRESHOLD:
        status = NutrientStatus.EXCESSIVE_NEAR_UL
    elif (ear_amount is not None and actual_amount < ear_amount) or (
        reference_type == REFERENCE_TYPE_AI and actual_amount < reference_amount * LOW_THRESHOLD
    ):
        status = NutrientStatus.AT_RISK_INADEQUATE
    elif reference_type != REFERENCE_TYPE_AI and actual_amount < reference_amount:
        status = NutrientStatus.BELOW_RDA
    return status


def contains_forbidden_terms(messages: list[str]) -> bool:
    """사용자 노출 문구에 금지 표현이 있는지 확인한다.

    Args:
        messages: 사용자 노출 문구 목록.

    Returns:
        금지 표현 포함 여부.
    """
    return any(term in message for message in messages for term in FORBIDDEN_TERMS)


def _result_by_code(results: list[NutrientAnalysisResult]) -> dict[str, NutrientAnalysisResult]:
    """영양소 코드 기준으로 분석 결과를 조회할 수 있게 변환한다.

    Args:
        results: 영양소별 분석 결과 목록.

    Returns:
        영양소 코드를 key로 하는 분석 결과 dict.
    """
    return {result.nutrient_code: result for result in results}


def _append_unique_message(messages: list[str], message: str) -> None:
    """중복 없이 안전 메시지를 추가한다.

    Args:
        messages: 누적 메시지 목록.
        message: 추가할 메시지.
    """
    if message not in messages:
        messages.append(message)


def _nutrient_interaction_messages(results: list[NutrientAnalysisResult]) -> list[str]:
    """영양소 간 섭취 균형 확인 메시지를 생성한다.

    Args:
        results: 영양소별 분석 결과 목록.

    Returns:
        사용자에게 노출할 안전 확인 메시지 목록.
    """
    messages: list[str] = []
    by_code = _result_by_code(results)
    calcium = by_code.get("calcium_mg")
    magnesium = by_code.get("magnesium_mg")
    vitamin_d = by_code.get("vitamin_d_ug")
    zinc = by_code.get("zinc_mg")
    iron = by_code.get("iron_mg")

    if (
        calcium is not None
        and magnesium is not None
        and magnesium.actual_amount > 0
        and calcium.actual_amount / magnesium.actual_amount > HIGH_CALCIUM_MAGNESIUM_RATIO
    ):
        _append_unique_message(
            messages,
            "칼슘:마그네슘 섭취 비율이 높아 두 미네랄 섭취 균형을 함께 확인하세요.",
        )
    if (
        vitamin_d is not None
        and magnesium is not None
        and vitamin_d.status in HIGH_OR_ADEQUATE_NUTRIENT_STATUSES
        and magnesium.status in LOW_NUTRIENT_STATUSES
    ):
        _append_unique_message(
            messages,
            "비타민 D 섭취가 충분하거나 높은 상태에서는 마그네슘 섭취 상태도 함께 확인하세요.",
        )
    if zinc is not None and zinc.actual_amount > ZINC_COPPER_REVIEW_THRESHOLD_MG:
        _append_unique_message(
            messages,
            "아연 50mg/day 초과 섭취는 구리 섭취 상태 확인이 필요합니다.",
        )
    if (
        calcium is not None
        and iron is not None
        and calcium.actual_amount >= CALCIUM_IRON_REVIEW_THRESHOLD_MG
        and iron.status in LOW_NUTRIENT_STATUSES
    ):
        _append_unique_message(
            messages,
            "칼슘과 철분을 함께 많이 섭취하는 경우 철분 섭취 상태를 따로 확인하세요.",
        )
    return messages


def analyze_nutrient_intakes(
    profile: UserProfile,
    intakes: list[NutrientIntake],
) -> NutritionAnalysisResponse:
    """KDRIs 샘플 기준값과 섭취량을 비교한다.

    Args:
        profile: 사용자 프로필.
        intakes: 영양소 섭취량 목록.

    Returns:
        영양소별 섭취 상태 분석 응답.

    Raises:
        ValueError: 기준값이 없거나 단위 환산이 불가능한 영양소가 포함된 경우.
    """
    results: list[NutrientAnalysisResult] = []
    dataset_context = get_kdris_dataset_context()
    condition_guides = get_condition_nutrition_guides(profile.chronic_diseases)
    referral_messages = _referral_route_messages(profile)
    if referral_messages:
        return NutritionAnalysisResponse(
            results=[],
            dataset_status=dataset_context["dataset_status"],
            dataset_version=dataset_context["dataset_version"],
            source_manifest_version=dataset_context["source_manifest_version"],
            routing_status="referral_required",
            safety_messages=referral_messages,
            condition_nutrition_guides=condition_guides,
            note="결과는 보류되었으며 개인 건강 상태에 맞춘 상담을 권장합니다.",
        )

    profile_references = get_kdris_for_profile(
        age=profile.age,
        sex=profile.sex,
        pregnancy_status=profile.pregnancy_status,
    )
    safety_messages: list[str] = []
    if _is_current_smoker(profile):
        safety_messages.append(
            "현재 흡연자는 비타민 C 분석 기준에 IOM/NIH ODS 참고치 +35mg을 반영했습니다."
        )
    if profile.audit_kr_score is not None and profile.audit_kr_score >= AUDIT_KR_RISK_CUTOFF:
        safety_messages.append(
            "AUDIT-KR 위험 음주 범위에서는 B1, 엽산, 마그네슘, 아연 섭취 상태 확인을 우선 권장합니다."
        )

    for intake in intakes:
        reference, ear_reference = _select_reference_pair(profile_references, intake.nutrient_code)
        reference_amount = _analysis_reference_amount(reference, profile)

        actual_amount = convert_amount(
            amount=intake.amount,
            from_unit=intake.unit,
            to_unit=reference.reference_unit,
            nutrient_code=intake.nutrient_code,
        )
        ul_amount = reference.ul_amount
        if reference.ul_amount is not None and reference.ul_unit is not None:
            ul_amount = convert_amount(
                amount=reference.ul_amount,
                from_unit=reference.ul_unit,
                to_unit=reference.reference_unit,
                nutrient_code=intake.nutrient_code,
            )
        ear_amount = None
        if ear_reference is not None:
            ear_amount = convert_amount(
                amount=ear_reference.reference_amount or 0.0,
                from_unit=ear_reference.reference_unit,
                to_unit=reference.reference_unit,
                nutrient_code=intake.nutrient_code,
            )
        status = _classify_status(
            actual_amount=actual_amount,
            reference_amount=reference_amount,
            ul_amount=ul_amount,
            reference_type=reference.reference_type,
            ear_amount=ear_amount,
        )
        ratio = actual_amount / reference_amount
        priority_seed = 0
        if (
            profile.audit_kr_score is not None
            and profile.audit_kr_score >= AUDIT_KR_RISK_CUTOFF
            and reference.nutrient_code in AUDIT_KR_SUPPORT_NUTRIENTS
            and status
            in (
                NutrientStatus.AT_RISK_INADEQUATE,
                NutrientStatus.BELOW_RDA,
                NutrientStatus.DEFICIENT,
                NutrientStatus.LOW,
            )
        ):
            priority_seed = 1
        results.append(
            NutrientAnalysisResult(
                nutrient_code=reference.nutrient_code,
                nutrient_name=reference.nutrient_name,
                reference_amount=reference_amount,
                reference_type=reference.reference_type,
                source_id=reference.source_id,
                errata_version=reference.errata_version,
                review_status=reference.review_status,
                reference_unit=reference.reference_unit,
                actual_amount=round(actual_amount, AMOUNT_DECIMALS),
                ratio=round(ratio, RATIO_DECIMALS),
                ul_amount=ul_amount,
                status=status,
                priority=priority_seed,
                user_message=_message_for_status(status),
            )
        )

    low_results = [
        result
        for result in results
        if result.status
        in (
            NutrientStatus.DEFICIENT,
            NutrientStatus.LOW,
            NutrientStatus.AT_RISK_INADEQUATE,
            NutrientStatus.BELOW_RDA,
        )
    ]
    priority_boosts: dict[str, int] = {}
    for result in low_results:
        if result.priority > 0:
            priority_boosts[result.nutrient_code] = result.priority
            result.priority_context.append("audit_kr_risk")
            result.priority_source_ids.append("audit_kr_profile")
            result.user_message = "현재 프로필 기준으로 우선 확인 대상입니다."
        priority_match = get_chronic_priority_match(
            nutrient_code=result.nutrient_code,
            chronic_diseases=profile.chronic_diseases,
        )
        if priority_match is None:
            continue
        priority_boosts[result.nutrient_code] = priority_match.boost_score
        result.priority_context = list(priority_match.condition_codes)
        result.priority_source_ids = list(priority_match.source_ids)
        result.user_message = priority_match.message

    low_results.sort(
        key=lambda result: (
            -priority_boosts.get(result.nutrient_code, 0),
            result.ratio,
            result.nutrient_code,
        )
    )
    for index, result in enumerate(low_results, start=1):
        result.priority = index

    for message in _nutrient_interaction_messages(results):
        _append_unique_message(safety_messages, message)

    return NutritionAnalysisResponse(
        results=results,
        dataset_status=dataset_context["dataset_status"],
        dataset_version=dataset_context["dataset_version"],
        source_manifest_version=dataset_context["source_manifest_version"],
        safety_messages=safety_messages,
        condition_nutrition_guides=condition_guides,
    )
