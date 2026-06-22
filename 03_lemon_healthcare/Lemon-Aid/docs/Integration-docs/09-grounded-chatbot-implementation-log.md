# 09. 근거 기반 동적 답변 프레임 챗봇 구현 로그

> Status: implementation log
> 작성일: 2026-05-29
> 기준 브랜치: `feat/ai-agent-backend-integration`
> PRD: [05-grounded-chatbot-prd.md](./05-grounded-chatbot-prd.md)
> TDD: [06-grounded-chatbot-tdd.md](./06-grounded-chatbot-tdd.md)
> TODO: [07-grounded-chatbot-todo.md](./07-grounded-chatbot-todo.md)
> TRD: [08-grounded-chatbot-trd.md](./08-grounded-chatbot-trd.md)

## 1. 구현 목적

이번 작업은 질문별 수동 FAQ 카드 몇 개에 의존하는 챗봇에서 벗어나, 모든 건강 답변이 검수 지식
기반 내부 답변 프레임인 `AnswerCard` 또는 boundary/unknown renderer를 통과하도록 첫 runtime 구현을
연결하는 작업이다.

핵심 구현 목표:

- `AnswerCard` 표준 타입 추가
- reviewed seed knowledge를 `AnswerCard` 내부 답변 프레임으로 정규화
- 질문별 reviewed `AnswerCard` retrieval
- reviewed `AnswerCard`가 없으면 `unknown_no_reviewed_source`로 fail-closed
- LLM prompt와 deterministic fallback이 `AnswerCard` 기반 grounding을 사용
- API response에 `answerability`와 reviewed source metadata 추가
- production chat route에서 reviewed source governance DB 미준비 시 fail-closed
- 작업 내용을 테스트와 문서로 남김

## 2. 주요 변경

### 2.1 AnswerCard 계층 추가

`AnswerCard`는 질문별로 미리 작성하는 수동 FAQ 카드가 아니라, 검색된 검수 지식을
답변 직전에 `allowed_guidance`, `specific_examples`, `checklist`,
`caution_conditions`, `must_not_say`, source metadata로 정리한 내부 답변 프레임이다.
장기 목표는 seed를 계속 늘리는 것이 아니라 DB-backed reviewed evidence를 이 shape로
동적 정규화하는 것이다.

추가 파일:

- `backend/ai_agent_chat/src/lemon_ai_agent/answer_card.py`
- `backend/ai_agent_chat/tests/test_answer_card_normalizer.py`

구현 내용:

- `Answerability` 타입 추가
  - `answerable`
  - `answerable_with_caution`
  - `needs_more_info`
  - `unknown_no_reviewed_source`
  - `medical_decision_boundary`
  - `urgent_escalation`
- `AnswerCard` dataclass 추가
- `KnowledgeRetrievalResult` dataclass 추가
- `AnswerCardNormalizer` 추가
- `MedicalKnowledgeRetriever` 추가
- draft, paper candidate, user-facing 불가 source를 카드로 만들지 않도록 차단
- 약/영양제 병용 caution 질문에서 무관한 범용 카드를 끌어오지 않도록 relevance filter 추가

### 2.2 ChatTurnModule 재배선

변경 파일:

- `backend/ai_agent_chat/src/lemon_ai_agent/chat_turn.py`
- `backend/ai_agent_chat/tests/test_chat_turn.py`

구현 내용:

- `ChatTurnPlan`에 아래 필드 추가
  - `answer_cards`
  - `answerability`
  - `retrieval_status`
  - `retrieval_warnings`
  - `sources`
- `requires_boundary_response`를 기존 category 기반에서 answerability 기반으로 변경
- unsupported 질문은 `unknown_no_reviewed_source`로 내려가도록 테스트 추가

### 2.3 reviewed seed 보강

변경 파일:

- `backend/ai_agent_chat/src/lemon_ai_agent/knowledge.py`

구현 내용:

- `ChatIntentAnalysis.normalized_question` 추가
- 일반 건강기록 점검용 reviewed seed item 추가
  - `general_health_record_review`
- 일반 영양제 라벨 점검용 reviewed seed item 추가
  - `supplement_label_check`
- 기존 마그네슘/나트륨/당뇨/고혈압/신장질환 seed item은 `AnswerCard`로 변환되는
  grounding source로 사용

주의:

- 이번 작업의 seed 추가는 coverage mechanism 확장이 아니라, `AnswerCard` adapter와
  fallback 경로를 검증하기 위한 v1 reviewed seed다.
- 새 topic coverage는 앞으로 source/evidence update와 retriever/normalizer 테스트를 통해
  확장해야 한다.

### 2.4 ChatbotAgent AnswerCard-only/unknown 흐름

변경 파일:

- `backend/ai_agent_chat/src/lemon_ai_agent/agents/chatbot.py`
- `backend/ai_agent_chat/tests/test_chatbot_agent.py`

구현 내용:

- `unknown_no_reviewed_source`이면 LLM을 호출하지 않고 deterministic unknown 응답 반환
- LLM prompt의 reviewed grounding을 `AnswerCard` summary로 전환
- LLM system rule에 "provided reviewed AnswerCards만 factual grounding으로 사용" 규칙 추가
- LLM 출력 후 `must_not_say` phrase 검사 추가
- 성공/실패/fallback 응답에 `answerability`와 `sources` metadata 포함
- 마그네슘+혈압약 질문은 `answerable_with_caution`으로 유지
- 리튬+셀레늄처럼 reviewed `AnswerCard`가 없는 병용 질문은 unknown으로 fail-closed

### 2.5 SafetyGuard 보강

변경 파일:

- `backend/ai_agent_chat/src/lemon_ai_agent/guards/safety.py`
- `backend/ai_agent_chat/tests/test_safety_guard.py`

구현 내용:

- `check_forbidden_phrases()` 추가
- AnswerCard의 `must_not_say` 표현이 LLM 출력에 나오면 fallback할 수 있게 연결
- 기존 금지 표현, unsupported fact, unsupported numeric claim 검증 유지

### 2.6 API 응답 계약 확장

변경 파일:

- `backend/ai_agent_chat/src/lemon_ai_agent/chat_session.py`
- `backend/Nutrition-backend/src/api/v1/ai_agent.py`
- `backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py`

구현 내용:

- `ChatbotResponse`에 `answerability`, `sources` 추가
- `ChatbotApiResponse`에 `answerability`, `sources` 추가
- `/api/v1/ai-agent/chat` route가 additive response field를 내려주도록 변경
- magnesium caution route test가 `answerability=answerable_with_caution`과 source metadata를 검증
- unknown route test가 LLM 미호출, `unknown_no_reviewed_source`, `sources=[]`를 검증

### 2.7 production source governance fail-closed

변경 파일:

- `backend/Nutrition-backend/src/api/v1/ai_agent.py`
- `backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py`

구현 내용:

- `_production_medical_source_gate()` 추가
- `settings.environment == "production"`이면 `build_medical_source_readiness_from_db()`를
  통해 DB-backed reviewed source readiness를 확인
- production에서 reviewed source governance가 준비되지 않으면 LLM client를 만들지 않고
  `unknown_no_reviewed_source` 응답 반환
- local/dev에서는 기존 registry-backed chatbot path 유지

## 3. 추가한 테스트

새 테스트 파일:

- `backend/ai_agent_chat/tests/test_answer_card_normalizer.py`

보강한 테스트:

- `backend/ai_agent_chat/tests/test_chat_turn.py`
- `backend/ai_agent_chat/tests/test_chatbot_agent.py`
- `backend/ai_agent_chat/tests/test_safety_guard.py`
- `backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py`

주요 검증:

- reviewed seed item -> `AnswerCard`
- draft/paper candidate item -> card 생성 거부
- 무관한 병용 질문 -> `no_match`
- 마그네슘+혈압약 -> reviewed caution card
- unsupported 질문 -> LLM 미호출 unknown 응답
- API response -> `answerability`, `sources`
- production source readiness 실패 -> LLM 미호출 fail-closed
- `must_not_say` phrase 차단

## 4. 실행한 검증

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests
```

결과:

```text
79 passed, 1 skipped
```

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py
```

결과:

```text
15 passed, 1 warning
```

```powershell
python -m compileall backend/ai_agent_chat/src backend/Nutrition-backend/src/api/v1/ai_agent.py
```

결과:

```text
success
```

```powershell
python -m ruff check backend/ai_agent_chat/src backend/ai_agent_chat/tests backend/Nutrition-backend/src/api/v1/ai_agent.py backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py
```

결과:

```text
All checks passed!
```

## 5. 완료된 TODO 범위

이번 작업에서 완료한 범위:

- Phase 1: answerability, AnswerCard, unknown, API contract 테스트 추가
- Phase 2: `MedicalKnowledgeItem` -> `AnswerCard` seed adapter 구현
- Phase 3: AnswerCard normalizer 구현
- Phase 4: registry-backed retriever 구현
- Phase 5: ChatTurnModule answerability/card 기반 재배선
- Phase 6: ChatbotAgent unknown/card grounding 흐름 연결
- Phase 7: SafetyGuard `must_not_say` 검사 추가
- Phase 8: API response contract에 `answerability`, `sources` 추가
- Phase 9 일부: production chat route의 DB-backed source readiness fail-closed gate 연결
- Phase 10 일부: magnesium, unknown, emergency, P0, lab boundary, sodium golden behavior 유지/확장
- Phase 11: 지정된 테스트, compileall, ruff 검증 통과

## 6. 남은 후속 범위

이번 작업에서 일부러 남긴 범위:

- 실제 `medical_evidence_items` DB row를 읽어 `AnswerCard`로 변환하는 DB retriever
- `medical_rag_chunks` 또는 vector index 연결
- source owner/reviewer workflow UI 또는 admin seed
- KDRIs `approved -> reviewed` adapter 세부 연결
- Flutter UI에서 `sources[]` detail sheet 표시
- `needs_more_info` 상태의 별도 renderer 세분화

남긴 이유:

- PRD와 TDD가 정한 v1 순서는 먼저 reviewed seed/registry 기반 `AnswerCard` 계약과
  fail-closed behavior를 고정한 뒤, DB evidence/RAG를 별도 PR로 붙이는 것이다.
- RAG/vector DB는 답변 품질 보강 계층이며 safety boundary를 대체하지 않는다.

## 7. 완료 판정

이번 구현으로 현재 runtime은 다음 조건을 만족한다.

- 건강 답변 경로가 `AnswerCard`, boundary renderer, unknown renderer 중 하나를 사용한다.
- reviewed `AnswerCard`가 없는 unsupported 병용 질문은 LLM으로 넘어가지 않는다.
- P0, 응급, 검사수치 치료 판단은 LLM을 호출하지 않는다.
- `/api/v1/ai-agent/chat`가 `answerability`와 reviewed source metadata를 내려준다.
- production 환경에서는 reviewed source governance DB readiness 실패 시 fail-closed한다.
- 테스트와 문서가 같은 answerability/source/safety 용어를 사용한다.

## 8. 2026-05-29 후속 보완: source traceability와 stale 차단

LLM-WIKI `AGENTS.md` 기준 재점검 후, 사용자-facing `AnswerCard`가 실제 source publisher/domain과
맞지 않는 문제를 먼저 보완했다.

반영:

- `nih-ods-magnesium`, `niddk-kidney-disease`, `niddk-diabetes-living`,
  `cdc-public-health` reviewed source registry entry 추가
- CDC/NIDDK/NIH ODS seed item의 `source_id`를 실제 source URL 계열과 일치하도록 수정
- `AnswerCardNormalizer`가 `review_expires_at`이 지난 source를 `AnswerCard`로 만들지 않도록 차단
- matched `AnswerCard`가 모두 stale이면 `retrieval_status="stale_only"`와 `source_stale` warning 반환
- user-facing `AnswerCard`의 source id, expiry metadata, source URL domain 정합성 테스트 추가

검증:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_answer_card_normalizer.py backend/ai_agent_chat/tests/test_medical_knowledge_registry.py backend/ai_agent_chat/tests/test_chatbot_agent.py::test_chatbot_magnesium_blood_pressure_med_question_gives_caution_checklist backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py::test_chat_route_magnesium_blood_pressure_med_uses_caution_policy
```

결과:

```text
16 passed, 1 warning
```

## 9. 2026-05-29 후속 보완: unknown backlog와 DB evidence 구조 필드

최종 계획의 PR 1/PR 2 범위 중 runtime에 바로 필요한 계약을 추가했다.

반영:

- `chatbot_unknown_knowledge_events` ORM 모델과 Alembic revision
  `0010_add_chatbot_unknown_backlog` 추가
- unknown 이벤트는 `answerability`, `primary_intent`, `category`, `related_conditions`,
  `missing_topics`, `retrieval_status`, `retrieval_warnings`, `needed_evidence_type`, `status`만
  저장한다.
- raw question, raw prompt, raw OCR, raw LLM response 컬럼은 추가하지 않았다.
- `/api/v1/ai-agent/chat`에서 `unknown_no_reviewed_source` 응답이 나오면 원문 없이
  분류 메타데이터 기반 backlog 이벤트를 stage한다.
- `medical_evidence_items`에 DB evidence를 `AnswerCard`로 정규화하기 위한
  `specific_examples`, `checklist`, `caution_conditions`, `must_not_say` JSONB 필드를 추가했다.
- `AnswerCardNormalizer.from_evidence_record()`로 reviewed/not stale DB evidence record를
  runtime `AnswerCard`로 바꾸는 최소 adapter를 추가했다.
- P0 상호작용 boundary 후보에 세인트존스워트, 자몽, 칼륨/저염소금, nitrate+PDE5,
  SSRI/SNRI+세로토닌성 보충제, statin+홍국 조합을 추가했다.

검증:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog.py
python -m pytest -q --no-cov backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py::test_chat_route_unknown_question_fails_closed_without_llm
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_answer_card_normalizer.py::test_answer_card_normalizer_converts_reviewed_db_evidence_record backend/ai_agent_chat/tests/test_answer_card_normalizer.py::test_answer_card_normalizer_rejects_unreviewed_or_stale_db_evidence_record
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_medical_knowledge_registry.py::test_p0_interaction_and_context_questions_route_to_boundary_policy backend/ai_agent_chat/tests/test_chatbot_agent.py::test_chatbot_p0_interaction_examples_return_boundary_without_llm
```

결과:

```text
모두 통과
```

## 10. 2026-05-29 Supabase dev DB and DB-backed retriever wiring

Supabase 프로젝트 `lemon-aid-chatbot-dev`를 생성하고 챗봇 knowledge bootstrap용 최소
schema와 seed evidence를 적용했다.

프로젝트:

- project ref: `ajgvoxttzsjcwtphtsuz`
- region: `ap-northeast-2`
- status: `ACTIVE_HEALTHY`
- cost check: Free org 기준 `월 0`

Supabase migration:

- `create_chatbot_medical_knowledge_subset`
  - `medical_sources`
  - `medical_source_versions`
  - `medical_evidence_items`
  - `chatbot_unknown_knowledge_events`
  - `magnesium_supplement_caution` seed evidence
  - `sodium_dinner_adjustment` seed evidence
- `secure_chatbot_medical_knowledge_subset`
  - public schema 테이블 RLS 활성화
  - `medical_evidence_items.source_version_id` FK 인덱스 추가

원격 DB 검증:

- `magnesium_supplement_caution`: source `nih-ods-magnesium`, reviewed, expires `2026-11-29`
- `sodium_dinner_adjustment`: source `kdris-2025`, reviewed, expires `2027-05-19`
- Supabase security advisor의 RLS disabled error는 해소했다.
- RLS policy가 없다는 INFO는 의도된 상태다. 현재 Flutter 직접 DB 접근은 열지 않고 FastAPI 서버
  경로만 사용한다.

코드 반영:

- `EvidenceRecordMedicalKnowledgeRetriever`를 추가했다.
  - DB evidence record를 `AnswerCard`로 정규화한다.
  - production-like 경로에서는 DB evidence가 없으면 unknown으로 fail-closed한다.
  - local/dev에서는 기존 registry fallback을 유지한다.
- `build_chatbot_medical_knowledge_retriever()`를 추가해 FastAPI route에서 DB evidence retriever를
  `ChatbotAgent`에 주입하도록 연결했다.
- `ChatbotAgent`는 외부 retriever를 주입받을 수 있게 바뀌었다.

검증:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests
python -m pytest -q --no-cov backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog.py backend/Nutrition-backend/tests/unit/services/test_chatbot_evidence_retriever.py backend/Nutrition-backend/tests/unit/services/test_medical_source_readiness.py backend/Nutrition-backend/tests/unit/db/test_models.py backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py
python -m ruff check backend/ai_agent_chat/src backend/ai_agent_chat/tests/test_answer_card_normalizer.py backend/Nutrition-backend/src/api/v1/ai_agent.py backend/Nutrition-backend/src/services/chatbot_unknown_backlog.py backend/Nutrition-backend/src/services/chatbot_evidence_retriever.py backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog.py backend/Nutrition-backend/tests/unit/services/test_chatbot_evidence_retriever.py backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py
```

결과:

```text
backend/ai_agent_chat/tests: 86 passed, 1 skipped
backend chatbot/API/source/db focused tests: 69 passed
ruff: All checks passed
```

남은 점:

- 전체 FastAPI를 Supabase 하나로 smoke하려면 Supabase Dashboard에서 DB connection string을 받아
  Alembic `upgrade head`를 추가로 실행해야 한다.
- structured output JSON renderer와 renderer class 분리는 아직 후속 작업이다.

## 11. 2026-05-29 structured output response_format 연결

SGLang/OpenAI-compatible 경로에서 JSON schema 기반 structured output을 우선 요청하도록
`ChatbotAgent`를 보강했다.

반영:

- `STRUCTURED_RESPONSE_FORMAT`을 추가했다.
- LLM request에 `response_format={"type": "json_schema", ...}`를 전달한다.
- LLM이 JSON object를 반환하면 아래 최소 구조를 검증한 뒤 기존 사용자-facing section으로
  렌더링한다.
  - `summary`
  - `why_it_matters`
  - `today_actions`
  - `specific_examples`
  - `caution_conditions`
  - `expert_check_points`
  - `source_basis`
- JSON이 아니거나 schema가 맞지 않으면 기존 text contract 검증 경로를 유지한다.
- 렌더링된 text도 기존 SafetyEnvelope, forbidden phrase, required section, card specificity 검사를
  그대로 통과해야 한다.

검증:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_chatbot_agent.py backend/ai_agent_chat/tests/test_sglang_client.py
python -m ruff check backend/ai_agent_chat/src/lemon_ai_agent/agents/chatbot.py backend/ai_agent_chat/tests/test_chatbot_agent.py
python -m compileall backend/ai_agent_chat/src/lemon_ai_agent/agents/chatbot.py
```

결과:

```text
25 passed
ruff: All checks passed
compileall: passed
```

남은 점:

- JSON parse failure를 별도 warning code로 노출하는 세부 정책은 아직 추가하지 않았다.
- `CardAnswerRenderer`, `UnknownRenderer`, `BoundaryRenderer` class 분리는 아직 남아 있다.

## 12. 2026-05-29 renderer class 분리

`ChatbotAgent` 내부에 섞여 있던 deterministic 응답 생성을 별도 renderer 모듈로 분리했다.

반영:

- `lemon_ai_agent.renderers.BoundaryRenderer`
  - 응급, 정신건강 위험, P0 병용/상호작용, 검사수치/처방 변경 boundary 응답을 담당한다.
  - LLM을 호출하지 않는 deterministic 경로다.
- `lemon_ai_agent.renderers.UnknownRenderer`
  - `unknown_no_reviewed_source` 응답을 담당한다.
  - 사용자 질문 원문이나 raw context를 포함하지 않는다.
- `lemon_ai_agent.renderers.CardAnswerRenderer`
  - reviewed card 기반 deterministic fallback 응답을 담당한다.
  - 현재는 medication/supplement caution과 sodium meal adjustment fallback을 담당한다.
- `ChatbotAgent`
  - intent/retrieval/LLM/safety orchestration 중심으로 남기고, boundary/unknown/card fallback
    메시지 조립을 renderer에 위임한다.

검증:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_chatbot_renderers.py backend/ai_agent_chat/tests/test_chatbot_agent.py
python -m ruff check backend/ai_agent_chat/src/lemon_ai_agent/agents/chatbot.py backend/ai_agent_chat/src/lemon_ai_agent/renderers.py backend/ai_agent_chat/tests/test_chatbot_renderers.py backend/ai_agent_chat/tests/test_chatbot_agent.py
python -m compileall backend/ai_agent_chat/src/lemon_ai_agent/agents/chatbot.py backend/ai_agent_chat/src/lemon_ai_agent/renderers.py
```

결과:

```text
27 passed
ruff: All checks passed
compileall: passed
```

남은 점:

- generic fallback까지 모두 `CardAnswerRenderer`로 옮기는 내부 정리는 후속으로 가능하다.
- 현재 사용자-facing 핵심 경로인 boundary, unknown, medication caution, sodium meal fallback은
  renderer class를 통과한다.

## 13. 2026-05-29 Supabase full smoke readiness check

Supabase 원격 DB 상태와 로컬 도구 상태를 점검했다.

확인:

- 원격 `lemon-aid-chatbot-dev`에는 현재 public table 29개가 있다.
- `alembic_version.version_num`은 `0010_add_chatbot_unknown_backlog`다.
- seed 지식은 2개다.
  - `magnesium_supplement_caution`: reviewed, `specific_examples` 7개, `checklist` 6개
  - `sodium_dinner_adjustment`: reviewed, `specific_examples` 17개, `checklist` 6개
- Alembic offline SQL 생성은 가능하다.
  - `python -m alembic -c backend/alembic.ini upgrade head --sql`
  - 생성 SQL은 `alembic_version`, 전체 FastAPI 테이블, vector extension, 0010 migration까지 포함한다.
- MCP migration으로 bootstrap subset 이후 누락된 FastAPI 테이블을 추가했다.
  - `create_fastapi_core_tables`
  - `create_fastapi_agent_and_regulated_tables`
  - `enable_rls_on_fastapi_public_tables`
  - `add_covering_indexes_for_fk_advisors`
- 로컬 CLI 상태:
  - `supabase` CLI 없음
  - `psql` CLI 없음

판단:

- Supabase security advisor의 `rls_disabled_in_public` ERROR는 해소했다.
- Supabase performance advisor의 `unindexed_foreign_keys` INFO는 FK covering index 추가로 해소했다.
- `rls_enabled_no_policy` INFO는 현재 Flutter가 DB에 직접 접근하지 않는 구조에서는 의도된 잠금
  상태다. FastAPI 서버 전용 DB 연결만 사용한다.
- `extension_in_public` WARN은 남아 있다. 현재 Alembic의 pgvector extension 생성 방식과 타입
  search path 영향이 있어 별도 migration으로 다룬다.
- `unused_index` INFO는 새 dev DB라 쿼리 통계가 없어 발생한다.

남은 점:

- Dashboard DB connection string/password가 있으면
  `backend/scripts/smoke_ai_agent_server.py --database-url ... --skip-db-upgrade --skip-sglang-check`로
  전체 FastAPI smoke를 진행한다.
- 실제 SGLang runtime까지 포함한 smoke는 SGLang 서버가 떠 있는 상태에서 `--skip-sglang-check`를
  제거하고 실행한다.

## 14. 2026-05-29 DB-backed AnswerCard source basis and smoke output polish

DB-backed retriever를 사용할 때 deterministic fallback의 `출처 기준`이 registry용
`knowledge_items` 기본값으로 떨어질 수 있는 문제를 보강했다.

반영:

- `ChatbotAgent` fallback source basis가 `AnswerCard` source metadata를 우선 사용한다.
  - DB evidence의 `nih-ods-magnesium` card는 `NIH ODS Magnesium Fact Sheet`로 표시된다.
  - KDRIs/KDCA card가 함께 있으면 기존 사용자-facing 순서인
    `질병관리청 건강정보, KDRIs 영양 기준`을 유지한다.
- generic deterministic fallback도 `CardAnswerRenderer.render_general()`을 통과하게 정리했다.
- LLM prompt의 answer strategy가 DB-backed `answer_cards` 존재를 기준으로
  "reviewed answer cards를 사용하라"는 방향을 명시한다.
- `ask_chatbot_agent.py`가 `answerability`, `source_families`, `sources[]`를 출력한다.
- `smoke_ai_agent_server.py`가 chatbot 응답의 `answerability`와 `sources` 존재를 검증하고
  summary JSON에 포함한다.
- 여러 식사 기록이 있는 나트륨 답변의 요약 bullet이 줄바꿈으로 깨지지 않게 한 줄로 정리했다.

검증:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_chatbot_agent.py backend/ai_agent_chat/tests/test_chatbot_renderers.py backend/ai_agent_chat/tests/test_answer_card_normalizer.py
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/scripts/test_smoke_ai_agent_server.py backend/ai_agent_chat/tests/test_chatbot_agent.py
python -m ruff check backend/scripts/ask_chatbot_agent.py backend/scripts/smoke_ai_agent_server.py backend/Nutrition-backend/tests/unit/scripts/test_smoke_ai_agent_server.py backend/ai_agent_chat/src/lemon_ai_agent/agents/chatbot.py backend/ai_agent_chat/src/lemon_ai_agent/renderers.py
python backend\scripts\ask_chatbot_agent.py --preset supplement-drug-boundary
python backend\scripts\ask_chatbot_agent.py --preset hypertension-kimchi-stew
python backend\scripts\ask_chatbot_agent.py "리튬 약을 먹는데 셀레늄 영양제 같이 먹어도 돼?"
python backend\scripts\ask_chatbot_agent.py --preset exercise-dizziness-red-flags
```

결과:

```text
chatbot/renderers/normalizer focused tests: 38 passed
smoke script + chatbot tests: 28 passed
ruff: All checks passed
CLI smoke: magnesium caution, sodium dinner adjustment, unknown, emergency boundary all returned expected answerability and source metadata
```

남은 점:

- Supabase live FastAPI smoke는 Dashboard DB connection string/password가 있어야 실행할 수 있다.
- 운영 coverage는 seed 2개 수준이므로, 실제 사용자 질문 backlog를 보고 reviewed evidence와 golden
  test를 계속 추가해야 한다.

## 15. 2026-05-29 Supabase reviewed evidence coverage seed

Supabase 원격 DB와 Alembic migration에 registry bootstrap 수준의 reviewed evidence seed를 추가했다.
이제 production-like DB-backed retriever가 마그네슘/나트륨 2개 topic에만 의존하지 않고,
초기 golden set에 필요한 주요 topic을 DB evidence에서 바로 찾을 수 있다.

반영:

- Alembic `0011_seed_chatbot_reviewed_evidence` 추가
  - reviewed source 7개
  - current reviewed source version 7개
  - reviewed evidence item 14개
- Supabase MCP migration `seed_chatbot_reviewed_evidence_coverage` 적용
- Supabase `alembic_version.version_num`을 `0011_seed_chatbot_reviewed_evidence`로 갱신
- DB-only retriever topic matching 보강
  - `adult_activity`
  - `exercise_dizziness`
  - `protein_food_candidates`
  - `vitamin_d_food_candidates`
  - `fiber_food_candidates`
  - `supplement_label_check`
  - chronic condition and sodium topic keywords

원격 Supabase 확인:

```text
medical_sources: 7
current reviewed medical_source_versions: 7
medical_evidence_items: 14 reviewed topics
alembic_version: 0011_seed_chatbot_reviewed_evidence
security advisor: rls_disabled_in_public ERROR 없음
```

검증:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py backend/ai_agent_chat/tests/test_chatbot_agent.py backend/Nutrition-backend/tests/unit/services/test_chatbot_evidence_retriever.py
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_answer_card_normalizer.py backend/ai_agent_chat/tests/test_chatbot_agent.py
python -m ruff check backend/alembic/versions/0011_seed_chatbot_reviewed_evidence.py backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py backend/ai_agent_chat/src/lemon_ai_agent/answer_card.py backend/ai_agent_chat/tests/test_answer_card_normalizer.py
```

결과:

```text
alembic/chatbot/evidence retriever focused tests: 41 passed
answer card + chatbot focused tests: 36 passed
ruff: All checks passed
```

남은 점:

- 아직 Supabase Dashboard DB connection string/password가 없어 live FastAPI smoke는 미실행이다.
- seed coverage는 초기 golden set 수준이다. 실제 사용자 unknown backlog를 보고 reviewed evidence와
  golden test를 계속 추가해야 한다.

## 16. 2026-05-29 Supabase reviewed policy boundary seed

P0 병용/상호작용 boundary가 코드 키워드에만 남지 않도록 `medical_policy_boundaries`에도
초기 reviewed boundary seed를 추가했다. 런타임 답변은 여전히 LLM 호출 전에 deterministic
boundary renderer가 처리하지만, 운영 DB에서 어떤 조합을 검수된 boundary 후보로 관리하는지
추적할 수 있게 했다.

반영:

- Alembic `0012_seed_chatbot_policy_boundaries` 추가
- Supabase MCP migration `seed_chatbot_policy_boundaries` 적용
- Supabase `alembic_version.version_num`을 `0012_seed_chatbot_policy_boundaries`로 갱신
- reviewed policy boundary 6개 seed:
  - `p0_st_johns_wort_antidepressant`
  - `p0_grapefruit_statin`
  - `p0_potassium_salt_substitute`
  - `p0_nitrate_pde5_inhibitor`
  - `p0_serotonergic_supplement_antidepressant`
  - `p0_statin_red_yeast_rice`
- SSRI/SNRI + 세로토닌성 보충제 boundary 키워드에 `트립토판`, `tryptophan`,
  `l-tryptophan`, `세로토닌`, `serotonin`을 추가했다.

원격 Supabase 확인:

```text
medical_policy_boundaries: 6 reviewed boundaries
alembic_version: 0012_seed_chatbot_policy_boundaries
```

검증:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_medical_knowledge_registry.py::test_p0_interaction_and_context_questions_route_to_boundary_policy backend/ai_agent_chat/tests/test_chatbot_agent.py::test_chatbot_p0_interaction_examples_return_boundary_without_llm
python -m ruff check backend/alembic/versions/0012_seed_chatbot_policy_boundaries.py backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py
```

결과:

```text
alembic setup tests: 15 passed
P0 policy/chatbot focused tests: 2 passed
ruff: All checks passed
```

남은 점:

- `medical_policy_boundaries`는 현재 운영/governance seed이며, 런타임 boundary 판정은 아직
  `knowledge.py` deterministic classifier가 담당한다.
- DB connection string/password가 없어 live FastAPI smoke는 아직 미실행이다.

## 17. 2026-05-29 Flutter chat source detail contract

백엔드 `/api/v1/ai-agent/chat` 응답에 추가한 `answerability`, `sources[]`가 모바일에서
버려지지 않도록 Flutter chat DTO와 화면을 보강했다. 이제 사용자는 source family chip뿐 아니라
실제 reviewed source id/version/expiry도 화면에서 확인할 수 있다.

반영:

- `ChatbotResponse`에 `answerability`, `sources`, `hasReviewedSources` 추가
- `ChatbotSource` DTO 추가
  - `source_id`
  - `source_family`
  - `review_status`
  - `version_label`
  - `reviewed_at`
  - `expires_at`
  - `source_url`
- `ChatScreen`에 answerability chip과 `검수 근거` panel 추가
- static Flutter contract test에 source detail contract를 추가

검증:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/mobile/test_flutter_ai_agent_contract.py::test_flutter_chat_mvp_uses_safe_contract_and_navigation
flutter analyze
python -m pytest -q --no-cov backend/ai_agent_chat/tests backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog.py backend/Nutrition-backend/tests/unit/services/test_chatbot_evidence_retriever.py backend/Nutrition-backend/tests/unit/services/test_medical_source_readiness.py backend/Nutrition-backend/tests/unit/db/test_models.py backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py backend/Nutrition-backend/tests/unit/scripts/test_smoke_ai_agent_server.py backend/Nutrition-backend/tests/unit/scripts/test_smoke_chatbot_db_evidence.py backend/Nutrition-backend/tests/unit/mobile/test_flutter_ai_agent_contract.py
```

결과:

```text
Flutter chat contract focused test: 1 passed
flutter analyze: No issues found
related tests with mobile contract: 187 passed, 1 skipped
ruff: All checks passed
```

## 18. 2026-05-29 P0 boundary Korean expression coverage

CLI smoke 중 P0로 닫혀야 하는 질문이 특정 성분명 대신 생활 표현을 쓰면 unknown으로
떨어지는 케이스를 확인했다.

보강:

- `statin`/`스타틴` 대신 `고지혈증 약`, `고지혈증약`, `콜레스테롤 약`, `콜레스테롤약`을
  쓰는 자몽/홍국 질문도 P0 boundary로 분류한다.
- `PDE5` 대신 `비아그라`, `시알리스`, `실데나필`, `타다라필`, `발기부전 치료제`를 쓰는
  nitrate/협심증 질문도 P0 boundary로 분류한다.
- registry policy test와 chatbot no-LLM boundary test에 한국어 생활 표현 사례를 추가했다.

검증:

```powershell
python backend/scripts/ask_chatbot_agent.py "고지혈증 약 먹는데 자몽주스 마셔도 돼?"
python backend/scripts/ask_chatbot_agent.py "협심증약 먹는데 비아그라 같이 먹어도 돼?"
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_medical_knowledge_registry.py::test_p0_interaction_and_context_questions_route_to_boundary_policy backend/ai_agent_chat/tests/test_chatbot_agent.py::test_chatbot_p0_interaction_examples_return_boundary_without_llm
```

결과:

```text
고지혈증 약 + 자몽주스: answerability=medical_decision_boundary, Drug interaction boundary applied
협심증약 + 비아그라: answerability=medical_decision_boundary, Drug interaction boundary applied
focused P0 tests: 2 passed
```

## 19. 2026-05-29 unknown backlog triage report

`unknown_no_reviewed_source`를 DB에 기록하는 것에서 한 단계 더 나아가, 운영자가 반복 질문
주제를 검수 evidence 후보로 볼 수 있는 privacy-safe 리포트 레이어를 추가했다.

반영:

- `chatbot_unknown_backlog_report.py`
  - `MedicalUnknownKnowledgeEvent`를 `status`, `category`, `primary_intent`,
    `missing_topic`, `needed_evidence_type`, `retrieval_status` 기준으로 집계한다.
  - 출력 payload에는 raw question, raw prompt, OCR 원문, 대화 전문이 들어갈 수 없다.
- `report_chatbot_unknown_backlog.py`
  - Supabase/PostgreSQL `DATABASE_URL`을 받아 JSON 또는 Markdown 리포트를 출력한다.
  - `postgresql://...sslmode=require` 형태의 Supabase connection string을 async SQLAlchemy용
    `postgresql+asyncpg://...ssl=require`로 정규화한다.
- Supabase 개발 DB 문서에 unknown backlog triage 명령과 운영 절차를 추가했다.

검증:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog_report.py
python -m ruff check backend/Nutrition-backend/src/services/chatbot_unknown_backlog_report.py backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog_report.py backend/scripts/report_chatbot_unknown_backlog.py
```

결과:

```text
unknown backlog report tests: 2 passed
ruff: All checks passed
```

## 20. 2026-05-29 live smoke backlog persistence check

Supabase `DATABASE_URL`이 준비되면 한 번의 live smoke로 DB-backed chat answer와 unknown backlog
저장까지 확인할 수 있도록 `smoke_ai_agent_server.py`를 보강했다.

반영:

- Supabase Dashboard connection string 정규화
  - `postgresql://...sslmode=require`
  - `postgresql+asyncpg://...ssl=require`
- 기본 live smoke가 기존 daily coaching/chat smoke에 더해 unknown 질문을 한 번 호출한다.
- unknown 호출 전후 `chatbot_unknown_knowledge_events` row 수를 DB에서 직접 확인한다.
- summary JSON에 `unknown_answerability`, `unknown_source_count`, `unknown_backlog_delta`를 추가했다.
- 이미 떠 있는 서버나 읽기 전용 점검에서는 `--skip-unknown-backlog-check`로 backlog row 증가 확인을
  생략할 수 있다.

검증:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/scripts/test_smoke_ai_agent_server.py
python -m ruff check backend/scripts/smoke_ai_agent_server.py backend/Nutrition-backend/tests/unit/scripts/test_smoke_ai_agent_server.py
```

결과:

```text
smoke script tests: 4 passed
ruff: All checks passed
```

## 21. 2026-05-29 chatbot golden answer eval

사용자가 기대한 답변 품질 조건을 CLI에서 바로 검증할 수 있도록 deterministic golden eval을
추가했다. 이 eval은 unit test보다 운영자가 읽기 쉬운 JSON 요약을 출력하며, 답변 품질 회귀를
빠르게 잡는 용도다.

반영:

- `eval_chatbot_golden.py`
  - `hypertension_sodium_dinner`
  - `magnesium_blood_pressure_med`
  - `urgent_chest_pain_shortness_of_breath`
  - `p0_grapefruit_lipid_med`
  - `unknown_lithium_selenium`
- 각 케이스에서 `answerability`, 필수 문구, 금지 문구, source id를 검사한다.
- eval 중 P0 boundary 답변에 `안전합니다` 표현이 포함되고 source metadata가 비어 있는 문제를
  발견해 수정했다.
  - P0 병용 답변 문구를 "임의로 시작, 중단, 증량, 감량하지 않는 쪽으로 안내합니다"로 변경
  - drug interaction boundary fallback에 `mfds-drug-safety` source metadata 추가

검증:

```powershell
python backend/scripts/eval_chatbot_golden.py
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_chatbot_agent.py::test_chatbot_p0_interaction_examples_return_boundary_without_llm backend/ai_agent_chat/tests/test_chatbot_renderers.py::test_boundary_renderer_uses_drug_safety_source_without_allow_or_ban_language
python -m ruff check backend/ai_agent_chat/src/lemon_ai_agent/renderers.py backend/ai_agent_chat/tests/test_chatbot_agent.py backend/ai_agent_chat/tests/test_chatbot_renderers.py backend/scripts/eval_chatbot_golden.py
```

결과:

```text
golden eval: 5 pass
focused P0 renderer tests: 2 passed
ruff: All checks passed
```

## 22. 2026-05-29 manual QA preset contract

수동 QA와 데모에 쓰는 `ask_chatbot_agent.py` preset이 읽기 쉬운 한국어 질문과 의도한
`answerability`를 유지하는지 테스트를 추가했다. PowerShell 콘솔 인코딩에 따라 `Get-Content`
출력이 깨져 보일 수 있으므로, 실제 UTF-8 파일 내용과 챗봇 라우팅 결과를 테스트로 고정했다.

검증:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/scripts/test_ask_chatbot_agent.py
python -m ruff check backend/Nutrition-backend/tests/unit/scripts/test_ask_chatbot_agent.py backend/scripts/ask_chatbot_agent.py
```

결과:

```text
ask chatbot preset tests: 2 passed
ruff: All checks passed
```

## 23. 2026-05-29 Supabase unknown backlog summary view

unknown backlog를 스크립트로만 보는 것이 아니라 Supabase Dashboard에서도 바로 triage할 수 있도록
privacy-safe aggregate view를 추가했다.

반영:

- Alembic `0013_create_chatbot_unknown_backlog_summary_view` 추가
- Supabase MCP migration `create_chatbot_unknown_backlog_summary_view` 적용
- Supabase `alembic_version.version_num`을
  `0013_create_chatbot_unknown_backlog_summary_view`로 갱신
- `chatbot_unknown_knowledge_backlog_summary`
  - `status`
  - `category`
  - `primary_intent`
  - `missing_topic`
  - `needed_evidence_type`
  - `retrieval_status`
  - `event_count`
  - `latest_event_at`
- view는 `security_invoker = true`로 생성해 underlying
  `chatbot_unknown_knowledge_events` table의 RLS를 따르게 했다.
- raw question, raw prompt, OCR 원문, conversation/free text 컬럼은 없다.

원격 Supabase 확인:

```text
alembic_version: 0013_create_chatbot_unknown_backlog_summary_view
chatbot_unknown_knowledge_backlog_summary unsafe columns: 0
security advisor: 신규 ERROR 없음
performance advisor: 새 dev DB unused_index INFO만 유지
```

검증:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py
python -m ruff check backend/alembic/versions/0013_create_chatbot_unknown_backlog_summary_view.py backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py
```

결과:

```text
alembic setup tests: 17 passed
ruff: All checks passed
```

## 24. 2026-05-29 P0 boundary reason detail

P0 복약/영양제 boundary 답변이 "허용 또는 금지로 판정하지 않는다"에서 멈추지 않고,
사용자가 왜 확인해야 하는지 이해할 수 있도록 조합별 위험 이유와 확인 정보를 보강했다.

반영:

- `BoundaryRenderer`의 `drug_or_interaction` 답변에 `위험 이유`와 `확인할 정보` 문구 추가
- P0 조합별 deterministic detail 추가 또는 구체화
  - 자몽 + 고지혈증 약: 대사와 혈중 농도 영향 가능성, 약 이름/성분명 확인
  - nitrate/협심증 약 + PDE5 억제제: 혈압 저하 가능성, 처방명/성분명 확인
  - 세인트존스워트 + 항우울제: 약효 변화와 세로토닌 관련 이상 반응 가능성
  - SSRI/SNRI + 세로토닌성 보충제: 작용 중복 가능성
  - 칼륨 보충제 + 저염소금: 칼륨 섭취 중복, 신장 기능과 복용 약 확인
  - 홍국 + 고지혈증 약: 작용 또는 성분 중복 가능성
- golden eval의 `p0_grapefruit_lipid_med` 케이스가 `위험 이유`, `혈중 농도`,
  `약 이름`, `성분명`을 요구하도록 강화
- nitrate/PDE5 renderer 단위 테스트 추가

검증:

```powershell
python backend/scripts/eval_chatbot_golden.py
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_chatbot_renderers.py backend/ai_agent_chat/tests/test_chatbot_agent.py -k "boundary or p0 or interaction"
```

결과:

```text
golden eval: 5 pass
focused P0 renderer/agent tests: 6 passed
```

## 25. 2026-05-29 manual QA golden presets

`ask_chatbot_agent.py`의 수동 QA preset이 기존 데모 질문에 머물러 있어 golden eval에서 보는
핵심 챗봇 케이스를 이름으로 바로 실행하기 어려웠다. 개발자와 운영자가 같은 질문 세트로
답변 품질을 확인할 수 있도록 golden 케이스에 맞춘 preset을 추가했다.

추가한 preset:

- `hypertension-sodium-dinner`
- `magnesium-blood-pressure-med`
- `p0-grapefruit-lipid-med`
- `unknown-lithium-selenium`
- `urgent-chest-pain`

확인 명령:

```powershell
python backend\scripts\ask_chatbot_agent.py --preset hypertension-sodium-dinner --llm none
python backend\scripts\ask_chatbot_agent.py --preset magnesium-blood-pressure-med --llm none
python backend\scripts\ask_chatbot_agent.py --preset p0-grapefruit-lipid-med --llm none
python backend\scripts\ask_chatbot_agent.py --preset unknown-lithium-selenium --llm none
python backend\scripts\ask_chatbot_agent.py --preset urgent-chest-pain --llm none
```

검증:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/scripts/test_ask_chatbot_agent.py
python -m ruff check backend/scripts/ask_chatbot_agent.py backend/Nutrition-backend/tests/unit/scripts/test_ask_chatbot_agent.py
```

## 26. 2026-05-29 Supabase smoke missing-DB hint

FastAPI + Supabase live smoke의 마지막 남은 입력값은 로컬에만 둬야 하는 DB password다.
`DATABASE_URL`이 없는 상태에서 스크립트가 짧은 에러만 출력하면 다음 행동이 불명확하므로,
Lemon Aid Supabase dev project 기준 placeholder connection string을 안내하도록 바꿨다.

반영:

- `smoke_ai_agent_server.py`에 Supabase dev project ref와 pooler host 기반 missing DB URL
  안내 추가
- 실제 password는 `<password>` placeholder로만 표시
- `TEST_DATABASE_URL`, `DATABASE_URL`, `--database-url` 중 하나를 쓰도록 안내
- 실제 connection string/password를 커밋하지 말라는 문구 추가

검증:

```powershell
python backend\scripts\smoke_ai_agent_server.py --skip-sglang-check
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/scripts/test_smoke_ai_agent_server.py backend/Nutrition-backend/tests/unit/scripts/test_ask_chatbot_agent.py
python -m ruff check backend/scripts/smoke_ai_agent_server.py backend/Nutrition-backend/tests/unit/scripts/test_smoke_ai_agent_server.py backend/scripts/ask_chatbot_agent.py backend/Nutrition-backend/tests/unit/scripts/test_ask_chatbot_agent.py
```

결과:

```text
missing DATABASE_URL hint: Supabase dev placeholder 출력 확인
script contract tests: 7 passed
ruff: All checks passed
```

## 27. 2026-05-29 remote Supabase backlog view probe and stricter live smoke

Supabase DB password 없이도 MCP SQL로 원격 DB의 reviewed knowledge readiness와 unknown backlog
summary view 동작을 확인했다. 또한 live FastAPI smoke가 단순히 `sources` 필드 존재만 확인하지
않고, sodium/hypertension 질문에서 실제 reviewed nutrition source를 반환해야 통과하도록 강화했다.

원격 Supabase SQL 확인:

```text
alembic_version: 0013_create_chatbot_unknown_backlog_summary_view
medical_sources: 7
reviewed non-stale source versions: 7
reviewed answerable evidence items: 14
reviewed answerable policy boundaries: 6
unknown events before/after smoke probe cleanup: 0 / 0
```

backlog summary view probe:

- 개인정보 없는 임시 missing topic `__smoke_probe_unknown_topic__` 삽입
- `chatbot_unknown_knowledge_backlog_summary`에서 `event_count = 1` 집계 확인
- 임시 event 삭제
- event table과 summary view에 임시 row가 남지 않음을 확인

live smoke 보강:

- reviewed sodium/hypertension 질문은 `answerability == "answerable"`이어야 함
- `sources[]`가 비어 있으면 실패
- `sources[]`에 `kdris-2025` 또는 `kdca-healthinfo`가 없으면 실패
- `review_status`가 포함된 source가 `reviewed`가 아니면 실패

검증:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/scripts/test_smoke_ai_agent_server.py
python -m ruff check backend/scripts/smoke_ai_agent_server.py backend/Nutrition-backend/tests/unit/scripts/test_smoke_ai_agent_server.py
python backend\scripts\smoke_ai_agent_server.py --skip-sglang-check
```

결과:

```text
smoke script tests: 7 passed
ruff: All checks passed
missing DATABASE_URL path: Supabase placeholder 안내 출력 확인
```

## 28. 2026-05-29 TODO/gap review status alignment

구현은 진행됐지만 `07-grounded-chatbot-todo.md`의 세부 체크박스가 최초 초안 상태로 남아 있어
현재 구현 상태와 충돌했다. completion audit 기준에서 완료된 항목과 남은 항목을 구분하도록
문서를 정리했다.

반영:

- Phase 1-8 구현 체크리스트를 현재 테스트/코드 기준으로 완료 표시
- Phase 9는 DB-backed retriever, production fail-closed, dev fallback, stale source 차단을 완료로 표시
- Phase 10 golden set은 현재 검증된 케이스와 아직 coverage 확장이 필요한 케이스를 분리
- 완료 정의에 Supabase `DATABASE_URL` live FastAPI smoke를 남은 항목으로 명시
- `10-grounded-chatbot-gap-review.md`의 source mismatch 항목을 해결 완료 상태로 갱신

현재 TODO에 남은 항목:

- KDRIs `approved -> reviewed` adapter 별도 테스트 명시
- `신장질환 + 채소/과일` golden coverage
- `당뇨 과식 후 다음 끼니` golden coverage
- Supabase `DATABASE_URL` live FastAPI smoke

검증:

```powershell
rg -n "\[ \]|NIH ODS를 KDRIs|NIDDK를 KDCA|safety_warnings만|세부 체크박스" docs/Integration-docs/07-grounded-chatbot-todo.md docs/Integration-docs/10-grounded-chatbot-gap-review.md
git diff --check -- docs/Integration-docs/07-grounded-chatbot-todo.md docs/Integration-docs/10-grounded-chatbot-gap-review.md
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/scripts/test_smoke_ai_agent_server.py backend/Nutrition-backend/tests/unit/scripts/test_ask_chatbot_agent.py
```

결과:

```text
remaining unchecked TODO: intended 4 items
doc diff check: no whitespace errors
script tests: 9 passed
```

## 29. 2026-05-29 kidney/diabetes golden coverage and KDRIs adapter test

남은 coverage TODO 중 live smoke 없이 검증 가능한 항목을 보강했다.

반영:

- golden eval에 `kidney_disease_vegetable_fruit_potassium` 추가
  - 신장질환 맥락에서 채소/과일은 칼륨 제한 여부를 먼저 확인하도록 요구
  - 관련 없는 supplement source가 섞이지 않고 `niddk-kidney-disease` source를 반환하도록 확인
- golden eval에 `diabetes_overeating_next_meal` 추가
  - 과식 후 다음 끼니에서 탄수화물/당류 조정, 비전분 채소, 단백질 후보를 요구
  - 두부, 달걀, 생선구이 같은 구체 후보를 요구
- `AnswerCardNormalizer`가 KDRIs seed를 `reviewed` nutrition source로 변환하는 별도 테스트 추가
- `ask_chatbot_agent.py` manual QA preset 추가
  - `kidney-vegetable-fruit-potassium`
  - `diabetes-overeating-next-meal`
- `07-grounded-chatbot-todo.md`에서 해당 coverage와 KDRIs adapter 항목을 완료로 갱신

검증:

```powershell
python backend\scripts\eval_chatbot_golden.py
python backend\scripts\ask_chatbot_agent.py --llm none "신장질환이 있는데 채소랑 과일은 어떻게 골라야 해? 칼륨이 걱정돼"
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_answer_card_normalizer.py backend/ai_agent_chat/tests/test_chatbot_agent.py -k "kdris or diabetes or kidney"
python -m ruff check backend/ai_agent_chat/src/lemon_ai_agent/agents/chatbot.py backend/ai_agent_chat/src/lemon_ai_agent/knowledge.py backend/ai_agent_chat/tests/test_answer_card_normalizer.py backend/scripts/eval_chatbot_golden.py
```

결과:

```text
golden eval: 7 pass
kidney manual QA: answerable, source niddk-kidney-disease only
focused tests: 4 passed
ruff: All checks passed
```

## 30. 2026-05-29 Supabase live DATABASE_URL smoke completion

로컬 `backend/.env`에 Supabase `DATABASE_URL`을 주입한 뒤, 막혀 있던 live smoke를
재개했다. 최초 안내에 사용한 pooler host `aws-0-ap-northeast-2.pooler.supabase.com`은
이 프로젝트에서 `tenant/user postgres.ajgvoxttzsjcwtphtsuz not found`를 반환했다.
동일한 DB 비밀번호로 pooler 후보를 점검한 결과 현재 프로젝트는
`aws-1-ap-northeast-2.pooler.supabase.com`에서 정상 연결된다.

반영:

- `backend/.env`의 Supabase pooler host를 `aws-1-ap-northeast-2.pooler.supabase.com`으로 교정
- `backend/.env.example`, live smoke 안내 문구, Supabase setup 문서의 pooler host 예시 교정
- DB-backed retriever가 복약/영양제 unknown 질문에서 `supplement_label_check`나 다른
  `*_caution` 카드를 넓게 재사용하지 않도록 매칭 순서를 강화
- `lithium medicine selenium supplement interaction` 회귀 테스트 추가

검증:

```powershell
python backend\scripts\smoke_chatbot_db_evidence.py
python backend\scripts\smoke_chatbot_db_evidence.py --preset magnesium-blood-pressure-med
python backend\scripts\smoke_chatbot_db_evidence.py --preset unknown-lithium-selenium
python backend\scripts\smoke_ai_agent_server.py --skip-db-upgrade --skip-sglang-check
python backend\scripts\eval_chatbot_golden.py
python -m pytest -q --no-cov backend\ai_agent_chat\tests backend\Nutrition-backend\tests\integration\api\test_ai_agent_api.py backend\Nutrition-backend\tests\unit\services\test_chatbot_unknown_backlog.py backend\Nutrition-backend\tests\unit\services\test_chatbot_unknown_backlog_report.py backend\Nutrition-backend\tests\unit\services\test_chatbot_evidence_retriever.py backend\Nutrition-backend\tests\unit\services\test_medical_source_readiness.py backend\Nutrition-backend\tests\unit\db\test_models.py backend\Nutrition-backend\tests\unit\db\test_alembic_setup.py backend\Nutrition-backend\tests\unit\scripts\test_ask_chatbot_agent.py backend\Nutrition-backend\tests\unit\scripts\test_smoke_ai_agent_server.py backend\Nutrition-backend\tests\unit\scripts\test_smoke_chatbot_db_evidence.py backend\Nutrition-backend\tests\unit\mobile\test_flutter_ai_agent_contract.py
python -m ruff check backend\ai_agent_chat\src\lemon_ai_agent\answer_card.py backend\ai_agent_chat\tests\test_answer_card_normalizer.py backend\scripts\smoke_ai_agent_server.py backend\Nutrition-backend\tests\unit\scripts\test_smoke_ai_agent_server.py
flutter analyze
git diff --check
```

결과:

```text
DB smoke sodium: ok, answerable, reviewed sources 3
DB smoke magnesium: ok, answerable_with_caution, source nih-ods-magnesium
DB smoke unknown: ok, unknown_no_reviewed_source, sources 0
FastAPI live smoke: ok, unknown backlog delta 1
golden eval: 7 pass
pytest: 201 passed, 1 skipped
focused ruff: All checks passed
flutter analyze: No issues found
git diff --check: no whitespace errors, line-ending warnings only
```
## 2026-05-30 추가 구현: AnswerCard 후보 선택 방식 정정

사용자 피드백에 따라 `AnswerCard`와 renderer가 채소/단백질 후보를 고정 FAQ처럼 반복하지
않도록 정정했다. `AnswerCard`의 `specific_examples`는 항상 출력할 문장 목록이 아니라,
질문 의도, 질환 맥락, 최근 영양 기록에 따라 선택할 수 있는 검수된 후보 재료다.

- 나트륨 저녁 fallback은 기본적으로 국물, 소스, 장류, 김치류, 가공육 같은 나트륨 직접 조정
  포인트를 우선 말한다.
- 단백질 후보는 `daily_coaching_summary`나 확인된 기록에 단백질 맥락이 있을 때만 추가한다.
- 신장질환 맥락에서는 채소/과일 일반 추천보다 칼륨 제한 확인을 우선한다.
- `test_chatbot_sodium_dinner_fallback_uses_specific_food_and_action_cards`는 채소/단백질
  개수 강제가 아니라 sodium-specific action 선택을 검증하도록 수정했다.
- `test_chatbot_sodium_dinner_adds_protein_candidates_only_when_context_needs_it`를 추가해
  필요한 영양 맥락이 있을 때만 단백질 후보가 들어가도록 고정했다.
- `eval_chatbot_golden.py`의 `hypertension_sodium_dinner` 기준도 고정 채소/단백질 후보 요구가
  아니라 나트륨 조정 포인트와 확인 가능한 기록 점검을 요구하도록 갱신했다.

## 2026-05-31 추가 구현: visible analysis stale 기준 확장

`이 결과로 질문하기` 흐름에서 사용자가 보고 있던 분석 결과가 현재 앱 기록과 달라졌는지
확인하는 기준을 확장했다. 기존에는 음식 기록 ID 변경만 감지했지만, 이제 오늘 체크한
영양제와 체크리스트 항목도 visible analysis context의 기준 ID와 비교한다.

반영:

- `visible_analysis_context.food_record_ids`와 현재 음식 기록 ID 비교 유지
- `visible_analysis_context.checked_supplement_ids`와 현재 `checked_today` 영양제 ID 비교 추가
- `visible_analysis_context.checklist_item_ids`와 현재 체크리스트 항목 ID 비교 추가
- 변경이 있으면 `stale=true`, `stale_reasons`, 현재 ID 목록을 함께 반환
- golden context case를 음식 기록, 영양제 체크, 체크리스트 변경 3종으로 확장

검증:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_user_health_context_snapshot.py
python backend\scripts\eval_chatbot_golden.py
python -m ruff check backend/Nutrition-backend/src/services/user_health_context_snapshot.py backend/Nutrition-backend/tests/unit/services/test_user_health_context_snapshot.py backend/scripts/eval_chatbot_golden.py
python -m pytest -q --no-cov backend/ai_agent_chat/tests backend/Nutrition-backend/tests/unit/services/test_user_health_context_snapshot.py backend/Nutrition-backend/tests/unit/services/test_food_records.py backend/Nutrition-backend/tests/unit/services/test_supplement_registration.py backend/Nutrition-backend/tests/unit/services/test_app_health_analysis.py backend/Nutrition-backend/tests/integration/api/test_food_records_api.py backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py backend/Nutrition-backend/tests/unit/db/test_models.py backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py backend/Nutrition-backend/tests/unit/mobile/test_flutter_ai_agent_contract.py
git diff --check
```

결과:

```text
user_health_context_snapshot unit: 4 passed
golden eval: 20 passed
focused ruff: All checks passed
targeted regression: 228 passed, 1 skipped
git diff --check: no whitespace errors, line-ending warnings only
```

추가 정리:

- 전체 backend ruff 실행을 막던 기존 lint 위반을 정리했다.
  - notification schema의 `23` magic value를 `MAX_HOUR_OF_DAY`로 치환
  - notifications API test의 unused argument 정리
  - answer card / knowledge matcher의 return 분기 수 축소
  - Alembic env / secure headers test import 정렬
- `12-agent-chatbot-todo.md`의 구현 TODO 체크박스를 현재 코드와 테스트 증거 기준으로 완료 갱신했다.

최종 확인:

```powershell
python -m ruff check backend
C:\src\flutter\bin\flutter.bat test
C:\src\flutter\bin\flutter.bat analyze
python backend\scripts\eval_chatbot_golden.py
python -m pytest -q --no-cov backend/ai_agent_chat/tests backend/Nutrition-backend/tests/unit/services/test_user_health_context_snapshot.py backend/Nutrition-backend/tests/unit/services/test_food_records.py backend/Nutrition-backend/tests/unit/services/test_supplement_registration.py backend/Nutrition-backend/tests/unit/services/test_app_health_analysis.py backend/Nutrition-backend/tests/integration/api/test_food_records_api.py backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py backend/Nutrition-backend/tests/unit/db/test_models.py backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py backend/Nutrition-backend/tests/unit/mobile/test_flutter_ai_agent_contract.py
python -m pytest -q --no-cov backend/Nutrition-backend/tests/integration/api/test_notifications_api.py backend/Nutrition-backend/tests/integration/test_secure_headers.py
git diff --check
```

결과:

```text
ruff backend: All checks passed
flutter test: 7 passed
flutter analyze: No issues found
golden eval: 20 passed
targeted regression: 228 passed, 1 skipped
lint-fix regression: 6 passed
git diff --check: no whitespace errors, line-ending warnings only
```

참고:

- `python -m pytest -q --no-cov backend` 전체 실행은 현재 worktree의 `backend/.env`에 있는
  sync PostgreSQL `DATABASE_URL`이 `Settings()` 단위 테스트에 주입되어 실패한다.
- 같은 실행에서 `DATABASE_URL`을 asyncpg URL로 덮어쓰면 대부분 통과하지만, 기본값을 기대하는
  config test 1개와 production `LOG_LEVEL` 환경 오염 test 2개가 남는다.
- 이는 이번 챗봇/앱 컨텍스트 구현 경로의 실패가 아니라 로컬 `.env`와 설정 테스트 격리 문제다.

## 2026-05-31 릴리스 TODO 실행

기준 문서:

- [13-agent-chatbot-release-todo.md](./13-agent-chatbot-release-todo.md)
- [14-agent-chatbot-release-execution-report.md](./14-agent-chatbot-release-execution-report.md)

작업 결과:

- PR 분리표를 7개 후보로 확정했다.
  - 문서/계약
  - agent/chatbot core
  - DB-backed evidence/unknown backlog
  - 앱 컨텍스트 데이터 API
  - 분석/CTA API
  - Flutter chat/CTA
  - 릴리스 smoke/운영
- 전체 backend pytest를 깨던 환경 오염을 수정했다.
  - `test_report_chatbot_unknown_backlog.py`에서 테스트가 남긴 `DATABASE_URL`을 직접 제거한다.
  - production config 테스트 baseline은 `_env_file=None`으로 로컬 `.env`와 분리한다.
- Supabase DB evidence smoke 3종을 통과시켰다.
  - `hypertension-sodium`: `answerable`, source 2개
  - `magnesium-blood-pressure-med`: `answerable_with_caution`, source 1개
  - `unknown-lithium-selenium`: `unknown_no_reviewed_source`, source 0개
- FastAPI live smoke를 통과시켰다.
  - 첫 실행은 Supabase dev DB에 `food_records` 테이블이 없어 실패했다.
  - `smoke_ai_agent_server.py --skip-sglang-check --timeout 120` 실행 중
    Alembic `0015_create_food_records`가 적용된 뒤 통과했다.
  - unknown backlog delta는 `2 -> 3`, `+1`로 확인했다.
- SGLang live smoke를 완료했다.
  - 첫 preflight에서는 Docker daemon이 꺼져 있고 host Python에 `sglang`/`torch`가 없어 blocked 상태였다.
  - Docker Desktop 시작 후 기존 `lemon-sglang` 컨테이너가 `127.0.0.1:30000`에 올라왔다.
  - 모델 로딩 완료 후 `/v1/models`가 `Qwen/Qwen2.5-0.5B-Instruct`를 반환했다.
  - `ask_chatbot_agent.py --llm sglang` 2종은 실제 `provider=sglang`로 응답했다.
  - FastAPI smoke도 `sglang_check=required` 상태로 통과했다.
  - 이때 daily-coaching은 `provider=sglang`, chatbot endpoint는 deterministic fallback으로 안전 계약을 유지했다.
- unknown backlog report를 최신화했다.
  - 현재 open group은 `supplement_drug_interaction` 1개, 4 events다.
  - 다음 coverage PR에서 공식 source, allowed/blocked wording, seed migration, golden test를 함께 추가한다.

검증:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/scripts/test_report_chatbot_unknown_backlog.py backend/Nutrition-backend/tests/unit/test_config.py
python -m ruff check backend
python -m pytest -q --no-cov backend
python backend\scripts\smoke_chatbot_db_evidence.py
python backend\scripts\smoke_chatbot_db_evidence.py --preset magnesium-blood-pressure-med
python backend\scripts\smoke_chatbot_db_evidence.py --preset unknown-lithium-selenium
python backend\scripts\smoke_ai_agent_server.py --skip-sglang-check --timeout 120
python backend\scripts\check_ai_agent_runtime_prereqs.py
python backend\scripts\ask_chatbot_agent.py --preset hypertension-sodium-dinner --llm sglang
python backend\scripts\ask_chatbot_agent.py --preset magnesium-blood-pressure-med --llm sglang
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_sglang_smoke.py backend/ai_agent_chat/tests/test_sglang_client.py backend/ai_agent_chat/tests/test_chatbot_agent.py::test_chatbot_structured_json_output_is_rendered_to_answer_sections
python backend\scripts\smoke_ai_agent_server.py --skip-db-upgrade --timeout 120
python backend\scripts\eval_chatbot_golden.py
python backend\scripts\report_chatbot_unknown_backlog.py --format markdown
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_answer_card_normalizer.py backend/ai_agent_chat/tests/test_chatbot_agent.py
```

결과:

```text
report/config focused tests: 51 passed
ruff backend: All checks passed
backend full pytest: 668 passed, 5 skipped, 3 warnings
DB evidence smoke: 3 presets passed
FastAPI smoke: passed after applying 0015_create_food_records
SGLang preflight: passed after starting Docker Desktop/lemon-sglang
SGLang asks: provider=sglang, safe answerability preserved
SGLang structured tests: 3 passed
FastAPI SGLang smoke: sglang_check=required, daily-coaching provider=sglang, chatbot fallback safe
golden eval: pass, 20 cases
unknown backlog report: 1 group, 4 events
answer-card/chatbot focused tests: 45 passed
```

## 2026-05-31 Reviewed evidence coverage 승격

대상:

- unknown backlog의 반복 smoke trigger였던 `리튬 + 셀레늄 영양제` 병용 질문
- 기존에는 `unknown_no_reviewed_source`로 닫았지만, 운영 루프 검증을 위해 첫 coverage 승격 대상으로 처리했다.

구현:

- `medlineplus-lithium` reviewed source를 registry에 추가했다.
  - Source: MedlinePlus Lithium Drug Information
  - Publisher: U.S. National Library of Medicine
  - URL: `https://medlineplus.gov/druginfo/meds/a681039.html`
  - review window: `2026-05-31` to `2026-11-30`
- `리튬 + 셀레늄` 조합을 `drug_or_interaction` boundary로 라우팅했다.
- boundary renderer는 개인 병용 허용/금지를 단정하지 않고, 리튬 혈중 농도, 신장 기능,
  탈수·염분 변화, 제품 라벨 확인, 의사 또는 약사 확인으로 답변한다.
- `0016_seed_lithium_supplement_boundary` Alembic migration에 source/version/boundary
  allowed wording과 blocked wording을 함께 넣었다.
- `unknown-lithium-selenium` preset은 이제 `medical_decision_boundary` 계약으로 바뀌었다.
- unknown 경로 회귀는 `리튬 + 타우린`처럼 아직 검수 source/boundary가 없는 조합으로 유지했다.

검증:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_medical_knowledge_registry.py::test_p0_interaction_and_context_questions_route_to_boundary_policy backend/ai_agent_chat/tests/test_chatbot_renderers.py::test_boundary_renderer_uses_lithium_source_for_selenium_supplement_question
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py backend/ai_agent_chat/tests/test_medical_knowledge_registry.py backend/ai_agent_chat/tests/test_chatbot_renderers.py backend/ai_agent_chat/tests/test_chatbot_agent.py backend/ai_agent_chat/tests/test_answer_card_normalizer.py
python backend\scripts\eval_chatbot_golden.py
python backend\scripts\ask_chatbot_agent.py --preset unknown-lithium-selenium --llm none
python backend\scripts\smoke_chatbot_db_evidence.py --preset unknown-herbal-blend
python backend\scripts\smoke_chatbot_db_evidence.py --preset unknown-lithium-selenium
python backend\scripts\smoke_ai_agent_server.py --skip-db-upgrade --timeout 120
python backend\scripts\report_chatbot_unknown_backlog.py --format markdown --output docs\Integration-docs\chatbot-unknown-backlog-report.md
```

결과:

```text
new boundary red/green tests: 2 passed after implementation
alembic/chatbot focused tests: 80 passed
golden eval: pass, 20 cases
unknown-lithium-selenium preset: medical_decision_boundary, source medlineplus-lithium
DB smoke unknown-herbal-blend: unknown_no_reviewed_source, source 0
DB smoke unknown-lithium-selenium: medical_decision_boundary, source medlineplus-lithium
FastAPI SGLang smoke: sglang_check=required, chat_provider=sglang, unknown delta 5 -> 6
unknown backlog report: 1 group, 6 events
```

## 2026-06-01 Flutter chatbot bridge 연결

대상:

- Flutter UI에서 챗봇 질문을 보내면 동의 생성, `/api/v1/ai-agent/chat` 호출,
  agent/chatbot 응답 렌더링이 한 흐름으로 이어지는지 확인했다.

구현:

- `ChatRepository`를 `chatRepositoryProvider`로 노출하고 `ChatScreen`이 Riverpod provider를
  통해 repository를 읽도록 바꿨다.
- widget test에서 repository를 override할 수 있게 되어, 화면 입력 -> consent 호출 ->
  chatbot 요청 -> assistant bubble/source/provider 렌더링을 고정했다.
- `ChatRepository`가 4xx/비정상 응답을 빈 챗봇 답변처럼 파싱하지 않고
  `ChatRepositoryException`으로 닫도록 수정했다.
- `0013_create_chatbot_unknown_backlog_summary_view` migration의 multi-statement `op.execute`
  를 분리해 asyncpg 로컬 Alembic upgrade가 통과하도록 고쳤다.
- mobile README와 flutter_app README에 FastAPI + Flutter chatbot 실행 순서를 반영했다.

검증:

```powershell
C:\src\flutter\bin\flutter.bat test test\chat_repository_test.dart test\widget_test.dart
python -m alembic -c backend\alembic.ini upgrade head
Invoke-RestMethod http://127.0.0.1:18080/health
python -c "<UTF-8 Korean chatbot smoke>"
```

결과:

```text
chat repository/widget tests: 4 passed
local Alembic upgrade: upgraded through 0016_seed_lithium_supplement_boundary
FastAPI health: {"status":"ok","version":"0.1.0"}
UTF-8 Korean chatbot smoke: medical_decision_boundary, source medlineplus-lithium
```

## 2026-06-08 MEDICAL-WIKI reviewed claim adapter 연결

대상:

- `C:\MyWorkspace\lemon_aid\MEDICAL-WIKI\manifest\reviewed_claims.jsonl`의 21개 reviewed claim
- `C:\MyWorkspace\lemon_aid\MEDICAL-WIKI\manifest\chatbot_answer_eval_inputs.jsonl`의 42개 golden boundary 질문

구현:

- `lemon_ai_agent.medical_wiki_claims.MedicalWikiReviewedClaimRetriever`를 추가했다.
  - `review_status=reviewed`
  - `rag_eligible=true`
  - `service_rag_eligible=true`
  - not expired
  - `allowed_user_wording`, `blocked_wording`, `sources`, `answer_card` 필수
- MEDICAL-WIKI claim을 backend `AnswerCard`로 변환한다.
- `AnswerCard`에 `severity`, `primary_action`, `blocked_wording`, `linked_claim_id` optional field를 추가했다.
- `ChatTurnModule`은 reviewed claim card의 `urgent_escalation`, `medical_decision_boundary`, `safety_boundary` answerability를 우선 보존한다.
- `BoundaryRenderer`는 `linked_claim_id`가 있는 reviewed claim boundary card를 기존 registry boundary source보다 먼저 deterministic 응답으로 렌더링한다.
- `eval_medical_wiki_chatbot.py`를 추가해 MEDICAL-WIKI 42개 eval input을 backend deterministic `ChatbotAgent` 경로로 검증한다.

검증:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_medical_wiki_claim_adapter.py backend/Nutrition-backend/tests/unit/scripts/test_eval_medical_wiki_chatbot.py
python -X utf8 backend\scripts\eval_medical_wiki_chatbot.py --as-of 2026-06-08
```

결과:

```text
medical wiki adapter/script tests: 7 passed
MEDICAL-WIKI backend deterministic eval: 42/42 pass
retrieved top-1: 42/42
retrieved top-k: 42/42
```

남은 점:

- SGLang/OpenAI-compatible structured output을 같은 42개 입력으로 비교하는 작업은 후속 단계다.
- LangChain, vector DB, embedding, reranker는 아직 붙이지 않았다.

## 2026-06-08 MEDICAL-WIKI LLM guardrail eval

대상:

- `MEDICAL-WIKI/manifest/chatbot_answer_eval_inputs.jsonl` 42개
- 모두 `urgent_escalation`, `medical_decision_boundary`, `safety_boundary` 계열 boundary/safety anchor다.

구현:

- `backend/scripts/eval_medical_wiki_chatbot.py`에 `--llm none|ollama|sglang` 옵션을 추가했다.
- `--llm sglang` 모드는 SGLang client를 `ChatbotAgent`에 주입하되, reviewed claim boundary가 LLM보다 먼저 닫히는지 확인한다.
- 결과 파일은 `MEDICAL-WIKI/manifest/backend_llm_guardrail_eval_results.jsonl`에 쓴다.
- fake LLM client를 넣어도 boundary에서 호출되지 않는 단위 테스트를 추가했다.

검증:

```powershell
python -m ruff check backend/scripts/eval_medical_wiki_chatbot.py backend/Nutrition-backend/tests/unit/scripts/test_eval_medical_wiki_chatbot.py
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/scripts/test_eval_medical_wiki_chatbot.py
python -X utf8 backend\scripts\eval_medical_wiki_chatbot.py --as-of 2026-06-08 --llm sglang
python -X utf8 backend\scripts\ask_chatbot_agent.py --llm sglang --mode raw --timeout 30 "Return the word ok."
```

결과:

```text
ruff: All checks passed
script tests: 3 passed
MEDICAL-WIKI LLM guardrail eval: 42/42 pass
retrieved top-1: 42/42
LLM bypassed by boundary: 42/42
raw SGLang smoke: provider=sglang, model=Qwen/Qwen2.5-0.5B-Instruct
```

해석:

- 이 42개 eval에서 LLM이 답변을 생성하지 않는 것이 성공 조건이다.
- 실제 structured output 품질 평가는 answerable reviewed card 또는 reviewed section 입력이 생긴 뒤 별도 eval로 만든다.

## 2026-06-09 MEDICAL-WIKI 최신 25 claim / 50 eval adapter 갱신

대상:

- `MEDICAL-WIKI/manifest/reviewed_claims.jsonl`의 25개 reviewed/service-rag-eligible claim
- `MEDICAL-WIKI/manifest/chatbot_answer_eval_inputs.jsonl`의 50개 backend eval 입력
- 새로 승격된 4개 claim:
  - anxiety/panic red flag
  - drug-nutrient interaction clearance 금지
  - food combination / interaction generalization 금지
  - exercise prescription red flag

반영:

- `MedicalWikiReviewedClaimRetriever`의 lightweight query boost를 최신 4개 claim까지 확장했다.
- 기존 21개 claim 기준 adapter 테스트를 25개 claim 기준으로 갱신했다.
- MEDICAL-WIKI manifest 원문을 raw RAG로 넣지 않고, reviewed claim -> `AnswerCard` -> deterministic boundary renderer 경로만 사용했다.

검증:

```powershell
python -X utf8 backend\scripts\eval_medical_wiki_chatbot.py --as-of 2026-06-09
python -X utf8 -m pytest -q --no-cov backend\ai_agent_chat\tests\test_medical_wiki_claim_adapter.py backend\Nutrition-backend\tests\unit\scripts\test_eval_medical_wiki_chatbot.py
python -X utf8 -m pytest -q --no-cov backend\ai_agent_chat\tests
python -m ruff check backend\ai_agent_chat\src\lemon_ai_agent\medical_wiki_claims.py backend\ai_agent_chat\src\lemon_ai_agent\answer_card.py backend\ai_agent_chat\src\lemon_ai_agent\chat_turn.py backend\ai_agent_chat\src\lemon_ai_agent\renderers.py backend\scripts\eval_medical_wiki_chatbot.py backend\ai_agent_chat\tests\test_medical_wiki_claim_adapter.py backend\Nutrition-backend\tests\unit\scripts\test_eval_medical_wiki_chatbot.py
python -m compileall backend\ai_agent_chat\src\lemon_ai_agent\medical_wiki_claims.py backend\ai_agent_chat\src\lemon_ai_agent\answer_card.py backend\ai_agent_chat\src\lemon_ai_agent\chat_turn.py backend\ai_agent_chat\src\lemon_ai_agent\renderers.py backend\scripts\eval_medical_wiki_chatbot.py
```

결과:

```text
MEDICAL-WIKI backend deterministic eval: 50/50 pass
retrieved top-1: 50/50
retrieved top-k: 50/50
medical wiki adapter/script tests: 8 passed
ai_agent_chat tests: 134 passed, 1 skipped
ruff: All checks passed
compileall: passed
forbidden marker scan: no hits
```

해석:

- backend adapter는 최신 25개 reviewed claim과 50개 eval 입력을 실제로 소비한다.
- boundary 질문은 deterministic renderer에서 닫히며, 복약 변경, 진단 단정, 응급 red flag 완화,
  운동/식단 해결 지시를 내지 않는다.
- `sources[]`에는 eval 입력이 요구한 reviewed `source_id`가 유지된다.

## 2026-06-09 MEDICAL-WIKI EvidenceBundle backend adapter 연결

대상:

- `MEDICAL-WIKI/manifest/evidence_bundle_adapter_fixtures.jsonl`의 60개 EvidenceBundle adapter fixture
  - boundary fixture 50개
  - answerable-with-section fixture 10개

반영:

- `lemon_ai_agent.medical_wiki_evidence_bundles.MedicalWikiEvidenceBundleRetriever`를 추가했다.
- EvidenceBundle fixture를 backend `AnswerCard` tuple로 변환한다.
  - boundary fixture는 `urgent_escalation`, `medical_decision_boundary`, `safety_boundary` 중 하나로 유지한다.
  - answerable fixture는 `answerable_with_caution` card로 유지하고 linked boundary claim을 `linked_claim_id`로 보존한다.
  - section explanation은 `reviewed_section:<section_id>` grounding id와 card checklist/examples로만 반영한다.
  - boundary fixture는 section grounding을 버린다.
- `blocked_actions`, safety anchor `blocked_wording`, section `blocked_scope`/`must_not_do`를
  `AnswerCard.must_not_say`로 전달한다.
- `sources[]`에는 claim source와 section source의 `source_id`, `source_family`,
  `review_status`, `version_label`, `reviewed_at`, `expires_at`, `source_url`을 additive field로 보존한다.
- `eval_medical_wiki_evidence_bundles.py`를 추가해 backend deterministic `ChatbotAgent` 경로에서
  route/source/safety 계약을 검증한다.
- raw retrieval rank, matched terms, debug trace, raw prompt, raw LLM response는 adapter 입력이나
  사용자-facing 응답에 넣지 않았다.

검증:

```powershell
python -X utf8 -m pytest -q --no-cov backend\ai_agent_chat\tests\test_medical_wiki_evidence_bundle_adapter.py backend\Nutrition-backend\tests\unit\scripts\test_eval_medical_wiki_evidence_bundles.py
python -X utf8 backend\scripts\eval_medical_wiki_evidence_bundles.py --as-of 2026-06-09 --dry-run
python -X utf8 MEDICAL-WIKI\tools\run_claim_section_retrieval_smoke.py --as-of 2026-06-09 --dry-run
python -X utf8 MEDICAL-WIKI\tools\run_evidence_bundle_normalizer_smoke.py --as-of 2026-06-09 --dry-run
python -X utf8 MEDICAL-WIKI\tools\run_answerable_normalizer_polish_smoke.py --mode draft --dry-run
python -X utf8 MEDICAL-WIKI\tools\run_answerable_normalizer_polish_smoke.py --mode polish --llm sglang --dry-run --timeout 60
python -X utf8 backend\scripts\eval_medical_wiki_chatbot.py --as-of 2026-06-09 --llm sglang --dry-run
```

결과:

```text
EvidenceBundle adapter tests: 5 passed
backend EvidenceBundle deterministic eval: 60/60 pass
boundary renderer fixtures: 50
answer renderer with boundary anchor fixtures: 10
forbidden marker hits: 0
unsafe pattern hits: 0
claim + section retrieval smoke: 60/60 pass
answerable section top-1: 10/10
boundary claim top-k: 50/50
EvidenceBundle normalizer smoke: 60/60 pass
answerable section included: 10/10
boundary sections discarded: 50/50
answerable deterministic draft smoke: 30/30 pass
answerable SGLang polish smoke: 30/30 pass
backend SGLang guardrail eval: 50/50 pass, LLM bypassed by boundary 50/50
```

LangChain/vector DB/reranker/SGLang 해석:

- `run_claim_section_retrieval_smoke.py`의 `claim_section_boundary_claim_first` 경로로
  boundary claim-first rerank 기준을 확인했다.
- `build_langchain_review_pipeline.py`는 candidate review index manifest를 생성하는 helper-only
  도구이며, `/api/v1/ai-agent/chat` runtime이나 production dependency로 연결하지 않았다.
- SGLang은 answerable deterministic draft의 polish 보존 smoke로만 확인했다.
  boundary 50개는 `--llm sglang`에서도 계속 deterministic bypass가 성공 조건이다.
