"""Tests for OCR 3-tier fixture evaluation report generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import evaluate_ocr_three_tier as evaluate


def _write_manifest(path: Path, rows: list[dict[str, object]]) -> None:
    """Write a JSONL manifest.

    Args:
        path: Destination path.
        rows: Manifest rows.
    """
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_evaluate_manifest_returns_redacted_provider_metrics(tmp_path: Path) -> None:
    """Verify provider observations are aggregated without raw artifacts."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest_path,
        [
            {
                "fixture_id": "fixture-1",
                "image_path": "images/missing.png",
                "expected": {"ingredients": [{"name": "vitamin c"}]},
                "observations": [
                    {
                        "provider": "google_vision_document",
                        "latency_ms": 100,
                        "text_non_empty": True,
                        "parser_success": True,
                        "parsed_ingredients": [{"name": "vitamin c"}],
                    }
                ],
            }
        ],
    )

    summary = evaluate.evaluate_manifest(manifest_path)

    providers = summary["providers"]
    assert isinstance(providers, dict)
    google_metrics = providers["google_vision_document"]
    assert isinstance(google_metrics, dict)
    assert google_metrics["calls"] == 1
    assert google_metrics["text_non_empty_rate"] == 1.0
    assert google_metrics["ingredient_name_exact_rate"] == 1.0
    assert summary["manifest"] == "manifest.jsonl"
    assert "manifest_path_hash" in summary
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
    assert summary["missing_image_count"] == 1
    assert summary["raw_artifacts_stored"] is False
    assert summary["raw_ocr_text_stored"] is False


def test_evaluate_manifest_resolves_allowlisted_env_image_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify env-token image references do not create false missing-image counts."""
    image_root = tmp_path / "images"
    image_root.mkdir()
    image_path = image_root / "fixture.jpg"
    image_path.write_bytes(b"image-bytes")
    monkeypatch.setenv("SUPPLEMENT_OCR_FIXTURE_ROOT", str(image_root))
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest_path,
        [
            {
                "fixture_id": "fixture-1",
                "image_path": "$SUPPLEMENT_OCR_FIXTURE_ROOT/fixture.jpg",
                "expected": {"ingredients": [{"name": "vitamin c"}]},
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "text_non_empty": True,
                        "parser_success": True,
                        "parsed_ingredients": [{"name": "vitamin c"}],
                    }
                ],
            }
        ],
    )

    summary = evaluate.evaluate_manifest(manifest_path)

    assert summary["missing_image_count"] == 0
    assert str(image_root) not in json.dumps(summary, ensure_ascii=False)


def test_evaluate_manifest_rejects_raw_ocr_text(tmp_path: Path) -> None:
    """Verify raw OCR text cannot enter report manifests."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest_path,
        [
            {
                "fixture_id": "fixture-1",
                "observations": [{"provider": "google_vision_document", "raw_ocr_text": "secret"}],
            }
        ],
    )

    with pytest.raises(ValueError, match="raw_ocr_text"):
        evaluate.evaluate_manifest(manifest_path)


def test_evaluate_manifest_rejects_provider_payload(tmp_path: Path) -> None:
    """Verify provider payloads cannot enter report manifests."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest_path,
        [
            {
                "fixture_id": "fixture-1",
                "observations": [
                    {
                        "provider": "google_vision_document",
                        "provider_payload": {"raw": "do-not-store"},
                    }
                ],
            }
        ],
    )

    with pytest.raises(ValueError, match="provider_payload"):
        evaluate.evaluate_manifest(manifest_path)


def test_evaluate_manifest_records_llm_metrics_separately(tmp_path: Path) -> None:
    """Verify LLM parser metrics are aggregated independently from OCR matches."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest_path,
        [
            {
                "fixture_id": "fixture-1",
                "expected": {
                    "ingredients": [{"name": "vitamin c"}, {"name": "zinc"}],
                },
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "latency_ms": 200,
                        "text_non_empty": True,
                        "parser_success": True,
                        # OCR regex 매칭은 1/2 (vitamin c만 잡힘)
                        "parsed_ingredients": [{"name": "vitamin c"}],
                        # LLM 파서는 2/2 모두 잡음 (실제 schema 는 display_name 사용)
                        "llm_parse_status": "completed",
                        "llm_parsed_ingredients": [
                            {"display_name": "vitamin c", "normalized_name": "vitamin c"},
                            {"display_name": "zinc", "normalized_name": "zinc"},
                        ],
                    }
                ],
            }
        ],
    )

    summary = evaluate.evaluate_manifest(manifest_path)
    providers = summary["providers"]
    assert isinstance(providers, dict)
    metrics = providers["paddleocr_local"]
    assert isinstance(metrics, dict)
    # OCR 메트릭과 LLM 메트릭이 독립적으로 계산됨
    assert metrics["ingredient_name_exact_rate"] == 0.5
    assert metrics["llm_ingredient_name_exact_rate"] == 1.0
    assert metrics["llm_parse_attempt_count"] == 1
    assert metrics["llm_parse_success_rate"] == 1.0


def test_evaluate_manifest_reports_structured_v3_metrics(tmp_path: Path) -> None:
    """Verify V3 section/intake/claim metrics are benchmarked without raw text."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest_path,
        [
            {
                "fixture_id": "fixture-1",
                "expected": {
                    "ingredients": [
                        {"display_name": "Vitamin D", "amount": 25, "unit": "mcg"},
                        {"display_name": "Zinc", "amount": 10, "unit": "mg"},
                    ],
                    "label_sections": [
                        {"section_type": "supplement_facts"},
                        {"section_type": "intake_method"},
                    ],
                    "intake_method": {"text": "1일 1정"},
                    "precautions": [{"text": "임산부는 전문가와 상담"}],
                    "functional_claims": [{"text": "뼈 건강에 필요"}],
                },
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "status": "completed",
                        "text_non_empty": True,
                        "parser_success": True,
                        "parsed_ingredients": [
                            {
                                "display_name": "Vitamin D",
                                "amount": 25,
                                "unit": "mcg",
                            },
                            {
                                "display_name": "Magnesium",
                                "amount": 10,
                                "unit": "mg",
                            },
                        ],
                        "label_sections": [{"section_type": "supplement_facts"}],
                        "intake_method": {"text": "1일 1정"},
                        "functional_claims": [{"text": "뼈 건강에 필요"}],
                    }
                ],
            }
        ],
    )

    summary = evaluate.evaluate_manifest(manifest_path)
    metrics = summary["providers"]["paddleocr_local"]  # type: ignore[index]
    assert isinstance(metrics, dict)
    assert metrics["ingredient_name_exact_rate"] == 0.5
    assert metrics["ingredient_amount_unit_exact_rate"] == 0.5
    assert metrics["ingredient_false_hallucination_rate"] == 0.5
    assert metrics["intake_method_extraction_rate"] == 1.0
    assert metrics["precaution_extraction_rate"] == 0.0
    assert metrics["functional_claim_extraction_rate"] == 1.0
    assert metrics["section_type_recall"] == 0.5
    assert summary["raw_ocr_text_stored"] is False


def test_evaluate_manifest_reports_scoreable_ingredient_metric(tmp_path: Path) -> None:
    """Verify package-count expected contaminants do not define the scoreable KPI."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest_path,
        [
            {
                "fixture_id": "fixture-1",
                "expected": {
                    "verification_status": "provisional",
                    "warnings": ["auto_expected_requires_human_verification"],
                    "ingredients": [
                        {"name": "비타민 D"},
                        {"name": "g X30포("},
                        {"name": "건강기능식품"},
                    ],
                },
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "latency_ms": 100,
                        "text_non_empty": True,
                        "parser_success": True,
                        "parsed_ingredients": [{"name": "비타민 D"}],
                    }
                ],
            }
        ],
    )

    summary = evaluate.evaluate_manifest(manifest_path)
    metrics = summary["providers"]["paddleocr_local"]  # type: ignore[index]
    assert isinstance(metrics, dict)
    assert metrics["ingredient_name_exact_rate"] == 0.3333
    assert metrics["scoreable_ingredient_name_exact_rate"] == 1.0
    assert summary["scoreable_fixture_count"] == 1
    assert summary["provisional_fixture_count"] == 1
    assert summary["expected_quality_warnings"] == {
        "auto_expected_requires_human_verification": 1,
        "invalid_generic_heading_ingredient": 1,
        "invalid_packaging_quantity_ingredient": 1,
    }


def test_kpi_gate_fails_when_scoreable_denominator_is_too_small(tmp_path: Path) -> None:
    """Verify provisional tiny-denominator metrics cannot pass the official KPI."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest_path,
        [
            {
                "fixture_id": "fixture-1",
                "expected": {
                    "verification_status": "provisional",
                    "warnings": ["auto_expected_requires_human_verification"],
                    "ingredients": [{"name": "비타민 D"}],
                },
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "text_non_empty": True,
                        "parser_success": True,
                        "parsed_ingredients": [{"name": "비타민 D"}],
                    }
                ],
            }
        ],
    )

    summary = evaluate.evaluate_manifest(manifest_path)
    gate = evaluate.evaluate_kpi_gate(
        summary,
        evaluate.KpiGateConfig(
            provider="paddleocr_local",
            require_scoreable_fixtures=16,
            require_no_provisional=True,
            min_scoreable_ingredient_rate=0.95,
        ),
    )

    assert gate is not None
    assert gate["passed"] is False
    assert gate["provider"] == "paddleocr_local"
    assert gate["failures"] == [
        {
            "code": "scoreable_fixture_count_below_required",
            "required": 16,
            "actual": 1,
        },
        {
            "code": "provisional_fixture_count_nonzero",
            "required": 0,
            "actual": 1,
        },
    ]


def test_kpi_gate_passes_verified_scoreable_threshold(tmp_path: Path) -> None:
    """Verify a fully scoreable verified fixture set can pass the KPI gate."""
    manifest_path = tmp_path / "manifest.jsonl"
    rows: list[dict[str, object]] = []
    for index in range(2):
        ingredient = f"비타민 {index}"
        rows.append(
            {
                "fixture_id": f"fixture-{index}",
                "expected": {
                    "verification_status": "verified",
                    "warnings": [],
                    "ingredients": [{"name": ingredient}],
                },
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "text_non_empty": True,
                        "parser_success": True,
                        "parsed_ingredients": [{"name": ingredient}],
                    }
                ],
            }
        )
    _write_manifest(manifest_path, rows)

    summary = evaluate.evaluate_manifest(manifest_path)
    gate = evaluate.evaluate_kpi_gate(
        summary,
        evaluate.KpiGateConfig(
            provider="paddleocr_local",
            require_scoreable_fixtures=2,
            require_no_provisional=True,
            min_scoreable_ingredient_rate=0.95,
        ),
    )

    assert gate is not None
    assert gate["passed"] is True
    assert gate["failures"] == []


def test_evaluate_manifest_counts_error_status_rows(tmp_path: Path) -> None:
    """Verify provider error observations are reflected in aggregate error count."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest_path,
        [
            {
                "fixture_id": "fixture-1",
                "expected": {"ingredients": [{"name": "비타민 D"}]},
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "status": "error",
                        "error_code": "ocr_empty_text",
                    }
                ],
            }
        ],
    )

    summary = evaluate.evaluate_manifest(manifest_path)
    metrics = summary["providers"]["paddleocr_local"]  # type: ignore[index]
    assert isinstance(metrics, dict)
    assert metrics["calls"] == 1
    assert metrics["errors"] == 1
    assert metrics["ingredient_name_exact_rate"] == 0.0
    assert metrics["status_counts"] == {"error": 1}
    assert metrics["error_code_counts"] == {"ocr_empty_text": 1}


def test_evaluate_manifest_reports_bounded_diagnostic_counters(tmp_path: Path) -> None:
    """Verify parser diagnostics are aggregated without accepting unsafe tokens."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest_path,
        [
            {
                "fixture_id": "fixture-1",
                "expected": {"ingredients": [{"name": "vitamin c"}]},
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "status": "completed",
                        "text_non_empty": True,
                        "parser_success": False,
                        "warning_codes": [
                            "layout_unavailable",
                            "/private/tmp/raw-path-should-not-appear",
                        ],
                        "pii_screening_status": "completed_local_screening",
                        "llm_parse_status": "error",
                        "llm_parse_error_code": "ollama_client",
                    }
                ],
            }
        ],
    )

    summary = evaluate.evaluate_manifest(manifest_path)
    metrics = summary["providers"]["paddleocr_local"]  # type: ignore[index]
    assert isinstance(metrics, dict)
    assert metrics["status_counts"] == {"completed": 1}
    assert metrics["warning_code_counts"] == {
        "layout_unavailable": 1,
        "unsafe_token": 1,
    }
    assert metrics["pii_screening_status_counts"] == {"completed_local_screening": 1}
    assert metrics["llm_parse_status_counts"] == {"error": 1}
    assert metrics["llm_parse_error_code_counts"] == {"ollama_client": 1}
    assert "/private/tmp" not in json.dumps(metrics, ensure_ascii=False)


def test_evaluate_manifest_llm_failure_counted(tmp_path: Path) -> None:
    """Verify LLM parser failures contribute to attempt count but not success count."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest_path,
        [
            {
                "fixture_id": "fixture-1",
                "expected": {"ingredients": [{"name": "vitamin c"}]},
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "latency_ms": 100,
                        "text_non_empty": True,
                        "parser_success": True,
                        "parsed_ingredients": [{"name": "vitamin c"}],
                        "llm_parse_status": "ollama_client_error",
                    }
                ],
            }
        ],
    )

    summary = evaluate.evaluate_manifest(manifest_path)
    providers = summary["providers"]
    assert isinstance(providers, dict)
    metrics = providers["paddleocr_local"]
    assert isinstance(metrics, dict)
    assert metrics["llm_parse_attempt_count"] == 1
    assert metrics["llm_parse_success_rate"] == 0.0
    # llm_parsed_ingredients 가 없으니 정확도 분모는 0 → None
    assert metrics["llm_ingredient_name_exact_rate"] is None


def test_evaluate_manifest_backward_compatible_without_llm_fields(tmp_path: Path) -> None:
    """Verify legacy observations without LLM fields still produce valid metrics."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest_path,
        [
            {
                "fixture_id": "fixture-1",
                "expected": {"ingredients": [{"name": "vitamin c"}]},
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "latency_ms": 100,
                        "text_non_empty": True,
                        "parser_success": True,
                        "parsed_ingredients": [{"name": "vitamin c"}],
                    }
                ],
            }
        ],
    )

    summary = evaluate.evaluate_manifest(manifest_path)
    providers = summary["providers"]
    assert isinstance(providers, dict)
    metrics = providers["paddleocr_local"]
    assert isinstance(metrics, dict)
    assert metrics["ingredient_name_exact_rate"] == 1.0
    assert metrics["llm_parse_attempt_count"] == 0
    assert metrics["llm_parse_success_rate"] is None
    assert metrics["llm_ingredient_name_exact_rate"] is None


def test_evaluate_manifest_aggregates_language_error_rates(tmp_path: Path) -> None:
    """Verify CER/WER fields on observations are averaged per provider."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest_path,
        [
            {
                "fixture_id": "fixture-1",
                "expected": {"ingredients": [{"name": "vitamin c"}]},
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "latency_ms": 100,
                        "text_non_empty": True,
                        "parser_success": True,
                        "parsed_ingredients": [{"name": "vitamin c"}],
                        "cer_ko": 0.1,
                        "cer_en": 0.05,
                        "wer_ko": 0.2,
                        "wer_en": 0.0,
                    }
                ],
            },
            {
                "fixture_id": "fixture-2",
                "expected": {"ingredients": [{"name": "vitamin c"}]},
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "latency_ms": 120,
                        "text_non_empty": True,
                        "parser_success": True,
                        "parsed_ingredients": [{"name": "vitamin c"}],
                        "cer_ko": 0.3,
                        "cer_en": 0.15,
                        "wer_ko": 0.4,
                        "wer_en": 0.2,
                    }
                ],
            },
        ],
    )

    summary = evaluate.evaluate_manifest(manifest_path)
    providers = summary["providers"]
    assert isinstance(providers, dict)
    metrics = providers["paddleocr_local"]
    assert isinstance(metrics, dict)
    # 두 관찰의 CER/WER 평균이 출력된다
    assert metrics["cer_ko_avg"] == pytest.approx(0.2, abs=1e-6)
    assert metrics["cer_en_avg"] == pytest.approx(0.1, abs=1e-6)
    assert metrics["wer_ko_avg"] == pytest.approx(0.3, abs=1e-6)
    assert metrics["wer_en_avg"] == pytest.approx(0.1, abs=1e-6)


def test_evaluate_manifest_groups_accuracy_by_chronic_disease(tmp_path: Path) -> None:
    """Verify chronic_disease_indications drive per-condition accuracy buckets."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest_path,
        [
            {
                "fixture_id": "fixture-1",
                "expected": {
                    "ingredients": [{"name": "vitamin c"}, {"name": "zinc"}],
                    "chronic_disease_indications": ["cardiovascular", "dyslipidemia"],
                },
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "latency_ms": 100,
                        "text_non_empty": True,
                        "parser_success": True,
                        # 두 ingredient 중 1개만 매칭됨 → 1/2 = 0.5
                        "parsed_ingredients": [{"name": "vitamin c"}],
                    }
                ],
            },
            {
                "fixture_id": "fixture-2",
                "expected": {
                    "ingredients": [{"name": "magnesium"}],
                    "chronic_disease_indications": ["cardiovascular"],
                },
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "latency_ms": 100,
                        "text_non_empty": True,
                        "parser_success": True,
                        # 완전 매칭 → 1/1 = 1.0
                        "parsed_ingredients": [{"name": "magnesium"}],
                    }
                ],
            },
        ],
    )

    summary = evaluate.evaluate_manifest(manifest_path)
    metrics = summary["providers"]["paddleocr_local"]  # type: ignore[index]
    assert isinstance(metrics, dict)
    by_condition = metrics["accuracy_by_condition"]
    assert isinstance(by_condition, dict)
    # cardiovascular: 두 fixture 모두 참여 → (1+1) / (2+1) = 2/3 ≈ 0.6667
    assert by_condition["cardiovascular"] == pytest.approx(2 / 3, abs=1e-4)
    # dyslipidemia: fixture-1 만 참여 → 1/2 = 0.5
    assert by_condition["dyslipidemia"] == 0.5


def test_evaluate_manifest_without_chronic_disease_indications_empty_dict(
    tmp_path: Path,
) -> None:
    """Verify fixtures without chronic_disease_indications produce empty by-condition map."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest_path,
        [
            {
                "fixture_id": "fixture-1",
                "expected": {"ingredients": [{"name": "vitamin c"}]},
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "latency_ms": 100,
                        "text_non_empty": True,
                        "parser_success": True,
                        "parsed_ingredients": [{"name": "vitamin c"}],
                    }
                ],
            }
        ],
    )

    summary = evaluate.evaluate_manifest(manifest_path)
    metrics = summary["providers"]["paddleocr_local"]  # type: ignore[index]
    assert isinstance(metrics, dict)
    assert metrics["accuracy_by_condition"] == {}


def test_evaluate_manifest_missing_language_metrics_returns_none(tmp_path: Path) -> None:
    """Verify CER/WER averages are None when observations carry no values."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_manifest(
        manifest_path,
        [
            {
                "fixture_id": "fixture-1",
                "expected": {"ingredients": [{"name": "vitamin c"}]},
                "observations": [
                    {
                        "provider": "paddleocr_local",
                        "latency_ms": 100,
                        "text_non_empty": True,
                        "parser_success": True,
                        "parsed_ingredients": [{"name": "vitamin c"}],
                    }
                ],
            }
        ],
    )

    summary = evaluate.evaluate_manifest(manifest_path)
    providers = summary["providers"]
    assert isinstance(providers, dict)
    metrics = providers["paddleocr_local"]
    assert isinstance(metrics, dict)
    assert metrics["cer_ko_avg"] is None
    assert metrics["cer_en_avg"] is None
    assert metrics["wer_ko_avg"] is None
    assert metrics["wer_en_avg"] is None
