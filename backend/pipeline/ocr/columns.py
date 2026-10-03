"""RapidOCR with the text grouped by zone of the form: header, vehicle A, circumstances, vehicle B.

After straightening, the form is one printed template: two tall green strips frame the circumstances column and hold both
checkbox columns. A text box's centre says which zone it is in, so the text can be given to the model as labelled blocks
instead of one stream that mixes the two vehicles.
"""

import logging
import time
from pathlib import Path

import cv2
import numpy as np

from ..core.errors import OcrError
from .base import OcrResult
from .rapidocr import RapidOcrEngine

logger = logging.getLogger(__name__)

ZONES = ("header", "vehicle_a", "circumstances", "vehicle_b")
GREEN_LOW, GREEN_HIGH = (
    (40, 60, 60),
    (90, 255, 255),
)  # HSV range of the form's printed green


def find_zone_cuts(bgr: np.ndarray) -> tuple[float, float, float]:
    """Where to cut the page, as fractions of its size, found from the printed green strips.

    Counts green pixels per column in the middle of the page: the two tall strips are the two peaks.

    Args:
        bgr: The straightened page, as OpenCV loads it.

    Returns:
        The outer left edge of the left strip, the outer right edge of the right strip, and the top of the strips
        (the header ends there).

    Raises:
        ValueError: If two strips are not found.
    """
    height, width = bgr.shape[:2]
    green = cv2.inRange(cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV), GREEN_LOW, GREEN_HIGH) > 0
    profile = green[int(0.25 * height) : int(0.70 * height)].mean(axis=0)
    columns = np.flatnonzero(profile > 0.3 * profile.max())
    runs = np.split(columns, np.flatnonzero(np.diff(columns) > 5) + 1)
    if len(runs) < 2:
        raise ValueError("the two green strips were not found")
    left, right = sorted(sorted(runs, key=len, reverse=True)[:2], key=np.mean)
    strips = np.zeros_like(green)
    strips[:, left.min() : left.max() + 1] = strips[
        :, right.min() : right.max() + 1
    ] = True
    rows = np.flatnonzero((green & strips).sum(axis=1) > 0.5 * strips.sum(axis=1).max())
    tall = max(
        np.split(rows, np.flatnonzero(np.diff(rows) > 10) + 1), key=len
    )  # not a stray green patch
    return left.min() / width, right.max() / width, tall.min() / height


def group_by_zone(
    boxes: list[np.ndarray],
    texts: list[str],
    size: tuple[int, int],
    cuts: tuple[float, float, float],
) -> str:
    """The text as four labelled blocks, each sorted top to bottom, by the centre of each box.

    Args:
        boxes: One array of corner points per text line.
        texts: The text of each box.
        size: Width and height of the page in pixels.
        cuts: The result of ``find_zone_cuts``.
    """
    (width, height), (left, right, header) = size, cuts
    blocks: dict[str, list[tuple[float, float, str]]] = {zone: [] for zone in ZONES}
    for box, text in zip(boxes, texts):
        x, y = box[:, 0].mean() / width, box[:, 1].mean() / height
        if y < header:
            zone = "header"
        else:
            zone = (
                "vehicle_a"
                if x < left
                else "circumstances"
                if x < right
                else "vehicle_b"
            )
        blocks[zone].append((y, x, text))
    return "\n\n".join(
        f"## {zone}\n" + "\n".join(text for _, _, text in sorted(blocks[zone]))
        for zone in ZONES
    )


class ColumnRapidOcrEngine(RapidOcrEngine):
    """An ``OcrEngine`` that reads like ``RapidOcrEngine`` but returns the text grouped by zone."""

    def read(self, image_path: Path) -> OcrResult:
        if not image_path.is_file():
            raise OcrError(f"image not found: {image_path}", form_id=image_path.stem)
        started = time.perf_counter()
        try:
            image = cv2.imread(str(image_path))
            output = self._engine(str(image_path))
            text = group_by_zone(
                [
                    np.asarray(box)
                    for box in (output.boxes if output.boxes is not None else ())
                ],
                list(output.txts or ()),
                (image.shape[1], image.shape[0]),
                find_zone_cuts(image),
            )
        except Exception as exc:  # boundary with a third-party OCR library: any failure means "could not read"
            raise OcrError(
                f"RapidOCR (columns) failed on {image_path.name}: {exc}",
                form_id=image_path.stem,
            ) from exc
        seconds = time.perf_counter() - started
        logger.info(
            "ocr %s: %d characters in %.1fs", image_path.name, len(text), seconds
        )
        return OcrResult(text=text, seconds=seconds)
