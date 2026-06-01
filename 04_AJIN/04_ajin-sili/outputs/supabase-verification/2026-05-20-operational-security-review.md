# Operational Security Review - Supabase Cutover

## Verdict

- Release security guard: PASS (`4 pass / 0 fail / 0 skip`).
- Supabase secret/service-role/DB URL boundary: backend-only.
- Browser-visible frontend source and built `dist`: no backend-only Supabase secret markers found.
- Cloud Run runtime mapping: deploy-local values are absent and secret env vars are Secret Manager-backed.
- Admin health output: status-only posture, Firebase fallback disabled, no raw secret fields observed.

## Official Basis

- Supabase API keys: https://supabase.com/docs/guides/getting-started/api-keys
- Supabase RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase API security / exposed schema: https://supabase.com/docs/guides/api/securing-your-api
- Supabase changelog: https://supabase.com/changelog

Supabase documents `sb_publishable_...` as public-client appropriate and `sb_secret_...` / legacy `service_role` as backend-only elevated access that bypasses RLS. Supabase also states that RLS must be enabled on tables in exposed schemas, with `public` exposed by default.

## Current Guardrails

| Area | Current control | Release posture |
| --- | --- | --- |
| Frontend bundle | `scripts/verify_release_security.py` scans `frontend/src`, `frontend/api`, frontend env files, `.vercel`, and `frontend/dist` for backend-only Supabase/DB markers. | PASS |
| Supabase RLS/Data API | `make supabase-release-check` and `release-security-check` require RLS, sensitive grants, deny policies, and default admin posture to pass. | PASS |
| Cloud Run secrets | `DATABASE_URL`, `SUPABASE_SECRET_KEY`, and `AJIN_JWT_SECRET` must use Secret Manager refs; `SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD`, and `SMOKE_ADMIN_JWT` must not exist in runtime env. | PASS |
| Admin health | Health output must expose booleans/status only and confirm `FIREBASE_WRITE_ENABLED=false`, `FIREBASE_READ_FALLBACK_ENABLED=false`. | PASS |
| Storage | Private buckets plus signed URL owner/admin allow and other-user deny remain part of the Supabase release gate. | PASS |

## Operating Checklist

1. Keep `SUPABASE_SECRET_KEY`, `service_role`, and raw DB URLs out of all browser-visible Vite env vars and frontend bundles.
2. Keep deploy-local credentials (`SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD`, `SMOKE_ADMIN_JWT`) out of Cloud Run runtime.
3. Treat any RLS disabled table, sensitive table public grant, unsafe policy, or exposed-schema table without RLS as a Firebase-removal blocker.
4. Keep smoke JWT TTL at 60 minutes or less and mint from gitignored secret files only.
5. Keep admin health secret-safe: no raw key, token, password, or DSN fields.
6. Re-run `make release-security-check`, `make supabase-release-check`, `npm audit --audit-level=moderate`, `npm run build`, and browser route smoke before promotion.

## Brainstormed Follow-ups

- Add the `release-security-check` target to CI after the Supabase env/secret injection story is stable.
- Store Cloud Run service JSON and admin health JSON only as redacted artifacts or ephemeral `/tmp` files; do not commit raw service descriptions by default.
- Add a small frontend CI guard that fails on `VITE_SUPABASE_SECRET*`, `VITE_DATABASE_URL`, and `service_role` before Vite build.
- Add periodic Supabase advisor monitoring, especially after migrations or exposed schema changes.
- For future authenticated SSE, prefer cookie-backed or backend-issued stream sessions instead of putting bearer tokens into EventSource URLs.

## Residual Non-blocking Items

- Supabase CLI still reports `2.100.1` available, but Homebrew `brew upgrade supabase` reports `2.98.2` already installed and `brew outdated supabase` returns no outdated formula.
- Docker frontend build emits an npm major-version notice (`10.8.2 -> 11.14.1`); this is not part of the Firebase/Supabase release gate.
- Broad dependency modernization from `npm outdated` remains a separate maintenance task, not a cutover blocker.
