#!/usr/bin/env python3
"""Copy a Firebase Storage export directory into Supabase Storage.

기본은 파일 manifest 생성용 dry-run이다. `--apply`는 로컬 export 파일을
Supabase private bucket에 업로드한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.supabase_storage import bucket_for_type, get_storage_settings  # noqa: E402


def _client():
    """Create a Supabase Python client lazily."""
    settings = get_storage_settings(required=True)
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError("supabase package is required for --apply") from exc
    return create_client(settings.url, settings.service_key)


def _sha256(path: Path) -> str:
    """Compute a file SHA-256 checksum."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_files(source_dir: Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Discover files from a Firebase Storage export directory.

    Args:
        source_dir: Local Firebase Storage export directory.
        limit: Optional file count limit.

    Returns:
        list[dict[str, Any]]: File manifest rows.
    """
    rows: list[dict[str, Any]] = []
    for path in sorted(p for p in source_dir.rglob("*") if p.is_file()):
        object_path = path.relative_to(source_dir).as_posix()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        rows.append(
            {
                "source_path": str(path),
                "object_path": object_path,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
                "content_type": content_type,
            }
        )
        if limit is not None and len(rows) >= limit:
            break
    return rows


def load_manifest(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Load a JSON manifest produced by dry-run."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    files = raw.get("files", raw) if isinstance(raw, dict) else raw
    if not isinstance(files, list):
        raise ValueError("manifest must be a list or an object with files")
    rows = [dict(item) for item in files if isinstance(item, dict)]
    return rows if limit is None else rows[:limit]


def upload_files(bucket: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Upload manifest rows to Supabase Storage.

    Args:
        bucket: Supabase bucket name.
        rows: Manifest rows with source_path and object_path.

    Returns:
        list[dict[str, Any]]: Per-file upload results.
    """
    storage = _client().storage.from_(bucket)
    results: list[dict[str, Any]] = []
    for row in rows:
        source_path = Path(str(row["source_path"]))
        object_path = str(row["object_path"]).lstrip("/")
        content_type = str(row.get("content_type") or "application/octet-stream")
        with source_path.open("rb") as handle:
            storage.upload(
                path=object_path,
                file=handle,
                file_options={
                    "cache-control": "3600",
                    "content-type": content_type,
                    "upsert": "false",
                },
            )
        results.append({"object_path": object_path, "size_bytes": row.get("size_bytes", 0)})
    return results


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-dir", type=Path)
    source.add_argument("--manifest-json", type=Path)
    parser.add_argument("--bucket-type", choices=["attachments", "draft_exports"], default="attachments")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--report-json", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    """Run the Firebase Storage to Supabase copy command."""
    args = parse_args()
    if args.source_dir:
        files = discover_files(args.source_dir, args.limit)
    else:
        files = load_manifest(args.manifest_json, args.limit)

    report: dict[str, Any] = {
        "mode": "apply" if args.apply else "dry-run",
        "bucket_type": args.bucket_type,
        "files": files,
        "total_files": len(files),
        "total_bytes": sum(int(row.get("size_bytes") or 0) for row in files),
    }
    if args.apply:
        report["bucket"] = bucket_for_type(args.bucket_type)
        report["uploaded"] = upload_files(report["bucket"], files)

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
