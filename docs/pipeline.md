# The pipeline

Read a phone photo of a filled constat amiable, turn it into a record, and score it against the answer key.
It is deliberately basic: plain OCR, then an LLM that only sees the OCR text. v1 used Tesseract; v2 swapped in a stronger CPU
engine (PP-OCRv6) and changed nothing else.

```
photo ──► straighten ──► ocr ──► structure ──► evaluate (only when an answer key is given) ──► result
          (optional)     OCR engine  LLM, JSON mode         field-by-field score
```

It is one LangGraph graph (`backend/pipeline/flow/graph.py`). Without an answer key the graph stops after `structure`, which
is how it would run in production.

## The steps

| Step | What it does | Saved to `runs/<run-id>/` |
|---|---|---|
| **straighten** (optional) | `STRAIGHTENER=opencv` finds the page against the desk and warps it flat. Off by default, so v1 and v2 stay reproducible | `straightened/<id>.jpg` |
| **ocr** | The engine named by `OCR_ENGINE` reads the image (the straightened one when that step ran) into text (default `rapidocr-v6`, PP-OCRv6 on CPU; `tesseract` is the v1 baseline). No contrast fixes | `ocr/<id>.txt`, `ocr_usage/<id>.json` |
| **structure** | An LLM (Groq `openai/gpt-oss-120b`, temperature 0) fills the `Record` from the text only. It never sees the image | `structured/<id>.json` (record and token counts) |
| **evaluate** | Compares the record with the answer key, field by field | `evaluation/<id>.json` |

Each step saves its own output, so any step can be inspected or skipped on a re-run (`--reuse`).

### How the LLM is asked (JSON mode)
JSON mode guarantees valid JSON but does not enforce a schema. So the prompt (`structuring/prompts.py`) explains the task
and the layout of the form, and the output format is appended (`structuring/output_format.py`): the exact JSON to fill,
with every value shown as `null`, and one line per key with its meaning and allowed values. That text is generated from the
Pydantic `Record`, so the prompt can never drift from the schema. The answer is then validated against `Record`.

A model that wraps its answer in another key, or returns nothing at all, raises `StructuringError`; the graph retries that
step once, and after that the form is recorded as "no output".

## Run it

From `backend/`. Keys are read from `backend/.env` (`GROQ_API_KEY`, `LANGSMITH_API_KEY`); git ignores that file.

```bash
cd ~/projects/constat-ocr/backend && uv run python -m pipeline.run --run-id v2-dev --dev 5 --test 0
```

The v1 baseline is the same command with `OCR_ENGINE=tesseract`. Add `STRAIGHTENER=opencv` to straighten the photo first (v3a).

| Option | Default | Meaning |
|---|---|---|
| `--run-id` | required | Name of the run. Its files go to `runs/<run-id>/` |
| `--dev`, `--test` | 5 and 20 | How many forms to take from the start of each split |
| `--reuse` | off | Do not redo a step whose output is already saved |

Two files per run are committed: `run.json` (what was run: the forms, the dataset fingerprint, the model, tool and package
versions, the command) and `summary.json` (the metrics of `docs/metrics.md`). Per-form files are ignored by git.

Where the errors come from:

```bash
cd ~/projects/constat-ocr/backend && uv run python -m scripts.analyze_run v2-dev
```

For every wrong text field it asks whether the answer-key value appears anywhere in the OCR text. If not, the OCR never read
it and nothing downstream could have got it right. It writes `failures.json` next to the summary.

## Observability

LangSmith traces every form as one trace (the graph run, with one span per step and the LLM call inside). The two secrets
come from `.env`; `pipeline/core/observability.py` sets the non-secret variables (`LANGSMITH_TRACING`, `LANGSMITH_PROJECT`).
Free plan: 5,000 traces a month, 180-day retention. Every form is synthetic, so nothing personal is sent.

## Code map

| File | Role |
|---|---|
| `core/schema.py` | `Record`: the one definition of the answer-key shape (LLM output, scoring, tests) |
| `core/config.py` | `Settings` from the environment; no secret defaults |
| `core/errors.py` | `PipelineError` and one subclass per step |
| `core/observability.py` | Turns on LangSmith tracing |
| `straightening/` | `Straightener` (Protocol), a registry (`factory.py`) and `OpenCvStraightener` |
| `ocr/` | `OcrEngine` (Protocol), a registry (`factory.py`) and four engines: `tesseract`, `rapidocr` (PP-OCRv5), `rapidocr-v6` (PP-OCRv6, the default), `doctr` |
| `structuring/` | `Structurer` (Protocol), `LangChainStructurer`, the prompt, the generated output format, the model factory |
| `evaluation/` | `FormScorer`, one class per metric, `Evaluator` |
| `data/storage.py` | `ArtifactStore` (Protocol) and `FileArtifactStore` |
| `data/dataset.py` | Reads the frozen dataset and picks the evaluation forms |
| `flow/graph.py` | Builds the LangGraph graph from injected parts |
| `flow/runner.py` | Runs forms one at a time; a failing form is recorded and scored as "no output" |
| `run.py` | The command line |

## Extending it (the point of the structure)

- **A different straightening method:** a new class with `straighten(image_path, out_path)` in `straightening/`, plus one
  `@register_straightener("name")` builder in `straightening/factory.py`. Select it with `STRAIGHTENER=name`.
- **A different OCR engine** (for example one that also returns confidences): a new class with `read(image_path) -> OcrResult`
  in `ocr/`, plus one `@register_ocr_engine("name")` builder in `ocr/factory.py`. Select it with `OCR_ENGINE=name`. Nothing else changes.
- **A different model or provider:** register a builder with `@register_model_builder("name")` in `structuring/factory.py`
  and set `LLM_PROVIDER`.
- **A vision model:** a new `Structurer`. Its input already carries the image path as well as the OCR text.
- **A new metric:** a class with a `name` and `compute(results)`, added to the list given to `Evaluator`.
- **A new step** (image cleanup, validation, a second model on low confidence, routing to a human): a node and an edge
  in `flow/graph.py`; the existing nodes are untouched.

## Tests

```bash
cd backend && uv run pytest
```

Unit (`tests/unit/`: schema, metrics, graph, run metadata, OCR registry — fakes and a local OCR model, no network) and regression
(`tests/regression/`: generator consistency, dataset determinism, and this pipeline's own scoring
math replayed against v1's saved output) run on every push, no key needed. Integration
(`tests/integration/`: the real pipeline on 2 forms) needs `GROQ_API_KEY` and self-skips without
it. Full breakdown, file by file: [docs/testing.md](testing.md).

## Known limits (v1 to v3a)

- The LLM sees text only, so ticks, circled letters, the highlighted vehicle type, the impact zone and the sketch are invisible to it by design.
- The OCR engines run with default settings on tilted phone photos; the only image step is straightening, and there is no column handling.
- The evaluation set is small (5 dev forms and 20 test forms) because of the free plan's rate limits, so percentages are an early signal, not a precise score.
- **Volume:** the provider's free plan (8,000 tokens a minute, 200,000 a day) makes a 20-form run take about 8 minutes, and a large
  run impractical. Hosted providers in general cap or bill by volume.
- **Data governance and residency:** the OCR text of each form is sent to a third-party API, so where it is processed and stored is
  outside our control. Acceptable only because every form is synthetic. Real claims contain personal data and would need a
  self-hosted or in-region model.
- `langchain-community` (which holds `TesseractBlobParser`) does not follow semantic versioning; it is pinned to one minor version.
