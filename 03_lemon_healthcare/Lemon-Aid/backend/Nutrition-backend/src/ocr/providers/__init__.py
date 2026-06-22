"""OCR provider implementations."""

from src.ocr.providers.clova import ClovaOCRAdapter
from src.ocr.providers.google_vision import GoogleVisionOCRAdapter
from src.ocr.providers.noop import NoopOCRAdapter
from src.ocr.providers.paddle import PaddleOCRAdapter

__all__ = ["ClovaOCRAdapter", "GoogleVisionOCRAdapter", "NoopOCRAdapter", "PaddleOCRAdapter"]
