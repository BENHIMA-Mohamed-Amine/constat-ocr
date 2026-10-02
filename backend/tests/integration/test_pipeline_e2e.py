"""Integration: the real pipeline (real Tesseract, real Groq) runs end to end on 2 forms.

Answers "does the real pipeline still run at all?" — as opposed to
``regression/test_evaluation_regression.py``, which answers "if I feed the evaluator the exact
same LLM output as last time, do I get the exact same numbers as last time?" using frozen output
and no network. This test calls the real OCR engine and the real model, so its assertions stay
loose (the LLM's answers are not identical run to run): it checks that the pipeline *ran* and
*produced something usable*, not that any specific field came out right — exact values are judged
separately, by hand, when a version's results are recorded in ``docs/results-log.md``.

Capped at exactly the 2 dev forms, on purpose: each run costs a couple of real Groq calls (about
$0.002 based on the v1-dev run's actual usage) and a couple of minutes, so it must stay cheap
enough to run on every CI push that has the secret available.
"""

import json
import os
from pathlib import Path

import pytest

from pipeline.core.config import Settings
from pipeline.core.observability import configure_tracing
from pipeline.data.dataset import DatasetReader
from pipeline.data.storage import FileArtifactStore
from pipeline.evaluation import FormScorer, build_default_evaluator
from pipeline.flow.graph import build_graph
from pipeline.flow.runner import PipelineRunner, describe_run, write_run_files
from pipeline.ocr import LangChainTesseractEngine
from pipeline.structuring import LangChainStructurer, build_chat_model

pytestmark = pytest.mark.skipif(
    not os.environ.get("GROQ_API_KEY"), reason="needs a live GROQ_API_KEY"
)


def test_dev_forms_run_through_the_real_pipeline(tmp_path: Path) -> None:
    """The 2 dev forms go through OCR, structuring and evaluation, and the run's files are written.

    Checks, without asserting on any extracted value: exactly 2 results come back and both report
    that the pipeline produced a record; both forms used a non-zero number of input and output
    tokens (proof the Groq call actually ran, not that it was skipped or faked); and ``run.json``
    plus ``summary.json`` are written, parse as JSON, and ``run.json``'s dataset fingerprint
    matches what the dataset reader itself reports for the forms used.
    """
    settings = Settings()
    configure_tracing(settings)
    reader = DatasetReader(settings.dataset_dir)
    forms = reader.first("dev", 2)
    store = FileArtifactStore(tmp_path)
    scorer = FormScorer()
    graph = build_graph(
        LangChainTesseractEngine(settings.ocr_languages),
        LangChainStructurer(build_chat_model(settings)),
        scorer,
        store,
    )
    evaluator = build_default_evaluator(
        settings.input_price_per_million, settings.output_price_per_million
    )
    summary = PipelineRunner(graph, scorer, evaluator, store).run("e2e-test", forms)

    assert summary["forms"] == 2
    assert summary["forms_with_output"] == 2

    write_run_files(
        tmp_path, describe_run("e2e-test", settings, forms, reader.fingerprint), summary
    )
    run_description = json.loads((tmp_path / "run.json").read_text())
    written_summary = json.loads((tmp_path / "summary.json").read_text())
    assert run_description["dataset_fingerprint"] == reader.fingerprint
    assert written_summary == summary

    for form in forms:
        usage = store.read_json("structured", form.form_id)["usage"]
        assert usage["input_tokens"] > 0
        assert usage["output_tokens"] > 0
