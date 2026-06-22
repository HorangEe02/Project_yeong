# 10. 근거 기반 챗봇 문서-코드 갭 리뷰

> 작성일: 2026-05-29
> 기준 worktree: `ai-agent-backend-integration`
> 기준 브랜치: `feat/ai-agent-backend-integration`

## 1. 검토 목적

이번 문서는 Lemon Aid LLM/agent 챗봇 작업이 지금까지 작성한 문서와 실제 코드 기준에서
올바른 방향으로 가고 있는지 확인하고, 다음에 추가하거나 수정해야 할 항목을 정리하기 위한
점검 문서다.

검토 기준은 다음이다.

- workspace 규칙: `AGENTS.md`, `agent-rules/project.md`, `agent-rules/safety.md`,
  `agent-rules/verification.md`
- LLM-WIKI 참고 자료: `start/llm-wiki.md`, `wiki/index.md`, `structured-output`,
  `rag-vs-refrag`, 약물-영양제 상호작용, 만성질환 알고리즘, 정신건강 P0 문서
- Lemon Aid 설계 문서: `03-ai-agent-safety-porting-contract.md`,
  `04-medical-source-db-contract.md`, `05-grounded-chatbot-prd.md`,
  `06-grounded-chatbot-tdd.md`, `07-grounded-chatbot-todo.md`,
  `08-grounded-chatbot-trd.md`, `09-grounded-chatbot-implementation-log.md`
- 현재 코드: `knowledge.py`, `answer_card.py`, `chat_turn.py`, `chatbot.py`,
  `safety.py`, `/api/v1/ai-agent/chat`, `medical_source_readiness.py`

## 2. 결론

큰 방향은 맞다. 현재 구조는 "LLM이 의료 지식을 만들지 않고, 검수된 지식으로 만든
내부 답변 프레임과 deterministic boundary를 문장화한다"는 제품 철학에 맞게 이동했다.

2026-05-29 후속 구현으로 이 리뷰의 주요 P1/P2 갭 중 `unknown backlog`,
`DB-backed evidence -> AnswerCard retriever`, `P0 interaction boundary expansion`,
`structured output`, `renderer class 분리`, `CLI/smoke output contract`는 1차 구현과
테스트까지 완료됐다. 따라서 이 문서는 당시 발견한 위험과 후속 결정의 근거로 유지하고,
현재 남은 핵심 갭은 "검수 evidence coverage를 실제 운영 질문만큼 넓히는 일"과
"Supabase DB connection string을 사용한 live FastAPI smoke"다.

특히 아래는 문서와 코드가 잘 맞는다.

- `AnswerCard`와 `answerability`가 생겨 답변 가능 상태가 명시됐다.
- `unknown_no_reviewed_source`가 있어 검수 지식이 없는 질문을 LLM 일반 지식으로 채우지 않는다.
- 응급, 정신건강 위험, P0 병용, 검사수치/복용량 결정은 LLM 전에 deterministic boundary로 닫는다.
- `SafetyEnvelope`, `SafetyGuard`, `must_not_say`로 LLM 출력 후 검증과 fallback이 있다.
- `/api/v1/ai-agent/chat` 응답에 `answerability`와 `sources`가 추가됐다.
- production source readiness gate가 생겨 reviewed source governance가 비어 있으면 fail-closed할 수 있다.

다만 아직 "검수 지식이 있는 모든 질문을 답변 프레임 품질로 답한다"는 목표까지는 미완성이다.
현재는 작은 seed frame 기반 MVP이며, coverage를 넓히는 검색/정규화/검수 workflow가
아직 수동 registry 중심이다. 여기서 `AnswerCard`는 질문별 수동 FAQ 카드가 아니라, 검색된
검수 지식을 답변 직전 정리하는 내부 답변 프레임이다.

## 2.1 처음부터 지금까지의 작업 흐름

현재 브랜치 히스토리와 문서를 기준으로 보면 Lemon Aid LLM/agent 작업은 아래 흐름으로 발전했다.

1. **Daily Coaching 품질 고정**
   - 초기 목표는 confirmed food/supplement/activity 입력을 deterministic engine이 해석하고,
     LLM은 한국어 설명과 카드형 응답 문장을 담당하게 하는 것이었다.
   - 관련 근거: `2026-05-21-daily-coaching-chatbot-alarm-exercise-todo.md`,
     `2026-05-21-daily-coaching-chatbot-alarm-exercise-learning-notes.md`

2. **Chatbot endpoint 분리**
   - `/api/v1/ai-agent/chat`를 daily-coaching과 분리해 만들되, 같은 sensitive-health consent,
     local LLM provider, SafetyGuard, raw trace 비노출 원칙을 재사용했다.
   - 이 단계의 챗봇은 "안전한 한국어 fallback + LLM wording" 중심이었다.

3. **Mobile/API 계약 연결**
   - Flutter chat 화면, provider/memory badge, medical disclaimer, source family chip이 붙었다.
   - backend contract test가 route와 mobile DTO의 최소 호환성을 고정했다.

4. **Runtime readiness와 local/self-hosted provider 정리**
   - Ollama는 개발용 로컬 반복, SGLang은 self-hosted runtime 후보로 나뉘었다.
   - `SGLANG_BASE_URL=http://127.0.0.1:30000/v1`, `Qwen/Qwen2.5-0.5B-Instruct`가 smoke 기준으로 쓰였다.
   - 관련 근거: `2026-05-22-mvp-runtime-and-medical-knowledge-todo.md`, LLM-WIKI `ollama`, `sglang`,
     `vllm-vs-sglang`

5. **의료 지식층 분리**
   - 만성질환·복약·영양제 사실을 LLM fine-tuning에 넣지 않고, reviewed source registry와
     readiness gate로 관리하는 방향이 잡혔다.
   - 관련 근거: `31-medical-knowledge-layer.md`

6. **Safety와 source family 회귀 테스트 강화**
   - 약 중단/복용량 변경, 진단/치료 단정, unsupported evidence/numeric claim을 막는 테스트가 추가됐다.
   - 이 시점부터 "LLM이 말하면 안 되는 것"이 코드 정책으로 고정되기 시작했다.

7. **AnswerCard 기반 구조로 전환**
   - 최근 5개 커밋에서 `AnswerCard`, `ChatTurnModule`, `unknown_no_reviewed_source`,
     `answerability`, `sources[]`, DB-backed source readiness가 들어왔다.
   - 이 단계가 현재 우리가 말하는 "검수 지식이 있으면 내부 답변 프레임으로 구체 답변하고,
     검수 지식이 없으면 모른다고 하기"의 1차 구현이다.

이 연대기를 보면 지금 방향은 갑자기 바뀐 것이 아니라, 처음의 deterministic-first 원칙이 점점 더
구조화된 source/card governance로 강화된 흐름이다.

## 3. 문서 기준 핵심 요구사항

### 3.1 LLM-WIKI 기준

LLM-WIKI는 단순 RAG보다 지속 관리되는 지식층을 강조한다.

- raw source는 불변 source of truth로 둔다.
- LLM이 raw source를 매번 다시 읽는 대신, 구조화된 wiki 또는 중간 지식층을 유지한다.
- 질문 시에는 index 또는 구조화 지식층에서 관련 지식을 찾고, 출처와 함께 답한다.
- 의료/법률 도메인은 RAG + 강한 인용 추적이 우선이며, REFRAG는 출처 추적 약화 가능성이 있다.
- SGLang은 structured output과 agent/tool calling 성격이 강한 워크로드에 적합하다.
- Ollama는 로컬 개발과 빠른 반복에 적합하다.

우리 방향과의 연결:

- `AnswerCard`는 LLM-WIKI의 "raw source와 최종 답변 사이의 구조화된 내부 답변 프레임"
  역할을 한다.
- 현재는 vector RAG보다 card normalizer를 먼저 고정한 점이 맞다.
- 다음 단계는 manual seed를 늘리는 것이 아니라, raw source나 DB evidence를 검색해
  매번 `AnswerCard` shape로 동적 정규화하는 workflow다.

### 3.2 Lemon Aid 문서 기준

PRD/TRD/TDD가 반복해서 요구하는 핵심은 다음이다.

- 모든 사용자-facing 건강 답변은 `AnswerCard`, boundary renderer, unknown renderer 중 하나에서 나온다.
- reviewed, user-facing allowed, not stale source만 답변 근거가 된다.
- draft, paper_candidate, stale source는 사용자 답변에 노출하지 않는다.
- LLM prompt에는 raw chunk, raw OCR, raw prompt, internal trace, draft source를 넣지 않는다.
- LLM은 `AnswerCard` 밖 건강 사실이나 개인 의료 결정을 만들면 안 된다.
- production-like 경로에서는 DB-backed reviewed source가 없으면 fail-closed한다.
- RAG/vector DB는 source governance와 card normalizer가 안정된 뒤 별도 단계로 붙인다.

## 4. 현재 구현이 잘 맞는 부분

### 4.1 답변 가능 상태가 명시됐다

`answer_card.py`에 `Answerability`가 생겼고, `ChatTurnModule`이 질문별 `ChatTurnPlan`을 만든다.

현재 상태:

- `answerable`
- `answerable_with_caution`
- `needs_more_info`
- `unknown_no_reviewed_source`
- `medical_decision_boundary`
- `urgent_escalation`

이 구조는 "차단 여부"가 아니라 "어디까지 설명 가능한가"로 분류하자는 방향과 맞다.

### 4.2 Unknown fail-closed가 구현됐다

`MedicalKnowledgeRetriever`가 관련 `AnswerCard`를 찾지 못하면 `no_reviewed_answer_card` warning과 함께
`unknown_no_reviewed_source`로 내려간다. `ChatbotAgent`는 이 상태에서 LLM을 호출하지 않고
unknown renderer로 답한다.

이 부분은 사용자가 말한 "우리가 가지고 있지 않은 질문은 모른다고 해야 한다"는 요구와 맞다.

### 4.3 약/영양제 병용 질문의 완전 차단을 완화했다

`혈압약 + 마그네슘`은 `medication_supplement_caution`으로 분류되고, 답변에는 제품 라벨, 함량,
혈압약 종류, 신장 기능, 이상 증상, 약사/의사 확인이 들어간다.

동시에 `와파린 + 비타민 K`, `갑상선약 + 칼슘/철분`, 약 중단/증량/감량, 검사수치 치료 판단은
boundary로 유지된다.

이 방향은 "구체적으로 돕되, 개인 의료 결정은 넘지 않는다"와 맞다.

### 4.4 테스트가 정책을 잘 고정한다

현재 테스트는 아래 중요한 회귀를 잡는다.

- 카드 없는 질문은 LLM 호출 없이 unknown
- 응급/정신건강/P0/검사수치는 LLM 미호출
- LLM이 금지 문구, unsupported fact, unsupported number를 만들면 fallback
- 마그네슘 caution은 필수 체크리스트 포함
- 나트륨 저녁은 구체 음식과 행동 단위 답변
- route 응답에서 `answerability`와 `sources` 유지
- production source gate fail-closed

실행 확인:

```text
python -m pytest -q --no-cov backend/ai_agent_chat/tests \
  backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py \
  backend/Nutrition-backend/tests/unit/services/test_medical_source_readiness.py

106 passed, 1 skipped, 1 warning
```

## 4.5 요구사항-증거 매트릭스

| 요구사항 | 현재 증거 | 판정 |
| --- | --- | --- |
| LLM은 의료 판단자가 아니라 문장화 계층이다 | `31-medical-knowledge-layer.md`, `ChatAgent`, `ChatbotAgent`, SafetyGuard fallback tests | 대체로 충족 |
| 응급, 정신건강, P0 병용, 검사수치/복용량 결정은 LLM 전에 닫는다 | `classify_question()`, `ChatbotAgent._boundary_response()`, no-LLM tests | 충족 |
| 검수 지식이 없으면 LLM 일반 지식으로 답하지 않는다 | `MedicalKnowledgeRetriever`, `ChatbotAgent._unknown_response()`, unknown tests | 충족 |
| 내부 답변 프레임 기반 답변에는 reviewed source metadata가 따라간다 | `AnswerCard.source_metadata()`, API `sources[]`, route integration test | 충족 |
| reviewed, user-facing allowed, not stale source만 `AnswerCard`가 된다 | normalizer가 review status, user-facing, expiry를 검사 | 충족 |
| production-like 경로는 reviewed source DB 없으면 fail-closed한다 | `build_chatbot_medical_knowledge_retriever()`, route/service tests | 충족 |
| 실제 답변 `AnswerCard`가 DB-backed source에서 왔음을 보장한다 | DB row -> `MedicalEvidenceAnswerCardRecord` -> `AnswerCardNormalizer.from_evidence_record()`, route/service tests | 충족 |
| RAG/vector DB는 source governance 안정 후 붙인다 | 문서와 구현 모두 RAG 미도입 | 충족 |
| LLM-WIKI 지식은 raw 자료가 아니라 구조화된 내부 답변 프레임으로 흡수한다 | `AnswerCard`, DB evidence seed, unknown backlog workflow | 1차 충족 |
| SGLang structured output 강점을 활용한다 | OpenAI-compatible `response_format` JSON schema와 fallback tests | 1차 충족 |

## 5. 부족하거나 위험한 부분

### 5.1 일부 `AnswerCard`의 source_id와 실제 source_url이 맞지 않았다

가장 먼저 고쳐야 할 부분이었다. 2026-05-29 후속 작업에서 registry source를 분리해 1차 수정했다.

기존 `magnesium_supplement_caution`은 다음 상태였다.

- `source="NIH ODS Magnesium Fact Sheet"`
- `source_url="https://ods.od.nih.gov/factsheets/Magnesium-Consumer/"`
- `source_id="kdris-2025"`

이러면 사용자 응답의 source metadata는 KDRIs로 보이는데, 실제 근거 URL은 NIH ODS가 된다.
문서가 요구한 source traceability와 충돌한다.

비슷하게 `kidney_disease_meal_caution`도 `source="NIDDK Kidney Disease"`인데
`source_id="kdca-healthinfo"`를 사용한다.

반영 내용:

- `nih-ods-magnesium`, `niddk-kidney-disease`, `niddk-diabetes-living`,
  `cdc-public-health` registry entry를 추가했다.
- CDC/NIDDK/NIH ODS seed item의 `source_id`를 실제 source URL domain과 맞췄다.
- 모든 user-facing card의 `source_id`가 reviewed registry에 있고, card URL과 registry URL의
  host가 같은 계열인지 확인하는 governance test를 추가했다.

### 5.2 not-stale 판정이 AnswerCardNormalizer 안에 없었다

TRD는 reviewed, user-facing allowed, not stale source만 `AnswerCard`가 되어야 한다고 한다.
2026-05-29 후속 작업에서 normalizer가 `review_expires_at`을 직접 검사하도록 1차 수정했다.

API production gate는 DB readiness에서 stale을 막을 수 있지만, `ai_agent_chat` 패키지 단독 사용이나
local/dev 경로에서도 stale registry seed가 그대로 `AnswerCard`가 되지 않도록 막는다.

반영 내용:

- `AnswerCardNormalizer`가 만료된 source를 `AnswerCard`로 만들지 않는다.
- matched `AnswerCard`가 모두 stale이면 retriever가 `retrieval_status="stale_only"`와 `source_stale`
  warning을 반환한다.
- stale source normalizer/retriever test를 추가했다.

### 5.3 production source gate와 실제 답변 AnswerCard source 분리 문제는 1차 해소됐다

초기 리뷰 시점에는 `/api/v1/ai-agent/chat` production gate가 DB에 reviewed source가
하나라도 있으면 통과했지만, 실제 답변 생성은 registry 기반 `MedicalKnowledgeRetriever`가
수행했다.

2026-05-29 후속 구현에서 FastAPI route는 `ChatbotEvidenceRepository`를 통해
`medical_sources`, `medical_source_versions`, `medical_evidence_items`를 읽고,
DB row를 `MedicalEvidenceAnswerCardRecord`로 정리한 뒤
`AnswerCardNormalizer.from_evidence_record()`를 통과시킨다. production-like 환경에서
reviewed/not-stale DB evidence가 없으면 registry fallback 없이 fail-closed한다.

남은 확인은 코드 구조가 아니라 운영 연결 확인이다. 즉, Supabase `DATABASE_URL`로 실제
FastAPI 서버를 띄워 `/api/v1/ai-agent/chat` 응답의 `answerability`, `sources[]`,
unknown backlog 기록까지 end-to-end smoke로 확인해야 한다.

### 5.4 reviewed knowledge coverage 확장 workflow가 아직 부족하다

사용자 목표는 "질문별 수동 FAQ 카드를 많이 만드는 것"이 아니라, "축적된 검수 지식 안에서는
모든 질문을 내부 답변 프레임으로 정리해 구체 답변하고, 검수 지식이 없으면 모른다고 하기"다.
현재는 seed frame 몇 개로 golden path와 내부 shape를 고정한 상태다.

남은 것:

- reviewed knowledge coverage inventory
- backlog 반복 주제를 사람이 검수 evidence로 승격하는 운영 화면
- source owner/reviewer 운영 책임 지정
- evidence/source 추가 시 version/expiry/allowed wording/blocked wording/golden test까지 함께
  추가하는 절차 자동화

현재 반영된 것:

- `chatbot_unknown_knowledge_events`는 raw 질문 없이 structured topic metadata만 저장한다.
- `report_chatbot_unknown_backlog.py`와 Supabase
  `chatbot_unknown_knowledge_backlog_summary` view로 1차 triage가 가능하다.
- Supabase MCP SQL로 privacy-safe 임시 topic insert, summary 집계, cleanup을 확인했다.

후속 방향:

- backlog summary view를 admin 화면 또는 운영 문서 workflow에 연결한다.
- evidence/source 추가 템플릿과 review checklist를 만든다.

### 5.5 P0 상호작용 매트릭스는 우선순위 항목을 1차 확장했다

초기 테스트는 와파린+비타민 K, 갑상선약+칼슘/철분 등 핵심만 잡았다.
2026-05-29 후속 구현에서 reviewed policy boundary로 세인트존스워트, 자몽, 칼륨 보충제/저염소금,
nitrate+PDE5 inhibitor, SSRI/SNRI+세로토닌성 보충제, statin+홍국 조합을 추가했다.

주의:

- 이 내용을 바로 사용자 답변에 넣으면 안 된다.
- 먼저 reviewed source로 승격하고, P0 boundary card 또는 policy boundary로 만들어야 한다.

남은 방향:

- coverage inventory에서 반복되는 P0 후보를 추가로 선별한다.
- LLM-WIKI 항목은 계속 "검수 후보"로만 사용한다.
- MFDS/KDCA/공식 label source와 연결된 항목만 user-facing boundary로 승격한다.

### 5.6 structured output은 1차 적용됐다

SGLang/OpenAI-compatible 경로에서는 `response_format` JSON schema를 사용해
`summary`, `why_it_matters`, `today_actions`, `specific_examples`,
`caution_conditions`, `expert_check_points`, `source_basis`를 요구한다.

schema 불일치, 파싱 실패, 금지 표현 감지, grounding 실패 시 deterministic
`CardAnswerRenderer` fallback으로 전환한다. 남은 작업은 실제 SGLang 서버를 붙인 운영
smoke와 schema 품질 튜닝이다.

### 5.7 `CONTEXT.md`는 좋은 용어집이지만 아직 추적되지 않는다

`CONTEXT.md`는 `LLM Completion`, `Deterministic Coaching`, `Safety Envelope`, `Chat Turn`,
`App Intake` 용어를 잘 정리한다. 현재 untracked라 협업 기준 문서로는 아직 불안정하다.

수정 방향:

- 이 파일을 유지할 거면 `docs/Integration-docs/` 또는 `backend/ai_agent_chat/README.md`에 통합한다.
- 아니면 임시 메모로 폐기한다.
- 용어는 `03`, `06`, `08` 문서와 맞춰 중복 없이 정리한다.

## 6. 추가/수정 우선순위

### P0. 바로 고쳐야 할 정합성 문제

1. `source_id`와 실제 source URL/publisher 불일치 수정
   - `magnesium_supplement_caution`: `nih-ods-magnesium` source로 분리
   - `kidney_disease_meal_caution`: `niddk-kidney-disease` source로 분리
   - 상태: 2026-05-29 1차 수정 완료

2. AnswerCard 생성 시 source expiry 검사 추가
   - stale source는 `AnswerCard`로 만들지 않는다.
   - 테스트: expired reviewed source -> `stale_only` 또는 unknown.
   - 상태: 2026-05-29 1차 수정 완료

3. source governance test 강화
   - 모든 user-facing card의 `source_id`가 registry에 존재해야 한다.
   - `source_url`이 registry source와 설명 가능한 관계인지 확인한다.
   - `source_id`, `source_family`, `review_status`, `expires_at` 누락 금지.
   - 상태: 2026-05-29 1차 수정 완료

### P1. 다음 기능 품질을 결정할 작업

4. unknown backlog 설계
    - unknown 질문에서 필요한 topic/source 후보만 안전하게 기록한다.
    - raw prompt, raw OCR, 개인 건강정보는 저장하지 않는다.
   - 상태: 2026-05-29 1차 구현 완료

5. DB-backed retriever 전환 계획 구체화
    - 현재 DB readiness와 registry card retrieval 사이의 간극을 줄인다.
    - production path에서 실제 `AnswerCard` source가 DB reviewed/not stale인지 확인한다.
   - 상태: 2026-05-29 1차 구현 완료

6. P0 interaction boundary 확장
    - LLM-WIKI interaction matrix를 검수 후보로 삼는다.
    - MFDS/KDCA/공식 label source와 연결된 항목만 user-facing boundary로 승격한다.
   - 상태: 2026-05-29 1차 구현 완료

7. 기존 runtime/preflight 문서와 새 AnswerCard 문서의 상태 동기화
   - `2026-05-22-mvp-runtime-and-medical-knowledge-todo.md`는 아직 코드 registry 중심 설명이 강하다.
   - `31-medical-knowledge-layer.md`는 `source_families`와 Flutter chip 완료 상태를 언급하지만,
     `answerability`, `sources[]`, `AnswerCard` 이후 상태를 충분히 반영하지 않는다.
   - 후속 문서 정리에서 05~10번 Integration-docs를 기준으로 오래된 TODO의 "부분 완료" 항목을 갱신한다.

### P2. LLM/agent 완성도를 높이는 작업

8. structured output 도입 검토
    - SGLang/OpenAI-compatible `response_format`을 활용해 답변 section JSON을 강제한다.
    - SafetyGuard는 JSON fields 단위로 검증한다.
   - 상태: 2026-05-29 1차 구현 완료

9. AnswerCard renderer 분리
    - 현재 `ChatbotAgent` 안에 fallback renderer가 많다.
    - `CardAnswerRenderer`, `UnknownRenderer`, `BoundaryRenderer`로 분리하면 테스트와 확장이 쉬워진다.
   - 상태: 2026-05-29 1차 구현 완료

10. source card UI 계약 준비
    - backend는 `sources[]`를 내보내지만 UI detail sheet는 아직 별도 범위다.
    - `source_id`, `source_family`, `review_status`, `version_label`, `reviewed_at`,
      `expires_at`, `source_url` 표시 정책을 고정한다.
    - 상태: 2026-05-29 1차 구현 완료

11. local smoke 스크립트와 CLI의 새 응답 계약 반영
   - `backend/scripts/ask_chatbot_agent.py`는 `answerability`, `sources`, `source_families`,
     `safety_warnings`를 출력한다.
   - golden eval 핵심 케이스를 수동 QA preset으로 실행할 수 있다.
   - `smoke_ai_agent_server.py`는 chat summary에 `answerability`, source metadata, unknown backlog
     delta를 포함한다.
   - 상태: 2026-05-29 1차 구현 완료

## 7. 지금 상태 평가

현재 챗봇 설계 기초는 이전보다 훨씬 탄탄해졌다.

좋은 점:

- 답변 철학이 코드와 테스트에 들어갔다.
- LLM hallucination을 막는 fail-closed 경로가 생겼다.
- 약/영양제 질문을 무조건 회피하지 않고, 설명 가능한 범위와 결정 금지 범위를 나눴다.
- RAG를 성급하게 붙이지 않고, `AnswerCard`라는 안전한 내부 답변 프레임을 먼저 만들었다.

아직 미흡한 점:

- Supabase `DATABASE_URL`을 사용한 live FastAPI smoke가 아직 실행되지 않았다.
- Supabase MCP SQL로 원격 DB readiness와 backlog summary view probe는 확인했다.
- 검수 지식이 있는 모든 질문을 답변 프레임 품질로 답하려면 reviewed knowledge coverage 확장
  workflow와 운영 backlog triage가 필요하다.
- P0 상호작용 지식은 우선순위 6개 조합을 승격했지만, 실제 사용자 질문 로그 기반으로 계속
  확장해야 한다.
- structured output은 1차 적용됐지만, 실제 SGLang 서버 연결 smoke와 schema 품질 튜닝이 남아 있다.

따라서 다음 작업은 새 기능을 크게 붙이는 것보다, Supabase live FastAPI smoke를 통과시키고
reviewed knowledge coverage 확장 체계를 만드는 것이 맞다.

## 8. 다음 작업 제안

다음 PR/작업 단위는 아래 순서가 안전하다.

1. `Supabase live FastAPI smoke`
   - `DATABASE_URL`을 연결해 `/api/v1/ai-agent/chat`에서 DB evidence 기반 답변,
     unknown backlog 기록, `sources[]`를 확인

2. `unknown backlog 운영 리포트`
   - 저장 금지 경계를 지키는 unknown topic capture 결과를 triage 가능한 형태로 집계
   - 상태: 2026-05-29 1차 구현 완료

3. `reviewed evidence coverage expansion`
   - 반복 질문을 source/version/evidence/golden test 단위로 승격

4. `P0 interaction boundary expansion`
   - LLM-WIKI 후보를 reviewed source와 매핑한 boundary card로 추가 승격

## 9. 문서별 후속 반영 필요 여부

| 문서 | 현재 상태 | 후속 조치 |
| --- | --- | --- |
| `01-ci-pr-integration-operations.md` | 일반 PR/CI 운영 문서 | 유지 |
| `02-ai-agent-worktree-integration-plan.md` | integration base와 PR split 기준은 여전히 유효 | AnswerCard/source governance PR split을 반영하면 좋음 |
| `03-ai-agent-safety-porting-contract.md` | 안전/저장 금지 상위 계약으로 유효 | P0 boundary 확장 시 boundary_code 기준 추가 |
| `04-medical-source-db-contract.md` | DB governance 계약으로 유효 | Supabase live smoke 결과가 나오면 운영 연결 절 갱신 |
| `05-grounded-chatbot-prd.md` | 제품 목표와 답변 철학 기준으로 유효 | coverage workflow와 unknown backlog 운영 요구를 계속 보강 |
| `06-grounded-chatbot-tdd.md` | 구현 설계와 테스트 기준으로 유효 | live smoke 결과와 SGLang schema 튜닝 결과 반영 |
| `07-grounded-chatbot-todo.md` | 구현 반영 상태와 체크박스를 현재 audit 기준으로 갱신 | live smoke 완료 시 완료 정의 갱신 |
| `08-grounded-chatbot-trd.md` | 기술 요구사항 기준으로 유효 | Supabase 운영 연결과 source detail UI 계약 보강 |
| `09-grounded-chatbot-implementation-log.md` | 최근 구현 로그로 유효 | live smoke 완료 시 결과 추가 |
| `31-medical-knowledge-layer.md` | 초기 의료 지식층 원칙으로 유효 | `AnswerCard`, `answerability`, `sources[]` 이후 상태 반영 필요 |

## 10. 완료 판단

이번 리뷰는 "현재 방향이 맞는가"에 대해서는 근거 있게 답할 수 있다.

판정:

- 방향성: 맞다.
- 설계 기초: 이전보다 탄탄해졌다.
- MVP 구현: 핵심 safety/unknown/card route와 DB-backed AnswerCard 경로는 테스트와 원격 DB readiness
  probe에서 작동한다.
- production-grade reviewed knowledge coverage: 아직 아니다.
- 다음 작업: Supabase `DATABASE_URL`로 live FastAPI smoke를 실행하고, reviewed knowledge coverage를
  운영 workflow로 확장해야 한다.

따라서 지금 단계에서 "운영 챗봇 전체가 완성됐다"가 아니라, "Supabase 기반 DB evidence ->
AnswerCard -> renderer 골격은 구현됐고, live smoke와 reviewed knowledge coverage 확장이 남았다"가
정확한 결론이다.
