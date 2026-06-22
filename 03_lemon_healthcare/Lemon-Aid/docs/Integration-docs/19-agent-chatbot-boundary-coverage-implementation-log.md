# 19. 에이전트/챗봇 Boundary Coverage 구현 로그

> Status: implementation-log
> 작성일: 2026-06-01
> 기준 문서: [15-agent-llm-gap-audit.md](./15-agent-llm-gap-audit.md)

## 1. 왜 했나

`15-agent-llm-gap-audit.md`는 LLM-WIKI 상호작용 매트릭스를 바로 사용자 답변 evidence로 쓰지 말고,
후보 boundary와 golden case로만 다루라고 정리했다.

이번 작업은 그 원칙을 유지하면서, 이미 P0 boundary로 닫는 runtime 항목들이 운영/리포트/테스트에서
추적 가능한 `boundary_code`를 남기도록 만든 1차 구현이다.

## 2. 이번 범위

이번 변경은 새 병용 가능/불가 지식을 추가한 것이 아니다.

- P0 후보는 계속 `drug_or_interaction` boundary로 닫는다.
- 답변은 복용 가능/불가를 판정하지 않고 의사 또는 약사 확인으로 안내한다.
- `boundary_code`는 raw prompt 없이 운영 집계와 UI source detail에 연결하기 위한 metadata다.

## 3. 구현

변경 파일:

- `backend/ai_agent_chat/src/lemon_ai_agent/entity_normalization.py`
- `backend/ai_agent_chat/src/lemon_ai_agent/renderers.py`
- `backend/ai_agent_chat/tests/test_medical_knowledge_registry.py`
- `backend/ai_agent_chat/tests/test_chatbot_agent.py`

구현 내용:

- `match_p0_boundary()`를 추가해 normalized entity pair에서 `boundary_code`, `topic`,
  `entity_ids`를 반환한다.
- `BoundaryRenderer`가 P0 boundary 응답의 `safety_warnings`에 `boundary_code:<code>`를 남긴다.
- boundary `sources[]`에도 `boundary_code`를 포함한다.
- 흡연/베타카로틴/비타민 A, 음주/비타민 A/아세트아미노펜, MAOI/티라민처럼 기존 P0 테스트에 있던
  생활 맥락 경계도 정규화 대상으로 포함했다.

## 4. 안전 경계

- LLM-WIKI 항목은 여전히 후보이며, 공식 source 검수 전 answerable evidence로 쓰지 않는다.
- `boundary_code`가 있어도 개인 병용 가능/불가 판단은 하지 않는다.
- 응답과 source metadata에는 raw prompt, raw OCR, provider payload를 넣지 않는다.

## 5. 검증

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests
```

결과:

```text
123 passed, 1 skipped
```

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py::test_chatbot_policy_boundary_seed_migration_contains_p0_codes
```

결과:

```text
1 passed
```

## 6. 남은 순서

다음 순서는 `15-agent-llm-gap-audit.md`의 권장 작업 순서에 맞춰 진행한다.

1. Retrieval eval and hybrid retrieval design
2. Structured output contract
3. Flutter source detail UI
4. Observability and report
