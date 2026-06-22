from __future__ import annotations

import json
from typing import Any

from lemon_ai_agent.answer_card import AnswerCard, MedicalKnowledgeRetriever
from lemon_ai_agent.chat_session import ChatbotRequest, ChatbotResponse
from lemon_ai_agent.chat_turn import ChatTurnModule, ChatTurnPlan
from lemon_ai_agent.entity_normalization import (
    EntityNormalizationResult,
    normalize_health_entities,
)
from lemon_ai_agent.guards.safety import SafetyEnvelope, SafetyGuard
from lemon_ai_agent.knowledge import (
    AnswerPolicy,
    ChatIntentAnalysis,
    MedicalKnowledgeItem,
    contract_summary,
    source_family_summary,
)
from lemon_ai_agent.llm import LLMCompletion, LLMMessage, LLMRequest, LocalLLMClient
from lemon_ai_agent.polish_slots import (
    build_deterministic_slot_contract,
    slot_value_sets_match,
    slot_values_are_preserved,
)
from lemon_ai_agent.renderers import (
    CHATBOT_TOOLS,
    BoundaryRenderer,
    CardAnswerRenderer,
    UnknownRenderer,
)
from lemon_ai_agent.tracing import AgentTraceRecorder, AgentTraceSpan, NoopAgentTraceRecorder

MEAL_LABELS = {
    "breakfast": "아침",
    "lunch": "점심",
    "dinner": "저녁",
    "snack": "간식",
}

NUTRIENT_LABELS = {
    "sodium": "나트륨",
    "protein": "단백질",
    "vitamin d": "비타민 D",
    "vitamin_d": "비타민 D",
    "magnesium": "마그네슘",
    "iron": "철",
    "calcium": "칼슘",
    "fiber": "식이섬유",
    "carbohydrate": "탄수화물",
    "carbohydrates": "탄수화물",
    "fat": "지방",
    "sugar": "당류",
    "sugars": "당류",
}

REQUIRED_CHATBOT_SOURCE_MARKER = "출처 기준"
REQUIRED_CHATBOT_ACTION_TERMS = (
    "오늘",
    "다음 끼니",
    "제품 라벨",
    "확인",
    "조절",
    "기록",
)
MIN_MARKDOWN_CODE_FENCE_LINES = 3
STRUCTURED_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "lemon_chatbot_answer",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "summary",
                "why_it_matters",
                "today_actions",
                "specific_examples",
                "caution_conditions",
                "expert_check_points",
                "source_basis",
            ],
            "properties": {
                "summary": {"type": "string"},
                "why_it_matters": {"type": "string"},
                "today_actions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 4,
                },
                "specific_examples": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 8,
                },
                "caution_conditions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 5,
                },
                "expert_check_points": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 5,
                },
                "source_basis": {"type": "string"},
            },
        },
    },
}

DIABETES_CONTEXT_TERMS = ("당뇨", "혈당", "diabetes", "glucose")
HYPERTENSION_CONTEXT_TERMS = ("고혈압", "혈압", "hypertension", "blood pressure")
KIDNEY_CONTEXT_TERMS = ("콩팥", "신장", "kidney", "renal")
MEMORY_BUNDLE_LABELS = {
    "profile_memory": "프로필 메모리",
    "behavior_memory": "행동 메모리",
    "conversation_memory": "대화 요약",
    "safety_memory": "주의 메모리",
}
MEMORY_SUMMARY_MAX_LINES = 6
INTERNAL_MEMORY_TOKENS = (
    "authorization",
    "full_prompt",
    "messages",
    "original_transcript",
    "prompt",
    "provider_payload",
    "raw_image",
    "raw_llm_response",
    "raw_ocr_text",
    "raw_prompt",
    "raw_provider_payload",
    "raw_transcript",
    "summary_json",
)


class ChatbotAgent:
    """Answers user chat with the same safety boundary as Daily Coaching."""

    def __init__(
        self,
        llm_client: LocalLLMClient | None = None,
        *,
        retriever: MedicalKnowledgeRetriever | None = None,
        trace_recorder: AgentTraceRecorder | None = None,
    ) -> None:
        self._completion = LLMCompletion(llm_client)
        self._has_llm_client = llm_client is not None
        self._safety_guard = SafetyGuard()
        self._safety_envelope = SafetyEnvelope(self._safety_guard)
        self._chat_turn = ChatTurnModule(retriever=retriever)
        self._boundary_renderer = BoundaryRenderer()
        self._unknown_renderer = UnknownRenderer()
        self._card_renderer = CardAnswerRenderer()
        self._trace_recorder = trace_recorder or NoopAgentTraceRecorder()

    def answer(self, request: ChatbotRequest) -> ChatbotResponse:  # noqa: PLR0911
        warnings: list[str] = []
        turn = self._chat_turn.plan(request)
        self._record_trace_span(turn, "chat_turn_plan", "planned", warnings=turn.retrieval_warnings)
        self._record_trace_span(turn, "retrieval", "retrieved", warnings=turn.retrieval_warnings)
        boundary_response = self._boundary_renderer.render(turn, warnings)
        if boundary_response is not None:
            self._record_response_trace(turn, boundary_response, "boundary", warnings)
            return boundary_response
        context_resolution_response = self._context_resolution_response(request)
        if context_resolution_response is not None:
            self._record_response_trace(
                turn, context_resolution_response, "needs_more_info", warnings
            )
            return context_resolution_response
        entity_resolution_response = self._entity_resolution_response_for_turn(turn, request)
        if entity_resolution_response is not None:
            self._record_response_trace(
                turn, entity_resolution_response, "needs_more_info", warnings
            )
            return entity_resolution_response
        label_only_response = self._label_only_supplement_response(request, warnings)
        if label_only_response is not None:
            self._record_response_trace(turn, label_only_response, "unknown", warnings)
            return label_only_response
        if turn.answerability == "unknown_no_reviewed_source":
            warnings.extend(turn.retrieval_warnings)
            response = self._unknown_renderer.render(turn, warnings)
            self._record_response_trace(turn, response, "unknown", warnings)
            return response

        if not self._has_llm_client:
            response = self._fallback_response(turn, warnings)
            self._record_response_trace(turn, response, "card_answer", warnings)
            return response

        return self._answer_with_llm_polish(request, turn, warnings)

    def _answer_with_llm_polish(
        self,
        request: ChatbotRequest,
        turn: ChatTurnPlan,
        warnings: list[str],
    ) -> ChatbotResponse:
        draft_response = self._fallback_response(turn, [*warnings])
        completion = self._completion.complete(self._build_llm_request(turn, draft_response))
        if not completion.ok:
            warnings.extend(completion.warnings)
            self._record_trace_span(
                turn,
                "llm_polish",
                "completion_failed",
                warnings=completion.warnings,
                provider=completion.provider,
                passed=False,
            )
            response = self._fallback_response(turn, warnings)
            self._record_response_trace(turn, response, "card_answer", warnings)
            return response

        structured_text, slot_warnings = self._render_structured_completion(completion.text, turn)
        completion_text = structured_text or completion.text
        warnings.extend(slot_warnings)
        self._record_trace_span(
            turn,
            "llm_polish",
            "completed",
            warnings=completion.warnings,
            provider=completion.provider,
        )

        safety = self._safety_envelope.screen_llm_output(
            completion_text,
            self._grounding_context(turn),
        )
        warnings.extend(safety.warnings)
        card_phrase_check = self._safety_guard.check_forbidden_phrases(
            completion_text,
            self._card_must_not_say(turn.answer_cards),
        )
        warnings.extend(card_phrase_check.warnings)
        has_required_shape = self._has_required_response_shape(completion_text)
        if not has_required_shape:
            warnings.append("Chatbot response contract not followed")
        safety_passed = safety.allowed and card_phrase_check.allowed and has_required_shape
        self._record_trace_span(
            turn,
            "safety_guard",
            "checked",
            warnings=warnings,
            provider=completion.provider,
            passed=safety_passed,
        )
        if not safety_passed:
            if structured_text is not None:
                warnings.append("unsafe_polish_fallback")
            response = self._fallback_response(turn, warnings)
            self._record_response_trace(turn, response, "card_answer", warnings)
            return response
        if not self._has_required_card_specificity(completion_text, turn):
            warnings.append("Chatbot response card detail not followed")
            response = self._fallback_response(turn, warnings)
            self._record_response_trace(turn, response, "card_answer", warnings)
            return response

        response = ChatbotResponse(
            request_id=request.request_id,
            message=safety.text,
            provider=completion.provider,
            used_tools=CHATBOT_TOOLS.copy(),
            safety_warnings=warnings,
            source_families=turn.source_families,
            answerability=turn.answerability,
            sources=turn.sources,
            requires_user_approval=False,
        )
        self._record_response_trace(turn, response, "llm_polish", warnings)
        return response

    def _record_response_trace(
        self,
        turn: ChatTurnPlan,
        response: ChatbotResponse,
        renderer_route: str,
        warnings: list[str],
    ) -> None:
        self._record_trace_span(turn, "route_decision", renderer_route, warnings=warnings)
        self._trace_recorder.record(
            AgentTraceSpan(
                request_id=turn.request.request_id,
                span_name="render",
                answerability=response.answerability,
                retrieval_status=turn.retrieval_status,
                renderer_route=renderer_route,
                claim_ids=self._claim_ids_for_turn(turn),
                source_ids=tuple(
                    str(source.get("source_id", ""))
                    for source in response.sources
                    if source.get("source_id")
                ),
                boundary_code=self._boundary_code_for_turn(turn),
                provider=response.provider,
                warning_codes=tuple(dict.fromkeys(warnings)),
                passed=True,
            )
        )

    def _record_trace_span(
        self,
        turn: ChatTurnPlan,
        span_name: str,
        renderer_route: str,
        *,
        warnings: tuple[str, ...] | list[str],
        provider: str = "",
        passed: bool = True,
    ) -> None:
        self._trace_recorder.record(
            AgentTraceSpan(
                request_id=turn.request.request_id,
                span_name=span_name,
                answerability=turn.answerability,
                retrieval_status=turn.retrieval_status,
                renderer_route=renderer_route,
                claim_ids=self._claim_ids_for_turn(turn),
                source_ids=self._source_ids_for_turn(turn),
                boundary_code=self._boundary_code_for_turn(turn),
                provider=provider,
                warning_codes=tuple(dict.fromkeys(warnings)),
                passed=passed,
            )
        )

    def _claim_ids_for_turn(self, turn: ChatTurnPlan) -> tuple[str, ...]:
        claim_ids = [card.linked_claim_id for card in turn.answer_cards if card.linked_claim_id]
        return tuple(dict.fromkeys(claim_ids))

    def _source_ids_for_turn(self, turn: ChatTurnPlan) -> tuple[str, ...]:
        source_ids = [card.source_id for card in turn.answer_cards if card.source_id]
        return tuple(dict.fromkeys(source_ids))

    def _boundary_code_for_turn(self, turn: ChatTurnPlan) -> str:
        if turn.answerability in {
            "urgent_escalation",
            "medical_decision_boundary",
            "safety_boundary",
        }:
            return turn.answerability
        return ""

    def _record_normalization_trace(
        self,
        turn: ChatTurnPlan,
        normalization: EntityNormalizationResult,
    ) -> None:
        warning_codes = []
        if normalization.needs_specific_medication_name:
            warning_codes.append("needs_specific_medication_name")
        if normalization.missing_topics:
            warning_codes.append("missing_topics_present")
        warning_codes.append(f"normalized_entity_count_{len(normalization.entities)}")
        self._record_trace_span(
            turn,
            "normalization",
            "entity_resolution",
            warnings=warning_codes,
            passed=not normalization.needs_specific_medication_name,
        )

    def _fallback_response(
        self,
        turn: ChatTurnPlan,
        warnings: list[str],
    ) -> ChatbotResponse:
        if turn.policy.category == "medication_supplement_caution":
            return self._card_renderer.render_medication_supplement_caution(
                turn,
                warnings,
                source_basis=self._source_basis_for_turn(turn),
            )
        if self._is_sodium_meal_question(turn):
            return self._card_renderer.render_sodium_meal(
                turn,
                warnings,
                safe_summary=self._safe_summary(turn.request.context),
                confirmed_foods=self._confirmed_food_summary(turn.request.context),
                source_basis=self._source_basis_for_turn(turn),
            )
        if turn.policy.category == "nutrition_analysis" and self._has_nutrition_candidate_card(
            turn
        ):
            return self._card_renderer.render_answer_card(
                turn,
                warnings,
                source_basis=self._source_basis_for_turn(turn),
            )

        request = turn.request
        summary = self._safe_summary(request.context)
        confirmed_foods = self._confirmed_food_summary(request.context)
        confirmed_foods_sentence = self._inline_text(confirmed_foods)
        if summary:
            summary_sentence = f"현재 입력 기준으로 {summary}"
        elif confirmed_foods:
            summary_sentence = f"확인된 기록은 {confirmed_foods_sentence}입니다."
        else:
            summary_sentence = "질문과 검수된 근거를 기준으로 우선 확인할 행동을 정리합니다."

        if turn.analysis.primary_intent == "symptom" and not turn.analysis.boundary:
            next_action = self._symptom_next_action(turn.analysis)
        elif turn.policy.category == "chronic_condition_context":
            next_action = self._chronic_condition_next_action(request)
        elif turn.policy.category == "supplement_question":
            next_action = (
                "제품 라벨의 섭취량, 원재료, 기능성 표시를 확인하고 같은 성분의 "
                "중복 섭취를 피하세요."
            )
        else:
            next_action = "확정된 식사, 영양제, 건강 기록을 먼저 확인해 주세요."

        caution = self._fallback_caution(request, turn.policy, turn.analysis)
        management_points = self._fallback_management_points(
            turn.analysis,
            turn.knowledge_items,
        )

        return self._card_renderer.render_general(
            turn,
            warnings,
            summary_sentence=summary_sentence,
            caution=caution,
            next_action=next_action,
            management_points=management_points,
            source_basis=self._source_basis_for_turn(turn),
        )

    def _context_resolution_response(self, request: ChatbotRequest) -> ChatbotResponse | None:
        resolution = request.context.get("user_health_context_resolution")
        if not isinstance(resolution, dict):
            return None
        if resolution.get("status") != "needs_structured_lookup":
            return None

        required_records = resolution.get("required_records")
        record_label = "구조화된 기록"
        if isinstance(required_records, list) and "food_records" in required_records:
            record_label = "음식 기록"
        return ChatbotResponse(
            request_id=request.request_id,
            message=(
                "요약\n"
                f"- 이 질문은 현재 앱 snapshot만으로 확정해서 답하지 않고 {record_label} 조회가 필요합니다.\n"
                "현재 답할 수 없는 이유\n"
                "- 특정 날짜나 끼니 기록은 전체 context를 추측해서 말하지 않고 구조화된 기록 조회로 확인해야 합니다.\n"
                "오늘 할 일\n"
                f"- 앱에 저장된 {record_label}을 먼저 확인하거나 빠진 기록을 추가해 주세요.\n"
                "출처 기준\n"
                "- 사용자 확인 기록과 앱에 저장된 구조화 기록"
            ),
            provider="deterministic",
            used_tools=["user_health_context_snapshot"],
            safety_warnings=["needs_structured_lookup"],
            source_families=[],
            answerability="needs_more_info",
            sources=[],
            requires_user_approval=False,
        )

    def _entity_resolution_response_for_turn(
        self,
        turn: ChatTurnPlan,
        request: ChatbotRequest,
    ) -> ChatbotResponse | None:
        normalization = normalize_health_entities(request.message, request.context)
        if normalization.needs_specific_medication_name:
            self._record_normalization_trace(turn, normalization)
        return self._entity_resolution_response(request, normalization)

    def _entity_resolution_response(
        self,
        request: ChatbotRequest,
        result: EntityNormalizationResult,
    ) -> ChatbotResponse | None:
        if not result.needs_specific_medication_name:
            return None
        return ChatbotResponse(
            request_id=request.request_id,
            message=(
                "요약\n"
                "- 이 질문은 정확한 약 이름이나 약 종류가 있어야 안전하게 다음 확인 지점을 정리할 수 있습니다.\n"
                "현재 답할 수 없는 이유\n"
                "- '혈압약', '당뇨약', '이뇨제' 같은 넓은 표현만으로는 성분별 상호작용 경계를 판단하지 않습니다.\n"
                "필요한 확인 지점\n"
                "- 처방전이나 약 봉투의 정확한 약 이름, 성분명, 복용 중인 영양제 성분명을 확인해 주세요.\n"
                "지금 할 수 있는 안전한 행동\n"
                "- 정확한 약 이름을 확인하기 전에는 새 영양제를 시작하거나 복용량을 바꾸지 말고 의사 또는 약사에게 확인해 주세요."
            ),
            provider="deterministic",
            used_tools=CHATBOT_TOOLS.copy(),
            safety_warnings=["needs_specific_medication_name"],
            source_families=[],
            answerability="needs_more_info",
            sources=[],
            requires_user_approval=False,
        )

    def _label_only_supplement_response(
        self,
        request: ChatbotRequest,
        warnings: list[str],
    ) -> ChatbotResponse | None:
        label_only_names = self._label_only_supplement_names(request.context)
        if not label_only_names:
            return None
        normalized_message = request.message.casefold()
        if not any(name.casefold() in normalized_message for name in label_only_names):
            return None
        warnings.append("label_only_supplement_requires_reviewed_evidence")
        return ChatbotResponse(
            request_id=request.request_id,
            message=(
                "요약\n"
                "- 현재 검토된 출처 안에서는 이 label-only 성분을 표준 영양성분처럼 분석할 수 없습니다.\n"
                "현재 답할 수 없는 이유\n"
                "- nutrient_code가 없는 라벨 정보는 사용자 제품 정보로만 다루고, 효과나 섭취 판단은 reviewed answer card가 필요합니다.\n"
                "필요한 확인 지점\n"
                "- 제품 라벨의 성분명, 함량, 섭취량, 검수된 출처 연결 여부를 먼저 확인해야 합니다.\n"
                "지금 할 수 있는 안전한 행동\n"
                "- 새로 시작하거나 복용량을 정하기 전에는 제품 라벨과 복용 중인 약 목록을 전문가에게 확인해 주세요."
            ),
            provider="deterministic",
            used_tools=CHATBOT_TOOLS.copy(),
            safety_warnings=warnings,
            source_families=[],
            answerability="unknown_no_reviewed_source",
            sources=[],
            requires_user_approval=False,
        )

    def _build_llm_request(
        self,
        turn: ChatTurnPlan,
        draft_response: ChatbotResponse,
    ) -> LLMRequest:
        request = turn.request
        history = "\n".join(f"{turn.role}: {turn.content}" for turn in request.conversation[-6:])
        summary = self._safe_summary(request.context) or "none"
        confirmed_foods = self._confirmed_food_summary(request.context) or "none"
        memory_summary = self._agent_memory_summary(request.context) or "none"

        return LLMRequest(
            messages=[
                LLMMessage(
                    role="system",
                    content=(
                        "You are the Lemon Aid chatbot for health-management coaching. "
                        "Answer only in Korean. Do not lock the user-facing answer into "
                        "fixed card section labels. Write a natural mobile-readable answer "
                        "that still includes a short summary, the main caution, today's "
                        "action, and source basis. "
                        "You are polishing a deterministic draft, not making medical "
                        "decisions or choosing sources. "
                        "Do not diagnose, treat, prescribe, guarantee effects, "
                        "or promote buying a specific product. "
                        "Use cautious but practical phrasing such as '현재 입력 기준', "
                        "'줄이는 것이 좋습니다', '다음 끼니에서 조절하세요', "
                        "and '권장합니다'. "
                        "Use professional-confirmation wording only for medication or "
                        "supplement co-use, starting/stopping/changing doses, diagnosis, "
                        "treatment, prescription, lab-value interpretation, emergency or "
                        "mental-health risk, worsening symptoms, or other personal medical "
                        "judgment requests. "
                        "Avoid absolute-ban wording such as '먹으면 안 된다', "
                        "'완전히 금지', or '절대 먹지 마세요'. "
                        "sodium 같은 영문 영양소명은 나트륨처럼 한국어 표시명으로 바꾸세요. "
                        "Do not mention or quote internal calculation logs, trace, "
                        "tool names, 'supplement totals', or 'nutrition findings'. "
                        "Do not create new health facts without a listed source family. "
                        "Do not create new health judgments beyond the supplied context. "
                        "Do not use Semantic Scholar as a user-facing source. "
                        "Use only the provided reviewed answer cards as factual grounding. "
                        "Do not change source_basis, caution_conditions, specific_examples, "
                        "or expert_check_points; the backend will reattach those slots "
                        "from reviewed cards after your polish. "
                        "If no reviewed answer card is provided, do not answer with model knowledge. "
                        "Do not answer with only broad categories such as vegetables or protein; "
                        "use concrete examples from the provided knowledge cards. "
                        "For medication/supplement co-use questions, explain general principles "
                        "and checklist items, but do not conclude whether the user personally can "
                        "or cannot take them together. "
                        "Professional-confirmation wording must attach to the decision point; "
                        "it must not replace the useful checklist. "
                        "For emergency questions, do not provide long differential diagnosis; "
                        "prioritize risk reason and immediate action. "
                        "End with a brief source basis sentence like: "
                        "'출처 기준: 질병관리청 건강정보, KDRIs 영양 기준'."
                    ),
                ),
                LLMMessage(
                    role="user",
                    content=(
                        f"User message: {request.message.strip()}\n"
                        f"Question category: {turn.policy.category}\n"
                        f"Classification reasons: {', '.join(turn.policy.reasons)}\n"
                        "Allowed source families:\n"
                        f"{source_family_summary(turn.policy.source_families)}\n"
                        "Response contract:\n"
                        f"{contract_summary(turn.policy.contract)}\n"
                        "Intent analysis:\n"
                        f"{self._intent_analysis_summary(turn.analysis)}\n"
                        "Reviewed knowledge items:\n"
                        f"{self._answer_cards_summary(turn.answer_cards)}\n"
                        "Answer plan:\n"
                        f"{turn.answer_plan.to_prompt_summary()}\n"
                        "Answer strategy:\n"
                        f"{self._answer_strategy(turn)}\n"
                        "Deterministic safety slots to preserve exactly:\n"
                        f"{self._deterministic_slot_contract(turn)}\n"
                        "Deterministic answer draft to polish without changing safety slots:\n"
                        f"{draft_response.message}\n"
                        f"Recent conversation:\n{history or 'none'}\n"
                        "Confirmed meal and nutrient context:\n"
                        f"{confirmed_foods}\n"
                        "User-reported memory context "
                        "(confirmed app record가 아닌 낮은 강도 참고 정보):\n"
                        f"{memory_summary}\n"
                        "Internal context for grounding only; do not quote or mention "
                        f"internal keys: {summary}"
                    ),
                ),
            ],
            temperature=0.1,
            response_format=STRUCTURED_RESPONSE_FORMAT,
        )

    def _safe_summary(self, context: dict[str, object]) -> str:
        raw_summary = context.get("daily_coaching_summary")
        if not isinstance(raw_summary, str):
            return ""

        check = self._safety_guard.check_text(raw_summary)
        if not check.allowed:
            return ""
        return raw_summary.strip()

    def _agent_memory_summary(self, context: dict[str, object]) -> str:
        memory = context.get("agent_memory")
        if not isinstance(memory, dict):
            return ""
        bundle = memory.get("memory_bundle")
        if not isinstance(bundle, dict):
            return ""

        lines: list[str] = []
        for memory_type, label in MEMORY_BUNDLE_LABELS.items():
            records = bundle.get(memory_type)
            if not isinstance(records, list):
                continue
            for record in records[:2]:
                line = self._agent_memory_record_summary(label, record)
                if line:
                    lines.append(line)
                if len(lines) >= MEMORY_SUMMARY_MAX_LINES:
                    return "\n".join(lines)
        return "\n".join(lines)

    def _agent_memory_record_summary(self, label: str, record: object) -> str:
        if not isinstance(record, dict):
            return ""
        summary_json = record.get("summary_json")
        if not isinstance(summary_json, dict):
            return ""
        summary = self._safe_memory_text(summary_json.get("summary"))
        if not summary:
            return ""

        metadata = []
        confidence = self._safe_memory_text(summary_json.get("confidence"))
        source = self._safe_memory_text(summary_json.get("source_kind"))
        if confidence:
            metadata.append(f"confidence={confidence}")
        if source:
            metadata.append(f"source={source}")
        metadata.append("confirmed app record가 아닌 낮은 강도 참고 정보")
        return f"{label}: {summary} ({'; '.join(metadata)})"

    def _safe_memory_text(self, value: object) -> str:
        if not isinstance(value, str):
            return ""
        stripped = " ".join(value.strip().split())
        if not stripped:
            return ""
        if any(token in stripped.casefold() for token in INTERNAL_MEMORY_TOKENS):
            return ""
        check = self._safety_guard.check_text(stripped)
        if not check.allowed:
            return ""
        return stripped[:240]

    def _grounding_context(
        self,
        turn: ChatTurnPlan,
    ) -> str:
        request = turn.request
        conversation = "\n".join(turn.content for turn in request.conversation[-6:])
        summary = self._safe_summary(request.context)
        memory_summary = self._agent_memory_summary(request.context)
        confirmed_foods = self._confirmed_food_summary(request.context)
        knowledge = "\n".join(item.concrete_guidance for item in turn.knowledge_items)
        cards = "\n".join(self._answer_card_text(card) for card in turn.answer_cards)
        return "\n".join(
            (
                request.message,
                conversation,
                summary,
                memory_summary,
                confirmed_foods,
                knowledge,
                cards,
                turn.answer_plan.to_prompt_summary(),
            )
        )

    def _render_structured_completion(
        self,
        text: str,
        turn: ChatTurnPlan,
    ) -> tuple[str | None, list[str]]:
        stripped = self._extract_structured_json_object(text)
        if stripped is None:
            return None, []
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            return None, []
        if not isinstance(data, dict) or not self._has_structured_response_schema(data):
            return None, []

        summary = str(data["summary"]).strip()
        why_it_matters = str(data["why_it_matters"]).strip()
        today_actions = self._structured_string_list(data["today_actions"])
        specific_examples = self._structured_string_list(data["specific_examples"])
        caution_conditions = self._structured_string_list(data["caution_conditions"])
        expert_check_points = self._structured_string_list(data["expert_check_points"])
        source_basis = str(data["source_basis"]).strip()
        if not all(
            (
                summary,
                why_it_matters,
                source_basis,
                today_actions,
                specific_examples,
                caution_conditions,
                expert_check_points,
            )
        ):
            return None, []

        warnings = self._structured_slot_mutation_warnings(
            turn,
            source_basis=source_basis,
            specific_examples=specific_examples,
            caution_conditions=caution_conditions,
            expert_check_points=expert_check_points,
        )
        deterministic_actions = self._deterministic_today_actions(turn)
        deterministic_examples = self._deterministic_specific_examples(turn)
        deterministic_cautions = self._deterministic_caution_conditions(turn)
        deterministic_checks = self._deterministic_expert_check_points(turn)
        deterministic_source_basis = self._source_basis_for_turn(turn)

        message = (
            f"{summary} {why_it_matters} {'; '.join(deterministic_cautions[:3])}\n"
            f"오늘은 {'; '.join(deterministic_actions[:4])} "
            f"구체적으로는 {', '.join(deterministic_examples[:6])}부터 확인하세요. "
            f"확인 포인트는 {'; '.join(deterministic_checks[:5])}입니다.\n\n"
            f"출처 기준: {deterministic_source_basis}"
        )
        return message, warnings

    def _structured_slot_mutation_warnings(
        self,
        turn: ChatTurnPlan,
        *,
        source_basis: str,
        specific_examples: list[str],
        caution_conditions: list[str],
        expert_check_points: list[str],
    ) -> list[str]:
        warnings: list[str] = []
        if not slot_value_sets_match(
            [source_basis],
            [self._source_basis_for_turn(turn)],
        ):
            warnings.append("llm_source_slot_ignored")
        if not self._slot_values_are_deterministic(
            specific_examples,
            self._deterministic_specific_examples(turn),
        ):
            warnings.append("llm_specific_examples_slot_ignored")
        if not self._slot_values_are_deterministic(
            caution_conditions,
            self._deterministic_caution_conditions(turn),
        ):
            warnings.append("llm_caution_slot_ignored")
        if not self._slot_values_are_deterministic(
            expert_check_points,
            self._deterministic_expert_check_points(turn),
        ):
            warnings.append("llm_expert_check_slot_ignored")
        return warnings

    def _deterministic_slot_contract(self, turn: ChatTurnPlan) -> str:
        return build_deterministic_slot_contract(
            source_basis=self._source_basis_for_turn(turn),
            specific_examples=self._deterministic_specific_examples(turn),
            caution_conditions=self._deterministic_caution_conditions(turn),
            expert_check_points=self._deterministic_expert_check_points(turn),
        )

    def _slot_values_are_deterministic(
        self,
        candidate_values: list[str],
        deterministic_values: list[str],
    ) -> bool:
        return slot_values_are_preserved(candidate_values, deterministic_values)

    def _deterministic_today_actions(self, turn: ChatTurnPlan) -> list[str]:
        checklist = self._deterministic_checklist_values(turn)
        if checklist:
            return [f"{item} 확인" for item in checklist[:4]]
        guidance = self._unique_card_values(turn.answer_cards, "allowed_guidance")
        if guidance:
            return guidance[:4]
        return ["검수된 카드 범위에서 확인할 항목을 먼저 정리하세요"]

    def _deterministic_specific_examples(self, turn: ChatTurnPlan) -> list[str]:
        examples = self._unique_card_values(turn.answer_cards, "specific_examples")
        if examples:
            return examples
        checklist = self._unique_card_values(turn.answer_cards, "checklist")
        if checklist:
            return checklist
        return ["검수된 answer card"]

    def _deterministic_caution_conditions(self, turn: ChatTurnPlan) -> list[str]:
        cautions = self._unique_card_values(turn.answer_cards, "caution_conditions")
        if cautions:
            return cautions
        return ["개인 의료 결정은 앱에서 단정하지 않고 전문가 확인이 필요할 수 있습니다"]

    def _deterministic_expert_check_points(self, turn: ChatTurnPlan) -> list[str]:
        check_points = self._deterministic_checklist_values(turn)
        if turn.policy.category == "medication_supplement_caution":
            return list(dict.fromkeys([*check_points[:4], "의사 또는 약사 확인"]))
        if check_points:
            return list(dict.fromkeys(check_points))
        return self._deterministic_caution_conditions(turn)

    def _deterministic_checklist_values(self, turn: ChatTurnPlan) -> list[str]:
        values: list[str] = []
        for card in turn.answer_cards:
            for value in card.checklist:
                values.append(self._display_checklist_value(card, value))
        return list(dict.fromkeys(values))

    def _display_checklist_value(self, card: AnswerCard, value: str) -> str:
        if value == "함량" and "마그네슘" in card.concrete_guidance:
            return "마그네슘 함량"
        return value

    def _unique_card_values(
        self,
        answer_cards: tuple[AnswerCard, ...],
        field_name: str,
    ) -> list[str]:
        values: list[str] = []
        for card in answer_cards:
            raw_values = getattr(card, field_name)
            values.extend(str(value) for value in raw_values if str(value).strip())
        return list(dict.fromkeys(values))

    def _has_structured_response_schema(self, data: dict[str, object]) -> bool:
        required = {
            "summary",
            "why_it_matters",
            "today_actions",
            "specific_examples",
            "caution_conditions",
            "expert_check_points",
            "source_basis",
        }
        return required.issubset(data)

    def _structured_string_list(self, value: object) -> list[str]:
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _extract_structured_json_object(self, text: str) -> str | None:
        stripped = text.strip()
        if not stripped:
            return None
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= MIN_MARKDOWN_CODE_FENCE_LINES and lines[0].strip().casefold() in {
                "```",
                "```json",
            }:
                stripped = "\n".join(lines[1:-1]).strip()
        if stripped.startswith("{"):
            return stripped

        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end <= start:
            return None
        return stripped[start : end + 1]

    def _bullet_lines(self, values: list[str]) -> str:
        return "\n".join(f"- {value}" for value in values)

    def _has_required_response_shape(self, text: str) -> bool:
        return REQUIRED_CHATBOT_SOURCE_MARKER in text and any(
            term in text for term in REQUIRED_CHATBOT_ACTION_TERMS
        )

    def _has_required_card_specificity(self, text: str, turn: ChatTurnPlan) -> bool:
        if turn.policy.category == "medication_supplement_caution":
            required_terms = ("마그네슘", "제품 라벨", "함량", "혈압약 종류", "신장 기능")
            return all(term in text for term in required_terms)
        return True

    def _card_must_not_say(self, answer_cards: tuple[AnswerCard, ...]) -> tuple[str, ...]:
        phrases: list[str] = []
        for card in answer_cards:
            phrases.extend(card.must_not_say)
        return tuple(dict.fromkeys(phrases))

    def _fallback_caution(
        self,
        request: ChatbotRequest,
        policy: AnswerPolicy,
        analysis: ChatIntentAnalysis,
    ) -> str:
        if analysis.primary_intent == "symptom" and not analysis.boundary:
            return "흉통, 숨참, 마비, 실신, 말이 어눌함 같은 증상이 있으면 일반 코칭을 중단하세요."
        if policy.category == "chronic_condition_context":
            return self._chronic_condition_caution(request)
        if policy.category == "supplement_question":
            return "건강기능식품은 제품 라벨의 섭취량과 성분 중복 여부를 먼저 확인하세요."
        if policy.category == "nutrition_analysis":
            return "KDRIs 영양 기준과 확인된 식사 기록을 기준으로 반복 패턴을 조절하세요."
        return "검수된 근거와 현재 질문 범위 안에서 다음 행동을 좁혀 보세요."

    def _symptom_next_action(self, analysis: ChatIntentAnalysis) -> str:
        if "diabetes" in analysis.related_conditions:
            return (
                "운동을 멈추고 휴식하며 수분을 보충한 뒤 서늘한 곳에서 증상을 보세요. "
                "당뇨 맥락에서는 저혈당 가능성도 조심스럽게 확인하세요."
            )
        return "운동을 멈추고 휴식하며 수분을 보충한 뒤 서늘한 곳에서 증상 변화를 보세요."

    def _fallback_management_points(
        self,
        analysis: ChatIntentAnalysis,
        knowledge_items: tuple[MedicalKnowledgeItem, ...],
    ) -> str:
        if analysis.primary_intent == "symptom" and not analysis.boundary:
            return "증상이 반복되거나 악화되면 운동 강도, 수분, 식사 간격을 기록하고 확인하세요."
        if "diabetes" in analysis.related_conditions and knowledge_items:
            return self._diabetes_management_points(knowledge_items)
        if "kidney_disease" in analysis.related_conditions and knowledge_items:
            return self._kidney_management_points(knowledge_items)
        return "한 번의 식사보다 반복 패턴을 보고 다음 기록에서 조절하세요."

    def _diabetes_management_points(
        self,
        knowledge_items: tuple[MedicalKnowledgeItem, ...],
    ) -> str:
        guidance = " ".join(item.concrete_guidance for item in knowledge_items)
        points: list[str] = []
        if "비전분 채소 1/2" in guidance:
            points.append("식사는 비전분 채소 1/2, 단백질 1/4, 탄수화물 1/4로 잡아 보세요")
            points.append(
                "채소 후보는 비전분 채소, 단백질 후보는 두부, 달걀, 생선구이, 콩류부터 고르세요"
            )
        if "주 150분" in guidance:
            points.append("운동은 주 150분 중강도 유산소와 주 2일 근력운동을 목표로 하세요")
        if "7시간" in guidance:
            points.append("수면은 성인 기준 하루 7시간 이상을 기록하세요")
        return "; ".join(points) if points else "식사, 운동, 수면, 체중 기록을 함께 보세요."

    def _kidney_management_points(
        self,
        knowledge_items: tuple[MedicalKnowledgeItem, ...],
    ) -> str:
        examples = self._unique_examples(knowledge_items)
        if examples:
            examples_text = ", ".join(examples[:4])
            return (
                "신장질환 맥락에서는 채소와 과일을 칼륨 제한 여부를 먼저 확인한 뒤 고르세요. "
                f"현재 카드에서 확인할 후보와 행동은 {examples_text}입니다. "
                "검사수치 해석이나 약 조정은 여기서 결정하지 않습니다."
            )
        return "신장질환 맥락에서는 채소와 과일의 칼륨 제한 여부를 먼저 확인하고, 국물과 가공식품은 줄이세요."

    def _unique_examples(
        self,
        knowledge_items: tuple[MedicalKnowledgeItem, ...],
    ) -> list[str]:
        examples: list[str] = []
        for item in knowledge_items:
            for example in item.specific_examples:
                if example not in examples:
                    examples.append(example)
        return examples

    def _source_basis_for_turn(self, turn: ChatTurnPlan) -> str:
        card_basis = self._source_basis_from_answer_cards(turn.answer_cards)
        if card_basis:
            return card_basis
        return self._source_basis(turn.knowledge_items)

    def _source_basis_from_answer_cards(self, answer_cards: tuple[AnswerCard, ...]) -> str:
        if not answer_cards:
            return ""

        source_names: list[str] = []
        for card in answer_cards:
            source_names.append(self._source_name_for_card(card))
        unique_sources = list(dict.fromkeys(source_names))
        return ", ".join(self._ordered_source_names(unique_sources))

    def _source_name_for_card(self, card: AnswerCard) -> str:
        source_id_names = {
            "kdris-2025": "KDRIs 영양 기준",
            "nih-ods-magnesium": "NIH ODS Magnesium Fact Sheet",
            "kdca-healthinfo": "질병관리청 건강정보",
        }
        if card.source_id in source_id_names:
            return source_id_names[card.source_id]
        prefix_names = {
            "niddk-": "NIDDK",
            "cdc-": "CDC",
        }
        for prefix, name in prefix_names.items():
            if card.source_id.startswith(prefix):
                return name
        if card.source_name and card.source_name != card.source_id:
            return card.source_name
        return card.source_id

    def _ordered_source_names(self, source_names: list[str]) -> list[str]:
        preferred = ("질병관리청 건강정보", "KDRIs 영양 기준")
        ordered = [source for source in preferred if source in source_names]
        ordered.extend(source for source in source_names if source not in preferred)
        return ordered

    def _source_basis(self, knowledge_items: tuple[MedicalKnowledgeItem, ...]) -> str:
        if not knowledge_items:
            return "질병관리청 건강정보, KDRIs 영양 기준"

        source_names = []
        for item in knowledge_items:
            if item.source_id == "kdca-healthinfo":
                source_names.append("질병관리청 건강정보")
            elif item.source_id == "kdris-2025":
                source_names.append("KDRIs 영양 기준")
            elif item.source.startswith("CDC"):
                source_names.append("CDC")
            elif item.source.startswith("NIDDK"):
                source_names.append("NIDDK")
            else:
                source_names.append(item.source)

        unique_sources = list(dict.fromkeys(source_names))
        return ", ".join(self._ordered_source_names(unique_sources))

    def _intent_analysis_summary(self, analysis: ChatIntentAnalysis) -> str:
        related = ", ".join(analysis.related_conditions) or "none"
        red_flags = ", ".join(analysis.red_flags) or "none"
        boundary = ", ".join(analysis.boundary) or "none"
        return (
            f"primary_intent={analysis.primary_intent}; category={analysis.category}; "
            f"related_conditions={related}; red_flags={red_flags}; boundary={boundary}"
        )

    def _knowledge_items_summary(
        self,
        knowledge_items: tuple[MedicalKnowledgeItem, ...],
    ) -> str:
        if not knowledge_items:
            return "none"
        return "\n".join(self._knowledge_card_text(item) for item in knowledge_items)

    def _answer_cards_summary(
        self,
        answer_cards: tuple[AnswerCard, ...],
    ) -> str:
        if not answer_cards:
            return "none"
        return "\n".join(self._answer_card_text(card) for card in answer_cards)

    def _answer_card_text(self, card: AnswerCard) -> str:
        return (
            f"- card_id={card.card_id} | answerability={card.answerability} | "
            f"source_id={card.source_id} | source_family={card.source_family} | "
            f"review_status={card.review_status} | version={card.version_label} | "
            f"topic={card.topic} | intent={card.intent} | condition={card.condition or 'general'} | "
            f"guidance={card.concrete_guidance} | allowed={'; '.join(card.allowed_guidance)} | "
            f"examples={', '.join(card.specific_examples)} | checklist={', '.join(card.checklist)} | "
            f"cautions={', '.join(card.caution_conditions)} | must_not_say={', '.join(card.must_not_say)} | "
            f"url={card.source_url}"
        )

    def _knowledge_card_text(self, item: MedicalKnowledgeItem) -> str:
        return (
            f"- {item.source} | source_id={item.source_id} | topic={item.topic} | "
            f"intent={item.intent} | condition={item.condition or 'general'} | "
            f"guidance={item.concrete_guidance} | allowed={'; '.join(item.allowed_guidance)} | "
            f"examples={', '.join(item.specific_examples)} | checklist={', '.join(item.checklist)} | "
            f"cautions={', '.join(item.caution_conditions)} | must_not_say={', '.join(item.must_not_say)} | "
            f"url={item.source_url}"
        )

    def _answer_strategy(self, turn: ChatTurnPlan) -> str:
        analysis = turn.analysis
        if analysis.boundary:
            return "Apply the boundary response and do not provide normal coaching."
        if analysis.category == "medication_supplement_caution":
            return (
                "Explain the general nutrient role and checklist from the card, "
                "but do not decide personal co-use safety."
            )
        if analysis.primary_intent == "symptom":
            return (
                "Start with red-flag screening, then rest, hydration, cool place, and observation."
            )
        if turn.answer_cards:
            return "Use the reviewed answer cards as concrete coaching points without exposing raw retrieval."
        if turn.knowledge_items:
            return "Use the reviewed guidance items as concrete coaching points without exposing raw retrieval."
        return "Use general health-management coaching only within the allowed source families."

    def _is_sodium_meal_question(self, turn: ChatTurnPlan) -> bool:
        text = self._condition_context(turn.request)
        return turn.analysis.primary_intent == "meal" and self._has_any_context_term(
            text,
            (
                "나트륨",
                "소금",
                "짠",
                "고혈압",
                "혈압",
                "라면",
                "찌개",
                "국물",
                "소스",
                "장류",
                "가공육",
            ),
        )

    def _has_nutrition_candidate_card(self, turn: ChatTurnPlan) -> bool:
        nutrition_candidate_topics = {
            "vitamin_d_food_candidates",
            "protein_food_candidates",
            "fiber_food_candidates",
        }
        return any(card.topic in nutrition_candidate_topics for card in turn.answer_cards)

    def _chronic_condition_caution(self, request: ChatbotRequest) -> str:
        condition_context = self._condition_context(request)
        if self._has_any_context_term(condition_context, DIABETES_CONTEXT_TERMS):
            return (
                "당뇨 맥락에서는 밥, 면, 빵 같은 탄수화물 양과 초콜릿, 아이스크림 같은 "
                "당류 간식을 한 번에 많이 먹는 패턴을 줄이는 것이 좋습니다."
            )
        if self._has_any_context_term(condition_context, HYPERTENSION_CONTEXT_TERMS):
            return "고혈압 맥락에서는 짠 국물, 가공식품, 반복적인 고나트륨 식사를 줄이는 것이 좋습니다."
        if self._has_any_context_term(condition_context, KIDNEY_CONTEXT_TERMS):
            return (
                "신장질환/콩팥 질환 맥락에서는 짠 음식과 가공식품을 줄이되, 채소와 과일은 "
                "칼륨 제한을 들은 적이 있는지 먼저 확인해야 합니다."
            )
        return "질환 맥락에서는 한 번의 식사보다 반복되는 과식, 고나트륨, 고당류 패턴을 줄이는 것이 좋습니다."

    def _chronic_condition_next_action(self, request: ChatbotRequest) -> str:
        condition_context = self._condition_context(request)
        if self._has_any_context_term(condition_context, DIABETES_CONTEXT_TERMS):
            if self._has_any_context_term(
                condition_context,
                ("개선", "관리", "운동", "수면", "체중관리", "체중 관리", "lifestyle"),
            ):
                return (
                    "식사는 접시 구성을 단순하게 잡고, 운동은 걷기부터 시작하며, "
                    "수면과 체중 기록을 함께 확인해 주세요."
                )
            if self._has_any_context_term(
                condition_context,
                ("식단", "짜줘", "점심", "저녁", "메뉴", "meal plan"),
            ):
                return (
                    "점심은 현미밥이나 잡곡밥 양을 작게 잡고 두부, 달걀, 생선구이 같은 "
                    "단백질 반찬과 채소 반찬을 곁들이세요. 저녁은 밥, 면, 빵 양을 더 줄이고 "
                    "채소와 단백질 중심으로 구성하며 달콤한 간식은 다음 기록에서 줄여 보세요."
                )
            return (
                "저녁은 밥 양을 줄이고 채소와 단백질 반찬을 곁들이며, 달콤한 간식은 "
                "다음 기록에서 줄여 보세요."
            )
        if self._has_any_context_term(condition_context, HYPERTENSION_CONTEXT_TERMS):
            return (
                "다음 끼니에서 짠 국물, 짠 반찬, 가공식품을 줄이고 혈압 반응처럼 "
                "직접 확인 가능한 기록을 우선 점검해 주세요."
            )
        if self._has_any_context_term(condition_context, KIDNEY_CONTEXT_TERMS):
            return (
                "다음 끼니에서는 국물과 가공식품을 줄이고, 채소·과일은 칼륨 제한 여부와 "
                "최근 검사 결과를 확인한 뒤 선택해 주세요."
            )
        return "다음 끼니에서는 과식, 짠 음식, 당류 간식을 줄이고 확인 가능한 기록을 우선 점검해 주세요."

    def _condition_context(self, request: ChatbotRequest) -> str:
        parts = [request.message]
        profile = request.context.get("profile")
        if isinstance(profile, dict):
            conditions = profile.get("chronic_conditions")
            if isinstance(conditions, list):
                parts.extend(str(condition) for condition in conditions)

        parts.extend(turn.content for turn in request.conversation[-6:])
        return " ".join(parts).casefold()

    def _label_only_supplement_names(self, context: dict[str, object]) -> tuple[str, ...]:
        snapshot = context.get("user_health_context_snapshot")
        if not isinstance(snapshot, dict):
            return ()
        supplement_snapshot = snapshot.get("active_supplement_snapshot")
        if not isinstance(supplement_snapshot, dict):
            return ()
        supplements = supplement_snapshot.get("registered_supplements")
        if not isinstance(supplements, list):
            return ()
        names: list[str] = []
        for supplement in supplements:
            if not isinstance(supplement, dict):
                continue
            ingredients = supplement.get("ingredients")
            if not isinstance(ingredients, list):
                continue
            for ingredient in ingredients:
                if not isinstance(ingredient, dict):
                    continue
                if ingredient.get("analysis_use") != "label_only":
                    continue
                display_name = ingredient.get("display_name")
                if isinstance(display_name, str) and display_name.strip():
                    names.append(display_name.strip())
        return tuple(dict.fromkeys(names))

    def _has_any_context_term(self, text: str, terms: tuple[str, ...]) -> bool:
        return any(term.casefold() in text for term in terms)

    def _confirmed_food_summary(self, context: dict[str, object]) -> str:
        entries = context.get("latest_confirmed_entries")
        if not isinstance(entries, dict):
            return ""

        foods = entries.get("foods")
        if not isinstance(foods, list):
            return ""

        lines: list[str] = []
        for raw_food in foods[:6]:
            if not isinstance(raw_food, dict):
                continue

            name = self._clean_label(raw_food.get("name"))
            if not name:
                continue

            meal_type = self._clean_label(raw_food.get("meal_type"))
            meal_label = MEAL_LABELS.get(meal_type.casefold(), meal_type or "식사")
            nutrient_text = self._nutrient_summary(raw_food.get("nutrients"))
            if nutrient_text:
                lines.append(f"{meal_label}: {name}, {nutrient_text}")
            else:
                lines.append(f"{meal_label}: {name}")

        return "\n".join(lines)

    def _inline_text(self, value: str) -> str:
        return "; ".join(part.strip() for part in value.splitlines() if part.strip())

    def _nutrient_summary(self, raw_nutrients: object) -> str:
        if not isinstance(raw_nutrients, list):
            return ""

        nutrients: list[str] = []
        for raw_nutrient in raw_nutrients[:6]:
            if not isinstance(raw_nutrient, dict):
                continue

            raw_name = self._clean_label(raw_nutrient.get("name"))
            amount = raw_nutrient.get("amount")
            unit = self._clean_label(raw_nutrient.get("unit"))
            if not raw_name or amount is None or not unit:
                continue

            name = NUTRIENT_LABELS.get(raw_name.casefold(), raw_name)
            nutrients.append(f"{name} {self._format_amount(amount)}{unit}")

        return ", ".join(nutrients)

    def _clean_label(self, value: object) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip()

    def _format_amount(self, value: object) -> str:
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            return str(int(value)) if value.is_integer() else f"{value:g}"
        return str(value).strip()
