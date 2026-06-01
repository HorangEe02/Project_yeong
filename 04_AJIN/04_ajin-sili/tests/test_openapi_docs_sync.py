"""Regression tests for OpenAPI-derived documentation counts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


def _load_openapi_spec() -> dict[str, Any]:
    """Load the committed OpenAPI document.

    Returns:
        Parsed OpenAPI JSON object.

    Raises:
        OSError: If the OpenAPI document cannot be read.
        json.JSONDecodeError: If the document is not valid JSON.
    """

    return json.loads((ROOT / "docs/openapi.json").read_text(encoding="utf-8"))


def _operation_count(spec: dict[str, Any]) -> int:
    """Count OpenAPI operations using the official path + method identity.

    Args:
        spec: Parsed OpenAPI document.

    Returns:
        Number of HTTP method operations under ``paths``.

    Raises:
        None.
    """

    count = 0
    for path_item in spec.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        count += sum(1 for method in path_item if method.lower() in HTTP_METHODS)
    return count


def test_api_markdown_count_matches_openapi_spec() -> None:
    """docs/API.md must report the same endpoint count as docs/openapi.json."""

    spec = _load_openapi_spec()
    api_markdown = (ROOT / "docs/API.md").read_text(encoding="utf-8")
    match = re.search(r"- \*\*총 endpoint:\*\* \*\*(\d+)\*\*", api_markdown)

    assert match, "docs/API.md is missing the generated total endpoint line"
    assert int(match.group(1)) == _operation_count(spec)


def test_summary_artifacts_match_openapi_spec() -> None:
    """Generated summary JSON and Markdown must match the OpenAPI spec counts."""

    spec = _load_openapi_spec()
    path_count = len(spec.get("paths", {}))
    endpoint_count = _operation_count(spec)

    summary = json.loads((ROOT / "docs/openapi-summary.json").read_text(encoding="utf-8"))
    summary_markdown = (ROOT / "docs/generated/openapi-summary.md").read_text(encoding="utf-8")

    assert summary["path_count"] == path_count
    assert summary["operation_count"] == endpoint_count
    assert sum(item["endpoint_count"] for item in summary["feature_counts"]) == endpoint_count
    assert sum(summary["tag_counts"].values()) == endpoint_count
    assert f"- **총 path:** **{path_count}**" in summary_markdown
    assert f"- **총 endpoint:** **{endpoint_count}**" in summary_markdown


def test_readme_openapi_block_matches_summary() -> None:
    """README should use the generated OpenAPI summary block instead of stale numbers."""

    summary = json.loads((ROOT / "docs/openapi-summary.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "<!-- OPENAPI_SUMMARY:START -->" in readme
    assert "<!-- OPENAPI_SUMMARY:END -->" in readme
    assert f"- **총 path:** **{summary['path_count']}**" in readme
    assert f"- **총 endpoint:** **{summary['operation_count']}**" in readme
    assert "모듈 수는 OpenAPI에서 검증할 수 없는 코드 구조 수치" in readme


def test_stale_endpoint_literals_not_reintroduced() -> None:
    """High-visibility docs must not reintroduce old hand-written endpoint totals."""

    stale_patterns = (
        r"178 endpoint",
        r"API 인덱스 \(178 endpoint\)",
        r"152.*26.*178 endpoint",
        r"FastAPI 178",
        r"68 endpoint",
        r"Endpoint\s+68",
        r"백엔드 Endpoint.*68개",
        r"백엔드 Endpoint 목록 \(43개\)",
        r"Endpoint\s+43",
        r"`/api/onboarding/\.\.\.` 11개 endpoint",
        r"Endpoint\s+11개",
        r"\*\*FastAPI\*\* \| 12 endpoint",
        r"Endpoint\s+12",
    )
    checked_paths = (
        ROOT / "README.md",
        ROOT / "docs/DEMO_SCRIPT.md",
        ROOT / "docs/FEATURE_A_SEARCH.md",
        ROOT / "docs/FEATURE_B_DRAFT.md",
        ROOT / "docs/FEATURE_C_ONBOARDING.md",
        ROOT / "docs/FEATURE_D_COMPLIANCE.md",
        ROOT / "docs/FEATURE_E_ADMIN.md",
        ROOT / "docs/FEATURE_F_EQUIPMENT.md",
    )

    for path in checked_paths:
        text = path.read_text(encoding="utf-8")
        for pattern in stale_patterns:
            assert not re.search(pattern, text), f"{path.relative_to(ROOT)} contains stale {pattern!r}"
