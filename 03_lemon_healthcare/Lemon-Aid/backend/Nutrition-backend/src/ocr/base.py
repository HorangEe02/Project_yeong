"""OCR adapter contracts for supplement label image analysis.

The OCR layer owns text extraction only. It does not persist raw images, call
LLMs, or make health decisions. Callers must enforce consent and storage policy
before passing images into an adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.vision.base import BoundingBox


class OCRError(RuntimeError):
    """Raised when OCR input validation or text extraction fails."""


@dataclass(frozen=True)
class OCRImageInput:
    """Validated image payload passed to OCR providers.

    Attributes:
        image_bytes: Bounded image bytes. The caller must validate size and MIME type first.
        mime_type: Detected MIME type such as ``image/png``.
        width: Decoded image width in pixels.
        height: Decoded image height in pixels.
        label_region: Optional supplement-label ROI detected by the vision layer.
    """

    image_bytes: bytes
    mime_type: str
    width: int
    height: int
    label_region: BoundingBox | None = None


@dataclass(frozen=True)
class OCRVertex:
    """One OCR bounding polygon vertex.

    Attributes:
        x: Horizontal coordinate.
        y: Vertical coordinate.
    """

    x: float
    y: float


@dataclass(frozen=True)
class OCRBoundingPoly:
    """OCR bounding polygon normalized across providers.

    Attributes:
        vertices: Provider-returned vertices in provider order.
    """

    vertices: tuple[OCRVertex, ...]


@dataclass(frozen=True)
class OCRWord:
    """One OCR word with layout metadata.

    Attributes:
        text: Word text assembled from provider symbols.
        confidence: Optional word confidence from 0.0 to 1.0.
        bounding_box: Optional word bounding polygon.
        block_index: Zero-based block index on the page.
        paragraph_index: Zero-based paragraph index in the block.
        word_index: Zero-based word index in the paragraph.
    """

    text: str
    confidence: float | None
    bounding_box: OCRBoundingPoly | None
    block_index: int
    paragraph_index: int
    word_index: int


@dataclass(frozen=True)
class OCRParagraph:
    """One OCR paragraph with child words.

    Attributes:
        text: Paragraph text assembled from child words.
        confidence: Optional paragraph confidence from 0.0 to 1.0.
        bounding_box: Optional paragraph bounding polygon.
        words: Words in provider order.
    """

    text: str
    confidence: float | None
    bounding_box: OCRBoundingPoly | None
    words: tuple[OCRWord, ...]


@dataclass(frozen=True)
class OCRBlock:
    """One OCR block with paragraph hierarchy.

    Attributes:
        text: Block text assembled from child paragraphs.
        confidence: Optional block confidence from 0.0 to 1.0.
        bounding_box: Optional block bounding polygon.
        block_type: Provider block type such as ``TEXT`` when present.
        paragraphs: Paragraphs in provider order.
    """

    text: str
    confidence: float | None
    bounding_box: OCRBoundingPoly | None
    block_type: str | None
    paragraphs: tuple[OCRParagraph, ...]


@dataclass(frozen=True)
class OCRPage:
    """One OCR page containing layout blocks.

    Attributes:
        width: Page width in provider units, usually pixels for images.
        height: Page height in provider units, usually pixels for images.
        confidence: Optional page confidence from 0.0 to 1.0.
        blocks: Blocks in provider order.
    """

    width: int | None
    height: int | None
    confidence: float | None
    blocks: tuple[OCRBlock, ...]


@dataclass(frozen=True)
class OCRResult:
    """Text extracted from a supplement label image.

    Attributes:
        text: Extracted text. Empty text means the adapter did not produce usable OCR output.
        provider: Bounded provider label for audit and preview metadata.
        confidence: Optional OCR confidence from 0.0 to 1.0.
        pages: Optional OCR layout hierarchy. Empty means the provider returned flat text
            only or layout parsing was unavailable.
    """

    text: str
    provider: str
    confidence: float | None = None
    pages: tuple[OCRPage, ...] = ()


class OCRAdapter(ABC):
    """Abstract OCR provider interface.

    Implementations convert validated image bytes into text. They must not store raw
    images or emit medical advice.
    """

    @abstractmethod
    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Extract text from a validated supplement label image.

        Args:
            image: Validated image payload and optional label-region ROI.

        Returns:
            OCR text and provider metadata.

        Raises:
            OCRError: If extraction fails or the provider returns invalid metadata.
        """
        ...
