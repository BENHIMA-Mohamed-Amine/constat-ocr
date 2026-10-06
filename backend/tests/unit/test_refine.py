"""Unit (1 test): the crop re-reader, with a fake server and the blank template as the page.

One pytest item made of 3 named sub-checks. No network and no model: the HTTP call is faked, so the checks cover where the crops are cut,
how the answer is merged into the record, and that a failure or an unreadable field never removes a value.
"""

import json
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest

from pipeline.core.config import BACKEND_DIR
from pipeline.core.errors import ConfigurationError
from pipeline.core.schema import Record, Vehicle
from pipeline.marks.layout import load_layout
from pipeline.refine import FieldRefiner

from ..checks import run_checks

TEMPLATE = BACKEND_DIR / "assets" / "constat-template.pdf"
FIELDS = ["plate", "policy_no"]


class _Reply:
    def __init__(self, answer: dict) -> None:
        self._answer = answer

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"choices": [{"message": {"content": json.dumps(self._answer)}}]}


def _crops_follow_the_template(refiner: FieldRefiner, page: Path) -> None:
    """Each crop is the template's field box plus the margin, enlarged, for both vehicles."""
    layout = load_layout(TEMPLATE)
    crops = refiner.crops(page)
    assert {v: list(c) for v, c in crops.items()} == {
        "vehicle_a": FIELDS,
        "vehicle_b": FIELDS,
    }
    for side, vehicle in enumerate(("vehicle_a", "vehicle_b")):
        x0, y0, x1, y1 = layout.text_fields["plate"][side]
        image = cv2.imdecode(
            np.frombuffer(crops[vehicle]["plate"], "uint8"),
            cv2.IMREAD_COLOR,
        )
        assert image.shape[:2] == ((y1 - y0 + 14) * 3, (x1 - x0 + 20) * 3)


def _merge_keeps_values_it_cannot_replace(
    refiner: FieldRefiner, page: Path, monkeypatch
) -> None:
    """A read value replaces the page value; null keeps it; a field not asked for is untouched."""
    record = Record(
        vehicle_a=Vehicle(plate="1-A-1", policy_no="123", make="Kia"),
        vehicle_b=Vehicle(plate="2-B-2"),
    )
    answer = {
        "vehicle_a": {"plate": "52033-D-39", "policy_no": None},
        "vehicle_b": {"plate": "14472-T-1", "policy_no": "729171160852"},
    }
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Reply(answer))
    result = refiner.refine(page, record)
    assert result.record.vehicle_a.plate == "52033-D-39"
    assert result.record.vehicle_a.policy_no == "123"
    assert result.record.vehicle_a.make == "Kia"
    assert result.record.vehicle_b.policy_no == "729171160852"
    assert sorted(c.path for c in result.changes) == [
        "vehicle_a.plate",
        "vehicle_b.plate",
        "vehicle_b.policy_no",
    ]


def _failure_and_bad_fields(refiner: FieldRefiner, page: Path, monkeypatch) -> None:
    """A failed call returns the record as it was; an unknown field name is refused at build time."""

    def boom(*args, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", boom)
    record = Record(vehicle_a=Vehicle(plate="1-A-1"))
    result = refiner.refine(page, record)
    assert result.record == record and result.changes == [] and result.failed
    with pytest.raises(ConfigurationError):
        FieldRefiner(TEMPLATE, "https://x.modal.run", ["not_a_field"])


def _header_and_damage(page: Path, monkeypatch) -> None:
    """Header fields get one crop each and are merged into the top level; damage is a vehicle field."""
    refiner = FieldRefiner(
        TEMPLATE, "https://x.modal.run", ["date", "phone_b", "damage"]
    )
    assert {g: list(c) for g, c in refiner.crops(page).items()} == {
        "header": ["date", "phone_b"],
        "vehicle_a": ["damage"],
        "vehicle_b": ["damage"],
    }
    answer = {
        "header": {"date": "29/06/2022", "phone_b": None},
        "vehicle_a": {"damage": "Pare choc arriere, coffre"},
        "vehicle_b": {"damage": None},
    }
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Reply(answer))
    record = Record(
        date="29/06/2021", phone_b="0709147381", vehicle_b=Vehicle(damage="x")
    )
    result = refiner.refine(page, record).record
    assert (result.date, result.phone_b) == ("29/06/2022", "0709147381")
    assert result.vehicle_a.damage == "Pare choc arriere, coffre"
    assert result.vehicle_b.damage == "x"


def test_refine(tmp_path: Path, monkeypatch) -> None:
    page = tmp_path / "page.png"
    cv2.imwrite(str(page), load_layout(TEMPLATE).template)
    refiner = FieldRefiner(
        TEMPLATE, "https://x.modal.run", FIELDS, auth_token="wk-1.ws-2", retry_delay=0
    )
    run_checks(
        [
            (
                "crops follow the template",
                lambda: _crops_follow_the_template(refiner, page),
            ),
            (
                "merge",
                lambda: _merge_keeps_values_it_cannot_replace(
                    refiner, page, monkeypatch
                ),
            ),
            (
                "failure and bad field",
                lambda: _failure_and_bad_fields(refiner, page, monkeypatch),
            ),
        ]
    )
