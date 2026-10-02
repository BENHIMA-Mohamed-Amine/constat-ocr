"""Unit (1 test): the per-field scorer and the six ``docs/metrics.md`` metrics.

One pytest item made of 8 named sub-checks, each a hand-built prediction/answer-key pair whose
correct score is known by construction (not generated), so a failing sub-check points to a bug in
the scoring math itself, independent of any LLM output.
"""

import random

from generator.data import sample_record
from pipeline.core.schema import Record
from pipeline.evaluation import FormScorer, Usage, build_default_evaluator
from pipeline.evaluation.fields import FIELD_KINDS, TOP_LEVEL_FIELDS, VEHICLE_FIELDS
from pipeline.evaluation.normalize import normalize

from ..checks import run_checks

SCORER = FormScorer()
EVALUATOR = build_default_evaluator(
    input_price_per_million=0.15, output_price_per_million=0.60
)


def _truth(seed: int = 0, **vehicle_a: object) -> Record:
    """A generated record, with some fields of vehicle A overridden.

    Args:
        seed: Generator seed for the base record.
        **vehicle_a: Fields to override on ``vehicle_a`` (e.g. ``circumstances=[8, 10]``).

    Returns:
        The base record, or a copy with vehicle A's overrides applied.
    """
    base = Record.model_validate(sample_record(random.Random(seed)))
    if not vehicle_a:
        return base
    return base.model_copy(
        update={"vehicle_a": base.vehicle_a.model_copy(update=vehicle_a)}
    )


def _summary(
    pairs: list[tuple[Record | None, Record]], usages: list[Usage | None] | None = None
) -> dict:
    """Score each (prediction, truth) pair and return the aggregated metrics.

    Args:
        pairs: (predicted record or None, answer-key record) pairs, one per fake "form".
        usages: One :class:`Usage` per pair, or None to record no usage.

    Returns:
        The dict :meth:`Evaluator.summarize` returns for these forms.
    """
    results = [
        SCORER.score(str(i), pred, true, (usages or [None] * len(pairs))[i])
        for i, (pred, true) in enumerate(pairs)
    ]
    return EVALUATOR.summarize(results)


def _every_field_is_classified() -> None:
    """Every field of ``Record``/``Vehicle`` has an entry in ``FIELD_KINDS``.

    A field with no entry would be silently skipped by every metric — present in the schema and
    the answer key, but never scored.
    """
    assert set(FIELD_KINDS) == set(TOP_LEVEL_FIELDS) | set(VEHICLE_FIELDS)


def _normalize_rule() -> None:
    """``normalize`` trims/collapses whitespace and lowercases, but forgives nothing else.

    Two values that differ only in one character (e.g. the last digit of a plate) must still
    compare as different: the project's fixed rule (docs/metrics.md) is no partial credit for
    single-character confusions such as 0/O or 1/7.
    """
    assert normalize("  Rue   TARFAYA ") == normalize("rue tarfaya")
    assert normalize(True) == "true"
    assert normalize(False) == "false"
    assert normalize("41654-A-55") != normalize("41654-A-56")


def _perfect_prediction() -> None:
    """A prediction identical to the answer key scores 100% on every metric that has an accuracy."""
    record = _truth()
    s = _summary([(record, record)])
    assert s["field_accuracy"]["critical"]["accuracy"] == 1.0
    assert s["field_accuracy"]["minor"]["accuracy"] == 1.0
    assert s["forms_without_critical_error"]["share"] == 1.0
    assert s["character_error_rate"]["overall"]["rate"] == 0.0
    assert s["checkbox_score"]["ticks_missed"] == 0
    assert s["checkbox_score"]["ticks_extra"] == 0
    assert all(v["accuracy"] == 1.0 for v in s["category_accuracy"].values())


def _one_wrong_digit() -> None:
    """One wrong character in a critical field costs exactly one field and one character edit.

    Checks that character error rate gives partial credit (edit distance 1, not "totally wrong")
    while field accuracy and "forms without critical error" still treat it as a failed field/form,
    per the project's fixed rule: exact match only, no forgiveness for a single wrong character.
    """
    record = _truth()
    plate = record.vehicle_a.plate
    flipped = plate[:-1] + ("0" if plate[-1] != "0" else "1")
    wrong = record.model_copy(
        update={"vehicle_a": record.vehicle_a.model_copy(update={"plate": flipped})}
    )
    s = _summary([(wrong, record)])
    critical = s["field_accuracy"]["critical"]
    assert critical["correct"] == critical["total"] - 1
    assert s["character_error_rate"]["overall"]["edits"] == 1
    assert s["forms_without_critical_error"]["without_critical_error"] == 0
    assert s["field_accuracy"]["per_field"]["plate"]["correct"] == 1
    assert s["field_accuracy"]["per_field"]["plate"]["total"] == 2


def _no_output_counts_everything_wrong() -> None:
    """A ``None`` prediction (the pipeline produced nothing) scores as if every field were missing.

    Character error rate must be 1.0 (100% of characters missing), not undefined or 0; every
    field-accuracy count must be zero correct; no ticks are "found", but none are wrongly "extra"
    either, since nothing was returned at all.
    """
    record = _truth()
    s = _summary([(None, record)])
    assert s["forms_with_output"] == 0
    assert s["field_accuracy"]["critical"]["correct"] == 0
    assert s["field_accuracy"]["minor"]["correct"] == 0
    assert s["character_error_rate"]["overall"]["rate"] == 1.0
    assert s["checkbox_score"]["ticks_found"] == 0
    assert s["checkbox_score"]["ticks_extra"] == 0
    assert s["forms_without_critical_error"]["without_critical_error"] == 0


def _checkboxes_found_missed_extra() -> None:
    """The checkbox metric separately counts ticks found, missed and extra, per vehicle.

    Truth: vehicle A ticked 8 and 10, vehicle B ticked none. Prediction: vehicle A ticked 8 and 11.
    Expected: tick 8 is found, tick 10 is missed, tick 11 is extra — precision and recall must
    both come out to 1 found / 2 total = 0.5, and the two tick-count boxes (2 and 0) are correct
    because the prediction leaves vehicle B's circumstances untouched from the truth used here.
    """
    record = _truth(circumstances=[8, 10], circumstance_count=2)
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
    box = _summary([(guess, record)])["checkbox_score"]
    assert (box["ticks_found"], box["ticks_missed"], box["ticks_extra"]) == (1, 1, 1)
    assert box["precision"] == 0.5
    assert box["recall"] == 0.5
    assert box["tick_count_correct"] == 2
    assert box["tick_count_total"] == 2


def _category_accuracy_next_to_the_guessing_baseline() -> None:
    """Category accuracy is reported alongside the score of always guessing the most common value.

    3 of 4 forms have vehicle type "car" on both vehicles and are predicted perfectly; the 4th has
    vehicle A as "moto" and is predicted (wrongly) as "car". So 7 of 8 vehicle-type slots are
    correct, and "always answer car" would also score 7/8 here — the two numbers must match
    exactly, since a system that always guesses "car" and this particular predictor happen to
    agree on every slot in this fixture.
    """
    pairs = []
    for i, kind in enumerate(["car", "car", "car", "moto"]):
        record = _truth(seed=i, vehicle_type=kind)
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
    vehicle_type = _summary(pairs)["category_accuracy"]["vehicle_type"]
    assert vehicle_type["total"] == 8
    assert vehicle_type["correct"] == 7
    assert vehicle_type["most_common_answer"] == "car"
    assert vehicle_type["guess_most_common_accuracy"] == 7 / 8


def _cost_and_time() -> None:
    """Cost is a token-weighted average in dollars, and p95 time is the slower of two forms.

    Two forms cost (1000*0.15 + 200*0.60)/1e6 = 0.00027 and (3000*0.15 + 800*0.60)/1e6 = 0.00093
    dollars; their mean is 0.0006. With only two samples, the 95th-percentile time is the larger
    of the two totals (1+9=10s), not an interpolated value.
    """
    record = _truth()
    usages = [Usage(1.0, 2.0, 1000, 200), Usage(1.0, 9.0, 3000, 800)]
    cost = _summary([(record, record)] * 2, usages)["cost_and_time"]
    assert abs(cost["dollars_per_form"] - 0.0006) < 1e-9
    assert cost["seconds_p95"] == 10.0
    assert cost["forms_measured"] == 2


def test_scorer_and_metrics_compute_correctly() -> None:
    """The scorer and all six metrics give the expected numbers on 8 hand-built cases.

    See the module docstring: runs the 8 named sub-checks and reports every one that fails.
    """
    run_checks(
        [
            ("every_field_is_classified", _every_field_is_classified),
            ("normalize_rule", _normalize_rule),
            ("perfect_prediction", _perfect_prediction),
            ("one_wrong_digit", _one_wrong_digit),
            ("no_output_counts_everything_wrong", _no_output_counts_everything_wrong),
            ("checkboxes_found_missed_extra", _checkboxes_found_missed_extra),
            (
                "category_accuracy_next_to_the_guessing_baseline",
                _category_accuracy_next_to_the_guessing_baseline,
            ),
            ("cost_and_time", _cost_and_time),
        ]
    )
