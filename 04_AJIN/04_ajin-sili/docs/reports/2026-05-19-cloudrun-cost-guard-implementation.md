# AJIN Cloud Run Cost Guard Implementation Report

- Date: 2026-05-19
- Scope: `ajin-backend` in project `ajin-cb`, region `asia-northeast3`
- Production traffic policy: unchanged
- Tag deletion policy: review only, no tags deleted

## Applied Commands

```bash
gcloud run services update ajin-backend \
  --project ajin-cb \
  --region asia-northeast3 \
  --min 0 \
  --max 1 \
  --cpu-throttling
```

Because revision-level settings still showed `minScale=1`, the revision-level guard was also applied:

```bash
gcloud run services update ajin-backend \
  --project ajin-cb \
  --region asia-northeast3 \
  --min-instances 0 \
  --max-instances 1 \
  --cpu-throttling
```

Both updates completed without changing production traffic:

```text
Service [ajin-backend] revision [ajin-backend-00215-zoc] has been deployed and is serving 0 percent of traffic.
```

## Verification Results

Current service-level and template-level non-secret fields:

```text
run.googleapis.com/maxScale=1
run.googleapis.com/cpu-throttling=true
autoscaling.knative.dev/maxScale=1
autoscaling.knative.dev/minScale=<absent>
production traffic=ajin-backend-00156-pm6 100%
latest smoke tag=deploy-20260519-140944 -> ajin-backend-00215-zoc
```

Important residual finding:

```text
ajin-backend-00156-pm6 annotations:
  autoscaling.knative.dev/minScale=1
  autoscaling.knative.dev/maxScale=5

ajin-backend-00215-zoc annotations:
  autoscaling.knative.dev/minScale=1
  autoscaling.knative.dev/maxScale=5
```

Interpretation:

- The active service template is now guarded for future revisions.
- Service-level max is capped at `1`.
- Request-based billing is explicitly enabled through `cpu-throttling=true`.
- Full scale-to-zero is still blocked for already-serving or tagged revisions that retain revision-level `minScale=1`.
- This is expected under the current constraint: production traffic was not promoted, and tags were not removed.

## Traffic Tag Deletion Candidates

Brainstormed zero-idle-cost paths:

```text
Option A: Remove stale traffic tags only.
  Effect: Reduces tagged-revision idle cost risk without changing production traffic.
  Limit: Current production revision and temporary smoke tag can still retain revision-level minScale=1.

Option B: Remove all traffic tags, including the latest smoke tag.
  Effect: Removes tag-triggered idle cost risk.
  Limit: Loses direct smoke URL and still does not fix production revision minScale=1.

Option C: Promote a guarded revision with no revision-level minScale, then clear all tags.
  Effect: Best path to true idle zero-cost.
  Limit: This is a production traffic change and must be separately approved.
```

Chosen action in this pass:

```text
Option A: remove stale traffic tags only.
```

Keep:

```text
production: ajin-backend-00156-pm6 at 100% traffic, no tag
temporary smoke tag: deploy-20260519-140944 -> ajin-backend-00215-zoc
```

Review for deletion after rollback policy approval:

```text
fix-bm25
deploy-20260508-114432
deploy-20260508-121012
deploy-20260508-122107
deploy-20260508-123926
deploy-20260508-151909
deploy-20260508-181307
deploy-20260508-183441
deploy-20260508-185352
fix-employee-detector
fix-real-crawlers-phase1
fix-crawler-titles
deploy-20260510-171234
deploy-20260510-174223
deploy-20260510-222153
deploy-20260510-224417
deploy-20260510-230656
deploy-20260510-232819
deploy-20260511-000314
deploy-20260511-001410
deploy-20260511-003200
deploy-20260511-004559
deploy-20260511-011436
deploy-20260511-063308
deploy-20260511-082801
deploy-20260511-103912
deploy-20260511-150821
deploy-20260511-151521
```

Do not run this without explicit approval:

```bash
gcloud run services update-traffic ajin-backend \
  --project ajin-cb \
  --region asia-northeast3 \
  --remove-tags=fix-bm25,deploy-20260508-114432,deploy-20260508-121012,deploy-20260508-122107,deploy-20260508-123926,deploy-20260508-151909,deploy-20260508-181307,deploy-20260508-183441,deploy-20260508-185352,fix-employee-detector,fix-real-crawlers-phase1,fix-crawler-titles,deploy-20260510-171234,deploy-20260510-174223,deploy-20260510-222153,deploy-20260510-224417,deploy-20260510-230656,deploy-20260510-232819,deploy-20260511-000314,deploy-20260511-001410,deploy-20260511-003200,deploy-20260511-004559,deploy-20260511-011436,deploy-20260511-063308,deploy-20260511-082801,deploy-20260511-103912,deploy-20260511-150821,deploy-20260511-151521
```

Executed after approval:

```text
Routing traffic...................done
Done.
URL: https://ajin-backend-ncsnraqdaa-du.a.run.app
Traffic:
  100% ajin-backend-00156-pm6
  0%   ajin-backend-00215-zoc
         deploy-20260519-140944: https://deploy-20260519-140944---ajin-backend-ncsnraqdaa-du.a.run.app
```

Post-removal traffic state:

```text
production traffic: ajin-backend-00156-pm6 100%
remaining tag: deploy-20260519-140944 -> ajin-backend-00215-zoc
removed stale tags: 28
```

## Light API PoC

Added a no-secret Vercel API function:

```text
frontend/api/edge-health.js
```

Expected response:

```json
{
  "ok": true,
  "service": "ajin-frontend",
  "runtime": "vercel-function",
  "cloud_run": false,
  "timestamp": "<iso timestamp>"
}
```

Local function mock result:

```text
200 no-store {"ok":true,"service":"ajin-frontend","runtime":"vercel-function","cloud_run":false,"timestamp":"2026-05-19T05:43:13.530Z"}
```

## Validation

```text
git diff --check: pass
npm run build: pass
frontend/dist secret scan: no matches
Cloud Run production /api/health: 200 application/json
Cloud Run production /api/health after tag removal: 200 application/json
```

Secret scan command:

```bash
rg -n "SUPABASE_SECRET|service_role|sb_secret|DATABASE_URL|SUPABASE_ACCESS_TOKEN|SUPABASE_DB_PASSWORD|postgresql://|postgres://|supabase\\.co" frontend/dist
```

Result:

```text
exit code 1, no output
```

## Production Zero-Min Cutover

Executed after approval:

```text
fresh revision: ajin-backend-zero-min-20260519-1
image digest: sha256:e5ca4ceb9304d4a8413202116625ddf93bf75f9b0886c176a592794a7835ee8c
smoke URL: https://zero-min-smoke-20260519---ajin-backend-ncsnraqdaa-du.a.run.app
```

Smoke results:

```text
/api/health: 200 application/json
scripts/smoke-test.sh: PASSED
required logs:
  Application startup complete
  인증 DB 초기화 완료
  Firestore read fallback 비활성
forbidden startup keywords: none
```

Production traffic was promoted:

```text
Traffic:
  100% ajin-backend-zero-min-20260519-1
```

All traffic tags were removed after production health passed:

```text
Cloud Run production /api/health after promote: 200 application/json
status.traffic tags: none
```

Final revision guard:

```text
autoscaling.knative.dev/minScale=<absent>
autoscaling.knative.dev/maxScale=1
run.googleapis.com/cpu-throttling=true
```

Rollback command:

```bash
gcloud run services update-traffic ajin-backend \
  --project ajin-cb \
  --region asia-northeast3 \
  --to-revisions=ajin-backend-00156-pm6=100
```

Post-cutover validation:

```text
git diff --check: pass
npm run build: pass
frontend/dist secret scan: no matches
```

## Remaining Monitoring

Cloud Run compute idle cost is now reduced to the closest practical zero-idle posture:

- production serves a revision with no revision-level `minScale`;
- service-level max is capped at `1`;
- request-based billing is enabled through CPU throttling;
- no traffic tags remain.

For the next 3 days, monitor `run.googleapis.com/request_count` for `ajin-backend` and classify any remaining requests as heavy API, smoke/manual check, crawler, bot, or frontend rewrite leakage.
