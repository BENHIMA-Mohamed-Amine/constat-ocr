# Refactor: group the pipeline folder into sub-packages

Status: done

## Goal
`backend/pipeline/` has 9 loose modules next to 3 step packages. Group them so it is clear where a new part goes
(a new step, like v3a's `straightening/`, is one new folder). Moves and import fixes only, no logic change.

## Layout
```
pipeline/
  run.py             CLI entry, command unchanged: python -m pipeline.run
  core/              config.py, errors.py, schema.py, observability.py   (shared foundations)
  data/              dataset.py, storage.py                              (reading forms, saving step outputs)
  flow/              graph.py, runner.py                                 (wiring and running the steps)
  ocr/ structuring/ evaluation/                                          (the steps, unchanged)
```

## Done when
- `git mv` only, so history follows the files; imports, tests, scripts and docs point to the new paths.
- `ruff check` and `pytest tests/unit tests/regression` pass as before (same results as before the move).
- `CLAUDE.md` project structure and `docs/pipeline.md` code map updated; this plan moved to `plans/done/`.
