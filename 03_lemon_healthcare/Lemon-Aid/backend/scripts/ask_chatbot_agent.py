from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import uuid4

AI_AGENT_SRC = Path(__file__).resolve().parents[1] / "ai_agent_chat" / "src"
sys.path.insert(0, str(AI_AGENT_SRC))

from lemon_ai_agent.agents.chatbot import ChatbotAgent  # noqa: E402
from lemon_ai_agent.chat_session import ChatbotRequest  # noqa: E402
from lemon_ai_agent.llm import LLMMessage, LLMRequest, OllamaClient, SGLangClient  # noqa: E402

PRESETS = {
    "diabetes-high-carb": {
        "message": "나 당뇨환자인데, 밥을 세 공기나 과식했어. 초콜릿도 먹었는데 저녁은 어떻게 조절하면 좋을까?",
        "context": {"profile": {"chronic_conditions": ["diabetes"]}},
    },
    "diabetes-improvement": {
        "message": "당뇨를 개선하려면 식단, 운동, 수면, 체중관리를 어떻게 해야 해?",
        "context": {"profile": {"chronic_conditions": ["diabetes"]}},
    },
    "exercise-dizziness": {
        "message": "운동 후 어지러움이 있는데 지금은 어떻게 하면 좋아?",
        "context": {"profile": {"chronic_conditions": ["diabetes"]}},
    },
    "exercise-dizziness-red-flags": {
        "message": "운동 후 어지러운데 가슴 통증이 있고 숨이 차",
        "context": {"profile": {"chronic_conditions": ["diabetes"]}},
    },
    "hypertension-kimchi-stew": {
        "message": "고혈압이 있는데 오늘 점심으로 김치찌개랑 햄 반찬을 먹었어. 저녁은 어떻게 조절하면 좋을까?",
        "context": {
            "profile": {"chronic_conditions": ["hypertension"]},
            "latest_confirmed_entries": {
                "foods": [
                    {
                        "name": "김치찌개",
                        "meal_type": "lunch",
                        "nutrients": [{"name": "sodium", "amount": 1700, "unit": "mg"}],
                    },
                    {
                        "name": "햄 반찬",
                        "meal_type": "lunch",
                        "nutrients": [{"name": "sodium", "amount": 900, "unit": "mg"}],
                    },
                ]
            },
        },
    },
    "hypertension-sodium-dinner": {
        "message": "오늘 저녁 나트륨을 줄이려면 어떤 음식으로 바꾸면 좋아?",
        "context": {"profile": {"chronic_conditions": ["hypertension"]}},
    },
    "ldl-treatment": {
        "message": "LDL 검사 수치가 130인데 치료를 시작해야 해?",
        "context": {},
    },
    "supplement-drug-boundary": {
        "message": "혈압약을 먹는데 마그네슘 영양제를 같이 먹어도 돼?",
        "context": {"profile": {"chronic_conditions": ["hypertension"]}},
    },
    "magnesium-blood-pressure-med": {
        "message": "혈압약을 먹는데 마그네슘 영양제를 같이 먹어도 돼?",
        "context": {"profile": {"chronic_conditions": ["hypertension"]}},
    },
    "p0-grapefruit-lipid-med": {
        "message": "고지혈증 약 먹는데 자몽주스 마셔도 돼?",
        "context": {},
    },
    "kidney-vegetable-fruit-potassium": {
        "message": "신장질환이 있는데 채소랑 과일은 어떻게 골라야 해? 칼륨이 걱정돼",
        "context": {"profile": {"chronic_conditions": ["kidney_disease"]}},
    },
    "diabetes-overeating-next-meal": {
        "message": "당뇨가 있는데 점심에 밥 세 공기랑 초콜릿을 먹었어. 다음 끼니는 어떻게 조절해?",
        "context": {"profile": {"chronic_conditions": ["diabetes"]}},
    },
    "unknown-lithium-selenium": {
        "message": "리튬 약을 먹는데 셀레늄 영양제 같이 먹어도 돼?",
        "context": {},
    },
    "urgent-chest-pain": {
        "message": "가슴이 아프고 숨이 차",
        "context": {},
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ask Lemon Aid ChatbotAgent or the configured local LLM directly."
    )
    parser.add_argument("message", nargs="?", help="Question to ask the local chatbot.")
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        help="Use a built-in scenario for quick tone/boundary checks.",
    )
    parser.add_argument(
        "--llm",
        choices=("none", "ollama", "sglang"),
        default="none",
        help="Use a real local LLM instead of deterministic fallback.",
    )
    parser.add_argument(
        "--mode",
        choices=("chatbot", "raw"),
        default="chatbot",
        help="chatbot runs app safety/format guard; raw asks only the LLM.",
    )
    parser.add_argument("--model", help="Override model name.")
    parser.add_argument("--endpoint", help="Override LLM endpoint URL.")
    parser.add_argument("--api-key", help="SGLang/OpenAI-compatible API key.")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Keep asking questions until you type exit.",
    )
    args = parser.parse_args()

    if args.preset:
        scenario = PRESETS[args.preset]
        message = str(scenario["message"])
        context = dict(scenario["context"])
    elif args.message:
        message = args.message
        context = {}
    elif args.interactive:
        message = ""
        context = {}
    else:
        parser.error("provide a message or --preset")

    llm_client = _build_llm_client(args)

    if args.interactive:
        _run_interactive(args, llm_client, message, context)
        return

    _print_answer(args, llm_client, message, context)


def _build_llm_client(args: argparse.Namespace) -> OllamaClient | SGLangClient | None:
    if args.llm == "none":
        return None
    if args.llm == "ollama":
        return OllamaClient(
            model=args.model or os.getenv("OLLAMA_MODEL", "qwen3.5:9b"),
            endpoint=args.endpoint or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            timeout=args.timeout,
        )
    return SGLangClient(
        model=args.model or os.getenv("SGLANG_MODEL", "Qwen/Qwen2.5-0.5B-Instruct"),
        endpoint=args.endpoint or os.getenv("SGLANG_BASE_URL", "http://127.0.0.1:30000/v1"),
        api_key=args.api_key or os.getenv("SGLANG_API_KEY") or None,
        timeout=args.timeout,
    )


def _run_interactive(
    args: argparse.Namespace,
    llm_client: OllamaClient | SGLangClient | None,
    first_message: str,
    context: dict[str, object],
) -> None:
    print("Type a question and press Enter. Type exit to quit.")
    print()
    if first_message:
        _print_answer(args, llm_client, first_message, context)

    while True:
        try:
            message = input("\n질문> ").strip()
        except EOFError:
            break
        if message.casefold() in {"exit", "quit", "q"}:
            break
        if not message:
            continue
        _print_answer(args, llm_client, message, context)


def _print_answer(
    args: argparse.Namespace,
    llm_client: OllamaClient | SGLangClient | None,
    message: str,
    context: dict[str, object],
) -> None:
    if args.mode == "raw":
        if llm_client is None:
            raise SystemExit("--mode raw requires --llm ollama or --llm sglang")
        response = llm_client.generate(
            LLMRequest(
                messages=[
                    LLMMessage(
                        role="system",
                        content="Answer in Korean. Keep the answer concise and practical.",
                    ),
                    LLMMessage(role="user", content=message),
                ],
                temperature=0.2,
                max_tokens=700,
            )
        )
        print(response.text)
        print()
        print(f"provider: {response.provider}")
        print(f"model: {response.model}")
        return

    response = ChatbotAgent(llm_client=llm_client).answer(
        ChatbotRequest(
            request_id=f"local-chat-{uuid4()}",
            user_id="local-dev-user",
            message=message,
            context=context,
        )
    )

    print(response.message)
    print()
    print(f"provider: {response.provider}")
    print(f"answerability: {response.answerability}")
    if response.source_families:
        print(f"source_families: {', '.join(response.source_families)}")
    if response.sources:
        print("sources:")
        for source in response.sources:
            source_id = source.get("source_id", "unknown")
            version = source.get("version_label", "unknown")
            expires_at = source.get("expires_at", "unknown")
            print(f"- {source_id} | version={version} | expires_at={expires_at}")
    if response.safety_warnings:
        print("safety_warnings:")
        for warning in response.safety_warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
