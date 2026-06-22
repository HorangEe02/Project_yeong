"""Supplement-image vision labels used by gated detectors."""

from __future__ import annotations

from enum import StrEnum


class VisionLabel(StrEnum):
    """Allowed non-medical object labels for supplement image detection.

    Attributes:
        PRODUCT_IDENTITY: Product name / brand / manufacturer text region.
        SUPPLEMENT_FACTS: Supplement facts / nutrition facts table region.
        INGREDIENT_AMOUNTS: Ingredient names and amount rows inside or near a facts panel.
        PRECAUTIONS: Warning, caution, contraindication, or precaution text region.
        ALLERGEN_WARNING: Allergy, allergen, intolerance, or contains statement text region.
        INTAKE_METHOD: Suggested use / directions / dosage text region.
        OTHER_INGREDIENTS: Excipients or other ingredient declaration region.
        FUNCTIONAL_CLAIMS: Functionality or benefit claim text region.
        SUPPLEMENT_LABEL: Product label region used as OCR input.
        SUPPLEMENT_BOTTLE: Bottle, pouch, or box that contains a supplement.
        BLISTER_PACK: Blister-pack object used only as capture context.
    """

    PRODUCT_IDENTITY = "product_identity"
    SUPPLEMENT_FACTS = "supplement_facts"
    INGREDIENT_AMOUNTS = "ingredient_amounts"
    PRECAUTIONS = "precautions"
    ALLERGEN_WARNING = "allergen_warning"
    INTAKE_METHOD = "intake_method"
    OTHER_INGREDIENTS = "other_ingredients"
    FUNCTIONAL_CLAIMS = "functional_claims"
    SUPPLEMENT_LABEL = "supplement_label"
    SUPPLEMENT_BOTTLE = "supplement_bottle"
    BLISTER_PACK = "blister_pack"


class FoodVisionLabel(StrEnum):
    """Allowed non-medical object labels for meal-image detection.

    These labels describe image regions only. They are not food taxonomy rows,
    nutrition facts, medical risks, or user-facing diet decisions.

    Attributes:
        MEAL_REGION: Whole plate, tray, bowl, table, or meal area.
        FOOD_ITEM: Individual food object area requiring user/database review.
        MENU_TEXT: Menu or package text region that can route OCR.
        NUTRITION_LABEL: Nutrition label or nutrition-facts table region.
    """

    MEAL_REGION = "meal_region"
    FOOD_ITEM = "food_item"
    MENU_TEXT = "menu_text"
    NUTRITION_LABEL = "nutrition_label"


VISION_DETECTION_LABELS = frozenset(label.value for label in VisionLabel)
VISION_SECTION_LABELS = frozenset(
    {
        VisionLabel.PRODUCT_IDENTITY.value,
        VisionLabel.SUPPLEMENT_FACTS.value,
        VisionLabel.INGREDIENT_AMOUNTS.value,
        VisionLabel.PRECAUTIONS.value,
        VisionLabel.ALLERGEN_WARNING.value,
        VisionLabel.INTAKE_METHOD.value,
        VisionLabel.OTHER_INGREDIENTS.value,
        VisionLabel.FUNCTIONAL_CLAIMS.value,
    }
)
VISION_LABEL_ALIASES = {
    "product_name": VisionLabel.PRODUCT_IDENTITY.value,
    "brand": VisionLabel.PRODUCT_IDENTITY.value,
    "brand_name": VisionLabel.PRODUCT_IDENTITY.value,
    "manufacturer": VisionLabel.PRODUCT_IDENTITY.value,
    "front_label_title": VisionLabel.PRODUCT_IDENTITY.value,
    "nutrition_facts": VisionLabel.SUPPLEMENT_FACTS.value,
    "nutrition_facts_panel": VisionLabel.SUPPLEMENT_FACTS.value,
    "supplement_facts_panel": VisionLabel.SUPPLEMENT_FACTS.value,
    "facts": VisionLabel.SUPPLEMENT_FACTS.value,
    "nutrition_info": VisionLabel.SUPPLEMENT_FACTS.value,
    "nutrition_information": VisionLabel.SUPPLEMENT_FACTS.value,
    "nutrition_function_info": VisionLabel.SUPPLEMENT_FACTS.value,
    "amounts": VisionLabel.INGREDIENT_AMOUNTS.value,
    "ingredient": VisionLabel.INGREDIENT_AMOUNTS.value,
    "ingredients": VisionLabel.INGREDIENT_AMOUNTS.value,
    "ingredient_amount": VisionLabel.INGREDIENT_AMOUNTS.value,
    "ingredient_rows": VisionLabel.INGREDIENT_AMOUNTS.value,
    "active_ingredients": VisionLabel.INGREDIENT_AMOUNTS.value,
    "warning": VisionLabel.PRECAUTIONS.value,
    "warnings": VisionLabel.PRECAUTIONS.value,
    "caution": VisionLabel.PRECAUTIONS.value,
    "cautions": VisionLabel.PRECAUTIONS.value,
    "precaution": VisionLabel.PRECAUTIONS.value,
    "allergy": VisionLabel.ALLERGEN_WARNING.value,
    "allergies": VisionLabel.ALLERGEN_WARNING.value,
    "allergen": VisionLabel.ALLERGEN_WARNING.value,
    "allergens": VisionLabel.ALLERGEN_WARNING.value,
    "allergy_warning": VisionLabel.ALLERGEN_WARNING.value,
    "allergen_warning": VisionLabel.ALLERGEN_WARNING.value,
    "directions": VisionLabel.INTAKE_METHOD.value,
    "direction": VisionLabel.INTAKE_METHOD.value,
    "suggested_use": VisionLabel.INTAKE_METHOD.value,
    "suggested_adult_use": VisionLabel.INTAKE_METHOD.value,
    "usage": VisionLabel.INTAKE_METHOD.value,
    "dosage": VisionLabel.INTAKE_METHOD.value,
    "how_to_take": VisionLabel.INTAKE_METHOD.value,
    "intake": VisionLabel.INTAKE_METHOD.value,
    "other_ingredient": VisionLabel.OTHER_INGREDIENTS.value,
    "excipient": VisionLabel.OTHER_INGREDIENTS.value,
    "excipients": VisionLabel.OTHER_INGREDIENTS.value,
    "ingredient_list": VisionLabel.OTHER_INGREDIENTS.value,
    "claims": VisionLabel.FUNCTIONAL_CLAIMS.value,
    "claim": VisionLabel.FUNCTIONAL_CLAIMS.value,
    "functional_claim": VisionLabel.FUNCTIONAL_CLAIMS.value,
    "functional_claim_text": VisionLabel.FUNCTIONAL_CLAIMS.value,
    "benefits": VisionLabel.FUNCTIONAL_CLAIMS.value,
    "supplement_container": VisionLabel.SUPPLEMENT_BOTTLE.value,
    "bottle": VisionLabel.SUPPLEMENT_BOTTLE.value,
    "label": VisionLabel.SUPPLEMENT_LABEL.value,
    "blister": VisionLabel.BLISTER_PACK.value,
}
VISION_ROI_LABEL_PRIORITY = {
    VisionLabel.PRODUCT_IDENTITY.value: 0,
    VisionLabel.SUPPLEMENT_FACTS.value: 1,
    VisionLabel.INGREDIENT_AMOUNTS.value: 2,
    VisionLabel.PRECAUTIONS.value: 3,
    VisionLabel.ALLERGEN_WARNING.value: 4,
    VisionLabel.INTAKE_METHOD.value: 5,
    VisionLabel.OTHER_INGREDIENTS.value: 6,
    VisionLabel.FUNCTIONAL_CLAIMS.value: 7,
    VisionLabel.SUPPLEMENT_LABEL.value: 8,
    VisionLabel.SUPPLEMENT_BOTTLE.value: 9,
    VisionLabel.BLISTER_PACK.value: 10,
}
FOOD_VISION_DETECTION_LABELS = frozenset(label.value for label in FoodVisionLabel)
FOOD_VISION_LABEL_ALIASES = {
    "meal": FoodVisionLabel.MEAL_REGION.value,
    "meal_area": FoodVisionLabel.MEAL_REGION.value,
    "plate": FoodVisionLabel.MEAL_REGION.value,
    "tray": FoodVisionLabel.MEAL_REGION.value,
    "bowl": FoodVisionLabel.MEAL_REGION.value,
    "dish": FoodVisionLabel.FOOD_ITEM.value,
    "food": FoodVisionLabel.FOOD_ITEM.value,
    "food_object": FoodVisionLabel.FOOD_ITEM.value,
    "food_region": FoodVisionLabel.FOOD_ITEM.value,
    "menu": FoodVisionLabel.MENU_TEXT.value,
    "menu_item": FoodVisionLabel.MENU_TEXT.value,
    "menu_region": FoodVisionLabel.MENU_TEXT.value,
    "menu_text_region": FoodVisionLabel.MENU_TEXT.value,
    "food_label": FoodVisionLabel.NUTRITION_LABEL.value,
    "nutrition": FoodVisionLabel.NUTRITION_LABEL.value,
    "nutrition_facts": FoodVisionLabel.NUTRITION_LABEL.value,
    "nutrition_facts_panel": FoodVisionLabel.NUTRITION_LABEL.value,
    "nutrition_info": FoodVisionLabel.NUTRITION_LABEL.value,
    "nutrition_information": FoodVisionLabel.NUTRITION_LABEL.value,
}


def normalize_vision_label(label: str) -> str | None:
    """Normalize a detector label into the allowed supplement ROI taxonomy.

    Args:
        label: Raw model label.

    Returns:
        Canonical label when allowed, otherwise None.
    """
    normalized = label.strip().lower().replace(" ", "_").replace("-", "_")
    return (
        normalized
        if normalized in VISION_DETECTION_LABELS
        else VISION_LABEL_ALIASES.get(normalized)
    )


def normalize_vision_label_set(labels: list[str]) -> list[str]:
    """Normalize configured detector labels into stable supplement ROI labels.

    Args:
        labels: Raw configured label names or aliases.

    Returns:
        Sorted canonical labels that belong to the supplement ROI taxonomy.
    """
    return sorted(
        {
            normalized
            for label in labels
            if (normalized := normalize_vision_label(label)) is not None
        }
    )


def normalize_food_vision_label(label: str) -> str | None:
    """Normalize a detector label into the allowed meal-image ROI taxonomy.

    Args:
        label: Raw model label.

    Returns:
        Canonical food-region label when allowed, otherwise None.
    """
    normalized = label.strip().lower().replace(" ", "_").replace("-", "_")
    return (
        normalized
        if normalized in FOOD_VISION_DETECTION_LABELS
        else FOOD_VISION_LABEL_ALIASES.get(normalized)
    )


def normalize_food_vision_label_set(labels: list[str]) -> list[str]:
    """Normalize configured detector labels into stable meal-image ROI labels.

    Args:
        labels: Raw configured food-region label names or aliases.

    Returns:
        Sorted canonical labels that belong to the meal-image ROI taxonomy.
    """
    return sorted(
        {
            normalized
            for label in labels
            if (normalized := normalize_food_vision_label(label)) is not None
        }
    )


def label_priority(label: str | None) -> int:
    """Return ROI selection priority for a canonical label.

    Args:
        label: Canonical supplement ROI label.

    Returns:
        Lower value means a stronger OCR ROI candidate.
    """
    if label is None:
        return len(VISION_ROI_LABEL_PRIORITY) + 1
    return VISION_ROI_LABEL_PRIORITY.get(label, len(VISION_ROI_LABEL_PRIORITY) + 1)
