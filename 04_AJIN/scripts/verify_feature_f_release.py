#!/usr/bin/env python3
"""Verify Feature F equipment/SPC release hardening posture.

The verifier is secret-safe. It checks the OpenAPI surface, Redis stream
contract, PLC ingest to live-alarm persistence wiring, `/equipment/field`
offline queue wiring, and Feature F RBAC hardening. Actual OPC-UA bridge
connectivity is a warning by default and becomes a blocker only with
``--require-live-plc``.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DOC_REFERENCES = (
    "https://redis.io/docs/latest/commands/xreadgroup/",
    "https://mqtt.org/mqtt-specification/",
    "https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API",
    "https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API",
    "https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest",
    "https://opcfoundation.org/developer-tools/specifications-unified-architecture/",
)
HTTP_METHODS = {"get", "put", "post", "delete", "patch", "options", "head"}
EXPECTED_ENDPOINT_COUNTS = {"equipment": 19, "live-alarms": 2}
REQUIRED_ROUTES: Mapping[str, set[str]] = {
    "/api/equipment/dashboard/overview": {"get"},
    "/api/equipment/headline": {"get"},
    "/api/equipment/spc/{process_id}": {"get"},
    "/api/equipment/spc/violations/recent": {"get"},
    "/api/equipment/spc/upload-csv": {"post"},
    "/api/equipment/inspection/checklist/{equipment_type}": {"get"},
    "/api/equipment/inspection/upload-csv": {"post"},
    "/api/equipment/inspection/submit": {"post"},
    "/api/equipment/inspection/ingest-log/recent": {"get"},
    "/api/equipment/plc/status": {"get"},
    "/api/equipment/drawing/{drawing_id}/ocr": {"post"},
    "/api/live-alarms/recent": {"get"},
    "/api/live-alarms/{alarm_id}/ack": {"post"},
}
PLC_REQUIRED_FIELDS = ("ts", "line_id", "process", "value", "lot_id", "source")


@dataclass(frozen=True)
class CheckResult:
    """Single Feature F release check result.

    Args:
        name: Stable machine-readable check name.
        status: One of pass, warn, fail, or skip.
        summary: Human-readable secret-safe summary.
        details: Optional secret-safe metadata.
    """

    name: str
    status: str
    summary: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable check.

        Returns:
            dict[str, Any]: Result fields for reports.
        """

        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class FeatureFConfig:
    """Runtime configuration for the Feature F verifier.

    Args:
        root: Repository root.
        openapi_path: OpenAPI JSON path.
        strict: Whether fail checks should return a non-zero exit code.
        require_live_plc: Whether actual PLC runtime health is a blocker.
    """

    root: Path = ROOT
    openapi_path: Path = ROOT / "docs" / "openapi.json"
    strict: bool = False
    require_live_plc: bool = False


def _load_openapi(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _count_operations_by_tag(openapi: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in openapi.get("paths", {}).values():
        if not isinstance(item, Mapping):
            continue
        for method, operation in item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, Mapping):
                continue
            for tag in operation.get("tags", []):
                counts[str(tag)] = counts.get(str(tag), 0) + 1
    return counts


def verify_endpoint_surface(config: FeatureFConfig) -> CheckResult:
    """Verify Feature F OpenAPI tag counts and required route methods."""

    openapi = _load_openapi(config.openapi_path)
    counts = _count_operations_by_tag(openapi)
    paths = openapi.get("paths", {})
    missing_counts = {
        tag: {"expected": expected, "actual": counts.get(tag, 0)}
        for tag, expected in EXPECTED_ENDPOINT_COUNTS.items()
        if counts.get(tag, 0) != expected
    }
    missing_required: dict[str, list[str]] = {}
    for route, methods in REQUIRED_ROUTES.items():
        operations = paths.get(route, {})
        present = {m for m in operations.keys() if m.lower() in HTTP_METHODS}
        missing = sorted(methods - present)
        if missing:
            missing_required[route] = missing

    if missing_counts or missing_required:
        return CheckResult(
            "feature_f_endpoint_surface",
            "fail",
            "Feature F endpoint surface does not match the release baseline.",
            {
                "counts": {tag: counts.get(tag, 0) for tag in EXPECTED_ENDPOINT_COUNTS},
                "missing_counts": missing_counts,
                "missing_required": missing_required,
            },
        )
    return CheckResult(
        "feature_f_endpoint_surface",
        "pass",
        "Feature F endpoint surface matches the 21-operation baseline.",
        {"counts": {tag: counts.get(tag, 0) for tag in EXPECTED_ENDPOINT_COUNTS}},
    )


def verify_plc_contract(config: FeatureFConfig) -> CheckResult:
    """Verify Redis stream payload contract and ingest-to-alarm wiring."""

    del config
    from features.equipment import plc_ingest
    from features.equipment.spc_realtime import NelsonViolation

    sample = {
        "ts": "2026-05-20T00:00:00Z",
        "line_id": "L01",
        "process": "cch_plate_thickness",
        "value": "3.200000",
        "lot_id": "LOT-F-001",
        "source": "simulator",
    }
    missing = [field for field in PLC_REQUIRED_FIELDS if field not in sample]
    messages = [
        {
            **sample,
            "ts": f"2026-05-20T00:00:{i:02d}Z",
            "value": f"{3.2 + ((i % 5) - 2) * 0.01:.6f}",
        }
        for i in range(12)
    ]
    stats = plc_ingest.process_batch(messages, on_violation=lambda *_args: None)

    violation = NelsonViolation(
        rule_number=1,
        rule_name="Beyond 3 sigma",
        description="3 sigma breach",
        violating_indices=[11],
        severity="critical",
        recommended_action="Stop and inspect line",
    )
    alarm = plc_ingest.violation_to_alarm(
        violation,
        process="cch_plate_thickness",
        line_id="L01",
        lot_id="LOT-F-001",
        violation_id="plc-test-violation",
    )
    consume_src = inspect.getsource(plc_ingest.consume)
    persist_src = inspect.getsource(plc_ingest._persist_and_push)
    required_markers = {
        "xreadgroup": "xreadgroup" in consume_src,
        "xack": "xack" in consume_src,
        "insert_violation": "insert_violation" in persist_src,
        "insert_alarm": "insert_alarm" in persist_src,
        "domain_equipment": 'domain="equipment"' in persist_src,
        "source_system_lineage": 'source_system: str = "plc_ingest"' in persist_src
        and "source_system=source_system" in persist_src,
        "alarm_source": alarm.get("source") == "plc_ingest",
        "alarm_type": alarm.get("type") == "spc_violation",
    }
    failed_markers = [name for name, ok in required_markers.items() if not ok]
    if missing or stats.get("messages") != len(messages) or failed_markers:
        return CheckResult(
            "feature_f_plc_contract",
            "fail",
            "PLC stream contract or persistence wiring is incomplete.",
            {
                "required_fields": list(PLC_REQUIRED_FIELDS),
                "missing_sample_fields": missing,
                "batch_stats": stats,
                "failed_markers": failed_markers,
            },
        )

    return CheckResult(
        "feature_f_plc_contract",
        "pass",
        "PLC stream payload, simulator batch path, and live-alarm persistence contract are wired.",
        {
            "required_fields": list(PLC_REQUIRED_FIELDS),
            "batch_stats": stats,
            "markers": sorted(required_markers),
        },
    )


def verify_adapter_registry(config: FeatureFConfig) -> CheckResult:
    """Verify OPC-UA/MQTT/MES adapters use the common measurement contract."""

    del config
    from features.equipment import plc_adapters

    registry = plc_adapters.bridge_adapter_registry()
    required_sources = {
        "opcua_bridge",
        "mqtt_bridge",
        "mes_adapter",
        "plc_ingest",
        "plc_simulator",
    }
    sample = {
        "ts": "2026-05-20T00:00:00Z",
        "line_id": "L01",
        "process": "cch_plate_thickness",
        "value": "3.2",
        "lot_id": "LOT-F-001",
        "source": "bridge",
    }
    normalized = {
        "opcua_bridge": plc_adapters.normalize_opcua_payload(sample).source_system,
        "mqtt_bridge": plc_adapters.normalize_mqtt_payload(sample).source_system,
        "mes_adapter": plc_adapters.normalize_mes_payload(sample).source_system,
    }
    redacted = plc_adapters.redact_bridge_config(
        {
            "broker_url": "mqtts://plant.internal",
            "opc_endpoint": "opc.tcp://10.0.0.10:4840",
            "password": "secret",
            "line_id": "L01",
        }
    )
    failed = []
    if set(registry) != required_sources:
        failed.append("registry_sources")
    if set(plc_adapters.REQUIRED_MEASUREMENT_FIELDS) != set(PLC_REQUIRED_FIELDS):
        failed.append("required_fields")
    if any(key != value for key, value in normalized.items()):
        failed.append("normalizers")
    if redacted.get("broker_url") != "***redacted***" or redacted.get("opc_endpoint") != "***redacted***":
        failed.append("redaction")
    mes_note = str(registry.get("mes_adapter", {}).get("note", ""))
    if "generic MES API" not in mes_note:
        failed.append("mes_documentation_limit")
    if failed:
        return CheckResult(
            "feature_f_adapter_registry",
            "fail",
            "Feature F bridge adapter registry or measurement contract is incomplete.",
            {"failed_markers": failed},
        )
    return CheckResult(
        "feature_f_adapter_registry",
        "pass",
        "OPC-UA/MQTT/MES adapters normalize to the shared Redis Stream measurement contract.",
        {"source_systems": sorted(registry)},
    )


def verify_offline_queue_wiring(config: FeatureFConfig) -> CheckResult:
    """Verify `/equipment/field` uses IndexedDB queue for real submit flow."""

    queue_path = config.root / "frontend/src/utils/inspectionOfflineQueue.ts"
    route_path = config.root / "frontend/src/routes/equipment-field.tsx"
    missing_files = [
        str(path.relative_to(config.root))
        for path in (queue_path, route_path)
        if not path.exists()
    ]
    queue_text = queue_path.read_text(encoding="utf-8") if queue_path.exists() else ""
    route_text = route_path.read_text(encoding="utf-8") if route_path.exists() else ""
    required_markers = {
        "indexedDB": "indexedDB" in queue_text,
        "client_uuid": "client_uuid" in queue_text,
        "queued_at": "queued_at" in queue_text,
        "retry_count": "retry_count" in queue_text,
        "last_error": "last_error" in queue_text,
        "next_retry_at": "next_retry_at" in queue_text,
        "dead_letter": "dead_letter" in queue_text,
        "max_retry": "MAX_RETRY = 5" in queue_text,
        "backoff": "10, 30, 120, 600, 1800" in queue_text,
        "http_4xx_terminal": "status >= 400 && status < 500" in queue_text,
        "enqueue_export": "export async function enqueueInspection" in queue_text,
        "flush_export": "export async function flushQueue" in queue_text,
        "pending_export": "export async function pendingCount" in queue_text,
        "field_enqueue_call": "enqueueInspection(" in route_text,
        "field_direct_submit": "submitInspection(" in route_text,
        "field_flush_call": "flushQueue(" in route_text,
        "online_listener": "addEventListener('online'" in route_text,
        "flush_result_message": "성공" in route_text and "remaining" in queue_text,
    }
    missing_markers = [name for name, ok in required_markers.items() if not ok]
    if missing_files or missing_markers:
        return CheckResult(
            "feature_f_offline_queue_wiring",
            "fail",
            "Offline queue is not connected to the field inspection submit flow.",
            {"missing_files": missing_files, "missing_markers": missing_markers},
        )
    return CheckResult(
        "feature_f_offline_queue_wiring",
        "pass",
        "`/equipment/field` direct submit, offline enqueue, retry backoff, dead-letter, pending count, and queue flush are wired.",
        {"checked_files": [str(queue_path.relative_to(config.root)), str(route_path.relative_to(config.root))]},
    )


def verify_data_lineage_wiring(config: FeatureFConfig) -> CheckResult:
    """Verify Feature F responses expose real/synthetic/system/unknown lineage."""

    schema_path = config.root / "backend/schemas/equipment.py"
    router_path = config.root / "backend/routers/equipment.py"
    frontend_types_path = config.root / "frontend/src/types/equipment.ts"
    badge_path = config.root / "frontend/src/lib/syntheticBadge.tsx"
    schema_text = schema_path.read_text(encoding="utf-8")
    router_text = router_path.read_text(encoding="utf-8")
    frontend_types = frontend_types_path.read_text(encoding="utf-8")
    badge_text = badge_path.read_text(encoding="utf-8")
    required_markers = {
        "schema_lineage_fields": "class LineageFields" in schema_text,
        "schema_data_class_vocab": 'Literal["real", "synthetic", "system", "unknown"]' in schema_text,
        "router_lineage_helper": "def _lineage_kwargs" in router_text,
        "router_demo_to_synthetic": 'normalized == "demo"' in router_text,
        "frontend_lineage_fields": "interface LineageFields" in frontend_types,
        "frontend_data_class_badge": "function DataClassBadge" in badge_text,
        "equipment_badge_usage": "DataClassBadge" in (config.root / "frontend/src/components/equipment/tabs/DashboardSubTab.tsx").read_text(encoding="utf-8"),
    }
    missing = [name for name, ok in required_markers.items() if not ok]
    if missing:
        return CheckResult(
            "feature_f_data_lineage_wiring",
            "fail",
            "Feature F data lineage labels are not consistently wired.",
            {"missing_markers": missing},
        )
    return CheckResult(
        "feature_f_data_lineage_wiring",
        "pass",
        "Feature F responses and UI expose data_class/source_system/source_label labels.",
        {"data_classes": ["real", "synthetic", "system", "unknown"]},
    )


def verify_drawing_ocr_allowlist(config: FeatureFConfig) -> CheckResult:
    """Verify drawing OCR remains drawing_id-based and allowlist-bound."""

    equipment_path = config.root / "backend/routers/equipment.py"
    equipment_text = equipment_path.read_text(encoding="utf-8")
    required_markers = {
        "default_dirs": "_DRAWING_OCR_ALLOWED_BASE_DIRS" in equipment_text,
        "env_dirs": "EQUIPMENT_DRAWING_OCR_ALLOWED_DIRS" in equipment_text,
        "resolve_check": "resolve(strict=False)" in equipment_text,
        "relative_to_check": "relative_to(base)" in equipment_text,
        "forbidden_detail": "drawing_file_forbidden" in equipment_text,
        "not_found_detail": "drawing_image_not_found" in equipment_text,
        "suffixes": '".png"' in equipment_text and '".jpg"' in equipment_text and '".jpeg"' in equipment_text,
        "drawing_id_lookup": "get_drawing(drawing_id)" in equipment_text,
    }
    missing = [name for name, ok in required_markers.items() if not ok]
    if missing:
        return CheckResult(
            "feature_f_drawing_ocr_allowlist",
            "fail",
            "Drawing OCR path allowlist hardening is incomplete.",
            {"missing_markers": missing},
        )
    return CheckResult(
        "feature_f_drawing_ocr_allowlist",
        "pass",
        "Drawing OCR is drawing_id-based and constrained to configured allowlist roots.",
        {"default_roots": ["data/equipment/drawings", "data/equipment/drawings_samples"]},
    )


def verify_rbac_wiring(config: FeatureFConfig) -> CheckResult:
    """Verify Feature F department and role-level backend guard wiring."""

    equipment_path = config.root / "backend/routers/equipment.py"
    alarms_path = config.root / "backend/routers/live_alarms.py"
    equipment_text = equipment_path.read_text(encoding="utf-8")
    alarms_text = alarms_path.read_text(encoding="utf-8")
    required_markers = {
        "guard_function": "def require_equipment_access" in equipment_text,
        "department_keywords": "EQUIPMENT_DEPARTMENT_KEYWORDS" in equipment_text,
        "department_fail": "equipment_department_required" in equipment_text,
        "level4_override": "role_level >= 4" in equipment_text,
        "read_level": "require_equipment_access(1)" in equipment_text,
        "submit_level": "require_equipment_access(2)" in equipment_text,
        "upload_level": "require_equipment_access(3)" in equipment_text,
        "live_alarm_read": "require_equipment_access(1)" in alarms_text,
        "live_alarm_ack": "require_equipment_access(3)" in alarms_text,
    }
    missing = [name for name, ok in required_markers.items() if not ok]
    if missing:
        return CheckResult(
            "feature_f_rbac_wiring",
            "fail",
            "Feature F RBAC guard wiring is incomplete.",
            {"missing_markers": missing},
        )
    return CheckResult(
        "feature_f_rbac_wiring",
        "pass",
        "Feature F endpoints use department+level RBAC with L4+ override.",
        {"allowed_department_keywords": ["생산", "품질", "자동화", "금형", "안전"]},
    )


async def _load_plc_status() -> Mapping[str, Any]:
    from backend.routers.equipment import plc_status

    response = await plc_status()
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if hasattr(response, "dict"):
        return response.dict()
    return dict(response)  # type: ignore[arg-type]


def verify_live_plc_status(config: FeatureFConfig) -> CheckResult:
    """Check live PLC bridge health when requested, otherwise record warning."""

    if not config.require_live_plc:
        return CheckResult(
            "feature_f_live_plc_bridge",
            "warn",
            "Actual OPC-UA/field PLC bridge connectivity is not required for the default release gate.",
            {"require_live_plc": False},
        )

    try:
        status = dict(asyncio.run(_load_plc_status()))
    except Exception as exc:
        return CheckResult(
            "feature_f_live_plc_bridge",
            "fail",
            "Live PLC status check failed.",
            {"error_type": type(exc).__name__},
        )

    healthy = bool(status.get("healthy"))
    active_lanes = int(status.get("active_lanes") or 0)
    age = status.get("last_message_age_sec")
    try:
        age_ok = age is not None and float(age) < 30.0
    except (TypeError, ValueError):
        age_ok = False
    source_system = str(status.get("source_system") or "unknown")
    data_class = str(status.get("data_class") or "unknown")
    source_ok = source_system in {"opcua_bridge", "mqtt_bridge", "mes_adapter", "plc_ingest"} and data_class == "real"
    if healthy and active_lanes >= 1 and age_ok and source_ok:
        return CheckResult(
            "feature_f_live_plc_bridge",
            "pass",
            "Live PLC status is healthy.",
            {"active_lanes": active_lanes, "last_message_age_sec": age, "source_system": source_system},
        )
    return CheckResult(
        "feature_f_live_plc_bridge",
        "fail",
        "Live PLC status is not healthy under --require-live-plc.",
        {
            "healthy": healthy,
            "active_lanes": active_lanes,
            "last_message_age_sec": age,
            "source_system": source_system,
            "data_class": data_class,
            "error": status.get("error"),
        },
    )


def run_verification(config: FeatureFConfig) -> list[CheckResult]:
    """Run all Feature F release checks."""

    return [
        verify_endpoint_surface(config),
        verify_plc_contract(config),
        verify_adapter_registry(config),
        verify_offline_queue_wiring(config),
        verify_data_lineage_wiring(config),
        verify_drawing_ocr_allowlist(config),
        verify_rbac_wiring(config),
        verify_live_plc_status(config),
    ]


def write_markdown(path: Path, results: list[CheckResult], config: FeatureFConfig) -> None:
    """Write a secret-safe Markdown report.

    Args:
        path: Destination Markdown path.
        results: Check results.
        config: Verifier configuration.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    status_counts = {status: sum(1 for r in results if r.status == status) for status in ("pass", "warn", "fail", "skip")}
    lines = [
        "# Feature F Release Verification",
        "",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- Strict: {config.strict}",
        f"- Require live PLC: {config.require_live_plc}",
        f"- Summary: pass={status_counts['pass']} warn={status_counts['warn']} fail={status_counts['fail']} skip={status_counts['skip']}",
        "",
        "## Checks",
        "",
    ]
    for result in results:
        lines.extend(
            [
                f"### {result.name}",
                "",
                f"- Status: `{result.status}`",
                f"- Summary: {result.summary}",
            ]
        )
        if result.details:
            lines.extend(["- Details:", ""])
            lines.append("```json")
            lines.append(json.dumps(result.details, ensure_ascii=False, indent=2, sort_keys=True))
            lines.append("```")
        lines.append("")

    lines.extend(["## Official References", ""])
    for url in DOC_REFERENCES:
        lines.append(f"- {url}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any check fails.")
    parser.add_argument("--require-live-plc", action="store_true", help="Treat live PLC unhealthy status as a failure.")
    parser.add_argument("--markdown", type=Path, help="Write a secret-safe Markdown report.")
    parser.add_argument("--json", action="store_true", help="Print JSON results.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    config = FeatureFConfig(strict=args.strict, require_live_plc=args.require_live_plc)
    results = run_verification(config)
    if args.markdown:
        write_markdown(args.markdown, results, config)
    if args.json:
        print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
    else:
        for result in results:
            print(f"[{result.status.upper()}] {result.name}: {result.summary}")
    has_fail = any(result.status == "fail" for result in results)
    return 1 if args.strict and has_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
