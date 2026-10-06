# Testing

How this project is tested, and why it's split the way it is. Applies to every version, not just
v1: later versions add their own tests to the same folders, following the same categories.
Design decisions are in [plans/done/testing-ci.md](../plans/done/testing-ci.md).

## 16 tests in total

One pytest item per file, one file per capability being verified — not one item per file per seed
or per case. Where a capability needs several checks (e.g. 8 generator-consistency rules, or 8
hand-built scoring cases), those are kept as separate, named, documented functions internally for
readability, but run together through `tests/checks.py`'s `run_checks` and reported as a single
pytest item. If more than one sub-check fails, the failure message lists every one that did, by
name — not just the first.

```
$ uv run pytest
tests/integration/test_pipeline_e2e.py s
tests/regression/test_data.py .
tests/regression/test_dataset.py .
tests/regression/test_evaluation_regression.py .
tests/unit/test_chandra.py .
tests/unit/test_columns.py .
tests/unit/test_graph.py .
tests/unit/test_marks.py .
tests/unit/test_metrics.py .
tests/unit/test_ocr_engines.py .
tests/unit/test_repair.py .
tests/unit/test_reproducibility.py .
tests/unit/test_schema.py .
tests/unit/test_refine.py .
tests/unit/test_straightening.py .
tests/unit/test_vision.py .
15 passed, 1 skipped
```

`addopts = "-ra"` (`pyproject.toml`) makes the skip reason print by default — no extra flag needed:

```
SKIPPED [1] tests/integration/test_pipeline_e2e.py:34: needs a live GROQ_API_KEY
```

## The four categories

| Category | Folder | Needs Tesseract? | Needs network/a key? | Speed |
|---|---|---|---|---|
| **Unit** | `backend/tests/unit/` | Only `test_reproducibility.py` (and the registry check in `test_ocr_engines.py` builds Tesseract) | No | Fast (~1s) |
| **Regression / golden** | `backend/tests/regression/` | No | No | ~55s (mostly real image rendering in `test_dataset.py`) |
| **Integration / E2E** | `backend/tests/integration/` | Yes | Yes — `GROQ_API_KEY` | ~15s, real cost (~$0.002) |
| Snapshot / robustness | — | — | — | **Not used**, see below |

Four types were considered; two were dropped on purpose:
- **Snapshot tests** would compare the LLM's live output against a saved reference — but that
  output isn't reproducible run to run, so every run would "fail" and the diff would become noise
  nobody reads. Skipped.
- **Robustness tests** (rotate/blur/noise and check the score degrades gracefully) would duplicate
  what the synthetic dataset already does: its `phone`-level degradation (`docs/synthetic-data.md`)
  already makes the data hard to extract on purpose. A separate robustness suite would be testing
  the same thing twice. Skipped.

## Run everything

```bash
cd backend && uv run pytest
```

Or by category:

```bash
uv run pytest tests/unit tests/regression   # no key needed, safe to run anywhere
uv run pytest tests/integration             # needs GROQ_API_KEY in the environment
```

`tests/integration` self-skips (not fails) when `GROQ_API_KEY` isn't set — that's the normal state
for a fork or a contributor without the key, not an error.

## Unit — `tests/unit/`

Fakes and pure functions only; no I/O beyond a temp directory, no real model or OCR call.

| File | Sub-checks | What it tests |
|---|---|---|
| `test_schema.py` | 3 | 300 generated records validate against `Record`; the schema's `Literal` choices (vehicle type, impact zone, licence category) exactly match what the generator can produce, in both directions |
| `test_marks.py` | 3 | Two forms rendered by the generator are read back exactly (ticks, vehicle type, licence letter, impact zone, OUI or NON); the marks overwrite the five fields they give, the tick count is the number of ticks and a missing vehicle is created; the graph scores the marks and saves them |
| `test_metrics.py` | 8 | The scorer and all six `docs/metrics.md` metrics, on hand-built prediction/truth pairs whose correct score is known by construction: perfect prediction, one wrong digit, no output at all, ticks found/missed/extra, the category "guess most common" baseline, cost/time math |
| `test_graph.py` | 3 | The LangGraph pipeline's wiring, with a fake OCR engine and structurer: state flows between nodes, each step's output is saved and reloadable (`--reuse`), a failing form is recorded and doesn't stop the run, and the graph stops after `structure` when no answer key is given (production behaviour) |
| `test_ocr_engines.py` | 2 | The OCR registry builds the engine named in the settings and raises a clear error for an unknown name; the real RapidOCR engine reads the words and digits of a printed image the test draws itself, and reports its seconds |
| `test_chandra.py` | 4 | The repeat check flags a loop and not ordinary HTML; Chandra's HTML becomes the four zone blocks with `[x]`, `(x)` and picture descriptions, and a block cut off by the token cap is dropped; the engine sends the model, the image and Datalab's prompt, and regenerates a looping answer warmer; the `chandra` prompt is the `columns` prompt with the tick sentences replaced |
| `test_columns.py` | 3 | The zone cuts sit on the outer edges of two green strips drawn on a page (and the header ends where the strips start, not at the short header bar); boxes at known positions land in the right block, sorted top to bottom, with the four blocks always printed; the `columns` prompt is the `flat` prompt with only the column bullet replaced |
| `test_straightening.py` | 3 | A tilted page the test draws comes back upright and cropped; the registry builds the named straightener (none when unset) and rejects an unknown name; the graph feeds OCR the straightened file and does not redo the step on `--reuse` |
| `test_vision.py` | 3 | The vision structurer sends the image, the proxy token, the `Record` schema and the format rules, and turns the JSON answer into a `Record`; text that is not JSON, a wrong type and an empty record each raise `StructuringError`; a network failure raises it with the form id (HTTP faked, no model) |
| `test_refine.py` | 4 | Each crop is the template's field box plus the margin, enlarged, for both vehicles; a read value replaces the page value while `null` keeps it and fields not asked for are untouched; header fields merge at the top level and damage is a vehicle field; a failed call returns the record unchanged and flagged failed, and an unknown field name is refused (HTTP faked, the blank template as the page) |
| `test_repair.py` | 4 | Each repair rule fixes its own case and leaves the rest alone (dates swap only when start is after end); the changes are reported with rule, field, before and after, and a record with nothing to fix gives an empty list; the registry builds named rules and fails on an unknown one; the graph scores the repaired record and saves the repair |
| `test_reproducibility.py` | 1 | `describe_run()`'s metadata is complete: model, temperature, OCR engine + languages + the real installed Tesseract version, every dependency's installed version, the dataset fingerprint, the exact command |

## Regression / golden — `tests/regression/`

Checks today's output against a frozen reference. Two different kinds of "frozen reference" here:
the generator's own internal consistency rules, and a past run's saved LLM output.

| File | Sub-checks | What it tests |
|---|---|---|
| `test_data.py` | 8 | One named sub-check per property the generator must always hold, each looped over 300 seeds internally: tick count matches the ticks, insurance covers the accident date, the licence is valid on that date, the two plates differ, the sketch's two damaged zones touch, both cars fit the canvas, vehicle A's lane matches its heading, and T-junction geometry (side, lane) is consistent |
| `test_dataset.py` | 3 | The `generator.dataset` command is deterministic (same seed → byte-identical manifest and file hashes, with 1 or 2 workers), splits and levels come out as asked, and a different seed changes the fingerprint |
| `test_evaluation_regression.py` | 2 (`v1-dev`, `v1`) | Loads v1's own saved per-form results (`fixtures/evaluation/v1-dev/`, `fixtures/evaluation/v1/` — copies of `runs/v1-dev/evaluation/` and `runs/v1/evaluation/`, committed because the originals under `runs/` are gitignored), recomputes the six metrics with today's code, and asserts the result equals the committed `summary.json` exactly |

`test_evaluation_regression.py` answers **"if I feed the evaluator the exact same LLM output as
last time, do I get the exact same numbers as last time?"** — it never calls Tesseract or Groq, so
a failure means the *scoring code* changed (a metric formula, the normalisation rule, the
critical/minor split), not that a model call went differently.

## Integration / E2E — `tests/integration/`

| File | What it tests |
|---|---|
| `test_pipeline_e2e.py` | The real pipeline — real Tesseract, real Groq — runs end to end on exactly the 2 dev forms |

This answers **"does the real pipeline still run at all?"** — the opposite question from the
regression test above. Because the LLM's answers aren't reproducible, its assertions are
deliberately loose: exactly 2 results come back, both report a produced record, both used a
non-zero number of input/output tokens (proof the model call actually ran), and `run.json` /
`summary.json` get written and parse. It never asserts on an extracted value — exact numbers are
judged by hand and recorded in `docs/results-log.md` when a version is finished.

**Neither test alone covers the pipeline.** The regression test can't catch a broken Groq client,
a missing Tesseract install, or a graph-wiring bug — it never runs those parts. The E2E test can't
reliably catch a subtle scoring bug — its assertions have to stay loose precisely because the LLM
varies run to run. Together they cover what neither does alone.

**Kept deliberately capped at 2 forms**, never more: each CI run of it costs real Groq calls
(about $0.002, based on v1-dev's actual token usage) against the same free-plan budget used for
real evaluation runs (`docs/pipeline.md`), so it stays cheap enough to run on every push.

## CI

`.github/workflows/ci.yml`, two jobs:
- **`offline`** — lint (`ruff check`) + `tests/unit` + `tests/regression`. Runs on every push and
  PR, including from forks, no secret needed.
- **`e2e`** — generates just the 2 dev forms (`generator.dataset --count 2 --dev 2`, same seed as
  the real dataset, so they're the exact same 2 forms) and runs `tests/integration`. Needs the
  `GROQ_API_KEY` repo secret, so it's skipped on pull requests from forks (which don't receive
  secrets) but runs on every push to the repo.

## Docstring convention

Every test file has a module docstring naming its category and what it covers as a whole. Every
`test_*` function has a Google-format docstring stating the specific condition checked and why it
matters — not a restatement of the function name.

## Migration note for later versions

A new step or a swapped OCR/structurer engine gets its own unit tests in `tests/unit/`, next to
the existing ones. Once it has its own `runs/<id>/evaluation/*.json`, it gets its own fixture
subfolder under `tests/regression/fixtures/evaluation/` and either an added parametrize case in
`test_evaluation_regression.py` or its own file. `tests/integration/test_pipeline_e2e.py` is
extended (or a sibling file added) to also exercise the new pipeline — still capped at 2 forms.
Everything else here carries over unchanged.
