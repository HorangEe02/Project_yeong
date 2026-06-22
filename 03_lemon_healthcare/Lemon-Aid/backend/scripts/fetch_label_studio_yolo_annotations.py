"""Pull YOLO section annotations from Label Studio and convert them for Chain B.

Authenticates to a local Label Studio instance with the Personal Access Token in
``LABEL_STUDIO_API_TOKEN`` (``.env`` via :func:`src.config.get_settings`, or the
``--token`` override), exports the chosen project's annotations through the REST
API, and runs :mod:`convert_label_studio_yolo_annotations` to merge the drawn
boxes onto the annotation template — producing the JSONL that the existing YOLO
gate chain (reconcile -> preflight -> promote -> materialize -> validate -> gate)
consumes. This removes the manual "Export JSON" step.

Auth is version-tolerant: it tries the legacy ``Authorization: Token <token>``
header first, then the newer Personal Access Token refresh flow
(``POST /api/token/refresh`` -> ``Authorization: Bearer <access>``).

Only labels and normalized coordinates are written downstream; no raw OCR text,
provider payloads, or local paths. Dry-run by default; pass ``--apply`` to write.

References:
    https://labelstud.io/api
    https://labelstud.io/guide/access_tokens
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from src.config import get_settings

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CONVERTER = Path(__file__).resolve().parent / "convert_label_studio_yolo_annotations.py"
REQUEST_TIMEOUT_SECONDS = 60
HTTP_OK = 200


def _request(
    url: str, *, headers: dict[str, str], method: str = "GET", body: dict[str, Any] | None = None
) -> tuple[int, bytes]:
    """Perform an HTTP request and return ``(status_code, body_bytes)``.

    Args:
        url: Absolute request URL.
        headers: Request headers.
        method: HTTP method.
        body: Optional JSON body.

    Returns:
        The HTTP status code and raw response body (empty on transport error).
    """
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise SystemExit(f"ERROR: cannot reach Label Studio at {url}: {exc}") from exc


def _resolve_auth_headers(base_url: str, token: str) -> dict[str, str]:
    """Return working Authorization headers for the Label Studio API.

    Tries the legacy access-token header, then the Personal Access Token refresh
    flow (exchanging the PAT for a short-lived bearer access token).

    Args:
        base_url: Label Studio base URL (no trailing slash).
        token: The configured access/personal token.

    Returns:
        Headers including a working ``Authorization`` value.

    Raises:
        SystemExit: If neither auth scheme is accepted.
    """
    probe = f"{base_url}/api/projects?page_size=1"
    legacy = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    status, _ = _request(probe, headers=legacy)
    if status == HTTP_OK:
        return legacy
    refresh_status, refresh_body = _request(
        f"{base_url}/api/token/refresh",
        headers={"Content-Type": "application/json"},
        method="POST",
        body={"refresh": token},
    )
    if refresh_status == HTTP_OK:
        access = json.loads(refresh_body).get("access")
        if access:
            return {"Authorization": f"Bearer {access}", "Content-Type": "application/json"}
    raise SystemExit(
        "ERROR: Label Studio rejected the token (legacy Token and PAT refresh both failed). "
        "Check LABEL_STUDIO_API_TOKEN and that the URL points at your Label Studio instance."
    )


def _resolve_project_id(base_url: str, headers: dict[str, str], wanted: int | None) -> int:
    """Return the project id to export, auto-selecting a YOLO section project.

    Args:
        base_url: Label Studio base URL.
        headers: Authorized request headers.
        wanted: Explicit project id, or None to auto-select.

    Returns:
        The resolved project id.

    Raises:
        SystemExit: If no suitable project can be found.
    """
    if wanted is not None:
        return wanted
    status, raw = _request(f"{base_url}/api/projects?page_size=200", headers=headers)
    if status != HTTP_OK:
        raise SystemExit(f"ERROR: listing Label Studio projects failed (HTTP {status}).")
    payload = json.loads(raw)
    projects = payload.get("results", payload) if isinstance(payload, dict) else payload
    if not projects:
        raise SystemExit("ERROR: no Label Studio projects found for this token.")
    for project in projects:
        title = str(project.get("title", "")).lower()
        if "yolo" in title or "section" in title or "annotation" in title:
            return int(project["id"])
    if len(projects) == 1:
        return int(projects[0]["id"])
    titles = ", ".join(f"{p.get('id')}:{p.get('title')}" for p in projects)
    raise SystemExit(f"ERROR: multiple projects; pass --project-id. Available: {titles}")


def _export_annotations(base_url: str, headers: dict[str, str], project_id: int) -> list[Any]:
    """Export a project's annotations as Label Studio JSON.

    Args:
        base_url: Label Studio base URL.
        headers: Authorized request headers.
        project_id: Project to export.

    Returns:
        The parsed Label Studio export (a list of task records).

    Raises:
        SystemExit: If the export request fails or is not a JSON array.
    """
    url = f"{base_url}/api/projects/{project_id}/export?exportType=JSON&download_all_tasks=true"
    status, raw = _request(url, headers=headers)
    if status != HTTP_OK:
        raise SystemExit(f"ERROR: export failed (HTTP {status}) for project {project_id}.")
    export = json.loads(raw)
    if not isinstance(export, list):
        raise SystemExit("ERROR: Label Studio export was not a JSON array of tasks.")
    return export


def _run_converter(*, export_path: Path, template: Path, output: Path) -> int:
    """Invoke the Label Studio -> pipeline converter as a subprocess.

    Args:
        export_path: Saved Label Studio export JSON.
        template: Annotation template JSONL to merge boxes onto.
        output: Converted annotation JSONL output path.

    Returns:
        The converter process return code.
    """
    return subprocess.run(
        [
            sys.executable,
            str(CONVERTER),
            "--label-studio-export",
            str(export_path),
            "--template",
            str(template),
            "--output",
            str(output),
            "--apply",
        ],
        check=False,
    ).returncode


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True, help="Annotation template JSONL.")
    parser.add_argument("--output", type=Path, required=True, help="Converted annotation JSONL.")
    parser.add_argument(
        "--export-out", type=Path, default=None, help="Where to save the raw export."
    )
    parser.add_argument("--project-id", type=int, default=None)
    parser.add_argument("--url", default=None, help="Override LABEL_STUDIO_URL.")
    parser.add_argument("--token", default=None, help="Override LABEL_STUDIO_API_TOKEN.")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings()
    base_url = (args.url or settings.label_studio_url).rstrip("/")
    token = args.token
    if token is None and settings.label_studio_api_token is not None:
        token = settings.label_studio_api_token.get_secret_value()
    if not token:
        raise SystemExit("ERROR: no Label Studio token (set LABEL_STUDIO_API_TOKEN or --token).")

    if not args.apply:
        print(json.dumps({"apply_requested": False, "base_url": base_url}, ensure_ascii=False))
        return 0

    headers = _resolve_auth_headers(base_url, token)
    project_id = _resolve_project_id(base_url, headers, args.project_id)
    export = _export_annotations(base_url, headers, project_id)
    export_out = args.export_out or args.output.with_suffix(".label-studio-export.json")
    export_out.parent.mkdir(parents=True, exist_ok=True)
    export_out.write_text(json.dumps(export, ensure_ascii=False), encoding="utf-8")

    code = _run_converter(export_path=export_out, template=args.template, output=args.output)
    summary = {
        "apply_requested": True,
        "base_url": base_url,
        "project_id": project_id,
        "exported_tasks": len(export),
        "export_out": str(export_out),
        "converter_returncode": code,
        "output": str(args.output),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
