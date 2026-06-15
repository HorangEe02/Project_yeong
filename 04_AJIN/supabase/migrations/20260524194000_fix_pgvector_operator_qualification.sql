-- 0008 - Fix pgvector private functions: use OPERATOR(extensions.<=>) explicitly.
--
-- Background:
--   Despite setting search_path = 'extensions, public' on the private RAG
--   functions, the `<=>` operator resolution still fails at runtime with:
--     ERROR 42883: operator does not exist: extensions.vector <=> extensions.vector
--
--   Root cause: when a SECURITY DEFINER public wrapper invokes a SQL function
--   in `private.*`, the planner may inline the called function into the
--   caller's context. The caller's session (PostgREST request) does not have
--   `extensions` on its effective search_path even though the function's own
--   `proconfig` says so — Postgres resolves the operator at parse time of the
--   outer query, not based on the inner function's search_path.
--
-- Design:
--   - Explicitly qualify the `<=>` operator as `OPERATOR(extensions.<=>)`
--     everywhere it appears in the function bodies. This is search_path-
--     independent and immune to inlining.
--   - Recreate the two affected functions: private.match_document_chunks and
--     private.hybrid_search_document_chunks. Other private.* functions
--     (match_employee_profiles, match_rag_chunks) follow the same pattern but
--     are out of scope for the C1 demo path; can be patched later if needed.
--
-- Resolves: C1 demo_check + production RAG search at runtime.

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
set search_path = 'extensions, public'
as $$
  select
    dc.id,
    dc.source_doc_id,
    dc.title,
    dc.content,
    dc.metadata,
    (1 - (de.embedding OPERATOR(extensions.<=>) query_embedding))::double precision as similarity
  from public.document_embeddings de
  join public.document_chunks dc on dc.id = de.chunk_id
  where (doc_type_filter is null or dc.doc_type = doc_type_filter)
    and (part_name_filter is null or dc.part_name = part_name_filter)
    and dc.metadata @> coalesce(metadata_filter, '{}'::jsonb)
    and (1 - (de.embedding OPERATOR(extensions.<=>) query_embedding)) >= match_threshold
  order by de.embedding OPERATOR(extensions.<=>) query_embedding
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
set search_path = 'extensions, public'
as $$
  with vector_matches as (
    select
      dc.id as chunk_id,
      dc.source_doc_id,
      dc.title,
      dc.content,
      dc.metadata,
      (1 - (de.embedding OPERATOR(extensions.<=>) query_embedding))::double precision as vector_similarity,
      0::double precision as keyword_score,
      row_number() over (order by de.embedding OPERATOR(extensions.<=>) query_embedding) as rank_ix
    from public.document_embeddings de
    join public.document_chunks dc on dc.id = de.chunk_id
    where (doc_type_filter is null or dc.doc_type = doc_type_filter)
      and (part_name_filter is null or dc.part_name = part_name_filter)
      and dc.metadata @> coalesce(metadata_filter, '{}'::jsonb)
    order by de.embedding OPERATOR(extensions.<=>) query_embedding
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

comment on function private.hybrid_search_document_chunks(
  text, extensions.vector, integer, text, text, jsonb
) is
  'BM25 + pgvector cosine hybrid search via RRF. Uses OPERATOR(extensions.<=>) explicitly to bypass search_path / inlining resolution issues.';
