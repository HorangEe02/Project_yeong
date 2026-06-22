"""Collect redacted supplement OCR provider observations.

The collector is an explicit operator tool. It validates a consented fixture
manifest and writes provider observations without raw image bytes, raw OCR text,
provider payloads, credentials, or request headers. External providers only run
when their opt-in smoke-test environment variables are set.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Literal, cast

from PIL import Image, UnidentifiedImageError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.config import Settings  # noqa: E402
from src.llm.ollama import (  # noqa: E402
    OllamaClientError,
    OllamaConfigurationError,
    OllamaStructuredOutputError,
    OllamaSupplementParser,
)
from src.ocr.base import OCRAdapter, OCRError, OCRImageInput, OCRResult  # noqa: E402
from src.ocr.factory import (  # noqa: E402
    OCRConfigurationError,
    build_supplement_image_analysis_adapters_for_provider,
)
from src.ocr.providers.paddle import PaddleOCRAdapter  # noqa: E402
from src.parsing.layout_parser import parse_label_layout  # noqa: E402
from src.utils.text_metrics import language_segmented_error_rates  # noqa: E402

ProviderName = Literal["google_vision_document", "paddleocr_local", "clova_ocr"]
ObservationStatus = Literal["completed", "error", "not_run"]

SUPPORTED_PROVIDERS: tuple[ProviderName, ...] = (
    "google_vision_document",
    "paddleocr_local",
    "clova_ocr",
)
PROVIDER_OPT_IN_ENV: dict[ProviderName, str] = {
    "google_vision_document": "RUN_GOOGLE_VISION_SMOKE",
    "paddleocr_local": "RUN_PADDLEOCR_PROBE",
    "clova_ocr": "RUN_CLOVA_OCR_LIVE_SMOKE",
}
ALLOWED_IMAGE_PATH_ENV_VARS = frozenset(
    {
        "LEMON_OCR_FIXTURE_ROOT",
        "NAVER_TAMPERMONKEY_SOURCE_ROOT",
        "SUPPLEMENT_OCR_FIXTURE_ROOT",
    }
)
ENV_IMAGE_PATH_PATTERN = re.compile(r"^\$(?P<name>[A-Z][A-Z0-9_]*)(?:/(?P<path>.*))?$")
OPERATOR_ENV_ALLOWLIST = frozenset(
    {
        "ALLOW_EXTERNAL_OCR",
        "ENABLE_CLOVA_OCR",
        "ENABLE_LOCAL_OCR",
        "GOOGLE_CLOUD_API_KEY",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_VISION_AUTH_MODE",
        "GOOGLE_VISION_FEATURE",
        "GOOGLE_VISION_LANGUAGE_HINTS",
        "GOOGLE_VISION_LOCATION",
        "GOOGLE_VISION_MAX_RETRIES",
        "GOOGLE_VISION_TIMEOUT_SECONDS",
        "LOCAL_OCR_MODEL_PROFILE",
        "LOCAL_OCR_PREPROCESS_MODE",
        "OCR_PRIMARY_PROVIDER",
        "RUN_CLOVA_OCR_LIVE_SMOKE",
        "RUN_GOOGLE_VISION_SMOKE",
        "RUN_PADDLEOCR_PROBE",
    }
)
RAW_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "image_bytes",
        "ocr_text",
        "provider_payload",
        "raw_image",
        "raw_ocr_text",
        "raw_provider_payload",
        "request_headers",
        "service_key",
    }
)
ALLOWED_LICENSE_STATUS = frozenset({"public", "team_approved", "consented", "synthetic"})
ALLOWED_CONSENT_STATUS = frozenset({"not_required", "team_approved", "consented"})
SHA256_HEX_LENGTH = 64
MIN_QUOTED_DOTENV_VALUE_CHARS = 2
AUTO_EXPECTED_SOURCE = "google_vision_auto_seed"
AUTO_EXPECTED_VERIFICATION_STATUS = "provisional"
AUTO_EXPECTED_WARNING = "auto_expected_requires_human_verification"
AUTO_EXPECTED_NO_INGREDIENTS_WARNING = "auto_expected_no_ingredient_candidates"
AUTO_EXPECTED_MAX_INGREDIENTS = 40
AUTO_EXPECTED_MIN_PRODUCT_NAME_CHARS = 3
AUTO_EXPECTED_MAX_PRODUCT_NAME_CHARS = 160
AUTO_EXPECTED_MIN_INGREDIENT_NAME_CHARS = 2
AUTO_EXPECTED_MAX_INGREDIENT_NAME_CHARS = 80
TRAILING_INGREDIENT_PUNCTUATION = " -_/.,:\uff1a|·•"
INGREDIENT_AMOUNT_PATTERN = re.compile(
    r"(?P<name>[A-Za-z가-힣][A-Za-z가-힣0-9\s()/+\-.,]{1,80}?)"
    r"\s*(?P<amount>\d+(?:[,.]\d+)?)\s*"
    r"(?P<unit>mg|g|mcg|μg|ug|㎍|iu|IU|%)\b"
)
EXPECTED_NAME_SEPARATOR_PATTERN = re.compile(r"\s*(?:,|\uff0c|\u3001)\s*")
INGREDIENT_MATCH_SEPARATOR_PATTERN = re.compile(r"[^0-9A-Za-z가-힣]+")
INGREDIENT_PARENTHESES_PATTERN = re.compile(r"\((?P<inner>[^)]{2,80})\)")
KOREAN_INGREDIENT_DESCRIPTOR_PREFIXES = (
    "초임계",
    "검은",
    "블랙",
    "유기농",
    "식물성",
    "저분자",
)
ENGLISH_INGREDIENT_DESCRIPTOR_PREFIXES = (
    "extra virgin ",
    "natural ",
    "mixed ",
)
PACKAGING_QUANTITY_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Reject auto-seed contaminants observed in chronic fixtures: "g (", "g X30포(".
    re.compile(
        r"^(?:g|mg|kg|ml|l)\s*(?:x\s*)?\d*\s*(?:포|정|캡슐|개입)?\s*\(?$",
        re.IGNORECASE,
    ),
    # Reject tablet-count fragments such as "정(" and "정x 3개입(".
    re.compile(r"^정\s*(?:x\s*)?\d*\s*(?:개입)?\s*\(?$", re.IGNORECASE),
    re.compile(r"^\d+\s*(?:정|포|캡슐|개입)\s*\(?$", re.IGNORECASE),
)
PII_CANDIDATE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "email_candidate",
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    ),
    (
        "phone_candidate",
        re.compile(r"\b(?:01[016789]|0\d{1,2})[-.\s]?\d{3,4}[-.\s]?\d{4}\b"),
    ),
    (
        "order_number_candidate",
        re.compile(r"(?:주문\s*번호|주문번호|배송\s*번호|운송장)\D{0,12}\d{6,}"),
    ),
    (
        "address_candidate",
        re.compile(r"(?:주소|배송지|수령지|[가-힣]{2,}(?:로|길)\s*\d{1,4})"),
    ),
)
LLM_PARSE_RETRY_DELAYS_SECONDS = (0.25, 1.0)
MAX_TEXT_EXTRACTION_METRIC_CHARS = 12000


@dataclass(frozen=True)
class FixtureCase:
    """One consented supplement OCR fixture.

    Attributes:
        fixture_id: Stable fixture identifier.
        image_path: Path to the committed non-sensitive image, relative to manifest.
        expected: Redacted expected field summary.
        manifest_row: Original allowlisted manifest row.
    """

    fixture_id: str
    image_path: Path
    expected: dict[str, object]
    manifest_row: dict[str, object]

    def with_expected(self, expected: dict[str, object]) -> FixtureCase:
        """Return a copy with a different expected field summary.

        Args:
            expected: Replacement expected field summary.

        Returns:
            Fixture copy carrying the new expected object.
        """
        return FixtureCase(
            fixture_id=self.fixture_id,
            image_path=self.image_path,
            expected=expected,
            manifest_row=self.manifest_row,
        )


@dataclass(frozen=True)
class ProviderObservationResult:
    """One provider observation with transient OCR result for in-memory seeding.

    Attributes:
        row: Redacted observation row.
        ocr_result: OCR result kept only in process memory.
    """

    row: dict[str, object]
    ocr_result: OCRResult | None = None


@dataclass(frozen=True)
class CollectionResult:
    """Redacted collection output and optional auto-expected manifest.

    Attributes:
        observations: Redacted observation rows.
        auto_expected_manifest: Optional manifest seeded from a live provider.
    """

    observations: list[dict[str, object]]
    auto_expected_manifest: dict[str, object] | None = None


def main() -> None:
    """Run the redacted observation collector from CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help=(
            "Optional operator dotenv file. Only OCR allowlisted keys are loaded, "
            "and existing process environment values take precedence."
        ),
    )
    parser.add_argument(
        "--providers",
        default=",".join(SUPPORTED_PROVIDERS),
        help="Comma-separated provider names to observe.",
    )
    parser.add_argument(
        "--auto-expected-provider",
        choices=SUPPORTED_PROVIDERS,
        default=None,
        help=(
            "Provider used to seed provisional expected fields in memory. "
            "Use google_vision_document for live seed baselines."
        ),
    )
    parser.add_argument(
        "--llm-parse",
        action="store_true",
        help=(
            "Opt-in: send each non-empty OCR text to the local OllamaSupplementParser "
            "and record redacted llm_parsed_ingredients on each completed observation. "
            "Raw OCR text and raw model responses are never written; only structured "
            "ingredient display_name/original_name/amount/unit/confidence fields are stored. "
            "Review rows pending PII screening are skipped before LLM handoff."
        ),
    )
    parser.add_argument(
        "--auto-expected-manifest",
        type=Path,
        default=None,
        help="Optional output manifest with provisional provider-seeded expected fields.",
    )
    args = parser.parse_args()
    if args.auto_expected_manifest is not None and args.auto_expected_provider is None:
        parser.error("--auto-expected-manifest requires --auto-expected-provider")

    collection = asyncio.run(
        collect_observations_with_auto_expected(
            manifest_path=args.manifest,
            providers=_parse_providers(args.providers),
            auto_expected_provider=cast(ProviderName | None, args.auto_expected_provider),
            auto_expected_manifest_path=args.auto_expected_manifest,
            env_file=args.env_file or _default_operator_env_file(),
            llm_parse_enabled=bool(args.llm_parse),
        )
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / "supplement-ocr-observations.jsonl"
    output_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in collection.observations),
        encoding="utf-8",
    )
    summary: dict[str, object] = {
        "observation_count": len(collection.observations),
        "output": str(output_path),
    }
    if collection.auto_expected_manifest is not None and args.auto_expected_manifest is not None:
        args.auto_expected_manifest.parent.mkdir(parents=True, exist_ok=True)
        args.auto_expected_manifest.write_text(
            json.dumps(collection.auto_expected_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        summary["auto_expected_manifest"] = str(args.auto_expected_manifest)
    print(json.dumps(summary, ensure_ascii=False))


async def collect_observations(
    *,
    manifest_path: Path,
    providers: tuple[ProviderName, ...],
) -> list[dict[str, object]]:
    """Collect redacted observations for all fixture/provider pairs.

    Args:
        manifest_path: JSON or JSONL fixture manifest path.
        providers: Provider ids to observe.

    Returns:
        Redacted observation dictionaries.
    """
    return (
        await collect_observations_with_auto_expected(
            manifest_path=manifest_path,
            providers=providers,
        )
    ).observations


async def collect_observations_with_auto_expected(
    *,
    manifest_path: Path,
    providers: tuple[ProviderName, ...],
    auto_expected_provider: ProviderName | None = None,
    auto_expected_manifest_path: Path | None = None,
    env_file: Path | None = None,
    llm_parse_enabled: bool = False,
    llm_parser: OllamaSupplementParser | None = None,
) -> CollectionResult:
    """Collect observations and optionally seed provisional expected fields.

    Args:
        manifest_path: JSON or JSONL fixture manifest path.
        providers: Provider ids to observe.
        auto_expected_provider: Provider id whose OCR text seeds expected fields.
        auto_expected_manifest_path: Destination path used to calculate image paths
            relative to the seeded manifest. The file is written by ``main``.
        env_file: Optional operator dotenv file for live OCR opt-in settings.

    Returns:
        Collection result containing redacted observations and optional manifest.
    """
    fixtures = _read_fixture_manifest(manifest_path, providers=providers)
    operator_env = _load_operator_env_file(env_file)
    with _temporary_operator_env(operator_env):
        settings = (
            Settings(_env_file=env_file) if env_file is not None else Settings(_env_file=None)
        )
        active_llm_parser: OllamaSupplementParser | None = llm_parser
        if llm_parse_enabled and active_llm_parser is None:
            active_llm_parser = OllamaSupplementParser(settings)
        observations: list[dict[str, object]] = []
        seeded_expected: dict[str, dict[str, object]] = {}
        for fixture in fixtures:
            active_fixture = fixture
            for provider in providers:
                observed = await _observe_provider(
                    active_fixture,
                    provider,
                    settings,
                    llm_parser=active_llm_parser if llm_parse_enabled else None,
                )
                observations.append(observed.row)
                if provider == auto_expected_provider and observed.ocr_result is not None:
                    expected = _auto_expected_from_result(
                        fixture=fixture,
                        provider=provider,
                        result=observed.ocr_result,
                    )
                    seeded_expected[fixture.fixture_id] = expected
                    active_fixture = fixture.with_expected(expected)
        auto_manifest = None
        if auto_expected_provider is not None:
            auto_manifest = _build_auto_expected_manifest(
                fixtures=fixtures,
                seeded_expected=seeded_expected,
                auto_expected_provider=auto_expected_provider,
                output_manifest_path=auto_expected_manifest_path or manifest_path,
            )
        return CollectionResult(observations=observations, auto_expected_manifest=auto_manifest)


async def _observe_provider(
    fixture: FixtureCase,
    provider: ProviderName,
    settings: Settings,
    *,
    llm_parser: OllamaSupplementParser | None = None,
) -> ProviderObservationResult:
    """Collect one provider observation or a safe not-run/error record.

    Args:
        fixture: Fixture case.
        provider: Provider id.
        settings: Runtime settings read from the operator environment.

    Returns:
        Redacted observation row and transient OCR result when completed.
    """
    opt_in_env = PROVIDER_OPT_IN_ENV[provider]
    if os.getenv(opt_in_env) != "1":
        return ProviderObservationResult(
            row=_observation(
                fixture_id=fixture.fixture_id,
                provider=provider,
                status="not_run",
                error_code=f"opt_in_env_missing:{opt_in_env}",
            )
        )
    try:
        adapter = _build_provider_adapter(provider, settings)
        image = _load_image_input(fixture.image_path)
        start = time.perf_counter()
        result = await adapter.extract_text(image)
        latency_ms = int((time.perf_counter() - start) * 1000)
    except Exception as exc:
        return ProviderObservationResult(
            row=_observation(
                fixture_id=fixture.fixture_id,
                provider=provider,
                status="error",
                error_code=_safe_error_code(exc),
            )
        )
    row = _completed_observation(
        fixture=fixture,
        provider=provider,
        result=result,
        latency_ms=latency_ms,
    )
    if llm_parser is not None and row.get("text_non_empty"):
        if _requires_local_pii_screening(fixture):
            row["llm_parse_status"] = "skipped_pii_screening_required"
            return ProviderObservationResult(row=row, ocr_result=result)
        await _attach_llm_parse(row=row, ocr_result=result, llm_parser=llm_parser)
    _attach_text_extraction_metrics(row=row, ocr_result=result, expected=fixture.expected)
    _attach_language_metrics(row=row, ocr_result=result, expected=fixture.expected)
    return ProviderObservationResult(row=row, ocr_result=result)


def _build_provider_adapter(provider: ProviderName, settings: Settings) -> OCRAdapter:
    """Build the requested provider adapter.

    Args:
        provider: Provider id.
        settings: Runtime settings.

    Returns:
        OCR adapter.

    Raises:
        OCRConfigurationError: If settings do not permit the provider.
    """
    if provider == "google_vision_document":
        adapter = build_supplement_image_analysis_adapters_for_provider(
            settings,
            "google_vision",
        ).ocr
        if adapter is None:
            raise OCRConfigurationError("Google Vision adapter is not configured.")
        return adapter
    if provider == "paddleocr_local":
        if not settings.enable_local_ocr:
            raise OCRConfigurationError("ENABLE_LOCAL_OCR=true is required for PaddleOCR.")
        return PaddleOCRAdapter(settings)
    if provider == "clova_ocr":
        adapter = build_supplement_image_analysis_adapters_for_provider(
            settings,
            "clova",
        ).ocr
        if adapter is None:
            raise OCRConfigurationError("CLOVA adapter is not configured.")
        return adapter
    raise OCRConfigurationError(f"Unsupported provider: {provider}")


async def _attach_llm_parse(
    *,
    row: dict[str, object],
    ocr_result: OCRResult,
    llm_parser: OllamaSupplementParser,
    retry_delays_seconds: Sequence[float] = LLM_PARSE_RETRY_DELAYS_SECONDS,
) -> None:
    """Run the local LLM parser on OCR text and attach a redacted ingredient list.

    Args:
        row: Completed observation row to mutate in place.
        ocr_result: PaddleOCR/CLOVA/Google Vision result with in-memory text.
        llm_parser: Local OllamaSupplementParser instance.
        retry_delays_seconds: Bounded retry delays for transient local Ollama
            transport failures.

    Notes:
        Raw OCR text and raw Ollama responses are never persisted. Only the
        structured ingredient display_name/original_name/amount/unit/confidence and the
        ingredient_count are written to ``row``. Failure modes and retry counts
        are recorded as safe bounded tokens/integers only.
    """
    text = (ocr_result.text or "").strip()
    if not text:
        row["llm_parse_status"] = "skipped_empty_text"
        return
    retry_delays = tuple(max(0.0, float(delay)) for delay in retry_delays_seconds)
    attempts = 0
    while True:
        attempts += 1
        try:
            parse_result = await llm_parser.parse_supplement_ocr_text(text)
            break
        except OllamaConfigurationError:
            _attach_llm_parse_error(
                row=row,
                error_code="ollama_configuration",
                attempts=attempts,
            )
            return
        except OllamaStructuredOutputError:
            _attach_llm_parse_error(
                row=row,
                error_code="ollama_structured_output",
                attempts=attempts,
            )
            return
        except OllamaClientError:
            if attempts <= len(retry_delays):
                await asyncio.sleep(retry_delays[attempts - 1])
                continue
            _attach_llm_parse_error(
                row=row,
                error_code="ollama_client",
                attempts=attempts,
            )
            return
        except Exception as exc:  # pragma: no cover - defensive
            _attach_llm_parse_error(
                row=row,
                error_code=f"unexpected:{type(exc).__name__}",
                attempts=attempts,
            )
            return

    ingredients: list[dict[str, object]] = []
    for ingredient in parse_result.ingredient_candidates:
        ingredients.append(
            {
                "display_name": ingredient.display_name,
                "original_name": ingredient.original_name,
                "nutrient_code": ingredient.nutrient_code,
                "amount": ingredient.amount,
                "unit": ingredient.unit,
                "confidence": ingredient.confidence,
                "source": ingredient.source,
            }
        )
    row["llm_parse_status"] = "completed"
    row["llm_parse_attempt_count"] = attempts
    if attempts > 1:
        row["llm_parse_retry_count"] = attempts - 1
    row["llm_parsed_ingredients"] = ingredients
    row["llm_parsed_ingredient_count"] = len(ingredients)
    if parse_result.parsed_product.product_name:
        row["llm_parsed_product_name_present"] = True
    if parse_result.parsed_product.serving_size:
        row["llm_parsed_serving_size_text_present"] = True


def _attach_llm_parse_error(
    *,
    row: dict[str, object],
    error_code: str,
    attempts: int,
) -> None:
    """Attach a redacted local LLM parse error summary.

    Args:
        row: Observation row to mutate in place.
        error_code: Bounded parser error code.
        attempts: Number of parser attempts performed.
    """
    row["llm_parse_status"] = "error"
    row["llm_parse_error_code"] = error_code
    row["llm_parse_attempt_count"] = attempts
    if attempts > 1:
        row["llm_parse_retry_count"] = attempts - 1


def _build_reference_text(expected: dict[str, object]) -> str:
    """Concatenate expected ingredient display strings into a reference string.

    Used only as the comparison reference for CER/WER calculation. Returns an
    empty string when no expected ingredients are present, in which case the
    caller should skip metric attachment.

    Args:
        expected: Redacted expected field summary from the fixture manifest.

    Returns:
        Space-joined reference text suitable for language-segmented metrics.
    """
    parts: list[str] = []
    for ingredient in _expected_ingredients(expected):
        for name in _expected_ingredient_names(ingredient):
            parts.append(name)
        amount = ingredient.get("amount")
        if amount is not None:
            parts.append(str(amount))
        unit = ingredient.get("unit")
        if isinstance(unit, str) and unit:
            parts.append(unit)
    return " ".join(parts)


def _attach_language_metrics(
    *,
    row: dict[str, object],
    ocr_result: OCRResult,
    expected: dict[str, object],
) -> None:
    """Attach Korean/English segmented CER/WER to an observation row.

    Skipped silently when the fixture has no expected ingredients (no
    comparison reference available). Raw OCR text is not persisted; only the
    rounded numeric metrics are written to the row.

    Args:
        row: Observation row to mutate in place.
        ocr_result: PaddleOCR/CLOVA/Google Vision result with in-memory text.
        expected: Redacted expected field summary from the fixture manifest.
    """
    reference_text = _build_reference_text(expected)
    if not reference_text:
        return
    hypothesis = (ocr_result.text or "").strip()
    rates = language_segmented_error_rates(hypothesis=hypothesis, reference=reference_text)
    row["cer_ko"] = round(rates["cer_ko"], 4)
    row["cer_en"] = round(rates["cer_en"], 4)
    row["wer_ko"] = round(rates["wer_ko"], 4)
    row["wer_en"] = round(rates["wer_en"], 4)


def _attach_text_extraction_metrics(
    *,
    row: dict[str, object],
    ocr_result: OCRResult,
    expected: dict[str, object],
) -> None:
    """Attach normalized text precision/recall/F1 without storing OCR text.

    Args:
        row: Observation row to mutate in place.
        ocr_result: Provider OCR result whose text is held only in memory.
        expected: Human-reviewed expected fields from the fixture manifest.
    """
    reference_text, reference_source = _expected_text_metric_reference(expected)
    if not reference_text:
        return
    metrics = _normalized_text_extraction_metrics(
        reference=reference_text,
        hypothesis=(ocr_result.text or "").strip(),
    )
    if metrics is None:
        row.setdefault("warning_codes", [])
        warning_codes = row["warning_codes"]
        if isinstance(warning_codes, list):
            warning_codes.append("text_metric_reference_too_large")
        return
    row["metric_source"] = "in_memory_provider_result"
    row["text_metric_reference_source"] = reference_source
    row["matched_char_count"] = metrics["matched_char_count"]
    row["reference_char_count"] = metrics["reference_char_count"]
    row["hypothesis_char_count"] = metrics["hypothesis_char_count"]
    row["normalized_text_precision"] = metrics["normalized_text_precision"]
    row["normalized_text_recall"] = metrics["normalized_text_recall"]
    row["normalized_text_f1"] = metrics["normalized_text_f1"]


def _expected_text_metric_reference(expected: dict[str, object]) -> tuple[str | None, str]:
    """Return text reference for extraction metrics.

    Args:
        expected: Expected fixture object.

    Returns:
        Reference text and source label.
    """
    for key in ("text", "full_text", "normalized_text", "ground_truth_text"):
        value = expected.get(key)
        if isinstance(value, str) and value.strip():
            return value, f"expected.{key}"
    structured_text = _expected_structured_metric_text(expected)
    if structured_text:
        return structured_text, "expected.structured_sections"
    return None, "missing"


def _expected_structured_metric_text(expected: dict[str, object]) -> str | None:
    """Return structured expected fields as a text reference.

    Args:
        expected: Expected fixture object.

    Returns:
        Space-joined structured text or None.
    """
    parts: list[str] = []
    _append_metric_text(parts, expected.get("product_name"))
    _append_metric_text(parts, expected.get("manufacturer"))
    for ingredient in _expected_ingredients(expected):
        for name in _expected_ingredient_names(ingredient):
            _append_metric_text(parts, name)
        _append_metric_text(parts, ingredient.get("amount"))
        _append_metric_text(parts, ingredient.get("unit"))
    intake_method = expected.get("intake_method")
    if isinstance(intake_method, dict):
        _append_metric_text(parts, intake_method.get("text"))
    else:
        _append_metric_text(parts, intake_method)
    for key in ("precautions", "allergen_warnings", "functional_claims", "label_sections"):
        value = expected.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, dict):
                _append_metric_text(parts, item.get("text"))
                _append_metric_text(parts, item.get("section_type"))
            else:
                _append_metric_text(parts, item)
    return " ".join(parts) if parts else None


def _append_metric_text(parts: list[str], value: object) -> None:
    """Append one scalar expected value to the metric reference.

    Args:
        parts: Mutable text part list.
        value: Candidate scalar value.
    """
    if isinstance(value, str) and value.strip():
        parts.append(value.strip())
    elif isinstance(value, int | float) and not isinstance(value, bool):
        parts.append(str(value))


def _normalized_text_extraction_metrics(
    *,
    reference: str,
    hypothesis: str,
) -> dict[str, object] | None:
    """Return normalized character precision, recall, and F1.

    Args:
        reference: Human-reviewed reference text.
        hypothesis: Provider OCR text.

    Returns:
        Numeric metrics, or None when exact scoring is intentionally skipped.
    """
    reference_chars = _normalize_text_for_metric(reference)
    hypothesis_chars = _normalize_text_for_metric(hypothesis)
    if not reference_chars:
        return None
    if (
        len(reference_chars) > MAX_TEXT_EXTRACTION_METRIC_CHARS
        or len(hypothesis_chars) > MAX_TEXT_EXTRACTION_METRIC_CHARS
    ):
        return None
    matched = _lcs_length(reference_chars, hypothesis_chars)
    precision = _metric_rate(matched, len(hypothesis_chars))
    recall = _metric_rate(matched, len(reference_chars))
    f1 = _metric_f1(precision=precision, recall=recall)
    return {
        "matched_char_count": matched,
        "reference_char_count": len(reference_chars),
        "hypothesis_char_count": len(hypothesis_chars),
        "normalized_text_precision": _metric_float(precision),
        "normalized_text_recall": _metric_float(recall),
        "normalized_text_f1": _metric_float(f1),
    }


def _normalize_text_for_metric(value: str) -> str:
    """Normalize OCR text for character-level extraction scoring.

    Args:
        value: Raw text kept only in memory.

    Returns:
        Lowercase NFKC letters and numbers.
    """
    normalized = unicodedata.normalize("NFKC", value).lower()
    return "".join(char for char in normalized if char.isalnum())


def _lcs_length(reference: str, hypothesis: str) -> int:
    """Return exact longest common subsequence length.

    Args:
        reference: Normalized reference string.
        hypothesis: Normalized OCR hypothesis string.

    Returns:
        LCS character count.
    """
    if not reference or not hypothesis:
        return 0
    previous = [0] * (len(hypothesis) + 1)
    for reference_char in reference:
        current = [0]
        diagonal = 0
        for index, hypothesis_char in enumerate(hypothesis, 1):
            above = previous[index]
            left = current[index - 1]
            value = diagonal + 1 if reference_char == hypothesis_char else max(above, left)
            current.append(value)
            diagonal = above
        previous = current
    return previous[-1]


def _metric_rate(numerator: int, denominator: int) -> Decimal:
    """Return a bounded metric rate.

    Args:
        numerator: Matched count.
        denominator: Denominator count.

    Returns:
        Decimal rate.
    """
    if denominator <= 0:
        return Decimal("0")
    return Decimal(numerator) / Decimal(denominator)


def _metric_f1(*, precision: Decimal, recall: Decimal) -> Decimal:
    """Return harmonic mean of precision and recall.

    Args:
        precision: Precision rate.
        recall: Recall rate.

    Returns:
        F1 rate.
    """
    if precision + recall == 0:
        return Decimal("0")
    return (Decimal("2") * precision * recall) / (precision + recall)


def _metric_float(value: Decimal) -> float:
    """Return a stable four-decimal metric value.

    Args:
        value: Decimal metric.

    Returns:
        Rounded float.
    """
    return float(value.quantize(Decimal("0.0001")))


def _completed_observation(
    *,
    fixture: FixtureCase,
    provider: ProviderName,
    result: OCRResult,
    latency_ms: int,
) -> dict[str, object]:
    """Build a redacted completed observation.

    Args:
        fixture: Fixture case.
        provider: Provider id.
        result: OCR result.
        latency_ms: Provider call latency in milliseconds.

    Returns:
        Redacted observation row.
    """
    normalized_text = _normalize_text(result.text)
    parsed_ingredients = _matched_expected_ingredients(normalized_text, fixture.expected)
    layout = parse_label_layout(result) if result.pages else None
    evidence_grounded = _parsed_values_grounded(normalized_text, parsed_ingredients)
    warning_codes: list[str] = []
    layout_available = bool(layout and layout.sections)
    if not layout_available:
        warning_codes.append("layout_unavailable")
    pii_screening_required = _requires_local_pii_screening(fixture)
    pii_candidate_flags = _pii_candidate_flags(result.text) if pii_screening_required else []
    if pii_screening_required:
        warning_codes.append("review_pii_screening_required")
    if pii_candidate_flags:
        warning_codes.append("pii_candidate_detected")
    row = _observation(
        fixture_id=fixture.fixture_id,
        provider=provider,
        status="completed",
        latency_ms=latency_ms,
        text_non_empty=bool(normalized_text),
        text_hash=(
            hashlib.sha256(normalized_text.encode("utf-8")).hexdigest() if normalized_text else None
        ),
        char_count=len(normalized_text),
        layout_available=layout_available,
        parser_success=(
            bool(parsed_ingredients)
            if _expected_ingredients(fixture.expected)
            else bool(normalized_text)
        ),
        parsed_ingredients=parsed_ingredients,
        evidence_grounded=evidence_grounded,
        warning_codes=warning_codes,
    )
    if pii_screening_required:
        row["pii_screening_status"] = "completed_local_screening"
        row["pii_candidate_flags"] = pii_candidate_flags
    return row


def _observation(
    *,
    fixture_id: str,
    provider: ProviderName,
    status: ObservationStatus,
    error_code: str | None = None,
    latency_ms: int | None = None,
    text_non_empty: bool = False,
    text_hash: str | None = None,
    char_count: int = 0,
    layout_available: bool = False,
    parser_success: bool = False,
    parsed_ingredients: list[dict[str, object]] | None = None,
    evidence_grounded: bool = False,
    warning_codes: list[str] | None = None,
) -> dict[str, object]:
    """Build one redacted observation record.

    Args:
        fixture_id: Fixture id.
        provider: Provider id.
        status: Observation status.
        error_code: Optional safe error code.
        latency_ms: Optional latency in milliseconds.
        text_non_empty: Whether OCR text was non-empty.
        text_hash: SHA-256 hash of normalized OCR text, never the text itself.
        char_count: Normalized OCR character count.
        layout_available: Whether provider layout metadata was usable.
        parser_success: Whether expected fields were recoverable from OCR text.
        parsed_ingredients: Redacted parsed ingredient summary.
        evidence_grounded: Whether parsed values are visible in OCR text.
        warning_codes: Safe warning codes.

    Returns:
        Observation row.
    """
    row: dict[str, object] = {
        "fixture_id": fixture_id,
        "provider": provider,
        "status": status,
        "text_non_empty": text_non_empty,
        "char_count": char_count,
        "layout_available": layout_available,
        "parser_success": parser_success,
        "parsed_ingredients": parsed_ingredients or [],
        "evidence_grounded": evidence_grounded,
        "warning_codes": warning_codes or [],
    }
    if text_hash is not None:
        row["text_hash"] = text_hash
    if latency_ms is not None:
        row["latency_ms"] = latency_ms
    if error_code is not None:
        row["error_code"] = error_code
    return row


def _default_operator_env_file() -> Path | None:
    """Return the default backend dotenv file when present.

    Returns:
        Backend-level dotenv path or None.
    """
    env_file = BACKEND_ROOT / ".env"
    return env_file if env_file.exists() else None


def _load_operator_env_file(env_file: Path | None) -> dict[str, str]:
    """Read allowlisted OCR operator env vars without leaking secret values.

    Existing process environment values take precedence over dotenv entries so
    CI or shell-level overrides remain authoritative.

    Args:
        env_file: Optional dotenv path.

    Returns:
        Allowlisted dotenv values to apply temporarily.
    """
    if env_file is None:
        return {}
    resolved = env_file.expanduser().resolve()
    if not resolved.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in resolved.read_text(encoding="utf-8").splitlines():
        parsed = _parse_dotenv_assignment(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        if not value or key not in OPERATOR_ENV_ALLOWLIST or key in os.environ:
            continue
        values[key] = value
    return values


@contextmanager
def _temporary_operator_env(values: dict[str, str]) -> Iterator[None]:
    """Temporarily expose operator dotenv values to provider opt-in checks.

    Args:
        values: Environment values returned by ``_load_operator_env_file``.

    Yields:
        None while the temporary environment overlay is active.
    """
    applied_keys: list[str] = []
    for key, value in values.items():
        if key in os.environ:
            continue
        os.environ[key] = value
        applied_keys.append(key)
    try:
        yield
    finally:
        for key in applied_keys:
            os.environ.pop(key, None)


def _parse_dotenv_assignment(raw_line: str) -> tuple[str, str] | None:
    """Parse one simple dotenv assignment.

    Args:
        raw_line: Raw dotenv line.

    Returns:
        Key and value, or None for comments/unsupported lines.
    """
    stripped = raw_line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None
    return key, _strip_dotenv_value(value.strip())


def _strip_dotenv_value(value: str) -> str:
    """Strip quotes and inline comments from a dotenv value.

    Args:
        value: Raw dotenv value.

    Returns:
        Parsed value.
    """
    if (
        len(value) >= MIN_QUOTED_DOTENV_VALUE_CHARS
        and value[0] == value[-1]
        and value[0] in {'"', "'"}
    ):
        return value[1:-1]
    return value.split(" #", 1)[0].strip()


def _auto_expected_from_result(
    *,
    fixture: FixtureCase,
    provider: ProviderName,
    result: OCRResult,
) -> dict[str, object]:
    """Build a provisional expected summary from one live OCR result.

    The generated object contains only structured candidates and hashes/counts.
    It intentionally does not include raw OCR text or provider payloads.

    Args:
        fixture: Source fixture.
        provider: Provider used to seed the expected summary.
        result: OCR result kept only in memory.

    Returns:
        Provisional expected object for agreement analysis.
    """
    normalized_text = _normalize_text(result.text)
    ingredients = _extract_ingredient_candidates(result.text)
    warnings = [AUTO_EXPECTED_WARNING]
    if not ingredients:
        warnings.append(AUTO_EXPECTED_NO_INGREDIENTS_WARNING)
    expected: dict[str, object] = {
        "expected_source": AUTO_EXPECTED_SOURCE,
        "verification_status": AUTO_EXPECTED_VERIFICATION_STATUS,
        "seed_provider": provider,
        "seed_fixture_id": fixture.fixture_id,
        "seed_text_hash": (
            hashlib.sha256(normalized_text.encode("utf-8")).hexdigest() if normalized_text else None
        ),
        "seed_char_count": len(normalized_text),
        "product_name": _extract_product_name_candidate(result.text),
        "ingredients": ingredients,
        "warnings": warnings,
    }
    return expected


def _build_auto_expected_manifest(
    *,
    fixtures: list[FixtureCase],
    seeded_expected: dict[str, dict[str, object]],
    auto_expected_provider: ProviderName,
    output_manifest_path: Path,
) -> dict[str, object]:
    """Build a manifest with provisional provider-seeded expected fields.

    Args:
        fixtures: Original fixture cases.
        seeded_expected: Expected objects keyed by fixture id.
        auto_expected_provider: Provider selected as the seed source.
        output_manifest_path: Manifest path used for relative image paths.

    Returns:
        JSON-serializable manifest object.
    """
    output_parent = output_manifest_path.parent.resolve()
    cases: list[dict[str, object]] = []
    for fixture in fixtures:
        row = dict(fixture.manifest_row)
        row["image_path"] = os.path.relpath(fixture.image_path, output_parent)
        row["expected"] = seeded_expected.get(
            fixture.fixture_id,
            {
                "expected_source": f"{auto_expected_provider}_auto_seed_not_completed",
                "verification_status": AUTO_EXPECTED_VERIFICATION_STATUS,
                "seed_provider": auto_expected_provider,
                "ingredients": [],
                "warnings": ["auto_expected_provider_not_completed"],
            },
        )
        cases.append(row)
    return {
        "version": "supplement-ocr-live-google-seed-v1",
        "expected_policy": "google_vision_auto_seed_provisional",
        "seed_provider": auto_expected_provider,
        "full_text_artifact_stored": False,
        "provider_artifact_stored": False,
        "image_bytes_in_manifest": False,
        "cases": cases,
    }


def _extract_ingredient_candidates(ocr_text: str) -> list[dict[str, object]]:
    """Extract bounded ingredient candidates from OCR text.

    Args:
        ocr_text: Raw OCR text kept only in process memory.

    Returns:
        Structured ingredient candidates safe for provisional expected snapshots.
    """
    ingredients: list[dict[str, object]] = []
    seen: set[tuple[str, object, str]] = set()
    for line in _ocr_lines(ocr_text):
        for match in INGREDIENT_AMOUNT_PATTERN.finditer(line):
            name = _clean_ingredient_name(match.group("name"))
            if not name:
                continue
            amount = _parse_amount(match.group("amount"))
            unit = _normalize_unit(match.group("unit"))
            key = (_normalize_text(name), amount, unit)
            if key in seen:
                continue
            seen.add(key)
            ingredients.append(
                {
                    "name": name,
                    "amount": amount,
                    "unit": unit,
                    "expected_source": AUTO_EXPECTED_SOURCE,
                    "verification_status": AUTO_EXPECTED_VERIFICATION_STATUS,
                }
            )
            if len(ingredients) >= AUTO_EXPECTED_MAX_INGREDIENTS:
                return ingredients
    return ingredients


def _extract_product_name_candidate(ocr_text: str) -> str | None:
    """Extract a short product-name candidate from OCR text.

    Args:
        ocr_text: Raw OCR text kept only in process memory.

    Returns:
        Product name candidate or None.
    """
    for line in _ocr_lines(ocr_text):
        stripped = line.strip()
        if not (
            AUTO_EXPECTED_MIN_PRODUCT_NAME_CHARS
            <= len(stripped)
            <= AUTO_EXPECTED_MAX_PRODUCT_NAME_CHARS
        ):
            continue
        if INGREDIENT_AMOUNT_PATTERN.search(stripped):
            continue
        if _looks_like_non_product_heading(stripped):
            continue
        return stripped
    return None


def _ocr_lines(ocr_text: str) -> list[str]:
    """Return bounded non-empty OCR lines.

    Args:
        ocr_text: Raw OCR text kept only in process memory.

    Returns:
        Non-empty lines.
    """
    return [line.strip() for line in ocr_text.splitlines() if line.strip()][:300]


def _clean_ingredient_name(value: str) -> str:
    """Clean an ingredient name candidate.

    Args:
        value: Regex-captured ingredient prefix.

    Returns:
        Cleaned ingredient name or an empty string when unsuitable.
    """
    cleaned = re.sub(r"^[^A-Za-z가-힣]+", "", value)
    cleaned = re.sub(r"[:\uff1a|·•]+$", "", cleaned).strip(TRAILING_INGREDIENT_PUNCTUATION)
    cleaned = " ".join(cleaned.split())
    if not (
        AUTO_EXPECTED_MIN_INGREDIENT_NAME_CHARS
        <= len(cleaned)
        <= AUTO_EXPECTED_MAX_INGREDIENT_NAME_CHARS
    ):
        return ""
    if _looks_like_non_product_heading(cleaned):
        return ""
    if _looks_like_packaging_quantity_token(cleaned):
        return ""
    if not re.search(r"[A-Za-z가-힣]", cleaned):
        return ""
    return cleaned


def _looks_like_packaging_quantity_token(value: str) -> bool:
    """Return whether a candidate is a package quantity, not an ingredient.

    Args:
        value: Cleaned ingredient candidate.

    Returns:
        True when the value is a bounded package/serving-count fragment.
    """
    normalized = _normalize_text(value)
    if not normalized:
        return False
    return any(pattern.fullmatch(normalized) for pattern in PACKAGING_QUANTITY_PATTERNS)


def _parse_amount(value: str) -> int | float:
    """Parse a numeric amount without inventing units or conversions.

    Args:
        value: OCR amount text.

    Returns:
        Integer or float amount.
    """
    numeric_text = value.replace(",", "")
    numeric_value = float(numeric_text)
    return int(numeric_value) if numeric_value.is_integer() else numeric_value


def _normalize_unit(value: str) -> str:
    """Normalize common OCR unit variants.

    Args:
        value: OCR unit text.

    Returns:
        Normalized unit string.
    """
    normalized = value.strip()
    if normalized in {"μg", "㎍"}:
        return "ug"
    if normalized.casefold() == "iu":
        return "IU"
    return normalized.casefold() if normalized != "%" else "%"


def _pii_candidate_flags(ocr_text: str) -> list[str]:
    """Return bounded PII candidate flags without exposing matched text.

    Args:
        ocr_text: Raw OCR text kept only in process memory.

    Returns:
        Stable flag names for possible PII tokens.
    """
    flags: list[str] = []
    for flag, pattern in PII_CANDIDATE_PATTERNS:
        if pattern.search(ocr_text):
            flags.append(flag)
    return flags


def _looks_like_non_product_heading(value: str) -> bool:
    """Return whether text is a generic label heading, not a product/ingredient.

    Args:
        value: Candidate text.

    Returns:
        True when the text looks like a generic section heading.
    """
    normalized = _normalize_text(value)
    heading_tokens = (
        "nutrition facts",
        "supplement facts",
        "영양 정보",
        "영양정보",
        "섭취 방법",
        "섭취방법",
        "주의 사항",
        "주의사항",
        "원재료명",
        "기능 정보",
        "기능정보",
        "건강기능식품",
    )
    return any(token in normalized for token in heading_tokens)


def _read_fixture_manifest(
    manifest_path: Path,
    *,
    providers: tuple[ProviderName, ...],
) -> list[FixtureCase]:
    """Read and validate fixture manifest rows.

    Args:
        manifest_path: JSON or JSONL manifest path.
        providers: Providers requested for this run.

    Returns:
        Fixture cases.

    Raises:
        ValueError: If the manifest contains raw or unsafe fields.
    """
    rows = _manifest_rows(manifest_path)
    fixtures: list[FixtureCase] = []
    for row in rows:
        _reject_raw_fields(row)
        fixture_id = row.get("fixture_id")
        image_path = row.get("image_path")
        if not isinstance(fixture_id, str) or not fixture_id.strip():
            raise ValueError("Each OCR fixture requires fixture_id.")
        if not isinstance(image_path, str) or not image_path.strip():
            raise ValueError(f"OCR fixture requires image_path: {fixture_id}")
        image_sha256 = row.get("image_sha256")
        if not isinstance(image_sha256, str) or len(image_sha256) != SHA256_HEX_LENGTH:
            raise ValueError(f"OCR fixture requires image_sha256: {fixture_id}")
        if row.get("license_status") not in ALLOWED_LICENSE_STATUS:
            raise ValueError(f"OCR fixture has unsupported license_status: {fixture_id}")
        if row.get("consent_status") not in ALLOWED_CONSENT_STATUS:
            raise ValueError(f"OCR fixture has unsupported consent_status: {fixture_id}")
        _validate_fixture_privacy(row=row, providers=providers, fixture_id=fixture_id)
        expected = row.get("expected", {})
        if not isinstance(expected, dict):
            raise ValueError(f"OCR fixture expected must be an object: {fixture_id}")
        resolved_image_path = _resolve_fixture_image_path(manifest_path, image_path)
        if not resolved_image_path.exists():
            raise ValueError(f"OCR fixture image is missing: {fixture_id}")
        actual_sha = hashlib.sha256(resolved_image_path.read_bytes()).hexdigest()
        if actual_sha != image_sha256:
            raise ValueError(f"OCR fixture image_sha256 mismatch: {fixture_id}")
        fixtures.append(
            FixtureCase(
                fixture_id=fixture_id.strip(),
                image_path=resolved_image_path,
                expected=expected,
                manifest_row=dict(row),
            )
        )
    return fixtures


def _resolve_fixture_image_path(manifest_path: Path, image_path: str) -> Path:
    """Resolve a manifest image path without persisting operator-local roots.

    Args:
        manifest_path: Path to the fixture manifest being read.
        image_path: Relative, absolute legacy, or allowlisted ``$ENV/path`` image path.

    Returns:
        Absolute resolved image path for runtime file loading.

    Raises:
        ValueError: If an environment-token path is unsupported, unset, or unsafe.
    """
    env_match = ENV_IMAGE_PATH_PATTERN.fullmatch(image_path)
    if env_match:
        env_name = env_match.group("name")
        if env_name not in ALLOWED_IMAGE_PATH_ENV_VARS:
            raise ValueError(f"OCR fixture image_path env is not allowlisted: {env_name}")
        env_root = os.environ.get(env_name)
        if not env_root:
            raise ValueError(f"OCR fixture image_path env is not set: {env_name}")
        relative_text = env_match.group("path") or ""
        relative_path = PurePosixPath(relative_text)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError("OCR fixture image_path env suffix must stay under the image root.")
        resolved_root = Path(env_root).expanduser().resolve()
        resolved_path = (resolved_root / Path(*relative_path.parts)).resolve()
        try:
            resolved_path.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError(
                "OCR fixture image_path env suffix must resolve under the image root."
            ) from exc
        return resolved_path

    path = Path(image_path)
    if path.is_absolute():
        return path.expanduser().resolve()
    return (manifest_path.parent / path).resolve()


def _validate_fixture_privacy(
    *,
    row: dict[str, object],
    providers: tuple[ProviderName, ...],
    fixture_id: object,
) -> None:
    """Validate row-level privacy policy for the requested providers.

    Args:
        row: Manifest row.
        providers: Providers requested for the current collector run.
        fixture_id: Fixture id used in error messages.

    Raises:
        ValueError: If a row can leak personal data to an external provider.
    """
    if row.get("contains_personal_data") is False:
        return
    if _row_requires_local_pii_screening(row) and providers == ("paddleocr_local",):
        return
    raise ValueError(f"OCR fixture must be non-personal or local PII-screening only: {fixture_id}")


def _requires_local_pii_screening(fixture: FixtureCase) -> bool:
    """Return whether a fixture is a review row pending local-only PII screening."""
    return _row_requires_local_pii_screening(fixture.manifest_row)


def _row_requires_local_pii_screening(row: dict[str, object]) -> bool:
    """Return whether a manifest row is restricted to local PII screening."""
    return (
        row.get("section") == "review"
        and row.get("contains_personal_data") is None
        and row.get("pii_screening_status") == "pending_local_screening"
        and row.get("external_transfer_allowed") is False
        and row.get("local_processing_allowed") is True
    )


def _manifest_rows(manifest_path: Path) -> list[dict[str, object]]:
    """Return manifest objects from JSON or JSONL input.

    Args:
        manifest_path: Manifest path.

    Returns:
        Parsed rows.
    """
    text = manifest_path.read_text(encoding="utf-8")
    if manifest_path.suffix == ".jsonl":
        rows: list[dict[str, object]] = []
        for line_number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parsed = json.loads(stripped)
            if not isinstance(parsed, dict):
                raise ValueError(f"Manifest line {line_number} must be an object.")
            rows.append(parsed)
        return rows
    parsed_json = json.loads(text)
    if isinstance(parsed_json, dict) and isinstance(parsed_json.get("cases"), list):
        return [cast(dict[str, object], row) for row in parsed_json["cases"]]
    if isinstance(parsed_json, list):
        return [cast(dict[str, object], row) for row in parsed_json]
    raise ValueError("Manifest must be JSONL, a JSON list, or a JSON object with cases.")


def _load_image_input(image_path: Path) -> OCRImageInput:
    """Load a fixture image for an explicitly opted-in provider call.

    Args:
        image_path: Local fixture image path.

    Returns:
        OCR image DTO.

    Raises:
        RuntimeError: If the image cannot be decoded.
    """
    try:
        image_bytes = image_path.read_bytes()
    except FileNotFoundError as exc:
        raise OCRError("OCR fixture image is missing.") from exc
    except PermissionError as exc:
        raise OCRError("OCR fixture image cannot be read.") from exc
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            width, height = image.size
            mime_type = Image.MIME.get(image.format or "", "image/png")
    except (OSError, UnidentifiedImageError) as exc:
        raise OCRError("OCR fixture image cannot be decoded.") from exc
    return OCRImageInput(
        image_bytes=image_bytes,
        mime_type=mime_type,
        width=width,
        height=height,
    )


def _reject_raw_fields(value: object) -> None:
    """Reject raw OCR/image fields recursively.

    Args:
        value: Candidate manifest or observation value.

    Raises:
        ValueError: If a forbidden raw field is present.
    """
    if isinstance(value, dict):
        forbidden = RAW_FORBIDDEN_KEYS.intersection(str(key).lower() for key in value)
        if forbidden:
            raise ValueError(f"Payload contains forbidden raw field(s): {sorted(forbidden)}")
        for nested_value in value.values():
            _reject_raw_fields(nested_value)
    elif isinstance(value, list):
        for item in value:
            _reject_raw_fields(item)


def _expected_ingredients(expected: dict[str, object]) -> list[dict[str, object]]:
    """Return expected ingredients from a fixture expected object.

    Args:
        expected: Expected fixture summary.

    Returns:
        Ingredient dictionaries.
    """
    ingredients = expected.get("ingredients")
    if not isinstance(ingredients, list):
        return []
    return [item for item in ingredients if isinstance(item, dict)]


def _expected_ingredient_names(ingredient: dict[str, object]) -> list[str]:
    """Return displayable expected ingredient names across manifest schemas.

    Args:
        ingredient: Expected ingredient row from a fixture manifest.

    Returns:
        One or more ingredient names, or an empty list when no supported name
        field exists.
    """
    for key in ("name", "display_name", "normalized_name"):
        value = ingredient.get(key)
        if isinstance(value, str) and value.strip():
            return _split_expected_ingredient_name(value.strip(), ingredient)
    return []


def _split_expected_ingredient_name(value: str, ingredient: dict[str, object]) -> list[str]:
    """Split bounded compound expected names when no dose is attached.

    Args:
        value: Expected ingredient name.
        ingredient: Full expected ingredient row.

    Returns:
        A list of display names. Dose-bearing rows are kept as one name.
    """
    if ingredient.get("amount") is not None or ingredient.get("unit") is not None:
        return [value]
    parts = [
        part.strip()
        for part in EXPECTED_NAME_SEPARATOR_PATTERN.split(value)
        if _looks_like_expected_name_part(part)
    ]
    return parts if len(parts) > 1 else [value]


def _looks_like_expected_name_part(value: str) -> bool:
    """Return whether a compound expected-name part is safe to emit.

    Args:
        value: Candidate split name.

    Returns:
        True for bounded alphabetic ingredient-name fragments.
    """
    stripped = value.strip()
    return (
        AUTO_EXPECTED_MIN_INGREDIENT_NAME_CHARS
        <= len(stripped)
        <= AUTO_EXPECTED_MAX_INGREDIENT_NAME_CHARS
        and bool(re.search(r"[A-Za-z가-힣]", stripped))
        and not _looks_like_packaging_quantity_token(stripped)
    )


def _matched_expected_ingredients(
    normalized_text: str,
    expected: dict[str, object],
) -> list[dict[str, object]]:
    """Return expected ingredients whose values are visible in OCR text.

    Args:
        normalized_text: Normalized OCR text.
        expected: Expected fixture summary.

    Returns:
        Redacted parsed ingredient summaries.
    """
    parsed: list[dict[str, object]] = []
    seen_names: set[str] = set()
    match_text = _normalize_ingredient_match_token(normalized_text)
    compact_match_text = match_text.replace(" ", "")
    for ingredient in _expected_ingredients(expected):
        for name in _expected_ingredient_names(ingredient):
            normalized_name = _normalize_text(name)
            if not normalized_name or normalized_name in seen_names:
                continue
            if not _ingredient_name_visible(
                name,
                match_text=match_text,
                compact_match_text=compact_match_text,
            ):
                continue
            seen_names.add(normalized_name)
            observed: dict[str, object] = {"name": name}
            amount = ingredient.get("amount")
            unit = ingredient.get("unit")
            if amount is not None and _normalize_text(amount) in normalized_text:
                observed["amount"] = amount
            if isinstance(unit, str) and _normalize_text(unit) in normalized_text:
                observed["unit"] = unit
            parsed.append(observed)
    return parsed


def _ingredient_name_visible(
    name: str,
    *,
    match_text: str,
    compact_match_text: str,
) -> bool:
    """Return whether an expected ingredient name is visible in OCR text.

    Args:
        name: Expected ingredient display name.
        match_text: Punctuation-normalized OCR text kept only in memory.
        compact_match_text: Space-free normalized OCR text.

    Returns:
        True when the exact name or a bounded semantic alias is visible.
    """
    for variant in _ingredient_name_match_variants(name):
        if variant in match_text or variant.replace(" ", "") in compact_match_text:
            return True
    return False


def _ingredient_name_match_variants(name: str) -> tuple[str, ...]:
    """Return bounded OCR-match variants for one expected ingredient name.

    Args:
        name: Expected ingredient display name.

    Returns:
        Normalized variants. These are used only for transient matching and are
        never persisted as raw OCR evidence.
    """
    normalized = _normalize_ingredient_match_token(name)
    if not normalized:
        return ()
    variants: list[str] = [normalized]
    compact = normalized.replace(" ", "")
    if compact:
        variants.append(compact)

    for match in INGREDIENT_PARENTHESES_PATTERN.finditer(name):
        inner = _normalize_ingredient_match_token(match.group("inner").replace("&", " "))
        if _looks_like_expected_name_part(inner):
            variants.append(inner)

    without_parentheses = _normalize_ingredient_match_token(
        INGREDIENT_PARENTHESES_PATTERN.sub("", name)
    )
    if without_parentheses and without_parentheses != normalized:
        variants.append(without_parentheses)

    for prefix in KOREAN_INGREDIENT_DESCRIPTOR_PREFIXES:
        if compact.startswith(prefix) and len(compact) > len(prefix) + 1:
            variants.append(compact.removeprefix(prefix))

    for prefix in ENGLISH_INGREDIENT_DESCRIPTOR_PREFIXES:
        if normalized.startswith(prefix) and len(normalized) > len(prefix) + 3:
            variants.append(normalized.removeprefix(prefix))

    return tuple(_dedupe_match_variants(variants))


def _normalize_ingredient_match_token(value: object) -> str:
    """Normalize text for transient ingredient-name matching.

    Args:
        value: Candidate text-like value.

    Returns:
        Case-folded token with punctuation collapsed to spaces.
    """
    normalized = _normalize_text(value).replace("&", " ")
    return " ".join(INGREDIENT_MATCH_SEPARATOR_PATTERN.sub(" ", normalized).split())


def _dedupe_match_variants(values: list[str]) -> list[str]:
    """Return unique, bounded ingredient match variants.

    Args:
        values: Candidate normalized variants.

    Returns:
        Variants in stable order.
    """
    deduped: list[str] = []
    for value in values:
        stripped = value.strip()
        if not stripped or stripped in deduped:
            continue
        if len(stripped) < AUTO_EXPECTED_MIN_INGREDIENT_NAME_CHARS:
            continue
        deduped.append(stripped)
    return deduped


def _parsed_values_grounded(normalized_text: str, ingredients: list[dict[str, object]]) -> bool:
    """Return whether all parsed ingredient values are present in OCR text.

    Args:
        normalized_text: Normalized OCR text.
        ingredients: Parsed ingredient summaries.

    Returns:
        True when every emitted value is visible in normalized OCR text.
    """
    for ingredient in ingredients:
        for value in ingredient.values():
            if _normalize_text(value) not in normalized_text:
                return False
    return True


def _normalize_text(value: object) -> str:
    """Normalize text for redacted fixture matching.

    Args:
        value: Candidate text-like value.

    Returns:
        Case-folded whitespace-normalized text.
    """
    raw = str(int(value)) if isinstance(value, float) and value.is_integer() else str(value or "")
    return " ".join(raw.casefold().split())


def _safe_error_code(exc: Exception) -> str:
    """Map an exception to a stable non-sensitive error code.

    Args:
        exc: Provider exception.

    Returns:
        Safe error code.
    """
    if isinstance(exc, OCRConfigurationError):
        return "provider_configuration_error"
    if isinstance(exc, OCRError):
        return _safe_ocr_error_code(str(exc))
    return f"{exc.__class__.__name__.casefold()}".replace(" ", "_")


def _safe_ocr_error_code(message: str) -> str:
    """Map sanitized OCR error text to a bounded error code."""
    if "Google Vision OCR provider error:" in message:
        status = message.rsplit(":", 1)[-1].strip().casefold()
        status_token = re.sub(r"[^a-z0-9]+", "_", status).strip("_") or "unknown"
        return f"ocr_provider_error_{status_token}"
    status_match = re.search(r"status\s+(\d{3})", message)
    if status_match:
        return f"ocr_http_status_{status_match.group(1)}"
    message_token = message.casefold()
    mapped = {
        "authentication": "ocr_authentication_error",
        "transport": "ocr_transport_error",
        "invalid json": "ocr_invalid_json",
        "ocr fixture image is missing": "image_missing",
        "ocr fixture image cannot be read": "image_read_error",
        "ocr fixture image cannot be decoded": "image_decode_error",
        "paddleocr is not installed": "ocr_dependency_missing",
        "paddleocr predictor initialization failed": "ocr_provider_initialization",
        "paddleocr provider prediction failed": "ocr_provider_prediction_failed",
        "paddleocr temporary image write failed": "image_write_error",
        "paddleocr returned no readable text": "ocr_empty_text",
        "paddleocr confidence is below": "ocr_low_confidence",
        "enable_local_ocr=true is required": "local_ocr_disabled",
    }
    for needle, code in mapped.items():
        if needle in message_token:
            return code
    return "ocr_error"


def _parse_providers(value: str) -> tuple[ProviderName, ...]:
    """Parse a comma-separated provider list.

    Args:
        value: CLI provider list.

    Returns:
        Provider tuple.

    Raises:
        ValueError: If a provider is unsupported.
    """
    parsed: list[ProviderName] = []
    for item in value.split(","):
        provider = item.strip()
        if not provider:
            continue
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider}")
        parsed.append(provider)
    return tuple(parsed or SUPPORTED_PROVIDERS)


if __name__ == "__main__":
    main()
