"""Where the marks are on the blank constat template, in the pixels of the template rendered at 200 dpi.

The geometry (checkboxes, picture frames, letter positions) is defined once, in the ``generator`` package, from the template PDF.
This is the only module of the pipeline that imports it, so a standalone parser of the PDF could replace it without touching the reader.
"""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pymupdf

from generator import drawings, fields

DPI = 200
SCALE = DPI / 72  # PDF points to pixels

Box = tuple[int, int, int, int]  # x0, y0, x1, y1


@dataclass(frozen=True)
class Layout:
    """The blank template and the boxes of everything a driver marks, for vehicle A then vehicle B."""

    template: np.ndarray  # grayscale render of the blank page
    ticks: tuple[
        list[Box], list[Box]
    ]  # the 23 circumstance boxes of each vehicle, top to bottom
    pickers: list[tuple[float, float, float, float]]  # the vehicle-type pictures
    impacts: list[tuple[float, float, float, float]]  # the impact-point pictures
    categories: tuple[
        list[tuple[float, float]], list[tuple[float, float]]
    ]  # centre of each licence letter
    damage: dict[
        bool, list[Box]
    ]  # the OUI (True) and NON (False) cells, French and Arabic side
    text_fields: dict[
        str, tuple[Box, Box]
    ]  # where each vehicle field is written, for vehicle A and vehicle B


def _px(rect: tuple[float, ...], grow: float = 0) -> Box:
    x0, y0, x1, y1 = (v * SCALE for v in rect)
    return round(x0 - grow), round(y0 - grow), round(x1 + grow), round(y1 + grow)


def load_layout(template_pdf: Path) -> Layout:
    """Read the template page and the geometry of its marks."""
    page = pymupdf.open(template_pdf)[0]
    pixmap = page.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
    template = (
        np.frombuffer(pixmap.samples, np.uint8)
        .reshape(pixmap.height, pixmap.width)
        .copy()
    )
    (ticks_a, ticks_b), _ = fields.checkboxes(page)
    pickers, impacts, _ = drawings.boxes(page, SCALE)
    return Layout(
        template=template,
        ticks=([_px(r) for r in ticks_a], [_px(r) for r in ticks_b]),
        pickers=pickers,
        impacts=impacts,
        categories=tuple(
            [(x * SCALE, y * SCALE) for x, y in side]
            for side in fields.CATEGORY_CENTRES
        ),
        damage={
            answer: [_px(c) for c in cells]
            for answer, cells in fields.OTHER_DAMAGE.items()
        },
        text_fields={name: (_px(a), _px(b)) for name, (a, b) in fields.VEHICLE.items()},
    )
