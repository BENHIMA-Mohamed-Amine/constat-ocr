# v3b: sort the OCR text by column

Status: done

## Goal
v3a showed straightening alone changes little. In v2 and v3a, vehicle B's values are in the OCR text but mixed with the
circumstance lines and unlabelled, and the LLM answered `null` for 97 of them (v3a). v3b keeps the straightened photo
and the same OCR engine, and only changes how the OCR text is ordered and labelled. Same LLM, settings, forms and metrics
(`docs/metrics.md`). v3a results: `docs/results-log.md`.

| Run | Change |
|---|---|
| `v3a` (done) | PP-OCRv6 on the straightened photo, text in the engine's order |
| `v3b` | Same OCR, but each text box is assigned to a zone by position and the text is given as 4 labelled blocks |

## How
RapidOCR already returns a box for every text line; the engine keeps only the text. After straightening, the columns sit at
fixed positions, so a box's centre says which zone it is in. No second OCR pass and no image cutting (no word is sliced).

```python
# pipeline/ocr/columns.py
def find_zone_cuts(bgr) -> tuple[float, float, float]:
    """Per form, from the printed green strips: outer edge of the left strip, outer edge of the right strip, top of the strips.
    Green pixels per column in the middle of the page give two peaks; the strips frame the circumstances column
    and hold both checkbox columns, so the cuts sit on their outer edges."""

def group_by_zone(boxes, texts, width, height, cuts) -> str:
    """Four labelled blocks (header, vehicle_a, circumstances, vehicle_b), each sorted top to bottom, by box centre."""

class ColumnRapidOcrEngine(RapidOcrEngine):
    """RapidOCR, with the text grouped by zone."""
    def read(self, image_path: Path) -> OcrResult: ...   # text = group_by_zone(output.boxes, output.txts, w, h, find_zone_cuts(image))
```

```python
# pipeline/ocr/factory.py: one registry entry
@register_ocr_engine("rapidocr-v6-columns")
def _rapidocr_v6_columns(settings): return ColumnRapidOcrEngine("v6")
```

The prompt must describe the new text. The existing prompt stays as it is (v1 to v3a stay reproducible); a second prompt is
added and chosen by a setting, with the same registry pattern:

```python
# pipeline/structuring/prompts.py
PROMPTS = {"flat": SYSTEM_PROMPT, "columns": COLUMNS_SYSTEM_PROMPT}
# COLUMNS_SYSTEM_PROMPT: same as SYSTEM_PROMPT, but the "two columns, the OCR mixes them" bullet becomes:
#   "The text comes in 4 blocks: header (date, place, phones), vehicle_a (left column), circumstances (the middle list,
#    no values to extract) and vehicle_b (right column, mostly Arabic labels). Fill each vehicle from its own block."
# setting: STRUCTURING_PROMPT=columns  (default flat)
```

## Decisions
- **Off by default.** `OCR_ENGINE=rapidocr-v6-columns STRUCTURING_PROMPT=columns` turns it on, so earlier runs stay reproducible.
- **Cut points are found per form, not fixed.** The page position shifts by about 2% between forms. Checked on the 5 dev forms: both cuts on the outer edges of the green strips, header cut at the top of the strips.
- **The prompt change is part of this one change.** It only describes the new text layout; nothing else in it moves.
- **The circumstances block stays in the text** (it is mostly printed labels). Dropping it would save tokens but is a separate change.
- **Selection on dev forms only.** Test forms are run once, as `v3b`.

## Work
```
backend/pipeline/ocr/columns.py        group_by_zone, ColumnRapidOcrEngine (new)
backend/pipeline/ocr/factory.py        one registry entry
backend/pipeline/structuring/prompts.py  COLUMNS_SYSTEM_PROMPT, PROMPTS registry
backend/pipeline/core/config.py        structuring_prompt setting
backend/pipeline/run.py                pick the prompt from the setting
backend/pipeline/flow/runner.py        record the prompt name in run.json
backend/tests/unit/                    one check: boxes in known positions land in the right block, sorted top to bottom
```

## Steps
1. Done: zones drawn on the 5 dev forms and checked by eye; only the footer text crosses a cut, both phone rows are in the header.
2. Print the 4 blocks for one form and check vehicle B's values (make, plate, insurer, names) are in `vehicle_b`.
3. Run the 5 dev forms and compare with `v3a-dev5` (15 of 95 critical, 42 of 150 minor right):
   ```bash
   cd backend
   STRAIGHTENER=opencv OCR_ENGINE=rapidocr-v6-columns STRUCTURING_PROMPT=columns \
     uv run python -m pipeline.run --run-id v3b-dev5 --dev 5 --test 0
   ```
4. Run the 20 test forms as `v3b`, same command with `--run-id v3b --dev 0 --test 20`.
5. Log in `docs/results-log.md` next to v1, v2 and v3a; update the README table, `docs/pipeline.md` and `CLAUDE.md` structure.

## Result
- `v3b` on the 20 test forms: 55 of 380 critical fields right (54 for v3a), 99 of 600 minor (89), character error rate 53.2% (66.8%).
  Vehicle B text fields right: 26 of 440 (7). Vehicle A lost 8 critical fields, probably from the stricter prompt wording.
- Full table and analysis: `docs/results-log.md`.

## Done when
- `v3b` is scored on the 20 test forms and logged, with the vehicle B counts compared with v3a (0 of 180 critical right,
  97 values in the text but returned as null).
- Docs are updated and this plan is moved to `plans/done/`.

## Open
- Column crops were tried and rejected: 10% more text lines but the same answer-key values found (81 against 83 of 245 on 5 dev forms).
- What the ceiling is: 670 values were never in the OCR text, so a layout change cannot recover them.
