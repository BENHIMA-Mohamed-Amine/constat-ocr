# v4c: crop the remaining fields (last iteration of v4)

Status: done

## Goal
v4b took the six digit fields from the page read to crops and critical fields went from 222 to 299 of 380; the minor fields (names, addresses, makes,
agencies, licence dates) did not move, 482 of 600. v4c puts every other written field through the same crop step. Same server, same step, same saved v4a
records, so the new fields are the only difference. This is the last iteration of v4: no bigger model, no fine-tuning.

## How
- **Vehicle fields:** `REFINE_FIELDS` already takes any field of `generator/fields.VEHICLE`: model, make, coming_from, going_to, the insured and driver
  names and addresses, insurer, agency, licence issue date, prefecture and validity. Measured first on the 5 dev forms with no code change.
- **Header and damage:** the date, time, place and two phones (`fields.HEADER`, `PHONE_B`) and each vehicle's damage text (`fields.DAMAGE`) have their own
  boxes. `marks/layout.py` gets them (`header_fields`, and `damage` in `text_fields`), and the refiner asks for a `header` object next to
  `vehicle_a` and `vehicle_b`.
- **Choice on dev only:** a field that gets worse on the dev forms is dropped from `REFINE_FIELDS`; the six fields of v4b stay.

## Work
```
backend/pipeline/marks/layout.py       header_fields, damage in text_fields
backend/pipeline/refine/reader.py      header crops and the header object of the answer; larger answer cap
backend/tests/unit/test_refine.py      header and damage crops, header merge
docs/results-log.md, README.md, docs/pipeline.md, CLAUDE.md
```

## Steps
1. Dev run with all vehicle fields (no code). → verify: per-field accuracy against `v4a-dev5-p2`.
2. Add header and damage, dev run again. Drop any field that is worse.
3. Test run on the 20 forms from the saved v4a records (`v4c`), once.
4. Document, move this plan to `plans/done/`.

## Open
- **Long texts** (addresses, damage) are free text: a crop cannot fix a word the handwriting makes ambiguous, and the model may "correct" it. The
  dev run shows whether crops help on text as they do on digits.
- **Cost:** about 40 crops per form instead of 12, so the step costs more GPU than the $0.014 per form of v4b.

## Result
- `v4c` on the 20 test forms (22 fields cropped, from the saved v4a records): 315 of 380 critical (v4b: 299), 501 of 600 minor (482), text fields 816 of 980, character error rate 2.5%
  (3.7%), 4 forms with no critical error (2). Five fields were dropped on dev because crops were worse than the page (insured and driver address, driver first name, place, licence
  prefecture).
- The first test pass was invalid: 8 forms had their crop call fail on network and 502 and 503 errors while the container restarted. The refiner now retries 3 times and does not save a
  failed refinement; the 8 forms were rerun on a warm server. Details in `docs/results-log.md`.
