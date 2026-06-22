"""Authentication header providers for Google Vision REST OCR calls."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, cast

import google.auth
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from pydantic import SecretStr

CLOUD_VISION_SCOPE = "https://www.googleapis.com/auth/cloud-vision"


class GoogleVisionAuthError(RuntimeError):
    """Raised when Google Vision authentication headers cannot be built."""


class GoogleVisionAuthHeadersProvider(Protocol):
    """Protocol for building Google Vision request authentication headers."""

    async def build_headers(self) -> dict[str, str]:
        """Return authentication headers for one Google Vision REST request.

        Returns:
            Header names and values for a Google Vision request.

        Raises:
            GoogleVisionAuthError: If credentials cannot provide a usable token.
        """


class GoogleVisionApiKeyAuthHeaders:
    """Build API-key headers for local Google Vision smoke tests."""

    def __init__(self, api_key: SecretStr | str) -> None:
        """Initialize the API-key header provider.

        Args:
            api_key: Server-side Google Cloud API key. It must not be exposed to clients.
        """
        self._api_key = api_key

    async def build_headers(self) -> dict[str, str]:
        """Return an ``x-goog-api-key`` header.

        Returns:
            Google REST API key header.

        Raises:
            GoogleVisionAuthError: If the API key is blank.
        """
        api_key = _secret_to_string(self._api_key).strip()
        if not api_key:
            raise GoogleVisionAuthError("Google Vision API key is not configured.")
        return {"x-goog-api-key": api_key}


class GoogleVisionADCAuthHeaders:
    """Build bearer-token headers from Application Default Credentials."""

    def __init__(
        self,
        *,
        project_id: str | None,
        credentials: Credentials | None = None,
        request: GoogleAuthRequest | None = None,
    ) -> None:
        """Initialize the ADC header provider.

        Args:
            project_id: Google Cloud project used for quota attribution.
            credentials: Optional injected credentials for tests.
            request: Optional google-auth transport request.
        """
        self._project_id = project_id
        self._credentials = credentials
        self._request = request or GoogleAuthRequest()

    async def build_headers(self) -> dict[str, str]:
        """Return bearer-token headers from ADC.

        Returns:
            Authorization header and optional quota project header.

        Raises:
            GoogleVisionAuthError: If ADC cannot provide a bearer token.
        """
        token = await asyncio.to_thread(self._refresh_and_get_token)
        headers = {"Authorization": f"Bearer {token}"}
        if self._project_id:
            headers["x-goog-user-project"] = self._project_id
        return headers

    def _refresh_and_get_token(self) -> str:
        """Refresh ADC credentials and return a bearer token.

        Returns:
            OAuth bearer token.

        Raises:
            GoogleVisionAuthError: If credentials cannot be loaded or refreshed.
        """
        try:
            credentials = self._credentials
            if credentials is None:
                credentials, _project_id = google.auth.default(scopes=[CLOUD_VISION_SCOPE])
                self._credentials = credentials
            if not credentials.valid:
                cast(Any, credentials).refresh(self._request)
            token = credentials.token
        except Exception as exc:  # pragma: no cover - exercised through fake auth provider.
            raise GoogleVisionAuthError("Google Vision ADC credentials are unavailable.") from exc

        if not token:
            raise GoogleVisionAuthError("Google Vision ADC token is unavailable.")
        return str(token)


def _secret_to_string(value: SecretStr | str) -> str:
    """Return the raw secret string without logging it.

    Args:
        value: Pydantic secret or plain string.

    Returns:
        Raw secret string.
    """
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return value
