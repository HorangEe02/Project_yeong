"""Language-segmented text accuracy metrics.

Provides character-level and word-level error rate calculations split by
script (Korean vs English) so that OCR evaluation can report 한/영 accuracy
separately. The implementation uses only the Python standard library so no
third-party edit-distance package needs to be added to requirements.

Reference:
    outputs/todo-list/2026-05-21/project-status-report.md §6 P0-3
"""

from __future__ import annotations

from typing import Literal

LanguageTag = Literal["ko", "en", "other"]
"""한국어/영문/기타 태그."""

_HANGUL_SYLLABLE_START = 0xAC00
"""한글 음절 시작 코드 포인트 (가)."""

_HANGUL_SYLLABLE_END = 0xD7A3
"""한글 음절 끝 코드 포인트 (힣)."""

_HANGUL_JAMO_START = 0x1100
"""한글 자모 시작 코드 포인트."""

_HANGUL_JAMO_END = 0x11FF
"""한글 자모 끝 코드 포인트."""

_HANGUL_COMPAT_JAMO_START = 0x3130
"""한글 호환 자모 시작 코드 포인트 (ㄱ)."""

_HANGUL_COMPAT_JAMO_END = 0x318F
"""한글 호환 자모 끝 코드 포인트 (ㆎ)."""


def classify_char_language(char: str) -> LanguageTag:
    """단일 문자를 한국어/영문/기타로 분류한다.

    Args:
        char: 분류할 단일 문자.

    Returns:
        ``"ko"`` (한글 음절·자모), ``"en"`` (ASCII 알파벳), ``"other"`` (그 외).

    Raises:
        ValueError: ``char`` 가 정확히 1 문자가 아닌 경우.

    Examples:
        >>> classify_char_language("가")
        'ko'
        >>> classify_char_language("A")
        'en'
        >>> classify_char_language("1")
        'other'
    """
    if len(char) != 1:
        raise ValueError(f"char must be a single character, got length {len(char)}")
    code_point = ord(char)
    if _HANGUL_SYLLABLE_START <= code_point <= _HANGUL_SYLLABLE_END:
        return "ko"
    if _HANGUL_JAMO_START <= code_point <= _HANGUL_JAMO_END:
        return "ko"
    if _HANGUL_COMPAT_JAMO_START <= code_point <= _HANGUL_COMPAT_JAMO_END:
        return "ko"
    if ("a" <= char <= "z") or ("A" <= char <= "Z"):
        return "en"
    return "other"


def _flush_buffer(
    buffer: list[str],
    lang: LanguageTag,
    ko_tokens: list[str],
    en_tokens: list[str],
) -> None:
    """``buffer`` 내용을 ``lang`` 에 따라 토큰 목록에 합쳐 넣는다.

    Args:
        buffer: 누적된 문자 리스트.
        lang: 누적된 문자의 언어 태그 (``"ko"`` 또는 ``"en"``).
        ko_tokens: 한국어 토큰 누적 리스트.
        en_tokens: 영문 토큰 누적 리스트.
    """
    if not buffer:
        return
    joined = "".join(buffer)
    if lang == "ko":
        ko_tokens.append(joined)
    elif lang == "en":
        en_tokens.append(joined)


def split_text_by_language(text: str) -> dict[Literal["ko", "en"], str]:
    """텍스트를 한국어/영문 부분으로 분리한다.

    각 언어의 연속된 문자 시퀀스를 공백 하나로 구분해 합쳐서 반환한다.
    기타 문자(숫자, 기호 등)는 어느 쪽에도 포함되지 않는다.

    Args:
        text: 분리 대상 원본 문자열.

    Returns:
        ``{"ko": <한국어 부분>, "en": <영문 부분>}`` 형태의 사전.

    Examples:
        >>> result = split_text_by_language("비타민 C 100 mg")
        >>> result["ko"]
        '비타민'
        >>> result["en"]
        'C mg'
    """
    ko_tokens: list[str] = []
    en_tokens: list[str] = []
    current_lang: LanguageTag | None = None
    buffer: list[str] = []
    for char in text:
        lang: LanguageTag = classify_char_language(char) if char.strip() else "other"
        if lang == "other":
            if current_lang is not None:
                _flush_buffer(buffer, current_lang, ko_tokens, en_tokens)
                current_lang = None
                buffer = []
            continue
        if current_lang is not None and current_lang != lang:
            _flush_buffer(buffer, current_lang, ko_tokens, en_tokens)
            buffer = []
        current_lang = lang
        buffer.append(char)
    if current_lang is not None:
        _flush_buffer(buffer, current_lang, ko_tokens, en_tokens)
    return {
        "ko": " ".join(ko_tokens),
        "en": " ".join(en_tokens),
    }


def levenshtein_distance(hypothesis: str, reference: str) -> int:
    """Levenshtein 편집 거리를 계산한다.

    표준 O(n*m) 동적 계획법. 메모리 절감을 위해 두 줄만 유지한다.

    Args:
        hypothesis: 비교 대상 문자열 (가설).
        reference: 기준 문자열 (정답).

    Returns:
        삽입·삭제·치환 1회씩을 비용 1로 계산한 최소 편집 횟수.

    Examples:
        >>> levenshtein_distance("kitten", "sitting")
        3
        >>> levenshtein_distance("", "abc")
        3
        >>> levenshtein_distance("abc", "abc")
        0
    """
    if hypothesis == reference:
        return 0
    if not hypothesis:
        return len(reference)
    if not reference:
        return len(hypothesis)
    previous_row = list(range(len(reference) + 1))
    for i, hyp_char in enumerate(hypothesis, start=1):
        current_row = [i] + [0] * len(reference)
        for j, ref_char in enumerate(reference, start=1):
            cost_substitute = previous_row[j - 1] + (0 if hyp_char == ref_char else 1)
            cost_insert = current_row[j - 1] + 1
            cost_delete = previous_row[j] + 1
            current_row[j] = min(cost_substitute, cost_insert, cost_delete)
        previous_row = current_row
    return previous_row[-1]


def character_error_rate(hypothesis: str, reference: str) -> float:
    """문자 단위 오류율(CER)을 계산한다.

    CER = edit_distance(hypothesis, reference) / max(len(reference), 1).
    분모가 0이면 빈 가설은 0.0, 비빈 가설은 1.0을 반환한다 (관례적 정의).

    Args:
        hypothesis: 비교 대상 문자열.
        reference: 기준 문자열.

    Returns:
        0.0 이상의 CER 값. 일반적으로 0.0~1.0 사이이나, 가설이 기준보다 길면 1.0을 초과할 수 있다.

    Examples:
        >>> character_error_rate("비타민C", "비타민 C")
        0.2
        >>> character_error_rate("", "abc")
        1.0
        >>> character_error_rate("abc", "abc")
        0.0
    """
    if not reference:
        return 0.0 if not hypothesis else 1.0
    distance = levenshtein_distance(hypothesis, reference)
    return distance / len(reference)


def word_error_rate(hypothesis: str, reference: str) -> float:
    """단어 단위 오류율(WER)을 계산한다.

    공백 기반 토큰화 후 word-level edit distance를 계산한다.

    Args:
        hypothesis: 비교 대상 문자열.
        reference: 기준 문자열.

    Returns:
        0.0 이상의 WER 값.

    Examples:
        >>> word_error_rate("the cat sat", "the cat sat")
        0.0
        >>> word_error_rate("the cat", "the cat sat")
        0.3333333333333333
        >>> word_error_rate("", "a b c")
        1.0
    """
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    distance = _token_edit_distance(hyp_words, ref_words)
    return distance / len(ref_words)


def _token_edit_distance(hyp_tokens: list[str], ref_tokens: list[str]) -> int:
    """토큰 시퀀스에 대한 Levenshtein 거리를 계산한다.

    Args:
        hyp_tokens: 가설 토큰 시퀀스.
        ref_tokens: 기준 토큰 시퀀스.

    Returns:
        삽입·삭제·치환 1회씩을 비용 1로 계산한 최소 편집 횟수.
    """
    if hyp_tokens == ref_tokens:
        return 0
    if not hyp_tokens:
        return len(ref_tokens)
    if not ref_tokens:
        return len(hyp_tokens)
    previous_row = list(range(len(ref_tokens) + 1))
    for i, hyp_token in enumerate(hyp_tokens, start=1):
        current_row = [i] + [0] * len(ref_tokens)
        for j, ref_token in enumerate(ref_tokens, start=1):
            cost_substitute = previous_row[j - 1] + (0 if hyp_token == ref_token else 1)
            cost_insert = current_row[j - 1] + 1
            cost_delete = previous_row[j] + 1
            current_row[j] = min(cost_substitute, cost_insert, cost_delete)
        previous_row = current_row
    return previous_row[-1]


LanguageMetricKey = Literal["cer_ko", "cer_en", "wer_ko", "wer_en"]
"""한/영 분리 메트릭 키."""


def language_segmented_error_rates(
    hypothesis: str,
    reference: str,
) -> dict[LanguageMetricKey, float]:
    """텍스트를 한국어/영문 부분으로 분리한 뒤 각 언어별 CER/WER을 계산한다.

    한국어 또는 영문 부분이 기준 텍스트에서 비어 있는 경우, 해당 키의 값은
    ``character_error_rate`` / ``word_error_rate`` 의 관례적 정의 ("ref 가 비고
    hyp 도 비면 0.0, ref 가 비고 hyp 는 있으면 1.0") 를 따른다.

    Args:
        hypothesis: 비교 대상 문자열 (OCR 결과 등).
        reference: 기준 문자열 (ground truth).

    Returns:
        ``{"cer_ko", "cer_en", "wer_ko", "wer_en"}`` 키를 모두 포함하는 사전.

    Examples:
        >>> rates = language_segmented_error_rates("비타민 C", "비타민 C")
        >>> rates["cer_ko"]
        0.0
        >>> rates["cer_en"]
        0.0
    """
    hyp_split = split_text_by_language(hypothesis)
    ref_split = split_text_by_language(reference)
    return {
        "cer_ko": character_error_rate(hyp_split["ko"], ref_split["ko"]),
        "cer_en": character_error_rate(hyp_split["en"], ref_split["en"]),
        "wer_ko": word_error_rate(hyp_split["ko"], ref_split["ko"]),
        "wer_en": word_error_rate(hyp_split["en"], ref_split["en"]),
    }
