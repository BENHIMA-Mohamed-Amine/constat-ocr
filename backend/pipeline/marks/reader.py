"""Read what a driver marked on the form, from fixed positions on the template, with plain image processing and no model.

The page is aligned on the blank template, then each mark is a measurement at a known place: ink in a checkbox, colour in a vehicle-type
tile, ink on a ring around a licence letter, a blue patch on the impact picture, ink in an OUI or NON cell. Thresholds were set on the
dev forms only.

Works on the synthetic forms, where the marks are clean ink crosses, one circle, a colour highlight and a blue patch. Real forms have
messier marks; this reader is a baseline for what the template alone can tell.
"""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from generator import drawings, fields

from ..core.schema import Record, Vehicle
from .align import to_template
from .layout import SCALE, Box, Layout, load_layout

INK = 55  # a pixel this much darker than the blank template is ink
TICK_THRESHOLD = 0.14  # share of ink pixels inside a box: dev forms gave 0.225 and above for ticked, 0.058 and below for empty
SATURATED = (
    70  # a tile pixel this colourful belongs to the highlight; grey tiles have none
)
_VEHICLES = ("vehicle_a", "vehicle_b")


@dataclass(frozen=True)
class VehicleMarks:
    """What was marked for one vehicle."""

    circumstances: list[int]
    vehicle_type: str
    license_category: str
    impact_zone: str


@dataclass(frozen=True)
class Marks:
    """Everything read from the template positions of one form."""

    vehicle_a: VehicleMarks
    vehicle_b: VehicleMarks
    other_damage: bool

    def apply(self, record: Record) -> Record:
        """The record with the fields these marks give replaced. The tick count is the number of ticks."""
        update: dict[str, object] = {"other_damage": self.other_damage}
        for name in _VEHICLES:
            marks = getattr(self, name)
            vehicle = getattr(record, name) or Vehicle()
            update[name] = vehicle.model_copy(
                update={
                    "circumstances": marks.circumstances,
                    "circumstance_count": len(marks.circumstances),
                    "vehicle_type": marks.vehicle_type,
                    "license_category": marks.license_category,
                    "impact_zone": marks.impact_zone,
                }
            )
        return record.model_copy(update=update)


class MarksReader:
    """Reads the marks of a straightened photo of the form."""

    def __init__(self, template_pdf: Path) -> None:
        """Load the blank template.

        Args:
            template_pdf: The blank constat page.
        """
        self._layout: Layout = load_layout(template_pdf)

    def read(self, image_path: Path) -> Marks:
        """Align the straightened page on the template and measure every mark.

        Raises:
            ValueError: If the image cannot be read.
        """
        page = cv2.imread(str(image_path))
        if page is None:
            raise ValueError(f"image not found or unreadable: {image_path}")
        aligned = to_template(page, self._layout.template)
        gray, ink = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY), self._ink(aligned)
        sides = [
            VehicleMarks(
                circumstances=self._ticks(gray, ink, side),
                vehicle_type=self._vehicle_type(aligned, side),
                license_category=self._license_category(gray, ink, side),
                impact_zone=self._impact_zone(aligned, side),
            )
            for side in (0, 1)
        ]
        return Marks(sides[0], sides[1], self._other_damage(ink))

    def _ink(self, aligned: np.ndarray) -> np.ndarray:
        """How much darker each pixel is than the blank template, with lighting differences removed.

        The template is thickened by 2 pixels first, so a printed line that lands a pixel or two off is not counted as ink.
        """
        gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY).astype(np.float32)
        template = self._layout.template.astype(np.float32)
        gain = cv2.GaussianBlur(gray, (0, 0), 25) / (
            cv2.GaussianBlur(template, (0, 0), 25) + 1
        )
        return np.clip(
            cv2.erode(template, np.ones((5, 5), np.uint8)) * gain - gray, 0, 255
        )

    def _shift(
        self, gray: np.ndarray, box: Box, margin: int = 5, radius: int = 10
    ) -> tuple[int, int]:
        """How far the printed content around ``box`` sits from where the template says, found by matching the template patch."""
        x0, y0, x1, y1 = box
        patch = self._layout.template[
            y0 - margin : y1 + margin, x0 - margin : x1 + margin
        ]
        area = gray[
            y0 - margin - radius : y1 + margin + radius,
            x0 - margin - radius : x1 + margin + radius,
        ]
        _, _, _, (best_x, best_y) = cv2.minMaxLoc(
            cv2.matchTemplate(area, patch, cv2.TM_CCOEFF_NORMED)
        )
        return best_x - radius, best_y - radius

    def tick_scores(self, gray: np.ndarray, ink: np.ndarray, side: int) -> list[float]:
        """The share of ink pixels inside each of the 23 boxes of one vehicle, after moving each box onto its printed square.

        The alignment of the whole page can be a few pixels off at one end of the column, so each box is placed on its own.
        """
        scores = []
        for box in self._layout.ticks[side]:
            dx, dy = self._shift(gray, box)
            x0, y0, x1, y1 = box
            scores.append(
                float(
                    (
                        ink[y0 + dy + 2 : y1 + dy - 2, x0 + dx + 2 : x1 + dx - 2] > INK
                    ).mean()
                )
            )
        return scores

    def _ticks(self, gray: np.ndarray, ink: np.ndarray, side: int) -> list[int]:
        return [
            n
            for n, score in enumerate(self.tick_scores(gray, ink, side), start=1)
            if score >= TICK_THRESHOLD
        ]

    def _vehicle_type(self, aligned: np.ndarray, side: int) -> str:
        """The tile with the most colour: the chosen one is filled with the vehicle's highlight, the others are grey."""
        x0, y0, x1, y1 = self._layout.pickers[side]
        sx, sy = (x1 - x0) / drawings.PICKER[0], (y1 - y0) / drawings.PICKER[1]
        saturation = cv2.cvtColor(aligned, cv2.COLOR_BGR2HSV)[..., 1]
        share = {
            name: float(
                (
                    saturation[
                        int(y0 + b * sy) : int(y0 + d * sy),
                        int(x0 + a * sx) : int(x0 + c * sx),
                    ]
                    > SATURATED
                ).mean()
            )
            for name, (a, b, c, d) in drawings.TILES.items()
        }
        return max(share, key=share.get)

    def _license_category(self, gray: np.ndarray, ink: np.ndarray, side: int) -> str:
        """The letter with the most ink on a ring around it: the driver circles the right one.

        The row of letters is placed on its printed letters first.
        """
        centres = self._layout.categories[side]
        xs, ys = (
            [c[0] for c in centres],
            [c[1] for c in centres],
        )  # vehicle B's letters run right to left
        row = (
            int(min(xs) - 8 * SCALE),
            int(min(ys) - 6 * SCALE),
            int(max(xs) + 8 * SCALE),
            int(max(ys) + 6 * SCALE),
        )
        dx, dy = self._shift(gray, row)
        yy, xx = np.ogrid[: ink.shape[0], : ink.shape[1]]
        scores = []
        for cx, cy in centres:
            x, y = cx + dx, cy + dy
            reach = int(11 * SCALE)
            window = (
                slice(int(y) - reach, int(y) + reach),
                slice(int(x) - reach, int(x) + reach),
            )
            distance = np.sqrt(
                (xx[:, window[1]] - x) ** 2 + (yy[window[0], :] - y) ** 2
            )
            ring = (distance > 6.5 * SCALE) & (distance < 9.5 * SCALE)
            scores.append(float((ink[window][ring] > INK).mean()))
        return fields.CATEGORIES[int(np.argmax(scores))]

    def _impact_zone(self, aligned: np.ndarray, side: int) -> str:
        """The zone whose rectangle best matches the vivid blue patch on the impact picture."""
        x0, y0, x1, y1 = (int(v) for v in self._layout.impacts[side])
        hsv = cv2.cvtColor(aligned[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
        blue = (
            (np.abs(hsv[..., 0].astype(int) - 100) < 12)
            & (hsv[..., 1] > 150)
            & (hsv[..., 2] > 120)
        )
        ys, xs = np.nonzero(blue)
        if len(xs) < 30:  # no patch found: fall back to the most common zone
            return "front_left"
        sx, sy = (x1 - x0) / drawings.IMPACT[0], (y1 - y0) / drawings.IMPACT[1]
        patch = (
            np.percentile(xs, 2) / sx,
            np.percentile(ys, 2) / sy,
            np.percentile(xs, 98) / sx,
            np.percentile(ys, 98) / sy,
        )

        def overlap(zone: str) -> float:
            (a, b, c, d), _ = drawings.ZONES[zone]
            inter = max(0, min(patch[2], c) - max(patch[0], a)) * max(
                0, min(patch[3], d) - max(patch[1], b)
            )
            return inter / (
                (patch[2] - patch[0]) * (patch[3] - patch[1])
                + (c - a) * (d - b)
                - inter
            )

        return max(drawings.ZONES, key=overlap)

    def _other_damage(self, ink: np.ndarray) -> bool:
        """True when the OUI cells hold more ink than the NON cells (the driver marks both sides alike)."""
        share = {
            answer: float(
                np.mean([(ink[y0:y1, x0:x1] > INK).mean() for x0, y0, x1, y1 in cells])
            )
            for answer, cells in self._layout.damage.items()
        }
        return share[True] > share[False]
