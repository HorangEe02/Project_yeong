# 33. Agent/LLM Team Integration Contract

> Status: integration contract draft
> 작성일: 2026-06-04
> 기준 worktree: `feat/ai-agent-backend-integration`
> 기준 문서: [31-agent-llm-runtime-decision-eval.md](./31-agent-llm-runtime-decision-eval.md), [32-agent-llm-model-smoke-eval-report.md](./32-agent-llm-model-smoke-eval-report.md)

## 1. 목적

이 문서는 현재 한 worktree에 있는 DB/UI/backend 구현을 전체 팀 최종 상태로 단정하지
않는다. 다른 팀원의 파트가 합쳐졌을 때 Agent가 바로 작동하려면 무엇을 최소 입력으로
받고, 무엇을 출력해야 하는지 계약으로 고정한다.

작성 기준:

- 중심은 `Agent I/O 최소 계약`이다.
- 현재 구현 gap은 계약 충족 여부를 판단하는 보조 증거로만 둔다.
- 팀별 세부 구현 방식은 강제하지 않는다.

## 2. Agent가 믿을 수 있는 입력

Agent는 raw 데이터나 preview를 직접 건강 판단 근거로 쓰지 않는다. 아래 상태와 신뢰도
계약을 통과한 입력만 사용한다.

| 입력 | 필수 상태 | Agent 사용 방식 |
| --- | --- | --- |
| 음식 기록 | `confirmed` | 영양축, 식사 후보, 오늘 분석, 스마트 분석에 사용 |
| 영양제 기록 | `confirmed`, 성분/함량/단위/`nutrient_code` 가능하면 포함 | 복용 체크, 병용 주의, 분석 context에 사용 |
| OCR/사진 분석 후보 | `preview` 또는 unconfirmed | 건강 분석 근거에서 제외 |
| 사용자 프로필 | 공식 DB record 또는 `user_reported` memory | 공식 record는 강한 근거, user_reported는 약한 표현 |
| 복약/질환 | 공식 DB 또는 `user_reported` safety memory | boundary와 상담 준비 정보에 사용 |
| 체크리스트 | candidate/selected/completed/rejected 구분 | candidate는 제안, selected 이후만 저장/알림 |
| reviewed evidence | reviewed, not stale, user-facing allowed | AnswerCard/BoundaryPlan의 유일한 의료 근거 |
| raw chat | archive 또는 recent turns | 장기 prompt로 직접 사용하지 않고 요약 memory만 사용 |
| raw prompt/log | audit/debug only | 개인화 memory와 사용자 응답에 사용하지 않음 |

## 3. 최소 입력 계약

### 3.1 DB/데이터 파트

DB/데이터 파트는 Agent가 아래 필드를 조회할 수 있게 해야 한다.

Food record:

```json
{
  "food_record_id": "...",
  "recorded_at": "...",
  "meal_type": "breakfast|lunch|dinner|snack|unknown",
  "display_items": ["라면"],
  "portion": {"amount": 1, "unit": "serving"},
  "nutrients": [{"code": "sodium", "amount": 2600, "unit": "mg"}],
  "rough_nutrient_axes": ["sodium_high"],
  "status": "confirmed"
}
```

Supplement record:

```json
{
  "supplement_id": "...",
  "display_name": "Magnesium",
  "ingredients": [
    {
      "display_name": "Magnesium",
      "nutrient_code": "magnesium",
      "amount": 100,
      "unit": "mg",
      "analysis_use": "standard_nutrient"
    }
  ],
  "checked_today": true,
  "status": "confirmed"
}
```

Profile/medication:

```json
{
  "profile": {
    "age": null,
    "sex": null,
    "height_cm": null,
    "weight_kg": null,
    "chronic_conditions": ["hypertension"],
    "lifestyle": {"smoking": "unknown", "alcohol": "unknown"}
  },
  "medications": [
    {
      "display_name": "혈압약",
      "status": "active",
      "confidence": "official_record|user_reported"
    }
  ]
}
```

Evidence:

```json
{
  "source_id": "nih-ods-magnesium",
  "review_status": "reviewed",
  "expires_at": "2026-11-29",
  "user_facing_allowed": true,
  "allowed_wording": [],
  "must_not_say": []
}
```

### 3.2 Backend/API 파트

Backend는 Agent에게 raw-free snapshot을 제공해야 한다.

필수 bundle:

```json
{
  "user_health_context_snapshot": {},
  "agent_memory_bundle": {
    "profile_memory": [],
    "behavior_memory": [],
    "conversation_memory": [],
    "safety_memory": []
  },
  "reviewed_evidence_bundle": {},
  "visible_analysis_context": {},
  "request_context": {}
}
```

Backend가 보장해야 하는 것:

- confirmed food/supplement만 강한 분석 근거로 포함한다.
- preview OCR/사진 후보는 제외하거나 `preview_excluded` warning으로만 노출한다.
- raw OCR, raw prompt, raw LLM output, provider payload 전문은 포함하지 않는다.
- source governance fail 시 production-like path는 fail-closed한다.
- action approval 전에는 저장, 알림 등록, 체크리스트 추가를 실행하지 않는다.
- conversation을 client body에만 의존하지 않고 서버측 session/compaction 설계로 옮긴다.

### 3.3 Flutter/UI 파트

Flutter는 backend response contract를 그대로 소비해야 한다.

필수 response fields:

```json
{
  "request_id": "...",
  "message": "...",
  "answerability": "answerable|answerable_with_caution|unknown_no_reviewed_source|medical_decision_boundary|urgent_escalation|needs_more_info",
  "provider": "deterministic|sglang|ollama",
  "sources": [],
  "safety_warnings": [],
  "requires_user_approval": false,
  "ctas": [],
  "analysis_snapshot": null
}
```

UI 표시 요구:

- `urgent_escalation`은 일반 채팅 카드보다 강한 위험 UI로 표시한다.
- `medical_decision_boundary`는 차단 카드가 아니라 설명형 boundary 카드로 표시한다.
- `unknown_no_reviewed_source`는 빈 답변이 아니라 검수 지식 부족 상태로 표시한다.
- `sources[]`는 접을 수 있는 출처 panel로 표시한다.
- `requires_user_approval=true`인 CTA는 사용자가 확인하기 전까지 side effect가 없어야 한다.
- streaming이 도입되면 partial text와 final safety-validated response를 구분해야 한다.

### 3.4 Agent 파트

Agent는 아래 책임을 가진다.

- confirmed/reviewed/user_reported/preview를 구분한다.
- LLM이 아닌 deterministic policy가 의료 boundary를 먼저 판정한다.
- LLM은 AnswerPlan/BoundaryPlan/AnswerCard를 표현하는 보조 계층으로만 사용한다.
- LLM 출력이 schema, grounding, safety를 통과하지 못하면 fallback한다.
- raw chat 전체를 memory처럼 매번 prompt에 넣지 않는다.
- action은 제안만 하고 실행은 approval service 뒤로 넘긴다.

## 4. 출력 계약

Agent output은 아래 세 종류로 나뉜다.

| Output | 설명 | 저장 여부 |
| --- | --- | --- |
| `AnswerPlan` | 질문 답변, source, CTA, boundary 포함 | 기본 저장 없음 |
| `AnalysisPlan` | 오늘 분석/스마트 분석 snapshot | 사용자가 실행/갱신 승인 시 저장 |
| `ActionPreview` | 체크리스트 추가, 분석 실행, 알림 등록 preview | 승인 전 저장 없음 |

ActionPreview 최소 계약:

```json
{
  "action_type": "add_checklist_item|run_analysis|add_reminder",
  "preview": {},
  "requires_user_confirmation": true,
  "will_persist": false
}
```

## 5. 현재 구현 gap

현재 worktree 기준 gap은 아래와 같다.

| 영역 | 현재 상태 | 계약 대비 gap |
| --- | --- | --- |
| Chat API | `/api/v1/ai-agent/chat` 존재, `answerability`, `sources`, `requires_user_approval`, `ctas` schema 존재 | streaming 없음, 서버측 session lifecycle 없음 |
| Conversation | request body `conversation` max 24, 최근 6턴 일부 사용 | raw archive/rolling summary/turn timeout/cost budget 미구현 |
| Agent memory | `agent_memory` 테이블과 v0 memory service 존재 | 새 4종 `profile/behavior/conversation/safety_memory` schema 미구현 |
| Evidence DB | reviewed source governance와 retriever 구조 존재 | source content 확장, live RAG/vector eval은 계속 필요 |
| Flutter chat | sources/CTA/status panel 일부 구현 | approval preview 저장 flow, boundary 카드, streaming UI 미완성 |
| Runtime | deterministic golden eval pass, Ollama port ok, SGLang port missing | SGLang Qwen/Gemma live smoke 필수 미통과 |
| Rate limit/session | 명확한 LLM rate limit/session 정책 확인 안 됨 | MVP 전 cost/abuse guard 필요 |
| Privacy delete | 전체 데이터 삭제 flow에 agent memory 포함 | 별도 memory 삭제/보관/탈퇴 UX와 raw chat retention 정책 필요 |
| Push notification | reminder preference API 흔적 존재 | FCM/APNs push dispatch와 deep link 계약 필요 |

## 6. 팀별 최소 준비 조건

### DB 팀

- confirmed food/supplement/profile/medication 상태값을 안정화한다.
- preview와 confirmed를 query/API에서 구분 가능하게 한다.
- reviewed evidence는 review 상태, 만료일, user-facing 여부, source metadata를 포함한다.
- agent memory 4종 schema를 수용할 migration 방향을 합의한다.

### Backend 팀

- `UserHealthContextSnapshot`을 Agent의 유일한 app context 입구로 유지한다.
- memory bundle과 evidence bundle을 raw-free로 만든다.
- action approval 전 side effect 금지를 route test로 고정한다.
- streaming/session/rate limit은 31/32 runtime 결정 뒤 별도 PR로 설계한다.

### Flutter 팀

- chat response DTO는 `answerability`, `sources`, `ctas`, `requires_user_approval`,
  `analysis_snapshot`을 보존한다.
- urgent/boundary/unknown/approval 상태를 일반 assistant bubble과 구분한다.
- CTA는 placeholder가 아니라 선택/확인/취소 flow로 이어져야 한다.
- streaming 도입 전후 모두 final response의 safety state를 표시할 수 있어야 한다.

### Agent/LLM 팀

- SGLang Qwen/Gemma live smoke를 완료한다.
- 모델 기본값 변경은 smoke/eval 결과 뒤에만 한다.
- LLM 출력은 structured output + validator + deterministic fallback을 통과해야 한다.
- reviewed source 없는 건강 사실은 unknown/backlog로 보낸다.

## 7. Start gate

팀 통합 후 Agent 작업을 바로 시작하려면 아래가 최소 충족되어야 한다.

- confirmed food/supplement/profile/medication snapshot이 backend에서 조회된다.
- reviewed evidence가 source metadata와 함께 `AnswerCard`로 정규화된다.
- deterministic golden eval이 pass다.
- SGLang Qwen/Gemma live smoke 중 최소 Qwen baseline이 pass이고, Gemma 후보는 pass 또는 명확한 fail reason이 있다.
- Flutter가 `sources[]`, `ctas[]`, `requires_user_approval`, `answerability`를 손실 없이 표시한다.
- memory 4종 schema는 구현 전이라도 field contract가 확정되어 있다.

이 gate는 "모든 팀 구현 완료"를 뜻하지 않는다. Agent가 소비할 최소 계약이 안정되어 다음
PR을 안전하게 시작할 수 있다는 뜻이다.
