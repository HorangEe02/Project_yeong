# Firebase Removal Gate Verification - 2026-05-20

## Verdict

- Supabase release gate: PASS.
- RLS/Data API/advisor: PASS, no unresolved warn/error.
- Local Storage signed URL permissions: PASS.
- Cloud Run no-traffic tag Storage/Admin smoke: PASS after refreshing the short-lived smoke JWT.
- Firebase complete removal decision: initial HOLD was for app-smoke cleanup only; the four named warnings were remediated or converted into explicit release-smoke policy in the follow-up section below.

The Supabase backend gate itself is green. Production promotion still requires the normal final route smoke on the target revision, but RLS/advisor, Storage authorization, and fallback-off runtime posture are not blocking.

## Official References

- Supabase RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase CLI `db push --dry-run`: https://supabase.com/docs/reference/cli/supabase-db-push
- Supabase Storage access control: https://supabase.com/docs/guides/storage/security/access-control
- Supabase Python signed upload URL: https://supabase.com/docs/reference/python/storage-from-createsigneduploadurl
- Supabase JavaScript signed URL upload: https://supabase.com/docs/reference/javascript/storage-from-uploadtosignedurl
- Supabase changelog: https://supabase.com/changelog

## Environment Posture

- Project ref: `ycjuzwltwbeudanjykag`.
- Runtime DB: `APP_DB_BACKEND=postgres`.
- Firebase writes: `FIREBASE_WRITE_ENABLED=false`.
- Firebase read fallback: `FIREBASE_READ_FALLBACK_ENABLED=false`.
- Supabase CLI: `2.98.2`; official update notice reported `2.100.1` available.
- Secrets were not printed. Smoke JWT was read/minted from gitignored local secret files only.

## Automated Gates

| Gate | Result | Evidence |
| --- | --- | --- |
| `set -a; source .env.supabase.local; set +a; make supabase-release-check` | PASS | `Supabase remote verification: pass`, `checks pass=22 warn=0 fail=0 skip=0`, dry-run `Remote database is up to date`, advisor `No issues found`. |
| `.venv/bin/python -m pytest tests/test_supabase_remote_verify.py tests/test_storage_permissions.py tests/test_runtime_feature_guards.py -q` | PASS | `31 passed`; no warnings after Storage options regression test update. |
| `.venv/bin/python -m pytest -q` | PASS | Initial run: `1145 passed, 8 skipped in 104.32s`; follow-up run after remediation: `1147 passed, 8 skipped in 104.79s`. No warning summary printed. |
| `npm run build` | PASS | Vite build completed; non-blocking large chunk warning for `rhwp_bg`/`plotly`. |
| `make openapi-docs-check` | PASS | `OpenAPI docs are current.` |
| `make supabase-docker-config` | PASS | Compose config valid. |
| `make supabase-docker-up` | PASS | Docker Supabase override stack rebuilt and started at `http://localhost:8080`. |
| `make supabase-docker-ps` | PASS | backend up, frontend healthy, redis healthy, reverse proxy healthy on `0.0.0.0:8080`. |
| `make supabase-docker-health` | PASS after follow-up | `/api/health` returns `status=ok`, `llm_connected=true`, `chroma_connected=false`; Chroma is optional in slim mode. |

## RLS, Data API, Advisor

Strict verifier PASS items:

- `required_tables_rls_enabled`
- `sensitive_role_grants`
- `data_api_deny_policies`
- `default_admin_risk`
- `storage_api_access`
- `storage_buckets_present`
- `storage_buckets_private`
- `firebase_read_fallback_disabled`

Supabase CLI advisor result:

```text
supabase db advisors --linked --type security --level warn
No issues found
```

No Firebase-removal blocker was found in RLS, sensitive role grants, Data API deny policies, default admin posture, or Supabase Storage bucket privacy.

## Storage Signed URL Smoke

### Local Docker Runtime

Base URL: `http://localhost:8080`

| Step | Result |
| --- | --- |
| `/api/admin/system/health-extended` | `200`; `firebase_write_enabled=false`, `firebase_read_fallback_enabled=false`, `external.supabase.status=ok`, `database_connected=true`, `storage_configured=true`, `storage_buckets_present=true`. |
| `/api/storage/signed-upload` as owner `PE-0019` | `200`; attachment id and signed URL returned. |
| signed URL `PUT` | `200`. |
| `/api/storage/complete-upload` as owner | `200`; `ok=true`; signed download URL returned. |
| owner `/api/storage/signed-download/{attachment_id}` | `200`. |
| other employee `/api/storage/signed-download/{attachment_id}` | `403`, `attachment_forbidden`. |
| signed download URL `GET` | `200`, `text/plain`, payload matched smoke content. |

Plan credential note:

- Exact demo credentials from the plan, `SYS-0001/Demo!2026` and `PE-0019/Demo!2026`, returned `401` in local runtime.
- `SYS-0001` login with the gitignored bootstrap password file worked. Storage smoke used short-lived JWTs to avoid printing or embedding passwords.

### Cloud Run No-Traffic Tag

- Revision: `ajin-backend-00226-cer`.
- Tag URL: `https://supabase-gate-20260520---ajin-backend-ncsnraqdaa-du.a.run.app`.
- Traffic: `0 percent`; no production promote was performed.
- Deploy log: `/tmp/ajin-deploy-logs/deploy-20260520-083518.log`.

`scripts/deploy-backend.sh --mode slim --require-supabase --skip-canary --tag supabase-gate-20260520` created the revision and passed tag URL smoke, then exited non-zero because the initial `SMOKE_ADMIN_JWT` received `401`. The smoke token was refreshed from `secrets/ajin-jwt-secret.txt` using `scripts/mint_smoke_admin_jwt.py --overwrite --ttl-minutes 60`, then the runtime admin health and Storage owner smoke passed:

| Step | Result |
| --- | --- |
| `bash scripts/smoke-test.sh <TAG_URL> ajin-backend-00226-cer` | PASS; HTTP probes non-5xx, startup logs include `Application startup complete`, auth DB init, and `Firestore read fallback 비활성`; forbidden boot keywords absent. |
| `/api/admin/system/health-extended` with refreshed smoke JWT | `200`; `firebase_write_enabled=false`, `firebase_read_fallback_enabled=false`, `supabase_status=ok`, `database_connected=true`, `storage_configured=true`, `storage_buckets_present=true`, `data_api_locked_down=true`, `default_admin_risk=false`. |
| Tag `/api/storage/signed-upload` as owner `PE-0019` | `200`; attachment id and signed URL returned. |
| Tag signed URL `PUT` | `200`. |
| Tag `/api/storage/complete-upload` as owner | `200`; `ok=true`; signed download URL returned. |
| Tag owner `/api/storage/signed-download/{attachment_id}` | `200`. |
| Tag other employee `/api/storage/signed-download/{attachment_id}` | `403`, `attachment_forbidden`. |
| Tag signed download URL `GET` | `200`, `text/plain`, payload matched smoke content. |

## Screen Smoke

Browser URL: `http://localhost:8080`

| Route | Result | Notes |
| --- | --- | --- |
| `/login` | PASS with warning | Page rendered without blank screen. Exact `Demo!2026` credentials returned `401`; actual bootstrap admin credential path worked without exposing the password. |
| `/` | PASS with warnings | Dashboard loaded; core dashboard APIs returned `200`. `/api/compliance/glossary` returned `404`; compliance alarm EventSource returned `401`, while polling fallback endpoints returned `200`. |
| `/search` | PASS with warning | Employee/org/facility APIs returned `200`; `/api/compliance/glossary` returned `404`. |
| `/chat` | PASS with warning | Chat screen and file attach UI loaded; model/onboarding APIs returned `200`; `/api/compliance/glossary` returned `404`. |
| `/onboarding` | PASS with warning | SOP/checklist screen loaded; APIs returned `200`; UI showed a question-list load warning; `/api/compliance/glossary` returned `404`. |
| `/draft` | PASS with warning | Draft/export UI loaded; draft APIs returned `200`; `/api/compliance/glossary` returned `404`. |
| `/compliance` | PASS with warning | Alarm/feed/crawler screen loaded; functional APIs returned `200`; `/api/compliance/glossary` returned `404`. |
| `/equipment` overview/SPC/inspection | PASS with warnings | Equipment APIs returned `200`; SPC NaN SVG console issue was fixed and rechecked; live gateway shows offline because redis package is missing in local runtime; `/api/compliance/glossary` returned `404`. |
| `/management?cat=system` | PASS with warning | `/api/admin/system/health-extended` returned `200`; UI shows `firebase_write_enabled=false`, `firebase_read_fallback_enabled=false`, and external status `ok`; Redis section is `error`. |

No route showed a 5xx loop, blank screen, or Firebase read fallback dependency failure.

## Fixes Applied During Verification

- `backend/services/supabase_storage.py`: added a Storage signed-upload options wrapper that behaves as both a mapping and an object with `.upsert`, matching the installed `storage3` runtime while preserving the official mapping shape documented by Supabase.
- `tests/test_storage_permissions.py`: added a regression test for the signed-upload options shape.
- `frontend/src/components/equipment/tabs/SPCSubTab.tsx`: guarded SPC SVG rendering until chart values and control limits are finite, removing `NaN` SVG console errors during the SPC tab smoke.

## Initial Remaining Blockers / Warnings Before Firebase Removal

The following list is the raw output from the first gate pass. It is superseded by the follow-up remediation section below.

1. Exact smoke credentials in the plan, `SYS-0001/Demo!2026` and `PE-0019/Demo!2026`, do not authenticate locally. Either update the smoke plan to use the bootstrap secret/JWT path or align the demo credentials.
2. `/api/compliance/glossary` returns `404` across major screens and produces one console error per route.
3. Dashboard compliance alarm SSE returns `401`; polling fallback works, but EventSource cannot attach the localStorage JWT in its current form.
4. Local Docker `/api/health` is `degraded` because `chroma_connected=false` and `chroma_doc_count=0`.
5. Admin extended health reports Redis section `error` locally (`No module named 'redis'` in the earlier detailed payload), while the Docker Redis container itself is healthy.
6. Supabase CLI update is available (`2.100.1` vs installed `2.98.2`); non-blocking because current gates pass.
7. Build/deploy emitted non-blocking warnings: Vite large chunks, Dockerfile JSON CMD recommendation, pip root-user warning, and npm audit moderate warning.

## Remaining Release Follow-up

1. Run a final browser route smoke on the target no-traffic/canary revision before any production promote.
2. Keep dashboard compliance alarms on polling unless an authenticated cookie-based SSE design is implemented and verified.
3. Refresh Supabase CLI after the release gate is stable; the current installed version still passes the required checks.
4. Treat Vite large chunk, Dockerfile JSON CMD recommendation, and pip root-user warning as non-blocking cleanup unless the release owner raises them to blockers.
5. Current revision `ajin-backend-00226-cer` remains no-traffic only; promote only through the normal canary flow.

## Follow-up Remediation - 2026-05-20

| Item | Follow-up status | Evidence |
| --- | --- | --- |
| `Demo!2026` smoke credential `401` | Resolved as policy separation. `Demo!2026` is mock seed/demo-chip only and must not be used as Supabase/Postgres release smoke credential. Release smoke uses the bootstrap secret path locally and short-lived `SMOKE_ADMIN_JWT` on Cloud Run. | `frontend/src/lib/demoAccounts.ts` now shows chips by default only when `VITE_USE_MOCK=true` in dev; `docs/SUPABASE_REMOTE_OPERATION_RUNBOOK.md` defines the smoke credential contract. |
| `/api/compliance/glossary` `404` | Resolved in the frontend. Backend `404 {"detail":"feature_disabled"}` remains the intended D2 gate when `d2_rag=false`; the shared `GlossaryProvider` now waits for Feature D flags and skips the glossary fetch while D2 is disabled. | Local Docker `/api/feature-flags/d` returned `d2_rag=false`; direct `/api/compliance/glossary` returned expected `404 feature_disabled`; frontend build passed. |
| Dashboard SSE `401` | Resolved by defaulting dashboard alarms to authenticated polling. Native EventSource stream remains opt-in via `VITE_COMPLIANCE_ALARMS_SSE=true` for a future cookie-auth experiment. | Unauthenticated direct `/api/compliance/alarms/stream` still returns expected `401`; dashboard production bundle initializes SSE state to `false`; `npm run build` passed. |
| Local `/api/health` degraded from Chroma | Resolved for slim runtime. Chroma is optional when `ENABLE_FEATURE_A=false`; full/search runtime can still require it through `ENABLE_FEATURE_A=true` or `REQUIRE_CHROMA_HEALTH=true`. | Local Docker `/api/health` returned `{"status":"ok","llm_connected":true,"chroma_connected":false}`; `tests/test_system_health.py` covers optional vs required Chroma. |
| Admin health Redis package warning | Resolved in slim runtime dependency set. | `requirements-cloudrun.txt` includes `redis>=5.0`; rebuilt Docker image installed `redis-7.4.0`; `/api/admin/system/health-extended` returned `sections.redis.status=ok`, `ping_ms=3`. |

Follow-up verification:

```text
.venv/bin/python -m pytest tests/test_system_health.py tests/test_feature_d_gating.py tests/test_mint_smoke_admin_jwt.py -q
23 passed in 1.28s

.venv/bin/python -m pytest -q
1147 passed, 8 skipped in 104.79s (0:01:44)

npm run build
✓ built; existing large chunk warning only

make openapi-docs-check
OpenAPI docs are current.

set -a; source .env.supabase.local; set +a; make supabase-release-check
Supabase remote verification: pass
checks pass=22 warn=0 fail=0 skip=0
Remote database is up to date.
No issues found
```

Residual non-blocking warnings:

- Supabase CLI update notice: installed `2.98.2`, available `2.100.1`.
- Vite large chunk warning for existing large assets, primarily `plotly`/WASM.
- Docker build warnings unrelated to the Supabase gate: JSON-form CMD recommendation and pip root-user warning.
