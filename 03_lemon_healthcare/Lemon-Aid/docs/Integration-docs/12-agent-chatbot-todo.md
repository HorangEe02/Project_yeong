# 12. 앱 컨텍스트 기반 에이전트 & 챗봇 TODO

> Status: design-confirmed TODO
> 작성일: 2026-05-31
> 기준 worktree: `feat/ai-agent-backend-integration`
> 관련 문서:
> - [05-grounded-chatbot-prd.md](./05-grounded-chatbot-prd.md)
> - [06-grounded-chatbot-tdd.md](./06-grounded-chatbot-tdd.md)
> - [07-grounded-chatbot-todo.md](./07-grounded-chatbot-todo.md)
> - [08-grounded-chatbot-trd.md](./08-grounded-chatbot-trd.md)
> - [09-grounded-chatbot-implementation-log.md](./09-grounded-chatbot-implementation-log.md)
> - [10-grounded-chatbot-gap-review.md](./10-grounded-chatbot-gap-review.md)
> - [13-agent-chatbot-release-todo.md](./13-agent-chatbot-release-todo.md)

> 이 문서는 앱 컨텍스트 기반 건강 에이전트/챗봇 v1 구현 기준선입니다. 다음 릴리스 안정화,
> PR 분리, 운영 smoke, reviewed evidence coverage 확장 TODO는
> [13-agent-chatbot-release-todo.md](./13-agent-chatbot-release-todo.md)에서 관리합니다.

## 1. 확정 방향

Lemon Aid의 AI는 FAQ 챗봇이 아니라 **앱 전체 상태를 읽는 개인화 건강 에이전트**로 만든다.

```text
사용자 질문
→ 사용자 앱 컨텍스트 로드
→ 필요한 구조화 기록 추가 조회
→ 검수 evidence 검색
→ AnswerPlan / AnalysisPlan 생성
→ SafetyBoundary 확인
→ 챗봇 또는 분석 탭 renderer 출력
→ CTA / 기록 저장 / 분석 갱신 제안
```

기존 `AnswerCard` 방향은 유지하되, `AnswerCard`는 최종 답변 틀이 아니라 검수된 지식 재료로 사용한다. 그 위에 `AnswerPlan` / `AnalysisPlan`을 두어 사용자의 기록, 분석 결과, 영양제, 체크리스트, 질문 흐름에 맞게 답변 구조를 먼저 만든다.

## 2. 설계 원칙

- 질환명을 코드 범위로 고정하지 않는다.
  - `diabetes`, `hypertension` 같은 질환명은 예시일 뿐이다.
  - 런타임 구조는 `health_axes`, `risk_flags`, `nutrition_targets`, `medication_context`, `supplement_context`, `behavior_context`, `safety_boundary` 중심으로 둔다.
- 챗봇과 분석 탭은 같은 planning layer를 공유한다.
  - 챗봇 탭은 대화형 전문가 코칭으로 출력한다.
  - 분석 탭은 카드, 점수, 섹션, 체크리스트 UI로 출력한다.
- LLM은 최종 표현을 돕는 역할이다.
  - 사용자 건강 사실, 의료 판단, 복약 가능 여부, 검사수치 해석을 새로 만들지 않는다.
  - structured output은 `AnswerPlan` 또는 최종 section 생성에만 사용한다.
- 음식은 v1에서 정확한 영양성분 계산보다 태그 기반으로 빠르게 시작한다.
  - 나중에 음식 DB 매칭과 `nutrient_estimates`를 붙일 수 있게 필드는 열어둔다.
- 영양제는 기존 영양제 파트의 confirmed schema를 소비한다.
  - OCR preview는 근거가 아니다.
  - 사용자 확인된 라벨과 allowlisted `nutrient_code`만 강하게 반영한다.
- 검수 evidence가 없으면 지어내지 않는다.
  - unknown 답변과 backlog 기록으로 넘긴다.

## 3. Phase 1. 공통 사용자 컨텍스트 계약

### TODO

- [x] `UserHealthContextSnapshot` 계약을 정의한다.
  - `user_profile_summary`
  - `today_analysis_snapshot`
  - `health_analysis_snapshot`
  - `active_supplement_snapshot`
  - `recent_food_and_checklist_snapshot`
  - `chat_derived_health_signals`
  - `visible_analysis_context`
- [x] 챗봇 호출 전 항상 snapshot을 로드하는 service를 만든다.
- [x] snapshot에 raw prompt, raw OCR, raw chat transcript, raw LLM output을 넣지 않도록 테스트한다.
- [x] `ContextResolver`를 추가한다.
  - 기본 snapshot으로 충분한 질문인지 판단한다.
  - 부족하면 필요한 구조화 DB만 추가 조회한다.
  - DB에도 없으면 `needs_more_info` 또는 `unknown_no_reviewed_source`로 넘긴다.

### Acceptance

- 챗봇은 매 답변 전에 사용자 앱 상태를 읽는다.
- 일반 질문도 사용자 맥락을 가볍게 연결할 수 있다.
- 특정 날짜/식사/영양제 조회는 snapshot 전체 dump가 아니라 필요한 DB 조회로 처리한다.

## 4. Phase 2. 음식 기록 v1

### TODO

- [x] `FoodRecordSnapshot v1` schema를 정의한다.
  - `food_record_id`
  - `recorded_date`
  - `meal_type`: `breakfast | lunch | dinner | snack | extra`
  - `display_items`
  - `amount_text`
  - `estimated_tags`
  - `rough_nutrient_axes`
  - `user_confirmed`
  - `source`
  - `food_db_match_id`
  - `match_confidence`
  - `nutrient_estimates`
- [x] 음식 기록 DB 테이블과 migration을 추가한다.
- [x] 음식 기록 CRUD API를 추가한다.
- [x] 음식명 기반 자동 태그 추정기를 추가한다.
  - 예: 라면 -> `sodium_high`, `refined_carb`, `soup_or_stew`
  - 예: 흰쌀밥 -> `carbohydrate_high`
  - 예: 닭가슴살 -> `protein_food`
- [x] 사용자가 음식명, 양, 끼니, 자동 태그를 수정할 수 있게 API 계약을 둔다.
- [x] `food_db_match_id`, `match_confidence`, `nutrient_estimates`는 v1에서 nullable로 둔다.

### Acceptance

- 음식 DB 매칭 없이도 챗봇이 오늘 식사 흐름을 말할 수 있다.
- 나중에 식품 DB를 붙여도 기존 기록 구조를 갈아엎지 않는다.
- “채소/단백질 드세요” 대신 실제 음식 후보를 낼 수 있다.

## 5. Phase 3. 영양제 snapshot 연결

### TODO

- [x] 기존 `user_supplements` / confirmed supplement 흐름을 읽는 adapter를 만든다.
- [x] 오늘 체크된 영양제와 등록 영양제를 분리해 snapshot에 넣는다.
- [x] `nutrient_code`가 있는 성분만 표준 영양성분 분석에 강하게 사용한다.
- [x] `nutrient_code`가 없는 성분은 확인된 라벨 정보로만 언급한다.
- [x] OCR preview 또는 사용자 미확인 라벨은 분석/챗봇 판단에 강하게 반영하지 않도록 테스트한다.
- [x] 의약품처럼 보이는 입력은 supplement answer flow가 아니라 medication boundary로 보낸다.

### Acceptance

- 챗봇은 제품 자체를 검수한 것처럼 말하지 않는다.
- 제품/브랜드/용량/복용 시작 결정을 추천하지 않는다.
- 검수 evidence가 있는 성분 단위 설명만 허용한다.

## 6. Phase 4. AnswerPlan / AnalysisPlan

### TODO

- [x] `AnswerPlan` schema를 정의한다.
  - `intent`
  - `answer_depth`
  - `context_used`
  - `personalization_level`
  - `readiness_level`
  - `problem_axes`
  - `nutrient_priorities`
  - `food_first_actions`
  - `supplement_considerations`
  - `behavior_actions`
  - `safety_boundaries`
  - `source_basis`
  - `ctas`
  - `must_not_say`
- [x] `AnalysisPlan` schema를 정의한다.
  - `score_status`
  - `score`
  - `readiness_level`
  - `strengths`
  - `priority_adjustments`
  - `nutrient_priorities`
  - `recommended_foods`
  - `checklist_actions`
  - `missing_records`
  - `safety_boundaries`
  - `ctas`
- [x] 기존 `AnswerCard`는 `AnswerPlan`의 evidence 재료로 연결한다.
- [x] 질환명 literal 중심 타입을 줄이고 generic `health_axes` / `risk_flags` 구조로 옮긴다.
- [x] structured output은 plan 또는 section JSON 생성에 적용한다.
- [x] schema parse 실패, 금지 표현, unsupported fact 감지 시 deterministic fallback으로 전환한다.

### Acceptance

- 답변 품질은 카드 문구 고정이 아니라 `AnswerPlan` 품질로 결정된다.
- 같은 근거라도 질문 흐름과 사용자 기록에 따라 다른 우선순위로 답할 수 있다.
- `AnswerPlan`에 없는 건강 사실을 LLM이 추가하지 않는다.

## 7. Phase 5. Renderer 분리 확장

### TODO

- [x] `ChatRenderer`를 만든다.
  - 기본 답변은 짧은 전문가 코칭으로 유지한다.
  - 6개 요소를 기본으로 한다.
    - 현재 기록/상황 요약
    - 핵심 건강축 또는 영양축
    - 오늘 먹을 수 있는 음식 후보
    - 줄일 음식/습관
    - 오늘 할 행동
    - 위험/복약/검사수치 boundary
- [x] `AnalysisRenderer`를 만든다.
  - 같은 plan을 분석 탭 카드/섹션/점수/체크리스트 UI로 변환한다.
- [x] 기존 filler 문구를 금지한다.
  - “현재 확인된 기록을 기준으로 답변드릴 수 있습니다.”
  - “확정된 식사, 영양제, 건강 기록을 먼저 확인해 주세요.”
  - “공식자료와 확인된 기록을 기준으로 일반적인 건강관리 범위에서 조절하세요.”
- [x] meal recommendation은 한국식 실제 식사 예시를 기본값으로 둔다.
- [x] 사용자가 “자세히”, “왜”, “식단 짜줘”, “영양제까지 봐줘”라고 하면 확장 depth로 전환한다.

### Acceptance

- 일반 답변은 5~8문장 수준으로 핵심적이다.
- 식단 답변에는 분류어만 나오지 않고 실제 음식과 조리/섭취 방식이 나온다.
- 분석 탭과 챗봇 탭은 같은 판단을 다른 UI로 보여준다.

## 8. Phase 6. 오늘의 분석

### TODO

- [x] `today_analysis_snapshot` 저장 구조를 정의한다.
- [x] 점수명을 `오늘 현재 분석 점수`로 고정한다.
- [x] 점수 설명을 `기록 기반 생활관리 점수`로 고정한다.
- [x] 최소 분석 조건을 구현한다.
  - 등록 영양제가 있는 사용자: 오늘 식사 1개 이상 + 오늘 체크된 영양제 1개 이상
  - 등록 영양제가 없는 사용자: 오늘 식사 1개 이상
- [x] 최소 조건 미달 시 낮은 점수를 주지 않고 `analysis_pending`으로 둔다.
- [x] 오늘의 분석은 하루 최종 평가가 아니라 현재까지 등록된 기록 기준 분석으로 만든다.
- [x] 새 음식, 영양제 체크, 체크리스트 변경 시 snapshot stale 처리한다.

### Acceptance

- 아침 식사와 아침 영양제만으로도 현재까지의 분석을 실행할 수 있다.
- 기록이 부족하면 정직하게 분석 대기를 보여준다.
- 점수가 건강상태/질병위험 점수처럼 보이지 않는다.

## 9. Phase 7. 건강 분석

### TODO

- [x] `health_analysis_snapshot` 저장 구조를 정의한다.
- [x] 건강 분석 성숙도 단계를 구현한다.
  - `level_0_preparing`
  - `level_1_initial`
  - `level_2_recent_pattern`
  - `level_3_personal_baseline`
  - `level_4_long_term`
- [x] 영역별 coverage를 분리한다.
  - `food`
  - `supplement`
  - `checklist`
  - `chat_signals`
- [x] 분석 결과에 `strengths`를 반드시 포함한다.
  - 챗봇 기본 답변: 1~2개
  - 분석 탭 상세: 최대 3개
- [x] `priority_adjustments`에는 부족/과잉 영양축과 행동 우선순위를 넣는다.
- [x] 채팅 기록은 아래 세 단계로 반영한다.
  - `confirmed_from_chat`
  - `user_reported_signal`
  - `conversation_context_only`

### Acceptance

- 초기 사용자에게 과하게 장기 패턴처럼 말하지 않는다.
- 기록이 쌓일수록 개인 기준선과 장기 패턴을 더 강하게 반영한다.
- 잘하고 있는 행동과 바꿀 행동을 함께 제시한다.

## 10. Phase 8. 분석 실행과 CTA

### TODO

- [x] 챗봇에서 분석 실행 의도를 감지한다.
- [x] 분석 실행 전 항상 사용자 확인을 받는다.
  - 오늘의 분석: “오늘 등록된 음식, 오늘 체크된 영양제, 오늘 체크리스트를 기준으로 오늘의 분석을 실행할까요?”
  - 건강 분석: “누적 식사 기록, 등록/섭취 영양제, 체크리스트, 최근 채팅에서 확인된 건강 신호를 기준으로 건강 분석을 실행할까요?”
- [x] 사용자가 승인하면 같은 `AnalysisService`를 호출한다.
- [x] 챗봇에서 실행한 분석 결과도 분석 탭 snapshot으로 저장한다.
- [x] CTA contract를 정의한다.
  - `complete_missing_record`
  - `run_or_refresh_analysis`
  - `add_checklist_item`
  - `ask_about_this_result`
- [x] 체크리스트 추가는 바로 저장하지 않고 편집 화면/모달을 거친다.
- [x] “이 결과로 질문하기”는 사용자가 본 분석 결과 visible content를 챗봇 context로 넘긴다.
- [x] “이 결과로 질문하기” 후에도 최신 DB/snapshot을 다시 확인한다.

### Acceptance

- 챗봇은 사용자 확인 없이 분석을 실행하거나 기록을 저장하지 않는다.
- 분석 탭과 챗봇 탭의 결과가 서로 따로 놀지 않는다.
- CTA는 최대 2개 중심으로 노출한다.

## 11. Phase 9. Safety, Unknown, Evidence

### TODO

- [x] `unknown_no_reviewed_source`는 원문 없이 구조화 topic만 backlog에 남긴다.
- [x] 복약, 검사수치, 진단, 치료, 응급 질문은 `SafetyBoundary`가 우선한다.
- [x] reviewed evidence가 없는 약물/영양제/질환 조합은 병용 가능 여부를 판단하지 않는다.
- [x] supplement OCR label은 evidence가 아니라 사용자 제품 정보로 취급한다.
- [x] LLM-WIKI 자료는 사용자 답변에 바로 쓰지 않고 source governance를 통과한 뒤 evidence로 승격한다.
- [x] source metadata와 만료일, review status, 금지 표현을 계속 검증한다.

### Acceptance

- 모르는 질문에 그럴듯한 일반 LLM 답변을 만들지 않는다.
- unknown 답변도 “왜 답할 수 없는지, 무엇을 확인해야 하는지”를 안내한다.
- 개인정보성 free text, raw prompt, raw OCR은 backlog나 prompt에 저장하지 않는다.

## 12. Golden Test Set

### TODO

- [x] 고혈당/과식 후 저녁 추천 follow-up case를 추가한다.
- [x] 나트륨 높은 식사 후 다음 끼니 case를 추가한다.
- [x] 영양제 라벨 확인 후 성분 기준 설명 case를 추가한다.
- [x] `nutrient_code` 없는 성분 label-only case를 추가한다.
- [x] 음식 기록이 부족한 날 분석 대기 case를 추가한다.
- [x] 오늘 분석 최소 조건 충족 case를 추가한다.
- [x] 건강 분석 성숙도 level별 case를 추가한다.
- [x] “이 결과로 질문하기” 후 새 기록이 추가된 stale case를 추가한다.
- [x] 복약/영양제 reviewed evidence 없음 unknown case를 추가한다.
- [x] filler 문구 금지 regression test를 추가한다.

### Required quality checks

- 식단 추천은 실제 음식 후보를 포함한다.
- 부족/과잉 영양축은 상위 3~5개를 우선순위화한다.
- 핵심 1~2개 영양축은 음식 후보까지 구체화한다.
- 영양제는 성분 후보 수준까지만 말한다.
- 제품명/브랜드/용량/복용 시작을 추천하지 않는다.
- 검사수치/처방/복용량/병용 가능 여부를 단정하지 않는다.

## 13. 구현 PR 제안 순서

1. **PR A. 문서 계약 정리**
   - PRD/TRD/TDD에 앱 컨텍스트 기반 agent 방향 반영
   - 이 TODO와 기존 `07-grounded-chatbot-todo.md`의 관계 정리
2. **PR B. UserHealthContextSnapshot**
   - snapshot schema/service/test
   - ContextResolver 초안
3. **PR C. FoodRecordSnapshot v1**
   - DB/API/schema/tagger/test
4. **PR D. SupplementSnapshot adapter**
   - confirmed supplement read adapter
   - nutrient_code / label-only policy test
5. **PR E. AnswerPlan / AnalysisPlan**
   - generic health axes 기반 plan schema
   - existing AnswerCard evidence 연결
6. **PR F. Renderer 확장**
   - ChatRenderer / AnalysisRenderer
   - filler 문구 제거
7. **PR G. Today/Health Analysis**
   - 오늘 현재 분석 점수
   - 건강 분석 성숙도
   - strengths / missing record / CTA
8. **PR H. End-to-end QA**
   - golden tests
   - FastAPI route tests
   - Flutter contract tests
   - Supabase smoke

## 14. 완료 정의

- 챗봇이 사용자 앱 컨텍스트를 매번 읽는다.
- 분석 탭과 챗봇 탭이 같은 plan layer를 공유한다.
- 음식 기록 v1이 태그 기반으로 동작한다.
- 영양제는 confirmed supplement만 강하게 반영한다.
- 오늘 분석 점수와 건강 분석 성숙도가 구현된다.
- 답변은 짧고 전문적이며 실제 음식/행동 후보를 포함한다.
- reviewed evidence 없는 건강 판단은 unknown/boundary로 닫힌다.
- 모든 새 계약은 unit/integration/golden test로 고정된다.
