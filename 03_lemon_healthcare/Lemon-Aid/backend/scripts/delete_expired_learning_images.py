"""Delete expired consent-gated learning image objects without leaking object details."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.config import get_settings  # noqa: E402
from src.db.session import get_sessionmaker  # noqa: E402
from src.learning.factory import build_learning_object_store  # noqa: E402
from src.learning.pipeline import delete_expired_learning_image_objects  # noqa: E402

MIN_LIMIT = 1
MAX_LIMIT = 1000


def _bounded_limit(raw_limit: str) -> int:
    """Validate the maximum retention cleanup batch size.

    Args:
        raw_limit: Candidate batch size from argparse.

    Returns:
        Validated batch size.

    Raises:
        argparse.ArgumentTypeError: If the value is outside the supported range.
    """
    try:
        limit = int(raw_limit)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("limit must be an integer") from exc
    if limit < MIN_LIMIT or limit > MAX_LIMIT:
        raise argparse.ArgumentTypeError(f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}")
    return limit


async def run_cli(argv: list[str] | None = None) -> int:
    """Delete expired learning image objects with sanitized operator output.

    Args:
        argv: Optional CLI argument list for tests.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=_bounded_limit,
        default=100,
        help=f"Maximum expired image objects to delete ({MIN_LIMIT}-{MAX_LIMIT}).",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    if settings.learning_object_storage_provider == "disabled":
        print(
            "status=skipped "
            "provider=disabled "
            f"limit={args.limit} reason=learning_object_storage_disabled"
        )
        return 0

    object_store = build_learning_object_store(settings)
    sessionmaker = get_sessionmaker()
    try:
        async with sessionmaker() as session:
            deleted = await delete_expired_learning_image_objects(
                session=session,
                object_store=object_store,
                limit=args.limit,
            )
    except Exception as exc:
        print(
            "status=failed "
            f"provider={settings.learning_object_storage_provider} "
            f"limit={args.limit} error_type={type(exc).__name__}"
        )
        return 1

    print(
        "status=completed "
        f"provider={settings.learning_object_storage_provider} "
        f"limit={args.limit} deleted={deleted}"
    )
    return 0


def main() -> None:
    """Run the CLI entrypoint."""
    raise SystemExit(asyncio.run(run_cli()))


if __name__ == "__main__":
    main()
