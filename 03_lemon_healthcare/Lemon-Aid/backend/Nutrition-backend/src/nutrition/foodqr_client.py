"""FoodQR OpenAPI client for official barcode product lookup."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from src.config import Settings

FOODQR_PROVIDER = "foodqr"
HTTP_ERROR_STATUS_MIN = 400
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
SUCCESS_CODES = {"00", "INFO-000"}
NO_DATA_CODES = {"03", "INFO-200"}

FoodQrLookupStatus = Literal[
    "not_configured",
    "invalid_request",
    "not_found",
    "matched",
    "provider_error",
]


@dataclass(frozen=True)
class FoodQrProduct:
    """Allowlisted FoodQR product fields used by the backend.

    Attributes:
        product_name: Official product name when present.
        barcode: Barcode number returned by FoodQR.
        business_name: Business or manufacturer name when present.
        report_no: MFDS 품목제조보고번호 when FoodQR exposes it.
        version: FoodQR version information.
        valid_from: FoodQR validity start date.
        valid_to: FoodQR validity end date.
        source_fields: Redacted allowlisted source fields.
    """

    product_name: str | None
    barcode: str | None
    business_name: str | None
    report_no: str | None
    version: str | None
    valid_from: str | None
    valid_to: str | None
    source_fields: dict[str, str | None]


@dataclass(frozen=True)
class FoodQrLookupResult:
    """Normalized FoodQR lookup result.

    Attributes:
        provider: Provider identifier.
        status: Lookup status.
        products: Allowlisted product candidates.
        message_code: Provider message code when available.
        message: Provider message without credentials or raw query.
    """

    provider: str
    status: FoodQrLookupStatus
    products: tuple[FoodQrProduct, ...] = ()
    message_code: str | None = None
    message: str | None = None


class FoodQrClientError(RuntimeError):
    """Raised when FoodQR lookup cannot be completed safely."""


class FoodQrClient:
    """Client for FoodQR product-list lookup and opt-in detail lookup."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        """Initialize the FoodQR client.

        Args:
            settings: Runtime settings containing FoodQR endpoint and service key.
            client: Optional injected HTTP client for tests.
        """
        self._settings = settings
        self._client = client

    async def lookup_by_barcode(self, barcode: str) -> FoodQrLookupResult:
        """Look up FoodQR product-list rows by barcode.

        Args:
            barcode: Normalized EAN/UPC/GTIN barcode string.

        Returns:
            Normalized lookup result. Missing credentials return ``not_configured``
            instead of raising so callers can fail closed.
        """
        normalized_barcode = barcode.strip()
        if not normalized_barcode:
            return FoodQrLookupResult(provider=FOODQR_PROVIDER, status="invalid_request")
        return await self.fetch_product_list(barcode=normalized_barcode)

    async def fetch_product_list(
        self,
        *,
        barcode: str | None = None,
        product_name: str | None = None,
        version: str | None = None,
        page_no: int = 1,
        num_of_rows: int | None = None,
    ) -> FoodQrLookupResult:
        """Fetch FoodQR product-list rows with optional filters.

        Args:
            barcode: Optional ``brcd_no`` exact lookup value.
            product_name: Optional ``prdt_nm`` filter.
            version: Optional FoodQR version filter.
            page_no: One-based page number.
            num_of_rows: Optional page size override.

        Returns:
            Normalized lookup result.
        """
        if page_no < 1:
            return FoodQrLookupResult(provider=FOODQR_PROVIDER, status="invalid_request")
        service_key = _secret_value(self._settings.foodqr_service_key)
        if not self._settings.enable_barcode_lookup or not service_key:
            return FoodQrLookupResult(provider=FOODQR_PROVIDER, status="not_configured")

        params = {
            "serviceKey": service_key,
            "pageNo": str(page_no),
            "numOfRows": str(num_of_rows or self._settings.foodqr_num_of_rows),
            "type": "json",
        }
        if barcode:
            params["brcd_no"] = barcode.strip()
        if product_name:
            params["prdt_nm"] = product_name.strip()
        if version:
            params["ver_info"] = version.strip()
        response = await self._get_with_retries(params=params)
        return _parse_foodqr_response(response)

    async def fetch_product_manufacturing_info(
        self,
        *,
        barcode: str,
        version: str | None = None,
        page_no: int = 1,
        num_of_rows: int | None = None,
    ) -> FoodQrLookupResult:
        """Fetch configured FoodQR product-manufacturing rows by barcode.

        Args:
            barcode: ``brcd_no`` exact lookup value.
            version: Optional FoodQR version filter.
            page_no: One-based page number.
            num_of_rows: Optional page size override.

        Returns:
            Normalized lookup result. The method fails closed until an official
            detail endpoint path is configured.
        """
        normalized_barcode = barcode.strip()
        if not normalized_barcode or page_no < 1:
            return FoodQrLookupResult(provider=FOODQR_PROVIDER, status="invalid_request")
        service_key = _secret_value(self._settings.foodqr_service_key)
        if not self._settings.enable_barcode_lookup or not service_key:
            return FoodQrLookupResult(provider=FOODQR_PROVIDER, status="not_configured")
        path = self._settings.foodqr_product_manufacturing_path
        if not path:
            return FoodQrLookupResult(
                provider=FOODQR_PROVIDER,
                status="not_configured",
                message="FoodQR product-manufacturing endpoint path is not configured.",
            )

        params = {
            "serviceKey": service_key,
            "pageNo": str(page_no),
            "numOfRows": str(num_of_rows or self._settings.foodqr_num_of_rows),
            "type": "json",
            "brcd_no": normalized_barcode,
        }
        if version:
            params["ver_info"] = version.strip()
        response = await self._get_with_retries(params=params, path=path)
        return _parse_foodqr_response(response)

    async def _get_with_retries(
        self,
        *,
        params: Mapping[str, str],
        path: str | None = None,
    ) -> dict[str, Any]:
        """Call FoodQR with bounded transient retries.

        Args:
            params: Query parameters, including credentials.
            path: Optional endpoint path override.

        Returns:
            Parsed JSON response object.

        Raises:
            FoodQrClientError: If transport or response parsing fails.
        """
        attempts = self._settings.foodqr_max_retries + 1
        last_error: FoodQrClientError | None = None
        for attempt_index in range(attempts):
            try:
                response = await self._get_once(params=params, path=path)
                if response.status_code in TRANSIENT_STATUS_CODES and attempt_index < attempts - 1:
                    last_error = FoodQrClientError(
                        f"FoodQR transient failure: status {response.status_code}."
                    )
                    continue
                return _parse_json_response(response)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = FoodQrClientError("FoodQR transport failure.")
                if attempt_index >= attempts - 1:
                    raise last_error from exc
        if last_error is not None:
            raise last_error
        raise FoodQrClientError("FoodQR request failed.")

    async def _get_once(
        self,
        *,
        params: Mapping[str, str],
        path: str | None = None,
    ) -> httpx.Response:
        """Execute one FoodQR HTTP GET request.

        Args:
            params: Query parameters.
            path: Optional endpoint path override.

        Returns:
            HTTP response.
        """
        url = _join_url(
            self._settings.foodqr_base_url, path or self._settings.foodqr_product_list_path
        )
        if self._client is not None:
            return await self._client.get(
                url,
                params=params,
                timeout=self._settings.foodqr_timeout_seconds,
            )
        async with httpx.AsyncClient(timeout=self._settings.foodqr_timeout_seconds) as client:
            return await client.get(url, params=params)


def _parse_json_response(response: httpx.Response) -> dict[str, Any]:
    """Parse a FoodQR HTTP response as a JSON object.

    Args:
        response: HTTP response.

    Returns:
        Parsed JSON object.

    Raises:
        FoodQrClientError: If the response is an HTTP error or not a JSON object.
    """
    if response.status_code >= HTTP_ERROR_STATUS_MIN:
        raise FoodQrClientError(f"FoodQR request failed: status {response.status_code}.")
    try:
        parsed = response.json()
    except ValueError as exc:
        raise FoodQrClientError("FoodQR returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise FoodQrClientError("FoodQR returned an invalid response shape.")
    return parsed


def _parse_foodqr_response(payload: dict[str, Any]) -> FoodQrLookupResult:
    """Parse a FoodQR JSON payload into a normalized result.

    Args:
        payload: FoodQR JSON response.

    Returns:
        Normalized result with allowlisted product fields only.
    """
    message_code, message = _extract_provider_message(payload)
    if message_code in NO_DATA_CODES:
        return FoodQrLookupResult(
            provider=FOODQR_PROVIDER,
            status="not_found",
            message_code=message_code,
            message=message,
        )
    if message_code and message_code not in SUCCESS_CODES:
        return FoodQrLookupResult(
            provider=FOODQR_PROVIDER,
            status="provider_error",
            message_code=message_code,
            message=message,
        )

    products = tuple(_normalize_foodqr_item(item) for item in _extract_items(payload))
    if not products:
        return FoodQrLookupResult(
            provider=FOODQR_PROVIDER,
            status="not_found",
            message_code=message_code,
            message=message,
        )
    return FoodQrLookupResult(
        provider=FOODQR_PROVIDER,
        status="matched",
        products=products,
        message_code=message_code,
        message=message,
    )


def _normalize_foodqr_item(item: dict[str, Any]) -> FoodQrProduct:
    """Normalize one FoodQR row while preserving only reviewed fields.

    Args:
        item: Provider row.

    Returns:
        Product candidate with allowlisted fields.
    """
    product_name = _field_string(item, ("PRDT_NM", "PRDLST_NM", "product_name", "제품명"))
    barcode = _field_string(item, ("BRCD_NO", "BAR_CD", "barcode", "바코드번호"))
    business_name = _field_string(
        item,
        ("ENTP_NM", "BSSH_NM", "business_name", "업체명", "업소명"),
    )
    report_no = _field_string(
        item,
        ("PRDLST_REPORT_NO", "ITEM_REPORT_NO", "report_no", "품목제조보고번호"),
    )
    version = _field_string(item, ("VER_INFO", "version", "버전정보"))
    valid_from = _field_string(item, ("VLD_BGNG_YMD", "valid_from", "유효시작일자"))
    valid_to = _field_string(item, ("VLD_END_YMD", "valid_to", "유효종료일자"))
    return FoodQrProduct(
        product_name=product_name,
        barcode=barcode,
        business_name=business_name,
        report_no=report_no,
        version=version,
        valid_from=valid_from,
        valid_to=valid_to,
        source_fields={
            "product_name": product_name,
            "barcode": barcode,
            "business_name": business_name,
            "report_no": report_no,
            "version": version,
            "valid_from": valid_from,
            "valid_to": valid_to,
        },
    )


def _extract_provider_message(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract a provider result code and message from known response envelopes.

    Args:
        payload: Provider payload.

    Returns:
        Message code and message, if present.
    """
    response = payload.get("response")
    if isinstance(response, dict):
        header = response.get("header")
        if isinstance(header, dict):
            return _field_string(header, ("resultCode", "RESULT_CODE")), _field_string(
                header,
                ("resultMsg", "RESULT_MSG"),
            )

    header = payload.get("header")
    if isinstance(header, dict):
        return _field_string(header, ("resultCode", "RESULT_CODE")), _field_string(
            header,
            ("resultMsg", "RESULT_MSG"),
        )

    for value in payload.values():
        if not isinstance(value, dict):
            continue
        result = value.get("RESULT")
        if isinstance(result, dict):
            return _field_string(result, ("CODE",)), _field_string(result, ("MSG",))
    return None, None


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract item rows from common public-data response envelopes.

    Args:
        payload: Provider payload.

    Returns:
        List of item dictionaries.
    """
    response = payload.get("response")
    if isinstance(response, dict):
        body = response.get("body")
        if isinstance(body, dict):
            items = _item_rows(body.get("items"))
            if items:
                return items

    body = payload.get("body")
    if isinstance(body, dict):
        items = _item_rows(body.get("items"))
        if items:
            return items

    direct_items = _item_rows(payload.get("items"))
    if direct_items:
        return direct_items

    for value in payload.values():
        if isinstance(value, dict):
            rows = _item_rows(value.get("row"))
            if rows:
                return rows
    return []


def _item_rows(value: object) -> list[dict[str, Any]]:
    """Normalize a public-data item or row container to dictionaries.

    Args:
        value: Raw item container.

    Returns:
        Item dictionaries.
    """
    if isinstance(value, dict) and "item" in value:
        value = value["item"]
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _field_string(mapping: Mapping[str, Any], aliases: tuple[str, ...]) -> str | None:
    """Return the first non-empty field value matched by aliases.

    Args:
        mapping: Provider row or envelope.
        aliases: Field aliases to check, case-insensitively for ASCII keys.

    Returns:
        Trimmed string value or None.
    """
    lowered = {key.lower(): value for key, value in mapping.items() if isinstance(key, str)}
    for alias in aliases:
        value = mapping.get(alias)
        if value is None:
            value = lowered.get(alias.lower())
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _join_url(base_url: str, path: str) -> str:
    """Join a configured base URL and endpoint path.

    Args:
        base_url: Base URL.
        path: Endpoint path.

    Returns:
        Joined URL without duplicate slashes.
    """
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _secret_value(value: object) -> str | None:
    """Return a pydantic secret value without logging it.

    Args:
        value: SecretStr-like object or None.

    Returns:
        Secret text or None.
    """
    if value is None:
        return None
    get_secret_value = getattr(value, "get_secret_value", None)
    if not callable(get_secret_value):
        return None
    secret = get_secret_value()
    return secret if isinstance(secret, str) and secret else None
