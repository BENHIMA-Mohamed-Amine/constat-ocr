# v3e: read the ticks, tiles and circles from the template

Status: done

## Goal
Chandra gave ticks for the first time in v3c, but the mark fields were still poor after the LLM: ticks 10 found of 25 (15 missed, 4 extra),
tick count 4 of 40, vehicle type 12 of 40, licence category 2 of 40, impact zone 4 of 40, other damage 8 of 20. The form is a fixed template,
so these marks are measurements at known places, not a reading problem. v3e adds one optional step after the LLM that reads them with plain
image processing (no model, no GPU, no LLM) and puts them in the record. Nothing else changes, and the v3d outputs are reused.

## How
- **Geometry from the template:** the checkbox squares, the picture frames and the licence-letter positions come from the blank template PDF
  (defined once in `generator/`, imported by one module, `pipeline/marks/layout.py`).
- **Alignment:** the straightened page is aligned on the template (ECC homography on the printed content), then every checkbox and the
  licence-letter row is placed on its own printed square by template matching, since the page alignment is a few pixels off at one end.
- **Readings:** ink in a box (a pixel darker than the blank template), colour in the vehicle-type tile, ink on a ring around the licence
  letters, the zone rectangle that best matches the blue patch on the impact picture, ink in the OUI or NON cells. The tick count is the
  number of ticks.
- **Thresholds on the dev forms only;** the held-out test forms were read once.

## Work
```
backend/pipeline/marks/              layout.py, align.py, reader.py (MarksReader, Marks) (new)
backend/pipeline/flow/graph.py       marks node, optional, before repair
backend/pipeline/core/config.py      read_marks setting
backend/pipeline/run.py              build the reader from the setting
backend/scripts/eval_marks.py        accuracy of the reader on a whole split, no LLM or GPU
backend/tests/unit/test_marks.py     rendered forms read back exactly, fields replaced, graph wiring
```

## Result
- Reader alone, 400 held-out test forms: ticks 542 of 542 found, 0 missed, 0 extra; tick count, vehicle type, licence category and impact
  zone 800 of 800 each; other damage 400 of 400. On the 100 dev forms (where the thresholds were set): all marks 100%.
- In the pipeline, 20 test forms from the v3d outputs: ticks 10 / 15 / 4 to 25 / 0 / 0, tick count 4 to 40 of 40, vehicle type 12 to 40,
  licence category 2 to 40, impact zone 4 to 40, other damage 8 to 20 of 20. The text fields are unchanged.
- About 0.7 s per form on a CPU. Full table and caveats: `docs/results-log.md`.
