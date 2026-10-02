"""Regression (1 test): the six metrics, recomputed from frozen LLM output, reproduce v1's numbers.

Answers "if I feed the evaluator the exact same LLM output as last time, do I get the exact same
numbers as last time?" — it never calls Tesseract or Groq, so a failure means the *scoring code*
changed behaviour (a metric formula, the normalisation rule, the critical/minor split), not that a
model call went differently. This is the counterpart to ``test_pipeline_e2e.py``, which answers
"does the real pipeline still run at all?" without checking exact numbers, because the LLM's
output is not reproducible run to run. Together they cover what neither can alone: this test would
not catch a broken Groq client (it never calls one); the E2E test would not reliably catch a
subtle metric bug (its assertions must stay loose, since the LLM's answers vary).

Fixtures are copies of ``runs/v1-dev/evaluation/*.json`` and ``runs/v1/evaluation/*.json`` (the
real per-form scoring results from the v1 baseline's dev and test runs) plus their ``summary.json``.
The originals live under ``runs/`` but that folder's per-form output is gitignored, so these copies
are committed here instead — they hold no personal data, since every form is synthetic.
"""

import json
from pathlib import Path

from pipeline.evaluation import (
    Evaluator,
    FieldResult,
    FormResult,
    Usage,
    build_default_evaluator,
)
from pipeline.evaluation.fields import FieldKind

from ..checks import run_checks

FIXTURES = Path(__file__).parent / "fixtures" / "evaluation"
EVALUATOR: Evaluator = build_default_evaluator(
    input_price_per_million=0.15, output_price_per_million=0.60
)
RUN_IDS = ("v1-dev", "v1")


def _load_form_result(path: Path) -> FormResult:
    """Rebuild a :class:`FormResult` from a saved ``evaluation/<id>.json`` file.

    Args:
        path: Path to one form's saved evaluation JSON, as written by ``pipeline/flow/graph.py``.

    Returns:
        The :class:`FormResult` that produced that file, field for field.
    """
    data = json.loads(path.read_text())
    fields = tuple(
        FieldResult(
            path=f["path"],
            kind=FieldKind(f["kind"]),
            expected=f["expected"],
            predicted=f["predicted"],
            correct=f["correct"],
            edit_distance=f["edit_distance"],
            reference_length=f["reference_length"],
        )
        for f in data["fields"]
    )
    usage = Usage(**data["usage"]) if data["usage"] is not None else None
    return FormResult(
        form_id=data["form_id"],
        produced_output=data["produced_output"],
        fields=fields,
        usage=usage,
    )


def _load_run_fixture(run_id: str) -> tuple[list[FormResult], dict]:
    """Load every form's saved result and the committed summary for one fixture run.

    Args:
        run_id: Subfolder of ``FIXTURES``, e.g. ``"v1-dev"`` or ``"v1"``.

    Returns:
        The list of :class:`FormResult` (one per form, sorted by id) and the committed summary dict.
    """
    run_dir = FIXTURES / run_id
    results = [
        _load_form_result(p)
        for p in sorted(run_dir.glob("*.json"))
        if p.stem != "summary"
    ]
    summary = json.loads((run_dir / "summary.json").read_text())
    return results, summary


def _summary_matches(run_id: str) -> None:
    """Recomputing the metrics from ``run_id``'s saved per-form results reproduces its summary."""
    results, expected_summary = _load_run_fixture(run_id)
    assert EVALUATOR.summarize(results) == expected_summary, f"run {run_id}"


def test_evaluation_reproduces_v1_saved_results() -> None:
    """v1's dev-run and test-run summaries are both exactly reproducible from their saved output.

    See the module docstring: covers both the 2-form dev run and the 20-form test run.
    """
    run_checks(
        [
            (
                f"summary_matches[{run_id}]",
                lambda run_id=run_id: _summary_matches(run_id),
            )
            for run_id in RUN_IDS
        ]
    )
