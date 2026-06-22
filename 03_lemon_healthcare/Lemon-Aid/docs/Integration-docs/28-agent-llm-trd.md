# 28. Agent/LLM TRD

> Status: technical requirements draft
> 작성일: 2026-06-04
> PRD: [27-agent-llm-prd.md](./27-agent-llm-prd.md)
> 기준 문서: [26-agent-llm-product-direction-reset.md](./26-agent-llm-product-direction-reset.md)
> 기준 worktree: `feat/ai-agent-backend-integration`

## 1. 목적

이 문서는 Agent/LLM PRD를 구현자가 바로 코드, 테스트, API 계약으로 옮길 수 있게
기술 요구사항으로 분해한다.

요구사항 키워드는 다음 의미로 사용한다.

- `MUST`: 구현하지 않으면 제품 요구 미달이다.
- `SHOULD`: 기본 구현 기준이다. 예외가 있으면 설계 문서나 PR에 이유를 남긴다.
- `MAY`: MVP 이후 확장 후보다.

## 2. 시스템 범위

포함 범위:

- `/api/v1/ai-agent/chat`
- Agent memory 생성, 압축, 조회, 갱신 계약
- 오늘 분석과 스마트 분석 snapshot
- 체크리스트 후보 생성, 확장, 저장 승인, 수행 결과 반영
- reviewed evidence retrieval, `AnswerCard` 정규화, boundary/unknown/answer rendering
- LLM structured output과 deterministic fallback
- Flutter가 소비할 response contract

제외 범위:

- 자동 진단, 치료 여부 결정, 개인 복용량 결정
- 사용자 승인 없는 공식 기록 변경
- raw OCR preview의 건강 분석 반영
- live web search 결과의 직접 사용자 답변
- LLM fine-tuning 기반 의료 지식 주입

## 3. 기능 요구사항

### TRD-FR-001. Agent 오케스트레이션

- 시스템은 사용자 질문 또는 분석 요청마다 앱 컨텍스트 snapshot을 생성해야 한다.
- 시스템은 필요한 경우 추가 구조화 조회가 필요한지 판단해야 한다.
- 시스템은 앱 컨텍스트, memory, reviewed evidence를 합쳐 `AnswerPlan` 또는
  `AnalysisPlan`을 생성해야 한다.
- 시스템은 저장, 알림 등록, 체크리스트 추가, 분석 실행 같은 앱 액션을 사용자 승인 없이
  실행하면 안 된다.

완료 증거:

- route integration test
- context resolver test
- action confirmation contract test

### TRD-FR-002. LLM 역할 제한

- LLM은 plan 또는 `AnswerCard` 밖 건강 사실을 생성하면 안 된다.
- LLM prompt에는 raw OCR, raw prompt, raw LLM output, internal trace, source registry dump가
  들어가면 안 된다.
- LLM 출력은 schema, grounding, safety 검증을 통과해야 한다.
- 검증 실패 시 deterministic renderer로 fallback해야 한다.

완료 증거:

- prompt capture test
- unsupported fact fallback test
- structured output parse failure test

### TRD-FR-003. Raw 저장소와 agent memory 분리

- 시스템은 raw chat archive와 agent memory를 구분해야 한다.
- raw chat은 장기 prompt memory로 직접 사용하면 안 된다.
- raw prompt log는 개인화 memory로 사용하면 안 된다.
- 대화가 길어지면 핵심 요약만 `conversation_memory`로 갱신해야 한다.

완료 증거:

- memory writer unit test
- raw prompt exclusion test
- conversation summary compaction test

### TRD-FR-004. Agent memory 타입

시스템은 최소한 아래 memory 타입을 지원해야 한다.

- `profile_memory`
- `behavior_memory`
- `conversation_memory`
- `safety_memory`

각 memory record는 최소한 아래 metadata를 가져야 한다.

- `memory_id`
- `user_scope`
- `memory_type`
- `summary`
- `confidence`
- `source_kind`
- `source_ref`
- `created_at`
- `updated_at`
- `expires_at` 또는 `review_after`

완료 증거:

- DB model 또는 repository test
- memory retrieval priority test
- memory expiry/review test

### TRD-FR-005. 채팅 기반 memory 승격

- 채팅에서 나온 건강 정보는 memory에는 저장할 수 있다.
- 채팅 정보는 공식 앱 기록을 자동 수정하면 안 된다.
- 복약, 질환, 검사수치, 영양제 성분 같은 정보는 `user_reported` 또는 동등한 신뢰도 표시를
  가져야 한다.
- 공식 DB 반영이 필요한 경우 등록 또는 확인 CTA를 제안해야 한다.

완료 증거:

- chat-derived medication memory test
- no official medication auto-write test
- registration CTA test

### TRD-FR-006. OCR preview와 사진 분석 후보 제외

- OCR preview와 사진 분석 후보는 memory에 저장하면 안 된다.
- 사용자가 확정 저장한 음식/영양제만 confirmed 기록으로 분석에 강하게 사용해야 한다.
- OCR/라벨 구조화 보조는 가능하지만 최종 영양성분, 함량, 단위, 칼로리는 DB와 알고리즘
  결과를 기준으로 해야 한다.

완료 증거:

- OCR preview exclusion test
- confirmed supplement/food contract test
- nutrition algorithm output adapter test

### TRD-FR-007. 오늘 현재 분석 점수

- 시스템은 오늘 기록 기준의 `오늘 현재 분석 점수`를 생성해야 한다.
- 점수는 현재까지 등록된 음식, 오늘 체크된 영양제, 체크리스트, 오늘 대화 맥락을 사용한다.
- 기록이 부족하면 낮은 점수 대신 `analysis_pending` 또는 동등한 상태를 반환해야 한다.
- 점수 설명은 질병 위험이나 건강 상태 판정처럼 표현하면 안 된다.

완료 증거:

- today analysis minimum condition test
- pending state test
- forbidden wording test

### TRD-FR-008. 스마트 생활관리 점수

- 시스템은 누적 기록 기반의 `스마트 생활관리 점수`를 생성해야 한다.
- 점수는 반복 영양축, 체크리스트 수행률, 거절 항목, 선호 시간대, 대화 메모리, 사용자 프로필을
  사용할 수 있다.
- 점수는 생활관리 습관의 안정도를 나타내야 하며 질병 위험 예측으로 표현하면 안 된다.

완료 증거:

- smart analysis snapshot test
- behavior memory influence test
- safety wording test

### TRD-FR-009. 체크리스트 후보 생성

- 시스템은 기본 모드에서 우선순위 1~3개 체크리스트 후보를 제안해야 한다.
- 사용자가 더 원하면 확장 모드로 카테고리별 후보를 제공해야 한다.
- 실제 저장과 알림 등록은 사용자가 선택한 항목만 반영해야 한다.
- 수행률, 거절 항목, 반복 실패, 선호 시간대, 난이도는 `behavior_memory`에 반영해야 한다.

완료 증거:

- checklist candidate test
- expanded checklist mode test
- selected-only persistence test
- behavior memory update test

### TRD-FR-010. 의료 지식 retrieval

- 의료/영양/복약 지식은 reviewed, not stale, user-facing allowed source만 사용해야 한다.
- retrieval 결과는 바로 prompt에 넣지 않고 `AnswerCard` 또는 동등한 내부 프레임으로 정규화해야 한다.
- 검수 evidence가 없으면 `unknown_no_reviewed_source`로 닫거나 boundary로 처리해야 한다.
- RAG/vector retrieval은 source governance와 normalizer 뒤에 붙어야 한다.

완료 증거:

- retriever gate test
- answer card normalizer test
- unknown no reviewed source test
- retrieval eval test

### TRD-FR-011. 의료 boundary

- boundary는 답변 금지가 아니라 결정 금지로 구현해야 한다.
- 응급, 복약, 검사수치, 병용 질문에서도 가능한 위험 범주, 일반 원리, 확인할 정보,
  상담 준비 질문, 낮은 위험 행동을 설명할 수 있어야 한다.
- 시스템은 진단명 확정, 치료 여부 결정, 약 시작/중단/증량/감량, 개인 복용량, 병용 가능/불가,
  응급 여부를 단정하면 안 된다.
- 응급 가능성이 있는 질문은 즉시 행동 안내를 포함해야 한다.

완료 증거:

- emergency explanatory boundary test
- lab value decision boundary test
- medication dose boundary test
- forbidden decision wording test

### TRD-FR-012. API 응답 계약

`/api/v1/ai-agent/chat` 응답은 기존 mobile 호환성을 유지하면서 아래 정보를 제공해야 한다.

- `answerability`
- `provider`
- `sources[]`
- `safety_warnings`
- `requires_user_approval`
- `ctas[]`
- `analysis_snapshot` 또는 linkable analysis reference
- raw/internal field 비노출

완료 증거:

- route response contract test
- mobile DTO compatibility test
- raw/internal negative test

## 4. 비기능 요구사항

### TRD-NFR-001. 안전성

- 모든 의료 결정 경계는 deterministic하게 판정되어야 한다.
- LLM 출력은 SafetyGuard 또는 동등한 검증 계층을 통과해야 한다.
- unsupported numeric claim과 unsupported medical fact는 fallback해야 한다.

### TRD-NFR-002. 개인정보

- raw prompt, raw OCR, raw image, EXIF, raw LLM output, provider payload 전문은 사용자 응답,
  memory prompt, unknown backlog에 노출하면 안 된다.
- raw chat archive는 보관, 삭제, 동의 정책을 가져야 한다.

### TRD-NFR-003. 추적성

- 사용자-facing 건강 사실은 source metadata로 추적 가능해야 한다.
- memory에서 나온 정보는 memory type, confidence, source_kind로 추적 가능해야 한다.

### TRD-NFR-004. 테스트 가능성

- LLM provider가 없어도 deterministic renderer로 핵심 정책을 검증할 수 있어야 한다.
- 새 memory type, answerability, boundary, score status를 추가할 때는 unit 또는 integration test를 함께 추가해야 한다.

### TRD-NFR-005. 확장성

- 추천 랭킹 모델, OCR/음식 인식 모델 개선, LLM fine-tuning은 MVP 경로와 분리되어야 한다.
- 모델 학습은 동의, 비식별화, 검수, 회귀 평가를 통과한 뒤 별도 단계로 진행해야 한다.

## 5. 완료 정의

- PRD의 제품 목표가 각 TRD 요구사항으로 추적된다.
- memory, analysis, checklist, boundary, retrieval 요구사항이 테스트 가능하다.
- 공식 앱 기록과 chat-derived memory의 경계가 코드와 문서에서 일관된다.
- 오늘 분석과 스마트 생활관리 점수가 건강 판정처럼 표현되지 않는다.
- 의료 boundary 답변이 결정 금지를 지키면서도 충분한 설명을 제공한다.
