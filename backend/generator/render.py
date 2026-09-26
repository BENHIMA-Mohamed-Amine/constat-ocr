"""Draw a record onto the template page in handwriting: per-character jitter, X marks, a circled licence category."""

import math
import random
from functools import lru_cache
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from . import drawings, fields

FONT_DIR = Path(__file__).resolve().parents[1] / "assets/fonts"
SYSTEM_FONTS = [
    f"/usr/share/fonts/opentype/comic-neue/ComicNeue-{s}.otf"
    for s in ("Regular", "Italic", "LightItalic")
]
INKS = [(25, 35, 140), (20, 20, 30), (40, 65, 155), (15, 30, 110)]
DPI = 200
SCALE = DPI / 72


@lru_cache
def x_height_ratio(font_path):
    """Lower-case letter height / font size, so different fonts can be scaled to the same visible size."""
    top, bottom = ImageFont.truetype(font_path, 100).getbbox("x", anchor="ls")[1::2]
    return (bottom - top) / 100


class Writer:
    """One hand: a font, an ink and a habit of slant and size, fixed for a whole vehicle block."""

    def __init__(self, rng):
        fonts = sorted(FONT_DIR.glob("*.[ot]tf")) or [
            Path(f) for f in SYSTEM_FONTS if Path(f).exists()
        ]
        self.font = str(rng.choice(fonts))
        self.ink = rng.choice(INKS)
        self.slant = rng.uniform(-0.05, 0.3)
        self.size = rng.uniform(1.0, 1.25)  # relative to the line height


def _char(img, ch, font, x, y, writer, rng):
    """Paste one glyph with its own tilt, slant, position and ink pressure. (x, y) is the left baseline."""
    pad = font.size
    layer = Image.new("RGBA", (int(pad * 2.5), int(pad * 2.5)), writer.ink + (0,))
    ImageDraw.Draw(layer).text(
        (pad // 2, pad * 1.5), ch, font=font, fill=writer.ink + (255,), anchor="ls"
    )
    layer = layer.transform(
        layer.size,
        Image.AFFINE,
        (1, writer.slant + rng.gauss(0, 0.05), 0, 0, 1, 0),
        Image.BICUBIC,
    )
    layer = layer.rotate(
        rng.gauss(0, 2.5), resample=Image.BICUBIC, center=(pad // 2, pad * 1.5)
    )
    pressure = rng.uniform(0.72, 1.0)
    alpha = layer.getchannel("A").point(lambda a: int(a * pressure))
    img.paste(
        layer.convert("RGB"),
        (round(x - pad // 2), round(y - pad * 1.5 + rng.gauss(0, 1.2))),
        alpha,
    )


def text(img, value, box, writer, rng, align="left"):
    x0, y0, x1, y1 = (v * SCALE for v in box)
    size = (
        (y1 - y0) * writer.size * 0.42 / x_height_ratio(writer.font)
    )  # 0.42 = wanted letter height as a share of the line
    while True:  # shrink until the line fits its box
        font = ImageFont.truetype(writer.font, round(size))
        gaps = [rng.uniform(0.94, 1.06) for _ in value]
        advances = [font.getlength(c) * g for c, g in zip(value, gaps)]
        if sum(advances) <= x1 - x0 or size < 12:
            break
        size *= 0.93
    x = {
        "left": x0,
        "right": x1 - sum(advances),
        "center": (x0 + x1 - sum(advances)) / 2,
    }[align] + rng.uniform(0, 3)
    baseline = y1 - (y1 - y0) * 0.12 + rng.gauss(0, 1.5)
    for ch, adv in zip(value, advances):
        if ch != " ":
            _char(img, ch, font, x, baseline, writer, rng)
        x += adv


def cross(draw, box, writer, rng):
    """An X over a checkbox: two strokes that overshoot a little and never quite meet."""
    x0, y0, x1, y1 = (v * SCALE for v in box)
    j = lambda: rng.uniform(-2.5, 2.5)
    w = rng.randint(2, 3)
    draw.line(
        [(x0 - 2 + j(), y0 - 2 + j()), (x1 + 2 + j(), y1 + 2 + j())],
        fill=writer.ink,
        width=w,
    )
    draw.line(
        [(x1 + 2 + j(), y0 - 2 + j()), (x0 - 2 + j(), y1 + 2 + j())],
        fill=writer.ink,
        width=w,
    )


def circle(draw, centre, writer, rng):
    cx, cy = centre[0] * SCALE, centre[1] * SCALE
    rx, ry, start = (
        8 * SCALE * rng.uniform(0.9, 1.15),
        7 * SCALE * rng.uniform(0.9, 1.15),
        rng.uniform(0, math.tau),
    )
    pts = [
        (
            cx + rx * math.cos(start + t) * rng.uniform(0.94, 1.06),
            cy + ry * math.sin(start + t) * rng.uniform(0.94, 1.06),
        )
        for t in [i * math.tau * 1.08 / 28 for i in range(29)]
    ]  # slightly more than a full turn, like a real loop
    draw.line(pts, fill=writer.ink, width=2, joint="curve")


def wrap2(value):
    words = value.split()
    cut = (
        max(
            range(1, len(words)),
            key=lambda i: -abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))),
        )
        if len(words) > 1
        else 1
    )
    return [" ".join(words[:cut]), " ".join(words[cut:])]


def render(template, record, rng):
    page = pymupdf.open(template)[0]
    pix = page.get_pixmap(dpi=DPI)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    draw = ImageDraw.Draw(img)
    (circ_a, circ_b), counts = fields.checkboxes(page)
    writers = {"a": Writer(rng), "b": Writer(rng)}
    pickers, impacts, sketch_box = drawings.boxes(page, SCALE)

    for name, box in fields.HEADER.items():
        text(img, record[name], box, writers["a"], rng)
    text(img, record["phone_b"], fields.PHONE_B, writers["b"], rng, "right")
    for cell in fields.OTHER_DAMAGE[record["other_damage"]]:
        x0, y0, x1, y1 = cell
        cross(draw, (x0 + 2, y0 + 1.5, x1 - 2, y1 - 1.5), writers["a"], rng)

    for side, i, circ, count_box in (
        ("a", 0, circ_a, counts[0]),
        ("b", 1, circ_b, counts[1]),
    ):
        v, w = record[f"vehicle_{side}"], writers[side]
        align = "left" if side == "a" else "right"
        for name, boxes in fields.VEHICLE.items():
            text(img, v[name], boxes[i], w, rng, align)
        x0, y0, x1, y1 = fields.DAMAGE[i]
        lines = wrap2(v["damage"]) if side == "a" else [v["damage"]]
        for k, ln in enumerate(lines):
            text(
                img,
                ln,
                (
                    x0,
                    y0 + k * (y1 - y0) / len(lines),
                    x1,
                    y0 + (k + 1) * (y1 - y0) / len(lines),
                ),
                w,
                rng,
                align,
            )
        circle(
            draw,
            fields.CATEGORY_CENTRES[i][fields.CATEGORIES.index(v["license_category"])],
            w,
            rng,
        )
        for n in v["circumstances"]:
            cross(draw, circ[n - 1], w, rng)
        text(img, str(v["circumstance_count"]), count_box, w, rng, "center")
        drawings.mark_vehicle_type(img, pickers[i], v["vehicle_type"], side)
        drawings.mark_impact(img, impacts[i], v["impact_zone"])
    drawings.sketch(img, sketch_box, record["sketch"])
    return img
