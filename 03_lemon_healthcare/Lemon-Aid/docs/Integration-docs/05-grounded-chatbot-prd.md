# 05. 근거 기반 동적 답변 프레임 챗봇 PRD

> Status: product requirements draft
> 작성일: 2026-05-29
> 기준 브랜치: `feat/ai-agent-backend-integration`
> 상위 안전 계약: [03-ai-agent-safety-porting-contract.md](./03-ai-agent-safety-porting-contract.md)
> 의료정보 DB 계약: [04-medical-source-db-contract.md](./04-medical-source-db-contract.md)

## 1. 배경

현재 Lemon Aid 챗봇은 safety boundary, source registry, 일부 구조화된
`MedicalKnowledgeItem`, deterministic fallback, golden test를 갖고 있다. 이 방향은
맞지만 제품 목표에는 아직 부족하다.

부족한 지점은 "몇 개의 수동 FAQ 카드가 있는 질문만 잘 답하는 챗봇"으로 보일 수 있다는
점이다. Lemon Aid의 목표는 모든 의료/영양/복약 관련 답변이 같은 구조를 통과하는
것이다.

```text
질문 분류 -> 검수 지식 검색 -> 답변 프레임 정규화 -> 안전 정책 적용 -> LLM 문장화 -> 출력 검증
```

검수된 지식이 있으면 질문별 수동 FAQ 카드가 없어도 같은 품질의 내부 답변 프레임으로
구체적으로 답한다. 검수된 지식이 없으면 일반 LLM 지식으로 채우지 않고 모른다고 말한다.

이 문서에서 `AnswerCard`라고 부르는 것은 사용자 질문별로 미리 작성해두는 FAQ 카드가
아니다. 검색된 검수 지식을 LLM에 넘기기 전에 `allowed_guidance`,
`specific_examples`, `checklist`, `caution_conditions`, `must_not_say`,
`source metadata`로 정리한 **내부 답변 프레임**이다.

## 2. 제품 목표

Lemon Aid 챗봇의 제품 원칙은 다음과 같다.

- 구체적으로 돕되, 개인 의료 결정은 넘지 않는다.
- 검수된 지식 안에서만 건강 사실을 말한다.
- 카드가 미리 있는 질문만 잘 답하는 구조가 아니라, 검색된 검수 지식을 항상 내부 답변
  프레임 형태로 바꿔 답한다.
- 검수 지식이 없거나 stale이면 답하지 않고 필요한 정보와 업데이트 경로를 안내한다.
- LLM은 최종 문장 작성자이며, 지식 생성자나 의료 판단자가 아니다.

## 3. 대상 사용자와 대표 상황

대상 사용자는 식사, 영양제, 운동, 수면, 만성질환 맥락의 생활관리 질문을 하는 일반
사용자다. 사용자는 전문 용어가 아니라 "오늘 저녁 뭐 먹지?", "혈압약 먹는데 이
영양제 괜찮아?", "가슴이 아프고 숨이 차"처럼 묻는다.

대표 상황:

- 일반 식사 조정: "나트륨 줄이려면 저녁을 뭘로 바꿔?"
- 만성질환 맥락: "당뇨가 있는데 과식했어. 다음 끼니 어떻게 해?"
- 영양제/복약 주의: "혈압약 먹는데 마그네슘 같이 먹어도 돼?"
- 의료 결정 경계: "LDL 130이면 치료해야 해?"
- 응급: "가슴이 아프고 숨이 차"
- 지식 없음: "검수 자료가 없는 특정 성분/질환/제품 조합을 판단해줘"

## 4. 사용자 가치

사용자는 다음을 기대한다.

- "채소와 단백질을 드세요"처럼 고정된 목록을 반복하지 않고, 질문과 최근 기록에서 중요한
  영양성분과 조정 포인트를 골라 바로 바꿀 수 있는 후보를 본다.
- "전문가에게 물어보세요"만 듣는 것이 아니라 왜 확인이 필요한지, 오늘 무엇을 확인해야
  하는지 안다.
- 응급 또는 복약 변경 같은 위험 상황에서는 길게 코칭하지 않고 즉시 행동 안내를 받는다.
- 검수되지 않은 내용은 그럴듯한 답 대신 "현재 검수된 지식 안에서는 답할 수 없다"는
  말을 듣는다.

## 5. 범위

### MVP 포함

- 질문을 답변 가능 범위 기준으로 분류한다.
- reviewed source만 검색 대상으로 사용한다.
- 검색 결과를 표준 `AnswerCard`로 정규화한다.
- 모든 사용자-facing 답변은 하나 이상의 reviewed `AnswerCard` 또는 boundary renderer에서
  생성한다.
- 카드가 없으면 fail-closed unknown 응답을 반환한다.
- LLM은 카드 안의 내용만 자연스러운 한국어로 바꾼다.
- SafetyGuard가 금지 표현, 새 수치 주장, unsupported medical fact, raw/internal trace
  노출을 차단한다.
- golden test와 route-level integration test로 정책을 고정한다.

### MVP 제외

- live web search를 사용자-facing 의료 답변에 직접 연결
- unreviewed paper나 internal note를 답변 근거로 사용
- 개인 진단, 치료, 처방, 복용 가능 여부 단정
- 모델 fine-tuning으로 의료 사실을 주입
- 대형 vector DB를 먼저 붙여 답변 품질을 해결하려는 접근

## 6. 답변 가능 상태

| 상태 | 의미 | 사용자 응답 |
| --- | --- | --- |
| `answerable` | 검수 지식으로 일반 생활관리 답변 가능 | 구체 행동, 예시, 출처 기준 |
| `answerable_with_caution` | 검수 지식으로 원리/체크리스트 설명 가능하나 개인 결정은 불가 | 원리, 확인 항목, 전문가 확인 지점 |
| `needs_more_info` | 질문의 핵심 조건이 부족함 | 필요한 추가 정보와 낮은 위험 행동 |
| `unknown_no_reviewed_source` | 관련 reviewed knowledge가 없음 | 모른다고 말하고 업데이트/확인 경로 안내 |
| `medical_decision_boundary` | 검사수치 해석, 치료, 처방, 복용량 변경 등 | 결정하지 않고 준비할 정보 안내 |
| `urgent_escalation` | 응급 또는 자해 위험 | 짧은 위험 이유와 즉시 행동 |

## 7. 답변 형식

답변 형식은 질문 유형별로 다르다. 공통적으로 내부 trace, raw prompt, raw OCR, raw
LLM response, draft source는 노출하지 않는다.

일반/질환 식사 질문:

- `요약`
- `오늘 바꿀 것`
- `추천 음식 후보`
- `피할 조합`
- `주의 조건`
- `출처 기준`

약/영양제 병용 질문:

- `요약`
- `왜 확인이 필요한가`
- `오늘 확인할 것`
- `상대적으로 안전한 대안`
- `전문가 확인이 필요한 지점`
- `출처 기준`

응급 질문:

- `가능한 위험 이유`
- `지금 할 일`
- `도움 요청 기준`
- `출처 기준`

지식 없음:

- `요약`
- `현재 답할 수 없는 이유`
- `필요한 검수 지식`
- `지금 할 수 있는 안전한 행동`

## 8. 내부 답변 프레임 요구사항

내부 답변 프레임은 수동 seed와 동적 정규화 결과가 같은 shape를 가져야 한다. 여기서
수동 seed는 답변 품질 기준과 golden test를 고정하기 위한 부트스트랩이며, 장기적인
coverage mechanism이 아니다.

필수 필드:

- `card_id`
- `answerability`
- `topic`
- `intent`
- `condition`
- `allowed_guidance`
- `specific_examples`
- `checklist`
- `caution_conditions`
- `must_not_say`
- `source_id`
- `source_url`
- `source_family`
- `source_version_id` 또는 `version_label`
- `review_status`
- `reviewed_at`
- `expires_at`
- `grounding_snippet_ids`

내부 답변 프레임 생성 규칙:

- reviewed, user-facing allowed, not stale source만 사용한다.
- draft, paper_candidate, deprecated, stale source는 사용자 답변 프레임으로 만들지 않는다.
- 내부 답변 프레임에 없는 새 건강 사실을 LLM prompt에서 만들지 않는다.
- manual seed는 seed/golden example일 뿐 coverage mechanism이 아니다.

## 9. 성공 기준

- 나트륨 저녁 질문은 국물, 소스, 장류, 가공육, 김치류처럼 나트륨 조정에 직접 관련된
  포인트를 우선 고르고, 채소/단백질 후보는 질문 또는 기록상 해당 영양 맥락이 필요할 때
  제공한다.
- 마그네슘+혈압약 질문은 보충제 함량, 제품 라벨, 혈압약 종류, 신장 기능, 이상 증상,
  약사/의사 확인을 포함하되 개인 병용 가능 여부를 단정하지 않는다.
- 응급 질문은 LLM 호출 없이 심장/폐 응급 신호 가능성과 119/응급실 행동을 안내한다.
- 검수 지식이 없는 질문은 hallucination 없이 `unknown_no_reviewed_source`로 내려간다.
- LLM이 unsupported fact나 금지 문구를 만들면 deterministic fallback으로 내려간다.
- `/api/v1/ai-agent/chat` route에서도 같은 정책이 유지된다.

## 10. 비성공 기준

아래 중 하나라도 발생하면 제품 기준 미달이다.

- 수동 seed가 있는 몇 개 질문만 잘 답하고 나머지는 LLM 일반 지식으로 답한다.
- "전문가 상담" 문구가 유용한 설명을 대체한다.
- 출처 없는 수치, 용량, 검사수치 기준, 안전성 단정이 나온다.
- reviewed source가 없는데도 그럴듯한 건강 사실을 말한다.
- draft/paper/internal note가 사용자-facing source로 노출된다.
- RAG 검색 결과가 safety boundary보다 먼저 적용된다.

## 11. 운영 업데이트 모델

새로운 질문을 잘 처리하는 방식은 prompt를 늘리는 것이 아니라 지식 업데이트다.

1. 사용자 질문 로그에서 답하지 못한 topic을 집계한다.
2. source owner가 공식 자료 또는 검수 자료를 확인한다.
3. claim을 `medical_evidence_items` 또는 registry seed로 추가한다.
4. allowed wording, blocked wording, caution level을 검수한다.
5. retrieval이 해당 claim을 찾아 `AnswerCard`로 정규화하는지 테스트한다.
6. golden test를 추가한 뒤 production-like 경로에 반영한다.

## 12. 의존 문서

- [03-ai-agent-safety-porting-contract.md](./03-ai-agent-safety-porting-contract.md)
- [04-medical-source-db-contract.md](./04-medical-source-db-contract.md)
- [dev-guides/31-medical-knowledge-layer.md](../Nutrition-docs/dev-guides/31-medical-knowledge-layer.md)
- [45-development-dependency-split.md](../Nutrition-docs/45-development-dependency-split.md)
