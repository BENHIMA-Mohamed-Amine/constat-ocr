"""Tesseract, through LangChain's ``TesseractBlobParser``. Plain OCR: no image cleanup, text only."""

import logging
import time
from collections.abc import Iterable
from pathlib import Path

from langchain_community.document_loaders.parsers.images import TesseractBlobParser
from langchain_core.documents.base import Blob

from ..errors import OcrError
from .base import OcrResult

logger = logging.getLogger(__name__)


class LangChainTesseractEngine:
    """An ``OcrEngine`` backed by Tesseract. Needs the Tesseract program and the language packs installed."""

    def __init__(self, languages: Iterable[str] = ("fra",)) -> None:
        """Create the engine.

        Args:
            languages: Tesseract language codes, for example ``("fra",)``.
        """
        self._parser = TesseractBlobParser(langs=tuple(languages))

    def read(self, image_path: Path) -> OcrResult:
        """Read one image into text (lines in reading order, as Tesseract returns them)."""
        if not image_path.is_file():
            raise OcrError(f"image not found: {image_path}", form_id=image_path.stem)
        started = time.perf_counter()
        try:
            documents = self._parser.parse(Blob.from_path(image_path))
        except Exception as exc:  # boundary with a third-party OCR library: any failure means "could not read"
            raise OcrError(
                f"Tesseract failed on {image_path.name}: {exc}", form_id=image_path.stem
            ) from exc
        text = "\n".join(document.page_content for document in documents).strip()
        seconds = time.perf_counter() - started
        logger.info(
            "ocr %s: %d characters in %.1fs", image_path.name, len(text), seconds
        )
        return OcrResult(text=text, seconds=seconds)
