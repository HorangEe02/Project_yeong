# 08. 근거 기반 동적 답변 프레임 챗봇 TRD

> Status: technical requirements draft
> 작성일: 2026-05-29
> 기준 브랜치: `feat/ai-agent-backend-integration`
> PRD: [05-grounded-chatbot-prd.md](./05-grounded-chatbot-prd.md)
> 관련 기술설계: [06-grounded-chatbot-tdd.md](./06-grounded-chatbot-tdd.md)
> 구현 TODO: [07-grounded-chatbot-todo.md](./07-grounded-chatbot-todo.md)
> 용어: 이 문서의 TRD는 `Technical Requirements Document`를 의미한다.

## 1. 목적

이 문서는 PRD의 제품 요구를 구현자가 바로 테스트와 코드 요구사항으로 옮길 수 있게
기술 요구사항으로 분해한다.

핵심 목표:

- 모든 사용자-facing 건강 답변은 검수된 지식 또는 boundary renderer에서 생성한다.
- 수동 질문 카드 몇 개가 아니라, 검색된 검수 지식을 표준 내부 답변 프레임인 `AnswerCard`로
  정규화해 답한다.
- 검수 지식이 없으면 LLM 일반 지식으로 채우지 않고 fail-closed unknown 응답을 낸다.
- LLM은 문장 작성만 담당하고, 의료 사실 생성이나 개인 의료 판단을 하지 않는다.

## 2. 요구사항 용어

- `MUST`: 구현하지 않으면 PRD 목표 미달이다.
- `SHOULD`: 기본 구현 기준이다. 예외가 있으면 PR 또는 설계 문서에 이유를 남긴다.
- `MAY`: MVP 이후 확장 후보다.
- `AnswerCard`: 질문별로 미리 만들어두는 수동 FAQ 카드가 아니다. 검색된 reviewed
  evidence/source를 LLM 입력과 deterministic fallback에 쓰기 위해 정리한 내부 답변
  프레임이다. 장기 목표는 manual seed를 늘리는 것이 아니라 reviewed knowledge를
  검색하고 매번 `AnswerCard` shape로 동적 정규화하는 것이다.

## 3. 시스템 범위

포함 범위:

- `POST /api/v1/ai-agent/chat`
- `backend/ai_agent_chat`의 질문 분류, retrieval, `AnswerCard` normalization, rendering,
  SafetyGuard, LLM prompt/fallback
- `backend/Nutrition-backend`의 source readiness, DB-backed reviewed source 연결,
  API response contract
- 문서화된 golden test와 route integration test

제외 범위:

- live web search 직접 답변
- unreviewed paper/internal note 사용자-facing 노출
- 치료, 처방, 복약량, 병용 가능 여부 확정
- 의료 사실 fine-tuning
- RAG/vector DB를 safety boundary보다 먼저 적용하는 구조

## 4. 기능 요구사항

### TRD-FR-001. 질문 분류

- 시스템은 모든 사용자 질문을 answerability 기준으로 분류해야 한다.
- 지원 상태는 `answerable`, `answerable_with_caution`, `needs_more_info`,
  `unknown_no_reviewed_source`, `medical_decision_boundary`, `urgent_escalation`이다.
- 응급/자해 위험은 retrieval과 LLM 호출보다 먼저 판정해야 한다.
- 검사수치 치료 판단, 처방/복용량 변경, 약 중단/증량/감량 요청은
  `medical_decision_boundary`로 분류해야 한다.
- 일반 약/영양제 병용 질문은 P0/high-risk 조합이 아니면
  `answerable_with_caution`으로 설명 가능해야 한다.

완료 증거:

- `test_chat_turn.py` 또는 `test_medical_knowledge_registry.py`
- `test_chatbot_agent.py`의 P0, magnesium, emergency, lab-value 케이스

### TRD-FR-002. 검수 지식 검색

- 시스템은 사용자-facing 답변에 reviewed, not stale, user-facing allowed source만
  검색 대상으로 사용해야 한다.
- `draft`, `paper_candidate`, `deprecated`, stale source는 검색 결과에서 제외해야 한다.
- 검색 결과가 없으면 `unknown_no_reviewed_source`로 내려가야 한다.
- local/dev registry fallback은 허용할 수 있으나 production-like 경로에서는 DB-backed
  reviewed source가 없을 때 fail-closed해야 한다.

완료 증거:

- `test_medical_knowledge_retriever.py`
- `test_medical_source_readiness.py`
- `/api/v1/ai-agent/chat` unknown integration test

### TRD-FR-003. 내부 답변 프레임 정규화

- 검색 결과는 LLM prompt에 직접 들어가면 안 된다.
- 모든 검색 결과는 내부 답변 프레임인 `AnswerCard`로 정규화되어야 한다.
- `AnswerCard`는 최소한 아래 필드를 가져야 한다.
  - `card_id`
  - `answerability`
  - `topic`
  - `intent`
  - `condition`
  - `allowed_guidance`
  - `specific_examples`
  - `checklist`
  - `caution_conditions`
  - `must_not_say`
  - `source_id`
  - `source_url`
  - `source_family`
  - `source_version_id` 또는 `version_label`
  - `review_status`
  - `reviewed_at`
  - `expires_at`
  - `grounding_snippet_ids`
- 필수 필드가 누락되거나 reviewed source가 아니면 카드를 폐기해야 한다.

완료 증거:

- `test_answer_card_normalizer.py`
- `test_medical_knowledge_registry.py`

### TRD-FR-004. 내부 답변 프레임 기반 답변 생성

- `answerable`과 `answerable_with_caution` 응답은 하나 이상의 `AnswerCard`에서
  생성되어야 한다.
- deterministic fallback도 같은 내부 답변 프레임인 `AnswerCard`를 사용해야 한다.
- fallback은 "확인된 기록을 보세요" 수준의 일반 문구만 내면 안 된다.
- 식사 질문은 카드의 `specific_examples`를 사용해 구체 음식/행동 후보를 포함해야 한다.
- 약/영양제 caution 질문은 카드의 `checklist`와 `caution_conditions`를 사용해야 한다.

완료 증거:

- 나트륨 저녁, 당뇨 과식, 고혈압 라면, 혈압약+마그네슘 golden test

### TRD-FR-005. Unknown 응답

- reviewed `AnswerCard`가 없는 건강 질문은 LLM 일반 지식으로 답하면 안 된다.
- unknown 응답은 사용자에게 "현재 검수된 지식 안에서 답할 수 없음"을 알려야 한다.
- unknown 응답은 필요한 검수 지식, 사용자가 제공할 수 있는 정보, 낮은 위험도의 일반 행동만
  안내해야 한다.
- unknown 응답에도 raw/internal trace를 노출하면 안 된다.

완료 증거:

- `unknown_no_reviewed_source` unit test
- route-level unknown integration test

### TRD-FR-006. Boundary 응답

- `urgent_escalation`과 `medical_decision_boundary`는 LLM을 호출하지 않아야 한다.
- 응급 응답은 위험 이유를 먼저 짧게 설명하고 119 또는 응급실 행동을 안내해야 한다.
- 의료 결정 boundary는 제품이 결정하지 않는다고 말하고, 의료진에게 가져갈 정보 목록을
  안내해야 한다.
- P0 병용 boundary는 약/제품 이름, 라벨, 처방 정보, 신장/간 기능 등 확인 항목을
  안내하되 병용 가능/금지를 단정하면 안 된다.

완료 증거:

- emergency no-LLM test
- lab-value no-LLM test
- P0 interaction no-LLM test

### TRD-FR-007. LLM prompt

- LLM prompt에는 `AnswerCard` summary만 전달해야 한다.
- LLM prompt에는 raw prompt, raw OCR, raw LLM output, internal trace, draft source,
  paper candidate, source registry 전체 dump를 넣으면 안 된다.
- LLM system rule은 `AnswerCard` 밖 건강 사실 생성 금지, 개인 의료 결정 금지, unknown 시 답변
  생성 금지를 포함해야 한다.
- LLM 출력이 required section, card specificity, safety 검증을 통과하지 못하면 fallback해야
  한다.

완료 증거:

- prompt capture test
- missing section fallback test
- unsupported fact/numeric fallback test

### TRD-FR-008. API 응답 계약

- `/api/v1/ai-agent/chat` 응답은 기존 mobile 호환성을 유지하면서 additive field를
  추가해야 한다.
- 응답은 `answerability`를 포함해야 한다.
- 응답은 reviewed source metadata를 포함해야 한다. 최소 후보는 `source_id`,
  `source_family`, `review_status`, `version_label`, `reviewed_at`, `expires_at`이다.
- 응답은 raw prompt, raw LLM response, raw OCR, internal trace, draft source를 포함하면
  안 된다.
- 동의 없는 민감 건강 분석 요청은 기존 consent boundary를 유지해야 한다.

완료 증거:

- `test_ai_agent_api.py`
- mobile DTO 호환성 테스트가 있는 경우 해당 테스트

## 5. 비기능 요구사항

### TRD-NFR-001. 안전성

- SafetyGuard는 진단, 치료, 처방, 복용량 변경, 안전성 단정, 절대 금지 표현을 차단해야
  한다.
- `AnswerCard` 근거에 없는 수치 claim은 차단해야 한다.
- `must_not_say`와 유사한 표현은 출력되면 안 된다.

### TRD-NFR-002. 추적성

- 사용자-facing 건강 사실은 source metadata로 추적 가능해야 한다.
- source version, review status, reviewed date, expiry가 테스트 또는 response metadata에서
  확인 가능해야 한다.

### TRD-NFR-003. 최신성

- stale source는 사용자-facing `AnswerCard`로 만들면 안 된다.
- source expiry 기준은 DB-backed source governance 또는 registry metadata에서 판정해야
  한다.

### TRD-NFR-004. 개인정보와 내부 정보 보호

- raw prompt, raw LLM response, provider payload 전문, raw OCR text, raw image bytes,
  EXIF, 원본 파일명, internal trace는 DB/API/LLM prompt/user response에 노출하지 않는다.
- 사용자별 민감 건강 context는 consent gate 이후에만 사용한다.

### TRD-NFR-005. 테스트 가능성

- 모든 안전 경계는 unit 또는 integration test로 고정해야 한다.
- 새 source family 또는 answerability를 추가할 때는 golden test를 함께 추가해야 한다.
- LLM provider가 없어도 deterministic renderer로 핵심 정책을 검증할 수 있어야 한다.

## 6. 데이터 요구사항

### Source record

source record는 최소한 아래 정보를 제공해야 한다.

- `source_id`
- `source_family`
- `publisher`
- `title`
- `canonical_url`
- `jurisdiction`
- `review_status`
- `version_label`
- `reviewed_at`
- `expires_at`
- `user_facing_allowed`

### Evidence item

evidence item은 최소한 아래 정보를 제공해야 한다.

- `topic`
- `audience`
- `claim_summary`
- `allowed_user_wording`
- `blocked_wording`
- `applicability_note`
- `caution_level`
- `review_status`

### AnswerCard

AnswerCard는 PRD 8장의 필드와 이 문서 TRD-FR-003을 따른다. 이름은 card지만 제품
관점에서는 수동 질문 카드가 아니라 동적으로 생성되는 grounded answer frame이다.

## 7. 모듈별 기술 요구사항

| 모듈 | 요구사항 |
| --- | --- |
| `ChatTurnModule` | 질문 분류, intent analysis, retrieval query 생성, answerability 결정 |
| `MedicalKnowledgeRetriever` | reviewed/not stale/user-facing source만 검색 |
| `AnswerCardNormalizer` | 검색 결과를 표준 AnswerCard로 변환, 부적격 후보 폐기 |
| `ChatbotAgent` | `AnswerCard` only prompt, boundary/unknown/AnswerCard renderer 선택 |
| `SafetyGuard` | 금지 표현, unsupported fact, unsupported numeric claim, card grounding 검증 |
| `Nutrition-backend API route` | consent gate, response contract, raw/internal field 비노출 |
| `medical_source_readiness` | DB-backed reviewed source readiness와 local/dev fallback 경계 |

## 8. 상태 전이 요구사항

```text
urgent keyword/self-harm
  -> urgent_escalation

medical decision request or P0 interaction
  -> medical_decision_boundary

answerable-looking question + reviewed AnswerCards found
  -> answerable or answerable_with_caution

answerable-looking question + missing required user info
  -> needs_more_info

answerable-looking question + no reviewed AnswerCards
  -> unknown_no_reviewed_source
```

상태 전이는 deterministic해야 한다. LLM 출력에 따라 answerability가 완화되면 안 된다.

## 9. 테스트 요구사항 매핑

| 요구사항 | 테스트 |
| --- | --- |
| TRD-FR-001 | classifier/chat_turn tests |
| TRD-FR-002 | retriever/readiness tests |
| TRD-FR-003 | answer_card_normalizer tests |
| TRD-FR-004 | chatbot golden tests |
| TRD-FR-005 | unknown response tests |
| TRD-FR-006 | no-LLM boundary tests |
| TRD-FR-007 | prompt capture and fallback tests |
| TRD-FR-008 | API integration tests |
| TRD-NFR-001 | safety guard tests |
| TRD-NFR-002 | source metadata contract tests |
| TRD-NFR-003 | stale source tests |
| TRD-NFR-004 | raw/internal field negative tests |
| TRD-NFR-005 | no-LLM deterministic tests |

## 10. 구현 우선순위

1. `Answerability`와 unknown response contract를 먼저 고정한다.
2. `AnswerCard` seed adapter와 normalizer를 만든다.
3. registry-backed retriever를 붙이고 no reviewed source fail-closed를 구현한다.
4. `ChatTurnModule`을 answerability/card 기반으로 재배선한다.
5. `ChatbotAgent` prompt와 fallback을 `AnswerCard` only로 바꾼다.
6. SafetyGuard grounding을 `must_not_say`와 card numeric claim 기준으로 강화한다.
7. API response에 additive source metadata를 추가한다.
8. DB-backed reviewed source readiness와 production fail-closed를 연결한다.
9. RAG/vector DB는 reviewed source governance와 card normalizer가 안정된 뒤 별도 PR로 붙인다.

## 11. 완료 기준

- PRD의 모든 MVP 포함 요구가 TRD 요구사항 또는 TODO 항목으로 추적된다.
- 모든 건강 답변 경로가 `AnswerCard`, boundary renderer, unknown renderer 중 하나를
  사용한다.
- reviewed source 없는 질문이 LLM 일반 지식으로 답변되지 않는다.
- P0, 응급, 검사수치 치료 판단은 LLM을 호출하지 않는다.
- `/api/v1/ai-agent/chat`가 answerability와 reviewed source metadata를 보존한다.
- 문서, unit test, integration test가 같은 answerability/source/safety 용어를 사용한다.
