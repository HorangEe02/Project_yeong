# 21. 에이전트/챗봇 Structured Output 구현 로그

> Status: implementation-log
> 작성일: 2026-06-01
> 기준 문서: [15-agent-llm-gap-audit.md](./15-agent-llm-gap-audit.md)

## 1. 왜 했나

`15-agent-llm-gap-audit.md`는 OpenAI-compatible runtime이라도 provider별 structured output 지원 수준이
다르므로, schema success/failure 경로를 명확히 고정해야 한다고 정리했다.

## 2. 이번 범위

이번 변경은 provider별 live smoke 확장이 아니라, chatbot runtime의 structured output 계약을
unit regression으로 고정한 1차 작업이다.

- LLM request는 `json_schema` response format을 포함한다.
- schema에 맞는 JSON은 사용자-facing section answer로 렌더링한다.
- schema가 맞지 않으면 raw provider payload를 노출하지 않고 deterministic fallback을 사용한다.

## 3. 구현

변경 파일:

- `backend/ai_agent_chat/tests/test_chatbot_agent.py`

기존 구현 확인:

- `backend/ai_agent_chat/src/lemon_ai_agent/agents/chatbot.py`의 `STRUCTURED_RESPONSE_FORMAT`
- `_render_structured_completion()`
- `_has_structured_response_schema()`
- fallback 경로

추가 검증:

- `test_chatbot_invalid_structured_json_falls_back_without_raw_payload`

## 4. 안전 경계

- schema 실패 시 raw JSON/provider payload가 사용자 응답에 들어가지 않는다.
- forbidden wording이 있거나 required section shape가 맞지 않으면 deterministic fallback으로 닫는다.
- fallback도 reviewed card/source basis를 사용한다.

## 5. 검증

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests
```

결과:

```text
124 passed, 1 skipped
```

## 6. 남은 순서

다음 순서는 `15-agent-llm-gap-audit.md`의 권장 작업 순서에 맞춰 진행한다.

1. Flutter source detail UI
2. Observability and report
