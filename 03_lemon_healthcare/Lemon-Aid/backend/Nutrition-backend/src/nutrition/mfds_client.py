"""FoodSafetyKorea MFDS OpenAPI client for supplement product lookup."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote

import httpx

from src.config import Settings

MFDS_PROVIDER = "mfds_openapi"
MFDS_C003_SERVICE_ID = "C003"
MFDS_I0760_SERVICE_ID = "I0760"
HTTP_ERROR_STATUS_MIN = 400
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
SUCCESS_CODES = {"INFO-000"}
NO_DATA_CODES = {"INFO-200"}
NON_JSON_PROVIDER_ERROR_CODE = "NON_JSON_PROVIDER_ERROR"
NON_JSON_PROVIDER_ERROR_MESSAGE = "MFDS returned a non-JSON provider error."
NON_JSON_ERROR_MESSAGES = {
    "INFO-100": "MFDS rejected the key for this service.",
    "INFO-300": "MFDS quota has been exceeded.",
    "INFO-400": "MFDS key is not authorized for this service.",
    "ERROR-310": "MFDS service id was rejected.",
    NON_JSON_PROVIDER_ERROR_CODE: NON_JSON_PROVIDER_ERROR_MESSAGE,
}
NON_JSON_ERROR_HINTS = (
    ("INFO-400", ("권한",)),
    ("INFO-300", ("호출건수", "초과")),
    ("ERROR-310", ("서비스", "찾을 수")),
    ("INFO-100", ("인증키",)),
)

MfdsLookupStatus = Literal[
    "not_configured",
    "invalid_request",
    "not_found",
    "matched",
    "provider_error",
]


@dataclass(frozen=True)
class MfdsProduct:
    """Allowlisted MFDS product fields used by the backend.

    Attributes:
        product_name: MFDS product name.
        business_name: MFDS business name.
        report_no: MFDS 품목제조보고번호.
        license_no: MFDS license number.
        intake_method: Official intake method text when available.
        primary_functionality: Official primary functionality text when available.
        attention: Official caution text when available.
        raw_material_name: Official raw material names when available.
        source_fields: Redacted allowlisted source fields.
    """

    product_name: str | None
    business_name: str | None
    report_no: str | None
    license_no: str | None
    intake_method: str | None
    primary_functionality: str | None
    attention: str | None
    raw_material_name: str | None
    source_fields: dict[str, str | None]


@dataclass(frozen=True)
class MfdsLookupResult:
    """Normalized MFDS lookup result.

    Attributes:
        provider: Provider identifier.
        service_id: MFDS service id such as C003 or I0760.
        status: Lookup status.
        products: Allowlisted product rows.
        total_count: Provider total count when available.
        message_code: Provider message code when available.
        message: Provider message without credentials or raw query.
    """

    provider: str
    service_id: str
    status: MfdsLookupStatus
    products: tuple[MfdsProduct, ...] = ()
    total_count: int | None = None
    message_code: str | None = None
    message: str | None = None


class MfdsClientError(RuntimeError):
    """Raised when an MFDS OpenAPI lookup cannot be completed safely."""


class MfdsOpenAPIClient:
    """Client for FoodSafetyKorea OpenAPI services used by P1-1."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        """Initialize the MFDS client.

        Args:
            settings: Runtime settings containing MFDS endpoint and key.
            client: Optional injected HTTP client for tests.
        """
        self._settings = settings
        self._client = client

    async def get_product_by_report_no(self, report_no: str) -> MfdsLookupResult:
        """Look up C003 rows by exact 품목제조보고번호.

        Args:
            report_no: Official MFDS 품목제조보고번호.

        Returns:
            Normalized lookup result.
        """
        normalized_report_no = report_no.strip()
        if not normalized_report_no:
            return MfdsLookupResult(
                provider=MFDS_PROVIDER,
                service_id=MFDS_C003_SERVICE_ID,
                status="invalid_request",
            )
        return await self.fetch_service_rows(
            service_id=MFDS_C003_SERVICE_ID,
            params={"PRDLST_REPORT_NO": normalized_report_no},
        )

    async def search_products(
        self,
        *,
        product_name: str | None = None,
        business_name: str | None = None,
    ) -> MfdsLookupResult:
        """Search C003 by product and business name as review-only candidates.

        Args:
            product_name: Optional MFDS product-name query.
            business_name: Optional MFDS business-name query.

        Returns:
            Normalized lookup result.
        """
        params: dict[str, str] = {}
        if product_name and product_name.strip():
            params["PRDLST_NM"] = product_name.strip()
        if business_name and business_name.strip():
            params["BSSH_NM"] = business_name.strip()
        if not params:
            return MfdsLookupResult(
                provider=MFDS_PROVIDER,
                service_id=MFDS_C003_SERVICE_ID,
                status="invalid_request",
            )
        return await self.fetch_service_rows(service_id=MFDS_C003_SERVICE_ID, params=params)

    async def get_ingredient_rows(self, group_name: str | None = None) -> MfdsLookupResult:
        """Fetch I0760 rows for ingredient enrichment smoke or review.

        Args:
            group_name: Optional health item group-name query.

        Returns:
            Normalized lookup result.
        """
        params: dict[str, str] = {}
        if group_name and group_name.strip():
            params["HELT_ITM_GRP_NM"] = group_name.strip()
        return await self.fetch_service_rows(service_id=MFDS_I0760_SERVICE_ID, params=params)

    async def fetch_sample_service_rows(
        self,
        *,
        service_id: str,
        start_idx: int = 1,
        end_idx: int = 5,
    ) -> MfdsLookupResult:
        """Fetch MFDS public sample rows using the documented ``sample`` keyId.

        Args:
            service_id: MFDS service id.
            start_idx: One-based start index.
            end_idx: End index.

        Returns:
            Normalized lookup result.
        """
        if not service_id or start_idx < 1 or end_idx < start_idx:
            return MfdsLookupResult(
                provider=MFDS_PROVIDER,
                service_id=service_id,
                status="invalid_request",
            )
        response = await self._get_with_retries(
            service_id=service_id,
            api_key="sample",
            start_idx=start_idx,
            end_idx=end_idx,
            params={},
        )
        return _parse_mfds_response(response, service_id=service_id)

    async def fetch_service_rows(
        self,
        *,
        service_id: str,
        params: Mapping[str, str] | None = None,
        start_idx: int = 1,
        end_idx: int | None = None,
    ) -> MfdsLookupResult:
        """Fetch and parse rows from an MFDS service.

        Args:
            service_id: MFDS service id.
            params: Optional MFDS path parameters.
            start_idx: One-based start index.
            end_idx: Optional end index. Defaults to configured page size.

        Returns:
            Normalized lookup result.
        """
        api_key = _secret_value(self._settings.mfds_api_key)
        if not self._settings.enable_barcode_lookup or not api_key:
            return MfdsLookupResult(
                provider=MFDS_PROVIDER,
                service_id=service_id,
                status="not_configured",
            )
        if not service_id or start_idx < 1:
            return MfdsLookupResult(
                provider=MFDS_PROVIDER,
                service_id=service_id,
                status="invalid_request",
            )
        resolved_end_idx = end_idx or start_idx + self._settings.mfds_openapi_page_size - 1
        response = await self._get_with_retries(
            service_id=service_id,
            api_key=api_key,
            start_idx=start_idx,
            end_idx=resolved_end_idx,
            params=params or {},
        )
        return _parse_mfds_response(response, service_id=service_id)

    async def _get_with_retries(
        self,
        *,
        service_id: str,
        api_key: str,
        start_idx: int,
        end_idx: int,
        params: Mapping[str, str],
    ) -> dict[str, Any]:
        """Call MFDS OpenAPI with bounded transient retries.

        Args:
            service_id: MFDS service id.
            api_key: MFDS keyId value.
            start_idx: One-based start index.
            end_idx: End index.
            params: Additional MFDS path parameters.

        Returns:
            Parsed JSON response object.

        Raises:
            MfdsClientError: If transport or response parsing fails.
        """
        attempts = self._settings.mfds_openapi_max_retries + 1
        last_error: MfdsClientError | None = None
        for attempt_index in range(attempts):
            try:
                response = await self._get_once(
                    service_id=service_id,
                    api_key=api_key,
                    start_idx=start_idx,
                    end_idx=end_idx,
                    params=params,
                )
                if response.status_code in TRANSIENT_STATUS_CODES and attempt_index < attempts - 1:
                    last_error = MfdsClientError(
                        f"MFDS transient failure: status {response.status_code}."
                    )
                    continue
                return _parse_json_response(response, service_id=service_id)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = MfdsClientError("MFDS transport failure.")
                if attempt_index >= attempts - 1:
                    raise last_error from exc
        if last_error is not None:
            raise last_error
        raise MfdsClientError("MFDS request failed.")

    async def _get_once(
        self,
        *,
        service_id: str,
        api_key: str,
        start_idx: int,
        end_idx: int,
        params: Mapping[str, str],
    ) -> httpx.Response:
        """Execute one MFDS HTTP GET request.

        Args:
            service_id: MFDS service id.
            api_key: MFDS keyId value.
            start_idx: One-based start index.
            end_idx: End index.
            params: Additional MFDS path parameters.

        Returns:
            HTTP response.
        """
        url = _build_mfds_url(
            self._settings.mfds_openapi_base_url,
            api_key=api_key,
            service_id=service_id,
            start_idx=start_idx,
            end_idx=end_idx,
            params=params,
        )
        if self._client is not None:
            return await self._client.get(
                url,
                timeout=self._settings.mfds_openapi_timeout_seconds,
            )
        async with httpx.AsyncClient(timeout=self._settings.mfds_openapi_timeout_seconds) as client:
            return await client.get(url)


def _parse_json_response(response: httpx.Response, *, service_id: str) -> dict[str, Any]:
    """Parse an MFDS HTTP response as a JSON object.

    Args:
        response: HTTP response.
        service_id: MFDS service id used to synthesize typed provider errors.

    Returns:
        Parsed JSON object.

    Raises:
        MfdsClientError: If the response is an HTTP error or not a JSON object.
    """
    if response.status_code >= HTTP_ERROR_STATUS_MIN:
        raise MfdsClientError(f"MFDS request failed: status {response.status_code}.")
    try:
        parsed = response.json()
    except ValueError as exc:
        classified = _classify_non_json_provider_error(response.text, service_id=service_id)
        if classified is not None:
            return classified
        raise MfdsClientError("MFDS returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise MfdsClientError("MFDS returned an invalid response shape.")
    return parsed


def _parse_mfds_response(payload: dict[str, Any], *, service_id: str) -> MfdsLookupResult:
    """Parse an MFDS JSON payload into a normalized result.

    Args:
        payload: MFDS JSON response.
        service_id: MFDS service id.

    Returns:
        Normalized lookup result with allowlisted rows only.
    """
    service_payload = payload.get(service_id)
    if not isinstance(service_payload, dict):
        return MfdsLookupResult(
            provider=MFDS_PROVIDER,
            service_id=service_id,
            status="provider_error",
            message="MFDS response is missing the service envelope.",
        )

    result = service_payload.get("RESULT")
    message_code: str | None = None
    message: str | None = None
    if isinstance(result, dict):
        message_code = _field_string(result, ("CODE",))
        message = _field_string(result, ("MSG",))

    total_count = _field_int(service_payload, "total_count")
    if message_code in NO_DATA_CODES:
        return MfdsLookupResult(
            provider=MFDS_PROVIDER,
            service_id=service_id,
            status="not_found",
            total_count=total_count,
            message_code=message_code,
            message=message,
        )
    if message_code and message_code not in SUCCESS_CODES:
        return MfdsLookupResult(
            provider=MFDS_PROVIDER,
            service_id=service_id,
            status="provider_error",
            total_count=total_count,
            message_code=message_code,
            message=message,
        )

    rows = _item_rows(service_payload.get("row"))
    products = tuple(_normalize_mfds_row(row) for row in rows)
    if not products:
        return MfdsLookupResult(
            provider=MFDS_PROVIDER,
            service_id=service_id,
            status="not_found",
            total_count=total_count,
            message_code=message_code,
            message=message,
        )
    return MfdsLookupResult(
        provider=MFDS_PROVIDER,
        service_id=service_id,
        status="matched",
        products=products,
        total_count=total_count,
        message_code=message_code,
        message=message,
    )


def _classify_non_json_provider_error(
    text: str,
    *,
    service_id: str,
) -> dict[str, Any] | None:
    """Classify an MFDS non-JSON provider error without storing raw body text.

    Args:
        text: Response text.
        service_id: MFDS service id.

    Returns:
        Synthetic provider envelope, or None if the body is not an MFDS error.
    """
    normalized = text.strip().lower()
    looks_like_provider_error = normalized.startswith("<script") or normalized.startswith("<html")
    looks_like_provider_error = looks_like_provider_error or "인증키" in text or "권한" in text
    if not looks_like_provider_error:
        return None

    code = NON_JSON_PROVIDER_ERROR_CODE
    for candidate_code, hints in NON_JSON_ERROR_HINTS:
        if all(hint in text for hint in hints):
            code = candidate_code
            break
    return {
        service_id: {
            "RESULT": {
                "CODE": code,
                "MSG": NON_JSON_ERROR_MESSAGES[code],
            }
        }
    }


def _normalize_mfds_row(row: dict[str, Any]) -> MfdsProduct:
    """Normalize one MFDS row while preserving only reviewed fields.

    Args:
        row: Provider row.

    Returns:
        Product candidate with allowlisted fields.
    """
    product_name = _field_string(row, ("PRDLST_NM", "product_name", "제품명"))
    business_name = _field_string(row, ("BSSH_NM", "business_name", "업소명"))
    report_no = _field_string(row, ("PRDLST_REPORT_NO", "report_no", "품목제조보고번호"))
    license_no = _field_string(row, ("LCNS_NO", "license_no", "인허가번호"))
    intake_method = _field_string(row, ("NTK_MTHD", "intake_method", "섭취방법"))
    primary_functionality = _field_string(
        row,
        ("PRIMARY_FNCLTY", "primary_functionality", "주된기능성"),
    )
    attention = _field_string(row, ("IFTKN_ATNT_MATR_CN", "attention", "섭취시주의사항"))
    raw_material_name = _field_string(row, ("RAWMTRL_NM", "raw_material_name", "원재료"))
    return MfdsProduct(
        product_name=product_name,
        business_name=business_name,
        report_no=report_no,
        license_no=license_no,
        intake_method=intake_method,
        primary_functionality=primary_functionality,
        attention=attention,
        raw_material_name=raw_material_name,
        source_fields={
            "product_name": product_name,
            "business_name": business_name,
            "report_no": report_no,
            "license_no": license_no,
            "intake_method": intake_method,
            "primary_functionality": primary_functionality,
            "attention": attention,
            "raw_material_name": raw_material_name,
        },
    )


def _build_mfds_url(
    base_url: str,
    *,
    api_key: str,
    service_id: str,
    start_idx: int,
    end_idx: int,
    params: Mapping[str, str],
) -> str:
    """Build an MFDS OpenAPI URL.

    Args:
        base_url: MFDS OpenAPI base URL.
        api_key: MFDS keyId value.
        service_id: MFDS service id.
        start_idx: One-based start index.
        end_idx: End index.
        params: Additional request parameters appended after end index.

    Returns:
        MFDS URL path.
    """
    url = (
        f"{base_url.rstrip('/')}/{api_key}/{service_id.strip().upper()}/json/"
        f"{start_idx}/{end_idx}"
    )
    if not params:
        return url
    encoded_params = "&".join(
        f"{quote(key, safe='')}={quote(value, safe='')}" for key, value in params.items()
    )
    return f"{url}/{encoded_params}"


def _item_rows(value: object) -> list[dict[str, Any]]:
    """Normalize an MFDS row container to dictionaries.

    Args:
        value: Raw row container.

    Returns:
        Item dictionaries.
    """
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


def _field_int(mapping: Mapping[str, Any], alias: str) -> int | None:
    """Return an integer field when available.

    Args:
        mapping: Provider envelope.
        alias: Field name.

    Returns:
        Integer value or None.
    """
    value = mapping.get(alias)
    if value is None:
        value = mapping.get(alias.upper())
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


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
