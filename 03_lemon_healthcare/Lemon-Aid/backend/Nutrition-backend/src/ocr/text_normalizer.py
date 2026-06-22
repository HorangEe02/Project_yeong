"""OCR 후처리 정규화 — 유니코드 단위 + 한·영 경계 공백.

베이스라인 측정(2026-05-20)에서 발견된 빈도 높은 오류 패턴을 흡수하는 모듈.

처리:
    1. micro sign(``µ`` U+00B5) → Greek mu(``μ`` U+03BC) 통일.
    2. ASCII ``u`` 가 숫자 뒤 단위 자리에 등장(``1000ug``)할 때 ``μ`` 로 교정.
    3. 복합 단위 사이 공백 보장 — ``μgRAE`` → ``μg RAE``.
    4. ``α-TE`` 변형(``a-TE``) 정규화.
    5. 한글 ↔ 영문/숫자 경계 자동 공백 삽입 — ``비타민C`` → ``비타민 C``.

설계 원칙:
    - 결정론적, 순수 함수. 사이드 이펙트 없음.
    - GT 와 OCR 양쪽에 동일하게 적용해 mismatch 표면적을 줄이는 것이 목적.
    - 일반 영어 단어 안의 ``ug`` (예: ``August``) 는 손대지 않음 — 숫자 뒤 또는
      단위 키워드 직전에서만 교정.

Reference:
    docs/ocr_baseline_reports/baseline_summary.md §5
    backend/src/ocr/metrics.py
"""

from __future__ import annotations

import re
from typing import Final

MICRO_SIGN: Final[str] = "µ"
"""U+00B5 micro sign — Unicode 호환 분류로 인해 일부 폰트·OCR이 사용."""
GREEK_MU: Final[str] = "μ"
"""U+03BC greek small letter mu — KDRIs 표준 형식."""

# 단위 정규화: 모두 ``Greek mu`` 와 ``α`` 로 통일하고 사이 공백 보장.
# 패턴은 순서대로 적용된다 — 광범위 → 협소 순서로 두면 안 됨 (먼저 매치된 자리에 사이가 덮어쓰임).
_UNIT_RULES: Final[list[tuple[re.Pattern[str], str]]] = [
    # 1. micro sign → greek mu (간단 치환)
    # 별도 처리 — 정규식 아닌 직접 replace.
    # 2. 숫자 뒤 단위 자리의 ASCII u → μ
    #    "1000ug" / "10 ug" / "10ug RAE" 같은 경우만 잡고 "August" 같은 단어는 건드리지 않음.
    (re.compile(r"(\d+\s*)u(g)(?=\s*(?:RAE|DFE|NE|TE|\b))", re.IGNORECASE), r"\1μ\2"),
    # 3. 단위 사이 공백 보장 — μg{RAE|DFE} → μg \1
    (re.compile(r"(μg)\s*(RAE|DFE)\b", re.IGNORECASE), r"\1 \2"),
    # 4. mg NE 사이 공백 보장
    (re.compile(r"(mg)\s*(NE)\b", re.IGNORECASE), r"\1 \2"),
    # 5. mg α-TE / mg a-TE → mg α-TE
    (re.compile(r"(mg)\s*[aα]-?TE\b", re.IGNORECASE), r"\1 α-TE"),
]


def normalize_units(text: str) -> str:
    """단위 표기를 KDRIs 표준 형식으로 정규화.

    Args:
        text: OCR 또는 GT 텍스트.

    Returns:
        정규화된 텍스트.

    Examples:
        >>> normalize_units("1000ug RAE")
        '1000μg RAE'
        >>> normalize_units("50µg DFE")
        '50μg DFE'
        >>> normalize_units("12mga-TE")
        '12mg α-TE'
        >>> normalize_units("100mgNE")
        '100mg NE'
    """
    out = text.replace(MICRO_SIGN, GREEK_MU)
    for pattern, replacement in _UNIT_RULES:
        out = pattern.sub(replacement, out)
    return out


# 한글 ↔ 영문/숫자 경계 — 한글 음절(가-힣) 직후·직전의 ASCII alnum 에 공백 삽입.
_KO_TO_ALNUM: Final[re.Pattern[str]] = re.compile(r"([가-힣])([A-Za-z0-9])")
_ALNUM_TO_KO: Final[re.Pattern[str]] = re.compile(r"([A-Za-z0-9])([가-힣])")


def normalize_ko_en_spacing(text: str) -> str:
    """한글 ↔ 영문/숫자 경계에 자동으로 공백을 삽입.

    Args:
        text: 정규화할 텍스트.

    Returns:
        공백이 보강된 텍스트.

    Examples:
        >>> normalize_ko_en_spacing("비타민C")
        '비타민 C'
        >>> normalize_ko_en_spacing("Vitamin비타민")
        'Vitamin 비타민'
        >>> normalize_ko_en_spacing("비타민C1000mg")
        '비타민 C1000mg'
        >>> normalize_ko_en_spacing("비타민 C 1000mg")
        '비타민 C 1000mg'
    """
    return _ALNUM_TO_KO.sub(r"\1 \2", _KO_TO_ALNUM.sub(r"\1 \2", text))


def normalize_ocr_text(text: str) -> str:
    """단위 + 한·영 공백을 한 번에 적용.

    ``metrics.normalize_text`` 와 ``field_extractor`` 양쪽에서 호출되는 진입점.

    Args:
        text: OCR 출력 또는 GT 텍스트.

    Returns:
        정규화된 텍스트.
    """
    return normalize_ko_en_spacing(normalize_units(text))
