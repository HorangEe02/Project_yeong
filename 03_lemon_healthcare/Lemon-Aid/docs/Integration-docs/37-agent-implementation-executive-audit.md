# 37. Agent 구현 현황 총괄 감사

> 기준 시점: 2026-06-12 KST  
> 대상 worktree: `feat/ai-agent-backend-integration`  
> 관점: PM + 개발 총괄 팀장 관점의 기획 대비 구현 성숙도, 모듈/인터페이스, 품질, 보안, 성능, 운영 준비도 감사

## 1. 총괄 결론

현재 Lemon Aid Agent는 "아이디어 검증" 단계를 지나, 검수 근거 기반 건강 답변을
안전하게 닫는 핵심 runtime은 상당히 구현된 상태다. 특히 `reviewed claim ->
EvidenceBundle/AnswerCard -> renderer/LLM polish -> SafetyGuard` 축은 문서와 코드,
golden/eval/smoke 로그가 서로 맞물려 있다.

다만 제품 기획 전체인 "앱 맥락을 이해하고, 개인 건강 컨텍스트를 반영하며, 안전한
행동 제안과 운영 관측까지 갖춘 Agent" 기준으로 보면 아직 production 완료가 아니라
pre-production hardening 단계다. 핵심 의료 답변 안전성은 강하지만, 앱 DB context adapter,
CI 자동화, 부하/지연 성능 gate, 장애 알림/대시보드, 모듈 분리, PR 단위 운영 통제는 더
고정해야 한다.

한 줄 판정:

| 축 | 판정 | 이유 |
|---|---:|---|
| 기획 방향 부합 | 높음 | 수동 FAQ가 아니라 reviewed evidence를 `AnswerCard`로 정규화하고, 없으면 unknown으로 닫는 방향이 구현됨 |
| 핵심 의료 안전 runtime | 높음 | boundary/unknown/unsupported claim/SafetyGuard/LLM bypass 테스트와 로그가 축적됨 |
| 앱 맥락 기반 Agent | 중간 | `UserHealthContextSnapshot`와 app-record adapter가 진행 중이나, 현재 변경이 크고 아직 PR 안정화 대상 |
| 인터페이스/모듈 규격 | 중간 | 주요 seam은 존재하지만 `knowledge.py`, `ChatbotAgent`, `renderers.py`, `user_health_context.py`가 커지고 있음 |
| 테스트 자동화 | 중상 | 로컬 unit/integration/eval/smoke는 강함. 단, 이 worktree에 `.github/workflows`가 없어 CI 자동 감독은 약함 |
| 보안/개인정보 | 중상 | raw prompt/OCR/provider payload 차단, owner scoping, secret handling이 구현됨. 자동 보안 audit은 부족 |
| 성능/확장성 | 중간 | 현재 corpus 규모에서는 충분하지만, 검색/렌더링/컨텍스트 adapter의 선형 처리와 live latency gate가 약함 |
| 장애 예방/모니터링 | 중간 | preflight/smoke/trace에 더해 raw-free runtime metric report와 structured warning log가 구현됨. 운영 dashboard, 보존 정책, regression monitor는 아직 남음 |

## 2. 현재 구현 단계 지도

### 2.1 Agent 제품 목표 대비 단계

| 제품 능력 | 현재 단계 | 근거 | 남은 gate |
|---|---|---|---|
| 검수 지식 기반 답변 | 구현/검증됨 | `05` PRD, `06` TDD, `07` TODO, `AnswerCardNormalizer`, MEDICAL-WIKI adapter | reviewed claim/section 규모 확장, stale/source governance 지속 |
| 모르면 모른다고 답변 | 구현/검증됨 | `unknown_no_reviewed_source`, unknown backlog, unknown route tests | unknown backlog triage -> reviewed source 승격 운영 루프 |
| 의료 boundary 선차단 | 구현/검증됨 | P0 interaction, emergency, lab-value no-LLM tests | boundary taxonomy 확장, UI/QA 시나리오 확대 |
| LLM은 판단자가 아니라 polish | 1차 구현 | SGLang polish slot sealing, boundary LLM bypass, structured output fallback | answerable live 품질 평가, model 변경 regression |
| 앱 context 반영 | 진행 중 | `UserHealthContextSnapshot`, `ContextResolver`, app record snapshot builder 변경 | DB route wiring, consent/ownership integration, adapter contract doc |
| 개인화 memory | 일부 구현 | `agent_memory`, memory bundle, raw-free exclusion tests | conversation compaction, chat-derived memory write policy |
| checklist/action agent | 계획/부분 구현 | `30-agent-llm-todo.md` PR H/I/J 항목 다수 미완료 | action approval contract, no-side-effect-before-confirmation tests |
| observability/eval | 1차 구현 | sanitized trace, optional LangSmith exporter, dry-run eval export, runtime metric report/alert code | 운영 dashboard, trace 보존 정책, cloud/self-host upload 승인 gate |

### 2.2 최근 구현 흐름

최근 커밋 흐름은 구현 방향이 올바르게 좁혀지고 있음을 보여준다.

- `97c39a3 feat(ai): connect medical wiki reviewed claims`
- `d949368 feat(ai): consume medical wiki evidence bundles`
- `20b2bce feat(ai): add sanitized tracing and langsmith export gate`
- `9941651 fix(ai): tolerate sglang structured output formatting`
- `bea3582 fix(ai): seal sglang polish slots`

이 순서는 "지식 연결 -> evidence bundle 소비 -> 관측/평가 -> SGLang polish 안정화"로
이어져, 기획한 deterministic core 우선 방향과 맞다.

## 3. 인터페이스 및 모듈화 감사

### 3.1 잘 잡힌 seam

| seam | 현재 의미 | 긍정 판단 |
|---|---|---|
| `ChatTurnModule.plan()` | 한 Chat Turn의 intent, retrieval, answerability 결정 | LLM 호출 전 결정 경계가 분리되어 안전 정책을 고정하기 좋음 |
| `AnswerCard` / `AnswerCardNormalizer` | 검색된 reviewed evidence를 답변용 내부 프레임으로 표준화 | raw chunk나 FAQ card로 흐르지 않게 하는 핵심 interface |
| `MedicalKnowledgeRetriever` 계열 | seed/DB/MEDICAL-WIKI evidence를 카드로 공급 | adapter 교체가 가능하고 eval fixture 연결이 쉬움 |
| `CardAnswerRenderer` / `UnknownRenderer` / `BoundaryRenderer` | answerability별 출력 경로 분리 | fail-closed와 boundary UX를 독립 테스트하기 좋음 |
| `SafetyGuard` / `SafetyEnvelope` | 금지 표현, unsupported fact, numeric claim, trace 차단 | 의료 boundary의 마지막 출구 점검으로 적절함 |
| `AgentTraceSpan` / recorder / LangSmith exporter | raw-free 관측 이벤트 | 운영 관측을 agent core와 느슨하게 연결하는 방향이 좋음 |
| `UserHealthContextSnapshot` | 앱 context를 agent가 소비 가능한 형태로 축약 | raw app payload와 agent prompt를 분리하려는 방향이 맞음 |

### 3.2 모듈화 리스크

| 리스크 | 근거 | 영향 | 권장 조치 |
|---|---|---|---|
| `knowledge.py` 비대화 | 약 1,857 lines | 분류, source registry, seed knowledge, eval case가 한 파일에 몰림 | `classification`, `seed_registry`, `policy`, `eval_cases`로 단계적 분리 |
| `agents/chatbot.py` 비대화 | 약 1,211 lines | LLM request, fallback, renderer routing, trace, slot sealing, context formatting이 집중 | `llm_polish.py`, `prompt_builder.py`, `response_router.py` 후보 분리 |
| `renderers.py` 비대화 | 약 584 lines | boundary/card/general rendering과 source wording이 함께 증가 | answerability별 renderer 파일 분리 |
| `user_health_context.py` 급성장 | 현재 변경으로 약 688 lines | 앱 DB row folding 규칙이 한 파일에 집중되어 회귀 위험 | adapter contract doc + table별 mapper 함수 테스트 강화 |
| 문자열 기반 policy 증가 | answerability, warning code, source family가 문자열로 다수 사용 | 오타/불일치가 runtime에서 늦게 발견될 수 있음 | Literal/Enum, warning code registry, contract test 추가 |

판단: interface 방향은 맞지만 구현 파일의 locality가 약해지는 구간에 들어섰다. 지금은 큰
재작성보다 "새 변경이 닿는 부분부터 interface test를 먼저 고정하고, 이후 깊은 module로
옮기는" 방식이 안전하다.

## 4. 기술 부채 및 중복 코드

| 영역 | 상태 | 위험도 | 설명 |
|---|---|---:|---|
| legacy seed knowledge와 MEDICAL-WIKI adapter 공존 | 의도된 과도기 | 중간 | fallback/seed가 완전히 사라진 것이 아니므로 source precedence 규칙이 계속 필요 |
| answerability 문자열 중복 | 존재 | 중간 | `unknown_no_reviewed_source`, `medical_decision_boundary` 등이 여러 파일/테스트/문서에 반복 |
| source metadata formatting 중복 | 존재 | 중간 | source basis가 `ChatbotAgent`, `renderers`, API contract에 흩어짐 |
| raw-field denylist 중복 | 존재하지만 의도됨 | 낮음~중간 | `tracing`, `user_health_context`, `agent_memory`, exporter가 각각 차단 목록 보유. 보안상 중복은 괜찮지만 drift 감시 필요 |
| local smoke와 문서 로그 의존 | 존재 | 중간 | 검증 결과가 문서에 강하게 남아 있으나 CI로 자동 재현되는 수준은 부족 |

우선 제거할 중복은 raw denylist가 아니라 answerability/source/warning code registry다. raw
denylist는 보안 방어선이므로 중복 자체보다 "공통 forbidden marker test"로 drift를 잡는 편이
낫다.

## 5. 테스트 자동화 감독 상태

### 5.1 강한 부분

- `ai_agent_chat/tests`에 Chat Turn, chatbot, renderer, safety, SGLang client, tracing,
  LangSmith exporter, MEDICAL-WIKI adapter 테스트가 존재한다.
- `Nutrition-backend/tests/integration/api/test_ai_agent_api.py`가 route-level contract를
  검증한다.
- `backend/scripts/eval_chatbot_golden.py`, `eval_medical_wiki_chatbot.py`,
  `eval_medical_wiki_evidence_bundles.py`가 deterministic/evidence eval 경로를 제공한다.
- `36-medical-wiki-rag-execution-plan.md` 기준 최근 검증은 `168 passed, 1 skipped`, ruff,
  compileall, diff check pass로 기록되어 있다.
- `pyproject.toml`에는 ruff, black, mypy strict, pytest coverage 80% 기준이 정의되어 있다.
- `.pre-commit-config.yaml`에는 formatting, ruff, mypy, markdownlint, detect-secrets가 있다.

### 5.2 약한 부분

- 현재 worktree에는 `.github/workflows`가 없다. 프로젝트 문서에는 GitHub Actions가 언급되지만
  실제 branch 파일로 확인되지 않는다.
- `pytest --cov-fail-under=80` 설정은 있지만, 많은 로컬 검증 명령은 `--no-cov`를 사용한다.
- MEDICAL-WIKI sibling corpus가 필요한 테스트는 skip 전략이 필요하다. 이 전략은 계획 문서에
  있으나 CI에서 강제되는지는 아직 확인되지 않는다.
- SGLang live smoke, Supabase live smoke는 환경 의존성이 커서 자동 회귀 감시로는 약하다.

### 5.3 권장 test gate

PR마다 최소:

```powershell
python -X utf8 -m pytest -q --no-cov backend\ai_agent_chat\tests
python -X utf8 -m pytest -q --no-cov backend\Nutrition-backend\tests\integration\api\test_ai_agent_api.py
python -X utf8 backend\scripts\eval_medical_wiki_chatbot.py --as-of 2026-06-10 --dry-run
python -X utf8 backend\scripts\eval_medical_wiki_evidence_bundles.py --as-of 2026-06-10 --dry-run
python -m ruff check backend\ai_agent_chat\src backend\ai_agent_chat\tests backend\scripts
python -m compileall backend\ai_agent_chat\src backend\scripts
git diff --check
```

CI hardening PR:

- backend path filter로 위 명령 중 corpus 없는 CI에서 가능한 subset을 실행한다.
- MEDICAL-WIKI가 없으면 adapter unit은 skip하되, schema/contract unit은 항상 실행한다.
- live SGLang/Supabase는 nightly 또는 manual workflow로 분리한다.

## 6. 성능 저하 유발 코드 감사

| 후보 | 현재 위험 | 근거 | 권장 감시 |
|---|---:|---|---|
| in-process BM25-lite retrieval | 낮음~중간 | 현재 42/84/94 규모에서는 충분. claim/section이 커지면 선형 scan 부담 증가 | 500/1k/5k claim fixture latency benchmark |
| `ChatbotAgent` response path | 중간 | prompt build, renderer, safety, trace가 한 클래스 안에서 순차 실행 | per-span `latency_ms` 실제 기록/집계 |
| `UserHealthContextSnapshot` app record folding | 중간 | meal/supplement/analysis rows를 여러 mapping으로 조합 | row count cap, newest-first ordering, large payload fuzz test |
| SGLang live call | 중간 | timeout 기본 30~60초, answerable polish에만 사용 | provider latency SLO, fallback rate, timeout warning dashboard |
| structured output JSON extraction | 낮음~중간 | formatting tolerance가 최근 fix 대상 | malformed output regression set 유지 |

성능상 지금 당장 막힌 병목은 보이지 않는다. 하지만 corpus와 app context가 커지면 가장 먼저
문제될 곳은 retrieval scan과 app context folding이다.

## 7. 보안/개인정보 감사

### 7.1 강점

- `raw_prompt`, `raw_ocr_text`, `raw_provider_payload`, `debug_trace`, token 계열 field를
  차단하려는 denylist가 여러 계층에 있다.
- API route는 client `user_id`를 그대로 신뢰하지 않고 authenticated owner subject를 사용하는
  흐름이 보인다.
- agent memory는 owner subject hash 기반 접근과 raw/internal field exclusion을 갖는다.
- LangSmith exporter는 opt-in이고, SDK/API key 부재나 production block이 chat flow를 깨지
  않게 설계되어 있다.
- unknown backlog와 source detail contract는 raw question/source raw text를 사용자 artifact에
  노출하지 않는 테스트가 있다.

### 7.2 남은 위험

| 위험 | 등급 | 설명 | 권장 조치 |
|---|---:|---|---|
| LangSmith/cloud upload 승인 경계 | P1 | dry-run은 안전하지만 실제 업로드 정책/승인 절차는 아직 운영 gate | `LANGSMITH_EXPORT_ENABLED` production block + 승인 runbook |
| 자동 보안 audit 부족 | P1 | detect-secrets는 있으나 dependency audit, SAST, Bandit/pip-audit 계열 자동화가 보이지 않음 | CI에 `pip-audit` 또는 equivalent, Bandit scoped run 추가 |
| app context adapter raw field drift | P1 | 새 DB column이 생기면 raw denylist 우회 가능 | common forbidden marker fixture + recursive sanitizer contract |
| source governance 확대 | P1 | LLM-WIKI 내용은 직접 runtime 사용 금지. reviewed source 승격 절차 유지 필요 | claim-level review metadata/golden test 없이는 runtime 미반영 |

## 8. 장애 예방 및 모니터링 상태

현재 있는 것:

- `/health` endpoint.
- `check_ai_agent_runtime_prereqs.py`로 PostgreSQL, SGLang, Ollama, medical source readiness 확인.
- `smoke_ai_agent_server.py`로 FastAPI + PostgreSQL + SGLang + unknown backlog smoke.
- sanitized `AgentTraceSpan`, structured log recorder, optional LangSmith exporter.
- `build_runtime_metrics_report()`로 sanitized span만 집계해 request id, claim id, source id 없이
  운영 지표를 만든다.
- `StructuredLogRuntimeMetricsReporter`가 `agent_runtime_metrics` JSON log를 남기고,
  alert code가 있으면 `WARNING`, 없으면 `INFO`로 기록한다.
- unknown backlog report script.

부족한 것:

- 운영 SLO: p95 latency, unknown rate, boundary rate, fallback rate, unsafe polish fallback rate,
  retrieval no-match, stale source의 코드 기준 threshold 초안은 생겼다. 단, 최근 24h/주간 집계,
  baseline 비교, dashboard target은 아직 고정되어 있지 않다.
- 장애 alert: runtime warning log와 alert code는 생겼지만 Slack `#prod-alerts` 같은 실제
  alert routing rule 파일은 확인되지 않는다.
- regression monitor: MEDICAL-WIKI eval pass rate와 live smoke 결과를 정기적으로 저장/비교하는
  workflow가 없다.
- trace sink: structured log가 어디에 수집되는지, 보존 기간과 개인정보 정책이 아직 약하다.

현재 코드 기준 지표와 초안 threshold:

| Metric | 목적 | 경고 기준 초안 |
|---|---|---|
| `answerability_unknown_rate` | reviewed source gap 증가 감지 | 최근 24h 30% 초과 또는 전주 대비 2배 |
| `boundary_rate_by_code` | P0/응급 boundary 급증 감지 | 특정 code 급증 시 PM/의료 검토 |
| `llm_polish_fallback_rate` | SGLang 품질/timeout 문제 감지 | 10% 초과 |
| `unsafe_polish_fallback_count` | LLM output 안전 실패 감지 | 1건 이상이면 review |
| `retrieval_no_match_rate` | corpus coverage 문제 감지 | topic별 backlog 자동 생성 |
| `source_stale_count` | source governance 만료 감지 | 1건 이상이면 release block 후보 |
| `p95_chat_latency_ms` | UX 성능 감시 | target 미정. 우선 local baseline부터 수집 |

현재 구현된 alert code:

- `answerability_unknown_rate_high`
- `llm_polish_fallback_rate_high`
- `retrieval_no_match_rate_high`
- `unsafe_polish_fallback_present`
- `source_stale_present`
- `p95_chat_latency_high`

## 9. PM 관점 구현 성숙도

| Phase | 상태 | PM 판단 |
|---|---|---|
| 0. 기획/제품 철학 | 완료 | reviewed evidence 기반, unknown fail-closed, deterministic core 원칙이 명확함 |
| 1. 안전 답변 core | 완료에 가까움 | 의료 boundary와 SafetyGuard가 구현되어 demo/QA 가능한 수준 |
| 2. reviewed evidence 연결 | 구현됨 | MEDICAL-WIKI claim/EvidenceBundle adapter가 검증됨 |
| 3. 앱 context 연결 | 진행 중 | snapshot builder가 들어왔지만 route/DB 통합 안정화 필요 |
| 4. LLM runtime polish | 1차 완료 | SGLang이 판단자가 아니라 polish로 제한됨 |
| 5. 개인화 memory | 부분 완료 | raw-free memory와 bundle grounding은 있으나 compaction/chat-derived write는 남음 |
| 6. UI/API contract | 부분 완료 | API `sources[]`, answerability는 있으나 Flutter source detail/CTA/approval preview는 추가 검증 필요 |
| 7. 운영/관측 | 부분 완료 | trace/export/preflight와 runtime metrics warning log는 있으나 dashboard/retention/regression monitor는 아직 미흡 |
| 8. 팀 통합/릴리스 | 조건부 가능 | feature branch 기준 구현은 빠르게 전진했지만 CI/PR 자동 gate가 약함 |

## 10. 최우선 리스크 목록

| 우선순위 | 리스크 | 왜 중요한가 | 다음 조치 |
|---:|---|---|---|
| P0 | 현재 dirty 변경의 app context adapter 안정화 | 사용자 건강/식단/복약 context가 agent 답변 품질과 안전에 직접 영향 | targeted tests, route wiring 전 contract doc, diff review |
| P0 | CI workflow 부재 | 로컬 검증 로그가 좋아도 팀 통합 시 자동 감독이 약함 | backend agent CI workflow 추가 |
| P1 | `ChatbotAgent`/`knowledge.py` 비대화 | 안전 정책과 LLM polish 변경이 한 파일에서 충돌할 위험 | prompt/polish/router/registry 순서로 점진 분리 |
| P1 | 운영 observability 미완성 | runtime metric report와 warning log는 생겼지만 dashboard/routing/regression monitor가 없으면 장애나 hallucination regression을 늦게 볼 수 있음 | metric dashboard + alert routing + trace retention |
| P1 | source governance 운영 루프 | unknown backlog가 쌓여도 reviewed source로 승격되지 않으면 coverage 정체 | backlog triage -> claim review -> golden update runbook |
| P2 | performance/load gate 없음 | corpus와 app context 확장 후 latency 악화 가능 | retrieval/context folding benchmark |
| P2 | dependency/security audit 미흡 | 의료/개인정보 앱으로서 release gate 부족 | pip-audit/Bandit/secret scan CI |

## 11. 다음 실행 순서

### 11.1 바로 해야 할 것

1. 현재 `user_health_context.py` app record adapter 변경을 별도 PR 단위로 안정화한다.
2. `backend/ai_agent_chat/tests/test_user_health_context.py`를 먼저 통과시킨 뒤 전체
   `ai_agent_chat` 테스트를 다시 돌린다.
3. `37` 문서와 `36` 상태가 서로 충돌하지 않는지 확인한다.
4. 이 branch에 CI workflow가 없는 이유를 확인하고, 최소 agent CI workflow를 만든다.

### 11.2 다음 PR 후보

| PR | 목표 | 완료 기준 |
|---|---|---|
| PR-Context | app DB records -> `UserHealthContextSnapshot` adapter 확정 | raw-free tests, inactive row tests, route wiring contract |
| PR-CI | Agent backend CI 자동화 | ruff, compileall, core tests, corpus skip strategy |
| PR-Observability | sanitized trace 운영화 | metric report/warning log 구현됨. 남은 기준은 dashboard, alert routing, retention/runbook |
| PR-Modularize | `ChatbotAgent` 분리 1차 | behavior no-change tests 유지, prompt/polish helper 분리 |
| PR-UnknownLoop | unknown backlog -> reviewed claim workflow | triage report, source review checklist, golden test addition |

## 12. 감사 체크리스트

| 항목 | 상태 | 비고 |
|---|---|---|
| 기획한 Agent 철학 반영 | 통과 | deterministic core + bounded LLM |
| 모든 건강 답변이 reviewed card/boundary/unknown 중 하나 | 대체로 통과 | TODO/log/test 근거 있음 |
| raw prompt/OCR/provider payload 노출 차단 | 대체로 통과 | 중복 denylist + tests. drift 감시 필요 |
| app context adapter 규격 | 진행 중 | 현재 dirty 변경이 핵심 |
| source metadata `sources[]` 공개 계약 | 통과 | route-level tests 기록 |
| local test/eval/smoke | 강함 | 최근 168 passed 기록 |
| CI 자동 감독 | 미흡 | `.github/workflows` 확인 안 됨 |
| 성능 자동 회귀 | 미흡 | benchmark/SLO 없음 |
| 보안 자동 audit | 미흡 | detect-secrets 외 dependency/SAST 약함 |
| 장애 모니터링 | 부분 | health/preflight/smoke/trace/runtime metric warning log 있음, dashboard/routing/retention 없음 |
| 모듈화 | 주의 | interface는 좋지만 파일 비대화 |
| 중복 코드 | 주의 | answerability/source/warning code registry 필요 |

## 13. 최종 판정

Lemon Aid Agent는 "처음 기획한 방향대로 가고 있는가?"라는 질문에는 예, 꽤 정확히 가고
있다고 답할 수 있다. 특히 의료/영양/복약 답변을 LLM 일반 지식에 맡기지 않고, 검수 지식
안에서만 답하고, 없으면 unknown으로 닫는 핵심 방향은 구현과 테스트가 따라왔다.

하지만 "이제 운영 서비스로 안정적으로 굴릴 수 있는가?"라는 질문에는 아직 조건부다.
다음 병목은 새로운 모델이 아니라 운영 discipline이다. CI, trace/metric, source promotion,
app context contract, 파일 비대화 관리를 잡으면 현재 구현은 production candidate로 올릴 수
있다.
