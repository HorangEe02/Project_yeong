# 25. LLM/RAG/Agent 고도화 시작 기준

> Status: start-gate decision
> 작성일: 2026-06-02
> 기준 worktree: `feat/ai-agent-backend-integration`
> 이전 문서: [23-agent-llm-pipeline-flow.md](./23-agent-llm-pipeline-flow.md),
> [24-post-merge-integration-blueprint.md](./24-post-merge-integration-blueprint.md)

## 1. 결론

LLM/RAG/Agent 고도화 시작 기준은 "팀 작업이 모두 완성됐는가"가 아니라
**우리가 의존하는 계약이 더 이상 자주 깨지지 않는가**로 잡는다.

권장 시점은 **계약 고정 후, 전체 병합 완료 전**이다. 즉, `develop` 통합과 Phase 0
history/root 정리를 기다리되, 기다리기만 하지 않고 고정된 API, DB, 출력 계약 위에서
LLM/RAG/Agent 작업을 병렬로 진행한다.

병합 실행은 [24-post-merge-integration-blueprint.md](./24-post-merge-integration-blueprint.md)의
Phase 0을 통과한 뒤에만 한다. 반면 reviewed evidence coverage, unknown backlog 승격,
retrieval eval, structured output 튜닝 같은 작업은 계약이 안정된 범위에서 먼저 시작할 수 있다.

## 2. 반드시 먼저 끝나야 하는 것

아래는 "고도화 작업 시작"보다 특히 "병합 실행" 전에 필요한 최소 조건이다.

| Gate | 기준 | 판정 방법 |
| --- | --- | --- |
| Phase 0 | OCR/backend 계열의 unrelated history 처리 방식 확정 | `merge-base` 감사 결과와 병합 전략이 문서화됨 |
| 통합 기준 브랜치 | `develop` 직접 push가 아니라 통합용 feature 브랜치와 PR 사용 | 브랜치명, PR 기준, explicit staging 기준 확인 |
| 최신 agent 산출물 공유 | agent 최신 문서/코드가 GitHub에 올라가 팀원이 같은 기준을 볼 수 있음 | 로컬 ahead/untracked 상태 해소 또는 publish 계획 확정 |
| chat API 계약 | `/api/v1/ai-agent/chat` 응답 shape가 additive contract로 고정 | route/mobile contract test |
| runtime smoke | Supabase/FastAPI/SGLang smoke가 최소 1회 통과한 상태 유지 | smoke script 결과 또는 릴리스 실행 리포트 |

`/api/v1/ai-agent/chat`에서 특히 고정해야 하는 필드는 다음이다.

- `answerability`
- `sources[]`
- `safety_warnings`
- `provider`
- raw prompt, raw OCR, raw LLM output, internal trace 비노출

## 3. 팀별 완성이 아니라 의존 가능 기준

각 파트는 최종 완성본이 아니라 **agent가 소비할 안정된 계약**을 먼저 제공하면 된다.

| 파트 | 의존 가능 기준 | 아직 최종 완성이 아니어도 되는 것 |
| --- | --- | --- |
| OCR/영양제 | 사용자 확인 후 저장되는 confirmed supplement 데이터 계약이 안정적 | OCR 정확도 100%, 모든 제품 커버리지 |
| Food/YOLO | `food_records` 또는 `FoodClassificationResult` shape가 고정되어 IntakeAgent가 받을 수 있음 | 최종 taxonomy/model 확정, 모바일 온디바이스 최적화 |
| 모바일 | `answerability`, `sources[]`, provider, CTA를 깨지 않고 표시/파싱 | 최종 UX, source detail sheet 완성 |
| DB/보안 | dev DB migration과 source governance table이 smoke 가능 | FORCE RLS 운영 전환, client direct DB access |
| LLM/RAG | reviewed evidence -> `AnswerCard` -> renderer -> SafetyGuard 흐름 고정 | 대규모 vector index, REFRAG, live web search |

## 4. 지금 바로 시작 가능한 작업

아래 작업은 팀 전체 병합이 끝나기 전에도 현재 계약 위에서 진행할 수 있다.

1. reviewed evidence coverage 확장
2. unknown backlog topic을 공식 source, evidence, boundary, golden test로 승격
3. `medical_rag_chunks` 설계와 hybrid retrieval eval set 작성
4. `AnswerCard` 기반 renderer 품질 개선
5. SGLang/OpenAI-compatible structured output schema 튜닝
6. `AgentRunLogger`와 `AgentMemoryWriter` DB 연결 설계
7. provider capability matrix와 fallback reason 관측성 정리

이 작업들은 모두 다음 원칙을 지킨다.

- LLM-WIKI 항목은 후보 자료일 뿐, 사용자-facing evidence가 아니다.
- 공식 source 또는 검수 자료로 승격되기 전에는 답변 범위를 넓히지 않는다.
- vector retrieval 결과도 prompt에 바로 넣지 않고 `AnswerCardNormalizer`를 통과한다.
- reviewed source가 없으면 `unknown_no_reviewed_source` 또는 boundary로 닫는다.

## 5. 아직 기다려야 하는 작업

아래 작업은 다른 파트의 계약 또는 병합 결과에 강하게 묶이므로 기다린다.

| 작업 | 기다리는 이유 |
| --- | --- |
| IntakeAgent 최종 로직 | 최종 food taxonomy/model과 식품성분 DB 매핑이 필요 |
| 모바일 온디바이스 YOLO/TFLite/CoreML 최적화 | 모델 선택, 크기, 정확도 하락, domain shift 검증이 필요 |
| FORCE RLS 운영 전환 | service role, `lemon_app` 권한, policy test가 필요 |
| source detail 최종 UI | 모바일 UX와 표시 정책 합의가 필요 |
| 운영용 대규모 vector index 구축 | reviewed chunk governance, eval, expiry/deprecation 정책이 먼저 필요 |

## 6. Go / Conditional Go / No-Go

### Go

다음이 모두 충족되면 LLM/RAG/Agent 고도화는 시작한다.

- API, DB, 응답 계약이 고정됐다.
- Supabase/FastAPI/SGLang smoke가 통과했다.
- reviewed evidence -> `AnswerCard` -> renderer -> SafetyGuard 경로가 테스트로 고정됐다.
- raw prompt/OCR/LLM output 비노출이 유지된다.

### Conditional Go

food/OCR 모델은 미완성이라도 다음 조건이면 adapter/fallback 기반으로 시작한다.

- 사용자 확인 후 저장되는 confirmed/persisted 데이터 shape가 있다.
- agent는 해당 shape를 optional context로 소비할 수 있다.
- missing/low-confidence 값은 `needs_more_info`, unknown, fallback으로 닫는다.

### No-Go

아래 중 하나라도 해당하면 병합 실행은 보류한다.

- 통합 기준 브랜치가 불명확하다.
- unrelated history 처리 방식이 미정이다.
- 최신 agent 문서/코드가 GitHub에 없고 publish 계획도 없다.
- `/api/v1/ai-agent/chat` 응답 계약이 아직 깨질 수 있다.
- smoke가 실패했는데 실패 원인과 다음 조치가 문서화되지 않았다.

## 7. 이번 기준의 가정

- 고도화의 1차 목표는 모델 성능 극대화가 아니라 **검수 근거 기반으로 안전하게 답하는 agent 경로 완성**이다.
- 팀 산출물은 최종 완성본이 아니라 안정된 계약 단위로 받아들인다.
- 최종 병합 전에도 agent/RAG 작업은 가능하지만, 병합 실행은 Phase 0 통과 후에만 한다.
- RAG/vector DB는 source governance와 `AnswerCard` gate를 대체하지 않는다.

## 8. 다음 PR 기준

다음 PR은 큰 통합 PR이 아니라 아래 중 하나로 좁힌다.

1. 문서/계약 PR: 이 기준 문서와 23/24번 문서 간 참조 정리
2. evidence coverage PR: unknown topic 하나를 source/version/evidence/boundary/golden/smoke 세트로 승격
3. retrieval eval PR: `medical_rag_chunks`, FTS, pgvector, RRF eval skeleton 추가
4. observability PR: raw-free fallback reason, unknown trend, source expiry report 강화

각 PR은 `git diff --check`, 관련 문서 재읽기, 그리고 해당 범위의 smoke 또는 focused test를 완료 조건으로 둔다.
