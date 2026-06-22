"""Deterministic supplement product matching services."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db.supplement import SupplementProduct, SupplementProductIngredient
from src.models.schemas.supplement import MatchedSupplementCandidate, UserSupplementCreate

MAX_MATCH_CANDIDATES = 5
MAX_PRODUCTS_TO_SCORE = 200
AUTO_MATCH_THRESHOLD = 0.92
AUTO_MATCH_NAME_THRESHOLD = 0.9
EXACT_NAME_SCORE = 1.0
TEXT_PATTERN = re.compile(r"[^\w가-힣]+", re.UNICODE)
WHITESPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True)
class SupplementProductMatch:
    """Matched supplement product decision.

    Attributes:
        matched_product_id: Product id accepted by conservative auto-match rules.
        matched_source_manifest_version: Source manifest version for the accepted product.
        candidates: Ranked product candidates for preview traceability.
    """

    matched_product_id: UUID | None
    matched_source_manifest_version: str | None
    candidates: list[MatchedSupplementCandidate]


def normalize_supplement_text(value: str | None) -> str:
    """Normalize supplement product, manufacturer, and ingredient text.

    Args:
        value: Raw text value.

    Returns:
        Case-folded text with compatibility normalization and collapsed spaces.
    """
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = TEXT_PATTERN.sub(" ", normalized)
    return WHITESPACE_PATTERN.sub(" ", normalized).strip()


async def match_supplement_product(
    session: AsyncSession,
    request: UserSupplementCreate,
) -> SupplementProductMatch:
    """Find a conservative reference product match for a user-confirmed supplement.

    Args:
        session: Request-scoped async database session.
        request: User-confirmed supplement creation request.

    Returns:
        Match decision with ranked candidates. The accepted product id is set only
        when the best candidate satisfies strict automatic matching thresholds.
    """
    products = await _load_active_products(session)
    if not products:
        return SupplementProductMatch(
            matched_product_id=None,
            matched_source_manifest_version=None,
            candidates=[],
        )

    product_ingredients = await _load_product_ingredients(session, products)
    scored = [
        (
            _score_product_candidate(request, product, product_ingredients.get(product.id, [])),
            product,
        )
        for product in products
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    ranked = [(score, product) for score, product in scored[:MAX_MATCH_CANDIDATES] if score > 0]
    candidates = [
        MatchedSupplementCandidate(
            source_id=f"{product.source_provider}:{product.source_product_id}",
            product_name=product.product_name,
            manufacturer=product.manufacturer,
            match_score=round(score, 4),
        )
        for score, product in ranked
    ]

    matched_product_id: UUID | None = None
    matched_source_manifest_version: str | None = None
    if ranked:
        top_score, top_product = ranked[0]
        top_name_score = _name_score(
            normalize_supplement_text(request.display_name),
            normalize_supplement_text(
                top_product.normalized_product_name or top_product.product_name
            ),
        )
        if top_score >= AUTO_MATCH_THRESHOLD and top_name_score >= AUTO_MATCH_NAME_THRESHOLD:
            matched_product_id = top_product.id
            matched_source_manifest_version = top_product.source_manifest_version

    return SupplementProductMatch(
        matched_product_id=matched_product_id,
        matched_source_manifest_version=matched_source_manifest_version,
        candidates=candidates,
    )


async def _load_active_products(session: AsyncSession) -> list[SupplementProduct]:
    """Load bounded active reference products for deterministic scoring.

    Args:
        session: Request-scoped async database session.

    Returns:
        Active product rows.
    """
    result = await session.scalars(
        select(SupplementProduct)
        .where(SupplementProduct.is_active.is_(True))
        .order_by(SupplementProduct.normalized_product_name)
        .limit(MAX_PRODUCTS_TO_SCORE)
    )
    return list(result.all())


async def _load_product_ingredients(
    session: AsyncSession,
    products: list[SupplementProduct],
) -> dict[UUID, list[SupplementProductIngredient]]:
    """Load ingredients for candidate products.

    Args:
        session: Request-scoped async database session.
        products: Candidate product rows.

    Returns:
        Product id to ingredient rows.
    """
    product_ids = [product.id for product in products]
    if not product_ids:
        return {}
    result = await session.scalars(
        select(SupplementProductIngredient).where(
            SupplementProductIngredient.product_id.in_(product_ids)
        )
    )
    grouped: dict[UUID, list[SupplementProductIngredient]] = {}
    for ingredient in result.all():
        grouped.setdefault(ingredient.product_id, []).append(ingredient)
    return grouped


def _score_product_candidate(
    request: UserSupplementCreate,
    product: SupplementProduct,
    product_ingredients: list[SupplementProductIngredient],
) -> float:
    """Score one reference product against a user-confirmed supplement request.

    Args:
        request: User-confirmed supplement request.
        product: Reference supplement product.
        product_ingredients: Reference product ingredients.

    Returns:
        Score in the range 0.0 to 1.0.
    """
    request_name = normalize_supplement_text(request.display_name)
    product_name = normalize_supplement_text(
        product.normalized_product_name or product.product_name
    )
    manufacturer_score = _manufacturer_score(request.manufacturer, product.manufacturer)
    ingredient_score = _ingredient_overlap_score(request, product_ingredients)
    return min(
        1.0,
        (_name_score(request_name, product_name) * 0.72)
        + (manufacturer_score * 0.18)
        + (ingredient_score * 0.10),
    )


def _name_score(request_name: str, product_name: str) -> float:
    """Score normalized product-name similarity.

    Args:
        request_name: Normalized request product name.
        product_name: Normalized reference product name.

    Returns:
        Similarity score.
    """
    if not request_name or not product_name:
        return 0.0
    if request_name == product_name:
        return EXACT_NAME_SCORE
    if request_name in product_name or product_name in request_name:
        return 0.94
    return SequenceMatcher(None, request_name, product_name, autojunk=False).ratio()


def _manufacturer_score(
    request_manufacturer: str | None, product_manufacturer: str | None
) -> float:
    """Score manufacturer similarity.

    Args:
        request_manufacturer: User-confirmed manufacturer.
        product_manufacturer: Reference manufacturer.

    Returns:
        Similarity score, or 0.0 when either side is absent.
    """
    request_value = normalize_supplement_text(request_manufacturer)
    product_value = normalize_supplement_text(product_manufacturer)
    if not request_value or not product_value:
        return 0.0
    if request_value == product_value:
        return EXACT_NAME_SCORE
    return SequenceMatcher(None, request_value, product_value, autojunk=False).ratio()


def _ingredient_overlap_score(
    request: UserSupplementCreate,
    product_ingredients: list[SupplementProductIngredient],
) -> float:
    """Score overlap between user-confirmed and reference ingredient names or codes.

    Args:
        request: User-confirmed supplement request.
        product_ingredients: Reference product ingredients.

    Returns:
        Overlap ratio from 0.0 to 1.0.
    """
    request_terms = {
        term
        for ingredient in request.ingredients
        for term in (
            normalize_supplement_text(ingredient.display_name),
            normalize_supplement_text(ingredient.nutrient_code),
        )
        if term
    }
    product_terms = {
        term
        for ingredient in product_ingredients
        for term in (
            normalize_supplement_text(ingredient.standard_name),
            normalize_supplement_text(ingredient.nutrient_code),
        )
        if term
    }
    if not request_terms or not product_terms:
        return 0.0
    return len(request_terms & product_terms) / len(request_terms)
