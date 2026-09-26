"""The dataset command is deterministic and splits as asked. Run from backend/: uv run python -m tests.test_dataset"""

import json
import tempfile
from pathlib import Path

from generator.dataset import generate


def rows(out):
    return [
        json.loads(line)
        for line in (Path(out) / "manifest.jsonl").read_text().splitlines()
    ]


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        first = generate(a, count=5, dev=2, seed=7, workers=1)
        second = generate(b, count=5, dev=2, seed=7, workers=2)
        assert first == second, "same command, different dataset"
        assert rows(a) == rows(b), (
            "images or answer keys differ between runs"
        )  # hashes of every file
        assert [r["split"] for r in rows(a)] == ["dev", "dev", "test", "test", "test"]
        assert {r["level"] for r in rows(a)} == {"phone"}
        for r in rows(a):
            assert (Path(a) / r["image"]).exists() and (Path(a) / r["truth"]).exists()
        other = generate(a, count=5, dev=2, seed=8, workers=1)
        assert other["fingerprint"] != first["fingerprint"], "seed has no effect"
    print("ok: deterministic, split as asked, phone level only")
