# Supabase Remote Verification

- Checked at: `2026-05-18T08:10:01.846626+00:00`
- Project ref: `ycjuzwltwbeudanjykag`
- Expected URL: `https://ycjuzwltwbeudanjykag.supabase.co`
- Strict mode: `True`
- Overall status: `fail`
- Counts: pass=4, warn=1, fail=9, skip=6

## Checks

| Check | Status | Summary |
|---|---:|---|
| `project_ref_configured` | `fail` | SUPABASE_PROJECT_REF is required in strict mode. |
| `url_matches_project_ref` | `fail` | SUPABASE_URL is missing. |
| `db_backend` | `fail` | APP_DB_BACKEND must be postgres for Supabase operation. |
| `database_url_configured` | `fail` | DATABASE_URL is missing. |
| `secret_key_configured` | `fail` | SUPABASE_SECRET_KEY is missing or not an elevated backend key. |
| `publishable_key_configured` | `warn` | SUPABASE_PUBLISHABLE_KEY presence checked. |
| `firebase_write_disabled` | `pass` | Firebase writes are disabled. |
| `firebase_read_fallback_disabled` | `pass` | Firebase read fallback is disabled. |
| `supabase_cli_available` | `pass` | Supabase CLI is executable. |
| `supabase_access_token_shape` | `pass` | Supabase access token shape is valid. |
| `supabase_project_list` | `fail` | Supabase CLI project list failed. |
| `supabase_linked_project_ref` | `fail` | Supabase project is not linked locally. |
| `database_connected` | `fail` | DATABASE_URL is missing; DB check cannot run. |
| `alembic_current` | `skip` | Skipped because DATABASE_URL is missing. |
| `required_tables_present` | `skip` | Skipped because DATABASE_URL is missing. |
| `required_tables_rls_enabled` | `skip` | Skipped because DATABASE_URL is missing. |
| `sensitive_role_grants` | `skip` | Skipped because DATABASE_URL is missing. |
| `storage_api_access` | `fail` | SUPABASE_URL and SUPABASE_SECRET_KEY are required for Storage verification. |
| `storage_buckets_present` | `skip` | Skipped because Storage API is not configured. |
| `storage_buckets_private` | `skip` | Skipped because Storage API is not configured. |

## Redacted JSON

```json
{
  "checked_at": "2026-05-18T08:10:01.846626+00:00",
  "checks": [
    {
      "details": {
        "expected": "ycjuzwltwbeudanjykag"
      },
      "name": "project_ref_configured",
      "status": "fail",
      "summary": "SUPABASE_PROJECT_REF is required in strict mode."
    },
    {
      "details": {
        "expected": "https://ycjuzwltwbeudanjykag.supabase.co"
      },
      "name": "url_matches_project_ref",
      "status": "fail",
      "summary": "SUPABASE_URL is missing."
    },
    {
      "details": {
        "configured": "sqlite"
      },
      "name": "db_backend",
      "status": "fail",
      "summary": "APP_DB_BACKEND must be postgres for Supabase operation."
    },
    {
      "details": {},
      "name": "database_url_configured",
      "status": "fail",
      "summary": "DATABASE_URL is missing."
    },
    {
      "details": {
        "key_type": "missing"
      },
      "name": "secret_key_configured",
      "status": "fail",
      "summary": "SUPABASE_SECRET_KEY is missing or not an elevated backend key."
    },
    {
      "details": {
        "key_type": "missing"
      },
      "name": "publishable_key_configured",
      "status": "warn",
      "summary": "SUPABASE_PUBLISHABLE_KEY presence checked."
    },
    {
      "details": {},
      "name": "firebase_write_disabled",
      "status": "pass",
      "summary": "Firebase writes are disabled."
    },
    {
      "details": {},
      "name": "firebase_read_fallback_disabled",
      "status": "pass",
      "summary": "Firebase read fallback is disabled."
    },
    {
      "details": {
        "version": "2.98.2"
      },
      "name": "supabase_cli_available",
      "status": "pass",
      "summary": "Supabase CLI is executable."
    },
    {
      "details": {
        "source": "~/.supabase/access-token"
      },
      "name": "supabase_access_token_shape",
      "status": "pass",
      "summary": "Supabase access token shape is valid."
    },
    {
      "details": {
        "error": "Invalid access token format. Must be like `sbp_0102...1920`.\nTry rerunning the command with --debug to troubleshoot the error."
      },
      "name": "supabase_project_list",
      "status": "fail",
      "summary": "Supabase CLI project list failed."
    },
    {
      "details": {
        "expected": "ycjuzwltwbeudanjykag",
        "source": "supabase/.temp/project-ref"
      },
      "name": "supabase_linked_project_ref",
      "status": "fail",
      "summary": "Supabase project is not linked locally."
    },
    {
      "details": {},
      "name": "database_connected",
      "status": "fail",
      "summary": "DATABASE_URL is missing; DB check cannot run."
    },
    {
      "details": {},
      "name": "alembic_current",
      "status": "skip",
      "summary": "Skipped because DATABASE_URL is missing."
    },
    {
      "details": {},
      "name": "required_tables_present",
      "status": "skip",
      "summary": "Skipped because DATABASE_URL is missing."
    },
    {
      "details": {},
      "name": "required_tables_rls_enabled",
      "status": "skip",
      "summary": "Skipped because DATABASE_URL is missing."
    },
    {
      "details": {},
      "name": "sensitive_role_grants",
      "status": "skip",
      "summary": "Skipped because DATABASE_URL is missing."
    },
    {
      "details": {
        "secret_key_type": "missing",
        "url_configured": false
      },
      "name": "storage_api_access",
      "status": "fail",
      "summary": "SUPABASE_URL and SUPABASE_SECRET_KEY are required for Storage verification."
    },
    {
      "details": {},
      "name": "storage_buckets_present",
      "status": "skip",
      "summary": "Skipped because Storage API is not configured."
    },
    {
      "details": {},
      "name": "storage_buckets_private",
      "status": "skip",
      "summary": "Skipped because Storage API is not configured."
    }
  ],
  "expected_url": "https://ycjuzwltwbeudanjykag.supabase.co",
  "project_ref": "ycjuzwltwbeudanjykag",
  "strict": true,
  "summary": {
    "fail": 9,
    "pass": 4,
    "skip": 6,
    "status": "fail",
    "total": 20,
    "warn": 1
  }
}
```
