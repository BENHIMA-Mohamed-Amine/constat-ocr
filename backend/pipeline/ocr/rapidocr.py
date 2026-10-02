"""PP-OCR models through RapidOCR (ONNX Runtime). Runs on a CPU, no image cleanup, text only."""

import logging
import time
from pathlib import Path

from ..core.errors import OcrError
from .base import OcrResult

logger = logging.getLogger(__name__)


class RapidOcrEngine:
    """An ``OcrEngine`` backed by RapidOCR.

    Two model families: ``"v5"`` (PP-OCRv5 mobile, Latin recognizer) and ``"v6"`` (PP-OCRv6 small, French). The models
    are downloaded on first use (about 12 MB) and cached inside the ``rapidocr`` package.
    """

    def __init__(self, version: str = "v6") -> None:
        """Load the models.

        Args:
            version: ``"v5"`` or ``"v6"``.
        """
        from rapidocr import (  # imported here so other engines do not need the package
            LangRec,
            ModelType,
            OCRVersion,
            RapidOCR,
        )

        if version == "v5":
            params = {
                "Det.ocr_version": OCRVersion.PPOCRV5,
                "Det.model_type": ModelType.MOBILE,
                "Rec.ocr_version": OCRVersion.PPOCRV5,
                "Rec.model_type": ModelType.MOBILE,
                "Rec.lang_type": LangRec.LATIN,
            }
        elif version == "v6":
            params = {
                "Det.ocr_version": OCRVersion.PPOCRV6,
                "Det.model_type": ModelType.SMALL,
                "Det.lang_type": "french",
                "Rec.ocr_version": OCRVersion.PPOCRV6,
                "Rec.model_type": ModelType.SMALL,
                "Rec.lang_type": "french",
            }
        else:
            raise ValueError(f"unknown RapidOCR version {version!r}; known: v5, v6")
        self._engine = RapidOCR(params=params)

    def read(self, image_path: Path) -> OcrResult:
        """Read one image into text, one line per detected text box, in the order RapidOCR returns them."""
        if not image_path.is_file():
            raise OcrError(f"image not found: {image_path}", form_id=image_path.stem)
        started = time.perf_counter()
        try:
            output = self._engine(str(image_path))
        except Exception as exc:  # boundary with a third-party OCR library: any failure means "could not read"
            raise OcrError(
                f"RapidOCR failed on {image_path.name}: {exc}", form_id=image_path.stem
            ) from exc
        text = "\n".join(
            output.txts or ()
        ).strip()  # txts is None when nothing is found
        seconds = time.perf_counter() - started
        logger.info(
            "ocr %s: %d characters in %.1fs", image_path.name, len(text), seconds
        )
        return OcrResult(text=text, seconds=seconds)
