"""Command line: run the pipeline on the evaluation set.

uv run python -m pipeline.run --run-id v2-dev --dev 5 --test 0
uv run python -m pipeline.run --run-id v2 --dev 0 --test 20
OCR_ENGINE=tesseract uv run python -m pipeline.run --run-id v1 --dev 0 --test 20   (the v1 baseline)
"""

import argparse
import json
import logging

from .core.config import Settings
from .core.observability import configure_tracing
from .data.dataset import DatasetReader
from .data.storage import FileArtifactStore
from .evaluation import FormScorer, build_default_evaluator
from .flow.graph import build_graph
from .flow.runner import PipelineRunner, describe_run, write_run_files
from .ocr import build_ocr_engine
from .straightening import build_straightener
from .structuring import LangChainStructurer, build_chat_model
from .structuring.prompts import PROMPTS


def main() -> None:
    """Parse the arguments, wire the parts together, run, print the summary."""
    settings = Settings()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--run-id",
        required=True,
        help="name of the run; its files go to runs/<run-id>/",
    )
    parser.add_argument(
        "--dev",
        type=int,
        default=settings.eval_dev_count,
        help="how many dev forms (from the first)",
    )
    parser.add_argument(
        "--test",
        type=int,
        default=settings.eval_test_count,
        help="how many test forms (from the first)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="forms processed at the same time (useful when OCR runs on a server)",
    )
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="do not redo a step whose output is already saved",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    tracing = configure_tracing(settings)
    logging.info("LangSmith tracing: %s", "on" if tracing else "off")
    reader = DatasetReader(settings.dataset_dir)
    forms = reader.first("dev", args.dev) + reader.first("test", args.test)
    run_dir = settings.runs_dir / args.run_id
    store = FileArtifactStore(run_dir)
    scorer = FormScorer()
    graph = build_graph(
        build_ocr_engine(settings),
        LangChainStructurer(
            build_chat_model(settings), PROMPTS[settings.structuring_prompt]
        ),
        scorer,
        store,
        reuse=args.reuse,
        straightener=build_straightener(settings),
    )
    evaluator = build_default_evaluator(
        settings.input_price_per_million, settings.output_price_per_million
    )
    summary = PipelineRunner(graph, scorer, evaluator, store, args.workers).run(
        args.run_id, forms
    )
    write_run_files(
        run_dir, describe_run(args.run_id, settings, forms, reader.fingerprint), summary
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
