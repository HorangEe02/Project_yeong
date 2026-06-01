-- 0009 - Public RPC: count public table RLS coverage
--
-- Background:
--   demo_check.py D3 needs RLS coverage stats but PostgREST blocks direct
--   pg_catalog access from anon/authenticated/service_role for safety.
--   Wrap the aggregate query in a SECURITY DEFINER public RPC that returns
--   only counts (no table names, no row data) — zero information leakage.
--
-- Design:
--   - SECURITY DEFINER + set search_path = '' (lint 0011 compliant)
--   - Returns 2 ints: rls_enabled, total_tables
--   - EXECUTE granted to service_role + authenticated only (anon excluded)
--
-- Resolves: demo_check.py D3 "자동 확인 불가" WARN → automatic PASS gate.

create or replace function public.count_rls_tables()
returns table (rls_enabled int, total_tables int)
language sql
stable
security definer
set search_path = ''
as $$
  select
    count(*) filter (where c.relrowsecurity = true)::int as rls_enabled,
    count(*)::int as total_tables
  from pg_catalog.pg_tables t
  join pg_catalog.pg_class c on c.relname = t.tablename
  join pg_catalog.pg_namespace n on n.oid = c.relnamespace
    and n.nspname = t.schemaname
  where t.schemaname = 'public'
    and t.tablename not like 'pg_%'
    and t.tablename not like 'sql_%';
$$;

revoke all on function public.count_rls_tables() from public;
grant execute on function public.count_rls_tables() to service_role, authenticated;

comment on function public.count_rls_tables() is
  'RLS coverage aggregate (enabled, total) for public schema. Used by demo_check.py D3 verification.';
