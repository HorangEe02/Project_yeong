-- 0006 - Fix search_path for pgvector private RPC functions.
--
-- Background:
--   Migration 20260520171146 set search_path = '' on private.* RAG functions
--   to satisfy linter 0011 (mutable search_path). But the function bodies use
--   the `<=>` cosine-distance operator (defined in `extensions` schema), so
--   resolution fails at runtime:
--     ERROR 42883: operator does not exist: extensions.vector <=> extensions.vector
--
-- Design:
--   - Set search_path = 'extensions, public' explicitly. Still immutable from
--     role/session perspective (lint 0011 still satisfied), but the operator
--     lookup succeeds because `extensions` is on the path.
--   - Apply to all four private.* RAG functions identically.
--
-- Resolves: C1 demo_check failure + frontend hybrid search at runtime.

alter function private.match_document_chunks(
  extensions.vector,
  integer,
  double precision,
  text,
  text,
  jsonb
) set search_path = 'extensions, public';

alter function private.hybrid_search_document_chunks(
  text,
  extensions.vector,
  integer,
  text,
  text,
  jsonb
) set search_path = 'extensions, public';

alter function private.match_employee_profiles(
  extensions.vector,
  integer,
  text,
  jsonb
) set search_path = 'extensions, public';

alter function private.match_rag_chunks(
  extensions.vector,
  integer,
  text,
  jsonb
) set search_path = 'extensions, public';

comment on function private.hybrid_search_document_chunks(
  text, extensions.vector, integer, text, text, jsonb
) is
  'BM25 + pgvector cosine hybrid search via RRF. search_path includes extensions for <=> operator resolution.';
