"""Run a sanitized live smoke test for learning private object storage."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.config import get_settings  # noqa: E402
from src.learning.factory import build_learning_object_store  # noqa: E402
from src.learning.object_storage import LearningImageObjectInput  # noqa: E402

RUN_GATE_ENV = "RUN_LEARNING_STORAGE_LIVE_SMOKE"
SMOKE_IMAGE_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _smoke_image_bytes() -> bytes:
    """Return a tiny valid PNG used only for round-trip storage verification.

    Returns:
        PNG image bytes.
    """
    return base64.b64decode(SMOKE_IMAGE_BASE64)


async def run_cli(argv: list[str] | None = None) -> int:
    """Run a put/get/delete smoke without printing object URIs or credentials.

    Args:
        argv: Optional CLI argument list for tests.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    if os.environ.get(RUN_GATE_ENV) != "1":
        print(f"status=skipped reason={RUN_GATE_ENV}_unset")
        return 0

    settings = get_settings()
    provider = settings.learning_object_storage_provider
    object_store = build_learning_object_store(settings)
    image_bytes = _smoke_image_bytes()
    payload = LearningImageObjectInput(
        image_bytes=image_bytes,
        image_sha256=hashlib.sha256(image_bytes).hexdigest(),
        mime_type="image/png",
        owner_subject_hash="0" * 64,
        retained_until=datetime.now(UTC) + timedelta(minutes=5),
        metadata={
            "purpose": "learning-storage-smoke",
            "schema_version": "v1",
        },
    )

    stage = "put"
    stored = None
    cleanup_failed = False
    try:
        stored = await object_store.put_image(payload)
        stage = "get"
        loaded = await object_store.get_image(stored.object_uri, stored.version_id)
        if loaded != image_bytes:
            try:
                await object_store.delete_image(stored.object_uri, stored.version_id)
            except Exception:
                cleanup_failed = True
            print(
                f"status=failed provider={provider} stage=get "
                f"error_type=RoundTripMismatch cleanup_failed={str(cleanup_failed).lower()}"
            )
            return 1
        stage = "delete"
        await object_store.delete_image(stored.object_uri, stored.version_id)
    except Exception as exc:
        failed_stage = stage
        if stored is not None and stage != "delete":
            try:
                await object_store.delete_image(stored.object_uri, stored.version_id)
            except Exception:
                cleanup_failed = True
        print(
            f"status=failed provider={provider} stage={failed_stage} "
            f"error_type={type(exc).__name__} cleanup_failed={str(cleanup_failed).lower()}"
        )
        return 1

    print(
        f"status=passed provider={provider} stored=true round_trip=true "
        f"deleted=true bytes={len(image_bytes)}"
    )
    return 0


def main() -> None:
    """Run the CLI entrypoint."""
    raise SystemExit(asyncio.run(run_cli()))


if __name__ == "__main__":
    main()
