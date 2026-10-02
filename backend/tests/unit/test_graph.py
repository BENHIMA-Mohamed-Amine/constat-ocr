"""Unit (1 test): the LangGraph pipeline graph and runner, with fake OCR/structurer.

One pytest item made of 3 named sub-checks, none of which touches Tesseract or a network call.
Together they check the graph's *wiring*: state flows between nodes correctly, each step's output
is saved and reloadable, a failing form does not stop a run, and the graph behaves differently with
and without an answer key (evaluation vs. production use). A failure here means the graph itself is
broken, not that a specific OCR or LLM call went wrong.
"""

from pathlib import Path

from pipeline.data.dataset import FormRef
from pipeline.data.storage import FileArtifactStore
from pipeline.evaluation import FormScorer, build_default_evaluator
from pipeline.flow.graph import build_graph
from pipeline.flow.runner import PipelineRunner

from ..checks import run_checks
from ..conftest import FakeOcrEngine, FakeStructurer, sample_truth

TRUTH = sample_truth(3)


def _make_form(root: Path) -> FormRef:
    """Write ``TRUTH`` as an answer-key file and return a :class:`FormRef` pointing at it."""
    (root / "truth.json").write_text(TRUTH.model_dump_json())
    return FormRef("000000", "dev", root / "image.jpg", root / "truth.json")


def _runs_saves_and_scores(
    ocr: FakeOcrEngine, structurer: FakeStructurer, store: FileArtifactStore
) -> None:
    """With an answer key, the graph runs ocr -> structure -> evaluate and saves every step.

    Checks: the returned :class:`FormResult` reflects the fake structurer's known one-field error
    (vehicle A's plate) and the fake OCR/LLM usage numbers; all four step outputs (``ocr``,
    ``ocr_usage``, ``structured``, ``evaluation``) exist in the artifact store afterwards; and,
    separately, that *without* an answer key the graph stops after ``structure`` and returns a
    record but no ``result`` — this is how the graph is meant to run in production, where there is
    no ground truth to evaluate against.
    """
    graph = build_graph(ocr, structurer, FormScorer(), store)
    state = graph.invoke({"form_id": "000000", "image_path": "x.jpg", "truth": TRUTH})
    result = state["result"]
    assert result.produced_output
    assert result.usage.total_seconds == 2.0
    assert result.usage.input_tokens == 100
    assert sum(not f.correct for f in result.fields if f.path == "vehicle_a.plate") == 1
    assert all(
        store.exists(step, "000000")
        for step in ("ocr", "ocr_usage", "structured", "evaluation")
    )

    state = graph.invoke({"form_id": "000001", "image_path": "x.jpg"})
    assert "record" in state
    assert "result" not in state


def _reuse_skips_finished_steps(
    ocr: FakeOcrEngine, structurer: FakeStructurer, store: FileArtifactStore
) -> None:
    """``reuse=True`` loads a step's saved output instead of calling the engine/structurer again.

    Runs the same form through the graph twice, the second time with ``reuse=True``. The OCR and
    structurer fakes must each be called exactly once in total (not twice), proving the second run
    read from disk, and the reloaded result's timings must match the first run's, proving the
    saved usage numbers (not fresh zeros) were restored.
    """
    first = {"form_id": "000000", "image_path": "x.jpg", "truth": TRUTH}
    build_graph(ocr, structurer, FormScorer(), store).invoke(first)
    state = build_graph(ocr, structurer, FormScorer(), store, reuse=True).invoke(first)
    assert ocr.calls == 1, "a saved OCR step was run again"
    assert structurer.calls == 1, "a saved structuring step was run again"
    assert state["result"].usage.total_seconds == 2.0, "saved timings were not reloaded"


def _runner_survives_a_failing_form(store: FileArtifactStore, tmp_path: Path) -> None:
    """A ``StructuringError`` on one form is recorded and scored as "no output"; the run continues.

    Uses a structurer forced to fail. The runner must still return a summary covering the one
    form (not raise), score it as if the pipeline produced nothing (0 correct fields, 0 forms
    without a critical error), and save an ``errors/000000.json`` artifact naming the exception
    type, so a batch of many forms is not aborted by a single bad one.
    """
    scorer = FormScorer()
    failing_structurer = FakeStructurer(TRUTH, fail=True)
    graph = build_graph(FakeOcrEngine(), failing_structurer, scorer, store)
    summary = PipelineRunner(
        graph, scorer, build_default_evaluator(0.15, 0.60), store
    ).run("t", [_make_form(tmp_path)])
    assert summary["forms"] == 1
    assert summary["forms_with_output"] == 0
    assert summary["field_accuracy"]["critical"]["correct"] == 0
    assert store.read_json("errors", "000000")["type"] == "StructuringError"


def test_graph_is_wired_correctly(
    fake_ocr_engine: FakeOcrEngine,
    fake_structurer: FakeStructurer,
    tmp_run_dir: FileArtifactStore,
    tmp_path: Path,
) -> None:
    """The graph saves every step, reuses finished ones, and survives a failing form.

    See the module docstring: runs 3 named sub-checks and reports every one that fails. Each
    sub-check gets its own fresh fake OCR/structurer/store so they don't interfere with each
    other's call counts or saved artifacts.
    """
    run_checks(
        [
            (
                "runs_saves_and_scores",
                lambda: _runs_saves_and_scores(
                    fake_ocr_engine, fake_structurer, tmp_run_dir
                ),
            ),
            (
                "reuse_skips_finished_steps",
                lambda: _reuse_skips_finished_steps(
                    FakeOcrEngine(),
                    FakeStructurer(TRUTH),
                    FileArtifactStore(tmp_path / "reuse"),
                ),
            ),
            (
                "runner_survives_a_failing_form",
                lambda: _runner_survives_a_failing_form(
                    FileArtifactStore(tmp_path / "fail"), tmp_path
                ),
            ),
        ]
    )
