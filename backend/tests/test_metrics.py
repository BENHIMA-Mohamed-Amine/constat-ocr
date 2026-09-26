"""The scorer and the six metrics give the expected numbers on hand-made cases.
Run from backend/: uv run python -m tests.test_metrics"""

import random

from generator.data import sample_record
from pipeline.evaluation import FormScorer, Usage, build_default_evaluator
from pipeline.evaluation.fields import FIELD_KINDS, TOP_LEVEL_FIELDS, VEHICLE_FIELDS
from pipeline.evaluation.normalize import normalize
from pipeline.schema import Record

SCORER = FormScorer()
EVALUATOR = build_default_evaluator(
    input_price_per_million=0.15, output_price_per_million=0.60
)


def truth(seed: int = 0, **vehicle_a) -> Record:
    """A generated record, with some fields of vehicle A overridden."""
    base = Record.model_validate(sample_record(random.Random(seed)))
    return (
        base.model_copy(
            update={"vehicle_a": base.vehicle_a.model_copy(update=vehicle_a)}
        )
        if vehicle_a
        else base
    )


def summary(
    pairs: list[tuple[Record | None, Record]], usages: list[Usage | None] | None = None
) -> dict:
    results = [
        SCORER.score(str(i), pred, true, (usages or [None] * len(pairs))[i])
        for i, (pred, true) in enumerate(pairs)
    ]
    return EVALUATOR.summarize(results)


def test_every_field_is_classified() -> None:
    assert set(FIELD_KINDS) == set(TOP_LEVEL_FIELDS) | set(VEHICLE_FIELDS)


def test_normalize() -> None:
    assert normalize("  Rue   TARFAYA ") == normalize("rue tarfaya")
    assert normalize(True) == "true" and normalize(False) == "false"
    assert normalize("41654-A-55") != normalize(
        "41654-A-56"
    )  # no forgiveness for one wrong character


def test_perfect_prediction() -> None:
    record = truth()
    s = summary([(record, record)])
    assert (
        s["field_accuracy"]["critical"]["accuracy"] == 1.0
        and s["field_accuracy"]["minor"]["accuracy"] == 1.0
    )
    assert s["forms_without_critical_error"]["share"] == 1.0
    assert s["character_error_rate"]["overall"]["rate"] == 0.0
    assert (
        s["checkbox_score"]["ticks_missed"] == 0
        and s["checkbox_score"]["ticks_extra"] == 0
    )
    assert all(v["accuracy"] == 1.0 for v in s["category_accuracy"].values())


def test_one_wrong_digit() -> None:
    record = truth()
    plate = record.vehicle_a.plate
    wrong = record.model_copy(
        update={
            "vehicle_a": record.vehicle_a.model_copy(
                update={"plate": plate[:-1] + ("0" if plate[-1] != "0" else "1")}
            )
        }
    )
    s = summary([(wrong, record)])
    critical = s["field_accuracy"]["critical"]
    assert critical["correct"] == critical["total"] - 1
    assert (
        s["character_error_rate"]["overall"]["edits"] == 1
    )  # exactly one character differs
    assert s["forms_without_critical_error"]["without_critical_error"] == 0
    assert (
        s["field_accuracy"]["per_field"]["plate"]["correct"] == 1
        and s["field_accuracy"]["per_field"]["plate"]["total"] == 2
    )


def test_no_output_counts_everything_wrong() -> None:
    record = truth()
    s = summary([(None, record)])
    assert s["forms_with_output"] == 0
    assert (
        s["field_accuracy"]["critical"]["correct"] == 0
        and s["field_accuracy"]["minor"]["correct"] == 0
    )
    assert (
        s["character_error_rate"]["overall"]["rate"] == 1.0
    )  # every character missing
    assert (
        s["checkbox_score"]["ticks_found"] == 0
        and s["checkbox_score"]["ticks_extra"] == 0
    )
    assert s["forms_without_critical_error"]["without_critical_error"] == 0


def test_checkboxes_found_missed_extra() -> None:
    record = truth(circumstances=[8, 10], circumstance_count=2)
    record = record.model_copy(
        update={
            "vehicle_b": record.vehicle_b.model_copy(
                update={"circumstances": [], "circumstance_count": 0}
            )
        }
    )
    guess = record.model_copy(
        update={
            "vehicle_a": record.vehicle_a.model_copy(update={"circumstances": [8, 11]})
        }
    )
    box = summary([(guess, record)])["checkbox_score"]
    assert (box["ticks_found"], box["ticks_missed"], box["ticks_extra"]) == (1, 1, 1)
    assert box["precision"] == 0.5 and box["recall"] == 0.5
    assert box["tick_count_correct"] == 2 and box["tick_count_total"] == 2


def test_category_accuracy_next_to_the_guessing_baseline() -> None:
    pairs = []
    for i, kind in enumerate(["car", "car", "car", "moto"]):
        record = truth(seed=i, vehicle_type=kind)
        record = record.model_copy(
            update={
                "vehicle_b": record.vehicle_b.model_copy(update={"vehicle_type": "car"})
            }
        )
        guess = record.model_copy(
            update={
                "vehicle_a": record.vehicle_a.model_copy(update={"vehicle_type": "car"})
            }
        )
        pairs.append((guess, record))
    vehicle_type = summary(pairs)["category_accuracy"]["vehicle_type"]
    assert vehicle_type["total"] == 8 and vehicle_type["correct"] == 7
    assert (
        vehicle_type["most_common_answer"] == "car"
        and vehicle_type["guess_most_common_accuracy"] == 7 / 8
    )


def test_cost_and_time() -> None:
    record = truth()
    usages = [Usage(1.0, 2.0, 1000, 200), Usage(1.0, 9.0, 3000, 800)]
    cost = summary([(record, record)] * 2, usages)["cost_and_time"]
    assert abs(cost["dollars_per_form"] - 0.0006) < 1e-9  # (0.00027 + 0.00093) / 2
    assert cost["seconds_p95"] == 10.0 and cost["forms_measured"] == 2


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"ok: {len(tests)} metric checks pass")
