"""Smoke-test DB-backed chatbot evidence without starting FastAPI."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
AI_AGENT_SRC = BACKEND_ROOT / "ai_agent_chat" / "src"

sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))
sys.path.insert(0, str(AI_AGENT_SRC))
sys.path.insert(0, str(BACKEND_ROOT))

from lemon_ai_agent.agents.chatbot import ChatbotAgent  # noqa: E402
from lemon_ai_agent.chat_session import ChatbotRequest  # noqa: E402
from src.services.chatbot_evidence_retriever import (  # noqa: E402
    ChatbotEvidenceRepository,
    build_chatbot_medical_knowledge_retriever,
)

PRESETS: dict[str, dict[str, Any]] = {
    "hypertension-sodium": {
        "message": "고혈압이 있는데 오늘 점심 나트륨이 높았어. 저녁은 어떻게 조절하면 좋을까?",
        "context": {
            "profile": {"chronic_conditions": ["hypertension"]},
            "latest_confirmed_entries": {
                "foods": [
                    {
                        "name": "라면",
                        "meal_type": "lunch",
                        "nutrients": [{"name": "sodium", "amount": 2600, "unit": "mg"}],
                    }
                ]
            },
        },
        "expected_answerability": "answerable",
        "require_sources": True,
    },
    "magnesium-blood-pressure-med": {
        "message": "혈압약을 먹는데 마그네슘 영양제를 같이 먹어도 돼?",
        "context": {"profile": {"chronic_conditions": ["hypertension"]}},
        "expected_answerability": "answerable_with_caution",
        "require_sources": True,
    },
    "unknown-lithium-selenium": {
        "message": "리튬 약을 먹는데 셀레늄 영양제 같이 먹어도 돼?",
        "context": {},
        "expected_answerability": "medical_decision_boundary",
        "require_sources": True,
    },
    "unknown-herbal-blend": {
        "message": "Can you analyze my Herbal blend supplement ingredient?",
        "context": {
            "user_health_context_snapshot": {
                "active_supplement_snapshot": {
                    "registered_supplements": [
                        {
                            "display_name": "Herbal blend",
                            "ingredients": [
                                {
                                    "display_name": "Herbal blend",
                                    "nutrient_code": None,
                                    "analysis_use": "label_only",
                                }
                            ],
                            "user_confirmed": True,
                        }
                    ],
                    "policy": {
                        "nutrient_code_required_for_standard_analysis": True,
                        "unconfirmed_preview_excluded": True,
                    },
                }
            }
        },
        "expected_answerability": "unknown_no_reviewed_source",
        "require_sources": False,
    },
}


def main() -> int:
    args = _parse_args()
    if not args.database_url:
        print(
            "ERROR: set DATABASE_URL or TEST_DATABASE_URL, or pass --database-url.", file=sys.stderr
        )
        return 2

    database_url = _normalize_database_url(args.database_url)
    summary = asyncio.run(_run_smoke(args=args, database_url=database_url))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url", default=os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    )
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        default="hypertension-sodium",
    )
    parser.add_argument(
        "--environment",
        choices=("development", "staging", "production"),
        default="production",
        help="Use production to prove DB-only retrieval without registry fallback.",
    )
    return parser.parse_args(argv)


async def _run_smoke(*, args: argparse.Namespace, database_url: str) -> dict[str, Any]:
    engine = create_async_engine(database_url)
    try:
        async with AsyncSession(engine) as session:
            records = await ChatbotEvidenceRepository(session).list_answer_card_records()
            retriever = await build_chatbot_medical_knowledge_retriever(
                session,
                SimpleNamespace(environment=args.environment),
            )
    finally:
        await engine.dispose()

    preset = PRESETS[args.preset]
    response = ChatbotAgent(retriever=retriever).answer(
        ChatbotRequest(
            request_id=f"db-evidence-smoke-{args.preset}",
            user_id="db-evidence-smoke-user",
            message=str(preset["message"]),
            context=dict(preset["context"]),
        )
    )
    _assert_response(
        response.answerability == preset["expected_answerability"],
        f"expected answerability {preset['expected_answerability']}, got {response.answerability}",
    )
    if preset["require_sources"]:
        _assert_response(bool(response.sources), "expected at least one reviewed source")

    return _summary_payload(
        environment=args.environment,
        preset=args.preset,
        record_count=len(records),
        answerability=response.answerability,
        source_count=len(response.sources),
        sources=response.sources,
        safety_warnings=response.safety_warnings,
    )


def _normalize_database_url(database_url: str) -> str:
    normalized = database_url.strip()
    if normalized.startswith("postgresql://"):
        normalized = "postgresql+asyncpg://" + normalized[len("postgresql://") :]
    return normalized.replace("sslmode=require", "ssl=require")


def _summary_payload(
    *,
    environment: str,
    preset: str,
    record_count: int,
    answerability: str,
    source_count: int,
    sources: list[dict[str, str]],
    safety_warnings: list[str],
) -> dict[str, Any]:
    return {
        "status": "ok",
        "environment": environment,
        "preset": preset,
        "db_evidence_record_count": record_count,
        "answerability": answerability,
        "source_count": source_count,
        "sources": [
            {
                "source_id": source.get("source_id"),
                "source_family": source.get("source_family"),
                "version_label": source.get("version_label"),
                "expires_at": source.get("expires_at"),
            }
            for source in sources
        ],
        "safety_warnings": safety_warnings,
    }


def _assert_response(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


if __name__ == "__main__":
    raise SystemExit(main())
