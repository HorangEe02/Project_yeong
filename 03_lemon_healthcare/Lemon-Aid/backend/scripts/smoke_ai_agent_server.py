"""Run a live FastAPI + PostgreSQL + SGLang AI Agent smoke test."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
AI_AGENT_SRC = BACKEND_ROOT / "ai_agent_chat" / "src"
DEFAULT_SERVER_URL = "http://127.0.0.1:18080"
DEFAULT_SGLANG_BASE_URL = "http://127.0.0.1:30000/v1"
DEFAULT_SGLANG_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
SUPABASE_CHATBOT_PROJECT_REF = "ajgvoxttzsjcwtphtsuz"
SUPABASE_CHATBOT_POOLER_HOST = "aws-1-ap-northeast-2.pooler.supabase.com"
EXPECTED_CHATBOT_SOURCE_IDS = {"kdris-2025", "kdca-healthinfo"}

sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))
sys.path.insert(0, str(AI_AGENT_SRC))
sys.path.insert(0, str(BACKEND_ROOT))

from src.models.db.medical_source import MedicalUnknownKnowledgeEvent  # noqa: E402


def main() -> int:
    args = _parse_args()

    if not args.database_url:
        print(_missing_database_url_message(), file=sys.stderr)
        return 2

    database_url = _normalize_database_url(args.database_url)
    sglang_check = "skipped" if args.skip_sglang_check else "required"
    if not args.skip_sglang_check:
        _require_sglang(args.sglang_base_url, args.timeout)

    env = _server_env(database_url, args.sglang_base_url, args.sglang_model)
    if not args.skip_db_upgrade:
        _run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"], env=env)

    unknown_before = None
    if not args.skip_unknown_backlog_check:
        unknown_before = asyncio.run(_unknown_backlog_count(database_url))

    process = None if args.use_existing_server else _start_server(args.server_url, env)
    try:
        _wait_for_health(args.server_url, args.timeout)
        consent = _post_json(
            f"{args.server_url}/api/v1/me/privacy/consents/sensitive_health_analysis",
            {},
            timeout=args.timeout,
        )
        first = _post_json(
            f"{args.server_url}/api/v1/ai-agent/daily-coaching",
            _daily_coaching_payload("server-smoke-1"),
            timeout=args.timeout,
        )
        second = _post_json(
            f"{args.server_url}/api/v1/ai-agent/daily-coaching",
            _daily_coaching_payload("server-smoke-2"),
            timeout=args.timeout,
        )
        chat = _post_json(
            f"{args.server_url}/api/v1/ai-agent/chat",
            _chat_payload("server-chat-smoke"),
            timeout=args.timeout,
        )
        unknown_chat = None
        if not args.skip_unknown_backlog_check:
            unknown_chat = _post_json(
                f"{args.server_url}/api/v1/ai-agent/chat",
                _unknown_chat_payload("server-chat-unknown-smoke"),
                timeout=args.timeout,
            )
    finally:
        if process is not None:
            _stop_server(process)

    _assert_response(consent.get("granted") is True, "consent grant failed")
    _assert_response(first.get("status") == "completed", "first coaching request did not complete")
    _assert_response(
        second.get("status") == "completed", "second coaching request did not complete"
    )
    _assert_response(
        "agent_memory" in second.get("used_tools", []),
        "second coaching request did not reload persisted agent_memory",
    )
    _assert_response(
        second.get("provider") in {"sglang", "deterministic"},
        "unexpected provider in coaching response",
    )
    _assert_response(
        chat.get("provider") in {"sglang", "deterministic"},
        "unexpected provider in chatbot response",
    )
    _assert_reviewed_chatbot_response(chat)
    _assert_response(
        "agent_memory" in chat.get("used_tools", []),
        "chatbot request did not include agent_memory in used_tools",
    )

    unknown_after = None
    if not args.skip_unknown_backlog_check:
        _assert_response(unknown_chat is not None, "unknown chatbot smoke did not run")
        _assert_response(
            unknown_chat.get("answerability") == "unknown_no_reviewed_source",
            "unknown chatbot smoke did not return unknown_no_reviewed_source",
        )
        _assert_response(
            unknown_chat.get("sources") == [],
            "unknown chatbot smoke unexpectedly returned reviewed sources",
        )
        unknown_after = asyncio.run(_unknown_backlog_count(database_url))
        _assert_response(
            unknown_before is not None and unknown_after >= unknown_before + 1,
            "unknown chatbot smoke did not persist a backlog event",
        )

    print(
        json.dumps(
            _summary_payload(
                args=args,
                sglang_check=sglang_check,
                first=first,
                second=second,
                chat=chat,
                unknown_chat=unknown_chat,
                unknown_backlog_before=unknown_before,
                unknown_backlog_after=unknown_after,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-url", default=DEFAULT_SERVER_URL)
    parser.add_argument(
        "--sglang-base-url",
        default=os.getenv("SGLANG_BASE_URL", DEFAULT_SGLANG_BASE_URL),
    )
    parser.add_argument("--sglang-model", default=os.getenv("SGLANG_MODEL", DEFAULT_SGLANG_MODEL))
    parser.add_argument(
        "--database-url", default=os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    )
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--skip-db-upgrade", action="store_true")
    parser.add_argument(
        "--skip-sglang-check",
        action="store_true",
        help="Skip /v1/models readiness and allow deterministic fallback smoke.",
    )
    parser.add_argument(
        "--use-existing-server",
        action="store_true",
        help="Call an already running FastAPI server instead of starting uvicorn.",
    )
    parser.add_argument(
        "--skip-unknown-backlog-check",
        action="store_true",
        help="Skip the unknown_no_reviewed_source request and DB backlog persistence assertion.",
    )
    return parser.parse_args(argv)


def _summary_payload(
    *,
    args: argparse.Namespace,
    sglang_check: str,
    first: dict[str, Any],
    second: dict[str, Any],
    chat: dict[str, Any],
    unknown_chat: dict[str, Any] | None = None,
    unknown_backlog_before: int | None = None,
    unknown_backlog_after: int | None = None,
) -> dict[str, Any]:
    unknown_backlog_delta = (
        unknown_backlog_after - unknown_backlog_before
        if unknown_backlog_before is not None and unknown_backlog_after is not None
        else None
    )
    return {
        "status": "ok",
        "server_url": args.server_url,
        "sglang_base_url": args.sglang_base_url,
        "sglang_check": sglang_check,
        "model": args.sglang_model,
        "first_provider": first.get("provider"),
        "second_provider": second.get("provider"),
        "second_used_tools": second.get("used_tools", []),
        "chat_provider": chat.get("provider"),
        "chat_used_tools": chat.get("used_tools", []),
        "chat_answerability": chat.get("answerability"),
        "chat_source_count": (
            len(chat.get("sources", [])) if isinstance(chat.get("sources"), list) else 0
        ),
        "unknown_answerability": unknown_chat.get("answerability") if unknown_chat else None,
        "unknown_source_count": (
            len(unknown_chat.get("sources", []))
            if unknown_chat and isinstance(unknown_chat.get("sources"), list)
            else None
        ),
        "unknown_backlog_before": unknown_backlog_before,
        "unknown_backlog_after": unknown_backlog_after,
        "unknown_backlog_delta": unknown_backlog_delta,
        "chat_sources": [
            {
                "source_id": source.get("source_id"),
                "source_family": source.get("source_family"),
                "version_label": source.get("version_label"),
                "expires_at": source.get("expires_at"),
            }
            for source in chat.get("sources", [])
            if isinstance(source, dict)
        ],
    }


def _server_env(database_url: str, sglang_base_url: str, sglang_model: str) -> dict[str, str]:
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    paths = [str(NUTRITION_BACKEND_ROOT), str(AI_AGENT_SRC), str(BACKEND_ROOT)]
    if existing_pythonpath:
        paths.append(existing_pythonpath)
    env.update(
        {
            "PYTHONPATH": os.pathsep.join(paths),
            "DATABASE_URL": database_url,
            "AUTH_MODE": "disabled",
            "LLM_PROVIDER": "sglang",
            "SGLANG_BASE_URL": sglang_base_url,
            "SGLANG_MODEL": sglang_model,
            "SGLANG_API_KEY": os.getenv("SGLANG_API_KEY", "EMPTY"),
            "ALLOW_EXTERNAL_LLM": "false",
            "LOG_LEVEL": "WARNING",
        }
    )
    return env


def _normalize_database_url(database_url: str) -> str:
    normalized = database_url.strip()
    if normalized.startswith("postgresql://"):
        normalized = "postgresql+asyncpg://" + normalized[len("postgresql://") :]
    return normalized.replace("sslmode=require", "ssl=require")


def _missing_database_url_message() -> str:
    return (
        "ERROR: set TEST_DATABASE_URL, DATABASE_URL, or pass --database-url.\n"
        "For the Lemon Aid Supabase dev project, copy the database password from "
        "Supabase Dashboard and set a local-only value like:\n"
        "$env:DATABASE_URL="
        f'"postgresql+asyncpg://postgres.{SUPABASE_CHATBOT_PROJECT_REF}:<password>@'
        f'{SUPABASE_CHATBOT_POOLER_HOST}:5432/postgres?ssl=require"\n'
        "Do not commit the real password or connection string."
    )


def _assert_reviewed_chatbot_response(chat: dict[str, Any]) -> None:
    _assert_response(
        chat.get("answerability") == "answerable",
        "chatbot smoke did not return answerable for the reviewed sodium/hypertension question",
    )
    sources = chat.get("sources")
    _assert_response(isinstance(sources, list), "chatbot response did not include sources list")
    _assert_response(bool(sources), "chatbot smoke did not return reviewed sources")
    source_ids = {source.get("source_id") for source in sources if isinstance(source, dict)}
    _assert_response(
        bool(source_ids & EXPECTED_CHATBOT_SOURCE_IDS),
        "chatbot smoke did not return expected reviewed nutrition sources",
    )
    unsafe_sources = [
        source
        for source in sources
        if isinstance(source, dict) and source.get("review_status") not in {None, "reviewed"}
    ]
    _assert_response(not unsafe_sources, "chatbot smoke returned an unreviewed source")


async def _unknown_backlog_count(database_url: str) -> int:
    engine = create_async_engine(database_url)
    try:
        async with AsyncSession(engine) as session:
            result = await session.execute(
                select(func.count()).select_from(MedicalUnknownKnowledgeEvent)
            )
            return int(result.scalar_one())
    finally:
        await engine.dispose()


def _start_server(server_url: str, env: dict[str, str]) -> subprocess.Popen[str]:
    host, port = _host_port(server_url)
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "src.main:app",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    return subprocess.Popen(
        command,
        cwd=NUTRITION_BACKEND_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _stop_server(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _wait_for_health(server_url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = _get_json(f"{server_url}/health", timeout=2)
            if response.get("status") == "ok":
                return
        except Exception as exc:
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"server did not become healthy: {last_error}")


def _require_sglang(base_url: str, timeout: float) -> None:
    models = _get_json(f"{base_url.rstrip('/')}/models", timeout=timeout)
    data = models.get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError("SGLang /v1/models did not return any models")


def _get_json(url: str, *, timeout: float) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {url} failed with {exc.code}: {detail}") from exc


def _run(command: list[str], *, env: dict[str, str]) -> None:
    subprocess.run(command, cwd=BACKEND_ROOT, env=env, check=True)


def _host_port(server_url: str) -> tuple[str, int]:
    parsed = urllib.parse.urlparse(server_url)
    if parsed.hostname is None or parsed.port is None:
        raise ValueError("--server-url must include host and port")
    return parsed.hostname, parsed.port


def _assert_response(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _daily_coaching_payload(request_id: str) -> dict[str, Any]:
    return {
        "request_id": request_id,
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
            "date": "2026-05-20",
            "sources": [
                {
                    "source_type": "food_ocr",
                    "image_id": f"{request_id}-image",
                    "raw_ocr_text": "instant noodles sodium 2600mg",
                    "user_confirmed": True,
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
                    "summary": "Meal score has dropped for 7 days.",
                }
            ],
        },
    }


def _chat_payload(request_id: str) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "user_id": "client-supplied-user",
        "message": "오늘 점심 나트륨이 높았는데 저녁은 어떻게 조절하면 좋을까?",
        "conversation": [
            {
                "role": "user",
                "content": "점심에 라면을 먹었어.",
                "created_at": "2026-05-20T12:30:00+09:00",
            }
        ],
        "context": {
            "profile": {
                "age": 52,
                "gender": "male",
                "chronic_conditions": ["hypertension"],
            },
            "latest_confirmed_entries": {
                "foods": [
                    {
                        "name": "instant noodles",
                        "meal_type": "lunch",
                        "nutrients": [{"name": "sodium", "amount": 2600, "unit": "mg"}],
                    }
                ]
            },
        },
    }


def _unknown_chat_payload(request_id: str) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "user_id": "client-supplied-user",
        "message": "리튬 약과 타우린 영양제 같이 먹어도 돼?",
        "conversation": [],
        "context": {"profile": {"chronic_conditions": []}},
    }


if __name__ == "__main__":
    raise SystemExit(main())
