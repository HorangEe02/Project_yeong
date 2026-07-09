# Final Browser Route Smoke - 2026-05-20

- Checked at: `2026-05-20T01:05:16.838Z`
- Browser target: `http://127.0.0.1:8080`
- Auth: short-lived release-owner smoke JWT from gitignored token file; token value not recorded.
- Overall: PASS (14/14 routes passed)

## Cloud Run Backend Target

- Tag URL: `https://supabase-gate-20260520---ajin-backend-ncsnraqdaa-du.a.run.app`
- Revision: `ajin-backend-00226-cer`
- Note: the tag URL is the backend Cloud Run service; SPA route smoke uses the rebuilt Docker reverse proxy serving the release frontend bundle.

## Route Results

| Route | Result | Final URL | 5xx | Glossary API | Alarm SSE | Console errors | Notes |
|---|---:|---|---:|---:|---:|---:|---|
| `/login` | PASS | `/login` | 0 | 0 | 0 | 0 | login page render |
| `/` | PASS | `/` | 0 | 0 | 0 | 0 | dashboard render |
| `/search` | PASS | `/search` | 0 | 0 | 0 | 0 | search render |
| `/draft` | PASS | `/draft` | 0 | 0 | 0 | 0 | draft render |
| `/chat` | PASS | `/chat` | 0 | 0 | 0 | 0 | chat render |
| `/onboarding` | PASS | `/onboarding` | 0 | 0 | 0 | 0 | onboarding render |
| `/compliance` | PASS | `/compliance` | 0 | 0 | 0 | 0 | compliance render |
| `/equipment` | PASS | `/equipment` | 0 | 0 | 0 | 0 | equipment render |
| `/management?cat=system` | PASS | `/management?cat=system` | 0 | 0 | 0 | 0 | system management render |
| `/equipment/field` | PASS | `/equipment/field` | 0 | 0 | 0 | 0 | field equipment render |
| `/compliance/search` | PASS | `/compliance` | 0 | 0 | 0 | 0 | D2-gated redirect to /compliance |
| `/compliance/glossary` | PASS | `/compliance` | 0 | 0 | 0 | 0 | D2-gated redirect to /compliance |
| `/admin` | PASS | `/management?cat=system` | 0 | 0 | 0 | 0 | redirect to /management?cat=system |
| `/hr` | PASS | `/management?cat=users` | 0 | 0 | 0 | 0 | redirect to /management?cat=users |

## Artifacts

- JSON: `~/99_me/00_github/04_AJIN/ajin-ai-assistant-react/outputs/supabase-verification/2026-05-20-browser-smoke/route-smoke-results.json`
- Screenshots: `~/99_me/00_github/04_AJIN/ajin-ai-assistant-react/outputs/supabase-verification/2026-05-20-browser-smoke`
