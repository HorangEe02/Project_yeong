-- Fix Supabase database linter WARN 0011 for private pgvector RPC functions.
-- Function bodies use schema-qualified table/type references; an empty
-- search_path removes role-mutable name resolution from the execution context.

alter function private.match_document_chunks(
  extensions.vector,
  integer,
  double precision,
  text,
  text,
  jsonb
) set search_path = '';

alter function private.hybrid_search_document_chunks(
  text,
  extensions.vector,
  integer,
  text,
  text,
  jsonb
) set search_path = '';

alter function private.match_employee_profiles(
  extensions.vector,
  integer,
  text,
  jsonb
) set search_path = '';

alter function private.match_rag_chunks(
  extensions.vector,
  integer,
  text,
  jsonb
) set search_path = '';
