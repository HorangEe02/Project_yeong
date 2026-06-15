# Supabase Remote Verification

- Checked at: `2026-05-18T15:53:33.201806+00:00`
- Project ref: `ycjuzwltwbeudanjykag`
- Expected URL: `https://ycjuzwltwbeudanjykag.supabase.co`
- Strict mode: `True`
- Overall status: `pass`
- Counts: pass=22, warn=0, fail=0, skip=0

## Checks

| Check | Status | Summary |
|---|---:|---|
| `project_ref_configured` | `pass` | SUPABASE_PROJECT_REF matches. |
| `url_matches_project_ref` | `pass` | SUPABASE_URL matches project ref. |
| `db_backend` | `pass` | APP_DB_BACKEND is postgres. |
| `database_url_configured` | `pass` | DATABASE_URL is configured. |
| `secret_key_configured` | `pass` | SUPABASE_SECRET_KEY is configured for backend-only access. |
| `publishable_key_configured` | `pass` | SUPABASE_PUBLISHABLE_KEY presence checked. |
| `firebase_write_disabled` | `pass` | Firebase writes are disabled. |
| `firebase_read_fallback_disabled` | `pass` | Firebase read fallback is disabled. |
| `supabase_cli_available` | `pass` | Supabase CLI is executable. |
| `supabase_access_token_shape` | `pass` | Supabase access token shape is valid. |
| `supabase_project_list` | `pass` | Target Supabase project is visible to the CLI token. |
| `supabase_linked_project_ref` | `pass` | Local Supabase link matches project ref. |
| `database_connected` | `pass` | DATABASE_URL read-only connection succeeded. |
| `alembic_current` | `pass` | Alembic revision matches expected head. |
| `required_tables_present` | `pass` | Required public tables are present. |
| `required_tables_rls_enabled` | `pass` | RLS is enabled on required tables. |
| `sensitive_role_grants` | `pass` | No anon/authenticated/service_role grants found on sensitive public tables. |
| `data_api_deny_policies` | `pass` | Explicit deny-all Data API policies are present. |
| `default_admin_risk` | `pass` | Default admin posture is safe. |
| `storage_api_access` | `pass` | Storage API list_buckets call succeeded. |
| `storage_buckets_present` | `pass` | Required Storage buckets are present. |
| `storage_buckets_private` | `pass` | Required Storage buckets are private. |

## Redacted JSON

```json
{
  "checked_at": "2026-05-18T15:53:33.201806+00:00",
  "checks": [
    {
      "details": {},
      "name": "project_ref_configured",
      "status": "pass",
      "summary": "SUPABASE_PROJECT_REF matches."
    },
    {
      "details": {},
      "name": "url_matches_project_ref",
      "status": "pass",
      "summary": "SUPABASE_URL matches project ref."
    },
    {
      "details": {},
      "name": "db_backend",
      "status": "pass",
      "summary": "APP_DB_BACKEND is postgres."
    },
    {
      "details": {
        "database_url": "postgresql://aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres"
      },
      "name": "database_url_configured",
      "status": "pass",
      "summary": "DATABASE_URL is configured."
    },
    {
      "details": {
        "key_type": "secret"
      },
      "name": "secret_key_configured",
      "status": "pass",
      "summary": "SUPABASE_SECRET_KEY is configured for backend-only access."
    },
    {
      "details": {
        "key_type": "publishable"
      },
      "name": "publishable_key_configured",
      "status": "pass",
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
        "source": "env:SUPABASE_ACCESS_TOKEN"
      },
      "name": "supabase_access_token_shape",
      "status": "pass",
      "summary": "Supabase access token shape is valid."
    },
    {
      "details": {
        "output_format": "json",
        "project_ref": "ycjuzwltwbeudanjykag"
      },
      "name": "supabase_project_list",
      "status": "pass",
      "summary": "Target Supabase project is visible to the CLI token."
    },
    {
      "details": {
        "source": "supabase/.temp/project-ref"
      },
      "name": "supabase_linked_project_ref",
      "status": "pass",
      "summary": "Local Supabase link matches project ref."
    },
    {
      "details": {
        "database_url": "postgresql://aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres"
      },
      "name": "database_connected",
      "status": "pass",
      "summary": "DATABASE_URL read-only connection succeeded."
    },
    {
      "details": {
        "expected": "20260518_0002"
      },
      "name": "alembic_current",
      "status": "pass",
      "summary": "Alembic revision matches expected head."
    },
    {
      "details": {
        "missing": []
      },
      "name": "required_tables_present",
      "status": "pass",
      "summary": "Required public tables are present."
    },
    {
      "details": {
        "disabled": []
      },
      "name": "required_tables_rls_enabled",
      "status": "pass",
      "summary": "RLS is enabled on required tables."
    },
    {
      "details": {},
      "name": "sensitive_role_grants",
      "status": "pass",
      "summary": "No anon/authenticated/service_role grants found on sensitive public tables."
    },
    {
      "details": {
        "missing_policy": [],
        "rls_disabled": []
      },
      "name": "data_api_deny_policies",
      "status": "pass",
      "summary": "Explicit deny-all Data API policies are present."
    },
    {
      "details": {
        "active_sys_admin_count": 1,
        "blockers": [],
        "default_admin_active": false,
        "default_password_detected": false,
        "named_sys_admin_count": 1
      },
      "name": "default_admin_risk",
      "status": "pass",
      "summary": "Default admin posture is safe."
    },
    {
      "details": {},
      "name": "storage_api_access",
      "status": "pass",
      "summary": "Storage API list_buckets call succeeded."
    },
    {
      "details": {
        "missing": [],
        "required": [
          "ajin-attachments",
          "ajin-draft-exports"
        ]
      },
      "name": "storage_buckets_present",
      "status": "pass",
      "summary": "Required Storage buckets are present."
    },
    {
      "details": {
        "public_buckets": []
      },
      "name": "storage_buckets_private",
      "status": "pass",
      "summary": "Required Storage buckets are private."
    }
  ],
  "expected_url": "https://ycjuzwltwbeudanjykag.supabase.co",
  "project_ref": "ycjuzwltwbeudanjykag",
  "strict": true,
  "summary": {
    "fail": 0,
    "pass": 22,
    "skip": 0,
    "status": "pass",
    "total": 22,
    "warn": 0
  }
}
```
