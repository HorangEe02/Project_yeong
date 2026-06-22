from __future__ import annotations

import json
import logging

import pytest
from lemon_ai_agent.agents.chatbot import ChatbotAgent
from lemon_ai_agent.chat_session import ChatbotRequest
from lemon_ai_agent.llm import FakeLLMClient
from lemon_ai_agent.tracing import (
    AgentTraceSpan,
    InMemoryAgentTraceRecorder,
    NoopAgentTraceRecorder,
    StructuredLogRuntimeMetricsReporter,
    build_runtime_metrics_report,
    evaluate_runtime_metric_alerts,
)


def test_agent_trace_span_accepts_only_sanitized_fields() -> None:
    span = AgentTraceSpan(
        request_id="req-1",
        span_name="chat_turn_plan",
        answerability="answerable_with_caution",
        retrieval_status="found",
        renderer_route="card_answer",
        claim_ids=("claim-1",),
        source_ids=("source-1",),
        boundary_code="",
        provider="deterministic",
        latency_ms=12.5,
        warning_codes=("fallback_used",),
        passed=True,
    )

    assert span.to_public_dict() == {
        "request_id": "req-1",
        "span_name": "chat_turn_plan",
        "answerability": "answerable_with_caution",
        "retrieval_status": "found",
        "renderer_route": "card_answer",
        "claim_ids": ["claim-1"],
        "source_ids": ["source-1"],
        "boundary_code": "",
        "provider": "deterministic",
        "latency_ms": 12.5,
        "warning_codes": ["fallback_used"],
        "passed": True,
        "raw_fields_stored": False,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("span_name", "raw_prompt"),
        ("warning_codes", ("raw llm response leaked",)),
        ("warning_codes", ("raw_llm_response",)),
        ("warning_codes", ("raw_user_question",)),
        ("warning_codes", ("raw_ocr_text",)),
        ("warning_codes", ("debug_trace",)),
        ("warning_codes", ("user_health_snapshot",)),
        ("source_ids", ("provider payload",)),
    ],
)
def test_agent_trace_span_rejects_forbidden_markers(field: str, value: object) -> None:
    kwargs = {
        "request_id": "req-1",
        "span_name": "chat_turn_plan",
        "answerability": "answerable",
        "retrieval_status": "found",
        "renderer_route": "card_answer",
        "claim_ids": (),
        "source_ids": (),
        "boundary_code": "",
        "provider": "deterministic",
        "latency_ms": None,
        "warning_codes": (),
        "passed": True,
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match="forbidden trace marker"):
        AgentTraceSpan(**kwargs)


def test_trace_recorder_is_disabled_by_default_noop() -> None:
    recorder = NoopAgentTraceRecorder()
    recorder.record(
        AgentTraceSpan(
            request_id="req-1",
            span_name="render",
            answerability="unknown_no_reviewed_source",
            retrieval_status="no_match",
            renderer_route="unknown",
            claim_ids=(),
            source_ids=(),
            boundary_code="",
            provider="deterministic",
            latency_ms=None,
            warning_codes=("no_reviewed_answer_card",),
            passed=True,
        )
    )

    assert recorder.spans == ()


def test_runtime_metrics_report_aggregates_safe_operational_signals() -> None:
    spans = (
        AgentTraceSpan(
            request_id="req-1",
            span_name="retrieval",
            retrieval_status="found",
            latency_ms=10.0,
        ),
        AgentTraceSpan(
            request_id="req-1",
            span_name="render",
            answerability="answerable_with_caution",
            renderer_route="card_answer",
            provider="deterministic",
            latency_ms=30.0,
        ),
        AgentTraceSpan(
            request_id="req-2",
            span_name="retrieval",
            retrieval_status="no_match",
            latency_ms=20.0,
        ),
        AgentTraceSpan(
            request_id="req-2",
            span_name="render",
            answerability="unknown_no_reviewed_source",
            renderer_route="unknown",
            warning_codes=("source_stale",),
            latency_ms=40.0,
        ),
        AgentTraceSpan(
            request_id="req-3",
            span_name="llm_polish",
            answerability="answerable_with_caution",
            provider="sglang",
            warning_codes=("unsafe_polish_fallback",),
            passed=False,
            latency_ms=100.0,
        ),
        AgentTraceSpan(
            request_id="req-3",
            span_name="render",
            answerability="answerable_with_caution",
            renderer_route="card_answer",
            provider="deterministic",
            warning_codes=("unsafe_polish_fallback",),
            latency_ms=120.0,
        ),
        AgentTraceSpan(
            request_id="req-4",
            span_name="render",
            answerability="medical_decision_boundary",
            boundary_code="medical_decision_boundary",
            latency_ms=80.0,
        ),
    )

    report = build_runtime_metrics_report(spans)

    assert report == {
        "request_count": 4,
        "answerability_unknown_rate": 0.25,
        "boundary_rate_by_code": {"medical_decision_boundary": 0.25},
        "llm_polish_fallback_rate": 0.25,
        "unsafe_polish_fallback_count": 1,
        "retrieval_no_match_rate": 0.25,
        "source_stale_count": 1,
        "p95_chat_latency_ms": 120.0,
    }
    report_text = str(report).casefold()
    assert "req-" not in report_text
    assert "claim-" not in report_text
    assert "source-" not in report_text


def test_runtime_metrics_alerts_and_structured_log_stay_sanitized(
    caplog: pytest.LogCaptureFixture,
) -> None:
    spans = (
        AgentTraceSpan(
            request_id="req-alert-1",
            span_name="render",
            answerability="unknown_no_reviewed_source",
            retrieval_status="no_match",
            claim_ids=("claim-sensitive-1",),
            source_ids=("source-sensitive-1",),
        ),
        AgentTraceSpan(
            request_id="req-alert-2",
            span_name="llm_polish",
            answerability="answerable_with_caution",
            warning_codes=("unsafe_polish_fallback",),
            passed=False,
            latency_ms=2500.0,
        ),
    )
    logger = logging.getLogger("test.agent.runtime.metrics")
    reporter = StructuredLogRuntimeMetricsReporter(logger=logger)

    with caplog.at_level(logging.WARNING, logger=logger.name):
        report = reporter.emit(spans)

    assert evaluate_runtime_metric_alerts(report) == (
        "answerability_unknown_rate_high",
        "llm_polish_fallback_rate_high",
        "retrieval_no_match_rate_high",
        "unsafe_polish_fallback_present",
    )
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
    payload = json.loads(caplog.records[0].getMessage().removeprefix("agent_runtime_metrics "))
    assert payload == {
        "alert_codes": [
            "answerability_unknown_rate_high",
            "llm_polish_fallback_rate_high",
            "retrieval_no_match_rate_high",
            "unsafe_polish_fallback_present",
        ],
        "report": report,
    }
    logged_text = caplog.records[0].getMessage().casefold()
    assert "req-alert" not in logged_text
    assert "claim-sensitive" not in logged_text
    assert "source-sensitive" not in logged_text


def test_chatbot_records_sanitized_spans_when_recorder_is_injected() -> None:
    recorder = InMemoryAgentTraceRecorder()

    response = ChatbotAgent(trace_recorder=recorder).answer(
        ChatbotRequest(
            request_id="trace-test-1",
            user_id="trace-user",
            message="리튬 복용 중인데 타우린 영양제를 같이 먹어도 돼?",
        )
    )

    assert response.answerability == "unknown_no_reviewed_source"
    assert [span.span_name for span in recorder.spans] == [
        "chat_turn_plan",
        "retrieval",
        "route_decision",
        "render",
    ]
    assert all(span.raw_fields_stored is False for span in recorder.spans)
    assert all(not span.claim_ids for span in recorder.spans)
    assert all(not span.source_ids for span in recorder.spans)


def test_chatbot_records_llm_and_safety_spans_without_raw_content() -> None:
    recorder = InMemoryAgentTraceRecorder()
    response = ChatbotAgent(
        llm_client=FakeLLMClient(
            response_text=(
                "요약\n"
                "- 제품 라벨의 마그네슘 함량과 혈압약 종류를 확인해야 합니다.\n"
                "오늘 할 일\n"
                "- 제품 라벨, 함량, 혈압약 종류, 신장 기능을 확인하세요.\n"
                "출처 기준\n"
                "- NIH ODS Magnesium Fact Sheet"
            )
        ),
        trace_recorder=recorder,
    ).answer(
        ChatbotRequest(
            request_id="trace-test-llm",
            user_id="trace-user",
            message="혈압약 먹는데 마그네슘 영양제를 같이 먹어도 돼?",
        )
    )

    assert response.provider == "fake"
    assert response.answerability == "answerable_with_caution"
    assert [span.span_name for span in recorder.spans] == [
        "chat_turn_plan",
        "retrieval",
        "llm_polish",
        "safety_guard",
        "route_decision",
        "render",
    ]
    assert all(span.raw_fields_stored is False for span in recorder.spans)
    assert all("혈압약" not in str(span.to_public_dict()) for span in recorder.spans)
    assert recorder.spans[-1].provider == "fake"
    assert recorder.spans[-1].source_ids


def test_chatbot_records_normalization_span_on_entity_resolution_path() -> None:
    recorder = InMemoryAgentTraceRecorder()

    response = ChatbotAgent(trace_recorder=recorder).answer(
        ChatbotRequest(
            request_id="trace-test-normalization",
            user_id="trace-user",
            message="혈압약 먹는데 칼슘 영양제를 같이 먹어도 돼?",
            context={
                "user_health_snapshot": {"raw_prompt": "must not leak"},
                "raw_ocr_text": "제품 라벨 원문",
                "raw_provider_payload": {"messages": ["hidden"]},
            },
        )
    )

    assert response.answerability == "needs_more_info"
    assert [span.span_name for span in recorder.spans] == [
        "chat_turn_plan",
        "retrieval",
        "normalization",
        "route_decision",
        "render",
    ]
    trace_text = str([span.to_public_dict() for span in recorder.spans]).casefold()
    assert "혈압약" not in trace_text
    assert "칼슘" not in trace_text
    assert "raw_prompt" not in trace_text
    assert "raw_ocr_text" not in trace_text
    assert "raw_provider_payload" not in trace_text
    assert "user_health_snapshot" not in trace_text
