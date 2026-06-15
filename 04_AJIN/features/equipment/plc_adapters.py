"""Feature F PLC/MES bridge contracts.

This module does not open live PLC, OPC-UA, MQTT, or MES connections. It defines
the small, secret-safe event contract that bridge implementations must satisfy
before data is allowed into the Redis Stream/SPC ingest path.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

REQUIRED_MEASUREMENT_FIELDS = ("ts", "line_id", "process", "value", "lot_id", "source")
ALLOWED_SOURCE_SYSTEMS = {
    "opcua_bridge",
    "mqtt_bridge",
    "mes_adapter",
    "plc_ingest",
    "plc_simulator",
}
REAL_SOURCE_SYSTEMS = {"opcua_bridge", "mqtt_bridge", "mes_adapter", "plc_ingest"}
SYNTHETIC_SOURCE_SYSTEMS = {"plc_simulator"}
SENSITIVE_CONFIG_FRAGMENTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "credential",
    "cert",
    "private_key",
    "broker_url",
    "endpoint",
    "url",
    "dsn",
)


class MeasurementContractError(ValueError):
    """Raised when a bridge payload violates the Feature F measurement contract."""


@dataclass(frozen=True)
class MeasurementEvent:
    """Normalized Feature F equipment measurement event.

    Args:
        ts: Measurement timestamp. Bridges should use ISO-8601 UTC where possible.
        line_id: Production line or lane id.
        process: SPC process id.
        value: Numeric measurement value.
        lot_id: Lot id, or ``unknown`` when the upstream system cannot provide it.
        source: Source label from the incoming stream or bridge.
        source_system: Canonical source system used for lineage labels.
        equipment_id: Optional equipment id from the bridge payload.
        tag_id: Optional OPC-UA node id, MQTT topic, or MES tag reference.
        quality: Optional upstream quality code.
        unit: Optional engineering unit.
        raw_ref: Optional non-secret pointer to an upstream message.
    """

    ts: str
    line_id: str
    process: str
    value: float
    lot_id: str
    source: str
    source_system: str
    equipment_id: str = ""
    tag_id: str = ""
    quality: str = ""
    unit: str = ""
    raw_ref: str = ""

    def to_redis_fields(self) -> dict[str, str]:
        """Return a Redis Stream field map.

        Returns:
            dict[str, str]: String-only field map accepted by Redis clients.
        """

        fields = {
            "ts": self.ts,
            "line_id": self.line_id,
            "process": self.process,
            "value": f"{self.value:.12g}",
            "lot_id": self.lot_id,
            "source": self.source,
            "source_system": self.source_system,
        }
        optional = {
            "equipment_id": self.equipment_id,
            "tag_id": self.tag_id,
            "quality": self.quality,
            "unit": self.unit,
            "raw_ref": self.raw_ref,
        }
        for key, value in optional.items():
            if value:
                fields[key] = value
        return fields

    @property
    def data_class(self) -> str:
        """Return the canonical Feature F data class.

        Returns:
            str: ``real`` for live bridge sources, ``synthetic`` for simulator
            sources, otherwise ``unknown``.
        """

        if self.source_system in REAL_SOURCE_SYSTEMS:
            return "real"
        if self.source_system in SYNTHETIC_SOURCE_SYSTEMS:
            return "synthetic"
        return "unknown"


def bridge_adapter_registry() -> dict[str, dict[str, Any]]:
    """Return the configured Feature F bridge adapter registry.

    Returns:
        dict[str, dict[str, Any]]: Adapter metadata used by release verification.
    """

    return {
        "opcua_bridge": {
            "protocol": "OPC-UA",
            "canonical_bus": "Redis Stream plc:lane:{line_id}",
            "official_reference": "https://opcfoundation.org/developer-tools/specifications-unified-architecture/",
            "live_enabled_by_default": False,
        },
        "mqtt_bridge": {
            "protocol": "MQTT",
            "canonical_bus": "Redis Stream plc:lane:{line_id}",
            "official_reference": "https://mqtt.org/mqtt-specification/",
            "live_enabled_by_default": False,
        },
        "mes_adapter": {
            "protocol": "MES vendor API",
            "canonical_bus": "Redis Stream plc:lane:{line_id}",
            "official_reference": "",
            "live_enabled_by_default": False,
            "note": (
                "I cannot find the official documentation for a generic MES API; "
                "vendor-specific docs are required before live MES connector implementation."
            ),
        },
        "plc_ingest": {
            "protocol": "Redis Stream consumer",
            "canonical_bus": "Redis Stream plc:lane:{line_id}",
            "official_reference": "https://redis.io/docs/latest/commands/xreadgroup/",
            "live_enabled_by_default": True,
        },
        "plc_simulator": {
            "protocol": "local simulator",
            "canonical_bus": "Redis Stream plc:lane:{line_id}",
            "official_reference": "",
            "live_enabled_by_default": False,
        },
    }


def redact_bridge_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Redact bridge config before logging or audit emission.

    Args:
        config: Bridge configuration mapping.

    Returns:
        dict[str, Any]: Copy with secret-bearing keys redacted.
    """

    redacted: dict[str, Any] = {}
    for key, value in config.items():
        normalized = str(key).lower()
        if any(fragment in normalized for fragment in SENSITIVE_CONFIG_FRAGMENTS):
            redacted[str(key)] = "***redacted***"
        else:
            redacted[str(key)] = value
    return redacted


def normalize_source_system(payload: Mapping[str, Any], default_source_system: str = "plc_ingest") -> str:
    """Resolve the canonical source system for a measurement payload.

    Args:
        payload: Incoming bridge or Redis Stream field map.
        default_source_system: Source system to use when the payload omits one.

    Returns:
        str: Canonical source system.

    Raises:
        MeasurementContractError: If the resolved source system is not allowed.
    """

    raw = payload.get("source_system") or default_source_system
    source_system = str(raw or "").strip()
    source = str(payload.get("source") or "").strip().lower()
    if source in {"simulator", "simulation", "synthetic", "test"} and not payload.get("source_system"):
        source_system = "plc_simulator"
    if source_system not in ALLOWED_SOURCE_SYSTEMS:
        raise MeasurementContractError(f"unsupported source_system: {source_system}")
    return source_system


def normalize_measurement_event(
    payload: Mapping[str, Any],
    *,
    default_source_system: str = "plc_ingest",
) -> MeasurementEvent:
    """Validate and normalize a bridge payload.

    Args:
        payload: Incoming OPC-UA, MQTT, MES, simulator, or Redis Stream payload.
        default_source_system: Source system used when the payload omits one.

    Returns:
        MeasurementEvent: Normalized event safe for SPC ingest.

    Raises:
        MeasurementContractError: If required fields are missing or invalid.
    """

    missing = [
        field
        for field in REQUIRED_MEASUREMENT_FIELDS
        if payload.get(field) is None or str(payload.get(field)).strip() == ""
    ]
    if missing:
        raise MeasurementContractError(f"missing required fields: {', '.join(missing)}")

    try:
        value = float(str(payload.get("value")))
    except (TypeError, ValueError) as exc:
        raise MeasurementContractError("value must be numeric") from exc
    if not math.isfinite(value):
        raise MeasurementContractError("value must be finite")

    source_system = normalize_source_system(payload, default_source_system)
    return MeasurementEvent(
        ts=str(payload.get("ts") or "").strip(),
        line_id=str(payload.get("line_id") or "").strip(),
        process=str(payload.get("process") or "").strip(),
        value=value,
        lot_id=str(payload.get("lot_id") or "").strip(),
        source=str(payload.get("source") or "").strip(),
        source_system=source_system,
        equipment_id=str(payload.get("equipment_id") or "").strip(),
        tag_id=str(payload.get("tag_id") or "").strip(),
        quality=str(payload.get("quality") or "").strip(),
        unit=str(payload.get("unit") or "").strip(),
        raw_ref=str(payload.get("raw_ref") or "").strip(),
    )


def normalize_opcua_payload(payload: Mapping[str, Any]) -> MeasurementEvent:
    """Normalize an OPC-UA bridge payload.

    Args:
        payload: OPC-UA bridge payload already mapped to the common field names.

    Returns:
        MeasurementEvent: Normalized Feature F event.
    """

    return normalize_measurement_event(payload, default_source_system="opcua_bridge")


def normalize_mqtt_payload(payload: Mapping[str, Any]) -> MeasurementEvent:
    """Normalize an MQTT bridge payload.

    Args:
        payload: MQTT bridge payload already mapped to the common field names.

    Returns:
        MeasurementEvent: Normalized Feature F event.
    """

    return normalize_measurement_event(payload, default_source_system="mqtt_bridge")


def normalize_mes_payload(payload: Mapping[str, Any]) -> MeasurementEvent:
    """Normalize a vendor MES adapter payload.

    Args:
        payload: MES adapter payload already mapped to the common field names.

    Returns:
        MeasurementEvent: Normalized Feature F event.
    """

    return normalize_measurement_event(payload, default_source_system="mes_adapter")
