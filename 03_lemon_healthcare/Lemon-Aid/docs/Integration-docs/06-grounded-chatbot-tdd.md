# 06. 근거 기반 동적 답변 프레임 챗봇 TDD

> Status: technical design draft
> 작성일: 2026-05-29
> 기준 브랜치: `feat/ai-agent-backend-integration`
> PRD: [05-grounded-chatbot-prd.md](./05-grounded-chatbot-prd.md)
> 용어: 이 문서의 TDD는 `Technical Design Document`를 의미한다.

## 1. 목표 아키텍처

목표는 수동 질문 카드를 몇 개 늘리는 것이 아니라, 모든 사용자-facing 건강 답변을
같은 grounding pipeline으로 통과시키는 것이다.

이 문서에서 `AnswerCard`는 제품 관점의 수동 FAQ 카드가 아니다. 검색된 reviewed
source/evidence를 LLM 입력과 deterministic fallback에 쓰기 위해 정리한 내부 답변
프레임이다. 수동 seed는 초기 품질 기준과 golden test를 고정하기 위한 부트스트랩이며,
장기 coverage mechanism은 reviewed evidence retrieval과 `AnswerCardNormalizer`다.

```text
ChatbotRequest
  -> ChatTurnModule
  -> QuestionClassifier
  -> MedicalKnowledgeRetriever
  -> AnswerCardNormalizer
  -> AnswerabilityPolicy
  -> ChatbotAgent
  -> LLMCompletion 또는 deterministic renderer
  -> SafetyEnvelope
  -> ChatbotResponse
```

핵심 불변식:

- reviewed source 없는 건강 사실은 답변에 들어가지 않는다.
- LLM prompt에는 raw chunk가 아니라 정규화된 `AnswerCard`만 들어간다.
- fallback도 같은 `AnswerCard`를 사용한다.
- boundary와 urgent escalation은 retrieval/LLM보다 먼저 적용한다.
- retrieval 실패는 안전 경계를 우회하지 않는다.

## 2. 현재 구현과 gap

현재 구현에 이미 있는 것:

- `ChatTurnModule`이 policy, intent analysis, knowledge item을 묶는다.
- `MedicalKnowledgeItem`이 내부 답변 프레임용 필드를 일부 갖는다.
- `policy_for_question()`과 `analyze_chat_intent()`가 질문을 분류한다.
- `ChatbotAgent`가 LLM 응답을 SafetyEnvelope로 검증하고 fallback한다.
- `SafetyGuard`가 금지 표현, unsupported fact, unsupported numeric claim을 차단한다.
- golden test가 마그네슘/나트륨/응급/P0 병용 등을 검증한다.

현재 gap:

- `select_medical_knowledge()`가 정적 `MEDICAL_KNOWLEDGE_ITEMS`를 순회한다.
- reviewed source DB나 chunk retrieval이 chat answer path에 직접 연결되어 있지 않다.
- 검색 결과를 내부 답변 프레임으로 정규화하는 계층이 없다.
- reviewed source가 없는 질문을 `unknown_no_reviewed_source`로 fail-closed하는 계약이
  약하다.
- manual seed가 부트스트랩인지 coverage mechanism인지 코드 경계가 명확하지 않다.

## 3. 핵심 타입

### `Answerability`

```python
Answerability = Literal[
    "answerable",
    "answerable_with_caution",
    "needs_more_info",
    "unknown_no_reviewed_source",
    "medical_decision_boundary",
    "urgent_escalation",
]
```

### `AnswerCard`

```python
@dataclass(frozen=True)
class AnswerCard:
    card_id: str
    answerability: Answerability
    topic: str
    intent: ChatIntent
    condition: Condition | None
    allowed_guidance: tuple[str, ...]
    specific_examples: tuple[str, ...]
    checklist: tuple[str, ...]
    caution_conditions: tuple[str, ...]
    must_not_say: tuple[str, ...]
    source_id: str
    source_url: str
    source_family: SourceFamily
    source_version_id: str | None
    version_label: str
    review_status: SourceStatus
    reviewed_at: date
    expires_at: date
    grounding_snippet_ids: tuple[str, ...]
```

`MedicalKnowledgeItem`은 v1 migration 동안 seed evidence alias로 유지할 수 있다. 최종
runtime에서는 내부 답변 프레임인 `AnswerCard`를 표준 입력으로 사용한다.

### `KnowledgeRetrievalResult`

```python
@dataclass(frozen=True)
class KnowledgeRetrievalResult:
    cards: tuple[AnswerCard, ...]
    missing_topics: tuple[str, ...]
    warnings: tuple[str, ...]
    retrieval_status: Literal["found", "no_match", "stale_only", "not_reviewed_only"]
```

## 4. 질문 분류 설계

기존 category를 answerability 중심으로 보강한다.

| 기존/신규 의도 | answerability | LLM 호출 |
| --- | --- | --- |
| 일반 식사/운동/수면 | `answerable` | 가능 |
| 만성질환 생활관리 | `answerable` 또는 `answerable_with_caution` | 가능 |
| 일반 약/영양제 병용 주의 | `answerable_with_caution` | 가능 |
| 약 중단/증량/감량/복용량 결정 | `medical_decision_boundary` | 금지 |
| 검사수치 치료 판단 | `medical_decision_boundary` | 금지 |
| P0 병용 조합 | `medical_decision_boundary` | 금지 |
| 임신/신장질환/심한 증상 결합 병용 판단 | `medical_decision_boundary` 또는 `needs_more_info` | 원칙 금지 |
| 가슴통증/숨참/마비/실신/자해 | `urgent_escalation` | 금지 |
| reviewed source 없음 | `unknown_no_reviewed_source` | 금지 또는 unknown renderer |

분류 순서:

1. urgent escalation keyword와 self-harm risk를 먼저 본다.
2. diagnosis/treatment/prescription/dose/lab-value decision boundary를 본다.
3. P0 interaction 조합과 high-risk context를 본다.
4. 일반 caution 가능한 medication/supplement 질문을 분리한다.
5. 생활관리, 식사, 운동, 수면, 체중, 증상 경도 질문을 분류한다.
6. retrieval 결과가 없으면 `unknown_no_reviewed_source`로 재분류한다.

## 5. Retrieval 설계

### v1 repository

초기 구현은 DB와 registry를 모두 지원하되 production-like 경로는 DB-backed reviewed
source를 우선한다.

```python
class MedicalKnowledgeRetriever:
    def retrieve(self, query: KnowledgeQuery) -> KnowledgeRetrievalResult:
        ...
```

`KnowledgeQuery` 필드:

- normalized question text
- primary intent
- category
- related conditions
- medication/supplement entities
- requested decision type
- locale/jurisdiction

검색 대상:

- `medical_evidence_items.review_status == "reviewed"`
- source version이 reviewed이고 `expires_at >= today`
- `user_facing_allowed == true`
- topic/intent/condition/source_family가 질문과 관련 있음

검색 제외:

- `draft`
- `paper_candidate`
- `deprecated`
- stale source
- raw web search 결과
- raw OCR/raw prompt/raw LLM output

### v1 matching

MVP에서는 BM25/vector 없이도 아래 순서로 시작할 수 있다.

1. entity/keyword/topic rule matching
2. source_family/category filter
3. condition filter
4. caution_level filter
5. score threshold

이후 v2에서 `medical_rag_chunks`와 vector index를 붙인다. vector 결과도 바로 prompt에
넣지 않고 `AnswerCardNormalizer`를 반드시 통과한다.

## 6. AnswerCardNormalizer 설계

Normalizer는 retrieval record를 사용자 답변용 내부 답변 프레임으로 바꾼다.

입력 후보:

- `medical_evidence_items.allowed_user_wording`
- `medical_evidence_items.blocked_wording`
- `medical_evidence_items.applicability_note`
- `medical_policy_boundaries.allowed_response_pattern`
- `medical_policy_boundaries.blocked_response_pattern`
- `medical_rag_chunks.chunk_text` 중 reviewed/not stale chunk
- 기존 seed `MedicalKnowledgeItem`

정규화 규칙:

- `allowed_guidance`는 사용자가 할 수 있는 낮은 위험 행동만 담는다.
- `specific_examples`는 음식, 행동, 체크 항목처럼 답변 구체성을 만드는 재료다.
- `checklist`는 사용자가 오늘 확인할 항목이다.
- `caution_conditions`는 전문가 확인, 중단, 응급 행동으로 넘어가는 조건이다.
- `must_not_say`는 SafetyGuard와 golden test에 전달한다.
- source metadata는 반드시 카드에 남긴다.

정규화 실패 조건:

- source metadata 없음
- reviewed status 아님
- allowed guidance 없음
- must_not_say 없음
- topic이 질문과 낮은 관련도
- 금지 표현이 allowed guidance에 섞임

실패하면 해당 후보를 버리고 retrieval warning을 남긴다.

## 7. ChatbotAgent 변경

`ChatbotAgent`는 `MedicalKnowledgeItem` tuple 대신 `AnswerCard` tuple을 표준으로 받는다.

동작:

1. `ChatTurnModule.plan()`이 answerability와 cards를 만든다.
2. `urgent_escalation`과 `medical_decision_boundary`는 deterministic boundary renderer로
   즉시 종료한다.
3. `unknown_no_reviewed_source`는 unknown renderer로 즉시 종료한다.
4. answerable 계열은 LLM client가 있으면 `AnswerCard` only prompt를 만든다.
5. LLM 출력이 shape/detail/safety 검증을 통과하지 못하면 card renderer fallback으로
   내려간다.
6. fallback은 일반론이 아니라 카드의 examples/checklist/caution을 사용한다.

LLM prompt 금지:

- raw chunk 전문
- raw prompt/internal trace
- source registry 전체 dump
- draft/paper_candidate
- "known by the model" 같은 일반 지식 허용 문구

## 8. Renderer 설계

### `CardAnswerRenderer`

질문 유형별 섹션을 만든다.

- meal/condition: `요약`, `오늘 바꿀 것`, `추천 음식 후보`, `피할 조합`, `주의 조건`,
  `출처 기준`
- medication/supplement caution: `요약`, `왜 확인이 필요한가`, `오늘 확인할 것`,
  `상대적으로 안전한 대안`, `전문가 확인이 필요한 지점`, `출처 기준`
- unknown: `요약`, `현재 답할 수 없는 이유`, `필요한 검수 지식`, `지금 할 수 있는 안전한 행동`

### `BoundaryRenderer`

LLM 없이 응급/의료 결정 경계 답변을 만든다.

- urgent: 위험 이유를 먼저 짧게 말하고 119/응급실 행동을 마지막에 둔다.
- medical decision: 제품이 결정하지 않는다고 말하고, 의료진에게 가져갈 정보 목록을
  안내한다.
- P0 interaction: 약/제품 이름, 라벨, 처방 정보, 신장/간 기능 등 확인 항목을 안내하되
  병용 가능/금지를 단정하지 않는다.

## 9. SafetyGuard 보강

기존 금지 표현은 유지한다.

추가 테스트 기준:

- 허용: "먹어도 되는지 여부는 약 종류와 상태에 따라 달라질 수 있습니다."
- 허용: "제품 라벨의 마그네슘 함량을 확인하세요."
- 금지: "혈압약과 함께 먹어도 됩니다."
- 금지: "혈압약을 줄이세요."
- 금지: "라면은 절대 먹지 마세요."
- 금지: reviewed `AnswerCard`에 없는 새 용량, 혈압, 검사수치 기준

Grounding check:

- 출력의 source_id/source_family가 카드 metadata와 일치해야 한다.
- 수치 claim은 사용자 입력 또는 카드/grounding snippet에 존재할 때만 허용한다.
- `must_not_say`와 유사한 문구가 출력되면 fallback한다.

## 10. API 계약

`POST /api/v1/ai-agent/chat` 응답은 기존 필드와 호환하되 source detail을 확장한다.

추가 또는 강화 필드 후보:

- `answerability`
- `source_families`
- `sources[]`
  - `source_id`
  - `source_family`
  - `review_status`
  - `version_label`
  - `reviewed_at`
  - `expires_at`
- `safety_warnings`
- `requires_user_approval`
- `requires_professional_review`

주의:

- raw prompt, raw LLM response, raw OCR, internal trace는 응답에 넣지 않는다.
- unknown 응답도 정상 200 + `answerability=unknown_no_reviewed_source`로 처리할 수 있다.
  단, 동의 없는 호출은 기존처럼 consent boundary를 유지한다.

## 11. Test Design

### Unit

- `test_answer_card_normalizer.py`
  - reviewed record를 카드로 변환
  - draft/paper/stale record 제외
  - 필수 필드 누락 시 카드 폐기
  - must_not_say가 SafetyGuard 입력으로 전달

- `test_medical_knowledge_retriever.py`
  - topic/condition/intent matching
  - no reviewed source -> `unknown_no_reviewed_source`
  - stale only -> `source_stale` warning
  - registry fallback은 local/dev에서만 허용

- `test_chatbot_agent.py`
  - reviewed `AnswerCard`가 있는 질문은 구체 답변
  - reviewed `AnswerCard`가 없는 질문은 unknown
  - P0/응급은 LLM 미호출
  - LLM이 `AnswerCard` 밖 사실을 만들면 fallback

- `test_safety_guard.py`
  - 좋은 caution 문구는 허용
  - 개인 복용 가능/금지 단정은 차단
  - grounded number만 허용

### Integration

- `backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py`
  - `/api/v1/ai-agent/chat`에서 answerability/source metadata 유지
  - consent 없으면 기존처럼 차단
  - unknown_no_reviewed_source 응답 계약
  - boundary 질문은 LLM 미호출
  - caution 질문은 LLM 가능하되 fallback 안전

### Golden set

초기 golden set:

- 나트륨 저녁 조정
- 당뇨 과식 후 다음 끼니
- 고혈압 라면 조정
- 신장질환 칼륨 주의
- 혈압약+마그네슘
- 와파린+비타민 K
- 갑상선약+칼슘/철분
- LDL 검사수치 치료 판단
- 가슴통증+숨참
- 검수 지식 없는 성분/제품 조합

## 12. Migration Plan

1. 현 seed `MedicalKnowledgeItem`을 `AnswerCard` seed adapter로 감싼다.
2. `Answerability`와 unknown response contract를 추가한다.
3. `AnswerCardNormalizer`와 테스트를 만든다.
4. registry-backed retriever를 먼저 만든다.
5. `medical_source_readiness`와 DB-backed source governance를 chat path에 연결한다.
6. production-like path에서 reviewed source 없으면 fail-closed한다.
7. `ChatbotAgent` prompt/fallback을 `AnswerCard` only로 바꾼다.
8. API response에 source detail과 answerability를 추가한다.
9. golden/API/safety 테스트를 확장한다.
10. 그 다음 `medical_rag_chunks`/vector retrieval을 별도 PR로 붙인다.

## 13. Completion Criteria

- 모든 사용자-facing 건강 답변이 `AnswerCard`, boundary renderer, unknown renderer 중 하나에서 생성된다.
- reviewed source 없는 질문은 LLM 일반 지식으로 답하지 않는다.
- route-level integration test가 answerability, source metadata, consent, safety boundary를
  함께 검증한다.
- manual seed는 seed/golden fixture로만 남고, 새 coverage는 retriever+normalizer+reviewed
  evidence update로 확장된다.
