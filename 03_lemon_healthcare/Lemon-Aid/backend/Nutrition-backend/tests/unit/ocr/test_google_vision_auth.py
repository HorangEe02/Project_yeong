"""Google Vision authentication header tests."""

from __future__ import annotations

from typing import Any

import pytest
from google.auth.credentials import Credentials
from pydantic import SecretStr
from src.ocr.providers.google_vision_auth import (
    GoogleVisionADCAuthHeaders,
    GoogleVisionApiKeyAuthHeaders,
    GoogleVisionAuthError,
)


class _FakeCredentials(Credentials):
    """Fake google-auth credentials for ADC header tests."""

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self.refresh_count = 0

    def refresh(self, request: Any) -> None:
        """Populate a fake bearer token.

        Args:
            request: google-auth request object.
        """
        _ = request
        self.refresh_count += 1
        self.token = "fake-adc-token"


@pytest.mark.asyncio
async def test_api_key_auth_headers_use_x_goog_api_key() -> None:
    """Verify local API-key auth uses a header, not a URL query parameter."""
    auth = GoogleVisionApiKeyAuthHeaders(SecretStr("test-google-key"))

    headers = await auth.build_headers()

    assert headers == {"x-goog-api-key": "test-google-key"}


@pytest.mark.asyncio
async def test_api_key_auth_rejects_blank_key() -> None:
    """Verify blank API keys fail closed."""
    auth = GoogleVisionApiKeyAuthHeaders("")

    with pytest.raises(GoogleVisionAuthError, match="API key"):
        await auth.build_headers()


@pytest.mark.asyncio
async def test_adc_auth_headers_refresh_credentials_and_add_quota_project() -> None:
    """Verify ADC auth creates bearer and quota-project headers without key files."""
    credentials = _FakeCredentials()
    auth = GoogleVisionADCAuthHeaders(project_id="lemon-prod", credentials=credentials)

    headers = await auth.build_headers()

    assert headers == {
        "Authorization": "Bearer fake-adc-token",
        "x-goog-user-project": "lemon-prod",
    }
    assert credentials.refresh_count == 1
