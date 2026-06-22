# 30. Agent/LLM TODO

> Status: implementation TODO draft
> 작성일: 2026-06-04
> PRD: [27-agent-llm-prd.md](./27-agent-llm-prd.md)
> TRD: [28-agent-llm-trd.md](./28-agent-llm-trd.md)
> TDD: [29-agent-llm-tdd.md](./29-agent-llm-tdd.md)
> 기준 worktree: `feat/ai-agent-backend-integration`

## 1. 작업 원칙

- 기존 구현을 지우고 새로 만들지 않는다.
- 기존 grounded chatbot 경로를 유지하면서 memory, smart analysis, checklist, boundary를
  좁은 PR로 확장한다.
- 각 PR은 문서, 코드, 테스트를 함께 포함한다.
- raw prompt, raw OCR, raw LLM output, raw image는 memory와 사용자 응답에 넣지 않는다.
- 공식 앱 기록 변경은 사용자 승인 후에만 한다.

## 2. PR A. 문서 체인 정리

목표: 26~30번 문서를 기준 체인으로 고정한다.

TODO:

- [x] 26번 방향 재정리 문서 작성
- [x] 27번 PRD 작성
- [x] 28번 TRD 작성
- [x] 29번 TDD 작성
- [x] 30번 TODO 작성
- [ ] 기존 05/06/08/12 문서와 새 26~30 문서의 관계를 상단에 명시
- [ ] 용어 매핑 표 추가: `health_analysis_snapshot` ↔ `smart_analysis_snapshot`
- [x] docs index 갱신

검증:

- [x] `python scripts/update_docs_index.py --write ai-agent-backend-integration\docs\Integration-docs`
- [x] `git diff --check`

## 3. PR B. Agent memory schema

목표: 사용자별 memory 4종을 저장하고 조회할 최소 계약을 만든다.

TODO:

- [x] `agent_memory_records` DB 모델 또는 repository 계약 정의
- [x] `profile_memory`, `behavior_memory`, `conversation_memory`, `safety_memory` enum 정의
- [x] `confidence`, `source_kind`, `source_ref`, `priority`, `review_after`, `expires_at` 필드 정의
- [x] raw chat archive와 agent memory를 분리한 설계 테스트 추가
- [x] raw prompt가 memory로 들어가지 않는 negative test 추가

검증:

- [x] memory model unit test
- [x] memory repository unit test
- [x] raw/internal field exclusion test

구현 메모:

- Day 2 범위에서는 새 migration을 만들지 않고 기존 `agent_memory` table의
  `memory_type`, `summary_json`, `source_counters`를 사용한다.
- `backend/Nutrition-backend/src/services/agent_memory.py`에 4종 memory type contract와
  `upsert_agent_memory_record()`를 추가했다.
- `load_agent_memory_context()`는 기존 v0 `summaries`를 유지하면서 4종 memory만
  `memory_bundle`으로 그룹화한다.
- raw transcript, raw prompt, raw OCR, raw LLM response, provider payload, messages key는
  저장/조회 memory context에서 제거한다.

## 4. PR C. Conversation memory compaction

목표: raw chat 전체를 prompt memory로 쓰지 않고 핵심 요약만 유지한다.

TODO:

- [ ] 최근 N턴 기준 conversation summary 생성기 작성
- [ ] 대화 길이 한계 초과 시 rolling summary 갱신
- [ ] 선호, 관심사, 답변 길이, 반복 질문을 `conversation_memory`로 추출
- [ ] 복약/질환/검사수치 언급은 `safety_memory` 후보로 분리
- [ ] summary prompt에 raw prompt/provider payload가 섞이지 않도록 방지

검증:

- [ ] conversation compaction test
- [ ] preference extraction test
- [ ] safety-relevant mention extraction test
- [ ] raw prompt exclusion test

## 5. PR D. Chat-derived memory boundary

목표: 채팅 정보는 memory에 반영하되 공식 앱 기록을 자동 수정하지 않는다.

TODO:

- [ ] "혈압약 먹고 있어" 같은 발화를 `safety_memory` user_reported로 저장
- [ ] 공식 `user_medications` DB에는 자동 등록하지 않도록 테스트
- [ ] 복약/질환/검사수치 발화에는 등록/확인 CTA 제공
- [ ] memory confidence에 따른 답변 표현 규칙 추가

검증:

- [ ] chat-derived medication memory test
- [ ] no official record auto-write test
- [ ] registration CTA contract test

## 6. PR E. Food/supplement algorithm adapter audit

목표: 팀원이 만든 음식/영양제 알고리즘 결과가 agent context로 안정적으로 들어오는지 확인한다.

TODO:

- [ ] 음식 알고리즘 산출물 필드 확인: 음식명, g/인분, 칼로리, 영양성분, confidence
- [ ] 영양제 알고리즘 산출물 필드 확인: 성분, 함량, 단위, nutrient_code, confirmed status
- [ ] OCR preview와 confirmed record 경계 테스트
- [ ] agent context에는 confirmed record만 강하게 반영
- [ ] 누락 필드와 임시 fallback 문서화

검증:

- [ ] food algorithm adapter test
- [ ] supplement confirmed adapter test
- [ ] OCR preview exclusion test

## 7. PR F. Smart analysis score contract

목표: `스마트 생활관리 점수`를 질병 위험이 아닌 생활관리 안정도 점수로 정의한다.

TODO:

- [ ] `smart_analysis_snapshot` schema 정의
- [ ] 기존 `health_analysis_snapshot` 호환 계층 정의
- [ ] 누적 기록, 체크리스트 수행률, 거절 항목, 반복 패턴, memory 입력 정의
- [ ] 점수 산식 v1 작성
- [ ] 금지/권장 UI copy 테스트 추가
- [ ] 스마트 분석 readiness level 정의

검증:

- [ ] smart analysis snapshot unit test
- [ ] score wording negative test
- [ ] readiness level test

## 8. PR G. Today analysis wording hardening

목표: `오늘 현재 분석 점수`가 건강 판정처럼 보이지 않게 고정한다.

TODO:

- [ ] 오늘 분석 score name과 description 고정
- [ ] 기록 부족 시 `analysis_pending` 유지
- [ ] "건강이 좋아졌다", "질병 위험이 낮아졌다" 금지 문구 테스트
- [ ] 오늘 대화 맥락을 낮은 강도로 반영하는 규칙 추가

검증:

- [ ] today analysis minimum condition test
- [ ] pending state test
- [ ] forbidden wording test

## 9. PR H. Checklist planner

목표: 기본 1~3개와 확장 모드 체크리스트 후보를 생성한다.

TODO:

- [ ] `ChecklistPlanner` 인터페이스 정의
- [ ] 기본 모드 후보 1~3개 제한
- [ ] 확장 모드 카테고리 정의: 식사, 영양제, 활동, 기록, 복약 주의
- [ ] 후보와 실제 저장 항목 분리
- [ ] 의료/복약 체크리스트를 확인/기록/상담 준비로 제한
- [ ] 수행률, 거절, 반복 실패, 선호 시간대 memory update hook 추가

검증:

- [ ] checklist candidate limit test
- [ ] expanded mode test
- [ ] selected-only persistence test
- [ ] behavior memory update test
- [ ] medical checklist safety wording test

## 10. PR I. Action approval contract

목표: 저장, 알림, 분석 실행, 체크리스트 추가가 사용자 확인 후 실행되게 한다.

TODO:

- [ ] action preview schema 정의
- [ ] `requires_user_confirmation`와 `will_persist` 필드 고정
- [ ] 분석 실행 전 confirmation payload 반환
- [ ] 체크리스트 추가 전 선택 UI/CTA 계약 정의
- [ ] 알림 등록 전 확인 계약 정의

검증:

- [ ] run analysis confirmation test
- [ ] add checklist confirmation test
- [ ] reminder confirmation test
- [ ] no side effect before confirmation test

## 11. PR J. BoundaryPlan and explanatory renderer

목표: boundary 답변을 "못 답함"이 아니라 "결정 금지 안에서 자세히 설명"으로 개선한다.

TODO:

- [ ] `BoundaryPlan` 타입 정의
- [ ] 응급/위험 질문 설명형 renderer 구현
- [ ] 검사수치/치료 판단 설명형 renderer 구현
- [ ] 약/영양제 병용 설명형 renderer 구현
- [ ] 사용자 memory 기반 위험 맥락 연결
- [ ] 진단/치료/복용량/병용 가능 여부 단정 금지 검증

검증:

- [ ] emergency explanatory boundary test
- [ ] lab value boundary test
- [ ] medication supplement boundary test
- [ ] forbidden decision wording test

## 12. PR K. Reviewed evidence and RAG eval

목표: RAG를 source governance 뒤에 안전하게 붙이기 위한 평가 기반을 만든다.

TODO:

- [ ] `medical_rag_chunks` 또는 equivalent chunk contract 점검
- [ ] reviewed/not stale/user-facing allowed gate 적용
- [ ] retrieval eval set 작성
- [ ] 검색 결과를 `AnswerCardNormalizer`에만 전달
- [ ] normalizer 실패 시 후보 폐기
- [ ] unknown topic -> safe backlog -> evidence 승격 루프 문서화

검증:

- [ ] retrieval gate test
- [ ] answer card normalization test
- [ ] stale source exclusion test
- [ ] unknown backlog test

## 13. PR L. Mobile response contract

목표: Flutter가 answerability, source, CTA, analysis snapshot, approval preview를 안정적으로 표시한다.

TODO:

- [ ] chat response DTO에 `ctas[]` 확인
- [ ] approval preview 표시 계약 추가
- [ ] 오늘/스마트 분석 snapshot 표시 계약 추가
- [ ] source detail 표시와 stale/unknown 상태 표시 확인
- [ ] raw/internal field 비노출 테스트

검증:

- [ ] mobile DTO compatibility test
- [ ] source display contract test
- [ ] approval preview UI contract test

## 14. PR M. End-to-end golden tests

목표: 사용자가 기대하는 대표 흐름을 회귀 테스트로 고정한다.

TODO:

- [ ] 라면 점심 후 저녁 추천
- [ ] 혈압약 언급 + 마그네슘 질문
- [ ] LDL 수치 질문
- [ ] 가슴 통증/숨참 응급 질문
- [ ] 아침 결식 반복 + 체크리스트 추천
- [ ] 스마트 생활관리 점수 상승 표현
- [ ] 사용자가 더 원할 때 확장 체크리스트
- [ ] OCR preview는 분석 근거 제외

검증:

- [ ] golden tests
- [ ] route integration tests
- [ ] deterministic no-LLM tests
- [ ] focused Flutter contract tests

## 15. Day10 follow-up gaps

목표: Day10 화면 smoke에서 확인된 통합 gap을 다음 PR 후보로 분리한다.

권장 우선순위:

1. `CORS/dev-proxy`: 팀원이 기본 Chrome 보안 설정으로 Flutter web 화면을 열어도 backend consent/chat이 통과하게 한다.
2. `display-visibility`: source, analysis, approval preview가 응답 직후 화면에서 확인 가능하게 한다.
3. `pure-unknown-fixture`: demo/golden/smoke에서 `unknown_no_reviewed_source`를 안정적으로 재현한다.
4. `team-contract-audit`: 팀원 DB/식단/영양제/복약 작업이 confirmed record와 preview/candidate를 분리하는지 확인한다.
5. `renderer-golden-quality`: 답변 품질은 위 통합 gap 이후 BoundaryPlan, UnknownRenderer, CardAnswerRenderer, Lemon Aid 톤 golden examples로 분리해 진행한다.

TODO:

- [ ] backend CORS allowlist에 Flutter web dev origin을 명시하거나 same-origin dev proxy를 둔다.
- [ ] source/analysis/approval preview 패널이 응답 직후 화면에서 확인 가능하도록 panel anchor, sticky summary, 또는 scroll placement를 조정한다.
- [ ] `unknown_no_reviewed_source` demo 문구를 golden fixture와 Flutter smoke fixture에 안정적으로 고정한다.
- [ ] Day10 smoke 스크립트를 임시 `output/day10` 산출물이 아니라 재사용 가능한 dev smoke 명령으로 정리할지 결정한다.
- [ ] 팀원 DB/식단/영양제/복약 작업이 Agent confirmed context 계약을 만족하는지 audit한다.
- [ ] 답변 품질/프롬프트 대수정은 `renderer-golden-quality` 후속 PR로 분리한다.

검증:

- [ ] 기본 Chrome 보안 설정에서 Flutter web -> backend consent/chat preflight가 통과한다.
- [ ] 실제 화면에서 answer, sources, boundary/unknown, CTA, approval preview가 한 번의 demo flow로 확인된다.
- [ ] pure unknown scenario가 `sources=[]`, `answerability=unknown_no_reviewed_source`로 고정된다.
- [ ] team contract audit 결과 confirmed record와 preview/candidate record가 구분된다.

## 16. 완료 정의

- Agent가 앱 컨텍스트와 memory를 함께 읽는다.
- raw archive와 agent memory가 분리된다.
- memory 4종이 조회/갱신/압축된다.
- 공식 기록 변경은 사용자 승인 후에만 일어난다.
- 오늘 분석과 스마트 분석의 점수 의미가 안전하게 고정된다.
- 체크리스트 후보와 저장 항목이 분리된다.
- boundary 답변은 결정 금지 안에서 충분히 설명한다.
- reviewed evidence 없는 건강 판단은 unknown 또는 boundary로 닫힌다.
- 모든 핵심 경계는 unit, integration, golden test 중 하나로 고정된다.
