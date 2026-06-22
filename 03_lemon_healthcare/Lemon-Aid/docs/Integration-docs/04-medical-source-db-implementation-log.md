# 의료정보 DB 계약 구현 로그

> 기준 문서: [04-medical-source-db-contract.md](./04-medical-source-db-contract.md)
> 작업 브랜치: `feat/ai-agent-backend-integration`
> 작성일: 2026-05-28

이 문서는 의료정보 DB 계약 구현 중 각 단계가 끝날 때마다 실제 수행 내용, 확인한
파일, 검증 결과, 남은 위험을 기록하기 위한 작업 로그다. 완료 보고 전에 이 로그와
`04-medical-source-db-contract.md`의 `13. 완료 후 검증 체크리스트`를 함께 대조한다.

## Step 0. 작업 범위 확정

상태: 완료

사용자 결정:

- 작업 범위는 추천안대로 `schema + ORM + DB 단위 테스트`까지로 제한한다.
- readiness DB 전환, KDRIs `approved -> reviewed` adapter, 팀원 코드 이식, RAG/vector DB
  연결은 별도 PR로 미룬다.
- 작업은 `ai-agent-backend-integration` worktree에서 계속 진행한다.
- 큰 단계가 끝날 때마다 이 로그 문서에 수행 내용과 검증 결과를 남긴다.

확인한 현재 상태:

- 현재 worktree는 `feat/ai-agent-backend-integration` 브랜치다.
- 기존 dirty/untracked 파일이 많으므로 이번 작업에서 건드리는 파일을 좁게 유지해야 한다.
- `04-medical-source-db-contract.md`는 아직 untracked 상태다.

다음 단계:

- 기존 DB 모델, migration, 테스트 패턴을 확인한다.
- production code 작성 전에 실패하는 DB 계약 테스트를 먼저 추가한다.

## Step 1. 기존 DB 패턴 확인

상태: 완료

확인한 파일:

- `backend/Nutrition-backend/src/db/base.py`
- `backend/Nutrition-backend/src/models/db/mixins.py`
- `backend/Nutrition-backend/src/models/db/__init__.py`
- `backend/Nutrition-backend/src/models/db/notification.py`
- `backend/Nutrition-backend/src/models/db/privacy.py`
- `backend/Nutrition-backend/src/models/db/agent_memory.py`
- `backend/Nutrition-backend/tests/unit/db/test_models.py`
- `backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py`
- `backend/alembic/versions/0008_create_reminder_preferences.py`

확인한 구현 규칙:

- UUID primary key는 기존 모델처럼 `postgresql.UUID(as_uuid=True)`와 `uuid4` default를
  사용한다.
- timestamp는 기존 `TimestampMixin`을 기본으로 사용한다.
- Alembic revision head는 현재 `0008_create_reminder_preferences`다.
- ORM `CheckConstraint` 이름은 naming convention에 의해 실제 DB 이름이
  `ck_<table>_<constraint_name>` 형태가 되므로, ORM에는 중복 prefix 없이 의미 있는
  constraint name을 둔다.
- migration 파일에서는 기존 패턴대로 `op.f("ck_<table>_<constraint_name>")`를 사용한다.
- 기존 `audit_logs` 테이블은 `backend/Nutrition-backend/src/models/db/privacy.py`에 있고,
  `event_metadata`는 JSONB다. 새 audit table은 만들지 않는다.

다음 단계:

- `test_models.py`와 `test_alembic_setup.py`에 의료 source governance 계약 테스트를
  먼저 추가한다.
- 테스트가 새 모델과 migration이 없어서 실패하는지 확인한다.

## Step 2. RED 테스트 추가 및 실패 확인

상태: 완료

변경한 파일:

- `backend/Nutrition-backend/tests/unit/db/test_models.py`
- `backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py`

추가한 테스트:

- 5개 의료 source governance 테이블이 `Base.metadata`에 등록되는지 확인
- `medical_sources.id`가 `String(80)` primary key인지 확인
- 나머지 4개 테이블 id가 UUID primary key인지 확인
- 필수 컬럼, `Date`, `Text`, named `CheckConstraint`, index가 있는지 확인
- raw prompt, raw LLM response, raw OCR text, raw image 계열 저장 컬럼이 없는지 확인
- Alembic head가 `0009_create_medical_source_governance_tables`인지 확인
- `0009_create_medical_source_governance_tables.py` migration 파일이 있는지 확인

RED 확인 명령:

```powershell
python -m pytest -q backend/Nutrition-backend/tests/unit/db/test_models.py
python -m pytest -q backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py
```

실패 결과:

- `test_models.py`: 새 5개 테이블이 `Base.metadata.tables`에 없어서 7개 테스트 실패
- `test_alembic_setup.py`: Alembic head가 아직 `0008_create_reminder_preferences`이고
  `0009` migration 파일이 없어서 3개 테스트 실패
- 단일 파일 pytest 실행 시 repo coverage fail-under도 함께 실패로 표시됨. 기능 검증
  단계에서는 동일 테스트를 `--no-cov`로도 실행해 계약 테스트 자체의 통과 여부를 확인한다.

다음 단계:

- 최소 production code로 ORM 모델, model export, Alembic migration을 추가한다.

## Step 3. ORM, export, migration 추가

상태: 완료

변경한 파일:

- `backend/Nutrition-backend/src/models/db/medical_source.py`
- `backend/Nutrition-backend/src/models/db/__init__.py`
- `backend/alembic/versions/0009_create_medical_source_governance_tables.py`

수행한 작업:

- `medical_sources`는 `String(80)` primary key로 구현했다.
- `medical_source_versions`, `medical_evidence_items`, `medical_policy_boundaries`,
  `medical_rag_chunks`는 UUID primary key로 구현했다.
- 날짜 필드는 `Date`, 긴 문구와 snippet은 `Text`, timestamp는 기존 `TimestampMixin`을
  사용했다.
- enum 성격 필드는 `String`과 named `CheckConstraint`로 구현했다.
- production seed data는 migration에 넣지 않았다.
- 새 audit table은 만들지 않았고, 기존 `audit_logs` 구조도 변경하지 않았다.
- runtime readiness, KDRIs adapter, 팀원 코드 이식, RAG/vector DB 연결은 건드리지
  않았다.

GREEN 확인 명령:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/db/test_models.py
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py
```

통과 결과:

- `test_models.py`: 25 passed
- `test_alembic_setup.py`: 11 passed

주의:

- repo pytest 설정의 coverage fail-under 때문에 단일 파일 테스트를 `--no-cov` 없이
  실행하면 기능 테스트가 통과해도 전체 coverage 계산으로 실패할 수 있다.
- 완료 보고에는 기능 검증 결과와 coverage 설정에 따른 제한을 분리해서 적는다.

다음 단계:

- 문서 체크리스트, whitespace, compile, 금지 필드 검색을 수행한다.

## Step 4. 검증 및 범위 확인

상태: 완료

실행한 검증:

```powershell
python -m compileall -q backend\Nutrition-backend\src\models\db\medical_source.py backend\alembic\versions\0009_create_medical_source_governance_tables.py
git diff --check -- backend/Nutrition-backend/src/models/db/medical_source.py backend/Nutrition-backend/src/models/db/__init__.py backend/Nutrition-backend/tests/unit/db/test_models.py backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py backend/alembic/versions/0009_create_medical_source_governance_tables.py docs/Integration-docs/04-medical-source-db-contract.md docs/Integration-docs/04-medical-source-db-implementation-log.md
Select-String -Path backend\Nutrition-backend\src\models\db\medical_source.py,backend\alembic\versions\0009_create_medical_source_governance_tables.py,docs\Integration-docs\04-medical-source-db-contract.md,docs\Integration-docs\04-medical-source-db-implementation-log.md -Pattern '[ \t]+$'
rg -n "raw_prompt|full_prompt|raw_llm|provider_payload|raw_ocr|raw_image|base64|exif|file_name|service-account|provider_key" backend\Nutrition-backend\src\models\db backend\alembic\versions backend\Nutrition-backend\tests\unit\db docs\Integration-docs\04-medical-source-db-contract.md docs\Integration-docs\04-medical-source-db-implementation-log.md
```

검증 결과:

- 최종 DB 단위 테스트:
  - 명령: `python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/db/test_models.py backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py`
  - 결과: 36 passed
- compileall: 통과
- `git diff --check`: 오류 없음. 단, 기존 tracked 파일 3개는 Git이 다음 touch 때 CRLF를 LF로
  바꿀 수 있다는 warning을 출력했다.
- 새로 추가한 주요 파일 trailing whitespace: 없음
- 금지 필드 후보 검색: 새 `medical_source.py`와 `0009` migration에는 금지 저장 컬럼이
  없다. 검색 결과는 계약 문서/테스트의 금지어 설명, 기존 regulated OCR의
  `raw_image_deleted_at` 삭제 시각 컬럼에서만 나왔다.

이번 작업으로 직접 변경한 파일:

- `backend/Nutrition-backend/src/models/db/__init__.py`
- `backend/Nutrition-backend/src/models/db/medical_source.py`
- `backend/Nutrition-backend/tests/unit/db/test_models.py`
- `backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py`
- `backend/alembic/versions/0009_create_medical_source_governance_tables.py`
- `docs/Integration-docs/04-medical-source-db-contract.md`
- `docs/Integration-docs/04-medical-source-db-implementation-log.md`

이번 작업에서 의도적으로 하지 않은 것:

- readiness DB 전환
- KDRIs `approved -> reviewed` adapter 구현
- 팀원 브랜치 코드 이식
- RAG/vector DB 연결
- PostgreSQL live migration smoke
- commit 또는 push

남은 위험:

- PostgreSQL test DB를 사용한 migration smoke는 아직 실행하지 않았다.
- 단일 pytest 파일을 `--no-cov` 없이 실행하면 repo coverage fail-under 때문에 실패한다.
  기능 계약 테스트 자체는 `--no-cov` 기준으로 통과했다.

## Step 5. Runtime readiness DB 전환

상태: 완료

변경한 파일:

- `backend/Nutrition-backend/src/services/medical_source_readiness.py`
- `backend/Nutrition-backend/tests/unit/services/test_medical_source_readiness.py`

수행한 작업:

- `MedicalSourceReadinessRecord`를 추가해 DB row에서 readiness에 필요한
  `source_id`, `source_family`, `review_status`, `reviewed_at`, `expires_at`을 명시했다.
- `MedicalSourceGovernanceRepository`를 추가해 `medical_sources`와
  `medical_source_versions`를 join하는 DB-backed 조회 경로를 만들었다.
- `build_medical_source_readiness_from_db()`를 추가했다.
- production-like 경로에서는 DB row가 비어 있으면 registry fallback 없이
  `no_reviewed_sources`로 fail-closed 처리한다.
- development/local 경로에서는 bootstrap 용도로만 registry fallback을 허용한다.
- 기존 `build_medical_source_readiness()`는 로컬/dev registry preflight 호환성을 위해
  유지했다.

RED 확인:

- `MedicalSourceReadinessRecord`, `MedicalSourceGovernanceRepository`,
  `build_medical_source_readiness_from_db()` import가 없어
  `test_medical_source_readiness.py` collection 단계에서 실패하는 것을 확인했다.

GREEN 확인:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/services/test_medical_source_readiness.py
```

결과:

- 12 passed

## Step 6. 팀 코드 이식 기준 확인

상태: 완료

목적:

- 팀원 브랜치를 통째 merge하지 않고, `04-medical-source-db-contract.md` 12.2 기준의 계약
  단위 diff만 확인한다.

확인 명령:

```powershell
git -C C:\MyWorkspace\lemon_aid\main worktree list
Get-ChildItem -Path C:\MyWorkspace\lemon_aid -Directory | Select-Object -ExpandProperty Name
rg -n "REVIEWED_MEDICAL_SOURCE_REGISTRY|SafetyGuard|source_family|source_families|reviewed|approved|raw_ocr|raw_image|ocr_text_hash" C:\MyWorkspace\lemon_aid\changmin-aiagent C:\MyWorkspace\lemon_aid\taedong-design -S
git branch -a --list "*yeong*" "*sunghoon*" "*taedong*" "*changmin*"
git grep -n "approved\|review_status\|KDRIs\|raw_ocr\|raw_image\|ocr_text_hash" origin/yeong-tech -- .
git grep -n "auth\|profile\|consent\|medical_sources\|medical_source" origin/sunghoon-database -- .
git grep -n "source_id\|source_family\|review_status\|algorithm_version\|source card\|source_card" origin/taedong-design -- .
git grep -n "REVIEWED_MEDICAL_SOURCE_REGISTRY\|SafetyGuard\|source_family\|source_families" origin/changmin-aiagent -- ai-agent
```

확인 결과:

- `changmin-aiagent`: reviewed registry, `SafetyGuard`, source family 정책이 이미 현재
  `ai_agent_chat` 계층에 반영된 범위와 맞는다. 독립 server/package 구조나 prompt 전문은
  이식하지 않았다.
- `yeong-tech`: KDRIs 2025 approved row/manifest, OCR privacy, raw image/OCR 비저장
  패턴이 확인됐다. 이번 PR 범위에서는 KDRIs adapter 구현을 하지 않고,
  `approved -> reviewed` 의미 변환은 문서와 runtime TODO 기준으로 유지했다.
- `sunghoon-database`: auth/profile/consent 중심 branch로 확인됐다. 의료 source
  governance table을 사용자 DB schema로 덮어쓰지 않았다.
- `taedong-design`: `algorithm_version` 등 UI 모델 일부만 확인됐고, 의료 source card
  계약 필드는 아직 본격 구현되어 있지 않다. 이번 backend PR에서는 UI 코드를 이식하지
  않았다.

결론:

- 팀원 브랜치 통째 merge 없음.
- 이번 작업에 필요한 계약 단위는 schema/runtime readiness 구현으로 충족했다.
- KDRIs adapter, UI source card 상세 반영, 팀원 branch의 파일 단위 이식은 별도 PR에서
  진행할 수 있도록 범위를 남겼다.

## Step 7. 최종 검증

상태: 완료

실행한 명령:

```powershell
python -m pytest -q --no-cov backend/Nutrition-backend/tests/unit/db/test_models.py backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py backend/Nutrition-backend/tests/unit/services/test_medical_source_readiness.py backend/Nutrition-backend/tests/unit/scripts/test_check_ai_agent_runtime_prereqs.py
python -m pytest -q --no-cov backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py
python -m compileall -q backend\Nutrition-backend\src\models\db\medical_source.py backend\Nutrition-backend\src\services\medical_source_readiness.py backend\alembic\versions\0009_create_medical_source_governance_tables.py
python -m pytest -q --no-cov backend/Nutrition-backend/tests/integration/db/test_alembic_migration_smoke.py
git diff --check -- backend/Nutrition-backend/src/models/db/__init__.py backend/Nutrition-backend/src/models/db/medical_source.py backend/Nutrition-backend/src/services/medical_source_readiness.py backend/Nutrition-backend/tests/unit/db/test_models.py backend/Nutrition-backend/tests/unit/db/test_alembic_setup.py backend/Nutrition-backend/tests/unit/services/test_medical_source_readiness.py backend/alembic/versions/0009_create_medical_source_governance_tables.py docs/Integration-docs/04-medical-source-db-contract.md docs/Integration-docs/04-medical-source-db-implementation-log.md
rg -n "raw_prompt|full_prompt|raw_llm|provider_payload|raw_ocr|raw_image|base64|exif|file_name|service-account|provider_key" backend\Nutrition-backend\src\models\db backend\Nutrition-backend\src\services\medical_source_readiness.py backend\alembic\versions backend\Nutrition-backend\tests\unit\db backend\Nutrition-backend\tests\unit\services\test_medical_source_readiness.py backend\Nutrition-backend\tests\integration\api\test_ai_agent_api.py docs\Integration-docs\04-medical-source-db-contract.md docs\Integration-docs\04-medical-source-db-implementation-log.md
```

결과:

- DB/schema/readiness/preflight unit 묶음: 66 passed
- AI Agent API integration: 13 passed, 1 warning
- compileall: 통과
- PostgreSQL migration smoke: 1 skipped
  - 이유: `RUN_POSTGRES_MIGRATION_SMOKE`와 `TEST_DATABASE_URL`이 설정되어 있지 않음
- `git diff --check`: whitespace 오류 없음
  - warning: 기존 tracked 파일 3개는 다음 Git touch 때 CRLF가 LF로 바뀔 수 있음
- 금지 필드 검색:
  - 새 `medical_source.py`, `medical_source_readiness.py`, `0009` migration에는 raw prompt,
    raw LLM response, raw OCR text, raw image 저장 컬럼이 없음
  - 검색 결과는 계약 문서/테스트의 금지어 설명, 기존 regulated OCR의
    `raw_image_deleted_at` 삭제 시각 컬럼, API 테스트 입력 샘플에서만 확인됨

완료 기준 대조:

- Schema 계약: 완료
- Runtime/readiness 계약: 완료
- Safety 저장 금지 계약: 테스트와 검색으로 확인
- Audit/status 용어 계약: 새 audit table을 만들지 않았고 기존 `audit_logs` 재사용 원칙 유지
- 팀 코드 이식 기준: 통째 merge 없이 계약 단위 확인 완료

남은 외부 의존 검증:

- 실제 PostgreSQL test DB에 대한 live migration upgrade/downgrade smoke는 환경 변수가
  없어 실행되지 않았다. 테스트 파일은 존재하며, 실행 조건은
  `RUN_POSTGRES_MIGRATION_SMOKE=1`과 `TEST_DATABASE_URL` 설정이다.

## Step 8. 완료 체크리스트 반영 및 감사

상태: 완료

수행한 작업:

- `04-medical-source-db-contract.md`의 13장 완료 후 검증 체크리스트를 현재 구현과
  검증 결과 기준으로 다시 채웠다.
- 완료된 schema, readiness, safety 저장 금지, audit table 미생성, 팀 코드 통째 merge
  금지 항목은 `[x]`로 표시했다.
- 현재 작업 범위 밖이거나 외부 환경이 필요한 항목은 체크하지 않고 사유를 남겼다.

체크하지 않은 항목과 이유:

- RAG retrieval 실패 검증: 실제 RAG/vector DB 연결은 12장에서 별도 PR로 미룬 항목이다.
- KDRIs `approved -> reviewed` adapter 코드/테스트: DB schema와 readiness 전환 이후 별도
  adapter PR에서 구현한다.
- `taedong-design` UI source card 실제 반영: Flutter/UI PR 범위이며 이번 backend
  DB/readiness 변경에는 UI 파일을 섞지 않았다.
- PostgreSQL live migration smoke: `RUN_POSTGRES_MIGRATION_SMOKE`와 `TEST_DATABASE_URL`이
  설정되어 있지 않아 skip으로 확인했다.

완료 판단:

- `04` 문서의 이번 구현 범위인 schema, migration, ORM, DB model export, unit test,
  readiness DB 전환, production-like fail-closed, safety 저장 금지 검증, 팀 코드 이식 기준
  확인은 완료했다.
- RAG/vector DB, KDRIs adapter, Flutter source card 반영, live PostgreSQL smoke는 문서에
  별도 후속 작업 또는 외부 환경 의존 검증으로 남겨 두었다.
