from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from lemon_ai_agent.tracing import FORBIDDEN_TRACE_MARKERS, AgentTraceSpan


@dataclass(frozen=True)
class LangSmithExportConfig:
    export_enabled: bool = False
    endpoint: str = "https://api.smith.langchain.com"
    project: str = "lemon-aid-local"
    workspace_id: str = ""
    api_key: str = ""
    environment: str = "development"
    upload_allowed: bool = False

    @classmethod
    def from_env(cls, *, environment: str | None = None) -> LangSmithExportConfig:
        return cls(
            export_enabled=_env_flag("LANGSMITH_EXPORT_ENABLED"),
            endpoint=os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
            project=os.getenv("LANGSMITH_PROJECT", "lemon-aid-local"),
            workspace_id=os.getenv("LANGSMITH_WORKSPACE_ID", ""),
            api_key=os.getenv("LANGSMITH_API_KEY", ""),
            environment=environment or os.getenv("ENVIRONMENT", "development"),
            upload_allowed=_env_flag("LANGSMITH_UPLOAD_ALLOWED"),
        )


@dataclass
class LangSmithTraceExporter:
    config: LangSmithExportConfig
    client_factory: Callable[[LangSmithExportConfig], Any] | None = None

    def export(self, spans: Sequence[AgentTraceSpan]) -> dict[str, object]:
        readiness = self._readiness()
        if readiness is not None:
            return readiness
        payloads = self.build_run_payloads(spans)
        if not payloads:
            return {"status": "skipped", "exported": 0, "reason": "no spans"}
        if not self.config.upload_allowed:
            return {
                "status": "blocked",
                "exported": 0,
                "reason": "LangSmith upload is not allowed",
            }

        runtime = self._runtime()
        if isinstance(runtime, dict):
            return runtime
        client, tracing_context = runtime

        with tracing_context(enabled=True):
            for payload in payloads:
                create_run = getattr(client, "create_run", None)
                if create_run is None:
                    return {
                        "status": "unavailable",
                        "exported": 0,
                        "reason": "langsmith client does not expose create_run",
                    }
                create_run(**payload)
        return {"status": "exported", "exported": len(payloads), "reason": ""}

    def build_run_payloads(self, spans: Sequence[AgentTraceSpan]) -> list[dict[str, Any]]:
        return [_run_payload(_validated_span(span), self.config.project) for span in spans]

    def _readiness(self) -> dict[str, object] | None:
        if not self.config.export_enabled:
            return {
                "status": "disabled",
                "exported": 0,
                "reason": "LANGSMITH_EXPORT_ENABLED is false",
            }
        if self.config.environment == "production":
            return {
                "status": "blocked",
                "exported": 0,
                "reason": "LangSmith export is not allowed in production",
            }
        if not self.config.api_key:
            return {
                "status": "disabled",
                "exported": 0,
                "reason": "LANGSMITH_API_KEY is not configured",
            }
        return None

    def _build_client(self) -> Any | None:
        if self.client_factory is not None:
            return self.client_factory(self.config)
        try:
            from langsmith import Client  # noqa: PLC0415
        except ImportError:
            return None
        kwargs: dict[str, str] = {
            "api_key": self.config.api_key,
            "api_url": self.config.endpoint,
        }
        if self.config.workspace_id:
            kwargs["workspace_id"] = self.config.workspace_id
        return Client(**kwargs)

    def _tracing_context(self) -> Any | None:
        try:
            from langsmith import tracing_context  # noqa: PLC0415
        except ImportError:
            return None
        return tracing_context

    def _runtime(self) -> tuple[Any, Any] | dict[str, object]:
        client = self._build_client()
        if client is None:
            return {
                "status": "unavailable",
                "exported": 0,
                "reason": "langsmith SDK is not installed",
            }

        tracing_context = self._tracing_context()
        if tracing_context is None:
            return {
                "status": "unavailable",
                "exported": 0,
                "reason": "langsmith tracing_context is not available",
            }
        return client, tracing_context


def _env_flag(name: str) -> bool:
    return os.getenv(name, "false").casefold() in {"1", "true", "yes", "on"}


def _run_payload(span: AgentTraceSpan, project: str) -> dict[str, Any]:
    payload = {
        "name": span.span_name,
        "run_type": "chain",
        "inputs": {
            "request_id": span.request_id,
            "claim_ids": list(span.claim_ids),
            "source_ids": list(span.source_ids),
        },
        "outputs": {
            "answerability": span.answerability,
            "retrieval_status": span.retrieval_status,
            "renderer_route": span.renderer_route,
            "boundary_code": span.boundary_code,
            "provider": span.provider,
            "warning_codes": list(span.warning_codes),
            "passed": span.passed,
            "raw_fields_stored": False,
        },
        "metadata": {
            "latency_ms": span.latency_ms,
            "project": project,
        },
    }
    _assert_payload_is_sanitized(payload)
    return payload


def _validated_span(span: AgentTraceSpan) -> AgentTraceSpan:
    if not isinstance(span, AgentTraceSpan):
        raise ValueError("invalid LangSmith trace span")
    return span


def _assert_payload_is_sanitized(payload: dict[str, Any]) -> None:
    serialized = str(payload).casefold()
    if any(marker in serialized for marker in FORBIDDEN_TRACE_MARKERS):
        raise ValueError("forbidden trace marker in LangSmith payload")
