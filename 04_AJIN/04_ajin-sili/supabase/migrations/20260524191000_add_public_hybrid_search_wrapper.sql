-- 0005 - Public wrapper for private.hybrid_search_document_chunks
--
-- Background:
--   PostgREST (Supabase REST API) only exposes `public` and `graphql_public`
--   schemas by default. The actual hybrid search function lives in `private.`
--   to prevent direct anonymous access. demo_check.py and frontend cannot
--   call private.* via supabase-py RPC (PGRST106 "Invalid schema: private").
--
-- Design:
--   - SECURITY DEFINER wrapper in public.* — runs with the function owner's
--     privileges (postgres), so it can read private.* even though the caller
--     (service_role / authenticated) cannot reach private directly.
--   - EXECUTE granted to service_role and authenticated only — anon is excluded
--     to keep the RAG corpus gated behind auth.
--   - search_path = '' for safety (Supabase advisor 0011).
--
-- Resolves: PGRST106 for demo C1 + makes frontend hybrid search callable.

create or replace function public.hybrid_search_document_chunks(
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
security definer
set search_path = ''
as $$
  select
    chunk_id, source_doc_id, title, content, metadata,
    score, vector_similarity, keyword_score
  from private.hybrid_search_document_chunks(
    query_text, query_embedding, match_count,
    doc_type_filter, part_name_filter, metadata_filter
  );
$$;

revoke all on function public.hybrid_search_document_chunks(
  text, extensions.vector, integer, text, text, jsonb
) from public;

grant execute on function public.hybrid_search_document_chunks(
  text, extensions.vector, integer, text, text, jsonb
) to service_role, authenticated;

comment on function public.hybrid_search_document_chunks(
  text, extensions.vector, integer, text, text, jsonb
) is
  'SECURITY DEFINER wrapper for private.hybrid_search_document_chunks. Exposes RAG search to authenticated and service_role roles via PostgREST.';
