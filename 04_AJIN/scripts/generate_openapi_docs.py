#!/usr/bin/env python3
"""Generate the committed OpenAPI spec and API index documentation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
GENERATED_DOCS_DIR = DOCS_DIR / "generated"
OPENAPI_PATH = DOCS_DIR / "openapi.json"
API_MD_PATH = DOCS_DIR / "API.md"
OPENAPI_SUMMARY_PATH = DOCS_DIR / "openapi-summary.json"
OPENAPI_SUMMARY_MD_PATH = GENERATED_DOCS_DIR / "openapi-summary.md"
README_PATH = ROOT / "README.md"

README_SUMMARY_START = "<!-- OPENAPI_SUMMARY:START -->"
README_SUMMARY_END = "<!-- OPENAPI_SUMMARY:END -->"

HTTP_METHOD_ORDER = ("get", "post", "put", "patch", "delete", "options", "head", "trace")
HTTP_METHOD_RANK = {method: index for index, method in enumerate(HTTP_METHOD_ORDER)}

FEATURE_GROUPS = (
    {
        "code": "A",
        "domain": "검색·조직도",
        "tags": ("search", "employee", "directory"),
        "doc": "[docs/FEATURE_A_SEARCH.md](FEATURE_A_SEARCH.md)",
    },
    {
        "code": "B",
        "domain": "문서 작성",
        "tags": ("draft",),
        "doc": "[docs/FEATURE_B_DRAFT.md](FEATURE_B_DRAFT.md)",
    },
    {
        "code": "C",
        "domain": "AI 업무 도우미",
        "tags": ("onboarding", "scenarios", "feature-flags"),
        "doc": "[docs/FEATURE_C_ONBOARDING.md](FEATURE_C_ONBOARDING.md)",
    },
    {
        "code": "D",
        "domain": "법규 모니터링",
        "tags": ("compliance", "notifications"),
        "doc": "[docs/FEATURE_D_COMPLIANCE.md](FEATURE_D_COMPLIANCE.md)",
    },
    {
        "code": "E",
        "domain": "인사·관리",
        "tags": ("admin", "admin-scenarios", "auth", "idp"),
        "doc": "[docs/FEATURE_E_ADMIN.md](FEATURE_E_ADMIN.md)",
    },
    {
        "code": "F",
        "domain": "설비·SPC",
        "tags": ("equipment",),
        "doc": "[docs/FEATURE_F_EQUIPMENT.md](FEATURE_F_EQUIPMENT.md)",
    },
    {
        "code": "공통",
        "domain": "인프라·헬스·모델",
        "tags": ("dashboard", "models", "export", "health", "me", "slack", "untagged"),
        "doc": "—",
    },
)


@dataclass(frozen=True)
class Operation:
    """OpenAPI path operation summarized for the Markdown index.

    Args:
        tag: First OpenAPI tag for the operation, or ``untagged``.
        method: Uppercase HTTP method.
        path: OpenAPI path template.
        summary: Human-readable operation summary.

    Raises:
        None.
    """

    tag: str
    method: str
    path: str
    summary: str


@dataclass(frozen=True)
class FeatureEndpointSummary:
    """Endpoint count aggregated for one product feature group.

    Args:
        code: Product feature code such as ``A`` or ``공통``.
        domain: Human-readable business domain.
        tags: OpenAPI tags counted for the feature.
        endpoint_count: Number of OpenAPI operations under the tags.
        doc: Markdown link to the detailed feature document.

    Raises:
        None.
    """

    code: str
    domain: str
    tags: tuple[str, ...]
    endpoint_count: int
    doc: str


@dataclass(frozen=True)
class OpenAPISummary:
    """Deterministic count summary derived from the OpenAPI document.

    Args:
        api_version: Application API version from OpenAPI ``info.version``.
        openapi_version: OpenAPI specification version.
        path_count: Number of path templates in the OpenAPI ``paths`` object.
        operation_count: Number of HTTP method operations across all paths.
        openapi_size_kb: Serialized ``docs/openapi.json`` size in KiB.
        feature_counts: Feature-group endpoint counts.
        tag_counts: Endpoint counts by OpenAPI tag.

    Raises:
        None.
    """

    api_version: str
    openapi_version: str
    path_count: int
    operation_count: int
    openapi_size_kb: int
    feature_counts: tuple[FeatureEndpointSummary, ...]
    tag_counts: dict[str, int]


def load_app() -> Any:
    """Import the FastAPI app without starting a server or lifespan services.

    Returns:
        The ``backend.main.app`` FastAPI instance.

    Raises:
        ImportError: If the backend application cannot be imported.
    """

    os.chdir(ROOT)
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    from backend.main import app

    return app


def build_openapi_spec() -> dict[str, Any]:
    """Build the current OpenAPI schema from the registered FastAPI routes.

    Returns:
        A JSON-serializable OpenAPI document.

    Raises:
        RuntimeError: If FastAPI does not return a mapping-like schema.
    """

    app = load_app()
    spec = app.openapi()
    if not isinstance(spec, dict):
        raise RuntimeError("app.openapi() did not return an OpenAPI mapping")
    return spec


def collect_operations(spec: dict[str, Any]) -> list[Operation]:
    """Collect path operations from an OpenAPI document.

    Args:
        spec: OpenAPI document generated by FastAPI.

    Returns:
        Operations sorted by tag, path, and stable HTTP method order.

    Raises:
        ValueError: If ``paths`` is not an object.
    """

    paths = spec.get("paths", {})
    if not isinstance(paths, dict):
        raise ValueError("OpenAPI spec paths must be an object")

    operations: list[Operation] = []
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in HTTP_METHOD_ORDER:
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            tags = operation.get("tags") or ["untagged"]
            tag = str(tags[0]) if tags else "untagged"
            operations.append(
                Operation(
                    tag=tag,
                    method=method.upper(),
                    path=str(path),
                    summary=str(operation.get("summary") or ""),
                )
            )

    tag_order = tag_sort_order(operations)
    return sorted(
        operations,
        key=lambda item: (
            tag_order.get(item.tag, len(tag_order)),
            item.path,
            HTTP_METHOD_RANK.get(item.method.lower(), len(HTTP_METHOD_RANK)),
        ),
    )


def tag_sort_order(operations: Sequence[Operation]) -> dict[str, int]:
    """Create a stable tag order from feature groups and discovered unknown tags.

    Args:
        operations: Operations extracted from the OpenAPI document.

    Returns:
        Mapping from tag name to display order.

    Raises:
        None.
    """

    ordered_tags: list[str] = []
    discovered = {operation.tag for operation in operations}
    for group in FEATURE_GROUPS:
        for tag in group["tags"]:
            if tag in discovered and tag not in ordered_tags:
                ordered_tags.append(tag)

    for tag in sorted(discovered):
        if tag not in ordered_tags:
            ordered_tags.append(tag)

    return {tag: index for index, tag in enumerate(ordered_tags)}


def render_openapi_json(spec: dict[str, Any]) -> str:
    """Serialize the OpenAPI document with deterministic formatting.

    Args:
        spec: OpenAPI document generated by FastAPI.

    Returns:
        Pretty-printed JSON text ending with a newline.

    Raises:
        TypeError: If the schema contains non-serializable values.
    """

    return json.dumps(spec, ensure_ascii=False, indent=2) + "\n"


def markdown_cell(value: str) -> str:
    """Escape a value for safe use inside a Markdown table cell.

    Args:
        value: Raw text from the OpenAPI operation.

    Returns:
        Escaped Markdown table cell text.

    Raises:
        None.
    """

    return value.replace("|", "\\|").replace("\n", "<br>")


def feature_code_for_tag(tag: str) -> str:
    """Resolve the feature code for a tag.

    Args:
        tag: OpenAPI tag name.

    Returns:
        Feature code, or ``공통`` for unmapped tags.

    Raises:
        None.
    """

    for group in FEATURE_GROUPS:
        if tag in group["tags"]:
            return str(group["code"])
    return "공통"


def count_operations_by_tag(operations: Sequence[Operation]) -> dict[str, int]:
    """Count operations by first OpenAPI tag.

    Args:
        operations: Operations extracted from an OpenAPI document.

    Returns:
        Mapping of tag name to operation count.

    Raises:
        None.
    """

    counts_by_tag: dict[str, int] = {}
    for operation in operations:
        counts_by_tag[operation.tag] = counts_by_tag.get(operation.tag, 0) + 1
    return dict(sorted(counts_by_tag.items()))


def summarize_feature_counts(operations: Sequence[Operation]) -> tuple[FeatureEndpointSummary, ...]:
    """Aggregate endpoint counts according to the documented feature groups.

    Args:
        operations: Operations extracted from an OpenAPI document.

    Returns:
        Feature summaries in the same order used by ``docs/API.md``.

    Raises:
        None.
    """

    counts_by_tag = count_operations_by_tag(operations)
    known_tags = {tag for group in FEATURE_GROUPS for tag in group["tags"]}
    unknown_tags = sorted(tag for tag in counts_by_tag if tag not in known_tags)

    summaries: list[FeatureEndpointSummary] = []
    for group in FEATURE_GROUPS:
        tags = list(group["tags"])
        if group["code"] == "공통":
            tags.extend(unknown_tags)
        visible_tags = tuple(tag for tag in tags if tag in counts_by_tag)
        endpoint_count = sum(counts_by_tag.get(tag, 0) for tag in visible_tags)
        summaries.append(
            FeatureEndpointSummary(
                code=str(group["code"]),
                domain=str(group["domain"]),
                tags=visible_tags,
                endpoint_count=endpoint_count,
                doc=str(group["doc"]),
            )
        )
    return tuple(summaries)


def build_openapi_summary(spec: dict[str, Any], openapi_json_text: str) -> OpenAPISummary:
    """Build deterministic count metadata from a generated OpenAPI document.

    Args:
        spec: OpenAPI document generated by FastAPI.
        openapi_json_text: Serialized JSON text used to compute the displayed size.

    Returns:
        Summary used by generated docs and README blocks.

    Raises:
        KeyError: If required OpenAPI metadata is missing.
    """

    info = spec["info"]
    operations = collect_operations(spec)
    return OpenAPISummary(
        api_version=str(info["version"]),
        openapi_version=str(spec["openapi"]),
        path_count=len(spec.get("paths", {})),
        operation_count=len(operations),
        openapi_size_kb=max(1, round(len(openapi_json_text.encode("utf-8")) / 1024)),
        feature_counts=summarize_feature_counts(operations),
        tag_counts=count_operations_by_tag(operations),
    )


def render_openapi_summary_json(summary: OpenAPISummary) -> str:
    """Serialize the OpenAPI count summary with deterministic formatting.

    Args:
        summary: Summary derived from the current OpenAPI document.

    Returns:
        Pretty-printed JSON text ending with a newline.

    Raises:
        TypeError: If the summary contains non-serializable values.
    """

    payload = {
        "api_version": summary.api_version,
        "openapi_version": summary.openapi_version,
        "path_count": summary.path_count,
        "operation_count": summary.operation_count,
        "openapi_size_kb": summary.openapi_size_kb,
        "feature_counts": [
            {
                "code": item.code,
                "domain": item.domain,
                "tags": list(item.tags),
                "endpoint_count": item.endpoint_count,
                "doc": item.doc,
            }
            for item in summary.feature_counts
        ],
        "tag_counts": summary.tag_counts,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def render_feature_table(operations: Sequence[Operation]) -> str:
    """Render the feature distribution table from operation tags.

    Args:
        operations: Operations extracted from the OpenAPI document.

    Returns:
        Markdown table text.

    Raises:
        None.
    """

    lines = [
        "| Feature | 도메인 | Tag | endpoint 수 | 상세 문서 |",
        "|---|---|---|---:|---|",
    ]
    total = 0
    for summary in summarize_feature_counts(operations):
        total += summary.endpoint_count
        tag_text = ", ".join(f"`{tag}`" for tag in summary.tags) if summary.tags else "—"
        lines.append(
            f"| **{summary.code}** | {summary.domain} | {tag_text} | **{summary.endpoint_count}** | {summary.doc} |"
        )

    lines.append(f"| 합계 | | | **{total}** | |")
    return "\n".join(lines)


def render_summary_feature_table(summary: OpenAPISummary) -> str:
    """Render a compact feature endpoint table for generated summary docs.

    Args:
        summary: Summary derived from the current OpenAPI document.

    Returns:
        Markdown table text without relative document links.

    Raises:
        None.
    """

    lines = [
        "| Feature | 도메인 | OpenAPI tag | endpoint 수 |",
        "|---|---|---|---:|",
    ]
    for item in summary.feature_counts:
        tag_text = ", ".join(f"`{tag}`" for tag in item.tags) if item.tags else "—"
        lines.append(f"| **{item.code}** | {item.domain} | {tag_text} | **{item.endpoint_count}** |")
    lines.append(f"| 합계 | | | **{summary.operation_count}** |")
    return "\n".join(lines)


def render_tag_count_table(summary: OpenAPISummary) -> str:
    """Render endpoint counts by OpenAPI tag.

    Args:
        summary: Summary derived from the current OpenAPI document.

    Returns:
        Markdown table text.

    Raises:
        None.
    """

    lines = [
        "| Tag | endpoint 수 |",
        "|---|---:|",
    ]
    for tag, count in summary.tag_counts.items():
        lines.append(f"| `{tag}` | **{count}** |")
    return "\n".join(lines)


def render_openapi_summary_markdown(summary: OpenAPISummary) -> str:
    """Render a small Markdown summary generated from OpenAPI counts.

    Args:
        summary: Summary derived from the current OpenAPI document.

    Returns:
        Markdown text ending with a newline.

    Raises:
        None.
    """

    body = f"""# AJIN AI Assistant OpenAPI Summary

> 이 파일은 `scripts/generate_openapi_docs.py`가 FastAPI `app.openapi()` 결과에서 생성합니다.
> endpoint는 OpenAPI operation, 즉 `METHOD + path` 조합 기준입니다.

- **API 버전:** {summary.api_version}
- **OpenAPI 버전:** {summary.openapi_version}
- **총 path:** **{summary.path_count}**
- **총 endpoint:** **{summary.operation_count}**
- **원본 spec 크기:** **{summary.openapi_size_kb} KB**

## Feature 별 endpoint 분포

{render_summary_feature_table(summary)}

## Tag 별 endpoint 분포

{render_tag_count_table(summary)}
"""
    return body.rstrip() + "\n"


def render_readme_summary_block(summary: OpenAPISummary) -> str:
    """Render the generated README API summary block.

    Args:
        summary: Summary derived from the current OpenAPI document.

    Returns:
        Markdown text between README summary markers.

    Raises:
        None.
    """

    body = f"""{README_SUMMARY_START}
> 이 블록은 `scripts/generate_openapi_docs.py`가 FastAPI `app.openapi()` 기준으로 생성합니다.
> endpoint는 OpenAPI operation(`METHOD + path`) 기준이며, path 수와 구분합니다.

- **API 버전:** {summary.api_version}
- **OpenAPI 버전:** {summary.openapi_version}
- **총 path:** **{summary.path_count}**
- **총 endpoint:** **{summary.operation_count}**
- **상세 인덱스:** [docs/API.md](docs/API.md)
- **머신 리더블 요약:** [docs/openapi-summary.json](docs/openapi-summary.json)

{render_summary_feature_table(summary)}

> 모듈 수는 OpenAPI에서 검증할 수 없는 코드 구조 수치이므로 이 자동 산정 표에서 제외합니다.
{README_SUMMARY_END}"""
    return body.rstrip()


def replace_generated_block(
    text: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
    *,
    path_label: str,
) -> str:
    """Replace a marker-delimited generated block.

    Args:
        text: Existing document text.
        start_marker: Start marker that must exist exactly once.
        end_marker: End marker that must exist after the start marker.
        replacement: Full replacement block including both markers.
        path_label: Human-readable file path for error messages.

    Returns:
        Document text with the generated block replaced.

    Raises:
        ValueError: If either marker is missing or misordered.
    """

    start_index = text.find(start_marker)
    end_index = text.find(end_marker)
    if start_index < 0 or end_index < 0 or end_index < start_index:
        raise ValueError(f"{path_label} is missing generated OpenAPI summary markers")

    end_index += len(end_marker)
    return text[:start_index] + replacement + text[end_index:]


def render_readme(summary: OpenAPISummary) -> str:
    """Render README with its generated OpenAPI summary block refreshed.

    Args:
        summary: Summary derived from the current OpenAPI document.

    Returns:
        README text ending with a newline.

    Raises:
        OSError: If README cannot be read.
        ValueError: If the generated block markers are absent.
    """

    readme_text = README_PATH.read_text(encoding="utf-8")
    rendered = replace_generated_block(
        readme_text,
        README_SUMMARY_START,
        README_SUMMARY_END,
        render_readme_summary_block(summary),
        path_label=str(README_PATH.relative_to(ROOT)),
    )
    return rendered.rstrip() + "\n"


def render_tag_sections(operations: Sequence[Operation]) -> str:
    """Render all endpoint tables grouped by OpenAPI tag.

    Args:
        operations: Operations extracted from the OpenAPI document.

    Returns:
        Markdown sections for each tag.

    Raises:
        None.
    """

    operations_by_tag: dict[str, list[Operation]] = {}
    for operation in operations:
        operations_by_tag.setdefault(operation.tag, []).append(operation)

    sections: list[str] = []
    for tag in tag_sort_order(operations):
        tag_operations = operations_by_tag[tag]
        sections.append(f"### `{tag}` ({feature_code_for_tag(tag)} — {len(tag_operations)}개)")
        sections.append("")
        sections.append("| Method | Path | Summary |")
        sections.append("|---|---|---|")
        for operation in tag_operations:
            sections.append(
                f"| `{operation.method}` | `{operation.path}` | {markdown_cell(operation.summary)} |"
            )
        sections.append("")

    return "\n".join(sections).rstrip()


def render_api_markdown(spec: dict[str, Any], openapi_json_text: str) -> str:
    """Render the human-readable API index from the OpenAPI document.

    Args:
        spec: OpenAPI document generated by FastAPI.
        openapi_json_text: Serialized JSON text used to compute the displayed size.

    Returns:
        Markdown API index ending with a newline.

    Raises:
        KeyError: If required OpenAPI metadata is missing.
    """

    info = spec["info"]
    operations = collect_operations(spec)
    path_count = len(spec.get("paths", {}))
    operation_count = len(operations)
    openapi_size_kb = max(1, round(len(openapi_json_text.encode("utf-8")) / 1024))

    body = f"""# {info["title"]} — OpenAPI 인덱스

> FastAPI 앱에서 생성한 OpenAPI {spec["openapi"]} spec의 사람-친화 인덱스.
> 원본 머신-리더블 spec: [`openapi.json`](openapi.json) ({openapi_size_kb} KB).

- **API 버전:** {info["version"]}
- **OpenAPI 버전:** {spec["openapi"]}
- **총 path:** **{path_count}**
- **총 endpoint:** **{operation_count}**

---

## 재생성 방법

기본 재생성 경로는 호스트 `.venv`에서 FastAPI 앱을 import한 뒤 `app.openapi()` 결과를 저장하는 방식입니다. 서버를 띄우거나 lifespan 서비스를 시작하지 않습니다.

```bash
make openapi-docs
make openapi-docs-check
```

---

## Swagger UI / ReDoc 접근 방법

FastAPI가 두 가지 인터랙티브 문서 UI를 자동 생성합니다. 단, 본 프로젝트는 nginx-rp가 `/api/*`만 backend로 프록시하므로 외부에서는 직접 접근할 수 없습니다.

### 1. 컨테이너 안에서 직접

```bash
# Swagger UI (인터랙티브 — endpoint 호출도 가능)
docker compose exec backend curl -s http://localhost:8080/docs | head -20

# OpenAPI JSON spec
docker compose exec backend curl -s http://localhost:8080/openapi.json > /tmp/spec.json

# 컨테이너 외부 (호스트 macOS)로 복사
docker compose cp backend:/tmp/spec.json ./docs/openapi.json
```

### 2. backend 컨테이너 직접 노출 (개발자용)

docker-compose.yml의 backend service에 `ports: ["8081:8080"]` 추가 후:
- http://localhost:8081/docs (Swagger UI)
- http://localhost:8081/redoc (ReDoc)
- http://localhost:8081/openapi.json (raw spec)

### 3. 외부 도구로 spec import

`docs/openapi.json`을 다음 도구에 업로드:
- **Postman** — Import → File → openapi.json (모든 endpoint 자동 컬렉션)
- **Insomnia** — Import → openapi.json
- **Swagger Editor** (https://editor.swagger.io/) — 온라인 뷰어
- **VS Code OpenAPI 확장** — 인라인 미리보기

---

## Feature 별 endpoint 분포

{render_feature_table(operations)}

---

## 태그 별 endpoint 전체 ({operation_count}개)

{render_tag_sections(operations)}
"""
    return body.rstrip() + "\n"


def build_generated_artifacts() -> dict[Path, str]:
    """Build all generated OpenAPI documentation artifacts.

    Returns:
        Mapping of output path to generated file text.

    Raises:
        OSError: If README cannot be read while refreshing the generated block.
        ValueError: If README generated block markers are absent.
    """

    spec = build_openapi_spec()
    openapi_json_text = render_openapi_json(spec)
    summary = build_openapi_summary(spec, openapi_json_text)
    api_markdown_text = render_api_markdown(spec, openapi_json_text)
    summary_json_text = render_openapi_summary_json(summary)
    summary_markdown_text = render_openapi_summary_markdown(summary)
    readme_text = render_readme(summary)

    return {
        OPENAPI_PATH: openapi_json_text,
        API_MD_PATH: api_markdown_text,
        OPENAPI_SUMMARY_PATH: summary_json_text,
        OPENAPI_SUMMARY_MD_PATH: summary_markdown_text,
        README_PATH: readme_text,
    }


def write_generated_files() -> dict[Path, str]:
    """Generate and write OpenAPI documentation artifacts.

    Returns:
        Mapping of output path to generated file text.

    Raises:
        OSError: If output files cannot be written.
        ValueError: If README generated block markers are absent.
    """

    artifacts = build_generated_artifacts()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for path, text in artifacts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return artifacts


def check_generated_files() -> int:
    """Check that committed documentation artifacts match generated output.

    Returns:
        Process exit code, where ``0`` means files are current and ``1`` means stale.

    Raises:
        OSError: If output files cannot be read.
    """

    artifacts = build_generated_artifacts()

    mismatches = []
    for path, expected_text in artifacts.items():
        if not path.exists() or path.read_text(encoding="utf-8") != expected_text:
            mismatches.append(str(path.relative_to(ROOT)))

    if mismatches:
        print("OpenAPI docs are stale:")
        for path in mismatches:
            print(f"  - {path}")
        print("Run: make openapi-docs")
        return 1

    print("OpenAPI docs are current.")
    return 0


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: CLI arguments excluding the executable name.

    Returns:
        Parsed arguments.

    Raises:
        SystemExit: If argparse detects invalid input.
    """

    parser = argparse.ArgumentParser(description="Generate docs/openapi.json and docs/API.md")
    parser.add_argument("--check", action="store_true", help="fail if generated docs differ")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the OpenAPI documentation generator.

    Args:
        argv: Optional CLI arguments excluding the executable name.

    Returns:
        Process exit code.

    Raises:
        OSError: If file operations fail.
    """

    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.check:
        return check_generated_files()

    artifacts = write_generated_files()
    summary = json.loads(artifacts[OPENAPI_SUMMARY_PATH])
    print(
        f"Wrote {OPENAPI_PATH.relative_to(ROOT)} "
        f"({summary['path_count']} paths, {summary['operation_count']} endpoints)"
    )
    for path, text in artifacts.items():
        if path == OPENAPI_PATH:
            continue
        print(f"Wrote {path.relative_to(ROOT)} ({len(text.encode('utf-8'))} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
