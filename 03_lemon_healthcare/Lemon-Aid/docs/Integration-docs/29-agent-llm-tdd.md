# 29. Agent/LLM TDD

> Status: technical design draft
> 작성일: 2026-06-04
> PRD: [27-agent-llm-prd.md](./27-agent-llm-prd.md)
> TRD: [28-agent-llm-trd.md](./28-agent-llm-trd.md)
> 기준 문서: [26-agent-llm-product-direction-reset.md](./26-agent-llm-product-direction-reset.md)
> 기준 worktree: `feat/ai-agent-backend-integration`
> 용어: 이 문서의 TDD는 `Technical Design Document`를 의미한다.

## 1. 설계 목표

Agent/LLM v2 설계는 기존 grounded chatbot 경로를 폐기하지 않는다. 기존
`UserHealthContextSnapshot`, `AnswerCard`, `AnswerPlan`, `AnalysisPlan`, renderer, source
governance를 제품 방향에 맞게 확장한다.

핵심 설계 원칙:

- Agent는 app context와 memory를 읽는 오케스트레이터다.
- LLM은 plan을 표현하는 보조 계층이다.
- 개인화는 memory와 deterministic 정책 업데이트로 시작한다.
- 모델 학습은 장기 품질 개선 단계로 분리한다.
- RAG는 reviewed evidence 검색 계층이며 source governance를 대체하지 않는다.
- 의료 boundary는 답변 금지가 아니라 결정 금지다.

## 2. 전체 흐름

```text
User question / analysis request
-> FastAPI ai-agent route
-> consent and safety precheck
-> app data snapshot
-> relevant memory retrieval
-> context resolver
-> intent / entity / policy analysis
-> boundary precheck
-> reviewed evidence retrieval
-> AnswerCard normalizer
-> AnswerPlan / AnalysisPlan builder
-> checklist candidate planner
-> LLM structured output or deterministic renderer
-> SafetyGuard / grounding validator
-> response + CTA
-> user-approved action execution
-> memory update after confirmed outcome
```

## 3. 주요 모듈

| 모듈 | 책임 |
| --- | --- |
| `UserHealthContextSnapshot` | 사용자 앱 데이터의 raw-free snapshot 생성 |
| `AgentMemoryRepository` | 사용자별 memory 조회, 갱신, 만료, 압축 |
| `MemoryCompressor` | raw chat 또는 recent turns에서 핵심 conversation memory 생성 |
| `MemoryPromoter` | 대화 요약 중 장기 가치가 있는 항목을 profile/behavior/safety memory로 승격 |
| `ContextResolver` | snapshot과 memory로 충분한지, 추가 구조화 조회가 필요한지 판단 |
| `AnswerCardRetriever` | reviewed evidence 검색 |
| `AnswerCardNormalizer` | 검색 결과를 내부 답변 프레임으로 정규화 |
| `AnswerPlanBuilder` | 질문 답변용 plan 생성 |
| `AnalysisPlanBuilder` | 오늘/스마트 분석용 plan 생성 |
| `ChecklistPlanner` | 기본/확장 체크리스트 후보 생성 |
| `BoundaryRenderer` | 결정 금지 경계 안에서 설명형 답변 생성 |
| `ChatRenderer` | 답변 plan을 사용자-facing 답변으로 변환 |
| `AnalysisRenderer` | 분석 plan을 UI section으로 변환 |
| `ActionApprovalService` | 저장, 알림, 체크리스트 추가 전 사용자 승인 계약 관리 |
| `MemoryUpdateService` | 승인된 행동과 수행 결과를 memory에 반영 |

## 4. 데이터 모델 초안

### 4.1 Agent memory

```python
class AgentMemoryRecord:
    memory_id: str
    owner_subject_hash: str
    memory_type: Literal[
        "profile_memory",
        "behavior_memory",
        "conversation_memory",
        "safety_memory",
    ]
    summary: str
    structured_payload: dict[str, Any]
    confidence: Literal["confirmed", "user_reported", "inferred_pattern", "summary"]
    source_kind: Literal[
        "official_profile",
        "official_food_record",
        "official_supplement_record",
        "official_medication_record",
        "chat_summary",
        "checklist_result",
        "analysis_result",
    ]
    source_ref: str | None
    priority: int
    created_at: datetime
    updated_at: datetime
    review_after: datetime | None
    expires_at: datetime | None
```

설계 원칙:

- memory는 raw chat 전문을 저장하지 않는다.
- raw chat archive는 별도 테이블 또는 로그 저장소에 둔다.
- `summary`는 prompt에 넣을 수 있는 짧은 형태여야 한다.
- `structured_payload`는 retrieval/filtering에 쓰는 key-value 형태다.
- `confidence`는 답변 강도와 공식 기록 CTA를 결정한다.

### 4.2 Raw chat archive

```python
class RawChatArchiveRecord:
    chat_id: str
    owner_subject_hash: str
    message_role: Literal["user", "assistant"]
    message_text: str
    created_at: datetime
    retention_until: datetime | None
    deletion_requested_at: datetime | None
```

설계 원칙:

- raw chat archive는 memory prompt에 직접 넣지 않는다.
- retention, deletion, consent 정책과 연결한다.
- 장기 memory는 `MemoryCompressor`가 만든 요약만 사용한다.

### 4.3 Raw prompt log

```python
class RawPromptLog:
    run_id: str
    owner_subject_hash: str | None
    provider: str
    prompt_hash: str
    redacted_prompt_preview: str
    created_at: datetime
```

설계 원칙:

- raw prompt 원문 저장은 원칙적으로 피한다.
- 필요하면 redaction과 hash 중심으로 감사 가능성을 확보한다.
- 개인화 memory로 사용하지 않는다.

## 5. Memory retrieval 설계

### 5.1 입력

- user id 또는 owner subject
- current question
- answerability category
- intent/entity analysis
- app context snapshot
- requested analysis kind

### 5.2 출력

```python
class AgentMemoryBundle:
    profile_memory: tuple[AgentMemoryRecord, ...]
    behavior_memory: tuple[AgentMemoryRecord, ...]
    conversation_memory: tuple[AgentMemoryRecord, ...]
    safety_memory: tuple[AgentMemoryRecord, ...]
    warnings: tuple[str, ...]
```

### 5.3 선택 규칙

- 질문과 관련 있는 memory만 고른다.
- `safety_memory`는 boundary 판단 전에 우선 조회한다.
- 오래되었거나 confidence가 낮은 memory는 약한 표현으로만 사용한다.
- `conversation_memory`는 최근 요약과 장기 선호를 분리한다.
- prompt budget을 넘으면 safety, profile, current behavior, conversation 순서로 압축한다.

## 6. Memory update 설계

### 6.1 업데이트 시점

- 사용자가 음식/영양제를 확정 저장한 뒤
- 사용자가 체크리스트를 수행, 거절, 반복 실패한 뒤
- 사용자가 분석 실행을 승인하고 결과가 생성된 뒤
- 대화가 일정 길이를 넘거나 주제가 바뀐 뒤
- safety-relevant 정보를 채팅에서 언급한 뒤

### 6.2 업데이트 원칙

- raw chat 전체를 memory로 승격하지 않는다.
- 복약/질환/검사수치 언급은 `user_reported`로 저장하고 공식 DB 자동 수정은 하지 않는다.
- 선호, 답변 길이, 반복 관심사, 실천 실패/성공 패턴은 확인 없이 memory에 반영할 수 있다.
- memory 충돌이 있으면 최신 confirmed 기록을 우선한다.

## 7. App context 설계

`UserHealthContextSnapshot`은 아래 섹션을 유지한다.

```text
user_profile_summary
today_analysis_snapshot
smart_analysis_snapshot
active_supplement_snapshot
recent_food_and_checklist_snapshot
chat_derived_health_signals
visible_analysis_context
```

`health_analysis_snapshot`이라는 기존 이름은 구현 호환을 위해 유지할 수 있지만, 제품 copy와
문서에서는 `smart_analysis_snapshot` 또는 `스마트 분석`으로 정리한다.

## 8. Analysis 설계

### 8.1 Today analysis

입력:

- 오늘 음식 기록
- 오늘 체크된 영양제
- 오늘 체크리스트
- 오늘 대화 맥락
- 관련 profile/safety memory

출력:

- `score_name = "오늘 현재 분석 점수"`
- `score_status`
- `score`
- `priority_adjustments`
- `recommended_foods`
- `checklist_candidates`
- `missing_records`
- `ctas`

### 8.2 Smart analysis

입력:

- 누적 음식 기록
- 누적 영양제 체크
- 체크리스트 수행률
- 거절 항목
- 반복 실패/성공 패턴
- conversation/behavior/profile/safety memory

출력:

- `score_name = "스마트 생활관리 점수"`
- `readiness_level`
- `score`
- `stable_patterns`
- `risk_attention_axes`
- `strengths`
- `next_focus`
- `checklist_candidates`
- `ctas`

점수 설명은 생활관리 안정도로 제한한다.

## 9. Checklist 설계

### 9.1 후보 생성

`ChecklistPlanner`는 아래 입력을 사용한다.

- `AnalysisPlan`
- `AnswerPlan`
- `behavior_memory`
- `profile_memory`
- `safety_memory`
- reviewed evidence

기본 모드는 1~3개 후보만 반환한다.

### 9.2 확장 모드

사용자가 더 많은 계획을 요청하면 카테고리별 후보를 반환한다.

- 식사
- 영양제
- 활동
- 기록
- 복약 주의

### 9.3 저장

체크리스트 후보는 바로 저장하지 않는다. 선택한 항목만 action approval flow를 통과해 저장한다.

## 10. Boundary 설계

Boundary는 답변 금지가 아니라 결정 금지다.

### 10.1 BoundaryPlan

```python
class BoundaryPlan:
    boundary_type: Literal[
        "urgent_escalation",
        "medical_decision_boundary",
        "medication_supplement_boundary",
        "lab_value_boundary",
    ]
    possible_risk_areas: tuple[str, ...]
    general_principles: tuple[str, ...]
    user_context_factors: tuple[str, ...]
    information_to_prepare: tuple[str, ...]
    low_risk_actions: tuple[str, ...]
    must_not_say: tuple[str, ...]
    immediate_action: str | None
```

`BoundaryRenderer`는 `BoundaryPlan`을 사용해 충분히 설명하되 결정 표현을 막는다.

### 10.2 응급 질문

- 가능한 위험 범주를 설명한다.
- 사용자 memory에서 위험 맥락을 연결한다.
- 원인을 진단하지 않는다.
- 증상이 지속되거나 심하면 즉시 행동 안내를 제공한다.

### 10.3 검사수치/치료 질문

- 수치의 일반 의미와 함께 보는 요인을 설명한다.
- 치료 여부를 결정하지 않는다.
- 병원 상담 준비 정보를 제공한다.

### 10.4 병용 질문

- reviewed evidence가 있으면 일반 원리, 확인 항목, 주의 조건을 설명한다.
- 병용 가능/불가를 단정하지 않는다.
- 제품 라벨과 복용 중인 약 목록을 확인하도록 안내한다.

## 11. Retrieval/RAG 설계

Retrieval 흐름:

```text
question + entities + memory safety context
-> reviewed evidence retrieval
-> source governance gate
-> AnswerCardNormalizer
-> AnswerPlan / BoundaryPlan
-> renderer / LLM
```

RAG/vector DB는 아래 조건을 만족해야 한다.

- reviewed source chunk만 검색 대상
- stale source 제외
- 검색 결과를 바로 prompt에 넣지 않음
- `AnswerCardNormalizer` 실패 시 후보 폐기
- unknown topic은 raw-free backlog로 저장

## 12. API 계약 초안

### 12.1 Chat request context

```json
{
  "message": "...",
  "context": {
    "user_health_context_snapshot": {},
    "visible_analysis_context": {},
    "requested_depth": "standard"
  }
}
```

### 12.2 Chat response

```json
{
  "request_id": "...",
  "message": "...",
  "answerability": "answerable_with_caution",
  "provider": "sglang|ollama|deterministic",
  "sources": [],
  "ctas": [],
  "requires_user_approval": false,
  "analysis_snapshot": null,
  "safety_warnings": []
}
```

### 12.3 Action approval

```json
{
  "action_type": "add_checklist_item|run_analysis|add_reminder",
  "preview": {},
  "requires_user_confirmation": true,
  "will_persist": false
}
```

## 13. 테스트 전략

- memory type별 unit test
- raw field exclusion test
- context resolver test
- today/smart score wording test
- checklist candidate and approval test
- boundary explanatory response test
- retrieval and unknown test
- route response contract test
- mobile DTO compatibility test

## 14. 마이그레이션 전략

1. 기존 `health_analysis_snapshot`과 `AnalysisPlan`은 유지한다.
2. 제품 copy에서 `스마트 분석` 용어를 도입한다.
3. memory repository와 writer를 별도 PR로 추가한다.
4. boundary renderer를 새 `BoundaryPlan` 기반으로 점진 교체한다.
5. 체크리스트 planner와 action approval을 route/API와 연결한다.
6. PRD/TRD/TDD/TODO 용어가 안정되면 기존 05/06/08/12 문서를 새 기준에 맞게 재정리한다.
