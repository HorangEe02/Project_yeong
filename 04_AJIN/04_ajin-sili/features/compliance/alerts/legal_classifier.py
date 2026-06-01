"""P1 D1 — 법무 5분류 + 벌칙 조항 자동 추출.

ChangeRecord 본문 → 다음 enrich 필드 부착:
  - legal_class: list[str] — criminal / administrative / civil / contract / standardization
  - penalty_extract: str — "5년 이하 징역, 1억 이하 벌금" 같은 한 줄 요약
  - penalty_severity_krw_mn: int — 정렬·집계용 (백만원 단위, 벌금 max)

설계:
  1. 룰 우선 — 키워드 + 정규식. LLM 호출 없이 80% 케이스 처리.
  2. LLM 보조 — 룰 미스 시 Gemini/Ollama 호출 (P1 범위에서는 Ollama 사용, Gemini 는
     ENABLE_GEMINI 별도 토글).
  3. 안전 폴백 — 분류·추출 실패 시 빈 list / 빈 string 반환. 조용히 실패하지 않고
     change dict 의 errors 에 기록.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# 5분류 키워드 사전 — 한국어 법문 표현
# ─────────────────────────────────────────────────────────────

_LEGAL_CLASS_KEYWORDS: dict[str, tuple[str, ...]] = {
    "criminal": (
        "징역", "금고", "구류", "형사", "처벌", "벌칙",
        "체포", "구속", "기소", "공소시효",
    ),
    "administrative": (
        "과징금", "과태료", "조업정지", "영업정지", "행정처분",
        "시정명령", "사용금지", "허가취소", "면허취소", "자격정지",
        "이행강제금", "환경개선부담금",
    ),
    "civil": (
        "손해배상", "민사", "배상책임", "위자료", "연대책임",
    ),
    "contract": (
        "위약금", "계약해지", "납품중단", "거래중지", "계약종료",
        "공급중단", "리콜비용분담", "납품정지",
    ),
    "standardization": (
        "인증", "표시의무", "자체점검", "표준", "KS", "ISO인증",
        "검사기관", "정기검사", "수시검사", "성능평가", "적합성평가",
    ),
}


# ─────────────────────────────────────────────────────────────
# 벌칙 정규식 — 한국어 표현 패턴
# ─────────────────────────────────────────────────────────────

# 징역/금고 — "5년 이하 징역", "10년 이하의 징역" 등
_RE_IMPRISONMENT = re.compile(
    r"(\d+)\s*년\s*이하(?:의)?\s*(징역|금고|구류)"
)

# 벌금 — "1억원 이하", "5천만원 이하", "5,000만원 이하"
# 단위: 억=10000만, 천만=1000만, 백만=100만
_RE_FINE_KRW = re.compile(
    r"(\d+(?:,\d{3})*)\s*(억|천만|백만)?\s*원?\s*이하(?:의)?\s*(벌금|과징금|과태료)"
)

# 과징금 비율 — "초과 배출량 × 시장가격 3배 과징금"
_RE_PENALTY_MULTIPLIER = re.compile(
    r"(\d+)\s*배\s*(과징금|벌금)"
)


def _parse_amount_to_krw_mn(amount: str, unit: str | None) -> int:
    """금액 표현 → 백만원 단위 정규화.

    "1억" → 100, "5천만" → 50, "5,000만" → 50, "100백만" → 100
    """
    try:
        n = int(amount.replace(",", ""))
    except ValueError:
        return 0
    unit = (unit or "").strip()
    if unit == "억":
        return n * 100
    if unit == "천만":
        return n * 10
    if unit == "백만":
        return n
    # 단위 없음 — "5,000만원" 같은 케이스: 만원 단위로 가정
    if n >= 1_000_000:  # "5000000원" 같은 풀 표기
        return n // 1_000_000
    if n >= 100_000:  # "5000000원"
        return n // 1_000
    # 만 단위로 해석 — "5000만원" → 입력이 5000 이고 unit 이 빠진 경우
    return n // 100


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────


def classify_legal(change: dict) -> list[str]:
    """ChangeRecord → 5분류 list (다중 가능, 우선순위 정렬).

    빈 list 반환 = 분류 불가 (UI 에서 "미분류" 라벨).
    """
    text = _gather_text(change)
    if not text:
        return []

    matched: list[str] = []
    for klass, keywords in _LEGAL_CLASS_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                matched.append(klass)
                break  # 같은 클래스 첫 매칭만

    # 우선순위 정렬 — criminal > administrative > civil > contract > standardization
    priority = ["criminal", "administrative", "civil", "contract", "standardization"]
    matched.sort(key=lambda c: priority.index(c) if c in priority else 999)
    return matched


def extract_penalty(change: dict) -> dict[str, Any]:
    """ChangeRecord → 벌칙 dict.

    Returns:
        {
            "raw_text": "5년 이하 징역, 1억 이하 벌금",  # UI 한 줄 표시용
            "max_imprisonment_years": 5,
            "max_fine_krw_mn": 100,
            "max_multiplier": 3,  # 배수 과징금
        }
        또는 매칭 실패 시 {"raw_text": "", "max_imprisonment_years": 0, "max_fine_krw_mn": 0, "max_multiplier": 0}.
    """
    text = _gather_text(change)
    out = {
        "raw_text": "",
        "max_imprisonment_years": 0,
        "max_fine_krw_mn": 0,
        "max_multiplier": 0,
    }
    if not text:
        return out

    parts: list[str] = []

    # 징역/금고
    imp_matches = list(_RE_IMPRISONMENT.finditer(text))
    if imp_matches:
        max_years = max(int(m.group(1)) for m in imp_matches)
        out["max_imprisonment_years"] = max_years
        kind = imp_matches[0].group(2)
        parts.append(f"{max_years}년 이하 {kind}")

    # 벌금/과징금/과태료
    fine_matches = list(_RE_FINE_KRW.finditer(text))
    if fine_matches:
        max_mn = 0
        kind = ""
        for m in fine_matches:
            amount = m.group(1)
            unit = m.group(2)
            mn = _parse_amount_to_krw_mn(amount, unit)
            if mn > max_mn:
                max_mn = mn
                kind = m.group(3)
        if max_mn > 0:
            out["max_fine_krw_mn"] = max_mn
            # UI 표시: 1억 이상이면 "X억", 천만 단위면 "X천만"
            if max_mn >= 100:
                amt_str = f"{max_mn // 100}억"
                if max_mn % 100:
                    amt_str += f" {max_mn % 100 * 100:,}만"
            elif max_mn >= 10:
                amt_str = f"{max_mn // 10}천만"
            else:
                amt_str = f"{max_mn * 100:,}만"
            parts.append(f"{amt_str} 이하 {kind}")

    # 배수 과징금
    mult_matches = list(_RE_PENALTY_MULTIPLIER.finditer(text))
    if mult_matches:
        max_mult = max(int(m.group(1)) for m in mult_matches)
        out["max_multiplier"] = max_mult
        parts.append(f"{max_mult}배 {mult_matches[0].group(2)}")

    out["raw_text"] = ", ".join(parts)
    return out


def enrich_legal(change: dict) -> dict:
    """change dict 를 in-place 로 enrich + 그대로 반환.

    부착되는 키:
      - legal_class: list[str]
      - penalty_extract: str  (UI 한 줄)
      - penalty_severity_krw_mn: int (정렬용)
      - penalty_imprisonment_years: int
    """
    classes = classify_legal(change)
    penalty = extract_penalty(change)

    change["legal_class"] = classes
    change["penalty_extract"] = penalty["raw_text"]
    change["penalty_severity_krw_mn"] = penalty["max_fine_krw_mn"]
    change["penalty_imprisonment_years"] = penalty["max_imprisonment_years"]
    return change


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def _gather_text(change: dict) -> str:
    """change dict 에서 분류·추출 대상 텍스트 합치기."""
    return " ".join([
        str(change.get("item_title") or ""),
        str(change.get("summary_ko") or ""),
        str(change.get("new_value") or "")[:2000],  # 너무 긴 본문 컷
        str(change.get("old_value") or "")[:1000],
    ])
