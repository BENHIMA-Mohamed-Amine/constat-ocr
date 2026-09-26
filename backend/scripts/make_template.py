"""Blank the filled constat PDF into a PII-free template.

Values to remove live in _local/values.json ([text, [x0,y0,x1,y1]] pairs; gitignored, contains PII).
Drawn checkbox marks and signature images are removed by rule; the vehicle picker, impact pictures
and sketch box are kept but rebuilt without the user's selection, arrow or drawing.
"""

import io
import json
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

BACKEND = Path(__file__).resolve().parents[1]
SRC, VALUES = (
    BACKEND.parent / "_local/constat-maroc-filled.pdf",
    BACKEND.parent / "_local/values.json",
)
OUT = BACKEND / "assets/constat-template.pdf"

doc = pymupdf.open(SRC)
page = doc[0]
values = json.load(open(VALUES))

for text, clip in values:
    x0, y0, x1, y1 = clip
    hits = page.search_for(text, clip=pymupdf.Rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1))
    assert hits, f"value not found: {text!r} in {clip}"
    for r in hits:
        # centre band only: line spacing is tight, full-height rects would clip the label on the next line
        page.add_redact_annot(
            pymupdf.Rect(r.x0 - 0.5, r.y0 + 1.5, r.x1 + 0.5, r.y1 - 1.5)
        )

PICKER, IMPACT, SKETCH = (
    (362, 336),
    (232, 331),
    (240, 82),
)  # image pixel sizes, rebuilt below
images = {(i["width"], i["height"]): [] for i in page.get_image_info()}
for i in page.get_image_info(xrefs=True):
    images[(i["width"], i["height"])].append(i["xref"])
    if (i["width"], i["height"]) not in (PICKER, IMPACT, SKETCH):  # signatures
        page.add_redact_annot(pymupdf.Rect(i["bbox"]))

page.apply_redactions(
    images=pymupdf.PDF_REDACT_IMAGE_REMOVE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE
)

# second pass, text untouched: drawn X marks (stroke-only squares on a checkbox) and the boxes
# around the selected licence category letter (A side, B side); redraw the empty checkbox afterwards
SELECTION_BOXES = [(43, 452, 56, 466), (540, 442, 553, 456)]
drawings = page.get_drawings()
boxes = {
    tuple(round(v) for v in d["rect"]): d
    for d in drawings
    if d["type"] == "fs" and 6 < d["rect"].width < 9 and 6 < d["rect"].height < 9
}
marks = [
    tuple(round(v) for v in d["rect"])
    for d in drawings
    if d["type"] == "s"
    and d["fill"] is None
    and 6 < d["rect"].width < 9
    and 6 < d["rect"].height < 9
]
for m in marks + SELECTION_BOXES:
    page.add_redact_annot(pymupdf.Rect(m))

page.apply_redactions(
    images=pymupdf.PDF_REDACT_IMAGE_NONE,
    text=pymupdf.PDF_REDACT_TEXT_NONE,
    graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
)

for m in set(marks):
    b = boxes[m]
    page.draw_rect(b["rect"], color=b["color"], fill=b["fill"], width=b["width"])


def load_rgba(xref):
    info = doc.extract_image(xref)
    im = Image.open(io.BytesIO(info["image"])).convert("RGB")
    if info["smask"]:
        m = pymupdf.Pixmap(doc, info["smask"])
        im.putalpha(Image.frombytes("L", (m.width, m.height), m.samples))
    return im.convert("RGBA")


def png(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def unselect_picker(im):
    """The selected tile is the only saturated one: its border bounds it. Repaint it like the grey tiles."""
    px = im.load()
    sat = [
        (x, y)
        for y in range(im.height)
        for x in range(im.width)
        if px[x, y][3] and max(px[x, y][:3]) - min(px[x, y][:3]) > 60
    ]
    x0, y0 = min(x for x, _ in sat), min(y for _, y in sat)
    x1, y1 = max(x for x, _ in sat), max(y for _, y in sat)
    tile = px[20, 20][:3]  # background of an unselected tile
    icon_grey = 160
    src, out = im.copy().load(), im.copy()
    ImageDraw.Draw(out).rounded_rectangle(
        (x0, y0, x1, y1), radius=4, fill=tile + (255,)
    )
    op = out.load()
    for y in range(y0 + 3, y1 - 2):
        for x in range(x0 + 3, x1 - 2):
            cov = 1 - min(src[x, y][:3]) / 255
            if cov > 0.02:
                op[x, y] = tuple(round(t + (icon_grey - t) * cov) for t in tile) + (
                    255,
                )
    return out


def blue_rows(im):
    px = im.load()
    return [
        y
        for y in range(im.height)
        if any(
            px[x, y][3] and px[x, y][2] > 200 and px[x, y][0] < 80
            for x in range(im.width)
        )
    ]


def clear_impact(a, b):
    """Each impact picture has its arrow on a blue patch (one at the top, one at the bottom); the car
    and road are otherwise identical, so take the arrow-free rows from the other picture."""
    top, bottom = (
        (a, b) if sum(blue_rows(a)) / len(blue_rows(a)) < a.height / 2 else (b, a)
    )
    cut = max(blue_rows(top)) + 1
    assert cut <= min(blue_rows(bottom)), "blue patches overlap, rows cannot be swapped"
    out = top.copy()
    out.paste(bottom.crop((0, 0, top.width, cut)), (0, 0))
    return out


def blank_sketch(im):
    """Empty road canvas: the lane/direction arrows and the cars are drawn per accident by the generator."""
    px = im.load()
    strip = next(
        x for x in range(im.width) if sum(px[x, 5][:3]) / 3 < 200
    )  # pale strip on the left edge
    out = Image.new("RGBA", im.size, px[im.width // 2, 5])
    out.paste(px[2, 5], (0, 0, strip, im.height))
    return out


for xref in images.get(PICKER, []):
    page.replace_image(xref, stream=png(unselect_picker(load_rgba(xref))))
impact = [load_rgba(x) for x in images[IMPACT]]
for xref in images[IMPACT]:
    page.replace_image(xref, stream=png(clear_impact(*impact)))
for xref in images.get(SKETCH, []):
    page.replace_image(xref, stream=png(blank_sketch(load_rgba(xref))))

doc.set_metadata({})
doc.save(OUT, garbage=4, deflate=True)

# check: no value of 3+ chars survives in the template text
out_text = pymupdf.open(OUT)[0].get_text()
leaks = [t for t, _ in values if len(t) > 2 and t in out_text]
assert not leaks, f"values still present: {leaks}"
print(f"ok: {OUT}, {len(values)} values, {len(marks)} marks")
