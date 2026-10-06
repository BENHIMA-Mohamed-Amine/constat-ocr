# v4b: re-read the hard digit fields from crops

Status: done

## Goal
After v4a, 73% of the 282 wrong text fields are one or two characters off, mostly long digit strings: licence number 12 of 40 right,
attestation 16, validity start date 16, plate 18, policy number 18. The model sees the whole page at about 1 vision token per 32 by 32
pixels, so a handwritten digit (about 15 px high) is half a token. v4b adds one optional step after the structurer: it crops each of
these fields from the page at its known template position, enlarges the crop, and asks the same Qwen server to read it. Nothing else
changes: the saved v4a records are reused, so the step is the only difference.

The offline check of Chandra against Qwen (no GPU) showed a second opinion does not fix these fields (the two agree on 87 of 240 and 71 are
right), so the lever is better pixels, not a second model.

## How
```
straightened page ──► align on the template ──► crop the 6 fields of each vehicle ──► enlarge ──► Qwen (12 images, one request, JSON)
                                                                                                        │
v4a record ───────────────────────────────────────────────────────────────────────────────────────► replace those fields
```
- **Geometry:** the field boxes come from the generator's `fields.VEHICLE` (PDF points, where each value is written), through
  `pipeline/marks/layout.py`, which stays the only module that imports the generator. The crop is the box plus a margin (10 px across,
  7 px down at 200 dpi) so a value that runs a little outside is kept.
- **Alignment:** the page is aligned on the template with the same ECC alignment as the marks reader (`marks/align.py`).
- **Request:** one call per form. The user message holds each crop as an image, preceded by a label (`vehicle_a plate`). The answer is
  schema-guided JSON with the six keys for each vehicle. Thinking off, temperature 0.
- **Prompt:** the format lines for these fields are shared with `VLM_SYSTEM_PROMPT` (one place), plus: copy what is written, `null` when
  unreadable.
- **Merge:** a non-empty answer replaces the page value; `null` or a failed call keeps the page value (a refinement never loses a field).
  What changed is saved in `runs/<id>/refined/<form>.json`.
- **Settings:** `REFINE_FIELDS` (comma-separated, off when unset), `refine_scale` (enlargement, 3).

## Work
```
backend/pipeline/marks/layout.py          text_fields in Layout (px boxes of the vehicle fields)
backend/pipeline/refine/                  FieldRefiner (new)
backend/pipeline/structuring/prompts.py   shared format lines, CROP_SYSTEM_PROMPT
backend/pipeline/flow/graph.py            refine node, optional, after structure and before marks
backend/pipeline/core/config.py           refine_fields, refine_scale
backend/pipeline/run.py, flow/runner.py   build it, record it in run.json
backend/tests/unit/test_refine.py         crops land where the template says, merge keeps old value on null or failure, graph wiring
docs/results-log.md, docs/pipeline.md, README, CLAUDE.md
```

## Steps
1. Implement and test with fakes. → verify: tests pass.
2. Dev run on the 5 dev forms from the saved v4a-dev5 records (`v4b-dev5`); look at what the crops read against the page read, per field.
   If a field gets worse from crops (dates, for example), drop it from `REFINE_FIELDS`. Choices are made on dev only.
3. Test run on the same 20 forms from the saved v4a records (`v4b`), once.
4. Log in `docs/results-log.md` (per-field before and after, GPU cost of the extra calls), update the docs, move this plan to `plans/done/`.

## Open
- **Real forms:** the boxes are where the generator writes. A real photo has handwriting at other places on the line, so the margin may
  need to grow. This is a baseline on synthetic forms.
- **Alignment error:** a few pixels at the ends of the page; the margin absorbs it. Crops can be checked by eye on the dev forms.
- **Dates:** the validity fields are the first to drop if crops are worse than the page.

## Result
- `v4b` on the 20 test forms (from the saved v4a records): 299 of 380 critical fields right (v4a: 222), minor 482 of 600 (unchanged), character error rate 3.7% (5.3%),
  and the first 2 forms with no critical error (0 before). Licence number 12 to 27 of 40, attestation 16 to 30, policy 18 to 31, plate 18 to 23, validity dates
  16 to 34 and 28 to 40. Of 127 changed fields, 83 became right and 6 became wrong.
- Dev run (5 forms) improved all six fields, so none was dropped. The crop step costs about $0.014 per form of GPU; v4b is about $0.043 per form.
- Full table and analysis: `docs/results-log.md`.
