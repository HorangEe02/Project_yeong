from __future__ import annotations

from lemon_ai_agent.answer_card import AnswerCard
from lemon_ai_agent.answer_plan import AnalysisPlan, AnswerPlan
from lemon_ai_agent.chat_session import ChatbotResponse
from lemon_ai_agent.chat_turn import ChatTurnPlan
from lemon_ai_agent.entity_normalization import match_p0_boundary
from lemon_ai_agent.knowledge import REVIEWED_MEDICAL_SOURCE_REGISTRY

CHATBOT_TOOLS = [
    "chatbot_agent",
    "intent_analysis",
    "medical_knowledge_retrieval",
    "knowledge_policy",
    "safety_guard",
]


class ChatRenderer:
    """Render an AnswerPlan into the six-section chatbot surface."""

    def render(self, plan: AnswerPlan) -> str:
        message = (
            "현재 기록/상황 요약\n"
            f"- 개인화 수준: {plan.personalization_level}; 준비도: {plan.readiness_level}\n"
            "핵심 건강축/영양축\n"
            f"- {_join_or_default((*plan.problem_axes, *plan.nutrient_priorities), '확인된 우선순위 없음')}\n"
            "오늘 먹을 수 있는 음식 후보\n"
            f"- {_join_or_default(plan.food_first_actions, '추가 음식 기록이 필요합니다')}\n"
            "줄일 음식/습관\n"
            f"- {_join_or_default(plan.behavior_actions, '반복되는 기록을 더 확인합니다')}\n"
            "오늘 행동\n"
            f"- {_join_or_default(plan.ctas, 'ask_about_this_result')}\n"
            "위험/복약/검사수치 boundary\n"
            f"- {_join_or_default(plan.safety_boundaries, '개인 의료 판단은 전문가 확인이 필요합니다')}\n"
            "출처 기준\n"
            f"- {_source_basis(plan)}"
        )
        if plan.answer_depth != "expanded":
            return message
        return (
            f"{message}\n"
            "추가 확인 지점\n"
            f"- 영양제: {_join_or_default(plan.supplement_considerations, '확인된 영양제 고려사항 없음')}\n"
            f"- 행동/기록: {_join_or_default(plan.behavior_actions, '추가 행동 기록을 확인합니다')}"
        )


class AnalysisRenderer:
    """Render an AnalysisPlan into UI-ready analysis sections."""

    def render(self, plan: AnalysisPlan) -> dict[str, object]:
        return {
            "score_status": plan.score_status,
            "score": plan.score,
            "readiness_level": plan.readiness_level,
            "sections": {
                "strengths": list(plan.strengths),
                "priority_adjustments": list(plan.priority_adjustments),
                "nutrient_priorities": list(plan.nutrient_priorities),
                "recommended_foods": list(plan.recommended_foods),
                "checklist_actions": list(plan.checklist_actions),
                "missing_records": list(plan.missing_records),
                "safety_boundaries": list(plan.safety_boundaries),
            },
            "ctas": list(plan.ctas),
        }


class BoundaryRenderer:
    """Render deterministic boundary responses without calling the LLM."""

    def render(
        self,
        turn: ChatTurnPlan,
        warnings: list[str],
    ) -> ChatbotResponse | None:
        policy = turn.policy
        if _has_reviewed_claim_boundary_card(turn):
            warnings.append("Reviewed claim boundary applied")
            card = turn.answer_cards[0]
            return _deterministic_response(
                turn,
                _reviewed_claim_boundary_message(card),
                warnings,
            )

        if policy.category == "symptom_or_emergency":
            warnings.append("Emergency escalation boundary applied")
            return _deterministic_response(
                turn,
                (
                    "즉시 안내: 가슴 통증, 숨참, 마비, 실신처럼 응급 가능성이 있는 "
                    "증상은 단순 피로나 소화불량으로 단정할 수 없고 심장이나 폐 쪽 "
                    "응급 신호일 수 있습니다. 지금 증상이 지속되거나 심하면 119에 "
                    "연락하거나 가까운 응급실로 이동하세요. "
                    "주의: Lemon Aid는 이런 상황에서 개인 의료 판단을 대신하지 "
                    "않습니다. 연결 자원: E-Gen 응급의료포털과 보건복지상담센터 "
                    "129를 참고할 수 있습니다."
                ),
                warnings,
            )

        if policy.category == "mental_health_risk":
            warnings.append("Mental health escalation boundary applied")
            return _deterministic_response(
                turn,
                (
                    "즉시 안내: 자해, 자살 생각, 극단적인 굶기처럼 안전 위험이 보이면 "
                    "일반 건강관리 안내를 멈추고 사람의 도움을 먼저 받아야 합니다. "
                    "혼자 있지 말고 신뢰할 수 있는 사람이나 가까운 의료기관에 즉시 "
                    "알리세요. 주의: 체중 관리 조언보다 현재 안전 확인이 우선입니다. "
                    "연결 자원: 자살예방상담전화 109, 보건복지상담센터 129, "
                    "국가정신건강정보포털을 이용할 수 있습니다."
                ),
                warnings,
            )

        if policy.category == "drug_or_interaction":
            warnings.append("Drug interaction boundary applied")
            stored_medication_terms = _stored_medication_terms(turn.request.context)
            boundary_match = match_p0_boundary(
                " ".join((turn.request.message, *stored_medication_terms))
            )
            if boundary_match is not None:
                warnings.append(f"boundary_code:{boundary_match.boundary_code}")
            interaction_detail = _p0_interaction_detail(
                " ".join((turn.request.message, *stored_medication_terms))
            )
            stored_medication_sentence = _stored_medication_sentence(turn.request.context)
            interaction_detail = (
                f"Question context: {turn.request.message}. "
                f"{stored_medication_sentence}{interaction_detail}"
            )
            return _deterministic_response(
                turn,
                (
                    "요약: 약, 질환, 영양제 병용 질문은 Lemon Aid가 허용 또는 "
                    "금지로 판정하지 않습니다. 주의: 현재 복용 중인 약, 질환, "
                    "검사 수치, 제품 성분표에 따라 확인할 내용이 달라질 수 있습니다. "
                    f"위험 이유: {interaction_detail} "
                    "확인할 정보: 정확한 약 이름, 성분명, 제품 라벨, 복용 중인 약 "
                    "목록, 신장/간 기능, 최근 이상 증상을 확인하세요. 다음 행동: "
                    "제품 라벨과 복용 중인 약 목록을 가지고 의사 또는 약사에게 "
                    "확인하세요. 임의로 시작, 중단, 증량, 감량하지 않는 쪽으로 "
                    "안내합니다."
                ),
                warnings,
            )

        if policy.category == "out_of_scope":
            warnings.append("Out-of-scope medical decision boundary applied")
            return _deterministic_response(
                turn,
                (
                    "요약: 개인 복용량, 처방 변경, 질환 판단처럼 개인 의료 결정에 "
                    "해당하는 질문은 Lemon Aid가 결정하지 않습니다. 주의: 영양소도 "
                    "검사 결과, 현재 섭취량, 복용 중인 약, 질환 맥락에 따라 확인이 "
                    "필요합니다. 다음 행동: 현재 식사와 영양제 섭취량을 정리하고, "
                    "필요하면 검사 결과를 바탕으로 전문가와 상담하세요."
                ),
                warnings,
            )

        return None


class UnknownRenderer:
    """Render unknown responses when reviewed evidence is unavailable."""

    def render(
        self,
        turn: ChatTurnPlan,
        warnings: list[str],
    ) -> ChatbotResponse:
        request = turn.request
        return ChatbotResponse(
            request_id=request.request_id,
            message=(
                "요약\n"
                "- 현재 검수된 지식 안에서 답할 수 없습니다.\n"
                "현재 답할 수 없는 이유\n"
                "- 이 질문에 맞는 reviewed answer card가 아직 없어 LLM 일반 지식으로 "
                "병용 가능 여부나 건강 판단을 채우지 않습니다.\n"
                "필요한 검수 지식\n"
                "- 정확한 약 이름, 제품 라벨, 성분명, 복용 목적, 관련 질환과 함께 "
                "검수된 출처가 필요합니다.\n"
                "지금 할 수 있는 안전한 행동\n"
                "- 새로 시작하거나 함께 복용할지 결정하기 전에는 제품 라벨과 약 목록을 "
                "가지고 약사 또는 의사에게 확인하세요."
            ),
            provider="deterministic",
            used_tools=CHATBOT_TOOLS.copy(),
            safety_warnings=warnings,
            source_families=turn.source_families,
            answerability=turn.answerability,
            sources=[],
            requires_user_approval=False,
        )


class CardAnswerRenderer:
    """Render deterministic reviewed-card answers and fallback messages."""

    def render_answer_card(
        self,
        turn: ChatTurnPlan,
        warnings: list[str],
        *,
        source_basis: str,
    ) -> ChatbotResponse:
        card = turn.answer_cards[0]
        return _deterministic_response(
            turn,
            _natural_reviewed_answer(
                summary_sentence=_card_summary_sentence(card),
                caution=_card_caution_sentence(card),
                next_action=_card_examples_sentence(card),
                management_points=_card_checklist_sentence(card),
                source_basis=source_basis,
            ),
            warnings,
        )

    def render_general(
        self,
        turn: ChatTurnPlan,
        warnings: list[str],
        *,
        summary_sentence: str,
        caution: str,
        next_action: str,
        management_points: str,
        source_basis: str,
    ) -> ChatbotResponse:
        return _deterministic_response(
            turn,
            _natural_reviewed_answer(
                summary_sentence=summary_sentence,
                caution=caution,
                next_action=next_action,
                management_points=management_points,
                source_basis=source_basis,
            ),
            warnings,
        )

    def render_medication_supplement_caution(
        self,
        turn: ChatTurnPlan,
        warnings: list[str],
        *,
        source_basis: str,
    ) -> ChatbotResponse:
        stored_medication_sentence = _stored_medication_sentence(
            turn.request.context,
            for_caution=True,
        )
        source_basis = f"{stored_medication_sentence}{source_basis}"
        return _deterministic_response(
            turn,
            (
                "마그네슘은 근육·신경 기능과 관련된 영양소라 관심을 가질 수 있지만, "
                "혈압약을 복용 중이면 제품 라벨의 마그네슘 함량, 혈압약 종류, "
                "신장 기능, 다른 영양제 중복 여부를 함께 봐야 합니다.\n"
                "오늘은 제품 라벨과 복용 중인 혈압약 이름을 확인하고, 최근 어지러움, "
                "설사, 복통 같은 이상 증상이 있었는지 정리하세요.\n"
                "식품으로는 견과류, 콩류, 통곡물, 녹색 잎채소처럼 마그네슘을 "
                "포함한 후보를 우선 고려할 수 있습니다. 보충제를 새로 시작하거나 "
                "복용량을 정하는 지점은 약 이름과 제품 라벨을 가지고 약사 또는 "
                "의사에게 확인하세요.\n\n"
                f"출처 기준: {source_basis}"
            ),
            warnings,
        )

    def render_sodium_meal(
        self,
        turn: ChatTurnPlan,
        warnings: list[str],
        *,
        safe_summary: str,
        confirmed_foods: str,
        source_basis: str,
    ) -> ChatbotResponse:
        return _render_contextual_sodium_meal(
            turn,
            warnings,
            safe_summary=safe_summary,
            confirmed_foods=confirmed_foods,
            source_basis=source_basis,
        )


def _render_contextual_sodium_meal(
    turn: ChatTurnPlan,
    warnings: list[str],
    *,
    safe_summary: str,
    confirmed_foods: str,
    source_basis: str,
) -> ChatbotResponse:
    if safe_summary:
        summary_sentence = f"현재 입력 기준으로 {safe_summary}"
    elif confirmed_foods:
        summary_sentence = f"확인된 기록은 {_inline_text(confirmed_foods)}입니다."
    else:
        summary_sentence = (
            "오늘 저녁 나트륨을 줄이려면 국물, 소스, 장류, 가공육처럼 "
            "짠맛을 크게 올리는 요소부터 줄이는 쪽이 실용적입니다."
        )

    kidney_caution = ""
    if "kidney_disease" in turn.analysis.related_conditions:
        kidney_caution = (
            " 신장질환이나 콩팥 관련 칼륨 제한을 들은 적이 있다면 "
            "채소와 과일 선택은 따로 확인이 필요합니다."
        )

    protein_action = ""
    if _needs_protein_candidates(safe_summary, confirmed_foods):
        protein_action = (
            "\n- 단백질이 부족한 기록이면 햄·소시지·베이컨 대신 두부, 달걀, 생선구이, "
            "닭가슴살, 살코기, 콩류처럼 덜 짠 단백질 후보 중에서 고르세요."
        )

    return _deterministic_response(
        turn,
        (
            f"{summary_sentence} 찌개나 라면은 국물을 남기고, "
            "간장·쌈장·고추장·드레싱 같은 소스와 장류는 "
            f"부어 먹기보다 찍어 먹는 쪽이 좋습니다.{kidney_caution}\n"
            "오늘은 김치류, 장아찌, 젓갈은 한 가지 이하로 줄이고 햄·소시지·베이컨 같은 "
            f"가공육은 다음 끼니에서 빼거나 양을 줄이세요.{protein_action}\n"
            "직접 확인 가능한 기록에서 짠 국물, 양념, 소스, 절임 반찬이 "
            "반복되는지 먼저 확인하세요.\n\n"
            f"출처 기준: {source_basis}"
        ),
        warnings,
    )


def _card_summary_sentence(card: AnswerCard) -> str:
    if card.allowed_guidance:
        return card.allowed_guidance[0]
    return card.concrete_guidance


def _card_caution_sentence(card: AnswerCard) -> str:
    if card.caution_conditions:
        return (
            "개인 검사수치 해석, 치료 판단, 보충제 고용량 결정은 여기서 단정하지 않고 "
            + (", ".join(card.caution_conditions[:3]))
            + "을 함께 확인하세요."
        )
    return "검수된 근거와 현재 질문 범위 안에서 다음 행동을 좁혀 보세요."


def _card_examples_sentence(card: AnswerCard) -> str:
    if card.specific_examples:
        return "구체 후보는 " + ", ".join(card.specific_examples[:6]) + "부터 확인하세요."
    return "확정된 식사, 영양제, 건강 기록을 먼저 확인해 주세요."


def _card_checklist_sentence(card: AnswerCard) -> str:
    if card.checklist:
        return "확인할 항목은 " + ", ".join(card.checklist[:5]) + "입니다."
    return "한 번의 식사보다 반복 패턴을 보고 다음 기록에서 조절하세요."


def _reviewed_claim_boundary_message(card: AnswerCard) -> str:
    summary = _safe_boundary_summary(
        card.allowed_guidance[0] if card.allowed_guidance else card.concrete_guidance
    )
    action = _reviewed_claim_action_sentence(card)
    checklist = ", ".join(card.checklist[:5]) if card.checklist else "현재 증상과 복용 정보를 정리"
    source_basis = _reviewed_claim_source_basis(card)
    if card.answerability == "urgent_escalation":
        return (
            f"즉시 안내: {summary} "
            f"다음 행동: {action} "
            "주의: Lemon Aid는 이 상황에서 진단을 내리거나, 처방약을 바꾸라고 하거나, "
            "약 용량을 앱에서 정하라고 안내하지 않습니다. 응급 가능성도 배제하지 않습니다. "
            f"확인할 정보: {checklist}.\n\n"
            f"출처 기준: {source_basis}"
        )
    return (
        f"요약: {summary} "
        f"다음 행동: {action} "
        "주의: Lemon Aid는 개인의 복용 가능 여부, 시작·중단·증량·감량, "
        "검사수치 해석, 치료 필요 여부를 결정하지 않습니다. "
        f"확인할 정보: {checklist}.\n\n"
        f"출처 기준: {source_basis}"
    )


def _safe_boundary_summary(summary: str) -> str:
    return (
        summary.replace("혈압약을 줄이거나 중단할지는", "처방 계획 변경 여부는")
        .replace("약을 줄이거나 중단할지는", "처방 계획 변경 여부는")
        .replace("중단할지는", "변경할지는")
    )


def _has_reviewed_claim_boundary_card(turn: ChatTurnPlan) -> bool:
    return (
        turn.requires_boundary_response
        and bool(turn.answer_cards)
        and bool(turn.answer_cards[0].linked_claim_id)
    )


def _reviewed_claim_action_sentence(card: AnswerCard) -> str:
    action_labels = {
        "seek_medical_care_or_emergency_help": "의료기관 또는 응급 도움으로 연결하세요.",
        "call_119_or_seek_emergency_care": "119 또는 응급실 도움을 우선하세요.",
        "call_119_or_seek_emergency_care_for_severe_symptoms": "심한 증상이 있으면 119 또는 응급실 도움을 우선하세요.",
        "call_119_or_seek_emergency_care_for_anaphylaxis_symptoms": "아나필락시스 의심 증상이 있으면 119 또는 응급실 도움을 우선하세요.",
        "call_119_or_seek_emergency_care_for_severe_allergic_reaction": "심한 알레르기 반응 가능성이 있으면 119 또는 응급실 도움을 우선하세요.",
        "follow_existing_diabetes_plan_or_seek_help_for_red_flags": "기존 당뇨 관리 계획을 확인하고 중증 신호가 있으면 즉시 도움을 받으세요.",
        "check_label_and_consult_prescriber_or_pharmacist": "제품 라벨과 복용 중인 약 목록을 가지고 처방자 또는 약사에게 확인하세요.",
        "follow_diabetes_plan_and_consult_clinician_for_alcohol_questions": "당뇨 관리 계획을 우선하고 음주 관련 결정은 의료진에게 확인하세요.",
        "prepare_questions_for_prescriber_or_pharmacist": "복용 중인 약, 용량, 증상, 질문을 정리해 처방자 또는 약사에게 확인하세요.",
        "organize_questions_for_clinician_review": "검사수치와 증상, 병력, 복용 중인 약을 정리해 의료진에게 확인하세요.",
        "consult_obstetrician_prescriber_or_pharmacist": "임신·수유 여부와 복용 제품 정보를 가지고 산부인과, 처방자, 약사에게 확인하세요.",
        "consult_pediatrician_or_pharmacist_and_follow_label": "아이의 나이, 체중, 제품 라벨을 가지고 소아청소년과 또는 약사에게 확인하세요.",
        "organize_medication_list_and_consult_clinician_or_pharmacist": "복용 약 목록과 낙상·탈수·혼돈 증상을 정리해 의료진 또는 약사에게 확인하세요.",
        "consult_nephrology_or_renal_dietitian_for_individualized_limits": "신장 기능과 검사 결과를 바탕으로 담당 의료진 또는 신장 영양상담과 확인하세요.",
        "consult_prescriber_anticoagulation_team_or_pharmacist": "항응고제 관리팀, 처방자, 약사에게 약 이름과 비타민 K 섭취 변화를 확인하세요.",
        "consult_prescriber_or_seek_care_for_toxicity_or_dehydration_symptoms": "처방자에게 확인하고 독성 또는 탈수 의심 증상이 있으면 진료를 받으세요.",
        "check_drug_label_and_consult_prescriber_or_pharmacist": "약 이름과 제품 라벨을 확인해 처방자 또는 약사에게 상담하세요.",
        "consult_prescriber_or_pharmacist_before_use": "새로 시작하기 전에 처방자 또는 약사에게 확인하세요.",
        "seek_medical_care_for_high_risk_or_severe_symptoms": "고위험군이거나 증상이 심하면 의료기관 진료로 연결하세요.",
        "refuse_unsafe_weight_loss_methods_and_connect_to_clinical_support": "위험한 감량 방법은 안내하지 않고 임상적 도움으로 연결하세요.",
    }
    return action_labels.get(
        card.primary_action,
        "이 질문은 앱에서 단정하지 않고 의료진 또는 약사 확인으로 연결하세요.",
    )


def _reviewed_claim_source_basis(card: AnswerCard) -> str:
    if card.source_name and card.source_name != card.source_id:
        return card.source_name
    return card.source_id


def _natural_reviewed_answer(
    *,
    summary_sentence: str,
    caution: str,
    next_action: str,
    management_points: str,
    source_basis: str,
) -> str:
    return (
        f"{summary_sentence} {caution}\n"
        f"오늘은 {next_action} {management_points}\n\n"
        f"출처 기준: {source_basis}"
    )


def _needs_protein_candidates(safe_summary: str, confirmed_foods: str) -> bool:
    text = f"{safe_summary}\n{confirmed_foods}".casefold()
    return any(term in text for term in ("단백질", "protein"))


def _deterministic_response(
    turn: ChatTurnPlan,
    message: str,
    warnings: list[str],
) -> ChatbotResponse:
    sources = (
        turn.sources if _has_medical_wiki_sources(turn) else _boundary_sources(turn) or turn.sources
    )
    return ChatbotResponse(
        request_id=turn.request.request_id,
        message=message,
        provider="deterministic",
        used_tools=CHATBOT_TOOLS.copy(),
        safety_warnings=warnings,
        source_families=list(turn.policy.source_families),
        answerability=turn.answerability,
        sources=sources,
        requires_user_approval=False,
    )


def _has_medical_wiki_sources(turn: ChatTurnPlan) -> bool:
    return bool(turn.answer_cards and turn.answer_cards[0].linked_claim_id)


def _inline_text(value: str) -> str:
    return "; ".join(part.strip() for part in value.splitlines() if part.strip())


def _join_or_default(values: tuple[str, ...], default: str) -> str:
    clean_values = [value for value in values if value]
    return ", ".join(clean_values) if clean_values else default


def _source_basis(plan: AnswerPlan) -> str:
    source_ids = [source["source_id"] for source in plan.source_basis if source.get("source_id")]
    return ", ".join(dict.fromkeys(source_ids)) if source_ids else "reviewed source required"


def _stored_medication_sentence(
    context: dict[str, object],
    *,
    for_caution: bool = False,
) -> str:
    names = _stored_medication_names(context)
    if not names:
        return ""
    joined = ", ".join(names)
    if for_caution:
        return (
            f"Stored medication context: {joined}. Check this medication name "
            "with the magnesium product label before starting or combining a supplement. "
        )
    return f"Stored medication context: {joined}. "


def _stored_medication_terms(context: dict[str, object]) -> tuple[str, ...]:
    profile = context.get("profile")
    if not isinstance(profile, dict):
        return ()
    terms: list[str] = []
    for name in _stored_medication_names(context):
        terms.append(name)
    medication_details = profile.get("medication_details")
    if isinstance(medication_details, list):
        for detail in medication_details:
            if not isinstance(detail, dict):
                continue
            for key in ("normalized_name", "medication_class"):
                value = detail.get(key)
                if isinstance(value, str) and value.strip():
                    terms.append(value.strip())
    if terms:
        terms.append("medication")
    return tuple(dict.fromkeys(terms))


def _stored_medication_names(context: dict[str, object]) -> tuple[str, ...]:
    profile = context.get("profile")
    if not isinstance(profile, dict):
        return ()
    names: list[str] = []
    medication_details = profile.get("medication_details")
    if isinstance(medication_details, list):
        for detail in medication_details:
            if not isinstance(detail, dict):
                continue
            value = detail.get("display_name") or detail.get("normalized_name")
            if isinstance(value, str) and value.strip():
                names.append(value.strip())
    medication_names = profile.get("medications")
    if isinstance(medication_names, list):
        for name in medication_names:
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
    return tuple(dict.fromkeys(names))


def _p0_interaction_detail(message: str) -> str:
    normalized = message.casefold()
    interaction_rules = (
        (
            ("리튬", "lithium"),
            ("셀레늄", "selenium"),
            "리튬은 혈중 농도, 신장 기능, 탈수·염분 변화, 함께 쓰는 약과 영양제에 따라 확인이 필요한 약입니다. "
            "셀레늄 제품도 라벨과 복용 목적을 가지고 의사 또는 약사와 확인해야 합니다.",
        ),
        (
            ("자몽", "자몽주스", "grapefruit"),
            ("스타틴", "statin", "고지혈증 약", "고지혈증약", "콜레스테롤 약", "콜레스테롤약"),
            "자몽은 일부 고지혈증 약의 대사와 혈중 농도에 영향을 줄 수 있어 약 이름과 성분명 확인이 필요합니다.",
        ),
        (
            ("니트로글리세린", "협심증", "nitrate", "nitroglycerin"),
            (
                "pde5",
                "발기부전약",
                "발기부전 약",
                "발기부전 치료제",
                "비아그라",
                "시알리스",
                "실데나필",
                "타다라필",
            ),
            "협심증 약이나 nitrate 계열 약과 PDE5 억제제 조합은 혈압이 크게 떨어질 수 있어 처방명과 성분명 확인이 필요합니다.",
        ),
        (
            ("세인트존스워트", "세인트 존스 워트", "st john", "st. john"),
            ("항우울제", "ssri", "snri"),
            "세인트존스워트는 항우울제 계열 약과 함께 쓸 때 약효 변화나 세로토닌 관련 이상 반응 가능성을 확인해야 합니다.",
        ),
        (
            ("ssri", "snri", "항우울제"),
            ("5-htp", "트립토판", "tryptophan", "l-tryptophan", "세로토닌", "serotonin"),
            "SSRI/SNRI와 세로토닌성 보충제는 작용이 겹칠 수 있어 성분명과 증상 확인이 필요합니다.",
        ),
        (
            ("칼륨", "potassium"),
            ("저염소금", "low sodium salt", "salt substitute"),
            "칼륨 보충제와 저염소금은 칼륨 섭취가 겹칠 수 있어 신장 기능과 복용 약 확인이 필요합니다.",
        ),
        (
            ("홍국", "red yeast rice"),
            ("스타틴", "statin", "고지혈증 약", "고지혈증약", "콜레스테롤 약", "콜레스테롤약"),
            "홍국 제품은 고지혈증 약과 작용 또는 성분이 겹칠 수 있어 제품 라벨과 약 이름 확인이 필요합니다.",
        ),
    )
    for first_keywords, second_keywords, detail in interaction_rules:
        if _has_any(normalized, first_keywords) and _has_any(normalized, second_keywords):
            return detail
    return "약, 질환, 영양제 조합은 현재 복용 중인 약과 제품 성분에 따라 확인할 내용이 달라집니다."


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _boundary_sources(turn: ChatTurnPlan) -> list[dict[str, str]]:
    if turn.policy.category != "drug_or_interaction":
        return []
    stored_medication_terms = _stored_medication_terms(turn.request.context)
    boundary_match = match_p0_boundary(" ".join((turn.request.message, *stored_medication_terms)))
    source_id = (
        "medlineplus-lithium"
        if _has_any(turn.request.message.casefold(), ("리튬", "lithium"))
        else "mfds-drug-safety"
    )
    source = next(
        (
            candidate
            for candidate in REVIEWED_MEDICAL_SOURCE_REGISTRY
            if candidate.source_id == source_id
        ),
        None,
    )
    if source is None:
        return []
    return [
        {
            "source_id": source.source_id,
            "source_family": "drug_safety_boundary",
            "review_status": source.status,
            "version_label": source.version_label,
            "reviewed_at": source.last_reviewed_at,
            "expires_at": source.review_expires_at,
            "source_url": source.url,
            **(
                {"boundary_code": boundary_match.boundary_code}
                if boundary_match is not None
                else {}
            ),
        }
    ]
