"""Auto-normalize supplement brand candidates from crawling-image product folders.

Produces a REVIEW DRAFT (not a DB write, not the gated decision file). For each
product sub-folder it strips marketplace/promo prefixes, then resolves a brand
via a known-brand allowlist (scanned across the whole title) with a first-token
fallback. Noisy / unresolved rows are flagged ``needs_review=true``.

Privacy: the draft persists only the normalized brand, the trailing numeric
product id, and the lowercase safe category key used by the reviewed taxonomy
staging manifest. It does NOT persist full product titles, absolute paths, OCR
text, or provider payloads.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

DEFAULT_ROOT = Path("data") / "nutrition_reference" / "crawling-image"

# Known Korean/global supplement brands (scanned anywhere in the title).
# Order matters: longer / more specific names first so "종근당건강" wins over "종근당".
KNOWN_BRANDS = [
    "종근당건강",
    "내츄럴플러스",
    "뉴트리코스트",
    "블루보넷뉴트리션",
    "닥터스베스트",
    "자로우포뮬러스",
    "라이프익스텐션",
    "네츄럴펙터스",
    "네이처스웨이",
    "스포츠리서치",
    "파라다이스허브",
    "이노빅스랩스",
    "캘리포니아골드뉴트리션",
    "바디닥터스",
    "닥터프로그램",
    "닥터에디션",
    "쏜리서치",
    "고려은단",
    "굿앤키즈",
    "나우푸드",
    "뉴트리코어",
    "에스더포뮬러",
    "닥터린",
    "유한양행",
    "프롬바이오",
    "삼대오백",
    "세노비스",
    "센트룸",
    "락티브",
    "락토핏",
    "리포데이",
    "얼라이브",
    "에버핏",
    "써큐란",
    "덴프스",
    "아임비타",
    "데일리원",
    "안국건강",
    "한미양행",
    "광동제약",
    "대웅제약",
    "동국제약",
    "뉴트리원",
    "GNM",
    "솔가",
    "나우",
    "쏜",
    "종근당",
    "YDY",
    "헬스밸런스",
    "BNF",
    "비타민하우스",
    "주영엔에스",
]
# Longest-first for greedy match.
KNOWN_BRANDS_SORTED = sorted(set(KNOWN_BRANDS), key=len, reverse=True)

# Tokens that are NOT brands even if they appear as the first token.
NOISE_TOKENS = {
    "마시는",
    "미국산",
    "국내산",
    "수용성",
    "지용성",
    "식물성",
    "동물성",
    "유기농",
    "유통기한",
    "원스데일리",
    "데일리",
    "메가",
    "에너지",
    "아르기닌",
    "조인트",
    "알부민",
    "종합",
    "고함량",
    "프리미엄",
    "초임계",
    "저분자",
    "활성형",
    "고흡수",
    "어린이",
    "키즈",
    "임산부",
    "남성",
    "여성",
}

# Leading promo / marketplace tokens to drop before first-token extraction.
PROMO_TOKEN_RE = re.compile(
    r"^(슈퍼적립|네이버|단독|정기구독|증정|사은품|무료배송|쿠폰|특가|핫딜|baby|키즈|성인)$",
    re.IGNORECASE,
)
# Leading bracket/paren groups: [3개월], (아이허브), {…}
BRACKET_RE = re.compile(r"^\s*[\[\(\{][^\]\)\}]*[\]\)\}]\s*")
# Quantity/period tokens: 3개월, 6개월분, 30일분, 120정, +60정, 2개, 100캡슐
QTY_TOKEN_RE = re.compile(
    r"^[+]?\d+\s*(개월분|개월|일분|일|정|포|캡슐|병|개|박스|매|ml|g|mg|회분|차)$",
    re.IGNORECASE,
)
TRAILING_ID_RE = re.compile(r"_(\d{6,})$")


def category_key_from_folder(folder_name: str) -> str:
    """Return the reviewed taxonomy category key for a source folder.

    Args:
        folder_name: Raw top-level crawling-image category folder name.

    Returns:
        Lowercase underscore-delimited category key matching the
        supplement-taxonomy DB staging contract.
    """
    normalized = unicodedata.normalize("NFC", folder_name).strip()
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1].strip()
    key = re.sub(r"[^\w]+", "_", normalized.casefold(), flags=re.UNICODE).strip("_")
    return key or "unknown"


def _strip_leading_noise(title: str) -> str:
    """Drop leading bracket groups, promo tokens, and quantity tokens."""
    prev = None
    cur = title.strip()
    while cur != prev:
        prev = cur
        cur = BRACKET_RE.sub("", cur).strip()
        head = cur.split()[0] if cur.split() else ""
        if head and (PROMO_TOKEN_RE.match(head) or QTY_TOKEN_RE.match(head)):
            cur = cur[len(head) :].strip()
    return cur


def normalize_brand(folder_name: str) -> tuple[str, str, bool]:
    """Return (proposed_brand, method, needs_review) for a product folder name.

    Args:
        folder_name: Raw product sub-folder name (crawled listing title + _id).

    Returns:
        proposed_brand, resolution method, and whether human review is advised.
    """
    title = TRAILING_ID_RE.sub("", folder_name).strip()

    # 1) Allowlist scan across the whole (de-spaced) title — most reliable.
    despaced = title.replace(" ", "")
    for brand in KNOWN_BRANDS_SORTED:
        if brand.replace(" ", "") in despaced:
            return brand, "allowlist", False

    # 2) First meaningful token after stripping promo/bracket/qty prefixes.
    cleaned = _strip_leading_noise(title)
    tokens = cleaned.split()
    if tokens:
        head = tokens[0].strip("[](){}")
        if head and head not in NOISE_TOKENS and not QTY_TOKEN_RE.match(head):
            # Plausible brand token but not in allowlist → low confidence.
            return head, "first_token", True

    # 3) Unresolved.
    return "", "unresolved", True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.expanduser().resolve()
    rows: list[dict] = []
    for cat_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        # macOS stores filenames as NFD (decomposed Hangul); normalize to NFC so
        # comparisons against NFC literals / DB rows (migration seeds) match.
        cat_name = unicodedata.normalize("NFC", cat_dir.name)
        category_key = category_key_from_folder(cat_name)
        for prod_dir in sorted(p for p in cat_dir.iterdir() if p.is_dir()):
            prod_name = unicodedata.normalize("NFC", prod_dir.name)
            m = TRAILING_ID_RE.search(prod_name)
            product_id = m.group(1) if m else None
            brand, method, needs_review = normalize_brand(prod_name)
            rows.append(
                {
                    "category_key": category_key,
                    "category_folder": cat_name,
                    "source_product_id": product_id,
                    "proposed_brand": brand,
                    "resolution_method": method,
                    "needs_human_review": needs_review,
                }
            )

    brand_counts = Counter(r["proposed_brand"] for r in rows if r["proposed_brand"])
    method_counts = Counter(r["resolution_method"] for r in rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )
    summary = {
        "schema_version": "supplement-brand-normalization-draft-v1",
        "product_count": len(rows),
        "distinct_proposed_brands": len(brand_counts),
        "needs_human_review_count": sum(1 for r in rows if r["needs_human_review"]),
        "high_confidence_count": sum(1 for r in rows if not r["needs_human_review"]),
        "resolution_method_counts": dict(method_counts),
        "brand_counts": dict(sorted(brand_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "note": "DRAFT for operator review; allowlist=high-confidence, first_token/unresolved=needs review.",
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "product_count",
                    "distinct_proposed_brands",
                    "high_confidence_count",
                    "needs_human_review_count",
                    "resolution_method_counts",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
