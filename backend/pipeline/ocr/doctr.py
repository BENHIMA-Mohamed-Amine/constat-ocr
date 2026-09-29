"""docTR (PyTorch) on a CPU. Plain OCR: no image cleanup, text only."""

import logging
import time
from pathlib import Path

from ..errors import OcrError
from .base import OcrResult

logger = logging.getLogger(__name__)


class DoctrEngine:
    """An ``OcrEngine`` backed by docTR (MobileNet detector and recognizer, French vocabulary, from docTR's pretrained models).

    Needs the optional ``candidates`` dependencies. The models are downloaded on first use.
    """

    def __init__(self) -> None:
        """Load the models."""
        from doctr.models import (  # imported here so other engines do not need the package
            ocr_predictor,
        )

        self._predictor = ocr_predictor(
            det_arch="db_mobilenet_v3_large",
            reco_arch="crnn_mobilenet_v3_small",
            pretrained=True,
        )

    def read(self, image_path: Path) -> OcrResult:
        """Read one image into text, one line per docTR line, in docTR's reading order."""
        if not image_path.is_file():
            raise OcrError(f"image not found: {image_path}", form_id=image_path.stem)
        from doctr.io import DocumentFile

        started = time.perf_counter()
        try:
            document = self._predictor(DocumentFile.from_images(str(image_path)))
        except Exception as exc:  # boundary with a third-party OCR library: any failure means "could not read"
            raise OcrError(
                f"docTR failed on {image_path.name}: {exc}", form_id=image_path.stem
            ) from exc
        lines = [
            " ".join(word.value for word in line.words)
            for page in document.pages
            for block in page.blocks
            for line in block.lines
        ]
        text = "\n".join(lines).strip()
        seconds = time.perf_counter() - started
        logger.info(
            "ocr %s: %d characters in %.1fs", image_path.name, len(text), seconds
        )
        return OcrResult(text=text, seconds=seconds)
