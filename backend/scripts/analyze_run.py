"""Where do the text-field errors of a run come from?

For every text field that is wrong, ask whether the answer-key value appears anywhere in the OCR text:
  - not in the OCR text: the OCR did not read it (nothing downstream could have got it right);
  - in the OCR text but no value returned: the LLM did not extract it;
  - in the OCR text but a different value: the LLM picked the wrong text.

    uv run python -m scripts.analyze_run v1-dev   (from backend/)
"""

import json
import sys
from collections import Counter, defaultdict

from pipeline.core.config import Settings
from pipeline.core.schema import Record
from pipeline.data.dataset import DatasetReader
from pipeline.data.storage import FileArtifactStore
from pipeline.evaluation.fields import (
    FIELD_KINDS,
    TOP_LEVEL_FIELDS,
    VEHICLE_FIELDS,
    VEHICLES,
    FieldKind,
)
from pipeline.evaluation.normalize import normalize

TEXT = (FieldKind.CRITICAL_TEXT, FieldKind.MINOR_TEXT)


def compact(text: str) -> str:
    """Normalised text without spaces, so '41654 - A - 55' and '41654-A-55' can be found in each other."""
    return normalize(text).replace(" ", "")


def main(run_id: str) -> None:
    settings = Settings()
    run_dir = settings.runs_dir / run_id
    store = FileArtifactStore(run_dir)
    forms = json.loads((run_dir / "run.json").read_text())["forms"]
    reader = DatasetReader(settings.dataset_dir)
    refs = {
        f.form_id: f
        for split in {f["split"] for f in forms}
        for f in reader.first(split, 10_000)
    }
    counts: dict[str, Counter] = defaultdict(
        Counter
    )  # "critical/vehicle_a" -> outcome -> count
    for form in forms:
        truth = refs[form["id"]].load_truth()
        ocr = compact(store.read_text("ocr", form["id"]))
        predicted = (
            Record.model_validate(store.read_json("structured", form["id"])["record"])
            if store.exists("structured", form["id"])
            else None
        )
        pairs = [
            (name, getattr(truth, name), getattr(predicted, name, None), "top")
            for name in TOP_LEVEL_FIELDS
        ]
        for side in VEHICLES:
            pv = getattr(predicted, side, None)
            pairs += [
                (
                    name,
                    getattr(getattr(truth, side), name),
                    getattr(pv, name, None),
                    side,
                )
                for name in VEHICLE_FIELDS
            ]
        for name, expected, got, where in pairs:
            kind = FIELD_KINDS[name]
            if kind not in TEXT:
                continue
            group = (
                f"{'critical' if kind is FieldKind.CRITICAL_TEXT else 'minor'}/{where}"
            )
            if got is not None and normalize(got) == normalize(expected):
                outcome = "correct"
            elif compact(str(expected)) not in ocr:
                outcome = "value not in the OCR text"
            elif got is None:
                outcome = "in the OCR text, no value returned"
            else:
                outcome = "in the OCR text, wrong value returned"
            counts[group][outcome] += 1
    report = {group: dict(c) for group, c in sorted(counts.items())}
    (run_dir / "failures.json").write_text(json.dumps(report, indent=2))
    for group, c in report.items():
        total = sum(c.values())
        print(
            f"{group:20} ({total} fields): "
            + "; ".join(f"{k} {v}" for k, v in sorted(c.items(), key=lambda kv: -kv[1]))
        )


if __name__ == "__main__":
    main(sys.argv[1])
