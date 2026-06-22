# 18. 에이전트/챗봇 Entity Normalization 구현 로그

> Status: implementation-log
> 작성일: 2026-06-01
> 기준 문서: [15-agent-llm-gap-audit.md](./15-agent-llm-gap-audit.md)

## 1. 왜 했나

`15-agent-llm-gap-audit.md`의 다음 보완점은 약물/영양제 상호작용 판단을 raw text keyword가 아니라
정규화된 entity pair 또는 class pair 위에 올리는 것이었다.

기존 구현은 P0 상호작용 keyword group을 갖고 있었지만, "리튬/lithium/탄산리튬"처럼 같은 대상을
여러 표현으로 묻는 경우와 "혈압약/당뇨약/이뇨제"처럼 너무 넓은 약 표현을 구분하는 전용 계층이
없었다.

## 2. 이번 범위

이번 변경은 외부 의약품 DB를 붙이는 작업이 아니라, runtime safety routing에 필요한 최소
normalization layer를 만든 1차 작업이다.

- 약물: `lithium`, `warfarin`, `levothyroxine`, `metformin`
- 약물 class: `statin`, `ssri`, `snri`, `antidepressant`, `nitrate`, `pde5_inhibitor`
- 넓은 약 표현: `blood_pressure_medication`, `diabetes_medication`, `diuretic`, `anticoagulant`
- 보충제/영양성분/식품: `st_johns_wort`, `grapefruit`, `vitamin_k`, `potassium`, `selenium`,
  `calcium`, `iron`, `omega3`, `ginkgo`, `vitamin_e`, `red_yeast_rice`, `five_htp`

## 3. 구현

변경 파일:

- `backend/ai_agent_chat/src/lemon_ai_agent/entity_normalization.py`
- `backend/ai_agent_chat/src/lemon_ai_agent/knowledge.py`
- `backend/ai_agent_chat/src/lemon_ai_agent/agents/chatbot.py`
- `backend/ai_agent_chat/tests/test_medical_knowledge_registry.py`
- `backend/ai_agent_chat/tests/test_chatbot_agent.py`

구현 내용:

- `normalize_health_entities()`를 추가해 alias를 canonical id로 정규화했다.
- `has_p0_entity_pair()`를 추가해 P0 boundary를 entity pair로도 판정한다.
- 저장된 medication context의 `normalized_name`, `medication_class`도 정규화 입력으로 사용한다.
- `혈압약 + 칼륨`처럼 넓은 약 표현과 특정 성분이 함께 나온 질문은 LLM을 호출하지 않고
  `needs_more_info`로 닫는다.

## 4. 안전 경계

- broad medication term만으로 병용 가능/불가를 말하지 않는다.
- 정확한 약 이름, 성분명, 제품 라벨, 복용 중인 영양제 성분명을 확인하도록 안내한다.
- `needs_more_info` 응답에는 raw prompt나 내부 trace를 넣지 않는다.
- 기존 reviewed evidence, boundary, unknown fail-closed 계약은 유지한다.

## 5. 검증

Focused RED/GREEN:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_medical_knowledge_registry.py::test_entity_normalizer_maps_aliases_to_canonical_ids backend/ai_agent_chat/tests/test_medical_knowledge_registry.py::test_entity_normalizer_requires_specific_medication_for_broad_terms backend/ai_agent_chat/tests/test_chatbot_agent.py::test_chatbot_broad_medication_potassium_question_needs_specific_name
```

RED에서는 chatbot 응답이 아직 `unknown_no_reviewed_source`로 떨어져 실패했다. 구현 후 GREEN 결과:

```text
3 passed
```

Regression:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests
```

결과:

```text
122 passed, 1 skipped
```

## 6. 남은 순서

다음 순서는 `15-agent-llm-gap-audit.md`의 권장 작업 순서에 맞춰 진행한다.

1. Reviewed boundary/evidence coverage
2. Retrieval eval and hybrid retrieval design
3. Structured output contract
4. Flutter source detail UI
5. Observability and report
