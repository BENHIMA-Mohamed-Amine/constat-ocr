# v3c: Chandra-OCR-2 reads the page

Status: done

## Goal
v3b showed the ceiling is the reading: 676 of 980 values were never in the OCR text. v3c replaces the OCR engine with an OCR vision
model that can read handwriting, and changes nothing else: same straightened photo, same `gpt-oss-120b`, same forms and metrics.
Chandra-OCR-2 (Datalab, 5.3B) is served on Modal with vLLM on an H100 (`backend/serving/`).

Why Chandra: on one dev page it found 28 of 49 answer-key values against 18 for RapidOCR, it read vehicle B, and it returned the
ticked boxes. PaddleOCR-VL and DeepSeek-OCR-2 were tried first and dropped: they are built for printed pages and fell into
loops on the handwritten form (they read the header, then repeated text until the token cap).

## How
```
straightened photo ──► Chandra (HTML, one div per block, each with a bbox) ──► blocks sorted into 4 zones ──► LLM
```
- **`pipeline/ocr/chandra.py`**: `ChandraOcrEngine`. Sends the page and Datalab's `ocr_layout` prompt to the server, regenerates at a
  higher temperature when the answer ends in a repeated pattern (Datalab's own client does this, a loop was seen on the H100), then
  turns the HTML into text: `[x]` and `[ ]` for checkboxes, `(x)` for a circled radio, `[image: ...]` for picture descriptions.
- **Zones:** each block goes to header, vehicle A, circumstances or vehicle B by the centre of its bbox, with the per-form cuts of
  v3b (`find_zone_cuts`). The grouping code of v3b is reused, not copied.
- **Prompt:** `chandra`, the `columns` prompt with two bullets replaced: the circumstances block now holds ticks, and the text now
  marks ticked boxes and describes pictures.
- **Settings:** `CHANDRA_OCR_2_SERVER_URL` (one variable per model), engine name `chandra-ocr-2`, `STRUCTURING_PROMPT=chandra`.
- **Runner:** `--workers N` processes forms in parallel (default 1, so earlier runs are unchanged). At 25 to 55 s per page, one
  form at a time would take most of an hour.

## Work
```
backend/pipeline/ocr/chandra.py          ChandraOcrEngine, repeat check, HTML to zone text (new)
backend/pipeline/ocr/factory.py          one registry entry
backend/pipeline/core/config.py          chandra_ocr_2_server_url
backend/pipeline/structuring/prompts.py  CHANDRA_SYSTEM_PROMPT
backend/pipeline/flow/runner.py          workers
backend/pipeline/run.py                  --workers
backend/tests/unit/test_chandra.py       repeat check, HTML parsing and zones, request and retry, prompt
```

## Steps
1. Implement and test with fakes.
2. Run the 5 dev forms (`v3c-dev5`) and the 20 test forms (`v3c`) at the same time, as two runs with `--workers`.
3. Rerun with `--reuse` to finish any form where the free Groq plan's rate limit stopped the LLM step; the OCR output is reused.
4. Log in `docs/results-log.md` next to v1, v2, v3a and v3b, including the two rejected models; update the README, `docs/pipeline.md`,
   `docs/testing.md`, `CLAUDE.md`.

## Result
- `v3c` on the 20 test forms: 168 of 380 critical fields right (v3b: 55), 377 of 600 minor (99), character error rate 16.8% (53.2%),
  ticks found 10 of 25 (0). Vehicle B text fields right: 200 of 440 (26). Still 0 of 20 forms without a critical error.
- 8 forms needed the `--reuse` pass because of the Groq rate limit. Full table and analysis: `docs/results-log.md`.

## Open
- The licence of the weights is OpenRAIL: read its terms before treating this as the final choice for a company.
- Vehicle B's checkboxes were not in the HTML on the L4 run; the ticks the model returns are probably vehicle A's only.
- Results differ between GPUs (an L4 run finished, an H100 run looped), so one run is weak evidence.
