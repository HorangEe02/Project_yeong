# 41. Learning/vector DB 상세 설계 및 구현 플랜

작성일: 2026-05-15
범위: `docs/Nutrition-docs/36-post-p1-execution-plan.md`의 P3 Learning/vector DB 항목

## 1. 현재 상태 확인

현재 프로젝트는 Learning/vector DB 기능을 바로 켤 수 있는 상태가 아니라, 안전하게 막아둔 골격까지 구현된 상태다.

| 영역 | 현재 구현 | 남은 작업 |
| --- | --- | --- |
| Feature gate | `ENABLE_IMAGE_LEARNING_PIPELINE=false`, `ENABLE_PGVECTOR_STORAGE=false`, `IMAGE_RETENTION_DAYS=0` 기본값 | 운영 sign-off 전까지 기본 OFF 유지 |
| Consent gate | `learning/consent_gate.py`가 `OCR_IMAGE_PROCESSING`, `DATA_RETENTION`, `IMAGE_LEARNING_DATASET` 3개 동의를 요구 | 실제 저장 경로에도 동일 gate 적용 |
| Retention | `learning/retention.py`가 보유 기한을 계산 | object storage 삭제 worker와 연결 |
| Embedding | `EmbeddingProvider`, `DisabledEmbeddingProvider` 계약 존재 | 실제 model runner 구현 |
| Vector store | `VectorStore`, `DisabledVectorStore` 계약 존재 | pgvector table, adapter, upsert 구현 |
| DB | `supplement_analysis_runs`는 image hash와 OCR text hash만 저장 | image object, embedding job, embedding record table 추가 |
| Manual review | `learning_image_objects.review_metadata_snapshot`에 sanitized confirmed metadata만 보관하고 `apply_learning_manual_review_decision.py`로 승인/거절 | 운영 UI 또는 admin console 연결 |

핵심 제약은 명확하다. 원본 이미지와 raw OCR text는 기본 분석 DB에 저장하지 않고, 학습 재사용은 별도 동의와 retention 설정이 모두 통과된 경우에만 시작해야 한다.

## 2. 공식 문서 확인 근거

아래 문서는 구현 전에 확인한 공식 또는 프로젝트 공식 문서다.

| 주제 | 확인한 내용 | 설계 반영 |
| --- | --- | --- |
| PostgreSQL extension | `CREATE EXTENSION [ IF NOT EXISTS ]` 구문이 있고, extension 설치에는 권한과 서버 측 지원 파일이 필요하다. Supabase pgvector 예시는 `schema extensions`와 `extensions.vector` 타입을 사용한다. | Alembic migration은 `CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions`를 별도 단계로 두고, 운영 DB 권한 preflight를 요구한다. |
| pgvector | `vector` type, HNSW/IVFFlat index, cosine opclass가 지원된다. HNSW는 빠른 검색을 위해 recall과 build cost trade-off가 있다. | 초기 PR은 exact search와 upsert 안정성에 집중하고, HNSW index는 데이터가 쌓인 뒤 별도 benchmark PR로 분리한다. |
| pgvector-python SQLAlchemy | SQLAlchemy에서 `VECTOR(n)` 컬럼과 HNSW/IVFFlat index를 정의할 수 있다. | ORM 모델은 `pgvector.sqlalchemy.VECTOR`를 사용하되 optional dependency import를 feature-on 경로로 제한한다. |
| Alembic | migration에서 literal SQL이 필요한 경우 `Operations.execute()`를 사용할 수 있다. | extension 생성과 pgvector-specific DDL은 Alembic `op.execute()` 또는 명시 SQL로 관리한다. |
| Sentence Transformers image search | `sentence-transformers/clip-ViT-B-32`를 통해 이미지와 텍스트를 같은 vector space로 encode하는 예시가 공식 문서에 있다. | `embedding_model` 기본값과 맞추되, model output dimension은 구현 PR에서 실제 runner readiness test로 기록한 뒤 고정한다. |
| Boto3 S3 object API | `put_object`는 bucket에 object를 추가하고, `delete_object`는 versioning 상태에 따라 object 또는 delete marker를 처리한다. | object storage adapter는 `put_object`와 `delete_object` 모두를 감싸고, versioned bucket에서는 version id 저장 여부를 결정해야 한다. |
| Supabase Storage S3 | Supabase Storage는 S3-compatible API와 access key 기반 server-side 인증을 제공하며, Storage 접근 제어는 bucket 공개 여부와 `storage.objects` RLS policy에 의해 결정된다. | 학습 원본 이미지는 `learning-images` private bucket에만 저장하고, client role policy는 이 bucket을 대상으로 만들지 않는다. |
| PostgreSQL row locking | `FOR UPDATE SKIP LOCKED`는 queue-like table에서 lock contention을 피하는 용도로 사용할 수 있다. | 별도 broker를 도입하기 전에는 DB-backed job queue와 `SKIP LOCKED` 방식으로 worker를 시작한다. |

참고 URL:

- PostgreSQL `CREATE EXTENSION`: https://www.postgresql.org/docs/current/sql-createextension.html
- PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED`: https://www.postgresql.org/docs/18/sql-select.html
- pgvector documentation: https://access.crunchydata.com/documentation/pgvector/latest/
- pgvector-python SQLAlchemy: https://github.com/pgvector/pgvector-python
- Alembic operations: https://alembic.sqlalchemy.org/en/latest/api/operations.html
- Sentence Transformers image search: https://sbert.net/examples/sentence_transformer/applications/image-search/README.html
- Boto3 S3 `put_object`: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html
- Boto3 S3 `delete_object`: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/delete_object.html
- Supabase Storage S3 authentication: https://supabase.com/docs/guides/storage/s3/authentication
- Supabase Storage S3 compatibility: https://supabase.com/docs/guides/storage/s3/compatibility
- Supabase Storage access control: https://supabase.com/docs/guides/storage/security/access-control
- Supabase MCP setup: https://supabase.com/docs/guides/ai-tools/mcp
- Supabase CLI config: https://supabase.com/docs/guides/local-development/cli/config
- Supabase API keys: https://supabase.com/docs/guides/getting-started/api-keys

### 확인 한계

위 Sentence Transformers image-search 문서는 `clip-ViT-B-32` 사용 예시는 제공하지만, 이 문서 안에서 output vector dimension을 직접 명시하지 않는다. 따라서 migration의 `VECTOR(n)` 값은 기억이나 추정으로 고정하지 않고, 구현 PR에서 실제 model probe 결과와 테스트 증거를 남긴 뒤 고정한다.

## 2.1 Supabase MCP 및 로컬 Docker 포트 기준

현재 프로젝트는 Supabase MCP를 project-scoped, env-driven 방식으로 연결한다.

- MCP 설정 파일: `.mcp.json`
- 서버 URL: `https://mcp.supabase.com/mcp`
- 필수 로컬 입력값: `SUPABASE_PROJECT_REF`
- 기본 접근 모드: `SUPABASE_MCP_READ_ONLY=true`
- 기본 기능 그룹: `database,docs,debugging,storage`

`SUPABASE_ACCESS_TOKEN`은 CI나 headless 환경에서만 사용하고, 기본 로컬 MCP 인증은
OAuth 흐름을 우선한다. 토큰, DB URL, secret key는 `.env` 또는 비밀 저장소에만
입력하며 `.mcp.json`, PR 본문, 문서, 테스트 fixture에는 기록하지 않는다.

로컬 Supabase Docker 포트는 다른 프로젝트의 기본 `5432x` 블록과 충돌하지 않도록
`5632x` 블록으로 고정한다.

| 서비스 | 포트 |
| --- | --- |
| API | `56321` |
| DB | `56322` |
| Shadow DB | `56320` |
| Studio | `56323` |
| Inbucket | `56324` |
| Pooler | `56329` |

학습 이미지 bucket은 `supabase/config.toml`에 `learning-images`로 정의하며 기본
비공개(`public=false`) 상태를 유지한다. 허용 MIME type은 `image/png`,
`image/jpeg`, `image/webp`이고, 원본 이미지는 사용자 opt-in과 검수 gate를 통과한
경우에만 private Storage/S3-compatible bucket에 저장한다.

## 3. 설계 원칙

1. 기본값은 계속 OFF다. `ENABLE_IMAGE_LEARNING_PIPELINE`, `ENABLE_PGVECTOR_STORAGE`, object storage provider는 sign-off 전까지 production에서 true로 둘 수 없다.
2. 학습 재사용은 세 동의가 모두 있어야 한다. `OCR_IMAGE_PROCESSING`, `DATA_RETENTION`, `IMAGE_LEARNING_DATASET` 중 하나라도 없으면 이미지 저장, embedding 생성, vector upsert를 모두 막는다.
3. API 요청 경로와 heavy runner를 분리한다. `/api/v1/supplements/analyze`는 preview 응답을 우선하고, embedding 작업은 job table과 worker로 넘긴다.
4. raw OCR text는 저장하지 않는다. vector metadata에는 사용자 확인이 끝난 structured field와 가명화된 참조값만 저장한다.
5. 원본 이미지는 DB에 넣지 않는다. 허용된 경우에도 object storage에만 저장하고, DB에는 URI, hash, 크기, MIME, 보유 기한만 남긴다.
6. 삭제와 동의 철회를 구현 범위에 포함한다. `delete all user data`, preview expiry, consent withdrawal, retention expiry가 object와 vector row를 정리해야 한다.
7. optional dependency는 lazy-load한다. 기본 backend install과 CI가 `pgvector`, `sentence-transformers`, torch 계열 의존성 없이도 계속 통과해야 한다.

## 4. 데이터 흐름 설계

### 4.1 Preview 단계

`/api/v1/supplements/analyze`에서 raw image bytes를 사용할 수 있는 시점은 요청 처리 중뿐이다. 따라서 학습 재사용을 나중에 시작하려면 이 시점에 gate를 평가하고, 허용된 경우에만 object storage에 이미지를 보관해야 한다.

흐름:

1. 기존 OCR/parse preview를 실행한다.
2. `hash_actor_subject(user, settings)`로 `owner_subject_hash`를 만든다.
3. `evaluate_image_learning_gate(settings, granted_consents)`를 호출한다.
4. gate가 실패하면 아무 learning row도 만들지 않는다.
5. gate가 통과하면 raw image를 object storage에 저장하고 `learning_image_objects.status='awaiting_confirmation'` row를 만든다.
6. 이 단계에서는 embedding job을 실행하지 않는다. 사용자가 확인하지 않은 OCR text나 parser 추정값을 학습 metadata에 넣지 않기 위함이다.

### 4.2 Confirmation 단계

사용자가 supplement preview를 확인하면, 그때부터 structured field를 학습 metadata 후보로 사용할 수 있다.

흐름:

1. `supplement_analysis_runs.status`가 `confirmed`로 바뀐다.
2. 같은 `analysis_id`의 `learning_image_objects` row가 있으면 `status='ready'`로 전환한다.
3. `image_embedding_jobs`에 `pending` job을 생성한다.
4. job payload에는 raw OCR text를 넣지 않고, 확인된 제품명, 제조사, 성분명, 단위, source manifest version, parser version 같은 structured field만 넣는다.
5. `require_learning_manual_review=true`인 기본 경로에서는 같은 structured field를 `learning_image_objects.review_metadata_snapshot`에만 저장하고, operator 승인 전까지 job을 만들지 않는다.

### 4.3 Worker 단계

worker는 API 프로세스와 분리한다.

흐름:

1. `image_embedding_jobs`에서 `pending` row를 `FOR UPDATE SKIP LOCKED`로 가져온다.
2. object storage에서 image bytes를 읽는다.
3. `EmbeddingProvider.embed()`로 embedding을 만든다.
4. vector 값이 비어 있거나, dimension이 다르거나, `NaN`/`Infinity`가 있으면 실패 처리한다.
5. `VectorStore.upsert_image_embedding()`으로 `image_embedding_records`를 upsert한다.
6. 성공하면 job을 `succeeded`, image object를 `embedded`로 전환한다.
7. retention deadline 또는 사용자 삭제 요청이 오면 object와 vector row를 삭제하거나 tombstone 처리한다.

## 5. DB 설계 초안

### 5.1 pgvector extension migration

권장 migration:

- revision: `0005_create_learning_vector_tables`
- upgrade 첫 단계: `op.execute("CREATE SCHEMA IF NOT EXISTS extensions")`, `op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions")`
- downgrade: extension drop은 기본적으로 하지 않는다. 다른 테이블이나 future feature가 vector extension을 공유할 수 있기 때문이다.

운영 전 preflight:

- 운영 PostgreSQL에 `vector` extension 지원 파일이 설치되어 있는지 확인한다.
- migration 실행 계정이 extension 생성 권한을 갖는지 확인한다.
- production에서 learning flag가 true인 경우 migration 적용 여부를 startup check로 확인한다.

### 5.2 `learning_image_objects`

목적: object storage에 저장된 원본 이미지의 안전한 참조와 보유 기한 관리.

주요 필드:

| 필드 | 설명 |
| --- | --- |
| `id` | UUID primary key |
| `owner_subject_hash` | `hash_actor_subject` 결과. raw subject 저장 금지 |
| `analysis_id` | `supplement_analysis_runs.id` 참조 |
| `image_sha256` | image bytes SHA-256 |
| `object_uri` | `s3://bucket/key` 또는 local dev URI |
| `object_storage_provider` | `s3`, `local`, `disabled` 중 실제 provider |
| `object_version_id` | versioned bucket 사용 시 삭제 정확도를 위해 저장 |
| `image_mime_type` | 허용 MIME |
| `image_size_bytes` | 업로드 크기 |
| `retained_until` | 자동삭제 기준 시각 |
| `status` | `awaiting_confirmation`, `pending_auto_filter`, `pending_manual_review`, `approved_for_embedding`, `ready`, `embedded`, `deleted`, `cancelled`, `failed`, `rejected_by_auto_filter`, `rejected_by_review` |
| `consent_snapshot` | 동의 type과 policy version. raw consent text 저장 금지 |
| `review_metadata_snapshot` | 수동 검수 대기 중인 user-confirmed structured metadata. raw OCR text, provider payload, image bytes, secret 저장 금지 |
| `created_at`, `updated_at`, `deleted_at` | lifecycle 추적 |

제약:

- raw image bytes 컬럼 금지
- raw OCR text 컬럼 금지
- `owner_subject_hash`는 64자 HMAC hex로 제한
- `image_sha256`은 64자 hex로 제한
- `retained_until`은 `IMAGE_RETENTION_DAYS > 0`인 경우 필수

### 5.3 `image_embedding_jobs`

목적: API와 embedding runner를 분리하는 DB-backed queue.

주요 필드:

| 필드 | 설명 |
| --- | --- |
| `id` | UUID primary key |
| `image_object_id` | `learning_image_objects.id` 참조 |
| `analysis_id` | 중복 조회 방지용 참조 |
| `owner_subject_hash` | owner filter |
| `status` | `pending`, `running`, `succeeded`, `failed`, `dead`, `cancelled` |
| `attempt_count` | retry 횟수 |
| `next_run_at` | backoff 후 재시도 시각 |
| `locked_at`, `locked_by` | worker lease |
| `error_code`, `error_message` | 안전한 오류 코드와 요약. raw OCR text 금지 |
| `metadata_snapshot` | 사용자 확인 structured field만 저장 |
| `created_at`, `updated_at` | lifecycle 추적 |

worker 동시성:

- pending job 조회는 `FOR UPDATE SKIP LOCKED`로 처리한다.
- 같은 `image_object_id`, `embedding_model` 조합은 unique constraint로 중복 job을 막는다.
- 일정 횟수 이상 실패하면 `dead`로 전환하고 운영자가 재시작하도록 한다.

### 5.4 `image_embedding_records`

목적: pgvector에 저장되는 최종 image embedding record.

주요 필드:

| 필드 | 설명 |
| --- | --- |
| `id` | UUID primary key |
| `owner_subject_hash` | similarity query owner scope |
| `analysis_id` | 원본 preview 참조 |
| `image_object_id` | source object 참조 |
| `image_sha256` | source image hash |
| `embedding_model` | 모델 식별자 |
| `embedding_dimensions` | 실제 output dimension |
| `embedding` | `VECTOR(n)` |
| `metadata` | 확인된 structured field와 버전 정보 |
| `created_at`, `updated_at`, `deleted_at` | lifecycle 추적 |

제약:

- `embedding_dimensions`와 `VECTOR(n)`은 같은 값을 사용한다.
- `embedding` 값은 finite float만 허용한다. pgvector도 finite 값만 허용하므로 runner에서 사전 검증한다.
- `metadata`에는 raw image, base64 image, raw OCR text, full owner subject, access token, vendor credential을 넣지 않는다.
- 초기에는 `(owner_subject_hash, analysis_id, embedding_model, image_sha256)` unique constraint로 idempotent upsert를 보장한다.

### 5.5 Vector index 전략

초기 migration에서 HNSW index를 바로 만들지 않는다.

이유:

- HNSW는 recall과 성능 trade-off가 있고, index build time과 memory cost가 있다.
- 현재는 label fixture 기반 embedding 품질과 query 목적이 아직 확정되지 않았다.
- 데이터가 거의 없는 초기 단계에서는 exact search로도 동작 검증이 가능하다.

후속 benchmark PR에서 아래 조건을 만족하면 HNSW index를 추가한다.

- fixture 기준 similarity query 결과가 팀 검토를 통과한다.
- `EXPLAIN (ANALYZE, BUFFERS)` 결과와 latency 리포트가 있다.
- opclass는 기본 후보로 `vector_cosine_ops`를 검토한다.
- HNSW 설정값은 pgvector 기본값부터 시작하고, 임의 성능 수치를 문서에 적지 않는다.

## 6. Adapter 설계

### 6.1 Object storage adapter

패키지 후보:

```text
src/learning/object_storage.py
```

계약:

```text
LearningImageObjectStore.put_image(image_bytes, metadata, retained_until) -> StoredLearningImage
LearningImageObjectStore.get_image(object_uri, version_id=None) -> bytes
LearningImageObjectStore.delete_image(object_uri, version_id=None) -> None
```

구현 순서:

1. `DisabledLearningImageObjectStore`: 기본값. 항상 fail-closed.
2. `LocalLearningImageObjectStore`: 개발/테스트 전용. git ignored temp path 사용.
3. `S3LearningImageObjectStore`: S3 또는 S3-compatible storage. `put_object`, `delete_object` 래핑.

권장 설정:

| 설정 | 기본값 | 설명 |
| --- | --- | --- |
| `LEARNING_OBJECT_STORAGE_PROVIDER` | `disabled` | `disabled`, `local`, `s3`, `supabase_s3` |
| `LEARNING_OBJECT_STORAGE_BUCKET` | 없음 | generic `s3` provider에서 필수. `supabase_s3`는 기본적으로 `SUPABASE_STORAGE_PRIVATE_BUCKET` 사용 |
| `LEARNING_OBJECT_STORAGE_PREFIX` | `learning/images` | object key prefix |
| `LEARNING_OBJECT_STORAGE_ENDPOINT_URL` | 없음 | S3-compatible storage 사용 시. hosted `supabase_s3`는 비워두면 `SUPABASE_PROJECT_REF`로 endpoint를 구성 |
| `LEARNING_OBJECT_STORAGE_REGION` | 없음 | cloud provider region. Supabase S3 설정 페이지의 region을 사용 |
| `LEARNING_OBJECT_STORAGE_SSE` | `AES256` 후보 | 운영 sign-off 후 확정 |
| `SUPABASE_STORAGE_S3_ACCESS_KEY_ID` | 없음 | Supabase Storage S3 설정에서 발급한 server-only access key id |
| `SUPABASE_STORAGE_S3_SECRET_ACCESS_KEY` | 없음 | Supabase Storage S3 설정에서 발급한 server-only secret access key |

credential JSON이나 access key는 저장소에 커밋하지 않는다. 실제 secret은 배포 환경의 secret manager 또는 runtime env에서만 주입한다.

### 6.2 Embedding model runner

패키지 후보:

```text
src/learning/embedding_runner.py
```

구현체 후보:

- `DisabledEmbeddingProvider`: 기존 기본값 유지
- `SentenceTransformersImageEmbeddingProvider`: `sentence-transformers/clip-ViT-B-32` 기반 local runner

요구사항:

- model은 lazy-load한다.
- 요청 처리 중 network download가 일어나지 않도록 운영 image build 단계에서 model cache를 준비한다.
- output vector dimension은 runner readiness test로 기록한다.
- `embedding_model` 설정과 실제 loaded model id가 다르면 실패한다.
- output vector는 tuple of finite float로 정규화한다.
- raw OCR text를 runner input으로 넘기지 않는다. 필요한 경우 사용자 확인 structured field를 canonical text로 별도 생성한다.

구현 전 필수 확인:

- `clip-ViT-B-32` 실제 output dimension probe 결과
- CPU/GPU memory footprint
- 평균 runner latency. 단, 실측 전 문서에 임의 latency 수치를 적지 않는다.

### 6.3 pgvector store adapter

패키지 후보:

```text
src/learning/pgvector_store.py
```

역할:

- `VectorStore.upsert_image_embedding(record)` 구현
- owner scope 밖 similarity query를 금지
- vector dimension mismatch를 DB insert 전에 차단
- optional dependency import 실패 시 명확한 `VectorStoreError` 반환

초기 query API는 외부 공개 endpoint로 만들지 않는다. 먼저 내부 service와 worker의 upsert 안정성을 확보한 뒤, similarity search endpoint는 별도 sign-off 뒤에 추가한다.

## 7. 구현 플랜

### LVB-0. 기준선 문서와 sign-off 준비

- `docs/Nutrition-docs/41-learning-vector-db-implementation-design-plan.md`를 팀 리뷰 기준 문서로 사용한다.
- `docs/Nutrition-docs/36-post-p1-execution-plan.md`의 P3 항목에서 본 문서를 참조한다.
- production flag 활성화 PR에는 sign-off 문서와 migration 적용 evidence를 요구한다.

완료 기준:

- 현재 learning 기능이 default-off skeleton이라는 점이 docs/22, docs/36, docs/41에서 충돌하지 않는다.

### LVB-1. pgvector migration과 ORM schema

작업:

- `0005_create_learning_vector_tables.py` migration 추가
- `learning_image_objects`, `image_embedding_jobs`, `image_embedding_records` table 생성
- `CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions` 포함
- ORM 모델 `models/db/learning.py` 추가
- `Base` metadata import 경로에 모델 연결
- pgvector dependency는 optional `[learning]`로 유지

검증:

- Alembic upgrade/downgrade dry-run
- SQLAlchemy model metadata test
- raw image/raw OCR text 컬럼명이 없다는 schema test
- production에서 flag가 false일 때 app boot 영향이 없다는 config smoke

### LVB-2. Object storage adapter

작업:

- `LearningImageObjectStore` 계약 추가
- disabled/local/s3 adapter 추가
- object URI와 version id 처리 규칙 정의
- retention cleanup helper 추가
- `.env.example`에 secret 값을 제외한 설정 이름만 추가

검증:

- fake/local store unit test
- S3 adapter는 fake client 기반으로 `put_object`, `delete_object` 호출 인자 검증
- image bytes가 DB payload나 log에 남지 않는 테스트

### LVB-3. Embedding runner

작업:

- `SentenceTransformersImageEmbeddingProvider` 구현
- model lazy-load와 readiness probe 추가
- output dimension, finite float, empty vector 검증
- raw OCR text 입력 차단
- real model test는 `RUN_LEARNING_REAL_MODEL_TESTS=1` 같은 opt-in gate 뒤에 둔다.

검증:

- fake provider unit test
- real provider smoke는 opt-in에서만 실행
- dimension mismatch test
- optional dependency 미설치 시 disabled path가 깨지지 않는 test

### LVB-4. Vector upsert worker

작업:

- `image_embedding_jobs` polling worker 구현
- `FOR UPDATE SKIP LOCKED` 기반 lease 처리
- retry/backoff/dead-letter 상태 전환
- `PgvectorStore.upsert_image_embedding()` 연결
- worker CLI 또는 관리 command 추가

검증:

- fake store + fake embedding provider로 worker 성공/실패/retry test
- 같은 image object job 중복 upsert idempotency test
- `metadata_snapshot`에 금지 필드가 있으면 실패하는 test

### LVB-5. API integration

작업:

- `/api/v1/supplements/analyze`에서 gate 통과 시 object 저장 row 생성
- supplement confirmation 흐름에서 job enqueue
- preview expiry cleanup에서 awaiting object cancel/delete
- user deletion request에서 learning object, job, vector record 삭제 반영

검증:

- learning flags false일 때 기존 analyze 응답과 DB 저장이 변하지 않는 regression test
- consent 누락 시 storage/worker 호출이 없는 integration test
- consent 통과 시 object row만 생성되고 embedding은 confirmation 전 실행되지 않는 test
- confirmation 후 job이 생성되는 test

### LVB-6. Retention과 deletion

작업:

- `retained_until < now` object 삭제 worker 추가
- consent withdrawal 또는 delete all user data에서 object와 vector row 삭제
- object delete 실패 시 재시도 가능한 상태로 남김
- audit log에는 object URI 전체 대신 resource id와 안전한 error code만 남김

검증:

- retention expiry test
- delete all user data count에 learning rows 포함
- object delete failure retry test

### LVB-7. Similarity search와 benchmark

작업:

- 내부 similarity lookup service 추가
- owner scope 강제
- fixture 기반 정확도/latency 리포트 작성
- 필요 시 HNSW index migration 추가

검증:

- owner A query가 owner B embedding을 반환하지 않는 test
- HNSW 추가 전후 `EXPLAIN (ANALYZE, BUFFERS)` evidence
- 임의 성능 수치가 아닌 실제 fixture report만 문서화

## 8. 테스트 매트릭스

| 테스트 | 목적 |
| --- | --- |
| `test_learning_flags_default_off` | 기본 환경에서 learning/vector 저장이 꺼져 있는지 확인 |
| `test_learning_gate_requires_three_consents` | 세 동의가 모두 없으면 저장 차단 |
| `test_learning_schema_forbids_raw_payload_columns` | raw image/raw OCR text 컬럼 방지 |
| `test_object_store_fake_put_delete` | object storage adapter 계약 검증 |
| `test_embedding_runner_rejects_invalid_vector` | empty, NaN, Infinity, dimension mismatch 차단 |
| `test_worker_uses_confirmed_metadata_only` | preview 추정값이나 raw OCR text 저장 방지 |
| `test_worker_idempotent_upsert` | 중복 job 안전성 |
| `test_delete_all_user_data_removes_learning_records` | 사용자 삭제 요청 반영 |
| `test_retention_cleanup_deletes_expired_objects` | 보유 기간 만료 후 object 삭제 |
| `test_real_embedding_provider_opt_in` | 실제 model smoke는 명시 opt-in에서만 실행 |
| `test_pgvector_integration_opt_in` | 실제 pgvector DB test는 명시 opt-in에서만 실행 |

## 9. PR 분리 권장안

1. `docs(learning): define vector db implementation plan`
   - 이유: 구현 전 저장 정책, 동의 gate, DB/worker 구조를 팀 기준으로 맞추기 위함.
2. `feat(db): add consent-gated learning vector tables`
   - 이유: pgvector extension과 learning table을 runtime adapter와 분리해 migration risk를 먼저 검토하기 위함.
3. `feat(learning): add image object storage adapters`
   - 이유: raw image를 DB에 넣지 않는 저장 경로와 삭제 경로를 먼저 확정하기 위함.
4. `feat(learning): add local embedding runner`
   - 이유: model loading, dimension, invalid vector 검증을 vector DB upsert와 분리해 검증하기 위함.
5. `feat(learning): add vector upsert worker`
   - 이유: API latency와 embedding 작업을 분리하고 retry/idempotency를 보장하기 위함.
6. `feat(api): enqueue confirmed supplement image embeddings`
   - 이유: 사용자 확인이 끝난 structured field만 학습 metadata로 사용하기 위함.
7. `fix(privacy): include learning artifacts in deletion flows`
   - 이유: 사용자 삭제와 retention 정책이 object storage와 vector row까지 닿도록 하기 위함.

## 10. 이번 단계의 결론

Learning/vector DB는 단일 PR로 바로 연결하면 위험하다. raw image가 필요한 시점은 analyze 요청 중이고, 학습 metadata로 사용할 수 있는 값은 confirmation 이후에 확정되므로, object 저장과 embedding job enqueue를 분리해야 한다.

따라서 다음 구현 착수 순서는 `migration/schema -> object storage -> embedding runner -> worker -> API integration -> retention/deletion -> similarity benchmark`가 가장 안전하다. 모든 단계에서 기본 OFF와 세 동의 gate를 유지해야 하며, 실제 model dimension과 성능 수치는 구현 PR의 opt-in smoke와 fixture report로만 기록한다.

## 11. 2026-05-15 구현 반영 상태

이번 구현에서 아래 항목을 코드에 반영했다.

| 항목 | 구현 파일 |
| --- | --- |
| pgvector extension migration과 learning table | `backend/alembic/versions/0005_create_learning_vector_tables.py` |
| ORM schema | `backend/src/models/db/learning.py`, `backend/src/models/db/__init__.py` |
| object storage adapter | `backend/src/learning/object_storage.py`, `backend/src/learning/factory.py` |
| embedding runner | `backend/src/learning/embedding_runner.py` |
| pgvector upsert adapter | `backend/src/learning/pgvector_store.py` |
| vector upsert worker | `backend/src/learning/upsert_worker.py`, `backend/scripts/run_learning_vector_worker.py` |
| analyze/confirmation 연결 | `backend/src/services/supplement_image_analysis.py`, `backend/src/api/v1/supplements.py` |
| manual review decision runner | `backend/scripts/apply_learning_manual_review_decision.py` |
| user deletion/retention helper | `backend/src/learning/pipeline.py`, `backend/src/services/privacy.py` |
| regression tests | `backend/tests/unit/learning/`, `backend/tests/unit/db/test_models.py`, `backend/tests/unit/test_config.py`, `backend/tests/unit/services/test_privacy.py` |

운영 활성화 전 남은 opt-in 검증:

- 실제 PostgreSQL 환경에서 `0005_create_learning_vector_tables` migration 적용 확인
- `sentence-transformers/clip-ViT-B-32` 실제 model probe로 output dimension 기록
- 실제 pgvector insert/query smoke test
- Supabase `learning-images` private bucket에 대한 S3-compatible put/get/delete smoke test
- fixture 기반 embedding similarity 품질 리포트와 HNSW index 추가 여부 판단

## 12. 2026-05-25 Supabase 운영 반영 보안 보강

사용자 결정에 따라 운영 경로는 "기존 Supabase + Private Storage + 사용자 opt-in + 자동 필터링 + 수동 검수 후 학습"으로 고정한다. 자동 필터링을 운영상 사용할 수 없는 환경에서는 수동 검수 장벽을 fallback으로 유지한다.

반영 원칙:

- `learning_image_objects`, `image_embedding_jobs`, `image_embedding_records`는 backend direct PostgreSQL 연결 전용이다.
- Supabase Data API 경로는 `anon`, `authenticated`, `service_role`, `PUBLIC` grant 제거와 RLS enable로 기본 차단한다.
- 사용자 opt-in과 supplement confirmation이 끝나도 먼저 `enable_learning_auto_filter=true` 기준으로 raw key, PII-like text, 성분 signal을 검사한다. 실패하면 `rejected_by_auto_filter`, 통과 후 `require_learning_manual_review=true` 기본값에서는 embedding job을 만들지 않고 `pending_manual_review` 상태에서 멈춘다.
- `ocr_image_processing`, `data_retention`, `image_learning_dataset` 중 하나라도 철회되면
  기존 learning image object, embedding job, pgvector row, private Storage 원본을 삭제한다.
  audit metadata에는 삭제 count만 남기고 object URI, owner hash, raw OCR/provider payload는 남기지 않는다.
- Private Storage는 Supabase Storage의 S3-compatible private bucket 또는 동등한 private object store만 허용한다. Public bucket은 학습 이미지 원본 저장에 쓰지 않는다.
- 모델 학습 입력에는 operator 검수로 승인된 구조화 라벨과 image object reference/hash만 사용하며 raw OCR text, provider payload, request header, secret은 계속 금지한다.

Supabase `supabase_s3` provider는 generic S3와 다르게 `x-amz-server-side-encryption`
계열 헤더를 전송하지 않는다. Supabase Storage S3 compatibility 문서에서
`PutObject`의 `x-amz-server-side-encryption` 헤더가 미지원으로 표시되어 있기
때문이다. `LEARNING_OBJECT_STORAGE_SSE`는 generic `s3` provider에만 적용한다.
object metadata도 raw OCR text, provider payload, request header, image bytes,
secret-like value를 금지해 S3 metadata header를 통한 우회 저장을 차단한다.

반영 순서:

1. 로컬 PostgreSQL에서 Alembic `upgrade head`를 먼저 실행한다.
2. `backend/scripts/check_learning_vector_db_security.py --strict`로 pgvector extension, learning/vector table, RLS, Supabase API-role grant, raw column 부재, `learning-images` private bucket 설정, client role Storage policy 누출 부재를 확인한다.
3. 기존 Supabase 프로젝트가 link된 작업 디렉터리에서 preflight/advisor를 실행한다.
4. Supabase 원격 DB에는 동일 Alembic migration을 적용한 뒤 같은 preflight를 재실행한다.
5. server-only S3 access key가 준비된 operator 환경에서 아래 live smoke를 실행해
   `learning-images` private bucket의 put/get/delete round-trip을 확인한다.
6. 운영 batch 또는 수동 작업으로 아래 retention cleanup을 주기 실행해
   `retained_until`이 지난 image object와 private Storage 원본을 삭제한다.
7. 수동 검수 대상은 아래 queue export로 먼저 확인하고, `object_uri`,
   `owner_subject_hash`, raw OCR/provider payload 없이 internal operator artifact로만
   보관한다.

```bash
RUN_LEARNING_STORAGE_LIVE_SMOKE=1 \
PYTHONPATH=backend/Nutrition-backend \
.venv/bin/python backend/scripts/smoke_learning_private_storage.py
```

이 smoke는 object URI, object metadata, image bytes, SDK exception message,
secret 값을 출력하지 않고 `status`, provider, round-trip 여부만 표시한다.

```bash
PYTHONPATH=backend/Nutrition-backend \
.venv/bin/python backend/scripts/delete_expired_learning_images.py --limit 100
```

retention cleanup 출력도 object URI, SDK exception message, secret 값을 표시하지 않고
삭제 건수와 provider만 표시한다. 삭제 실패 시에는 해당 exception type만 출력해 운영자가
로그 접근 권한이 있는 환경에서 별도 조사하도록 한다.

```bash
PYTHONPATH=backend/Nutrition-backend \
.venv/bin/python backend/scripts/retry_failed_learning_image_deletions.py --limit 100
```

사용자 삭제 또는 동의 철회 중 private Storage 삭제가 실패한 image object는
DB row를 즉시 제거하지 않고 `status=failed` 상태로 보존한다. 재시도 runner 출력은
provider, limit, scanned/deleted/failure count만 표시하고 object URI, owner hash,
SDK exception message, secret 값은 표시하지 않는다. 실패 row의 object URI는 backend
operator retry를 위해 DB 내부에만 남기며, manual review/export artifact에는 포함하지 않는다.

```bash
PYTHONPATH=backend/Nutrition-backend \
.venv/bin/python backend/scripts/export_learning_manual_review_queue.py \
  --output outputs/generated/learning/manual-review-queue.jsonl \
  --limit 100
```

manual review queue는 `image_object_id`, `analysis_id`, provider, MIME, size,
retention deadline, metadata shape summary만 내보낸다. 원본 object URI, owner hash,
metadata value body, raw OCR text, provider payload, request headers, image bytes,
secret-like value는 출력하지 않는다.

검증 기록:

- 2026-05-25 로컬 Supabase Postgres clean DB 검증:
  - `alembic upgrade head`가 `0012_configure_learning_private_storage_bucket`까지 적용됨
  - `check_learning_vector_db_security.py --strict` 통과
  - `vector_extension_schema=extensions`, learning/vector 3개 table RLS enabled, unsafe privilege 0, forbidden raw column 0, unsafe SECURITY DEFINER function 0
  - `learning-images` bucket 존재, `public=false`, `file_size_limit=20971520`, allowed MIME type `image/jpeg`, `image/png`, `image/webp`, unsafe learning Storage policy 0
  - `supabase db advisors --local --type security --output json` 결과: `No issues found`
- 2026-05-25 기존 Supabase 원격 반영 상태(MCP):
  - project: `Lemon-Aid`, ref `weipsloxntjzcqjvzjax`, region `ap-south-1`, Postgres `17`
  - 원격 DB에 learning/vector 3개 table과 `extensions.vector` 존재 확인
  - 원격 DB `learning_image_objects.review_metadata_snapshot` JSONB column 존재 확인
  - 원격 DB에서 `anon`, `authenticated`, `service_role`, `PUBLIC`의 learning/vector table 직접 grant 제거 완료
  - 원격 DB에서 `public.rls_auto_enable()` SECURITY DEFINER helper의 client-role execute grant 제거 완료
  - 원격 DB `alembic_version=0013_index_user_supplement_foreign_keys` 확인
  - 원격 DB `user_supplements.source_analysis_run_id`, `user_supplements.matched_product_id`
    covering index 존재 확인
  - Supabase performance advisor의 `user_supplements` unindexed foreign key 항목 제거 확인
    (`unused_index` INFO는 새 인덱스 생성 직후 사용 통계가 아직 없어 발생)
  - 원격 보안 요약: vector extension in `extensions` true, learning table RLS true, unsafe privilege 0, forbidden raw column 0, unsafe SECURITY DEFINER function 0
  - 원격 Storage 요약: `learning-images` bucket private configured true, unsafe learning Storage policy 0
  - Supabase security advisor의 WARN 항목은 제거됨. RLS enabled/no-policy INFO는 fail-closed 정책상 의도한 상태로 둔다.
  - 로컬 `.env` 기반 `check_learning_vector_db_security.py --strict`는 현재
    `DATABASE_URL` 인증 실패(`InvalidPasswordError`)로 직접 DB 접속 검증 불가.
    원격 검증은 Supabase MCP read-only SQL/advisor와 `apply_migration` 결과로 대체했다.

### 2026-05-25 추가 반영: user_supplements FK index

Supabase performance advisor가 `user_supplements`의 아래 foreign key에 covering index가
없다고 지적했다.

- `source_analysis_run_id -> supplement_analysis_runs.id`
- `matched_product_id -> supplement_products.id`

`0013_index_user_supplement_foreign_keys` migration은 데이터 노출 범위를 바꾸지 않고
아래 index만 추가한다.

- `ix_user_supplements_source_analysis_run_id`
- `ix_user_supplements_matched_product_id`

이 변경은 confirmed supplement가 preview run 또는 reference product와 조인될 때,
그리고 FK `ON DELETE SET NULL` referential action이 실행될 때 불필요한 table scan을
줄이기 위한 성능 보강이다. `GRANT`, RLS policy, raw OCR/provider payload column은
추가하지 않는다.

### 2026-05-25 추가 반영: private Storage bucket

원격 Supabase 확인 결과 `learning-images` bucket이 아직 없었으므로
`0012_configure_learning_private_storage_bucket` migration으로 아래 설정을
idempotent하게 반영한다.

- bucket id/name: `learning-images`
- 공개 여부: `public=false`
- 파일 크기 제한: `20MiB`
- 허용 MIME type: `image/jpeg`, `image/png`, `image/webp`
- `storage.objects` client role policy는 이 bucket을 대상으로 만들지 않는다.

`check_learning_vector_db_security.py`는 v2부터 DB table 보안뿐 아니라 이 private
bucket 존재 여부와 `anon`/`authenticated`/`public` policy가 `learning-images`를
노출하지 않는지도 함께 확인한다.
- `pytest -o addopts='' tests/unit/learning tests/unit/db/test_models.py tests/unit/test_config.py tests/unit/services/test_supplement_image_analysis.py tests/unit/services/test_privacy.py -q` 통과
- `pytest -o addopts='' -q --ignore=tests/unit/db/test_session.py` 통과
- `ruff check src tests scripts` 통과
- `mypy src scripts` 통과
- `git diff --check` 통과

현재 로컬 Python runtime에는 `asyncpg`가 설치되어 있지 않아 전체 `pytest -o addopts='' -q` 중 `tests/unit/db/test_session.py` 3건은 `ModuleNotFoundError: No module named 'asyncpg'`로 실패한다. 해당 실패는 이번 learning/vector 구현 로직 실패가 아니라 PostgreSQL async driver 미설치 환경 문제다.
