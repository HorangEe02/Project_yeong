-- 0003 - Lock down public.alembic_version RLS: explicit deny for anon and authenticated.
--
-- Background:
--   `public.alembic_version` is Alembic migration metadata. RLS was enabled but
--   no policies existed. Supabase database linter reports advisor INFO
--   "0008_rls_enabled_no_policy" because policy intent is ambiguous.
--
-- Design:
--   - service_role bypasses RLS entirely (Supabase docs). The Alembic CLI uses
--     service_role / postgres so it keeps full access.
--   - anon and authenticated roles must never read or write migration metadata.
--   - Use `as restrictive` so this policy AND-combines with any future policy.
--
-- Resolves: Supabase advisor `0008_rls_enabled_no_policy` for alembic_version.

create policy "alembic_version_no_client_access"
  on public.alembic_version
  as restrictive
  for all
  to anon, authenticated
  using (false)
  with check (false);

comment on policy "alembic_version_no_client_access" on public.alembic_version is
  'Block anon and authenticated roles from alembic_version. service_role bypasses RLS for migrations. (resolves linter 0008_rls_enabled_no_policy)';
