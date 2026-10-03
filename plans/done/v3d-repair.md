# v3d: repair the record with deterministic rules

Status: done

## Goal
`scripts/near_misses.py v3c` showed 57% of the wrong text fields are one or two characters off, and some errors are rules, not reading:
vehicle B's validity dates come out swapped (the line is written right to left) and ID numbers carry stray spaces. v3d adds one step
after the LLM: small rules that repair the record. Nothing else changes, and the OCR and LLM outputs of v3c are reused, so any
change in the metrics comes from the rules alone.

On the 20 test forms of v3c, a check of simple rules found these fixes (fields that become exactly right):

| Rule | Fields fixed |
|---|---|
| Validity dates put in order (start before end) | 16 |
| Attestation number format (`59A 150196573`: three characters, a space, the digits) | 7 |
| Phone numbers without spaces or dots | 4 |
| Policy number without spaces | 1 |

## Decisions
- **A new step, `repair`, after `structure`, optional.** A rule is a small class with a name and `apply(record) -> record`, registered by
  name like the OCR engines. A new rule is a new class and one registry entry. Off by default, so earlier runs stay reproducible.
- **The step reports what it changed:** `repaired/<id>.json` holds the repaired record and a list of (rule, field, before, after).
- **Rules that hold on any real form** go in by default: dates in order, phones and policy numbers without spaces.
- **A rule taken from the synthetic data is marked as such in its docstring:** the attestation number format is the generator's.
  Real attestation numbers differ between insurers, so this rule is only trusted on synthetic forms.
- **Rules left out on purpose:** snapping names, insurers or prefectures to a list (the lists would come from the generator, which would
  inflate the score without the pipeline getting better), and stripping the period of "Bd." (cosmetic, specific to the answer key).
- **The v3c outputs are reused.** The saved Chandra text and the saved LLM records are copied to the v3d run and the run uses `--reuse`,
  so the step is the only difference and no GPU or LLM call is made.

## Work
```
backend/pipeline/repair/             Repairer, RepairRule protocol, rules, registry (new)
backend/pipeline/flow/graph.py       repair node, optional
backend/pipeline/core/config.py      repairs setting (comma-separated rule names)
backend/pipeline/run.py              build it from the setting
backend/pipeline/flow/runner.py      record the rules in run.json
backend/tests/unit/test_repair.py    each rule on a record, the change report, the graph wiring
```

## Steps
1. Implement and test.
2. Copy the saved v3c outputs into `runs/v3d-dev5` and `runs/v3d`, run both with `REPAIRS=...` and `--reuse`.
3. Log in `docs/results-log.md` next to v3c: the table, and what each rule changed.
4. Update the README, `docs/pipeline.md`, `docs/testing.md`, `CLAUDE.md`.

## Result
- `v3d` on the 20 test forms: 194 of 380 critical fields right (v3c: 168), 381 of 600 minor (377), character error rate 16.1% (16.8%).
  40 fields changed, 30 became right, none became wrong. Without the attestation rule (synthetic format) the gain is +19 critical.
- Full table and analysis: `docs/results-log.md`.

## Done when
- `v3d` is scored on the 20 test forms from the same OCR and LLM outputs as v3c, and logged with the effect of each rule.
