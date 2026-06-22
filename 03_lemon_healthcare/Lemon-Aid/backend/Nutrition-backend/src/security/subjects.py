"""Authenticated subject key helpers."""

from __future__ import annotations

from src.security.auth import AuthenticatedUser

MAX_OWNER_SUBJECT_LENGTH = 512


def build_owner_subject(user: AuthenticatedUser) -> str:
    """Build the persisted owner key from issuer and subject.

    Args:
        user: Authenticated principal resolved by the auth dependency.

    Returns:
        Issuer-qualified subject string.

    Raises:
        ValueError: If the owner key is empty or exceeds the database column length.
    """
    issuer = user.issuer or "unknown-issuer"
    owner_subject = f"{issuer}::{user.subject}"
    if not user.subject or len(owner_subject) > MAX_OWNER_SUBJECT_LENGTH:
        raise ValueError("Authenticated owner subject is invalid.")
    return owner_subject
