"""Generate the frozen synthetic dataset every version is evaluated on.

    uv run python -m generator.dataset --out ../data/synthetic --count 500 --dev 100 --seed 1

Form i uses seed (base_seed * 1_000_000 + i), so the same command always gives the same records. The first `dev` forms
are the dev split (for tuning), the rest the test split (never tuned on). Every form is degraded at the "phone" level.
"""

import argparse
import hashlib
import json
import os
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from .data import sample_record
from .degrade import degrade
from .render import render

TEMPLATE = Path(__file__).resolve().parents[1] / "assets/constat-template.pdf"
LEVEL = "phone"  # the one degradation level of the dataset (the generator CLI offers others for experiments)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make(job):
    i, seed, split, level, out, keep_clean = job
    rng = random.Random(
        seed
    )  # same call order as `python -m generator`, so a single form can be reproduced from its seed
    record = sample_record(rng)
    clean = render(TEMPLATE, record, rng)
    image = degrade(clean, level, rng)
    name = f"{i:06d}"
    folder = out / split
    folder.mkdir(parents=True, exist_ok=True)
    image.save(folder / f"{name}.jpg", quality=95)
    truth = json.dumps(record, indent=2, ensure_ascii=False)
    (folder / f"{name}.json").write_text(truth)
    if keep_clean:
        (out / "clean").mkdir(exist_ok=True)
        clean.save(out / "clean" / f"{name}.png")
    return {
        "id": name,
        "split": split,
        "level": level,
        "seed": seed,
        "image": f"{split}/{name}.jpg",
        "truth": f"{split}/{name}.json",
        "image_sha256": sha((folder / f"{name}.jpg").read_bytes()),
        "truth_sha256": sha(truth.encode()),
    }


def generate(out, count=500, dev=100, seed=1, keep_clean=False, workers=None):
    out = Path(out)
    assert 0 <= dev <= count, "dev must be between 0 and count"
    jobs = [
        (i, seed * 1_000_000 + i, "dev" if i < dev else "test", LEVEL, out, keep_clean)
        for i in range(count)
    ]
    out.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(workers or os.cpu_count()) as pool:
        rows = sorted(pool.map(make, jobs, chunksize=4), key=lambda r: r["id"])
    (out / "manifest.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    summary = {
        "count": count,
        "dev": dev,
        "test": count - dev,
        "base_seed": seed,
        "level": LEVEL,
        # changes if any answer key changes: compare it to know two runs (or two code versions) produced the same data
        "fingerprint": sha("".join(r["truth_sha256"] for r in rows).encode()),
    }
    (out / "dataset.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--out", default="../data/synthetic")
    p.add_argument("--count", type=int, default=500)
    p.add_argument("--dev", type=int, default=100)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument(
        "--keep-clean",
        action="store_true",
        help="also save the undegraded render of each form (about 1 MB each)",
    )
    p.add_argument("--workers", type=int, default=None, help="default: all CPU cores")
    args = p.parse_args()
    print(
        json.dumps(
            generate(
                args.out, args.count, args.dev, args.seed, args.keep_clean, args.workers
            ),
            indent=2,
        )
    )
