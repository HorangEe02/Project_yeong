"""AI Agent daily coaching API tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from lemon_ai_agent.chat_session import ChatbotResponse
from lemon_ai_agent.llm import LLMRequest, LLMResponse
from sqlalchemy.orm import Session
from src.api.v1 import ai_agent
from src.config import Settings, get_settings
from src.db.dependencies import get_async_session, get_rls_context_session
from src.main import create_app
from src.services.chatbot_wiki_rag import WikiRagAnswer
from src.services.privacy import ConsentRequiredError


class _UnavailableOllamaClient:
    """Network-free Ollama stand-in for route fallback tests."""

    provider = "ollama"
    model = "offline-test-ollama"

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Accept the production client constructor shape without opening a socket."""

    def generate(self, _request: LLMRequest) -> LLMResponse:
        """Force the app adapter through its deterministic fallback path."""
        raise RuntimeError("offline test llm")


@pytest.fixture(autouse=True)
def _disable_live_ollama_for_route_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep route tests isolated from whichever Ollama server is running locally."""
    monkeypatch.setattr(ai_agent, "OllamaClient", _UnavailableOllamaClient)
    monkeypatch.setattr(
        ai_agent,
        "load_active_user_medication_context",
        _empty_medication_context,
    )
    monkeypatch.setattr(
        ai_agent,
        "load_recent_user_food_record_context",
        _empty_food_record_context,
    )
    monkeypatch.setattr(
        ai_agent,
        "load_active_supplement_context",
        _empty_supplement_context,
    )


class _FakeChatSession:
    """Fake session supporting the route-owned RLS context managers.

    ``rls_request_transaction_allow_inner_commit`` (run_chatbot) registers an
    ``after_begin`` listener on ``sync_session`` and, at exit, commits only when
    a transaction is still open. A real (unbound) ``Session`` is a valid event
    target; no transaction ever begins on it in these route tests, so the
    listener never fires and ``in_transaction()`` stays False.
    """

    def __init__(self) -> None:
        self.sync_session = Session()
        self.info: dict[str, object] = {}

    def in_transaction(self) -> bool:
        """No real transaction is opened on this fake."""
        return False

    async def commit(self) -> None:
        """No-op commit (exit-path only fires when in_transaction())."""

    async def rollback(self) -> None:
        """No-op rollback (error-path only fires when in_transaction())."""


async def _fake_session_dependency() -> AsyncIterator[object]:
    """Yield a fake session for route tests.

    Yields:
        Fake session object.
    """
    session = _FakeChatSession()
    try:
        yield session
    finally:
        session.sync_session.close()


async def _allow_consent(*_args: object, **_kwargs: object) -> None:
    """No-op consent service for route tests.

    Args:
        *_args: Positional call arguments.
        **_kwargs: Keyword call arguments.

    Returns:
        None.
    """


async def _deny_consent(*_args: object, **_kwargs: object) -> None:
    """Raise a missing-consent service error.

    Args:
        *_args: Positional call arguments.
        **_kwargs: Keyword call arguments.

    Returns:
        None.

    Raises:
        ConsentRequiredError: Always raised for this test.
    """
    raise ConsentRequiredError("Consent is required.")


async def _record_noop_audit(*_args: object, **_kwargs: object) -> None:
    """No-op audit service for route tests.

    Args:
        *_args: Positional call arguments.
        **_kwargs: Keyword call arguments.

    Returns:
        None.
    """


async def _memory_context(*_args: object, **_kwargs: object) -> dict[str, object]:
    """Return route-level memory context for injection tests.

    Args:
        *_args: Positional call arguments.
        **_kwargs: Keyword call arguments.

    Returns:
        Sanitized Agent memory context.
    """
    return {
        "schema_version": "agent-memory-summary-v1",
        "summaries": [
            {
                "memory_type": "daily_coaching",
                "summary_json": {
                    "repeated_nutrient_patterns": {
                        "sodium": 3,
                        "protein": 2,
                    }
                },
                "source_counters": {"daily_coaching": 3},
                "algorithm_version": "agent-memory-summary-v1.0.0",
            }
        ],
        "memory_bundle": {
            "profile_memory": [
                {
                    "summary_json": {
                        "summary": "두부와 닭가슴살을 선호한다고 말함.",
                        "confidence": "user_reported",
                        "source_kind": "chat_summary",
                        "raw_prompt": "hidden prompt",
                    }
                }
            ],
            "behavior_memory": [],
            "conversation_memory": [
                {
                    "summary_json": {
                        "summary": "최근 대화에서 나트륨 조절을 우선순위로 둠.",
                        "provider_payload": {"messages": ["hidden"]},
                    }
                }
            ],
            "safety_memory": [
                {
                    "summary_json": {
                        "summary": "혈압약 복용을 사용자 보고로 언급함.",
                        "confidence": "user_reported",
                        "source_kind": "chat_summary",
                    }
                }
            ],
        },
    }


async def _empty_medication_context(*_args: object, **_kwargs: object) -> dict[str, object]:
    """Return no saved medications for route tests unless a test overrides it."""
    return {"medications": [], "medication_details": []}


async def _empty_food_record_context(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
    """Return no saved food records for route tests unless a test overrides it."""
    return []


async def _empty_supplement_context(*_args: object, **_kwargs: object) -> dict[str, object]:
    """Return no saved supplements for route tests unless a test overrides it."""
    return {"registered_supplements": [], "checked_today": []}


def _client(settings: Settings | None = None) -> TestClient:
    """Return a TestClient with the DB session dependency replaced.

    Args:
        settings: Optional settings override for route dependency injection.

    Returns:
        FastAPI test client.
    """
    app = create_app()
    # run_daily_coaching adopted get_rls_context_session; run_chatbot is still on
    # get_async_session (Phase C). Override both so this mixed router's tests yield
    # the fake session regardless of which seam a route uses.
    app.dependency_overrides[get_async_session] = _fake_session_dependency
    app.dependency_overrides[get_rls_context_session] = _fake_session_dependency
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def _payload(*, user_confirmed: bool = True, unsafe_trend: bool = False) -> dict[str, object]:
    """Return a daily coaching request payload.

    Args:
        user_confirmed: Whether the OCR source has user confirmation.
        unsafe_trend: Whether to include unsafe trend text for sanitization.

    Returns:
        JSON request payload.
    """
    trend_summary = (
        "diabetes. purchase this supplement."
        if unsafe_trend
        else "Meal score has dropped for 7 days."
    )
    return {
        "request_id": "daily-coaching-route-test",
        "user_id": "client-supplied-user",
        "context": {
            "profile": {
                "age": 52,
                "gender": "male",
                "goals": ["meal_management"],
                "chronic_conditions": ["hypertension"],
                "medications": ["blood_pressure_medication"],
            }
        },
        "payload": {
            "date": "2026-05-18",
            "sources": [
                {
                    "source_type": "food_ocr",
                    "image_id": "meal-image-1",
                    "raw_ocr_text": "instant noodles sodium 2600mg",
                    "user_confirmed": user_confirmed,
                }
            ],
            "foods": [
                {
                    "name": "instant noodles",
                    "meal_type": "lunch",
                    "serving_label": "1 bowl",
                    "nutrients": [
                        {"name": "sodium", "amount": 2600, "unit": "mg"},
                        {"name": "protein", "amount": 25, "unit": "g"},
                    ],
                }
            ],
            "supplements": [],
            "health_trends": [
                {
                    "metric": "meal_score",
                    "direction": "down",
                    "severity": "watch",
                    "summary": trend_summary,
                }
            ],
        },
    }


def _chat_payload(
    *,
    message: str = "오늘 기록을 보고 먼저 확인할 점을 알려줘.",
    preview_context: bool = False,
) -> dict[str, object]:
    """Return a chatbot request payload.

    Args:
        preview_context: Whether the request contains preview-only client context.

    Returns:
        JSON request payload.
    """
    return {
        "request_id": "chat-route-test",
        "user_id": "client-supplied-user",
        "message": message,
        "conversation": [
            {
                "role": "user",
                "content": "점심과 영양제를 입력했어.",
                "created_at": "2026-05-21T09:00:00+09:00",
            }
        ],
        "context": {
            "daily_coaching_summary": "나트륨 섭취가 반복적으로 높게 기록되었습니다.",
            "preview_only": preview_context,
            "internal_trace": "supplement totals: vitamin d=25mcg",
        },
    }


def test_daily_coaching_returns_completed_result_for_confirmed_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the route runs deterministic coaching for confirmed input."""
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)

    response = _client().post("/api/v1/ai-agent/daily-coaching", json=_payload())

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["user_id"] == "local-dev-user"
    assert body["status"] == "completed"
    assert body["approval_status"] == "confirmed"
    assert body["provider"] == "deterministic"
    assert body["debug_trace"] == []
    assert {
        "message",
        "findings",
        "recommendations",
        "safety_warnings",
        "provider",
        "used_tools",
    }.issubset(body)
    assert "오늘의 요약" in body["message"]
    assert "권장 행동" in body["message"]
    assert "참고 및 주의" in body["message"]
    assert "supplement totals" not in body["message"]
    assert "nutrition findings" not in body["message"]
    assert "Trace" not in body["message"]
    levels = {finding["nutrient"]: finding["level"] for finding in body["findings"]}
    assert levels["sodium"] == "risky"
    assert levels["protein"] == "low"
    assert "raw_ocr_text" not in str(body)


def test_daily_coaching_injects_memory_and_records_confirmed_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify route-level memory injection and confirmed persistence handoff."""
    persisted: dict[str, object] = {}

    async def _capture_memory_update(*args: object, **_kwargs: object) -> None:
        persisted["memory_request"] = args[3]
        persisted["memory_output"] = args[4]

    async def _capture_agent_run(*args: object, **_kwargs: object) -> None:
        persisted["run_output"] = args[3]

    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)
    monkeypatch.setattr(ai_agent, "upsert_daily_coaching_memory", _capture_memory_update)
    monkeypatch.setattr(ai_agent, "record_agent_run", _capture_agent_run)

    response = _client().post("/api/v1/ai-agent/daily-coaching", json=_payload())

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert "agent_memory" in body["used_tools"]
    assert any(
        "appeared 3 times" in recommendation["rationale"]
        for recommendation in body["recommendations"]
    )
    memory_request = persisted["memory_request"]
    memory_output = persisted["memory_output"]
    run_output = persisted["run_output"]
    assert memory_request.context["agent_memory"]["summaries"][0]["memory_type"] == "daily_coaching"
    assert memory_output.status == "completed"
    assert memory_output.approval_status == "confirmed"
    assert run_output.status == "completed"


def test_daily_coaching_uses_sglang_provider_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify backend route selects the SGLang client under SGLang settings."""
    captured: dict[str, object] = {}

    class _FakeSGLangClient:
        """Network-free SGLang stand-in for route dependency tests."""

        def __init__(
            self,
            *,
            model: str,
            endpoint: str,
            api_key: str | None,
            timeout: float,
        ) -> None:
            self.model = model
            captured["sglang_client"] = {
                "model": model,
                "endpoint": endpoint,
                "api_key": api_key,
                "timeout": timeout,
            }

        def generate(self, request: LLMRequest) -> LLMResponse:
            captured["llm_request"] = request
            return LLMResponse(
                text=(
                    "오늘의 요약: 현재 입력 기준으로 한 가지 영양 항목은 "
                    "주의가 필요할 수 있습니다. 권장 행동: 확인된 권장 사항을 "
                    "먼저 살펴보세요. 참고 및 주의: 의학적 판단이 필요한 경우 "
                    "전문가와 상담해 주세요."
                ),
                provider="sglang",
                model=self.model,
            )

    async def _capture_agent_run(*args: object, **kwargs: object) -> None:
        captured["run_output"] = args[3]
        captured["run_model"] = kwargs.get("model")

    settings = Settings(
        _env_file=None,
        llm_provider="sglang",
        sglang_base_url="http://127.0.0.1:30000/v1",
        sglang_model="Qwen/Qwen2.5-0.5B-Instruct",
    )
    monkeypatch.setattr(ai_agent, "SGLangClient", _FakeSGLangClient)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "record_agent_run", _capture_agent_run)

    response = _client(settings=settings).post(
        "/api/v1/ai-agent/daily-coaching",
        json=_payload(),
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["provider"] == "sglang"
    assert "오늘의 요약" in body["message"]
    assert "supplement totals" not in body["message"]
    assert "nutrition findings" not in body["message"]
    assert captured["sglang_client"] == {
        "model": "Qwen/Qwen2.5-0.5B-Instruct",
        "endpoint": "http://127.0.0.1:30000/v1",
        "api_key": None,
        "timeout": settings.ollama_timeout_sec,
    }
    assert captured["llm_request"].messages[0].role == "system"
    assert "Answer only in Korean" in captured["llm_request"].messages[0].content
    assert (
        "Do not mention or quote internal calculation logs"
        in captured["llm_request"].messages[0].content
    )
    assert "Trace summary" not in captured["llm_request"].messages[1].content
    assert captured["run_output"].provider == "sglang"
    assert captured["run_model"] == "Qwen/Qwen2.5-0.5B-Instruct"


def test_daily_coaching_returns_preview_for_unconfirmed_ocr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify unconfirmed OCR source records stop at preview state."""
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)

    response = _client().post(
        "/api/v1/ai-agent/daily-coaching",
        json=_payload(user_confirmed=False),
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "preview"
    assert body["approval_status"] == "requires_confirmation"
    assert body["requires_user_approval"] is True
    assert body["findings"] == []
    assert body["recommendations"] == []
    assert body["actions"] == []


def test_daily_coaching_preview_does_not_persist_memory_or_run_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify unconfirmed preview responses skip memory and run persistence."""
    persisted: dict[str, int] = {"memory": 0, "run": 0}

    async def _capture_memory_update(*_args: object, **_kwargs: object) -> None:
        persisted["memory"] += 1

    async def _capture_agent_run(*_args: object, **_kwargs: object) -> None:
        persisted["run"] += 1

    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "upsert_daily_coaching_memory", _capture_memory_update)
    monkeypatch.setattr(ai_agent, "record_agent_run", _capture_agent_run)

    response = _client().post(
        "/api/v1/ai-agent/daily-coaching",
        json=_payload(user_confirmed=False),
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "preview"
    assert persisted == {"memory": 0, "run": 0}


def test_daily_coaching_requires_sensitive_health_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the route fails closed without sensitive-health consent."""
    monkeypatch.setattr(ai_agent, "require_user_consent", _deny_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)

    response = _client().post("/api/v1/ai-agent/daily-coaching", json=_payload())

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"]["code"] == "consent_required"


def test_daily_coaching_sanitizes_unsafe_trend_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify unsafe trace text is not returned from the API response."""
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)

    response = _client().post(
        "/api/v1/ai-agent/daily-coaching",
        json=_payload(unsafe_trend=True),
    )

    assert response.status_code == status.HTTP_200_OK
    body_text = str(response.json())
    assert "Trace text blocked" in body_text
    assert "diabetes" not in body_text
    assert "purchase this supplement" not in body_text


def test_daily_coaching_activity_context_omits_raw_sensitive_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify activity context does not expose raw device-sensitive extras."""
    payload = _payload()
    payload["payload"]["health_trends"] = [
        {
            "metric": "activity_context",
            "direction": "up",
            "severity": "info",
            "summary": "Confirmed activity entry: 7200 steps and 34 active minutes.",
            "steps": 7200,
            "active_minutes": 34,
            "activity_energy_kcal": 220,
            "workout_type": "walk",
            "source": "manual",
            "user_confirmed": True,
            "route_location": "home to clinic",
            "blood_pressure": "120/80",
            "sleep": "7h",
        }
    ]
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)

    response = _client().post("/api/v1/ai-agent/daily-coaching", json=payload)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    body_text = str(body)
    assert body["debug_trace"] == []
    assert "route_location" not in body_text
    assert "home to clinic" not in body_text
    assert "blood_pressure" not in body_text
    assert "120/80" not in body_text
    assert "sleep" not in body_text


def test_chat_route_uses_sglang_provider_and_agent_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify chatbot route reuses the local LLM and memory context safely."""
    captured: dict[str, object] = {}

    class _FakeSGLangClient:
        """Network-free SGLang stand-in for chatbot route tests."""

        def __init__(
            self,
            *,
            model: str,
            endpoint: str,
            api_key: str | None,
            timeout: float,
        ) -> None:
            self.model = model
            captured["sglang_client"] = {
                "model": model,
                "endpoint": endpoint,
                "api_key": api_key,
                "timeout": timeout,
            }

        def generate(self, request: LLMRequest) -> LLMResponse:
            captured["llm_request"] = request
            return LLMResponse(
                text=(
                    "현재 입력 기준으로 확인된 기록을 함께 살펴봤습니다. "
                    "의학적 판단이 필요한 경우에는 전문가와 상담해 주세요. "
                    "오늘은 확정한 식사와 영양제 기록부터 점검하고 반복 패턴을 확인하세요.\n\n"
                    "출처 기준: 질병관리청 건강정보, KDRIs 영양 기준"
                ),
                provider="sglang",
                model=self.model,
            )

    settings = Settings(
        _env_file=None,
        llm_provider="sglang",
        sglang_base_url="http://127.0.0.1:30000/v1",
        sglang_model="Qwen/Qwen2.5-0.5B-Instruct",
    )
    monkeypatch.setattr(ai_agent, "SGLangClient", _FakeSGLangClient)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)

    response = _client(settings=settings).post(
        "/api/v1/ai-agent/chat",
        json=_chat_payload(),
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["request_id"] == "chat-route-test"
    assert body["provider"] == "sglang"
    assert "현재 입력 기준" in body["message"]
    assert "오늘" in body["message"]
    assert "출처 기준:" in body["message"]
    assert "agent_memory" in body["used_tools"]
    assert "knowledge_policy" in body["used_tools"]
    assert body["source_families"] == [
        "supplement_reference",
        "nutrition_reference",
    ]
    assert "supplement totals" not in body["message"]
    assert "internal_trace" not in body["message"]
    assert captured["sglang_client"]["model"] == "Qwen/Qwen2.5-0.5B-Instruct"
    assert "Answer only in Korean" in captured["llm_request"].messages[0].content
    assert "Question category:" in captured["llm_request"].messages[1].content
    assert "Allowed source families:" in captured["llm_request"].messages[1].content
    assert "Response contract:" in captured["llm_request"].messages[1].content
    assert "Internal context for grounding only" in captured["llm_request"].messages[1].content
    assert "User-reported memory context" in captured["llm_request"].messages[1].content
    assert (
        "프로필 메모리: 두부와 닭가슴살을 선호한다고 말함."
        in captured["llm_request"].messages[1].content
    )
    assert (
        "대화 요약: 최근 대화에서 나트륨 조절을 우선순위로 둠."
        in captured["llm_request"].messages[1].content
    )
    assert (
        "주의 메모리: 혈압약 복용을 사용자 보고로 언급함."
        in captured["llm_request"].messages[1].content
    )
    assert (
        "confirmed app record가 아닌 낮은 강도 참고 정보"
        in captured["llm_request"].messages[1].content
    )
    assert "internal_trace" not in captured["llm_request"].messages[1].content
    assert "supplement totals" not in captured["llm_request"].messages[1].content
    assert "summary_json" not in captured["llm_request"].messages[1].content
    assert "raw_prompt" not in captured["llm_request"].messages[1].content
    assert "provider_payload" not in captured["llm_request"].messages[1].content
    assert "hidden prompt" not in captured["llm_request"].messages[1].content


def test_chat_route_preview_context_does_not_persist_daily_coaching_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify chat preview context is not recorded as a completed coaching run."""
    persisted: dict[str, int] = {"memory": 0, "run": 0}

    async def _capture_memory_update(*_args: object, **_kwargs: object) -> None:
        persisted["memory"] += 1

    async def _capture_agent_run(*_args: object, **_kwargs: object) -> None:
        persisted["run"] += 1

    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)
    monkeypatch.setattr(ai_agent, "upsert_daily_coaching_memory", _capture_memory_update)
    monkeypatch.setattr(ai_agent, "record_agent_run", _capture_agent_run)
    monkeypatch.setattr(ai_agent, "_build_llm_client", lambda _settings: None)

    response = _client().post(
        "/api/v1/ai-agent/chat",
        json=_chat_payload(preview_context=True),
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["provider"] == "deterministic"
    assert body["requires_user_approval"] is False
    assert persisted == {"memory": 0, "run": 0}


def test_chat_route_injects_saved_user_medications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify DB-confirmed medication names are passed to the chatbot context."""
    captured: dict[str, object] = {}

    async def _medication_context(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "medications": ["amlodipine"],
            "medication_details": [
                {
                    "display_name": "amlodipine",
                    "normalized_name": "amlodipine",
                    "medication_class": "calcium_channel_blocker",
                    "condition_tags": ["hypertension"],
                    "confirmation_status": "user_confirmed",
                }
            ],
        }

    class _CapturingChatbotAgent:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def answer(self, request: object) -> ChatbotResponse:
            captured["context"] = request.context
            return ChatbotResponse(
                request_id=request.request_id,
                message="ok",
                provider="deterministic",
                used_tools=["knowledge_policy"],
                answerability="answerable_with_caution",
            )

    monkeypatch.setattr(ai_agent, "ChatbotAgent", _CapturingChatbotAgent)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)
    monkeypatch.setattr(ai_agent, "load_active_user_medication_context", _medication_context)
    monkeypatch.setattr(ai_agent, "_build_llm_client", lambda _settings: None)

    response = _client().post(
        "/api/v1/ai-agent/chat",
        json=_chat_payload(
            message="Can I take magnesium?",
        ),
    )

    assert response.status_code == status.HTTP_200_OK
    profile = captured["context"]["profile"]
    assert profile["medications"] == ["amlodipine"]
    assert profile["medication_details"][0]["display_name"] == "amlodipine"
    assert profile["medication_details"][0]["medication_class"] == "calcium_channel_blocker"
    assert "raw_question" not in str(captured["context"])
    assert "raw_ocr_text" not in str(captured["context"])


def test_chat_route_loads_user_health_context_snapshot_before_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify every chatbot call receives a sanitized app health snapshot."""
    captured: dict[str, object] = {}

    async def _medication_context(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {"medications": ["amlodipine"], "medication_details": []}

    class _CapturingChatbotAgent:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def answer(self, request: object) -> ChatbotResponse:
            captured["context"] = request.context
            return ChatbotResponse(
                request_id=request.request_id,
                message="ok",
                provider="deterministic",
                used_tools=["knowledge_policy"],
                answerability="answerable",
            )

    payload = _chat_payload(message="오늘 저녁은 어떻게 먹을까?")
    payload["context"] = {
        **payload["context"],
        "profile": {
            "goals": ["meal_management"],
            "chronic_conditions": ["hypertension"],
        },
        "latest_confirmed_entries": {
            "foods": [{"display_items": ["라면"], "meal_type": "lunch"}],
            "raw_ocr_text": "raw meal OCR",
        },
        "visible_analysis_context": {
            "last_visible_summary": "오늘 분석 대기",
            "messages": [{"role": "assistant", "content": "raw"}],
        },
    }

    monkeypatch.setattr(ai_agent, "ChatbotAgent", _CapturingChatbotAgent)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)
    monkeypatch.setattr(ai_agent, "load_active_user_medication_context", _medication_context)
    monkeypatch.setattr(ai_agent, "_build_llm_client", lambda _settings: None)

    response = _client().post("/api/v1/ai-agent/chat", json=payload)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    context = captured["context"]
    snapshot = context["user_health_context_snapshot"]
    assert "user_health_context_snapshot" in body["used_tools"]
    assert context["user_health_context_resolution"]["status"] == "sufficient"
    assert snapshot["user_profile_summary"]["chronic_conditions"] == ["hypertension"]
    assert snapshot["user_profile_summary"]["medications"] == ["amlodipine"]
    assert snapshot["recent_food_and_checklist_snapshot"]["recent_food_records"] == [
        {"display_items": ["라면"], "meal_type": "lunch"}
    ]
    assert "raw_ocr_text" not in str(snapshot)
    assert "messages" not in str(snapshot)


def test_chat_route_replaces_client_preview_food_context_with_confirmed_db_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify client preview entries cannot reach the agent as confirmed food context."""
    captured: dict[str, object] = {}

    async def _recent_food_records(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        return [
            {
                "food_record_id": "record-confirmed",
                "recorded_date": "2026-06-05",
                "meal_type": "lunch",
                "display_items": ["confirmed rice bowl"],
                "estimated_tags": ["carbohydrate_high"],
                "rough_nutrient_axes": ["carbohydrate_high"],
                "user_confirmed": True,
                "source": "manual",
            },
            {
                "food_record_id": "record-preview",
                "recorded_date": "2026-06-05",
                "meal_type": "dinner",
                "display_items": ["ocr preview noodles"],
                "estimated_tags": ["sodium_high"],
                "rough_nutrient_axes": ["sodium_high"],
                "user_confirmed": False,
                "source": "ocr_preview",
                "raw_ocr_text": "hidden OCR",
            },
        ]

    class _CapturingChatbotAgent:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def answer(self, request: object) -> ChatbotResponse:
            captured["context"] = request.context
            return ChatbotResponse(
                request_id=request.request_id,
                message="ok",
                provider="deterministic",
                used_tools=["knowledge_policy"],
                answerability="answerable",
            )

    payload = _chat_payload(message="What did I eat today?")
    payload["context"] = {
        **payload["context"],
        "latest_confirmed_entries": {
            "foods": [
                {
                    "name": "client preview ramen",
                    "meal_type": "dinner",
                    "status": "preview",
                    "raw_ocr_text": "client OCR",
                }
            ],
        },
    }

    monkeypatch.setattr(ai_agent, "ChatbotAgent", _CapturingChatbotAgent)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)
    monkeypatch.setattr(ai_agent, "load_recent_user_food_record_context", _recent_food_records)
    monkeypatch.setattr(ai_agent, "_build_llm_client", lambda _settings: None)

    response = _client().post("/api/v1/ai-agent/chat", json=payload)

    assert response.status_code == status.HTTP_200_OK
    context = captured["context"]
    snapshot = context["user_health_context_snapshot"]
    assert snapshot["recent_food_and_checklist_snapshot"]["recent_food_records"] == [
        {
            "food_record_id": "record-confirmed",
            "recorded_date": "2026-06-05",
            "meal_type": "lunch",
            "display_items": ["confirmed rice bowl"],
            "estimated_tags": ["carbohydrate_high"],
            "rough_nutrient_axes": ["carbohydrate_high"],
            "user_confirmed": True,
            "source": "manual",
        }
    ]
    assert context["latest_confirmed_entries"] == {
        "foods": [
            {
                "name": "confirmed rice bowl",
                "meal_type": "lunch",
                "recorded_date": "2026-06-05",
                "food_record_id": "record-confirmed",
            }
        ]
    }
    assert "client preview ramen" not in str(context)
    assert "ocr preview noodles" not in str(context)
    assert "raw_ocr_text" not in str(context)


def test_chat_route_limits_confirmed_db_food_context_newest_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the route never forwards an unbounded food history to the agent."""
    captured: dict[str, object] = {}

    async def _recent_food_records(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        return [
            {
                "food_record_id": f"record-{index:02d}",
                "recorded_date": f"2026-06-{index:02d}",
                "meal_type": "lunch",
                "display_items": [f"meal {index:02d}"],
                "user_confirmed": True,
                "source": "manual",
            }
            for index in range(1, 13)
        ]

    class _CapturingChatbotAgent:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def answer(self, request: object) -> ChatbotResponse:
            captured["context"] = request.context
            return ChatbotResponse(
                request_id=request.request_id,
                message="ok",
                provider="deterministic",
                used_tools=["knowledge_policy"],
                answerability="answerable",
            )

    monkeypatch.setattr(ai_agent, "ChatbotAgent", _CapturingChatbotAgent)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)
    monkeypatch.setattr(ai_agent, "load_recent_user_food_record_context", _recent_food_records)
    monkeypatch.setattr(ai_agent, "_build_llm_client", lambda _settings: None)

    response = _client().post(
        "/api/v1/ai-agent/chat",
        json=_chat_payload(message="What did I eat recently?"),
    )

    assert response.status_code == status.HTTP_200_OK
    context = captured["context"]
    snapshot = context["user_health_context_snapshot"]
    records = snapshot["recent_food_and_checklist_snapshot"]["recent_food_records"]
    assert [record["food_record_id"] for record in records] == [
        "record-12",
        "record-11",
        "record-10",
        "record-09",
        "record-08",
        "record-07",
        "record-06",
        "record-05",
        "record-04",
        "record-03",
    ]
    assert [food["food_record_id"] for food in context["latest_confirmed_entries"]["foods"]] == [
        "record-12",
        "record-11",
        "record-10",
        "record-09",
        "record-08",
        "record-07",
        "record-06",
        "record-05",
        "record-04",
        "record-03",
    ]


def test_chat_route_loads_recent_food_records_before_context_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify saved food records can satisfy specific recent meal questions."""
    captured: dict[str, object] = {}

    async def _recent_food_records(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        return [
            {
                "food_record_id": "record-1",
                "recorded_date": "2026-05-31",
                "meal_type": "lunch",
                "display_items": ["ramen"],
                "estimated_tags": ["sodium_high"],
                "rough_nutrient_axes": ["sodium_high"],
                "user_confirmed": True,
                "source": "manual",
            }
        ]

    class _CapturingChatbotAgent:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def answer(self, request: object) -> ChatbotResponse:
            captured["context"] = request.context
            return ChatbotResponse(
                request_id=request.request_id,
                message="ok",
                provider="deterministic",
                used_tools=["knowledge_policy"],
                answerability="answerable",
            )

    monkeypatch.setattr(ai_agent, "ChatbotAgent", _CapturingChatbotAgent)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)
    monkeypatch.setattr(ai_agent, "load_recent_user_food_record_context", _recent_food_records)
    monkeypatch.setattr(ai_agent, "_build_llm_client", lambda _settings: None)

    response = _client().post(
        "/api/v1/ai-agent/chat",
        json=_chat_payload(message="What food did I eat today?"),
    )

    assert response.status_code == status.HTTP_200_OK
    context = captured["context"]
    snapshot = context["user_health_context_snapshot"]
    assert context["user_health_context_resolution"]["status"] == "sufficient"
    assert (
        snapshot["recent_food_and_checklist_snapshot"]["recent_food_records"][0]["food_record_id"]
        == "record-1"
    )
    assert snapshot["recent_food_and_checklist_snapshot"]["recent_food_records"][0][
        "display_items"
    ] == ["ramen"]


def test_chat_route_marks_visible_analysis_context_stale_after_new_food_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify ask-about-this-result context is compared with latest DB records."""
    captured: dict[str, object] = {}

    async def _recent_food_records(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        return [
            {
                "food_record_id": "record-1",
                "recorded_date": "2026-05-31",
                "meal_type": "lunch",
                "display_items": ["rice"],
                "estimated_tags": [],
                "rough_nutrient_axes": [],
                "user_confirmed": True,
                "source": "manual",
            },
            {
                "food_record_id": "record-2",
                "recorded_date": "2026-05-31",
                "meal_type": "dinner",
                "display_items": ["ramen"],
                "estimated_tags": ["sodium_high"],
                "rough_nutrient_axes": ["sodium_high"],
                "user_confirmed": True,
                "source": "manual",
            },
        ]

    class _CapturingChatbotAgent:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def answer(self, request: object) -> ChatbotResponse:
            captured["context"] = request.context
            return ChatbotResponse(
                request_id=request.request_id,
                message="ok",
                provider="deterministic",
                used_tools=["knowledge_policy"],
                answerability="answerable",
            )

    payload = _chat_payload(message="이 결과로 계속 질문할게. 저녁까지 보면 어때?")
    payload["context"] = {
        **payload["context"],
        "visible_analysis_context": {
            "analysis_kind": "today_analysis",
            "visible_result_id": "analysis-1",
            "food_record_ids": ["record-1"],
        },
    }

    monkeypatch.setattr(ai_agent, "ChatbotAgent", _CapturingChatbotAgent)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)
    monkeypatch.setattr(ai_agent, "load_recent_user_food_record_context", _recent_food_records)
    monkeypatch.setattr(ai_agent, "_build_llm_client", lambda _settings: None)

    response = _client().post("/api/v1/ai-agent/chat", json=payload)

    assert response.status_code == status.HTTP_200_OK
    snapshot = captured["context"]["user_health_context_snapshot"]
    visible = snapshot["visible_analysis_context"]
    assert visible["stale"] is True
    assert visible["stale_reasons"] == ["food_record_changed_after_visible_analysis"]
    assert visible["current_food_record_ids"] == ["record-1", "record-2"]
    assert (
        snapshot["recent_food_and_checklist_snapshot"]["recent_food_records"][1]["food_record_id"]
        == "record-2"
    )


def test_chat_route_loads_confirmed_supplement_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify saved supplements are loaded as active supplement context."""
    captured: dict[str, object] = {}

    async def _active_supplement_context(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "registered_supplements": [
                {
                    "supplement_id": "supplement-1",
                    "display_name": "Vitamin D",
                    "ingredients": [
                        {
                            "display_name": "Vitamin D",
                            "nutrient_code": "vitamin_d_ug",
                            "amount": 25,
                            "unit": "ug",
                            "analysis_use": "standard_nutrient",
                        },
                        {
                            "display_name": "Herbal blend",
                            "nutrient_code": None,
                            "analysis_use": "label_only",
                        },
                    ],
                    "user_confirmed": True,
                }
            ],
            "checked_today": [],
            "policy": {
                "nutrient_code_required_for_standard_analysis": True,
                "unconfirmed_preview_excluded": True,
            },
        }

    class _CapturingChatbotAgent:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def answer(self, request: object) -> ChatbotResponse:
            captured["context"] = request.context
            return ChatbotResponse(
                request_id=request.request_id,
                message="ok",
                provider="deterministic",
                used_tools=["knowledge_policy"],
                answerability="answerable_with_caution",
            )

    monkeypatch.setattr(ai_agent, "ChatbotAgent", _CapturingChatbotAgent)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)
    monkeypatch.setattr(ai_agent, "load_active_supplement_context", _active_supplement_context)
    monkeypatch.setattr(ai_agent, "_build_llm_client", lambda _settings: None)

    response = _client().post(
        "/api/v1/ai-agent/chat",
        json=_chat_payload(message="Can I use my vitamin D supplement?"),
    )

    assert response.status_code == status.HTTP_200_OK
    snapshot = captured["context"]["user_health_context_snapshot"]
    supplement_snapshot = snapshot["active_supplement_snapshot"]
    assert supplement_snapshot["registered_supplements"][0]["supplement_id"] == "supplement-1"
    assert (
        supplement_snapshot["registered_supplements"][0]["ingredients"][0]["analysis_use"]
        == "standard_nutrient"
    )
    assert (
        supplement_snapshot["registered_supplements"][0]["ingredients"][1]["analysis_use"]
        == "label_only"
    )
    assert "raw_ocr_text" not in str(supplement_snapshot)


def test_chat_route_analysis_run_intent_requires_user_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify chatbot analysis execution intent returns CTA without persistence."""
    persisted: dict[str, int] = {"count": 0}

    async def _store_analysis(*_args: object, **_kwargs: object) -> object:
        persisted["count"] += 1
        return object()

    async def _recent_food_records(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        return [
            {
                "food_record_id": "record-1",
                "recorded_date": "2026-05-31",
                "meal_type": "lunch",
                "display_items": ["rice"],
                "estimated_tags": [],
                "rough_nutrient_axes": [],
                "user_confirmed": True,
                "source": "manual",
            }
        ]

    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)
    monkeypatch.setattr(ai_agent, "load_recent_user_food_record_context", _recent_food_records)
    monkeypatch.setattr(ai_agent, "store_app_health_analysis_result", _store_analysis)

    response = _client().post(
        "/api/v1/ai-agent/chat",
        json=_chat_payload(message="Run today's analysis"),
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["requires_user_approval"] is True
    assert body["answerability"] == "needs_more_info"
    assert body["ctas"] == ["run_or_refresh_analysis", "ask_about_this_result"]
    assert "app_health_analysis_confirmation" in body["used_tools"]
    assert persisted == {"count": 0}


def test_chat_route_returns_analysis_checklist_cta_preview_without_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify Day 05 response contract is additive and preview-only."""
    persisted: dict[str, int] = {"analysis": 0}

    async def _store_analysis(*_args: object, **_kwargs: object) -> object:
        persisted["analysis"] += 1
        return object()

    async def _recent_food_records(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        return [
            {
                "food_record_id": "record-1",
                "recorded_date": "2026-06-05",
                "meal_type": "lunch",
                "display_items": ["ramen"],
                "estimated_tags": ["sodium_high"],
                "rough_nutrient_axes": ["sodium_high", "carbohydrate_high"],
                "user_confirmed": True,
                "source": "manual",
            },
            {
                "food_record_id": "record-preview",
                "recorded_date": "2026-06-05",
                "meal_type": "dinner",
                "display_items": ["ocr preview noodles"],
                "rough_nutrient_axes": ["sodium_high"],
                "user_confirmed": False,
                "source": "ocr_preview",
                "raw_ocr_text": "hidden OCR",
            },
        ]

    class _PreviewChatbotAgent:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def answer(self, request: object) -> ChatbotResponse:
            return ChatbotResponse(
                request_id=request.request_id,
                message="현재 입력 기준으로 확인했습니다. 오늘은 기록을 먼저 확인하세요.\n\n출처 기준: 사용자 확인 기록",
                provider="deterministic",
                used_tools=["knowledge_policy"],
                answerability="answerable",
                sources=[
                    {
                        "source_id": "kdris-2025",
                        "source_family": "nutrition_reference",
                        "review_status": "reviewed",
                        "version_label": "2025",
                        "reviewed_at": "2026-05-01",
                        "expires_at": "2027-05-01",
                        "source_url": "https://example.test/kdris",
                    }
                ],
            )

    monkeypatch.setattr(ai_agent, "ChatbotAgent", _PreviewChatbotAgent)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)
    monkeypatch.setattr(ai_agent, "load_recent_user_food_record_context", _recent_food_records)
    monkeypatch.setattr(ai_agent, "store_app_health_analysis_result", _store_analysis)
    monkeypatch.setattr(ai_agent, "_build_llm_client", lambda _settings: None)

    response = _client().post(
        "/api/v1/ai-agent/chat",
        json=_chat_payload(message="오늘 분석에서 나온 내용이 궁금해"),
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["analysis_snapshot"] == {
        "today_analysis": body["today_analysis"],
        "smart_analysis": body["smart_analysis"],
    }
    assert body["today_analysis"]["schema_version"] == "today-analysis-snapshot-v1"
    assert body["smart_analysis"]["schema_version"] == "health-analysis-snapshot-v1"
    assert 1 <= len(body["checklist_candidates"]) <= 3
    assert body["ctas"] == ["run_or_refresh_analysis", "ask_about_this_result"]
    assert body["approval_preview"]["required"] is True
    assert body["approval_preview"]["side_effects"] == []
    assert body["approval_preview"]["will_persist"] is False
    assert body["approval_preview"]["will_schedule_notification"] is False
    assert body["approval_preview"]["will_add_today_practice"] is False
    assert all(
        candidate["approval_state"] == "approval_required"
        for candidate in body["checklist_candidates"]
    )
    assert all(candidate["side_effect"] == "none" for candidate in body["checklist_candidates"])
    public_text = str(body)
    assert "ocr preview noodles" not in public_text
    assert "raw_ocr_text" not in public_text
    assert "provider_payload" not in public_text
    assert "unconfirmed" not in public_text
    assert persisted == {"analysis": 0}


def test_chat_route_confirmed_analysis_run_persists_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify approved chatbot analysis runs persist through analysis_results."""
    persisted: dict[str, object] = {}

    async def _recent_food_records(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        return [
            {
                "food_record_id": "record-1",
                "recorded_date": "2026-05-31",
                "meal_type": "lunch",
                "display_items": ["rice"],
                "estimated_tags": [],
                "rough_nutrient_axes": [],
                "user_confirmed": True,
                "source": "manual",
            }
        ]

    async def _store_analysis(*args: object, **kwargs: object) -> object:
        persisted["args"] = args
        persisted["kwargs"] = kwargs
        return object()

    payload = _chat_payload(message="Run today's analysis")
    payload["context"] = {
        **payload["context"],
        "analysis_run_approval": {"analysis_kind": "today_analysis", "approved": True},
    }

    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)
    monkeypatch.setattr(ai_agent, "load_recent_user_food_record_context", _recent_food_records)
    monkeypatch.setattr(ai_agent, "store_app_health_analysis_result", _store_analysis)

    response = _client().post("/api/v1/ai-agent/chat", json=payload)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["requires_user_approval"] is False
    assert body["answerability"] == "answerable"
    assert body["ctas"] == ["ask_about_this_result"]
    assert "app_health_analysis" in body["used_tools"]
    assert persisted["kwargs"]["analysis_kind"] == "today_analysis"
    assert persisted["kwargs"]["user_confirmed"] is True
    assert persisted["kwargs"]["result_snapshot"]["score_name"] == "오늘 현재 분석 점수"


def test_chat_route_magnesium_blood_pressure_med_uses_caution_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify lower-risk medication/supplement co-use can use the bounded LLM."""
    captured: dict[str, object] = {"generate_called": False}

    class _FakeSGLangClient:
        """SGLang stand-in for medication/supplement caution questions."""

        def __init__(
            self,
            *,
            model: str,
            endpoint: str,
            api_key: str | None,
            timeout: float,
        ) -> None:
            _ = (endpoint, api_key, timeout)
            self.model = model
            captured["model"] = model

        def generate(self, request: LLMRequest) -> LLMResponse:
            captured["generate_called"] = True
            captured["llm_request"] = request
            return LLMResponse(
                text=(
                    "마그네슘은 근육·신경 기능과 관련된 영양소입니다. "
                    "혈압약을 복용 중이면 혈압약 종류와 신장 기능, 다른 영양제 중복 여부를 함께 봐야 합니다. "
                    "오늘은 제품 라벨의 마그네슘 함량과 최근 어지러움, 설사, 복통 같은 이상 증상을 확인하세요. "
                    "새 보충제 시작이나 복용량 결정은 약 이름과 제품 라벨을 가지고 약사 또는 의사에게 확인하세요.\n\n"
                    "출처 기준: KDRIs 영양 기준, MFDS 의약품 안전 정보"
                ),
                provider="sglang",
                model=self.model,
            )

    settings = Settings(
        _env_file=None,
        llm_provider="sglang",
        sglang_base_url="http://127.0.0.1:30000/v1",
        sglang_model="Qwen/Qwen2.5-0.5B-Instruct",
    )
    monkeypatch.setattr(ai_agent, "SGLangClient", _FakeSGLangClient)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)

    response = _client(settings=settings).post(
        "/api/v1/ai-agent/chat",
        json=_chat_payload(message="혈압약 먹는데 마그네슘 영양제 같이 먹어도 돼?"),
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["provider"] == "sglang"
    assert body["requires_user_approval"] is False
    assert "knowledge_policy" in body["used_tools"]
    assert body["source_families"] == [
        "supplement_reference",
        "drug_safety_boundary",
        "chronic_condition",
    ]
    assert "마그네슘" in body["message"]
    assert "제품 라벨" in body["message"]
    assert "함량" in body["message"]
    assert "혈압약 종류" in body["message"]
    assert "신장 기능" in body["message"]
    assert "어지러움" in body["message"]
    assert "설사" in body["message"]
    assert "복통" in body["message"]
    assert "약사" in body["message"]
    assert "의사" in body["message"]
    assert "먹어도 됩니다" not in body["message"]
    assert "Drug interaction boundary applied" not in body["safety_warnings"]
    assert body["answerability"] == "answerable_with_caution"
    assert any(source["source_id"] == "nih-ods-magnesium" for source in body["sources"])
    assert captured["generate_called"] is True


def test_chat_route_medical_wiki_boundary_sources_are_public_and_claim_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify route-level source details keep boundary claim metadata public-only."""

    class _BoundarySourceChatbotAgent:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def answer(self, request: object) -> ChatbotResponse:
            return ChatbotResponse(
                request_id=request.request_id,
                message="Reviewed boundary response without raw question echo.",
                provider="deterministic",
                used_tools=["medical_knowledge_retrieval"],
                answerability="medical_decision_boundary",
                sources=[
                    {
                        "source_id": "reviewed_claim_drug_interaction_boundary",
                        "source_family": "medical_wiki_claim",
                        "review_status": "reviewed",
                        "version_label": "2026-06-09",
                        "reviewed_at": "2026-06-09",
                        "expires_at": "2026-12-09",
                        "source_url": "https://example.test/claim",
                        "debug_trace": "hidden rank details",
                        "retrieval_rank": "1",
                    },
                    {
                        "source_id": "reviewed_section_supporting_context",
                        "source_family": "medical_wiki_reviewed_section",
                        "review_status": "reviewed",
                        "version_label": "2026-06-09",
                        "reviewed_at": "2026-06-09",
                        "expires_at": "2026-12-09",
                        "source_url": "https://example.test/section",
                        "raw_text": "hidden source text",
                    },
                ],
            )

    async def _fake_retriever(*_args: object, **_kwargs: object) -> object:
        return object()

    monkeypatch.setattr(ai_agent, "ChatbotAgent", _BoundarySourceChatbotAgent)
    monkeypatch.setattr(ai_agent, "build_chatbot_medical_knowledge_retriever", _fake_retriever)
    monkeypatch.setattr(ai_agent, "_build_llm_client", lambda _settings: None)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)

    response = _client().post(
        "/api/v1/ai-agent/chat",
        json=_chat_payload(message="Can I change my medication timing for grapefruit?"),
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["answerability"] == "medical_decision_boundary"
    assert body["sources"][0]["source_id"] == "reviewed_claim_drug_interaction_boundary"
    assert body["sources"][1]["source_id"] == "reviewed_section_supporting_context"
    assert {
        "source_id",
        "source_family",
        "review_status",
        "version_label",
        "reviewed_at",
        "expires_at",
        "source_url",
    }.issubset(body["sources"][0])
    public_text = str(body)
    assert "debug_trace" not in public_text
    assert "retrieval_rank" not in public_text
    assert "raw_text" not in public_text


def test_chat_route_medical_wiki_answerable_sources_are_deduped_and_public(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify answerable route source details include claim and section without raw fields."""

    class _AnswerableSourceChatbotAgent:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def answer(self, request: object) -> ChatbotResponse:
            return ChatbotResponse(
                request_id=request.request_id,
                message="Reviewed answerable response without provider payload.",
                provider="deterministic",
                used_tools=["medical_knowledge_retrieval"],
                answerability="answerable_with_caution",
                sources=[
                    {
                        "source_id": "reviewed_claim_warfarin_vitamin_k_boundary",
                        "source_family": "medical_wiki_claim",
                        "review_status": "reviewed",
                        "version_label": "2026-06-09",
                        "reviewed_at": "2026-06-09",
                        "expires_at": "2026-12-09",
                        "source_url": "https://example.test/claim",
                    },
                    {
                        "source_id": "reviewed_section_leafy_greens_consistency",
                        "source_family": "medical_wiki_reviewed_section",
                        "review_status": "reviewed",
                        "version_label": "2026-06-09",
                        "reviewed_at": "2026-06-09",
                        "expires_at": "2026-12-09",
                        "source_url": "https://example.test/section",
                        "provider_payload": "hidden",
                    },
                    {
                        "source_id": "reviewed_claim_warfarin_vitamin_k_boundary",
                        "source_family": "medical_wiki_claim",
                        "review_status": "reviewed",
                        "version_label": "2026-06-09",
                        "reviewed_at": "2026-06-09",
                        "expires_at": "2026-12-09",
                        "source_url": "https://example.test/claim",
                    },
                ],
            )

    async def _fake_retriever(*_args: object, **_kwargs: object) -> object:
        return object()

    monkeypatch.setattr(ai_agent, "ChatbotAgent", _AnswerableSourceChatbotAgent)
    monkeypatch.setattr(ai_agent, "build_chatbot_medical_knowledge_retriever", _fake_retriever)
    monkeypatch.setattr(ai_agent, "_build_llm_client", lambda _settings: None)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)

    response = _client().post(
        "/api/v1/ai-agent/chat",
        json=_chat_payload(message="Can I eat leafy greens while taking warfarin?"),
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["answerability"] == "answerable_with_caution"
    assert [source["source_id"] for source in body["sources"]] == [
        "reviewed_claim_warfarin_vitamin_k_boundary",
        "reviewed_section_leafy_greens_consistency",
    ]
    assert "provider_payload" not in str(body)


def test_chat_route_unknown_falls_back_to_wiki_rag_and_records_backlog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the unknown branch records the backlog and serves the wiki-RAG answer."""

    class _UnknownSourceChatbotAgent:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def answer(self, request: object) -> ChatbotResponse:
            return ChatbotResponse(
                request_id=request.request_id,
                message="No reviewed source is available for this topic.",
                provider="deterministic",
                used_tools=["medical_knowledge_retrieval"],
                answerability="unknown_no_reviewed_source",
                sources=[],
            )

    async def _fake_retriever(*_args: object, **_kwargs: object) -> object:
        return object()

    rag_calls: list[str] = []

    async def _fake_wiki_rag(message: str, **_kwargs: object) -> WikiRagAnswer:
        rag_calls.append(message)
        return WikiRagAnswer(
            message="WIKI-RAG로 합성한 일반 안내 답변입니다.",
            sources=[],
            answerability="answered_from_wiki",
            safety_warnings=["전문가 상담 권고 안내문."],
            provider="gemma_wiki_rag",
            used_tools=["llm_wiki_rag"],
        )

    backlog_events: list[object] = []
    raw_question = "RAW_UNREVIEWED_SUPPLEMENT_QUESTION"

    monkeypatch.setattr(ai_agent, "ChatbotAgent", _UnknownSourceChatbotAgent)
    monkeypatch.setattr(ai_agent, "build_chatbot_medical_knowledge_retriever", _fake_retriever)
    monkeypatch.setattr(ai_agent, "_build_llm_client", lambda _settings: None)
    monkeypatch.setattr(ai_agent, "answer_with_wiki_rag", _fake_wiki_rag)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)
    monkeypatch.setattr(
        ai_agent,
        "record_unknown_knowledge_event",
        lambda _session, event: backlog_events.append(event),
    )

    response = _client().post(
        "/api/v1/ai-agent/chat",
        json=_chat_payload(message=raw_question),
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["answerability"] == "answered_from_wiki"
    assert body["provider"] == "gemma_wiki_rag"
    assert body["message"] == "WIKI-RAG로 합성한 일반 안내 답변입니다."
    assert "llm_wiki_rag" in body["used_tools"]
    assert body["sources"] == []
    assert raw_question not in str(body)
    assert rag_calls == [raw_question]
    assert len(backlog_events) == 1
    assert raw_question not in str(backlog_events[0].__dict__)


def test_chat_route_unknown_question_does_not_use_generic_sglang_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify uncovered knowledge skips the generic SGLang LLM and uses the wiki-RAG path."""
    captured: dict[str, int] = {"generate_calls": 0}
    backlog_events: list[object] = []

    class _FakeSGLangClient:
        """SGLang stand-in that must not generate for unknown-source questions."""

        def __init__(
            self,
            *,
            model: str,
            endpoint: str,
            api_key: str | None,
            timeout: float,
        ) -> None:
            pass

        def generate(self, _request: LLMRequest) -> LLMResponse:
            captured["generate_calls"] += 1
            return LLMResponse(
                text="타우린은 리튬과 함께 먹어도 됩니다.",
                provider="sglang",
                model="fake",
            )

    async def _fake_wiki_rag(_message: str, **_kwargs: object) -> WikiRagAnswer:
        return WikiRagAnswer(
            message="일반 정보 안내입니다. 정확한 내용은 전문가와 상담해 주세요.",
            sources=[],
            answerability="general_fallback",
            safety_warnings=["전문가 상담 권고 안내문."],
            provider="gemma_wiki_rag",
            used_tools=["llm_wiki_rag"],
        )

    settings = Settings(
        _env_file=None,
        llm_provider="sglang",
        sglang_base_url="http://127.0.0.1:30000/v1",
        sglang_model="Qwen/Qwen2.5-0.5B-Instruct",
    )
    monkeypatch.setattr(ai_agent, "SGLangClient", _FakeSGLangClient)
    monkeypatch.setattr(ai_agent, "answer_with_wiki_rag", _fake_wiki_rag)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)
    monkeypatch.setattr(
        ai_agent,
        "record_unknown_knowledge_event",
        lambda _session, event: backlog_events.append(event),
    )

    payload = _chat_payload(message="리튬 약과 타우린 영양제 같이 먹어도 돼?")

    response = _client(settings=settings).post("/api/v1/ai-agent/chat", json=payload)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["provider"] == "gemma_wiki_rag"
    assert body["answerability"] == "general_fallback"
    assert body["message"] == "일반 정보 안내입니다. 정확한 내용은 전문가와 상담해 주세요."
    assert body["sources"] == []
    # The generic, uncited SGLang answer is never surfaced for unknown questions.
    assert "타우린은 리튬과 함께 먹어도 됩니다" not in body["message"]
    assert captured["generate_calls"] == 0
    assert len(backlog_events) == 1
    event = backlog_events[0]
    assert event.answerability == "unknown_no_reviewed_source"
    assert event.missing_topics == ["supplement_drug_interaction"]
    assert event.retrieval_status == "no_match"
    assert "리튬" not in str(event.__dict__)
    assert "타우린" not in str(event.__dict__)


def test_chat_route_production_source_gate_fails_closed_before_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify production source governance failures stop chatbot generation."""
    captured: dict[str, int] = {"build_client_calls": 0}

    async def _deny_sources(*_args: object, **_kwargs: object) -> tuple[bool, list[str]]:
        return False, ["no_reviewed_sources"]

    def _capture_llm_client(_settings: Settings) -> object:
        captured["build_client_calls"] += 1
        raise AssertionError("source readiness failure should not build LLM client")

    monkeypatch.setattr(ai_agent, "_production_medical_source_gate", _deny_sources)
    monkeypatch.setattr(ai_agent, "_build_llm_client", _capture_llm_client)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)

    response = _client().post("/api/v1/ai-agent/chat", json=_chat_payload())

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["provider"] == "deterministic"
    assert body["answerability"] == "unknown_no_reviewed_source"
    assert body["sources"] == []
    assert body["source_families"] == []
    assert body["used_tools"] == ["medical_source_readiness"]
    assert "no_reviewed_sources" in body["safety_warnings"]
    assert "검수된 의료 지식 출처가 준비되지 않아 답변할 수 없습니다" in body["message"]
    assert captured["build_client_calls"] == 0


def test_chat_route_escalation_boundaries_do_not_call_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify emergency and mental-health risk route to deterministic resources."""
    captured: dict[str, int] = {"generate_calls": 0}

    class _FakeSGLangClient:
        """SGLang stand-in that must not generate for escalation questions."""

        def __init__(
            self,
            *,
            model: str,
            endpoint: str,
            api_key: str | None,
            timeout: float,
        ) -> None:
            pass

        def generate(self, _request: LLMRequest) -> LLMResponse:
            captured["generate_calls"] += 1
            raise AssertionError("escalation response should not call LLM")

    settings = Settings(
        _env_file=None,
        llm_provider="sglang",
        sglang_base_url="http://127.0.0.1:30000/v1",
        sglang_model="Qwen/Qwen2.5-0.5B-Instruct",
    )
    monkeypatch.setattr(ai_agent, "SGLangClient", _FakeSGLangClient)
    monkeypatch.setattr(ai_agent, "require_user_consent", _allow_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)
    monkeypatch.setattr(ai_agent, "load_agent_memory_context", _memory_context)

    emergency = _client(settings=settings).post(
        "/api/v1/ai-agent/chat",
        json=_chat_payload(message="가슴이 아프고 숨이 차"),
    )
    mental = _client(settings=settings).post(
        "/api/v1/ai-agent/chat",
        json=_chat_payload(message="살 빼려고 계속 굶을래"),
    )

    assert emergency.status_code == status.HTTP_200_OK
    assert mental.status_code == status.HTTP_200_OK
    emergency_body = emergency.json()
    mental_body = mental.json()
    assert "심장" in emergency_body["message"] or "폐" in emergency_body["message"]
    assert "단순 피로" in emergency_body["message"] or "소화불량" in emergency_body["message"]
    assert "119" in emergency_body["message"]
    assert "E-Gen" in emergency_body["message"]
    assert "109" in mental_body["message"]
    assert "체중 관리 조언보다 현재 안전 확인" in mental_body["message"]
    assert "Emergency escalation boundary applied" in emergency_body["safety_warnings"]
    assert "Mental health escalation boundary applied" in mental_body["safety_warnings"]
    assert captured["generate_calls"] == 0


def test_chat_route_requires_sensitive_health_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify chatbot route fails closed without sensitive-health consent."""
    monkeypatch.setattr(ai_agent, "require_user_consent", _deny_consent)
    monkeypatch.setattr(ai_agent, "record_sensitive_audit_event", _record_noop_audit)

    response = _client().post("/api/v1/ai-agent/chat", json=_chat_payload())

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"]["code"] == "consent_required"
