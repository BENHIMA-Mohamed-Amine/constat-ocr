"""Runs the graph over a list of forms, one at a time, and writes the run's summary."""
import json
import logging
import platform
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pytesseract
from langgraph.graph.state import CompiledStateGraph

from .config import Settings
from .dataset import FormRef
from .errors import PipelineError
from .evaluation import Evaluator, FormResult, FormScorer
from .storage import ArtifactStore

logger = logging.getLogger(__name__)


class PipelineRunner:
    """Runs forms through the graph. A form that fails is recorded and scored as "no output"; the run goes on."""

    def __init__(self, graph: CompiledStateGraph, scorer: FormScorer, evaluator: Evaluator, store: ArtifactStore) -> None:
        """Create the runner.

        Args:
            graph: The compiled pipeline graph.
            scorer: Scores a form that produced no output.
            evaluator: Computes the metrics over all forms.
            store: Where per-form artifacts (including failures) are saved.
        """
        self._graph = graph
        self._scorer = scorer
        self._evaluator = evaluator
        self._store = store

    def run(self, run_id: str, forms: Sequence[FormRef]) -> dict[str, Any]:
        """Process every form, then compute the metrics."""
        results: list[FormResult] = []
        for position, form in enumerate(forms, start=1):
            logger.info("[%d/%d] form %s (%s)", position, len(forms), form.form_id, form.split)
            truth = form.load_truth()
            try:
                state = self._graph.invoke(
                    {"form_id": form.form_id, "image_path": str(form.image_path), "truth": truth},
                    config={"run_name": f"{run_id}/{form.form_id}", "tags": [run_id, form.split],
                            "metadata": {"form_id": form.form_id, "split": form.split}})
                results.append(state["result"])
            except PipelineError as exc:
                logger.error("form %s failed: %s", form.form_id, exc)
                self._store.write_json("errors", form.form_id, {"error": str(exc), "type": type(exc).__name__})
                results.append(self._scorer.score(form.form_id, None, truth))
        return self._evaluator.summarize(results)


def describe_run(run_id: str, settings: Settings, forms: Sequence[FormRef], fingerprint: str) -> dict[str, Any]:
    """Everything needed to reproduce a run, without secrets."""
    return {
        "run_id": run_id,
        "date_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset_fingerprint": fingerprint,
        "forms": [{"id": f.form_id, "split": f.split} for f in forms],
        "llm": {"provider": settings.llm_provider, "model": settings.llm_model, "temperature": settings.llm_temperature,
                "reasoning_effort": settings.llm_reasoning_effort},
        "ocr": {"engine": "LangChainTesseractEngine", "languages": list(settings.ocr_languages),
                "tesseract": str(pytesseract.get_tesseract_version())},
        "versions": {name: version(name) for name in ("langchain", "langchain-core", "langchain-groq", "langchain-community",
                                                     "langgraph", "langsmith", "pydantic", "pytesseract", "jiwer")},
        "python": platform.python_version(),
        "command": " ".join(sys.argv),
    }


def write_run_files(run_dir: Path, description: dict[str, Any], summary: dict[str, Any]) -> None:
    """Save the two files of a run that are committed."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(json.dumps(description, indent=2), encoding="utf-8")
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
