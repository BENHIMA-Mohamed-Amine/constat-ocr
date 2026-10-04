"""How well does the template reader read the marks, on a whole split of the dataset (no LLM, no GPU)?

Straightens each photo (cached in runs/scratch/, which git ignores), reads the marks and compares them with the answer key: ticks found,
missed and extra, the tick count, vehicle type, licence category, impact zone and OUI/NON. Also prints how far the tick scores are from
the threshold, since the threshold was set on the dev forms.

    uv run python -m scripts.eval_marks dev    (from backend/; use "test" for the held-out forms)
"""

import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from pipeline.core.config import BACKEND_DIR, REPO_DIR
from pipeline.data.dataset import DatasetReader
from pipeline.marks import MarksReader
from pipeline.marks.reader import TICK_THRESHOLD
from pipeline.straightening.opencv import OpenCvStraightener

CACHE = REPO_DIR / "runs" / "scratch" / "straightened"
_reader: MarksReader | None = None


def _read(form):
    global _reader
    _reader = _reader or MarksReader(BACKEND_DIR / "assets" / "constat-template.pdf")
    straight = CACHE / form.split / f"{form.form_id}.jpg"
    if not straight.is_file():
        OpenCvStraightener().straighten(form.image_path, straight)
    marks = _reader.read(straight)
    return form.form_id, marks, form.load_truth()


def main(split: str) -> None:
    forms = DatasetReader(REPO_DIR / "data" / "synthetic").first(split, 10_000)
    with Pool(4) as pool:
        results = pool.map(_read, forms, chunksize=4)
    found = missed = extra = 0
    right: dict[str, int] = {
        k: 0
        for k in (
            "tick_count",
            "vehicle_type",
            "license_category",
            "impact_zone",
            "other_damage",
        )
    }
    total = {k: len(results) * (1 if k == "other_damage" else 2) for k in right}
    wrong: dict[str, list] = {k: [] for k in right}
    for form_id, marks, truth in results:
        right["other_damage"] += marks.other_damage == truth.other_damage
        if marks.other_damage != truth.other_damage:
            wrong["other_damage"].append(form_id)
        for side in ("vehicle_a", "vehicle_b"):
            got, want = getattr(marks, side), getattr(truth, side)
            ticked, expected = set(got.circumstances), set(want.circumstances)
            found, missed, extra = (
                found + len(ticked & expected),
                missed + len(expected - ticked),
                extra + len(ticked - expected),
            )
            for name, value in (
                ("tick_count", len(got.circumstances) == want.circumstance_count),
                ("vehicle_type", got.vehicle_type == want.vehicle_type),
                ("license_category", got.license_category == want.license_category),
                ("impact_zone", got.impact_zone == want.impact_zone),
            ):
                right[name] += value
                if not value:
                    wrong[name].append((form_id, side))
    print(f"{split}: {len(results)} forms (tick threshold {TICK_THRESHOLD})")
    print(
        f"ticks found {found} / missed {missed} / extra {extra}  (of {found + missed} real ticks)"
    )
    for name in right:
        print(
            f"{name:17} {right[name]}/{total[name]} ({right[name] / total[name]:.1%})  wrong: {wrong[name][:5]}"
        )


if __name__ == "__main__":
    main(sys.argv[1])
