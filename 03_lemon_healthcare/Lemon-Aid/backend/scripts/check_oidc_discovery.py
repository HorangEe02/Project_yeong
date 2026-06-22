"""Operational OIDC discovery preflight check."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import TextIO

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NUTRITION_BACKEND_ROOT = BACKEND_ROOT / "Nutrition-backend"
if str(NUTRITION_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(NUTRITION_BACKEND_ROOT))

from src.config import Settings, get_settings  # noqa: E402
from src.security.oidc import (  # noqa: E402
    OIDCMetadataError,
    fetch_oidc_metadata,
    resolve_oidc_discovery_url,
)


async def run_preflight(
    settings: Settings,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Fetch and validate configured OIDC discovery metadata.

    Args:
        settings: Application settings containing JWT/OIDC trust configuration.
        stdout: Stream used for the success JSON payload.
        stderr: Stream used for the failure JSON payload.

    Returns:
        Process-style exit code. Zero means discovery metadata matched the configured trust
        boundary; one means preflight failed.
    """
    discovery_url = ""
    try:
        discovery_url = resolve_oidc_discovery_url(settings)
        metadata = await fetch_oidc_metadata(settings)
    except OIDCMetadataError as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "discovery_url": discovery_url or None,
                    "error": str(exc),
                },
                sort_keys=True,
            ),
            file=stderr,
        )
        return 1

    print(
        json.dumps(
            {
                "status": "ok",
                "discovery_url": discovery_url,
                "issuer": metadata.issuer,
                "jwks_uri": metadata.jwks_uri,
            },
            sort_keys=True,
        ),
        file=stdout,
    )
    return 0


def main() -> int:
    """Run the OIDC discovery preflight from environment settings.

    Returns:
        Process exit code.
    """
    return asyncio.run(run_preflight(get_settings()))


if __name__ == "__main__":
    raise SystemExit(main())
