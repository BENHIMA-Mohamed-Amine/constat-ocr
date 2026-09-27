# Testing & CI (applies to every version, not just v1)

Status: done

## Goal
Convert the existing hand-run test scripts to pytest, organized into category folders, add the
three test types agreed on (integration/E2E, regression/golden on saved evaluation results,
reproducibility metadata), and add a CI workflow that runs the offline ones on every push, plus a
capped (max 2 forms) E2E run using a `GROQ_API_KEY` secret. No snapshot tests, no robustness tests
(decided against).

## Docstring convention (every file, every test)
- **Module docstring** at the top of every test file: what category it is and what it covers as a
  whole (1–3 sentences).
- **Function docstring** on every `test_*`: what it tests, specifically — not "tests X" restated,
  but the actual condition being checked and why it matters. Google format:
  ```python
  def test_tick_count_matches_circumstances() -> None:
      """Every generated record's circumstance_count equals len(circumstances) for both vehicles.

      This is what lets the checkbox metric trust the written count as a cross-check against the
      ticks it detects; if the generator itself could produce a mismatch, the metric would be
      validating against bad ground truth.
      """
  ```
  Fixtures in `conftest.py` get the same treatment (Args/Returns as applicable, Google format).

## Folder layout

```
tests/
  conftest.py                        shared fixtures (see below)
  unit/
    __init__.py
    test_schema.py                   schema <-> generator agreement
    test_metrics.py                  the 8 hand-built scoring cases
    test_graph.py                    graph/runner with fakes
    test_reproducibility.py          describe_run() metadata completeness
  regression/
    __init__.py
    test_data.py                     generator: 300-seed consistency checks
    test_dataset.py                  generator: dataset command determinism
    test_evaluation_regression.py    scoring math vs. committed summary.json
    fixtures/
      evaluation/
        v1-dev/*.json  + summary.json
        v1/*.json      + summary.json
  integration/
    __init__.py
    test_pipeline_e2e.py             real Tesseract + real Groq, capped at 2 forms
```

Rationale for the four categories: **unit** (fakes/pure functions, no I/O, no network), **regression**
(checks today's output against a frozen reference — generator determinism or saved LLM output),
**integration** (the real pipeline, real network, real cost — kept small on purpose).
`test_reproducibility.py` goes under `unit/` since it needs no network, only a real Tesseract binary
for the version string (already a dependency for the OCR unit-adjacent tests).

## Files

### `tests/conftest.py` — shared fixtures
- `tmp_run_dir` — a temp `FileArtifactStore` root, cleaned up after the test.
- `fake_ocr_engine` — an `OcrEngine` returning fixed text, call-counting.
- `fake_structurer` — a `Structurer` returning the answer key with one field perturbed, or raising
  `StructuringError` on demand.
- `sample_truth(seed)` — a generated `Record` for a given seed, for tests that need one real record.

### `unit/test_schema.py` — schema/generator agreement
- `test_generated_records_validate_against_schema` — every field of 300 generated records parses
  into `Record`/`Vehicle` without a validation error.
- `test_schema_and_generator_choices_match` — `VehicleType`, `ImpactZone`, `LicenseCategory` allow
  exactly the values the generator can produce, in both directions (schema not stricter than the
  generator, generator not looser than the schema).

### `unit/test_metrics.py` — the 8 existing hand-built cases
`test_every_field_is_classified`, `test_normalize`, `test_perfect_prediction`,
`test_one_wrong_digit`, `test_no_output_counts_everything_wrong`,
`test_checkboxes_found_missed_extra`, `test_category_accuracy_next_to_the_guessing_baseline`,
`test_cost_and_time` — same assertions as today, each gets its Google-format docstring.

### `unit/test_graph.py`
`test_graph_runs_saves_and_scores`, `test_reuse_skips_finished_steps`,
`test_runner_survives_a_failing_form` — same assertions as today, docstrings added.

### `unit/test_reproducibility.py` — new
- `test_describe_run_has_no_missing_metadata` — builds `describe_run()` with a fake `Settings` and
  a 1-form fake list; asserts every required key is present and non-empty: model, temperature,
  reasoning effort, OCR engine name, OCR languages, real Tesseract version string, the full package
  version dict, dataset fingerprint, the command string. Needs the real Tesseract binary (for
  `pytesseract.get_tesseract_version()`), no network, no Groq key.

### `regression/test_data.py` — generator, 300 seeds
`test_tick_count_matches_circumstances`, `test_attestation_covers_accident_date`,
`test_licence_valid_on_accident_date`, `test_plates_differ`, `test_sketch_contact_points_touch`,
`test_cars_fit_the_canvas`, `test_lane_matches_heading`, `test_t_junction_geometry_is_consistent`
— one assertion group per test function instead of today's single `check_record` loop, so a CI
failure names the exact property that broke.

### `regression/test_dataset.py` — generator, determinism
`test_same_command_gives_identical_manifest`, `test_split_and_level_are_as_asked`,
`test_different_seed_changes_the_fingerprint`.

### `regression/test_evaluation_regression.py` — new
- `test_v1_dev_summary_is_reproducible_from_saved_results` and
  `test_v1_test_summary_is_reproducible_from_saved_results` — load the committed per-form
  `FormResult` JSON from `regression/fixtures/evaluation/<run>/`, feed them through
  `Evaluator.summarize()`, assert the result equals the committed `summary.json`. Fixtures are
  copies of `runs/v1-dev/evaluation/*.json` and `runs/v1/evaluation/*.json` (gitignored at their
  original location; committed here because they're small and contain no PII — every form is
  synthetic). This tests the **scoring code**, not the LLM: it catches an accidental change to
  normalization, a metric formula, or the critical/minor split, using frozen LLM output as input.

### `integration/test_pipeline_e2e.py` — new, capped, needs `GROQ_API_KEY`
- `test_dev_forms_run_through_the_real_pipeline` — runs the real graph (real
  `LangChainTesseractEngine`, real `LangChainStructurer`) on **exactly the 2 dev forms**, nothing
  more, so a CI run costs at most 2 Groq calls (~$0.002 based on the v1-dev run's actual usage).
  Loose assertions only, since the LLM is not deterministic run to run: exactly 2 `FormResult`s
  come back, `produced_output` is `True` for both, `usage.input_tokens > 0` and
  `usage.output_tokens > 0`, `run.json`/`summary.json` are written and parse, `dataset_fingerprint`
  matches `DatasetReader(...).fingerprint`. Does not assert on extracted values — those are
  recorded by hand in `docs/results-log.md`.
  `@pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="needs a live Groq key")`.

### Unchanged, not tests
`scripts/analyze_run.py`, `scripts/make_template.py` stay as scripts.

## CI workflow

`.github/workflows/ci.yml`, on push and pull_request:
1. checkout, `sudo apt-get install tesseract-ocr tesseract-ocr-fra`, `astral-sh/setup-uv`,
   `cd backend && uv sync`
2. `uv run ruff check .`
3. `uv run pytest tests/unit tests/regression` — no secret needed, runs on every push/PR including
   forks.
4. `uv run pytest tests/integration` — only when `secrets.GROQ_API_KEY` is available (skipped on
   PRs from forks, which don't get repo secrets); passed through `env: GROQ_API_KEY: ...`. Capped
   at 2 forms by the test itself, so this step costs about $0.002 and a couple of minutes per run.

`GROQ_API_KEY` gets added as a GitHub Actions repo secret.

## Migration note for later versions
When v2 adds a step or swaps the OCR/structurer engine, its unit tests go in `tests/unit/` next to
the code they cover, and once it has its own `runs/v2*/evaluation/*.json`, its own fixture
subfolder + regression test in `tests/regression/`. `tests/integration/test_pipeline_e2e.py` is
extended (or a `test_pipeline_e2e_v2.py` added) to also exercise the new pipeline, still capped at
2 forms. Everything else in this plan is reused unchanged.

## Build order
1. `tests/conftest.py`.
2. `tests/unit/` — move and convert `test_schema.py`, `test_metrics.py`, `test_graph.py`
   (mechanical: `if __name__` runner → `def test_x():`, docstrings added); confirm `uv run pytest
   tests/unit` matches today's pass/fail.
3. `tests/regression/` — move and split `test_data.py` (one function per property),
   move+convert `test_dataset.py`.
4. Copy fixture evaluation files + summaries into `tests/regression/fixtures/evaluation/`.
5. `tests/regression/test_evaluation_regression.py`.
6. `tests/unit/test_reproducibility.py`.
7. `tests/integration/test_pipeline_e2e.py` — run once locally with the real key to confirm pass
   and timing (expect ~10s/form based on the v1-dev run).
8. Add `pytest`, `ruff` to `backend/pyproject.toml` dev dependencies.
9. `.github/workflows/ci.yml`; add `GROQ_API_KEY` as a repo secret.
10. Update `docs/pipeline.md` "Tests" section to match the new layout and commands.


## Outcome
- Converted to pytest, organized under `tests/unit/`, `tests/regression/`, `tests/integration/`,
  with a shared `tests/conftest.py`. `pytest`/`ruff` added as dev dependencies; `pythonpath = ["."]`
  and `testpaths = ["tests"]` set in `pyproject.toml`.
- `tests/regression/test_data.py` split into 8 functions (one per property), parametrized over 300
  seeds, with the sample cached per seed (`lru_cache`) so it doesn't re-sample 2,400 times.
- `tests/regression/test_evaluation_regression.py` + committed fixtures
  (`tests/regression/fixtures/evaluation/v1-dev/`, `.../v1/`, 384K, no PII) reproduce v1's own
  `summary.json` exactly from its saved per-form results.
- `tests/integration/test_pipeline_e2e.py` capped at exactly the 2 dev forms; run once for real
  (14.5s, passed) to confirm it actually works against live Groq, not just that it compiles.
- Full suite: 3,018 passed, 1 skipped (E2E, no key in the shell env), 0 failed, `ruff check` clean.
- `.github/workflows/ci.yml`: `offline` job (lint + unit + regression, no secret, every push/PR)
  and `e2e` job (generates only the 2 dev forms — same seed formula as the real dataset, so
  they're the same forms — then runs the integration test; needs the `GROQ_API_KEY` repo secret,
  so it's skipped on fork PRs). `GROQ_API_KEY` still needs to be added as a repo secret on GitHub
  by hand (not done from here).
- Docs: new `docs/testing.md`; "Tests" sections of `docs/pipeline.md` and `docs/synthetic-data.md`
  updated to match; README links to `docs/testing.md`.
