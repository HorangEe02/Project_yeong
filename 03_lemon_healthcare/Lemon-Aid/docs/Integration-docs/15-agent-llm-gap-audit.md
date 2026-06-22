# 15. 에이전트/LLM/DB 흐름 감사

> Status: gap-audit
> 작성일: 2026-06-01
> 기준 worktree: `feat/ai-agent-backend-integration`
> 기준 구현 문서:
> - [02-ai-agent-worktree-integration-plan.md](./02-ai-agent-worktree-integration-plan.md)
> - [03-ai-agent-safety-porting-contract.md](./03-ai-agent-safety-porting-contract.md)
> - [04-medical-source-db-contract.md](./04-medical-source-db-contract.md)
> - [04-medical-source-db-implementation-log.md](./04-medical-source-db-implementation-log.md)
> - [05-grounded-chatbot-prd.md](./05-grounded-chatbot-prd.md)
> - [06-grounded-chatbot-tdd.md](./06-grounded-chatbot-tdd.md)
> - [07-grounded-chatbot-todo.md](./07-grounded-chatbot-todo.md)
> - [08-grounded-chatbot-trd.md](./08-grounded-chatbot-trd.md)
> - [09-grounded-chatbot-implementation-log.md](./09-grounded-chatbot-implementation-log.md)
> - [10-grounded-chatbot-gap-review.md](./10-grounded-chatbot-gap-review.md)
> - [11-supabase-chatbot-dev-setup.md](./11-supabase-chatbot-dev-setup.md)
> - [12-agent-chatbot-todo.md](./12-agent-chatbot-todo.md)
> - [13-agent-chatbot-release-todo.md](./13-agent-chatbot-release-todo.md)
> - [14-agent-chatbot-release-execution-report.md](./14-agent-chatbot-release-execution-report.md)
> - [16-agent-chatbot-continuity-implementation-log.md](./16-agent-chatbot-continuity-implementation-log.md)
> - [17-agent-chatbot-source-governance-implementation-log.md](./17-agent-chatbot-source-governance-implementation-log.md)
> - [18-agent-chatbot-entity-normalization-implementation-log.md](./18-agent-chatbot-entity-normalization-implementation-log.md)
> - [19-agent-chatbot-boundary-coverage-implementation-log.md](./19-agent-chatbot-boundary-coverage-implementation-log.md)
> - [20-agent-chatbot-retrieval-eval-implementation-log.md](./20-agent-chatbot-retrieval-eval-implementation-log.md)
> - [21-agent-chatbot-structured-output-implementation-log.md](./21-agent-chatbot-structured-output-implementation-log.md)
> - [22-agent-chatbot-source-ui-observability-implementation-log.md](./22-agent-chatbot-source-ui-observability-implementation-log.md)
> - [31-medical-knowledge-layer.md](../Nutrition-docs/dev-guides/31-medical-knowledge-layer.md)
> - [45-development-dependency-split.md](../Nutrition-docs/45-development-dependency-split.md)

## 1. 결론

이전 점검은 현재 agent/chatbot 구현 여부와 LLM 보완점에 너무 치우쳤다. Lemon Aid가
처음부터 설계해 온 흐름은 더 넓다.

```text
worktree 선별 이식 계약
-> deterministic safety/backend 계약
-> medical source governance DB
-> reviewed evidence / AnswerCard
-> unknown backlog 운영 루프
-> 앱 컨텍스트 snapshot / conversation continuity / AnswerPlan / AnalysisPlan
-> SGLang/OpenAI-compatible structured output
-> Flutter chat/analysis UI
-> 나중에 RAG / hybrid retrieval / source detail UI
```

현재 구현은 이 흐름의 v1 골격을 상당히 연결했다. 하지만 운영형 건강 agent라고 부르려면
아직 세 가지가 부족하다.

- **대화 연속성**: 짧은 후속 질문이 이전 사용자 발화의 음식/영양/복약 맥락을 잃지 않아야 한다.
- **DB governance 운영성**: table과 seed는 있지만 source review, expiry, promotion,
  deprecation, audit를 반복 운영하는 절차가 아직 얇다.
- **검색/RAG 준비도**: `medical_rag_chunks` 계약은 있으나 실제 retrieval은 아직 DB evidence
  row 중심이다. pgvector/FTS/hybrid retrieval은 별도 설계와 eval이 필요하다.
- **entity normalization**: 음식/영양제/복약 context는 연결됐지만, 약물명, 약물 class,
  성분명, 영양성분 code를 공식 identifier 수준으로 정규화하는 층은 아직 시작 단계다.

따라서 다음 단계는 새 화면이나 새 LLM 기능을 넓히는 것이 아니라 **DB/source governance,
entity normalization, retrieval eval, source detail UI**를 순서대로 보강하는 것이다.

## 2. 이번 재검토에서 추가로 확인한 흐름

### 2.0 확인 범위

이번 문서는 기존에 확인했던 agent/chatbot 문서 위에, 사용자가 지적한 DB/LLM-WIKI/RAG
흐름을 추가로 확인해 다시 엮은 것이다. 이전 점검을 버리고 새로 DB만 본 것이 아니라,
기존 문서 흐름에 DB/LLM-WIKI/운영 루프 검토를 더했다. 아래 목록을 이 문서의 추적 가능한
입력으로 둔다.

기존 점검에서 이어서 반영한 문서:

- `05-grounded-chatbot-prd.md`
- `06-grounded-chatbot-tdd.md`
- `07-grounded-chatbot-todo.md`
- `08-grounded-chatbot-trd.md`
- `09-grounded-chatbot-implementation-log.md`
- `10-grounded-chatbot-gap-review.md`
- `12-agent-chatbot-todo.md`
- `13-agent-chatbot-release-todo.md`
- `14-agent-chatbot-release-execution-report.md`
- `16-agent-chatbot-continuity-implementation-log.md`
- `chatbot-unknown-backlog-report.md`

이번 재검토에서 추가로 앞쪽 설계 흐름까지 다시 확인한 문서:

- `02-ai-agent-worktree-integration-plan.md`
- `03-ai-agent-safety-porting-contract.md`
- `04-medical-source-db-contract.md`
- `04-medical-source-db-implementation-log.md`
- `11-supabase-chatbot-dev-setup.md`
- `../Nutrition-docs/dev-guides/31-medical-knowledge-layer.md`
- `../Nutrition-docs/45-development-dependency-split.md`

이번 재검토에서 추가로 확인한 LLM-WIKI/DB/RAG 문서:

- `C:\MyWorkspace\research\LLM-WIKI\wiki\entities\postgresql.md`
- `C:\MyWorkspace\research\LLM-WIKI\wiki\concepts\postgresql-indexes.md`
- `C:\MyWorkspace\research\LLM-WIKI\wiki\entities\pgvector.md`
- `C:\MyWorkspace\research\LLM-WIKI\wiki\entities\supabase.md`
- `C:\MyWorkspace\research\LLM-WIKI\wiki\concepts\supabase-database.md`
- `C:\MyWorkspace\research\LLM-WIKI\wiki\concepts\row-level-security.md`
- `C:\MyWorkspace\research\LLM-WIKI\wiki\concepts\vector-db-overview.md`
- `C:\MyWorkspace\research\LLM-WIKI\wiki\practices\vector-db-comparison.md`
- `C:\MyWorkspace\research\LLM-WIKI\wiki\concepts\hybrid-search.md`
- `C:\MyWorkspace\research\LLM-WIKI\wiki\practices\rag-vs-refrag.md`
- `C:\MyWorkspace\research\LLM-WIKI\wiki\practices\drug-nutrient-interactions.md`
- `C:\MyWorkspace\research\LLM-WIKI\wiki\practices\supplement-drug-interactions.md`

이번 재검토에서 대조한 현재 구현 파일:

- `backend/Nutrition-backend/src/models/db/medical_source.py`
- `backend/Nutrition-backend/src/services/chatbot_evidence_retriever.py`
- `backend/Nutrition-backend/src/models/db/user_medication.py`
- `backend/Nutrition-backend/src/models/db/food_record.py`
- `backend/Nutrition-backend/src/services/user_health_context_snapshot.py`
- `backend/ai_agent_chat/src/lemon_ai_agent/user_health_context.py`
- `backend/ai_agent_chat/src/lemon_ai_agent/answer_plan.py`
- `backend/ai_agent_chat/src/lemon_ai_agent/renderers.py`
- `backend/ai_agent_chat/src/lemon_ai_agent/chat_turn.py`
- `backend/ai_agent_chat/src/lemon_ai_agent/agents/chatbot.py`
- `backend/alembic/versions/0010_add_chatbot_unknown_backlog.py`
- `backend/alembic/versions/0011_seed_chatbot_reviewed_evidence.py`
- `backend/alembic/versions/0012_seed_chatbot_policy_boundaries.py`
- `backend/alembic/versions/0013_create_chatbot_unknown_backlog_summary_view.py`
- `backend/alembic/versions/0014_create_user_medications.py`
- `backend/alembic/versions/0015_create_food_records.py`
- `backend/alembic/versions/0016_seed_lithium_supplement_boundary.py`

### 2.1 통합 출발점

`02-ai-agent-worktree-integration-plan.md`의 핵심은 blind merge 금지다.

- API, backend, DB, mobile 계약은 `ai-agent-backend-integration` 기준이다.
- `changmin-aiagent`, `ai-agent-pr`, `sunghoon-database`, `taedong-design`는 필요한 단위만
  선별 비교한다.
- 포트, smoke, Flutter, SGLang은 분리한다.
- raw OCR, raw prompt, internal trace, full provider payload는 응답과 저장에서 제외한다.

이 흐름 때문에 DB도 "팀원이 만든 DB를 통째로 붙이는 것"이 아니라, 의료 source governance와
사용자 DB 책임을 분리하는 방향으로 설계됐다.

### 2.2 안전 계약

`03-ai-agent-safety-porting-contract.md`의 핵심은 역할 분리다.

- deterministic backend가 의료/영양 판단과 safety boundary를 소유한다.
- LLM은 설명자이고 새 의료 판단을 만들지 않는다.
- RAG는 reviewed source 보강 계층이며 safety boundary를 대체하지 않는다.
- DB는 계산식이 아니라 사용자 상태, 결과 version, source metadata, audit trail을 저장한다.

이 원칙은 아직 유효하다. RAG나 pgvector를 붙이더라도 LLM/RAG가 병용 가능 여부, 치료,
복약 변경, 검사수치 해석을 직접 결정하면 안 된다.

### 2.3 의료 지식층과 DB 계약

`31-medical-knowledge-layer.md`, `45-development-dependency-split.md`,
`04-medical-source-db-contract.md`는 같은 결론을 공유한다.

- 의료 사실은 model weight나 자유 prompt가 아니라 교체 가능한 source-versioned record로 둔다.
- MVP는 거대한 지식 DB가 아니라 source, version, evidence item, policy boundary,
  rag chunk governance부터 만든다.
- `draft`, `paper_candidate`, 내부 조사 snippet은 사용자-facing source와 RAG index에서 제외한다.
- KDRIs의 `approved`는 기존 dataset 용어로 유지하고, 의료 source governance의 사용자-facing
  기준은 `reviewed`로 통일한다.

현재 구현 로그 기준으로 `medical_sources`, `medical_source_versions`,
`medical_evidence_items`, `medical_policy_boundaries`, `medical_rag_chunks`는 schema/ORM으로
들어왔고, readiness DB 전환과 fail-closed도 구현됐다. 다만 실제 RAG/vector DB 연결,
KDRIs `approved -> reviewed` 운영 adapter, UI source detail은 후속 범위로 남아 있다.

### 2.4 앱 컨텍스트 agent 흐름

`12-agent-chatbot-todo.md`는 FAQ 챗봇을 버리고 앱 상태를 읽는 agent로 방향을 바꿨다.

- `UserHealthContextSnapshot`이 앱 상태를 raw-free 형태로 모은다.
- `ContextResolver`가 필요한 구조화 기록 조회를 판단한다.
- 음식 기록 v1, user medication, confirmed supplement snapshot이 연결됐다.
- `AnswerCard`는 최종 답변 문구가 아니라 reviewed evidence 재료다.
- `AnswerPlan`과 `AnalysisPlan`이 챗봇/분석 탭의 공통 planning layer다.
- `ChatRenderer`, `AnalysisRenderer`가 같은 판단을 다른 UI로 보여준다.

즉 현재 agent의 핵심은 "LLM이 똑똑하게 대답한다"가 아니라 "앱 컨텍스트와 검수 evidence를
먼저 구조화하고, LLM은 안전하게 표현한다"이다.

## 3. LLM-WIKI와 공식 문서 기준으로 다시 본 DB/RAG 판단

이번 재검토에서는 DB/RAG 관련 LLM-WIKI 문서를 추가로 확인했다.

- `wiki/entities/postgresql.md`
- `wiki/concepts/postgresql-indexes.md`
- `wiki/entities/pgvector.md`
- `wiki/entities/supabase.md`
- `wiki/concepts/supabase-database.md`
- `wiki/concepts/row-level-security.md`
- `wiki/concepts/vector-db-overview.md`
- `wiki/practices/vector-db-comparison.md`
- `wiki/concepts/hybrid-search.md`
- `wiki/practices/rag-vs-refrag.md`
- `wiki/practices/drug-nutrient-interactions.md`
- `wiki/practices/supplement-drug-interactions.md`

반영한 판단:

- Lemon Aid의 첫 RAG는 별도 vector DB보다 **PostgreSQL + pgvector + FTS**가 현실적이다.
  이미 Supabase/Postgres를 쓰고 있고, source metadata filter와 review status filter가
  중요하기 때문이다.
- 순수 vector retrieval만 쓰면 약물명, 성분명, 고유명사, 약어, 한국어 표기 변형에서
  오매칭 위험이 있다. **keyword/FTS + vector + RRF** 형태의 hybrid retrieval을 기본 후보로 둔다.
- 의료/영양 도메인은 REFRAG보다 RAG가 먼저다. 출처 추적과 review expiry가 핵심이므로
  압축 embedding 기반 접근은 지금 우선순위가 아니다.
- Supabase/RLS는 Flutter가 DB를 직접 때릴 때 강력한 모델이지만, Lemon Aid 현재 구조는
  FastAPI가 server-side gate다. Flutter가 medical governance/user health DB를 직접 읽기
  시작하는 순간 RLS와 정책 테스트를 별도 필수 작업으로 올려야 한다.

공식 문서 기준으로는 아래를 확인했다.

- PostgreSQL Full Text Search: `tsvector`, query parsing, ranking, index 구성이 기본 검색 후보가 된다.
  - https://www.postgresql.org/docs/current/textsearch.html
- PostgreSQL index type: B-tree, Hash, GiST, SP-GiST, GIN, BRIN을 쿼리 패턴에 맞춰 선택한다.
  - https://www.postgresql.org/docs/current/indexes-types.html
- PostgreSQL Row-Level Security: RLS enabled table에 policy가 없으면 default-deny로 동작한다.
  - https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- pgvector: vector type, HNSW/IVFFlat, metadata filtering 시 filter/index 전략이 중요하다.
  - https://github.com/pgvector/pgvector
- Supabase AI & Vectors: Postgres/pgvector 기반 vector store, semantic/keyword/hybrid search를 지원한다.
  - https://supabase.com/docs/guides/ai
- Supabase RLS: policy는 query에 implicit WHERE처럼 붙으므로 policy와 명시 filter를 함께 고려해야 한다.
  - https://supabase.com/docs/guides/database/postgres/row-level-security

## 4. 현재 구현의 강점

### 4.1 source governance table이 먼저 들어왔다

`medical_sources`, `medical_source_versions`, `medical_evidence_items`,
`medical_policy_boundaries`, `medical_rag_chunks`가 먼저 생긴 것은 맞는 방향이다.
RAG를 먼저 붙이지 않고 governance부터 세웠기 때문에 draft/paper/internal note가 곧바로
사용자 답변으로 새는 위험을 줄였다.

### 4.2 DB-backed evidence retriever가 AnswerCard로 정규화된다

`chatbot_evidence_retriever.py`는 DB row를 `MedicalEvidenceAnswerCardRecord`로 바꾼다.
이 구조는 raw DB row나 raw chunk를 prompt에 바로 넣지 않고 `AnswerCard` 계층을 통과시키는
현재 계약과 맞다.

### 4.3 unknown backlog가 raw-free다

`chatbot_unknown_knowledge_events`는 `primary_intent`, `category`, `related_conditions`,
`missing_topics`, `retrieval_status` 같은 구조화 metadata만 남긴다. raw question, raw OCR,
대화 전문을 저장하지 않는 방향은 유지해야 한다.

### 4.4 앱 컨텍스트가 실제로 붙었다

food record, user medication, supplement snapshot, visible analysis context가 챗봇 경로에
연결됐다. 분석 탭과 챗봇이 같은 planning layer를 공유한다는 `12` 문서의 방향은 코드에도
반영됐다.

### 4.5 SGLang/OpenAI-compatible 경로는 fallback과 함께 붙었다

structured output은 provider별 차이가 있지만, 현재는 schema parse 실패와 unsupported fact를
deterministic fallback으로 내리는 구조가 있다. 이 방식은 local/self-hosted runtime 실험을
허용하면서도 안전 경계를 유지한다.

## 5. 다시 정리한 보완점

### P0. 대화 연속성을 planning 단계에서 보존해야 한다

상태: 1차 완료. 세부 구현과 검증은
[16-agent-chatbot-continuity-implementation-log.md](./16-agent-chatbot-continuity-implementation-log.md)에
기록했다.

문제:

- 기존 구조는 `conversation`을 LLM prompt에는 넣었지만, `ChatTurnModule`의
  policy/intent/retrieval/AnswerPlan은 현재 `message`만 기준으로 만들었다.
- 그래서 "그럼 저녁은?", "그건 왜?", "영양제도 같이 봐줘" 같은 짧은 후속 질문은
  이전 사용자 발화의 음식, 나트륨, 질환, 복약 맥락을 잃을 수 있었다.
- LLM이 켜져 있으면 history를 보고 일부 복구할 수 있지만, deterministic fallback이나
  unknown/boundary 판단에서는 연속성이 약해졌다.

해야 할 일:

- 짧은 후속 질문이면 최근 사용자 발화만 planning context로 합쳐서 policy, intent,
  retrieval, AnswerPlan에 사용한다.
- assistant 답변은 factual grounding으로 쓰지 않는다.
- raw conversation을 snapshot, DB, unknown backlog에 저장하지 않는다.
- 기존 안전 경계, unknown 처리, reviewed source 제한을 유지한다.

완료 증거:

- `ChatTurnModule`이 "그럼 저녁은?"을 이전 사용자 발화의 고혈압/라면/나트륨 맥락과 함께
  해석해 `sodium_dinner_adjustment` answer card를 찾는다.
- `ChatbotAgent` deterministic fallback도 같은 흐름으로 저녁 나트륨 조절 답변을 낸다.
- 실행 검증:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_chat_turn.py backend/ai_agent_chat/tests/test_chatbot_agent.py
```

결과:

```text
36 passed
```

### P0. DB source governance를 "schema 있음"에서 "운영 루프 있음"으로 올려야 한다

상태: 1차 완료. unknown backlog status lifecycle 구현과 검증은
[17-agent-chatbot-source-governance-implementation-log.md](./17-agent-chatbot-source-governance-implementation-log.md)에
기록했다.

현재 table, migration, seed, smoke는 있다. 하지만 운영에서는 다음 흐름이 반복 가능해야 한다.

```text
unknown backlog topic
-> source 후보 지정
-> source version row 생성
-> reviewer/owner/expiry 확정
-> evidence item 또는 policy boundary 작성
-> allowed/blocked wording 검수
-> golden test 추가
-> smoke에서 sources[] 확인
-> expiry/deprecation/audit 추적
```

해야 할 일:

- source promotion checklist를 `13` 또는 별도 운영 문서에 고정한다.
- `reviewed`, `deprecated`, `stale_marked`, `review_extended` 이벤트를 기존 `audit_logs`로
  어떻게 남길지 실제 service/API 기준을 정한다.
- unknown event `status`를 `open`, `reviewing`, `promoted`, `dismissed`, `deprecated`처럼
  운영 lifecycle에 맞게 확장할지 검토한다.
- seed migration으로 넣은 reviewed evidence와 boundary가 장기 운영에서 admin seed/service로
  옮겨야 하는 범위를 구분한다.

완료 증거:

- 새 source 승격 PR이 source/version/evidence/boundary/golden/smoke/audit 증거를 한 세트로 남긴다.
- 만료 source는 자동으로 사용자-facing evidence에서 제외된다.
- unknown backlog report가 다음 evidence PR의 입력으로 바로 쓰인다.

1차 완료 내용:

- `chatbot_unknown_knowledge_events.status`를 `open`, `reviewing`, `promoted`, `dismissed`,
  `deprecated` 운영 상태로 확장했다.
- `update_unknown_knowledge_event_status()`로 임의 문자열이 상태에 들어가지 않도록 막았다.
- Alembic `0017_extend_unknown_backlog_status_lifecycle.py`를 추가해 DB check constraint와
  downgrade 매핑을 명시했다.
- raw prompt/question/conversation을 저장하지 않는 기존 unknown backlog 계약은 유지했다.

검증:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog.py backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog_report.py
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/db/test_models.py backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py
```

결과:

```text
7 passed
51 passed
```

### P0. 약물/영양제 entity normalization이 safety 품질의 병목이다

상태: 1차 완료. 약/성분 alias를 canonical entity로 모으고, broad medication term은
`needs_more_info`로 닫는 구현과 검증은
[18-agent-chatbot-entity-normalization-implementation-log.md](./18-agent-chatbot-entity-normalization-implementation-log.md)에
기록했다.

`user_medications`는 `display_name`, `normalized_name`, `medication_class`를 갖지만,
아직 RxNorm/MFDS/KDCA 등 공식 identifier와 synonym map 수준은 아니다. 현재 상태로는
"리튬", "lithium", "탄산리튬", "혈압약", "이뇨제" 같은 표현을 안정적으로 같은 boundary에
매핑하기 어렵다.

해야 할 일:

- `MedicationEntity` 계약을 추가한다.
  - `display_name`
  - `normalized_name`
  - `drug_class`
  - `ingredient_code` 또는 external code
  - `source_system`
  - `normalization_confidence`
  - `needs_user_confirmation`
- supplement ingredient도 `nutrient_code`, `ingredient_alias`, `label_only`,
  `unknown_ingredient`를 분리한다.
- interaction boundary는 raw product name이 아니라 normalized entity pair 또는 entity class pair로
  판단한다.
- broad term인 "혈압약", "당뇨약", "이뇨제"는 바로 병용 판단하지 않고 확인 질문 또는
  `needs_more_info`로 둔다.

완료 증거:

- "리튬", "lithium", "탄산리튬"이 같은 `lithium` boundary로 간다.
- "혈압약 + 칼륨"은 약 class 확인 전 병용 가능/불가를 단정하지 않는다.
- unknown backlog에는 원문 약명 대신 정규화 실패 category가 남는다.

1차 완료 내용:

- `entity_normalization.py`를 추가해 약물, 약물 class, 영양성분, 보충제, 식품 alias를
  canonical id로 정규화했다.
- `lithium`, `statin`, `levothyroxine`, `metformin`, `warfarin`, `st_johns_wort`,
  `grapefruit`, `vitamin_k`, `potassium`, `selenium` 같은 P0 후보를 entity pair로 묶었다.
- `혈압약`, `당뇨약`, `이뇨제`, `항응고제`처럼 넓은 표현은 특정 성분 질문에서
  `needs_more_info`로 닫는다.
- 저장된 medication context의 `normalized_name`과 `medication_class`도 entity normalization에 사용한다.

검증:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests
```

결과:

```text
122 passed, 1 skipped
```

### P0. LLM-WIKI 상호작용 매트릭스는 후보일 뿐, 바로 evidence가 아니다

상태: 1차 완료. LLM-WIKI 후보 중 runtime에서 이미 P0 boundary로 닫는 항목들이 stable
`boundary_code`와 source metadata를 남기도록 한 구현과 검증은
[19-agent-chatbot-boundary-coverage-implementation-log.md](./19-agent-chatbot-boundary-coverage-implementation-log.md)에
기록했다.

LLM-WIKI의 `drug-nutrient-interactions`, `supplement-drug-interactions`에는 세인트존스워트,
자몽, 비타민 K, levothyroxine 흡수 간섭, SSRI/5-HTP, warfarin/DOAC 등 중요한 P0 후보가 있다.
하지만 이 문서들은 사용자 답변의 reviewed source가 아니다.

해야 할 일:

- LLM-WIKI 항목은 `candidate_boundary`와 `candidate_golden_case`로만 다룬다.
- 공식 source 또는 검수 자료를 붙이기 전에는 runtime answerability를 확장하지 않는다.
- P0 후보는 evidence item보다 `medical_policy_boundaries`로 먼저 승격한다.
- 병용 가능 여부는 말하지 않고, 전문가 확인/복용 변경 금지/증상 또는 응급 경계만 말한다.

완료 증거:

- 세인트존스워트, 자몽, 비타민 K, levothyroxine, SSRI/5-HTP가 각각 공식 source와 golden test를 가진다.
- source가 없는 후보는 계속 `unknown_no_reviewed_source` 또는 `needs_more_info`로 닫힌다.

1차 완료 내용:

- P0 normalized pair가 `boundary_code`와 `topic`을 반환하도록 했다.
- boundary 응답의 `safety_warnings`에 `boundary_code:<code>`를 남겨 raw prompt 없이 운영 집계가 가능하게 했다.
- boundary `sources[]`에도 `boundary_code`를 포함해 UI/source detail 작업의 입력으로 쓸 수 있게 했다.
- 이 변경은 LLM-WIKI 후보를 곧바로 answerable evidence로 승격한 것이 아니다. 사용자-facing 답변은 계속
  professional review boundary로 닫는다.

검증:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py::test_chatbot_policy_boundary_seed_migration_contains_p0_codes
```

결과:

```text
123 passed, 1 skipped
1 passed
```

### P1. `medical_rag_chunks`를 실제 retrieval 설계로 연결해야 한다

상태: 1차 완료. DB evidence retrieval이 reviewed/not-expired filter를 통과한 row만
AnswerCard record로 만들도록 한 fail-closed eval gate는
[20-agent-chatbot-retrieval-eval-implementation-log.md](./20-agent-chatbot-retrieval-eval-implementation-log.md)에
기록했다.

현재 `medical_rag_chunks` table은 계약상 존재하지만 runtime retrieval은 evidence row 중심이다.
이것은 v1로는 맞지만, coverage가 늘면 keyword/topic matching만으로는 한계가 온다.

권장 설계:

```text
medical_evidence_items / medical_policy_boundaries
-> reviewed, not expired filter
-> medical_rag_chunks 생성
-> tsvector GIN index
-> pgvector embedding + HNSW index
-> keyword top-N + vector top-N
-> RRF 결합
-> low confidence evaluator
-> AnswerCardNormalizer
-> renderer
```

해야 할 일:

- chunk 생성 기준을 정한다. `chunk_text`는 검수된 snippet만 허용하고 raw web scrape/OCR은 금지한다.
- `review_status='reviewed'`와 `expires_at >= today` filter가 retrieval 전에 적용되게 한다.
- `tsvector` 컬럼 또는 generated/search document 전략을 정한다.
- pgvector embedding 차원, distance metric, HNSW/IVFFlat 선택 기준을 정한다.
- top-K result는 prompt로 바로 가지 않고 `AnswerCardNormalizer`를 반드시 통과한다.
- retrieval confidence가 낮으면 unknown 또는 needs_more_info로 닫는다.

완료 증거:

- `draft`, `paper_candidate`, expired chunk가 retrieval 결과에 나오지 않는 test가 있다.
- synonym/한국어 표기/약물 class/generic name eval set이 있다.
- retrieval 실패가 safety boundary를 우회하지 않는다.

1차 완료 내용:

- DB evidence repository query에 `MedicalEvidenceItem.review_status == reviewed`,
  `MedicalSourceVersion.review_status == reviewed`, `expires_at >= today` 필터를 추가했다.
- fake session 기반 테스트에서도 draft/expired row가 통과하지 않도록 post-filter를 유지했다.
- production empty DB는 계속 registry fallback 없이 `no_match`로 닫는다.

검증:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_chatbot_evidence_retriever.py
python -m pytest -q --no-cov backend/ai_agent_chat/tests/test_answer_card_normalizer.py backend/ai_agent_chat/tests/test_chatbot_agent.py
```

결과:

```text
6 passed
47 passed
```

### P1. Supabase/RLS 경계는 현재 FastAPI 중심 구조에 맞게 명확히 해야 한다

현재 Flutter는 FastAPI API를 통해 데이터를 쓰고 읽는 구조다. 이 경우 DB 접근 권한과 RLS는
server-side 계정/connection 관리가 핵심이다. 반대로 나중에 Supabase Flutter SDK로 직접 table을
읽게 되면 RLS가 제품 안전의 1차 방어선이 된다.

해야 할 일:

- "Flutter direct DB access 없음"을 현재 release contract에 명시한다.
- direct Supabase access를 도입할 경우 RLS policy test를 선행 조건으로 둔다.
- user health tables와 medical source governance tables의 노출 정책을 분리한다.
- medical source governance는 public read로 풀더라도 `reviewed`/not expired view만 노출해야 한다.
- user health records는 `owner_subject_hash`만으로 client-side RLS를 설계하지 않는다. Auth subject와
  매핑 정책을 별도로 둔다.

완료 증거:

- direct DB access 여부가 README/setup 문서에 명시된다.
- RLS 적용 table에는 policy test 또는 SQL smoke가 있다.
- service-role/server-side key가 Flutter bundle에 들어가지 않는다.

### P1. food/supplement/medication DB와 medical source DB를 섞지 말아야 한다

현재 food record와 user medication은 사용자 컨텍스트 DB이고, medical source governance는 검수 지식 DB다.
둘은 같이 쓰이지만 같은 책임이 아니다.

해야 할 일:

- user record DB는 privacy/deletion/consent flow에 묶는다.
- medical source DB는 source review/audit/expiry flow에 묶는다.
- app context snapshot은 사용자 DB에서 필요한 요약만 가져오고 raw text나 대화 전문을 넣지 않는다.
- RAG/vector DB는 medical source 쪽과 learning/image vector DB 쪽을 계속 분리한다.

완료 증거:

- privacy deletion이 food/user medication/agent memory 범위를 포함한다.
- medical source row는 사용자 삭제로 삭제되지 않는다.
- learning/vector DB 문서와 medical Q&A RAG 문서가 서로 다른 feature flag를 가진다.

### P1. provider structured output은 capability matrix가 필요하다

상태: 1차 완료. JSON schema output 렌더링과 schema 실패 fallback 검증은
[21-agent-chatbot-structured-output-implementation-log.md](./21-agent-chatbot-structured-output-implementation-log.md)에
기록했다.

OpenAI-compatible endpoint라고 해서 `response_format`, JSON schema strictness, tool calling,
Responses API statefulness가 동일하지 않다. SGLang, Ollama, OpenAI를 같은 client로 다루더라도
capability 차이를 문서와 smoke로 고정해야 한다.

해야 할 일:

- provider별 capability matrix를 만든다.
- schema parse failure, unsupported field, forbidden wording, unsupported fact fallback을 각각 smoke한다.
- LLM section JSON schema와 UI rendering schema를 분리한다.
- provider가 실패해도 user-facing response는 deterministic renderer로 내려간다.

완료 증거:

- SGLang/Ollama/OpenAI별 structured output smoke 결과가 문서에 남는다.
- schema 실패 시 raw provider payload가 응답이나 DB에 저장되지 않는다.

1차 완료 내용:

- chatbot LLM request가 `json_schema` response format을 요청한다.
- schema에 맞는 JSON은 한국어 section answer로 렌더링한다.
- schema가 맞지 않는 JSON/provider text는 raw payload를 노출하지 않고 deterministic fallback으로 닫는다.

검증:

```powershell
python -m pytest -q --no-cov backend/ai_agent_chat/tests
```

결과:

```text
124 passed, 1 skipped
```

### P1. 분석 점수는 임시 heuristic임을 계속 고정해야 한다

`오늘 현재 분석 점수`와 `기록 기반 생활관리 점수`라는 이름은 맞다. 다만 UI가 건강 위험 점수처럼
읽히면 안 된다.

해야 할 일:

- score formula와 입력 feature를 문서화한다.
- 최소 조건 미달 시 낮은 점수 대신 `analysis_pending`으로 유지한다.
- 점수는 질병 위험, 치료 필요성, 건강 상태 평가가 아니라 기록 기반 생활관리 지표로만 표시한다.

완료 증거:

- Flutter text/golden에서 진단, 치료, 질병위험 같은 표현이 없다.
- score formula 변경 시 golden case가 깨진다.

### P2. source detail UI가 필요하다

상태: 1차 완료. Flutter source model/detail label이 `boundary_code`를 포함하도록 맞춘 구현과 검증은
[22-agent-chatbot-source-ui-observability-implementation-log.md](./22-agent-chatbot-source-ui-observability-implementation-log.md)에
기록했다.

backend는 `sources[]`와 source family를 내려주지만, 사용자가 근거를 확인하는 UI는 아직 얇다.

해야 할 일:

- chat bubble source chip/detail sheet를 만든다.
- 표시 필드는 `source_id`, `publisher`, `source_family`, `version_label`, `reviewed_at`,
  `expires_at`, `review_status`, `source_url`로 제한한다.
- stale/expired/draft source는 detail에 나오지 않는다.
- 공식 source URL만 clickable하게 한다.

완료 증거:

- answerable, boundary, unknown별 source 표시 정책이 widget/golden test로 고정된다.

1차 완료 내용:

- `ChatbotSource`가 `boundary_code`를 파싱한다.
- chat source label에 `boundaryCode`를 포함한다.
- Flutter parsing/widget test로 source metadata 표시 경로를 검증했다.

### P2. 운영 관측성을 raw-free metric으로 확장해야 한다

상태: 1차 완료. runtime event를 raw-free report payload로 집계하는 구현과 검증은
[22-agent-chatbot-source-ui-observability-implementation-log.md](./22-agent-chatbot-source-ui-observability-implementation-log.md)에
함께 기록했다.

운영에서 봐야 할 것은 "LLM이 답했나"가 아니라 "왜 fallback/unknown/boundary가 됐나"다.

해야 할 일:

- warning/fallback code를 구조화한다.
  - `schema_parse_failed`
  - `unsupported_fact_fallback`
  - `no_reviewed_source`
  - `needs_structured_lookup`
  - `source_stale`
  - `boundary_medical_decision`
- unknown backlog trend와 source expiry approaching report를 만든다.
- raw prompt 없이 answerability, provider, source_count, fallback_reason, topic category만 집계한다.

완료 증거:

- smoke/report에서 fallback reason과 source expiry 상태를 볼 수 있다.
- 운영 리포트가 다음 evidence coverage PR의 입력으로 쓰인다.

1차 완료 내용:

- `chatbot_runtime_report_payload()`가 answerability, provider, fallback reason, source expiry,
  boundary code를 집계한다.
- report payload는 raw prompt, raw answer, conversation을 복사하지 않는다.

검증:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog_report.py backend/Nutrition-backend/tests/unit/services/test_chatbot_unknown_backlog.py
C:\src\flutter\bin\flutter.bat test test\confirmed_payload_test.dart test\widget_test.dart
```

결과:

```text
8 passed
All tests passed! (9 Flutter tests)
```

## 6. 권장 작업 순서

현재 dirty worktree는 이미 크다. 다음 PR은 기능을 넓히기보다 아래 순서로 쪼개는 것이 맞다.

0. **Answer continuity PR** `[1차 완료]`
   - 짧은 후속 질문이 이전 사용자 발화의 음식/영양/복약 맥락을 planning 단계에서 잃지 않도록 한다.
   - assistant 답변은 grounding으로 쓰지 않고, 최근 user turn만 transient planning context로 사용한다.
   - 완료 기록은 [16-agent-chatbot-continuity-implementation-log.md](./16-agent-chatbot-continuity-implementation-log.md)에 둔다.

1. **DB/source governance audit PR** `[1차 완료]`
   - `04` 계약과 현재 `0009~0016` migration, seed, readiness, unknown backlog 상태를 다시 대조한다.
   - source promotion/deprecation/expiry/audit checklist를 문서화한다.
   - unknown backlog status lifecycle과 DB constraint는 `0017` migration으로 고정했다.
   - 완료 기록은 [17-agent-chatbot-source-governance-implementation-log.md](./17-agent-chatbot-source-governance-implementation-log.md)에 둔다.

2. **Medication/supplement entity normalization PR** `[1차 완료]`
   - user medication과 supplement ingredient를 공식 identifier/alias/class 기반으로 정규화한다.
   - lithium, St John's wort, grapefruit, vitamin K, levothyroxine 같은 P0 후보의 normalized test를 둔다.
   - broad medication term은 병용 가능/불가로 답하지 않고 `needs_more_info`로 닫는다.
   - 완료 기록은 [18-agent-chatbot-entity-normalization-implementation-log.md](./18-agent-chatbot-entity-normalization-implementation-log.md)에 둔다.

3. **Reviewed boundary/evidence coverage PR** `[1차 완료]`
   - unknown backlog와 LLM-WIKI 후보를 공식 source 기반으로 하나씩 승격한다.
   - source/version/evidence 또는 boundary/golden/smoke를 한 세트로 추가한다.
   - P0 boundary runtime 응답은 `boundary_code`와 source metadata를 남긴다.
   - 완료 기록은 [19-agent-chatbot-boundary-coverage-implementation-log.md](./19-agent-chatbot-boundary-coverage-implementation-log.md)에 둔다.

4. **RAG/hybrid retrieval design PR** `[1차 완료]`
   - `medical_rag_chunks`, `tsvector`, pgvector, RRF, low confidence fallback, eval set을 설계한다.
   - 구현 전 문서와 test skeleton을 먼저 둔다.
   - DB evidence retrieval은 reviewed/not-expired gate를 먼저 통과해야 한다.
   - 완료 기록은 [20-agent-chatbot-retrieval-eval-implementation-log.md](./20-agent-chatbot-retrieval-eval-implementation-log.md)에 둔다.

5. **Provider capability audit PR** `[1차 완료]`
   - SGLang, Ollama, OpenAI structured output 차이를 smoke와 문서로 고정한다.
   - JSON schema success/failure 경로는 unit regression으로 고정했다.
   - 완료 기록은 [21-agent-chatbot-structured-output-implementation-log.md](./21-agent-chatbot-structured-output-implementation-log.md)에 둔다.

6. **Source detail UI PR** `[1차 완료]`
   - Flutter chat/analysis source detail UX를 backend `sources[]` 계약과 맞춘다.
   - `boundary_code`를 mobile source model과 source label에 연결했다.
   - 완료 기록은 [22-agent-chatbot-source-ui-observability-implementation-log.md](./22-agent-chatbot-source-ui-observability-implementation-log.md)에 둔다.

7. **Operational report PR** `[1차 완료]`
   - unknown trend, fallback reason, source expiry, provider capability를 raw-free report로 묶는다.
   - runtime report payload가 answerability/provider/fallback/source expiry/boundary code를 raw-free로 집계한다.
   - 완료 기록은 [22-agent-chatbot-source-ui-observability-implementation-log.md](./22-agent-chatbot-source-ui-observability-implementation-log.md)에 둔다.

## 7. 완료 판단 기준

아래가 충족되어야 "운영형 agent에 가까워졌다"고 말할 수 있다.

- 반복 unknown topic이 source/version/evidence/boundary/golden/smoke 세트로 승격된다.
- 약물/영양제 상호작용은 normalized entity pair 또는 class pair로 판단한다.
- LLM-WIKI 항목은 공식 source 검수 전 사용자-facing evidence로 쓰이지 않는다.
- `medical_rag_chunks` retrieval은 reviewed/not expired filter, hybrid retrieval, low confidence fallback,
  `AnswerCardNormalizer` gate를 모두 가진다.
- Flutter는 DB를 직접 읽지 않거나, 직접 읽는 경우 RLS policy test가 먼저 있다.
- user health DB와 medical source governance DB의 privacy/audit 책임이 섞이지 않는다.
- provider structured output 실패가 deterministic fallback으로 검증된다.
- 분석 점수는 생활관리 기록 지표로만 보인다.
- UI에서 reviewed source metadata를 확인할 수 있다.
- 운영 리포트가 raw prompt 없이 answerability, fallback reason, source expiry, unknown topic trend를 보여준다.
