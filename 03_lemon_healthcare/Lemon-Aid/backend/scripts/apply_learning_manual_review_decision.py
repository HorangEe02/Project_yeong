"""Apply an operator manual-review decision to one learning image object."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.config import get_settings  # noqa: E402
from src.db.session import get_sessionmaker  # noqa: E402
from src.learning.pipeline import (  # noqa: E402
    approve_learning_image_object_after_manual_review,
    reject_learning_image_object_after_manual_review,
)


async def apply_learning_manual_review_decision(
    *,
    image_object_id: UUID,
    decision: str,
) -> dict[str, object]:
    """Apply one manual review decision without printing private metadata.

    Args:
        image_object_id: Learning image object selected by an operator.
        decision: Either ``approve`` or ``reject``.

    Returns:
        Sanitized result summary.
    """
    settings = get_settings()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        if decision == "approve":
            job = await approve_learning_image_object_after_manual_review(
                session=session,
                image_object_id=image_object_id,
                settings=settings,
            )
            return {
                "decision": decision,
                "image_object_id": str(image_object_id),
                "embedding_job_created": job is not None,
                "embedding_job_id": str(job.id) if job is not None else None,
            }
        rejected = await reject_learning_image_object_after_manual_review(
            session=session,
            image_object_id=image_object_id,
        )
        return {
            "decision": decision,
            "image_object_id": str(image_object_id),
            "rejected": rejected,
        }


async def run_cli(argv: list[str] | None = None) -> int:
    """Parse arguments and apply the review decision.

    Args:
        argv: Optional argument list for tests.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-object-id", required=True, type=UUID)
    parser.add_argument("--decision", required=True, choices=("approve", "reject"))
    args = parser.parse_args(argv)

    result = await apply_learning_manual_review_decision(
        image_object_id=args.image_object_id,
        decision=args.decision,
    )
    if args.decision == "approve" and not result["embedding_job_created"]:
        print(
            f"decision=approve image_object_id={result['image_object_id']} "
            "embedding_job_created=false"
        )
        return 1
    if args.decision == "reject" and not result["rejected"]:
        print(f"decision=reject image_object_id={result['image_object_id']} rejected=false")
        return 1
    print(
        f"decision={result['decision']} image_object_id={result['image_object_id']} " "applied=true"
    )
    return 0


def main() -> None:
    """Run the CLI entrypoint."""
    raise SystemExit(asyncio.run(run_cli()))


if __name__ == "__main__":
    main()
