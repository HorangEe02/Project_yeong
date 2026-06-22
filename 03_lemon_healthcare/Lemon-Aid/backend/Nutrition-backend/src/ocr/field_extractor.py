"""OCR 텍스트 → 구조화 필드 (product_name / ingredients / dosage) 추출기.

OCR 정확도 평가에서 ``field-level exact match`` 지표를 계산하기 위한 모듈.
규칙 기반 + 영양제 사전(MFDS) 매칭으로 동작한다.

처리 흐름:
    1. ``normalize_text`` 로 공백·유니코드 정규화.
    2. 라벨 헤더(``영양 정보`` / ``Nutrition Facts`` / ``성분`` / ``Ingredients``) 다음 줄을
       product_name 후보로 추출.
    3. 사전(NUTRIENT_DICTIONARY) 기반으로 ingredients 줄을 매칭.
    4. 정규식으로 dosage 패턴을 찾아 첫 번째 매치를 대표값으로 채택.

설계 원칙:
    - 외부 LLM 호출 없음 — 결정론적, 빠른 평가 가능.
    - 사전은 ``data/mfds/functional_ingredients.csv`` 의 한·영·별칭에서 빌드.
    - ``synth_label_dataset.py`` 의 GT 필드와 round-trip 일치하도록 설계.

Reference:
    backend/src/ocr/metrics.py
    scripts/synth_label_dataset.py
"""

from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Final

from src.ocr.metrics import normalize_text

DEFAULT_MFDS_CSV: Final[Path] = Path("data/mfds/functional_ingredients.csv")

HEADER_KEYWORDS_KO: Final[frozenset[str]] = frozenset({"영양 정보", "성분", "성분 ingredients"})
HEADER_KEYWORDS_EN: Final[frozenset[str]] = frozenset({"nutrition facts", "ingredients"})
HEADER_KEYWORDS_MIXED: Final[frozenset[str]] = frozenset(
    {
        "영양 정보 / nutrition facts",
    }
)

# dosage 정규식: 숫자(소수 가능) + 단위. KDRIs 의 모든 단위 형태를 커버.
# PaddleOCR 가 'µ' 대신 'u' 로 인식하는 경우도 흡수.
# 긴 단위(μg DFE 등)는 짧은 단위(μg) 보다 먼저 매칭되어야 한다 — 정규식은 alt 의
# 첫 매치를 채택하므로 길이 내림차순 정렬.
DOSAGE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"""
    (?P<amount>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)      # 숫자
    \s*
    (?P<unit>
        mg\s+α-TE
        |mg\s+NE
        |mcg\s+RAE
        |μg\s+RAE
        |ug\s+RAE
        |mcg\s+DFE
        |μg\s+DFE
        |ug\s+DFE
        |mcg
        |μg
        |ug
        |㎍
        |mg
        |g
        |IU
        |kcal
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# 줄 단위 ingredient 패턴:
# "- 이름: 함량", "이름 | 함량", "이름  함량" 형태를 모두 허용한다.
INGREDIENT_LINE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"""
    ^\s*[-•]?\s*
    (?P<name>[^:：|]+?)
    \s*(?:[:：|]|\s{2,})\s*
    \d[\d,.]*\s*
    (?:mg|g|mcg|μg|ug|㎍|IU|iu|%)
    """,
    re.VERBOSE,
)


def _build_dictionary(mfds_csv: Path) -> dict[str, str]:
    """MFDS 영양소 사전을 lowercase 키 → 한국어 정식명 매핑으로 빌드.

    한·영·별칭을 모두 키로 등록하고 값은 ``name_ko`` 로 통일한다.

    Args:
        mfds_csv: MFDS functional_ingredients.csv 경로.

    Returns:
        ``{lowercase_alias: name_ko}`` 매핑. CSV 가 없으면 빈 dict.
    """
    if not mfds_csv.exists():
        return {}

    dictionary: dict[str, str] = {}
    with mfds_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name_ko = row.get("ingredient_name_ko", "").strip()
            if not name_ko:
                continue
            name_en = row.get("ingredient_name_en", "").strip()
            aliases_raw = row.get("source_aliases", "")
            aliases = [a.strip() for a in aliases_raw.split("|") if a.strip()]

            for key in [name_ko, name_en, *aliases]:
                if not key:
                    continue
                dictionary[key.lower()] = name_ko
    return dictionary


@lru_cache(maxsize=4)
def _load_dictionary(mfds_csv: Path) -> dict[str, str]:
    """``_build_dictionary`` 를 캐싱."""
    return _build_dictionary(mfds_csv)


def _is_header(line: str) -> bool:
    """라인이 라벨 헤더(``영양 정보`` 등)인지 판정."""
    lowered = line.strip().lower()
    return (
        lowered in HEADER_KEYWORDS_KO
        or lowered in HEADER_KEYWORDS_EN
        or lowered in HEADER_KEYWORDS_MIXED
    )


def extract_product_name(text: str) -> str | None:
    """OCR 텍스트에서 제품명을 추출한다.

    규칙:
        1. 줄 단위로 split.
        2. 헤더 키워드("영양 정보", "Nutrition Facts" 등) 다음의 첫 비어있지 않은 줄.
        3. 헤더가 없으면 첫 줄을 채택.

    Args:
        text: OCR 출력 텍스트.

    Returns:
        제품명 또는 ``None`` (텍스트가 비어있거나 모든 줄이 헤더인 경우).

    Examples:
        >>> extract_product_name("영양 정보\\n비타민 C 종합 영양제\\n성분\\n- 비타민 C: 1000mg")
        '비타민 C 종합 영양제'
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None

    saw_header = False
    for line in lines:
        if _is_header(line):
            saw_header = True
            continue
        if saw_header:
            return normalize_text(line)
    # 헤더가 없으면 첫 줄
    return normalize_text(lines[0])


def extract_ingredients(text: str, mfds_csv: Path = DEFAULT_MFDS_CSV) -> list[str]:
    """OCR 텍스트에서 성분 이름 목록을 추출한다.

    각 줄에서 ``이름: 함량`` 패턴을 찾고 추출된 이름을 그대로 반환한다.
    OCR 정확도 평가는 "라벨에 적힌 글자를 그대로 읽었는가" 가 핵심이므로
    canonicalization (영→한 변환) 은 하지 않는다.

    MFDS 사전은 추후 ``filter_only`` 인자로 noise 라인을 걸러내는 옵션을
    위해 보유한다 (현재 미사용).

    Args:
        text: OCR 출력 텍스트.
        mfds_csv: MFDS 사전 CSV 경로 (현재 캐싱 목적으로만 로드).

    Returns:
        등장 순서대로의 성분명 리스트. 중복은 제거하지 않는다 (호출자 책임).

    Examples:
        >>> extract_ingredients("- 비타민 C: 1000mg\\n- 비타민 D: 25μg")
        ['비타민 C', '비타민 D']
        >>> extract_ingredients("- Vitamin C: 1000mg")
        ['Vitamin C']
    """
    _load_dictionary(mfds_csv)  # warm cache; future: filter mode 에서 사용
    results: list[str] = []
    for raw_line in text.splitlines():
        match = INGREDIENT_LINE_PATTERN.match(raw_line)
        if match is None:
            continue
        results.append(normalize_text(match.group("name")))
    return results


def extract_dosage(text: str) -> str | None:
    """OCR 텍스트에서 첫 번째 dosage 패턴을 추출.

    Args:
        text: OCR 출력 텍스트.

    Returns:
        ``"1000mg"`` / ``"25μg RAE"`` 같은 정규화된 문자열. 매치 없으면 ``None``.

    Examples:
        >>> extract_dosage("비타민 C: 1000mg")
        '1000mg'
        >>> extract_dosage("비타민 D: 25 μg RAE")
        '25μg RAE'
    """
    match = DOSAGE_PATTERN.search(text)
    if match is None:
        return None
    amount = match.group("amount").replace(",", "")
    unit = _normalize_dosage_unit(match.group("unit"))
    return f"{amount}{unit}"


def _normalize_dosage_unit(unit: str) -> str:
    """대표 dosage 단위 표기를 정규화한다.

    Args:
        unit: 정규식에 매칭된 단위 문자열.

    Returns:
        RAE/DFE/IU 같은 대문자 suffix 를 복원한 단위.
    """
    normalized = " ".join(unit.split())
    lowered = normalized.casefold()
    suffixes = {
        "rae": "RAE",
        "dfe": "DFE",
        "ne": "NE",
        "α-te": "α-TE",
    }
    if lowered == "iu":
        return "IU"
    if lowered == "kcal":
        return "kcal"
    for suffix, canonical in suffixes.items():
        marker = f" {suffix}"
        if lowered.endswith(marker):
            return f"{normalized[: -len(marker)]} {canonical}"
    return normalized


def extract_fields(
    text: str,
    mfds_csv: Path = DEFAULT_MFDS_CSV,
) -> dict[str, str | list[str] | None]:
    """제품명·성분·함량 필드를 한 번에 추출.

    Args:
        text: OCR 출력 텍스트.
        mfds_csv: MFDS 사전 CSV 경로.

    Returns:
        ``{"product_name": str|None, "ingredients": list[str], "dosage": str|None}``.

    Examples:
        >>> extract_fields("영양 정보\\n비타민 C 종합\\n성분\\n- 비타민 C: 1000mg")
        {'product_name': '비타민 C 종합', 'ingredients': ['비타민 C'], 'dosage': '1000mg'}
    """
    return {
        "product_name": extract_product_name(text),
        "ingredients": extract_ingredients(text, mfds_csv),
        "dosage": extract_dosage(text),
    }
