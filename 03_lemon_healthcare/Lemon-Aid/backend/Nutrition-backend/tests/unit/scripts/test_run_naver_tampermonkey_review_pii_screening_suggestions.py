"""Tests for local Ollama review PII screening suggestion runner."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

from scripts import export_naver_tampermonkey_review_pii_screening_suggestions as exporter
from scripts import run_naver_tampermonkey_review_pii_screening_suggestions as runner


class _FakeResponse:
    """Fake sync HTTP response for local Ollama runner tests."""

    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        """Raise a fake status error when configured."""
        if self.status_code < 400:
            return
        request = httpx.Request("POST", "http://127.0.0.1:11434/api/chat")
        response = httpx.Response(self.status_code, request=request)
        raise httpx.HTTPStatusError("Fake status error.", request=request, response=response)

    def json(self) -> dict[str, object]:
        """Return fake JSON payload."""
        return self.payload


class _FakeClient:
    """Fake sync HTTP client that captures local Ollama requests."""

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.requests: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        timeout: float,
    ) -> _FakeResponse:
        """Capture request data and return the configured response."""
        self.requests.append({"url": url, "json": json, "timeout": timeout})
        return _FakeResponse(self.payload)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write JSONL rows."""
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _manifest_row() -> dict[str, object]:
    """Return one local-only review PII screening row."""
    return {
        "schema_version": "naver-tampermonkey-review-pii-screening-manifest-v1",
        "fixture_id": "naver-tm-review-pii-000001",
        "source": "naver_tampermonkey",
        "section": "review",
        "image_path": "$NAVER_TAMPERMONKEY_SOURCE_ROOT/review.jpg",
        "image_ref_hash": "a" * 64,
        "category_key": "omega_3",
        "contains_personal_data": None,
        "pii_screening_status": "pending_local_screening",
        "external_transfer_allowed": False,
        "local_processing_allowed": True,
        "operator_decision_required": True,
    }


def _manifest_rows(count: int) -> list[dict[str, object]]:
    """Return multiple local-only review PII screening rows."""
    rows: list[dict[str, object]] = []
    for index in range(1, count + 1):
        row = _manifest_row()
        row["fixture_id"] = f"naver-tm-review-pii-{index:06d}"
        row["image_ref_hash"] = f"{index:064x}"[-64:]
        rows.append(row)
    return rows


def _response_content(**overrides: object) -> str:
    """Return a schema-valid local model response content string."""
    payload: dict[str, object] = {
        "status_suggestion": "needs_operator_review",
        "confidence_bucket": "low",
        "evidence_codes": ["uncertain"],
        "reason_codes": ["operator_required"],
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _ollama_response(content: str) -> dict[str, object]:
    """Return a fake Ollama Chat API response."""
    return {"message": {"content": content}, "done": True}


def test_run_review_pii_screening_suggestions_posts_local_image_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the runner sends image bytes locally and stores only safe suggestions."""
    image = tmp_path / "source" / "review.jpg"
    image.parent.mkdir()
    image.write_bytes(b"review-image")
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(image.parent))
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    fake_client = _FakeClient(_ollama_response(_response_content()))

    result = runner.run_review_pii_screening_suggestions(
        manifest_path=manifest_path,
        model="gemma4:e4b",
        ollama_base_url="http://127.0.0.1:11434",
        timeout_sec=3.0,
        http_client=fake_client,
    )

    assert result.summary["suggestion_row_count"] == 1
    assert result.summary["external_transfer_allowed_rows"] == 0
    assert result.rows == [
        {
            "fixture_id": "naver-tm-review-pii-000001",
            "pii_screening_suggestion": {
                "model_id": "gemma4:e4b",
                "generated_at": result.rows[0]["pii_screening_suggestion"]["generated_at"],  # type: ignore[index]
                "status_suggestion": "needs_operator_review",
                "confidence_bucket": "low",
                "evidence_codes": ["uncertain"],
                "reason_codes": ["operator_required"],
            },
        }
    ]
    assert len(fake_client.requests) == 1
    request = fake_client.requests[0]
    assert request["url"] == "http://127.0.0.1:11434/api/chat"
    assert request["timeout"] == 3.0
    payload = request["json"]
    assert payload["model"] == "gemma4:e4b"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["format"]["additionalProperties"] is False
    user_message = payload["messages"][1]
    assert base64.b64decode(user_message["images"][0]) == b"review-image"
    serialized = json.dumps({"rows": result.rows, "summary": result.summary}, ensure_ascii=False)
    assert "review-image" not in serialized
    assert "images" not in serialized
    assert '"raw_model_response":' not in serialized
    assert "/Volumes/" not in serialized


def test_run_review_pii_screening_suggestions_output_matches_export_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify runner output can only become non-importable exported suggestions."""
    image = tmp_path / "source" / "review.jpg"
    image.parent.mkdir()
    image.write_bytes(b"review-image")
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(image.parent))
    manifest_path = tmp_path / "manifest.jsonl"
    suggestions_path = tmp_path / "model-suggestions.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    fake_client = _FakeClient(_ollama_response(_response_content(status_suggestion="likely_clear")))
    result = runner.run_review_pii_screening_suggestions(
        manifest_path=manifest_path,
        http_client=fake_client,
    )
    _write_jsonl(suggestions_path, result.rows)

    exported, summary = exporter.export_review_pii_screening_suggestions(
        manifest_path=manifest_path,
        suggestions_path=suggestions_path,
    )

    assert summary["decision_importable_rows"] == 0
    assert exported[0]["status_suggestion"] == "likely_clear"
    assert exported[0]["decision_importable"] is False
    assert exported[0]["operator_decision_required"] is True


def test_run_review_pii_screening_suggestions_deduplicates_model_tokens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify repeated allowed model tokens are stored once."""
    image = tmp_path / "source" / "review.jpg"
    image.parent.mkdir()
    image.write_bytes(b"review-image")
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(image.parent))
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    fake_client = _FakeClient(
        _ollama_response(
            _response_content(
                evidence_codes=["uncertain", "product_only", "uncertain"],
                reason_codes=["operator_required", "operator_required"],
            )
        )
    )

    result = runner.run_review_pii_screening_suggestions(
        manifest_path=manifest_path,
        http_client=fake_client,
    )

    suggestion = result.rows[0]["pii_screening_suggestion"]
    assert suggestion["evidence_codes"] == ["uncertain", "product_only"]  # type: ignore[index]
    assert suggestion["reason_codes"] == ["operator_required"]  # type: ignore[index]


def test_run_review_pii_screening_suggestions_dry_run_skips_model_call(tmp_path: Path) -> None:
    """Verify dry-run writes only a redacted execution plan."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    fake_client = _FakeClient(_ollama_response(_response_content()))

    result = runner.run_review_pii_screening_suggestions(
        manifest_path=manifest_path,
        dry_run=True,
        http_client=fake_client,
    )

    assert result.rows == []
    assert fake_client.requests == []
    assert result.summary["dry_run"] is True
    assert result.summary["selected_row_count"] == 1
    assert result.summary["suggestion_row_count"] == 0
    assert result.summary["request_payload_stored"] is False


def test_run_review_pii_screening_suggestions_dry_run_can_plan_large_batch(
    tmp_path: Path,
) -> None:
    """Verify large dry-runs stay allowed and redacted."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(
        manifest_path,
        _manifest_rows(runner.MAX_UNCONFIRMED_RUN_ROWS + 1),
    )

    result = runner.run_review_pii_screening_suggestions(
        manifest_path=manifest_path,
        dry_run=True,
    )

    assert result.rows == []
    assert result.summary["selected_row_count"] == runner.MAX_UNCONFIRMED_RUN_ROWS + 1
    assert result.summary["large_run_threshold"] == runner.MAX_UNCONFIRMED_RUN_ROWS
    assert result.summary["large_run_approved"] is False
    assert result.summary["request_payload_stored"] is False


def test_run_review_pii_screening_suggestions_rejects_large_batch_without_approval(
    tmp_path: Path,
) -> None:
    """Verify non-dry-run batches require explicit large-run approval."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(
        manifest_path,
        _manifest_rows(runner.MAX_UNCONFIRMED_RUN_ROWS + 1),
    )
    fake_client = _FakeClient(_ollama_response(_response_content()))

    with pytest.raises(ValueError, match="--allow-large-run"):
        runner.run_review_pii_screening_suggestions(
            manifest_path=manifest_path,
            http_client=fake_client,
        )

    assert fake_client.requests == []


def test_run_review_pii_screening_suggestions_rejects_non_object_rows_without_path_leak(
    tmp_path: Path,
) -> None:
    """Verify direct runner errors do not include the input path."""
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        runner.run_review_pii_screening_suggestions(manifest_path=manifest_path)

    assert str(tmp_path) not in str(exc_info.value)
    assert str(manifest_path) not in str(exc_info.value)
    assert str(exc_info.value) == "JSONL rows must be objects."


def test_main_large_batch_error_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify CLI failures do not print tracebacks or local paths."""
    manifest_path = tmp_path / "manifest.jsonl"
    output_path = tmp_path / "suggestions.jsonl"
    summary_path = tmp_path / "summary.json"
    _write_jsonl(
        manifest_path,
        _manifest_rows(runner.MAX_UNCONFIRMED_RUN_ROWS + 1),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_naver_tampermonkey_review_pii_screening_suggestions.py",
            "--manifest",
            str(manifest_path),
            "--output",
            str(output_path),
            "--summary",
            str(summary_path),
            "--limit",
            str(runner.MAX_UNCONFIRMED_RUN_ROWS + 1),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        runner.main()

    printed = capsys.readouterr().out
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert exc_info.value.code == 1
    assert "Traceback" not in printed
    assert str(tmp_path) not in printed
    assert str(tmp_path) not in json.dumps(summary, ensure_ascii=False)
    assert summary["status"] == "error"
    assert summary["error_code"] == "validation_error"
    assert summary["error_message"] == (
        "Large PII suggestion runs require --allow-large-run or a smaller --limit."
    )
    assert summary["raw_model_response_stored"] is False
    assert not output_path.exists()


def test_run_review_pii_screening_suggestions_rejects_remote_ollama_url(tmp_path: Path) -> None:
    """Verify review images cannot be sent to remote Ollama endpoints."""
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])

    with pytest.raises(ValueError, match="localhost"):
        runner.run_review_pii_screening_suggestions(
            manifest_path=manifest_path,
            ollama_base_url="https://ollama.example.com",
        )


def test_run_review_pii_screening_suggestions_rejects_raw_model_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify raw model payload fields from local responses fail closed."""
    image = tmp_path / "source" / "review.jpg"
    image.parent.mkdir()
    image.write_bytes(b"review-image")
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(image.parent))
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    fake_client = _FakeClient(_ollama_response(_response_content(raw_model_response="secret")))

    with pytest.raises(ValueError, match="raw_model_response"):
        runner.run_review_pii_screening_suggestions(
            manifest_path=manifest_path,
            http_client=fake_client,
        )


def test_run_review_pii_screening_suggestions_rejects_unexpected_response_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify model output cannot include ignored free-form PII fields."""
    image = tmp_path / "source" / "review.jpg"
    image.parent.mkdir()
    image.write_bytes(b"review-image")
    monkeypatch.setenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", str(image.parent))
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])
    fake_client = _FakeClient(_ollama_response(_response_content(person_name="hong_gildong")))

    with pytest.raises(ValueError, match="unsupported field"):
        runner.run_review_pii_screening_suggestions(
            manifest_path=manifest_path,
            http_client=fake_client,
        )


def test_run_review_pii_screening_suggestions_rejects_unset_image_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify image bytes are not read without an explicit token root."""
    monkeypatch.delenv("NAVER_TAMPERMONKEY_SOURCE_ROOT", raising=False)
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(manifest_path, [_manifest_row()])

    with pytest.raises(ValueError, match="env is not set"):
        runner.run_review_pii_screening_suggestions(
            manifest_path=manifest_path,
            http_client=_FakeClient(_ollama_response(_response_content())),
        )
