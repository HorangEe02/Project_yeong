# Release Security Verification

- Checked at: `2026-05-20T07:10:16.345958+00:00`
- Overall status: `pass`
- Counts: pass=2, fail=0, skip=2

## Checks

| Check | Status | Summary |
|---|---:|---|
| `frontend_secret_exposure` | `pass` | No backend-only Supabase secret markers found in frontend artifacts. |
| `supabase_rls_data_api_guard` | `pass` | Supabase RLS/Data API release checks are pass. |
| `cloud_run_secret_mapping` | `skip` | Skipped because no Cloud Run service JSON was supplied. |
| `admin_health_secret_safe` | `skip` | Skipped because no admin health JSON was supplied. |

## Redacted JSON

```json
{
  "checked_at": "2026-05-20T07:10:16.345958+00:00",
  "checks": [
    {
      "details": {
        "files_scanned": 476
      },
      "name": "frontend_secret_exposure",
      "status": "pass",
      "summary": "No backend-only Supabase secret markers found in frontend artifacts."
    },
    {
      "details": {
        "required_checks": [
          "data_api_deny_policies",
          "default_admin_risk",
          "required_tables_rls_enabled",
          "sensitive_role_grants"
        ]
      },
      "name": "supabase_rls_data_api_guard",
      "status": "pass",
      "summary": "Supabase RLS/Data API release checks are pass."
    },
    {
      "details": {},
      "name": "cloud_run_secret_mapping",
      "status": "skip",
      "summary": "Skipped because no Cloud Run service JSON was supplied."
    },
    {
      "details": {},
      "name": "admin_health_secret_safe",
      "status": "skip",
      "summary": "Skipped because no admin health JSON was supplied."
    }
  ],
  "root": "~/99_me/00_github/04_AJIN/ajin-ai-assistant-react",
  "summary": {
    "fail": 0,
    "pass": 2,
    "skip": 2,
    "status": "pass"
  }
}
```
