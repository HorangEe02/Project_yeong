"""Supabase Auth configuration helpers (ADR 39).

Supabase issues JWT access tokens that the backend verifies with its generic
OAuth/OIDC JWKS pipeline (``src/security/auth.py``) — no new ``/auth/*`` routes
are added. This module is the single source of truth for the canonical Supabase
issuer/JWKS endpoint derivation, so deployment config cannot drift from the
documented values: a wrong issuer silently breaks owner-subject/RLS isolation
because the issuer is part of ``build_owner_subject``'s trust anchor.

Deployment requirement: the Supabase project MUST be configured to use
asymmetric JWT signing keys (RS256 or ES256). Supabase's default HS256
(symmetric) tokens cannot be verified by this backend, which rejects symmetric
algorithms in production.

Official reference: https://supabase.com/docs/guides/auth/jwts
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Supabase access tokens carry aud="authenticated" for signed-in users and
# "anon" for the anonymous role; protected routes require "authenticated".
SUPABASE_AUTH_AUDIENCE = "authenticated"

# Asymmetric signing algorithms a Supabase project may enable. The backend must
# accept both because the active algorithm depends on the project's signing key
# type (RSA -> RS256, ECC -> ES256).
SUPABASE_ASYMMETRIC_ALGORITHMS = ("RS256", "ES256")

# Supabase hosted project refs are exactly 20 lowercase letters (official CLI
# ProjectRefPattern: ^[a-z]{20}$). Pinning the format keeps the derived
# issuer/JWKS URLs from being poisoned by an injected host or path (the issuer is
# the owner-subject trust anchor) and rejects values that can never resolve to a
# real hosted Supabase project. Self-hosted deployments set JWT_ISSUER directly.
_PROJECT_REF_PATTERN = re.compile(r"^[a-z]{20}$")


@dataclass(frozen=True)
class SupabaseAuthEndpoints:
    """Canonical Supabase Auth verification endpoints for a project.

    Attributes:
        issuer: Expected JWT ``iss`` claim (``https://<ref>.supabase.co/auth/v1``).
        jwks_url: JWKS endpoint for public-key retrieval.
        audience: Expected JWT ``aud`` claim for signed-in users.
        algorithms: Asymmetric signing algorithms the project may use.
    """

    issuer: str
    jwks_url: str
    audience: str
    algorithms: tuple[str, ...]


def supabase_auth_endpoints(project_ref: str) -> SupabaseAuthEndpoints:
    """Derive the documented Supabase Auth endpoints for a project ref.

    Args:
        project_ref: Supabase hosted project ref (e.g. ``abcdefghijklmnopqrst``).

    Returns:
        Canonical issuer, JWKS URL, audience, and asymmetric algorithms.

    Raises:
        ValueError: If the project ref is not exactly 20 lowercase letters.
    """
    ref = project_ref.strip()
    if not _PROJECT_REF_PATTERN.match(ref):
        raise ValueError("Supabase project ref must be exactly 20 lowercase letters.")
    base = f"https://{ref}.supabase.co/auth/v1"
    return SupabaseAuthEndpoints(
        issuer=base,
        jwks_url=f"{base}/.well-known/jwks.json",
        audience=SUPABASE_AUTH_AUDIENCE,
        algorithms=SUPABASE_ASYMMETRIC_ALGORITHMS,
    )
