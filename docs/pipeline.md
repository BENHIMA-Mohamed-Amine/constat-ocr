# The pipeline

Read a phone photo of a filled constat amiable, turn it into a record, and score it against the answer key.
It is deliberately basic: plain OCR, then an LLM that only sees the OCR text. v1 used Tesseract; v2 swapped in a stronger CPU
engine (PP-OCRv6), v3a added straightening, and v3b sorts the OCR text by zone of the form, and v3c replaces the OCR engine with Chandra-OCR-2 served on a GPU ([serving.md](serving.md)). Each changed one thing.

```
photo ──► straighten ──► ocr ──► structure ──► marks ──► repair ──► evaluate (only when an answer key is given) ──► result
          (optional)     OCR engine  LLM, JSON mode  (optional) (optional)      field-by-field score
```

It is one LangGraph graph (`backend/pipeline/flow/graph.py`). Without an answer key the graph stops after `structure`, which
is how it would run in production.

## The steps

| Step | What it does | Saved to `runs/<run-id>/` |
|---|---|---|
| **straighten** (optional) | `STRAIGHTENER=opencv` finds the page against the desk and warps it flat. Off by default, so v1 and v2 stay reproducible | `straightened/<id>.jpg` |
| **ocr** | The engine named by `OCR_ENGINE` reads the image (the straightened one when that step ran) into text (default `rapidocr-v6`, PP-OCRv6 on CPU; `tesseract` is the v1 baseline; `rapidocr-v6-columns` returns the text as four zone blocks, and `chandra-ocr-2` reads the page with an OCR vision model on a server, see below). No contrast fixes | `ocr/<id>.txt`, `ocr_usage/<id>.json` |
| **structure** | An LLM (Groq `openai/gpt-oss-120b`, temperature 0) fills the `Record` from the text only. It never sees the image | `structured/<id>.json` (record and token counts) |
| **marks** (optional) | `READ_MARKS=true` reads the ticks, vehicle-type tile, circled licence letter, impact patch and OUI/NON cells from fixed positions on the blank template, with plain image processing, and puts them in the record. Needs the straightened page. Off by default | `marks/<id>.json` |
| **repair** (optional) | `REPAIRS=all` (or rule names, comma-separated) applies small deterministic rules to the record: validity dates in order, phone and policy numbers without separators, attestation number format. Off by default | `repaired/<id>.json` (the record and the list of changes) |
| **evaluate** | Compares the record with the answer key, field by field | `evaluation/<id>.json` |

Each step saves its own output, so any step can be inspected or skipped on a re-run (`--reuse`).

### Zone blocks (v3b)
`rapidocr-v6-columns` keeps the boxes RapidOCR returns and assigns each to a zone by the position of its centre: `header` (above the
green strips: date, place, phones), `vehicle_a` (left of the left strip), `circumstances` (the two green strips and the numbered list
between them, so both checkbox columns stay together) and `vehicle_b` (right of the right strip). The cuts are found per form from
the printed green strips (`ocr/columns.py`), because the page shifts by about 2% between forms. Each block is sorted top to bottom.
`STRUCTURING_PROMPT=columns` selects the prompt that describes these blocks; the default `flat` prompt goes with the other engines.

`chandra-ocr-2` (`ocr/chandra.py`) sends the straightened page to Chandra-OCR-2 on a vLLM server (`CHANDRA_OCR_2_SERVER_URL`, with the Modal proxy token `MODAL_PROXY_TOKEN_ID` and `MODAL_PROXY_TOKEN_SECRET` as a Bearer header). The answer is HTML,
one block per layout region with its position (`data-bbox`, 0 to 1000). Each block goes to the same four zones, by the centre of its box and the
same per-form cuts, so the grouping code is shared with `rapidocr-v6-columns`. Checkboxes become `[x]` and `[ ]`, a circled letter `(x)`, and a
picture's description `[image: ...]`. An answer that ends in a repeated pattern is regenerated at a higher temperature (up to 6 times).
`STRUCTURING_PROMPT=chandra` selects the prompt that describes these marks.

### Template marks (v3e)
`marks/` (`MarksReader`) reads what a driver marked, with no model. The straightened page is aligned on the blank template (`align.py`, an ECC
homography on the printed content), then each mark is a measurement at a position given by the template (`layout.py`): ink in each of the 23
checkboxes of each vehicle (each box is placed on its own printed square first, since the page alignment can be a few pixels off), colour in
the five vehicle-type tiles, ink on a ring around each licence letter, the zone rectangle that best matches the blue patch of the impact picture,
and ink in the OUI or NON cells. The tick count is the number of ticks. The values replace the LLM's for those fields. The thresholds were set on
the dev forms; `scripts/eval_marks.py <split>` checks the reader alone on a whole split. Built for the synthetic forms, whose marks are clean.

### Repair rules (v3d)
`repair/` holds a `Repairer` that runs `RepairRule`s in order and reports every field a rule changed. A rule is a small class with a name and
`apply(record) -> record`, registered in `repair/factory.py`, so a new rule is a new class and one entry. The scorer sees the repaired record.
Only rules that hold on real forms belong by default; the attestation format comes from the synthetic forms and says so in its docstring.

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

The v1 baseline is the same command with `OCR_ENGINE=tesseract`. Add `STRAIGHTENER=opencv` to straighten the photo first (v3a), and `OCR_ENGINE=rapidocr-v6-columns STRUCTURING_PROMPT=columns` for the zone blocks (v3b), or `OCR_ENGINE=chandra-ocr-2 STRUCTURING_PROMPT=chandra` for Chandra (v3c, needs the server). `--workers N` processes N forms at the same time, useful when the reader runs on a server; with the free Groq plan keep it at 1 for the LLM step, or rerun with `--reuse`.

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

For every wrong text field it asks whether the answer-key value appears anywhere in the OCR text. `scripts.near_misses <run-id>` goes further: how many edits the final answer is from the truth, and how close the truth is to anything in the OCR text. If not, the OCR never read
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
| `marks/` | `MarksReader`, `Marks`: ticks, tiles, circles and patch read from template positions; `layout.py` (geometry), `align.py` (page on template) |
| `repair/` | `Repairer`, `RepairRule` (Protocol), the rules and a registry (`factory.py`) |
| `straightening/` | `Straightener` (Protocol), a registry (`factory.py`) and `OpenCvStraightener` |
| `ocr/` | `OcrEngine` (Protocol), a registry (`factory.py`) and six engines: `tesseract`, `rapidocr` (PP-OCRv5), `rapidocr-v6` (PP-OCRv6, the default), `rapidocr-v6-columns` (v6 with zone blocks, `columns.py`), `chandra-ocr-2` (`chandra.py`, a vision model on a server), `doctr` |
| `structuring/` | `Structurer` (Protocol), `LangChainStructurer`, the prompts (`flat`, `columns` and `chandra`), the generated output format, the model factory |
| `evaluation/` | `FormScorer`, one class per metric, `Evaluator` |
| `data/storage.py` | `ArtifactStore` (Protocol) and `FileArtifactStore` |
| `data/dataset.py` | Reads the frozen dataset and picks the evaluation forms |
| `flow/graph.py` | Builds the LangGraph graph from injected parts |
| `flow/runner.py` | Runs forms one at a time; a failing form is recorded and scored as "no output" |
| `run.py` | The command line |

## Extending it (the point of the structure)

- **A new repair rule:** a class with `name` and `apply(record) -> record` in `repair/rules.py`, registered in `repair/factory.py`. Select it with `REPAIRS=name`.
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

## Known limits (v1 to v3e)

- The LLM sees text only. Up to v3b that made ticks, circled letters, the highlighted vehicle type and the impact zone invisible; from v3c Chandra's text carries ticks and picture descriptions, but the category answers are still poor.
- The OCR engines run with default settings on tilted phone photos; the only image step is straightening, and the zone split only regroups the boxes the engine found.
- The evaluation set is small (5 dev forms and 20 test forms) because of the free plan's rate limits, so percentages are an early signal, not a precise score.
- **Volume:** the provider's free plan (8,000 tokens a minute, 200,000 a day) makes a 20-form run take about 8 minutes, and a large
  run impractical. Hosted providers in general cap or bill by volume.
- **Data governance and residency:** the OCR text of each form is sent to a third-party API, so where it is processed and stored is
  outside our control. Acceptable only because every form is synthetic. Real claims contain personal data and would need a
  self-hosted or in-region model.
- `langchain-community` (which holds `TesseractBlobParser`) does not follow semantic versioning; it is pinned to one minor version.
