# Supabase 챗봇 개발 DB 설정

이 문서는 챗봇을 빠르게 개발하기 위해 Supabase PostgreSQL을 개발 DB로 쓰는 방법을
정리한다. 제품 구조는 바꾸지 않는다. Flutter는 DB에 직접 붙지 않고, 계속 FastAPI
API만 호출한다.

```text
Flutter
-> FastAPI backend
-> Supabase PostgreSQL
-> ai_agent_chat
```

## 판단

- Supabase는 별도 DB 제품이 아니라 관리형 PostgreSQL이다.
- Lemon Aid 전체 아키텍처의 기준은 계속 PostgreSQL이다.
- 챗봇 개발 속도를 위해 로컬 PostgreSQL 대신 Supabase PostgreSQL을 사용할 수 있다.
- 의료/영양/복약 안전 정책, 동의, 개인정보 최소화, source governance는 FastAPI 계층에
  둔다.
- Flutter에서 Supabase 테이블을 직접 읽고 쓰는 방식은 이번 챗봇 개발 범위에서 제외한다.

## 사용할 DB 범위

Supabase 개발 DB에는 FastAPI 서버가 쓰는 Alembic 관리 테이블과 챗봇 검수 지식 테이블을
둔다. 챗봇 지식 경로에서 직접 쓰는 핵심 테이블은 다음과 같다.

- `medical_sources`
- `medical_source_versions`
- `medical_evidence_items`
- `medical_policy_boundaries`
- `medical_rag_chunks`
- `chatbot_unknown_knowledge_events`

저장하지 않는 것:

- 사용자 질문 원문
- raw prompt
- raw OCR 전문
- 대화 전문
- 개인정보성 free text

## 환경 변수

Supabase 프로젝트를 만든 뒤 Dashboard의 PostgreSQL connection string을
`DATABASE_URL`에 넣는다. Python async SQLAlchemy 경로에서는 드라이버가
`postgresql+asyncpg`여야 한다.

```powershell
$env:DATABASE_URL="postgresql+asyncpg://postgres.<project-ref>:<password>@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres?ssl=require"
$env:AUTH_MODE="disabled"
$env:LLM_PROVIDER="sglang"
$env:SGLANG_BASE_URL="http://127.0.0.1:30000/v1"
$env:SGLANG_MODEL="Qwen/Qwen2.5-0.5B-Instruct"
$env:ALLOW_EXTERNAL_LLM="false"
```

주의:

- 비밀번호와 실제 connection string은 커밋하지 않는다.
- Supabase pooler 주소, 포트, project ref는 프로젝트마다 다르다.
- 로컬 개발에서는 Session Pooler 또는 Direct connection 중 하나를 선택할 수 있다.
- FastAPI처럼 오래 떠 있는 서버는 Session Pooler 또는 Direct connection으로 시작한다.
- 서버리스/짧은 연결 환경은 Transaction Pooler를 검토하되, prepared statement 제한을
  따로 확인한다.

## 마이그레이션

Supabase DB도 일반 PostgreSQL처럼 Alembic으로 스키마를 올린다. 가능하면 Dashboard의
Direct connection을 쓰고, 로컬 네트워크에서 IPv6 연결이 어렵다면 Session Pooler로 먼저
검증한다.

```powershell
cd C:\MyWorkspace\lemon_aid\ai-agent-backend-integration\backend
python -m alembic -c alembic.ini upgrade head
```

챗봇 unknown backlog와 evidence AnswerCard 필드는 `0010_add_chatbot_unknown_backlog`
마이그레이션 이후부터 포함된다.

## 챗봇 스모크 테스트

SGLang/OpenAI-compatible 서버가 떠 있고 `DATABASE_URL`이 Supabase를 가리키는 상태에서
다음 명령을 실행한다.

```powershell
cd C:\MyWorkspace\lemon_aid\ai-agent-backend-integration
python backend\scripts\smoke_ai_agent_server.py --database-url $env:DATABASE_URL
```

이 스모크 테스트는 FastAPI 서버를 띄운 뒤 동의, 일일 코칭, 챗봇 API를 확인한다. DB
마이그레이션도 기본적으로 함께 실행한다.

## 운영 기준

- production-like 환경에서는 DB reviewed source/evidence만 답변 근거로 사용한다.
- reviewed 되지 않았거나 stale source version인 evidence는 `AnswerCard`로 변환하지 않는다.
- DB 지식이 없으면 LLM을 호출하지 않고 unknown 답변으로 간다.
- unknown 답변은 `chatbot_unknown_knowledge_events`에 개인정보 없이 부족한 지식 주제만
  기록한다.
- Supabase RLS는 앱 직접 접근을 열 때 다시 설계한다. 현재 구조에서는 FastAPI 서버가
  service role 또는 서버 전용 DB 연결로 접근하고, 클라이언트에는 DB 키를 주지 않는다.

## 다음 결정

원격 Supabase 프로젝트를 실제로 만들려면 조직과 비용 확인이 필요하다. 현재 개발 후보는
다음과 같다.

- 조직: `changmin5957-sys's Org`
- 프로젝트명 후보: `lemon-aid-chatbot-dev`
- 리전 후보: `ap-northeast-2`

프로젝트가 생성되면 connection string을 받아 `.env` 또는 로컬 셸 환경 변수에만 설정하고,
Alembic 마이그레이션과 스모크 테스트를 순서대로 실행한다.

## 생성된 개발 프로젝트

2026-05-29 기준 챗봇 개발용 Supabase 프로젝트를 생성했다.

- 프로젝트명: `lemon-aid-chatbot-dev`
- 프로젝트 ref: `ajgvoxttzsjcwtphtsuz`
- 리전: `ap-northeast-2`
- 상태: `ACTIVE_HEALTHY`
- 비용 확인 결과: Free 조직에서 프로젝트 생성 비용 `월 0`

MCP로 적용한 원격 migration:

- `create_chatbot_medical_knowledge_subset`
  - `medical_sources`
  - `medical_source_versions`
  - `medical_evidence_items`
  - `chatbot_unknown_knowledge_events`
  - magnesium supplement caution seed evidence
  - sodium dinner adjustment seed evidence
- `secure_chatbot_medical_knowledge_subset`
  - public schema 테이블 RLS 활성화
  - `medical_evidence_items.source_version_id` FK 인덱스 추가
- `create_fastapi_core_tables`
  - FastAPI core, privacy, supplement, health sync 테이블 추가
  - `alembic_version`을 `0010_add_chatbot_unknown_backlog`로 표시
- `create_fastapi_agent_and_regulated_tables`
  - agent memory, regulated OCR, medical policy/RAG 테이블 추가
  - `vector` extension 활성화
- `enable_rls_on_fastapi_public_tables`
  - 모든 public table에 RLS 활성화
- `add_covering_indexes_for_fk_advisors`
  - Supabase performance advisor가 지적한 FK covering index 추가
- `seed_chatbot_reviewed_evidence_coverage`
  - registry bootstrap 수준의 reviewed source/evidence coverage를 Supabase DB에 seed
  - `alembic_version`을 `0011_seed_chatbot_reviewed_evidence`로 표시
- `seed_chatbot_policy_boundaries`
  - P0 병용/상호작용 reviewed policy boundary 6개 seed
  - `alembic_version`을 `0012_seed_chatbot_policy_boundaries`로 표시
- `create_chatbot_unknown_backlog_summary_view`
  - `chatbot_unknown_knowledge_backlog_summary` view 생성
  - `security_invoker = true`로 underlying table RLS를 따르게 설정
  - `alembic_version`을 `0013_create_chatbot_unknown_backlog_summary_view`로 표시

확인된 seed evidence:

- reviewed source 7개
- reviewed current source version 7개
- reviewed evidence item 14개
- reviewed policy boundary 6개
- privacy-safe unknown backlog summary view 1개
- 주요 topic:
  - `magnesium_supplement_caution`
  - `sodium_dinner_adjustment`
  - `diabetes_plate_method`
  - `diabetes_healthy_living`
  - `adult_activity`
  - `adult_sleep`
  - `exercise_dizziness`
  - `hypertension_meal_adjustment`
  - `kidney_disease_meal_caution`
  - `vitamin_d_food_candidates`
  - `protein_food_candidates`
  - `fiber_food_candidates`
  - `general_health_record_review`
  - `supplement_label_check`

현재 원격 DB 확인 결과:

- public table 29개
- `alembic_version.version_num = 0013_create_chatbot_unknown_backlog_summary_view`
- public table 29개 모두 RLS 활성화
- seed source 7개, source version 7개, evidence item 14개
- reviewed policy boundary 6개:
  - `p0_st_johns_wort_antidepressant`
  - `p0_grapefruit_statin`
  - `p0_potassium_salt_substitute`
  - `p0_nitrate_pde5_inhibitor`
  - `p0_serotonergic_supplement_antidepressant`
  - `p0_statin_red_yeast_rice`
- `chatbot_unknown_knowledge_backlog_summary` columns:
  - `status`
  - `category`
  - `primary_intent`
  - `missing_topic`
  - `needed_evidence_type`
  - `retrieval_status`
  - `event_count`
  - `latest_event_at`

Supabase security advisor는 RLS가 켜졌지만 policy가 없다는 INFO를 표시한다. 현재 구조에서는
Flutter가 Supabase Data API에 직접 접근하지 않고 FastAPI 서버가 DB에 접근하므로, anon/client
접근은 기본 거부 상태로 둔다. Flutter 직접 접근을 열 때만 별도 RLS policy를 설계한다.

Supabase security advisor의 `rls_disabled_in_public` ERROR와 performance advisor의
`unindexed_foreign_keys` INFO는 해소했다. 남은 항목은 다음과 같다.

- `rls_enabled_no_policy` INFO: 현재 anon/client 접근을 열지 않는 의도된 잠금 상태다.
- `extension_in_public` WARN: 현재 Alembic이 `CREATE EXTENSION IF NOT EXISTS vector`를 public
  schema에 만든다. extension schema 이동은 pgvector 타입 search path 영향이 있으므로 별도
  migration으로 다룬다.
- `unused_index` INFO: 새 dev DB라 아직 쿼리 사용 통계가 없어 발생한다.

로컬에는 `supabase` CLI와 `psql` CLI가 설치되어 있지 않은 상태를 확인했다. 전체 FastAPI smoke는
Dashboard에서 DB connection string/password를 받아 서버 환경 변수에 설정한 뒤 실행한다. 현재
원격 DB는 MCP로 FastAPI 테이블을 맞춰 두었으므로, smoke 시에는 Alembic을 다시 올리기보다
`--skip-db-upgrade` 옵션을 먼저 쓰는 경로가 안전하다.

```powershell
python backend\scripts\smoke_ai_agent_server.py --database-url $env:DATABASE_URL --skip-db-upgrade --skip-sglang-check
```

이 smoke는 Supabase Dashboard에서 복사한 `postgresql://...sslmode=require` 형식의 connection
string도 자동으로 `postgresql+asyncpg://...ssl=require`로 정규화한다. 기본 동작은 다음까지
확인한다.

- FastAPI health check
- sensitive health consent route
- daily coaching 2회 호출과 `agent_memory` 재사용
- `/api/v1/ai-agent/chat`의 `answerability`, `sources[]`
- reviewed sodium/hypertension 질문의 `answerability = answerable`
- reviewed nutrition source(`kdris-2025` 또는 `kdca-healthinfo`) 반환
- `unknown_no_reviewed_source` 질문 1회 호출
- `chatbot_unknown_knowledge_events` row 증가

`DATABASE_URL`이 없으면 스크립트가 `lemon-aid-chatbot-dev` 프로젝트 ref
(`ajgvoxttzsjcwtphtsuz`)와 Supabase pooler host를 포함한 placeholder 예시를 출력한다.
실제 password는 Supabase Dashboard에서 복사해 로컬 환경 변수로만 설정한다.

이미 떠 있는 서버를 대상으로 확인하거나 backlog row 증가 확인을 생략해야 하면 아래 옵션을 사용한다.

```powershell
python backend\scripts\smoke_ai_agent_server.py --database-url $env:DATABASE_URL --use-existing-server --skip-db-upgrade --skip-sglang-check --skip-unknown-backlog-check
```

FastAPI 전체 서버를 띄우기 전에 DB evidence -> AnswerCard -> deterministic chatbot 경로만
먼저 확인하려면 아래 smoke를 실행한다. 기본값은 `environment=production`이므로 registry
fallback 없이 Supabase DB의 reviewed evidence만 사용한다.

```powershell
cd C:\MyWorkspace\lemon_aid\ai-agent-backend-integration
python backend\scripts\smoke_chatbot_db_evidence.py --database-url $env:DATABASE_URL --preset hypertension-sodium
python backend\scripts\smoke_chatbot_db_evidence.py --database-url $env:DATABASE_URL --preset magnesium-blood-pressure-med
python backend\scripts\smoke_chatbot_db_evidence.py --database-url $env:DATABASE_URL --preset unknown-herbal-blend
python backend\scripts\smoke_chatbot_db_evidence.py --database-url $env:DATABASE_URL --preset unknown-lithium-selenium
```

이 smoke는 DB 연결 문자열을 출력하지 않고, evidence record 수, answerability, source metadata,
safety warning만 요약한다.

## Golden answer eval

Supabase live smoke 전후로 사용자-facing 답변 품질을 빠르게 확인하려면 deterministic golden eval을
실행한다. 이 eval은 나트륨 저녁 조정, 혈압약+마그네슘, 응급 증상, 신장질환+채소/과일,
당뇨 과식 후 다음 끼니, P0 병용, unknown 질문의 `answerability`, 필수 문구, 금지 문구,
source metadata를 검사한다.

```powershell
cd C:\MyWorkspace\lemon_aid\ai-agent-backend-integration
python backend\scripts\eval_chatbot_golden.py
```

특정 케이스만 확인할 수도 있다.

```powershell
python backend\scripts\eval_chatbot_golden.py --case magnesium_blood_pressure_med
python backend\scripts\eval_chatbot_golden.py --case kidney_disease_vegetable_fruit_potassium
python backend\scripts\eval_chatbot_golden.py --case diabetes_overeating_next_meal
python backend\scripts\eval_chatbot_golden.py --case p0_grapefruit_lipid_med
python backend\scripts\eval_chatbot_golden.py --case p0_lithium_selenium_supplement
```

## Local manual QA presets

FastAPI 서버나 Supabase DB 연결 전에도 현재 챗봇 답변 톤과 boundary를 바로 확인할 수 있다.
`--llm none`은 LLM을 호출하지 않고 deterministic fallback/renderer 경로를 보여준다.

```powershell
cd C:\MyWorkspace\lemon_aid\ai-agent-backend-integration
python backend\scripts\ask_chatbot_agent.py --preset hypertension-sodium-dinner --llm none
python backend\scripts\ask_chatbot_agent.py --preset magnesium-blood-pressure-med --llm none
python backend\scripts\ask_chatbot_agent.py --preset kidney-vegetable-fruit-potassium --llm none
python backend\scripts\ask_chatbot_agent.py --preset diabetes-overeating-next-meal --llm none
python backend\scripts\ask_chatbot_agent.py --preset p0-grapefruit-lipid-med --llm none
python backend\scripts\ask_chatbot_agent.py --preset unknown-lithium-selenium --llm none
python backend\scripts\ask_chatbot_agent.py --preset urgent-chest-pain --llm none
```

각 명령은 답변 본문과 함께 `provider`, `answerability`, `source_families`, `sources`,
`safety_warnings`를 출력한다. P0와 응급 질문은 LLM을 호출하지 않아야 한다.
`unknown-lithium-selenium`은 reviewed boundary로 승격되어 `medical_decision_boundary`가
나와야 하고, 검수 source/boundary가 아직 없는 unknown 질문은 검수 지식이 없다는 답변으로
남아야 한다.

## Unknown backlog triage

`unknown_no_reviewed_source` 응답이 쌓이면 원문 질문을 보지 않고도 반복되는 검수 지식 공백을
확인할 수 있다. 리포트는 `chatbot_unknown_knowledge_events`의 구조화된 필드만 묶어서 보여주며,
사용자 질문 원문, raw prompt, OCR 원문, 대화 전문은 출력하지 않는다.

Supabase Dashboard에서는 아래 view를 직접 열어 반복되는 topic을 볼 수 있다.

```sql
select *
from chatbot_unknown_knowledge_backlog_summary
order by event_count desc, latest_event_at desc;
```

```powershell
cd C:\MyWorkspace\lemon_aid\ai-agent-backend-integration
python backend\scripts\report_chatbot_unknown_backlog.py --database-url $env:DATABASE_URL --status open --format markdown
```

리포트 기준:

- `missing_topic`과 `needed_evidence_type`이 반복되는 항목부터 검수 후보로 올린다.
- 운영자는 공식 자료 또는 내부 검수 자료를 찾아 `medical_sources`,
  `medical_source_versions`, `medical_evidence_items`에 reviewed evidence로 추가한다.
- evidence를 추가할 때는 source version, expiry, allowed wording, blocked wording, golden test를
  함께 추가한다.
- backlog event의 `status`는 검수 evidence로 승격하면 `reviewed`, 제품 범위 밖이면
  `dismissed`로 닫는다.
