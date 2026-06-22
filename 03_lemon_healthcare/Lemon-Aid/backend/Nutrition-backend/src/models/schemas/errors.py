"""Reusable API error schemas for OpenAPI contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field


class APIErrorResponse(BaseModel):
    """Structured API error response.

    Attributes:
        code: Stable machine-readable error code.
        message: Safe user-facing error message.
        required_scopes: OAuth scopes required by the route when applicable.
        required_consents: Consent buckets required by the route when applicable.
    """

    code: str = Field(examples=["not_implemented"])
    message: str = Field(examples=["This P1 API contract is not implemented yet."])
    required_scopes: list[str] = Field(default_factory=list)
    required_consents: list[str] = Field(default_factory=list)
