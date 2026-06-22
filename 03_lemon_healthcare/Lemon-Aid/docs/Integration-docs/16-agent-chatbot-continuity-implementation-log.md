# 16. 에이전트/챗봇 대화 연속성 구현 로그

> Status: implementation-log
> 작성일: 2026-06-01
> 기준 worktree: `feat/ai-agent-backend-integration`
> 기준 감사 문서: [15-agent-llm-gap-audit.md](./15-agent-llm-gap-audit.md)

## 1. 문제

사용자 UI에서 챗봇 답변의 연속성이 약하게 보였다. 코드 기준으로 확인한 원인은 다음과 같다.

- `ChatbotAgent`의 LLM prompt에는 `request.conversation`이 들어간다.
- 하지만 `ChatTurnModule.plan()`은 현재 `request.message`만으로 `policy_for_question`,
  `analyze_chat_intent`, reviewed evidence retrieval, `AnswerPlan`을 만들었다.
- 그래서 "그럼 저녁은?", "그건 왜?", "같이 먹어도 돼?" 같은 짧은 후속 질문은 이전 사용자
  발화의 음식, 나트륨, 질환, 복약 맥락을 잃을 수 있었다.
- LLM이 켜진 경우에는 prompt history로 일부 복구할 수 있지만, deterministic fallback,
  boundary, unknown 판단에서는 planning 단계의 context 손실이 그대로 드러난다.

## 2. 구현 원칙

- raw conversation을 DB, snapshot, unknown backlog에 저장하지 않는다.
- 답변 생성 전 transient planning에만 최근 사용자 발화를 사용한다.
- assistant 답변은 factual grounding으로 쓰지 않는다.
- 기존 reviewed evidence, AnswerCard, boundary, unknown fail-closed 계약은 유지한다.

## 3. 변경 내용

변경 파일:

- `backend/ai_agent_chat/src/lemon_ai_agent/chat_turn.py`
- `backend/ai_agent_chat/tests/test_chat_turn.py`
- `backend/ai_agent_chat/tests/test_chatbot_agent.py`
- `docs/Integration-docs/15-agent-llm-gap-audit.md`
- `docs/Integration-docs/16-agent-chatbot-continuity-implementation-log.md`

구현:

- `ChatTurnModule.plan()`이 짧은 후속 질문을 감지하면 최근 user turn 최대 3개와 현재 메시지를
  합친 planning question을 만든다.
- 이 planning question은 policy, intent analysis, reviewed evidence retrieval,
  `AnswerPlan` 생성에만 사용된다.
- `ChatbotRequest.message`는 그대로 보존한다.
- assistant turn은 planning context에 넣지 않는다.

## 4. 추가 테스트

추가한 테스트:

- `test_chat_turn_uses_recent_user_turn_for_brief_follow_up`
  - 현재 메시지: "그럼 저녁은?"
  - 이전 user turn: "고혈압이 있는데 점심에 라면을 먹었어. 나트륨이 걱정돼."
  - 기대: `hypertension` 맥락을 유지하고 `sodium_dinner_adjustment` card를 찾는다.

- `test_chatbot_brief_follow_up_keeps_previous_sodium_context`
  - deterministic chatbot fallback에서도 같은 후속 질문이 unknown/general로 빠지지 않고,
    저녁 나트륨 조절 답변을 낸다.

## 5. 검증

RED 확인:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_chat_turn.py::test_chat_turn_uses_recent_user_turn_for_brief_follow_up backend/ai_agent_chat/tests/test_chatbot_agent.py::test_chatbot_brief_follow_up_keeps_previous_sodium_context
```

초기 결과:

```text
2 failed
```

GREEN 확인:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_chat_turn.py::test_chat_turn_uses_recent_user_turn_for_brief_follow_up backend/ai_agent_chat/tests/test_chatbot_agent.py::test_chatbot_brief_follow_up_keeps_previous_sodium_context
```

결과:

```text
2 passed
```

회귀 확인:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_chat_turn.py backend/ai_agent_chat/tests/test_chatbot_agent.py
```

결과:

```text
36 passed
```

## 6. 남은 일

이번 변경은 연속성의 첫 단계다. 다음 작업은 `15-agent-llm-gap-audit.md`의 권장 순서를 따른다.

1. DB/source governance audit PR
2. Medication/supplement entity normalization PR
3. Reviewed boundary/evidence coverage PR
4. RAG/hybrid retrieval design PR
5. Provider capability audit PR
6. Source detail UI PR
7. Operational report PR
