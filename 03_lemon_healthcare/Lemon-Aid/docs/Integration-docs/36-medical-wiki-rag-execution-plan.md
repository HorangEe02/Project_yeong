# 36. MEDICAL-WIKI RAG 실행 계획

이 문서는 MEDICAL-WIKI reviewed claim / EvidenceBundle adapter 이후 작업을 이어가기 위한 실행 기준이다. 실제 구현 결과와 검증 로그는 [09-grounded-chatbot-implementation-log.md](./09-grounded-chatbot-implementation-log.md)에 축적하고, 이 문서는 다음 단계에서 무엇을 해야 하는지 판단하는 계획 원본으로 유지한다.

## 현재 상태

| Phase | 상태 | 기준 |
| --- | --- | --- |
| Phase 0. 42 claim / 84 boundary adapter | 완료 | `97c39a3 feat(ai): connect medical wiki reviewed claims` 이후 최신 MEDICAL-WIKI manifest 기준 |
| Phase 1. EvidenceBundle backend adapter | 완료 | 94 fixture backend 소비, boundary 84 / answerable 10 |
| Phase 2. API source detail contract | 완료 | `/api/v1/ai-agent/chat` route-level source contract test 추가, public source detail 필터/중복 제거 |
| Phase 3. claim + section retrieval baseline | smoke 완료, baseline 유지 대상 | claim + section retrieval smoke 94/94 |
| Phase 4. reranker 실험 | 완료 | baseline vs boundary-claim-first A/B, contextual expansion rank, 실패 분류 taxonomy 기록 |
| Phase 5. Sanitized trace / runtime metrics / LangSmith export | 1차 계약 구현 | 자체 span schema, runtime metric report, structured warning log, optional LangSmith exporter, raw-free eval export. Cloud/self-hosted 업로드는 승인 전 금지 |
| Phase 6. LangChain / vector DB 실험 | 대기 | 현재 42 claim / 5 section으로 production/runtime 도입 조건 미충족. LangChain core 도입 금지 |
| Phase 7. SGLang polish 실험 | smoke 완료, 정책 유지 대상 | boundary는 LLM bypass, answerable은 deterministic draft polish only |

현재 feature branch 기준:

- 작업 브랜치: `feat/ai-agent-backend-integration`
- 통합 방식: `develop` 직접 push 금지, PR로 통합
- PR 기준: `feat/ai-agent-backend-integration -> develop`
- MEDICAL-WIKI 위치: workspace root sibling. backend repo 내부로 복사하지 않는다.
- 제외 대상: `mobile/flutter_app/chrome-shot-profile/`, `mobile/flutter_app/*.png`, workspace-root `MEDICAL-WIKI/manifest/backend_deterministic_eval_results.jsonl`

## 불변 원칙

- LangChain, vector DB, reranker, SGLang은 의료 판단 계층이 아니다.
- runtime 답변은 계속 `reviewed claim -> EvidenceBundle/AnswerCard -> renderer/LLM polish -> SafetyGuard` 흐름을 통과해야 한다.
- raw source chunk, raw retrieval rank, matched terms, debug trace, raw prompt, raw LLM response, provider payload, user health data는 사용자 답변 artifact나 indexable runtime artifact에 넣지 않는다.
- 관측/평가 trace도 raw-free sanitized span만 허용한다. raw user question, raw prompt, raw OCR, raw LLM response, provider payload, debug trace, user health snapshot은 span/export/dataset에 넣지 않는다.
- safety boundary는 retrieval result, reviewed section, LLM polish보다 항상 우선한다.
- corpus 없는 CI에서는 MEDICAL-WIKI-dependent test를 skip한다.
- `sources[]` 확장은 additive field만 허용한다. 기존 Flutter DTO를 깨지 않는다.

## Phase 0. Reviewed Claim Adapter 완료 기록

완료 기준:

- 42 reviewed claim / 84 chatbot answer eval input backend adapter 연결
- 84/84 deterministic eval pass
- `ai_agent_chat` tests pass
- mobile screenshot / chrome profile 미포함
- feature branch push 완료
- develop 대상 PR 반영

고정된 검증:

```powershell
python -X utf8 backend\scripts\eval_medical_wiki_chatbot.py --as-of 2026-06-10
python -X utf8 -m pytest -q --no-cov backend\ai_agent_chat\tests
python -m ruff check backend\ai_agent_chat\src\lemon_ai_agent\medical_wiki_claims.py backend\ai_agent_chat\src\lemon_ai_agent\answer_card.py backend\ai_agent_chat\src\lemon_ai_agent\chat_turn.py backend\ai_agent_chat\src\lemon_ai_agent\renderers.py backend\scripts\eval_medical_wiki_chatbot.py backend\ai_agent_chat\tests\test_medical_wiki_claim_adapter.py backend\Nutrition-backend\tests\unit\scripts\test_eval_medical_wiki_chatbot.py
```

## Phase 1. EvidenceBundle Backend Adapter 완료 기록

완료 기준:

- `MEDICAL-WIKI/manifest/evidence_bundle_adapter_fixtures.jsonl` 94개 backend 소비
- boundary fixture 84개는 LLM 호출 없이 deterministic
- answerable fixture 10개는 deterministic draft 기반
- forbidden marker hit 0
- `source_id` / `linked_claim_id` 유지
- raw retrieval/debug trace 미사용

고정된 검증:

```powershell
python -X utf8 -m pytest -q --no-cov backend\ai_agent_chat\tests\test_medical_wiki_evidence_bundle_adapter.py backend\Nutrition-backend\tests\unit\scripts\test_eval_medical_wiki_evidence_bundles.py
python -X utf8 backend\scripts\eval_medical_wiki_evidence_bundles.py --as-of 2026-06-10 --dry-run
```

## Phase 2. Backend API Source Detail Contract

목표:

- backend API 응답에서 MEDICAL-WIKI claim/section source metadata가 UI에서 쓸 수 있는 형태로 유지되는지 고정한다.

구현 작업:

1. `/api/v1/ai-agent/chat` route-level integration test를 추가한다.
2. boundary route를 검증한다.
   - expected claim `source_id` 포함
   - section source가 boundary claim을 덮지 않음
   - raw text, debug trace, retrieval rank 미포함
3. answerable route를 검증한다.
   - safety anchor claim source 포함
   - reviewed section source 포함
   - claim source와 section source 중복 제거
   - raw text, debug trace, provider payload 미포함
4. unknown route를 검증한다.
   - `sources=[]`
   - raw question 저장 없음
5. route test에 MEDICAL-WIKI fixture가 필요하면 corpus 없는 CI에서는 skip한다.
6. route injection seam이 없으면 test-only factory override 또는 기존 agent construction seam을 사용한다. production route가 MEDICAL-WIKI fixture에 직접 의존하게 만들지 않는다.

최소 source detail field:

- `source_id`
- `source_family`
- `review_status`
- `version_label`
- `reviewed_at`
- `expires_at`
- `source_url`

완료 기준:

- `/api/v1/ai-agent/chat` integration test pass
- Flutter DTO 호환성 유지
- `sources[]`는 additive field로만 확장
- source detail에 raw text/debug 없음

2026-06-09 실행 결과:

- route-level integration test 3개 추가.
  - boundary: claim source가 먼저 유지되고 section source가 boundary claim을 덮지 않음.
  - answerable: safety anchor claim source와 reviewed section source를 모두 유지하고 같은 `source_id` 중복을 제거함.
  - unknown: `sources=[]`이며 raw question이 응답과 backlog event에 남지 않음.
- `ChatbotApiResponse.sources`는 `source_id`, `source_family`, `review_status`, `version_label`, `reviewed_at`, `expires_at`, `source_url`, `boundary_code`만 공개한다.
- 검증:

```powershell
python -X utf8 -m pytest -q --no-cov backend\Nutrition-backend\tests\integration\api\test_ai_agent_api.py::test_chat_route_medical_wiki_boundary_sources_are_public_and_claim_first backend\Nutrition-backend\tests\integration\api\test_ai_agent_api.py::test_chat_route_medical_wiki_answerable_sources_are_deduped_and_public backend\Nutrition-backend\tests\integration\api\test_ai_agent_api.py::test_chat_route_medical_wiki_unknown_sources_stay_empty_and_raw_free
```

결과: `3 passed, 1 warning`.

## Phase 3. Claim + Section Retrieval Baseline

목표:

- runtime 도입 전 claim-only와 claim+section retrieval을 비교 가능한 benchmark로 유지한다.

입력:

- `MEDICAL-WIKI/manifest/indexable_reviewed_claims.jsonl`
- `MEDICAL-WIKI/manifest/indexable_reviewed_sections.jsonl`
- `MEDICAL-WIKI/manifest/chatbot_answer_eval_inputs.jsonl`
- `MEDICAL-WIKI/manifest/answerable_eval_inputs.jsonl`

작업:

1. claim-only baseline을 유지한다.
   - boundary query 84/84 top-k claim 통과
2. claim+section baseline을 유지한다.
   - answerable query 10/10 expected section top-1
   - boundary query에서 section이 safety claim보다 우선하지 않음
3. 결과 파일은 실험 산출물로만 취급한다.
   - production runtime artifact 아님
   - PR 포함 여부는 별도 판단

검증:

```powershell
python -X utf8 MEDICAL-WIKI\tools\run_claim_section_retrieval_smoke.py --as-of 2026-06-10 --dry-run
python -X utf8 MEDICAL-WIKI\tools\run_evidence_bundle_normalizer_smoke.py --as-of 2026-06-10 --dry-run
```

완료 기준:

- claim + section retrieval smoke 94/94 pass
- boundary 84/84 top-k claim 유지
- answerable 10/10 expected section top-1
- EvidenceBundle normalizer 94/94 유지

## Phase 4. Reranker 실험

목표:

- corpus가 커질 때 safety claim이 reviewed section에 밀리지 않는 reranking 규칙을 검증한다.

기본 정책:

- hard boundary claim은 section보다 우선한다.
- `urgent_escalation`, `medical_decision_boundary`, `safety_boundary` claim이 top-k 밖으로 밀리면 실패다.
- reranker는 후보 순서만 바꾸고 answerability를 완화하지 않는다.
- runtime route에는 아직 연결하지 않는다.

작업 순서:

1. 현재 BM25-lite / keyword baseline을 저장한다.
2. contextual query expansion 적용 전후를 비교한다.
3. lightweight reranker를 추가 실험한다.
   - boundary claim boost
   - linked claim boost
   - reviewed section은 linked claim이 있을 때만 answerable 후보로 사용
   - stale/expired source 제외
4. 실패 케이스를 분류한다.
   - synonym 부족
   - claim/section overlap
   - disease context 누락
   - boundary red flag 누락
5. production 후보는 baseline보다 안전할 때만 문서화한다.

완료 기준:

- boundary claim top-k recall 하락 없음
- answerable section recall 개선 또는 동등
- 실패 케이스 문서화
- runtime 연결 없음

2026-06-09 실행 결과:

- `run_claim_section_retrieval_smoke.py`가 baseline score 정렬과 boundary-claim-first rerank 결과를 함께 기록한다.
- answerable query는 contextual expansion 전후 expected section rank를 기록한다.
- 실패 원인은 `synonym_or_context_gap`, `claim_section_overlap`, `boundary_red_flag_missed`, `boundary_priority_regression`, `unclassified_failure`로 분류한다.
- 현재 corpus dry-run 및 결과 파일 갱신 요약:
  - total 94/94 pass
  - answerable section top-1 10/10
  - boundary claim top-k 84/84
  - reranker preserved boundary claim 84/84
  - baseline 대비 boundary priority 개선 1건
  - failure category count `{}`
  - runtime route 연결 없음
- 검증:

```powershell
python -X utf8 -m unittest MEDICAL-WIKI\tools\test_claim_section_retrieval_smoke.py
python -X utf8 MEDICAL-WIKI\tools\run_claim_section_retrieval_smoke.py --as-of 2026-06-09 --dry-run
python -X utf8 MEDICAL-WIKI\tools\run_claim_section_retrieval_smoke.py --as-of 2026-06-09
```

## Phase 5. Sanitized Trace / Runtime Metrics / LangSmith Export

목표:

- LangSmith를 관측/평가 후보로 포함하되 Cloud 전송부터 시작하지 않는다.
- 먼저 자체 sanitized trace span 계약과 raw-free eval export를 고정한다.
- sanitized span에서 운영 지표를 집계하고, alert code를 structured log로 남긴다.
- LangSmith SDK는 optional exporter에서만 import하고 agent core flow를 decorator 기반으로 재작성하지 않는다.

공식 기준:

- LangSmith는 framework-agnostic observability/evaluation 플랫폼이다.
- SDK 기반 manual tracing과 offline/online evaluation 흐름을 지원한다.
- 프로그램 방식 tracing은 `tracing_context(enabled=...)`로 enable/disable을 제한할 수 있다.
- 참고: <https://docs.langchain.com/langsmith/home>, <https://docs.langchain.com/langsmith/observability>, <https://docs.langchain.com/langsmith/evaluation>, <https://docs.langchain.com/langsmith/trace-without-env-vars>

자체 span 계약:

- 허용 span: `chat_turn_plan`, `retrieval`, `normalization`, `route_decision`, `render`, `llm_polish`, `safety_guard`
- 허용 필드: `request_id`, `span_name`, `answerability`, `retrieval_status`, `renderer_route`, `claim_ids`, `source_ids`, `boundary_code`, `provider`, `latency_ms`, `warning_codes`, `passed`, `raw_fields_stored=false`
- 금지 필드/마커: raw user question, raw prompt, raw OCR, raw LLM response, provider payload, debug trace, user health snapshot
- 기본 recorder는 `NoopAgentTraceRecorder`이며, 테스트/로컬 실행에서만 `InMemoryAgentTraceRecorder` 또는 structured log recorder를 주입한다.

runtime metrics 계약:

- `build_runtime_metrics_report()`는 `AgentTraceSpan`만 입력으로 받는다.
- report에는 `request_id`, `claim_ids`, `source_ids`, raw question, raw prompt, raw OCR,
  raw LLM response, provider payload, user health snapshot을 넣지 않는다.
- 집계 지표:
  - `answerability_unknown_rate`
  - `boundary_rate_by_code`
  - `llm_polish_fallback_rate`
  - `unsafe_polish_fallback_count`
  - `retrieval_no_match_rate`
  - `source_stale_count`
  - `p95_chat_latency_ms`
- `StructuredLogRuntimeMetricsReporter`는 `agent_runtime_metrics {json}` 형태의 structured log를 남긴다.
- alert code가 있으면 `WARNING`, 없으면 `INFO`로 기록한다.
- 현재 alert code:
  - `answerability_unknown_rate_high`
  - `llm_polish_fallback_rate_high`
  - `retrieval_no_match_rate_high`
  - `unsafe_polish_fallback_present`
  - `source_stale_present`
  - `p95_chat_latency_high`

LangSmith exporter 게이트:

- `LANGSMITH_EXPORT_ENABLED=false` 기본값을 유지한다.
- `LANGSMITH_API_KEY`가 없으면 export는 비활성화하고 chat은 깨지지 않는다.
- production 환경에서는 export flag가 켜져도 block한다.
- `LANGSMITH_UPLOAD_ALLOWED=false` 기본값을 유지해 Cloud/self-hosted 업로드를 차단한다.
- exporter는 자체 sanitized span만 LangSmith run payload로 변환한다.
- `traceable` decorator로 `plan()`, retriever, renderer, SafetyGuard를 감싸지 않는다.

Eval export:

- `backend/scripts/export_medical_wiki_langsmith_eval.py`는 기존 MEDICAL-WIKI eval 입력을 LangSmith-compatible JSONL 형태로 파일 export한다.
- export row에는 case id, expected claim/source ids, expected renderer/answerability만 넣고 raw question/user context를 넣지 않는다.
- dry-run summary는 `row_count`, `forbidden_marker_hits`, `raw_fields_stored`, `upload_allowed_count`, `missing_required_ids`, `status`를 출력한다.
- Cloud/self-hosted 업로드는 아래 승인 게이트 전까지 금지한다.
  - PHI-free 확인
  - source/claim ids only 확인
  - raw question 또는 사용자 맥락 없음 확인
  - Cloud, self-hosted, internal-only 중 하나 명시 결정

검증:

```powershell
python -X utf8 -m pytest -q --no-cov backend\ai_agent_chat\tests\test_agent_tracing.py backend\ai_agent_chat\tests\test_langsmith_exporter.py backend\Nutrition-backend\tests\unit\scripts\test_export_medical_wiki_langsmith_eval.py
python -X utf8 backend\scripts\export_medical_wiki_langsmith_eval.py --kind claims --dry-run
python -X utf8 backend\scripts\export_medical_wiki_langsmith_eval.py --kind evidence-bundles --dry-run
```

완료 기준:

- sanitized span schema negative test 통과
- tracing disabled-by-default test 통과
- runtime metric report가 raw-free이고 request/source/claim id를 log에 남기지 않음
- runtime metric alert code와 structured warning log test 통과
- optional LangSmith exporter가 SDK/API key 부재로 chat을 깨지 않음
- production export block test 통과
- upload allowed gate false block test 통과
- claim eval export 84 rows, EvidenceBundle eval export 94 rows
- forbidden marker 0, raw_fields_stored false, upload_allowed_count 0, missing_required_ids 0

2026-06-10 smoke:

- LangSmith-compatible eval export는 dry-run만 확인했다. Cloud/self-hosted upload는 실행하지 않았다.
- `claims` export: 84 rows, `status=pass`, `forbidden_marker_hits=0`, `raw_fields_stored=false`, `upload_allowed_count=0`.
- `evidence-bundles` export: 94 rows, `status=pass`, `forbidden_marker_hits=0`, `raw_fields_stored=false`, `upload_allowed_count=0`.

2026-06-12 observability hardening:

- `build_runtime_metrics_report()`로 sanitized span을 request 단위로 집계한다.
- `evaluate_runtime_metric_alerts()`와 `StructuredLogRuntimeMetricsReporter`를 추가해 runtime
  metric report를 `agent_runtime_metrics` structured log로 남긴다.
- alert가 있으면 `WARNING`, 없으면 `INFO`로 기록한다.
- report/log에는 request id, claim id, source id를 남기지 않는다.
- 패키지 루트에서 `build_runtime_metrics_report`, `evaluate_runtime_metric_alerts`,
  `StructuredLogRuntimeMetricsReporter`를 export한다.
- 검증:

```powershell
python -X utf8 -m pytest -q --no-cov backend\ai_agent_chat\tests
python -m ruff check backend\ai_agent_chat\src backend\ai_agent_chat\tests
python -X utf8 -m compileall -q backend\ai_agent_chat\src
git diff --check
```

결과: `178 passed, 1 skipped`, ruff pass, compileall pass, diff check pass.

## Phase 6. LangChain / Vector DB 실험

목표:

- LangChain/vector DB를 helper-only retrieval experiment로만 평가한다. LangChain core는 현재 runtime에 도입하지 않는다.
- 현재 `backend/ai_agent_chat` agent runtime에는 LangChain/LangGraph import를 두지 않는다.
- `backend/pyproject.toml`의 `learning` optional dependency에 있는 `pgvector`는 Nutrition image-learning pipeline용이며, MEDICAL-WIKI RAG runtime 연결로 보지 않는다.

도입 조건:

- 최소 50 reviewed claim
- 100개 이상 golden/boundary+answerable eval
- 75-150 reviewed section 목표에 근접
- EvidenceBundle adapter 94/94 이상 유지

실험 원칙:

- LangChain `Document`는 `indexable_reviewed_claims`와 `indexable_reviewed_sections`만 사용한다.
- raw source chunking 금지.
- vector result는 prompt로 직접 전달 금지.
- vector result는 반드시 `EvidenceBundle -> AnswerCardNormalizer`를 통과해야 한다.
- `ChatTurnModule.plan()`은 direct LangChain/vector document 형태의 `knowledge_items`를 fail-closed로 제거하고 `retrieval_result_requires_answer_card_normalization` warning을 남긴다.
- production dependency 승격은 별도 결정으로 남긴다.

검증:

- vector retrieval top-k vs baseline 비교
- section explanation이 boundary claim을 넘지 않는지 확인
- stale/expired source 제외
- forbidden marker scan
- `backend/ai_agent_chat` runtime source에서 `import langchain`, `from langchain`, `import langgraph`, `from langgraph` 금지

완료 기준:

- vector DB가 safety gate를 우회하지 않음
- baseline보다 recall이 좋아지거나 운영 가치가 문서화됨
- production dependency 승격 여부가 별도 결정으로 남음

## Phase 7. LangGraph 도입 게이트

현재 결정:

- LangGraph는 즉시 도입하지 않는다.
- 단순 `SafetyPrecheck -> Retrieval` graph POC는 금지한다. 현재 `plan()`이 policy, intent, retrieval, answerability를 함께 계산하고, 검색된 top `AnswerCard`가 boundary를 끌어올리는 구조를 보존해야 한다.
- graph POC가 생겨도 `ChatTurnModule.plan()`의 결합 계약과 boundary early-return behavior를 먼저 테스트로 고정한다.

도입 트리거:

- retrieval retry/query expansion loop가 실제로 필요해짐
- approval flow가 suspend/resume HITL 상태를 요구함
- chatbot/analysis/memory/source-review agent handoff가 필요해짐

POC 기준:

- `PlanNode`가 현재 `plan()`의 policy/intent/retrieval/answerability 결합을 보존한다.
- 이후 conditional edge로 boundary, unknown, renderer, LLM polish, SafetyGuard를 분기한다.
- early-return behavior 회귀 테스트를 먼저 작성한다.
- direct vector/LangChain document가 prompt로 들어가지 않고 `AnswerCard` 또는 boundary renderer 경로로만 승격되는지 검증한다.

## Phase 8. SGLang Structured Output / Polish 실험

목표:

- SGLang은 답변 생성자가 아니라 deterministic draft polish 역할로만 평가한다.

Boundary eval:

- 84 boundary 질문은 계속 LLM bypass가 성공 조건이다.
- `--llm sglang`에서도 provider는 deterministic이어야 한다.

Answerable eval:

- deterministic `AnswerDraft` 생성
- SGLang은 문장 polish만 수행
- final output은 deterministic slot reattach
- LLM이 source, caution, boundary id를 바꿔도 final은 원 슬롯 유지

- `run_answerable_normalizer_polish_smoke.py`는 `source_note`, `caution`, `boundary_claim_ids`를 deterministic draft slot으로 재부착한다.
- LLM이 source/caution/boundary slot을 바꿔 반환해도 mutation을 기록하고 final output은 draft slot을 사용한다.
검증:

```powershell
python -X utf8 MEDICAL-WIKI\tools\run_answerable_normalizer_polish_smoke.py --mode draft --dry-run
python -X utf8 MEDICAL-WIKI\tools\run_answerable_normalizer_polish_smoke.py --mode polish --llm sglang --dry-run --timeout 60
python -X utf8 backend\scripts\eval_medical_wiki_chatbot.py --as-of 2026-06-10 --llm sglang --dry-run
```

완료 기준:

- boundary LLM bypass 84/84
- `--llm sglang` boundary eval summary에서 `llm_bypassed_by_boundary=84`, `provider=deterministic` 유지
- backend claim/evidence bundle tests에서 fake SGLang client 호출 0회 확인
- answerable final output unsafe directive 0
- final source/caution/boundary slots mutation 0
- unsafe polish는 deterministic fallback

2026-06-10 local smoke:

- `lemon-sglang` 컨테이너가 `127.0.0.1:30000`에서 실행 중임을 확인했다.
- `GET http://127.0.0.1:30000/v1/models`에서 `Qwen/Qwen2.5-0.5B-Instruct`를 확인했다.
- `ask_chatbot_agent.py --preset hypertension-sodium-dinner --llm sglang --timeout 90`은 `answerability=answerable`, `provider=sglang`을 반환했다.
- `ask_chatbot_agent.py --preset p0-grapefruit-lipid-med --llm sglang --timeout 90`은 `answerability=medical_decision_boundary`, `provider=deterministic`, `boundary_code:p0_grapefruit_statin`을 반환했다.
- 해석: answerable polish는 SGLang을 사용할 수 있고, P0 safety boundary 질문은 의도대로 LLM을 우회한다.

2026-06-11 backend runtime 이식:

- commit `bea3582 fix(ai): seal sglang polish slots`로 MEDICAL-WIKI에서 검증한
  `deterministic AnswerDraft -> optional SGLang polish -> deterministic slot reattach`
  구조를 `ChatbotAgent` answerable runtime에 연결했다.
- `ChatTurnModule.plan()` 구조는 유지했다. Boundary/unknown early-return 경로도 바꾸지 않았다.
- LLM 호출 전 deterministic card renderer로 draft를 먼저 만들고, SGLang prompt에는 이 draft를
  polish 대상으로 전달한다.
- SGLang structured output의 `source_basis`, `specific_examples`, `caution_conditions`,
  `expert_check_points`는 사용자 응답 슬롯으로 신뢰하지 않는다. 최종 응답은 `AnswerCard`의
  source, checklist, examples, caution slot을 다시 붙인다.
- LLM이 source/caution/example/check slot을 바꾸면 `llm_*_slot_ignored` warning으로 기록하고,
  final output은 deterministic slot을 사용한다.
- structured polish가 forbidden wording, `must_not_say`, required shape, card specificity 검증을
  통과하지 못하면 `unsafe_polish_fallback` warning과 함께 deterministic draft로 fallback한다.
- Live SGLang smoke에서 answerable preset은 `provider=sglang`을 유지했고, P0 grapefruit/statin
  preset은 `provider=deterministic`, `answerability=medical_decision_boundary`,
  `boundary_code:p0_grapefruit_statin`으로 LLM bypass를 유지했다.
- 검증:

```powershell
python -X utf8 -m pytest -q --no-cov backend\ai_agent_chat\tests
python -m ruff check backend\ai_agent_chat\src backend\ai_agent_chat\tests backend\scripts
python -m compileall backend\ai_agent_chat\src backend\scripts
git diff --check
```

결과: `168 passed, 1 skipped`, ruff pass, compileall pass, diff check pass.

## 항상 실행할 gate

작업 전:

```powershell
git -C ai-agent-backend-integration status --short --branch
git -C ai-agent-backend-integration diff --check
```

backend 최소 gate:

```powershell
python -X utf8 -m pytest -q --no-cov backend\ai_agent_chat\tests
python -m ruff check backend\ai_agent_chat\src backend\ai_agent_chat\tests backend\scripts
```

MEDICAL-WIKI full gate:

```powershell
python -X utf8 backend\scripts\eval_medical_wiki_chatbot.py --as-of 2026-06-10 --dry-run
python -X utf8 backend\scripts\eval_medical_wiki_evidence_bundles.py --as-of 2026-06-10 --dry-run
rg -n -i "raw prompt|raw llm response|raw ocr|provider payload|debug trace|base64 image|exif|api[_-]?key|secret|token" MEDICAL-WIKI\manifest\indexable_reviewed_claims.jsonl MEDICAL-WIKI\manifest\reviewed_claims.jsonl MEDICAL-WIKI\manifest\chatbot_answer_eval_inputs.jsonl MEDICAL-WIKI\manifest\evidence_bundle_adapter_fixtures.jsonl
```

PR hygiene:

- 명시 파일만 stage한다.
- mobile screenshot/profile artifact는 stage하지 않는다.
- `develop`에는 직접 push하지 않는다.
- GitHub PR comment에는 MEDICAL-WIKI sibling requirement, corpus 없는 CI skip, local full eval requirement, LangChain/vector DB/reranker/SGLang 미도입 여부, raw RAG가 아니라 reviewed claim/EvidenceBundle adapter임을 적는다.
