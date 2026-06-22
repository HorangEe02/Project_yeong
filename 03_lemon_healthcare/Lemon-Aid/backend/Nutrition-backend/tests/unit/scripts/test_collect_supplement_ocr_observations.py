"""Tests for redacted supplement OCR observation collection helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from src.models.schemas.supplement_parser import SupplementStructuredParseResult

from scripts import collect_supplement_ocr_observations as collector


class _SuccessfulParser:
    """Fake local parser returning a schema-valid structured result."""

    async def parse_supplement_ocr_text(self, _ocr_text: str) -> SupplementStructuredParseResult:
        """Return a parser result using the current schema shape."""
        return SupplementStructuredParseResult.model_validate(
            {
                "parsed_product": {
                    "product_name": "테스트 비타민",
                    "serving_size": "1정",
                },
                "ingredient_candidates": [
                    {
                        "display_name": "비타민 D",
                        "original_name": "Vitamin D",
                        "amount": 1000,
                        "unit": "IU",
                        "confidence": 0.91,
                    }
                ],
            }
        )


class _TransientClientParser(_SuccessfulParser):
    """Fake parser that fails with a transient client error before success."""

    def __init__(self, failures_before_success: int) -> None:
        """Initialize the number of transient client failures."""
        self.failures_before_success = failures_before_success
        self.calls = 0

    async def parse_supplement_ocr_text(self, ocr_text: str) -> SupplementStructuredParseResult:
        """Raise transient client errors before returning a schema-valid result."""
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise collector.OllamaClientError("transport unavailable")
        return await super().parse_supplement_ocr_text(ocr_text)


class _AlwaysClientErrorParser:
    """Fake parser that always fails with a local Ollama client error."""

    def __init__(self) -> None:
        """Initialize call accounting."""
        self.calls = 0

    async def parse_supplement_ocr_text(self, _ocr_text: str) -> SupplementStructuredParseResult:
        """Raise a client error without exposing OCR text."""
        self.calls += 1
        raise collector.OllamaClientError("transport unavailable")


@pytest.mark.asyncio
async def test_attach_llm_parse_records_schema_v2_candidates() -> None:
    """Verify LLM parse observations follow SupplementStructuredParseResult."""
    row: dict[str, object] = {}

    await collector._attach_llm_parse(
        row=row,
        ocr_result=collector.OCRResult(text="synthetic OCR text", provider="paddleocr_local"),
        llm_parser=_SuccessfulParser(),  # type: ignore[arg-type]
    )

    assert row["llm_parse_status"] == "completed"
    assert row["llm_parsed_ingredient_count"] == 1
    assert row["llm_parsed_ingredients"] == [
        {
            "display_name": "비타민 D",
            "original_name": "Vitamin D",
            "nutrient_code": None,
            "amount": 1000.0,
            "unit": "IU",
            "confidence": 0.91,
            "source": "ollama_structured",
        }
    ]
    assert row["llm_parsed_product_name_present"] is True
    assert row["llm_parsed_serving_size_text_present"] is True

    serialized = json.dumps(row, ensure_ascii=False).lower()
    assert "raw_ocr_text" not in serialized
    assert "raw_model_response" not in serialized


@pytest.mark.asyncio
async def test_attach_llm_parse_retries_transient_client_error() -> None:
    """Verify transient Ollama transport failures are retried without raw text."""
    row: dict[str, object] = {}
    parser = _TransientClientParser(failures_before_success=1)

    await collector._attach_llm_parse(
        row=row,
        ocr_result=collector.OCRResult(text="synthetic OCR text", provider="paddleocr_local"),
        llm_parser=parser,  # type: ignore[arg-type]
        retry_delays_seconds=(0.0,),
    )

    assert parser.calls == 2
    assert row["llm_parse_status"] == "completed"
    assert row["llm_parse_attempt_count"] == 2
    assert row["llm_parse_retry_count"] == 1
    assert row["llm_parsed_ingredient_count"] == 1
    serialized = json.dumps(row, ensure_ascii=False).lower()
    assert "synthetic ocr text" not in serialized
    assert "raw_model_response" not in serialized


@pytest.mark.asyncio
async def test_attach_llm_parse_records_bounded_retry_failure() -> None:
    """Verify exhausted Ollama retries record only bounded failure metadata."""
    row: dict[str, object] = {}
    parser = _AlwaysClientErrorParser()

    await collector._attach_llm_parse(
        row=row,
        ocr_result=collector.OCRResult(text="synthetic OCR text", provider="paddleocr_local"),
        llm_parser=parser,  # type: ignore[arg-type]
        retry_delays_seconds=(0.0, 0.0),
    )

    assert parser.calls == 3
    assert row == {
        "llm_parse_status": "error",
        "llm_parse_error_code": "ollama_client",
        "llm_parse_attempt_count": 3,
        "llm_parse_retry_count": 2,
    }


def _write_manifest_with_image(
    tmp_path: Path,
    *,
    contains_personal_data: object,
) -> Path:
    """Write a minimal local OCR manifest and matching image bytes."""
    image_path = tmp_path / "review.jpg"
    image_path.write_bytes(b"not-real-image-but-sha-valid")
    manifest_path = tmp_path / "manifest.jsonl"
    row = {
        "fixture_id": "review-1",
        "image_path": str(image_path),
        "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        "license_status": "team_approved",
        "consent_status": "team_approved",
        "section": "review",
        "contains_personal_data": contains_personal_data,
        "pii_screening_status": "pending_local_screening",
        "external_transfer_allowed": False,
        "local_processing_allowed": True,
        "expected": {},
    }
    manifest_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest_path


def test_read_fixture_manifest_allows_review_local_pii_screening(tmp_path: Path) -> None:
    """Verify review rows pending PII screening are local PaddleOCR only."""
    manifest_path = _write_manifest_with_image(tmp_path, contains_personal_data=None)

    fixtures = collector._read_fixture_manifest(
        manifest_path,
        providers=("paddleocr_local",),
    )

    assert len(fixtures) == 1
    assert collector._requires_local_pii_screening(fixtures[0]) is True


def test_read_fixture_manifest_blocks_review_pii_for_external_provider(tmp_path: Path) -> None:
    """Verify pending review PII rows cannot be sent to external OCR providers."""
    manifest_path = _write_manifest_with_image(tmp_path, contains_personal_data=None)

    with pytest.raises(ValueError, match="local PII-screening only"):
        collector._read_fixture_manifest(
            manifest_path,
            providers=("clova_ocr",),
        )


def test_read_fixture_manifest_resolves_allowlisted_env_image_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify tokenized image roots avoid storing local absolute paths."""
    image_root = tmp_path / "source"
    image_path = image_root / "detail.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"not-real-image-but-sha-valid")
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(image_root))
    manifest_path = tmp_path / "manifest.jsonl"
    row = {
        "fixture_id": "detail-1",
        "image_path": "$NAVER_TAMPERMONKEY_SOURCE_ROOT/detail.jpg",
        "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        "license_status": "team_approved",
        "consent_status": "team_approved",
        "contains_personal_data": False,
        "external_transfer_allowed": True,
        "local_processing_allowed": True,
        "expected": {},
    }
    manifest_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    fixtures = collector._read_fixture_manifest(
        manifest_path,
        providers=("paddleocr_local",),
    )

    assert fixtures[0].image_path == image_path.resolve()


def test_read_fixture_manifest_rejects_env_symlink_escape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify tokenized image paths cannot resolve outside the configured root."""
    image_root = tmp_path / "source"
    image_root.mkdir()
    escaped_image = tmp_path / "escaped.jpg"
    escaped_image.write_bytes(b"not-real-image-but-sha-valid")
    link_path = image_root / "linked.jpg"
    link_path.symlink_to(escaped_image)
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(image_root))
    manifest_path = tmp_path / "manifest.jsonl"
    row = {
        "fixture_id": "detail-1",
        "image_path": "$NAVER_TAMPERMONKEY_SOURCE_ROOT/linked.jpg",
        "image_sha256": hashlib.sha256(escaped_image.read_bytes()).hexdigest(),
        "license_status": "team_approved",
        "consent_status": "team_approved",
        "contains_personal_data": False,
        "external_transfer_allowed": True,
        "local_processing_allowed": True,
        "expected": {},
    }
    manifest_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="resolve under the image root"):
        collector._read_fixture_manifest(
            manifest_path,
            providers=("paddleocr_local",),
        )


def test_read_fixture_manifest_rejects_unallowlisted_env_image_path(tmp_path: Path) -> None:
    """Verify arbitrary env-variable paths are not accepted from manifests."""
    image_path = tmp_path / "detail.jpg"
    image_path.write_bytes(b"not-real-image-but-sha-valid")
    manifest_path = tmp_path / "manifest.jsonl"
    row = {
        "fixture_id": "detail-1",
        "image_path": "$HOME/detail.jpg",
        "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        "license_status": "team_approved",
        "consent_status": "team_approved",
        "contains_personal_data": False,
        "external_transfer_allowed": True,
        "local_processing_allowed": True,
        "expected": {},
    }
    manifest_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="env is not allowlisted"):
        collector._read_fixture_manifest(
            manifest_path,
            providers=("paddleocr_local",),
        )


def test_pii_candidate_flags_are_bounded_tokens() -> None:
    """Verify local PII screening records flag names, not matched text."""
    flags = collector._pii_candidate_flags(
        "주문번호 1234567890 / 010-1234-5678 / user@example.com / 서울로 12"
    )

    assert flags == [
        "email_candidate",
        "phone_candidate",
        "order_number_candidate",
        "address_candidate",
    ]
    serialized = json.dumps(flags, ensure_ascii=False)
    assert "010-1234-5678" not in serialized
    assert "user@example.com" not in serialized


def test_extract_ingredient_candidates_rejects_packaging_quantity_tokens() -> None:
    """Verify auto-expected seeding does not create ingredients from package counts."""
    candidates = collector._extract_ingredient_candidates(
        "\n".join(
            [
                "정x 3개입( 72g",
                "g X30포( 180g",
                "건강기능식품 500mg",
                "비타민 D 25mcg",
            ]
        )
    )

    assert candidates == [
        {
            "name": "비타민 D",
            "amount": 25,
            "unit": "mcg",
            "expected_source": "google_vision_auto_seed",
            "verification_status": "provisional",
        }
    ]


def test_matched_expected_ingredients_reads_v3_name_fields() -> None:
    """Verify V3 expected display/normalized names are matched safely."""
    normalized_text = collector._normalize_text("비타민 C 1000 mg zinc 15 mg")
    expected = {
        "ingredients": [
            {"display_name": "비타민 C", "amount": 1000, "unit": "mg"},
            {"normalized_name": "zinc", "amount": 15, "unit": "mg"},
        ]
    }

    parsed = collector._matched_expected_ingredients(normalized_text, expected)

    assert parsed == [
        {"name": "비타민 C", "amount": 1000, "unit": "mg"},
        {"name": "zinc", "amount": 15, "unit": "mg"},
    ]
    serialized = json.dumps(parsed, ensure_ascii=False).lower()
    assert "raw_ocr_text" not in serialized
    assert "provider_payload" not in serialized


def test_build_reference_text_reads_v3_name_fields() -> None:
    """Verify language metrics can use V3 expected names without raw text."""
    reference = collector._build_reference_text(
        {
            "ingredients": [
                {"display_name": "비타민 C", "amount": 1000, "unit": "mg"},
                {"normalized_name": "zinc"},
            ]
        }
    )

    assert reference == "비타민 C 1000 mg zinc"


def test_attach_text_extraction_metrics_uses_full_text_without_raw_storage() -> None:
    """Verify target-gate metrics are attached without persisting OCR text."""
    row: dict[str, object] = {"warning_codes": []}

    collector._attach_text_extraction_metrics(
        row=row,
        ocr_result=collector.OCRResult(text="Vitamin C 500 mg", provider="paddleocr_local"),
        expected={
            "verification_status": "human_reviewed",
            "text": "Vitamin C 500 mg",
        },
    )

    assert row["metric_source"] == "in_memory_provider_result"
    assert row["text_metric_reference_source"] == "expected.text"
    assert row["normalized_text_precision"] == 1.0
    assert row["normalized_text_recall"] == 1.0
    assert row["normalized_text_f1"] == 1.0
    serialized = json.dumps(row, ensure_ascii=False).lower()
    assert "vitamin" not in serialized
    assert "raw_ocr_text" not in serialized
    assert "provider_payload" not in serialized


def test_attach_text_extraction_metrics_scores_precision_and_recall() -> None:
    """Verify extra and missing OCR characters affect target-gate metrics."""
    row: dict[str, object] = {}

    collector._attach_text_extraction_metrics(
        row=row,
        ocr_result=collector.OCRResult(text="abcxyz", provider="paddleocr_local"),
        expected={
            "verification_status": "human_reviewed",
            "text": "abc",
        },
    )

    assert row["matched_char_count"] == 3
    assert row["reference_char_count"] == 3
    assert row["hypothesis_char_count"] == 6
    assert row["normalized_text_precision"] == 0.5
    assert row["normalized_text_recall"] == 1.0
    assert row["normalized_text_f1"] == 0.6667


def test_attach_text_extraction_metrics_uses_structured_expected_fallback() -> None:
    """Verify structured expected sections can be scored for gate metrics."""
    row: dict[str, object] = {}

    collector._attach_text_extraction_metrics(
        row=row,
        ocr_result=collector.OCRResult(
            text="ZMA Magnesium 100 mg Take daily Consult pharmacist",
            provider="paddleocr_local",
        ),
        expected={
            "verification_status": "human_reviewed",
            "product_name": "ZMA",
            "ingredients": [{"display_name": "Magnesium", "amount": 100, "unit": "mg"}],
            "intake_method": {"text": "Take daily"},
            "precautions": [{"text": "Consult pharmacist"}],
        },
    )

    assert row["text_metric_reference_source"] == "expected.structured_sections"
    assert row["normalized_text_f1"] == 1.0


def test_matched_expected_ingredients_splits_compound_v3_names() -> None:
    """Verify comma-joined V3 expected names are matched individually."""
    normalized_text = collector._normalize_text("비타민K 비타민D 엽산")
    expected = {
        "ingredients": [
            {"display_name": "비타민K,비타민D,비타민B6,엽산,비타민B12"},
        ]
    }

    parsed = collector._matched_expected_ingredients(normalized_text, expected)

    assert parsed == [
        {"name": "비타민K"},
        {"name": "비타민D"},
        {"name": "엽산"},
    ]


def test_matched_expected_ingredients_uses_bounded_name_aliases() -> None:
    """Verify expected ingredient aliases match OCR variants without raw storage."""
    normalized_text = collector._normalize_text(
        "비타민 K2 100 ug / 마카 400 mg / Olive Oil / EPA DHA"
    )
    expected = {
        "ingredients": [
            {"display_name": "초임계비타민K2"},
            {"display_name": "검은 마카", "amount": 400, "unit": "mg"},
            {"display_name": "Extra virgin olive oil"},
            {"display_name": "Omega-3 Fatty Acids (EPA & DHA)"},
        ]
    }

    parsed = collector._matched_expected_ingredients(normalized_text, expected)

    assert parsed == [
        {"name": "초임계비타민K2"},
        {"name": "검은 마카", "amount": 400, "unit": "mg"},
        {"name": "Extra virgin olive oil"},
        {"name": "Omega-3 Fatty Acids (EPA & DHA)"},
    ]
    serialized = json.dumps(parsed, ensure_ascii=False).lower()
    assert "raw_ocr_text" not in serialized
    assert "provider_payload" not in serialized


def test_matched_expected_ingredients_does_not_overmatch_generic_oil_alias() -> None:
    """Verify descriptor aliases do not collapse to broad generic words."""
    normalized_text = collector._normalize_text("fish oil 1000 mg")
    expected = {"ingredients": [{"display_name": "Extra virgin olive oil"}]}

    parsed = collector._matched_expected_ingredients(normalized_text, expected)

    assert parsed == []


def test_expected_ingredient_names_do_not_split_dose_bearing_rows() -> None:
    """Verify dose-bearing ingredient rows keep one expected display name."""
    names = collector._expected_ingredient_names(
        {"display_name": "비타민K,비타민D", "amount": 1000, "unit": "mg"}
    )

    assert names == ["비타민K,비타민D"]


def test_safe_error_code_preserves_google_status_without_details() -> None:
    """Verify provider error status is useful but bounded."""
    error = collector.OCRError("Google Vision OCR provider error: PERMISSION_DENIED")

    assert collector._safe_error_code(error) == "ocr_provider_error_permission_denied"


def test_safe_error_code_sanitizes_http_status() -> None:
    """Verify HTTP status is preserved without provider payload text."""
    error = collector.OCRError("Google Vision OCR request failed: status 403.")

    assert collector._safe_error_code(error) == "ocr_http_status_403"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (
            "PaddleOCR is not installed. Install backend .[ocr-local].",
            "ocr_dependency_missing",
        ),
        ("PaddleOCR predictor initialization failed.", "ocr_provider_initialization"),
        ("PaddleOCR provider prediction failed.", "ocr_provider_prediction_failed"),
        ("PaddleOCR temporary image write failed.", "image_write_error"),
        ("PaddleOCR returned no readable text.", "ocr_empty_text"),
        (
            "PaddleOCR confidence is below LOCAL_OCR_CONFIDENCE_THRESHOLD.",
            "ocr_low_confidence",
        ),
        (
            "ENABLE_LOCAL_OCR=true is required for PaddleOCR fallback.",
            "local_ocr_disabled",
        ),
        ("OCR fixture image is missing.", "image_missing"),
        ("OCR fixture image cannot be read.", "image_read_error"),
        ("OCR fixture image cannot be decoded.", "image_decode_error"),
    ],
)
def test_safe_error_code_maps_paddleocr_failures_without_details(
    message: str,
    expected: str,
) -> None:
    """Verify PaddleOCR failures become stable bounded categories."""
    assert collector._safe_error_code(collector.OCRError(message)) == expected
