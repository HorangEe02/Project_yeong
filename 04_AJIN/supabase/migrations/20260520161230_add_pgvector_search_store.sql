-- AJIN Supabase pgvector store.
--
-- The application still owns authorization in the backend. These tables stay in
-- public so operations can be inspected with Supabase tooling, but browser
-- roles receive no grants and RLS denies direct client access.

create extension if not exists vector with schema extensions;
create extension if not exists pgcrypto with schema extensions;

create schema if not exists private;
revoke all on schema private from public;
revoke all on schema private from anon;
revoke all on schema private from authenticated;
grant usage on schema private to postgres;
grant usage on schema private to service_role;

create table if not exists public.document_chunks (
  id uuid primary key default gen_random_uuid(),
  source_doc_id text not null,
  source_path text,
  title text,
  doc_type text,
  part_name text,
  chunk_index integer not null default 0,
  content text not null,
  content_hash text not null,
  metadata jsonb not null default '{}'::jsonb,
  data_class text not null default 'real',
  content_tsv tsvector generated always as (
    to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, ''))
  ) stored,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint document_chunks_embedding_source_unique unique (source_doc_id, chunk_index),
  constraint document_chunks_content_not_blank check (length(btrim(content)) > 0)
);

create table if not exists public.document_embeddings (
  chunk_id uuid primary key references public.document_chunks(id) on delete cascade,
  embedding extensions.vector(1024) not null,
  embedding_model text not null default 'bge-m3',
  embedding_dim integer not null default 1024,
  embedding_version text not null default 'v1',
  embedded_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  constraint document_embeddings_dim_check check (embedding_dim = 1024)
);

create table if not exists public.employee_embeddings (
  employee_id text primary key,
  display_name text not null,
  department text,
  position text,
  profile_text text not null,
  profile_tsv tsvector generated always as (
    to_tsvector(
      'simple',
      coalesce(display_name, '') || ' ' ||
      coalesce(department, '') || ' ' ||
      coalesce(position, '') || ' ' ||
      coalesce(profile_text, '')
    )
  ) stored,
  embedding extensions.vector(1024) not null,
  embedding_model text not null default 'bge-m3',
  embedding_dim integer not null default 1024,
  embedding_version text not null default 'v1',
  metadata jsonb not null default '{}'::jsonb,
  data_class text not null default 'real',
  is_active boolean not null default true,
  embedded_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint employee_embeddings_dim_check check (embedding_dim = 1024),
  constraint employee_embeddings_profile_not_blank check (length(btrim(profile_text)) > 0)
);

create table if not exists public.rag_collections (
  collection_id text primary key,
  feature_key text not null,
  display_name text not null,
  source_path text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.rag_chunks (
  id uuid primary key default gen_random_uuid(),
  collection_id text not null references public.rag_collections(collection_id) on delete cascade,
  source_item_id text,
  chunk_index integer not null default 0,
  content text not null,
  content_hash text not null,
  metadata jsonb not null default '{}'::jsonb,
  content_tsv tsvector generated always as (
    to_tsvector('simple', coalesce(content, ''))
  ) stored,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint rag_chunks_source_unique unique (collection_id, source_item_id, chunk_index),
  constraint rag_chunks_content_not_blank check (length(btrim(content)) > 0)
);

create table if not exists public.rag_chunk_embeddings (
  chunk_id uuid primary key references public.rag_chunks(id) on delete cascade,
  embedding extensions.vector(1024) not null,
  embedding_model text not null default 'bge-m3',
  embedding_dim integer not null default 1024,
  embedding_version text not null default 'v1',
  embedded_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  constraint rag_chunk_embeddings_dim_check check (embedding_dim = 1024)
);

create index if not exists document_chunks_content_tsv_idx
  on public.document_chunks using gin (content_tsv);
create index if not exists document_chunks_metadata_idx
  on public.document_chunks using gin (metadata jsonb_path_ops);
create index if not exists document_chunks_doc_type_idx
  on public.document_chunks (doc_type);
create index if not exists document_chunks_part_name_idx
  on public.document_chunks (part_name);
create index if not exists document_embeddings_hnsw_idx
  on public.document_embeddings using hnsw (embedding vector_cosine_ops);

create index if not exists employee_embeddings_profile_tsv_idx
  on public.employee_embeddings using gin (profile_tsv);
create index if not exists employee_embeddings_department_idx
  on public.employee_embeddings (department);
create index if not exists employee_embeddings_hnsw_idx
  on public.employee_embeddings using hnsw (embedding vector_cosine_ops);

create index if not exists rag_collections_feature_key_idx
  on public.rag_collections (feature_key);
create index if not exists rag_chunks_collection_idx
  on public.rag_chunks (collection_id);
create index if not exists rag_chunks_content_tsv_idx
  on public.rag_chunks using gin (content_tsv);
create index if not exists rag_chunks_metadata_idx
  on public.rag_chunks using gin (metadata jsonb_path_ops);
create index if not exists rag_chunk_embeddings_hnsw_idx
  on public.rag_chunk_embeddings using hnsw (embedding vector_cosine_ops);

alter table public.document_chunks enable row level security;
alter table public.document_embeddings enable row level security;
alter table public.employee_embeddings enable row level security;
alter table public.rag_collections enable row level security;
alter table public.rag_chunks enable row level security;
alter table public.rag_chunk_embeddings enable row level security;

revoke all on table public.document_chunks from anon, authenticated;
revoke all on table public.document_embeddings from anon, authenticated;
revoke all on table public.employee_embeddings from anon, authenticated;
revoke all on table public.rag_collections from anon, authenticated;
revoke all on table public.rag_chunks from anon, authenticated;
revoke all on table public.rag_chunk_embeddings from anon, authenticated;
grant select, insert, update, delete on table public.document_chunks to service_role;
grant select, insert, update, delete on table public.document_embeddings to service_role;
grant select, insert, update, delete on table public.employee_embeddings to service_role;
grant select, insert, update, delete on table public.rag_collections to service_role;
grant select, insert, update, delete on table public.rag_chunks to service_role;
grant select, insert, update, delete on table public.rag_chunk_embeddings to service_role;

drop policy if exists document_chunks_no_client_access on public.document_chunks;
create policy document_chunks_no_client_access
  on public.document_chunks
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

drop policy if exists document_embeddings_no_client_access on public.document_embeddings;
create policy document_embeddings_no_client_access
  on public.document_embeddings
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

drop policy if exists employee_embeddings_no_client_access on public.employee_embeddings;
create policy employee_embeddings_no_client_access
  on public.employee_embeddings
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

drop policy if exists rag_collections_no_client_access on public.rag_collections;
create policy rag_collections_no_client_access
  on public.rag_collections
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

drop policy if exists rag_chunks_no_client_access on public.rag_chunks;
create policy rag_chunks_no_client_access
  on public.rag_chunks
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

drop policy if exists rag_chunk_embeddings_no_client_access on public.rag_chunk_embeddings;
create policy rag_chunk_embeddings_no_client_access
  on public.rag_chunk_embeddings
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

create or replace function private.match_document_chunks(
  query_embedding extensions.vector(1024),
  match_count integer default 10,
  match_threshold double precision default 0,
  doc_type_filter text default null,
  part_name_filter text default null,
  metadata_filter jsonb default '{}'::jsonb
)
returns table (
  chunk_id uuid,
  source_doc_id text,
  title text,
  content text,
  metadata jsonb,
  similarity double precision
)
language sql
stable
as $$
  select
    dc.id,
    dc.source_doc_id,
    dc.title,
    dc.content,
    dc.metadata,
    (1 - (de.embedding <=> query_embedding))::double precision as similarity
  from public.document_embeddings de
  join public.document_chunks dc on dc.id = de.chunk_id
  where (doc_type_filter is null or dc.doc_type = doc_type_filter)
    and (part_name_filter is null or dc.part_name = part_name_filter)
    and dc.metadata @> coalesce(metadata_filter, '{}'::jsonb)
    and (1 - (de.embedding <=> query_embedding)) >= match_threshold
  order by de.embedding <=> query_embedding
  limit greatest(1, least(coalesce(match_count, 10), 100));
$$;

create or replace function private.hybrid_search_document_chunks(
  query_text text,
  query_embedding extensions.vector(1024),
  match_count integer default 10,
  doc_type_filter text default null,
  part_name_filter text default null,
  metadata_filter jsonb default '{}'::jsonb
)
returns table (
  chunk_id uuid,
  source_doc_id text,
  title text,
  content text,
  metadata jsonb,
  score double precision,
  vector_similarity double precision,
  keyword_score double precision
)
language sql
stable
as $$
  with vector_matches as (
    select
      dc.id as chunk_id,
      dc.source_doc_id,
      dc.title,
      dc.content,
      dc.metadata,
      (1 - (de.embedding <=> query_embedding))::double precision as vector_similarity,
      0::double precision as keyword_score,
      row_number() over (order by de.embedding <=> query_embedding) as rank_ix
    from public.document_embeddings de
    join public.document_chunks dc on dc.id = de.chunk_id
    where (doc_type_filter is null or dc.doc_type = doc_type_filter)
      and (part_name_filter is null or dc.part_name = part_name_filter)
      and dc.metadata @> coalesce(metadata_filter, '{}'::jsonb)
    order by de.embedding <=> query_embedding
    limit greatest(1, least(coalesce(match_count, 10), 100)) * 4
  ),
  keyword_matches as (
    select
      dc.id as chunk_id,
      dc.source_doc_id,
      dc.title,
      dc.content,
      dc.metadata,
      0::double precision as vector_similarity,
      ts_rank_cd(dc.content_tsv, websearch_to_tsquery('simple', query_text))::double precision as keyword_score,
      row_number() over (
        order by ts_rank_cd(dc.content_tsv, websearch_to_tsquery('simple', query_text)) desc
      ) as rank_ix
    from public.document_chunks dc
    where query_text is not null
      and btrim(query_text) <> ''
      and dc.content_tsv @@ websearch_to_tsquery('simple', query_text)
      and (doc_type_filter is null or dc.doc_type = doc_type_filter)
      and (part_name_filter is null or dc.part_name = part_name_filter)
      and dc.metadata @> coalesce(metadata_filter, '{}'::jsonb)
    order by keyword_score desc
    limit greatest(1, least(coalesce(match_count, 10), 100)) * 4
  ),
  combined as (
    select
      *,
      (0.70 / (60 + rank_ix))::double precision as contribution
    from vector_matches
    union all
    select
      *,
      (0.30 / (60 + rank_ix))::double precision as contribution
    from keyword_matches
  )
  select
    chunk_id,
    source_doc_id,
    title,
    content,
    metadata,
    sum(contribution)::double precision as score,
    max(vector_similarity)::double precision as vector_similarity,
    max(keyword_score)::double precision as keyword_score
  from combined
  group by chunk_id, source_doc_id, title, content, metadata
  order by score desc
  limit greatest(1, least(coalesce(match_count, 10), 100));
$$;

create or replace function private.match_employee_profiles(
  query_embedding extensions.vector(1024),
  match_count integer default 10,
  department_filter text default null,
  metadata_filter jsonb default '{}'::jsonb
)
returns table (
  employee_id text,
  display_name text,
  department text,
  employee_position text,
  profile_text text,
  metadata jsonb,
  similarity double precision
)
language sql
stable
as $$
  select
    ee.employee_id,
    ee.display_name,
    ee.department,
    ee.position,
    ee.profile_text,
    ee.metadata,
    (1 - (ee.embedding <=> query_embedding))::double precision as similarity
  from public.employee_embeddings ee
  where ee.is_active = true
    and (department_filter is null or ee.department = department_filter)
    and ee.metadata @> coalesce(metadata_filter, '{}'::jsonb)
  order by ee.embedding <=> query_embedding
  limit greatest(1, least(coalesce(match_count, 10), 100));
$$;

create or replace function private.match_rag_chunks(
  query_embedding extensions.vector(1024),
  match_count integer default 10,
  collection_filter text default null,
  metadata_filter jsonb default '{}'::jsonb
)
returns table (
  chunk_id uuid,
  collection_id text,
  source_item_id text,
  content text,
  metadata jsonb,
  similarity double precision
)
language sql
stable
as $$
  select
    rc.id,
    rc.collection_id,
    rc.source_item_id,
    rc.content,
    rc.metadata,
    (1 - (rce.embedding <=> query_embedding))::double precision as similarity
  from public.rag_chunk_embeddings rce
  join public.rag_chunks rc on rc.id = rce.chunk_id
  where (collection_filter is null or rc.collection_id = collection_filter)
    and rc.metadata @> coalesce(metadata_filter, '{}'::jsonb)
  order by rce.embedding <=> query_embedding
  limit greatest(1, least(coalesce(match_count, 10), 100));
$$;

revoke all on all functions in schema private from public, anon, authenticated;
grant execute on all functions in schema private to service_role;
