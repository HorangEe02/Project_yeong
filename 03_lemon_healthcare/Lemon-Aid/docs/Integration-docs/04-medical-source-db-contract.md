# 04. 의료정보 DB 계약

> Status: DB schema and implementation TODO draft
> 작성일: 2026-05-28
> 기준 브랜치: `feat/ai-agent-backend-integration`
> 상위 안전 계약: [03-ai-agent-safety-porting-contract.md](./03-ai-agent-safety-porting-contract.md)
> 관련 설계: [45-development-dependency-split.md](../Nutrition-docs/45-development-dependency-split.md),
> [dev-guides/31-medical-knowledge-layer.md](../Nutrition-docs/dev-guides/31-medical-knowledge-layer.md)

## 1. 목적

이 문서는 DB 담당자가 사용자 개인정보 DB만 설계하지 않도록, Lemon Aid의
의료정보 DB가 반드시 보존해야 하는 source, claim, review, boundary, RAG 연결
계약을 정의한다.

`03` 문서는 AI Agent 이식 시 지켜야 할 상위 안전/응답/저장 경계다. 이 문서는
그 경계를 DB schema와 migration 설계로 옮기기 위한 상세 계약이다.

핵심 결정:

- 의료정보 DB는 사용자 개인정보 DB와 분리해서 설계한다.
- MVP에서는 거대한 의료 지식 DB를 만들지 않고 reviewed source와 claim 단위
  governance부터 만든다.
- AI/backend 팀은 reviewed/draft 승격 기준, allowed wording, blocked wording,
  safety boundary mapping, RAG 노출 조건을 소유한다.
- DB 담당자는 migration, FK/index, audit/history, source versioning을 소유한다.
- RAG/vector DB는 reviewed source governance가 안정된 뒤 마지막에 연결한다.

## 2. 저장 금지 경계

다음 값은 의료정보 DB, 사용자 응답, source card, run log, RAG index에 저장하거나
노출하지 않는다.

- raw prompt 또는 full prompt
- raw LLM response, provider payload 전문
- raw OCR text
- raw image bytes, base64 image, EXIF, 원본 파일명
- draft/paper/internal note의 사용자-facing 노출
- 사용자 개인정보, 시크릿, provider key, service-account JSON

의료정보 DB는 검수된 출처와 claim metadata를 저장한다. 사용자별 건강 기록,
프로필, 동의 상태, 분석 결과 이력은 별도 사용자 DB 책임으로 둔다.

## 3. 최소 테이블 계약

아래 이름은 구현 기준 이름이다. 실제 migration에서 naming convention을 조정할 수
있지만, 필드 의미와 관계는 보존해야 한다.

### `medical_sources`

KDCA, KDRIs, MFDS 등 출처 원장을 관리한다.

| 필드 | 필수 | 의미 |
| --- | --- | --- |
| `id` | yes | stable source id. 예: `kdca-healthinfo`, `kdris-2025`, `mfds-drug-safety` |
| `source_family` | yes | UI/source card에 노출 가능한 family. 예: `public_health_guidance`, `nutrition_reference`, `drug_safety` |
| `publisher` | yes | 발행 기관 |
| `title` | yes | 출처 제목 |
| `canonical_url` | optional | 공식 원문 또는 API 안내 URL |
| `jurisdiction` | yes | 적용 지역. 예: `KR`, `GLOBAL` |
| `source_type` | yes | `guideline`, `public_health`, `regulator`, `reference_intake`, `paper`, `internal_review` |
| `default_review_status` | yes | `draft`, `reviewed`, `deprecated`, `paper_candidate` |
| `owner` | yes | 검수 책임자 또는 팀 |
| `created_at`, `updated_at` | yes | audit 기준 timestamp |

보존 기준:

- 사용자-facing 응답에는 `reviewed` 상태의 source family만 내려간다.
- `paper_candidate`와 `internal_review`는 research backlog로만 취급하고 사용자-facing
  source card나 RAG 결과에 넣지 않는다.
- 동일 기관의 여러 문서는 source id를 분리하되 family는 같은 값으로 묶을 수 있다.

### `medical_source_versions`

출처 버전, 검수일, 만료일, 담당자를 관리한다.

| 필드 | 필수 | 의미 |
| --- | --- | --- |
| `id` | yes | version row id |
| `source_id` | yes | `medical_sources.id` FK |
| `version_label` | yes | 발행/검수 버전. 예: `2025`, `2026-05-review-1` |
| `published_at` | optional | 원문 발행일 |
| `reviewed_at` | yes | 제품 반영 검수일 |
| `expires_at` | yes | stale 판정 기준 |
| `review_status` | yes | `draft`, `reviewed`, `deprecated`, `paper_candidate` |
| `reviewer` | yes | 검수자 또는 책임 팀 |
| `review_note` | optional | 내부 검수 요약. 사용자-facing 노출 금지 |
| `created_at`, `updated_at` | yes | audit 기준 timestamp |

보존 기준:

- `expires_at`이 지난 reviewed source는 사용자-facing source로 바로 내려가지 않는다.
- stale source는 backend에서 `source_stale` warning 또는 deterministic fallback으로
  처리할 수 있어야 한다.
- version row는 수정 삭제보다 새 row 추가를 우선한다. 기존 결과의 재현성을 위해
  과거 `source_version_id`를 보존한다.

### `medical_evidence_items`

사용자에게 말해도 되는 검수된 claim 단위를 관리한다.

| 필드 | 필수 | 의미 |
| --- | --- | --- |
| `id` | yes | evidence item id |
| `source_version_id` | yes | `medical_source_versions.id` FK |
| `topic` | yes | 예: `diabetes`, `hypertension`, `kidney_disease`, `supplement_interaction` |
| `audience` | yes | 예: `adult`, `older_adult`, `pregnancy`, `chronic_condition` |
| `claim_summary` | yes | 내부 검수용 claim 요약 |
| `allowed_user_wording` | yes | 사용자에게 말해도 되는 표현 |
| `blocked_wording` | yes | 금지 표현 또는 금지 패턴 |
| `applicability_note` | optional | 적용 조건과 한계 |
| `caution_level` | yes | `info`, `caution`, `professional_review`, `blocked` |
| `review_status` | yes | `draft`, `reviewed`, `deprecated`, `paper_candidate` |
| `algorithm_version` | optional | 특정 정책/알고리즘 버전과 연결될 때 사용 |
| `created_at`, `updated_at` | yes | audit 기준 timestamp |

보존 기준:

- 사용자-facing claim은 `review_status=reviewed`만 가능하다.
- `allowed_user_wording`은 그대로 UI 문구가 아니라 LLM/backend가 넘지 말아야 할 표현
  경계다.
- `blocked_wording`은 SafetyGuard, golden test, reviewer checklist에 재사용할 수
  있어야 한다.

### `medical_policy_boundaries`

복약, 진단, 검사수치, 혈당, 영양제 병용 같은 금지/주의 경계를 관리한다.

| 필드 | 필수 | 의미 |
| --- | --- | --- |
| `id` | yes | boundary id |
| `boundary_code` | yes | 예: `medication_change`, `diagnosis_treatment`, `lab_value_interpretation`, `glucose_prediction`, `supplement_interaction` |
| `topic` | yes | 적용 topic |
| `trigger_intent` | yes | 사용자 의도 분류 기준 |
| `response_status` | yes | `blocked`, `professional_review`, `caution`, `needs_more_info` |
| `required_warning_code` | yes | API warning code |
| `allowed_response_pattern` | yes | 허용 응답 방향 |
| `blocked_response_pattern` | yes | 금지 응답 방향 |
| `source_version_id` | optional | 근거 source version FK |
| `review_status` | yes | `draft`, `reviewed`, `deprecated` |
| `created_at`, `updated_at` | yes | audit 기준 timestamp |

보존 기준:

- 이 테이블은 LLM에게 의료 판단을 맡기기 위한 prompt 재료가 아니다.
- backend safety classifier와 contract test가 같은 `boundary_code`를 참조할 수 있어야 한다.
- `reviewed`가 아닌 boundary는 production-like 사용자 응답 경로에 연결하지 않는다.

### `medical_rag_chunks`

나중에 RAG용으로 사용할 reviewed snippet metadata를 관리한다.

| 필드 | 필수 | 의미 |
| --- | --- | --- |
| `id` | yes | chunk id |
| `evidence_item_id` | yes | `medical_evidence_items.id` FK |
| `source_version_id` | yes | `medical_source_versions.id` FK |
| `chunk_text` | yes | 검수된 snippet. raw OCR/raw web scrape 저장 금지 |
| `chunk_hash` | yes | 중복과 변경 감지용 hash |
| `embedding_status` | yes | `not_indexed`, `indexed`, `stale`, `disabled` |
| `review_status` | yes | `draft`, `reviewed`, `deprecated` |
| `expires_at` | yes | source stale 판정 기준 |
| `created_at`, `updated_at` | yes | audit 기준 timestamp |

보존 기준:

- RAG index에는 `review_status=reviewed`이고 만료되지 않은 chunk만 들어간다.
- `paper_candidate`, `draft`, 내부 조사 snippet은 embedding 대상에서 제외한다.
- retrieval 실패 또는 stale source는 deterministic fallback과 safety boundary를 우회하지 않는다.

## 4. 관계와 인덱스 기준

필수 관계:

- `medical_source_versions.source_id` -> `medical_sources.id`
- `medical_evidence_items.source_version_id` -> `medical_source_versions.id`
- `medical_policy_boundaries.source_version_id` -> `medical_source_versions.id` nullable FK
- `medical_rag_chunks.evidence_item_id` -> `medical_evidence_items.id`
- `medical_rag_chunks.source_version_id` -> `medical_source_versions.id`

필수 인덱스:

- `medical_sources(source_family, default_review_status)`
- `medical_source_versions(source_id, review_status, expires_at)`
- `medical_evidence_items(topic, audience, review_status)`
- `medical_policy_boundaries(boundary_code, review_status)`
- `medical_rag_chunks(review_status, embedding_status, expires_at)`
- `medical_rag_chunks(chunk_hash)` unique 또는 중복 방지 기준

Audit/history 기준:

- delete보다 `deprecated` 또는 새 version row 추가를 우선한다.
- reviewed -> draft 회귀, reviewed -> deprecated, expires_at 변경은 audit에 남긴다.
- 누가 언제 어떤 source/version/claim을 사용자-facing 가능 상태로 승격했는지 추적할 수
  있어야 한다.

## 5. DB 담당자 전달 TODO

DB 담당자가 맡을 영역:

- 위 최소 테이블의 migration 초안 작성
- FK, unique constraint, index 설계
- reviewed/deprecated/history 변경 audit 구조 설계
- source versioning과 stale source 조회 기준 설계
- 사용자 DB와 의료정보 DB의 분리 경계 확인

반드시 보존해야 할 필드 의미:

- 모든 사용자-facing source는 `source_id`, `source_family`, `review_status`,
  `source_version_id` 또는 `version_label`, `reviewed_at`, `expires_at`을 추적할 수
  있어야 한다.
- 모든 사용자-facing 의료 응답은 `algorithm_version`과 연결될 수 있어야 한다.
- 모든 claim은 `allowed_user_wording`과 `blocked_wording` 경계를 가져야 한다.
- 모든 RAG 후보 chunk는 reviewed 여부와 expiry 여부를 DB query만으로 판정할 수
  있어야 한다.

AI/backend 팀이 맡을 영역:

- `reviewed`, `draft`, `paper_candidate`, `deprecated` 승격/차단 기준
- allowed wording과 blocked wording의 실제 문구 검수
- safety boundary mapping과 warning code 정의
- RAG 노출 조건과 fallback 동작 정의
- 사용자-facing source card shape와 backend response contract

## 6. Backend 계약 테스트 TODO

Migration 구현 전후로 아래 테스트를 backend contract test 또는 integration test로
고정한다.

- `draft` source는 사용자 응답, source card, prompt grounding에 나오지 않는다.
- `paper_candidate`는 RAG 결과나 source card에 나오지 않는다.
- `review_status=reviewed`만 사용자-facing source로 내려간다.
- `expires_at`이 지난 source는 `source_stale` warning 또는 fallback으로 처리한다.
- 의료 질문 응답에는 `source_id`, `source_family`, `review_status`,
  `algorithm_version`이 보존된다.
- RAG retrieval 실패는 deterministic answer와 safety boundary를 우회하지 않는다.
- raw prompt, raw LLM response, raw OCR text, raw image metadata가 DB row나 API
  response에 저장/노출되지 않는다.

## 7. 구현 순서

1. 이 문서와 DB 담당자 전달 TODO를 먼저 합의한다.
2. migration/schema PR에서 table, FK, index, audit/history를 추가한다.
3. backend contract test로 reviewed/draft/stale source 동작을 고정한다.
4. source registry와 기존 readiness check를 DB 조회로 옮길지 결정한다.
5. reviewed source governance가 안정된 뒤 RAG/vector DB를 연결한다.

RAG는 답변 품질 보강 계층일 뿐이며, safety boundary나 deterministic backend 판단을
대체하지 않는다.

## 8. 최종 완수 기준

이 문서의 계약은 아래 조건이 모두 충족될 때 완수된 것으로 본다.

- Schema 계약 완료: `medical_sources`, `medical_source_versions`,
  `medical_evidence_items`, `medical_policy_boundaries`, `medical_rag_chunks` 5개
  의료 source governance 테이블이 migration과 ORM 모델에 반영되어 있다.
- Runtime 계약 완료: 사용자-facing 응답, source card, readiness 판정은
  `reviewed` source만 사용하며, draft/stale/paper candidate source는 노출하지 않는다.
- Safety 계약 완료: `draft`, `paper_candidate`, stale source, raw prompt, raw LLM
  response, raw OCR text, raw image 저장 금지를 검증하는 테스트가 있다.
- Team merge 기준 완료: 팀원 코드는 대형 merge가 아니라 이 문서의 계약 단위 diff로만
  비교하고 필요한 부분만 이식한다.

## 9. DB 구현 체크리스트

실제 schema 구현 PR은 아래 파일과 테스트를 기준으로 작성한다.

- Alembic migration 파일은
  `backend/alembic/versions/0009_create_medical_source_governance_tables.py`로 만든다.
- `down_revision`은 현재 head인 `0008_create_reminder_preferences`로 둔다.
- ORM 모델은 `backend/Nutrition-backend/src/models/db/medical_source.py`에 둔다.
- `backend/Nutrition-backend/src/models/db/__init__.py`에 새 모델 export를 추가한다.
- `backend/Nutrition-backend/tests/unit/db/test_models.py`에 아래 테스트를 추가한다.
  - metadata에 5개 의료 source governance 테이블이 등록되어 있는지 확인한다.
  - 각 테이블의 필수 컬럼이 존재하는지 확인한다.
  - `review_status`, `default_review_status`, `source_type`, `caution_level`,
    `response_status`, `embedding_status` 같은 enum 성격 필드에 named
    `CheckConstraint`가 있는지 확인한다.
  - 필수 FK, unique/index가 존재하는지 확인한다.
  - raw prompt, raw LLM response, raw OCR text, raw image bytes/base64/image metadata를
    저장하는 컬럼이 없는지 확인한다.
- `backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py`의 head 기대값을
  `0009_create_medical_source_governance_tables`로 갱신한다.

구현 PR에서 최소 실행해야 할 테스트:

```powershell
python -m pytest -q backend/Nutrition-backend/tests/unit/db/test_models.py
python -m pytest -q backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py
```

## 10. Schema 세부 결정

구현자는 아래 결정을 바꾸지 않고 migration과 ORM에 반영한다. 다른 선택지가 필요하면
구현 전에 이 문서를 먼저 갱신한다.

- `medical_sources.id`는 `String(80)` primary key로 둔다.
- 나머지 4개 테이블의 `id`는 UUID primary key로 둔다.
- 날짜는 SQLAlchemy `Date`를 사용한다.
- timestamp는 기존 DB 모델의 `TimestampMixin`을 사용한다.
- 긴 문구와 snippet은 `Text`를 사용한다.
- enum 성격 필드는 DB enum이 아니라 `String`과 named `CheckConstraint`로 구현한다.
- JSON payload는 기본 사용하지 않는다.
- audit metadata가 필요하면 새 JSON 컬럼을 만들지 않고 기존 `audit_logs.event_metadata`를
  사용한다.
- production seed data는 migration에 넣지 않는다.
- bootstrap/admin seed가 필요하면 별도 PR에서 source와 검수 책임자를 명시해 추가한다.

권장 constraint 이름:

- `ck_medical_sources_default_review_status`
- `ck_medical_sources_source_type`
- `ck_medical_source_versions_review_status`
- `ck_medical_evidence_items_caution_level`
- `ck_medical_evidence_items_review_status`
- `ck_medical_policy_boundaries_response_status`
- `ck_medical_policy_boundaries_review_status`
- `ck_medical_rag_chunks_embedding_status`
- `ck_medical_rag_chunks_review_status`

## 11. Audit 및 상태 용어 기준

새 audit table은 만들지 않고 기존 `audit_logs`를 재사용한다.

`audit_logs.resource_type`에는 아래 값을 사용한다.

- `medical_source`
- `medical_source_version`
- `medical_evidence_item`
- `medical_policy_boundary`
- `medical_rag_chunk`

`audit_logs.action`에는 아래 값을 사용한다.

- `reviewed`
- `deprecated`
- `stale_marked`
- `review_extended`
- `rag_index_disabled`

`audit_logs.event_metadata`에는 아래 값을 넣지 않는다.

- raw prompt
- raw LLM response 또는 provider payload 전문
- raw OCR text
- raw image bytes, base64 image, EXIF, 원본 파일명
- 내부 review note 전문
- 사용자 개인정보, 시크릿, provider key, service-account JSON

상태 용어 기준:

- KDRIs dataset의 기존 `approved` 상태는 그대로 유지한다.
- 의료 source governance의 사용자-facing 기준은 `reviewed`로 통일한다.
- KDRIs adapter가 기존 `approved` row를 source governance로 연결해야 한다면
  `approved -> reviewed` 의미 변환을 코드와 테스트에 명시한다.
- `approved`를 새 의료 source governance 테이블의 review status로 추가하지 않는다.

## 12. Runtime 전환 및 팀 코드 이식 TODO

### 12.1 Runtime 전환 순서

1. 기존 `REVIEWED_MEDICAL_SOURCE_REGISTRY`와 `medical_source_readiness.py`는 유지한다.
2. 먼저 DB schema, ORM 모델, migration, DB 단위 테스트만 추가한다.
3. 다음 PR에서 DB-backed repository를 추가한다.
4. readiness가 DB에서 `review_status=reviewed`, `expires_at`, `source_family`를 읽도록
   전환한다.
5. DB가 비어 있으면 production-like 사용자-facing readiness는 fail-closed로
   `no_reviewed_sources` 처리한다.
6. registry fallback은 local/dev bootstrap에만 허용한다.
7. 사용자-facing production path에서는 registry fallback을 사용하지 않는다.
8. RAG/vector DB 연결은 별도 PR로 미룬다.

전환 후 필수 테스트:

```powershell
python -m pytest -q backend/Nutrition-backend/tests/unit/services/test_medical_source_readiness.py
python -m pytest -q backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py
```

선택 smoke:

```powershell
$env:RUN_POSTGRES_MIGRATION_SMOKE='1'
$env:TEST_DATABASE_URL='<postgres-test-url>'
python -m pytest -q backend/Nutrition-backend/tests/integration/db/test_alembic_migration_smoke.py
```

### 12.2 팀 코드 이식 기준

팀원 브랜치는 통째 merge하지 않는다. 아래 계약 단위로 diff를 비교하고, 현재
`feat/ai-agent-backend-integration` 구조에 필요한 부분만 이식한다.

- `changmin-aiagent`: reviewed registry, `SafetyGuard`, source family 정책만 계약 단위로
  비교한다. 독립 server/package 구조나 prompt 전문은 그대로 가져오지 않는다.
- `yeong-tech`: KDRIs 2025 approved row/manifest, OCR privacy, raw image/OCR 비저장
  테스트만 파일 단위로 검토한다.
- `sunghoon-database`: auth/profile/consent는 사용자 DB 책임으로 분리한다. 의료 source
  governance table을 사용자 DB schema로 덮어쓰지 않는다.
- `taedong-design`: UI source card는 `source_id`, `source_family`, `review_status`,
  `algorithm_version` 계약에 맞는 표시만 반영한다.

팀 코드 이식 시 금지:

- draft 또는 paper candidate source를 사용자-facing source card에 노출
- raw prompt, raw LLM response, raw OCR text, raw image 저장 필드 추가
- migration에 production seed 삽입
- `reviewed` 대신 `approved`를 의료 source governance의 사용자-facing 기준으로 사용
- RAG retrieval을 safety boundary보다 우선시키는 runtime 흐름 추가

## 13. 완료 후 검증 체크리스트

이 체크리스트는 구현 PR을 끝낸 뒤 완료 보고 전에 반드시 다시 읽고 채운다. 단순히
"작업함"으로 표시하지 말고, 각 항목마다 확인한 파일, 실행한 명령, 통과 기준, 미실행
사유를 PR 본문 또는 작업 로그에 남긴다.

완료 판정 규칙:

- `[ ]` 항목은 실제 확인 전에는 체크하지 않는다.
- 테스트나 smoke를 실행하지 못했다면 체크하지 않고 이유와 남은 위험을 적는다.
- 실패한 검증이 있으면 완료로 보고하지 않는다. 실패 원인과 다음 조치를 먼저 기록한다.
- 이 문서와 구현 diff가 충돌하면 구현을 맞추기 전에 이 문서를 먼저 갱신하고 리뷰받는다.

2026-05-28 현재 체크 상태는
`04-medical-source-db-implementation-log.md`의 Step 7 최종 검증 결과를 기준으로 한다.
PostgreSQL live migration smoke, KDRIs adapter 세부 연결, 실제 RAG/vector DB 연결, UI
source card 반영은 이번 PR 범위 또는 현재 환경에서 완료하지 않은 항목으로 남긴다.

### 13.1 문서 재독해 게이트

- [x] 1-7장을 다시 읽고, 구현이 이 문서의 목적, 저장 금지 경계, 최소 테이블 계약,
  관계/index 기준, backend 계약 테스트, 구현 순서와 충돌하지 않는지 확인했다.
- [x] 8장의 최종 완수 기준 4개 항목을 PR 변경사항과 대조했다.
- [x] 9-12장의 파일 경로, schema 결정, audit/status 용어, runtime 전환 순서를 구현
  diff와 대조했다.
- [x] `03-ai-agent-safety-porting-contract.md`와 충돌하는 의료/영양/복약 문구 또는
  저장 경계 변경이 없는지 확인했다.

완료 증거:

```powershell
Get-Content -Raw -Encoding UTF8 docs\Integration-docs\04-medical-source-db-contract.md
Get-Content -Raw -Encoding UTF8 docs\Integration-docs\03-ai-agent-safety-porting-contract.md
```

### 13.2 변경 파일 범위 확인

- [x] 이번 작업의 변경 파일이 migration, ORM, DB model export, DB 테스트, readiness/repository 전환,
  필요한 문서 갱신 범위로 제한되어 있다.
- [x] `docs/Integration-docs/README.md`와 `docs/README.md`의 링크가 깨지지 않았다.
- [x] 팀원 브랜치 또는 다른 worktree의 파일을 통째로 복사하지 않았다.
- [x] unrelated dirty file을 stage하거나 commit하지 않았다.

참고: 현재 worktree에는 이번 작업 전후로 무관한 dirty/untracked 파일이 함께 존재한다.
완료 판정은 이번 작업에서 수정한 파일과 구현 로그에 기록한 명령 기준으로 한다.

완료 증거:

```powershell
git status --short
git diff --stat
git diff --name-only
```

### 13.3 Schema 완료 확인

- [x] `0009_create_medical_source_governance_tables.py` migration이 존재한다.
- [x] migration `down_revision`이 `0008_create_reminder_preferences`다.
- [x] `medical_sources`, `medical_source_versions`, `medical_evidence_items`,
  `medical_policy_boundaries`, `medical_rag_chunks` 5개 테이블이 생성된다.
- [x] `medical_sources.id`는 `String(80)` primary key다.
- [x] 나머지 4개 테이블 id는 UUID primary key다.
- [x] 날짜 필드는 `Date`, 긴 문구와 snippet은 `Text`, timestamp는 기존
  `TimestampMixin` 기준을 따른다.
- [x] enum 성격 필드는 `String`과 named `CheckConstraint`로 구현되어 있다.
- [x] 필수 FK, index, unique 또는 중복 방지 기준이 migration과 ORM에 반영되어 있다.
- [x] production seed data가 migration에 포함되어 있지 않다.

완료 증거:

```powershell
python -m pytest -q backend/Nutrition-backend/tests/unit/db/test_models.py
python -m pytest -q backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py
```

### 13.4 Safety 저장 금지 확인

- [x] raw prompt 또는 full prompt 저장 컬럼이 없다.
- [x] raw LLM response 또는 provider payload 전문 저장 컬럼이 없다.
- [x] raw OCR text 저장 컬럼이 없다.
- [x] raw image bytes, base64 image, EXIF, 원본 파일명 저장 컬럼이 없다.
- [x] 내부 review note 전문이 `audit_logs.event_metadata`나 사용자-facing 응답에 들어가지
  않는다.
- [x] 사용자 개인정보, 시크릿, provider key, service-account JSON을 저장하거나 노출하는
  변경이 없다.

완료 증거:

```powershell
rg -n "raw_prompt|full_prompt|raw_llm|provider_payload|raw_ocr|raw_image|base64|exif|file_name|service-account|provider_key" backend docs
python -m pytest -q backend/Nutrition-backend/tests/unit/db/test_models.py
```

위 `rg` 명령은 금지 필드 후보를 찾기 위한 수동 검토 보조다. 합법적인 설명 문서나
테스트의 금지어 언급은 허용되지만, DB column, persisted payload, API response field로
추가된 항목은 실패로 본다.

### 13.5 Runtime readiness 확인

- [x] readiness와 DB-backed source 판정에는 `review_status=reviewed` source만 사용된다.
- [x] `draft` source는 readiness 사용자-facing 허용 경로에 나오지 않는다.
- [x] `paper_candidate` source는 readiness 사용자-facing 허용 경로에 나오지 않는다.
- [x] `expires_at`이 지난 source는 `source_stale` warning 또는 deterministic fallback으로
  처리된다.
- [x] DB가 비어 있는 production-like 사용자-facing readiness는 fail-closed로
  `no_reviewed_sources`를 반환한다.
- [x] registry fallback은 local/dev bootstrap에서만 허용되고 production path에서는
  사용되지 않는다.
- [ ] RAG retrieval 실패가 deterministic fallback과 safety boundary를 우회하지 않는다.

참고: 실제 RAG/vector DB 연결은 12장의 별도 PR 범위로 남겼다. 이번 작업은 readiness
전환과 사용자-facing source 허용 판정을 고정한다.

완료 증거:

```powershell
python -m pytest -q backend/Nutrition-backend/tests/unit/services/test_medical_source_readiness.py
python -m pytest -q backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py
```

### 13.6 Audit 및 상태 용어 확인

- [x] 새 audit table을 만들지 않고 기존 `audit_logs`를 재사용한다.
- [x] 새 의료 source governance 구현에서 11장 밖의 `resource_type` 값을 추가하지 않았다.
- [x] 새 의료 source governance 구현에서 11장 밖의 `action` 값을 추가하지 않았다.
- [x] `event_metadata`에 raw prompt, raw LLM response, raw OCR text, raw image, 내부
  review note 전문을 넣지 않는다.
- [x] KDRIs 기존 `approved`는 유지하되, 의료 source governance의 사용자-facing 기준은
  `reviewed`로 통일했다.
- [ ] 필요한 adapter에는 `approved -> reviewed` 의미 변환이 코드와 테스트에 명시되어
  있다.

참고: KDRIs adapter의 `approved -> reviewed` 코드 연결은 이번 DB schema/readiness PR
이후 별도 adapter PR에서 처리한다.

완료 증거:

```powershell
rg -n "audit_logs|resource_type|stale_marked|review_extended|rag_index_disabled|approved -> reviewed|approved.*reviewed" backend
python -m pytest -q backend/Nutrition-backend/tests/unit/db/test_models.py
```

### 13.7 팀 코드 이식 확인

- [x] `changmin-aiagent`에서는 reviewed registry, `SafetyGuard`, source family 정책만
  계약 단위로 비교했다.
- [x] `yeong-tech`에서는 KDRIs 2025 approved row/manifest, OCR privacy, raw image/OCR
  비저장 테스트만 파일 단위로 검토했다.
- [x] `sunghoon-database`의 auth/profile/consent 책임을 의료 source governance table과
  섞지 않았다.
- [ ] `taedong-design`의 UI source card는 `source_id`, `source_family`, `review_status`,
  `algorithm_version` 계약에 맞는 표시만 반영했다.
- [x] 팀원 브랜치를 통째 merge하지 않았고, 필요한 diff만 현재 구조에 맞게 이식했다.

참고: `taedong-design` UI source card 실제 반영은 Flutter/UI PR 범위다. 이번 작업에서는
계약 필드 기준만 확인하고 backend DB/readiness 구현에 UI 파일을 섞지 않았다.

완료 증거:

```powershell
git diff --name-only
git diff --stat
```

필요하면 비교한 팀원 브랜치와 파일 경로를 PR 본문에 별도 목록으로 남긴다.

### 13.8 Migration smoke 확인

PostgreSQL 테스트 DB를 사용할 수 있는 환경에서는 migration smoke까지 실행한다.

- [ ] Alembic upgrade가 PostgreSQL test DB에서 성공한다.
- [ ] 5개 의료 source governance 테이블이 실제 DB에 생성된다.
- [ ] FK, index, unique, check constraint가 실제 DB에 반영된다.
- [ ] migration downgrade 또는 rollback 전략을 PR 본문에 명시했다.

완료 증거:

```powershell
$env:RUN_POSTGRES_MIGRATION_SMOKE='1'
$env:TEST_DATABASE_URL='<postgres-test-url>'
python -m pytest -q backend/Nutrition-backend/tests/integration/db/test_alembic_migration_smoke.py
```

실행하지 못한 경우:

- PostgreSQL test DB가 없어서 미실행했는지, 테스트가 아직 없어서 미실행했는지 구분해
  적는다.
- unit test만으로 대체했다면 남은 위험을 PR 본문에 남긴다.

현재 상태: 테스트 파일은 존재하지만 `RUN_POSTGRES_MIGRATION_SMOKE`와
`TEST_DATABASE_URL`이 설정되어 있지 않아 live smoke는 skip으로 확인했다.

### 13.9 완료 보고 템플릿

PR 또는 작업 완료 보고에는 아래 형식을 사용한다.

```markdown
## 완료 범위
- [ ] Schema 계약
- [ ] Runtime/readiness 계약
- [ ] Safety 저장 금지 계약
- [ ] Audit/status 용어 계약
- [ ] 팀 코드 이식 기준

## 실행한 검증
- [ ] `python -m pytest -q backend/Nutrition-backend/tests/unit/db/test_models.py`
- [ ] `python -m pytest -q backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py`
- [ ] `python -m pytest -q backend/Nutrition-backend/tests/unit/services/test_medical_source_readiness.py`
- [ ] `python -m pytest -q backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py`
- [ ] PostgreSQL migration smoke

## 미실행 검증과 이유
- 없음 또는 구체적 사유

## 남은 위험
- 없음 또는 구체적 위험
```
