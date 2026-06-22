"""Supplement OCR parser service tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import Settings
from src.llm.ollama import OllamaClientError, OllamaStructuredOutputError
from src.models.db.supplement import SupplementAnalysisRun
from src.models.schemas.label_layout import LabelLayout
from src.models.schemas.supplement import SupplementAnalysisStatus
from src.models.schemas.supplement_parser import SupplementStructuredParseResult
from src.models.schemas.supplement_snapshot import upcast_legacy_parsed_snapshot
from src.security.auth import AuthenticatedUser
from src.services.supplement_intake import supplement_analysis_run_to_preview
from src.services.supplement_parser import (
    LLM_PARSE_FALLBACK_WARNING,
    SupplementAnalysisExpiredError,
    SupplementAnalysisNotFoundError,
    SupplementParserConflictError,
    SupplementParserInputError,
    _build_parsed_snapshot,
    _extract_ocr_pattern_ingredient_candidates,
    hash_ocr_text,
    normalize_ocr_text,
    parse_supplement_analysis_ocr_text,
)


class _FakeParser:
    """Fake parser adapter for service tests."""

    def __init__(self, result: SupplementStructuredParseResult) -> None:
        self.result = result
        self.received_text: str | None = None

    async def parse_supplement_ocr_text(
        self,
        ocr_text: str,
    ) -> SupplementStructuredParseResult:
        """Capture OCR text and return a configured structured result.

        Args:
            ocr_text: OCR text passed by the service.

        Returns:
            Configured structured parse result.
        """
        self.received_text = ocr_text
        return self.result


class _RaisingParser:
    """Fake parser adapter that raises, to exercise the LLM-failure degrade path."""

    def __init__(self, error: Exception) -> None:
        self.error = error
        self.received_text: str | None = None

    async def parse_supplement_ocr_text(
        self,
        ocr_text: str,
    ) -> SupplementStructuredParseResult:
        """Capture OCR text then raise the configured error.

        Args:
            ocr_text: OCR text passed by the service.

        Raises:
            Exception: The configured parser failure.
        """
        self.received_text = ocr_text
        raise self.error


class _FakeParserSession:
    """Fake async session for parser service tests."""

    def __init__(self, record: SupplementAnalysisRun | None) -> None:
        self.record = record
        self.committed = False
        self.commits = 0
        self.refreshed: SupplementAnalysisRun | None = None
        # A real AsyncSession always exposes ``.info``; persist_scope reads it.
        self.info: dict[str, object] = {}

    async def flush(self) -> None:
        """No-op flush (persist_scope flushes pending writes)."""

    async def rollback(self) -> None:
        """No-op rollback (persist_scope own-mode rolls back on exception)."""

    async def scalar(self, _statement: object) -> SupplementAnalysisRun | None:
        """Return the configured analysis row.

        Args:
            _statement: SQLAlchemy select statement.

        Returns:
            Configured supplement analysis row or None.
        """
        return self.record

    async def commit(self) -> None:
        """Record legacy persist_scope commits without touching a database."""
        self.committed = True
        self.commits += 1

    async def refresh(self, record: SupplementAnalysisRun) -> None:
        """Record refresh calls without touching a database."""
        self.refreshed = record


def test_ocr_pattern_fallback_accepts_spaced_unit_glyphs() -> None:
    """Verify OCR-spaced unit tokens still produce bounded ingredient candidates."""
    candidates = _extract_ocr_pattern_ingredient_candidates(
        "\n".join(
            [
                "Vitamin C 100 m g",
                "Folate 400 m c g",
                "Vitamin D 1000 I U",
            ]
        )
    )

    by_name = {candidate["display_name"]: candidate for candidate in candidates}
    assert by_name["Vitamin C"]["amount"] == 100
    assert by_name["Vitamin C"]["unit"] == "mg"
    assert by_name["Folate"]["amount"] == 400
    assert by_name["Folate"]["unit"] == "ug"
    assert by_name["Vitamin D"]["amount"] == 1000
    assert by_name["Vitamin D"]["unit"] == "IU"

    async def commit(self) -> None:
        """Record a fake commit.

        Returns:
            None.
        """
        self.committed = True
        self.commits += 1

    async def refresh(self, record: object) -> None:
        """Record the refreshed analysis row.

        Args:
            record: ORM object being refreshed.

        Returns:
            None.
        """
        self.refreshed = cast(SupplementAnalysisRun, record)


def test_ocr_pattern_fallback_accepts_table_rows_and_parenthesized_sources() -> None:
    """Verify supplement-facts row delimiters preserve ingredient amounts."""
    candidates = _extract_ocr_pattern_ingredient_candidates(
        "\n".join(
            [
                "Magnesium (as magnesium glycinate) | 200 mg | 48%",
                "마그네슘 (Magnesium) : 100 mg 24%",
                "Vitamin B6 · 12 mg · 706%",
            ]
        )
    )

    by_name = {candidate["display_name"]: candidate for candidate in candidates}
    assert by_name["Magnesium (as magnesium glycinate)"]["amount"] == 200
    assert by_name["Magnesium (as magnesium glycinate)"]["unit"] == "mg"
    assert by_name["Magnesium (as magnesium glycinate)"]["daily_value_percent"] == 48
    assert by_name["마그네슘 (Magnesium)"]["amount"] == 100
    assert by_name["Vitamin B6"]["amount"] == 12


def test_ocr_pattern_fallback_pairs_unit_before_amount_columns() -> None:
    """Pair vertical column cells that print the unit before the number.

    Mirrors the existing amount-then-unit split for the reverse order found on
    rotated / column labels (``name`` / ``unit`` / ``number``).
    """
    candidates = _extract_ocr_pattern_ingredient_candidates("\n".join(["마그네슘", "mg", "200"]))

    by_name = {candidate["display_name"]: candidate for candidate in candidates}
    assert by_name["마그네슘"]["amount"] == 200
    assert by_name["마그네슘"]["unit"] == "mg"


def test_ocr_pattern_fallback_fuses_split_salt_continuation_name() -> None:
    """Fuse an OCR-split salt name into one ingredient before pairing.

    ``Magnesium`` / ``Citrate`` on separate lines must produce a single
    ``Magnesium Citrate`` candidate, not a truncated ``Magnesium``.
    """
    candidates = _extract_ocr_pattern_ingredient_candidates(
        "\n".join(["Magnesium", "Citrate", "200mg"])
    )

    by_name = {candidate["display_name"]: candidate for candidate in candidates}
    assert "Magnesium Citrate" in by_name
    assert by_name["Magnesium Citrate"]["amount"] == 200
    assert by_name["Magnesium Citrate"]["unit"] == "mg"


def test_ocr_pattern_fallback_never_fuses_two_standalone_ingredients() -> None:
    """Adjacent standalone ingredient names must never fuse into a phantom row.

    Covers the precision cases that distinguish a salt continuation (fused) from a
    second ingredient (kept separate): English names, Korean names absent from any
    nutrient lexicon, and the stacked 2-column read order (names then amounts).
    Only a salt/form word may continue a name, so none of these fuse.
    """
    english = {
        candidate["display_name"]
        for candidate in _extract_ocr_pattern_ingredient_candidates(
            "\n".join(["Calcium", "Magnesium", "200mg"])
        )
    }
    assert "Calcium Magnesium" not in english

    korean = {
        candidate["display_name"]
        for candidate in _extract_ocr_pattern_ingredient_candidates(
            "\n".join(["아연", "셀레늄", "200mg"])
        )
    }
    assert "아연 셀레늄" not in korean

    stacked = {
        candidate["display_name"]
        for candidate in _extract_ocr_pattern_ingredient_candidates(
            "\n".join(["셀레늄", "엽산", "비오틴", "55mcg", "400mcg", "30mcg"])
        )
    }
    assert "셀레늄 엽산 비오틴" not in stacked
    assert "셀레늄 엽산" not in stacked


def test_ocr_pattern_fallback_does_not_fuse_names_across_amounts() -> None:
    """A value line between two names blocks fusion and keeps both distinct."""
    candidates = _extract_ocr_pattern_ingredient_candidates(
        "\n".join(["Calcium", "500mg", "Zinc", "15mg"])
    )

    by_name = {candidate["display_name"]: candidate for candidate in candidates}
    assert by_name["Calcium"]["amount"] == 500
    assert by_name["Zinc"]["amount"] == 15
    assert "Calcium Zinc" not in by_name


def test_ocr_pattern_fallback_pairs_split_facts_table_cells() -> None:
    """Verify name/amount/%DV cells split by OCR still preserve visible values."""
    candidates = _extract_ocr_pattern_ingredient_candidates(
        "\n".join(
            [
                "Supplement Facts",
                "Vitamin B6",
                "Amount Per Serving",
                "10.5 mg",
                "618%",
                "Magnesium",
                "450",
                "mg",
                "107%",
                "Serving Size",
                "2 capsules",
            ]
        )
    )

    by_name = {candidate["display_name"]: candidate for candidate in candidates}
    assert by_name["Vitamin B6"]["amount"] == 10.5
    assert by_name["Vitamin B6"]["unit"] == "mg"
    assert by_name["Vitamin B6"]["daily_value_percent"] == 618
    assert by_name["Magnesium"]["amount"] == 450
    assert by_name["Magnesium"]["unit"] == "mg"
    assert by_name["Magnesium"]["daily_value_percent"] == 107
    assert "Serving Size" not in by_name


def _settings() -> Settings:
    """Return parser service test settings.

    Returns:
        Settings object.
    """
    # _env_file=None keeps these test settings hermetic — without it pydantic loads the
    # repo-root .env (which may set STORE_RAW_OCR_TEXT=true), making default-OFF
    # assertions flip with ambient operator config. Mirrors test_config.py.
    return Settings(
        privacy_hash_secret=SecretStr("test-privacy-secret"),
        _env_file=None,
    )


def _user() -> AuthenticatedUser:
    """Return an authenticated user fixture.

    Returns:
        Authenticated user model.
    """
    return AuthenticatedUser(
        subject="user_123",
        issuer="https://auth.example.com/",
        claims={"sub": "user_123"},
    )


def _analysis_run(
    *,
    analysis_id: UUID | None = None,
    expires_at: datetime | None = None,
    ocr_text_hash: str | None = None,
) -> SupplementAnalysisRun:
    """Return an owned supplement analysis row fixture.

    Args:
        analysis_id: Optional analysis row identifier.
        expires_at: Optional expiration time.
        ocr_text_hash: Optional stored OCR text hash.

    Returns:
        Supplement analysis run fixture.
    """
    now = datetime.now(UTC)
    return SupplementAnalysisRun(
        id=analysis_id or uuid4(),
        owner_subject="https://auth.example.com/::user_123",
        client_request_id="client-1",
        status=SupplementAnalysisStatus.REQUIRES_CONFIRMATION.value,
        image_sha256="a" * 64,
        image_mime_type="image/png",
        image_size_bytes=128,
        ocr_provider="intake-only",
        ocr_text_hash=ocr_text_hash,
        parsed_snapshot={
            "parsed_product": {},
            "ingredient_candidates": [],
            "low_confidence_fields": ["label_text"],
            "intake": {"mime_type": "image/png", "size_bytes": 128},
        },
        match_snapshot={"matched_product_candidates": []},
        warnings=[],
        algorithm_version="supplement-intake-v1.0.0",
        expires_at=expires_at or now + timedelta(minutes=30),
        created_at=now,
        updated_at=now,
    )


def _parse_result() -> SupplementStructuredParseResult:
    """Return a valid structured parser result.

    Returns:
        Structured supplement parse result fixture.
    """
    return SupplementStructuredParseResult.model_validate(
        {
            "parsed_product": {
                "product_name": "비타민 D 1000",
                "serving_size": "1 tablet",
                "daily_servings": 1,
            },
            "ingredient_candidates": [
                {
                    "display_name": "비타민 D",
                    "amount": 25,
                    "unit": "ug",
                    "confidence": 0.91,
                }
            ],
            "label_sections": [
                {
                    "section_id": "section-1",
                    "section_type": "supplement_facts",
                    "heading_text": "Supplement Facts",
                    "text_bundle": "Vitamin D 25 ug",
                    "confidence": 0.9,
                    "requires_review": False,
                    "evidence_refs": ["span-1"],
                }
            ],
            "intake_method": {
                "text": "1일 1정 섭취",
                "structured": {
                    "frequency": "daily",
                    "times_per_day": 1,
                    "amount_per_time": 1,
                    "amount_unit": "tablet",
                    "time_of_day": [],
                    "with_food": "unknown",
                },
                "confidence": 0.82,
                "requires_review": True,
                "evidence_refs": ["span-2"],
            },
            "precautions": [
                {
                    "text": "임산부는 전문가와 상담",
                    "category": "pregnancy",
                    "severity": "caution",
                    "confidence": 0.8,
                    "requires_review": True,
                    "evidence_refs": ["span-3"],
                }
            ],
            "functional_claims": [
                {
                    "text": "뼈 건강에 도움",
                    "claim_type": "label_claim",
                    "confidence": 0.77,
                    "requires_review": True,
                    "evidence_refs": ["span-4"],
                }
            ],
            "evidence_spans": [
                {
                    "span_id": "span-1",
                    "source_type": "ocr",
                    "section_type": "supplement_facts",
                    "text_excerpt": "Vitamin D 25 ug",
                    "confidence": 0.9,
                },
                {
                    "span_id": "span-2",
                    "source_type": "ocr",
                    "section_type": "intake_method",
                    "text_excerpt": "1일 1정 섭취",
                    "confidence": 0.82,
                },
            ],
            "missing_required_sections": [],
            "low_confidence_fields": ["manufacturer"],
            "warnings": ["제조사명은 확인이 필요합니다."],
        }
    )


def _minimal_parse_result() -> SupplementStructuredParseResult:
    """Return parser output with no parser-provided layout sections."""
    return SupplementStructuredParseResult.model_validate(
        {
            "parsed_product": {"product_name": "비타민 D 1000"},
            "ingredient_candidates": [
                {
                    "display_name": "비타민 D",
                    "amount": 25,
                    "unit": "ug",
                    "confidence": 0.91,
                }
            ],
            "missing_required_sections": ["supplement_facts", "intake_method", "precautions"],
            "low_confidence_fields": [],
            "warnings": [],
        }
    )


def _empty_parse_result() -> SupplementStructuredParseResult:
    """Return parser output with no ingredient candidates."""
    return SupplementStructuredParseResult.model_validate(
        {
            "ingredient_candidates": [],
            "missing_required_sections": [
                "product_name",
                "supplement_facts",
                "intake_method",
                "precautions",
            ],
            "low_confidence_fields": [],
            "warnings": [],
        }
    )


def _label_layout() -> LabelLayout:
    """Return deterministic OCR layout with facts and intake sections."""
    return LabelLayout.model_validate(
        {
            "provider": "fake-ocr",
            "page_count": 1,
            "sections": [
                {
                    "section_type": "nutrition_function_info",
                    "anchor_text": "Supplement Facts",
                    "anchor_box": {
                        "page_index": 0,
                        "left": 10,
                        "top": 10,
                        "right": 200,
                        "bottom": 40,
                    },
                    "rows": [
                        [
                            {
                                "row_index": 0,
                                "column_index": 0,
                                "text": "Supplement Facts",
                                "bounding_box": {
                                    "page_index": 0,
                                    "left": 10,
                                    "top": 10,
                                    "right": 200,
                                    "bottom": 40,
                                },
                                "confidence": 0.9,
                                "word_count": 1,
                            }
                        ],
                        [
                            {
                                "row_index": 1,
                                "column_index": 0,
                                "text": "Vitamin D",
                                "bounding_box": {
                                    "page_index": 0,
                                    "left": 10,
                                    "top": 50,
                                    "right": 140,
                                    "bottom": 80,
                                },
                                "confidence": 0.92,
                                "word_count": 1,
                            },
                            {
                                "row_index": 1,
                                "column_index": 1,
                                "text": "25 ug",
                                "bounding_box": {
                                    "page_index": 0,
                                    "left": 170,
                                    "top": 50,
                                    "right": 230,
                                    "bottom": 80,
                                },
                                "confidence": 0.9,
                                "word_count": 1,
                            },
                        ],
                    ],
                },
                {
                    "section_type": "intake_method",
                    "anchor_text": "섭취방법",
                    "anchor_box": {
                        "page_index": 0,
                        "left": 10,
                        "top": 100,
                        "right": 110,
                        "bottom": 130,
                    },
                    "rows": [
                        [
                            {
                                "row_index": 0,
                                "column_index": 0,
                                "text": "섭취방법 1일 1정",
                                "bounding_box": {
                                    "page_index": 0,
                                    "left": 10,
                                    "top": 100,
                                    "right": 220,
                                    "bottom": 130,
                                },
                                "confidence": 0.86,
                                "word_count": 1,
                            }
                        ]
                    ],
                },
            ],
            "warnings": [],
        }
    )


def _precaution_label_layout() -> LabelLayout:
    """Return deterministic OCR layout with a visible warning section."""
    return LabelLayout.model_validate(
        {
            "provider": "fake-ocr",
            "page_count": 1,
            "sections": [
                {
                    "section_type": "precautions",
                    "anchor_text": "Warning",
                    "anchor_box": {
                        "page_index": 0,
                        "left": 10,
                        "top": 140,
                        "right": 110,
                        "bottom": 170,
                    },
                    "rows": [
                        [
                            {
                                "row_index": 0,
                                "column_index": 0,
                                "text": "Warning",
                                "bounding_box": {
                                    "page_index": 0,
                                    "left": 10,
                                    "top": 140,
                                    "right": 110,
                                    "bottom": 170,
                                },
                                "confidence": 0.88,
                                "word_count": 1,
                            }
                        ],
                        [
                            {
                                "row_index": 1,
                                "column_index": 0,
                                "text": "Do not take if you are pregnant or taking medication.",
                                "bounding_box": {
                                    "page_index": 0,
                                    "left": 10,
                                    "top": 180,
                                    "right": 420,
                                    "bottom": 210,
                                },
                                "confidence": 0.84,
                                "word_count": 9,
                            }
                        ],
                        [
                            {
                                "row_index": 2,
                                "column_index": 0,
                                "text": "Contains soy allergen.",
                                "bounding_box": {
                                    "page_index": 0,
                                    "left": 10,
                                    "top": 220,
                                    "right": 180,
                                    "bottom": 250,
                                },
                                "confidence": 0.86,
                                "word_count": 3,
                            }
                        ],
                    ],
                }
            ],
            "warnings": [],
        }
    )


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_updates_preview_without_raw_text() -> None:
    """Verify parser output is stored as a sanitized preview snapshot."""
    record = _analysis_run()
    fake_session = _FakeParserSession(record)
    fake_parser = _FakeParser(_parse_result())
    settings = _settings()

    result = await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        " 비타민 D 1000\r\n1 tablet당 비타민 D 25 ug ",
        " manual-test ",
        0.91,
        settings,
        parser=fake_parser,
    )

    assert result.record is record
    assert result.parse_result.parsed_product.product_name == "비타민 D 1000"
    assert fake_parser.received_text == "비타민 D 1000\n1 tablet 당 비타민 D 25 μg"
    assert fake_session.committed is True
    assert fake_session.refreshed is record
    assert record.ocr_provider == "manual-test"
    assert record.ocr_confidence == Decimal("0.91")
    assert record.ocr_text_hash is not None
    assert record.ocr_text_hash != "비타민 D 1000\n1 tablet당 비타민 D 25 ug"
    assert len(record.ocr_text_hash) == 64
    assert record.algorithm_version == "supplement-ollama-parser-v1.0.0"
    assert record.parsed_snapshot["parsed_product"]["product_name"] == "비타민 D 1000"
    assert record.parsed_snapshot["ingredient_candidates"][0]["source"] == "ollama_structured"
    assert record.parsed_snapshot["layout_available"] is True
    assert record.parsed_snapshot["label_sections"][0]["section_type"] == "supplement_facts"
    assert record.parsed_snapshot["intake_method"]["text"] == "1일 1정 섭취"
    assert record.parsed_snapshot["precautions"][0]["category"] == "pregnancy"
    assert record.parsed_snapshot["functional_claims"][0]["claim_type"] == "label_claim"
    assert record.parsed_snapshot["evidence_spans"][0]["text_excerpt"] == "Vitamin D 25 ug"
    assert record.parsed_snapshot["missing_required_sections"] == []
    assert record.parsed_snapshot["parser_metadata"]["raw_ocr_text_stored"] is False
    assert record.parsed_snapshot["parser_metadata"]["raw_model_response_stored"] is False
    assert record.parsed_snapshot["parser_metadata"]["input_provider"] == "manual-test"
    assert "ocr_text" not in record.parsed_snapshot
    assert record.parsed_snapshot["intake"] == {"mime_type": "image/png", "size_bytes": 128}
    assert record.warnings[0].startswith("Structured OCR parsing is a preview")
    preview = supplement_analysis_run_to_preview(record)
    assert preview.layout_available is True
    assert preview.label_sections[0].section_type == "supplement_facts"
    assert preview.intake_method.text == "1일 1정 섭취"
    assert preview.precautions[0].category == "pregnancy"
    assert preview.functional_claims[0].text == "뼈 건강에 도움"
    assert preview.evidence_spans[0].span_id == "span-1"
    assert preview.missing_required_sections == []


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_keeps_bounded_ocr_preview_when_parser_empty() -> (
    None
):
    """Verify visible OCR lines remain reviewable when structured parsing fails.

    The mobile OCR text modal reads bounded ``label_sections`` /
    ``evidence_spans`` instead of raw OCR. This fallback prevents successfully
    recognized OCR text from disappearing when the parser cannot map it into a
    product or ingredient table.
    """
    record = _analysis_run()
    fake_session = _FakeParserSession(record)

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "\n".join(
            [
                "=== [이미지 1 · supplement_facts] ===",
                "Supplement Facts",
                "Vitamin C 1000 mg 111%",
                "Zinc 15 mg 136%",
                "=== [이미지 2 · directions] ===",
                "Suggested use: Take 1 capsule daily.",
            ]
        ),
        "clova_ocr",
        0.74,
        _settings(),
        parser=_FakeParser(_empty_parse_result()),
    )

    assert "ocr_text" not in record.parsed_snapshot
    assert record.parsed_snapshot["parser_metadata"]["raw_ocr_text_stored"] is False
    assert record.parsed_snapshot["layout_available"] is True
    assert record.parsed_snapshot["label_sections"][0]["section_type"] == "supplement_facts"
    assert record.parsed_snapshot["label_sections"][0]["requires_review"] is True
    assert "Vitamin C 1000 mg 111%" in record.parsed_snapshot["label_sections"][0]["text_bundle"]
    assert record.parsed_snapshot["evidence_spans"][0]["source_type"] == "ocr_text_preview"
    assert len(record.parsed_snapshot["evidence_spans"][0]["text_excerpt"]) <= 240
    assert "ocr_text_preview_fallback_requires_review" in record.warnings

    preview = supplement_analysis_run_to_preview(record)
    assert preview.label_sections[0].heading_text == "이미지 1 · supplement_facts"
    assert preview.evidence_spans[0].text_excerpt.startswith("Supplement Facts")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        OllamaStructuredOutputError("Ollama parse produced non-JSON output."),
        OllamaClientError("Ollama request failed."),
    ],
)
async def test_parse_supplement_analysis_recovers_candidates_when_llm_parse_fails(
    error: Exception,
) -> None:
    """Verify a failed LLM parse degrades to deterministic OCR fallbacks.

    A non-JSON / unreachable local LLM response previously aborted the whole
    analysis (HTTP 502 / an empty preview). The deterministic OCR amount-pattern
    fallback must still recover a single-ingredient label like ``Ubiquinol 200 mg``
    instead of stranding the user with an empty result, and the failure is surfaced
    as a review warning so the preview UI flags it.
    """
    record = _analysis_run()
    fake_session = _FakeParserSession(record)
    parser = _RaisingParser(error)

    result = await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "\n".join(["Supplement Facts", "Ubiquinol 200 mg"]),
        "clova_ocr",
        0.88,
        _settings(),
        parser=parser,
    )

    assert parser.received_text is not None
    candidates = record.parsed_snapshot["ingredient_candidates"]
    ubiquinol = next(c for c in candidates if c["display_name"] == "Ubiquinol")
    assert ubiquinol["amount"] == 200
    assert ubiquinol["unit"] == "mg"
    assert ubiquinol["source"] == "ocr_pattern_fallback"
    assert LLM_PARSE_FALLBACK_WARNING in record.warnings
    assert result.record is record


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_flags_low_ocr_confidence() -> None:
    """Verify low OCR confidence is surfaced as a user-review field."""
    record = _analysis_run()
    fake_session = _FakeParserSession(record)

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "비타민 D 1000",
        "manual-test",
        0.79,
        _settings(),
        parser=_FakeParser(_parse_result()),
    )

    assert record.ocr_confidence == Decimal("0.79")
    assert record.parsed_snapshot["low_confidence_fields"] == ["manufacturer", "ocr_text"]


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_merges_deterministic_layout() -> None:
    """Verify provider layout becomes bounded section evidence without raw OCR storage."""
    record = _analysis_run()
    fake_session = _FakeParserSession(record)

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "비타민 D 1000\nVitamin D 25 ug\n섭취방법 1일 1정",
        "fake-ocr",
        0.91,
        _settings(),
        ocr_layout=_label_layout(),
        parser=_FakeParser(_minimal_parse_result()),
    )

    assert record.parsed_snapshot["layout_available"] is True
    assert record.parsed_snapshot["parser_metadata"]["layout_provider"] == "fake-ocr"
    assert record.parsed_snapshot["parser_metadata"]["layout_page_count"] == 1
    assert [section["section_type"] for section in record.parsed_snapshot["label_sections"]] == [
        "supplement_facts",
        "intake_method",
    ]
    assert record.parsed_snapshot["label_sections"][0]["evidence_refs"] == ["layout-span-1"]
    assert record.parsed_snapshot["evidence_spans"][-1]["source_type"] == "ocr_layout"
    assert record.parsed_snapshot["evidence_spans"][-1]["cell_ref"] == "layout-section-2"
    assert record.parsed_snapshot["missing_required_sections"] == ["precautions"]
    assert "ocr_text" not in record.parsed_snapshot


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_promotes_layout_precautions() -> None:
    """Verify visible warning layout rows fill the structured precautions field."""
    record = _analysis_run()
    fake_session = _FakeParserSession(record)

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "Warning\nDo not take if you are pregnant or taking medication.\nContains soy allergen.",
        "fake-ocr",
        0.86,
        _settings(),
        ocr_layout=_precaution_label_layout(),
        parser=_FakeParser(_empty_parse_result()),
    )

    precautions = record.parsed_snapshot["precautions"]
    assert [item["text"] for item in precautions] == [
        "Do not take if you are pregnant or taking medication.",
        "Contains soy allergen.",
    ]
    assert precautions[0]["category"] == "pregnancy"
    assert precautions[0]["severity"] == "warning"
    assert precautions[0]["requires_review"] is True
    assert precautions[0]["evidence_refs"] == ["layout-span-1"]
    assert record.parsed_snapshot["missing_required_sections"] == [
        "product_name",
        "supplement_facts",
        "intake_method",
    ]
    assert "layout_precaution_fallback_requires_review" in record.warnings
    assert "ocr_text" not in record.parsed_snapshot
    preview = supplement_analysis_run_to_preview(record)
    assert preview.precautions[1].category == "allergy"
    assert preview.label_sections[0].section_type == "precautions"


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_adds_ocr_pattern_fallback_candidates() -> None:
    """Verify explicit OCR amount patterns survive when the LLM returns no ingredients."""
    record = _analysis_run()
    fake_session = _FakeParserSession(record)

    result = await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "\n".join(
            [
                "정x 3개입( 72g",
                "건강기능식품 500mg",
                "원재료명 및 함량 비타민 D 25mcg",
                "아연\t10 mg\t50%",
            ]
        ),
        "paddleocr_local",
        0.74,
        _settings(),
        parser=_FakeParser(_empty_parse_result()),
    )

    candidates = record.parsed_snapshot["ingredient_candidates"]
    assert result.parse_result.ingredient_candidates[0].source == "ocr_pattern_fallback"
    assert candidates == [
        {
            "display_name": "비타민 D",
            "original_name": "비타민 D",
            "amount": 25.0,
            "unit": "ug",
            "confidence": 0.55,
            "source": "ocr_pattern_fallback",
        },
        {
            "display_name": "아연",
            "original_name": "아연",
            "amount": 10.0,
            "unit": "mg",
            "daily_value_percent": 50.0,
            "confidence": 0.55,
            "source": "ocr_pattern_fallback",
        },
    ]
    assert "ingredient_candidates" in record.parsed_snapshot["low_confidence_fields"]
    assert "ocr_text" in record.parsed_snapshot["low_confidence_fields"]
    assert "ocr_pattern_fallback_requires_review" in record.warnings
    assert "ocr_text" not in record.parsed_snapshot


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_canonicalizes_unit_variants() -> None:
    """LLM ingredient units canonicalize so unit variants dedupe across paths (§6.2).

    The LLM emits 비타민 D with unit "μg" while the deterministic OCR-pattern path
    extracts the same "비타민 D 25mcg" row as unit "ug". Both must canonicalize to "ug"
    so the candidate renders consistently and the two sources dedupe to a single entry
    instead of a near-duplicate (before the fix the LLM "μg" and the fallback "ug" keyed
    differently and survived as two 비타민 D rows).
    """
    record = _analysis_run()
    fake_session = _FakeParserSession(record)
    llm_result = SupplementStructuredParseResult.model_validate(
        {
            "ingredient_candidates": [
                {
                    "display_name": "비타민 D",
                    "original_name": "Vitamin D",
                    "amount": 25,
                    "unit": "μg",
                    "confidence": 0.9,
                    "source": "ollama_structured",
                }
            ],
        }
    )

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "원재료명 및 함량 비타민 D 25mcg",
        "paddleocr_local",
        0.74,
        _settings(),
        parser=_FakeParser(llm_result),
    )

    candidates = record.parsed_snapshot["ingredient_candidates"]
    vit_d = [c for c in candidates if c["display_name"] == "비타민 D"]
    assert len(vit_d) == 1
    assert vit_d[0]["unit"] == "ug"
    assert vit_d[0]["amount"] == 25


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_degrades_when_fallback_exceeds_max() -> None:
    """Over-limit fallback enrichment degrades to a recoverable error, not a raw 500.

    Regression: when the LLM already returns the maximum number of ingredient
    candidates, the deterministic OCR-pattern fallback can append one more, pushing the
    structured result past the schema's ``max_length``. ``model_validate`` then raises a
    raw ``pydantic`` ``ValidationError`` that previously escaped this service and
    surfaced as HTTP 500 on the legacy per-image analyze-multi path. The service must
    translate it into the recoverable ``SupplementParserInputError`` so callers degrade
    to ``parser_used=False`` with a warning instead.
    """
    settings = _settings()
    record = _analysis_run()
    fake_session = _FakeParserSession(record)
    max_candidates = settings.supplement_parser_max_ingredients
    maxed_result = SupplementStructuredParseResult.model_validate(
        {
            "ingredient_candidates": [
                {
                    "display_name": f"성분{index}",
                    "amount": 1,
                    "unit": "mg",
                    "confidence": 0.9,
                }
                for index in range(max_candidates)
            ],
            "missing_required_sections": [],
            "low_confidence_fields": [],
            "warnings": [],
        }
    )

    with pytest.raises(SupplementParserInputError):
        await parse_supplement_analysis_ocr_text(
            cast(AsyncSession, fake_session),
            _user(),
            record.id,
            # An amount-pattern ingredient line the LLM result omitted; the fallback
            # merge appends it, pushing the candidate list to max + 1.
            "아연\t10 mg\t50%",
            "paddleocr_local",
            0.74,
            settings,
            parser=_FakeParser(maxed_result),
        )

    # Degraded before any preview write committed.
    assert fake_session.committed is False
    assert record.status == SupplementAnalysisStatus.REQUIRES_CONFIRMATION.value


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_pairs_split_name_and_amount_lines() -> None:
    """Verify OCR table cells split across lines still preserve visible amounts."""
    record = _analysis_run()
    fake_session = _FakeParserSession(record)

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "\n".join(
            [
                "Supplement Facts",
                "Vitamin C",
                "1,000 mg",
                "Zinc",
                "15 ㎎",
                "Serving Size",
                "2 capsules",
            ]
        ),
        "clova_ocr",
        0.82,
        _settings(),
        parser=_FakeParser(_empty_parse_result()),
    )

    candidates = record.parsed_snapshot["ingredient_candidates"]
    assert candidates[:2] == [
        {
            "display_name": "Vitamin C",
            "original_name": "Vitamin C",
            "amount": 1000.0,
            "unit": "mg",
            "confidence": 0.55,
            "source": "ocr_pattern_fallback",
        },
        {
            "display_name": "Zinc",
            "original_name": "Zinc",
            "amount": 15.0,
            "unit": "mg",
            "confidence": 0.55,
            "source": "ocr_pattern_fallback",
        },
    ]
    assert "Serving Size" not in {candidate["display_name"] for candidate in candidates}


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_promotes_intake_instruction_text() -> None:
    """Verify dosage rows are shown as intake method, not ingredient candidates."""
    record = _analysis_run()
    fake_session = _FakeParserSession(record)

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "\n".join(
            [
                "제품명 삼대오백 퓨어카보린 체리레몬향",
                "일 1 회,1 회 1 스푼( 26 g",
                "원재료명: 팔라티노스, 알룰로스",
            ]
        ),
        "paddleocr_local",
        0.87,
        _settings(),
        parser=_FakeParser(_empty_parse_result()),
    )

    candidate_names = {
        candidate["display_name"] for candidate in record.parsed_snapshot["ingredient_candidates"]
    }
    assert "일 1 회,1 회 1 스푼(" not in candidate_names
    assert {"팔라티노스", "알룰로스"} <= candidate_names
    assert record.parsed_snapshot["intake_method"]["text"] == "일 1 회,1 회 1 스푼( 26 g"
    assert record.parsed_snapshot["intake_method"]["requires_review"] is True
    assert "intake_method" not in record.parsed_snapshot["missing_required_sections"]
    assert "ocr_intake_method_fallback_requires_review" in record.warnings
    assert "ocr_text" not in record.parsed_snapshot


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_promotes_precaution_and_allergy_text() -> None:
    """Verify warning/allergen OCR lines fill the precautions section."""
    record = _analysis_run()
    fake_session = _FakeParserSession(record)

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "\n".join(
            [
                "제품명 테스트 영양제",
                "주의사항 임산부는 전문가와 상담 후 섭취하세요.",
                "알레르기 유발물질: 우유, 대두 함유",
            ]
        ),
        "paddleocr_local",
        0.88,
        _settings(),
        parser=_FakeParser(_empty_parse_result()),
    )

    precautions = record.parsed_snapshot["precautions"]
    assert [item["text"] for item in precautions] == [
        "주의사항 임산부는 전문가와 상담 후 섭취하세요.",
        "알레르기 유발물질: 우유, 대두 함유",
    ]
    assert precautions[0]["category"] == "pregnancy"
    assert precautions[0]["severity"] == "caution"
    assert precautions[1]["category"] == "allergy"
    assert "precautions" not in record.parsed_snapshot["missing_required_sections"]
    assert "ocr_precaution_fallback_requires_review" in record.warnings
    assert "ocr_text" not in record.parsed_snapshot


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_ignores_serving_and_contact_rows() -> None:
    """Verify serving/package and customer-service rows are not section facts."""
    record = _analysis_run()
    fake_session = _FakeParserSession(record)

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "\n".join(
            [
                "Serving Size 1 Tablet",
                "Servings Per Container 60",
                "60 capsules",
                "고객상담실 080-000-0000",
            ]
        ),
        "paddleocr_local",
        0.88,
        _settings(),
        parser=_FakeParser(_empty_parse_result()),
    )

    assert "text" not in record.parsed_snapshot["intake_method"]
    assert record.parsed_snapshot["precautions"] == []
    assert "intake_method" in record.parsed_snapshot["missing_required_sections"]
    assert "precautions" in record.parsed_snapshot["missing_required_sections"]
    assert "ocr_text" not in record.parsed_snapshot


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_mines_ingredient_declaration_names() -> None:
    """Verify a 원재료명-only label yields name-only candidates without amounts.

    This is the safety-sensitive path: an ingredient declaration list (no facts
    table) must still produce ingredient NAME candidates, each with amount/unit
    left null, marked ``source=ingredient_declaration``, with excipients dropped,
    and without the parser fabricating any amount.
    """
    record = _analysis_run()
    fake_session = _FakeParserSession(record)

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "[원재료명] 이노시톨, 레몬과즙분말, 카롬추출분말, 구연산, 효소처리스테비아, 젤라틴",
        "paddleocr_local",
        0.93,
        _settings(),
        parser=_FakeParser(_empty_parse_result()),
    )

    candidates = record.parsed_snapshot["ingredient_candidates"]
    assert candidates, "expected name-only candidates from the 원재료명 declaration"
    names = {candidate["display_name"] for candidate in candidates}
    assert "이노시톨" in names
    assert "효소처리스테비아" in names
    # Excipient dropped via the shared denylist.
    assert "젤라틴" not in names
    # Name-only: no fabricated amount/unit, declaration provenance recorded.
    for candidate in candidates:
        assert candidate["source"] == "ingredient_declaration"
        assert "amount" not in candidate or candidate["amount"] is None
        assert "unit" not in candidate or candidate["unit"] is None
    # A clear "names only, confirm amounts" review signal is surfaced. (The
    # ingredient.amount_missing warning is produced only for LLM-stage candidates,
    # before the declaration merge; the declaration warning is the right signal.)
    assert "ingredient_declaration_names_only_requires_review" in record.warnings
    assert "ingredient_candidates" in record.parsed_snapshot["low_confidence_fields"]
    assert "ocr_text" not in record.parsed_snapshot


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_merges_split_name_amount_unit_lines() -> None:
    """Verify OCR split as ingredient/name, amount, unit lines still carries amounts."""
    record = _analysis_run()
    fake_session = _FakeParserSession(record)

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "비타민 C\n100\nmg 167%\n아연\n8\nmg",
        "paddleocr_local",
        0.93,
        _settings(),
        parser=_FakeParser(_empty_parse_result()),
    )

    by_name = {
        candidate["display_name"]: candidate
        for candidate in record.parsed_snapshot["ingredient_candidates"]
    }

    assert by_name["비타민 C"]["amount"] == 100
    assert by_name["비타민 C"]["unit"] == "mg"
    assert by_name["비타민 C"]["daily_value_percent"] == 167
    assert by_name["아연"]["amount"] == 8
    assert by_name["아연"]["unit"] == "mg"
    assert all(candidate["source"] == "ocr_pattern_fallback" for candidate in by_name.values())
    assert "ocr_pattern_fallback_requires_review" in record.warnings
    assert "ocr_text" not in record.parsed_snapshot


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_accepts_korean_unit_variants() -> None:
    """Verify facts-table unit aliases are normalized from visible OCR text."""
    record = _analysis_run()
    fake_session = _FakeParserSession(record)

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "\n".join(
            [
                "Other Ingredients Vitamin B12 500 마이크로그램",
                "유산균 10 씨에프유",
                "비타민 D 1000 아이유",
            ]
        ),
        "paddleocr_local",
        0.93,
        _settings(),
        parser=_FakeParser(_empty_parse_result()),
    )

    by_name = {
        candidate["display_name"]: candidate
        for candidate in record.parsed_snapshot["ingredient_candidates"]
    }

    assert by_name["Vitamin B12"]["amount"] == 500
    assert by_name["Vitamin B12"]["unit"] == "ug"
    assert by_name["유산균"]["amount"] == 10
    assert by_name["유산균"]["unit"] == "CFU"
    assert by_name["비타민 D"]["amount"] == 1000
    assert by_name["비타민 D"]["unit"] == "IU"
    assert "Other Ingredients" not in by_name
    assert "ocr_pattern_fallback_requires_review" in record.warnings
    assert "ocr_text" not in record.parsed_snapshot


@pytest.mark.asyncio
async def test_ingredient_declaration_does_not_override_facts_amounts() -> None:
    """Verify facts-table amounts win and the declaration adds only new names.

    When the same name appears both in a facts-table candidate (with an amount)
    and in the 원재료명 declaration, the amount-bearing candidate must be kept and
    no duplicate name-only row is added. New declaration-only names may still be
    appended.
    """
    record = _analysis_run()
    fake_session = _FakeParserSession(record)

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "비타민 D 25mcg\n원재료명: 비타민 D, 이노시톨",
        "paddleocr_local",
        0.93,
        _settings(),
        parser=_FakeParser(_parse_result()),
    )

    candidates = record.parsed_snapshot["ingredient_candidates"]
    by_name = {candidate["display_name"]: candidate for candidate in candidates}
    # The LLM-provided 비타민 D (with amount) is kept and NOT replaced/duplicated.
    assert by_name["비타민 D"]["source"] == "ollama_structured"
    assert by_name["비타민 D"]["amount"] == 25
    assert sum(1 for c in candidates if c["display_name"] == "비타민 D") == 1
    # A declaration-only name is still added as name-only.
    assert "이노시톨" in by_name
    assert by_name["이노시톨"]["source"] == "ingredient_declaration"
    assert by_name["이노시톨"].get("amount") is None


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_does_not_duplicate_parser_candidate() -> None:
    """Verify OCR pattern fallback does not duplicate a parser-provided ingredient."""
    record = _analysis_run()

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, _FakeParserSession(record)),
        _user(),
        record.id,
        "비타민 D 25mcg",
        "paddleocr_local",
        0.91,
        _settings(),
        parser=_FakeParser(_parse_result()),
    )

    candidates = record.parsed_snapshot["ingredient_candidates"]
    assert len(candidates) == 1
    assert candidates[0]["source"] == "ollama_structured"


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_drops_llm_serving_size_candidates() -> None:
    """Verify LLM-emitted serving-size fragments never survive as ingredients."""
    record = _analysis_run()
    fake_session = _FakeParserSession(record)
    parser_result = SupplementStructuredParseResult.model_validate(
        {
            "parsed_product": {"product_name": "테스트 영양제", "serving_size": "1회 제공량 26g"},
            "ingredient_candidates": [
                {
                    "display_name": "1회제공량(",
                    "amount": 26,
                    "unit": "g",
                    "confidence": 0.72,
                    "source": "ollama_structured",
                },
                {
                    "display_name": "회 제공량",
                    "amount": 26,
                    "unit": "g",
                    "confidence": 0.71,
                    "source": "ollama_structured",
                },
                {
                    "display_name": "비타민 C",
                    "amount": 100,
                    "unit": "mg",
                    "confidence": 0.89,
                    "source": "ollama_structured",
                },
            ],
            "missing_required_sections": [],
            "low_confidence_fields": [],
            "warnings": [],
        }
    )

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "1회 제공량(26g)\n비타민 C 100 mg",
        "paddleocr_local",
        0.91,
        _settings(),
        parser=_FakeParser(parser_result),
    )

    candidates = record.parsed_snapshot["ingredient_candidates"]
    assert [candidate["display_name"] for candidate in candidates] == ["비타민 C"]
    assert candidates[0]["amount"] == 100
    assert "ingredient.non_ingredient_heading_filtered" in record.warnings


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_marks_vision_assist_input() -> None:
    """Verify vision-assist candidates stay identifiable as fallback preview input."""
    record = _analysis_run()
    fake_session = _FakeParserSession(record)

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, fake_session),
        _user(),
        record.id,
        "비타민 D 1000",
        "ollama_vision_assist",
        None,
        _settings(),
        parser=_FakeParser(_parse_result()),
    )

    assert record.ocr_provider == "ollama_vision_assist"
    assert record.parsed_snapshot["parser_metadata"]["input_provider"] == "ollama_vision_assist"
    assert any("Image-assisted text extraction" in warning for warning in record.warnings)


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_rejects_missing_owned_preview() -> None:
    """Verify parsing fails closed when the analysis row is not owner-visible."""
    fake_session = _FakeParserSession(None)

    with pytest.raises(SupplementAnalysisNotFoundError):
        await parse_supplement_analysis_ocr_text(
            cast(AsyncSession, fake_session),
            _user(),
            uuid4(),
            "비타민 D",
            "manual-test",
            None,
            _settings(),
            parser=_FakeParser(_parse_result()),
        )

    assert fake_session.committed is False


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_rejects_expired_preview() -> None:
    """Verify expired previews are not sent to the LLM parser."""
    record = _analysis_run(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    fake_parser = _FakeParser(_parse_result())

    with pytest.raises(SupplementAnalysisExpiredError):
        await parse_supplement_analysis_ocr_text(
            cast(AsyncSession, _FakeParserSession(record)),
            _user(),
            record.id,
            "비타민 D",
            "manual-test",
            None,
            _settings(),
            parser=fake_parser,
        )

    assert fake_parser.received_text is None


@pytest.mark.asyncio
async def test_parse_supplement_analysis_ocr_text_rejects_hash_conflict() -> None:
    """Verify a preview cannot be rebound to different OCR text."""
    record = _analysis_run(ocr_text_hash="b" * 64)
    fake_parser = _FakeParser(_parse_result())

    with pytest.raises(SupplementParserConflictError):
        await parse_supplement_analysis_ocr_text(
            cast(AsyncSession, _FakeParserSession(record)),
            _user(),
            record.id,
            "비타민 D",
            "manual-test",
            None,
            _settings(),
            parser=fake_parser,
        )

    assert fake_parser.received_text is None


def test_normalize_ocr_text_rejects_blank_or_oversized_text() -> None:
    """Verify OCR text input is bounded before the LLM adapter is invoked."""
    with pytest.raises(SupplementParserInputError):
        normalize_ocr_text(" \r\n ", 100)

    with pytest.raises(SupplementParserInputError):
        normalize_ocr_text("x" * 101, 100)


def test_normalize_ocr_text_prepares_units_for_llm_parser() -> None:
    """Verify OCR unit and Korean-English spacing noise is reduced before parsing."""
    assert normalize_ocr_text("엽산400ugDFE\r\n비타민D 25ug", 100) == (
        "엽산 400μg DFE\n비타민 D 25μg"
    )


def test_hash_ocr_text_depends_on_privacy_secret() -> None:
    """Verify OCR fingerprints are keyed HMACs rather than raw hashes."""
    first = hash_ocr_text("비타민 D", SecretStr("first-secret"))
    second = hash_ocr_text("비타민 D", SecretStr("second-secret"))

    assert first != second
    assert len(first) == 64
    assert len(second) == 64


def test_build_parsed_snapshot_omits_raw_ocr_text_when_not_retained() -> None:
    """Default (retain off): the normalized OCR text is never persisted."""
    snapshot = _build_parsed_snapshot(
        parse_result=_parse_result(),
        previous_snapshot={},
        ocr_confidence=None,
        ocr_provider="paddleocr",
        ocr_layout=None,
        settings=_settings(),
        ocr_text="비타민 D 1000\n비타민 D 25μg",
        retain_raw_ocr_text=False,
    )

    assert "raw_ocr_text" not in snapshot
    assert snapshot["parser_metadata"]["raw_ocr_text_stored"] is False


def test_build_parsed_snapshot_stores_raw_ocr_text_when_retained() -> None:
    """Retain on: the OCR text is kept at a top-level key while parser_metadata's
    privacy flag stays False so the snapshot invariants and upcast guard hold."""
    ocr_text = "비타민 D 1000\n비타민 D 25μg 100%"
    snapshot = _build_parsed_snapshot(
        parse_result=_parse_result(),
        previous_snapshot={},
        ocr_confidence=None,
        ocr_provider="paddleocr",
        ocr_layout=None,
        settings=_settings(),
        ocr_text=ocr_text,
        retain_raw_ocr_text=True,
    )

    assert snapshot["raw_ocr_text"] == ocr_text
    assert snapshot["parser_metadata"]["raw_ocr_text_stored"] is False
    # The legacy upcast guard only trips on parser_metadata.raw_ocr_text_stored, so a
    # snapshot carrying the sibling top-level key must still upcast without raising.
    upcast_legacy_parsed_snapshot(snapshot)


def test_build_parsed_snapshot_skips_blank_raw_ocr_text_when_retained() -> None:
    """Retain on but blank OCR text: nothing is stored (no empty key)."""
    snapshot = _build_parsed_snapshot(
        parse_result=_parse_result(),
        previous_snapshot={},
        ocr_confidence=None,
        ocr_provider="paddleocr",
        ocr_layout=None,
        settings=_settings(),
        ocr_text="   ",
        retain_raw_ocr_text=True,
    )

    assert "raw_ocr_text" not in snapshot


def _store_raw_settings() -> Settings:
    """Settings with the operator opt-in flag on (consent still gates storage)."""
    return Settings(
        privacy_hash_secret=SecretStr("test-privacy-secret"),
        _env_file=None,
        store_raw_ocr_text=True,
    )


@pytest.mark.asyncio
async def test_parse_stores_raw_ocr_text_when_flag_and_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flag on AND RAW_OCR_TEXT_RETENTION consent granted -> text retained."""

    async def _granted(*_args: object, **_kwargs: object) -> bool:
        return True

    monkeypatch.setattr("src.services.supplement_parser.has_active_consent", _granted)
    record = _analysis_run()

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, _FakeParserSession(record)),
        _user(),
        record.id,
        "비타민 D 1000\n비타민 D 25 ug",
        "paddleocr",
        0.9,
        _store_raw_settings(),
        parser=_FakeParser(_parse_result()),
    )

    assert record.parsed_snapshot["raw_ocr_text"]
    assert record.parsed_snapshot["parser_metadata"]["raw_ocr_text_stored"] is False


@pytest.mark.asyncio
async def test_parse_omits_raw_ocr_text_without_consent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flag on but consent absent -> text NOT retained (per-user opt-in honored)."""

    async def _absent(*_args: object, **_kwargs: object) -> bool:
        return False

    monkeypatch.setattr("src.services.supplement_parser.has_active_consent", _absent)
    record = _analysis_run()

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, _FakeParserSession(record)),
        _user(),
        record.id,
        "비타민 D 1000\n비타민 D 25 ug",
        "paddleocr",
        0.9,
        _store_raw_settings(),
        parser=_FakeParser(_parse_result()),
    )

    assert "raw_ocr_text" not in record.parsed_snapshot


@pytest.mark.asyncio
async def test_parse_skips_consent_check_when_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flag off -> consent is never queried and nothing is retained."""
    called = False

    async def _tracker(*_args: object, **_kwargs: object) -> bool:
        nonlocal called
        called = True
        return True

    monkeypatch.setattr("src.services.supplement_parser.has_active_consent", _tracker)
    record = _analysis_run()

    await parse_supplement_analysis_ocr_text(
        cast(AsyncSession, _FakeParserSession(record)),
        _user(),
        record.id,
        "비타민 D 1000\n비타민 D 25 ug",
        "paddleocr",
        0.9,
        _settings(),
        parser=_FakeParser(_parse_result()),
    )

    assert "raw_ocr_text" not in record.parsed_snapshot
    assert called is False
