# Feature E Release Hardening Check

- Generated: `2026-05-20T08:15:14.393459+00:00`
- Overall: `warn`

## Checks

### feature_e_endpoint_surface

- Status: `pass`
- Summary: Feature E endpoint surface matches the 74-operation baseline.

```json
{
  "counts": {
    "admin": 48,
    "admin-scenarios": 9,
    "auth": 12,
    "idp": 5
  }
}
```

### cookie_csrf_wiring

- Status: `pass`
- Summary: HttpOnly access/refresh cookies and JS-readable CSRF cookie are wired.

```json
{
  "cookies": [
    "ajin_access",
    "ajin_refresh",
    "ajin_csrf"
  ],
  "paths": {
    "ajin_access": "/api",
    "ajin_csrf": "/",
    "ajin_refresh": "/api/auth"
  },
  "samesite": "lax",
  "secure_runtime": false
}
```

### frontend_browser_token_posture

- Status: `pass`
- Summary: Frontend stores only user profile metadata and uses cookie auth.

```json
{}
```

### production_auth_environment

- Status: `pass`
- Summary: Production auth/session environment gate passed or is advisory locally.

```json
{
  "AJIN_JWT_SECRET_present": false,
  "REDIS_URL_present": false,
  "SESSION_STORE": "",
  "blockers": [],
  "production_detected": false,
  "release_note": "production env not detected; runtime secret/session checks are advisory locally",
  "warnings": []
}
```

### default_account_gate

- Status: `warn`
- Summary: Active default/demo accounts found in local auth.db; production must disable them.

```json
{
  "active_default_or_demo_accounts": [
    "HR-0001",
    "QA-0001",
    "SYS-0001"
  ],
  "production_detected": false
}
```

## References

- https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
- https://pages.nist.gov/800-63-4/sp800-63b.html
- https://www.rfc-editor.org/rfc/rfc9700.html
- https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie
- https://fastapi.tiangolo.com/advanced/response-cookies/
