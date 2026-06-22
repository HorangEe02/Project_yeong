"""Supplement OCR structured parsing service."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings
from src.db.tx import persist_scope
from src.llm.ollama import (
    SUPPLEMENT_PARSER_SOURCE,
    OllamaChatClient,
    OllamaClientError,
    OllamaStructuredOutputError,
    OllamaSupplementParser,
)
from src.models.db.supplement import SupplementAnalysisRun
from src.models.schemas.label_layout import LabelLayout, LabelSection
from src.models.schemas.privacy import ConsentType
from src.models.schemas.supplement import (
    SupplementAnalysisStatus,
    SupplementMissingRequiredSection,
    SupplementPreviewEvidenceSpan,
    SupplementPreviewIntakeMethod,
    SupplementPreviewLabelSection,
    SupplementPreviewPrecaution,
)
from src.models.schemas.supplement_parser import SupplementStructuredParseResult
from src.ocr.text_normalizer import normalize_ocr_text as normalize_provider_ocr_text
from src.security.auth import AuthenticatedUser
from src.security.subjects import build_owner_subject
from src.services.nutrient_display_name_localizer import localize_ingredient_display_names
from src.services.privacy import has_active_consent
from src.services.supplement_candidate_filter import filter_non_ingredient_ocr_fallback_candidates
from src.services.supplement_label_localizer import localize_snapshot_to_korean
from src.services.supplement_text_sanitizer import (
    sanitize_ingredient_name,
    sanitize_manufacturer,
    sanitize_preview_text,
    sanitize_product_name,
    sanitize_serving_size,
    sanitize_unit,
)

logger = logging.getLogger(__name__)

SUPPLEMENT_PARSER_CONFIRMATION_WARNING = (
    "Structured OCR parsing is a preview. Review and confirm every field before saving."
)
OCR_PATTERN_FALLBACK_WARNING = "ocr_pattern_fallback_requires_review"
# Emitted when the local LLM parser fails (non-JSON output or unreachable) and the
# deterministic OCR fallbacks are used to recover candidates instead of aborting.
LLM_PARSE_FALLBACK_WARNING = "llm_parse_failed_fallback_requires_review"
OCR_PATTERN_FALLBACK_SOURCE = "ocr_pattern_fallback"
# Name-only candidates mined from the Korean 원재료명 / 원료명 declaration list.
# They never carry a trustworthy amount/unit, so the UI must confirm amounts.
INGREDIENT_DECLARATION_SOURCE = "ingredient_declaration"
INGREDIENT_DECLARATION_WARNING = "ingredient_declaration_names_only_requires_review"
INGREDIENT_DECLARATION_CONFIDENCE = 0.4
EXCIPIENT_FILTERED_WARNING = "ingredient.excipient_filtered"
NON_INGREDIENT_HEADING_FILTERED_WARNING = "ingredient.non_ingredient_heading_filtered"
INTAKE_INSTRUCTION_FILTERED_WARNING = "ingredient.intake_instruction_filtered"
INGREDIENT_AMOUNT_MISSING_WARNING = "ingredient.amount_missing"
SUPPLEMENT_IMAGE_ASSIST_WARNING = (
    "Image-assisted text extraction is a fallback preview. Review every field before saving."
)
SUPPLEMENT_PARSER_PROVIDER = "ollama"
OLLAMA_VISION_ASSIST_PROVIDER = "ollama_vision_assist"
OCR_PROVIDER_MAX_LENGTH = 64
OCR_LOW_CONFIDENCE_THRESHOLD = Decimal("0.80")
LAYOUT_TEXT_BUNDLE_MAX_CHARS = 2_000
LAYOUT_EVIDENCE_EXCERPT_MAX_CHARS = 240
LAYOUT_PRECAUTION_TEXT_MAX_CHARS = 500
LAYOUT_PRECAUTION_FALLBACK_MAX_ITEMS = 40
LAYOUT_PRECAUTION_FALLBACK_WARNING = "layout_precaution_fallback_requires_review"
OCR_TEXT_SECTION_FALLBACK_CONFIDENCE = 0.55
OCR_TEXT_SECTION_FALLBACK_WARNING_INTAKE = "ocr_intake_method_fallback_requires_review"
OCR_TEXT_SECTION_FALLBACK_WARNING_PRECAUTION = "ocr_precaution_fallback_requires_review"
OCR_TEXT_PREVIEW_FALLBACK_WARNING = "ocr_text_preview_fallback_requires_review"
OCR_TEXT_SECTION_FALLBACK_MAX_PRECAUTIONS = 12
OCR_TEXT_SECTION_FALLBACK_TEXT_MAX_CHARS = 500
OCR_TEXT_PREVIEW_FALLBACK_MAX_SECTIONS = 6
OCR_TEXT_PREVIEW_FALLBACK_MAX_LINES_PER_SECTION = 80
FUSED_OCR_IMAGE_MARKER_PATTERN = re.compile(r"^=+\s*\[(?P<label>[^\]]{1,120})\]\s*=+$")
LAYOUT_SECTION_TYPE_MAP = {
    "daily_intake": "intake_method",
    "nutrition_function_info": "supplement_facts",
    "intake_method": "intake_method",
    "precautions": "precautions",
    "allergen_warning": "allergen_warning",
    "ingredients": "ingredients",
    "functionality": "functional_info",
    "storage_method": "storage_method",
}
INGREDIENT_UNIT_PATTERN = (
    r"mg|m\s*g|㎎|밀리그램|g|그램|mcg|m\s*c\s*g|μg|µg|ug|u\s*g|㎍|마이크로그램|"
    r"iu|i\s*u|i\.u\.|IU|아이유|cfu|CFU|씨에프유|%"
)
INGREDIENT_AMOUNT_PATTERN = re.compile(
    r"(?P<name>[A-Za-z가-힣][A-Za-z가-힣0-9\s()/+\-.,]{1,80}?)"
    r"\s*(?P<amount>\d+(?:[,.]\d+)?)\s*"
    rf"(?P<unit>{INGREDIENT_UNIT_PATTERN})"
    # Optional trailing %DV (영양성분기준치) after a real unit, e.g. "1000 mg 100%".
    r"(?:\s*(?P<dv>\d+(?:[,.]\d+)?)\s*%)?" r"(?=$|[\s,;:)\uff09\]]|[^\w])",
    re.IGNORECASE,
)
INGREDIENT_TABLE_ROW_PATTERN = re.compile(
    r"(?P<name>[A-Za-z가-힣][A-Za-z가-힣0-9\s()/+\-.,]{1,80}?)"
    r"\s*(?:[|｜:：·•]|\s{2,})\s*"  # noqa: RUF001
    r"(?P<amount>\d+(?:[,.]\d+)?)\s*"
    rf"(?P<unit>{INGREDIENT_UNIT_PATTERN})"
    # Two-column OCR often preserves a visual separator before the %DV column:
    # "Vitamin C | 100 mg | 111%". The separator is evidence, not syntax to store.
    r"(?:\s*(?:[|｜]\s*)?(?P<dv>\d+(?:[,.]\d+)?)\s*%)?"  # noqa: RUF001
    r"(?=$|[\s,;:)\uff09\]]|[^\w])",
    re.IGNORECASE,
)
BARE_INGREDIENT_AMOUNT_PATTERN = re.compile(
    rf"^\s*(?P<amount>\d+(?:[,.]\d+)?)\s*(?P<unit>{INGREDIENT_UNIT_PATTERN})"
    r"(?:\s*(?P<dv>\d+(?:[,.]\d+)?)\s*%)?\s*$",
    re.IGNORECASE,
)
BARE_INGREDIENT_NUMBER_PATTERN = re.compile(r"^\s*(?P<amount>\d+(?:[,.]\d+)?)\s*$")
BARE_DAILY_VALUE_PERCENT_PATTERN = re.compile(
    r"^\s*(?:[|｜·•:/-]\s*)?(?P<dv>\d+(?:[,.]\d+)?)\s*%\s*"  # noqa: RUF001 - OCR fullwidth bar
    r"(?:(?:daily\s*value|dv|영양성분\s*기준치|기준치)\b)?\s*$",
    re.IGNORECASE,
)
INGREDIENT_UNIT_ONLY_PATTERN = re.compile(
    rf"^\s*(?P<unit>{INGREDIENT_UNIT_PATTERN})" r"(?:\s*(?P<dv>\d+(?:[,.]\d+)?)\s*%)?\s*$",
    re.IGNORECASE,
)
# Amount-first rows such as "100 mg 비타민C" or "12 mg 100% 비타민B6". A visible unit
# from the lexicon is required (no fabricated amounts), and the trailing name still
# passes the shared ingredient-name guards via _append_ocr_pattern_candidate.
AMOUNT_FIRST_INGREDIENT_PATTERN = re.compile(
    rf"^\s*(?P<amount>\d+(?:[,.]\d+)?)\s*(?P<unit>{INGREDIENT_UNIT_PATTERN})"
    r"(?:\s*(?P<dv>\d+(?:[,.]\d+)?)\s*%)?\s+"
    r"(?P<name>[A-Za-z가-힣][A-Za-z가-힣0-9\s()/+\-.]{1,80})$",
    re.IGNORECASE,
)
# Korean amount qualifiers that trail a value ("100 mg 이상" = "100 mg or more").
# They satisfy the amount-first shape but are not ingredient names.
AMOUNT_FIRST_NAME_STOPWORDS = frozenset(
    {
        "이상",
        "이하",
        "미만",
        "초과",
        "이내",
        "내외",
        "정도",
        "최소",
        "최대",
        "함량",
        "권장량",
        "기준치",
    }
)
TRAILING_INGREDIENT_PUNCTUATION = " -_/.,:\uff1a|·•()"
TRAILING_INGREDIENT_EDGE_PUNCTUATION = " -_/.,:\uff1a|·•"
MAX_PATTERN_FALLBACK_INGREDIENTS = 20
INGREDIENT_MIN_NAME_CHARS = 2
INGREDIENT_MAX_NAME_CHARS = 80
# CFU counts carry a Korean myriad counter (억/조/만) or English magnitude
# (billion/million) between the number and the CFU unit ("100억 CFU"), which the
# standard amount grammar misses. 100억 = 10^10 exceeds the amount field bound, so
# the magnitude is preserved in the unit ("억 CFU") rather than multiplied out.
_CFU_MAGNITUDE = r"억|조|만|billion|million"
_CFU_UNIT = r"cfu|씨에프유"
CFU_MAGNITUDE_NAME_FIRST_PATTERN = re.compile(
    r"^\s*(?P<name>[A-Za-z가-힣][A-Za-z가-힣0-9\s()/+\-.]{1,80}?)\s*"
    r"(?P<amount>\d+(?:[,.]\d+)?)\s*"
    rf"(?P<mag>{_CFU_MAGNITUDE})\s*(?:{_CFU_UNIT})(?:\s.*)?$",
    re.IGNORECASE,
)
CFU_MAGNITUDE_AMOUNT_FIRST_PATTERN = re.compile(
    r"^\s*(?P<amount>\d+(?:[,.]\d+)?)\s*"
    rf"(?P<mag>{_CFU_MAGNITUDE})\s*(?:{_CFU_UNIT})\s+"
    r"(?P<name>[A-Za-z가-힣][A-Za-z가-힣0-9\s()/+\-.]{1,80})\s*$",
    re.IGNORECASE,
)
PACKAGING_QUANTITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"^(?:g|mg|kg|ml|l)\s*(?:x\s*)?\d*\s*(?:포|정|캡슐|개입)?\s*\(?$",
        re.IGNORECASE,
    ),
    re.compile(r"^정\s*(?:x\s*)?\d*\s*(?:개입)?\s*\(?$", re.IGNORECASE),
    re.compile(r"^\d+\s*(?:정|포|캡슐|개입)\s*\(?$", re.IGNORECASE),
)
INTAKE_INSTRUCTION_PATTERN = re.compile(
    r"(?:"
    r"섭취\s*방법|복용\s*방법|1\s*일|일\s*\d+\s*회|\d+\s*회|"
    r"스푼|스쿱|숟가락|정씩|포씩|캡슐씩|"
    r"suggested\s+use|directions?|recommendation|take\b|daily|"
    r"scoops?|tablets?|capsules?|softgels?"
    r")",
    re.IGNORECASE,
)
SERVING_OR_PACKAGE_CONTEXT_PATTERN = re.compile(
    r"(?:"
    r"1\s*회\s*제공량|회\s*제공량|제공량|총\s*내용량|내용량|"
    r"serving\s+size|servings?\s+per\s+container|amount\s+per\s+serving"
    r")",
    re.IGNORECASE,
)
BARE_PACKAGE_QUANTITY_PATTERN = re.compile(
    r"^\s*\d+\s*(?:capsules?|tablets?|softgels?|caps?|tabs?|servings?|count|ct)\.?\s*$",
    re.IGNORECASE,
)
PRECAUTION_TEXT_PATTERN = re.compile(
    r"(?:"
    r"섭취\s*시\s*주의|주의\s*사항|주의|경고|알레르기|알러지|유발\s*물질|"
    r"임산|임신|수유|어린이|소아|의약품|약물|전문가|상담|"
    r"warning|caution|allerg(?:y|en)|pregnan|nursing|children|medication|consult"
    r")",
    re.IGNORECASE,
)
NON_PRECAUTION_CONTACT_PATTERN = re.compile(
    r"(?:고객\s*상담|소비자\s*상담|상담\s*실|customer\s+service|questions?)",
    re.IGNORECASE,
)
BARE_INTAKE_HEADING_PATTERN = re.compile(
    r"^[\s:：\-·•]*(?:섭취\s*방법|복용\s*방법|suggested\s+use|directions?)"  # noqa: RUF001
    r"[\s:：\-·•]*$",  # noqa: RUF001
    re.IGNORECASE,
)
# Recognizes a line as a Korean ingredient-declaration header (원재료명 / 원료명 /
# 성분명). Only such lines are mined for name-only candidates, so marketing copy
# and stray OCR text are never treated as an ingredient list. The regex keeps
# the fullwidth punctuation Korean labels legitimately use; the per-line lint
# suppressions on the regex strings mark those chars as intentional, not typos.
INGREDIENT_DECLARATION_HEADER_PATTERN = re.compile(
    r"^[\s\[\]【】()<>:：·•\-]*"  # noqa: RUF001
    r"(?:원\s*재\s*료\s*명"  # 원재료명
    r"|원\s*료\s*명"  # 원료명
    r"|성\s*분\s*명)"  # 성분명
    r"\s*(?:및\s*함량)?"  # optional "및 함량"
    r"\s*[)\]】]?\s*[:：]?",  # noqa: RUF001
    re.IGNORECASE,
)
# Separators inside a declaration list: commas, middots, slashes, semicolons and
# Korean enumeration marks. Plain spaces are NOT separators, so multi-word names
# ("비타민 D", "코엔자임 Q10") stay intact. See the header note above.
INGREDIENT_DECLARATION_SPLIT_PATTERN = re.compile(r"[,，、;；/·∙ㆍ‧・]+")  # noqa: RUF001
# Inline/trailing parentheticals (source qualifiers, %DV notes, English glosses)
# are dropped so the canonical ingredient name remains.
INGREDIENT_DECLARATION_PAREN_PATTERN = re.compile(r"[(（【\[][^)）】\]]*[)）】\]]?")  # noqa: RUF001
# Explicit declared percentage literally present in the text, e.g.
# "이노시톨 88.8889%". Captured only when present; never inferred.
INGREDIENT_DECLARATION_PERCENT_PATTERN = re.compile(r"(?P<percent>\d+(?:[.,]\d+)?)\s*%")
# A trailing "<amount><unit>" or bare trailing number glued onto a declaration
# token (e.g. "비타민 D 25mcg"). Such tokens are amount-bearing rows handled by
# the OCR amount-pattern path; here we strip the amount so the declaration stays
# strictly name-only ("비타민 D") and dedupes against the amount-bearing candidate.
INGREDIENT_DECLARATION_TRAILING_AMOUNT_PATTERN = re.compile(
    r"\s*\d+(?:[.,]\d+)?\s*(?:mg|㎎|g|kg|mcg|μg|ug|㎍|iu|ml|l|억|%)?\s*$",
    re.IGNORECASE,
)
MAX_DECLARATION_INGREDIENTS = 40
MAX_DECLARATION_CONTINUATION_LINES = 8
DECLARATION_CONTINUATION_STOP_PATTERN = re.compile(
    r"^\s*(?:"
    r"nutrition\s*facts|supplement\s*facts|amount\s*per\s*serving|serving\s*size|"
    r"suggested\s+use|directions?|warnings?|cautions?|consult|"
    r"영양\s*정보|영양\s*성분|기능\s*정보|섭취\s*방법|복용\s*방법|주의\s*사항|"
    r"주의|경고|보관|제조원|판매원|유통\s*기한"
    r")\b",
    re.IGNORECASE,
)
# Inactive excipients / capsule-coating materials that the LLM sometimes lists as
# ingredients. Matched by exact normalized name only (never substring) so genuine
# active nutrients are never dropped.
# Maintenance: extend when a new LLM model surfaces more excipient false-positives
# (e.g., additional Korean coating agents); keep entries exact-match, lowercase-normalized.
_EXCIPIENT_NAME_KEYS: frozenset[str] = frozenset(
    {
        "gelatin",
        "젤라틴",
        "glycerin",
        "glycerine",
        "글리세린",
        "purified water",
        "정제수",
        "softgel",
        "sunflower oil",
        "해바라기씨유",
        "soybean oil",
        "대두유",
        "silicon dioxide",
        "이산화규소",
        "magnesium stearate",
        "스테아린산마그네슘",
        "microcrystalline cellulose",
        "결정셀룰로스",
        "titanium dioxide",
        "이산화티타늄",
        "hydroxypropyl methylcellulose",
        "hpmc",
    }
)


class SupplementOCRTextParser(Protocol):
    """Protocol for parser adapters that convert OCR text into structured facts."""

    async def parse_supplement_ocr_text(
        self,
        ocr_text: str,
    ) -> SupplementStructuredParseResult:
        """Parse OCR text into a validated supplement structure.

        Args:
            ocr_text: Normalized OCR text.

        Returns:
            Structured supplement parse result.
        """


@dataclass(frozen=True)
class SupplementParserStoreResult:
    """Stored supplement parser result.

    Attributes:
        record: Updated supplement analysis row.
        parse_result: Validated structured parse output.
    """

    record: SupplementAnalysisRun
    parse_result: SupplementStructuredParseResult


class SupplementParserInputError(ValueError):
    """Raised when OCR text or OCR metadata fails parser input validation."""


class SupplementAnalysisNotFoundError(ValueError):
    """Raised when the current user cannot access the requested analysis row."""


class SupplementAnalysisExpiredError(ValueError):
    """Raised when the analysis preview has expired before parsing."""


class SupplementAnalysisStateError(ValueError):
    """Raised when the analysis preview is not in a parseable lifecycle state."""


class SupplementParserConflictError(ValueError):
    """Raised when a preview already has a different OCR text hash."""


async def parse_supplement_analysis_ocr_text(
    session: AsyncSession,
    user: AuthenticatedUser,
    analysis_id: UUID,
    ocr_text: str,
    ocr_provider: str,
    ocr_confidence: float | None,
    settings: Settings,
    ocr_layout: LabelLayout | None = None,
    parser: SupplementOCRTextParser | None = None,
) -> SupplementParserStoreResult:
    """Parse OCR text and store the structured preview on an owned analysis row.

    Args:
        session: Request-scoped async database session.
        user: Authenticated owner.
        analysis_id: Supplement analysis preview identifier.
        ocr_text: Raw OCR text. It is normalized, hashed, and sent only to local Ollama.
            The normalized text is retained (top-level ``raw_ocr_text`` in the
            owner-scoped snapshot) only when ``store_raw_ocr_text`` is on AND the user
            granted the ``RAW_OCR_TEXT_RETENTION`` consent; otherwise never stored.
        ocr_provider: OCR provider label.
        ocr_confidence: Optional OCR confidence from 0.0 to 1.0.
        settings: Runtime settings.
        ocr_layout: Optional deterministic layout parsed from provider OCR coordinates.
        parser: Optional parser adapter, primarily for tests.

    Returns:
        Updated analysis row and validated parse result.

    Raises:
        SupplementParserInputError: If OCR text, provider, or confidence is invalid.
        SupplementAnalysisNotFoundError: If the row is absent or belongs to another owner.
        SupplementAnalysisExpiredError: If the preview has expired.
        SupplementAnalysisStateError: If the row is already confirmed, failed, or expired.
        SupplementParserConflictError: If a different OCR text was already attached.
    """
    normalized_text = normalize_ocr_text(ocr_text, settings.supplement_ocr_text_max_chars)
    normalized_provider = _normalize_ocr_provider(ocr_provider)
    normalized_confidence = _normalize_confidence(ocr_confidence)
    text_hash = hash_ocr_text(normalized_text, settings.privacy_hash_secret)
    owner_subject = build_owner_subject(user)

    record = await session.scalar(
        select(SupplementAnalysisRun).where(
            SupplementAnalysisRun.id == analysis_id,
            SupplementAnalysisRun.owner_subject == owner_subject,
        )
    )
    if record is None:
        raise SupplementAnalysisNotFoundError("Supplement analysis preview was not found.")
    _validate_parseable_record(record, text_hash)

    active_parser = parser or OllamaSupplementParser(settings)
    try:
        parse_result = await active_parser.parse_supplement_ocr_text(normalized_text)
    except (OllamaStructuredOutputError, OllamaClientError) as exc:
        # The local LLM produced unusable output (e.g. non-JSON on a dense label) or
        # was unreachable. Aborting here strands the user with an empty result
        # (previously HTTP 502 / an intake-only preview). Instead degrade to an empty
        # structured result and let the deterministic OCR fallbacks below recover
        # ingredient candidates from the OCR text; the failure is surfaced as a review
        # warning so the preview UI flags it.
        logger.warning(
            "Supplement LLM parse failed (%s); using deterministic OCR fallbacks.",
            type(exc).__name__,
        )
        parse_result = SupplementStructuredParseResult(warnings=[LLM_PARSE_FALLBACK_WARNING])
    _validate_parser_result(parse_result, settings.supplement_parser_max_ingredients)
    try:
        # The deterministic OCR fallbacks below append candidates on top of the
        # already-validated LLM result. When a label yields many ingredient-like
        # lines, the enriched list can exceed the structured schema's max_length and
        # make model_validate() raise a raw pydantic ValidationError. Translate it
        # into the recoverable parser error (the same signal _validate_parser_result
        # raises for the over-limit case it would otherwise check below) so callers
        # degrade to parser_used=False with a warning instead of returning HTTP 500.
        parse_result = _sanitize_parser_result(parse_result)
        parse_result = _merge_ocr_pattern_fallbacks(parse_result, normalized_text)
        parse_result = _merge_layout_precaution_fallbacks(parse_result, ocr_layout)
        parse_result = _merge_ocr_text_section_fallbacks(parse_result, normalized_text)
    except ValidationError as exc:
        raise SupplementParserInputError(
            "Parser fallback enrichment exceeded the structured result schema bounds."
        ) from exc
    _validate_parser_result(parse_result, settings.supplement_parser_max_ingredients)

    # Retain the OCR source text only under BOTH the operator opt-in flag AND the user's
    # per-user RAW_OCR_TEXT_RETENTION consent (optional consent — never blocks analysis).
    retain_raw_ocr_text = settings.store_raw_ocr_text and await has_active_consent(
        session, user, ConsentType.RAW_OCR_TEXT_RETENTION
    )
    snapshot = _build_parsed_snapshot(
        parse_result=parse_result,
        previous_snapshot=record.parsed_snapshot,
        ocr_confidence=normalized_confidence,
        ocr_provider=normalized_provider,
        ocr_layout=ocr_layout,
        settings=settings,
        ocr_text=normalized_text,
        retain_raw_ocr_text=retain_raw_ocr_text,
    )
    # KR-market display: translate any English precaution/intake/functional-claim text
    # to Korean (the source label may be English). Only with the real local LLM parser
    # (skipped when a parser is injected for tests) and best-effort, so a translation
    # failure or timeout never blocks confirmation.
    if parser is None:
        snapshot = await _localize_supplement_snapshot(snapshot, settings)
        # Deterministic KR-market display: rewrite English ingredient names to their
        # standard Korean names (English source preserved for the 한글(영문) render).
        snapshot = localize_ingredient_display_names(snapshot)

    async with persist_scope(session):
        record.ocr_provider = normalized_provider
        record.ocr_confidence = normalized_confidence
        record.ocr_text_hash = text_hash
        record.parsed_snapshot = snapshot
        record.warnings = _build_warning_list(parse_result.warnings, normalized_provider)
        record.algorithm_version = settings.supplement_parser_algorithm_version
        record.status = SupplementAnalysisStatus.REQUIRES_CONFIRMATION.value

    await session.refresh(record)
    return SupplementParserStoreResult(record=record, parse_result=parse_result)


# Async analysis is polled by the app (multi-minute budget), so allow a generous
# window: the localization may translate one coalesced precaution plus a per-item
# retry pass when the batched call returns an unusable response.
_LOCALIZATION_BUDGET_SEC = 40.0


async def _localize_supplement_snapshot(
    snapshot: dict[str, Any], settings: Settings
) -> dict[str, Any]:
    """Best-effort Korean localization of user-facing label sections (KR-market display).

    Uses the same local Ollama model as the structured parser to translate any English
    precaution / intake / functional-claim text to Korean. Bounded by a short budget;
    any failure or timeout returns the snapshot unchanged.

    Args:
        snapshot: Built parsed snapshot.
        settings: Runtime settings (Ollama host/model).

    Returns:
        The snapshot with localized section text, or the original on no-op/failure.
    """
    try:
        client = OllamaChatClient(settings)
        return await asyncio.wait_for(
            localize_snapshot_to_korean(
                snapshot, chat=client.post_chat, model=settings.ollama_model
            ),
            timeout=_LOCALIZATION_BUDGET_SEC,
        )
    except TimeoutError:
        logger.warning(
            "Supplement localization exceeded the %ss budget; keeping original text.",
            _LOCALIZATION_BUDGET_SEC,
        )
        return snapshot
    except Exception:
        # Localization is a display nicety; never let it block or fail parsing.
        logger.warning("Supplement localization failed; keeping original text.", exc_info=True)
        return snapshot


def normalize_ocr_text(ocr_text: str, max_chars: int) -> str:
    """Normalize OCR text before hashing and structured parsing.

    Args:
        ocr_text: Raw OCR text.
        max_chars: Maximum accepted character count.

    Returns:
        Normalized OCR text.

    Raises:
        SupplementParserInputError: If the OCR text is blank or too long.
    """
    normalized = "\n".join(
        line.rstrip() for line in ocr_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ).strip()
    normalized = normalize_provider_ocr_text(normalized)
    if not normalized:
        raise SupplementParserInputError("OCR text is empty.")
    if len(normalized) > max_chars:
        raise SupplementParserInputError("OCR text exceeds the configured parser limit.")
    return normalized


def hash_ocr_text(ocr_text: str, privacy_hash_secret: SecretStr) -> str:
    """Build a privacy-preserving HMAC-SHA256 fingerprint for OCR text.

    Args:
        ocr_text: Normalized OCR text.
        privacy_hash_secret: Application HMAC secret.

    Returns:
        Hex-encoded HMAC-SHA256 OCR text fingerprint.
    """
    secret = privacy_hash_secret.get_secret_value().encode("utf-8")
    return hmac.new(secret, ocr_text.encode("utf-8"), hashlib.sha256).hexdigest()


def _validate_parseable_record(record: SupplementAnalysisRun, ocr_text_hash: str) -> None:
    """Validate a preview row before parsing updates are applied.

    Args:
        record: Existing supplement analysis row.
        ocr_text_hash: HMAC fingerprint of the incoming OCR text.

    Raises:
        SupplementAnalysisExpiredError: If the preview TTL has elapsed.
        SupplementAnalysisStateError: If the row cannot be parsed in its current state.
        SupplementParserConflictError: If a different OCR text hash is already present.
    """
    if record.expires_at <= datetime.now(UTC):
        raise SupplementAnalysisExpiredError("Supplement analysis preview has expired.")
    if record.status not in (
        SupplementAnalysisStatus.REQUIRES_CONFIRMATION.value,
        SupplementAnalysisStatus.PROCESSING.value,
    ):
        raise SupplementAnalysisStateError("Supplement analysis preview is not parseable.")
    if record.ocr_text_hash is not None and record.ocr_text_hash != ocr_text_hash:
        raise SupplementParserConflictError("Supplement analysis preview already has OCR text.")


def _validate_parser_result(
    parse_result: SupplementStructuredParseResult,
    max_ingredients: int,
) -> None:
    """Validate runtime parser bounds not expressed by static JSON schema settings.

    Args:
        parse_result: Validated structured parser result.
        max_ingredients: Runtime maximum ingredient candidates.

    Raises:
        SupplementParserInputError: If the parser result exceeds runtime bounds.
    """
    if len(parse_result.ingredient_candidates) > max_ingredients:
        raise SupplementParserInputError("Parser returned too many ingredient candidates.")


def _sanitize_parser_result(
    parse_result: SupplementStructuredParseResult,
) -> SupplementStructuredParseResult:
    """Strip injection / SQL / HTML / URL payloads from free-text parser fields.

    Blocked product/manufacturer/serving fields collapse to ``None`` so the
    Pydantic schema remains satisfied. Ingredient candidates whose
    ``display_name`` would be blocked are dropped entirely because the schema
    requires a non-empty name. Sanitizer warning codes are merged into the
    returned ``warnings`` list so downstream callers and audit logs see them.

    Args:
        parse_result: Result returned by the LLM parser after schema validation.

    Returns:
        A new ``SupplementStructuredParseResult`` with sanitized free-text fields
        and any ``sanitizer.blocked:*`` warning codes appended.
    """
    snapshot = parse_result.model_dump()
    warnings: list[str] = list(snapshot.get("warnings", []))

    product = snapshot.get("parsed_product") or {}
    name_result = sanitize_product_name(product.get("product_name"))
    product["product_name"] = name_result.value or None
    warnings.extend(name_result.warnings)

    manufacturer_result = sanitize_manufacturer(product.get("manufacturer"))
    product["manufacturer"] = manufacturer_result.value or None
    warnings.extend(manufacturer_result.warnings)

    serving_result = sanitize_serving_size(product.get("serving_size"))
    product["serving_size"] = serving_result.value or None
    warnings.extend(serving_result.warnings)
    snapshot["parsed_product"] = product

    surviving_ingredients: list[dict[str, Any]] = []
    amount_missing = False
    for candidate in snapshot.get("ingredient_candidates", []):
        name_res = sanitize_ingredient_name(candidate.get("display_name"))
        if not name_res.value:
            warnings.extend(name_res.warnings)
            continue
        if _looks_like_non_ingredient_heading(
            name_res.value
        ) or _looks_like_packaging_quantity_token(name_res.value):
            warnings.append(NON_INGREDIENT_HEADING_FILTERED_WARNING)
            continue
        if _looks_like_intake_instruction_text(name_res.value):
            warnings.append(INTAKE_INSTRUCTION_FILTERED_WARNING)
            continue
        # Drop inactive excipients (gelatin, glycerin, purified water, ...) the
        # LLM sometimes emits as ingredients; they are not nutrient content.
        if _is_excipient_name(name_res.value):
            warnings.append(EXCIPIENT_FILTERED_WARNING)
            continue
        original_name_res = sanitize_ingredient_name(candidate.get("original_name"))
        unit_res = sanitize_unit(candidate.get("unit"))
        candidate["display_name"] = name_res.value
        candidate["original_name"] = original_name_res.value or None
        # Canonicalize the unit so LLM-emitted variants (㎎/μg/㎍/mcg/iu) match the
        # deterministic OCR-pattern path (which already normalizes via
        # _normalize_ingredient_unit). Without this, the same ingredient with a unit
        # variant fails to dedupe across the two sources and renders inconsistently.
        candidate["unit"] = _normalize_ingredient_unit(unit_res.value) if unit_res.value else None
        warnings.extend(original_name_res.warnings)
        warnings.extend(unit_res.warnings)
        if candidate.get("amount") is None:
            amount_missing = True
        surviving_ingredients.append(candidate)
    # Flag (do not drop) name-only candidates so reviewers see missing 함량/단위.
    if amount_missing:
        warnings.append(INGREDIENT_AMOUNT_MISSING_WARNING)
    snapshot["ingredient_candidates"] = surviving_ingredients
    snapshot = _sanitize_preview_fields(snapshot, warnings)

    deduped: list[str] = []
    seen: set[str] = set()
    for warning in warnings:
        if warning and warning not in seen:
            deduped.append(warning)
            seen.add(warning)
    snapshot["warnings"] = deduped

    return SupplementStructuredParseResult.model_validate(snapshot)


def _sanitize_preview_fields(snapshot: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    """Sanitize V3 review fields without exposing raw OCR or model payloads.

    Args:
        snapshot: Parser result dump being prepared for storage.
        warnings: Mutable warning list to receive sanitizer codes.

    Returns:
        Snapshot with unsafe review fields removed or normalized.
    """
    for section in snapshot.get("label_sections", []):
        if not isinstance(section, dict):
            continue
        _sanitize_optional_text_field(
            section, "heading_text", "label_section.heading_text", warnings
        )
        _sanitize_optional_text_field(section, "text_bundle", "label_section.text_bundle", warnings)

    intake_method = snapshot.get("intake_method")
    if isinstance(intake_method, dict):
        _sanitize_optional_text_field(intake_method, "text", "intake_method.text", warnings)

    _sanitize_required_text_items(
        snapshot.get("precautions"),
        field_key="text",
        warning_field="precaution.text",
        warnings=warnings,
    )
    _sanitize_required_text_items(
        snapshot.get("functional_claims"),
        field_key="text",
        warning_field="functional_claim.text",
        warnings=warnings,
    )
    _sanitize_required_text_items(
        snapshot.get("evidence_spans"),
        field_key="text_excerpt",
        warning_field="evidence_span.text_excerpt",
        warnings=warnings,
    )
    return snapshot


def _sanitize_optional_text_field(
    target: dict[str, Any],
    key: str,
    warning_field: str,
    warnings: list[str],
) -> None:
    """Sanitize an optional text field in place.

    Args:
        target: Mutable parser output object.
        key: Field name to sanitize.
        warning_field: Stable warning field name.
        warnings: Mutable warning list.
    """
    result = sanitize_preview_text(target.get(key), warning_field)
    warnings.extend(result.warnings)
    target[key] = result.value or None


def _sanitize_required_text_items(
    items: Any,
    *,
    field_key: str,
    warning_field: str,
    warnings: list[str],
) -> None:
    """Sanitize required text fields and drop unsafe items in place.

    Args:
        items: Candidate parser-output list.
        field_key: Required text field inside each list item.
        warning_field: Stable warning field name.
        warnings: Mutable warning list.
    """
    if not isinstance(items, list):
        return
    surviving: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result = sanitize_preview_text(item.get(field_key), warning_field)
        warnings.extend(result.warnings)
        if not result.value:
            continue
        item[field_key] = result.value
        surviving.append(item)
    items[:] = surviving


def _merge_ocr_pattern_fallbacks(
    parse_result: SupplementStructuredParseResult,
    ocr_text: str,
) -> SupplementStructuredParseResult:
    """Enrich missing amounts and add deterministic OCR-derived candidates.

    Two deterministic sources are merged on top of the LLM output:
      1. ``name + amount + unit`` rows from the OCR text (carry amounts).
      2. Name-only items from a Korean 원재료명 / 원료명 declaration list (no
         amount/unit — never fabricated; marked ``source=ingredient_declaration``).
    The amount-bearing source is applied first so that, on dedupe, a real amount
    always wins over a name-only declaration hit. It does not infer ingredients
    from product names or package counts, and it still stores no raw OCR text.

    Args:
        parse_result: Sanitized LLM parser output.
        ocr_text: Normalized OCR text held only in request memory.

    Returns:
        Parser result with bounded fallback candidates merged in.
    """
    fallback_candidates = _extract_ocr_pattern_ingredient_candidates(ocr_text)
    # Drop non-ingredient OCR fragments (nutrition-facts headers, units, short noise)
    # the pattern fallback mines from dense tables before they reach the snapshot.
    fallback_candidates = filter_non_ingredient_ocr_fallback_candidates(fallback_candidates)
    # These candidates are appended after _sanitize_parser_result runs, so content-
    # sanitize them here (before enrich + add) or injection / HTML / SQL / URL /
    # control-char payloads in the OCR text would bypass the filter the LLM path
    # applies and persist into parsed_snapshot.ingredient_candidates.
    fallback_candidates, fallback_warnings = _sanitize_ocr_pattern_candidates(fallback_candidates)
    declaration_candidates = _extract_ingredient_declaration_candidates(ocr_text)
    if not fallback_candidates and not declaration_candidates and not fallback_warnings:
        return parse_result

    snapshot = parse_result.model_dump()
    existing_candidates = _list_of_mappings(snapshot.get("ingredient_candidates"))

    # 1) Enrich existing name-only candidates (amount is None) with an amount/unit
    #    from a name-matched OCR amount pattern, instead of adding a duplicate row.
    enriched = _enrich_missing_amounts_from_fallbacks(existing_candidates, fallback_candidates)

    # 2) Add genuinely-new OCR amount-pattern candidates the LLM missed.
    existing_keys = {_ingredient_candidate_key(candidate) for candidate in existing_candidates}
    existing_name_keys = {
        name_key
        for candidate in existing_candidates
        for name_key in _ingredient_candidate_name_keys(candidate)
    }
    added = False
    for candidate in fallback_candidates:
        key = _ingredient_candidate_key(candidate)
        if key in existing_keys:
            continue
        candidate_name_keys = _ingredient_candidate_name_keys(candidate)
        if any(name_key in existing_name_keys for name_key in candidate_name_keys):
            continue
        existing_candidates.append(candidate)
        existing_keys.add(key)
        existing_name_keys.update(candidate_name_keys)
        added = True
        if len(existing_candidates) >= MAX_PATTERN_FALLBACK_INGREDIENTS:
            break

    # 3) Add name-only 원재료명 declaration candidates for genuinely-new names.
    declaration_added = _merge_declaration_candidates(
        existing_candidates,
        declaration_candidates,
        existing_name_keys,
    )

    if not enriched and not added and not declaration_added and not fallback_warnings:
        return parse_result

    snapshot["ingredient_candidates"] = existing_candidates
    warnings = snapshot.get("warnings")
    # Surface sanitizer codes for any blocked fallback candidate, even when every
    # mined candidate was dropped (so the audit trail records the blocked rows).
    for code in fallback_warnings:
        warnings = _append_unique_string(warnings, code)
    if added or enriched:
        warnings = _append_unique_string(warnings, OCR_PATTERN_FALLBACK_WARNING)
    if declaration_added:
        warnings = _append_unique_string(warnings, INGREDIENT_DECLARATION_WARNING)
    snapshot["warnings"] = warnings
    if added or enriched or declaration_added:
        snapshot["low_confidence_fields"] = _append_unique_string(
            snapshot.get("low_confidence_fields"),
            "ingredient_candidates",
        )
    return SupplementStructuredParseResult.model_validate(snapshot)


def _merge_ocr_text_section_fallbacks(
    parse_result: SupplementStructuredParseResult,
    ocr_text: str,
) -> SupplementStructuredParseResult:
    """Fill missing intake/precaution fields from bounded OCR text lines.

    The structured LLM parser is still preferred. This fallback only promotes
    short visible lines that clearly look like serving instructions or warning /
    allergen statements. It prevents those lines from being stranded in the
    ingredient table while keeping raw full OCR text out of persisted snapshots.

    Args:
        parse_result: Parser result after sanitization and ingredient fallback.
        ocr_text: Normalized OCR text held only in request memory.

    Returns:
        Parser result with review-required intake/precaution text added when
        those sections were otherwise empty or incomplete.
    """
    snapshot = parse_result.model_dump()
    warnings = snapshot.get("warnings")
    low_confidence_fields = snapshot.get("low_confidence_fields")
    updated = False

    intake_method = snapshot.get("intake_method")
    intake_text = intake_method.get("text") if isinstance(intake_method, dict) else None
    if not isinstance(intake_text, str) or not intake_text.strip():
        derived_intake = _extract_ocr_intake_method(ocr_text)
        if derived_intake is not None:
            snapshot["intake_method"] = derived_intake.model_dump(exclude_none=True)
            warnings = _append_unique_string(warnings, OCR_TEXT_SECTION_FALLBACK_WARNING_INTAKE)
            low_confidence_fields = _append_unique_string(low_confidence_fields, "intake_method")
            updated = True

    existing_precaution_keys = {
        _preview_text_key(str(item.get("text") or ""))
        for item in _list_of_mappings(snapshot.get("precautions"))
    }
    derived_precautions = _extract_ocr_precautions(ocr_text, existing_precaution_keys)
    if derived_precautions:
        snapshot["precautions"] = [
            *_list_of_mappings(snapshot.get("precautions")),
            *[item.model_dump(exclude_none=True) for item in derived_precautions],
        ]
        warnings = _append_unique_string(warnings, OCR_TEXT_SECTION_FALLBACK_WARNING_PRECAUTION)
        low_confidence_fields = _append_unique_string(low_confidence_fields, "precautions")
        updated = True

    if (
        not _has_structured_preview_content(snapshot)
        and not _list_of_mappings(snapshot.get("label_sections"))
        and not _list_of_mappings(snapshot.get("evidence_spans"))
    ):
        fallback_sections, fallback_spans = _build_ocr_text_preview_fallbacks(ocr_text)
        if fallback_sections:
            snapshot["label_sections"] = [
                section.model_dump(exclude_none=True) for section in fallback_sections
            ]
            snapshot["evidence_spans"] = [
                span.model_dump(exclude_none=True) for span in fallback_spans
            ]
            warnings = _append_unique_string(warnings, OCR_TEXT_PREVIEW_FALLBACK_WARNING)
            low_confidence_fields = _append_unique_string(low_confidence_fields, "label_sections")
            updated = True

    if not updated:
        return parse_result
    snapshot["warnings"] = warnings
    snapshot["low_confidence_fields"] = low_confidence_fields
    return SupplementStructuredParseResult.model_validate(snapshot)


def _has_structured_preview_content(snapshot: dict[str, Any]) -> bool:
    """Return whether the parser already produced reviewable structured fields.

    Args:
        snapshot: Parser snapshot dict before fallback mutation.

    Returns:
        True when the parser already produced a product identity or product
        match that makes a fallback OCR preview unnecessary. Ingredient,
        intake, precaution, or claim fragments alone are not enough to suppress
        the bounded OCR-text preview because the mobile "text view" still needs
        section/evidence rows to explain what OCR actually read.
    """
    product = snapshot.get("parsed_product")
    if isinstance(product, dict):
        for key in ("product_name", "manufacturer", "brand_name"):
            value = product.get(key)
            if isinstance(value, str) and value.strip():
                return True

    return bool(_list_of_mappings(snapshot.get("matched_product_candidates")))


def _build_ocr_text_preview_fallbacks(
    ocr_text: str,
) -> tuple[list[SupplementPreviewLabelSection], list[SupplementPreviewEvidenceSpan]]:
    """Build bounded review sections from visible OCR lines when parsing fails.

    This does not store the provider payload or unbounded raw OCR. It only
    promotes a small section/evidence preview so the mobile user can verify
    whether OCR actually read the label and decide what to reshoot or correct.

    Args:
        ocr_text: Normalized OCR text held only in request memory.

    Returns:
        Review-required label sections and matching evidence spans.
    """
    sections: list[SupplementPreviewLabelSection] = []
    evidence_spans: list[SupplementPreviewEvidenceSpan] = []
    for index, (heading, lines) in enumerate(_ocr_text_preview_chunks(ocr_text), start=1):
        sanitized_lines = _sanitize_ocr_preview_lines(lines, index)
        if not sanitized_lines:
            continue
        text_bundle = "\n".join(sanitized_lines)[:LAYOUT_TEXT_BUNDLE_MAX_CHARS]
        text_bundle = sanitize_preview_text(
            text_bundle,
            "ocr_text_preview.text_bundle",
        ).value
        if not text_bundle:
            continue
        heading_text = sanitize_preview_text(
            heading or "인식된 OCR 텍스트",
            "ocr_text_preview.heading_text",
        ).value
        section_type = _classify_ocr_text_preview_section(heading, sanitized_lines)
        section_id = f"ocr-text-section-{index:03d}"
        span_id = f"ocr-text-span-{index:03d}"
        sections.append(
            SupplementPreviewLabelSection.model_validate(
                {
                    "section_id": section_id,
                    "section_type": section_type,
                    "heading_text": heading_text,
                    "text_bundle": text_bundle,
                    "confidence": OCR_TEXT_SECTION_FALLBACK_CONFIDENCE,
                    "requires_review": True,
                    "evidence_refs": [span_id],
                }
            )
        )
        evidence_excerpt = sanitize_preview_text(
            text_bundle[:LAYOUT_EVIDENCE_EXCERPT_MAX_CHARS],
            "ocr_text_preview.evidence_excerpt",
        ).value
        if evidence_excerpt:
            evidence_spans.append(
                SupplementPreviewEvidenceSpan.model_validate(
                    {
                        "span_id": span_id,
                        "source_type": "ocr_text_preview",
                        "section_type": section_type,
                        "text_excerpt": evidence_excerpt,
                        "page_index": index - 1,
                        "cell_ref": section_id,
                        "confidence": OCR_TEXT_SECTION_FALLBACK_CONFIDENCE,
                    }
                )
            )
    return sections, evidence_spans


def _ocr_text_preview_chunks(ocr_text: str) -> list[tuple[str | None, list[str]]]:
    """Split fused multi-image OCR text into bounded image/section chunks.

    Args:
        ocr_text: Normalized OCR text held only in request memory.

    Returns:
        Ordered heading/line chunks, capped to the mobile preview schema.
    """
    chunks: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in _ocr_lines(ocr_text):
        marker_match = FUSED_OCR_IMAGE_MARKER_PATTERN.fullmatch(line)
        if marker_match is not None:
            if current_lines:
                chunks.append((current_heading, current_lines))
            current_heading = marker_match.group("label").strip()
            current_lines = []
            continue
        current_lines.append(line)

    if current_lines:
        chunks.append((current_heading, current_lines))
    if not chunks:
        lines = _ocr_lines(ocr_text)
        if lines:
            chunks.append((None, lines))
    return chunks[:OCR_TEXT_PREVIEW_FALLBACK_MAX_SECTIONS]


def _sanitize_ocr_preview_lines(lines: list[str], section_index: int) -> list[str]:
    """Return sanitized OCR lines for a single preview section.

    Args:
        lines: OCR lines belonging to one image/section chunk.
        section_index: One-based section index used for sanitizer field labels.

    Returns:
        Sanitized lines capped by count and aggregate preview size.
    """
    sanitized: list[str] = []
    total_chars = 0
    for line_index, line in enumerate(
        lines[:OCR_TEXT_PREVIEW_FALLBACK_MAX_LINES_PER_SECTION],
        start=1,
    ):
        text = _sanitize_ocr_section_line(
            line,
            f"ocr_text_preview.section_{section_index:03d}.line_{line_index:03d}",
        )
        if not text:
            continue
        sanitized.append(text)
        total_chars += len(text) + 1
        if total_chars >= LAYOUT_TEXT_BUNDLE_MAX_CHARS:
            break
    return sanitized


def _classify_ocr_text_preview_section(heading: str | None, lines: list[str]) -> str:
    """Classify a fallback OCR preview section by visible text cues.

    Args:
        heading: Optional fused image heading.
        lines: Sanitized visible OCR lines.

    Returns:
        A schema-supported section type for mobile grouping.
    """
    haystack = " ".join([heading or "", *lines[:20]]).casefold()
    if any(token in haystack for token in ("warning", "caution", "주의", "경고", "allergen")):
        return "precautions"
    if any(
        token in haystack
        for token in ("suggested use", "directions", "take ", "섭취", "복용", "1일")
    ):
        return "intake_method"
    if any(token in haystack for token in ("other ingredients", "ingredients", "원재료", "원료명")):
        return "ingredients"
    if any(
        token in haystack
        for token in (
            "supplement facts",
            "nutrition facts",
            "amount per serving",
            "daily value",
            "영양정보",
            "영양성분",
        )
    ):
        return "supplement_facts"
    if any(INGREDIENT_AMOUNT_PATTERN.search(line) for line in lines):
        return "supplement_facts"
    return "unknown"


def _extract_ocr_intake_method(ocr_text: str) -> SupplementPreviewIntakeMethod | None:
    """Return a bounded serving instruction candidate from OCR text.

    Args:
        ocr_text: Normalized OCR text held only in request memory.

    Returns:
        Review-required intake method preview, or None when no clear instruction
        line is visible.
    """
    for line in _ocr_lines(ocr_text):
        if not _looks_like_intake_instruction_text(line):
            continue
        if _looks_like_precaution_text(line):
            continue
        if BARE_INTAKE_HEADING_PATTERN.fullmatch(line.strip()):
            continue
        text = _sanitize_ocr_section_line(line, "ocr_intake_method.text")
        if not text:
            continue
        return SupplementPreviewIntakeMethod.model_validate(
            {
                "text": text,
                "confidence": OCR_TEXT_SECTION_FALLBACK_CONFIDENCE,
                "requires_review": True,
                "evidence_refs": ["ocr-text-intake-fallback"],
            }
        )
    return None


def _extract_ocr_precautions(
    ocr_text: str,
    existing_text_keys: set[str],
) -> list[SupplementPreviewPrecaution]:
    """Return bounded warning/allergen lines from OCR text.

    Args:
        ocr_text: Normalized OCR text held only in request memory.
        existing_text_keys: Already emitted precaution text keys.

    Returns:
        Review-required precaution preview rows.
    """
    precautions: list[SupplementPreviewPrecaution] = []
    for index, line in enumerate(_ocr_lines(ocr_text), start=1):
        if len(precautions) >= OCR_TEXT_SECTION_FALLBACK_MAX_PRECAUTIONS:
            break
        if not _looks_like_precaution_text(line):
            continue
        if _is_bare_precaution_heading(line):
            continue
        text = _sanitize_ocr_section_line(line, "ocr_precaution.text")
        if not text:
            continue
        text_key = _preview_text_key(text)
        if text_key in existing_text_keys:
            continue
        try:
            precautions.append(
                SupplementPreviewPrecaution.model_validate(
                    {
                        "text": text,
                        "category": _layout_precaution_category(text),
                        "severity": _layout_precaution_severity(text),
                        "confidence": OCR_TEXT_SECTION_FALLBACK_CONFIDENCE,
                        "requires_review": True,
                        "evidence_refs": [f"ocr-text-precaution-fallback-{index:03d}"],
                    }
                )
            )
        except ValueError:
            continue
        existing_text_keys.add(text_key)
    return precautions


def _merge_layout_precaution_fallbacks(
    parse_result: SupplementStructuredParseResult,
    ocr_layout: LabelLayout | None,
) -> SupplementStructuredParseResult:
    """Promote visible OCR layout caution rows into structured precautions.

    The LLM parser is still the primary structured extractor, but YOLO/ROI OCR can
    surface a warning section that the parser misses. This fallback uses only the
    bounded provider-neutral layout rows already kept for preview evidence; it does
    not store raw OCR text or provider payloads.

    Args:
        parse_result: Sanitized parser output.
        ocr_layout: Optional provider-neutral OCR layout.

    Returns:
        Parser result with missing visible precaution rows appended.
    """
    if ocr_layout is None:
        return parse_result

    existing_text_keys = {
        _preview_text_key(precaution.text) for precaution in parse_result.precautions
    }
    derived: list[SupplementPreviewPrecaution] = []
    for section_index, section in enumerate(ocr_layout.sections, start=1):
        if section.section_type not in {"precautions", "allergen_warning"}:
            continue
        span_id = f"layout-span-{section_index}"
        confidence = _section_confidence(section)
        section_severity = _layout_precaution_severity(section.anchor_text)
        for text in _layout_precaution_texts(section):
            text_key = _preview_text_key(text)
            if text_key in existing_text_keys:
                continue
            severity = _layout_precaution_severity(text)
            if severity == "unknown":
                severity = section_severity
            try:
                derived.append(
                    SupplementPreviewPrecaution.model_validate(
                        {
                            "text": text,
                            "category": _layout_precaution_category(text),
                            "severity": severity,
                            "confidence": confidence,
                            "requires_review": True,
                            "evidence_refs": [span_id],
                        }
                    )
                )
            except ValueError:
                continue
            existing_text_keys.add(text_key)
            if len(parse_result.precautions) + len(derived) >= LAYOUT_PRECAUTION_FALLBACK_MAX_ITEMS:
                break

    if not derived:
        return parse_result

    snapshot = parse_result.model_dump()
    snapshot["precautions"] = [
        *snapshot.get("precautions", []),
        *[precaution.model_dump(exclude_none=True) for precaution in derived],
    ]
    snapshot["warnings"] = _append_unique_string(
        snapshot.get("warnings"),
        LAYOUT_PRECAUTION_FALLBACK_WARNING,
    )
    snapshot["low_confidence_fields"] = _append_unique_string(
        snapshot.get("low_confidence_fields"),
        "precautions",
    )
    return SupplementStructuredParseResult.model_validate(snapshot)


def _layout_precaution_texts(section: LabelSection) -> list[str]:
    """Return sanitized visible precaution rows from a layout section.

    Args:
        section: OCR layout section classified as precautions.

    Returns:
        Bounded visible precaution row texts, excluding bare section headings.
    """
    texts: list[str] = []
    for row in section.rows:
        row_text = " ".join(cell.text for cell in sorted(row, key=lambda item: item.column_index))
        row_text = row_text.strip()
        if not row_text or _is_bare_precaution_heading(row_text):
            continue
        sanitized = sanitize_preview_text(
            row_text[:LAYOUT_PRECAUTION_TEXT_MAX_CHARS],
            "layout_precaution.text",
        ).value
        if sanitized:
            texts.append(sanitized)
    return texts


def _sanitize_ocr_section_line(value: str, warning_field: str) -> str | None:
    """Return a bounded sanitized OCR line suitable for a review section.

    Args:
        value: Candidate OCR line.
        warning_field: Sanitizer field label for audit warning codes.

    Returns:
        Sanitized line text, or None when the line is unsafe or empty.
    """
    return sanitize_preview_text(
        value[:OCR_TEXT_SECTION_FALLBACK_TEXT_MAX_CHARS],
        warning_field,
    ).value


def _looks_like_intake_instruction_text(value: str) -> bool:
    """Return whether text appears to describe how to take the supplement.

    Args:
        value: Candidate OCR or parser text.

    Returns:
        True for serving-instruction fragments such as "1일 1회 1스푼" or
        "Take 1 capsule daily".
    """
    normalized = _ingredient_name_key(value)
    if not normalized:
        return False
    if SERVING_OR_PACKAGE_CONTEXT_PATTERN.search(normalized):
        return False
    if BARE_PACKAGE_QUANTITY_PATTERN.fullmatch(normalized):
        return False
    compact = re.sub(r"[\s,，.·ㆍ:：;；(){}\[\]/|+\-]+", "", normalized)  # noqa: RUF001
    if any(
        token in compact
        for token in (
            "섭취방법",
            "복용방법",
            "1일",
            "일1회",
            "1회",
            "스푼",
            "스쿱",
            "숟가락",
            "정씩",
            "포씩",
            "캡슐씩",
        )
    ):
        return True
    return bool(INTAKE_INSTRUCTION_PATTERN.search(normalized))


def _looks_like_precaution_text(value: str) -> bool:
    """Return whether text appears to be a warning, caution, or allergen line.

    Args:
        value: Candidate OCR line.

    Returns:
        True when the line contains visible precaution/allergen wording.
    """
    normalized = _ingredient_name_key(value)
    if not normalized:
        return False
    if NON_PRECAUTION_CONTACT_PATTERN.search(normalized):
        return False
    return bool(PRECAUTION_TEXT_PATTERN.search(normalized))


def _is_bare_precaution_heading(value: str) -> bool:
    """Return whether a row is only a warning-section heading.

    Args:
        value: Candidate row text.

    Returns:
        True when the row should remain section metadata, not a precaution item.
    """
    normalized = re.sub(r"[\s·ㆍ:\uff1a\-()\[\]/|]+", "", value.casefold())
    return normalized in {
        "warning",
        "warnings",
        "caution",
        "cautions",
        "주의",
        "주의사항",
        "섭취시주의사항",
    }


def _layout_precaution_category(value: str) -> str:
    """Classify visible precaution text into a conservative UI category."""
    normalized = value.casefold()
    if any(token in normalized for token in ("pregnant", "pregnancy", "임산", "임신")):
        return "pregnancy"
    if any(token in normalized for token in ("allergy", "allergen", "알레르")):
        return "allergy"
    if any(
        token in normalized for token in ("medication", "blood clot", "medicine", "약물", "의약품")
    ):
        return "medication"
    if any(token in normalized for token in ("children", "child", "어린이", "소아", "유아")):
        return "children"
    return "unknown"


def _layout_precaution_severity(value: str) -> str:
    """Return a conservative severity marker from visible label wording."""
    normalized = value.casefold()
    if any(token in normalized for token in ("warning", "경고", "fatal", "poison")):
        return "warning"
    if any(token in normalized for token in ("caution", "주의", "consult", "상담")):
        return "caution"
    return "unknown"


def _preview_text_key(value: str) -> str:
    """Normalize preview text for deduplication."""
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


@dataclass(frozen=True)
class _FallbackAmountIndex:
    """Fallback OCR-pattern candidates indexed for amount enrichment.

    Attributes:
        by_full: First fallback per full name key.
        by_base: First fallback per base name key (form/source qualifier stripped).
        base_counts: Number of fallbacks sharing each base key.
        name_only_base_counts: Number of name-only existing candidates sharing each
            base key, used to gate base matching to the unambiguous 1:1 case.
    """

    by_full: dict[str, dict[str, Any]]
    by_base: dict[str, dict[str, Any]]
    base_counts: dict[str, int]
    name_only_base_counts: dict[str, int]


def _build_fallback_amount_index(
    existing_candidates: list[dict[str, Any]],
    fallback_candidates: list[dict[str, Any]],
) -> _FallbackAmountIndex:
    """Index fallback candidates by full and base name for amount enrichment."""
    by_full: dict[str, dict[str, Any]] = {}
    by_base: dict[str, dict[str, Any]] = {}
    base_counts: dict[str, int] = {}
    for candidate in fallback_candidates:
        for key in _ingredient_candidate_name_keys(candidate):
            by_full.setdefault(key, candidate)
        for base in _ingredient_candidate_base_keys(candidate):
            by_base.setdefault(base, candidate)
            base_counts[base] = base_counts.get(base, 0) + 1

    name_only_base_counts: dict[str, int] = {}
    for candidate in existing_candidates:
        if candidate.get("amount") is not None:
            continue
        for base in _ingredient_candidate_base_keys(candidate):
            name_only_base_counts[base] = name_only_base_counts.get(base, 0) + 1

    return _FallbackAmountIndex(by_full, by_base, base_counts, name_only_base_counts)


def _select_fallback_for_candidate(
    candidate: dict[str, Any],
    index: _FallbackAmountIndex,
    consumed_ids: set[int],
) -> dict[str, Any] | None:
    """Return the fallback to enrich a name-only candidate, or None.

    Prefers an exact full-name match, then an unambiguous base-name match (exactly
    one name-only candidate and one fallback share the base). Already-consumed
    fallbacks are skipped so one OCR amount enriches at most one candidate.
    """
    for key in _ingredient_candidate_name_keys(candidate):
        full = index.by_full.get(key)
        if full is not None and id(full) not in consumed_ids:
            return full
    for base in _ingredient_candidate_base_keys(candidate):
        if index.base_counts.get(base) != 1 or index.name_only_base_counts.get(base) != 1:
            continue
        base_match = index.by_base.get(base)
        if base_match is not None and id(base_match) not in consumed_ids:
            return base_match
    return None


def _enrich_missing_amounts_from_fallbacks(
    existing_candidates: list[dict[str, Any]],
    fallback_candidates: list[dict[str, Any]],
) -> bool:
    """Fill amount/unit on name-only candidates from name-matched OCR patterns.

    Matching prefers an exact full-name match, then an unambiguous base-name match
    (a trailing form/source qualifier stripped — see ``_ingredient_base_name_key`` —
    so a name-only ``Zinc (zinc mono-L-methionine, aspartate)`` matches the OCR
    pattern ``Zinc``). A base match fires only when exactly one name-only candidate
    AND exactly one fallback share that base, so a single OCR amount is never
    broadcast across two distinct chemical forms (e.g. two Vitamin A forms). Each
    fallback enriches at most one candidate and is then removed from
    ``fallback_candidates`` so the caller's add-new pass does not re-append it as a
    duplicate. Existing candidates that already carry an amount are left untouched.

    Args:
        existing_candidates: Candidate list mutated in place.
        fallback_candidates: Amount-bearing OCR pattern candidates; entries consumed
            by enrichment are removed in place.

    Returns:
        True when at least one candidate was enriched.
    """
    index = _build_fallback_amount_index(existing_candidates, fallback_candidates)
    consumed_ids: set[int] = set()
    enriched = False
    for candidate in existing_candidates:
        if candidate.get("amount") is not None:
            continue
        match = _select_fallback_for_candidate(candidate, index, consumed_ids)
        if match is None:
            continue
        candidate["amount"] = match.get("amount")
        if not candidate.get("unit"):
            candidate["unit"] = match.get("unit")
        if (
            candidate.get("daily_value_percent") is None
            and match.get("daily_value_percent") is not None
        ):
            candidate["daily_value_percent"] = match.get("daily_value_percent")
        consumed_ids.add(id(match))
        enriched = True

    if consumed_ids:
        fallback_candidates[:] = [
            candidate for candidate in fallback_candidates if id(candidate) not in consumed_ids
        ]
    return enriched


def _merge_declaration_candidates(
    existing_candidates: list[dict[str, Any]],
    declaration_candidates: list[dict[str, Any]],
    existing_name_keys: set[str],
) -> bool:
    """Append name-only 원재료명 declaration candidates for new names only.

    A name already present from the LLM or the amount-pattern path (with or
    without an amount) is left untouched, so trustworthy amounts always win over
    a name-only declaration hit.

    Args:
        existing_candidates: Candidate list mutated in place.
        declaration_candidates: Name-only declaration candidates to merge.
        existing_name_keys: Normalized names already present; updated in place.

    Returns:
        True when at least one declaration candidate was appended.
    """
    declaration_added = False
    for candidate in declaration_candidates:
        if len(existing_candidates) >= MAX_PATTERN_FALLBACK_INGREDIENTS:
            break
        name_keys = _ingredient_candidate_name_keys(candidate)
        if any(name_key in existing_name_keys for name_key in name_keys):
            continue
        existing_candidates.append(candidate)
        existing_name_keys.update(name_keys)
        declaration_added = True
    return declaration_added


# Name-fragment fusion bounds (port of the eval section-name-window recall
# recovery). OCR sometimes splits a COMPOUND ingredient name across adjacent
# lines (``Magnesium`` / ``Citrate``). To avoid ever merging two distinct
# ingredients, fusion only appends a known salt/form continuation word
# (``_SALT_FORM_CONTINUATION_WORDS``) onto a base name — never a second
# standalone name. Bounds keep fused names short and the window small.
_MIN_NAME_FUSION_FRAGMENTS = 2
_MAX_NAME_FRAGMENT_CHARS = 14
_MAX_NAME_FUSION_WINDOW = 4
_MAX_FUSED_NAME_CHARS = 48

# Salt / chelate / form words that trail a base ingredient name when OCR splits a
# compound name across lines. A fragment is fused only if it is one of these, so a
# fragment that is itself a plausible standalone ingredient (Calcium, 셀레늄,
# Folate ...) is never treated as a continuation and two real rows never merge.
_SALT_FORM_CONTINUATION_WORDS = frozenset(
    # Curated word list kept compact; a list literal would explode to one word
    # per line under the formatter, so SIM905 is suppressed on the line below.
    "citrate oxide carbonate gluconate glycinate bisglycinate malate picolinate "  # noqa: SIM905
    "chloride sulfate sulphate stearate aspartate lactate fumarate orotate "
    "taurate ascorbate phosphate acetate hydrochloride hcl chelate monohydrate "
    "hydroxide selenite selenate molybdate succinate pidolate".split()
)


def _looks_like_salt_continuation(fragment: str) -> bool:
    """Return whether a fragment is a salt / form word continuing a base name.

    Only such fragments are fused onto a preceding ingredient name, so two real
    adjacent ingredients are never merged into one phantom row.

    Args:
        fragment: A cleaned, short OCR line.

    Returns:
        True when any latin token of the fragment is a known salt/form word.
    """
    return any(
        token in _SALT_FORM_CONTINUATION_WORDS for token in re.findall(r"[a-z]+", fragment.lower())
    )


def _line_carries_amount_signal(line: str) -> bool:
    """Return whether a line carries any amount / number / unit token.

    Used by name-fragment fusion to stop at value lines, so fusion never spans an
    amount and can never invent one.

    Args:
        line: A single OCR line.

    Returns:
        True when the line holds an amount, a bare number, or a unit token.
    """
    return bool(
        BARE_INGREDIENT_AMOUNT_PATTERN.fullmatch(line)
        or BARE_INGREDIENT_NUMBER_PATTERN.fullmatch(line)
        or INGREDIENT_UNIT_ONLY_PATTERN.fullmatch(line)
        or INGREDIENT_AMOUNT_PATTERN.search(line)
    )


def _fuse_adjacent_name_fragment_lines(lines: list[str]) -> list[str]:
    """Fuse a split compound ingredient name onto its base line.

    Recovers OCR splits such as ``Magnesium`` / ``Citrate`` so downstream
    name+amount pairing sees the complete name and no stray fragment line.
    Conservative by design: an anchor must be a short name that is NOT itself a
    salt/form word, and every appended fragment must be a known salt/form
    continuation (``_looks_like_salt_continuation``) — so two distinct standalone
    ingredients are never merged. It never fuses across a value line, so it can
    neither invent nor move an amount.

    Args:
        lines: Bounded OCR lines.

    Returns:
        Lines with split compound names fused; all other lines unchanged.
    """
    fused: list[str] = []
    index = 0
    line_count = len(lines)
    while index < line_count:
        stripped = lines[index].strip()
        if (
            stripped
            and len(stripped) <= _MAX_NAME_FRAGMENT_CHARS
            and not _line_carries_amount_signal(stripped)
            and _clean_split_line_ingredient_name(stripped)
            # A salt/form word alone is a continuation, not a base ingredient name.
            and not _looks_like_salt_continuation(stripped)
        ):
            parts = [stripped]
            scan = index + 1
            while scan < line_count and len(parts) < _MAX_NAME_FUSION_WINDOW:
                candidate = lines[scan].strip()
                if (
                    not candidate
                    or len(candidate) > _MAX_NAME_FRAGMENT_CHARS
                    or _line_carries_amount_signal(candidate)
                    or not _clean_split_line_ingredient_name(candidate)
                    # Only a salt/form word continues a name; a standalone
                    # ingredient (Calcium, 셀레늄, Folate ...) is never fused.
                    or not _looks_like_salt_continuation(candidate)
                ):
                    break
                parts.append(candidate)
                scan += 1
            if (
                len(parts) >= _MIN_NAME_FUSION_FRAGMENTS
                and len(" ".join(parts)) <= _MAX_FUSED_NAME_CHARS
            ):
                fused.append(" ".join(parts))
                index = scan
                continue
        fused.append(lines[index])
        index += 1
    return fused


def _extract_ocr_pattern_ingredient_candidates(ocr_text: str) -> list[dict[str, Any]]:
    """Extract review-required ingredients from explicit OCR amount patterns.

    Args:
        ocr_text: Normalized OCR text held only in request memory.

    Returns:
        Bounded schema-shaped ingredient candidates.
    """
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, float, str]] = set()
    lines = _fuse_adjacent_name_fragment_lines(_ocr_lines(ocr_text))
    for line in lines:
        for pattern in (INGREDIENT_TABLE_ROW_PATTERN, INGREDIENT_AMOUNT_PATTERN):
            for match in pattern.finditer(line):
                _append_ocr_pattern_candidate(
                    candidates,
                    seen,
                    name=match.group("name"),
                    amount_text=match.group("amount"),
                    unit_text=match.group("unit"),
                    daily_value_text=match.group("dv"),
                )
                if len(candidates) >= MAX_PATTERN_FALLBACK_INGREDIENTS:
                    return candidates
    _extract_nearby_table_ingredient_candidates(lines, candidates, seen)
    if len(candidates) >= MAX_PATTERN_FALLBACK_INGREDIENTS:
        return candidates
    _extract_split_line_ingredient_candidates(lines, candidates, seen)
    return candidates


def _extract_nearby_table_ingredient_candidates(
    lines: list[str],
    candidates: list[dict[str, Any]],
    seen: set[tuple[str, float, str]],
) -> None:
    """Recover ingredient rows split across neighboring OCR table cells.

    The fallback is intentionally conservative: it requires a visible ingredient
    name line and a visible amount+unit nearby, optionally followed by a visible
    %DV line. It never infers an amount from GT or from the ingredient name.

    Args:
        lines: Bounded OCR lines.
        candidates: Mutable candidate list, already seeded by same-line rows.
        seen: Mutable dedupe set shared with other extraction passes.
    """
    for name_index, line in enumerate(lines):
        if len(candidates) >= MAX_PATTERN_FALLBACK_INGREDIENTS:
            return
        name = _clean_split_line_ingredient_name(line)
        if not name:
            continue
        if _append_nearby_amount_for_name(lines, name_index, name, candidates, seen):
            continue

    for amount_index, line in enumerate(lines):
        if len(candidates) >= MAX_PATTERN_FALLBACK_INGREDIENTS:
            return
        amount_match = BARE_INGREDIENT_AMOUNT_PATTERN.fullmatch(line)
        if amount_match is None:
            continue
        name = _nearest_name_for_amount(lines, amount_index)
        if not name:
            continue
        _append_ocr_pattern_candidate(
            candidates,
            seen,
            name=name,
            amount_text=amount_match.group("amount"),
            unit_text=amount_match.group("unit"),
            daily_value_text=amount_match.group("dv")
            or _daily_value_text_after(lines, amount_index),
        )


def _append_nearby_amount_for_name(
    lines: list[str],
    name_index: int,
    name: str,
    candidates: list[dict[str, Any]],
    seen: set[tuple[str, float, str]],
) -> bool:
    """Append the nearest visible amount for a split table-row name.

    Args:
        lines: OCR lines.
        name_index: Index of the visible ingredient name line.
        name: Cleaned ingredient name.
        candidates: Mutable candidate list.
        seen: Mutable dedupe set.

    Returns:
        True when a visible amount/unit was paired with ``name``.
    """
    scan_end = min(len(lines), name_index + 7)
    for amount_index in range(name_index + 1, scan_end):
        amount_match = BARE_INGREDIENT_AMOUNT_PATTERN.fullmatch(lines[amount_index])
        if amount_match is not None:
            _append_ocr_pattern_candidate(
                candidates,
                seen,
                name=name,
                amount_text=amount_match.group("amount"),
                unit_text=amount_match.group("unit"),
                daily_value_text=amount_match.group("dv")
                or _daily_value_text_after(lines, amount_index),
            )
            return True

        number_match = BARE_INGREDIENT_NUMBER_PATTERN.fullmatch(lines[amount_index])
        if number_match is None:
            continue
        for unit_index in range(amount_index + 1, min(len(lines), amount_index + 4)):
            unit_match = INGREDIENT_UNIT_ONLY_PATTERN.fullmatch(lines[unit_index])
            if unit_match is None:
                continue
            _append_ocr_pattern_candidate(
                candidates,
                seen,
                name=name,
                amount_text=number_match.group("amount"),
                unit_text=unit_match.group("unit"),
                daily_value_text=unit_match.group("dv")
                or _daily_value_text_after(lines, unit_index),
            )
            return True
    return False


def _daily_value_text_after(lines: list[str], index: int) -> str | None:
    """Return a visible %DV token following an amount line.

    Args:
        lines: OCR lines.
        index: Amount or unit line index.

    Returns:
        The visible percent number, or ``None`` when absent.
    """
    for next_index in range(index + 1, min(len(lines), index + 4)):
        match = BARE_DAILY_VALUE_PERCENT_PATTERN.fullmatch(lines[next_index])
        if match is not None:
            return match.group("dv")
    return None


def _nearest_name_for_amount(lines: list[str], amount_index: int) -> str:
    """Find the nearest safe visible name around an amount/unit line.

    Args:
        lines: OCR lines.
        amount_index: Index containing a visible amount and unit.

    Returns:
        Cleaned nearby ingredient name, or an empty string.
    """
    for distance in range(1, 7):
        previous_index = amount_index - distance
        if previous_index >= 0:
            previous_name = _clean_split_line_ingredient_name(lines[previous_index])
            if previous_name:
                return previous_name
        next_index = amount_index + distance
        if next_index < len(lines):
            next_name = _clean_split_line_ingredient_name(lines[next_index])
            if next_name:
                return next_name
    return ""


def _try_append_amount_first_candidate(
    candidates: list[dict[str, Any]],
    seen: set[tuple[str, float, str]],
    line: str,
) -> bool:
    """Append an amount-first ingredient row ("100 mg 비타민C") when the line matches.

    A visible unit is required so no amount is fabricated, and the trailing name
    passes the shared ingredient-name guards via :func:`_append_ocr_pattern_candidate`.

    Args:
        candidates: Mutable output candidate list.
        seen: Mutable dedupe set shared with the other extraction passes.
        line: A single OCR line.

    Returns:
        True when the line is an amount-first row (so the caller stops handling it),
        even when the trailing token is a qualifier (e.g. "이상") that is skipped.
    """
    match = AMOUNT_FIRST_INGREDIENT_PATTERN.fullmatch(line)
    if match is None:
        return False
    name = match.group("name").strip()
    # Skip when the leading token is a Korean amount qualifier ("100 mg 이상"); the
    # leading-token check also catches multi-word phrases ("100 mg 이상 섭취 금지").
    # A bare "%" unit is rejected centrally in _append_ocr_pattern_candidate.
    leading_token = name.split(maxsplit=1)[0] if name.split() else ""
    if leading_token not in AMOUNT_FIRST_NAME_STOPWORDS:
        _append_ocr_pattern_candidate(
            candidates,
            seen,
            name=name,
            amount_text=match.group("amount"),
            unit_text=match.group("unit"),
            daily_value_text=match.group("dv"),
        )
    return True


def _try_append_cfu_magnitude_candidate(
    candidates: list[dict[str, Any]],
    seen: set[tuple[str, float, str]],
    line: str,
) -> bool:
    """Append a CFU ingredient whose count uses a myriad counter or magnitude word.

    Handles "유산균 100억 CFU" (name-first) and "100억 CFU 유산균" (amount-first). The
    magnitude (억/조/billion) is kept in the unit string ("억 CFU") because the absolute
    count (e.g. 10^10) exceeds the amount field bound and the label shows no separate
    plain amount; the name passes the shared guards via _append_ocr_pattern_candidate.

    Args:
        candidates: Mutable output candidate list.
        seen: Mutable dedupe set shared with the other extraction passes.
        line: A single OCR line.

    Returns:
        True when the line is a CFU magnitude row (so the caller stops handling it).
    """
    for pattern in (CFU_MAGNITUDE_NAME_FIRST_PATTERN, CFU_MAGNITUDE_AMOUNT_FIRST_PATTERN):
        match = pattern.match(line)
        if match is None:
            continue
        _append_ocr_pattern_candidate(
            candidates,
            seen,
            name=match.group("name"),
            amount_text=match.group("amount"),
            unit_text=f"{match.group('mag')} CFU",
            daily_value_text=None,
        )
        return True
    return False


# A cohesive line-by-line state machine pairing name/amount/unit in both orders;
# splitting it across helpers would thread mutable pairing state and hurt
# readability, so the branch/statement caps are intentionally waived here.
def _extract_split_line_ingredient_candidates(  # noqa: PLR0912, PLR0915
    lines: list[str],
    candidates: list[dict[str, Any]],
    seen: set[tuple[str, float, str]],
) -> None:
    """Mine ingredients from amount-first and split name/amount/unit OCR lines.

    Mutates ``candidates`` in place, honoring the shared
    ``MAX_PATTERN_FALLBACK_INGREDIENTS`` cap. Handles amount-first rows, ``name``
    followed by a bare ``amount unit`` line, and three-line ``name`` / ``number`` /
    ``unit`` splits.

    Args:
        lines: Bounded OCR lines.
        candidates: Mutable candidate list, already seeded by the same-line pass.
        seen: Mutable dedupe set shared with the same-line pass.
    """
    previous_name: str | None = None
    pending_split_amount: tuple[str, str] | None = None
    # ``pending_split_unit`` mirrors ``pending_split_amount`` for the reverse
    # (unit-before-amount) line order found on vertical / column labels, where a
    # bare unit precedes the number: ``name`` then ``mg`` then ``200``. Holds
    # (name, unit) until the number arrives. Symmetric risk profile to
    # ``pending_split_amount`` and reset at the same points.
    pending_split_unit: tuple[str, str] | None = None
    for line in lines:
        if len(candidates) >= MAX_PATTERN_FALLBACK_INGREDIENTS:
            return
        if _try_append_cfu_magnitude_candidate(candidates, seen, line):
            previous_name = None
            pending_split_amount = None
            pending_split_unit = None
            continue
        if _try_append_amount_first_candidate(candidates, seen, line):
            previous_name = None
            pending_split_amount = None
            pending_split_unit = None
            continue
        amount_match = BARE_INGREDIENT_AMOUNT_PATTERN.fullmatch(line)
        if amount_match is not None:
            if previous_name is not None:
                _append_ocr_pattern_candidate(
                    candidates,
                    seen,
                    name=previous_name,
                    amount_text=amount_match.group("amount"),
                    unit_text=amount_match.group("unit"),
                    daily_value_text=amount_match.group("dv"),
                )
            previous_name = None
            pending_split_amount = None
            pending_split_unit = None
            continue
        number_match = BARE_INGREDIENT_NUMBER_PATTERN.fullmatch(line)
        if number_match is not None:
            if previous_name is not None:
                pending_split_amount = (previous_name, number_match.group("amount"))
                previous_name = None
                pending_split_unit = None
                continue
            if pending_split_unit is not None:
                pending_name, pending_unit = pending_split_unit
                _append_ocr_pattern_candidate(
                    candidates,
                    seen,
                    name=pending_name,
                    amount_text=number_match.group("amount"),
                    unit_text=pending_unit,
                    daily_value_text=None,
                )
                pending_split_unit = None
                continue
        unit_match = INGREDIENT_UNIT_ONLY_PATTERN.fullmatch(line)
        if unit_match is not None:
            if pending_split_amount is not None:
                pending_name, pending_amount = pending_split_amount
                _append_ocr_pattern_candidate(
                    candidates,
                    seen,
                    name=pending_name,
                    amount_text=pending_amount,
                    unit_text=unit_match.group("unit"),
                    daily_value_text=unit_match.group("dv"),
                )
                pending_split_amount = None
                continue
            if previous_name is not None:
                pending_split_unit = (previous_name, unit_match.group("unit"))
                previous_name = None
                continue
        if INGREDIENT_AMOUNT_PATTERN.search(line):
            previous_name = None
            pending_split_amount = None
            pending_split_unit = None
            continue
        previous_name = _clean_split_line_ingredient_name(line) or None
        if previous_name is not None:
            pending_split_amount = None
            pending_split_unit = None


def _append_ocr_pattern_candidate(
    candidates: list[dict[str, Any]],
    seen: set[tuple[str, float, str]],
    *,
    name: str,
    amount_text: str,
    unit_text: str,
    daily_value_text: str | None,
) -> bool:
    """Append one deterministic OCR ingredient candidate when it is safe.

    Args:
        candidates: Mutable output candidate list.
        seen: Mutable dedupe set keyed by normalized name, amount, and unit.
        name: Visible ingredient name text from OCR.
        amount_text: Visible amount number from OCR.
        unit_text: Visible amount unit from OCR.
        daily_value_text: Optional visible %DV number from OCR.

    Returns:
        True when a candidate was appended.
    """
    cleaned_name = _clean_ingredient_name(name)
    if not cleaned_name:
        return False
    # Excipients can also appear as "name + amount + unit" in OCR text; keep the
    # fallback path consistent with the LLM-path excipient filter.
    if _is_excipient_name(cleaned_name):
        return False
    amount = _parse_ingredient_amount(amount_text)
    unit = _normalize_ingredient_unit(unit_text)
    # A bare "%" unit means the number is a %DV, not an ingredient dose; never
    # fabricate it as an amount (covers every extraction path that appends here).
    if unit == "%":
        return False
    daily_value_percent = _parse_ingredient_amount(daily_value_text) if daily_value_text else None
    key = (_ingredient_name_key(cleaned_name), amount, unit)
    if key in seen:
        return False
    seen.add(key)
    candidates.append(
        {
            "display_name": cleaned_name,
            "original_name": cleaned_name,
            "nutrient_code": None,
            "amount": amount,
            "unit": unit,
            "daily_value_percent": daily_value_percent,
            "confidence": 0.55,
            "source": OCR_PATTERN_FALLBACK_SOURCE,
        }
    )
    return True


def _sanitize_ocr_pattern_candidates(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Apply output-stage content sanitization to OCR amount-pattern candidates.

    The deterministic amount-pattern fallback mines candidates straight from OCR
    text and :func:`_merge_ocr_pattern_fallbacks` appends them *after*
    :func:`_sanitize_parser_result` has already run. Unlike LLM candidates, their
    ``display_name`` / ``unit`` would otherwise reach the API preview without
    passing the prompt-injection / HTML / SQL / URL / control-char filter. This
    mirrors the LLM-path candidate loop in :func:`_sanitize_parser_result`: a
    candidate whose ``display_name`` is blocked is dropped, a blocked ``unit`` is
    cleared to ``None``, and the sanitizer warning codes are returned so the
    caller can record them. Excipient filtering already happens in
    :func:`_extract_ocr_pattern_ingredient_candidates`, so it is not repeated here.

    Args:
        candidates: Raw fallback candidates from
            :func:`_extract_ocr_pattern_ingredient_candidates`.

    Returns:
        Tuple of (surviving sanitized candidates, sanitizer warning codes).
    """
    surviving: list[dict[str, Any]] = []
    warnings: list[str] = []
    for candidate in candidates:
        name_res = sanitize_ingredient_name(candidate.get("display_name"))
        if not name_res.value:
            warnings.extend(name_res.warnings)
            continue
        if _looks_like_intake_instruction_text(name_res.value):
            warnings.append(INTAKE_INSTRUCTION_FILTERED_WARNING)
            continue
        unit_res = sanitize_unit(candidate.get("unit"))
        candidate["display_name"] = name_res.value
        candidate["original_name"] = name_res.value
        candidate["unit"] = unit_res.value or None
        warnings.extend(unit_res.warnings)
        surviving.append(candidate)
    return surviving, warnings


def _extract_ingredient_declaration_candidates(ocr_text: str) -> list[dict[str, Any]]:
    """Mine ingredient NAMES from a Korean 원재료명 / 원료명 declaration list.

    Unlike :func:`_extract_ocr_pattern_ingredient_candidates` (which requires a
    visible ``name + amount + unit``), this reads the ingredient-declaration
    section and emits name-only candidates. Per the app's safety posture these
    candidates always carry ``amount=None`` and ``unit=None`` — amounts are never
    fabricated. The only numeric value captured is an explicit ``<name> NN.NN%``
    declared percentage when it is literally present in the text.

    Provenance is recorded via ``source=INGREDIENT_DECLARATION_SOURCE`` so the UI
    and downstream code can distinguish declaration-sourced (name-only) candidates
    from facts-table candidates that carry real amounts. Excipients are dropped
    and the leading ``원재료명/원료명(및 함량)`` header is stripped, matching the
    existing fallback path.

    Args:
        ocr_text: Normalized OCR text held only in request memory.

    Returns:
        Bounded schema-shaped name-only ingredient candidates.
    """
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for declaration_body in _declaration_bodies_from_ocr_lines(_ocr_lines(ocr_text)):
        for name, percent in _split_ingredient_declaration(declaration_body):
            cleaned = _clean_declaration_ingredient_name(name)
            if not cleaned:
                continue
            # Declaration names skip ``_sanitize_parser_result`` (it runs before
            # this fallback), so route them through the same injection / HTML /
            # SQL / control-char filter here. Sanitize FIRST, then run the
            # excipient check and dedup on the sanitized value so a payload can
            # never slip past via the pre-sanitized string.
            name_result = sanitize_ingredient_name(cleaned)
            if not name_result.value:
                continue
            cleaned = name_result.value
            # Reuse the shared excipient denylist so 젤라틴/정제수/이산화규소 etc. are
            # dropped exactly as on every other ingredient path.
            if _is_excipient_name(cleaned):
                continue
            name_key = _ingredient_name_key(cleaned)
            if name_key in seen:
                continue
            seen.add(name_key)
            candidate: dict[str, Any] = {
                "display_name": cleaned,
                "original_name": cleaned,
                "nutrient_code": None,
                "amount": None,
                "unit": None,
                "daily_value_percent": percent,
                "confidence": INGREDIENT_DECLARATION_CONFIDENCE,
                "source": INGREDIENT_DECLARATION_SOURCE,
            }
            candidates.append(candidate)
            if len(candidates) >= MAX_DECLARATION_INGREDIENTS:
                return candidates
    return candidates


def _declaration_bodies_from_ocr_lines(lines: list[str]) -> list[str]:
    """Return declaration bodies after 원재료명/원료명/성분명 headings.

    OCR frequently emits the declaration heading and the ingredient names on
    separate lines. The previous one-line parser missed those names even though
    they were visible in OCR. This helper keeps the safety boundary intact: it
    starts only from an explicit declaration heading and stops at visible section
    headings such as 섭취 방법, 주의사항, or Supplement Facts.

    Args:
        lines: Bounded OCR lines.

    Returns:
        Declaration body strings. Multi-line bodies are joined with commas so
        each OCR line remains an independent candidate token.
    """
    bodies: list[str] = []
    for index, line in enumerate(lines):
        header = INGREDIENT_DECLARATION_HEADER_PATTERN.match(line)
        if header is None:
            continue
        parts: list[str] = []
        inline_body = line[header.end() :].strip()
        if inline_body:
            parts.append(inline_body)
        parts.extend(_collect_declaration_continuation_lines(lines, index + 1))
        if parts:
            bodies.append(", ".join(parts))
    return bodies


def _collect_declaration_continuation_lines(lines: list[str], start_index: int) -> list[str]:
    """Collect visible ingredient-declaration continuation lines.

    Args:
        lines: Bounded OCR lines.
        start_index: First line after a declaration heading.

    Returns:
        Safe continuation lines, capped to avoid swallowing unrelated label text.
    """
    continuation: list[str] = []
    for line in lines[start_index : start_index + MAX_DECLARATION_CONTINUATION_LINES]:
        stripped = line.strip()
        if not stripped:
            continue
        if INGREDIENT_DECLARATION_HEADER_PATTERN.match(stripped):
            break
        if _is_declaration_continuation_stop_line(stripped):
            break
        continuation.append(stripped)
    return continuation


def _is_declaration_continuation_stop_line(line: str) -> bool:
    """Return whether a line marks the end of an ingredient declaration block."""
    if DECLARATION_CONTINUATION_STOP_PATTERN.search(line):
        return True
    normalized = _ingredient_name_key(line)
    if not normalized:
        return True
    stop_tokens = (
        "nutrition facts",
        "supplement facts",
        "amount per serving",
        "serving size",
        "suggested use",
        "directions",
        "warning",
        "caution",
        "consult",
        "영양 정보",
        "영양정보",
        "영양 성분",
        "영양성분",
        "섭취 방법",
        "섭취방법",
        "복용 방법",
        "복용방법",
        "주의 사항",
        "주의사항",
    )
    return any(token in normalized for token in stop_tokens)


def _split_ingredient_declaration(text: str) -> list[tuple[str, float | None]]:
    """Split a 원재료명 declaration body into ``(name, declared_percent)`` tuples.

    The declared percent is populated only when an explicit ``NN.NN%`` is present
    next to the name (e.g. "이노시톨 88.8889%"); otherwise it is ``None``. No
    amount or unit is ever derived here.

    Args:
        text: Declaration text after the header prefix has been removed.

    Returns:
        Ordered ``(raw_name, declared_percent)`` tuples, before name cleaning.
    """
    results: list[tuple[str, float | None]] = []
    for token in INGREDIENT_DECLARATION_SPLIT_PATTERN.split(text):
        piece = token.strip()
        if not piece:
            continue
        percent: float | None = None
        percent_match = INGREDIENT_DECLARATION_PERCENT_PATTERN.search(piece)
        if percent_match is not None:
            percent = _parse_ingredient_amount(percent_match.group("percent"))
            piece = INGREDIENT_DECLARATION_PERCENT_PATTERN.sub("", piece)
        results.append((piece, percent))
    return results


def _clean_declaration_ingredient_name(value: str) -> str:
    """Normalize a single name token from a 원재료명 declaration list.

    Drops inline parentheticals and the same heading prefixes / packaging tokens
    the OCR-pattern path rejects, so the result is a bare ingredient name or an
    empty string when the token is not a usable name.

    Args:
        value: Raw name token split from the declaration body.

    Returns:
        Cleaned ingredient name, or an empty string when unusable.
    """
    cleaned = INGREDIENT_DECLARATION_PAREN_PATTERN.sub(" ", value)
    cleaned = _strip_ingredient_heading_prefix(cleaned)
    # Strip a trailing amount/unit so name-only candidates never embed a number
    # (the amount-pattern path owns "name + amount + unit" rows).
    cleaned = INGREDIENT_DECLARATION_TRAILING_AMOUNT_PATTERN.sub("", cleaned)
    cleaned = cleaned.strip(TRAILING_INGREDIENT_PUNCTUATION)
    cleaned = " ".join(cleaned.split())
    if not (INGREDIENT_MIN_NAME_CHARS <= len(cleaned) <= INGREDIENT_MAX_NAME_CHARS):
        return ""
    if _looks_like_non_ingredient_heading(cleaned):
        return ""
    if _looks_like_packaging_quantity_token(cleaned):
        return ""
    if _looks_like_intake_instruction_text(cleaned):
        return ""
    if not re.search(r"[A-Za-z가-힣]", cleaned):
        return ""
    return cleaned


def _ocr_lines(ocr_text: str) -> list[str]:
    """Return bounded non-empty OCR lines.

    Args:
        ocr_text: OCR text held only in request memory.

    Returns:
        Non-empty lines capped for deterministic fallback work.
    """
    return [line.strip() for line in ocr_text.splitlines() if line.strip()][:300]


def _clean_ingredient_name(value: str) -> str:
    """Normalize a regex-captured ingredient name.

    Args:
        value: Ingredient prefix captured before an amount and unit.

    Returns:
        Cleaned ingredient name, or an empty string when the prefix is unsafe.
    """
    cleaned = re.sub(r"^[^A-Za-z가-힣]+", "", value)
    cleaned = _strip_ingredient_heading_prefix(cleaned)
    cleaned = re.sub(r"[:\uff1a|·•]+$", "", cleaned).strip(TRAILING_INGREDIENT_EDGE_PUNCTUATION)
    cleaned = " ".join(cleaned.split())
    if not (INGREDIENT_MIN_NAME_CHARS <= len(cleaned) <= INGREDIENT_MAX_NAME_CHARS):
        return ""
    if _looks_like_non_ingredient_heading(cleaned):
        return ""
    if _looks_like_packaging_quantity_token(cleaned):
        return ""
    if _looks_like_intake_instruction_text(cleaned):
        return ""
    if not re.search(r"[A-Za-z가-힣]", cleaned):
        return ""
    return cleaned


def _clean_split_line_ingredient_name(value: str) -> str:
    """Normalize an OCR line that may be followed by a bare amount line.

    Args:
        value: Candidate ingredient-name line from OCR.

    Returns:
        Cleaned ingredient name, or an empty string when unusable.
    """
    cleaned = _clean_ingredient_name(value)
    if not cleaned:
        return ""
    if BARE_INGREDIENT_AMOUNT_PATTERN.fullmatch(cleaned):
        return ""
    if INGREDIENT_AMOUNT_PATTERN.search(cleaned):
        return ""
    if _is_excipient_name(cleaned):
        return ""
    # A split-line name should be mostly textual. This avoids turning noisy
    # product/package fragments such as "30 capsule count" into ingredients.
    alpha_count = len(re.findall(r"[A-Za-z가-힣]", cleaned))
    digit_count = len(re.findall(r"\d", cleaned))
    if digit_count > 0 and digit_count >= alpha_count:
        return ""
    return cleaned


def _strip_ingredient_heading_prefix(value: str) -> str:
    """Remove common Korean/English section prefixes from a candidate.

    Args:
        value: Candidate ingredient prefix.

    Returns:
        Candidate with non-ingredient section wording removed.
    """
    cleaned = value.strip()
    patterns = (
        r"^(?:nutrition facts|supplement facts)\s*[:\uff1a|·•-]*\s*",
        r"^(?:active\s+ingredients?|other\s+ingredients?|ingredients?)\s*[:\uff1a|·•-]*\s*",
        r"^(?:영양\s*정보|영양\s*기능\s*정보|기능\s*정보)\s*[:\uff1a|·•-]*\s*",
        r"^(?:원재료명|원료명)\s*(?:및\s*함량)?\s*[:\uff1a|·•-]*\s*",
        r"^(?:1일\s*)?(?:섭취량|섭취\s*방법)\s*[:\uff1a|·•-]*\s*",
        r"^(?:(?:1\s*)?회\s*)?제공량\s*[\(:\uff1a|·•-]*\s*",
        r"^(?:serving\s*size|amount\s*per\s*serving|servings?\s*per\s*container)"
        r"\s*[\(:\uff1a|·•-]*\s*",
    )
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _looks_like_non_ingredient_heading(value: str) -> bool:
    """Return whether text is a generic label heading, not an ingredient.

    Args:
        value: Cleaned ingredient candidate.

    Returns:
        True when the candidate is likely a section or package descriptor.
    """
    normalized = _ingredient_name_key(value)
    heading_tokens = (
        "nutrition facts",
        "supplement facts",
        "영양 정보",
        "영양정보",
        "영양성분기준치",
        "영양 성분 기준치",
        "영양 기능 정보",
        "영양기능정보",
        "daily value",
        "daily values",
        "% daily value",
        "%dv",
        "active ingredient",
        "active ingredients",
        "other ingredient",
        "other ingredients",
        "ingredients",
        "섭취 방법",
        "섭취방법",
        "주의 사항",
        "주의사항",
        "원재료명",
        "원료명",
        "기능 정보",
        "기능정보",
        "건강기능식품",
        "총 내용량",
        "내용량",
        "1회 제공량",
        "1회제공량",
        "회 제공량",
        "회제공량",
        "제공량",
        "serving size",
        "amount per serving",
        "servings per container",
        "제조원",
        "보관",
        "유통기한",
    )
    return any(token in normalized for token in heading_tokens)


def _looks_like_packaging_quantity_token(value: str) -> bool:
    """Return whether a candidate is a package quantity fragment.

    Args:
        value: Cleaned ingredient candidate.

    Returns:
        True when the value is a bounded package/serving-count fragment.
    """
    normalized = _ingredient_name_key(value)
    if not normalized:
        return False
    return any(pattern.fullmatch(normalized) for pattern in PACKAGING_QUANTITY_PATTERNS)


def _parse_ingredient_amount(value: str) -> int | float:
    """Parse a visible numeric ingredient amount.

    Args:
        value: OCR amount text.

    Returns:
        Integer when exact, otherwise float.
    """
    # PaddleOCR occasionally confuses numeric glyphs in tight facts tables.
    # Normalize only characters that are visually used as digits inside an
    # already amount-matched token; the regex gate prevents arbitrary words from
    # reaching this parser.
    numeric_value = float(
        value.translate(str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1"})).replace(",", "")
    )
    return int(numeric_value) if numeric_value.is_integer() else numeric_value


def _normalize_ingredient_unit(value: str) -> str:
    """Normalize common OCR unit variants.

    Args:
        value: OCR unit text.

    Returns:
        Normalized unit string.
    """
    stripped = value.strip()
    compact = re.sub(r"[\s.]+", "", stripped.casefold())
    if stripped in {"㎎", "밀리그램"} or compact == "mg":
        return "mg"
    if stripped in {"μg", "µg", "㎍"} or compact in {"mcg", "ug", "마이크로그램"}:
        return "ug"
    if compact in {"iu", "아이유"}:
        return "IU"
    if compact in {"cfu", "씨에프유"}:
        return "CFU"
    cfu_compound = re.fullmatch(
        rf"(?P<mag>{_CFU_MAGNITUDE})\s*(?:{_CFU_UNIT})", stripped, re.IGNORECASE
    )
    if cfu_compound is not None:
        magnitude = cfu_compound.group("mag")
        # Korean myriad counters keep their glyph; English magnitudes lower-case.
        magnitude = magnitude if re.search(r"[가-힣]", magnitude) else magnitude.casefold()
        return f"{magnitude} CFU"
    return stripped.casefold() if stripped != "%" else "%"


def _ingredient_candidate_key(candidate: dict[str, Any]) -> tuple[str, float | None, str | None]:
    """Return a stable dedupe key for ingredient candidates."""
    amount = candidate.get("amount")
    normalized_amount = float(amount) if isinstance(amount, int | float) else None
    unit = candidate.get("unit")
    return (
        _ingredient_name_key(str(candidate.get("display_name") or "")),
        normalized_amount,
        _normalize_ingredient_unit(str(unit)) if unit is not None else None,
    )


def _ingredient_candidate_name_keys(candidate: dict[str, Any]) -> set[str]:
    """Return display/original full name keys for candidate deduplication.

    Args:
        candidate: Ingredient candidate mapping.

    Returns:
        Non-empty normalized full names from both user-facing and OCR-original fields.
    """
    keys: set[str] = set()
    for field in ("display_name", "original_name"):
        name_key = _ingredient_name_key(str(candidate.get(field) or ""))
        if name_key:
            keys.add(name_key)
    return keys


def _ingredient_candidate_base_keys(candidate: dict[str, Any]) -> set[str]:
    """Return base-name keys (trailing form/source qualifier stripped) for a candidate.

    Used only by amount enrichment to match a name-only candidate carrying the full
    parenthetical form ("Zinc (zinc mono-L-methionine, aspartate)") with the plain OCR
    pattern name ("Zinc"). Kept separate from ``_ingredient_candidate_name_keys`` and
    the strict ``_ingredient_candidate_key`` so base-name collisions never widen the
    identity key or the add-new dedupe (which would drop a genuinely distinct
    same-base amount the LLM missed).

    Args:
        candidate: Ingredient candidate mapping.

    Returns:
        Non-empty base names from the user-facing and OCR-original fields.
    """
    keys: set[str] = set()
    for field in ("display_name", "original_name"):
        base_key = _ingredient_base_name_key(str(candidate.get(field) or ""))
        if base_key:
            keys.add(base_key)
    return keys


def _ingredient_name_key(value: str) -> str:
    """Return a normalized ingredient name key for comparison.

    NFC-normalizes first so that the same Korean ingredient name dedupes across
    sources even when one source emits decomposed (NFD) Hangul and another emits
    precomposed (NFC) — e.g. a 원재료명 declaration name vs the same name from the
    facts-table/amount-pattern path. Without this, a name-only declaration
    candidate could be appended as a duplicate of an amount-bearing candidate.
    """
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


# Trailing form/source qualifier appended to a nutrient name, e.g.
# "Zinc (zinc mono-L-methionine, aspartate)" or "Vitamin B6 (as pyridoxine HCl)".
# The leading base name is the canonical nutrient identity for match/dedupe.
_INGREDIENT_NAME_QUALIFIER_PATTERN = re.compile(r"\s*[(（【\[].*$")  # noqa: RUF001


def _ingredient_base_name_key(value: str) -> str:
    """Return the base ingredient name key with a trailing form qualifier removed.

    Strips a trailing parenthetical/bracketed qualifier (form or source) so the
    base nutrient name matches across sources — e.g. a name-only LLM candidate
    "Zinc (zinc mono-L-methionine, aspartate)" matches the amount-bearing OCR
    pattern candidate "Zinc". Returns "" when stripping would leave nothing (e.g.
    a leading-parenthesis fragment), so callers never add an empty key.
    """
    stripped = _INGREDIENT_NAME_QUALIFIER_PATTERN.sub("", value)
    return _ingredient_name_key(stripped)


def _is_excipient_name(value: str) -> bool:
    """Return whether a sanitized ingredient name is a known inactive excipient.

    Args:
        value: Sanitized ingredient display name.

    Returns:
        True only on an exact normalized match against the excipient allowlist,
        so genuine active nutrients are never dropped.
    """
    return _ingredient_name_key(value) in _EXCIPIENT_NAME_KEYS


def _list_of_mappings(value: Any) -> list[dict[str, Any]]:
    """Return dict items from a parser snapshot value."""
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _append_unique_string(value: Any, item: str) -> list[str]:
    """Append a bounded string to a list-shaped parser field once.

    Args:
        value: Existing parser field.
        item: String to append.

    Returns:
        Deduplicated list.
    """
    items = [entry for entry in value if isinstance(entry, str)] if isinstance(value, list) else []
    if item not in items:
        items.append(item)
    return items


def _normalize_ocr_provider(ocr_provider: str) -> str:
    """Normalize and validate OCR provider metadata.

    Args:
        ocr_provider: Raw OCR provider label.

    Returns:
        Trimmed provider label.

    Raises:
        SupplementParserInputError: If the provider label is invalid.
    """
    normalized = ocr_provider.strip()
    if not normalized:
        raise SupplementParserInputError("OCR provider is required.")
    if len(normalized) > OCR_PROVIDER_MAX_LENGTH:
        raise SupplementParserInputError("OCR provider exceeds the storage limit.")
    return normalized


def _normalize_confidence(ocr_confidence: float | None) -> Decimal | None:
    """Validate OCR confidence and convert it for database storage.

    Args:
        ocr_confidence: Optional OCR confidence value.

    Returns:
        Decimal confidence or None.

    Raises:
        SupplementParserInputError: If confidence is outside 0.0 to 1.0.
    """
    if ocr_confidence is None:
        return None
    if ocr_confidence < 0 or ocr_confidence > 1:
        raise SupplementParserInputError("OCR confidence must be between 0 and 1.")
    return Decimal(str(ocr_confidence))


def _build_parsed_snapshot(
    *,
    parse_result: SupplementStructuredParseResult,
    previous_snapshot: dict[str, Any],
    ocr_confidence: Decimal | None,
    ocr_provider: str,
    ocr_layout: LabelLayout | None,
    settings: Settings,
    ocr_text: str = "",
    retain_raw_ocr_text: bool = False,
) -> dict[str, Any]:
    """Build the sanitized JSON snapshot persisted for user confirmation.

    Args:
        parse_result: Validated structured parser result.
        previous_snapshot: Existing preview snapshot, used only to preserve intake metadata.
        ocr_confidence: Provider-level OCR confidence.
        ocr_provider: OCR-like provider that produced the parser input.
        ocr_layout: Optional deterministic layout parsed from OCR coordinates.
        settings: Runtime settings used for model and algorithm metadata.
        ocr_text: Normalized OCR text; retained at a top-level ``raw_ocr_text`` key
            only when ``retain_raw_ocr_text`` is True.
        retain_raw_ocr_text: Combined gate from the caller — the operator opt-in flag
            ``store_raw_ocr_text`` AND the user's ``RAW_OCR_TEXT_RETENTION`` consent.

    Returns:
        Sanitized parsed snapshot. Includes a top-level ``raw_ocr_text`` only when
        ``retain_raw_ocr_text`` is True; ``parser_metadata.raw_ocr_text_stored`` stays
        False so the V2/V3 snapshot invariant and legacy upcast guard hold.
    """
    low_confidence_fields = _build_low_confidence_fields(
        parse_result.low_confidence_fields,
        ocr_confidence,
    )
    layout_sections, layout_evidence_spans, layout_fallback_reason = _layout_context_to_preview(
        ocr_layout
    )
    label_sections = _merge_label_sections(parse_result.label_sections, layout_sections)
    evidence_spans = _merge_evidence_spans(parse_result.evidence_spans, layout_evidence_spans)
    missing_required_sections = _merge_missing_required_sections(
        parse_result.missing_required_sections,
        label_sections,
        intake_text=parse_result.intake_method.text,
        has_precautions=bool(parse_result.precautions),
    )
    snapshot: dict[str, Any] = {
        "parsed_product": parse_result.parsed_product.model_dump(exclude_none=True),
        "ingredient_candidates": [
            candidate.model_dump(exclude_none=True)
            for candidate in parse_result.ingredient_candidates
        ],
        "layout_available": bool(label_sections),
        "label_sections": [section.model_dump(exclude_none=True) for section in label_sections],
        "intake_method": parse_result.intake_method.model_dump(exclude_none=True),
        "precautions": [
            precaution.model_dump(exclude_none=True) for precaution in parse_result.precautions
        ],
        "functional_claims": [
            claim.model_dump(exclude_none=True) for claim in parse_result.functional_claims
        ],
        "evidence_spans": [span.model_dump(exclude_none=True) for span in evidence_spans],
        "missing_required_sections": missing_required_sections,
        "low_confidence_fields": low_confidence_fields,
        "parser_metadata": {
            "provider": SUPPLEMENT_PARSER_PROVIDER,
            "source": SUPPLEMENT_PARSER_SOURCE,
            "input_provider": ocr_provider,
            "model": settings.ollama_model,
            "algorithm_version": settings.supplement_parser_algorithm_version,
            "raw_ocr_text_stored": False,
            "raw_model_response_stored": False,
        },
    }
    if ocr_layout is not None:
        snapshot["parser_metadata"]["layout_provider"] = ocr_layout.provider
        snapshot["parser_metadata"]["layout_page_count"] = ocr_layout.page_count
        snapshot["parser_metadata"]["layout_warning_count"] = len(ocr_layout.warnings)
    if layout_fallback_reason is not None:
        snapshot["layout_fallback_reason"] = layout_fallback_reason
    intake = previous_snapshot.get("intake")
    if isinstance(intake, dict):
        snapshot["intake"] = intake
    # Operator opt-in (store_raw_ocr_text) AND per-user RAW_OCR_TEXT_RETENTION consent,
    # combined by the caller into retain_raw_ocr_text: retain the normalized OCR text at
    # a top-level key so the "OCR 텍스트 전체" view can show the source. Kept OUT of
    # parser_metadata so the V2/V3 snapshot privacy invariant (raw_ocr_text_stored
    # Literal[False]) and the legacy upcast guard stay intact.
    if retain_raw_ocr_text and ocr_text.strip():
        snapshot["raw_ocr_text"] = ocr_text
    return snapshot


def _layout_context_to_preview(
    ocr_layout: LabelLayout | None,
) -> tuple[list[SupplementPreviewLabelSection], list[SupplementPreviewEvidenceSpan], str | None]:
    """Convert deterministic OCR layout sections into bounded preview objects.

    Args:
        ocr_layout: Parsed provider-neutral label layout.

    Returns:
        Preview sections, evidence spans, and an optional fallback reason.
    """
    if ocr_layout is None:
        return [], [], None

    sections: list[SupplementPreviewLabelSection] = []
    evidence_spans: list[SupplementPreviewEvidenceSpan] = []
    for raw_index, section in enumerate(ocr_layout.sections, start=1):
        preview_type = LAYOUT_SECTION_TYPE_MAP.get(section.section_type)
        if preview_type is None:
            continue
        text_bundle = _section_text_bundle(section)
        sanitized_bundle = sanitize_preview_text(text_bundle, "layout_section.text_bundle").value
        if not sanitized_bundle:
            continue

        section_id = f"layout-section-{raw_index}"
        span_id = f"layout-span-{raw_index}"
        heading_text = sanitize_preview_text(
            section.anchor_text,
            "layout_section.heading_text",
        ).value
        confidence = _section_confidence(section)
        sections.append(
            SupplementPreviewLabelSection.model_validate(
                {
                    "section_id": section_id,
                    "section_type": preview_type,
                    "heading_text": heading_text,
                    "text_bundle": sanitized_bundle,
                    "confidence": confidence,
                    "requires_review": False,
                    "evidence_refs": [span_id],
                }
            )
        )
        evidence_excerpt = sanitize_preview_text(
            sanitized_bundle[:LAYOUT_EVIDENCE_EXCERPT_MAX_CHARS],
            "layout_section.evidence_excerpt",
        ).value
        if evidence_excerpt:
            evidence_spans.append(
                SupplementPreviewEvidenceSpan.model_validate(
                    {
                        "span_id": span_id,
                        "source_type": "ocr_layout",
                        "section_type": preview_type,
                        "text_excerpt": evidence_excerpt,
                        "page_index": _section_page_index(section),
                        "cell_ref": section_id,
                        "confidence": confidence,
                    }
                )
            )

    if sections:
        return sections, evidence_spans, None
    if ocr_layout.warnings:
        return [], [], ocr_layout.warnings[0]
    return [], [], None


def _section_text_bundle(section: LabelSection) -> str:
    """Build a bounded section text bundle from deterministic layout rows.

    Args:
        section: Parsed label section.

    Returns:
        Bounded section text assembled in visual row order.
    """
    rows: list[str] = []
    for row in section.rows:
        row_text = " | ".join(cell.text for cell in sorted(row, key=lambda item: item.column_index))
        if row_text.strip():
            rows.append(row_text.strip())
    return "\n".join(rows)[:LAYOUT_TEXT_BUNDLE_MAX_CHARS].strip()


def _section_page_index(section: LabelSection) -> int | None:
    """Return the first page index represented by a layout section."""
    if section.anchor_box is not None:
        return section.anchor_box.page_index
    for row in section.rows:
        if row:
            return row[0].bounding_box.page_index
    return None


def _section_confidence(section: LabelSection) -> float | None:
    """Return the average confidence across a deterministic layout section."""
    values = [
        cell.confidence for row in section.rows for cell in row if cell.confidence is not None
    ]
    if not values:
        return None
    return sum(values) / len(values)


def _merge_label_sections(
    parser_sections: list[SupplementPreviewLabelSection],
    layout_sections: list[SupplementPreviewLabelSection],
) -> list[SupplementPreviewLabelSection]:
    """Prefer deterministic layout sections and append non-duplicate parser sections."""
    if not layout_sections:
        return list(parser_sections)
    merged = list(layout_sections)
    seen_types = {section.section_type for section in merged}
    for section in parser_sections:
        if section.section_type in seen_types:
            continue
        merged.append(section)
        seen_types.add(section.section_type)
    return merged


def _merge_evidence_spans(
    parser_spans: list[SupplementPreviewEvidenceSpan],
    layout_spans: list[SupplementPreviewEvidenceSpan],
) -> list[SupplementPreviewEvidenceSpan]:
    """Merge parser and layout evidence by stable span id."""
    merged: list[SupplementPreviewEvidenceSpan] = []
    seen_ids: set[str] = set()
    for span in [*parser_spans, *layout_spans]:
        if span.span_id in seen_ids:
            continue
        merged.append(span)
        seen_ids.add(span.span_id)
    return merged


def _merge_missing_required_sections(
    parser_missing: list[SupplementMissingRequiredSection],
    label_sections: list[SupplementPreviewLabelSection],
    *,
    intake_text: str | None,
    has_precautions: bool,
) -> list[SupplementMissingRequiredSection]:
    """Remove missing-section markers proven present by parser or layout evidence."""
    present_types = {section.section_type for section in label_sections}
    if intake_text and intake_text.strip():
        present_types.add("intake_method")
    if has_precautions:
        present_types.add("precautions")
    if "allergen_warning" in present_types:
        present_types.add("precautions")

    normalized: list[SupplementMissingRequiredSection] = []
    seen: set[str] = set()
    for section in parser_missing:
        if _is_required_section_present(section, present_types):
            continue
        if section not in seen:
            normalized.append(section)
            seen.add(section)
    return normalized


def _is_required_section_present(
    section: SupplementMissingRequiredSection,
    present_types: set[str],
) -> bool:
    """Return whether a required section has supporting preview evidence."""
    if section == "supplement_facts":
        return bool({"supplement_facts", "nutrition_info", "ingredients"} & present_types)
    if section == "functional_info":
        return "functional_info" in present_types
    return section in present_types


def _build_low_confidence_fields(
    parser_fields: list[str],
    ocr_confidence: Decimal | None,
) -> list[str]:
    """Merge parser field warnings with OCR-level confidence review signals.

    Args:
        parser_fields: Field paths reported by the structured parser.
        ocr_confidence: Provider-level OCR confidence.

    Returns:
        Deduplicated field paths that require user review.
    """
    fields = list(parser_fields)
    if ocr_confidence is not None and ocr_confidence < OCR_LOW_CONFIDENCE_THRESHOLD:
        fields.append("ocr_text")

    normalized: list[str] = []
    seen: set[str] = set()
    for field in fields:
        stripped = field.strip()
        if not stripped or stripped in seen:
            continue
        normalized.append(stripped)
        seen.add(stripped)
    return normalized


def _build_warning_list(parser_warnings: list[str], ocr_provider: str) -> list[str]:
    """Merge parser warnings with the required user-confirmation warning.

    Args:
        parser_warnings: Safe parser-produced warning strings.
        ocr_provider: OCR-like provider that produced parser input.

    Returns:
        Deduplicated warning list.
    """
    warnings = [SUPPLEMENT_PARSER_CONFIRMATION_WARNING, *parser_warnings]
    if ocr_provider == OLLAMA_VISION_ASSIST_PROVIDER:
        warnings.append(SUPPLEMENT_IMAGE_ASSIST_WARNING)
    normalized: list[str] = []
    seen: set[str] = set()
    for warning in warnings:
        stripped = warning.strip()
        if not stripped or stripped in seen:
            continue
        normalized.append(stripped)
        seen.add(stripped)
    return normalized
