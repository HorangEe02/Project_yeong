"""Feature F PLC/MES bridge contract tests."""

from __future__ import annotations

import pytest

from features.equipment.plc_adapters import (
    ALLOWED_SOURCE_SYSTEMS,
    MeasurementContractError,
    bridge_adapter_registry,
    normalize_measurement_event,
    normalize_mes_payload,
    normalize_mqtt_payload,
    normalize_opcua_payload,
    redact_bridge_config,
)


def _payload(**overrides):
    """Return a complete measurement payload for adapter tests."""

    base = {
        "ts": "2026-05-21T00:00:00Z",
        "line_id": "L01",
        "process": "cch_plate_thickness",
        "value": "3.2",
        "lot_id": "LOT-1",
        "source": "bridge",
    }
    base.update(overrides)
    return base


def test_adapter_registry_covers_allowed_source_systems() -> None:
    """Every canonical source system should have an adapter registry entry."""

    registry = bridge_adapter_registry()

    assert set(registry) == ALLOWED_SOURCE_SYSTEMS
    assert registry["opcua_bridge"]["official_reference"].startswith("https://opcfoundation.org/")
    assert registry["mqtt_bridge"]["official_reference"].startswith("https://mqtt.org/")
    assert "generic MES API" in registry["mes_adapter"]["note"]


def test_normalize_measurement_event_requires_core_fields() -> None:
    """Missing core measurement fields should fail closed before SPC ingest."""

    payload = _payload()
    payload.pop("lot_id")

    with pytest.raises(MeasurementContractError, match="lot_id"):
        normalize_measurement_event(payload)


def test_normalize_measurement_event_rejects_bad_value() -> None:
    """Non-numeric values should not enter the SPC sliding window."""

    with pytest.raises(MeasurementContractError, match="numeric"):
        normalize_measurement_event(_payload(value="not-a-number"))


def test_normalize_adapter_payloads_preserve_lineage() -> None:
    """OPC-UA, MQTT, and MES wrappers should set canonical source systems."""

    assert normalize_opcua_payload(_payload()).source_system == "opcua_bridge"
    assert normalize_mqtt_payload(_payload()).source_system == "mqtt_bridge"
    assert normalize_mes_payload(_payload()).source_system == "mes_adapter"


def test_simulator_source_maps_to_synthetic_lineage() -> None:
    """Simulator/test payloads should be clearly marked as synthetic."""

    event = normalize_measurement_event(_payload(source="simulator"))

    assert event.source_system == "plc_simulator"
    assert event.data_class == "synthetic"


def test_redact_bridge_config_masks_secret_and_endpoint_values() -> None:
    """Bridge config logging should not expose credentials or plant endpoints."""

    redacted = redact_bridge_config(
        {
            "broker_url": "mqtts://plant.example.internal",
            "username": "operator",
            "password": "secret",
            "opc_endpoint": "opc.tcp://10.0.0.10:4840",
            "line_id": "L01",
        }
    )

    assert redacted["broker_url"] == "***redacted***"
    assert redacted["password"] == "***redacted***"
    assert redacted["opc_endpoint"] == "***redacted***"
    assert redacted["line_id"] == "L01"
