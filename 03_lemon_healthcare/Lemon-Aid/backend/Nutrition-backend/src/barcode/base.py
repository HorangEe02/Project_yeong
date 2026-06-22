"""Barcode adapter contracts for supplement identity lookup.

The default adapter is intentionally disabled. Mobile-provided barcode text and
official FoodQR lookup can be implemented without sending image bytes through a
server-side barcode decoder.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class BarcodeImageInput:
    """Validated image bytes for an optional barcode decoder.

    Attributes:
        image_bytes: Validated image bytes.
        mime_type: Detected MIME type.
        width: Decoded image width in pixels.
        height: Decoded image height in pixels.
    """

    image_bytes: bytes
    mime_type: str
    width: int
    height: int


@dataclass(frozen=True)
class BarcodeCandidate:
    """One decoded barcode candidate.

    Attributes:
        text: Decoded barcode or QR payload.
        format: Decoder-specific symbology label such as EAN13 or QR_CODE.
        confidence: Optional decoder confidence.
    """

    text: str
    format: str
    confidence: float | None = None


@dataclass(frozen=True)
class BarcodeScanResult:
    """Result from a barcode adapter.

    Attributes:
        provider: Adapter provider label.
        candidates: Decoded candidates.
        warnings: Safe warnings to display or persist.
    """

    provider: str
    candidates: tuple[BarcodeCandidate, ...] = ()
    warnings: tuple[str, ...] = ()


class BarcodeError(RuntimeError):
    """Raised when a barcode decoder cannot complete safely."""


class BarcodeAdapter(Protocol):
    """Protocol implemented by optional server-side barcode decoders."""

    async def scan(self, image: BarcodeImageInput) -> BarcodeScanResult:
        """Scan a validated image for barcodes.

        Args:
            image: Validated image input.

        Returns:
            Barcode scan result.

        Raises:
            BarcodeError: If decoding fails unexpectedly.
        """


class DisabledBarcodeAdapter:
    """Fail-closed barcode adapter used when server-side decoding is disabled."""

    async def scan(self, _image: BarcodeImageInput) -> BarcodeScanResult:
        """Return no candidates without inspecting image bytes.

        Args:
            _image: Validated image input, intentionally ignored.

        Returns:
            Disabled scan result.
        """

        return BarcodeScanResult(
            provider="disabled",
            warnings=("Server-side barcode decoding is disabled.",),
        )
