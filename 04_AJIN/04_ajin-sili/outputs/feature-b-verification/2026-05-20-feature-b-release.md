# Feature B Release Check

- Status: `warn`
- Checked at: `2026-05-20T07:07:54.042049+00:00`
- Counts: `{"pass": 3, "warn": 1, "fail": 0, "skip": 0}`
- AJIN_MAIL_MODE: `mock`
- Business signoff path: ``

## Checks

| Status | Check | Summary | Details |
| --- | --- | --- | --- |
| `pass` | `storage_ownership_smoke` | owner/admin allow, other-user deny, and missing object deny are enforced | `{"outcomes": {"owner": "allow", "admin": "allow", "other": "deny_403", "missing_object": "deny_409"}}` |
| `pass` | `mail_guard_operational_smoke` | mail guard decisions pass and real adapter remains sealed by default | `{"decisions": {"draft_block": "block_not_approved", "external_ack_required": "needs_external_ack", "external_ack_allow": "allow", "self_approval_block": "block_self_approval", "rate_limit_block": "block_rate_limit"}, "current_mode": "mock"}` |
| `pass` | `draft_template_render_smoke` | priority Draft templates render with strict sample contexts and review metadata | `{"rendered_count": 8, "templates": ["kb_8d_report", "kb_ecn", "kb_oem_email", "kb_weekly_report", "catalog_8d_report", "catalog_ecn_notice", "catalog_oem_email", "catalog_meeting_note"]}` |
| `warn` | `template_business_signoff` | automated template checks passed, but business-owner signoff remains pending | `{"required_review_scope": ["8D Report", "ECN notice", "OEM/internal mail", "weekly/meeting report"], "signoff_path": ""}` |

## Business Review Checklist

- 8D Report: confirm required fields, customer-response wording, D1-D8 section order, and attachment labels.
- ECN: confirm approval chain, effective-date wording, affected part scope, and validation plan language.
- Mail: confirm OEM/internal greeting, confidentiality footer, CC policy, and attachment recommendation labels.
- Reports: confirm weekly/meeting report headers, KPI wording, action-owner fields, and review cadence.

## References

- https://supabase.com/docs/guides/storage/security/access-control
- https://supabase.com/docs/reference/python/storage-from-createsigneduploadurl
- https://jinja.palletsprojects.com/en/stable/api/#jinja2.Environment
- https://docs.python.org/3/library/smtplib.html
