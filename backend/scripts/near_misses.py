"""How wrong are the wrong text fields of a run, and was the right value close in the OCR text?

For every text field that is wrong, two questions:
  - how far is the final answer from the truth (nothing returned, 1 edit, 2 edits, more)?
  - how close does the truth come to anything in the OCR text (exact, same without punctuation, 1 or 2 edits, further)?
A wrong field that is one or two characters off, or sits in the text with different punctuation, is a candidate for a re-read or a
repair rule. A field with nothing close in the text was never read.

    uv run python -m scripts.near_misses v3c   (from backend/)
"""

import json
import sys
from collections import Counter, defaultdict

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from pipeline.core.config import Settings
from pipeline.data.storage import FileArtifactStore
from pipeline.evaluation.normalize import normalize

TEXT_KINDS = {"critical_text", "minor_text"}


def compact(value: object) -> str:
    """Normalised, without spaces."""
    return normalize(value).replace(" ", "")


def letters_and_digits(value: object) -> str:
    """Normalised, keeping only letters and digits (ignores punctuation)."""
    return "".join(c for c in normalize(value) if c.isalnum())


def nearest_distance(value: str, text: str) -> int:
    """Edit distance between ``value`` and its best-matching stretch of ``text`` (approximate)."""
    if not value or not text:
        return len(value)
    best = fuzz.partial_ratio_alignment(value, text)
    return Levenshtein.distance(value, text[best.dest_start : best.dest_end])


def main(run_id: str) -> None:
    run_dir = Settings().runs_dir / run_id
    store = FileArtifactStore(run_dir)
    forms = [f["id"] for f in json.loads((run_dir / "run.json").read_text())["forms"]]
    final, in_text = Counter(), Counter()
    per_field: dict[str, Counter] = defaultdict(Counter)
    total = wrong = 0
    for form_id in forms:
        ocr = store.read_text("ocr", form_id)
        ocr_compact, ocr_letters = compact(ocr), letters_and_digits(ocr)
        for field in store.read_json("evaluation", form_id)["fields"]:
            if field["kind"] not in TEXT_KINDS:
                continue
            total += 1
            if field["correct"]:
                continue
            wrong += 1
            name = field["path"].split(".")[-1]
            expected = compact(field["expected"])
            # 1. how far the final answer is
            if field["predicted"] is None:
                final_bucket = "no value returned"
            else:
                final_bucket = {1: "1 edit", 2: "2 edits"}.get(
                    field["edit_distance"], "3 or more edits"
                )
            final[final_bucket] += 1
            # 2. how close the truth is in the OCR text
            if expected in ocr_compact:
                text_bucket = "exact in the text"
            elif letters_and_digits(field["expected"]) in ocr_letters:
                text_bucket = "in the text, punctuation differs"
            else:
                distance = nearest_distance(expected, ocr_compact)
                text_bucket = {1: "1 edit away", 2: "2 edits away"}.get(
                    distance, "3 or more edits away"
                )
            in_text[text_bucket] += 1
            per_field[name][text_bucket] += 1
            per_field[name]["wrong"] += 1
    print(f"{run_id}: {wrong} wrong of {total} text fields\n")
    print("How far the final answer is from the truth")
    for bucket in ("no value returned", "1 edit", "2 edits", "3 or more edits"):
        print(f"  {bucket:34} {final[bucket]:4}  ({final[bucket] / wrong:.0%})")
    print("\nHow close the truth is to the OCR text")
    for bucket in (
        "exact in the text",
        "in the text, punctuation differs",
        "1 edit away",
        "2 edits away",
        "3 or more edits away",
    ):
        print(f"  {bucket:34} {in_text[bucket]:4}  ({in_text[bucket] / wrong:.0%})")
    print(
        "\nPer field (wrong / exact in text / punctuation / 1-2 edits away / 3+ away)"
    )
    for name, c in sorted(per_field.items(), key=lambda kv: -kv[1]["wrong"]):
        near = c["1 edit away"] + c["2 edits away"]
        print(
            f"  {name:20} {c['wrong']:3} / {c['exact in the text']:3} / {c['in the text, punctuation differs']:3} / {near:3} / {c['3 or more edits away']:3}"
        )


if __name__ == "__main__":
    main(sys.argv[1])
