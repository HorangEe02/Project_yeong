"""Agent memory service tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from lemon_ai_agent.adapters import AgentFinding, AgentInput, AgentOutput
from src.config import Settings
from src.db.tx import REQUEST_MANAGED_TX
from src.models.db.agent_memory import AgentMemory
from src.models.db.analysis_result import AnalysisResult
from src.models.db.supplement import UserSupplement, UserSupplementIngredient
from src.security.auth import AuthenticatedUser
from src.services.agent_memory import (
    AGENT_MEMORY_TYPES,
    DAILY_COACHING_MEMORY_TYPE,
    NUTRITION_ANALYSIS_MEMORY_TYPE,
    PROFILE_MEMORY_TYPE,
    SAFETY_MEMORY_TYPE,
    SUPPLEMENT_MEMORY_TYPE,
    _commit_if_possible,
    load_agent_memory_context,
    record_agent_run,
    upsert_agent_memory_record,
    upsert_daily_coaching_memory,
    upsert_nutrition_analysis_memory,
    upsert_supplement_memory,
)


class _FakeSession:
    """Minimal async session for Agent memory unit tests."""

    def __init__(self, scalar_results: list[object | None] | None = None) -> None:
        self.scalar_results = list(scalar_results or [])
        self.added: list[object] = []
        self.committed = False

    async def scalar(self, _statement: object) -> object | None:
        return self.scalar_results.pop(0) if self.scalar_results else None

    async def scalars(self, _statement: object) -> _FakeScalarResult:
        return _FakeScalarResult([item for item in self.scalar_results if item is not None])

    def add(self, record: object) -> None:
        self.added.append(record)

    async def commit(self) -> None:
        self.committed = True


class _FakeScalarResult:
    def __init__(self, records: list[object]) -> None:
        self._records = records

    def all(self) -> list[object]:
        return self._records


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(
        subject="memory-user",
        issuer="https://auth.example.com/",
        claims={"sub": "memory-user"},
    )


def _settings() -> Settings:
    return Settings(_env_file=None)


def _agent_output() -> AgentOutput:
    return AgentOutput(
        request_id="memory-test",
        user_id="memory-user",
        agent_name="daily_health_agent",
        status="completed",
        approval_status="confirmed",
        requires_user_approval=False,
        message="ok",
        findings=[
            AgentFinding(
                nutrient="Vitamin-D",
                total_amount=400,
                unit="IU",
                ratio_to_target=0.5,
                level="low",
                message="Vitamin D intake is low.",
            )
        ],
    )


def _preview_output() -> AgentOutput:
    return AgentOutput(
        request_id="preview-test",
        user_id="memory-user",
        agent_name="daily_health_agent",
        status="preview",
        approval_status="requires_confirmation",
        requires_user_approval=True,
        message="Please confirm OCR results.",
        findings=[],
        recommendations=[],
        actions=[],
    )


def _memory_record(memory_type: str, summary_json: dict[str, object]) -> AgentMemory:
    return AgentMemory(
        owner_subject_hash="owner-hash",
        memory_type=memory_type,
        summary_json=summary_json,
        source_counters={"seed": 1},
        algorithm_version="test",
    )


def test_agent_memory_type_contract_lists_four_v2_types() -> None:
    """Verify Day 2 memory taxonomy is explicit and does not replace v0 memory."""
    assert AGENT_MEMORY_TYPES == (
        "profile_memory",
        "behavior_memory",
        "conversation_memory",
        "safety_memory",
    )
    assert DAILY_COACHING_MEMORY_TYPE not in AGENT_MEMORY_TYPES


def test_upsert_agent_memory_record_stores_sanitized_v2_summary() -> None:
    """Verify v2 memory records store compact summaries without raw/internal payloads."""
    session = _FakeSession()

    memory = asyncio.run(
        upsert_agent_memory_record(
            session,
            _user(),
            _settings(),
            memory_type=SAFETY_MEMORY_TYPE,
            summary="사용자가 혈압약 복용을 언급함.",
            structured_payload={
                "medication_class": "blood_pressure_medication",
                "raw_transcript": "혈압약 먹고 있어",
                "raw_prompt": "internal prompt",
                "provider_payload": {"messages": ["hidden"]},
            },
            confidence="user_reported",
            source_kind="chat_summary",
            source_ref="chat-session-1",
            priority=8,
        )
    )

    assert memory is not None
    assert memory.memory_type == SAFETY_MEMORY_TYPE
    assert memory.summary_json == {
        "schema_version": "agent-memory-summary-v1",
        "memory_type": SAFETY_MEMORY_TYPE,
        "summary": "사용자가 혈압약 복용을 언급함.",
        "structured_payload": {
            "medication_class": "blood_pressure_medication",
        },
        "confidence": "user_reported",
        "source_kind": "chat_summary",
        "source_ref": "chat-session-1",
        "priority": 8,
        "review_after": None,
        "expires_at": None,
    }
    assert "raw_transcript" not in str(memory.summary_json)
    assert "raw_prompt" not in str(memory.summary_json)
    assert "provider_payload" not in str(memory.summary_json)
    assert "messages" not in str(memory.summary_json)
    assert memory.source_counters == {"chat_summary": 1}
    assert session.committed


def test_commit_if_possible_participates_under_request_managed_tx() -> None:
    """Under a request-managed (RLS) session, flush only — never commit.

    Committing here would drop the transaction-local RLS GUCs the request
    dependency set, so the agent-memory writes must participate (flush) and let
    the request transaction commit at dependency teardown.
    """

    class _ParticipateSession:
        def __init__(self) -> None:
            self.info = {REQUEST_MANAGED_TX: True}
            self.flushed = False
            self.committed = False

        async def flush(self) -> None:
            self.flushed = True

        async def commit(self) -> None:
            self.committed = True

    session = _ParticipateSession()
    asyncio.run(_commit_if_possible(session))

    assert session.flushed is True
    assert session.committed is False


def test_commit_if_possible_commits_legacy_session() -> None:
    """A legacy (non-request-managed) session commits as before."""

    class _LegacySession:
        def __init__(self) -> None:
            self.info: dict[str, object] = {}
            self.committed = False

        async def commit(self) -> None:
            self.committed = True

    session = _LegacySession()
    asyncio.run(_commit_if_possible(session))

    assert session.committed is True


def test_load_agent_memory_context_groups_v2_types_and_keeps_v0_summary() -> None:
    """Verify retrieval returns v2 memory bundle while preserving v0 summaries."""
    session = _FakeSession(
        [
            _memory_record(
                DAILY_COACHING_MEMORY_TYPE,
                {"schema_version": "agent-memory-summary-v1", "recent_findings": []},
            ),
            _memory_record(
                PROFILE_MEMORY_TYPE,
                {
                    "schema_version": "agent-memory-summary-v1",
                    "summary": "두부를 선호함.",
                    "raw_prompt": "must be removed",
                },
            ),
            _memory_record(
                SAFETY_MEMORY_TYPE,
                {
                    "schema_version": "agent-memory-summary-v1",
                    "summary": "혈압약 복용을 언급함.",
                    "provider_payload": {"messages": ["must be removed"]},
                },
            ),
        ]
    )

    context = asyncio.run(load_agent_memory_context(session, _user(), _settings()))

    assert context["schema_version"] == "agent-memory-summary-v1"
    assert [item["memory_type"] for item in context["summaries"]] == [
        DAILY_COACHING_MEMORY_TYPE,
        PROFILE_MEMORY_TYPE,
        SAFETY_MEMORY_TYPE,
    ]
    assert context["memory_bundle"]["profile_memory"][0]["summary_json"] == {
        "schema_version": "agent-memory-summary-v1",
        "summary": "두부를 선호함.",
    }
    assert context["memory_bundle"]["safety_memory"][0]["summary_json"] == {
        "schema_version": "agent-memory-summary-v1",
        "summary": "혈압약 복용을 언급함.",
    }
    assert context["memory_bundle"]["behavior_memory"] == []
    assert context["memory_bundle"]["conversation_memory"] == []
    assert "daily_coaching" not in context["memory_bundle"]
    assert "raw_prompt" not in str(context)
    assert "provider_payload" not in str(context)
    assert "messages" not in str(context)


def test_daily_coaching_memory_uses_canonical_nutrient_schema() -> None:
    """Verify daily memory stores canonical nutrient keys and sanitized findings."""
    session = _FakeSession()
    request = AgentInput(
        request_id="memory-test",
        user_id="memory-user",
        payload={
            "date": "2026-05-19",
            "raw_ocr_text": "should not be stored",
        },
        context={
            "profile": {
                "chronic_conditions": ["hypertension"],
                "raw_llm_response": "should not be stored",
            }
        },
    )

    memory = asyncio.run(
        upsert_daily_coaching_memory(session, _user(), _settings(), request, _agent_output())
    )

    assert memory is not None
    assert memory.memory_type == DAILY_COACHING_MEMORY_TYPE
    assert memory.summary_json["schema_version"] == "agent-memory-summary-v1"
    assert memory.summary_json["repeated_nutrient_patterns"] == {"vitamin d": 1}
    assert memory.summary_json["recent_findings"] == [
        {
            "date": "2026-05-19",
            "nutrient": "vitamin d",
            "level": "low",
            "total_amount": 10.0,
            "unit": "mcg",
        }
    ]
    assert "raw_ocr_text" not in str(memory.summary_json)
    assert "raw_llm_response" not in str(memory.summary_json)
    assert session.committed


def test_preview_daily_coaching_does_not_write_memory_or_run_log() -> None:
    """Verify preview-only OCR output is not persisted to memory or run logs."""
    session = _FakeSession()
    request = AgentInput(
        request_id="preview-test",
        user_id="memory-user",
        payload={"sources": [{"source_type": "food_ocr", "user_confirmed": False}]},
    )
    output = _preview_output()

    memory = asyncio.run(
        upsert_daily_coaching_memory(session, _user(), _settings(), request, output)
    )
    run = asyncio.run(record_agent_run(session, _user(), _settings(), output))

    assert memory is None
    assert run is None
    assert session.added == []
    assert session.committed is False


def test_nutrition_analysis_memory_canonicalizes_priority_items() -> None:
    """Verify nested nutrition analysis priority items use canonical nutrient keys."""
    session = _FakeSession()
    record = AnalysisResult(
        owner_subject="issuer::memory-user",
        analysis_type="nutrition_analysis",
        algorithm_version="test",
        input_snapshot={},
        result_snapshot={
            "priority": [
                {"nutrient_name": "Vitamin-D", "status": "deficient"},
                {"nutrient": "sodium", "level": "high"},
            ],
            "raw_ocr_text": "should not be stored",
        },
    )
    record.created_at = datetime(2026, 5, 19, tzinfo=UTC)

    memory = asyncio.run(upsert_nutrition_analysis_memory(session, _user(), _settings(), record))

    assert memory is not None
    assert memory.memory_type == NUTRITION_ANALYSIS_MEMORY_TYPE
    assert memory.summary_json["schema_version"] == "agent-memory-summary-v1"
    assert memory.summary_json["repeated_nutrient_patterns"] == {
        "sodium": 1,
        "vitamin d": 1,
    }
    assert "raw_ocr_text" not in str(memory.summary_json)


def test_supplement_memory_does_not_drive_food_first_patterns() -> None:
    """Verify supplement memory stays separate from food-first nutrient patterns."""
    session = _FakeSession()
    supplement = UserSupplement(
        owner_subject="issuer::memory-user",
        display_name="Vitamin D capsule",
        user_confirmed_at=datetime(2026, 5, 19, tzinfo=UTC),
        serving_snapshot={},
        intake_schedule={},
    )
    ingredient = UserSupplementIngredient(
        display_name="Vitamin-D",
        nutrient_code="vitamin_d",
        amount=Decimal("400"),
        unit="IU",
        confidence=Decimal("1"),
        source="user_confirmed",
        sort_order=0,
    )

    memory = asyncio.run(
        upsert_supplement_memory(session, _user(), _settings(), supplement, [ingredient])
    )

    assert memory is not None
    assert memory.memory_type == SUPPLEMENT_MEMORY_TYPE
    assert "repeated_nutrient_patterns" not in memory.summary_json
    assert "recommendations" not in memory.summary_json
    assert memory.summary_json["supplement_ingredients"]["vitamin d"] == {
        "count": 1,
        "nutrient_code": "vitamin_d",
        "unit": "mcg",
        "amount_total": 10.0,
    }
