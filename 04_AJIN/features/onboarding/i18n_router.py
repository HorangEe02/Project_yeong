"""v4.7 C-2 — 챗봇 응답 다국어(KO/EN) 라우팅.

3 책임:
1. detect_language(text) — 한글 유니코드 비율 단순 판정 (외부 라이브러리 0).
2. verify_response_language(text, target) — 응답이 target 언어로 작성됐는지 검증.
3. localize_response_if_needed(text, target) — 위반 시 1회 재요청을 통한 강제 변환.

설계 결정:
- 'auto' 모드 시 사용자 query 의 언어를 감지해 그대로 응답 언어로 사용.
- 한글 유니코드 비율 0.3 임계 — 짧은 영문 단어가 섞인 한국어를 ko 로 보수적 판정.
- verify 실패 시 재요청 1회 한도 (무한 루프 방지). 두 번째 실패는 원본 그대로 반환.

호출 지점: features/onboarding/onboarding_bot.OnboardingBot.answer()
"""

from __future__ import annotations

import logging
import re
from typing import Literal, Optional

logger = logging.getLogger(__name__)

Language = Literal["ko", "en"]
LanguageOrAuto = Literal["ko", "en", "auto"]

# 한국어 유니코드 범위 — 한글 음절 영역(가-힣) 기준.
# 자모(ᄀ-ᇿ)나 호환자모(ㄱ-ㆎ)는 사용 빈도가 낮아 음절만 카운트.
_HANGUL_SYLLABLE_RE = re.compile(r"[가-힣]")
# 영문 알파벳
_LATIN_RE = re.compile(r"[A-Za-z]")

# 한국어 판정 임계: 한글 비율이 이 값 이상이면 'ko'
_KO_THRESHOLD = 0.30


def detect_language(text: str) -> Language:
    """질의 텍스트의 주 언어를 감지한다.

    한글 음절이 전체 알파넘 문자(한글+라틴) 중 30% 이상이면 'ko', 미만이면 'en'.
    빈 문자열·숫자만 / 기호만 입력은 'ko' (사내 기본 언어).
    """
    if not text:
        return "ko"
    han = len(_HANGUL_SYLLABLE_RE.findall(text))
    lat = len(_LATIN_RE.findall(text))
    total = han + lat
    if total == 0:
        return "ko"
    ratio = han / total
    return "ko" if ratio >= _KO_THRESHOLD else "en"


def verify_response_language(text: str, target: Language) -> bool:
    """응답 텍스트가 target 언어로 작성됐는지 검증한다.

    target='ko': 한글 음절이 라틴 문자 대비 0.3+ 이면 통과
    target='en': 라틴이 한글 대비 0.7+ 이면 통과 (전문용어로 한글 일부 포함 허용)

    너무 짧은(<20자) 또는 코드블록 위주 응답은 검증 통과 (false-negative 회피).
    """
    if not text or len(text) < 20:
        return True
    han = len(_HANGUL_SYLLABLE_RE.findall(text))
    lat = len(_LATIN_RE.findall(text))
    total = han + lat
    if total == 0:
        return True

    if target == "ko":
        return (han / total) >= _KO_THRESHOLD
    # target == 'en'
    return (lat / total) >= 0.70


def build_language_instruction(target: Language) -> str:
    """system prompt 에 주입할 언어 강제 지시문."""
    if target == "ko":
        return (
            "반드시 한국어로만 답변하세요. 전문 용어(예: 8D, PPAP, REACH)는 영문 그대로 사용 가능합니다."
        )
    return (
        "Respond strictly in English. You may keep Korean proper nouns (e.g., department names) "
        "in their original form, but all narrative text must be in English."
    )


async def localize_response_if_needed(
    response_text: str,
    target: Language,
    retry_fn: Optional[callable] = None,
) -> str:
    """응답이 target 언어 위반 시 1회 재요청으로 변환.

    Args:
        response_text: LLM 원본 응답
        target: 목표 언어
        retry_fn: async callable(prompt: str) -> str. 없으면 검증 실패 시 원본 그대로 반환.

    Returns:
        검증 통과 시 원본, 위반 + retry_fn 제공 시 재요청 결과, 그 외 원본.
    """
    if verify_response_language(response_text, target):
        return response_text

    if retry_fn is None:
        logger.info("language verify failed (target=%s) but no retry_fn — returning original", target)
        return response_text

    instruction = build_language_instruction(target)
    retry_prompt = (
        f"The following text must be rewritten in the target language.\n"
        f"{instruction}\n\n"
        f"Original text:\n{response_text}\n\n"
        f"Rewritten version (target language only):"
    )
    try:
        retried = await retry_fn(retry_prompt)
    except Exception:
        logger.exception("language retry failed")
        return response_text

    # 두 번째 검증 — 실패해도 그대로 반환 (재시도 1회 한도)
    if isinstance(retried, str) and retried.strip():
        return retried
    return response_text


def resolve_language(query: str, requested: LanguageOrAuto) -> Language:
    """요청된 언어(auto 포함)와 query 를 종합해 최종 언어를 결정."""
    if requested == "auto":
        return detect_language(query)
    return requested
