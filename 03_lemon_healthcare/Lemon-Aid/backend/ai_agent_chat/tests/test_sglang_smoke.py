"""Opt-in SGLang local server smoke test."""

from __future__ import annotations

import os

import pytest
from lemon_ai_agent.llm import LLMMessage, LLMRequest, SGLangClient


@pytest.mark.skipif(
    os.getenv("RUN_SGLANG_SMOKE") != "1",
    reason="SGLang smoke test requires RUN_SGLANG_SMOKE=1 and a local server.",
)
def test_sglang_local_server_smoke() -> None:
    """Verify an explicitly configured local SGLang server accepts chat completions."""
    client = SGLangClient(
        endpoint=os.getenv("SGLANG_BASE_URL", "http://127.0.0.1:30000/v1"),
        model=os.getenv("SGLANG_MODEL", "qwen-test"),
        api_key=os.getenv("SGLANG_API_KEY") or None,
        timeout=float(os.getenv("SGLANG_SMOKE_TIMEOUT_SECONDS", "30")),
    )

    response = client.generate(
        LLMRequest(
            messages=[
                LLMMessage(
                    role="user",
                    content="Return the word ok.",
                )
            ],
            temperature=0,
            max_tokens=16,
        )
    )

    assert response.provider == "sglang"
    assert response.text.strip()
