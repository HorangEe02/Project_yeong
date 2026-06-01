"""Repo-local content CMS helpers for Feature C onboarding.

CMS v1 intentionally stores content as JSON files under ``data/knowledge_base``
so release gates and runtime can share the same validation rules without a
database migration.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

ContentKind = Literal["sops", "glossary", "glossary_aliases"]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
KB_ROOT = REPO_ROOT / "data" / "knowledge_base"
CONTENT_DIRS: dict[str, Path] = {
    "sops": KB_ROOT / "sops",
    "glossary": KB_ROOT / "glossary",
    "glossary_aliases": KB_ROOT / "glossary_aliases",
}
REQUIRED_PUBLISHED_METADATA = {
    "citation_id",
    "owner_department",
    "reviewed_at",
    "effective_date",
    "version",
    "status",
}
_SAFE_OBJECT_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


@dataclass(frozen=True)
class ContentValidationIssue:
    """Single content validation issue.

    Args:
        path: Repository-relative content path.
        item_id: Item identifier inside the file.
        detail: Stable failure code.
        severity: Validation severity, currently ``fail`` or ``warn``.

    Returns:
        Immutable validation issue value object.
    """

    path: str
    item_id: str
    detail: str
    severity: Literal["fail", "warn"] = "fail"

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serializable representation.

        Returns:
            A dictionary containing path, item id, detail, and severity.
        """

        return asdict(self)


def _repo_relative(path: Path, root: Path = REPO_ROOT) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _content_dir(kind: str, root: Path = REPO_ROOT) -> Path:
    """Resolve a content directory for a known kind.

    Args:
        kind: One of ``sops``, ``glossary``, or ``glossary_aliases``.
        root: Repository root.

    Returns:
        Path: The content directory.

    Raises:
        ValueError: If ``kind`` is not supported.
    """

    if kind not in CONTENT_DIRS:
        raise ValueError(f"unsupported_content_kind:{kind}")
    return root / "data" / "knowledge_base" / kind


def _safe_object_path(kind: str, object_id: str, root: Path = REPO_ROOT) -> Path:
    """Resolve an object id to a JSON file path with traversal protection.

    Args:
        kind: Content kind.
        object_id: File id without the optional ``.json`` suffix.
        root: Repository root.

    Returns:
        Path: Resolved JSON file path.

    Raises:
        ValueError: If the object id is unsafe or escapes the content directory.
    """

    clean_id = object_id[:-5] if object_id.endswith(".json") else object_id
    if not _SAFE_OBJECT_ID_RE.fullmatch(clean_id):
        raise ValueError("unsafe_content_object_id")
    base = _content_dir(kind, root).resolve()
    path = (base / f"{clean_id}.json").resolve()
    if base != path.parent:
        raise ValueError("content_path_escape")
    return path


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or "published").strip().lower()


def _item_id(kind: str, payload: Mapping[str, Any], fallback: str) -> str:
    if kind == "sops":
        return str(payload.get("sop_id") or fallback)
    return str(payload.get("term") or payload.get("citation_id") or fallback)


def _validate_published_mapping(
    *,
    kind: str,
    payload: Mapping[str, Any],
    path: Path,
    fallback_id: str,
    inherited_metadata: Mapping[str, Any] | None = None,
) -> list[ContentValidationIssue]:
    """Validate required metadata for one published content item.

    Args:
        kind: Content kind.
        payload: Content item payload.
        path: Source JSON file path.
        fallback_id: Stable fallback item id.
        inherited_metadata: File-level metadata inherited by nested items.

    Returns:
        A list of validation issues. Empty means the item passes.
    """

    inherited_metadata = inherited_metadata or {}
    merged = {**inherited_metadata, **payload}
    if _status(merged) != "published":
        return []
    missing = sorted(
        key for key in REQUIRED_PUBLISHED_METADATA
        if not str(merged.get(key) or "").strip()
    )
    if not missing:
        return []
    return [
        ContentValidationIssue(
            path=_repo_relative(path),
            item_id=_item_id(kind, payload, fallback_id),
            detail=f"missing_published_metadata:{','.join(missing)}",
        )
    ]


def validate_content_store(root: Path = REPO_ROOT) -> dict[str, Any]:
    """Validate all repo-local onboarding content.

    Args:
        root: Repository root to inspect.

    Returns:
        dict[str, Any]: Secret-safe validation summary with issue details.
    """

    issues: list[ContentValidationIssue] = []
    counts: dict[str, int] = {"sops": 0, "glossary": 0, "glossary_aliases": 0}

    for kind in CONTENT_DIRS:
        directory = _content_dir(kind, root)
        if not directory.exists():
            issues.append(ContentValidationIssue(_repo_relative(directory, root), kind, "content_dir_missing"))
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                payload = _load_json(path)
            except Exception as exc:
                issues.append(
                    ContentValidationIssue(
                        _repo_relative(path, root),
                        path.stem,
                        f"json_error:{type(exc).__name__}",
                    )
                )
                continue

            counts[kind] += 1
            if kind == "glossary_aliases":
                if not isinstance(payload, Mapping):
                    issues.append(ContentValidationIssue(_repo_relative(path, root), path.stem, "aliases_not_object"))
                continue

            if kind == "glossary" and isinstance(payload, Mapping) and isinstance(payload.get("terms"), list):
                file_metadata = {
                    key: payload.get(key)
                    for key in REQUIRED_PUBLISHED_METADATA
                    if key in payload
                }
                for idx, item in enumerate(payload.get("terms") or []):
                    if isinstance(item, Mapping):
                        issues.extend(
                            _validate_published_mapping(
                                kind=kind,
                                payload=item,
                                path=path,
                                fallback_id=f"{path.stem}:{idx}",
                                inherited_metadata=file_metadata,
                            )
                        )
                    else:
                        issues.append(ContentValidationIssue(_repo_relative(path, root), f"{path.stem}:{idx}", "term_not_object"))
                continue

            if isinstance(payload, Mapping):
                issues.extend(
                    _validate_published_mapping(
                        kind=kind,
                        payload=payload,
                        path=path,
                        fallback_id=path.stem,
                    )
                )
            else:
                issues.append(ContentValidationIssue(_repo_relative(path, root), path.stem, "payload_not_object"))

    failures = [issue for issue in issues if issue.severity == "fail"]
    return {
        "ok": not failures,
        "counts": counts,
        "issues": [issue.to_dict() for issue in issues],
    }


def list_content(kind: str, include_unpublished: bool = False, root: Path = REPO_ROOT) -> list[dict[str, Any]]:
    """List JSON content files for admin CMS screens.

    Args:
        kind: Content kind.
        include_unpublished: Whether draft and archived items should be listed.
        root: Repository root.

    Returns:
        list[dict[str, Any]]: File summaries with payload metadata.
    """

    directory = _content_dir(kind, root)
    if not directory.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        payload = _load_json(path)
        if isinstance(payload, Mapping) and not include_unpublished and _status(payload) != "published":
            continue
        items.append({
            "object_id": path.stem,
            "path": _repo_relative(path, root),
            "status": _status(payload) if isinstance(payload, Mapping) else "unknown",
            "payload": payload,
        })
    return items


def get_content(kind: str, object_id: str, root: Path = REPO_ROOT) -> dict[str, Any]:
    """Read a single content object.

    Args:
        kind: Content kind.
        object_id: File id without the optional ``.json`` suffix.
        root: Repository root.

    Returns:
        dict[str, Any]: Object payload and repository-relative path.

    Raises:
        FileNotFoundError: If the content object does not exist.
        ValueError: If kind or object id is unsafe.
    """

    path = _safe_object_path(kind, object_id, root)
    payload = _load_json(path)
    return {"object_id": path.stem, "path": _repo_relative(path, root), "payload": payload}


def upsert_content(kind: str, object_id: str, payload: Mapping[str, Any], root: Path = REPO_ROOT) -> dict[str, Any]:
    """Create or replace a content object after validation.

    Args:
        kind: Content kind.
        object_id: File id without the optional ``.json`` suffix.
        payload: JSON-serializable content payload.
        root: Repository root.

    Returns:
        dict[str, Any]: Saved object metadata.

    Raises:
        ValueError: If validation fails or the object path is unsafe.
    """

    path = _safe_object_path(kind, object_id, root)
    issues = _validate_published_mapping(kind=kind, payload=payload, path=path, fallback_id=path.stem)
    if issues:
        raise ValueError(issues[0].detail)
    _write_json(path, payload)
    return {"object_id": path.stem, "path": _repo_relative(path, root)}


def archive_content(kind: str, object_id: str, root: Path = REPO_ROOT) -> dict[str, Any]:
    """Mark a content object as archived without deleting the file.

    Args:
        kind: Content kind.
        object_id: File id without the optional ``.json`` suffix.
        root: Repository root.

    Returns:
        dict[str, Any]: Archived object metadata.

    Raises:
        FileNotFoundError: If the object does not exist.
        ValueError: If the object path is unsafe.
    """

    path = _safe_object_path(kind, object_id, root)
    payload = _load_json(path)
    if not isinstance(payload, Mapping):
        raise ValueError("payload_not_object")
    updated = dict(payload)
    updated["status"] = "archived"
    _write_json(path, updated)
    return {"object_id": path.stem, "path": _repo_relative(path, root), "status": "archived"}
