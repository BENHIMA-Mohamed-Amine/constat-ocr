"""Unit (1 test): grouping OCR text by zone of the form, on a page the test draws itself.

One pytest item made of 3 named sub-checks. No dataset, model or network: the zone cuts are found on a drawn page with two
green strips, and the grouping runs on boxes at known positions.
"""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline.ocr.columns import find_zone_cuts, group_by_zone
from pipeline.structuring.prompts import COLUMNS_SYSTEM_PROMPT, PROMPTS, SYSTEM_PROMPT

from ..checks import run_checks

WIDTH, HEIGHT = 800, 1100
GREEN = (60, 190, 90)


def _drawn_page(path: Path) -> np.ndarray:
    """A grey page with two tall green strips (x 250-280 and 520-550, from y 190) and a short green header bar."""
    page = Image.new("RGB", (WIDTH, HEIGHT), (200, 200, 200))
    draw = ImageDraw.Draw(page)
    draw.rectangle((250, 190, 280, 1000), fill=GREEN)
    draw.rectangle((520, 190, 550, 1000), fill=GREEN)
    draw.rectangle(
        (20, 190, 230, 215), fill=GREEN
    )  # the "Véhicule A" bar: wide, but short
    page.save(path)
    return cv2.imread(str(path))


def _cuts_follow_the_green_strips(tmp_path: Path) -> None:
    """The cuts sit on the outer edges of the two strips and the header ends where the strips start.

    A cut through the middle of a strip would split the checkbox columns from the circumstances, and a header cut taken
    from the short header bar instead of the strips would be wrong, so the page has both.
    """
    left, right, header = find_zone_cuts(_drawn_page(tmp_path / "page.png"))
    assert abs(left - 250 / WIDTH) < 0.01, left
    assert abs(right - 550 / WIDTH) < 0.01, right
    assert abs(header - 190 / HEIGHT) < 0.01, header


def _boxes_land_in_the_right_block() -> None:
    """Each box goes to the zone of its centre, and each block is sorted top to bottom.

    Boxes are given out of order: the lower vehicle A line first. The header holds what is above the cut, the strips'
    own columns go to the circumstances, and a block with no box is still printed, so the blocks are always the same four.
    """

    def box(x: int, y: int) -> np.ndarray:
        return np.array([[x, y], [x + 40, y], [x + 40, y + 20], [x, y + 20]])

    boxes = [box(50, 600), box(60, 300), box(400, 400), box(600, 400), box(30, 50)]
    texts = ["A low", "A high", "middle", "B", "title"]
    result = group_by_zone(boxes, texts, (WIDTH, HEIGHT), (0.31, 0.69, 0.17))
    assert result == (
        "## header\ntitle\n\n## vehicle_a\nA high\nA low\n\n## circumstances\nmiddle\n\n## vehicle_b\nB"
    ), result


def _columns_prompt_differs_only_in_the_column_bullet() -> None:
    """The columns prompt is the flat prompt with one bullet replaced, and both are registered by name.

    Everything else in the prompt (formats, rules about nulls) must be identical, so a run with the columns prompt differs
    from a run with the flat prompt only in how it describes the OCR text.
    """
    assert (
        PROMPTS["flat"] == SYSTEM_PROMPT and PROMPTS["columns"] == COLUMNS_SYSTEM_PROMPT
    )
    flat = [line for line in SYSTEM_PROMPT.splitlines() if "two columns" not in line]
    columns = [
        line for line in COLUMNS_SYSTEM_PROMPT.splitlines() if "4 blocks" not in line
    ]
    assert flat == columns and len(flat) < len(SYSTEM_PROMPT.splitlines())
    assert "mixes the columns" not in COLUMNS_SYSTEM_PROMPT


def test_columns(tmp_path: Path) -> None:
    """The cuts follow the green strips, boxes are grouped by zone, and the columns prompt is the flat one with one bullet changed."""
    run_checks(
        [
            (
                "cuts_follow_the_green_strips",
                lambda: _cuts_follow_the_green_strips(tmp_path),
            ),
            ("boxes_land_in_the_right_block", _boxes_land_in_the_right_block),
            (
                "columns_prompt_differs_only_in_the_column_bullet",
                _columns_prompt_differs_only_in_the_column_bullet,
            ),
        ]
    )
