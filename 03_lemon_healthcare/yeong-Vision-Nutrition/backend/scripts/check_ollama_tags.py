"""Ollama 모델 태그 실재성 검증 — D5 수리.

``config.py`` 와 ``.env.example`` 의 ``OLLAMA_MODEL`` / ``OLLAMA_MULTIMODAL_MODEL``
태그가 Ollama 공식 레지스트리(``https://ollama.com/library``)에 실제로 존재하는지
검증한다. 잘못된 태그는 ``ollama pull`` 첫 시도에서 실패하므로 PR 단계에서 미리
차단한다.

CI lint 단계에서 실행. 실패하면 build fail.

Reference:
    /Users/yeong/.claude/plans/ocr-yolo-sprightly-neumann.md §3.1 D5
    /Users/yeong/.claude/plans/lemon-track-b/phase-00-bootstrap.md Step 7
    docs/12-local-llm-ollama-migration.md §3
"""

from __future__ import annotations

import sys
from typing import Final

import httpx

OLLAMA_LIBRARY_BASE: Final[str] = "https://ollama.com/library"

# config.py / .env.example 과 동기화. 변경 시 양쪽 모두 수정.
TAGS_TO_CHECK: Final[list[str]] = [
    "qwen3.5:9b",
    "gemma4:e4b",
]

REQUEST_TIMEOUT_SEC: Final[float] = 10.0


def check_tag_exists(tag: str) -> bool:
    """Ollama 레지스트리 페이지에서 태그 존재 여부를 검증한다.

    Args:
        tag: ``<model>:<variant>`` 형식의 태그 (예: ``qwen3.5:9b``).

    Returns:
        존재하면 True. 네트워크 실패·태그 부재 모두 False.

    Raises:
        ValueError: 태그 형식이 ``<name>:<variant>`` 가 아닐 때.

    Examples:
        >>> check_tag_exists("definitely:not-a-real-tag")
        False
    """
    if ":" not in tag:
        raise ValueError(f"Tag must be '<name>:<variant>', got: {tag!r}")
    name, variant = tag.split(":", 1)
    url = f"{OLLAMA_LIBRARY_BASE}/{name}/tags"
    try:
        resp = httpx.get(
            url,
            timeout=REQUEST_TIMEOUT_SEC,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        print(f"[ERROR] Failed to reach {url}: {exc}", file=sys.stderr)
        return False
    if resp.status_code != 200:
        print(f"[ERROR] {url} -> HTTP {resp.status_code}", file=sys.stderr)
        return False
    return variant in resp.text


def main() -> int:
    """Entry point — 모든 태그 확인. 미존재 태그가 1개라도 있으면 ``exit 1``."""
    missing: list[str] = []
    for tag in TAGS_TO_CHECK:
        if check_tag_exists(tag):
            print(f"[OK]      {tag}")
        else:
            print(f"[MISSING] {tag}")
            missing.append(tag)
    if missing:
        print(
            "\nDetected unknown Ollama tag(s). "
            "Update backend/src/config.py and backend/.env.example to use "
            "existing tags from https://ollama.com/library, and sync "
            "docs/12-local-llm-ollama-migration.md §3 first.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
