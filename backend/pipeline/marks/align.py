"""Put a straightened photo of the form exactly on the blank template, so template coordinates land on the right pixels."""

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_SCALE = 0.4  # the alignment is searched on a reduced copy, then applied at full size


def _flatten(gray: np.ndarray) -> np.ndarray:
    """Remove slow lighting changes (shadows, gradients) so only the printed form drives the alignment."""
    gray = gray.astype(np.float32)
    return cv2.GaussianBlur(
        gray / (cv2.GaussianBlur(gray, (0, 0), 20) + 1), (0, 0), 1.2
    )


def to_template(page: np.ndarray, template: np.ndarray) -> np.ndarray:
    """The page warped onto the template, at the template's size (BGR).

    The page is first resized to the template, then refined with a homography found by ECC image alignment on the printed content.
    If the alignment does not converge, the resized page is returned as it is.
    """
    height, width = template.shape
    resized = cv2.resize(page, (width, height), interpolation=cv2.INTER_AREA)
    small = lambda gray: _flatten(
        cv2.resize(gray, None, fx=_SCALE, fy=_SCALE, interpolation=cv2.INTER_AREA)
    )
    warp = np.eye(3, dtype=np.float32)
    try:
        _, warp = cv2.findTransformECC(
            small(template),
            small(cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)),
            warp,
            cv2.MOTION_HOMOGRAPHY,
            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 150, 1e-6),
            None,
            5,
        )
    except cv2.error:
        logger.warning("template alignment did not converge, using the resized page")
        return resized
    scale = np.diag([_SCALE, _SCALE, 1]).astype(np.float32)
    full = np.linalg.inv(scale) @ warp @ scale
    return cv2.warpPerspective(
        resized,
        full,
        (width, height),
        flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
        borderValue=(255, 255, 255),
    )
