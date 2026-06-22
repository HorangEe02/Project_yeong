"""Tests for batch-running Naver Tampermonkey OCR evaluations."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import run_naver_tampermonkey_batch_ocr_eval as batch_runner


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows for tests."""
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _manifest_row(index: int) -> dict[str, object]:
    """Return a safe manifest row for a detail-page fixture."""
    return {
        "fixture_id": f"naver-tm-detail-{index:06d}",
        "source": "naver_tampermonkey",
        "section": "detail",
        "image_path": "$NAVER_TAMPERMONKEY_SOURCE_ROOT/[오메가3]/sample/detail.jpg",
        "contains_personal_data": False,
        "external_transfer_allowed": True,
        "db_labeling": {
            "category_key": "omega_3",
            "language_targets": ["ko", "en"],
            "source_urls": ["https://ods.od.nih.gov/factsheets/list-all/"],
        },
    }


def _write_batch_summary(batch_dir: Path, names: list[str]) -> None:
    """Write a minimal batch summary with deterministic names."""
    payload = {
        "schema_version": "naver-tampermonkey-manifest-batches-v1",
        "batches": [{"name": name, "row_count": 1} for name in names],
        "raw_ocr_text_stored": False,
        "raw_provider_payload_stored": False,
        "raw_model_response_stored": False,
        "local_path_literals_stored": False,
    }
    (batch_dir / "manifest-batches.summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_build_batch_run_plans_uses_summary_order_and_redacts_paths(tmp_path: Path) -> None:
    """Verify batch plans are deterministic and redacted."""
    batch_dir = tmp_path / "batches"
    batch_dir.mkdir()
    _write_jsonl(batch_dir / "tm-batch-001.jsonl", [_manifest_row(1)])
    _write_jsonl(batch_dir / "tm-batch-002.jsonl", [_manifest_row(2)])
    _write_batch_summary(batch_dir, ["tm-batch-002.jsonl", "tm-batch-001.jsonl"])

    plans = batch_runner.build_batch_run_plans(
        batch_dir=batch_dir,
        batch_summary_path=batch_dir / "manifest-batches.summary.json",
        output_root=tmp_path / "runner-output",
        run_prefix="ocr-batch",
        runner_python_executable=Path("/private/tmp/python"),
        collector_python_executable=Path("/private/tmp/ocr-python"),
        providers="paddleocr",
        llm_parse=True,
        resume=True,
    )

    assert [plan.batch_name for plan in plans] == ["tm-batch-002.jsonl", "tm-batch-001.jsonl"]
    assert plans[0].output_root.name == "ocr-batch-001"
    assert "--llm-parse" in plans[0].command
    assert "--resume" in plans[0].command

    redacted = json.dumps([plan.redacted() for plan in plans], ensure_ascii=False)
    assert str(tmp_path) not in redacted
    assert "/private/tmp" not in redacted


def test_run_batch_evaluations_uses_sanitized_env_and_counts_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify batch subprocesses inherit only allowlisted runtime variables."""
    batch_dir = tmp_path / "batches"
    batch_dir.mkdir()
    manifest_path = batch_dir / "tm-batch-001.jsonl"
    _write_jsonl(manifest_path, [_manifest_row(1)])
    plan = batch_runner.BatchRunPlan(
        index=1,
        batch_name="tm-batch-001.jsonl",
        manifest_path=manifest_path,
        output_root=tmp_path / "out" / "batch-001",
        command=("/private/tmp/python", "run_naver_tampermonkey_ocr_eval.py"),
    )
    monkeypatch.setenv("UNRELATED_SECRET_TOKEN", "should-not-reach-child")
    monkeypatch.setenv("LOCAL_OCR_USE_TEXTLINE_ORIENTATION", "true")
    monkeypatch.setenv("OLLAMA_MODEL", "gemma4:e4b")
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(tmp_path / "fixtures"))
    calls: list[dict[str, object]] = []

    def fake_runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(kwargs)
        stdout = json.dumps(
            {
                "completed_runs": [{"provider_id": "paddleocr_local"}],
                "executed_runs": [{"provider_id": "paddleocr_local"}],
                "resumed_runs": [],
            },
            ensure_ascii=False,
        )
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="/private/tmp/leak")

    execution = batch_runner.run_batch_evaluations([plan], runner=fake_runner)
    summary = batch_runner.build_batch_execution_summary(
        batch_dir=batch_dir,
        output_root=tmp_path / "out",
        execution=execution,
        dry_run=False,
        continue_on_error=False,
        timeout_seconds=None,
    )

    assert execution.results[0].status == "completed"
    assert summary["provider_executed_run_count"] == 1
    env = calls[0]["env"]
    assert isinstance(env, dict)
    assert "UNRELATED_SECRET_TOKEN" not in env
    assert env["LOCAL_OCR_USE_TEXTLINE_ORIENTATION"] == "true"
    assert env["OLLAMA_MODEL"] == "gemma4:e4b"
    assert env["NAVER_TAMPERMONKEY_SOURCE_ROOT"] == str(tmp_path / "fixtures")
    serialized = json.dumps(summary, ensure_ascii=False)
    assert str(tmp_path) not in serialized
    assert "/private/tmp" not in serialized
    assert "leak" not in serialized


def test_run_batch_evaluations_stops_after_first_error_by_default(tmp_path: Path) -> None:
    """Verify failed batches are isolated and later batches are skipped by default."""
    batch_dir = tmp_path / "batches"
    batch_dir.mkdir()
    manifests = []
    for index in (1, 2):
        path = batch_dir / f"tm-batch-{index:03d}.jsonl"
        _write_jsonl(path, [_manifest_row(index)])
        manifests.append(path)
    plans = [
        batch_runner.BatchRunPlan(
            index=index,
            batch_name=path.name,
            manifest_path=path,
            output_root=tmp_path / "out" / f"batch-{index:03d}",
            command=("/private/tmp/python", "run_naver_tampermonkey_ocr_eval.py"),
        )
        for index, path in enumerate(manifests, 1)
    ]
    calls: list[list[str]] = []

    def fake_runner(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        stdout = json.dumps({"error_code": "local_file_error"}, ensure_ascii=False)
        raise subprocess.CalledProcessError(1, command, output=stdout, stderr="/private/tmp/leak")

    execution = batch_runner.run_batch_evaluations(plans, runner=fake_runner)

    assert len(calls) == 1
    assert execution.stopped_early is True
    assert execution.results[0].status == "error"
    assert execution.results[0].error_code == "local_file_error"


def test_run_batch_evaluations_can_continue_after_error(tmp_path: Path) -> None:
    """Verify continue-on-error records all batch failures without raw output."""
    batch_dir = tmp_path / "batches"
    batch_dir.mkdir()
    plans = []
    for index in (1, 2):
        path = batch_dir / f"tm-batch-{index:03d}.jsonl"
        _write_jsonl(path, [_manifest_row(index)])
        plans.append(
            batch_runner.BatchRunPlan(
                index=index,
                batch_name=path.name,
                manifest_path=path,
                output_root=tmp_path / "out" / f"batch-{index:03d}",
                command=("/private/tmp/python", "run_naver_tampermonkey_ocr_eval.py"),
            )
        )

    def fake_runner(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        stdout = json.dumps({"error_code": "/private/tmp/unsafe"}, ensure_ascii=False)
        raise subprocess.CalledProcessError(2, command, output=stdout, stderr="secret")

    execution = batch_runner.run_batch_evaluations(
        plans,
        continue_on_error=True,
        runner=fake_runner,
    )
    summary = batch_runner.build_batch_execution_summary(
        batch_dir=batch_dir,
        output_root=tmp_path / "out",
        execution=execution,
        dry_run=False,
        continue_on_error=True,
        timeout_seconds=None,
    )

    assert execution.stopped_early is False
    assert summary["error_batch_count"] == 2
    assert summary["status"] == "completed_with_errors"
    serialized = json.dumps(summary, ensure_ascii=False)
    assert "secret" not in serialized
    assert "/private/tmp" not in serialized


def test_build_batch_run_plans_rejects_unsafe_batch_manifest(tmp_path: Path) -> None:
    """Verify raw OCR text cannot enter batch orchestration."""
    batch_dir = tmp_path / "batches"
    batch_dir.mkdir()
    row = _manifest_row(1)
    row["raw_ocr_text"] = "do not persist"
    _write_jsonl(batch_dir / "tm-batch-001.jsonl", [row])

    with pytest.raises(ValueError, match="raw_ocr_text"):
        batch_runner.build_batch_run_plans(
            batch_dir=batch_dir,
            batch_summary_path=batch_dir / "missing-summary.json",
            output_root=tmp_path / "out",
        )


def test_main_dry_run_output_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI dry-run output and summary hide local paths."""
    batch_dir = tmp_path / "batches"
    batch_dir.mkdir()
    _write_jsonl(batch_dir / "tm-batch-001.jsonl", [_manifest_row(1)])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_naver_tampermonkey_batch_ocr_eval.py",
            "--batch-dir",
            str(batch_dir),
            "--output-root",
            str(tmp_path / "out"),
            "--runner-python-executable",
            "/private/tmp/python",
            "--dry-run",
        ],
    )

    batch_runner.main()

    printed = capsys.readouterr().out
    payload = json.loads(printed)
    assert payload["status"] == "planned"
    assert payload["planned_batch_count"] == 1
    assert "tm-batch-001.jsonl" in printed
    assert str(tmp_path) not in printed
    assert "/private/tmp" not in printed
    summary_text = (tmp_path / "out" / "batch-ocr-eval.summary.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in summary_text
    assert "/private/tmp" not in summary_text
