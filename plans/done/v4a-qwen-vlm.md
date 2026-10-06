# v4a: a general open VLM reads the page and fills the record

Status: done

## Goal
After v3e the mark fields are solved and the text is the problem: 405 of 980 text fields wrong (55% one or two characters off, 44% never
read). v4a tests one thing: replace "Chandra reads, `gpt-oss-120b` structures" with one open general vision model that reads the
straightened page and returns the record directly. Nothing is fine-tuned. Same forms, same metrics, same straightener, repair and marks
steps as v3e, so v3e (194 of 380 critical, 381 of 600 minor, character error rate 16.1%) is the number to beat.

Model: **Qwen3.8-27B** (Apache 2.0, newest open general VLM). Not yet checked: its exact HF repo id, its vLLM support and its
handwriting quality. Step 1 settles that. Fallback if it does not run: Qwen3-VL-8B or 32B.

## How
```
straightened photo ──► Qwen VLM (image + prompt, JSON out) ──► marks (v3e) ──► repair (v3d) ──► score
```
- **Serving:** `serving/deploy/qwen3_8_27b.py`, vLLM on Modal, one H100 (27B in bf16 is about 54 GB, a page is about 4,000 image tokens).
  Bigger GPU only if memory runs out. Secured with the Modal proxy token, like the Chandra server ([serving.md](../docs/serving.md#authentication)).
- **Query script:** `serving/query/qwen3_8_27b.py`, one image, one request, prints the answer and the seconds. Run it first, and run it
  without the token to check it is refused.
- **Pipeline:** `Structurer` already allows a vision model (`StructuringInput.image_path`). New `VisionStructurer`
  (`structuring/vision.py`) sends the image and a prompt to the server and parses the JSON into `Record`. The OCR step becomes a `none`
  engine (registry entry, returns empty text) so the graph is not edited.
- **Format:** the prompt carries the output instructions generated from `Record` (`output_format.py`, so it cannot drift), and the request
  asks vLLM for schema-guided output (`response_format` JSON schema), so the answer always has the right keys and types. The prompt also
  states the formats we expect: dates `DD/MM/YYYY`, plate `NNNNN-L-NN`, attestation `AAA NNNNNNNNN`, phone digits only, `null` when
  unreadable (never a guess), and "copy what is written, do not correct it" (models fix what they expect to see).
- **Thinking mode:** off for the first run, to keep latency and cost low. Open question below.
- **Settings:** `QWEN3_8_27B_SERVER_URL`, `STRUCTURER=vision`, `OCR_ENGINE=none`, `STRUCTURING_PROMPT=vlm`.

## Work
```
backend/serving/deploy/qwen3_8_27b.py     Modal + vLLM app (you type it)
backend/serving/query/qwen3_8_27b.py      one-image probe, with the token (you type it)
backend/pipeline/ocr/none.py              engine that reads nothing
backend/pipeline/ocr/factory.py           one registry entry
backend/pipeline/structuring/vision.py    VisionStructurer
backend/pipeline/structuring/prompts.py   VLM_SYSTEM_PROMPT
backend/pipeline/structuring/factory.py   one registry entry
backend/pipeline/core/config.py           server url setting
backend/tests/unit/test_vision.py         request shape, JSON parsed into Record, bad answer raises StructuringError
docs/results-log.md, docs/serving.md, docs/pipeline.md, README, CLAUDE.md
```

## Steps
1. **Deploy** the model on an H100; confirm the repo id, vLLM version and that image input works. → verify: server answers `/v1/models`.
2. **Query script** on one dev page. → verify: valid JSON back, a request with no token is refused.
3. **Wire** `VisionStructurer`, the `none` engine and the prompt, with unit tests. → verify: tests pass, one dev form runs end to end.
4. **Dev run:** 5 dev forms (`v4a-dev5`). Look at the errors by eye, fix the prompt once at most. Thresholds and prompt are set here only.
5. **Test run:** the same 20 test forms as v3e (`v4a`), once, with `--workers` and marks and repair on.
6. **Document:** v4a entry in `docs/results-log.md` (table against v3c, v3d, v3e; `analyze_run.py` and `near_misses.py` outputs; cost, time,
   GPU cost note), move this plan to `plans/done/`, update CLAUDE.md, then recap in chat.

## Metrics to report
- Critical and minor fields right, forms with no critical error, character error rate, ticks and categories (v3e's marks reader still
  fills those, so they will match v3e; say so).
- Cost: GPU seconds per form and rented-GPU cost, which the earlier tables did not include.
- Time per form, and how often the answer was not valid JSON (should be 0 with guided output).
- A guessing check: wrong values that look plausible (a name or plate that is valid but not on the form). Models rewrite what they expect, so
  count how many wrong fields are valid-looking but wrong.

## Open
- **Qwen3.8 27B:** repo id, vLLM support and image-size limits unverified.
- **Thinking mode:** may help on hard digit strings and may cost much time. Try it only as a v4b change.
- **Prompt tuning is limited to the dev forms,** one round. Anything more is v4b.
- **Later (not v4a):** a bigger or closed model (Gemini) as the upper bound, and the other ideas from the log (voting, crop re-read).
- **Licence:** Apache 2.0, so no OpenRAIL question as with Chandra; confirm on the model card.

## Result
- `v4a` on the 20 test forms: 222 of 380 critical fields right (v3e: 194), 482 of 600 minor (381), character error rate 5.3% (16.1%),
  ticks and categories 100% (the v3e reader), still 0 of 20 forms without a critical error. No LLM call; GPU about $0.029 per form warm
  (H100, $0.001097 per second), against about $0.019 for v3e (Chandra GPU $0.018 plus Groq $0.0012, estimated from the v3c files).
- Dev prompt iterations (3 runs) were within noise; the kept prompt is the round-2 text. Licence numbers (the `/` read as `1`) stay the
  weakest field (12 of 40). Full table and analysis: `docs/results-log.md`.
- Model id `Qwen/Qwen3.8-27B` and vLLM 0.30.0 worked as they were; thinking was off.
