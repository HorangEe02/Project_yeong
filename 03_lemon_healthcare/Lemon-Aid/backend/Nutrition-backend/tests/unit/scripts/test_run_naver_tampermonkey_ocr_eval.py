"""Tests for Naver Tampermonkey OCR runner guardrails."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import run_naver_tampermonkey_ocr_eval as runner


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows for tests."""
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_build_provider_runs_allows_local_paddle_with_llm_parse(tmp_path: Path) -> None:
    """Verify local PaddleOCR run plans are built without external opt-in."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(
        manifest_path,
        [
            {
                "fixture_id": "detail-1",
                "section": "detail",
                "contains_personal_data": False,
                "external_transfer_allowed": True,
            }
        ],
    )

    runs = runner.build_provider_runs(
        manifest_path=manifest_path,
        output_root=tmp_path / "out",
        providers=("paddleocr",),
        env_file=tmp_path / ".env",
        python_executable=Path("/private/tmp/ocr-python"),
        llm_parse=True,
        allow_external_providers=False,
        allow_review_external=False,
    )

    assert len(runs) == 1
    run = runs[0]
    assert run.provider_id == "paddleocr_local"
    assert run.command[0] == "/private/tmp/ocr-python"
    assert run.python_executable == Path("/private/tmp/ocr-python")
    assert run.env_overrides["RUN_PADDLEOCR_PROBE"] == "1"
    assert "--llm-parse" in run.command
    redacted = json.dumps(run.redacted(), ensure_ascii=False)
    assert "/private/tmp" not in redacted
    assert str(tmp_path) not in redacted
    assert ".env" not in redacted
    assert "api_key" not in redacted.lower()
    assert "secret" not in redacted.lower()


def test_external_provider_requires_explicit_allow_flag(tmp_path: Path) -> None:
    """Verify CLOVA/Google Vision cannot run without explicit external opt-in."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(
        manifest_path,
        [
            {
                "fixture_id": "detail-1",
                "section": "detail",
                "contains_personal_data": False,
                "external_transfer_allowed": True,
            }
        ],
    )

    with pytest.raises(ValueError, match="External providers require"):
        runner.build_provider_runs(
            manifest_path=manifest_path,
            output_root=tmp_path / "out",
            providers=("clova",),
            env_file=None,
            python_executable=Path("/tmp/ocr-python"),
            llm_parse=False,
            allow_external_providers=False,
            allow_review_external=False,
        )


def test_review_rows_block_external_transfer_by_default(tmp_path: Path) -> None:
    """Verify review images are not externally transferred by default."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(
        manifest_path,
        [
            {
                "fixture_id": "review-1",
                "section": "review",
                "contains_personal_data": False,
                "external_transfer_allowed": False,
            }
        ],
    )

    with pytest.raises(ValueError, match="Review image external transfer"):
        runner.build_provider_runs(
            manifest_path=manifest_path,
            output_root=tmp_path / "out",
            providers=("google_vision",),
            env_file=None,
            python_executable=Path("/tmp/ocr-python"),
            llm_parse=False,
            allow_external_providers=True,
            allow_review_external=False,
        )


def test_parse_provider_aliases_rejects_unknown_alias() -> None:
    """Verify unsupported provider aliases fail closed."""
    with pytest.raises(ValueError, match="Unsupported provider alias"):
        runner.parse_provider_aliases("paddleocr,unknown")


def test_main_dry_run_output_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify dry-run CLI output does not expose local paths or env filenames."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(
        manifest_path,
        [
            {
                "fixture_id": "detail-1",
                "section": "detail",
                "contains_personal_data": False,
                "external_transfer_allowed": True,
            }
        ],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_naver_tampermonkey_ocr_eval.py",
            "--manifest",
            str(manifest_path),
            "--output-root",
            str(tmp_path / "out"),
            "--env-file",
            str(tmp_path / ".env"),
            "--python-executable",
            "/private/tmp/ocr-python",
            "--dry-run",
        ],
    )

    runner.main()

    printed = capsys.readouterr().out
    payload = json.loads(printed)
    assert payload["runs"][0]["output_dir_name"] == "paddleocr-observations"
    assert payload["runs"][0]["python_executable_name"] == "ocr-python"
    assert "/private/tmp" not in printed
    assert str(tmp_path) not in printed
    assert ".env" not in printed


def test_main_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failures do not print tracebacks or local paths."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_naver_tampermonkey_ocr_eval.py",
            "--manifest",
            str(tmp_path / "missing-manifest.jsonl"),
            "--output-root",
            str(tmp_path / "out"),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        runner.main()

    printed = capsys.readouterr().out
    payload = json.loads(printed)
    assert exc_info.value.code == 1
    assert payload["status"] == "error"
    assert payload["error_code"] == "local_file_error"
    assert payload["manifest_name"] == "missing-manifest.jsonl"
    assert "Traceback" not in printed
    assert str(tmp_path) not in printed
    assert "/private/tmp" not in printed


def test_run_provider_evaluations_resumes_complete_output(tmp_path: Path) -> None:
    """Verify resume skips a complete provider output without rerunning."""
    output_dir = tmp_path / "paddleocr-observations"
    output_dir.mkdir()
    _write_jsonl(
        output_dir / "supplement-ocr-observations.jsonl",
        [
            {
                "fixture_id": "detail-1",
                "provider": "paddleocr_local",
                "status": "completed",
                "text_non_empty": True,
            },
            {
                "fixture_id": "detail-2",
                "provider": "paddleocr_local",
                "status": "error",
                "error_code": "ocrerror",
            },
        ],
    )
    run = runner.ProviderRun(
        alias="paddleocr",
        provider_id="paddleocr_local",
        output_dir=output_dir,
        python_executable=Path("/tmp/ocr-python"),
        command=("/tmp/ocr-python", "collector.py"),
        env_overrides={},
    )
    calls: list[list[str]] = []

    def fake_runner(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    result = runner.run_provider_evaluations(
        [run],
        resume=True,
        manifest_rows=[{"fixture_id": "detail-1"}, {"fixture_id": "detail-2"}],
        runner=fake_runner,
    )

    assert calls == []
    assert result.completed_runs == [run]
    assert result.executed_runs == []
    assert result.resumed_runs == [run]


def test_run_provider_evaluations_reruns_not_run_output(tmp_path: Path) -> None:
    """Verify resume does not treat guard-skipped outputs as complete."""
    output_dir = tmp_path / "google_vision-observations"
    output_dir.mkdir()
    _write_jsonl(
        output_dir / "supplement-ocr-observations.jsonl",
        [
            {
                "fixture_id": "detail-1",
                "provider": "google_vision_document",
                "status": "not_run",
            }
        ],
    )
    run = runner.ProviderRun(
        alias="google_vision",
        provider_id="google_vision_document",
        output_dir=output_dir,
        python_executable=Path("/tmp/ocr-python"),
        command=("/tmp/ocr-python", "collector.py"),
        env_overrides={},
    )
    calls: list[list[str]] = []

    def fake_runner(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    result = runner.run_provider_evaluations(
        [run],
        resume=True,
        manifest_rows=[{"fixture_id": "detail-1"}],
        runner=fake_runner,
    )

    assert calls == [["/tmp/ocr-python", "collector.py"]]
    assert result.completed_runs == [run]
    assert result.executed_runs == [run]
    assert result.resumed_runs == []


def test_run_provider_evaluations_captures_child_output(tmp_path: Path) -> None:
    """Verify provider subprocess output is captured instead of streamed."""
    run = runner.ProviderRun(
        alias="paddleocr",
        provider_id="paddleocr_local",
        output_dir=tmp_path / "paddleocr-observations",
        python_executable=Path("/tmp/ocr-python"),
        command=("/tmp/ocr-python", "collector.py"),
        env_overrides={},
    )
    kwargs_seen: list[dict[str, object]] = []

    def fake_runner(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        kwargs_seen.append(kwargs)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="/private/tmp/should-not-stream",
            stderr="secret-like child stderr",
        )

    result = runner.run_provider_evaluations(
        [run],
        runner=fake_runner,
    )

    assert result.executed_runs == [run]
    assert kwargs_seen[0]["capture_output"] is True
    assert kwargs_seen[0]["text"] is True
    assert kwargs_seen[0]["check"] is True


def test_run_provider_evaluations_uses_sanitized_child_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify unrelated parent secrets are not propagated to collectors."""
    run = runner.ProviderRun(
        alias="paddleocr",
        provider_id="paddleocr_local",
        output_dir=tmp_path / "paddleocr-observations",
        python_executable=Path("/tmp/ocr-python"),
        command=("/tmp/ocr-python", "collector.py"),
        env_overrides={"RUN_PADDLEOCR_PROBE": "1", "ENABLE_LOCAL_OCR": "true"},
    )
    monkeypatch.setenv("UNRELATED_SECRET_TOKEN", "should-not-reach-child")
    monkeypatch.setenv("ENABLE_LOCAL_OCR", "false")
    monkeypatch.setenv("LOCAL_OCR_CONFIDENCE_THRESHOLD", "0.65")
    monkeypatch.setenv("LOCAL_OCR_MODEL_PROFILE", "server_detection")
    monkeypatch.setenv("LOCAL_OCR_PREPROCESS_MODE", "autocontrast")
    monkeypatch.setenv("LOCAL_OCR_USE_TEXTLINE_ORIENTATION", "true")
    monkeypatch.setenv("OLLAMA_MODEL", "gemma4:e4b")
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(tmp_path / "fixtures"))
    kwargs_seen: list[dict[str, object]] = []

    def fake_runner(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        kwargs_seen.append(kwargs)
        return subprocess.CompletedProcess(command, 0)

    runner.run_provider_evaluations(
        [run],
        manifest_rows=[
            {
                "fixture_id": "detail-1",
                "image_path": "$NAVER_TAMPERMONKEY_SOURCE_ROOT/a.jpg",
            }
        ],
        runner=fake_runner,
    )

    env = kwargs_seen[0]["env"]
    assert isinstance(env, dict)
    assert "UNRELATED_SECRET_TOKEN" not in env
    assert env["RUN_PADDLEOCR_PROBE"] == "1"
    assert env["ENABLE_LOCAL_OCR"] == "true"
    assert env["LOCAL_OCR_CONFIDENCE_THRESHOLD"] == "0.65"
    assert env["LOCAL_OCR_MODEL_PROFILE"] == "server_detection"
    assert env["LOCAL_OCR_PREPROCESS_MODE"] == "autocontrast"
    assert env["LOCAL_OCR_USE_TEXTLINE_ORIENTATION"] == "true"
    assert env["OLLAMA_MODEL"] == "gemma4:e4b"
    assert env["NAVER_TAMPERMONKEY_SOURCE_ROOT"] == str(tmp_path / "fixtures")
    assert env["PYTHONPATH"] == str(runner.NUTRITION_BACKEND_ROOT)


def test_run_provider_evaluations_does_not_copy_unused_image_root_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify fixture roots are forwarded only when the manifest references them."""
    run = runner.ProviderRun(
        alias="paddleocr",
        provider_id="paddleocr_local",
        output_dir=tmp_path / "paddleocr-observations",
        python_executable=Path("/tmp/ocr-python"),
        command=("/tmp/ocr-python", "collector.py"),
        env_overrides={},
    )
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(tmp_path / "fixtures"))
    kwargs_seen: list[dict[str, object]] = []

    def fake_runner(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        kwargs_seen.append(kwargs)
        return subprocess.CompletedProcess(command, 0)

    runner.run_provider_evaluations(
        [run],
        manifest_rows=[{"fixture_id": "detail-1", "image_path": "images/a.jpg"}],
        runner=fake_runner,
    )

    env = kwargs_seen[0]["env"]
    assert isinstance(env, dict)
    assert "NAVER_TAMPERMONKEY_SOURCE_ROOT" not in env


def test_run_comparison_report_returns_names_without_paths(tmp_path: Path) -> None:
    """Verify comparison report summaries do not expose output paths."""
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="/private/tmp/leak")

    report = runner.run_comparison_report(
        manifest_path=tmp_path / "manifest.jsonl",
        output_root=tmp_path / "out",
        observation_dirs=[tmp_path / "paddleocr-observations"],
        runner=fake_runner,
    )

    assert calls
    assert calls[0][1]["capture_output"] is True
    assert report["json_name"] == runner.DEFAULT_REPORT_JSON_NAME
    assert report["markdown_name"] == runner.DEFAULT_REPORT_MARKDOWN_NAME
    serialized = json.dumps(report, ensure_ascii=False)
    assert str(tmp_path) not in serialized
