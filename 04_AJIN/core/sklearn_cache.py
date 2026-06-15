"""scikit-learn pickle cache metadata helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def cache_metadata_path(cache_path: Path) -> Path:
    """Return the sidecar metadata path for a sklearn pickle cache.

    Args:
        cache_path: Pickle cache file path.

    Returns:
        Metadata JSON path next to the pickle file.
    """

    return cache_path.with_name(f"{cache_path.name}.meta.json")


def current_sklearn_version() -> str:
    """Return the installed scikit-learn version.

    Returns:
        Version string from the active Python environment.
    """

    import sklearn

    return sklearn.__version__


def cache_matches_current_sklearn(cache_path: Path) -> bool:
    """Check cache metadata before loading a sklearn pickle.

    Args:
        cache_path: Pickle cache file path.

    Returns:
        True when the pickle exists and its sidecar metadata was written by the
        same scikit-learn version as the active runtime.
    """

    if not cache_path.exists():
        return False

    metadata_path = cache_metadata_path(cache_path)
    if not metadata_path.exists():
        return False

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    return metadata.get("sklearn_version") == current_sklearn_version()


def write_cache_metadata(cache_path: Path, **extra: Any) -> None:
    """Write sidecar metadata for a sklearn pickle cache.

    Args:
        cache_path: Pickle cache file path.
        **extra: Optional additional metadata fields.

    Raises:
        OSError: Propagated when the metadata file cannot be written.
    """

    metadata = {
        "format_version": 1,
        "sklearn_version": current_sklearn_version(),
        **extra,
    }
    cache_metadata_path(cache_path).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
