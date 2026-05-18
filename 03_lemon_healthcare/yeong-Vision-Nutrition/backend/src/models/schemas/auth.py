"""Auth API 입출력 Pydantic 스키마.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-05-api-integration.md Step 3
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class UserProfileInput(BaseModel):
    """``/auth/register`` 의 프로필 입력 (UserProfile DB row 와 1:1 매핑)."""

    model_config = ConfigDict(frozen=True)

    age: int = Field(..., ge=1, le=120)
    sex: Literal["male", "female"]
    height_cm: float = Field(..., ge=50, le=250)
    weight_kg: float = Field(..., ge=10, le=300)
    is_pregnant: bool = False
    is_lactating: bool = False
    is_smoker: bool = False
    chronic_diseases: list[str] = Field(default_factory=list)
    medications: list[dict[str, Any]] = Field(default_factory=list)


class ConsentAccept(BaseModel):
    """``/auth/register`` 시 함께 제출되는 단일 동의 항목."""

    model_config = ConfigDict(frozen=True)

    consent_type: str = Field(..., min_length=1, max_length=32)
    accepted: bool


class UserRegisterRequest(BaseModel):
    """``POST /api/v1/auth/register`` 요청."""

    model_config = ConfigDict(frozen=True)

    email: str = Field(
        ...,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        max_length=254,
    )
    password: str = Field(..., min_length=8, max_length=128)
    profile: UserProfileInput
    consents: list[ConsentAccept] = Field(default_factory=list)


class LoginRequest(BaseModel):
    """``POST /api/v1/auth/login`` 요청."""

    model_config = ConfigDict(frozen=True)

    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """``POST /api/v1/auth/refresh`` 요청."""

    model_config = ConfigDict(frozen=True)

    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """access + refresh 토큰 한 쌍."""

    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in_seconds: int = Field(..., ge=0)
