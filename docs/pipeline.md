# The v1 pipeline

Read a phone photo of a filled constat amiable, turn it into a record, and score it against the answer key.
v1 is the deliberately basic baseline: plain OCR, then an LLM that only sees the OCR text.

```
photo ──► ocr ──► structure ──► evaluate (only when an answer key is given) ──► result
          Tesseract   LLM, JSON mode         field-by-field score
```

It is one LangGraph graph (`backend/pipeline/graph.py`). Without an answer key the graph stops after `structure`, which
is how it would run in production.

## The steps

| Step | What it does | Saved to `runs/<run-id>/` |
|---|---|---|
| **ocr** | Tesseract (French pack) reads the image into text. No straightening, no contrast fixes | `ocr/<id>.txt`, `ocr_usage/<id>.json` |
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
cd ~/projects/constat-ocr/backend && uv run python -m pipeline.run --run-id v1-dev --dev 2 --test 0
```

| Option | Default | Meaning |
|---|---|---|
| `--run-id` | required | Name of the run. Its files go to `runs/<run-id>/` |
| `--dev`, `--test` | 2 and 20 | How many forms to take from the start of each split |
| `--reuse` | off | Do not redo a step whose output is already saved |

Two files per run are committed: `run.json` (what was run: the forms, the dataset fingerprint, the model, tool and package
versions, the command) and `summary.json` (the metrics of `docs/metrics.md`). Per-form files are ignored by git.

Where the errors come from:

```bash
cd ~/projects/constat-ocr/backend && uv run python -m scripts.analyze_run v1-dev
```

For every wrong text field it asks whether the answer-key value appears anywhere in the OCR text. If not, the OCR never read
it and nothing downstream could have got it right. It writes `failures.json` next to the summary.

## Observability

LangSmith traces every form as one trace (the graph run, with one span per step and the LLM call inside). The two secrets
come from `.env`; `pipeline/observability.py` sets the non-secret variables (`LANGSMITH_TRACING`, `LANGSMITH_PROJECT`).
Free plan: 5,000 traces a month, 180-day retention. Every form is synthetic, so nothing personal is sent.

## Code map

| File | Role |
|---|---|
| `schema.py` | `Record`: the one definition of the answer-key shape (LLM output, scoring, tests) |
| `config.py` | `Settings` from the environment; no secret defaults |
| `errors.py` | `PipelineError` and one subclass per step |
| `ocr/` | `OcrEngine` (Protocol) and `LangChainTesseractEngine` |
| `structuring/` | `Structurer` (Protocol), `LangChainStructurer`, the prompt, the generated output format, the model factory |
| `evaluation/` | `FormScorer`, one class per metric, `Evaluator` |
| `storage.py` | `ArtifactStore` (Protocol) and `FileArtifactStore` |
| `dataset.py` | Reads the frozen dataset and picks the evaluation forms |
| `graph.py` | Builds the LangGraph graph from injected parts |
| `runner.py` | Runs forms one at a time; a failing form is recorded and scored as "no output" |
| `run.py` | The command line |

## Extending it (the point of the structure)

- **A different OCR engine** (for example one that also returns confidences): a new class with `read(image_path) -> OcrResult`
  in `ocr/`, passed to `build_graph`. Nothing else changes.
- **A different model or provider:** register a builder with `@register_model_builder("name")` in `structuring/factory.py`
  and set `LLM_PROVIDER`.
- **A vision model:** a new `Structurer`. Its input already carries the image path as well as the OCR text.
- **A new metric:** a class with a `name` and `compute(results)`, added to the list given to `Evaluator`.
- **A new step** (image cleanup, validation, a second model on low confidence, routing to a human): a node and an edge
  in `graph.py`; the existing nodes are untouched.

## Tests

From `backend/`. None of them needs Tesseract or the network except where stated.

```bash
cd ~/projects/constat-ocr/backend && uv run python -m tests.test_schema && uv run python -m tests.test_metrics && uv run python -m tests.test_graph
```

- `test_schema`: the 300 generated records validate against `Record`, and the schema and the generator agree on every field and choice.
- `test_metrics`: 8 hand-made cases (perfect prediction, one wrong digit, no output, ticks found/missed/extra, the guessing baseline, cost and time).
- `test_graph`: the graph and the runner with fake parts: steps save their output, `--reuse` skips finished steps, one failing form does not stop a run, and without an answer key the graph stops after `structure`.

## Known limits of v1

- The LLM sees text only, so ticks, circled letters, the highlighted vehicle type, the impact zone and the sketch are invisible to it by design.
- Tesseract is run with default settings on tilted phone photos; there is no image cleanup.
- The evaluation set is small (2 dev forms and 20 test forms) because of the free plan's rate limits, so percentages are an early signal, not a precise score.
- `langchain-community` (which holds `TesseractBlobParser`) does not follow semantic versioning; it is pinned to one minor version.
