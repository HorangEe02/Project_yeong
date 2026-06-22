from __future__ import annotations

from time import perf_counter
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from lemon_ai_agent.agents.chat import ChatAgent
from lemon_ai_agent.app_intake import AppIntakeModule
from lemon_ai_agent.guards.safety import SafetyEnvelope, SafetyGuard
from lemon_ai_agent.llm import LocalLLMClient
from lemon_ai_agent.orchestrator import DailyHealthAgent
from lemon_ai_agent.schemas import (
    DailyCoachingResult,
    ProposedAction,
    ReferenceRange,
)

AgentStatus = Literal["preview", "completed", "failed"]


class AgentInput(BaseModel):
    request_id: str
    user_id: str
    payload: dict[str, Any]
    context: dict[str, Any] = Field(default_factory=dict)


class AgentFinding(BaseModel):
    nutrient: str
    total_amount: float
    unit: str
    ratio_to_target: float | None = None
    level: str
    message: str


class AgentRecommendation(BaseModel):
    category: str
    title: str
    rationale: str
    priority: int
    requires_professional_consult: bool = False


class AgentAction(BaseModel):
    action_type: str
    title: str
    payload: dict[str, str] = Field(default_factory=dict)
    requires_user_approval: bool = True


class AgentOutput(BaseModel):
    request_id: str
    user_id: str
    agent_name: str
    status: AgentStatus
    approval_status: str
    requires_user_approval: bool
    message: str
    findings: list[AgentFinding] = Field(default_factory=list)
    recommendations: list[AgentRecommendation] = Field(default_factory=list)
    actions: list[AgentAction] = Field(default_factory=list)
    safety_warnings: list[str] = Field(default_factory=list)
    used_tools: list[str] = Field(default_factory=list)
    latency_ms: float = 0
    cost_usd: float = 0
    provider: str = "deterministic"
    debug_trace: list[str] = Field(default_factory=list)


class AgentRunRecord(BaseModel):
    request_id: str
    user_id: str
    agent_name: str
    status: AgentStatus
    latency_ms: float
    cost_usd: float
    provider: str
    approval_status: str
    used_tools: list[str] = Field(default_factory=list)
    error: str | None = None


class AgentRunLogger(Protocol):
    def record(self, record: AgentRunRecord) -> None: ...


class AgentMemoryWriter(Protocol):
    def write(self, user_id: str, result: DailyCoachingResult) -> None: ...


class InMemoryAgentRunLogger:
    def __init__(self) -> None:
        self.records: list[AgentRunRecord] = []

    def record(self, record: AgentRunRecord) -> None:
        self.records.append(record)


class DailyHealthAgentAppAdapter:
    """Maps app AgentInput/AgentOutput to the internal deterministic agent."""

    def __init__(
        self,
        default_references: list[ReferenceRange] | None = None,
        llm_client: LocalLLMClient | None = None,
        run_logger: AgentRunLogger | None = None,
        memory_writer: AgentMemoryWriter | None = None,
        include_debug_trace: bool = False,
        agent_name: str = "daily_health_agent",
    ) -> None:
        self._app_intake = AppIntakeModule(default_references)
        self._chat_agent = ChatAgent(llm_client=llm_client)
        self._run_logger = run_logger
        self._memory_writer = memory_writer
        self._include_debug_trace = include_debug_trace
        self._agent_name = agent_name
        self._safety_guard = SafetyGuard()
        self._safety_envelope = SafetyEnvelope(self._safety_guard)
        self._provider = self._resolve_provider(llm_client)

    def run(self, agent_input: AgentInput) -> AgentOutput:
        started_at = perf_counter()
        used_tools = [
            "daily_health_agent",
            "nutrition_engine",
            "supplement_engine",
            "safety_guard",
            "chat_agent",
        ]

        try:
            app_intake = self._app_intake.parse(agent_input)
            if app_intake.agent_memory.get("summaries"):
                used_tools.append("agent_memory")

            result = DailyHealthAgent(app_intake.references).run(
                profile=app_intake.profile,
                intake=app_intake.intake,
                trends=app_intake.trends,
                agent_memory=app_intake.agent_memory,
            )
            message = self._chat_agent.answer("오늘 코칭 내용을 요약해 주세요.", result)
            output = self._to_output(
                agent_input=agent_input,
                result=result,
                message=message,
                used_tools=used_tools,
                latency_ms=self._elapsed_ms(started_at),
                provider=self._chat_agent.last_provider,
            )
            if result.approval_status == "confirmed" and self._memory_writer is not None:
                try:
                    self._memory_writer.write(agent_input.user_id, result)
                except Exception as exc:
                    output.safety_warnings.append(f"agent_memory update skipped: {exc}")
            if output.status != "preview":
                self._record_run(output)
            return output
        except Exception as exc:
            output = AgentOutput(
                request_id=agent_input.request_id,
                user_id=agent_input.user_id,
                agent_name=self._agent_name,
                status="failed",
                approval_status="requires_confirmation",
                requires_user_approval=True,
                message="Agent request failed before producing coaching output.",
                safety_warnings=[str(exc)],
                used_tools=used_tools,
                latency_ms=self._elapsed_ms(started_at),
                cost_usd=self._cost_usd(),
                provider=self._provider,
            )
            self._record_run(output, error=str(exc))
            return output

    def _to_output(
        self,
        agent_input: AgentInput,
        result: DailyCoachingResult,
        message: str,
        used_tools: list[str],
        latency_ms: float,
        provider: str,
    ) -> AgentOutput:
        status: AgentStatus = (
            "preview" if result.approval_status == "requires_confirmation" else "completed"
        )
        safety_warnings = list(result.safety_warnings)
        safe_message, message_warnings = self._safe_text(message)
        safety_warnings.extend(message_warnings)

        findings: list[AgentFinding] = []
        for finding in result.findings:
            message, warnings = self._safe_text(finding.message)
            safety_warnings.extend(warnings)
            findings.append(
                AgentFinding(
                    nutrient=finding.nutrient,
                    total_amount=finding.total_amount,
                    unit=finding.unit,
                    ratio_to_target=finding.ratio_to_target,
                    level=finding.level.value,
                    message=message,
                )
            )

        recommendations: list[AgentRecommendation] = []
        for recommendation in result.recommendations:
            title, title_warnings = self._safe_text(recommendation.title)
            rationale, rationale_warnings = self._safe_text(recommendation.rationale)
            safety_warnings.extend(title_warnings)
            safety_warnings.extend(rationale_warnings)
            recommendations.append(
                AgentRecommendation(
                    category=recommendation.category,
                    title=title,
                    rationale=rationale,
                    priority=recommendation.priority,
                    requires_professional_consult=(recommendation.requires_professional_consult),
                )
            )

        actions = [self._to_action(action, safety_warnings) for action in result.actions]

        return AgentOutput(
            request_id=agent_input.request_id,
            user_id=agent_input.user_id,
            agent_name=self._agent_name,
            status=status,
            approval_status=result.approval_status,
            requires_user_approval=status == "preview"
            or any(action.requires_user_approval for action in result.actions),
            message=safe_message,
            findings=findings,
            recommendations=recommendations,
            actions=actions,
            safety_warnings=safety_warnings,
            used_tools=used_tools,
            latency_ms=latency_ms,
            cost_usd=self._cost_usd(),
            provider=provider,
            debug_trace=result.trace if self._include_debug_trace else [],
        )

    def _to_action(
        self,
        action: ProposedAction,
        safety_warnings: list[str],
    ) -> AgentAction:
        title, title_warnings = self._safe_text(action.title)
        safety_warnings.extend(title_warnings)
        safe_payload: dict[str, str] = {}
        for key, value in action.payload.items():
            safe_value, value_warnings = self._safe_text(value)
            safety_warnings.extend(value_warnings)
            safe_payload[key] = safe_value

        return AgentAction(
            action_type=action.action_type,
            title=title,
            payload=safe_payload,
            requires_user_approval=action.requires_user_approval,
        )

    def _safe_text(self, text: str) -> tuple[str, list[str]]:
        result = self._safety_envelope.screen_text(text)
        return result.text, list(result.warnings)

    def _record_run(self, output: AgentOutput, error: str | None = None) -> None:
        if self._run_logger is None:
            return

        self._run_logger.record(
            AgentRunRecord(
                request_id=output.request_id,
                user_id=output.user_id,
                agent_name=output.agent_name,
                status=output.status,
                latency_ms=output.latency_ms,
                cost_usd=output.cost_usd,
                provider=output.provider,
                approval_status=output.approval_status,
                used_tools=output.used_tools,
                error=error,
            )
        )

    def _elapsed_ms(self, started_at: float) -> float:
        return round((perf_counter() - started_at) * 1000, 3)

    def _cost_usd(self) -> float:
        return 0

    def _resolve_provider(self, llm_client: LocalLLMClient | None) -> str:
        if llm_client is None:
            return "deterministic"
        return getattr(llm_client, "provider", llm_client.__class__.__name__)
