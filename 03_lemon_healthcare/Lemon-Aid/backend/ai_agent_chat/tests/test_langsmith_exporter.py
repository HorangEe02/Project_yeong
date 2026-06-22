from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import cast

import pytest
from lemon_ai_agent.langsmith_exporter import (
    LangSmithExportConfig,
    LangSmithTraceExporter,
)
from lemon_ai_agent.tracing import AgentTraceSpan


def _span() -> AgentTraceSpan:
    return AgentTraceSpan(
        request_id="req-1",
        span_name="retrieval",
        answerability="answerable_with_caution",
        retrieval_status="found",
        renderer_route="card_answer",
        claim_ids=("claim-1",),
        source_ids=("source-1",),
        boundary_code="",
        provider="deterministic",
        latency_ms=3.0,
        warning_codes=(),
        passed=True,
    )


def test_langsmith_exporter_disabled_without_flag() -> None:
    config = LangSmithExportConfig(export_enabled=False, api_key="test-key")

    result = LangSmithTraceExporter(config).export([_span()])

    assert result == {
        "status": "disabled",
        "exported": 0,
        "reason": "LANGSMITH_EXPORT_ENABLED is false",
    }


def test_langsmith_exporter_missing_api_key_disables_without_error() -> None:
    config = LangSmithExportConfig(export_enabled=True, api_key="")

    result = LangSmithTraceExporter(config).export([_span()])

    assert result == {
        "status": "disabled",
        "exported": 0,
        "reason": "LANGSMITH_API_KEY is not configured",
    }


def test_langsmith_exporter_blocks_production_export() -> None:
    config = LangSmithExportConfig(
        export_enabled=True,
        api_key="test-key",
        environment="production",
    )

    result = LangSmithTraceExporter(config).export([_span()])

    assert result == {
        "status": "blocked",
        "exported": 0,
        "reason": "LangSmith export is not allowed in production",
    }


def test_langsmith_export_payload_contains_only_sanitized_span_fields() -> None:
    config = LangSmithExportConfig(
        export_enabled=True,
        api_key="test-key",
        project="local-eval",
    )

    payloads = LangSmithTraceExporter(config).build_run_payloads([_span()])

    assert payloads == [
        {
            "name": "retrieval",
            "run_type": "chain",
            "inputs": {
                "request_id": "req-1",
                "claim_ids": ["claim-1"],
                "source_ids": ["source-1"],
            },
            "outputs": {
                "answerability": "answerable_with_caution",
                "retrieval_status": "found",
                "renderer_route": "card_answer",
                "boundary_code": "",
                "provider": "deterministic",
                "warning_codes": [],
                "passed": True,
                "raw_fields_stored": False,
            },
            "metadata": {
                "latency_ms": 3.0,
                "project": "local-eval",
            },
        }
    ]


def test_langsmith_exporter_skips_empty_spans_before_upload_gate() -> None:
    config = LangSmithExportConfig(export_enabled=True, api_key="test-key")

    result = LangSmithTraceExporter(config).export([])

    assert result == {"status": "skipped", "exported": 0, "reason": "no spans"}


def test_langsmith_exporter_blocks_upload_without_explicit_allowance() -> None:
    config = LangSmithExportConfig(export_enabled=True, api_key="test-key")

    result = LangSmithTraceExporter(config).export([_span()])

    assert result == {
        "status": "blocked",
        "exported": 0,
        "reason": "LangSmith upload is not allowed",
    }


def test_langsmith_exporter_reports_missing_sdk_when_upload_is_explicitly_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "langsmith", None)
    config = LangSmithExportConfig(
        export_enabled=True,
        api_key="test-key",
        upload_allowed=True,
    )

    result = LangSmithTraceExporter(config).export([_span()])

    assert result == {
        "status": "unavailable",
        "exported": 0,
        "reason": "langsmith SDK is not installed",
    }


def test_langsmith_exporter_rejects_invalid_span_object() -> None:
    config = LangSmithExportConfig(export_enabled=True, api_key="test-key")
    invalid_span = cast(
        AgentTraceSpan,
        SimpleNamespace(span_name="raw_prompt", request_id="req-raw"),
    )

    with pytest.raises(ValueError, match="invalid LangSmith trace span"):
        LangSmithTraceExporter(config).build_run_payloads([invalid_span])
