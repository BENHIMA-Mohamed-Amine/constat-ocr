"""Regression (1 test): the synthetic-data generator's records stay internally consistent.

One pytest item — "the generator produces internally consistent records" — made of 8 named
sub-checks, each looped over 300 seeds. Kept as separate private functions for readability and to
name the exact property that broke, but run together through ``run_checks`` so pytest reports this
as the single capability it is, not 8 unrelated items.
"""

import math
from datetime import datetime
from random import Random

from generator.data import LANE_Y, STEM_DX, _contact, _fits, sample_record

from ..checks import run_checks

SEEDS = range(300)


def _day(value: str) -> datetime:
    """Parse a dd/mm/yyyy date string as written by the generator."""
    return datetime.strptime(value, "%d/%m/%Y")


def _angle_offset(heading: float, target: float) -> float:
    """Smallest angle between ``heading`` and ``target``, in degrees, both mod 360."""
    return min(abs((heading - target) % 360), abs((target - heading) % 360))


def _records() -> list[tuple[int, dict]]:
    """A generated record for every seed in ``SEEDS``, paired with its seed for error messages."""
    return [(seed, sample_record(Random(seed))) for seed in SEEDS]


def _tick_count_matches_circumstances() -> None:
    """``circumstance_count`` always equals ``len(circumstances)``, for both vehicles.

    The checkbox metric (docs/metrics.md) reads the written count as a cross-check against the
    ticks it detects; if the generator itself could produce a mismatch, that check would be
    validating against bad ground truth.
    """
    for seed, record in _records():
        for side in ("a", "b"):
            vehicle = record[f"vehicle_{side}"]
            assert vehicle["circumstance_count"] == len(vehicle["circumstances"]), (
                f"seed {seed}, vehicle {side}"
            )


def _attestation_covers_accident_date() -> None:
    """Each vehicle's insurance attestation is valid on the day of the accident.

    A generated form where the accident falls outside the insurance's stated validity window
    would be an internally contradictory piece of ground truth.
    """
    for seed, record in _records():
        accident = _day(record["date"])
        for side in ("a", "b"):
            vehicle = record[f"vehicle_{side}"]
            assert (
                _day(vehicle["valid_from"]) <= accident <= _day(vehicle["valid_to"])
            ), f"seed {seed}, vehicle {side}"


def _licence_valid_on_accident_date() -> None:
    """Each driver's licence was issued before, and had not expired by, the accident date."""
    for seed, record in _records():
        accident = _day(record["date"])
        for side in ("a", "b"):
            vehicle = record[f"vehicle_{side}"]
            assert (
                _day(vehicle["license_issued"])
                < accident
                <= _day(vehicle["license_valid_until"])
            ), f"seed {seed}, vehicle {side}"


def _plates_differ() -> None:
    """Vehicle A and vehicle B never share a registration plate."""
    for seed, record in _records():
        assert record["vehicle_a"]["plate"] != record["vehicle_b"]["plate"], (
            f"seed {seed}"
        )


def _sketch_contact_points_touch() -> None:
    """The damaged zone drawn for A and the one drawn for B meet at (nearly) the same point.

    The sketch is built so that A's impact zone and B's impact zone touch (see ``sample_sketch``
    in ``generator/data.py``); a large gap would mean the two cars are drawn not actually
    colliding where the ticked circumstances say they should.
    """
    for seed, record in _records():
        a, b = record["sketch"]["a"], record["sketch"]["b"]
        (pax, pay), _ = _contact(record["vehicle_a"]["impact_zone"], a["heading"])
        (pbx, pby), _ = _contact(record["vehicle_b"]["impact_zone"], b["heading"])
        gap = math.hypot(a["x"] + pax - (b["x"] + pbx), a["y"] + pay - (b["y"] + pby))
        assert gap < 3, f"seed {seed}, gap {gap}"


def _cars_fit_the_canvas() -> None:
    """Both sketched cars lie fully inside the drawable sketch canvas, at their drawn heading."""
    for seed, record in _records():
        a, b = record["sketch"]["a"], record["sketch"]["b"]
        assert _fits(a["x"], a["y"], a["heading"]), f"seed {seed}, vehicle a"
        assert _fits(b["x"], b["y"], b["heading"]), f"seed {seed}, vehicle b"


def _lane_matches_heading() -> None:
    """Vehicle A is drawn in the road lane that matches the direction it is heading.

    Right-hand traffic: a car heading right (0 deg) belongs in the lane at ``LANE_Y[0]``, a car
    heading left (180 deg) in the lane at ``LANE_Y[180]``. A's drawn Y position must match its own
    heading's lane, within a small tolerance.
    """
    for seed, record in _records():
        a = record["sketch"]["a"]
        lane = 0 if _angle_offset(a["heading"], 0) < 10 else 180
        assert _angle_offset(a["heading"], lane) < 10, f"seed {seed}"
        assert abs(a["y"] - LANE_Y[lane]) < 4, f"seed {seed}"


def _t_junction_geometry_is_consistent() -> None:
    """On a T-junction, B comes from the side road, in the lane matching its own heading.

    On a two-way road, there is no junction and B is heading roughly along the same road as A
    (not perpendicular to it). On a T-junction, B is heading roughly north or south (into or out
    of the side road), the junction's recorded ``side`` matches that direction, and B's X position
    sits in that direction's lane of the side road (``STEM_DX``).
    """
    for seed, record in _records():
        sketch = record["sketch"]
        b = sketch["b"]
        if sketch["layout"] == "two_way":
            assert sketch["junction"] is None, f"seed {seed}"
            assert (
                min(_angle_offset(b["heading"], 0), _angle_offset(b["heading"], 180))
                < 55
            ), f"seed {seed}"
        else:
            direction = (
                90
                if _angle_offset(b["heading"], 90) < _angle_offset(b["heading"], 270)
                else 270
            )
            assert _angle_offset(b["heading"], direction) < 55, f"seed {seed}"
            assert sketch["junction"]["side"] == (
                "north" if direction == 90 else "south"
            ), f"seed {seed}"
            assert abs(b["x"] - (sketch["junction"]["x"] + STEM_DX[direction])) < 1, (
                f"seed {seed}"
            )


def test_generator_produces_internally_consistent_records() -> None:
    """The generator's 300-seed records satisfy every consistency rule the form implies.

    See the module docstring: this runs 8 named sub-checks (tick counts, insurance/licence date
    rules, distinct plates, sketch/impact-zone/lane/junction geometry) and reports every one that
    fails, not just the first.
    """
    run_checks(
        [
            ("tick_count_matches_circumstances", _tick_count_matches_circumstances),
            ("attestation_covers_accident_date", _attestation_covers_accident_date),
            ("licence_valid_on_accident_date", _licence_valid_on_accident_date),
            ("plates_differ", _plates_differ),
            ("sketch_contact_points_touch", _sketch_contact_points_touch),
            ("cars_fit_the_canvas", _cars_fit_the_canvas),
            ("lane_matches_heading", _lane_matches_heading),
            ("t_junction_geometry_is_consistent", _t_junction_geometry_is_consistent),
        ]
    )
