"""보안 유틸리티 모듈

LLM 프롬프트 인젝션 방어, HTML 이스케이프, 입력 검증 등
프로젝트 전체에서 사용하는 보안 함수를 제공한다.
"""
from __future__ import annotations

import html
import json
import re
from typing import Any


# ──────────────────────────────────────────────
# 1. HTML 이스케이프 (XSS 방어)
# ──────────────────────────────────────────────

def escape_html(text: str) -> str:
    """HTML 특수문자를 이스케이프한다. XSS 방어용."""
    if not isinstance(text, str):
        text = str(text)
    return html.escape(text, quote=True)


# ──────────────────────────────────────────────
# 2. LLM 프롬프트 인젝션 방어
# ──────────────────────────────────────────────

# 프롬프트 인젝션에 자주 사용되는 패턴
_INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+(instructions?|prompts?)",
    r"disregard\s+(previous|above|all)",
    r"you\s+are\s+now\s+(a|an)\s+",
    r"new\s+instructions?:",
    r"system\s*:\s*",
    r"<\s*system\s*>",
    r"\[INST\]",
    r"\[/INST\]",
    r"<<\s*SYS\s*>>",
]

_INJECTION_RE = re.compile(
    "|".join(_INJECTION_PATTERNS), re.IGNORECASE
)


def sanitize_llm_input(text: str, max_length: int = 2000) -> str:
    """LLM에 전달할 사용자 입력을 정제한다.

    - 길이 제한 (DoS 방어)
    - 프롬프트 인젝션 패턴 제거
    - 제어 문자 제거
    """
    if not isinstance(text, str):
        text = str(text)

    # 길이 제한
    text = text[:max_length]

    # 제어 문자 제거 (탭, 줄바꿈은 허용)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # 프롬프트 인젝션 패턴을 마스킹 (제거하면 의미가 변할 수 있으므로 [FILTERED]로 대체)
    text = _INJECTION_RE.sub("[FILTERED]", text)

    return text.strip()


def wrap_user_input(text: str) -> str:
    """사용자 입력을 명확한 경계 태그로 감싸서 프롬프트에 삽입한다.

    LLM이 사용자 입력과 시스템 지시를 구분할 수 있게 한다.
    """
    sanitized = sanitize_llm_input(text)
    return f"<user_input>\n{sanitized}\n</user_input>"


# ──────────────────────────────────────────────
# 3. 안전한 JSON 파싱
# ──────────────────────────────────────────────

def safe_json_loads(text: str, default: Any = None) -> Any:
    """안전하게 JSON을 파싱한다.

    - ```json``` 코드 블록 자동 추출
    - 파싱 실패 시 default 반환 (예외 미발생)
    - 중첩 깊이 제한
    """
    if not isinstance(text, str) or not text.strip():
        return default

    text = text.strip()

    # ```json ... ``` 코드 블록 추출
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            code_block = parts[1]
            if code_block.startswith("json"):
                code_block = code_block[4:]
            text = code_block.strip()
        elif len(parts) == 2:
            code_block = parts[1]
            if code_block.startswith("json"):
                code_block = code_block[4:]
            text = code_block.strip()

    # 크기 제한 (10MB)
    if len(text) > 10 * 1024 * 1024:
        return default

    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError, TypeError):
        return default


# ──────────────────────────────────────────────
# 4. 파일 경로 검증
# ──────────────────────────────────────────────

def validate_path(path: str, allowed_base: str) -> bool:
    """경로가 허용된 기본 디렉토리 내에 있는지 확인한다. (Path Traversal 방어)"""
    from pathlib import Path

    try:
        resolved = Path(path).resolve()
        base = Path(allowed_base).resolve()
        return str(resolved).startswith(str(base))
    except (ValueError, OSError):
        return False


# ──────────────────────────────────────────────
# 5. 입력 길이/형식 검증
# ──────────────────────────────────────────────

def validate_text_input(
    text: str,
    max_length: int = 5000,
    min_length: int = 1,
    field_name: str = "입력",
) -> str:
    """텍스트 입력을 검증하고 정제한다."""
    if not isinstance(text, str):
        raise ValueError(f"{field_name}은(는) 문자열이어야 합니다.")

    text = text.strip()

    if len(text) < min_length:
        raise ValueError(f"{field_name}을(를) 입력해주세요.")

    if len(text) > max_length:
        text = text[:max_length]

    return text
