# Feature F Release Verification

- Generated at: 2026-05-20T07:08:12.122447+00:00
- Strict: True
- Require live PLC: False
- Summary: pass=4 warn=1 fail=0 skip=0

## Checks

### feature_f_endpoint_surface

- Status: `pass`
- Summary: Feature F endpoint surface matches the 21-operation baseline.
- Details:

```json
{
  "counts": {
    "equipment": 19,
    "live-alarms": 2
  }
}
```

### feature_f_plc_contract

- Status: `pass`
- Summary: PLC stream payload, simulator batch path, and live-alarm persistence contract are wired.
- Details:

```json
{
  "batch_stats": {
    "messages": 12,
    "violations": 0
  },
  "markers": [
    "alarm_source",
    "alarm_type",
    "domain_equipment",
    "insert_alarm",
    "insert_violation",
    "source_system_plc_ingest",
    "xack",
    "xreadgroup"
  ],
  "required_fields": [
    "ts",
    "line_id",
    "process",
    "value",
    "lot_id",
    "source"
  ]
}
```

### feature_f_offline_queue_wiring

- Status: `pass`
- Summary: `/equipment/field` direct submit, offline enqueue, pending count, and queue flush are wired.
- Details:

```json
{
  "checked_files": [
    "frontend/src/utils/inspectionOfflineQueue.ts",
    "frontend/src/routes/equipment-field.tsx"
  ]
}
```

### feature_f_rbac_wiring

- Status: `pass`
- Summary: Feature F endpoints use department+level RBAC with L4+ override.
- Details:

```json
{
  "allowed_department_keywords": [
    "생산",
    "품질",
    "자동화",
    "금형",
    "안전"
  ]
}
```

### feature_f_live_plc_bridge

- Status: `warn`
- Summary: Actual OPC-UA/field PLC bridge connectivity is not required for the default release gate.
- Details:

```json
{
  "require_live_plc": false
}
```

## Official References

- https://redis.io/docs/latest/commands/xreadgroup/
- https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API
- https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest
- https://opcfoundation.org/developer-tools/specifications-unified-architecture/
