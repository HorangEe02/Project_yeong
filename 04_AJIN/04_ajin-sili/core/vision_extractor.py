"""부서별 Vision 카드 (부록 K Phase 1~3) 공통 헬퍼.

각 endpoint 는 (1) 부서별 prompt + JSON 스키마 hint 정의 → (2) invoke_vision_json
호출 → (3) 후처리만 담당. 호출·재시도·JSON 파싱은 본 모듈에서 일관 처리한다.

설계 원칙:
- Vision LLM 응답을 ``json ... `` 코드블록으로 강제하고 정규식 추출.
- JSON 파싱 실패는 명시적 에러 객체로 반환 (호출자가 사용자에게 표시).
- 무음 fallback 금지 — 실패는 호출자가 인지하도록.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# JSON 코드블록 패턴 — Vision LLM 이 ``` 또는 ```json 으로 응답하도록 prompt 강제.
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def invoke_vision_json(
    prompt: str,
    image_bytes: bytes,
    *,
    schema_hint: str = "",
    model: str | None = None,
) -> dict[str, Any]:
    """Vision LLM 호출 + JSON 응답 파싱.

    Returns:
        성공: 파싱된 dict (스키마 형태)
        실패: {"_parse_error": True, "_raw": "원응답"} — 호출자가 명시적 처리.
    """
    from core.llm_client import auto_select_vision_model, invoke_vision

    final_model = model or auto_select_vision_model()
    if not final_model:
        return {"_parse_error": True, "_error": "vision_model_unavailable"}

    full_prompt = (
        f"{prompt}\n\n"
        f"반드시 다음 JSON 스키마 그대로 ```json ... ``` 코드블록으로 응답하세요.\n"
        f"부가 설명·markdown 표·다른 텍스트 금지.\n\n"
        f"스키마:\n{schema_hint}"
    )

    try:
        raw = invoke_vision(full_prompt, image_bytes, model=final_model)
    except Exception as e:
        logger.warning("[vision_extractor] LLM 호출 실패: %s", e)
        return {"_parse_error": True, "_error": str(e)}

    match = _JSON_BLOCK_RE.search(raw)
    payload = match.group(1) if match else raw.strip()

    try:
        parsed = json.loads(payload)
        if isinstance(parsed, dict):
            return parsed
        return {"items": parsed} if isinstance(parsed, list) else {"value": parsed}
    except json.JSONDecodeError as e:
        logger.info("[vision_extractor] JSON 파싱 실패: %s — raw 길이 %d", e, len(raw))
        return {"_parse_error": True, "_raw": raw}
