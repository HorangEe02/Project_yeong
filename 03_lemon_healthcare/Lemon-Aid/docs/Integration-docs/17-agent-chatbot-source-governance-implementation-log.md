# 17. 에이전트/챗봇 Source Governance 구현 로그

> Status: implementation-log
> 작성일: 2026-06-01
> 기준 문서: [15-agent-llm-gap-audit.md](./15-agent-llm-gap-audit.md)

## 1. 왜 했나

`15-agent-llm-gap-audit.md`에서 확인한 다음 순서는 DB/source governance를 "테이블이 있다"에서
"운영 루프가 있다"로 올리는 것이었다.

기존 unknown backlog는 안전하게 topic metadata를 모으는 구조는 있었지만, 운영자가 어떤 항목을
검토 중인지, 어떤 항목이 reviewed evidence로 승격됐는지, 어떤 항목이 폐기됐는지를 DB constraint
수준에서 구분하기 어려웠다.

## 2. 이번 범위

이번 변경은 source 본문을 새로 늘리는 작업이 아니라, unknown backlog가 다음 evidence PR의 입력이
될 수 있도록 상태 흐름을 고정한 1차 작업이다.

- `open`: 새로 쌓인 unknown topic
- `reviewing`: 공식 source 확인 또는 팀 검수 중
- `promoted`: reviewed evidence/boundary 후보로 승격됨
- `dismissed`: 현재 제품 범위 밖이거나 evidence로 쓰지 않기로 함
- `deprecated`: 한때 후보였지만 만료되었거나 더 이상 쓰면 안 됨

## 3. 구현

변경 파일:

- `backend/Nutrition-backend/src/models/db/medical_source.py`
- `backend/Nutrition-backend/src/services/chatbot_unknown_backlog.py`
- `backend/alembic/versions/0017_extend_unknown_backlog_status_lifecycle.py`
- `backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog.py`
- `backend/Nutrition-backend/tests/unit/db/test_models.py`
- `backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py`

구현 내용:

- `chatbot_unknown_knowledge_events.status` check constraint를 운영 상태 5개로 확장했다.
- `UNKNOWN_KNOWLEDGE_EVENT_STATUSES`와 `update_unknown_knowledge_event_status()`를 추가했다.
- 지원하지 않는 상태 문자열은 `ValueError`로 막는다.
- Alembic `0017`에서 upgrade/downgrade를 명시했다.
- downgrade 때는 `reviewing -> open`, `promoted -> reviewed`, `deprecated -> dismissed`로
  이전 compact 상태에 맞춰 되돌린다.

## 4. 안전 경계

- raw question, raw prompt, raw OCR, raw conversation은 계속 저장하지 않는다.
- unknown backlog에는 intent/category/condition/topic/retrieval warning 같은 구조화된 metadata만 남긴다.
- LLM-WIKI 항목은 여전히 후보일 뿐이고, `promoted` 상태가 곧 사용자-facing evidence를 뜻하지 않는다.
  실제 답변에 쓰려면 reviewed source row, evidence item, boundary, golden test가 추가로 필요하다.

## 5. 검증

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog.py backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog_report.py
```

결과:

```text
7 passed
```

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/db/test_models.py backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py
```

결과:

```text
51 passed
```

## 6. 남은 순서

다음 순서는 `15-agent-llm-gap-audit.md`의 권장 작업 순서에 맞춰 진행한다.

1. Medication/supplement entity normalization
2. Reviewed boundary/evidence coverage
3. Retrieval eval and hybrid retrieval design
4. Structured output contract
5. Flutter source detail UI
6. Observability and report
