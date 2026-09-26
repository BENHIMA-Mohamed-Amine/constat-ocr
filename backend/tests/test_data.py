"""Consistency of the sampled records. Run from backend/: uv run python -m tests.test_data"""

import math
import random
from datetime import datetime

from generator.data import LANE_Y, STEM_DX, _contact, _fits, sample_record


def day(s):
    return datetime.strptime(s, "%d/%m/%Y")


def check(seed):
    r = sample_record(random.Random(seed))
    accident = day(r["date"])
    for k in "ab":
        v = r[f"vehicle_{k}"]
        assert v["circumstance_count"] == len(v["circumstances"]), seed
        assert day(v["valid_from"]) <= accident <= day(v["valid_to"]), (
            seed
        )  # attestation covers the accident
        assert day(v["license_issued"]) < accident <= day(v["license_valid_until"]), (
            seed
        )
    assert r["vehicle_a"]["plate"] != r["vehicle_b"]["plate"], seed
    a, b = (
        r["sketch"]["a"],
        r["sketch"]["b"],
    )  # the damaged zones of A and B must touch in the sketch
    (pax, pay), _ = _contact(r["vehicle_a"]["impact_zone"], a["heading"])
    (pbx, pby), _ = _contact(r["vehicle_b"]["impact_zone"], b["heading"])
    gap = math.hypot(a["x"] + pax - (b["x"] + pbx), a["y"] + pay - (b["y"] + pby))
    assert gap < 3, (seed, gap)
    assert _fits(a["x"], a["y"], a["heading"]) and _fits(
        b["x"], b["y"], b["heading"]
    ), seed
    sk = r["sketch"]  # the layout must match how the cars sit

    def off(h, target):
        return min(abs((h - target) % 360), abs((target - h) % 360))

    lane = 0 if off(a["heading"], 0) < 10 else 180
    assert off(a["heading"], lane) < 10 and abs(a["y"] - LANE_Y[lane]) < 4, (
        seed
    )  # A is in the lane of its direction
    if sk["layout"] == "two_way":
        assert (
            sk["junction"] is None
            and min(off(b["heading"], 0), off(b["heading"], 180)) < 55
        ), seed
    else:
        down = 90 if off(b["heading"], 90) < off(b["heading"], 270) else 270
        assert off(b["heading"], down) < 55 and sk["junction"]["side"] == (
            "north" if down == 90 else "south"
        ), seed
        assert abs(b["x"] - (sk["junction"]["x"] + STEM_DX[down])) < 1, (
            seed
        )  # B is in its lane of the side road


if __name__ == "__main__":
    for seed in range(300):
        check(seed)
    print("ok: 300 records consistent")
