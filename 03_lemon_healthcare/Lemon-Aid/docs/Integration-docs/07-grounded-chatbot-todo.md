# 07. 근거 기반 동적 답변 프레임 챗봇 TODO

> Status: implementation checklist updated
> 작성일: 2026-05-29
> 기준 브랜치: `feat/ai-agent-backend-integration`
> PRD: [05-grounded-chatbot-prd.md](./05-grounded-chatbot-prd.md)
> TDD: [06-grounded-chatbot-tdd.md](./06-grounded-chatbot-tdd.md)

## 2026-05-29 구현 반영 상태

아래 TODO는 최초 구현 순서 초안이다. 2026-05-29 현재 `ai-agent-backend-integration`
worktree에서는 다음 항목이 1차 구현 및 테스트까지 완료됐다.

- `Answerability`, `AnswerCard`, `AnswerCardNormalizer`
- reviewed/not-stale source만 `AnswerCard`로 변환하는 registry/DB normalizer
- no reviewed source 질문의 `unknown_no_reviewed_source` fail-closed 경로
- unknown backlog DB 모델, migration, route-level 기록
- unknown backlog privacy-safe triage report
- production-like DB-backed evidence retriever와 local/dev registry fallback
- P0 상호작용 boundary 확장
- SGLang/OpenAI-compatible `response_format` 기반 structured output 요청과 JSON section rendering
- `BoundaryRenderer`, `UnknownRenderer`, `CardAnswerRenderer` 분리
- API `answerability`, `sources[]` additive response contract
- Supabase 개발 DB 생성, seed evidence, public table RLS 활성화
- Alembic/Supabase reviewed evidence seed 14개 topic으로 확장
- Alembic/Supabase reviewed P0 policy boundary seed 6개 추가
- DB-only retriever topic keyword matching 보강
- CLI manual QA preset, deterministic golden eval, live smoke script 보강
- 원격 Supabase backlog summary view privacy-safe probe 확인

최신 판정은 [09-grounded-chatbot-implementation-log.md](./09-grounded-chatbot-implementation-log.md)를
기준으로 본다. 2026-05-29 이후 Supabase `DATABASE_URL` 기반 DB evidence smoke, FastAPI
live smoke, SGLang live smoke, Flutter chatbot bridge smoke까지 완료됐다. 남은 큰 축은
실제 운영 coverage 확장이다. 즉, 더 많은 검수 evidence를 source governance로 승격하고
golden test를 붙여 답변 범위를 늘리는 일이다.

## 0. 작업 원칙

- 수동 질문 카드를 늘리는 작업은 제품 coverage 전략이 아니다.
- 수동 seed는 seed/golden 보강으로만 취급한다.
- 제품 coverage는 `retriever -> normalizer -> AnswerCard -> renderer` 흐름으로 늘린다.
- `AnswerCard`는 질문별 수동 FAQ 카드가 아니라, 검색된 검수 지식을 답변 직전에 정리한
  내부 답변 프레임이다.
- reviewed source가 없는 질문은 unknown으로 닫는다.
- 응급, 자해, 복약 변경, 검사수치 치료 판단, P0 병용은 LLM 호출 전 boundary로 닫는다.
- 코드 PR은 작은 단계로 나누고 각 단계마다 테스트를 먼저 추가한다.

## Phase 1. 계약과 failing tests

- [x] `Answerability` enum 또는 Literal을 추가하는 테스트를 작성한다.
- [x] `AnswerCard` 필수 필드 테스트를 작성한다.
- [x] no reviewed source 질문이 `unknown_no_reviewed_source`로 내려가는 golden test를
  작성한다.
- [x] reviewed `AnswerCard`가 있는 질문과 없는 질문의 차이를 명확히 드러내는 테스트를
  작성한다.
- [x] `/api/v1/ai-agent/chat` 응답에 `answerability`와 reviewed source metadata가 남는
  integration test를 작성한다.
- [x] P0/응급/검사수치 boundary가 LLM을 호출하지 않는 기존 테스트를 유지하고 새 contract
  필드까지 검증한다.

검증:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_chatbot_agent.py
python -m pytest -q --no-cov backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py
```

## Phase 2. AnswerCard seed adapter

- [x] `MedicalKnowledgeItem`을 바로 지우지 말고 `AnswerCard`로 변환하는 adapter를 만든다.
- [x] 모든 reviewed seed item이 `source_id`, `source_url`, `reviewed_status`,
  `allowed_guidance`, `specific_examples`, `checklist`, `must_not_say`를 갖는지 검증한다.
- [x] seed item에 `answerability`를 매핑한다.
- [x] `draft`와 `paper_candidate` seed는 adapter 출력에서 제외한다.
- [x] adapter 출력이 없는 질문은 unknown으로 떨어지는 테스트를 통과시킨다.

대상 파일 후보:

- `backend/ai_agent_chat/src/lemon_ai_agent/knowledge.py`
- `backend/ai_agent_chat/tests/test_medical_knowledge_registry.py`

## Phase 3. AnswerCardNormalizer

- [x] `AnswerCardNormalizer` 모듈을 추가한다.
- [x] reviewed evidence item 또는 seed item을 `AnswerCard`로 정규화한다.
- [x] 필수 필드 누락, stale source, draft source, low relevance 후보를 폐기한다.
- [x] `must_not_say`를 SafetyGuard 검증 context에 전달할 수 있게 한다.
- [x] normalizer 테스트를 추가한다.

대상 파일 후보:

- `backend/ai_agent_chat/src/lemon_ai_agent/answer_card.py`
- `backend/ai_agent_chat/tests/test_answer_card_normalizer.py`

## Phase 4. MedicalKnowledgeRetriever

- [x] 별도 `KnowledgeQuery` 대신 `ChatIntentAnalysis` 기반 retrieval contract를 확정한다.
- [x] `ChatIntentAnalysis`에서 retrieval에 필요한 topic, intent, condition, entity 후보를
  만든다.
- [x] registry-backed retriever를 먼저 구현한다.
- [x] production-like DB-backed retriever 인터페이스를 정의한다.
- [x] reviewed/not stale/user-facing source만 검색 대상으로 삼는다.
- [x] no match, stale only, not reviewed only 상태를 구분한다.
- [x] local/dev registry fallback과 production fail-closed 조건을 테스트한다.

대상 파일 후보:

- `backend/ai_agent_chat/src/lemon_ai_agent/retrieval.py`
- `backend/ai_agent_chat/src/lemon_ai_agent/chat_turn.py`
- `backend/Nutrition-backend/src/services/medical_source_readiness.py`
- `backend/ai_agent_chat/tests/test_medical_knowledge_retriever.py`

## Phase 5. ChatTurnModule 재배선

- [x] `ChatTurnPlan`에 `answerability`, `answer_cards`, `retrieval_status`를 추가한다.
- [x] `requires_boundary_response`가 urgent, medical decision, P0 boundary만 true가 되게
  한다.
- [x] retrieval 결과가 없으면 `unknown_no_reviewed_source`로 내려가게 한다.
- [x] magnesium+blood-pressure-med 같은 caution 질문은 reviewed `AnswerCard`가 있으면 LLM/fallback
  설명 가능 상태로 둔다.
- [x] `drug_or_interaction` 전체 차단이 아니라 P0/high-risk 조합만 boundary인지 테스트한다.

대상 파일 후보:

- `backend/ai_agent_chat/src/lemon_ai_agent/chat_turn.py`
- `backend/ai_agent_chat/src/lemon_ai_agent/knowledge.py`
- `backend/ai_agent_chat/tests/test_chat_turn.py`
- `backend/ai_agent_chat/tests/test_chatbot_agent.py`

## Phase 6. AnswerCard-only ChatbotAgent

- [x] LLM prompt에서 raw knowledge item dump를 제거하고 `AnswerCard` summary만 전달한다.
- [x] prompt에 "`AnswerCard` 밖 사실 생성 금지"와 "unknown이면 답하지 말라" 규칙을 추가한다.
- [x] fallback renderer가 카드의 examples/checklist/caution을 사용하게 한다.
- [x] unknown renderer를 추가한다.
- [x] medication/supplement caution renderer를 `AnswerCard` 기반으로 바꾼다.
- [x] sodium/diabetes/hypertension special case를 점진적으로 renderer/card 조합으로
  흡수한다.

대상 파일 후보:

- `backend/ai_agent_chat/src/lemon_ai_agent/agents/chatbot.py`
- `backend/ai_agent_chat/tests/test_chatbot_agent.py`

## Phase 7. SafetyGuard grounding 강화

- [x] `must_not_say` 유사 문구 차단 테스트를 추가한다.
- [x] `AnswerCard` 근거에 없는 새 수치 claim 차단 테스트를 추가한다.
- [x] "제품 라벨의 마그네슘 함량 확인" 같은 좋은 caution 문구는 허용한다.
- [x] "혈압약과 함께 먹어도 됩니다", "혈압약을 줄이세요", "라면은 절대 먹지 마세요"를
  차단한다.
- [x] draft/paper source 이름이 사용자 응답에 나오면 차단한다.

대상 파일 후보:

- `backend/ai_agent_chat/src/lemon_ai_agent/guards/safety.py`
- `backend/ai_agent_chat/tests/test_safety_guard.py`

## Phase 8. API response contract 확장

- [x] `ChatbotResponse`에 `answerability`를 추가한다.
- [x] `sources[]` detail 후보를 추가하거나 기존 `source_families`와 병행한다.
- [x] 기존 mobile 호환성을 깨지 않도록 additive field로 시작한다.
- [x] consent required, memory context, raw field 비노출 기존 테스트를 유지한다.
- [x] route-level unknown, caution, boundary, urgent golden tests를 추가한다.

대상 파일 후보:

- `backend/ai_agent_chat/src/lemon_ai_agent/chat_session.py`
- `backend/Nutrition-backend/src/api/v1/ai_agent.py`
- `backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py`

## Phase 9. DB-backed reviewed source 연결

- [x] `medical_source_readiness` DB-backed 조회 결과를 retriever가 사용할 수 있게 adapter를
  정의한다.
- [x] DB가 비어 있는 production-like 환경은 `no_reviewed_sources`로 fail-closed한다.
- [x] local/dev에서만 registry fallback을 허용한다.
- [x] stale source는 사용자-facing 내부 답변 프레임으로 만들지 않는다.
- [x] KDRIs `approved -> reviewed` adapter는 별도 테스트로 명시한다.

대상 파일 후보:

- `backend/Nutrition-backend/src/services/medical_source_readiness.py`
- `backend/Nutrition-backend/tests/unit/services/test_medical_source_readiness.py`
- `backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py`

## Phase 10. Golden set 확장

- [x] `혈압약 + 마그네슘`: 체크리스트 포함, 병용 가능/불가 단정 없음.
- [x] `나트륨 줄이는 저녁`: 국물/소스/장류/가공육/김치류 등 나트륨 조정 포인트를 우선 선택.
- [x] 채소/단백질 후보는 고정 출력이 아니라 질문, 질환, 최근 영양 기록에서 필요할 때만 선택.
- [x] `신장질환 + 채소/과일`: 칼륨 주의 포함.
- [x] `당뇨 과식 후 다음 끼니`: 탄수화물/당류 조정과 단백질/채소 후보 포함.
- [x] `가슴통증 + 숨참`: LLM 미호출, 심장/폐 위험 이유, 119/응급실 안내.
- [x] `검수 지식 없는 질문`: unknown_no_reviewed_source, LLM 일반 지식 없음.
- [x] `와파린 + 비타민 K`: P0 boundary 유지.
- [x] `갑상선약 + 칼슘/철분`: P0 boundary 유지.
- [x] `LDL 수치 치료 판단`: medical decision boundary 유지.

## Phase 11. 검증 게이트

각 구현 PR의 최소 검증:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests
python -m pytest -q --no-cov backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py
python -m compileall backend/ai_agent_chat/src backend/Nutrition-backend/src/api/v1/ai_agent.py
python -m ruff check backend/ai_agent_chat/src backend/ai_agent_chat/tests backend/Nutrition-backend/src/api/v1/ai_agent.py backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py
```

문서만 바꾼 PR의 최소 검증:

```powershell
Get-Content -Raw -Encoding UTF8 docs\Integration-docs\05-grounded-chatbot-prd.md
Get-Content -Raw -Encoding UTF8 docs\Integration-docs\06-grounded-chatbot-tdd.md
Get-Content -Raw -Encoding UTF8 docs\Integration-docs\07-grounded-chatbot-todo.md
git diff --check -- docs\Integration-docs\05-grounded-chatbot-prd.md docs\Integration-docs\06-grounded-chatbot-tdd.md docs\Integration-docs\07-grounded-chatbot-todo.md docs\Integration-docs\README.md docs\README.md
```

## Phase 12. 완료 정의

- [x] 모든 건강 답변은 `AnswerCard`, boundary renderer, unknown renderer 중 하나에서 나온다.
- [x] reviewed source 없는 질문은 unknown으로 닫힌다.
- [x] manual seed는 seed/golden fixture와 local/dev fallback으로만 남는다.
- [x] LLM prompt는 `AnswerCard` 밖 지식 생성을 허용하지 않는다.
- [x] fallback도 `AnswerCard` 기반으로 구체 답변을 만든다.
- [x] API route가 answerability와 reviewed source metadata를 유지한다.
- [x] golden tests, SafetyGuard tests, route integration tests가 모두 통과한다.
- [x] RAG/vector DB 연결은 별도 PR로 남아 있어도, 연결 전 설계상 safety boundary와
  fail-closed behavior가 깨지지 않는다.
- [x] Supabase `DATABASE_URL`로 FastAPI live smoke를 실행해 DB-backed reviewed source와
  unknown backlog persistence를 end-to-end로 확인한다.
  - 증거: `09-grounded-chatbot-implementation-log.md`의 "Supabase live DATABASE_URL smoke
    completion", "릴리스 TODO 실행", "Flutter chatbot bridge 연결" 절.
