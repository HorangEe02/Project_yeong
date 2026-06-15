# Supabase pgvector 전환 브레인스토밍 및 상세 구현 계획

작성일: 2026-05-21  
범위: ChromaDB/vectorstore 기반 검색 및 RAG를 Supabase Postgres + pgvector 중심 구조로 전환하는 계획  
원칙: 공개 사용자 API는 유지하고, 내부 검색 저장소와 release gate를 단계적으로 교체한다.

## 1. 결론

AJIN 프로젝트의 vector DB는 `Supabase Postgres + pgvector`로 전환하는 것이 맞다. 현재 Supabase 전환, RLS, Storage signed URL, release-security-check가 이미 gate로 자리 잡고 있으므로, 벡터 검색도 같은 Postgres 데이터 평면으로 넣는 편이 운영/보안/백업/검증 측면에서 일관적이다.

권장 구조는 다음과 같다.

```text
현재
  data/*.db / ChromaDB / bm25_corpus.json / vectorstore/*

전환 목표
  Supabase Postgres
    public.documents
    public.document_chunks
    public.document_embeddings
    public.employee_embeddings
    public.rag_collections
    public.rag_chunks
    RPC: match_documents, hybrid_search_documents, match_employees, match_rag_chunks

  Embedding 생성
    Local Docker backend -> host.docker.internal Ollama -> bge-m3
    vector dimension: 현재 AJIN Ollama embedding 기준 1024 차원으로 고정 검증 필요
```

Supabase Storage Vector buckets도 선택지이지만, 사용자가 원하는 방향이 “Supabase를 이용한 벡터 DB + PostgreSQL 활용”이므로 이번 전환의 primary는 Postgres `pgvector`이다. Storage Vector는 대용량 비정형 object embedding이 별도 요구될 때 후보로 남긴다.

## 2. 공식 문서 기준

- Supabase는 AI & Vectors 문서에서 Postgres와 `pgvector`를 사용한 vector store, semantic search, keyword search, hybrid search를 지원한다고 설명한다.
- Supabase semantic search 문서는 `create extension vector with schema extensions`, `extensions.vector(n)` 컬럼, `match_documents` RPC, HNSW/IVFFlat index를 공식 예시로 제시한다.
- Supabase vector columns 문서는 vector 컬럼 차원을 embedding model output dimension과 반드시 맞춰야 한다고 설명한다.
- Supabase vector columns 문서는 PostgREST가 pgvector similarity operator를 직접 지원하지 않으므로 Postgres function으로 감싸고 RPC로 호출하는 방식을 제시한다.
- Supabase changelog 기준 2026-04-28 이후 SQL로 만든 table이 Data/GraphQL API에 자동 노출되지 않는 breaking change가 있으므로, public exposed schema에서 RLS와 GRANT/Data API posture를 별도 gate로 관리해야 한다.

참고:
- https://supabase.com/docs/guides/ai
- https://supabase.com/docs/guides/ai/semantic-search
- https://supabase.com/docs/guides/ai/vector-columns
- https://supabase.com/docs/guides/ai/hybrid-search
- https://supabase.com/docs/guides/ai/vector-indexes
- https://supabase.com/docs/guides/ai/vecs-python-client
- https://supabase.com/docs/guides/api/securing-your-api
- https://supabase.com/changelog?tags=database

## 3. 현재 AJIN 코드 영향 범위

현재 ChromaDB는 단일 Feature A에만 있는 것이 아니다. 제거 범위를 잘못 잡으면 C/D/F까지 회귀가 난다.

| 영역 | 현재 Chroma/Vector 의존 | 전환 대상 |
| --- | --- | --- |
| Feature A 문서 검색 | `features/search/searcher.py`, `features/search/indexer.py`, `vectorstore/documents`, `bm25_corpus.json`, collection `ajin_documents` | `public.document_chunks`, `public.document_embeddings`, RPC `hybrid_search_documents` |
| Feature A 직원 시맨틱 검색 | `features/search/employee/semantic_search.py`, collection `employee_profiles` | `public.employee_embeddings`, RPC `match_employees` |
| Feature B Draft 검색/RAG | `features/draft/search_engine.py`, `features/draft/fewshot_rag.py` | `public.rag_collections`, `public.rag_chunks`, collection key `draft_fewshot` |
| Feature D Compliance RAG | `features/compliance/infra/regulation_indexer.py`, `case_law_indexer.py`, `contract_indexer.py` | `public.rag_chunks`, collection keys `regulations_rag`, `case_law_rag`, `contracts_rag` |
| Feature F 설비 매뉴얼 RAG | `features/equipment/manual_rag.py` | `public.rag_chunks`, collection key `equipment_manuals` |
| Health/Dashboard | `backend/routers/health.py`, `backend/routers/admin.py`, `backend/routers/dashboard.py`가 Chroma/vectorstore 상태 표시 | Supabase vector status, table count, index status, RPC status로 교체 |
| Release gate | `scripts/verify_feature_a_consistency.py`가 SQLite/Chroma/Postgres/BM25 일관성 확인 | SQLite/Postgres/pgvector/FTS/RPC 일관성 gate로 교체 |

## 4. 핵심 설계

### 4.1 Schema

`extensions.vector(1024)`를 기준으로 설계한다. 단, 실제 차원은 `Ollama bge-m3 /api/embeddings` smoke로 release 전 한 번 더 고정해야 한다. embedding model이 바뀌면 기존 vector와 비교가 무의미하므로 `embedding_model`, `embedding_dim`, `embedding_version`을 모든 row에 남긴다.

```sql
create extension if not exists vector with schema extensions;

create table if not exists public.document_chunks (
  id uuid primary key default gen_random_uuid(),
  source_doc_id text not null,
  chunk_index integer not null,
  title text,
  doc_type text,
  part_name text,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  content_hash text not null,
  fts tsvector generated always as (
    to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, ''))
  ) stored,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (source_doc_id, chunk_index)
);

create table if not exists public.document_embeddings (
  chunk_id uuid primary key references public.document_chunks(id) on delete cascade,
  embedding extensions.vector(1024) not null,
  embedding_model text not null,
  embedding_dim integer not null,
  embedding_version text not null,
  embedded_at timestamptz not null default now()
);

create table if not exists public.employee_embeddings (
  employee_id text primary key references public.employees(employee_id) on delete cascade,
  searchable_text text not null,
  metadata jsonb not null default '{}'::jsonb,
  embedding extensions.vector(1024) not null,
  embedding_model text not null,
  embedding_dim integer not null,
  embedding_version text not null,
  embedded_at timestamptz not null default now()
);

create table if not exists public.rag_collections (
  key text primary key,
  feature text not null,
  description text,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.rag_chunks (
  id uuid primary key default gen_random_uuid(),
  collection_key text not null references public.rag_collections(key),
  source_id text not null,
  chunk_index integer not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  content_hash text not null,
  fts tsvector generated always as (to_tsvector('simple', content)) stored,
  embedding extensions.vector(1024) not null,
  embedding_model text not null,
  embedding_dim integer not null,
  embedding_version text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (collection_key, source_id, chunk_index)
);
```

### 4.2 Index

초기에는 HNSW를 기본으로 둔다. AJIN 검색은 read-heavy이고, release smoke/업무 화면에서 low latency가 더 중요하다. 데이터가 100k~10M row로 커지고 memory 부담이 커지면 IVFFlat을 별도 튜닝 후보로 둔다.

```sql
create index if not exists idx_document_chunks_fts
  on public.document_chunks using gin (fts);

create index if not exists idx_document_embeddings_hnsw
  on public.document_embeddings using hnsw (embedding vector_cosine_ops);

create index if not exists idx_employee_embeddings_hnsw
  on public.employee_embeddings using hnsw (embedding vector_cosine_ops);

create index if not exists idx_rag_chunks_fts
  on public.rag_chunks using gin (fts);

create index if not exists idx_rag_chunks_hnsw
  on public.rag_chunks using hnsw (embedding vector_cosine_ops);

create index if not exists idx_rag_chunks_collection
  on public.rag_chunks (collection_key);
```

### 4.3 RPC

Frontend나 일반 Data API가 vector operator를 직접 다루지 않게 한다. Backend가 service role 또는 DB URL로 RPC를 호출하고, UI API 응답 schema는 유지한다.

필요 RPC:

- `match_documents(query_embedding, match_count, doc_type_filter, part_name_filter, date_from, date_to)`
- `hybrid_search_documents(query_text, query_embedding, match_count, full_text_weight, semantic_weight, rrf_k, filters...)`
- `match_employees(query_embedding, match_count, department_filter, role_filter)`
- `match_rag_chunks(collection_key, query_embedding, match_count, metadata_filter)`

Hybrid search는 Supabase 문서처럼 Postgres `tsvector` + `pgvector`를 RRF로 합치는 방식이 맞다. 기존 Python `rank_bm25`와 `bm25_corpus.json`은 전환 기간에만 유지하고, 목표 상태에서는 Postgres FTS로 대체한다.

## 5. Adapter 구조

Chroma 호출부를 한 번에 갈아엎지 말고 내부 interface를 먼저 만든다.

```text
features/search/vector_store/
  __init__.py
  base.py
  chroma_store.py          # legacy fallback
  supabase_pgvector.py     # new primary
  embedding.py             # Ollama bge-m3 wrapper

settings:
  VECTOR_BACKEND=postgres | chroma | dual
  VECTOR_WRITE_MODE=postgres | chroma | dual
  VECTOR_READ_MODE=postgres | chroma
  VECTOR_EMBEDDING_MODEL=bge-m3
  VECTOR_EMBEDDING_DIM=1024
```

초기 release는 `VECTOR_BACKEND=dual`, `VECTOR_READ_MODE=chroma`로 시작해 비교 report를 만들고, pass가 쌓이면 `VECTOR_READ_MODE=postgres`로 전환한다. 마지막에 Chroma 코드를 제거한다.

## 6. 단계별 구현 계획

### Phase 0. 기준 고정

목표: 실제 embedding 차원, 현재 Chroma/BM25 row 수, Postgres table 상태를 고정한다.

작업:
- `scripts/verify_pgvector_prereq.py` 추가
  - Supabase project에 `vector` extension 존재 확인
  - `select extversion from pg_extension where extname='vector'`
  - `Ollama bge-m3` embedding dim smoke
  - `document Chroma count`, `bm25_corpus count`, `employee_profiles count`, `regulations_rag count` inventory
- 보고서: `outputs/supabase-verification/YYYY-MM-DD-pgvector-prereq.md`

완료 기준:
- embedding dim 확정
- Chroma collection별 count 산출
- Supabase SQL migration 가능 상태 확인

### Phase 1. Supabase schema migration

목표: pgvector 저장소와 RPC skeleton을 Supabase에 추가한다.

작업:
- `supabase migration new add_pgvector_search_store`
- `create extension vector with schema extensions`
- `document_chunks`, `document_embeddings`, `employee_embeddings`, `rag_collections`, `rag_chunks` 생성
- RLS enable
- exposed schema policy는 기본 deny
- backend service role/DB URL 경로만 write/read 허용
- `match_*`, `hybrid_search_*` RPC 추가
- verifier에 `pgvector_extension`, `vector_tables_rls_enabled`, `vector_rpc_available`, `vector_indexes_present` 추가

보안 기준:
- browser는 vector tables 직접 접근 금지
- service role/DB URL은 backend only
- admin health는 count/status만 표시, SQL/secret 노출 금지

### Phase 2. Ingestion pipeline 추가

목표: 기존 Chroma indexer와 동일한 소스 문서를 Postgres pgvector에 적재한다.

작업:
- `features/search/indexer.py`에 `build_pgvector_store()` 추가
- 기존 splitter와 metadata를 재사용
- `content_hash` 기반 idempotent upsert
- batch embedding: Ollama `bge-m3`
- `document_chunks` upsert 후 `document_embeddings` upsert
- `employee_embeddings` upsert용 `index_employee_one_pgvector()` 추가
- `rag_chunks` 공통 upsert helper 추가

주의:
- embedding model 혼용 금지
- Chroma id와 Postgres chunk id mapping을 report에 남긴다
- 삭제는 바로 하지 않고 `is_active` 또는 source inventory로 stale 감지부터 한다

### Phase 3. Query adapter

목표: `/api/search/documents`, employee semantic search, RAG 검색이 pgvector를 읽을 수 있게 한다.

작업:
- `SupabaseVectorStore.search_documents()`
- `SupabaseVectorStore.hybrid_search_documents()`
- `SupabaseVectorStore.search_employees()`
- `SupabaseVectorStore.search_rag(collection_key, query, filters)`
- `HybridSearcher`는 Chroma 직접 import 대신 adapter를 받도록 변경
- `features/search/employee/semantic_search.py`는 Chroma 함수와 pgvector 함수를 나란히 제공하고 flag로 선택
- `features/draft/fewshot_rag.py`, `features/equipment/manual_rag.py`, compliance indexers는 공통 `rag_chunks` adapter로 이동

완료 기준:
- 기존 API response schema 유지
- 검색 결과 개수/metadata/title/content 필드 유지
- Chroma 미설치 slim runtime에서도 Postgres vector search 가능

### Phase 4. Dual-run consistency gate

목표: Chroma와 pgvector 검색 품질/coverage 차이를 수치화한다.

작업:
- `scripts/verify_pgvector_consistency.py` 추가
  - Chroma collection count vs Postgres row count
  - sample query top-k overlap
  - required metadata coverage
  - embedding_dim/model consistency
  - employee real active coverage
  - RAG collection coverage
- `make pgvector-consistency-check`
- `make pgvector-reindex`
- `make pgvector-release-check`

권장 query set:
- 직원: `프레스 금형 담당자`, `IT전략팀`, `품질팀 관리자`
- 문서: `8D 고객 불만`, `ECN 변경 승인`, `프레스 안전거리`
- Compliance: `산업안전보건법 프레스`, `REACH SVHC`, `WP.29 R100`
- Equipment: `CNC 마모`, `금형 점검`, `Nelson Rule`

통과 기준:
- row coverage 100%
- embedding_dim mismatch 0
- required metadata missing 0
- top-k overlap은 초기에는 warn, release 전 threshold 확정

### Phase 5. Read primary 전환

목표: `VECTOR_READ_MODE=postgres`로 전환한다.

작업:
- Docker/local env:
  - `VECTOR_BACKEND=postgres`
  - `VECTOR_READ_MODE=postgres`
  - `VECTOR_WRITE_MODE=dual` 또는 `postgres`
- Cloud Run:
  - backend-only Supabase DB URL/service role 유지
  - Chroma/vectorstore volume 또는 baked files 의존 제거
- `/api/health`:
  - `chroma_connected` 중심에서 `vector_backend=postgres`, `pgvector.ok`, `document_chunks`, `employee_embeddings`, `rag_chunks`로 교체
- dashboard DATABASES:
  - `ChromaDB` 대신 `Supabase pgvector`

완료 기준:
- `npm run build`
- 지정 pytest
- `make openapi-docs-check`
- `make pgvector-release-check`
- `make supabase-release-check`
- 주요 화면 route smoke

### Phase 6. Chroma 제거

목표: ChromaDB runtime dependency와 vectorstore artifact를 release path에서 제거한다.

작업:
- Chroma fallback flag를 deprecated 처리
- `langchain_chroma`, `chromadb` import 제거 또는 dev-only로 이동
- `vectorstore/` baked copy 제거
- `scripts/sync_vectorstore_gcs.py` 폐기 또는 legacy archive
- Feature A consistency gate를 `SQLite/Postgres/pgvector/FTS` 기준으로 재정의
- 문서에서 “ChromaDB” 표기를 “Supabase pgvector”로 정리

## 7. RLS 및 운영 보안

Vector table은 검색용이라고 해도 실제 직원, 문서, 계약, 법규, 설비 매뉴얼 텍스트가 들어간다. public schema에 둘 경우 RLS는 반드시 켠다.

권장:
- `public.document_chunks`, `public.document_embeddings`, `public.employee_embeddings`, `public.rag_chunks`: RLS enabled
- `anon`, `authenticated` 직접 access deny
- Backend는 service role 또는 private DB connection으로만 접근
- RPC 함수는 가능하면 backend-only DB connection으로 호출
- 만약 Data API RPC를 노출해야 한다면:
  - `security definer`를 public exposed schema에 두지 않는다.
  - 별도 private schema 사용 또는 명확한 RLS/policy 검토 필요
  - admin/user별 department boundary는 SQL 함수 내부와 backend 모두에서 이중 적용

주의:
- Supabase Data API 설정 변경으로 SQL-created table이 자동 노출되지 않을 수 있다. 이 동작을 release gate에 포함해야 한다.
- `service_role`, `SUPABASE_SECRET_KEY`, raw DB URL은 frontend/Vercel public env에 절대 두지 않는다.

## 8. 테스트 계획

신규 테스트:
- `tests/test_pgvector_store.py`
  - embedding dim mismatch fail
  - content_hash idempotent upsert
  - RPC payload schema
  - filter mapping
- `tests/test_pgvector_consistency.py`
  - Chroma fixture vs Postgres fixture count mismatch
  - top-k overlap report
  - employee real active coverage
- `tests/test_search_pgvector_adapter.py`
  - `/api/search/documents` response schema 유지
  - vector backend down 시 503 또는 controlled fallback
- `tests/test_release_security.py` 확장
  - frontend에 Supabase secret/DB URL/vector table secret 노출 없음

명령:

```bash
.venv/bin/python -m pytest \
  tests/test_pgvector_store.py \
  tests/test_pgvector_consistency.py \
  tests/test_search_pgvector_adapter.py \
  tests/test_runtime_feature_guards.py -q

make pgvector-release-check
make supabase-release-check
make openapi-docs-check
cd frontend && npm run build
git diff --check
```

## 9. 리스크와 대응

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| embedding dimension 불일치 | 검색 결과 무의미 | `embedding_dim`, `embedding_model`, `embedding_version` 저장 및 gate fail |
| Postgres vector index tuning 미흡 | 검색 지연 | HNSW 기본, query latency report, 필요 시 IVFFlat 튜닝 |
| Chroma와 Postgres 결과 차이 | 사용자 검색 품질 흔들림 | dual-run overlap report 후 read 전환 |
| RLS/Data API 설정 오류 | 민감 문서 노출 | deny-by-default, release-security-check 확장 |
| 대량 reindex 중 timeout | 전환 지연 | batch size, checkpoint table, resumable ingestion |
| 한국어 FTS 품질 | BM25 대비 품질 저하 가능 | 초기에는 Python BM25 유지, 이후 pgroonga/한국어 tokenizer 검토 |
| Cloud Run startup 비용 | boot 지연 | startup reindex 금지, 별도 job/script로만 인덱싱 |

## 10. 권장 우선순위

1. `pgvector` extension + schema/RPC migration 작성
2. `scripts/verify_pgvector_prereq.py`와 `make pgvector-release-check` 추가
3. Feature A 문서 검색만 먼저 dual-write/read 비교
4. 직원 `employee_embeddings` 전환
5. Draft/Compliance/Equipment RAG를 `rag_chunks` 공통 테이블로 통합
6. Dashboard/health의 Chroma 표시를 Supabase pgvector 표시로 교체
7. Chroma dependency와 `vectorstore/` runtime artifact 제거

## 11. 완료 정의

Supabase pgvector 전환 완료는 다음을 모두 만족해야 한다.

- ChromaDB 없이 backend가 기동된다.
- `/api/health/llm-status`와 `/api/health`가 pgvector 상태를 표시한다.
- `/api/search/documents`, employee search, Draft few-shot, Compliance RAG, Equipment manual RAG가 Postgres vector RPC를 사용한다.
- `make pgvector-release-check`와 `make supabase-release-check`가 통과한다.
- RLS/advisor/release-security-check에서 vector tables 관련 warn/error가 없다.
- frontend DATABASES 카드가 `ChromaDB`가 아니라 `Supabase pgvector`를 표시한다.
