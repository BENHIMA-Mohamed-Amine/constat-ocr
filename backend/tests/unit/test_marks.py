"""Unit (1 test): reading the marks (ticks, tiles, circles, patch, OUI/NON) from template positions, on forms the test renders itself.

One pytest item made of 3 named sub-checks. No dataset, model or network: two clean forms are rendered by the generator, and the
graph wiring runs with a fake structurer and a reader that returns known marks.
"""

import random
from pathlib import Path

from generator.data import sample_record
from generator.render import render
from pipeline.core.schema import Record
from pipeline.data.storage import FileArtifactStore
from pipeline.evaluation import FormScorer
from pipeline.flow.graph import build_graph
from pipeline.marks import Marks, MarksReader, VehicleMarks
from pipeline.structuring import StructuringResult

from ..checks import run_checks
from ..conftest import FakeOcrEngine, sample_truth

TEMPLATE = Path(__file__).resolve().parents[2] / "assets" / "constat-template.pdf"
TRUTH = sample_truth(3)


def _marks_of(record: Record) -> Marks:
    sides = [
        VehicleMarks(v.circumstances, v.vehicle_type, v.license_category, v.impact_zone)
        for v in (record.vehicle_a, record.vehicle_b)
    ]
    return Marks(sides[0], sides[1], record.other_damage)


def _reads_the_marks_of_rendered_forms(tmp_path: Path) -> None:
    """Every mark of two rendered forms is read back exactly: ticks, vehicle type, licence letter, impact zone, OUI or NON.

    The forms are drawn by the generator (a clean page, so the alignment on the template is the identity). At least one tick must be
    present across the two, or the tick check would pass on empty boxes.
    """
    reader, ticks = MarksReader(TEMPLATE), 0
    for seed in (4, 9):
        rng = random.Random(seed)
        record = sample_record(rng)
        page = tmp_path / f"{seed}.png"
        render(TEMPLATE, record, rng).save(page)
        marks = reader.read(page)
        truth = Record.model_validate(record)
        assert marks == _marks_of(truth), (seed, marks, _marks_of(truth))
        ticks += sum(len(v.circumstances) for v in (marks.vehicle_a, marks.vehicle_b))
    assert ticks > 0


def _marks_replace_the_record_fields() -> None:
    """The marks overwrite the five fields they give, the tick count is the number of ticks, and a missing vehicle is created.

    The text fields the LLM filled are left alone.
    """
    marks = _marks_of(TRUTH)
    wrong = TRUTH.model_copy(
        update={"other_damage": not TRUTH.other_damage, "vehicle_b": None}
    )
    fixed = marks.apply(wrong)
    assert fixed.other_damage == TRUTH.other_damage
    assert fixed.vehicle_b.circumstance_count == len(TRUTH.vehicle_b.circumstances)
    assert (
        fixed.vehicle_b.impact_zone == TRUTH.vehicle_b.impact_zone
        and fixed.vehicle_b.plate is None
    )
    assert fixed.vehicle_a.plate == TRUTH.vehicle_a.plate


class _BlankMarksStructurer:
    """Returns the truth with every mark field empty, as a text-only model would."""

    def structure(self, inputs) -> StructuringResult:
        blank = {
            "circumstances": [],
            "circumstance_count": 0,
            "vehicle_type": None,
            "license_category": None,
            "impact_zone": None,
        }
        record = TRUTH.model_copy(
            update={
                "other_damage": None,
                "vehicle_a": TRUTH.vehicle_a.model_copy(update=blank),
                "vehicle_b": TRUTH.vehicle_b.model_copy(update=blank),
            }
        )
        return StructuringResult(record, input_tokens=1, output_tokens=1, seconds=0.1)


class _KnownMarksReader:
    def read(self, image_path: Path) -> Marks:
        return _marks_of(TRUTH)


def _graph_scores_the_marks(tmp_path: Path) -> None:
    """With a marks reader the score sees its marks and they are saved; without one the mark fields are wrong.

    The structurer leaves every mark field empty. The vehicle type fields are wrong in the plain run and right in the run with the reader,
    and ``marks/<id>.json`` exists only in the second.
    """
    state = {"form_id": "000000", "image_path": "x.jpg", "truth": TRUTH}

    def vehicle_type_correct(reader: _KnownMarksReader | None, folder: str) -> bool:
        store = FileArtifactStore(tmp_path / folder)
        graph = build_graph(
            FakeOcrEngine(),
            _BlankMarksStructurer(),
            FormScorer(),
            store,
            marks_reader=reader,
        )
        result = graph.invoke(state)["result"]
        assert store.exists("marks", "000000") == (reader is not None)
        return next(
            f.correct for f in result.fields if f.path == "vehicle_a.vehicle_type"
        )

    assert not vehicle_type_correct(None, "plain")
    assert vehicle_type_correct(_KnownMarksReader(), "with-marks")


def test_marks(tmp_path: Path) -> None:
    """The marks of rendered forms are read exactly, they replace the record's fields, and the graph scores them."""
    run_checks(
        [
            (
                "reads_the_marks_of_rendered_forms",
                lambda: _reads_the_marks_of_rendered_forms(tmp_path),
            ),
            ("marks_replace_the_record_fields", _marks_replace_the_record_fields),
            ("graph_scores_the_marks", lambda: _graph_scores_the_marks(tmp_path)),
        ]
    )
