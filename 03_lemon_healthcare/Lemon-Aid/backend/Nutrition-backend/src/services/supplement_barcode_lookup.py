"""Official barcode lookup service for supplement preview candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from src.barcode.normalization import (
    BarcodeIdentifier,
    BarcodeNormalizationError,
    barcode_value_hash,
    normalize_barcode_text,
)
from src.config import Settings
from src.db.tx import persist_scope
from src.models.db.supplement import SupplementAnalysisRun
from src.models.schemas.supplement import (
    MatchedSupplementCandidate,
    SupplementBarcodeLookupResponse,
    SupplementBarcodeProductCandidate,
    SupplementBarcodeProviderObservation,
)
from src.nutrition.foodqr_client import FoodQrClient, FoodQrClientError, FoodQrLookupResult
from src.nutrition.mfds_client import MFDS_C003_SERVICE_ID, MfdsClientError, MfdsOpenAPIClient

BarcodeLookupStatus = Literal[
    "not_configured",
    "invalid_request",
    "not_found",
    "review_required",
    "provider_error",
]

BARCODE_LOOKUP_NOT_CONFIGURED_WARNING = (
    "Official barcode lookup is not configured. Continue by reviewing label details manually."
)
BARCODE_LOOKUP_NOT_FOUND_WARNING = "No official FoodQR row was found for this barcode. Continue by reviewing label details manually."
BARCODE_LOOKUP_PROVIDER_ERROR_WARNING = "Official barcode lookup is temporarily unavailable. Continue by reviewing label details manually."
BARCODE_LOOKUP_MULTIPLE_ROWS_WARNING = (
    "FoodQR returned multiple rows for this barcode. Select the correct product version manually."
)
BARCODE_LOOKUP_REVIEW_REQUIRED_WARNING = (
    "Official barcode candidates require user confirmation before storage."
)
C003_PROVIDER_ERROR_WARNING = (
    "MFDS C003 product detail lookup is unavailable for this key or service scope."
)
FoodQrLookupPayload = tuple[FoodQrLookupResult, SupplementBarcodeProviderObservation]


@dataclass(frozen=True)
class BarcodeLookupServiceResult:
    """Service-level barcode lookup result.

    Attributes:
        status: Overall candidate lookup status.
        identifier: Normalized identifier when available.
        candidates: Candidate products from official providers.
        observations: Sanitized provider observations.
        warnings: Safe warnings for API response and preview snapshot.
        error_code: Optional invalid-input code.
        error_message: Optional invalid-input message.
    """

    status: BarcodeLookupStatus
    identifier: BarcodeIdentifier | None = None
    candidates: tuple[SupplementBarcodeProductCandidate, ...] = ()
    observations: tuple[SupplementBarcodeProviderObservation, ...] = ()
    warnings: tuple[str, ...] = ()
    error_code: str | None = None
    error_message: str | None = None


class SupplementBarcodeLookupService:
    """Fail-closed FoodQR-first barcode lookup service."""

    def __init__(
        self,
        settings: Settings,
        *,
        foodqr_client: FoodQrClient | None = None,
        mfds_client: MfdsOpenAPIClient | None = None,
    ) -> None:
        """Initialize the lookup service.

        Args:
            settings: Runtime settings.
            foodqr_client: Optional injected FoodQR client.
            mfds_client: Optional injected MFDS client.
        """

        self._settings = settings
        self._foodqr_client = foodqr_client or FoodQrClient(settings)
        self._mfds_client = mfds_client or MfdsOpenAPIClient(settings)

    async def lookup(
        self,
        barcode_text: str,
        *,
        barcode_format: str | None = None,
    ) -> BarcodeLookupServiceResult:
        """Look up official product candidates for one barcode.

        Args:
            barcode_text: Raw barcode scanner text.
            barcode_format: Optional client scanner format label.

        Returns:
            Fail-closed lookup result. Provider errors are represented as typed
            status values instead of leaking raw provider responses.
        """

        try:
            identifier = normalize_barcode_text(barcode_text, scanner_format=barcode_format)
        except BarcodeNormalizationError as exc:
            return BarcodeLookupServiceResult(
                status="invalid_request",
                warnings=(exc.message,),
                error_code=exc.code,
                error_message=exc.message,
            )

        if not self._settings.enable_barcode_lookup:
            return _not_configured_result(identifier)

        foodqr_payload = await self._lookup_foodqr(identifier)
        if isinstance(foodqr_payload, BarcodeLookupServiceResult):
            return foodqr_payload
        foodqr_result, foodqr_observation = foodqr_payload
        return await self._build_result_from_foodqr(
            identifier=identifier,
            foodqr_result=foodqr_result,
            foodqr_observation=foodqr_observation,
        )

    async def _lookup_foodqr(
        self,
        identifier: BarcodeIdentifier,
    ) -> BarcodeLookupServiceResult | FoodQrLookupPayload:
        """Run FoodQR lookup and normalize transport failures.

        Args:
            identifier: Normalized barcode identifier.

        Returns:
            Either a terminal failure result or FoodQR result with observation.
        """
        try:
            foodqr_result = await self._foodqr_client.lookup_by_barcode(identifier.normalized_value)
        except FoodQrClientError:
            return _provider_error_result(
                identifier,
                observation=SupplementBarcodeProviderObservation(
                    provider="foodqr",
                    status="provider_error",
                    item_count=0,
                ),
            )
        foodqr_observation = _provider_observation(
            provider="foodqr",
            status=foodqr_result.status,
            message_code=foodqr_result.message_code,
            item_count=len(foodqr_result.products),
        )
        return foodqr_result, foodqr_observation

    async def _build_result_from_foodqr(
        self,
        *,
        identifier: BarcodeIdentifier,
        foodqr_result: FoodQrLookupResult,
        foodqr_observation: SupplementBarcodeProviderObservation,
    ) -> BarcodeLookupServiceResult:
        """Build the final service result from a FoodQR response.

        Args:
            identifier: Normalized barcode identifier.
            foodqr_result: FoodQR lookup result.
            foodqr_observation: Sanitized FoodQR observation.

        Returns:
            Terminal lookup result.
        """

        if foodqr_result.status == "not_configured":
            return _not_configured_result(identifier, foodqr_observation)
        if foodqr_result.status == "not_found":
            return BarcodeLookupServiceResult(
                status="not_found",
                identifier=identifier,
                warnings=(BARCODE_LOOKUP_NOT_FOUND_WARNING,),
                observations=(foodqr_observation,),
            )
        if foodqr_result.status == "provider_error":
            return _provider_error_result(identifier, observation=foodqr_observation)
        if foodqr_result.status != "matched":
            return _provider_error_result(identifier, observation=foodqr_observation)

        candidates = _foodqr_candidates(foodqr_result)
        observations: list[SupplementBarcodeProviderObservation] = [foodqr_observation]
        warnings = [BARCODE_LOOKUP_REVIEW_REQUIRED_WARNING]
        if len(foodqr_result.products) > 1:
            warnings.append(BARCODE_LOOKUP_MULTIPLE_ROWS_WARNING)

        c003_warnings, c003_observations = await self._lookup_c003_for_report_numbers(candidates)
        warnings.extend(c003_warnings)
        observations.extend(c003_observations)

        if not candidates:
            return BarcodeLookupServiceResult(
                status="not_found",
                identifier=identifier,
                warnings=(BARCODE_LOOKUP_NOT_FOUND_WARNING,),
                observations=tuple(observations),
            )

        return BarcodeLookupServiceResult(
            status="review_required",
            identifier=identifier,
            candidates=tuple(candidates),
            observations=tuple(observations),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    async def _lookup_c003_for_report_numbers(
        self,
        candidates: list[SupplementBarcodeProductCandidate],
    ) -> tuple[list[str], list[SupplementBarcodeProviderObservation]]:
        """Look up MFDS C003 rows only when FoodQR exposes report numbers.

        Args:
            candidates: FoodQR product candidates.

        Returns:
            Safe warnings and provider observations.
        """

        warnings: list[str] = []
        observations: list[SupplementBarcodeProviderObservation] = []
        seen_report_numbers: set[str] = set()
        for candidate in candidates:
            if candidate.report_no is None or candidate.report_no in seen_report_numbers:
                continue
            seen_report_numbers.add(candidate.report_no)
            try:
                mfds_result = await self._mfds_client.get_product_by_report_no(candidate.report_no)
            except MfdsClientError:
                warnings.append(C003_PROVIDER_ERROR_WARNING)
                observations.append(
                    SupplementBarcodeProviderObservation(
                        provider="mfds_c003",
                        status="provider_error",
                        item_count=0,
                    )
                )
                continue
            observations.append(
                _provider_observation(
                    provider="mfds_c003",
                    status=mfds_result.status,
                    message_code=mfds_result.message_code,
                    item_count=len(mfds_result.products),
                )
            )
            if (
                mfds_result.service_id == MFDS_C003_SERVICE_ID
                and mfds_result.status == "provider_error"
            ):
                warnings.append(C003_PROVIDER_ERROR_WARNING)
        return warnings, observations


def build_supplement_barcode_lookup_service(settings: Settings) -> SupplementBarcodeLookupService:
    """Build the default barcode lookup service.

    Args:
        settings: Runtime settings.

    Returns:
        Barcode lookup service.
    """

    return SupplementBarcodeLookupService(settings)


def barcode_lookup_result_to_response(
    result: BarcodeLookupServiceResult,
) -> SupplementBarcodeLookupResponse:
    """Convert a service result to the public API response schema.

    Args:
        result: Service lookup result.

    Returns:
        Public response model.
    """

    identifier = result.identifier
    normalized_value = identifier.normalized_value if identifier is not None else None
    return SupplementBarcodeLookupResponse(
        status=result.status,
        normalized_barcode=normalized_value,
        barcode_format=identifier.scanner_format if identifier is not None else None,
        barcode_symbology=identifier.symbology if identifier is not None else None,
        barcode_hash=barcode_value_hash(normalized_value) if normalized_value is not None else None,
        check_digit_valid=identifier.check_digit_valid if identifier is not None else None,
        candidate_count=len(result.candidates),
        candidates=list(result.candidates),
        provider_observations=list(result.observations),
        warnings=list(result.warnings),
    )


async def attach_barcode_lookup_to_analysis(
    session: AsyncSession,
    record: SupplementAnalysisRun,
    result: BarcodeLookupServiceResult,
) -> SupplementAnalysisRun:
    """Persist a sanitized barcode lookup snapshot on a supplement preview.

    Args:
        session: Request-scoped async session.
        record: Supplement analysis preview row.
        result: Barcode lookup result.

    Returns:
        Updated supplement analysis row.
    """

    response = barcode_lookup_result_to_response(result)
    async with persist_scope(session):
        parsed_snapshot = dict(record.parsed_snapshot or {})
        parsed_snapshot["barcode_lookup"] = response.model_dump(mode="json")

        match_snapshot = dict(record.match_snapshot or {})
        match_snapshot["barcode_lookup"] = {
            "status": response.status,
            "candidate_count": response.candidate_count,
            "auto_confirmed": False,
            "raw_provider_payload_stored": False,
        }
        match_snapshot["matched_product_candidates"] = _merge_matched_candidates(
            match_snapshot.get("matched_product_candidates"),
            result.candidates,
        )

        existing_warnings = list(record.warnings or [])
        for warning in result.warnings:
            if warning not in existing_warnings:
                existing_warnings.append(warning)

        record.parsed_snapshot = parsed_snapshot
        record.match_snapshot = match_snapshot
        record.warnings = existing_warnings
    await session.refresh(record)
    return record


def _not_configured_result(
    identifier: BarcodeIdentifier,
    observation: SupplementBarcodeProviderObservation | None = None,
) -> BarcodeLookupServiceResult:
    """Build a not-configured lookup result.

    Args:
        identifier: Normalized barcode identifier.
        observation: Optional provider observation.

    Returns:
        Not-configured result.
    """

    observations = () if observation is None else (observation,)
    return BarcodeLookupServiceResult(
        status="not_configured",
        identifier=identifier,
        warnings=(BARCODE_LOOKUP_NOT_CONFIGURED_WARNING,),
        observations=observations,
    )


def _provider_error_result(
    identifier: BarcodeIdentifier,
    *,
    observation: SupplementBarcodeProviderObservation,
) -> BarcodeLookupServiceResult:
    """Build a provider-error lookup result.

    Args:
        identifier: Normalized barcode identifier.
        observation: Sanitized provider observation.

    Returns:
        Provider-error result.
    """

    return BarcodeLookupServiceResult(
        status="provider_error",
        identifier=identifier,
        warnings=(BARCODE_LOOKUP_PROVIDER_ERROR_WARNING,),
        observations=(observation,),
    )


def _provider_observation(
    *,
    provider: str,
    status: str,
    message_code: str | None = None,
    item_count: int = 0,
) -> SupplementBarcodeProviderObservation:
    """Build one sanitized provider observation.

    Args:
        provider: Provider label.
        status: Provider status.
        message_code: Provider message code.
        item_count: Number of allowlisted rows.

    Returns:
        Provider observation.
    """

    return SupplementBarcodeProviderObservation(
        provider=provider,
        status=status,
        message_code=message_code,
        item_count=item_count,
    )


def _foodqr_candidates(result: FoodQrLookupResult) -> list[SupplementBarcodeProductCandidate]:
    """Convert FoodQR rows into review-only product candidates.

    Args:
        result: Matched FoodQR result.

    Returns:
        Product candidates.
    """

    candidates: list[SupplementBarcodeProductCandidate] = []
    multiple_rows = len(result.products) > 1
    for index, product in enumerate(result.products, 1):
        if not product.product_name:
            continue
        barcode = product.barcode or "unknown"
        version = product.version or "unversioned"
        candidates.append(
            SupplementBarcodeProductCandidate(
                source_id=f"foodqr:{barcode}:{version}:{index}",
                provider="foodqr",
                product_name=product.product_name,
                manufacturer=product.business_name,
                barcode=product.barcode,
                report_no=product.report_no,
                version=product.version,
                valid_from=product.valid_from,
                valid_to=product.valid_to,
                match_score=0.74 if multiple_rows else 0.92,
                review_required_reason=(
                    "multiple_foodqr_rows" if multiple_rows else "user_confirmation_required"
                ),
            )
        )
    return candidates


def _merge_matched_candidates(
    existing_value: object,
    barcode_candidates: tuple[SupplementBarcodeProductCandidate, ...],
) -> list[dict[str, object]]:
    """Merge barcode candidates into the existing preview match list.

    Args:
        existing_value: Existing match snapshot value.
        barcode_candidates: Barcode candidates to expose as product matches.

    Returns:
        Serialized matched-product candidates.
    """

    existing: list[dict[str, object]] = []
    seen_source_ids: set[str] = set()
    if isinstance(existing_value, list):
        for item in existing_value:
            if not isinstance(item, dict):
                continue
            source_id = item.get("source_id")
            if isinstance(source_id, str):
                seen_source_ids.add(source_id)
            existing.append(item)

    for candidate in barcode_candidates:
        if candidate.source_id in seen_source_ids:
            continue
        matched = MatchedSupplementCandidate(
            source_id=candidate.source_id,
            product_name=candidate.product_name,
            manufacturer=candidate.manufacturer,
            match_score=candidate.match_score,
        )
        existing.append(matched.model_dump(mode="json"))
        seen_source_ids.add(candidate.source_id)
    return existing
