# 34. Agent/LLM Readiness Audit

작성일: 2026-06-04

이 문서는 31~33번 문서의 기준을 현재 `lemon_aid` workspace와 팀 원격 브랜치 상태에 대입해,
Agent/LLM 작업을 바로 시작할 수 있는지 좁게 검증한 결과다.

범위는 current-state audit이다. 팀 브랜치를 병합하지 않고, 원격 브랜치의 계약 흔적과 현재
`feat/ai-agent-backend-integration` 구현만 확인했다.

## 결론

지금은 **무조건 GitHub를 pull/merge해서 합치는 단계가 아니다.**

바로 시작 가능한 작업은 있다. 다만 시작 단위는 "모델 교체"나 "전체 팀 통합"이 아니라,
Agent가 다른 팀 결과물을 믿고 사용할 수 있게 만드는 **계약 고정 + adapter + 검증 게이트**여야 한다.

추천 순서:

1. 현재 31~34번 문서를 먼저 보호한다.
2. SGLang Qwen live smoke와 Day9 golden/fallback gate는 통과 상태로 유지하고, Gemma는 별도 runtime gate로 남긴다.
3. Agent memory 4종 schema와 current `agent_memory` 호환 adapter를 첫 구현 slice로 잡는다.
4. 영양제/식단/모바일/DB 팀 결과물은 바로 merge하지 말고, 확정 기록 adapter 계약에 맞춰 가져온다.

## 확인한 원격 기준

| 브랜치 | 확인한 역할 | 현재 판단 |
| --- | --- | --- |
| `origin/feat/ai-agent-backend-integration` | 현재 Agent/LLM backend 기준 | 핵심 route, deterministic fallback, reviewed evidence fail-closed, v0 memory 존재 |
| `origin/sunghoon-database` | DB/profile/reminder/agent_memory 방향 | schema guide 성격이 강함. 그대로 병합보다 필요한 table/field 계약만 추출해야 함 |
| `origin/taedong-design` | Flutter UX/chat 흐름 | streaming/rate/error 이벤트 아이디어는 유용하나 backend endpoint/DTO와 불일치 존재 |
| `origin/yeong-tech` | 영양제 OCR/confirmed record/KDRI | `requires_confirmation`, `user_confirmed`, raw 미저장, deterministic `nutrient_code` 원칙이 강함 |
| `origin/jongpil-tech` | 식단 인식/food DTO | `RecognizedMealItem` 등 인식 DTO는 유용하나 최종 확정 기록 adapter 확인 필요 |

## Gate별 상태

### 31 Runtime Decision Gate

상태: **부분 준비**

- 방향성: `SGLang + Ollama fallback`은 유지 가능하다.
- baseline/candidate: Qwen baseline, Gemma candidate 정책은 문서화됐다. Day10 runtime path는 `SGLang Qwen primary + deterministic safety fallback + Ollama dev fallback`이다.
- 현재 로컬 확인: SGLang port `127.0.0.1:30000`, Ollama port `127.0.0.1:11434`, PostgreSQL port `127.0.0.1:55432`, existing FastAPI server `127.0.0.1:18080`는 응답한다. host Python의 `sglang`/`torch` package는 여전히 없지만 SGLang은 Docker container에서 서빙된다.
- 판단: 기본 모델을 Gemma로 바꾸는 결정은 아직 이르다. Qwen baseline과 Day9 golden/fallback gate를 유지하고, Gemma는 license/cache/VRAM/live smoke가 준비된 뒤 별도 후보로만 본다.

필요한 다음 작업:

- Day10 Flutter -> backend -> Agent/LLM -> response display demo.
- SGLang Gemma 모델 live smoke는 Day10 이후 별도 runtime gate.
- first-token/structured JSON telemetry는 Day10 이후 runtime observability 고도화로 분리.

### 32 Eval + Live Smoke Gate

상태: **부분 통과**

- deterministic golden eval은 통과했다.
- deterministic chatbot smoke도 fallback 경로가 의미 있게 동작한다.
- existing-server PostgreSQL + SGLang smoke는 통과했다. 다만 `TEST_DATABASE_URL` 기반 migration smoke는 아직 별도 env 준비가 필요하다.
- 따라서 "문서/로컬 deterministic core와 Qwen runtime baseline은 안정"이지만 "runtime 모델 교체 준비 완료"는 아니다.

필요한 다음 작업:

- `check_ai_agent_runtime_prereqs.py`에서 PostgreSQL migration smoke env gate를 별도로 통과시킨다.
- `eval_chatbot_golden.py`는 모델 후보별 live mode 결과를 별도 산출물로 남긴다.
- live smoke 실패 시 Ollama fallback이 어떤 조건에서만 허용되는지 문서와 설정에 고정한다.

### 33 Team Integration Contract Gate

상태: **계약은 시작 가능, 전체 구현은 미완**

현재 구현/팀 브랜치에서 확인된 준비 요소:

- Chat API, SafetyGuard, AnswerCard, UnknownRenderer, BoundaryRenderer 방향은 이미 존재한다.
- DB-backed reviewed evidence table과 unknown backlog 구조가 있다.
- 영양제 쪽은 `requires_confirmation` preview와 `user_confirmed=true` 승격 원칙이 Agent 계약과 잘 맞는다.
- 식단 쪽은 인식 DTO와 `food_code`, `estimated_grams`, `needs_user_review` 같은 adapter 후보 필드가 있다.
- Flutter 쪽은 chat UX, error/rate/streaming 이벤트 요구가 있으나 현재 backend DTO와 endpoint 정렬이 필요하다.

미완 또는 위험 요소:

- Agent memory 4종은 제품 문서 기준으로는 필요하지만, 현재 구현은 v0 `agent_memory` summary 중심이다.
- 서버 주도 conversation session, turn limit, timeout, token/cost tracking은 아직 제품 gate 수준이 아니다.
- Streaming은 현재 핵심 LLM adapter에서 `stream=false` 경로다.
- rate limiting은 일부 script/에러 시나리오 흔적은 있으나 Agent chat runtime gate로 고정됐다고 보기 어렵다.
- reviewed evidence는 구조가 있으나 source별 readiness가 완전하지 않다.
- mobile contract는 `CTA`, `sources[]`, approval, boundary card, analysis snapshot을 명시적으로 맞춰야 한다.

## 시작 가능한 구현 Slice

### Slice A: Agent Memory 4종 Schema + Compatibility Adapter

상태: **지금 시작 가능**

이유:

- 다른 팀 merge를 기다리지 않아도 된다.
- 현재 v0 `agent_memory`를 깨지 않고 확장할 수 있다.
- 26~30번 문서의 Agent 정의를 실제 runtime context로 연결하는 첫 관문이다.

최소 산출물:

- `profile`, `behavior`, `conversation`, `safety` memory type schema.
- 기존 `daily_coaching` summary와의 read compatibility.
- raw transcript/prompt 미저장 테스트.
- chat-derived memory는 `user_reported` provenance로만 저장하고 공식 음식/영양제/복약 DB를 수정하지 않는 테스트.

### Slice B: Confirmed Record Adapter Audit

상태: **지금 시작 가능**

목표:

- Agent가 음식/영양제/복약 정보를 어떤 조건에서 "확정 기록"으로 볼지 고정한다.
- OCR/YOLO/LLM preview를 확정 데이터처럼 쓰는 실수를 막는다.

최소 산출물:

- 영양제: `user_confirmed=true`, deterministic `nutrient_code`, raw OCR/LLM 미저장 기준 확인.
- 식단: `needs_user_review=false` 또는 user confirmation equivalent 기준 확인.
- 복약: medication class/active status/provenance 기준 확인.
- `ContextResolver`가 preview/candidate 데이터를 제외하는 테스트.

### Slice C: Runtime Live Smoke Harness

상태: **환경 준비 후 시작**

목표:

- Qwen baseline과 Gemma candidate를 같은 SGLang 조건에서 비교한다.
- 모델 변경은 이 결과 이후에만 허용한다.

최소 산출물:

- SGLang Qwen live smoke 결과.
- SGLang Gemma live smoke 결과.
- Ollama fallback smoke 결과.
- first-token/total latency, answerability, boundary, JSON parse success 비교.

### Slice D: Mobile Agent I/O Contract

상태: **계약 문서 기준으로 시작 가능, 구현은 UI팀 branch와 맞춤 필요**

목표:

- 현재 backend `/api/v1/ai-agent/chat`와 mobile이 기대하는 chat UI/event 계약을 맞춘다.

최소 산출물:

- `sources[]` detail rendering contract.
- `CTA`와 `requires_user_approval` interaction contract.
- `BoundaryPlan` card severity mapping.
- streaming 도입 전 fallback UX와 timeout/error message는 Day9에서 최소 고정했다. Flutter display에서 실제 문구/상태 표시를 확인해야 한다.
- endpoint 기준은 `/api/v1/ai-agent/chat` canonical로 고정한다. `/api/v1/agents/chat` alias는 만들지 않는다.

## Go / No-Go

Go:

- 31~34 문서 보호.
- Agent memory schema/adapter 작업.
- confirmed record adapter audit.
- mobile response DTO 계약 정리.
- SGLang Qwen live smoke와 Day9 golden/fallback gate 유지. SGLang Gemma는 Day10 이후 별도 실험.

No-Go:

- Gemma를 기본 모델로 즉시 변경.
- 팀 브랜치를 현재 dirty worktree에 바로 merge.
- streaming을 제품 준비 완료로 간주.
- reviewed evidence 콘텐츠가 충분하다고 간주.
- preview/OCR/YOLO 후보를 Agent의 확정 건강 context로 사용.

## 다음 액션

가장 현실적인 첫 PR은 **Agent memory 4종 schema + v0 compatibility adapter**다.

그 다음 PR에서 confirmed record adapter audit을 붙이면, 음식/영양제/복약 팀 결과물을 가져올 때
"어떤 데이터는 Agent context에 넣고 어떤 데이터는 제외할지"가 명확해진다.

SGLang Qwen live smoke와 Day9 golden/fallback gate는 Day10 demo 기준으로 유지한다. Gemma live smoke와 모델
기본값 변경은 Day10 이후 별도 실험으로 보류한다.
