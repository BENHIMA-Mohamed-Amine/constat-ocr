"""The drawn parts of the form: selected vehicle type, impact-point patch, accident sketch.
Coordinates are pixels of the pictures embedded in the template (picker 362x336, impact 232x331, sketch 240x82)."""

import math

from PIL import Image, ImageDraw, ImageFont

from .data import CANVAS_SIZE, CAR_LENGTH, CAR_WIDTH, LANE_Y, STEM_DX

PICKER, IMPACT, SKETCH = (362, 336), (232, 331), (240, 82)
TILES = {
    "moto": (5, 5, 178, 105),
    "tricycle": (184, 5, 357, 105),
    "car": (5, 116, 178, 216),
    "bus": (184, 116, 357, 216),
    "truck": (5, 227, 357, 327),
}
SELECT = {
    "a": (17, 173, 183),
    "b": (218, 155, 44),
}  # highlight colour per vehicle, as in the source app
ROAD, BLUE, WHITE = (101, 101, 99), (46, 168, 224), (255, 255, 255)


def _flip(
    zone,
):  # mirror a front zone into the matching rear zone (picture is 331 px tall)
    (x0, y0, x1, y1), arrows = zone
    return (x0, 331 - y1, x1, 331 - y0), [
        ((tx, 331 - ty), (hx, 331 - hy)) for (tx, ty), (hx, hy) in arrows
    ]


_FRONT = {
    "front_left": ((13, 17, 150, 91), [((38, 30), (66, 64)), ((116, 26), (116, 64))]),
    "front": ((82, 17, 150, 91), [((116, 26), (116, 64))]),
    "front_right": (
        (82, 17, 219, 91),
        [((194, 30), (166, 64)), ((116, 26), (116, 64))],
    ),
}
ZONES = {
    **_FRONT,
    **{name.replace("front", "rear"): _flip(z) for name, z in _FRONT.items()},
    "left": ((13, 110, 82, 220), [((28, 165), (70, 165))]),
    "right": ((150, 110, 219, 220), [((204, 165), (162, 165))]),
}


def boxes(page, scale):
    """Pixel boxes of the embedded pictures, left to right: (A picker, B picker), (A impact, B impact), sketch."""

    def find(size):
        return sorted(
            (
                [v * scale for v in i["bbox"]]
                for i in page.get_image_info()
                if (i["width"], i["height"]) == size
            ),
            key=lambda b: b[0],
        )

    return find(PICKER), find(IMPACT), find(SKETCH)[0]


def mark_vehicle_type(img, box, vtype, side):
    """Highlight the chosen tile the way the app does: white tile, coloured border, icon in the vehicle's colour."""
    bx0, by0, bx1, by1 = box
    sx, sy = (bx1 - bx0) / PICKER[0], (by1 - by0) / PICKER[1]
    x0, y0, x1, y1 = TILES[vtype]
    r = (
        round(bx0 + x0 * sx),
        round(by0 + y0 * sy),
        round(bx0 + x1 * sx),
        round(by0 + y1 * sy),
    )
    colour, tile = SELECT[side], img.crop(r)
    px = tile.load()
    for y in range(tile.height):
        for x in range(tile.width):
            cover = min(
                1, max(0, (243 - min(px[x, y])) / (243 - 160))
            )  # grey icon on grey tile -> how much icon
            px[x, y] = tuple(round(255 + (c - 255) * cover) for c in colour)
    img.paste(tile, r[:2])
    ImageDraw.Draw(img).rounded_rectangle(r, radius=4, outline=colour, width=2)


def _arrow(draw, tail, tip, width=3, head=9, colour=WHITE):
    dx, dy = tip[0] - tail[0], tip[1] - tail[1]
    n = (dx * dx + dy * dy) ** 0.5
    ux, uy = dx / n, dy / n
    base = (tip[0] - ux * head, tip[1] - uy * head)
    draw.line([tail, base], fill=colour, width=width)
    draw.polygon(
        [
            tip,
            (base[0] - uy * head / 2, base[1] + ux * head / 2),
            (base[0] + uy * head / 2, base[1] - ux * head / 2),
        ],
        fill=colour,
    )


def mark_impact(img, box, zone):
    """Blue patch over the road where the car was hit, with white arrows pointing at it; the car stays on top."""
    bx0, by0, bx1, by1 = box
    sx, sy = (bx1 - bx0) / IMPACT[0], (by1 - by0) / IMPACT[1]
    at = lambda x, y: (bx0 + x * sx, by0 + y * sy)
    (px0, py0, px1, py1), arrows = ZONES[zone]
    (a, b), (c, d) = at(px0, py0), at(px1, py1)
    region = img.crop((round(a), round(b), round(c), round(d)))
    px = region.load()
    for y in range(region.height):
        for x in range(region.width):
            if all(
                abs(px[x, y][i] - ROAD[i]) < 14 for i in range(3)
            ):  # road only: car, lane dashes and edges stay
                px[x, y] = BLUE
    img.paste(region, (round(a), round(b)))
    draw = ImageDraw.Draw(img)
    for tail, tip in arrows:
        _arrow(draw, at(*tail), at(*tip))


WHITE_ARROW, ORANGE_ARROW = (
    ((255, 255, 255), 6, 24),
    ((255, 204, 128), 12, 32),
)  # colour, line width, head length (px at 4x)
ARROW_LENGTH = 26


def lane_arrows(sketch_record):
    """The road, as lane arrows: white = traffic heading right (main road) or down (side road), orange = left / up.
    Main road: two lanes, three arrows each. A T-junction adds a side road with one arrow per lane, and leaves the junction clear."""
    junction = sketch_record["junction"]
    clear = (junction["x"] - 26, junction["x"] + 26) if junction else None
    arrows = []
    for tail_x in (22, 94, 166):
        arrows.append(
            (WHITE_ARROW, (tail_x, LANE_Y[0]), (tail_x + ARROW_LENGTH, LANE_Y[0]))
        )
    for tail_x in (214, 142, 70):
        arrows.append(
            (ORANGE_ARROW, (tail_x, LANE_Y[180]), (tail_x - ARROW_LENGTH, LANE_Y[180]))
        )
    if junction:
        arrows = [
            a
            for a in arrows
            if not clear[0] < min(a[1][0], a[2][0]) + ARROW_LENGTH / 2 < clear[1]
        ]
        x = junction["x"]
        near, far = (
            (6, 30) if junction["side"] == "north" else (114, 90)
        )  # side road end at the canvas edge / at the main road
        arrows.append(
            (
                WHITE_ARROW,
                (x + STEM_DX[90], min(near, far)),
                (x + STEM_DX[90], max(near, far)),
            )
        )
        arrows.append(
            (
                ORANGE_ARROW,
                (x + STEM_DX[270], max(near, far)),
                (x + STEM_DX[270], min(near, far)),
            )
        )
    return arrows


def sketch(img, box, record):
    """The road (lane arrows), then both cars with their letters, drawn 4x and scaled down so the edges are smooth."""
    ss = 4
    layer = Image.new("RGBA", (CANVAS_SIZE[0] * ss, CANVAS_SIZE[1] * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = ImageFont.load_default(size=9 * ss)
    for (colour, line, head), tail, tip in lane_arrows(record):
        _arrow(
            draw,
            (tail[0] * ss, tail[1] * ss),
            (tip[0] * ss, tip[1] * ss),
            width=line,
            head=head,
            colour=colour,
        )
    for side, fill, dark in (
        ("a", (150, 215, 240), (75, 90, 125)),
        ("b", (250, 195, 115), (120, 90, 60)),
    ):
        car = record[side]
        body = Image.new(
            "RGBA", (CAR_LENGTH * ss + 8, CAR_WIDTH * ss + 8), (0, 0, 0, 0)
        )
        bd = ImageDraw.Draw(body)
        bd.rounded_rectangle(
            (4, 4, CAR_LENGTH * ss + 4, CAR_WIDTH * ss + 4),
            radius=CAR_WIDTH * ss // 3,
            fill=fill + (255,),
            outline=dark + (255,),
            width=2,
        )
        for start in (0.30, 0.68):  # windscreens seen from above
            bd.rectangle(
                (
                    4 + CAR_LENGTH * ss * start,
                    4 + CAR_WIDTH * ss * 0.2,
                    4 + CAR_LENGTH * ss * (start + 0.14),
                    4 + CAR_WIDTH * ss * 0.8,
                ),
                fill=dark + (255,),
            )
        body = body.rotate(-car["heading"], expand=True, resample=Image.BICUBIC)
        cx, cy = car["x"] * ss, car["y"] * ss
        layer.alpha_composite(
            body, (round(cx - body.width / 2), round(cy - body.height / 2))
        )
        draw.text((cx, cy), side.upper(), font=font, fill=dark + (255,), anchor="mm")
    x0, y0, x1, y1 = (round(v) for v in box)
    small = layer.resize((x1 - x0, y1 - y0), Image.LANCZOS)
    img.paste(small.convert("RGB"), (x0, y0), small.getchannel("A"))
