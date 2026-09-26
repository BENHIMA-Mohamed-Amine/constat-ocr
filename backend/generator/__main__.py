"""python -m generator --seed 1 --level phone --out ../_local/sample"""

import argparse
import json
import random
from pathlib import Path

from .data import sample_record
from .degrade import LEVELS, degrade
from .render import render

TEMPLATE = Path(__file__).resolve().parents[1] / "assets/constat-template.pdf"

p = argparse.ArgumentParser()
p.add_argument("--seed", type=int, default=1)
p.add_argument("--level", choices=LEVELS, default="phone")
p.add_argument("--out", type=Path, default=Path("../_local/sample"))
args = p.parse_args()

rng = random.Random(args.seed)
record = sample_record(rng)
clean = render(TEMPLATE, record, rng)
args.out.mkdir(parents=True, exist_ok=True)
name = f"{args.seed:06d}"
clean.save(args.out / f"{name}_clean.png")
degrade(clean, args.level, rng).save(args.out / f"{name}_{args.level}.jpg", quality=95)
(args.out / f"{name}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False))
print(f"wrote {args.out}/{name}_clean.png, {name}_{args.level}.jpg, {name}.json")
