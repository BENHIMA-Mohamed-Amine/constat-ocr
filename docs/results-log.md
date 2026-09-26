# Results log

One entry per version, newest last. Every version is scored on the same forms of the frozen dataset (see
[metrics.md](metrics.md) for the metrics and [pipeline.md](pipeline.md) for how a run works).

## v1 baseline: Tesseract, then an LLM (JSON mode)

- **What:** Tesseract (French) reads the photo; Groq `openai/gpt-oss-120b` fills the record from the OCR text only.
  No image cleanup. Run `v1`, files in `runs/v1/`.
- **Data:** the first 20 forms of the test split (`000100` to `000119`), phone level, dataset fingerprint in `runs/v1/run.json`.
  Run once. The prompt was written and checked on 2 dev forms (`runs/v1-dev`) and not changed after the test run.
- **Small sample:** 20 forms is 40 vehicles. Read the percentages as an early signal, not a precise score.

| Metric | Result | For comparison |
|---|---|---|
| Field accuracy, critical fields | **3 of 380 (0.8%)** | |
| Field accuracy, minor fields | **12 of 600 (2.0%)** | |
| Forms with no critical error | **0 of 20** | |
| Character error rate | **89%** (critical 89%, minor 89%) | |
| Ticks found / missed / extra | 0 / 25 / 10 (the 10 extra come from one vehicle) | |
| Tick count written on the form | 0 of 40 right | |
| Vehicle type | 0 of 40 | always answering "car": 88% |
| Impact zone | 0 of 40 | always answering the most common: 28% |
| Licence category | 0 of 40 | always answering "B": 88% |
| Other damage (yes/no) | 2 of 20 | always answering "no": 95% |
| Cost | **$0.0009 per form** ($0.019 for the 20 forms; 60,493 tokens in, 16,123 out) | |
| Time | 23 s per form on average, slowest 5% 30 s | see the note below |

**Time note.** The 23 seconds include waiting for Groq's free-plan limit (8,000 tokens a minute): 11 rate-limit retries in
this run. The model call itself took about 2.5 s in the dev run and Tesseract about 2.3 s, so about 5 s of real work per form.

### Where the errors come from

For each wrong text field: is the answer-key value anywhere in the OCR text? (`runs/v1/failures.json`)

| | Fields | Value never in the OCR text | In the text, no value returned | In the text, wrong value returned | Correct |
|---|---|---|---|---|---|
| Critical, top level | 20 | 20 | 0 | 0 | 0 |
| Critical, vehicle A | 180 | 178 | 1 | 0 | 1 |
| Critical, vehicle B | 180 | 165 | 12 | 1 | 2 |
| Minor, top level | 80 | 78 | 0 | 1 | 1 |
| Minor, vehicle A | 260 | 227 | 18 | 6 | 9 |
| Minor, vehicle B | 260 | 221 | 36 | 1 | 2 |
| **All text fields** | **980** | **889** | **67** | **9** | **15** |

- **The OCR is the bottleneck.** 889 of the 965 wrong values (92%) were never in the OCR text, so no LLM could have got them
  right. The LLM lost 76 (8%): 67 values it did not return and 9 wrong picks.
- **Vehicle B is nearly unreadable to it.** The right column has mostly Arabic labels and its handwriting is not recognised.
  Vehicle B gets 2.6 of 27 fields filled on average against 9.6 for vehicle A. Some of those are wrong.
- **The 15 correct values** are mostly the vehicle make (6 of 40) and single hits on plate, insurer, licence number and names.
- **What no text-only pipeline can do:** ticks, circled letters, the highlighted vehicle type, the impact zone and the sketch
  are pictures. Those metrics are near zero by design, and they sit far below the "always guess" scores.
- **The LLM step behaves.** No form failed. One model quirk showed up during the build: in strict JSON-schema mode the model
  wrapped its answer inside the schema's own keys, and the schema silently ignored it, giving an empty record. The switch to JSON
  mode with generated output instructions, and a check that rejects an empty record, came from that.

### What this says about v2
- **Fix the reading first.** Better OCR of tilted phone photos and of the Arabic-labelled column is worth far more than a
  better model on the text.
- **A vision model** reads the ticks, the highlighted tile and the impact zone directly: exactly the fields v1 cannot see.
- **Then measure again on the same 20 forms** (and more of the 500 if the provider limits allow), so v2 is compared with this
  row and not with a new sample.

### Reproduce

```bash
cd ~/projects/constat-ocr/backend && uv run python -m pipeline.run --run-id v1 --dev 0 --test 20
```
