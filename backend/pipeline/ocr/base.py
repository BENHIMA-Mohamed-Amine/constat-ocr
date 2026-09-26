"""The OCR contract. Any engine (Tesseract now, others later) implements ``OcrEngine``."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class OcrResult:
    """What an engine read from one image."""

    text: str
    seconds: float


class OcrEngine(Protocol):
    """Reads an image into text."""

    def read(self, image_path: Path) -> OcrResult:
        """Read one image.

        Raises:
            OcrError: If the image cannot be read.
        """
        ...
