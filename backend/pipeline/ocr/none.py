"""An engine that reads nothing, for pipelines where a vision model reads the page itself (see ``structuring/vision.py``)."""

from pathlib import Path

from .base import OcrResult


class NoOcrEngine:
    """An ``OcrEngine`` that returns empty text."""

    def read(self, image_path: Path) -> OcrResult:
        """Return empty text without opening the image."""
        return OcrResult("", 0.0)
