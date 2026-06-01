# AJIN Cloud Run Cost Reduction Route Plan

- Date: 2026-05-19
- Scope: `/Users/yeong/99_me/00_github/04_AJIN/ajin-ai-assistant-react`
- Goal: Reduce normal Cloud Run calls close to zero by moving light routes to Vercel/Supabase first, while keeping heavy FastAPI features on Cloud Run scale-to-zero.
- Implementation status: Inventory and design only. No route rewrite, Cloud Run update, or API migration was applied in this pass.

## 1. Current Command Results

### 1.1 Git status

The worktree is already heavily dirty. This plan intentionally preserves unrelated changes.

Focused status for the files named in the handoff:

```text
 M scripts/deploy-backend.sh
 M scripts/smoke-test.sh
?? docs/SUPABASE_REMOTE_OPERATION_RUNBOOK.md
?? frontend/vercel.json
?? scripts/configure_cloudrun_supabase_runtime.py
?? scripts/mint_smoke_admin_jwt.py
?? tests/test_configure_cloudrun_supabase_runtime.py
?? tests/test_mint_smoke_admin_jwt.py
```

### 1.2 Current `frontend/vercel.json`

Current routing still sends every `/api/*` call to Cloud Run:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://ajin-backend-ncsnraqdaa-du.a.run.app/api/:path*"
    },
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

### 1.3 Cloud Run cost guard status

Checked with:

```bash
gcloud run services describe ajin-backend --project ajin-cb --region asia-northeast3 '--format=json(metadata.annotations,spec.template.metadata.annotations,spec.template.spec.containerConcurrency,status.traffic,status.latestReadyRevisionName,status.latestCreatedRevisionName)'
```

Observed non-secret fields:

| Field | Current value | Cost impact |
| --- | --- | --- |
| Service-level max | `run.googleapis.com/maxScale=20` | Too high for a cost guard. |
| Revision min | `autoscaling.knative.dev/minScale=1` | Prevents true scale-to-zero for the latest revision. |
| Revision max | `autoscaling.knative.dev/maxScale=5` | Higher than the requested first-stage cap of `1`. |
| CPU throttling annotation | Missing | Official docs say missing means request-based billing. This part is OK. |
| Latest ready revision | `ajin-backend-00215-zoc` | Supabase smoke revision exists. |
| Production traffic | `ajin-backend-00156-pm6` at `100%` | Latest smoke revision is not production-promoted. |
| Traffic tags | Many old tags, plus `deploy-20260519-140944` | Old tagged revisions should be reviewed and removed if not needed. |

Important Cloud Run doc point: revision-level minimum instances plus traffic tags can keep tagged revisions active and billable. For this repo, tag cleanup is a real cost item, not cosmetic cleanup.

## 2. Backend Route Inventory

Routers are registered in `backend/main.py` under `/api`, except Slack:

| Router group | Representative routes | Initial class | Reason |
| --- | --- | --- | --- |
| `/api/health` | `/health`, `/health/llm-status` | Heavy/mixed | Current `/health` checks Ollama and Chroma, so it is not a cheap edge health route. Add a new light health endpoint before moving. |
| `/api/feature-flags` | `/c`, `/d`, `/firebase-cost` | Light | Env/config dictionary only. Good no-secret Vercel Function PoC. |
| `/api/storage` | `/signed-upload`, `/complete-upload`, `/signed-download/{id}` | Light but secret-bearing | Best target is Supabase Edge Function or direct Supabase Storage policy flow, not Vercel, because Vercel should not hold backend secrets in this plan. |
| `/api/live-alarms` | `/recent`, `/{alarm_id}/ack` | Light | Already backed by `live_alarms` via Postgres/SQLite. Candidate for Supabase direct RLS or Edge Function. |
| `/api/feedback` | `POST /feedback` | Light | Firebase RTDB replacement write path. Candidate for Supabase direct insert with RLS after policy review. |
| `/api/dashboard` | `/metrics`, `/ingestion`, `/module-counts`, `/alarms`, `/system-health`, `/system-info` | Mixed | Some endpoints count local SQLite/files or expose backend runtime info. Data-only summaries can move after Postgres parity; runtime health stays Cloud Run or gets split. |
| `/api/models` | `/catalog`, `/recommend`, `/installed`, `/vision`, `/llm-options` | Mixed | Catalog/recommend can become light; installed/vision/status may touch runtime/model inventory. |
| `/api/auth`, `/api/auth/idp`, `/api/me` | login, refresh, profile, 2FA, OIDC/SAML/LDAP | Ambiguous | Move only after auth cookie/session hardening and explicit threat model. Not a first PoC. |
| `/api/admin`, `/api/admin/scenarios`, `/api/scenarios`, `/api/directory` | HR/admin/scenario/directory reads and writes | Ambiguous | Mostly DB-backed but high RBAC/privacy risk. Needs RLS/permission parity before migration. |
| `/api/employee` | `/list`, `/by-department`, `/org-tree`, `/search` | Mixed | List/tree can become light after Postgres/RLS; semantic search remains Cloud Run. |
| `/api/search` | `/documents`, `/intent`, `/vision-query`, `/drawings`, captions | Heavy/mixed | Hybrid search, Chroma/OCR/vision candidates keep Cloud Run. Drawings metadata may later split. |
| `/api/onboarding` | chat, upload, SOP, quiz, vision/document tasks, badges | Heavy/mixed | Chat/vision/upload/document tasks stay Cloud Run. SOP/static/gamification reads can be later split. |
| `/api/draft` | generate, stream, export, quality, mail, versions | Heavy | LLM streaming, document processing/export, mail guard. Keep Cloud Run. |
| `/api/compliance` | changes, what-if, crawl, docs, search, alarms SSE, approvals, learning | Heavy/mixed | Crawlers, RAG, reports, search, scheduler stay Cloud Run. Alarm polling and simple docs lists may later split. |
| `/api/equipment` | dashboard, SPC, manual search, inspection upload, PLC, drawing OCR | Heavy/mixed | Manual search/OCR/uploads stay Cloud Run. Read-only dashboard/checklist/status can later split after DB parity. |
| `/api/export` | `/hwp`, `/hwpx` | Heavy | Binary document generation. Keep Cloud Run. |
| `/api/notifications` | prefs, test, dispatch, log | Ambiguous | Prefs can move after RLS; dispatch remains backend/work queue. |
| `/slack` | `/command`, `/health` | Heavy/external webhook | Keep Cloud Run unless Slack webhook signing and secret handling are moved to Supabase Edge Functions. |

## 3. Frontend API Caller Map

Frontend base routing:

- `frontend/src/api/baseUrl.ts`: default `API_BASE_URL=/api`.
- `frontend/src/api/client.ts`: axios instance uses `/api`, JWT interceptor, refresh-on-401, 30s timeout.
- Raw fetch/SSE bypass axios in specific flows.

High-volume or first-screen callers:

| Frontend caller | Routes | Migration note |
| --- | --- | --- |
| `frontend/src/api/dashboard.ts` | `/dashboard/metrics`, `/dashboard/ingestion`, `/dashboard/system-health`, `/dashboard/alarms`, `/dashboard/module-counts` | Split data-only summary endpoints first; keep runtime health on Cloud Run until a light health route exists. |
| `frontend/src/lib/featureFlags.ts` | `/feature-flags/c`, `/feature-flags/d` | Good Vercel no-secret Function PoC. |
| `frontend/src/api/liveAlarms.ts` | `/live-alarms/recent` | Good Supabase RLS/Edge PoC candidate. |
| `frontend/src/api/upload.ts` | `/storage/*`, `/onboarding/upload`, direct signed URL PUT | Storage signing can move to Supabase Edge; actual file parsing stays Cloud Run. |
| `frontend/src/hooks/useComplianceAlarmsSse.ts` | `/api/compliance/alarms/stream` | SSE keeps Cloud Run until Supabase Realtime is designed. |
| `frontend/src/hooks/useSSE.ts`, `frontend/src/api/draft.ts` | `/api/draft/stream`, `/api/draft/stream-v2`, `/api/onboarding/chat` | Heavy streaming paths stay Cloud Run. |
| `frontend/src/api/auth.ts`, `frontend/src/api/me.ts` | `/auth/*` | Security-sensitive; do not move in first PoC. |
| `frontend/src/api/compliance.ts` | broad `/compliance/*` | Split only simple read endpoints after policy review; crawlers/search/RAG stay Cloud Run. |
| `frontend/src/api/equipment.ts` | broad `/equipment/*` | Split only read-only DB endpoints later; upload/OCR/manual search stays Cloud Run. |
| `frontend/src/api/search.ts` | `/search/documents`, `/search/intent`, `/search/vision-query`, `/search/capabilities` | `capabilities` can become light; search/vision stays Cloud Run. |

## 4. Proposed Rewrite Strategy

Current state is one broad external rewrite:

```json
{ "source": "/api/:path*", "destination": "https://ajin-backend-ncsnraqdaa-du.a.run.app/api/:path*" }
```

Target transition shape:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "rewrites": [
    {
      "source": "/api/storage/:path*",
      "destination": "https://<supabase-project-ref>.functions.supabase.co/storage/:path*"
    },
    {
      "source": "/api/live-alarms/:path*",
      "destination": "https://<supabase-project-ref>.functions.supabase.co/live-alarms/:path*"
    },
    {
      "source": "/api/:path*",
      "destination": "https://ajin-backend-ncsnraqdaa-du.a.run.app/api/:path*"
    },
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

Rules:

- Keep a Cloud Run fallback rewrite during migration.
- Vercel Functions such as `/api/edge-health` and `/api/feature-flags/firebase-cost` should be served as filesystem API routes, not self-rewrites. Vercel routing applies filesystem routes before rewrites.
- Do not put Supabase service role, secret keys, DB URLs, or access tokens in Vercel.
- Use Vercel Functions only for no-secret endpoints such as edge health and static feature flags.
- Use Supabase direct RLS or Supabase Edge Functions for DB/Storage-backed light endpoints.
- Keep signed upload/download privilege checks server-side. A public Supabase publishable key alone is not authorization.

## 5. First Implementation Plan After Approval

### Step A. Cloud Run cost guard

Run only after approval:

```bash
gcloud run services update ajin-backend \
  --project ajin-cb \
  --region asia-northeast3 \
  --min 0 \
  --max 1 \
  --cpu-throttling
```

Then verify:

```bash
gcloud run services describe ajin-backend \
  --project ajin-cb \
  --region asia-northeast3 \
  '--format=json(metadata.annotations,spec.template.metadata.annotations,status.traffic,status.latestReadyRevisionName)'
```

Separate review item: remove old traffic tags that are not needed for rollback or smoke testing.

### Step B. No-secret Vercel Function PoC

Add a small Vercel Function for one of:

- `GET /api/edge-health`
- `GET /api/feature-flags/firebase-cost`

This validates that Vercel can serve light API traffic without Cloud Run and without secrets.

### Step C. Supabase-backed PoC

Pick exactly one:

- `GET /api/live-alarms/recent` via Supabase Edge Function or direct RLS.
- Storage signed URL flow via Supabase Edge Function.

`/api/live-alarms/recent` is lower risk because it is read-mostly and already has a clear table boundary. Storage is more valuable but riskier because owner checks and signed URL expiry must stay exact.

### Step D. Vercel rewrite split

Update `frontend/vercel.json` so only migrated light routes bypass Cloud Run. Keep all heavy and unknown paths on the Cloud Run fallback.

### Step E. Verification

Minimum local verification:

```bash
git diff --check
cd frontend && npm run build
rg -n "SUPABASE_SECRET|service_role|sb_secret|DATABASE_URL|SUPABASE_ACCESS_TOKEN|SUPABASE_DB_PASSWORD|postgresql://|postgres://|supabase\\.co" frontend/dist
```

Relevant backend/API tests depend on the chosen PoC:

- Feature flag PoC: existing frontend build plus route smoke.
- Live alarms PoC: `tests/test_live_events.py` and any new function/RLS tests.
- Storage PoC: `tests/test_storage_permissions.py` plus signed upload/download smoke.

## 6. Official Documentation Referenced

- Cloud Run billing settings: https://docs.cloud.google.com/run/docs/configuring/billing-settings
- Cloud Run minimum instances: https://docs.cloud.google.com/run/docs/configuring/min-instances
- Cloud Run maximum instances: https://docs.cloud.google.com/run/docs/configuring/max-instances
- `gcloud run services update`: https://cloud.google.com/sdk/gcloud/reference/run/services/update
- Vercel rewrites: https://vercel.com/docs/routing/rewrites
- Vercel routing order: https://vercel.com/docs/routing
- Vercel Functions limits: https://vercel.com/docs/functions/limitations
- Vercel environment variables: https://vercel.com/docs/environment-variables
- Vite env variables: https://vite.dev/guide/env-and-mode
- Supabase API keys: https://supabase.com/docs/guides/getting-started/api-keys
- Supabase RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase cost control: https://supabase.com/docs/guides/platform/cost-control
- Supabase breaking change for Data API exposure: https://supabase.com/changelog/45329-breaking-change-tables-not-exposed-to-data-and-graphql-api-automatically

## 7. Conventional Commit Suggestion

```text
docs(cost): classify Cloud Run routes for Vercel Supabase split

Explain which API routes can move off Cloud Run first and which routes must
remain on the scale-to-zero FastAPI backend because they depend on LLMs,
document generation, crawlers, OCR, SSE, or local runtime state.

This gives the team an endpoint-level migration gate before changing
Vercel rewrites or Cloud Run scaling settings.
```
