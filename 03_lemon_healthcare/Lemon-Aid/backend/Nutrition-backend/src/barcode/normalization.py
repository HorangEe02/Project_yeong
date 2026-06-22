"""Barcode value normalization for official FoodQR lookup."""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urlsplit

BarcodeSymbology = Literal["ean8", "upca", "ean13", "gtin14"]
QUERY_BARCODE_KEYS = ("brcd_no", "barcode", "gtin", "BRCD_NO", "BAR_CD")
BARCODE_LENGTH_SYMBOLOGIES: dict[int, BarcodeSymbology] = {
    8: "ean8",
    12: "upca",
    13: "ean13",
    14: "gtin14",
}


@dataclass(frozen=True)
class BarcodeIdentifier:
    """Normalized barcode identifier.

    Attributes:
        normalized_value: Digits-only barcode value used for provider lookup.
        symbology: Normalized barcode symbology inferred from digit length.
        scanner_format: Optional client or decoder format label.
        check_digit_valid: Whether the GS1-style check digit is valid.
    """

    normalized_value: str
    symbology: BarcodeSymbology
    scanner_format: str | None
    check_digit_valid: bool


class BarcodeNormalizationError(ValueError):
    """Raised when barcode text cannot be converted into a safe lookup key."""

    def __init__(self, *, code: str, message: str) -> None:
        """Initialize a stable normalization error.

        Args:
            code: Stable error code.
            message: Safe user-facing message.
        """

        super().__init__(message)
        self.code = code
        self.message = message


def normalize_barcode_text(
    barcode_text: str,
    *,
    scanner_format: str | None = None,
) -> BarcodeIdentifier:
    """Normalize raw scanner text into a FoodQR lookup identifier.

    Args:
        barcode_text: Raw text from a mobile scanner, decoder, or QR payload.
        scanner_format: Optional scanner symbology label.

    Returns:
        Normalized barcode identifier.

    Raises:
        BarcodeNormalizationError: If the value is blank, unsupported, or has an
            invalid check digit.
    """

    extracted = _extract_barcode_payload(barcode_text)
    if not extracted:
        raise BarcodeNormalizationError(
            code="barcode_empty",
            message="Barcode text is empty.",
        )

    normalized = "".join(
        char for char in unicodedata.normalize("NFKC", extracted).strip() if char not in " \t\r\n-"
    )
    if not normalized.isdigit():
        raise BarcodeNormalizationError(
            code="barcode_not_numeric",
            message="Only numeric EAN, UPC, and GTIN barcodes are supported for FoodQR lookup.",
        )

    symbology = _symbology_for_length(len(normalized))
    if symbology is None:
        raise BarcodeNormalizationError(
            code="barcode_length_unsupported",
            message="Only EAN-8, UPC-A, EAN-13, and GTIN-14 barcodes are supported.",
        )

    if not _has_valid_check_digit(normalized):
        raise BarcodeNormalizationError(
            code="barcode_check_digit_invalid",
            message="Barcode check digit is invalid.",
        )

    return BarcodeIdentifier(
        normalized_value=normalized,
        symbology=symbology,
        scanner_format=_normalize_scanner_format(scanner_format),
        check_digit_valid=True,
    )


def barcode_value_hash(normalized_value: str) -> str:
    """Return a one-way hash for audit metadata.

    Args:
        normalized_value: Normalized barcode value.

    Returns:
        SHA-256 hash label.
    """

    digest = hashlib.sha256(normalized_value.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _extract_barcode_payload(raw_text: str) -> str:
    """Extract a barcode-like payload from raw text or a QR URL.

    Args:
        raw_text: Raw scanner output.

    Returns:
        Candidate barcode text.
    """

    stripped = raw_text.strip()
    parsed_url = urlsplit(stripped)
    if parsed_url.scheme and parsed_url.netloc:
        query = parse_qs(parsed_url.query)
        for key in QUERY_BARCODE_KEYS:
            values = query.get(key)
            if values and values[0].strip():
                return values[0].strip()
    return stripped


def _symbology_for_length(length: int) -> BarcodeSymbology | None:
    """Infer barcode symbology from digit length.

    Args:
        length: Number of digits.

    Returns:
        Symbology label, or None for unsupported lengths.
    """

    return BARCODE_LENGTH_SYMBOLOGIES.get(length)


def _has_valid_check_digit(value: str) -> bool:
    """Validate an EAN/UPC/GTIN Mod-10 check digit.

    Args:
        value: Digits-only barcode value.

    Returns:
        True when the final digit matches the computed check digit.
    """

    digits = [int(char) for char in value]
    check_digit = digits[-1]
    total = 0
    for index, digit in enumerate(reversed(digits[:-1])):
        total += digit * (3 if index % 2 == 0 else 1)
    computed = (10 - (total % 10)) % 10
    return computed == check_digit


def _normalize_scanner_format(scanner_format: str | None) -> str | None:
    """Normalize an optional scanner format label.

    Args:
        scanner_format: Raw scanner format label.

    Returns:
        Uppercase scanner format, or None.
    """

    if scanner_format is None:
        return None
    normalized = scanner_format.strip().upper().replace("-", "_")
    return normalized or None
