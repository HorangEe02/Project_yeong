"""Run one consent-gated learning vector upsert worker batch."""

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
from src.learning.factory import (  # noqa: E402
    build_embedding_provider,
    build_learning_object_store,
    build_vector_store,
)
from src.learning.upsert_worker import LearningVectorUpsertWorker  # noqa: E402


async def _run(limit: int) -> None:
    """Run one worker batch.

    Args:
        limit: Maximum jobs to claim.
    """
    settings = get_settings()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        worker = LearningVectorUpsertWorker(
            session=session,
            object_store=build_learning_object_store(settings),
            embedding_provider=build_embedding_provider(settings),
            vector_store=build_vector_store(settings, session),
        )
        result = await worker.run_once(limit=limit)
    print(
        f"claimed={result.claimed} succeeded={result.succeeded} failed={result.failed} cancelled={result.cancelled}"
    )


def main() -> None:
    """Parse CLI arguments and run the worker."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10, help="Maximum jobs to process.")
    args = parser.parse_args()
    asyncio.run(_run(limit=args.limit))


if __name__ == "__main__":
    main()
