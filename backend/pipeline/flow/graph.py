"""The pipeline as one LangGraph graph: read the image, fill the record, and (given an answer key) score it.

The graph only wires steps together. Each node calls an injected implementation (``OcrEngine``, ``Structurer``,
``FormScorer``), so a new engine or model changes nothing here, and a new step is one more node and edge.
"""

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from ..core.errors import StructuringError
from ..core.schema import Record
from ..data.storage import ArtifactStore
from ..evaluation import FormResult, FormScorer, Usage
from ..marks import MarksReader
from ..ocr import OcrEngine
from ..refine import FieldRefiner
from ..repair import Repairer
from ..straightening import Straightener
from ..structuring import Structurer, StructuringInput

logger = logging.getLogger(__name__)


class PipelineState(TypedDict, total=False):
    """What flows through the graph for one form."""

    form_id: str
    image_path: str
    truth: Record  # the answer key; when present the graph also evaluates
    straightened_path: (
        str  # set when a straightener ran; OCR reads this instead of image_path
    )
    ocr_text: str
    ocr_seconds: float
    record: Record
    structure_seconds: float
    input_tokens: int
    output_tokens: int
    result: FormResult


def build_graph(
    ocr: OcrEngine,
    structurer: Structurer,
    scorer: FormScorer,
    store: ArtifactStore,
    reuse: bool = False,
    straightener: Straightener | None = None,
    repairer: Repairer | None = None,
    marks_reader: MarksReader | None = None,
    refiner: FieldRefiner | None = None,
) -> CompiledStateGraph:
    """Assemble the graph.

    Args:
        ocr: Reads the image into text.
        structurer: Turns the text into a record.
        scorer: Scores the record against the answer key.
        store: Where each step saves its output.
        reuse: If True, a step whose output is already saved is not run again (its saved output is loaded).
        straightener: If given, flattens the photo before OCR reads it.
        repairer: If given, repairs the record after the LLM, before it is scored.
        refiner: If given, re-reads some fields from crops of the straightened page after the structurer, before the marks.
        marks_reader: If given, reads the ticks, tiles and circles from the template positions of the straightened page and
            puts them in the record, after the LLM and before the repair step.
    """

    def straighten_node(state: PipelineState) -> dict[str, Any]:
        out = store.path("straightened", state["form_id"], ".jpg")
        if not (reuse and out.is_file()):
            straightener.straighten(Path(state["image_path"]), out)
        return {"straightened_path": str(out)}

    def ocr_node(state: PipelineState) -> dict[str, Any]:
        form_id = state["form_id"]
        if (
            reuse
            and store.exists("ocr", form_id)
            and store.exists("ocr_usage", form_id)
        ):
            return {
                "ocr_text": store.read_text("ocr", form_id),
                "ocr_seconds": store.read_json("ocr_usage", form_id)["seconds"],
            }
        result = ocr.read(Path(state.get("straightened_path", state["image_path"])))
        store.write_text("ocr", form_id, result.text)
        store.write_json("ocr_usage", form_id, {"seconds": result.seconds})
        return {"ocr_text": result.text, "ocr_seconds": result.seconds}

    def structure_node(state: PipelineState) -> dict[str, Any]:
        form_id = state["form_id"]
        if reuse and store.exists("structured", form_id):
            saved = store.read_json("structured", form_id)
            usage = saved["usage"]
            return {
                "record": Record.model_validate(saved["record"]),
                "structure_seconds": usage["seconds"],
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
            }
        result = structurer.structure(
            StructuringInput(
                form_id,
                Path(state.get("straightened_path", state["image_path"])),
                state.get("ocr_text"),
            )
        )
        usage = {
            "seconds": result.seconds,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }
        store.write_json(
            "structured",
            form_id,
            {"record": result.record.model_dump(mode="json"), "usage": usage},
        )
        return {
            "record": result.record,
            "structure_seconds": result.seconds,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }

    def refine_node(state: PipelineState) -> dict[str, Any]:
        form_id = state["form_id"]
        if reuse and store.exists("refined", form_id):
            return {
                "record": Record.model_validate(
                    store.read_json("refined", form_id)["record"]
                )
            }
        result = refiner.refine(
            Path(state.get("straightened_path", state["image_path"])), state["record"]
        )
        if (
            not result.failed
        ):  # a failed call is not saved, so a later --reuse run reads this form again
            store.write_json(
                "refined",
                form_id,
                {
                    "record": result.record.model_dump(mode="json"),
                    "changes": [asdict(change) for change in result.changes],
                },
            )
        return {"record": result.record}

    def marks_node(state: PipelineState) -> dict[str, Any]:
        marks = marks_reader.read(
            Path(state.get("straightened_path", state["image_path"]))
        )
        store.write_json("marks", state["form_id"], asdict(marks))
        return {"record": marks.apply(state["record"])}

    def repair_node(state: PipelineState) -> dict[str, Any]:
        result = repairer.repair(state["record"])
        store.write_json(
            "repaired",
            state["form_id"],
            {
                "record": result.record.model_dump(mode="json"),
                "changes": [asdict(change) for change in result.changes],
            },
        )
        return {"record": result.record}

    def evaluate_node(state: PipelineState) -> dict[str, Any]:
        usage = Usage(
            state["ocr_seconds"],
            state["structure_seconds"],
            state["input_tokens"],
            state["output_tokens"],
        )
        result = scorer.score(
            state["form_id"], state.get("record"), state["truth"], usage
        )
        store.write_json("evaluation", state["form_id"], asdict(result))
        return {"result": result}

    def after_structure(state: PipelineState) -> str:
        return "evaluate" if "truth" in state else END

    graph = StateGraph(PipelineState)
    graph.add_node("ocr", ocr_node)
    graph.add_node(
        "structure",
        structure_node,
        retry_policy=RetryPolicy(max_attempts=2, retry_on=StructuringError),
    )
    graph.add_node("evaluate", evaluate_node)
    if straightener:
        graph.add_node("straighten", straighten_node)
        graph.add_edge(START, "straighten")
        graph.add_edge("straighten", "ocr")
    else:
        graph.add_edge(START, "ocr")
    graph.add_edge("ocr", "structure")
    last = "structure"
    for name, node, step in (
        ("refine", refine_node, refiner),
        ("marks", marks_node, marks_reader),
        ("repair", repair_node, repairer),
    ):
        if step:
            graph.add_node(name, node)
            graph.add_edge(last, name)
            last = name
    graph.add_conditional_edges(last, after_structure, ["evaluate", END])
    graph.add_edge("evaluate", END)
    return graph.compile()
