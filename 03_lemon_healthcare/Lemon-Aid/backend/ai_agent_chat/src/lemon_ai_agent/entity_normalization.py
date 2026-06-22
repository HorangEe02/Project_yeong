from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EntityType = Literal[
    "medication",
    "medication_class",
    "supplement",
    "nutrient",
    "food",
    "risk_context",
]
EntitySpecificity = Literal["specific", "class", "ambiguous_class"]


@dataclass(frozen=True)
class NormalizedEntity:
    canonical_id: str
    entity_type: EntityType
    entity_class: str
    matched_term: str
    specificity: EntitySpecificity = "specific"


@dataclass(frozen=True)
class EntityNormalizationResult:
    entities: tuple[NormalizedEntity, ...]
    needs_specific_medication_name: bool = False
    missing_topics: tuple[str, ...] = ()


@dataclass(frozen=True)
class _EntityRule:
    canonical_id: str
    entity_type: EntityType
    entity_class: str
    aliases: tuple[str, ...]
    specificity: EntitySpecificity = "specific"


@dataclass(frozen=True)
class P0BoundaryMatch:
    boundary_code: str
    topic: str
    entity_ids: tuple[str, ...]


_ENTITY_RULES: tuple[_EntityRule, ...] = (
    _EntityRule("lithium", "medication", "mood_stabilizer", ("lithium", "리튬", "탄산리튬")),
    _EntityRule("warfarin", "medication", "anticoagulant", ("warfarin", "와파린")),
    _EntityRule(
        "statin",
        "medication_class",
        "statin",
        ("statin", "스타틴", "고지혈증약", "고지혈증 약", "콜레스테롤약", "콜레스테롤 약"),
    ),
    _EntityRule(
        "levothyroxine",
        "medication",
        "thyroid_hormone",
        ("levothyroxine", "갑상선약", "갑상선 호르몬"),
    ),
    _EntityRule("metformin", "medication", "diabetes_medication", ("metformin", "메트포민")),
    _EntityRule("ssri", "medication_class", "ssri", ("ssri", "선택적 세로토닌 재흡수 억제제")),
    _EntityRule("snri", "medication_class", "snri", ("snri",)),
    _EntityRule("antidepressant", "medication_class", "antidepressant", ("항우울제", "우울증약")),
    _EntityRule(
        "nitrate",
        "medication_class",
        "nitrate",
        ("nitrate", "nitroglycerin", "니트로글리세린", "협심증약"),
    ),
    _EntityRule("maoi", "medication_class", "maoi", ("maoi", "모노아민산화효소")),
    _EntityRule(
        "acetaminophen",
        "medication",
        "analgesic",
        ("acetaminophen", "아세트아미노펜", "타이레놀", "tylenol"),
    ),
    _EntityRule(
        "pde5_inhibitor",
        "medication_class",
        "pde5_inhibitor",
        ("pde5", "pde5 억제제", "비아그라", "시알리스", "실데나필", "타다라필", "발기부전약"),
    ),
    _EntityRule(
        "blood_pressure_medication",
        "medication_class",
        "antihypertensive",
        ("혈압약", "고혈압약"),
        "ambiguous_class",
    ),
    _EntityRule(
        "diabetes_medication",
        "medication_class",
        "diabetes_medication",
        ("당뇨약", "혈당약"),
        "ambiguous_class",
    ),
    _EntityRule("diuretic", "medication_class", "diuretic", ("이뇨제",), "ambiguous_class"),
    _EntityRule(
        "anticoagulant",
        "medication_class",
        "anticoagulant",
        ("항응고제", "피 묽게 하는 약"),
        "ambiguous_class",
    ),
    _EntityRule(
        "st_johns_wort",
        "supplement",
        "herbal_supplement",
        ("st john", "st. john", "세인트존스워트", "세인트 존스 워트"),
    ),
    _EntityRule("grapefruit", "food", "citrus", ("grapefruit", "자몽", "자몽주스")),
    _EntityRule("tyramine", "food", "tyramine_rich_food", ("tyramine", "티라민")),
    _EntityRule("vitamin_k", "nutrient", "vitamin", ("vitamin k", "비타민 k", "비타민k")),
    _EntityRule("vitamin_a", "nutrient", "vitamin", ("vitamin a", "비타민 a", "비타민a")),
    _EntityRule(
        "vitamin_b12", "nutrient", "vitamin", ("vitamin b12", "비타민 b12", "비타민b12", "b12")
    ),
    _EntityRule("potassium", "nutrient", "mineral", ("potassium", "칼륨")),
    _EntityRule("calcium", "nutrient", "mineral", ("calcium", "칼슘")),
    _EntityRule("iron", "nutrient", "mineral", ("iron", "철분")),
    _EntityRule("selenium", "nutrient", "mineral", ("selenium", "셀레늄")),
    _EntityRule("magnesium", "nutrient", "mineral", ("magnesium", "마그네슘")),
    _EntityRule("omega3", "supplement", "fatty_acid", ("omega-3", "omega3", "오메가3")),
    _EntityRule("ginkgo", "supplement", "herbal_supplement", ("ginkgo", "은행잎")),
    _EntityRule("vitamin_e", "nutrient", "vitamin", ("vitamin e", "비타민 e", "비타민e")),
    _EntityRule("red_yeast_rice", "supplement", "fermented_rice", ("red yeast rice", "홍국")),
    _EntityRule(
        "beta_carotene",
        "supplement",
        "provitamin_a",
        ("beta carotene", "beta-carotene", "베타카로틴"),
    ),
    _EntityRule(
        "five_htp",
        "supplement",
        "serotonergic_supplement",
        ("5-htp", "5 htp", "트립토판", "tryptophan"),
    ),
    _EntityRule(
        "salt_substitute",
        "food",
        "salt_substitute",
        ("저염소금", "low sodium salt", "salt substitute"),
    ),
    _EntityRule("smoking", "risk_context", "smoking", ("흡연", "흡연자", "smoker", "smoking")),
    _EntityRule("alcohol", "risk_context", "alcohol", ("음주", "술", "alcohol", "drinking")),
)

_P0_ENTITY_BOUNDARIES: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("p0_warfarin_vitamin_k", "warfarin_vitamin_k_interaction", ("warfarin",), ("vitamin_k",)),
    (
        "p0_levothyroxine_calcium_iron",
        "levothyroxine_mineral_absorption_boundary",
        ("levothyroxine",),
        ("calcium", "iron"),
    ),
    (
        "p0_metformin_vitamin_b12",
        "metformin_vitamin_b12_context_boundary",
        ("metformin",),
        ("vitamin_b12",),
    ),
    ("p0_maoi_tyramine", "maoi_tyramine_food_boundary", ("maoi",), ("tyramine",)),
    (
        "p0_smoker_beta_carotene_vitamin_a",
        "smoker_beta_carotene_vitamin_a_boundary",
        ("smoking",),
        ("beta_carotene", "vitamin_a"),
    ),
    (
        "p0_alcohol_vitamin_a_acetaminophen",
        "alcohol_vitamin_a_acetaminophen_boundary",
        ("alcohol",),
        ("vitamin_a", "acetaminophen"),
    ),
    (
        "p0_anticoagulant_omega3_ginkgo_vitamin_e",
        "anticoagulant_supplement_bleeding_boundary",
        ("anticoagulant", "warfarin"),
        ("omega3", "ginkgo", "vitamin_e"),
    ),
    (
        "p0_st_johns_wort_antidepressant",
        "st_johns_wort_antidepressant_interaction",
        ("st_johns_wort",),
        ("antidepressant", "ssri", "snri"),
    ),
    ("p0_grapefruit_statin", "grapefruit_statin_interaction", ("grapefruit",), ("statin",)),
    (
        "p0_potassium_salt_substitute",
        "potassium_salt_substitute_interaction",
        ("potassium",),
        ("salt_substitute",),
    ),
    (
        "p0_nitrate_pde5_inhibitor",
        "nitrate_pde5_inhibitor_interaction",
        ("nitrate",),
        ("pde5_inhibitor",),
    ),
    (
        "p0_serotonergic_supplement_antidepressant",
        "serotonergic_supplement_antidepressant_interaction",
        ("ssri", "snri", "antidepressant"),
        ("five_htp", "st_johns_wort"),
    ),
    (
        "p0_statin_red_yeast_rice",
        "statin_red_yeast_rice_interaction",
        ("statin",),
        ("red_yeast_rice",),
    ),
    ("p0_lithium_selenium", "lithium_selenium_supplement_boundary", ("lithium",), ("selenium",)),
)

_SPECIFIC_MEDICATION_REQUIRED_WITH = {
    "potassium",
    "vitamin_k",
    "vitamin_b12",
    "calcium",
    "iron",
    "omega3",
    "ginkgo",
    "vitamin_e",
    "st_johns_wort",
    "grapefruit",
    "red_yeast_rice",
    "five_htp",
}


def normalize_health_entities(
    text: str,
    context: dict[str, object] | None = None,
) -> EntityNormalizationResult:
    normalized_text = " ".join(text.casefold().split())
    entities: list[NormalizedEntity] = []

    for rule in _ENTITY_RULES:
        matched = _first_matching_alias(normalized_text, rule.aliases)
        if matched is None:
            continue
        entities.append(
            NormalizedEntity(
                canonical_id=rule.canonical_id,
                entity_type=rule.entity_type,
                entity_class=rule.entity_class,
                matched_term=matched,
                specificity=rule.specificity,
            )
        )

    entities.extend(_entities_from_context(context or {}))
    deduped = tuple(_dedupe_entities(entities))
    ids = {entity.canonical_id for entity in deduped}
    has_specific_medication = any(
        entity.entity_type == "medication"
        or (entity.entity_type == "medication_class" and entity.specificity == "class")
        for entity in deduped
    )
    has_ambiguous_medication = any(
        entity.entity_type == "medication_class" and entity.specificity == "ambiguous_class"
        for entity in deduped
    )
    needs_specific_medication_name = (
        has_ambiguous_medication
        and not has_specific_medication
        and bool(ids.intersection(_SPECIFIC_MEDICATION_REQUIRED_WITH))
    )
    missing_topics = ("unknown_medication",) if needs_specific_medication_name else ()
    return EntityNormalizationResult(
        entities=deduped,
        needs_specific_medication_name=needs_specific_medication_name,
        missing_topics=missing_topics,
    )


def has_p0_entity_pair(
    text: str,
    context: dict[str, object] | None = None,
) -> bool:
    return match_p0_boundary(text, context) is not None


def match_p0_boundary(
    text: str,
    context: dict[str, object] | None = None,
) -> P0BoundaryMatch | None:
    ids = {entity.canonical_id for entity in normalize_health_entities(text, context).entities}
    for boundary_code, topic, first_group, second_group in _P0_ENTITY_BOUNDARIES:
        first_match = ids.intersection(first_group)
        second_match = ids.intersection(second_group)
        if first_match and second_match:
            return P0BoundaryMatch(
                boundary_code=boundary_code,
                topic=topic,
                entity_ids=tuple(sorted(first_match | second_match)),
            )
    return None


def _first_matching_alias(text: str, aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        if alias.casefold() in text:
            return alias
    return None


def _entities_from_context(context: dict[str, object]) -> tuple[NormalizedEntity, ...]:
    profile = context.get("profile")
    if not isinstance(profile, dict):
        return ()
    medication_details = profile.get("medication_details")
    if not isinstance(medication_details, list):
        return ()

    entities: list[NormalizedEntity] = []
    for detail in medication_details:
        if not isinstance(detail, dict):
            continue
        normalized_name = detail.get("normalized_name")
        if isinstance(normalized_name, str) and normalized_name.strip():
            entities.extend(normalize_health_entities(normalized_name).entities)
        medication_class = detail.get("medication_class")
        if isinstance(medication_class, str) and medication_class.strip():
            value = medication_class.casefold().strip()
            entities.append(
                NormalizedEntity(
                    canonical_id=value,
                    entity_type="medication_class",
                    entity_class=value,
                    matched_term=medication_class.strip(),
                    specificity="class",
                )
            )
    return tuple(entities)


def _dedupe_entities(entities: list[NormalizedEntity]) -> list[NormalizedEntity]:
    deduped: dict[tuple[str, EntityType, EntitySpecificity], NormalizedEntity] = {}
    for entity in entities:
        key = (entity.canonical_id, entity.entity_type, entity.specificity)
        deduped.setdefault(key, entity)
    return list(deduped.values())
