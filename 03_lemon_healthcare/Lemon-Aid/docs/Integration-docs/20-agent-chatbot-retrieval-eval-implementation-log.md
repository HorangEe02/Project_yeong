# 20. 에이전트/챗봇 Retrieval Eval 구현 로그

> Status: implementation-log
> 작성일: 2026-06-01
> 기준 문서: [15-agent-llm-gap-audit.md](./15-agent-llm-gap-audit.md)

## 1. 왜 했나

`15-agent-llm-gap-audit.md`는 `medical_rag_chunks`, pgvector, hybrid search를 바로 붙이기 전에
reviewed/not-expired gate와 low-confidence fallback을 먼저 고정하라고 정리했다.

이번 변경은 RAG/vector search 구현이 아니라, DB evidence retrieval이 검수되지 않았거나 만료된
row를 AnswerCard로 승격하지 못하게 막는 1차 eval gate다.

## 2. 구현

변경 파일:

- `backend/Nutrition-backend/src/services/chatbot_evidence_retriever.py`
- `backend/Nutrition-backend/tests/unit/services/test_chatbot_evidence_retriever.py`

구현 내용:

- `MedicalEvidenceItem.review_status == "reviewed"` 필터를 추가했다.
- `MedicalSourceVersion.review_status == "reviewed"` 필터를 추가했다.
- `MedicalSourceVersion.expires_at >= today` 필터를 추가했다.
- fake session이나 테스트 double이 DB where를 우회해도 `draft`/expired row는 post-filter에서 제외한다.

## 3. 안전 경계

- production empty DB는 seed registry fallback 없이 `no_match`로 닫는다.
- dev/local만 seed registry fallback을 유지한다.
- retrieval 실패는 LLM 일반 지식으로 보완하지 않고 unknown/fallback 경로로 내려간다.

## 4. 검증

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_chatbot_evidence_retriever.py
```

결과:

```text
6 passed
```

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_answer_card_normalizer.py backend/ai_agent_chat/tests/test_chatbot_agent.py
```

결과:

```text
47 passed
```

## 5. 남은 순서

다음 순서는 `15-agent-llm-gap-audit.md`의 권장 작업 순서에 맞춰 진행한다.

1. Structured output contract
2. Flutter source detail UI
3. Observability and report
