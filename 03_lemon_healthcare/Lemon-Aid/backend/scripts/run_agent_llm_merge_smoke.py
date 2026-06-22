"""Run Agent/LLM merge-response smoke checks.

The smoke verifies routing contracts rather than medical answer quality:
answerable cases may use an LLM polish provider, while boundary and unknown
cases must remain deterministic.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
AI_AGENT_SRC = BACKEND_ROOT / "ai_agent_chat" / "src"
sys.path.insert(0, str(AI_AGENT_SRC))
sys.path.insert(0, str(BACKEND_ROOT))

from lemon_ai_agent.agents.chatbot import ChatbotAgent  # noqa: E402
from lemon_ai_agent.chat_session import ChatbotRequest  # noqa: E402
from lemon_ai_agent.llm import OllamaClient, SGLangClient  # noqa: E402

from scripts.ask_chatbot_agent import PRESETS, _build_llm_client  # noqa: E402


@dataclass(frozen=True)
class SmokeCase:
    case_id: str
    message: str
    expected_answerability: str
    context: dict[str, object] | None = None
    expected_provider: str | None = None
    expect_sources: bool | None = None
    required_source_ids: tuple[str, ...] = ()
    required_warning_prefixes: tuple[str, ...] = ()


MERGE_SMOKE_CASES: tuple[SmokeCase, ...] = (
    SmokeCase(
        case_id="answerable_sodium",
        message=str(PRESETS["hypertension-sodium-dinner"]["message"]),
        context=dict(PRESETS["hypertension-sodium-dinner"]["context"]),
        expected_answerability="answerable",
        expect_sources=True,
        required_source_ids=("kdris-2025",),
    ),
    SmokeCase(
        case_id="p0_grapefruit_statin",
        message=str(PRESETS["p0-grapefruit-lipid-med"]["message"]),
        context=dict(PRESETS["p0-grapefruit-lipid-med"]["context"]),
        expected_answerability="medical_decision_boundary",
        expected_provider="deterministic",
        expect_sources=True,
        required_source_ids=("mfds-drug-safety",),
        required_warning_prefixes=("boundary_code:p0_grapefruit_statin",),
    ),
    SmokeCase(
        case_id="urgent_chest_pain",
        message=str(PRESETS["urgent-chest-pain"]["message"]),
        context=dict(PRESETS["urgent-chest-pain"]["context"]),
        expected_answerability="urgent_escalation",
        expected_provider="deterministic",
        expect_sources=True,
        required_source_ids=("cdc-public-health",),
    ),
    SmokeCase(
        case_id="unknown_creatine_sleep",
        message="크레아틴을 먹으면 수면 질이 좋아져?",
        expected_answerability="unknown_no_reviewed_source",
        expected_provider="deterministic",
        expect_sources=False,
        required_warning_prefixes=("no_reviewed_answer_card",),
    ),
)


def main() -> int:
    args = _parse_args()
    llm_client = _build_llm_client(args)
    strict_answerable_provider = (
        args.llm if args.require_answerable_llm and args.llm != "none" else None
    )
    results = [
        _run_case(
            case,
            llm_client=llm_client,
            strict_answerable_provider=strict_answerable_provider,
        )
        for case in MERGE_SMOKE_CASES
    ]
    payload = {
        "status": "pass" if all(result["passed"] for result in results) else "fail",
        "llm": args.llm,
        "case_count": len(results),
        "passed": sum(1 for result in results if result["passed"]),
        "failed": sum(1 for result in results if not result["passed"]),
        "results": results,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if payload["status"] == "pass" else 1


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm", choices=("none", "ollama", "sglang"), default="none")
    parser.add_argument("--model")
    parser.add_argument("--endpoint")
    parser.add_argument("--api-key")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--require-answerable-llm",
        action="store_true",
        help=(
            "Fail answerable cases unless they use the selected LLM provider. "
            "Use this for live SGLang merge checks; leave it off for no-LLM CI."
        ),
    )
    return parser.parse_args(argv)


def _run_case(
    case: SmokeCase,
    *,
    llm_client: OllamaClient | SGLangClient | None,
    strict_answerable_provider: str | None = None,
) -> dict[str, Any]:
    response = ChatbotAgent(llm_client=llm_client).answer(
        ChatbotRequest(
            request_id=f"merge-smoke-{case.case_id}",
            user_id="merge-smoke-user",
            message=case.message,
            context=case.context or {},
        )
    )
    return _evaluate_case_result(
        case=case,
        provider=response.provider,
        answerability=response.answerability,
        source_ids=tuple(source.get("source_id", "") for source in response.sources),
        safety_warnings=tuple(response.safety_warnings),
        strict_answerable_provider=strict_answerable_provider,
    )


def _evaluate_case_result(
    *,
    case: SmokeCase,
    provider: str,
    answerability: str,
    source_ids: tuple[str, ...] | list[str],
    safety_warnings: tuple[str, ...] | list[str],
    strict_answerable_provider: str | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    source_id_list = [source_id for source_id in source_ids if source_id]
    warning_list = list(safety_warnings)
    expected_provider = case.expected_provider
    if (
        expected_provider is None
        and strict_answerable_provider is not None
        and case.expected_answerability in {"answerable", "answerable_with_caution"}
    ):
        expected_provider = strict_answerable_provider
    if answerability != case.expected_answerability:
        failures.append(
            f"answerability:expected={case.expected_answerability}:actual={answerability}"
        )
    if expected_provider is not None and provider != expected_provider:
        failures.append(f"provider:expected={expected_provider}:actual={provider}")
    if case.expect_sources is True and not source_id_list:
        failures.append("sources:expected=present:actual=empty")
    if case.expect_sources is False and source_id_list:
        failures.append(f"sources:expected=empty:actual={','.join(source_id_list)}")
    for source_id in case.required_source_ids:
        if source_id not in source_id_list:
            failures.append(f"source_id:missing={source_id}")
    for prefix in case.required_warning_prefixes:
        if not any(warning.startswith(prefix) for warning in warning_list):
            failures.append(f"warning:missing={prefix}")
    return {
        "case_id": case.case_id,
        "passed": not failures,
        "provider": provider,
        "answerability": answerability,
        "source_ids": source_id_list,
        "safety_warning_codes": warning_list,
        "failures": failures,
    }


if __name__ == "__main__":
    raise SystemExit(main())
