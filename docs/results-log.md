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

- **The provider is a limit too.** The free plan's rate limits stretched a 20-form run to about 8 minutes and rule out high volume,
  and sending form text to a hosted API gives up control of where the data is processed. Both are fine for synthetic data and not
  for real claims. The model is open-weight, so a later version can compare a self-hosted deployment (cost, latency, concurrency,
  residency) against the hosted one.

### Reproduce

```bash
cd ~/projects/constat-ocr/backend && OCR_ENGINE=tesseract uv run python -m pipeline.run --run-id v1 --dev 0 --test 20
```

## v2: PP-OCRv6 on CPU, same LLM

- **What:** the OCR engine changes and nothing else. PP-OCRv6 (small models, French) through RapidOCR on ONNX Runtime replaces
  Tesseract. Same `openai/gpt-oss-120b`, same prompt, same settings, same 20 test forms (`000100` to `000119`). Run `v2`,
  files in `runs/v2/`, engine name in `runs/v2/run.json`.
- **Why this engine:** picked on the dev forms, then run once on the test forms. See the next section.
- **Small sample:** 20 forms is 40 vehicles. Read the percentages as an early signal, not a precise score.

### Choosing the engine: 5 dev forms

Candidates: the CPU engines shortlisted in [the v2 plan](../plans/done/v2-cpu-ocr.md), run on the first 5 dev forms (`000000` to
`000004`) with the v1 prompt. Runs `v2-dev5-*`. Ordered by critical fields right.

| Rank | OCR engine | Critical fields right (of 95) | Minor fields right (of 150) | Character error rate | OCR seconds per form |
|---|---|---|---|---|---|
| 1 | **PP-OCRv6 (RapidOCR)** | **17** | **34** | **65.4%** | 4.1 |
| 2 | PP-OCRv5 (RapidOCR) | 6 | 19 | 72.8% | 5.3 |
| 3 | docTR | 4 | 9 | 82.1% | 1.9 |
| 4 | Tesseract (v1) | 1 | 7 | 87.3% | 4.4 |

- **The public benchmark did not predict the winner.** The shortlist came from OmniDocBench (page-level text recognition,
  English edit distance, lower is better): PaddleOCR 0.071 against Tesseract 0.096. It only covers the older PaddleOCR models,
  not v6, and its pages are not handwritten French forms. It was good enough to build a shortlist and not to pick from it.
- **No engine got a form fully right.** Every engine had 0 of 5 forms with no critical error.
- **Timing is noisy.** Tesseract took 4.4 s per form in this run and 2.2 s in the v1 run, on the same machine, so read the
  seconds column as a rough guide only.

### v2 results (20 test forms)

| Metric | v1 (Tesseract) | v2 (PP-OCRv6) | For comparison |
|---|---|---|---|
| Field accuracy, critical fields | 3 of 380 (0.8%) | **56 of 380 (14.7%)** | |
| Field accuracy, minor fields | 12 of 600 (2.0%) | **88 of 600 (14.7%)** | |
| Forms with no critical error | 0 of 20 | **0 of 20** | |
| Character error rate | 89.1% | **70.1%** (critical 65.8%, minor 72.8%) | |
| Ticks found / missed / extra | 0 / 25 / 10 | 1 / 24 / 12 | |
| Tick count written on the form | 0 of 40 right | 0 of 40 right | |
| Vehicle type | 0 of 40 | 0 of 40 | always answering "car": 88% |
| Impact zone | 0 of 40 | 0 of 40 | always answering the most common: 28% |
| Licence category | 0 of 40 | 0 of 40 | always answering "B": 88% |
| Other damage (yes/no) | 2 of 20 | 0 of 20 | always answering "no": 95% |
| Cost | $0.0009 per form | $0.0010 per form (51,344 tokens in, 21,271 out) | |
| OCR time | 2.2 s per form | 4.2 s per form | see the note below |
| Total time | 23.1 s per form, slowest 5% 30.2 s | 19.6 s per form, slowest 5% 29.1 s | see the note below |

**Time note.** Total time includes waiting for Groq's free-plan limit (8,000 tokens a minute), so it says little about the
engine. The OCR seconds are the fair comparison: PP-OCRv6 is about 2 s slower per form on this CPU. Cost per form is about the same
($0.0009 against $0.0010): the OCR is free and the LLM step is unchanged.

### Where the errors come from

For each wrong text field: is the answer-key value anywhere in the OCR text? (counts from `scripts/analyze_run.py v2`.)

| | Fields | Value never in the OCR text | In the text, no value returned | In the text, wrong value returned | Correct |
|---|---|---|---|---|---|
| Critical, top level | 20 | 12 | 0 | 0 | 8 |
| Critical, vehicle A | 180 | 125 | 2 | 8 | 45 |
| Critical, vehicle B | 180 | 148 | 26 | 3 | 3 |
| Minor, top level | 80 | 45 | 5 | 6 | 24 |
| Minor, vehicle A | 260 | 159 | 19 | 22 | 60 |
| Minor, vehicle B | 260 | 184 | 64 | 8 | 4 |
| **All text fields** | **980** | **673** | **116** | **47** | **144** |

- **Better reading, same bottleneck.** The share of wrong values that were never in the OCR text fell from 92% (v1) to 81%
  (673 of 836). The reader is still the main limit.
- **Vehicle B is still the problem.** It gets 7 of 440 text fields right, against 105 of 440 for vehicle A. For vehicle B, 332 of
  440 values are missing from the text, and in 90 more cases the value is in the text but the LLM returned nothing.
  A likely cause is that the two columns are read line by line and interleaved, so the model cannot tell which line belongs
  to which vehicle. That is a guess: the OCR text has not been checked for it yet.
- **The LLM lost more than in v1.** 163 values (116 not returned, 47 wrong) were in the OCR text and still went wrong, against
  76 in v1. There is more text to work with now, and the model is less sure where each value belongs.
- **What no text-only pipeline can do has not changed.** Ticks, the highlighted vehicle type, the impact zone and the sketch
  are pictures. Those metrics stay at zero and far below the "always guess" scores.
- **No form failed.** All 20 forms produced output.

### What this says about v3
- **A better CPU reader helps but is not enough.** Critical fields went from 0.8% to 14.7%, and no form is fully right.
- **Layout is the next cheap thing to test.** If the two columns are interleaved in the OCR text, giving the reader the column
  boundaries (or reading each column on its own) should lift vehicle B without changing the model.
- **A vision model** reads the ticks, the highlighted tile and the impact zone directly. That is still the only route to the
  fields that no OCR text contains.

### Reproduce

```bash
cd ~/projects/constat-ocr/backend && uv run python -m pipeline.run --run-id v2 --dev 0 --test 20
```
