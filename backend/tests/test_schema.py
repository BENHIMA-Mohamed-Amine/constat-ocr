"""The schema and the data generator agree. Run from backend/: uv run python -m tests.test_schema"""

import random
from typing import get_args

from generator import data, fields
from generator.data import sample_record
from pipeline.schema import ImpactZone, LicenseCategory, Record, Vehicle, VehicleType


def check_record(seed: int) -> None:
    truth = sample_record(random.Random(seed))
    record = Record.model_validate(
        truth
    )  # raises if a value has the wrong type or an unknown choice
    assert record.vehicle_a is not None and record.vehicle_b is not None, seed
    assert set(truth) - {"sketch"} == set(Record.model_fields), (
        f"top-level fields differ (seed {seed})"
    )
    for side in ("vehicle_a", "vehicle_b"):
        assert set(truth[side]) == set(Vehicle.model_fields), (
            f"{side} fields differ (seed {seed})"
        )


def check_choices() -> None:
    """The choices the schema allows are exactly the ones the generator can produce."""
    assert set(get_args(VehicleType)) == set(data.VEHICLE_TYPES)
    assert set(get_args(ImpactZone)) == set(data.ZONE_DIR)
    assert set(get_args(LicenseCategory)) == set(fields.CATEGORIES)


if __name__ == "__main__":
    for seed in range(300):
        check_record(seed)
    check_choices()
    print("ok: 300 generated records validate; schema and generator agree")
