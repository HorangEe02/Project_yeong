"""
온보딩/업무 챗봇 스트리밍 응답 엔진
- Ollama stream API 직접 호출
- thinking 토큰 필터링
- 업무 모드 [요약]/[상세] 구조 실시간 파싱
"""

import requests
import json
import re
from typing import Generator, Optional


def stream_chat_response(
    prompt: str,
    system_prompt: str = "",
    model: str = "qwen3.5:latest",
    temperature: float = 0.5,
    max_tokens: int = 2048,
) -> Generator[str, None, None]:
    """
    Ollama 스트리밍 응답 제너레이터

    Yields:
        토큰 문자열 (thinking 태그 제외)
    """
    url = "http://localhost:11434/api/generate"

    messages_prompt = prompt
    if system_prompt:
        messages_prompt = f"{system_prompt}\n\n{prompt}"

    try:
        response = requests.post(
            url,
            json={
                "model": model,
                "prompt": messages_prompt,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "top_p": 0.9,
                },
            },
            stream=True,
            timeout=120,
        )
        response.raise_for_status()

        in_thinking = False

        for line in response.iter_lines():
            if not line:
                continue

            try:
                chunk = json.loads(line)
                token = chunk.get("response", "")

                # thinking 태그 필터링
                if "<think>" in token:
                    in_thinking = True
                    continue
                if "</think>" in token:
                    in_thinking = False
                    continue
                if in_thinking:
                    continue

                if token:
                    yield token

                if chunk.get("done", False):
                    break

            except json.JSONDecodeError:
                continue

    except requests.exceptions.ConnectionError:
        yield "[오류] Ollama 서버에 연결할 수 없습니다."
    except Exception as e:
        yield f"[오류] {str(e)}"


def render_streaming_response(
    prompt: str,
    system_prompt: str,
    container,
    model: str = "qwen3.5:latest",
    mode: str = "onboarding",
) -> str:
    """
    Streamlit 컨테이너에 스트리밍 렌더링

    Args:
        container: st.empty() 객체
        mode: "onboarding" (전체 출력) 또는 "work" (요약/상세 분리)

    Returns:
        완성된 전체 텍스트
    """
    full_text = ""

    for token in stream_chat_response(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
    ):
        full_text += token
        # 실시간 업데이트 (커서 표시)
        container.markdown(full_text + "▌")

    # 최종 렌더링 (커서 제거)
    container.markdown(full_text)

    return full_text
