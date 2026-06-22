"""label_ground_truth + validate_ground_truth 단위 테스트."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import label_ground_truth, validate_ground_truth


class TestLabelGroundTruth:
    """V2 snapshot skeleton 생성기 테스트."""

    def test_skeleton_validates_against_schema(self, tmp_path: Path) -> None:
        """기본 skeleton 은 V2 schema 검증을 통과해야 한다."""
        output = tmp_path / "test-fx.snapshot_v2.json"
        created = label_ground_truth.write_skeleton(
            output_path=output,
            fixture_id="test-fx",
            category="비타민A",
            seed_ingredients=[],
            overwrite=False,
        )
        assert created is True
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["schema_version"] == "supplement-parsed-snapshot-v2"
        assert payload["product"]["product_name"] == "TBD"
        assert payload["ingredient_candidates"] == []
        assert label_ground_truth.PENDING_REVIEW_WARNING in payload["warnings"]
        assert "category:비타민A" in payload["warnings"]

    def test_seed_ingredients_marked_as_auto_seed(self, tmp_path: Path) -> None:
        """Seed 된 ingredient 는 source 가 자동 시드 값이어야 한다."""
        output = tmp_path / "test-fx.snapshot_v2.json"
        seeds = label_ground_truth._parse_ingredient_seed("비타민 A, 비타민 D, 칼슘")
        label_ground_truth.write_skeleton(
            output_path=output,
            fixture_id="test-fx",
            category="멀티비타민",
            seed_ingredients=seeds,
            overwrite=False,
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
        candidates = payload["ingredient_candidates"]
        assert len(candidates) == 3
        for candidate in candidates:
            assert candidate["source"] == label_ground_truth.AUTO_SEED_INGREDIENT_SOURCE
            assert candidate["confidence"] == 0.0
        assert candidates[0]["display_name"] == "비타민 A"
        assert candidates[0]["normalized_name"] == "비타민 a"

    def test_existing_file_skipped_without_overwrite(self, tmp_path: Path) -> None:
        """``--overwrite`` 없이 기존 파일이 있으면 skip 한다."""
        output = tmp_path / "test-fx.snapshot_v2.json"
        output.write_text("existing", encoding="utf-8")
        created = label_ground_truth.write_skeleton(
            output_path=output,
            fixture_id="test-fx",
            category="비타민A",
            seed_ingredients=[],
            overwrite=False,
        )
        assert created is False
        # 내용이 보존됨
        assert output.read_text(encoding="utf-8") == "existing"

    def test_overwrite_replaces_existing_file(self, tmp_path: Path) -> None:
        """``--overwrite`` 가 켜져 있으면 기존 파일을 대체한다."""
        output = tmp_path / "test-fx.snapshot_v2.json"
        output.write_text("existing", encoding="utf-8")
        created = label_ground_truth.write_skeleton(
            output_path=output,
            fixture_id="test-fx",
            category="비타민A",
            seed_ingredients=[],
            overwrite=True,
        )
        assert created is True
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["schema_version"] == "supplement-parsed-snapshot-v2"

    def test_v3_skeleton_includes_chronic_disease_indications(self, tmp_path: Path) -> None:
        """``.snapshot_v3.json`` 출력 시 V3 skeleton 이 생성되고 만성질환 인디케이션 채워짐."""
        output = tmp_path / "naver-chronic-0001.snapshot_v3.json"
        created = label_ground_truth.write_skeleton(
            output_path=output,
            fixture_id="naver-chronic-0001",
            category="오메가3",
            seed_ingredients=[],
            overwrite=False,
            chronic_disease_targets=["cardiovascular", "dyslipidemia"],
        )
        assert created is True
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["schema_version"] == "supplement-parsed-snapshot-v3"
        assert payload["chronic_disease_indications"] == ["cardiovascular", "dyslipidemia"]
        # V3 만의 필드들 확인
        assert "evidence_spans" in payload
        assert "domain_correction_audit" in payload
        assert "parser_schema_version" in payload["source"]

    def test_v3_skeleton_default_chronic_targets_empty(self, tmp_path: Path) -> None:
        """V3 skeleton 에서 chronic_disease_targets 없이도 빈 리스트로 valid."""
        output = tmp_path / "naver-chronic-0002.snapshot_v3.json"
        label_ground_truth.write_skeleton(
            output_path=output,
            fixture_id="naver-chronic-0002",
            category="오메가3",
            seed_ingredients=[],
            overwrite=False,
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert payload["chronic_disease_indications"] == []


class TestParseChronicDiseaseTargets:
    """``_parse_chronic_disease_targets`` helper 단위 테스트."""

    def test_valid_tokens_parsed(self) -> None:
        """유효한 토큰 리스트는 그대로 반환된다."""
        result = label_ground_truth._parse_chronic_disease_targets(
            "cardiovascular, diabetes,hypertension"
        )
        assert result == ["cardiovascular", "diabetes", "hypertension"]

    def test_duplicates_removed(self) -> None:
        """중복 토큰은 제거된다."""
        result = label_ground_truth._parse_chronic_disease_targets(
            "cardiovascular,cardiovascular, diabetes"
        )
        assert result == ["cardiovascular", "diabetes"]

    def test_unknown_token_raises(self) -> None:
        """정의되지 않은 condition 은 ValueError."""
        with pytest.raises(ValueError, match="Unknown chronic condition"):
            label_ground_truth._parse_chronic_disease_targets("covid_19")

    def test_empty_string_returns_empty_list(self) -> None:
        """빈 입력은 빈 리스트."""
        assert label_ground_truth._parse_chronic_disease_targets("") == []
        assert label_ground_truth._parse_chronic_disease_targets(" , , ") == []


class TestValidateGroundTruth:
    """라벨링 진행률 validator 테스트."""

    def _write_v2(self, path: Path, payload: dict[str, object]) -> None:
        """V2 snapshot JSON 을 파일에 작성한다."""
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_empty_directory_reports_zero(self, tmp_path: Path) -> None:
        """빈 디렉토리는 0/0 으로 보고된다."""
        summary = validate_ground_truth.validate_directory(tmp_path)
        assert summary.v2_total == 0
        assert summary.v2_human_labeled == 0
        assert summary.errors == []

    def test_pending_review_warning_counted_as_auto_seed(self, tmp_path: Path) -> None:
        """``ground_truth_pending_human_review`` 가 있으면 human-labeled 가 아니다."""
        payload = label_ground_truth.build_skeleton(
            fixture_id="naver-test-001",
            category="멀티비타민",
            seed_ingredients=label_ground_truth._parse_ingredient_seed("비타민 A"),
        )
        self._write_v2(tmp_path / "naver-test-001.snapshot_v2.json", payload)
        summary = validate_ground_truth.validate_directory(tmp_path)
        assert summary.v2_total == 1
        assert summary.v2_valid == 1
        assert summary.v2_human_labeled == 0

    def test_human_labeled_when_source_manual_and_warning_removed(self, tmp_path: Path) -> None:
        """source=manual + warning 제거된 경우 human-labeled 로 카운트된다."""
        payload = label_ground_truth.build_skeleton(
            fixture_id="naver-test-002",
            category="비타민B",
            seed_ingredients=label_ground_truth._parse_ingredient_seed("비타민 B"),
        )
        # 사람이 검수했음을 모사: source="manual", warning 제거
        payload["ingredient_candidates"] = [
            {
                **payload["ingredient_candidates"][0],  # type: ignore[index]
                "source": label_ground_truth.HUMAN_CONFIRMED_INGREDIENT_SOURCE,
                "confidence": 1.0,
            }
        ]
        warnings = payload["warnings"]
        assert isinstance(warnings, list)
        payload["warnings"] = [
            w for w in warnings if w != label_ground_truth.PENDING_REVIEW_WARNING
        ]
        self._write_v2(tmp_path / "naver-test-002.snapshot_v2.json", payload)
        summary = validate_ground_truth.validate_directory(tmp_path)
        assert summary.v2_human_labeled == 1

    def test_progress_line_formatting(self) -> None:
        """진행률 라인 포맷이 기대치와 일치한다."""
        assert validate_ground_truth._format_progress_line(3, 30) == "3/30 (10.0%)"
        assert validate_ground_truth._format_progress_line(0, 30) == "0/30 (0.0%)"
        assert validate_ground_truth._format_progress_line(30, 30) == "30/30 (100.0%)"
        assert validate_ground_truth._format_progress_line(5, 0) == "5/0 (0.0%)"

    def test_invalid_json_recorded_as_error(self, tmp_path: Path) -> None:
        """JSON 파싱 실패는 errors 리스트에 기록된다."""
        (tmp_path / "broken.snapshot_v2.json").write_text("not-json", encoding="utf-8")
        summary = validate_ground_truth.validate_directory(tmp_path)
        # 파일 자체는 v2 인덱스에서 +1 되지 않음 (read_or_parse 단계에서 실패)
        assert len(summary.errors) == 1
        assert "read_or_parse_error" in summary.errors[0][1]
        rendered = validate_ground_truth.render_report(summary, target_count=30)
        assert "broken.snapshot_v2.json" in rendered
        assert str(tmp_path) not in rendered

    def test_missing_directory_error_does_not_expose_local_path(self, tmp_path: Path) -> None:
        """존재하지 않는 expected-dir 절대경로는 report 에 출력하지 않는다."""
        missing_dir = tmp_path / "missing-expected"
        summary = validate_ground_truth.validate_directory(missing_dir)
        assert len(summary.errors) == 1
        assert summary.errors[0][1] == "directory_not_found"
        rendered = validate_ground_truth.render_report(summary, target_count=30)
        assert "missing-expected" in rendered
        assert str(tmp_path) not in rendered

    def test_schema_error_does_not_embed_raw_input_value(self, tmp_path: Path) -> None:
        """Pydantic schema 오류는 raw 입력값 대신 type/loc 만 출력한다."""
        secret_like_path = "/Volumes/Corsair EX400U Media/private-label.jpg"
        self._write_v2(
            tmp_path / "invalid.snapshot_v2.json",
            {
                "schema_version": "supplement-parsed-snapshot-v2",
                "fixture_id": secret_like_path,
            },
        )
        summary = validate_ground_truth.validate_directory(tmp_path)
        rendered = validate_ground_truth.render_report(summary, target_count=30)
        assert "schema_validation" in rendered
        assert secret_like_path not in rendered
        assert str(tmp_path) not in rendered
