"""The graph and the runner work with fake parts: no Tesseract, no network.
Run from backend/: uv run python -m tests.test_graph"""
import random
import tempfile
from pathlib import Path

from generator.data import sample_record
from pipeline.dataset import FormRef
from pipeline.errors import StructuringError
from pipeline.evaluation import FormScorer, build_default_evaluator
from pipeline.graph import build_graph
from pipeline.ocr import OcrResult
from pipeline.runner import PipelineRunner
from pipeline.schema import Record
from pipeline.storage import FileArtifactStore
from pipeline.structuring import StructuringInput, StructuringResult

TRUTH = Record.model_validate(sample_record(random.Random(3)))


class FakeOcr:
    def __init__(self) -> None:
        self.calls = 0

    def read(self, image_path: Path) -> OcrResult:
        self.calls += 1
        return OcrResult("some text", 0.5)


class FakeStructurer:
    """Returns the answer key with vehicle A's plate changed by one character, or fails on demand."""

    def __init__(self, fail: bool = False) -> None:
        self.fail, self.calls = fail, 0

    def structure(self, inputs: StructuringInput) -> StructuringResult:
        self.calls += 1
        if self.fail:
            raise StructuringError("model down", form_id=inputs.form_id)
        plate = TRUTH.vehicle_a.plate
        record = TRUTH.model_copy(update={"vehicle_a": TRUTH.vehicle_a.model_copy(update={"plate": plate[:-1] + ("0" if plate[-1] != "0" else "1")})})
        return StructuringResult(record, 100, 50, 1.5)


def make_form(root: Path) -> FormRef:
    (root / "truth.json").write_text(TRUTH.model_dump_json())
    return FormRef("000000", "dev", root / "image.jpg", root / "truth.json")


def test_graph_runs_saves_and_scores() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root, store = Path(tmp), FileArtifactStore(Path(tmp) / "run")
        ocr, structurer = FakeOcr(), FakeStructurer()
        graph = build_graph(ocr, structurer, FormScorer(), store)
        state = graph.invoke({"form_id": "000000", "image_path": "x.jpg", "truth": TRUTH})
        result = state["result"]
        assert result.produced_output and result.usage.total_seconds == 2.0 and result.usage.input_tokens == 100
        assert sum(not f.correct for f in result.fields if f.path == "vehicle_a.plate") == 1
        assert all(store.exists(step, "000000") for step in ("ocr", "ocr_usage", "structured", "evaluation"))
        # without an answer key the graph stops after structuring (production use)
        state = graph.invoke({"form_id": "000001", "image_path": "x.jpg"})
        assert "record" in state and "result" not in state


def test_reuse_skips_finished_steps() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = FileArtifactStore(Path(tmp))
        ocr, structurer = FakeOcr(), FakeStructurer()
        first = {"form_id": "000000", "image_path": "x.jpg", "truth": TRUTH}
        build_graph(ocr, structurer, FormScorer(), store).invoke(first)
        state = build_graph(ocr, structurer, FormScorer(), store, reuse=True).invoke(first)
        assert (ocr.calls, structurer.calls) == (1, 1), "a saved step was run again"
        assert state["result"].usage.total_seconds == 2.0, "saved timings were not reloaded"


def test_runner_survives_a_failing_form() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root, store = Path(tmp), FileArtifactStore(Path(tmp) / "run")
        scorer = FormScorer()
        graph = build_graph(FakeOcr(), FakeStructurer(fail=True), scorer, store)
        summary = PipelineRunner(graph, scorer, build_default_evaluator(0.15, 0.60), store).run("t", [make_form(root)])
        assert summary["forms"] == 1 and summary["forms_with_output"] == 0
        assert summary["field_accuracy"]["critical"]["correct"] == 0
        assert store.read_json("errors", "000000")["type"] == "StructuringError"


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"ok: {len(tests)} graph checks pass")
