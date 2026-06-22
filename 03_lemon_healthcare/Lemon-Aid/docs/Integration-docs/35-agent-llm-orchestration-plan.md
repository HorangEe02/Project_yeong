# 35. Agent/LLM Orchestration Plan

작성일: 2026-06-05

이 문서는 Agent/LLM 작업의 **실행 관제판**이다. 26~34번 문서를 다시 요약하거나
대체하지 않는다. 각 문서가 맡은 source of truth를 유지하면서, 어떤 순서로 실행하고
어떤 gate를 통과해야 다음 작업으로 갈 수 있는지 관리한다.

## 1. 문서 역할

35번 문서가 하는 일:

- Agent/LLM 작업의 phase, gate, blocked 조건을 한 곳에서 관리한다.
- 구현 slice를 시작하기 전에 작성할 touchpoint map 템플릿을 제공한다.
- 아직 구현/문서화가 약한 future risk를 누락되지 않게 추적한다.
- 새 문서를 계속 늘릴지, 기존 문서를 갱신할지 판단하는 운영 규칙을 둔다.

35번 문서가 하지 않는 일:

- 30번의 PR별 세부 TODO를 복제하지 않는다.
- 34번의 current-state readiness audit을 복제하지 않는다.
- 모델, schema, API 계약의 source of truth를 새로 만들지 않는다.
- 전체 touchpoint map을 미리 확정하지 않는다.

## 2. Source of Truth

| 영역 | 기준 문서 | 이 문서에서의 사용 방식 |
| --- | --- | --- |
| 제품 방향, Agent/LLM 정체성 | [26](./26-agent-llm-product-direction-reset.md) | 방향 판단 기준 |
| 제품 요구사항 | [27](./27-agent-llm-prd.md) | 제품 목표/비목표 판단 기준 |
| 기술 요구사항 | [28](./28-agent-llm-trd.md) | backend, DB, mobile, runtime 요구사항 기준 |
| 기술 설계 | [29](./29-agent-llm-tdd.md) | memory, analysis, checklist, boundary, retrieval 설계 기준 |
| 세부 PR TODO | [30](./30-agent-llm-todo.md) | PR별 실행 TODO 기준 |
| runtime/model/eval 기준 | [31](./31-agent-llm-runtime-decision-eval.md) | SGLang, Ollama fallback, Qwen/Gemma 채택 gate |
| smoke/eval 결과 | [32](./32-agent-llm-model-smoke-eval-report.md) | deterministic/live smoke 결과 기록 |
| 팀 통합 I/O 계약 | [33](./33-agent-llm-team-integration-contract.md) | DB/backend/mobile 최소 계약 |
| 현재 readiness 판단 | [34](./34-agent-llm-readiness-audit.md) | 지금 시작 가능한 slice와 no-go 판단 |

기존 grounded chatbot 구현을 수정해야 할 때는 05~10번과 17~22번을 함께 확인한다. 이때도
새 Agent/LLM 방향 판단은 26~34번을 기준으로 한다.

## 3. 10-Day Success Target

10일 목표는 축소판 chatbot이 아니다. 목표는 **Agent/LLM full vertical integration**이다.

Day 10 성공 기준:

- Flutter에서 사용자가 Agent에게 질문한다.
- Agent가 memory, app context, reviewed evidence를 함께 읽는다.
- LLM은 결정자가 아니라 답변 생성/정리 역할을 한다.
- 위험 질문은 BoundaryPlan으로 닫고, 근거 없는 질문은 unknown으로 닫는다.
- 음식, 영양제, 복약 context는 confirmed record 기준으로만 강하게 반영한다.
- today analysis snapshot과 smart analysis snapshot을 응답에 포함할 수 있다.
- checklist 후보와 CTA를 생성할 수 있다.
- `sources[]`, `ctas[]`, approval preview, boundary/unknown 상태를 Flutter가 표시할 수 있다.
- Qwen baseline과 Gemma 후보의 smoke/eval 결과가 있다.
- SGLang 경로를 우선 검증하고, 막히면 Ollama fallback으로 end-to-end demo가 돈다.
- golden scenario가 deterministic 경로와 LLM smoke 경로에서 핵심 boundary를 통과한다.

작업 방식:

- 기능을 빼지 않는다.
- 각 기능은 10일 안에 통합 가능한 v1 형태로 만든다.
- 완성도 고도화는 뒤로 미룰 수 있지만, 전체 흐름은 end-to-end로 돌아야 한다.
- 매일 최소 한 번 full flow smoke가 가능한 상태를 목표로 한다.

## 4. 10-Day Execution Board

10일 동안 순차 waterfall로 진행하지 않는다. 아래 track을 병렬로 진행하고, 매일 통합 상태를
확인한다.

| Track | 목표 | Day 10 산출물 | 주요 기준 문서 |
| --- | --- | --- | --- |
| Core Agent | memory, context resolver, answer plan, boundary, reviewed evidence를 연결한다. | memory + context + evidence 기반 답변 path | 26~30, 33~35 |
| Product Loop | today/smart analysis, checklist, CTA, approval preview를 연결한다. | analysis snapshot + checklist 후보 + CTA 응답 | 27~30, 33, 35 |
| Integration | DB confirmed adapter와 Flutter response contract를 맞춘다. | confirmed context와 mobile DTO/display contract | 30, 33~35 |
| Runtime | SGLang Qwen/Gemma, Ollama fallback, latency/error smoke를 검증한다. | Qwen/Gemma smoke 결과와 fallback demo path | 31, 32, 35 |
| Verification | golden scenarios와 demo script를 고정한다. | deterministic + LLM smoke + demo scenario | 30, 32, 35 |

10-day board:

| Day | 통합 목표 | 완료 gate |
| --- | --- | --- |
| Day 1 | 10일 목표 고정, Phase 1 touchpoint map 작성, worktree/doc 상태 보호 | 35번에 10-day board 반영, touchpoint map 준비 |
| Day 2 | Agent memory 4종 최소 schema와 v0 compatibility 시작 | memory 저장/조회 unit path |
| Day 3 | memory retrieval을 chat context에 연결 | raw 미저장 test, 기존 `agent_memory` read compatibility |
| Day 4 | confirmed food/supplement/medication context adapter 연결 | preview/candidate exclusion test |
| Day 5 | today/smart analysis snapshot과 checklist 후보 v1 연결 | response payload에 analysis/checklist/CTA 포함 |
| Day 6 | mobile response contract와 boundary/unknown/source 표시 연결 | Flutter DTO compatibility smoke |
| Day 7 | SGLang Qwen smoke와 Ollama fallback demo path 정리 | Qwen 또는 fallback end-to-end answer |
| Day 8 | Gemma 후보 smoke와 모델 비교 기록 | Qwen/Gemma/fallback 결과가 32번에 기록 |
| Day 9 | golden scenarios, error/timeout/fallback UX 정리 | representative scenarios 통과 |
| Day 10 | full vertical integration demo hardening | Flutter -> backend -> Agent/LLM -> response display demo 통과 |

## 5. Execution Phases

상태 값은 `Ready`, `In Progress`, `Blocked`, `Done`만 사용한다. PR별 체크박스는 30번에서
관리한다.

| Phase | 상태 | 목표 | 주요 기준 문서 | 완료 gate |
| --- | --- | --- | --- | --- |
| Phase 0. 기준 보호 | Done | 31~35 문서와 README 색인을 보호한다. | 31~35 | 문서가 index에 잡히고 diff check 통과 |
| Phase 1. Memory schema | Done | memory 4종 schema와 v0 compatibility adapter를 만든다. | 26~30, 33, 34 | raw 미저장 test와 기존 `agent_memory` read compatibility 통과 |
| Phase 2. Confirmed record adapter | Ready | 음식/영양제/복약 confirmed record만 Agent context로 쓰게 한다. | 26, 28~30, 33, 34 | preview/candidate exclusion test 통과 |
| Phase 3. Runtime live smoke | Blocked | SGLang Qwen/Gemma live smoke로 모델 후보를 비교한다. | 31, 32, 34 | SGLang prereq, Qwen smoke, Gemma smoke 통과 |
| Phase 4. Mobile response contract | Ready | Flutter가 CTA, approval, sources, boundary, analysis snapshot을 표시할 계약을 맞춘다. | 28~30, 33, 34 | DTO compatibility와 source/approval UI contract test 통과 |
| Phase 5. Integration hardening | Ready | session, rate limit, latency, observability, deletion, push 등 10일 성공에 필요한 gate를 정리한다. | 31~35 | Future Risk Register의 Blocker/Day-10 Critical 항목이 닫힘 |

## 6. Phase Gate Rules

### Phase 0. 기준 보호

시작 조건:

- 31~34번 문서가 작성되어 있다.
- README에 Agent/LLM 문서 참조 가이드가 있다.

완료 조건:

- 35번 문서가 작성된다.
- `docs/Integration-docs/README.md`와 `docs/README.md`에 35번이 잡힌다.
- `diff --check`가 통과한다.

Blocked 조건:

- 35번이 30번 TODO 또는 34번 readiness audit을 중복해 source of truth가 둘로 갈라진다.

### Phase 1. Memory schema

시작 조건:

- Phase 0 완료.
- 구현 전 slice touchpoint map 작성.

완료 조건:

- `profile`, `behavior`, `conversation`, `safety` memory type을 저장/조회할 수 있다.
- 기존 v0 `agent_memory` summary를 깨지 않고 읽는다.
- raw transcript, raw prompt, raw provider payload가 memory에 저장되지 않는 negative test가 있다.

Blocked 조건:

- memory 저장이 공식 음식/영양제/복약 DB를 자동 수정한다.
- chat-derived memory와 confirmed app record가 구분되지 않는다.

### Phase 2. Confirmed record adapter

시작 조건:

- 구현 전 slice touchpoint map 작성.
- 팀 브랜치를 바로 merge하지 않고 contract adapter 기준으로 확인한다.

완료 조건:

- 영양제는 `user_confirmed=true`와 deterministic `nutrient_code` 기준을 통과한 데이터만 강하게 반영한다.
- 식단은 user review/confirmation equivalent 기준을 통과한 데이터만 강하게 반영한다.
- 복약은 active status, provenance, medication class 기준이 명확하다.
- OCR/YOLO/LLM preview는 Agent context에서 확정 기록으로 쓰이지 않는다.

Blocked 조건:

- preview/candidate 데이터가 confirmed record와 같은 priority로 들어간다.
- raw OCR/LLM/model output이 context나 memory에 들어간다.

### Phase 3. Runtime live smoke

시작 조건:

- SGLang server와 model serving 환경이 준비된다.
- 31번의 Qwen baseline, Gemma candidate 기준을 유지한다.

완료 조건:

- SGLang Qwen live smoke 결과가 32번에 기록된다.
- SGLang Gemma live smoke 결과가 32번에 기록된다.
- Ollama fallback smoke 결과가 32번에 기록된다.
- answerability, boundary, source use, structured JSON parse, latency를 비교한다.

Blocked 조건:

- SGLang prereq가 통과하지 않는다.
- live smoke 없이 Gemma를 기본 모델로 바꾸려 한다.
- Ollama fallback을 production runtime으로 간주한다.

### Phase 4. Mobile response contract

시작 조건:

- 33번의 Agent I/O 계약을 기준으로 endpoint/DTO mismatch를 확인한다.
- 구현 전 slice touchpoint map 작성.

완료 조건:

- `sources[]`, `ctas[]`, `requires_user_approval`, `BoundaryPlan`, `analysis_snapshot` 표시 계약이 맞는다.
- timeout/error/fallback UX가 최소 계약에 포함된다.
- raw/internal field가 Flutter 응답에 노출되지 않는 test가 있다.

Blocked 조건:

- canonical endpoint `/api/v1/ai-agent/chat` 기준이 깨지거나 `/api/v1/agents/chat` alias를 새로 만들려 한다.
- Flutter가 unknown/source/boundary 상태를 구분해 표시할 수 없다.

### Phase 5. Integration hardening

시작 조건:

- Phase 1~4의 핵심 계약이 안정된다.
- Future Risk Register에서 Blocker/Day-10 Critical 항목의 owner가 정해진다.

완료 조건:

- session, rate limit, latency, observability, deletion, push, concurrency 중 Day 10 성공에 필요한 항목의 gate가 정리된다.
- release 전 필수 smoke/eval/monitoring 기준이 문서화된다.

Blocked 조건:

- 운영 리스크가 "나중에"로만 남고 owner/gate가 없다.

## 7. Slice Touchpoint Map Template

구현 slice가 확정되면 코드 수정 전에 아래 템플릿을 이 문서 또는 해당 slice 문서에 복사해
채운다. 전체 시스템 touchpoint map을 미리 만들지 않는다.

```markdown
### Touchpoint Map: <slice name>

- 목표:
- 기준 문서:
- 건드릴 가능성이 있는 backend 영역:
- 건드릴 가능성이 있는 DB/migration 영역:
- 건드릴 가능성이 있는 mobile/API contract:
- 기존 grounded chatbot 문서 확인 필요 여부:
- 팀 브랜치에서 확인할 후보:
- migration 필요 여부:
- 테스트/smoke 명령:
- 건드리면 안 되는 영역:
- 연결된 Future Risk 항목:
- 완료 조건:
```

### Touchpoint Map: Agent/LLM full vertical integration Day 1

- 목표:
  - Day 10 full vertical integration을 줄이지 않고, Day 2부터 바로 구현할 첫 slice와 검증 명령을 고정한다.
  - Agent memory, confirmed context, mobile response contract, runtime smoke를 한꺼번에 병합하지 않고 각각의 adapter/gate로 분리한다.
- 기준 문서:
  - Agent/LLM 방향과 요구사항: [26](./26-agent-llm-product-direction-reset.md), [27](./27-agent-llm-prd.md), [28](./28-agent-llm-trd.md), [29](./29-agent-llm-tdd.md), [30](./30-agent-llm-todo.md)
  - runtime/eval/team/readiness: [31](./31-agent-llm-runtime-decision-eval.md), [32](./32-agent-llm-model-smoke-eval-report.md), [33](./33-agent-llm-team-integration-contract.md), [34](./34-agent-llm-readiness-audit.md)
  - 기존 grounded chatbot 기준: [05](./05-grounded-chatbot-prd.md), [06](./06-grounded-chatbot-tdd.md), [07](./07-grounded-chatbot-todo.md), [08](./08-grounded-chatbot-trd.md), [09](./09-grounded-chatbot-implementation-log.md), [10](./10-grounded-chatbot-gap-review.md)
  - 관련 구현 로그 확인 대상: [17](./17-agent-chatbot-source-governance-implementation-log.md), [18](./18-agent-chatbot-entity-normalization-implementation-log.md), [19](./19-agent-chatbot-boundary-coverage-implementation-log.md), [20](./20-agent-chatbot-retrieval-eval-implementation-log.md), [21](./21-agent-chatbot-structured-output-implementation-log.md), [22](./22-agent-chatbot-source-ui-observability-implementation-log.md)
- 건드릴 가능성이 있는 backend 영역:
  - Day 2 첫 slice: `backend/Nutrition-backend/src/models/db/agent_memory.py`, `backend/Nutrition-backend/src/services/agent_memory.py`, `backend/Nutrition-backend/tests/unit/services/test_agent_memory.py`, `backend/Nutrition-backend/tests/unit/db/test_models.py`
  - compatibility 확인: `backend/Nutrition-backend/src/api/v1/ai_agent.py`, `backend/ai_agent_chat/src/lemon_ai_agent/app_intake.py`, `backend/ai_agent_chat/tests/test_agent_memory_context.py`
- 건드릴 가능성이 있는 DB/migration 영역:
  - 기존 `agent_memory` v0 table을 깨지 않는 additive migration 또는 repository-level compatibility를 우선 검토한다.
  - Day 2에서는 `profile_memory`, `behavior_memory`, `conversation_memory`, `safety_memory` type contract와 raw/internal field exclusion을 먼저 테스트로 고정한다.
- 건드릴 가능성이 있는 mobile/API contract:
  - Day 1에는 수정하지 않는다.
  - Day 6 후보로 `answerability`, `sources[]`, `ctas[]`, `requires_user_approval`, `analysis_snapshot`, boundary/unknown 표시 계약만 유지 확인한다.
- 기존 grounded chatbot 문서 확인 필요 여부:
  - 필요하다. Day 2 memory slice가 `/api/v1/ai-agent/chat`, `agent_memory`, `daily_coaching_summary`, `AnswerCard`/boundary/unknown 경로와 충돌하지 않아야 한다.
  - 단, Day 2는 reviewed evidence/RAG coverage를 넓히는 작업이 아니므로 05~10번의 source governance를 재정의하지 않는다.
- 팀 브랜치에서 확인할 후보:
  - `origin/sunghoon-database`: memory/profile/reminder schema 후보를 adapter 계약 참고로만 본다.
  - `origin/yeong-tech`: `user_confirmed`, `requires_confirmation`, deterministic `nutrient_code` 원칙을 confirmed supplement adapter 후보로 본다.
  - `origin/jongpil-tech`: `needs_user_review`, `food_code`, `estimated_grams` 같은 식단 adapter 후보 필드만 본다.
  - `origin/taedong-design`: source/CTA/boundary/streaming UI 아이디어를 mobile response contract 후보로만 본다.
  - 위 브랜치는 Day 1/Day 2에서 merge 대상이 아니다.
- migration 필요 여부:
  - Day 2 시작 전 확인한다.
  - v0 `agent_memory` table에 type contract만 추가해도 충분하면 migration 없이 service/repository compatibility를 먼저 고정한다.
  - 새 컬럼이 필요하면 raw transcript, raw prompt, raw provider payload 컬럼은 추가하지 않는다.
- 테스트/smoke 명령:
  - Day 2 RED 후보:
    - `python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_agent_memory.py`
    - `python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/db/test_models.py`
    - `python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_agent_memory_context.py`
  - Day 2 GREEN 후 회귀 후보:
    - `python -m pytest -q --no-cov backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py`
    - `python backend/scripts/eval_chatbot_golden.py`
- 건드리면 안 되는 영역:
  - 팀 브랜치 직접 merge 또는 cherry-pick
  - Gemma 기본 모델 전환, SGLang runtime 기본값 변경
  - `guide.html` 직접 수정
  - raw chat 전문, raw prompt, raw OCR, raw LLM output, provider payload를 memory/API/unknown backlog에 저장하는 구조
  - OCR/YOLO/LLM preview를 confirmed food/supplement/medication context로 승격하는 구조
  - reviewed source governance, `AnswerCard`, boundary/unknown renderer의 source of truth 재정의
- 연결된 Future Risk 항목:
  - Conversation session 관리
  - Privacy/deletion
  - Multi-device/concurrency
  - Reviewed evidence 콘텐츠 운영
  - Mobile contract completeness
  - Production LLM infra
- 완료 조건:
  - 35번의 Day 1 checklist와 gate가 완료 상태로 갱신된다.
  - Day 2 첫 구현 slice가 `Agent memory 4종 schema + v0 compatibility adapter`로 명확하다.
  - 팀 의존 질문과 독립 구현 작업이 분리되어 있다.
  - 코드 수정 전에 건드리면 안 되는 영역과 테스트 명령이 명시되어 있다.

### Touchpoint Map: Agent/LLM full vertical integration Day 3

- 목표:
  - Day 2에서 만든 `profile_memory`, `behavior_memory`, `conversation_memory`,
    `safety_memory` bundle을 `/api/v1/ai-agent/chat`의 grounding context에 연결한다.
  - chat-derived memory는 사용자 보고/요약 정보로 낮은 강도로만 반영하고, 공식 음식/영양제/복약
    DB record처럼 확정 표현하지 않는다.
- 기준 문서:
  - Agent/LLM memory 설계: [29](./29-agent-llm-tdd.md), [30](./30-agent-llm-todo.md)
  - 팀 통합 I/O 계약과 readiness: [33](./33-agent-llm-team-integration-contract.md), [34](./34-agent-llm-readiness-audit.md)
  - Day 1/2 실행 gate: [35](./35-agent-llm-orchestration-plan.md)
  - 기존 grounded chatbot 기준: [05](./05-grounded-chatbot-prd.md), [06](./06-grounded-chatbot-tdd.md), [08](./08-grounded-chatbot-trd.md), [10](./10-grounded-chatbot-gap-review.md)
- 건드릴 가능성이 있는 backend 영역:
  - `backend/ai_agent_chat/src/lemon_ai_agent/agents/chatbot.py`
  - `backend/ai_agent_chat/tests/test_chatbot_agent.py`
  - `backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py`
- 건드릴 가능성이 있는 DB/migration 영역:
  - 없다. Day 2의 service-level `memory_bundle` 계약을 소비한다.
- 건드릴 가능성이 있는 mobile/API contract:
  - response DTO는 바꾸지 않는다.
  - `used_tools`의 `agent_memory` 유지와 internal prompt/context raw-free 보장을 확인한다.
- 기존 grounded chatbot 문서 확인 필요 여부:
  - 필요하다. `AnswerCard`, reviewed evidence, boundary/unknown renderer의 source of truth를 재정의하지 않는다.
- 팀 브랜치에서 확인할 후보:
  - 없다. Day 3는 팀 브랜치 merge/cherry-pick 없이 현 worktree의 memory retrieval 소비만 구현한다.
- migration 필요 여부:
  - 없다.
- 테스트/smoke 명령:
  - RED/GREEN:
    - `python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_chatbot_agent.py`
    - `python -m pytest -q --no-cov backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py`
  - 회귀:
    - `python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_agent_memory.py backend/Nutrition-backend/tests/unit/db/test_models.py backend/ai_agent_chat/tests/test_agent_memory_context.py`
    - `python backend/scripts/eval_chatbot_golden.py`
- 건드리면 안 되는 영역:
  - 공식 음식/영양제/복약 DB 자동 수정
  - raw chat 전문, raw prompt, raw OCR, raw LLM output, provider payload의 prompt/API 노출
  - chat-derived memory를 confirmed app record와 같은 priority로 승격
  - reviewed evidence, `AnswerCard`, boundary/unknown renderer의 source of truth 변경
  - 팀 브랜치 직접 merge 또는 cherry-pick
- 연결된 Future Risk 항목:
  - Conversation session 관리
  - Privacy/deletion
  - Multi-device/concurrency
  - Medical boundary drift
- 완료 조건:
  - LLM prompt/grounding context에 4종 memory summary가 raw-free 형태로 들어간다.
  - confidence/provenance가 사용자 보고 또는 요약 memory로 표시되어 확정 기록과 구분된다.
  - 공식 음식/영양제/복약 DB는 chat 발화만으로 자동 수정되지 않는다.
  - memory context 관련 unit/integration smoke와 golden eval이 통과한다.

### Touchpoint Map: Agent/LLM full vertical integration Day 4

- 목표:
  - Agent가 음식, 영양제, 복약 정보를 사용할 때 `confirmed` 또는 그에 준하는 사용자 확정 기록만 강한 app context로 반영한다.
  - OCR/YOLO/LLM preview, parser candidate, unconfirmed candidate는 Agent confirmed context에서 제외하고 필요하면 warning 또는 lookup 대상 상태로만 남긴다.
  - Day 5 analysis/checklist/CTA 연결 전에 confirmed context의 입력 경계를 테스트로 먼저 고정한다.
- 기준 문서:
  - Agent/LLM 방향과 요구사항: [26](./26-agent-llm-product-direction-reset.md), [28](./28-agent-llm-trd.md), [29](./29-agent-llm-tdd.md), [30](./30-agent-llm-todo.md)
  - 팀 통합 I/O 계약과 readiness: [33](./33-agent-llm-team-integration-contract.md), [34](./34-agent-llm-readiness-audit.md)
  - Day 1~3 실행 gate: [35](./35-agent-llm-orchestration-plan.md)
  - 기존 grounded chatbot 기준: [05](./05-grounded-chatbot-prd.md), [06](./06-grounded-chatbot-tdd.md), [08](./08-grounded-chatbot-trd.md), [10](./10-grounded-chatbot-gap-review.md)
- 건드릴 가능성이 있는 backend 영역:
  - `backend/Nutrition-backend/src/services/user_health_context_snapshot.py`
  - `backend/Nutrition-backend/tests/unit/services/test_user_health_context_snapshot.py`
  - `backend/ai_agent_chat/src/lemon_ai_agent/user_health_context.py`
  - `backend/ai_agent_chat/tests/test_user_health_context.py`
  - 필요 시 `backend/ai_agent_chat/src/lemon_ai_agent/app_intake.py`, `backend/ai_agent_chat/tests/test_app_intake.py`
- 건드릴 가능성이 있는 DB/migration 영역:
  - Day 4 첫 slice에서는 migration을 기본값으로 두지 않는다.
  - 현재 route/service가 받는 `food_record_context`, `active_supplement_context`, `medication_context` payload를 compatibility adapter로 정규화할 수 있는지 먼저 확인한다.
  - 새 DB field가 필요하면 `confirmed`/`user_confirmed`/`active`/`provenance` 같은 상태 필드만 후보로 두고 raw OCR, raw LLM output, provider payload 컬럼은 추가하지 않는다.
- 건드릴 가능성이 있는 mobile/API contract:
  - response DTO는 Day 4에서 바꾸지 않는다.
  - confirmed context가 부족할 때는 기존 `needs_more_info`, `needs_structured_lookup`, warning 성격의 상태로 닫고 Flutter 표시 계약은 Day 6에서 정리한다.
- 기존 grounded chatbot 문서 확인 필요 여부:
  - 필요하다. Day 4는 `AnswerCard`, reviewed evidence, boundary/unknown renderer의 source of truth를 재정의하지 않는다.
  - confirmed context는 personalization/context 입력일 뿐, reviewed source 없는 의료/영양 사실을 새로 생성하는 근거가 아니다.
- 팀 브랜치에서 확인할 후보:
  - `origin/yeong-tech`: 영양제 `user_confirmed`, `requires_confirmation`, deterministic `nutrient_code`, OCR preview 보관 원칙을 확인 후보로만 본다.
  - `origin/feat/backend-supplement-ocr-db-hardening`: 영양제 OCR/DB hardening, supplement snapshot/schema, ingredient evidence ref, parser hardening, RLS 후보를 확인한다. 단, OCR/parser 산출물을 확정 context로 승격하지 않는다.
  - `origin/feat/ocr-quality-gates`, `origin/fix/ocr-*`, `origin/test/ocr-kpi-readiness-gate`: OCR 품질 게이트, raw OCR/UI 노출 차단, expected manifest/matching 보정, provider 진단을 preview/candidate exclusion test의 참고 근거로만 본다.
  - `origin/jongpil-tech`: 식단 `needs_user_review=false`, `user_confirmed` equivalent, `food_code`, `estimated_grams` 후보를 확인 후보로만 본다.
  - `origin/docs/data-yolo-*`, `origin/feat/data-yolo-exp*`, `origin/feat/backend-food-nutrition-demo`: 음식 인식/YOLO/영양소 매핑 실험과 manifest를 확인한다. 인식 결과는 확정 기록이 아니라 food candidate로 취급한다.
  - `origin/sunghoon-food-notfood-classification`: food/not-food gate classifier를 음식 후보 필터로만 본다. confirmed food record 기준을 대체하지 않는다.
  - `origin/sunghoon-database`: profile/medication active status, provenance, medication class 후보를 확인 후보로만 본다.
  - `origin/feat/db-internal-learning-pipeline`: learning/analysis/food/supplement 흐름이 섞인 후보를 확인한다. learning 결과나 analysis 결과를 confirmed health context로 승격하지 않는다.
  - `origin/taedong-design`, `origin/feat/taedong-agent-prototype-preview`, `origin/feat/mobile-dashboard-redesign`: Day 4에서는 참고만 한다. mobile source/CTA/boundary 표시 계약은 Day 6에서 다룬다.
  - `origin/changmin-aiagent`, `origin/feat/ai-agent-local-llm`: Agent/LLM 소비 방식 참고용이다. Day 4 confirmed adapter의 source of truth는 현재 `feat/ai-agent-backend-integration`의 `/api/v1/ai-agent/chat`와 33번 계약이다.
  - 위 브랜치들은 Day 4 첫 slice에서 merge 또는 cherry-pick 대상이 아니다.
- migration 필요 여부:
  - 시작 전 테스트로 확인한다.
  - service-level filtering과 snapshot sanitization으로 preview/candidate exclusion을 고정할 수 있으면 migration 없이 진행한다.
  - migration이 필요해지면 별도 PR slice로 분리하고 사용자에게 먼저 알린다.
- 테스트/smoke 명령:
  - Day 4 RED 후보:
    - `python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_user_health_context_snapshot.py`
    - `python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_user_health_context.py`
  - Day 4 GREEN 후 회귀 후보:
    - `python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_chatbot_agent.py backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py`
    - `python backend/scripts/eval_chatbot_golden.py`
    - `git diff --check`
- 건드리면 안 되는 영역:
  - 팀 브랜치 직접 merge 또는 cherry-pick
  - `guide.html` 직접 수정
  - raw chat 전문, raw prompt, raw OCR, raw LLM output, provider payload를 memory/API/prompt/context에 넣는 구조
  - OCR/YOLO/LLM preview 또는 parser candidate를 confirmed food/supplement/medication context와 같은 priority로 승격하는 구조
  - reviewed source governance, `AnswerCard`, boundary/unknown renderer의 source of truth 변경
  - Gemma 기본 모델 전환, SGLang runtime 기본값 변경
- 연결된 Future Risk 항목:
  - Reviewed evidence 콘텐츠 운영
  - Medical boundary drift
  - Privacy/deletion
  - Team merge risk
  - Mobile contract completeness
- 완료 조건:
  - preview/candidate exclusion test가 먼저 작성된다.
  - confirmed food/supplement/medication context만 Agent input의 강한 근거로 들어간다.
  - raw OCR/LLM/model/provider payload가 safe context, prompt, API response에 들어가지 않는다.
  - 팀 브랜치 후보 필드는 merge 없이 adapter 계약 참고로만 정리된다.

## 8. Future Risk Register

분류:

- `Blocker`: 이 항목이 닫히지 않으면 출시 또는 핵심 통합을 진행하지 않는다.
- `Day-10 Critical`: 10일 full vertical integration에 포함해 닫아야 한다.
- `After Day-10`: 10일 이후 고도화로 넘길 수 있지만 설계 충돌을 막기 위해 추적한다.
- `Watch`: 지금 결정하지 않되 구현 중 다시 확인한다.

| Risk | 분류 | 왜 중요한가 | 연결 Phase | 기준/갱신 문서 |
| --- | --- | --- | --- | --- |
| Streaming 응답 | Day-10 Critical | 10~30초 대기 UX를 줄이고 중간 실패를 설명해야 한다. 최소 loading/fallback UX라도 정해야 한다. | 4, 5 | 31, 33, 35 |
| Conversation session 관리 | Day-10 Critical | turn limit, timeout, compaction trigger, 앱 재시작 복원이 필요하다. | 1, 5 | 29, 30, 35 |
| Rate limiting/cost control | Day-10 Critical | LLM 비용 폭증과 반복 요청 abuse를 막아야 한다. | 3, 5 | 31, 32, 35 |
| Cold start | Day-10 Critical | 신규 사용자에게 분석/추천/질문 흐름을 어떻게 시작할지 정해야 한다. | 1, 4, 5 | 27, 29, 35 |
| Production LLM infra | Blocker | SGLang 운영, Ollama fallback 범위, 모델 lifecycle이 결정되어야 한다. | 3 | 31, 32 |
| Latency budget | Day-10 Critical | first token, total latency, timeout, degradation 기준이 필요하다. | 3, 5 | 31, 32, 35 |
| Error/timeout UX | Day-10 Critical | SGLang/LLM/DB 장애 시 Flutter와 backend 메시지가 일관돼야 한다. | 4, 5 | 33, 35 |
| Reviewed evidence 콘텐츠 운영 | Blocker | 구조만 있고 검수 콘텐츠가 부족하면 unknown으로 닫힌다. | 2, 5 | 30, 33, 34 |
| Privacy/deletion | Blocker | memory 삭제, 탈퇴, retention, raw archive 정책이 필요하다. | 1, 5 | 28, 29, 35 |
| Push notification | Day-10 Critical | checklist/reminder가 Agent action으로 노출되면 최소 등록/해제 계약 또는 명시적 deferred 상태가 필요하다. | 5 | 27, 30, 35 |
| Multi-device/concurrency | Day-10 Critical | message ordering, duplicate action, memory update race를 막아야 한다. | 1, 4, 5 | 29, 33, 35 |
| Mobile contract completeness | Day-10 Critical | CTA, approval, sources, BoundaryPlan card, analysis snapshot이 모두 맞아야 한다. | 4 | 33, 35 |
| Observability | Day-10 Critical | model, latency, answerability, fallback, unknown topic metrics가 필요하다. | 3, 5 | 31, 32, 35 |
| Rollback/fallback | Day-10 Critical | 모델 변경 실패 시 즉시 되돌릴 설정과 smoke 기준이 필요하다. | 3 | 31, 32 |
| Team merge risk | Watch | 팀 브랜치를 바로 병합하면 계약보다 구현 세부가 먼저 들어올 수 있다. | 2, 4, 5 | 33, 34, 35 |
| Secrets/API key hygiene | Blocker | 외부 OCR/LLM/API key가 prompt, log, repo에 섞이면 안 된다. | 3, 5 | 28, 31, 35 |
| Medical boundary drift | Blocker | 모델/renderer 변경 후 진단, 치료, 복용량 판단 문구가 다시 새어 나올 수 있다. | 3, 4, 5 | 26, 29, 30 |

## 9. 운영 규칙

- 새 Agent/LLM 방향, 모델, runtime, 팀 통합 판단은 먼저 26~34번 중 가까운 문서에 반영한다.
- 35번에는 10일 성공 기준, 실행 순서, gate 상태, future risk 연결만 반영한다.
- 세부 PR TODO는 30번을 갱신한다.
- smoke/eval 결과는 32번을 갱신한다.
- current-state readiness가 바뀌면 34번을 갱신한다.
- 코드 구현 전에는 해당 slice의 touchpoint map을 먼저 작성한다.
- 팀 브랜치는 바로 merge하지 않고, 33번 계약과 34번 readiness 기준으로 adapter 흡수 여부를 판단한다.
- 구현이 기존 grounded chatbot 코드나 계약을 건드리면 05~10번, 17~22번을 함께 확인한다.

## 10. Daily Execution TODO

이 TODO는 Day를 넘길 수 있는지 확인하기 위한 체크리스트다. 세부 PR TODO는 30번에서 관리하고,
여기서는 daily gate만 관리한다.

### Day 1. 기준 고정과 touchpoint map

- [x] 26~35번 문서에서 Day 1에 필요한 기준을 다시 확인한다.
- [x] `Touchpoint Map: Agent/LLM full vertical integration Day 1`을 작성한다.
- [x] 10일 성공 기준을 코드/문서/검증 작업으로 나눈다.
- [x] Core Agent, Product Loop, Integration, Runtime, Verification track별 Day 2~3 작업 경계를 정한다.
- [x] 팀 브랜치에서 확인할 후보를 merge 대상이 아니라 adapter 확인 대상으로 분리한다.
- [x] Day 2에서 바로 구현할 첫 코드 slice를 확정한다.
- [x] Day 1 완료 후 35번의 phase 상태를 갱신한다.

Day 1 완료 gate:

- [x] Day 1 touchpoint map이 작성되어 있다.
- [x] Day 2 첫 구현 slice와 테스트 명령이 명확하다.
- [x] 팀 의존 질문과 독립 구현 작업이 분리되어 있다.
- [x] 코드 수정 전에 건드리면 안 되는 영역이 명시되어 있다.

Day 1 실행 기록:

| 항목 | Day 1 판정 |
| --- | --- |
| 10일 성공 기준 분해 | `memory/context/evidence`, `analysis/checklist/CTA`, `DB/mobile contract`, `runtime smoke`, `golden/demo verification` 5개 track으로 유지한다. |
| Day 2 첫 구현 slice | `Agent memory 4종 schema + v0 compatibility adapter`를 첫 코드 slice로 시작한다. |
| Day 2 테스트 시작점 | `test_agent_memory.py`, `test_models.py`, `test_agent_memory_context.py`에 raw/internal exclusion과 v0 read compatibility RED를 먼저 추가한다. |
| Day 2에서 유지할 기존 경로 | v0 `daily_coaching` memory, `/api/v1/ai-agent/chat`, deterministic golden eval, `AnswerCard`/boundary/unknown 경로를 깨지 않는다. |
| 팀 의존 질문 | DB/team branch의 새 table/field, Flutter source/CTA/boundary 표시 세부 UI, SGLang live server 준비는 확인 대상으로 둔다. |
| 독립 구현 작업 | memory type contract, repository/service compatibility, raw prompt/transcript/provider payload 미저장 테스트는 현 worktree에서 바로 진행한다. |
| 사용자 확인 필요 여부 | Day 2 첫 slice를 시작하는 데 필요한 사용자 결정은 없다. 모델 전환, 팀 브랜치 병합, migration 방식이 충돌할 때만 확인한다. |

Day 2~3 track 경계:

| Track | Day 2 | Day 3 |
| --- | --- | --- |
| Core Agent | memory 4종 type contract와 v0 `agent_memory` read compatibility | memory bundle을 chat context 선택 규칙에 연결 |
| Product Loop | today/smart analysis는 수정하지 않고 memory 영향 후보만 기록 | conversation/behavior memory가 checklist/analysis로 들어가는 조건 정의 |
| Integration | migration 필요 여부와 existing `agent_memory` table compatibility 확인 | 공식 DB record와 chat-derived memory의 priority 분리 |
| Runtime | live model 변경 없음. deterministic fallback/golden을 회귀 기준으로 유지 | structured output/live smoke 준비만 병렬 추적 |
| Verification | raw/internal exclusion RED, model/service unit RED 작성 | chat route memory context smoke와 golden eval 회귀 |

### Day 2. Agent memory 최소 schema 시작

- [x] memory 4종 schema 구현 위치와 migration 필요 여부를 확인한다.
- [x] 기존 v0 `agent_memory` read compatibility를 유지한다.
- [x] raw transcript, raw prompt, raw provider payload 미저장 테스트를 먼저 고정한다.
- [x] memory repository 또는 service 최소 path를 구현한다.

Day 2 완료 gate:

- [x] memory 저장/조회 unit path가 있다.
- [x] raw/internal payload exclusion test가 있다.
- [x] 기존 chatbot/daily coaching path가 깨지지 않는다.

Day 2 실행 기록:

| 항목 | Day 2 판정 |
| --- | --- |
| 구현 위치 | 기존 `agent_memory` table을 유지하고 `backend/Nutrition-backend/src/services/agent_memory.py`의 service-level contract로 4종 memory를 추가했다. |
| migration 필요 여부 | 현재 Day 2 범위에서는 불필요하다. `memory_type`, `summary_json`, `source_counters` 기존 컬럼으로 v0 compatibility와 v2 memory taxonomy를 모두 표현할 수 있다. |
| memory type contract | `profile_memory`, `behavior_memory`, `conversation_memory`, `safety_memory`를 `AGENT_MEMORY_TYPES`로 고정했다. |
| 저장 path | `upsert_agent_memory_record()`가 compact summary, structured payload, confidence, source kind/ref, priority, review/expiry metadata를 sanitized `summary_json`으로 저장한다. |
| 조회 path | `load_agent_memory_context()`가 기존 `summaries`를 유지하면서 `memory_bundle`에 4종 memory를 type별로 묶어 반환한다. |
| v0 compatibility | 기존 `daily_coaching`, `confirmed_supplement`, `nutrition_analysis` memory type은 `summaries`에 그대로 남기고 4종 `memory_bundle`에는 섞지 않는다. |
| raw/internal exclusion | raw transcript, raw prompt, raw provider payload, raw OCR, raw LLM response, messages/provider payload key를 memory 저장/조회 결과에서 제거한다. |
| 기존 경로 회귀 | daily coaching memory service, DB model contract, app intake memory context, ai-agent API integration, deterministic golden eval을 회귀 검증 대상으로 확인했다. |

### Day 3. Memory retrieval과 chat context 연결

- [x] `profile`, `behavior`, `conversation`, `safety` memory retrieval을 chat context에 연결한다.
- [x] confidence/provenance가 답변 표현에 낮은 강도로 반영되는지 확인한다.
- [x] chat-derived memory와 confirmed app record가 섞이지 않게 한다.
- [x] 기존 grounded chatbot 흐름과 충돌하는지 05~10, 17~22 기준으로 확인한다.

Day 3 완료 gate:

- [x] Agent chat에서 memory context가 사용된다.
- [x] 공식 음식/영양제/복약 DB가 chat 발화만으로 자동 수정되지 않는다.
- [x] memory context 관련 smoke가 통과한다.

Day 3 실행 기록:

| 항목 | Day 3 판정 |
| --- | --- |
| 구현 위치 | `ChatbotAgent`가 `agent_memory.memory_bundle`을 `User-reported memory context` prompt section과 safety grounding context에 raw-free 요약으로 연결한다. |
| memory 표현 강도 | `confidence`, `source_kind`를 함께 표시하고 `confirmed app record가 아닌 낮은 강도 참고 정보` 문구로 공식 DB record와 구분한다. |
| raw/internal exclusion | `summary_json`, `raw_prompt`, `provider_payload`, `messages` 같은 internal key와 hidden payload는 prompt에 노출하지 않는다. |
| API contract 영향 | `/api/v1/ai-agent/chat` response DTO는 변경하지 않고 `agent_memory` used tool과 internal prompt safety만 보강했다. |
| DB/migration 영향 | 없다. Day 2의 기존 `agent_memory` service-level bundle 계약을 소비한다. |
| 회귀 기준 | `test_chatbot_agent.py`, `test_ai_agent_api.py`, Day 2 memory unit tests, deterministic golden eval을 회귀 검증 대상으로 확인한다. |

### Day 4. Confirmed context adapter

- [x] 전체 `origin/*` 브랜치 영향 범위를 confirmed/preview/candidate 관점으로 다시 확인한다.
- [x] 음식/영양제/복약 confirmed record 기준을 adapter로 고정한다.
- [x] OCR/YOLO/LLM preview와 후보 데이터는 확정 context에서 제외한다.
- [x] 팀 브랜치의 후보 필드는 33/34 기준으로 확인만 하고 바로 merge하지 않는다.
- [x] 부족한 필드는 fixture 또는 compatibility layer로 Day 10 demo path를 확보한다.

Day 4 완료 gate:

- [x] preview/candidate exclusion test가 있다.
- [x] confirmed food/supplement/medication context가 Agent input에 들어간다.
- [x] raw OCR/LLM/model output이 context에 들어가지 않는다.

Day 4 실행 기록:

| 항목 | Day 4 판정 |
| --- | --- |
| 구현 위치 | `build_user_health_context_snapshot()`가 food/supplement/medication context를 confirmed/active 기준으로 다시 정규화한다. |
| food context | `food_record_context`, existing snapshot, `latest_confirmed_entries` 모두 `user_confirmed=false`, `needs_user_review=true`, `preview/candidate/requires_confirmation` 상태를 제외한다. |
| supplement context | active supplement snapshot은 confirmed supplement만 남기고, `nutrient_code`가 있는 ingredient는 `standard_nutrient`, 없는 ingredient는 `label_only`로 표시한다. |
| medication context | profile medication은 server-owned `medication_context`의 active/user-confirmed detail만 강한 context로 반영한다. |
| legacy compatibility | `/api/v1/ai-agent/chat`가 legacy `latest_confirmed_entries`를 sanitized snapshot에서 다시 만들어 client preview 우회 경로를 닫는다. |
| raw/internal exclusion | `provider_payload`, `raw_provider_payload`, `raw_model_output`, `model_output`, `llm_output` key를 safe context에서 제거한다. |
| API/DB 영향 | response DTO와 migration 변경은 없다. |
| 회귀 기준 | `test_user_health_context_snapshot.py`, `test_user_health_context.py`, `test_chatbot_agent.py`, `test_ai_agent_api.py`, deterministic golden eval을 회귀 검증 대상으로 확인한다. |

### Day 5. Analysis snapshot, checklist, CTA

- [x] today analysis snapshot v1을 response contract에 연결한다.
- [x] smart analysis snapshot v1을 response contract에 연결한다.
- [x] checklist 후보 1~3개와 확장 후보 구조를 만든다.
- [x] CTA와 approval preview를 side effect 없이 반환한다.

Day 5 완료 gate:

- [x] response payload에 analysis/checklist/CTA가 포함된다.
- [x] 저장/알림/분석 실행은 사용자 승인 전에는 실행되지 않는다.
- [x] 금지 문구와 medical boundary wording test가 통과한다.

Day 5 실행 기록:

| 항목 | Day 5 판정 |
| --- | --- |
| 구현 위치 | `build_analysis_response_contract()`가 `today_analysis`, `smart_analysis`, `analysis_snapshot`, `checklist_candidates`, `ctas`, `approval_preview`를 하나의 preview-only 계약으로 만든다. |
| API contract | `/api/v1/ai-agent/chat` response DTO에 additive field로 `analysis_snapshot`, `today_analysis`, `smart_analysis`, `checklist_candidates`, `approval_preview`를 추가했다. |
| today analysis | `build_today_analysis_snapshot()`의 `today-analysis-snapshot-v1`을 그대로 사용하고, 최소 기록/누락 기록/score 상태/CTA를 response에 포함한다. |
| smart analysis | `build_health_analysis_snapshot()`의 `health-analysis-snapshot-v1`을 `smart_analysis`로 내려 분석 탭과 챗봇이 같은 장기/성숙도 snapshot을 읽을 수 있게 했다. |
| checklist 후보 | `checklist_candidates`는 최대 3개, `kind=today_practice`, `approval_state=approval_required`, `side_effect=none`, `deferred_action=add_today_practice` 구조로 반환한다. 저장된 오늘 실천이 아니다. |
| CTA/approval | `ctas`는 `run_or_refresh_analysis`, `ask_about_this_result`, `complete_missing_record` 계열만 bounded preview로 내려가며, `approval_preview`는 `will_persist=false`, `will_schedule_notification=false`, `will_add_today_practice=false`, `side_effects=[]`를 명시한다. |
| side effect boundary | 승인 전 일반 chat response와 analysis run confirmation response는 분석 저장, 알림 등록, 오늘 실천 추가를 실행하지 않는다. 승인된 analysis run persistence는 기존 명시 승인 경로만 유지한다. |
| raw/internal exclusion | preview/candidate food, raw OCR, raw/model/provider payload, internal prompt/context는 response contract test에서 비노출을 고정했다. |
| Day 6 이후 항목 | Flutter 표시/버튼 동작, source detail sheet, 실제 오늘 실천 저장 API, endpoint mismatch 정리는 Day 6 이후 mobile response contract로 남긴다. |
| 회귀 기준 | `test_app_health_analysis.py`, `test_ai_agent_api.py`, `test_user_health_context_snapshot.py`, `test_user_health_context.py`, `test_chatbot_agent.py`, deterministic golden eval을 회귀 검증 대상으로 확인한다. |

### Day 6. Mobile response contract

- [x] Flutter가 받을 `answerability`, `sources[]`, `ctas[]`, approval preview, boundary/unknown 상태를 맞춘다.
- [x] canonical endpoint를 `/api/v1/ai-agent/chat`로 유지하고 `/api/v1/agents/chat` alias를 만들지 않는다.
- [x] source detail, boundary card, unknown card, loading/error UX 최소 계약을 맞춘다.
- [x] raw/internal field가 mobile response에 노출되지 않게 한다.

Day 6 완료 gate:

- [x] backend/mobile DTO compatibility smoke가 통과한다.
- [x] Flutter에서 answer, source, CTA, boundary/unknown 상태를 표시할 수 있다.
- [x] timeout/error/fallback 메시지가 최소 계약에 포함된다.

### Day 7. Qwen baseline runtime smoke

- [x] SGLang Qwen 실행 조건을 확인한다.
- [x] SGLang이 막히면 Ollama fallback demo path를 확보한다.
- [x] SGLang Qwen baseline blocker와 Ollama fallback smoke를 32번에 기록한다.
- [x] latency, answerability, source use, boundary 결과를 기록한다.

Day 7 완료 gate:

- [x] Qwen 또는 fallback 경로로 end-to-end answer가 나온다.
- [x] 실패 원인과 fallback 조건이 32번 또는 35번에 남아 있다.
- [x] Gemma smoke 준비 조건이 명확하다.

Day 7 결과:

- 2026-06-06 초기 확인에서는 Docker Desktop Linux engine, SGLang port `127.0.0.1:30000`, PostgreSQL smoke port `127.0.0.1:55432` 전제가 미충족되어 SGLang Qwen live smoke가 blocked였다.
- Docker Desktop 시작, 기존 `lemon-sglang` 컨테이너 재시작, conda PostgreSQL `55432` 복구 후 SGLang Qwen baseline live smoke가 통과했다.
- `/v1/models`는 `Qwen/Qwen2.5-0.5B-Instruct`를 반환했고, FastAPI + PostgreSQL + SGLang smoke는 `first_provider=sglang`, `second_provider=sglang`, `chat_provider=sglang`, unknown backlog delta `+1`로 통과했다.
- 지속 FastAPI dev server도 `http://127.0.0.1:18080`에서 health OK이며, `--use-existing-server` smoke가 provider `sglang`로 통과했다.
- Ollama `qwen3.5:9b`는 설치되어 있고 raw chat 및 parser smoke는 fallback 경로로 통과했다.
- guarded Ollama chatbot path에서는 LLM 응답이 빈 응답으로 정규화되어 deterministic renderer로 안전 fallback됐다.
- P0 자몽/고지혈증 약 boundary는 fallback 경로에서도 `medical_decision_boundary`와 source/warning 계약을 유지했다.
- Day 8 Gemma 비교는 Qwen baseline 통과 상태에서 시작했고, Ollama `gemma4:e2b` smoke까지 실행했다. SGLang Gemma는 cache/license/download/VRAM 전략이 아직 준비되지 않았다.

### Day 8. Gemma 후보 smoke와 모델 비교

- [x] Gemma 후보 모델 실행 조건을 확인한다.
- [x] Ollama `gemma4:e2b` chatbot smoke를 실행하고 32번에 기록한다.
- [x] Qwen baseline, Ollama Gemma, Ollama fallback 결과를 비교한다.
- [x] 기본 모델 변경 여부는 live smoke 결과 없이 결정하지 않는다.
- [x] SGLang Gemma live smoke blocker를 32번에 기록한다.

Day 8 완료 gate:

- [x] Qwen/Ollama Gemma/fallback 비교 결과가 있다.
- [x] 모델별 실패/timeout/JSON parse/source/fallback/반복 차이가 기록되어 있다.
- [x] Day 10 demo runtime path가 확정되어 있다.

Day 8 실행 결과:

- Qwen baseline: 통과. SGLang `/v1/models`, chatbot smoke, FastAPI 조합 smoke, SGLang pytest smoke가 모두 통과했다.
- Ollama Gemma: `gemma4:e2b` 7.2GB 설치 후 sodium guarded/raw, P0 boundary smoke를 실행했다. raw 답변은 가능했지만 guarded sodium path는 `LLM response text was empty`로 deterministic fallback됐다.
- SGLang Gemma: 현재 `/v1/models`는 Qwen만 반환하고, SGLang container HF cache도 Qwen뿐이다. 후보 tag는 기존 `google/gemma-3n-E2B`와 SGLang Gemma 4 cookbook의 `google/gemma-4-E2B-it`로 좁힌다.
- SGLang Gemma blocker: HF usage license/token, 모델 다운로드/cache, 현재 8GB GPU에서 Qwen과 동시 상주 불가, Gemma 전용 SGLang image/runtime 호환 확인이 남아 있다.
- JSON parse: configured Ollama parser smoke는 통과했지만, SGLang/Gemma structured JSON live validation은 32번의 별도 gate로 남긴다.
- Day 10 runtime 후보: `SGLang Qwen primary + deterministic safety fallback + Ollama dev fallback`으로 둔다. Ollama Gemma는 실험 후보이며 primary runtime으로 올리지 않는다.

### Day 9. Golden scenarios와 failure UX

- [x] 대표 golden scenarios를 deterministic + LLM smoke로 실행한다.
- [x] 응급, unknown, 병용, 음식 조정, memory 반영, checklist/CTA 흐름을 확인한다.
- [x] error/timeout/fallback UX를 Flutter/backend 계약에 맞춘다.
- [x] observability 최소 항목을 기록한다.

Day 9 완료 gate:

- [x] representative scenarios가 통과한다.
- [x] 실패 케이스가 unknown/boundary/fallback으로 안전하게 닫힌다.
- [x] demo script가 고정되어 있다.

Day 9 실행 결과:

- deterministic golden eval: `python backend\scripts\eval_chatbot_golden.py`가 20개 case pass를 반환했다. 포함 범위는 sodium dinner, magnesium caution, urgent escalation, kidney/diabetes/vitamin D, unknown iron, P0 grapefruit, lithium/selenium boundary, label-only supplement unknown, structured lookup, today/health analysis snapshot, stale visible analysis context다.
- SGLang Qwen live smoke: sodium dinner는 `provider=sglang`, `answerability=answerable`, source `kdris-2025`로 응답했다. magnesium caution도 `provider=sglang`, `answerability=answerable_with_caution`, source `nih-ods-magnesium`으로 응답했다.
- no-LLM boundary: grapefruit/statin, lithium/selenium, urgent chest pain은 `provider=deterministic`으로 닫혔고 각각 `mfds-drug-safety`, `medlineplus-lithium`, `cdc-public-health` source와 boundary warning을 유지했다.
- unknown: 철분 음식 질문은 `unknown_no_reviewed_source`, `sources=[]`, `no_reviewed_answer_card` warning으로 닫혔다.
- analysis/checklist/CTA: app health analysis unit tests와 chat route integration tests가 analysis snapshot, checklist candidates, CTA, approval preview side-effect boundary를 통과했다.
- error/fallback: SGLang down endpoint `127.0.0.1:39999`와 timeout `0.001` smoke 모두 deterministic fallback으로 닫혔고 `LLM generation failed: RuntimeError` warning을 남겼다.
- existing-server smoke: `smoke_ai_agent_server.py --use-existing-server`가 `chat_provider=sglang`, `chat_answerability=answerable`, `chat_source_count=2`, `unknown_backlog_delta=1`로 통과했다.

Day 9 observability 최소 항목:

| 항목 | Day 10 demo에서 볼 값 |
| --- | --- |
| provider | `sglang` 또는 `deterministic` |
| model | SGLang primary는 `Qwen/Qwen2.5-0.5B-Instruct` |
| latency | CLI/runner wall time 기준으로 기록. first-token latency는 Day 10 이후 structured runtime telemetry로 분리 |
| answerability | `answerable`, `answerable_with_caution`, `unknown_no_reviewed_source`, `medical_decision_boundary`, `urgent_escalation`, `needs_more_info` |
| fallback 여부 | `provider=deterministic` plus `safety_warnings` 또는 boundary code |
| sources | reviewed source metadata. unknown은 `sources=[]` |
| safety_warnings | LLM failure, empty response, no reviewed card, emergency/P0 boundary code |
| unknown topic | server smoke에서 unknown backlog delta로 확인. raw user text는 summary payload에 넣지 않는다 |

### Day 10. Full vertical integration demo hardening

#### Day 10 실제 화면 smoke 결과

2026-06-06 기준 Day 10의 Flutter -> backend -> Agent/LLM -> response display 흐름은
실제 Flutter web 화면과 backend API smoke로 확인했다.

| 항목 | 결과 |
| --- | --- |
| backend runtime | FastAPI `http://127.0.0.1:18080`, PostgreSQL `127.0.0.1:55432`, SGLang `http://127.0.0.1:30000/v1` Qwen model 응답 확인 |
| backend smoke | `smoke_ai_agent_server.py --use-existing-server ...` pass, `chat_provider=sglang`, `chat_answerability=answerable`, `chat_source_count=2`, unknown backlog delta `+1` |
| Flutter config | web 기본 API base URL `http://localhost:18080`, repository endpoint `/api/v1/ai-agent/chat`; `/api/v1/agents/chat` alias 없음 |
| Flutter screen smoke | release web build를 `localhost:52111`에서 실행하고 Chrome local smoke로 consent 4회 + chat 4회, 총 8개 backend 응답 확인 |
| sodium dinner | 화면에 사용자 질문과 agent 답변 표시. payload는 `answerability=answerable`, sources `kdca-healthinfo`, `kdris-2025`, analysis/CTA/approval preview 포함 |
| grapefruit/lipid medication | 화면에 boundary 설명 표시. payload는 `answerability=medical_decision_boundary`, source `mfds-drug-safety`, CTA/approval preview 포함 |
| unknown-style question | 현재 문장 "검수된 근거가 없는 새로운 민간요법"은 drug-safety boundary로 닫혔다. 순수 unknown 질문 문구는 별도 fixture로 고정 필요 |
| today analysis/checklist/CTA | 화면에 분석 실행 전 확인 안내 표시. payload는 `answerability=needs_more_info`, CTA `run_or_refresh_analysis`, `ask_about_this_result`, approval preview 포함 |

Day 10 남은 gap:

- Flutter web 정적 서버 origin `http://localhost:52111`에서 backend `http://localhost:18080` 호출은 기본 Chrome 보안 설정에서 CORS preflight가 막힌다. 로컬 smoke는 Chrome web security를 끄고 실제 HTTP 호출을 확인했다. 통합 전 backend CORS allowlist 또는 same-origin dev proxy가 필요하다.
- Flutter 화면은 응답 후 대화 하단으로 자동 스크롤되어 source/analysis/approval preview 패널 확인성이 낮다. payload와 DTO/UI code path는 존재하지만 demo UX에서는 panel anchor 또는 summary placement 보강이 필요하다.
- unknown no reviewed source 시나리오는 질문 문구가 drug-safety boundary로 분류될 수 있다. Day10 이후 golden/demo 문구를 `unknown_no_reviewed_source`로 안정 고정해야 한다.

- [x] Flutter -> backend -> Agent/LLM -> response display 전체 흐름을 확인한다.
- [x] memory, confirmed context, reviewed evidence, analysis, checklist, CTA, source, boundary가 Flutter display까지 함께 돈다.
- [x] Qwen/Gemma/fallback 중 Day 10 demo runtime path를 고정한다.
- [x] 남은 gap은 35번 Future Risk Register 또는 30번 TODO로 되돌린다.

Day 10 완료 gate:

- [x] full vertical integration demo가 통과한다.
- [x] golden/smoke 결과가 기록되어 있다.
- [x] Day 10 이후 고도화 항목과 Blocker가 분리되어 있다.
- [x] 팀 통합 PR 또는 다음 작업 slice가 명확하다.

#### PR #4 팀 중간 검토 gate

PR #4는 최종 Agent/LLM 품질 PR이 아니라 팀 통합 전 중간 검토용 vertical slice다.
리뷰어는 답변 말투의 완성도보다 아래 계약이 실제 앱/백엔드 경로에서 유지되는지 먼저 본다.

| 검토 항목 | 확인 기준 |
| --- | --- |
| endpoint | Flutter chat repository가 `POST /api/v1/ai-agent/chat`를 호출하고 `/api/v1/agents/chat` alias가 필요하지 않다. |
| response DTO | `sources[]`, `answerability`, `ctas[]`, `approval_preview`, `today_analysis`, `smart_analysis`, `checklist_candidates`를 Flutter가 손실 없이 파싱한다. |
| 화면 흐름 | 질문 입력 후 backend consent/chat 호출이 발생하고 assistant answer가 화면에 표시된다. |
| safety boundary | P0 복약/영양제 상호작용은 LLM 판단으로 허용/금지하지 않고 deterministic boundary로 닫힌다. |
| unknown | reviewed source가 없는 질문은 `unknown_no_reviewed_source`, `sources=[]` 경로로 닫힐 수 있어야 한다. |
| runtime | Day 10 demo는 `SGLang Qwen primary + deterministic safety fallback + Ollama dev fallback`를 유지한다. |
| team data contract | 팀원 DB/식단/영양제/복약 작업은 confirmed record와 preview/candidate record를 구분해야 한다. Agent는 confirmed record만 강한 context로 소비한다. |
| dev environment | Flutter web과 backend를 함께 볼 때 CORS allowlist 또는 same-origin dev proxy가 필요하다. |

팀원이 최소로 끝냈는지 볼 계약:

- food: 사용자 확인이 끝난 음식 기록만 Agent context에 들어간다. OCR/YOLO/LLM preview는 confirmed food처럼 쓰지 않는다.
- supplement: active/confirmed supplement와 `nutrient_code`가 있는 성분은 강한 context로 쓰고, label-only 성분은 reviewed evidence 없이는 unknown/boundary로 닫는다.
- medication: active medication name/class/provenance가 분리되어 있어야 하며, 복약/영양제 병용 판단은 boundary renderer가 처리한다.
- mobile: source, CTA, approval preview, analysis snapshot, boundary/unknown 상태를 같은 응답에서 표시할 수 있어야 한다.
- privacy: raw prompt, raw transcript, raw OCR, raw provider payload는 memory/API/user-facing response에 노출하지 않는다.

## 11. 다음 실행 기준

현재 기준의 다음 실행 후보는 PR #4 팀 중간 검토 안정화 이후의 Day10 follow-up PR이다.

Day 10에서 실제 Flutter 화면과 API smoke로 vertical slice는 확인했다. 다음 구현은 모델 프롬프트/답변 품질을
바로 키우기보다, 팀원이 앱에서 같은 흐름을 안정적으로 볼 수 있게 하는 통합 gap을 먼저 닫는다.

권장 순서:

1. CORS allowlist 또는 same-origin dev proxy를 정리해 기본 Chrome 보안 설정에서도 Flutter web -> backend consent/chat이 통과하게 한다.
2. source/analysis/approval preview 패널이 응답 직후 화면에서 확인 가능하도록 panel anchor, sticky summary, 또는 scroll placement를 조정한다.
3. pure `unknown_no_reviewed_source` demo 문구를 golden fixture와 Flutter smoke fixture에 고정한다.
4. 팀원 DB/식단/영양제/복약 작업이 confirmed record 계약을 만족하는지 확인한다.
5. 그 다음 답변 품질 작업을 `renderer/golden 개선` PR로 분리한다. 이 단계에서 `AnswerCard`는 reviewed evidence를 담는 내부 프레임으로 유지하고, 사용자-facing `answerable`/`answerable_with_caution` 답변은 고정 카드 섹션이 아니라 자연스러운 대화형 문장 안에 요약, 주의점, 오늘 할 행동, 출처 기준이 드러나게 한다. `unknown_no_reviewed_source`, `medical_decision_boundary`, `urgent_escalation`의 fail-closed/deterministic 안전 계약은 완화하지 않는다.
