-- 0007 - Fix public.hybrid_search_document_chunks wrapper search_path.
--
-- Background:
--   Migration 0005 created the wrapper with `set search_path = ''`. PostgreSQL
--   SQL functions (LANGUAGE sql) marked STABLE may be inlined by the planner,
--   which means the wrapper's search_path propagates to the inlined body — and
--   the inner `private.hybrid_search_document_chunks` operator resolution
--   (`<=>` from extensions schema) fails:
--     ERROR 42883: operator does not exist: extensions.vector <=> extensions.vector
--
-- Design:
--   - Switch wrapper search_path to 'extensions, public, private' so that
--     (a) the `<=>` operator resolves, and (b) the unqualified `private.*`
--     function call works regardless of inlining behavior.
--   - The wrapper still uses SECURITY DEFINER so callers cannot access private
--     directly; only the wrapper's pre-baked call path is exposed.
--   - Includes `private` on the path since SECURITY DEFINER + STABLE SQL may
--     be inlined into the caller's context.
--
-- Resolves: C1 demo_check failure + frontend hybrid search at runtime.

alter function public.hybrid_search_document_chunks(
  text,
  extensions.vector,
  integer,
  text,
  text,
  jsonb
) set search_path = 'extensions, public, private';

comment on function public.hybrid_search_document_chunks(
  text, extensions.vector, integer, text, text, jsonb
) is
  'SECURITY DEFINER wrapper for private.hybrid_search_document_chunks. search_path includes extensions (for <=>) + private (for inlined SQL function call).';
