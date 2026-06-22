"""Seed entity_wiki_links: DB entities -> LLM-WIKI page slugs.

Links each supplement category (43) and food cuisine (5) to its canonical wiki
page(s), derived from the wiki hub pages ``supplement-category-reference`` and
``food-category-taxonomy``. These links let RAG retrieval boost the wiki pages
that are authoritative for a given DB entity (precise grounding), independent of
lexical/semantic scoring.

Reads the live category_keys / cuisine_codes from the DB, applies the curated
maps, warns about any target slug missing from ``wiki_documents`` (run the wiki
ingestion first), and upserts links. Dry-run by default; ``--apply`` to write.
Connection via ``--dsn`` (asyncpg URL; password may come from PGPASSWORD).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path
from uuid import uuid4

import asyncpg

SOURCE = "wiki-hub-mapping-v1"
SUPPLEMENT_REFERENCE_HUB = "supplement-category-reference"
FOOD_TAXONOMY_HUB = "food-category-taxonomy"

# supplement_categories.category_key -> primary theme wiki slug
# (from supplement-category-reference.md theme table; dedicated pages preferred).
CATEGORY_WIKI_MAP: dict[str, str] = {
    "BCAA_EAA": "sports-muscle-supplements",
    "HMB_타우린": "sports-muscle-supplements",
    "강황_커큐민": "liver-antiinflammatory-supplements",
    "관절_MSM_콘드로이친": "joint-bone-supplements",
    "글루코사민": "joint-bone-supplements",
    "기타": "supplements-overview",
    "남성_쏘팔메토": "population-specific-supplements",
    "뇌_은행잎": "eye-brain-sleep-stress-supplements",
    "다이어트_체지방": "population-specific-supplements",
    "단백질_프로틴": "sports-muscle-supplements",
    "루테인_눈": "eye-brain-sleep-stress-supplements",
    "마그네슘": "mineral-supplements",
    "멀티비타민": "multivitamin-supplements",
    "밀크씨슬_간": "liver-antiinflammatory-supplements",
    "비타민A": "fat-soluble-vitamin-supplements",
    "비타민B": "water-soluble-vitamin-supplements",
    "비타민C": "water-soluble-vitamin-supplements",
    "비타민D": "fat-soluble-vitamin-supplements",
    "비타민E": "fat-soluble-vitamin-supplements",
    "비타민K": "fat-soluble-vitamin-supplements",
    "수면_멜라토닌": "eye-brain-sleep-stress-supplements",
    "스트레스_아쉬와간다": "eye-brain-sleep-stress-supplements",
    "스피루리나_클로렐라": "antioxidant-cellular-vascular-supplements",
    "식이섬유": "gut-digestive-supplements",
    "아르기닌_시트룰린": "sports-muscle-supplements",
    "아사이_베리류": "antioxidant-cellular-vascular-supplements",
    "아연": "mineral-supplements",
    "어린이_키성장": "pregnancy-pediatric-elderly-supplements",
    "여성영양제": "population-specific-supplements",
    "오메가3": "omega3-fatty-acids",
    "유산균_프로바이오틱": "probiotics-prebiotics",
    "종합영양제": "multivitamin-supplements",
    "철분": "mineral-supplements",
    "카페인_각성": "eye-brain-sleep-stress-supplements",
    "칼슘": "mineral-supplements",
    "코엔자임Q10": "antioxidant-cellular-vascular-supplements",
    "콜라겐": "joint-collagen-supplements",
    "크레아틴": "sports-muscle-supplements",
    "프로폴리스_벌": "population-specific-supplements",
    "프리워크아웃": "sports-muscle-supplements",
    "항산화": "antioxidant-cellular-vascular-supplements",
    "혈관_낫토_폴리코사놀": "antioxidant-cellular-vascular-supplements",
    "효소_소화": "gut-digestive-supplements",
}

# food_cuisines.cuisine_code -> cuisine nutrition wiki slug.
CUISINE_WIKI_MAP: dict[str, str] = {
    "korean": "korean-food-nutrition",
    "chinese": "chinese-japanese-food-nutrition",
    "japanese": "chinese-japanese-food-nutrition",
    "western": "western-ethnic-food-nutrition",
    "other": "western-ethnic-food-nutrition",
}

UPSERT_SQL = """
INSERT INTO entity_wiki_links (id, entity_type, entity_key, wiki_slug, relation, source)
VALUES ($1,$2,$3,$4,$5,$6)
ON CONFLICT (entity_type, entity_key, wiki_slug) DO UPDATE SET
  relation=EXCLUDED.relation, source=EXCLUDED.source, updated_at=now()
"""


def _build_links(category_keys: list[str], cuisine_codes: list[str]) -> list[dict]:
    """Build (entity_type, entity_key, wiki_slug, relation) link rows."""
    links: list[dict] = []
    for key in category_keys:
        slug = CATEGORY_WIKI_MAP.get(key)
        if slug:
            links.append(
                {
                    "entity_type": "supplement_category",
                    "entity_key": key,
                    "wiki_slug": slug,
                    "relation": "primary",
                }
            )
        links.append(
            {
                "entity_type": "supplement_category",
                "entity_key": key,
                "wiki_slug": SUPPLEMENT_REFERENCE_HUB,
                "relation": "reference_hub",
            }
        )
    for code in cuisine_codes:
        slug = CUISINE_WIKI_MAP.get(code)
        if slug:
            links.append(
                {
                    "entity_type": "food_cuisine",
                    "entity_key": code,
                    "wiki_slug": slug,
                    "relation": "primary",
                }
            )
        links.append(
            {
                "entity_type": "food_cuisine",
                "entity_key": code,
                "wiki_slug": FOOD_TAXONOMY_HUB,
                "relation": "reference_hub",
            }
        )
    return links


async def run(*, dsn: str, apply: bool) -> dict:
    """Read entities, build links, verify wiki slugs, and optionally upsert."""
    conn = await asyncpg.connect(dsn=dsn)
    try:
        category_keys = [
            r["category_key"]
            for r in await conn.fetch(
                "select category_key from supplement_categories where is_active order by category_key"
            )
        ]
        cuisine_codes = [
            r["cuisine_code"]
            for r in await conn.fetch(
                "select cuisine_code from food_cuisines where is_active order by cuisine_code"
            )
        ]
        links = _build_links(category_keys, cuisine_codes)
        known_slugs = {r["slug"] for r in await conn.fetch("select slug from wiki_documents")}
        missing = sorted({lnk["wiki_slug"] for lnk in links if lnk["wiki_slug"] not in known_slugs})
        if apply:
            async with conn.transaction():
                for lnk in links:
                    await conn.execute(
                        UPSERT_SQL,
                        uuid4(),
                        lnk["entity_type"],
                        lnk["entity_key"],
                        lnk["wiki_slug"],
                        lnk["relation"],
                        SOURCE,
                    )
            total = await conn.fetchval("select count(*) from entity_wiki_links")
        else:
            total = None
        return {
            "category_count": len(category_keys),
            "cuisine_count": len(cuisine_codes),
            "links_built": len(links),
            "relation_breakdown": dict(Counter(lnk["relation"] for lnk in links)),
            "wiki_slugs_missing_from_db": missing,
            "entity_wiki_links_in_db": total,
            "apply_requested": apply,
        }
    finally:
        await conn.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--summary", type=str, default=None)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = asyncio.run(run(dsn=args.dsn, apply=bool(args.apply)))
    if args.summary:
        path = Path(args.summary)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
