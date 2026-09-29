"""Unit (1 test): agreement between the Pydantic ``Record`` schema and the data generator.

One pytest item made of 3 named sub-checks. The generator and the schema are two independent
descriptions of the same form; these catch the case where one is updated (a field renamed, a
choice added) and the other is not.
"""

import random
from typing import get_args

from generator import data, fields
from generator.data import sample_record
from pipeline.schema import ImpactZone, LicenseCategory, Record, Vehicle, VehicleType

from ..checks import run_checks

SEEDS = range(300)


def _generated_records_validate_against_schema() -> None:
    """Every one of 300 generator answer keys parses into ``Record`` with no validation error.

    ``Record.model_validate`` raises if a value has the wrong Python type or, for a ``Literal``
    field (vehicle type, impact zone, licence category), a value the schema does not list as a
    choice. This is what the structuring step relies on: the LLM is asked to produce exactly this
    shape, so if the generator's own answer keys did not validate, the schema would not describe
    the real form.
    """
    for seed in SEEDS:
        truth = sample_record(random.Random(seed))
        record = Record.model_validate(truth)
        assert record.vehicle_a is not None and record.vehicle_b is not None, (
            f"seed {seed}"
        )


def _generator_and_schema_agree_on_field_names() -> None:
    """The keys the generator writes are exactly the fields ``Record``/``Vehicle`` define.

    A field present in one but not the other would mean either the schema silently drops a value
    the generator produces, or the LLM is asked for a field the generator (and so the evaluator's
    answer key) never fills in. Checked across 300 seeds since a field can be conditionally absent.
    """
    for seed in SEEDS:
        truth = sample_record(random.Random(seed))
        assert set(truth) - {"sketch"} == set(Record.model_fields), f"seed {seed}"
        for side in ("vehicle_a", "vehicle_b"):
            assert set(truth[side]) == set(Vehicle.model_fields), f"seed {seed}, {side}"


def _schema_and_generator_choices_match() -> None:
    """The ``Literal`` choices the schema allows are exactly the ones the generator can produce.

    If the schema allowed a value the generator never emits, the LLM would never need to use it
    but the prompt (generated from the schema, see ``pipeline/structuring/output_format.py``)
    would still advertise it as valid. If the generator could emit a value the schema does not
    list, generated records would fail the validation sub-check above.
    """
    assert set(get_args(VehicleType)) == set(data.VEHICLE_TYPES)
    assert set(get_args(ImpactZone)) == set(data.ZONE_DIR)
    assert set(get_args(LicenseCategory)) == set(fields.CATEGORIES)


def test_schema_and_generator_agree() -> None:
    """The record schema and the data generator describe the same form, in every respect checked.

    See the module docstring: runs 3 named sub-checks and reports every one that fails.
    """
    run_checks(
        [
            (
                "generated_records_validate_against_schema",
                _generated_records_validate_against_schema,
            ),
            (
                "generator_and_schema_agree_on_field_names",
                _generator_and_schema_agree_on_field_names,
            ),
            ("schema_and_generator_choices_match", _schema_and_generator_choices_match),
        ]
    )
