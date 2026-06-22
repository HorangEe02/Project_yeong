from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import ceil
from typing import Protocol

ALLOWED_TRACE_SPANS = {
    "chat_turn_plan",
    "retrieval",
    "normalization",
    "route_decision",
    "render",
    "llm_polish",
    "safety_guard",
}

FORBIDDEN_TRACE_MARKERS = (
    "raw user question",
    "raw_user_question",
    "raw question",
    "raw prompt",
    "raw_prompt",
    "raw ocr",
    "raw_ocr",
    "raw_ocr_text",
    "raw llm response",
    "raw_llm_response",
    "raw_model_output",
    "provider payload",
    "provider_payload",
    "debug trace",
    "debug_trace",
    "user health snapshot",
    "user_health_snapshot",
    "user_health_context_snapshot",
    "full_prompt",
    "messages",
    "raw_provider_payload",
    "raw_transcript",
)


@dataclass(frozen=True)
class AgentTraceSpan:
    request_id: str
    span_name: str
    answerability: str = ""
    retrieval_status: str = ""
    renderer_route: str = ""
    claim_ids: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    boundary_code: str = ""
    provider: str = ""
    latency_ms: float | None = None
    warning_codes: tuple[str, ...] = ()
    passed: bool = True
    raw_fields_stored: bool = False

    def __post_init__(self) -> None:
        if self.span_name not in ALLOWED_TRACE_SPANS:
            raise ValueError(f"forbidden trace marker: {self.span_name}")
        if self.raw_fields_stored:
            raise ValueError("raw_fields_stored must remain false")
        for value in _iter_string_values(self):
            normalized = value.casefold()
            if any(marker in normalized for marker in FORBIDDEN_TRACE_MARKERS):
                raise ValueError(f"forbidden trace marker: {value}")

    def to_public_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "span_name": self.span_name,
            "answerability": self.answerability,
            "retrieval_status": self.retrieval_status,
            "renderer_route": self.renderer_route,
            "claim_ids": list(self.claim_ids),
            "source_ids": list(self.source_ids),
            "boundary_code": self.boundary_code,
            "provider": self.provider,
            "latency_ms": self.latency_ms,
            "warning_codes": list(self.warning_codes),
            "passed": self.passed,
            "raw_fields_stored": False,
        }


class AgentTraceRecorder(Protocol):
    def record(self, span: AgentTraceSpan) -> None: ...


@dataclass
class NoopAgentTraceRecorder:
    @property
    def spans(self) -> tuple[AgentTraceSpan, ...]:
        return ()

    def record(self, _span: AgentTraceSpan) -> None:
        return None


@dataclass
class InMemoryAgentTraceRecorder:
    _spans: list[AgentTraceSpan] = field(default_factory=list)

    @property
    def spans(self) -> tuple[AgentTraceSpan, ...]:
        return tuple(self._spans)

    def record(self, span: AgentTraceSpan) -> None:
        self._spans.append(span)


@dataclass
class StructuredLogAgentTraceRecorder:
    logger: logging.Logger = field(
        default_factory=lambda: logging.getLogger("lemon_ai_agent.trace")
    )

    def record(self, span: AgentTraceSpan) -> None:
        self.logger.info(
            "agent_trace_span %s",
            json.dumps(span.to_public_dict(), ensure_ascii=False, sort_keys=True),
        )


@dataclass(frozen=True)
class RuntimeMetricThresholds:
    answerability_unknown_rate: float = 0.3
    llm_polish_fallback_rate: float = 0.1
    retrieval_no_match_rate: float = 0.3
    unsafe_polish_fallback_count: int = 1
    source_stale_count: int = 1
    p95_chat_latency_ms: float | None = None


DEFAULT_RUNTIME_METRIC_THRESHOLDS = RuntimeMetricThresholds()


@dataclass
class StructuredLogRuntimeMetricsReporter:
    logger: logging.Logger = field(
        default_factory=lambda: logging.getLogger("lemon_ai_agent.runtime_metrics")
    )
    thresholds: RuntimeMetricThresholds = DEFAULT_RUNTIME_METRIC_THRESHOLDS

    def emit(self, spans: Sequence[AgentTraceSpan]) -> dict[str, object]:
        report = build_runtime_metrics_report(spans)
        alert_codes = evaluate_runtime_metric_alerts(report, self.thresholds)
        log_level = logging.WARNING if alert_codes else logging.INFO
        self.logger.log(
            log_level,
            "agent_runtime_metrics %s",
            json.dumps(
                {"alert_codes": list(alert_codes), "report": report},
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        return report


def build_runtime_metrics_report(
    spans: Sequence[AgentTraceSpan],
) -> dict[str, object]:
    validated_spans = tuple(_validated_span(span) for span in spans)
    spans_by_request: dict[str, list[AgentTraceSpan]] = defaultdict(list)
    latency_values: list[float] = []
    for span in validated_spans:
        spans_by_request[span.request_id].append(span)
        if span.latency_ms is not None:
            latency_values.append(span.latency_ms)

    request_count = len(spans_by_request)
    if request_count == 0:
        return {
            "request_count": 0,
            "answerability_unknown_rate": 0.0,
            "boundary_rate_by_code": {},
            "llm_polish_fallback_rate": 0.0,
            "unsafe_polish_fallback_count": 0,
            "retrieval_no_match_rate": 0.0,
            "source_stale_count": 0,
            "p95_chat_latency_ms": None,
        }

    unknown_count = 0
    retrieval_no_match_count = 0
    boundary_counts: dict[str, int] = defaultdict(int)
    llm_polish_fallback_request_ids: set[str] = set()
    unsafe_polish_fallback_request_ids: set[str] = set()
    source_stale_request_ids: set[str] = set()

    for request_id, request_spans in spans_by_request.items():
        answer_span = _selected_answer_span(request_spans)
        if answer_span.answerability == "unknown_no_reviewed_source":
            unknown_count += 1
        if any(span.retrieval_status == "no_match" for span in request_spans):
            retrieval_no_match_count += 1

        boundary_code = answer_span.boundary_code or _first_boundary_code(request_spans)
        if boundary_code:
            boundary_counts[boundary_code] += 1

        warning_codes = {
            warning_code for span in request_spans for warning_code in span.warning_codes
        }
        if any(_is_llm_polish_fallback_warning(code) for code in warning_codes) or any(
            span.span_name == "llm_polish" and not span.passed for span in request_spans
        ):
            llm_polish_fallback_request_ids.add(request_id)

        if "unsafe_polish_fallback" in warning_codes:
            unsafe_polish_fallback_request_ids.add(request_id)
        if any(_is_source_stale_warning(code) for code in warning_codes):
            source_stale_request_ids.add(request_id)

    return {
        "request_count": request_count,
        "answerability_unknown_rate": _rate(unknown_count, request_count),
        "boundary_rate_by_code": {
            code: _rate(count, request_count) for code, count in sorted(boundary_counts.items())
        },
        "llm_polish_fallback_rate": _rate(
            len(llm_polish_fallback_request_ids),
            request_count,
        ),
        "unsafe_polish_fallback_count": len(unsafe_polish_fallback_request_ids),
        "retrieval_no_match_rate": _rate(
            retrieval_no_match_count,
            request_count,
        ),
        "source_stale_count": len(source_stale_request_ids),
        "p95_chat_latency_ms": _nearest_rank_percentile(latency_values, 95),
    }


def evaluate_runtime_metric_alerts(
    report: dict[str, object],
    thresholds: RuntimeMetricThresholds = DEFAULT_RUNTIME_METRIC_THRESHOLDS,
) -> tuple[str, ...]:
    alert_codes: list[str] = []
    if _metric_float(report, "answerability_unknown_rate") > (
        thresholds.answerability_unknown_rate
    ):
        alert_codes.append("answerability_unknown_rate_high")
    if _metric_float(report, "llm_polish_fallback_rate") > (thresholds.llm_polish_fallback_rate):
        alert_codes.append("llm_polish_fallback_rate_high")
    if _metric_float(report, "retrieval_no_match_rate") > (thresholds.retrieval_no_match_rate):
        alert_codes.append("retrieval_no_match_rate_high")
    if _metric_int(report, "unsafe_polish_fallback_count") >= (
        thresholds.unsafe_polish_fallback_count
    ):
        alert_codes.append("unsafe_polish_fallback_present")
    if _metric_int(report, "source_stale_count") >= thresholds.source_stale_count:
        alert_codes.append("source_stale_present")

    latency_threshold = thresholds.p95_chat_latency_ms
    latency_value = report.get("p95_chat_latency_ms")
    if (
        latency_threshold is not None
        and isinstance(latency_value, int | float)
        and latency_value > latency_threshold
    ):
        alert_codes.append("p95_chat_latency_high")
    return tuple(alert_codes)


def _iter_string_values(span: AgentTraceSpan) -> tuple[str, ...]:
    values: list[str] = [
        span.request_id,
        span.span_name,
        span.answerability,
        span.retrieval_status,
        span.renderer_route,
        span.boundary_code,
        span.provider,
    ]
    values.extend(span.claim_ids)
    values.extend(span.source_ids)
    values.extend(span.warning_codes)
    return tuple(values)


def _validated_span(span: AgentTraceSpan) -> AgentTraceSpan:
    if not isinstance(span, AgentTraceSpan):
        raise TypeError("runtime metrics can only aggregate AgentTraceSpan")
    return span


def _selected_answer_span(spans: list[AgentTraceSpan]) -> AgentTraceSpan:
    for span in reversed(spans):
        if span.span_name == "render":
            return span
    for span in reversed(spans):
        if span.answerability:
            return span
    return spans[-1]


def _first_boundary_code(spans: list[AgentTraceSpan]) -> str:
    return next((span.boundary_code for span in spans if span.boundary_code), "")


def _is_llm_polish_fallback_warning(warning_code: str) -> bool:
    return warning_code in {
        "llm_client_unavailable",
        "llm_empty_response",
        "llm_generation_failed",
        "llm_polish_fallback",
        "unsafe_polish_fallback",
    }


def _is_source_stale_warning(warning_code: str) -> bool:
    return warning_code in {"source_stale", "stale_source"} or (
        "source_stale" in warning_code or "stale_source" in warning_code
    )


def _rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 4)


def _nearest_rank_percentile(values: Sequence[float], percentile: int) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    rank = max(1, ceil((percentile / 100) * len(sorted_values)))
    return sorted_values[rank - 1]


def _metric_float(report: dict[str, object], name: str) -> float:
    value = report.get(name)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _metric_int(report: dict[str, object], name: str) -> int:
    value = report.get(name)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0
