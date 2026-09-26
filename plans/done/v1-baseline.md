# v1 baseline: Tesseract, then an LLM fills the fields, then evaluate

Status: done

## Goal
The deliberately basic first version, and the foundation later versions extend. Read a phone photo of a filled constat
with plain OCR, turn the text into the answer-key JSON with a structured-output LLM, score it on a fixed set of forms
from the frozen dataset, and write down where it fails. Those failures decide v2.
Metrics: `docs/metrics.md`. Data: `docs/synthetic-data.md`.

## Decisions
- **Evaluation set: 22 forms, fixed.** The first 2 forms of the dev split (`000000`, `000001`) and the first 20 of the test
  split (`000100` to `000119`). The full 500-form dataset stays as generated; later versions can raise the count.
  Reason: Groq's free plan limits (below).
- **Names are minor fields**, not critical. Phones and vehicle make/model are minor too.
- **Tesseract through LangChain's `TesseractBlobParser`**, behind our own `OcrEngine` interface.

## Verified facts (checked online / on this machine)
| Fact | Value | Source |
|---|---|---|
| Groq model id | `openai/gpt-oss-120b`; 131k context; JSON schema mode and tool use supported | Groq docs |
| Groq price | $0.15 / M input tokens, $0.60 / M output | Groq docs |
| Groq free plan limits for it | 30 requests/min, 1,000/day, **8,000 tokens/min, 200,000 tokens/day** | Groq rate-limits page |
| LangSmith free (Developer, no card) | 5,000 traces / month (one graph run = one trace); 180-day retention | LangChain docs |
| Tesseract in LangChain | `TesseractBlobParser(langs=...)` in `langchain_community.document_loaders.parsers`: image `Blob` in, `Document` text out. Needs `pytesseract` and the Tesseract program. No confidences or positions, no Tesseract options | LangChain reference |
| `langchain-community` | not semantically versioned: pin to one minor series; one source calls it unmaintained | LangChain docs |
| This machine | Tesseract 5.3.4 with `fra` installed; Python packages installed; `backend/.env` holds the Groq and LangSmith keys (ignored by git) | checked |

**Budget with 22 forms.** At an estimated 3 to 5k tokens per form (to be measured), 22 forms is about 65 to 110k tokens:
inside the free plan's 200k a day, and about 10 to 15 minutes at 8k tokens a minute. So the free Groq plan is enough; cost at
paid rates would be about two cents. 22 LangSmith traces is nothing.
**Limit of a small sample:** with 20 test forms there are about 40 vehicles, so the rare vehicle types (motorbike, bus,
truck, three-wheeler, about 12% of vehicles) appear only a handful of times. Report counts next to percentages, treat the
result as an early signal and not a precise score, and re-run on more forms before drawing strong conclusions.

## Pipeline: one LangGraph graph
```
START -> ocr -> structure -> (answer key given?) -> evaluate -> END
```
- **`ocr`** (deterministic): `TesseractBlobParser(langs=("fra",))` on the image, no image cleanup. Output: the text.
- **`structure`** (LLM): text only, never the image. `ChatGroq(openai/gpt-oss-120b, temperature=0)` with
  `with_structured_output(Record, method="json_schema", include_raw=True)` (the raw message gives the token counts).
  Every field optional: null when the text does not contain it.
- **`evaluate`** (deterministic): runs only when an answer key is supplied (conditional edge). In production the graph
  ends after `structure`, so the same graph serves both.
- **Why a graph:** later versions add nodes (image cleanup, validation, a second model on low confidence, routing to a
  human) by adding a node and an edge, without touching the existing nodes.
- **Errors:** transient (rate limit, network) -> `RetryPolicy(max_attempts=3)` and respect Groq's `retry-after` header.
  Permanent (unreadable image, invalid output after retries) -> recorded in the state, counted as "no output"; one bad
  form never stops a run.
- **Concurrency:** one form at a time (`max_concurrency=1`); 22 forms do not need more, and it keeps us under the
  tokens-per-minute limit.

## Architecture (SOLID; graph nodes are thin wrappers, the logic lives in plain classes)
```
backend/pipeline/
  schema.py          Pydantic Record (the answer-key shape): single source of truth
  config.py          Settings from environment (pydantic-settings): model id, prices, paths, the evaluation set
  errors.py          PipelineError -> OcrError, StructuringError, EvaluationError
  ocr/               OcrEngine (Protocol) + LangChainTesseractEngine   <- Strategy; PytesseractEngine (with confidences) later = a new file
  structuring/       Structurer (Protocol) + LangChainStructurer       <- Strategy; a new model/provider is a new file
  evaluation/        Metric (Protocol) + one class per metric + Evaluator that runs the registered metrics   <- Open/Closed
  storage.py         ArtifactStore (Protocol) + FileArtifactStore      <- Repository; saves each step's output
  graph.py           build_graph(ocr, structurer, evaluator, store): dependencies injected, nodes only call them
  run.py             CLI: python -m pipeline.run --run-id v1
backend/tests/       fakes for every Protocol, so the graph is tested without Tesseract or network
runs/<run-id>/       run.json + summary.json committed; per-form ocr/, structured/, evaluation/ ignored
```
- **Single responsibility:** OCR reads, the structurer structures, metrics score, the store saves, the graph wires.
- **Open/closed:** a new OCR engine, model, metric or step is added by adding a class or node, not by editing working code.
- **Liskov / interface segregation:** small Protocols (`read(image) -> OcrResult`, `structure(inputs) -> Record`,
  `score(prediction, truth) -> MetricResult`). The structurer's input carries the image path and the OCR result, so a future
  vision model uses the same interface.
- **Dependency inversion:** `build_graph` receives implementations; nothing imports Tesseract or Groq except its own adapter.
- **Code standards:** Python 3.13, full type hints, docstrings, `logging` (no prints), no bare `except`, frozen dataclasses
  or Pydantic models for data passed between steps.

## Tools
`langchain>=1.0`, `langchain-core`, `langgraph>=1.0`, `langsmith`, `langchain-groq`, `langchain-community` (pinned to one
minor, used only for `TesseractBlobParser`), `pytesseract`, `pydantic`, `pydantic-settings`, `jiwer`.
LangSmith tracing: the key is in `.env` (ignored by git); the non-secret `LANGSMITH_TRACING` and `LANGSMITH_PROJECT` are set from `Settings` by `pipeline/observability.py` at the start of a run.
Data is synthetic, so sending it to Groq and LangSmith is fine.
System: `sudo apt install tesseract-ocr tesseract-ocr-fra`.
Left out on purpose: Ragas / DeepEval (exact answers exist), pandas, scikit-learn, Langfuse, a Markdown results table.

## Metrics and fixed rules (from docs/metrics.md)
Six metrics: field accuracy (critical vs minor), forms with no critical error, character error rate per field,
checkbox found/missed/extra, category accuracy next to the "always guess the most common" score, cost and time.
Comparison after trimming, collapsing spaces and ignoring case, nothing more. A missing field counts as wrong (CER 1.0).
The sketch is not scored in v1. Counts are reported next to percentages because the sample is small.

## Expected failures (hypotheses to confirm)
Tilted, blurry phone photos hurt handwriting and digits; ticks and drawn marks are invisible to text OCR; vehicle type,
impact zone and sketch cannot be read from text; values may be mixed up between vehicles A and B.

## Build order, each step with its check
Progress: all steps done. Results: `docs/results-log.md`; runs: `runs/v1-dev` (2 dev forms) and `runs/v1` (20 test forms).

1. Install Tesseract + French pack; add the Python packages. Check: `tesseract --list-langs` shows `fra`.
2. `schema.py`, `config.py`, `errors.py` + test: the 300 generated records validate against `Record`. (`tests/test_schema.py`; it also checks the schema and the generator agree on fields and choices)
3. `evaluation/` + tests: hand-made pairs give the expected numbers. (`tests/test_metrics.py`, 8 checks)
4. `ocr/` + `storage.py`: the 2 dev forms, open the saved text.
5. `structuring/`: same 2 forms; check JSON, retries, token counts; measure tokens per form and re-check the budget.
6. `graph.py` + `run.py`: tested with fakes, then for real on the 2 dev forms; check `summary.json` against a hand-scored form.
7. Read the dev failures, adjust the prompt if needed (only here, never after seeing the test forms), write the failures down.
8. The 20 test forms, once: `summary.json`, a row in `docs/results-log.md`, git tag `v1-baseline`.

## Outcome
- Structured output: JSON mode with generated output instructions works; an empty record is rejected.
- The free Groq plan is enough for 22 forms but slows a run to about 8 minutes (rate-limit waits).
- 20 test forms are enough to see the picture (92% of the errors are OCR misses) but not to compare close versions.
- Not done, on purpose: image cleanup, vision models, confidence scores, the sketch, the frontend.

## Out of scope for v1
Image cleanup, vision models, confidence scores, the sketch, the other documents, page 2, the frontend.
