"""OCR accuracy metrics — CER, WER, exact-match, field-level evaluation.

Brand-New-update follow-up: OCR 정확도 95% 목표 검증 인프라.

지원 지표:
    - CER (Character Error Rate): 한·영 혼합 텍스트 전반 정확도. 95% 목표 = CER ≤ 5%.
    - WER (Word Error Rate): 단어 단위 오류율 (공백 기준 토큰화).
    - exact_match: 정규화 후 완전 일치 여부 (0/1).
    - field_exact_match: product_name/ingredients/dosage 등 추출 필드별 일치율.

정규화 정책:
    - 양끝 공백 제거 + 연속 공백을 단일 스페이스로 축약.
    - 줄바꿈/탭은 스페이스로 치환.
    - 대소문자는 ``case_sensitive=False`` 옵션으로 무시 가능 (기본 True — 'C'≠'c').

라이선스: rapidfuzz (MIT) — Levenshtein 거리 C++ 구현.

Reference:
    docs/dev-guides/07-ocr-pipeline.md §7
    https://github.com/rapidfuzz/RapidFuzz
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

from rapidfuzz.distance import Levenshtein

from src.ocr.text_normalizer import normalize_ocr_text

_WHITESPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")
"""연속 공백/줄바꿈/탭을 단일 스페이스로 축약하기 위한 정규식."""


def normalize_text(text: str, *, case_sensitive: bool = True) -> str:
    """비교 전 정규화 — NFC 유니코드 + 단위·한·영 공백 정규화 + 공백 축약 + (옵션) 대소문자.

    Args:
        text: 원본 텍스트.
        case_sensitive: ``False`` 면 소문자로 통일.

    Returns:
        정규화된 텍스트.

    Examples:
        >>> normalize_text("비타민  C  1000mg\\n")
        '비타민 C 1000mg'
        >>> normalize_text("비타민C1000ug")
        '비타민 C1000μg'
        >>> normalize_text("Vitamin C", case_sensitive=False)
        'vitamin c'
    """
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalize_ocr_text(normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    if not case_sensitive:
        normalized = normalized.lower()
    return normalized


def cer(pred: str, gt: str, *, case_sensitive: bool = True) -> float:
    """문자 단위 오류율 (Character Error Rate).

    공식: ``CER = edit_distance(pred, gt) / max(len(gt), 1)``.
    한·영 혼합 텍스트에서 글자 단위 정확도를 측정하기에 적합 (한글 자모 단위가
    아닌 완성형 음절 단위).

    Args:
        pred: OCR 예측 텍스트.
        gt: ground-truth 텍스트.
        case_sensitive: 대소문자 구분 여부.

    Returns:
        CER ∈ [0.0, ∞). 보통 ≤ 1.0; pred 가 매우 길어 무관한 글자가 많으면 >1.0 가능.
        ``gt`` 가 빈 문자열인데 ``pred`` 도 비어 있으면 ``0.0``.

    Examples:
        >>> cer("비타민 C", "비타민 C")
        0.0
        >>> cer("비타민C", "비타민 C")  # 공백 1개 누락
        0.0
        >>> cer("비타민D", "비타민 C")  # 정규화 후 'D' vs 'C' — 1글자 차이
        0.125
    """
    pred_n = normalize_text(pred, case_sensitive=case_sensitive)
    gt_n = normalize_text(gt, case_sensitive=case_sensitive)
    if not gt_n:
        return 0.0 if not pred_n else float("inf")
    distance = Levenshtein.distance(pred_n, gt_n)
    return distance / len(gt_n)


def wer(pred: str, gt: str, *, case_sensitive: bool = True) -> float:
    """단어 단위 오류율 (Word Error Rate).

    토큰화: 정규화된 텍스트를 공백으로 split.

    Args:
        pred: OCR 예측 텍스트.
        gt: ground-truth 텍스트.
        case_sensitive: 대소문자 구분 여부.

    Returns:
        WER ∈ [0.0, ∞). ``gt`` 가 빈 토큰이면 pred 도 비었을 때 ``0.0``,
        그 외에는 ``inf``.

    Examples:
        >>> wer("비타민 C 1000mg", "비타민 C 1000mg")
        0.0
        >>> wer("비타민 D 1000mg", "비타민 C 1000mg")  # 1/3 단어 다름
        0.333...
    """
    pred_tokens = normalize_text(pred, case_sensitive=case_sensitive).split()
    gt_tokens = normalize_text(gt, case_sensitive=case_sensitive).split()
    if not gt_tokens:
        return 0.0 if not pred_tokens else float("inf")
    distance = Levenshtein.distance(pred_tokens, gt_tokens)
    return distance / len(gt_tokens)


def exact_match(pred: str, gt: str, *, case_sensitive: bool = True) -> bool:
    """정규화 후 완전 일치 여부.

    Args:
        pred: OCR 예측 텍스트.
        gt: ground-truth 텍스트.
        case_sensitive: 대소문자 구분 여부.

    Returns:
        정규화된 두 텍스트가 동일하면 ``True``.

    Examples:
        >>> exact_match("비타민  C", "비타민 C")
        True
        >>> exact_match("Vitamin C", "vitamin c")
        False
        >>> exact_match("Vitamin C", "vitamin c", case_sensitive=False)
        True
    """
    return normalize_text(pred, case_sensitive=case_sensitive) == normalize_text(
        gt, case_sensitive=case_sensitive
    )


FieldValue = str | list[str] | None
"""필드 값 타입 — 문자열(product_name/dosage) 또는 리스트(ingredients) 또는 부재."""


def _values_match(
    pred: FieldValue,
    gt: FieldValue,
    *,
    case_sensitive: bool,
) -> bool:
    """단일 필드 값 비교 — 문자열/리스트/None 분기.

    Args:
        pred: 예측 값.
        gt: 정답 값.
        case_sensitive: 대소문자 구분.

    Returns:
        정규화 후 일치 여부.
    """
    if gt is None and pred is None:
        return True
    if gt is None or pred is None:
        return False
    if isinstance(gt, list) and isinstance(pred, list):
        if len(gt) != len(pred):
            return False
        return all(
            exact_match(p, g, case_sensitive=case_sensitive) for p, g in zip(pred, gt, strict=True)
        )
    if isinstance(gt, str) and isinstance(pred, str):
        return exact_match(pred, gt, case_sensitive=case_sensitive)
    # 타입 불일치 (예: list vs str) 는 미스매치.
    return False


def field_exact_match(
    pred_fields: dict[str, FieldValue],
    gt_fields: dict[str, FieldValue],
    *,
    case_sensitive: bool = True,
) -> dict[str, bool]:
    """필드별 exact-match 평가 — product_name / ingredients / dosage 등.

    추출기(``field_extractor``)가 반환한 필드 dict 끼리 비교한다. 정답이 ``None``
    이면 예측도 ``None`` 이어야 일치로 처리한다 (필드 부재 일치).
    리스트 값(``ingredients``) 은 길이 + 순서대로의 element-wise 정규화 비교.

    Args:
        pred_fields: 예측 필드 dict.
        gt_fields: 정답 필드 dict.
        case_sensitive: 대소문자 구분 여부.

    Returns:
        ``{field_name: bool}`` 매핑. ``gt_fields`` 에 있는 키만 평가하며
        ``pred_fields`` 의 추가 키는 무시된다.

    Examples:
        >>> field_exact_match(
        ...     {"product_name": "비타민C", "dosage": "1000mg"},
        ...     {"product_name": "비타민 C", "dosage": "1000mg"},
        ... )
        {'product_name': True, 'dosage': True}
        >>> field_exact_match(
        ...     {"ingredients": ["비타민 C", "비타민 D"]},
        ...     {"ingredients": ["비타민 C", "비타민 D"]},
        ... )
        {'ingredients': True}
    """
    result: dict[str, bool] = {}
    for key, gt_value in gt_fields.items():
        pred_value = pred_fields.get(key)
        result[key] = _values_match(pred_value, gt_value, case_sensitive=case_sensitive)
    return result


def field_match_ratio(
    pred_fields: dict[str, FieldValue],
    gt_fields: dict[str, FieldValue],
    *,
    case_sensitive: bool = True,
) -> float:
    """필드 exact-match 평균 비율 — 95% 목표 측정값.

    Args:
        pred_fields: 예측 필드 dict.
        gt_fields: 정답 필드 dict.
        case_sensitive: 대소문자 구분 여부.

    Returns:
        ``0.0 ~ 1.0`` 의 비율. ``gt_fields`` 가 비어 있으면 ``1.0`` (vacuously true).

    Examples:
        >>> field_match_ratio(
        ...     {"product_name": "비타민 C", "dosage": "999mg"},
        ...     {"product_name": "비타민 C", "dosage": "1000mg"},
        ... )
        0.5
    """
    matches = field_exact_match(pred_fields, gt_fields, case_sensitive=case_sensitive)
    if not matches:
        return 1.0
    return sum(matches.values()) / len(matches)
