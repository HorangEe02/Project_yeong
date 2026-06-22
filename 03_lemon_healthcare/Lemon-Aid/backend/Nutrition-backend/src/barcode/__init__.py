"""Barcode adapter contracts and normalization helpers."""

from src.barcode.base import (
    BarcodeAdapter,
    BarcodeCandidate,
    BarcodeError,
    BarcodeImageInput,
    BarcodeScanResult,
    DisabledBarcodeAdapter,
)
from src.barcode.normalization import (
    BarcodeIdentifier,
    BarcodeNormalizationError,
    barcode_value_hash,
    normalize_barcode_text,
)

__all__ = [
    "BarcodeAdapter",
    "BarcodeCandidate",
    "BarcodeError",
    "BarcodeIdentifier",
    "BarcodeImageInput",
    "BarcodeNormalizationError",
    "BarcodeScanResult",
    "DisabledBarcodeAdapter",
    "barcode_value_hash",
    "normalize_barcode_text",
]
