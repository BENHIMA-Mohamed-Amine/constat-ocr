"""Make a clean render look scanned or photographed. Pillow only."""

import io
import random

from PIL import Image, ImageChops, ImageFilter

# level: rotation deg, warp (fraction of size), blur px, noise sigma, shadow strength, jpeg quality, desk margin (fraction)
LEVELS = {
    "scan": (1.0, 0.004, 0.5, 6, 0.10, 82, 0.0),
    "phone": (3.0, 0.02, 0.9, 10, 0.30, 65, 0.06),
    "bad": (5.0, 0.04, 1.5, 18, 0.45, 45, 0.10),
}
DESK = (118, 104, 92)


def degrade(img, level, rng: random.Random):
    angle, warp, blur, noise, shadow, quality, margin = LEVELS[level]
    w, h = img.size
    paper = ImageChops.multiply(
        img,
        Image.new(
            "RGB",
            img.size,
            (rng.randint(240, 252), rng.randint(238, 250), rng.randint(228, 246)),
        ),
    )
    mx, my = round(w * margin), round(h * margin)
    canvas = Image.new("RGB", (w + 2 * mx, h + 2 * my), DESK)
    canvas.paste(paper, (mx, my))
    canvas = canvas.rotate(
        rng.uniform(-angle, angle), resample=Image.BICUBIC, fillcolor=DESK
    )

    cw, ch = canvas.size

    def j():
        return rng.uniform(-warp, warp)

    quad = (
        cw * j(),
        ch * j(),
        cw * j(),
        ch * (1 + j()),
        cw * (1 + j()),
        ch * (1 + j()),
        cw * (1 + j()),
        ch * j(),
    )  # corners: UL, LL, LR, UR
    canvas = canvas.transform(
        canvas.size, Image.QUAD, quad, Image.BICUBIC, fillcolor=DESK
    )

    side = 2 * max(
        canvas.size
    )  # oversized so the rotated gradient still covers the canvas, then centre-crop
    light = (
        Image.linear_gradient("L")
        .resize((side, side))
        .rotate(rng.uniform(0, 360), resample=Image.BICUBIC)
    )
    left, top = (side - canvas.width) // 2, (side - canvas.height) // 2
    light = light.crop((left, top, left + canvas.width, top + canvas.height))
    dark = light.point(
        lambda p: 255 - int(p * shadow)
    )  # brighter side keeps 255, far side is darkened
    canvas = ImageChops.multiply(canvas, Image.merge("RGB", (dark, dark, dark)))

    canvas = canvas.filter(ImageFilter.GaussianBlur(rng.uniform(blur * 0.6, blur)))
    # seeded noise (Image.effect_noise uses a global generator, which would make results depend on process scheduling);
    # uniform bytes rescaled to standard deviation `noise` around mid-grey
    grain = (
        Image.frombytes("L", canvas.size, rng.randbytes(canvas.width * canvas.height))
        .point(lambda p: round(128 + (p - 127.5) * noise / 73.6))
        .convert("RGB")
    )
    canvas = ImageChops.add(canvas, grain, scale=1, offset=-128)

    buf = io.BytesIO()
    canvas.save(buf, "JPEG", quality=quality)
    return Image.open(buf).convert("RGB")
