"""Privacy-minimized Agent memory services."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from lemon_ai_agent.adapters import AgentInput, AgentOutput
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.db.tx import request_manages_transaction
from src.models.db.agent_memory import AgentMemory, AgentRun
from src.models.db.analysis_result import AnalysisResult
from src.models.db.supplement import UserSupplement, UserSupplementIngredient
from src.security.auth import AuthenticatedUser
from src.security.privacy import hash_actor_subject

AGENT_MEMORY_ALGORITHM_VERSION = "agent-memory-summary-v1.0.0"
MEMORY_SUMMARY_SCHEMA_VERSION = "agent-memory-summary-v1"
DAILY_COACHING_MEMORY_TYPE = "daily_coaching"
SUPPLEMENT_MEMORY_TYPE = "confirmed_supplement"
NUTRITION_ANALYSIS_MEMORY_TYPE = "nutrition_analysis"
PROFILE_MEMORY_TYPE = "profile_memory"
BEHAVIOR_MEMORY_TYPE = "behavior_memory"
CONVERSATION_MEMORY_TYPE = "conversation_memory"
SAFETY_MEMORY_TYPE = "safety_memory"
AGENT_MEMORY_TYPES = (
    PROFILE_MEMORY_TYPE,
    BEHAVIOR_MEMORY_TYPE,
    CONVERSATION_MEMORY_TYPE,
    SAFETY_MEMORY_TYPE,
)
MAX_PATTERN_COUNT = 99
RECENT_FINDING_LIMIT = 20
SUMMARY_LIST_LIMIT = 20
FORBIDDEN_MEMORY_KEYS = {
    "authorization",
    "full_prompt",
    "image_base64",
    "image_bytes",
    "messages",
    "original_transcript",
    "prompt",
    "provider_payload",
    "raw_image",
    "raw_image_bytes",
    "raw_llm_response",
    "raw_ocr_text",
    "raw_prompt",
    "raw_provider_payload",
    "raw_transcript",
}
NUTRIENT_ALIASES = {
    "vitamin-d": "vitamin d",
    "vitamin_d": "vitamin d",
    "비타민 d": "vitamin d",
    "비타민d": "vitamin d",
}
UNIT_ALIASES = {
    "g": "g",
    "gram": "g",
    "grams": "g",
    "mg": "mg",
    "milligram": "mg",
    "milligrams": "mg",
    "mcg": "mcg",
    "µg": "mcg",
    "μg": "mcg",
    "ug": "mcg",
    "iu": "iu",
}


async def load_agent_memory_context(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
) -> dict[str, Any]:
    """Load summarized Agent memory for injection into daily coaching."""
    if not hasattr(session, "scalars"):
        return {"summaries": []}

    owner_subject_hash = hash_actor_subject(user, settings)
    result = await session.scalars(
        select(AgentMemory).where(AgentMemory.owner_subject_hash == owner_subject_hash)
    )
    summaries = [_memory_record_to_context(record) for record in result.all()]
    return {
        "schema_version": MEMORY_SUMMARY_SCHEMA_VERSION,
        "summaries": _sanitize_memory_value(summaries),
        "memory_bundle": _memory_bundle_from_summaries(summaries),
    }


async def upsert_daily_coaching_memory(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    agent_input: AgentInput,
    output: AgentOutput,
) -> AgentMemory | None:
    """Update daily coaching memory from confirmed structured Agent output."""
    if output.status != "completed" or output.approval_status != "confirmed":
        return None
    if not hasattr(session, "scalar") or not hasattr(session, "add"):
        return None

    memory = await _get_or_create_memory(session, user, settings, DAILY_COACHING_MEMORY_TYPE)
    summary = _merge_daily_coaching_summary(memory.summary_json, agent_input, output)
    memory.summary_json = _sanitize_memory_value(summary)
    memory.source_counters = _increment_counter(memory.source_counters, "daily_coaching")
    memory.last_source_created_at = _utc_now()
    memory.algorithm_version = AGENT_MEMORY_ALGORITHM_VERSION
    await _commit_if_possible(session)
    return memory


async def upsert_agent_memory_record(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    *,
    memory_type: str,
    summary: str,
    structured_payload: dict[str, Any] | None = None,
    confidence: str,
    source_kind: str,
    source_ref: str | None = None,
    priority: int = 0,
    review_after: datetime | None = None,
    expires_at: datetime | None = None,
) -> AgentMemory | None:
    """Upsert one sanitized v2 Agent memory record.

    Day 2 keeps the existing `agent_memory` table and stores the new memory
    taxonomy as a service-level contract in `summary_json`. Raw transcript,
    prompt, OCR, and provider payload fields are stripped before persistence.
    """
    if memory_type not in AGENT_MEMORY_TYPES:
        raise ValueError(f"Unsupported agent memory type: {memory_type}")
    if not summary.strip():
        raise ValueError("Agent memory summary must not be blank")
    if not hasattr(session, "scalar") or not hasattr(session, "add"):
        return None

    memory = await _get_or_create_memory(session, user, settings, memory_type)
    memory.summary_json = _sanitize_memory_value(
        {
            "schema_version": MEMORY_SUMMARY_SCHEMA_VERSION,
            "memory_type": memory_type,
            "summary": summary.strip(),
            "structured_payload": structured_payload or {},
            "confidence": confidence,
            "source_kind": source_kind,
            "source_ref": source_ref,
            "priority": int(priority),
            "review_after": review_after.isoformat() if review_after else None,
            "expires_at": expires_at.isoformat() if expires_at else None,
        }
    )
    memory.source_counters = _increment_counter(memory.source_counters, source_kind)
    memory.last_source_created_at = _utc_now()
    memory.algorithm_version = AGENT_MEMORY_ALGORITHM_VERSION
    await _commit_if_possible(session)
    return memory


async def record_agent_run(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    output: AgentOutput,
    *,
    model: str | None = None,
) -> AgentRun | None:
    """Persist sanitized Agent execution metadata for non-preview runs."""
    if output.status == "preview" or not hasattr(session, "add"):
        return None

    run = AgentRun(
        request_id=output.request_id,
        owner_subject_hash=hash_actor_subject(user, settings),
        agent_name=output.agent_name,
        status=output.status,
        approval_status=output.approval_status,
        provider=output.provider,
        model=model,
        latency_ms=Decimal(str(output.latency_ms)),
        cost_usd=Decimal(str(output.cost_usd)),
        used_tools=list(output.used_tools),
    )
    session.add(run)
    await _commit_if_possible(session)
    return run


async def upsert_supplement_memory(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    supplement: UserSupplement,
    ingredients: list[UserSupplementIngredient],
) -> AgentMemory | None:
    """Update memory after a user confirms a supplement record."""
    if not hasattr(session, "scalar") or not hasattr(session, "add"):
        return None

    memory = await _get_or_create_memory(session, user, settings, SUPPLEMENT_MEMORY_TYPE)
    summary = _with_schema_version(memory.summary_json)
    ingredient_summary = dict(summary.get("supplement_ingredients", {}))
    for ingredient in ingredients:
        key = _canonical_nutrient_key(ingredient.nutrient_code or ingredient.display_name)
        if not key:
            continue
        current = dict(ingredient_summary.get(key, {}))
        current["count"] = int(current.get("count", 0)) + 1
        current["nutrient_code"] = ingredient.nutrient_code
        if ingredient.amount is not None:
            amount, unit = _canonical_amount(
                key,
                float(ingredient.amount),
                ingredient.unit or "",
            )
            current["unit"] = unit
            current["amount_total"] = round(
                float(current.get("amount_total", 0.0)) + amount,
                6,
            )
        elif ingredient.unit is not None:
            current["unit"] = _canonical_unit(ingredient.unit)
        ingredient_summary[key] = current

    memory.summary_json = _sanitize_memory_value(
        {
            **summary,
            "supplement_ingredients": ingredient_summary,
            "last_confirmed_supplement": {
                "display_name": supplement.display_name,
                "ingredient_count": len(ingredients),
            },
        }
    )
    memory.source_counters = _increment_counter(memory.source_counters, "confirmed_supplement")
    memory.last_source_created_at = supplement.user_confirmed_at
    memory.algorithm_version = AGENT_MEMORY_ALGORITHM_VERSION
    await _commit_if_possible(session)
    return memory


async def upsert_nutrition_analysis_memory(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    record: AnalysisResult,
) -> AgentMemory | None:
    """Update memory from a persisted nutrition analysis result."""
    if record.analysis_type != "nutrition_analysis":
        return None
    if not hasattr(session, "scalar") or not hasattr(session, "add"):
        return None

    memory = await _get_or_create_memory(session, user, settings, NUTRITION_ANALYSIS_MEMORY_TYPE)
    summary = _with_schema_version(memory.summary_json)
    patterns = dict(summary.get("repeated_nutrient_patterns", {}))
    priority_tags = list(summary.get("priority_tags", []))
    for item in _collect_nutrition_priority_items(record.result_snapshot):
        nutrient = _canonical_nutrient_key(item["nutrient"])
        patterns[nutrient] = _increment_pattern_count(patterns.get(nutrient, 0))
        tag = item.get("priority")
        if tag and tag not in priority_tags:
            priority_tags.append(tag)

    summary["repeated_nutrient_patterns"] = patterns
    summary["priority_tags"] = priority_tags[:SUMMARY_LIST_LIMIT]
    memory.summary_json = _sanitize_memory_value(summary)
    memory.source_counters = _increment_counter(memory.source_counters, "nutrition_analysis")
    memory.last_source_created_at = record.created_at
    memory.algorithm_version = AGENT_MEMORY_ALGORITHM_VERSION
    await _commit_if_possible(session)
    return memory


def _merge_daily_coaching_summary(
    existing: dict[str, Any],
    agent_input: AgentInput,
    output: AgentOutput,
) -> dict[str, Any]:
    summary = _with_schema_version(existing)
    patterns = dict(summary.get("repeated_nutrient_patterns", {}))
    recent_findings = list(summary.get("recent_findings", []))
    for finding in output.findings:
        if finding.level not in {"low", "high", "risky"}:
            continue
        nutrient = _canonical_nutrient_key(finding.nutrient)
        amount, unit = _canonical_amount(nutrient, finding.total_amount, finding.unit)
        patterns[nutrient] = _increment_pattern_count(patterns.get(nutrient, 0))
        recent_findings.append(
            {
                "date": str(agent_input.payload.get("date", "")),
                "nutrient": nutrient,
                "level": finding.level,
                "total_amount": amount,
                "unit": unit,
            }
        )

    profile = agent_input.context.get("profile", agent_input.context)
    health_caution_tags = list(summary.get("health_caution_tags", []))
    if isinstance(profile, dict):
        for tag in profile.get("chronic_conditions", []):
            if isinstance(tag, str) and tag not in health_caution_tags:
                health_caution_tags.append(tag)

    return {
        **summary,
        "repeated_nutrient_patterns": patterns,
        "recent_findings": recent_findings[-RECENT_FINDING_LIMIT:],
        "health_caution_tags": health_caution_tags[:SUMMARY_LIST_LIMIT],
    }


async def _get_or_create_memory(
    session: AsyncSession,
    user: AuthenticatedUser,
    settings: Settings,
    memory_type: str,
) -> AgentMemory:
    owner_subject_hash = hash_actor_subject(user, settings)
    memory = await session.scalar(
        select(AgentMemory).where(
            AgentMemory.owner_subject_hash == owner_subject_hash,
            AgentMemory.memory_type == memory_type,
        )
    )
    if memory is not None:
        return memory
    memory = AgentMemory(
        owner_subject_hash=owner_subject_hash,
        memory_type=memory_type,
        summary_json={},
        source_counters={},
        algorithm_version=AGENT_MEMORY_ALGORITHM_VERSION,
    )
    session.add(memory)
    return memory


def _memory_record_to_context(record: AgentMemory) -> dict[str, Any]:
    return {
        "memory_type": record.memory_type,
        "summary_json": record.summary_json,
        "source_counters": record.source_counters,
        "last_source_created_at": (
            record.last_source_created_at.isoformat()
            if record.last_source_created_at is not None
            else None
        ),
        "algorithm_version": record.algorithm_version,
    }


def _memory_bundle_from_summaries(
    summaries: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    bundle: dict[str, list[dict[str, Any]]] = {
        memory_type: [] for memory_type in AGENT_MEMORY_TYPES
    }
    for summary in _sanitize_memory_value(summaries):
        if not isinstance(summary, dict):
            continue
        memory_type = summary.get("memory_type")
        if isinstance(memory_type, str) and memory_type in bundle:
            bundle[memory_type].append(summary)
    return bundle


def _collect_nutrition_priority_items(value: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if isinstance(value, dict):
        nutrient = value.get("nutrient") or value.get("nutrient_name") or value.get("name")
        level = value.get("level") or value.get("status") or value.get("priority")
        if isinstance(nutrient, str) and isinstance(level, str):
            normalized = level.lower()
            if normalized in {"low", "deficient", "high", "excess", "risky", "priority"}:
                items.append({"nutrient": nutrient, "priority": normalized})
        for nested_value in value.values():
            items.extend(_collect_nutrition_priority_items(nested_value))
    elif isinstance(value, list):
        for item in value:
            items.extend(_collect_nutrition_priority_items(item))
    return items


def _increment_counter(counters: dict[str, Any], key: str) -> dict[str, Any]:
    updated = dict(counters)
    updated[key] = int(updated.get(key, 0)) + 1
    return updated


def _with_schema_version(summary: dict[str, Any]) -> dict[str, Any]:
    updated = dict(summary)
    updated["schema_version"] = MEMORY_SUMMARY_SCHEMA_VERSION
    return updated


def _canonical_nutrient_key(name: str) -> str:
    normalized = " ".join(name.strip().lower().replace("_", " ").split())
    return NUTRIENT_ALIASES.get(normalized, normalized)


def _canonical_unit(unit: str) -> str:
    return UNIT_ALIASES.get(unit.strip().lower(), unit.strip().lower())


def _canonical_amount(
    nutrient: str,
    amount: float,
    unit: str,
) -> tuple[float, str]:
    canonical_unit = _canonical_unit(unit)
    if nutrient == "vitamin d" and canonical_unit == "iu":
        return round(amount / 40.0, 6), "mcg"
    return round(amount, 6), canonical_unit


def _increment_pattern_count(existing_count: Any) -> int:
    try:
        current = int(existing_count)
    except (TypeError, ValueError):
        current = 0
    return min(current + 1, MAX_PATTERN_COUNT)


def _sanitize_memory_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize_memory_value(nested)
            for key, nested in value.items()
            if isinstance(key, str) and key.lower() not in FORBIDDEN_MEMORY_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_memory_value(item) for item in value]
    return value


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def _commit_if_possible(session: AsyncSession) -> None:
    """Persist agent-memory writes under the correct transaction-ownership mode.

    Request-managed (RLS) sessions own begin + commit at the dependency seam, so
    committing here would drop the transaction-local RLS GUCs; flush only
    (participate) and let the request transaction commit at teardown. Legacy
    sessions commit as before (reproducing the historical add + commit behavior).
    The ``getattr`` guards keep partial test doubles working.
    """
    if request_manages_transaction(session):
        flush = getattr(session, "flush", None)
        if flush is not None:
            await flush()
        return
    commit = getattr(session, "commit", None)
    if commit is not None:
        await commit()
