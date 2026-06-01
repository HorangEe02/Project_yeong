-- 0004 - Restore service_role schema USAGE + DML grants on public schema.
--
-- Background:
--   The new Supabase API key system (sb_secret_*) maps to the service_role
--   PostgreSQL role. By default service_role bypasses RLS but still requires
--   explicit GRANT on schema USAGE + DML on tables/sequences/functions.
--
--   The seed scripts return `permission denied for schema public (42501)`,
--   indicating service_role lost (or never received) USAGE on schema public.
--
-- Design:
--   - Re-grant USAGE, SELECT/INSERT/UPDATE/DELETE/REFERENCES/TRIGGER on tables,
--     USAGE/SELECT/UPDATE on sequences, EXECUTE on functions to service_role.
--   - ALTER DEFAULT PRIVILEGES so future tables/sequences/functions inherit.
--   - Idempotent: GRANT is additive; running twice is safe.
--
-- Resolves: 42501 "permission denied for schema public" for seed scripts.

grant usage on schema public to service_role;
grant usage on schema private to service_role;
grant usage on schema extensions to service_role;

grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;
grant execute on all functions in schema public to service_role;
grant execute on all functions in schema private to service_role;

alter default privileges in schema public grant all on tables to service_role;
alter default privileges in schema public grant all on sequences to service_role;
alter default privileges in schema public grant execute on functions to service_role;
alter default privileges in schema private grant execute on functions to service_role;

comment on schema public is
  'Standard public schema. service_role has USAGE + DML; anon/authenticated use RLS policies.';
