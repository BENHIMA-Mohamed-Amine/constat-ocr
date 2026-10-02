"""Find the page against the desk, then warp it flat. OpenCV only, no model to download."""

from pathlib import Path

import cv2
import numpy as np

from ..core.errors import StraighteningError


class OpenCvStraightener:
    """A ``Straightener`` that thresholds the page from the background and flattens its four corners."""

    def straighten(self, image_path: Path, out_path: Path) -> None:
        image = cv2.imread(str(image_path))
        if image is None:
            raise StraighteningError(
                f"image not found or unreadable: {image_path}", form_id=image_path.stem
            )
        flat = _flatten(image, _page_corners(image, image_path.stem))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), flat, [cv2.IMWRITE_JPEG_QUALITY, 95])


def _page_corners(image: np.ndarray, form_id: str) -> np.ndarray:
    """The page's four corners as top-left, top-right, bottom-right, bottom-left."""
    gray = cv2.GaussianBlur(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (9, 9), 0)
    _, page = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(page, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise StraighteningError("no page found", form_id=form_id)
    outline = max(contours, key=cv2.contourArea)
    approx = cv2.approxPolyDP(outline, 0.02 * cv2.arcLength(outline, True), True)
    corners = (
        approx.reshape(4, 2)
        if len(approx) == 4
        else cv2.boxPoints(cv2.minAreaRect(outline))
    )
    return _order(corners.astype(np.float32))


def _order(corners: np.ndarray) -> np.ndarray:
    """Sort four points as top-left, top-right, bottom-right, bottom-left."""
    by_sum, by_diff = corners.sum(axis=1), np.diff(corners, axis=1).ravel()
    return np.array(
        [
            corners[by_sum.argmin()],
            corners[by_diff.argmin()],
            corners[by_sum.argmax()],
            corners[by_diff.argmax()],
        ],
        dtype=np.float32,
    )


def _flatten(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    top_left, top_right, bottom_right, bottom_left = corners
    width = round(
        max(
            np.linalg.norm(top_right - top_left),
            np.linalg.norm(bottom_right - bottom_left),
        )
    )
    height = round(
        max(
            np.linalg.norm(bottom_left - top_left),
            np.linalg.norm(bottom_right - top_right),
        )
    )
    target = np.array(
        [[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float32
    )
    matrix = cv2.getPerspectiveTransform(corners, target)
    return cv2.warpPerspective(image, matrix, (width, height))
