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

## v3a: straighten the photo, then the same pipeline

- **What:** one step is added before OCR. `OpenCvStraightener` finds the page against the desk and warps it flat, so the OCR
  engine reads an upright, cropped page. Same PP-OCRv6, same `openai/gpt-oss-120b`, same prompt, same settings, same 20 test
  forms (`000100` to `000119`). Run `v3a`, files in `runs/v3a/` (the straightened images are in `runs/v3a/straightened/`,
  not committed). `runs/v3a/run.json` records `"straightener": "opencv"`.
- **Why:** v2 read the photo as it was, tilted and angled. Straightening is the first change, and the column split of the next
  run needs it. On its own it tests whether the tilt was holding the OCR back.
- **Dev check:** on the first 5 dev forms, 15 of 95 critical fields right against 17 for v2, and 42 of 150 minor fields against
  34. Character error rate 65.4% for both. No gain on 5 forms.
- **Small sample:** 20 forms is 40 vehicles. A difference of 2 fields is noise.

### v3a results (20 test forms)

| Metric | v2 (PP-OCRv6) | v3a (straightened) | For comparison |
|---|---|---|---|
| Field accuracy, critical fields | 56 of 380 (14.7%) | **54 of 380 (14.2%)** | |
| Field accuracy, minor fields | 88 of 600 (14.7%) | **89 of 600 (14.8%)** | |
| Forms with no critical error | 0 of 20 | **0 of 20** | |
| Character error rate | 70.1% (critical 65.8%, minor 72.8%) | **66.8%** (critical 63.7%, minor 68.6%) | |
| Ticks found / missed / extra | 1 / 24 / 12 | 0 / 25 / 0 | the 12 extra in v2 came from one vehicle |
| Tick count written on the form | 0 of 40 right | 0 of 40 right | |
| Vehicle type | 0 of 40 | 0 of 40 | always answering "car": 88% |
| Impact zone | 0 of 40 | 0 of 40 | always answering the most common: 28% |
| Licence category | 0 of 40 | 0 of 40 | always answering "B": 88% |
| Other damage (yes/no) | 0 of 20 | 0 of 20 | always answering "no": 95% |
| Cost | $0.0010 per form | $0.0010 per form (51,601 tokens in, 22,037 out) | |
| OCR time | 4.2 s per form | 3.9 s per form | straightening time is not measured separately |
| Total time | 19.6 s per form, slowest 5% 29.1 s | 23.9 s per form, slowest 5% 29.0 s | includes waiting for Groq's free-plan limit, so it says little about the step |

### Where the errors come from

Same method as v2 (`scripts/analyze_run.py v3a`): is the answer-key value anywhere in the OCR text?

| | Fields | Value never in the OCR text | In the text, no value returned | In the text, wrong value returned | Correct |
|---|---|---|---|---|---|
| Critical, top level | 20 | 11 | 0 | 0 | 9 |
| Critical, vehicle A | 180 | 124 | 1 | 10 | 45 |
| Critical, vehicle B | 180 | 146 | 32 | 2 | 0 |
| Minor, top level | 80 | 45 | 2 | 10 | 23 |
| Minor, vehicle A | 260 | 160 | 13 | 28 | 59 |
| Minor, vehicle B | 260 | 184 | 65 | 4 | 7 |
| **All text fields** | **980** | **670** | **113** | **54** | **143** |

- **Straightening alone changes almost nothing.** Correct text fields: 143 of 980, against 144 in v2. Values never in the OCR
  text: 670, against 673.
- **The only visible gain is the character error rate,** 70.1% to 66.8%. Field counts are flat, and the other differences
  (54 against 56 critical fields, ticks) are within noise on 20 forms.
- **The OCR engine was already coping with the tilt.** The unread values are mostly handwriting the engine misreads, not
  geometry.
- **Vehicle B is unchanged.** 0 of 180 critical fields right (3 in v2). In 97 cases the value is in the OCR text and the model
  returned nothing (32 critical, 65 minor), as in v2.
- **No form failed.** All 20 forms produced output, and the page was found on every form.
- **Ticks, vehicle type and impact zone stay at zero,** as for any text-only pipeline.

### What this says about v3b
- **Straightening is a prerequisite, not a fix.** It leaves the form upright with the columns at fixed positions, which the
  column split needs.
- **The next change is the layout.** Vehicle B's values are in the text but unlabelled and mixed with the circumstance lines.
  Reading each column on its own and giving the model labelled blocks targets those 97 values.
- **The ceiling is limited.** 670 values were never in the OCR text, so a layout change cannot recover them.

### Reproduce

```bash
cd ~/projects/constat-ocr/backend && STRAIGHTENER=opencv uv run python -m pipeline.run --run-id v3a --dev 0 --test 20
```

## v3b: the OCR text sorted by zone of the form

- **What:** the straightened photo is read by the same PP-OCRv6, but each text box is assigned to a zone by the position of its
  centre and the text is given to the model as four labelled blocks: `header`, `vehicle_a`, `circumstances`, `vehicle_b`.
  The cuts are found per form from the two printed green strips (outer edges, so both checkbox columns stay with the
  circumstances), and the header ends where the strips start. The prompt is the v1 prompt with the one bullet about mixed
  columns replaced by a description of the four blocks. Same `openai/gpt-oss-120b`, same settings, same 20 test forms
  (`000100` to `000119`). Run `v3b`, files in `runs/v3b/`. `runs/v3b/run.json` records the straightener and the prompt name.
- **Why:** in v3a, 97 of vehicle B's values were in the OCR text but the model returned nothing, because the two columns were
  mixed in one stream and the Arabic labels were not read. This run gives the model the columns apart.
- **Zones checked by eye** on the 5 dev forms: only the footer text crosses a cut, and both phone rows are in the header.
- **Column crops were tried and not used.** Reading each column as its own image found 10% more text lines but the same
  number of answer-key values (81 against 83 of 245 on the 5 dev forms), so the page is read once.
- **Dev check:** on the first 5 dev forms, 17 of 95 critical fields right against 15 for v3a, 40 of 150 minor against 42, and a
  character error rate of 54.4% against 65.4%.
- **Small sample:** 20 forms is 40 vehicles. Read the percentages as an early signal, not a precise score.

### v3b results (20 test forms)

| Metric | v2 | v3a | v3b (zone blocks) | For comparison |
|---|---|---|---|---|
| Field accuracy, critical fields | 56 of 380 (14.7%) | 54 of 380 (14.2%) | **55 of 380 (14.5%)** | |
| Field accuracy, minor fields | 88 of 600 (14.7%) | 89 of 600 (14.8%) | **99 of 600 (16.5%)** | |
| Forms with no critical error | 0 of 20 | 0 of 20 | **0 of 20** | |
| Character error rate | 70.1% | 66.8% | **53.2%** (critical 59.4%, minor 49.4%) | |
| Ticks found / missed / extra | 1 / 24 / 12 | 0 / 25 / 0 | 0 / 25 / 0 | |
| Tick count written on the form | 0 of 40 right | 0 of 40 right | 0 of 40 right | |
| Vehicle type, impact zone, licence category | 0 | 0 | 0 | always guessing the most common: 88%, 28%, 88% |
| Cost | $0.0010 per form | $0.0010 per form | $0.0011 per form (52,511 tokens in, 22,801 out) | |
| OCR time | 4.2 s per form | 3.9 s per form | 4.3 s per form | |
| Total time | 19.6 s per form | 23.9 s per form | 23.9 s per form, slowest 5% 31.5 s | includes waiting for Groq's free-plan limit |

### Where the errors come from

Same method as before (`scripts/analyze_run.py v3b`): is the answer-key value anywhere in the OCR text?

| | Fields | Value never in the OCR text | In the text, no value returned | In the text, wrong value returned | Correct |
|---|---|---|---|---|---|
| Critical, top level | 20 | 11 | 0 | 0 | 9 |
| Critical, vehicle A | 180 | 131 | 3 | 9 | 37 |
| Critical, vehicle B | 180 | 146 | 14 | 11 | 9 |
| Minor, top level | 80 | 46 | 2 | 14 | 18 |
| Minor, vehicle A | 260 | 158 | 6 | 32 | 64 |
| Minor, vehicle B | 260 | 184 | 40 | 19 | 17 |
| **All text fields** | **980** | **676** | **65** | **85** | **154** |

- **The split helped vehicle B.** Correct text fields went from 7 of 440 (v3a) to 26 of 440, nearly four times as many. Values
  that were in the text but returned as nothing fell from 97 to 54. Values returned wrong rose from 6 to 30: the model now
  tries, and sometimes misreads.
- **Vehicle B is still mostly unread.** 330 of its 440 values are not in the OCR text, exactly as in v3a. 26 of 440 is 6%.
- **Character error rate fell 13.6 points** (66.8% to 53.2%), the largest change of any version since v2. Values now land in
  the right vehicle's fields, so far fewer characters are wrong.
- **The critical total barely moved** (55 against 54) because vehicle A lost what vehicle B gained: 37 critical fields right
  against 45. The OCR text did not lose these values (only 1 of 1,580 checked values left the text, 2 entered it).
  In v3a the model had got 16 vehicle A critical values right although the exact value was not in the OCR text (it repaired a
  misread date, or filled an end date); in v3b only 9 of those 16 are right. The likely cause is the new prompt wording, "if a
  value is missing from its block, use null", which makes the model more careful. This is a guess: the prompt change and the
  layout change were made together, so this run cannot separate them.
- **Ticks, vehicle type and impact zone stay at zero,** as for any text-only pipeline.
- **No form failed.** All 20 forms produced output, and both green strips were found on every form.

### What this says about the next version
- **The layout was a real problem, but a small one.** Fixing it moves vehicle B from 7 to 26 right and the character error
  rate by 13 points, not the headline critical count.
- **The ceiling is the reading.** 676 of 980 values are not in the OCR text, so grouping cannot recover them. The next gain
  must come from a better handwriting reader: an OCR vision model, or a general vision model.
- **One cheap test left on this version:** relax the "use null" rule of the new prompt, to see whether vehicle A's 8 lost
  critical fields come back.

### Reproduce

```bash
cd ~/projects/constat-ocr/backend && STRAIGHTENER=opencv OCR_ENGINE=rapidocr-v6-columns STRUCTURING_PROMPT=columns \
  uv run python -m pipeline.run --run-id v3b --dev 0 --test 20
```

## v3c: Chandra-OCR-2 reads the page

- **What:** the OCR engine is replaced by an OCR vision model, **Chandra-OCR-2** (Datalab, 5.3B), served on Modal with vLLM 0.30.0
  on an H100 (`backend/serving/`, see [serving.md](serving.md)). It gets the straightened photo and Datalab's `ocr_layout` prompt and
  answers in HTML, one block per layout region, each with a bounding box. The blocks are sorted into the four zones of v3b by the
  centre of their box, checkboxes are kept as `[x]` and `[ ]`, a circled letter as `(x)`, and the description of a picture as
  `[image: ...]`. If an answer ends in a loop, the engine regenerates it warmer (0.2, 0.4 and so on), as Datalab's own client does.
  The prompt is the v3b prompt with two sentences changed, because the text now contains ticks and pictures. Same
  `openai/gpt-oss-120b`, same settings, same 20 test forms (`000100` to `000119`). Run `v3c`, files in `runs/v3c/`; the dev run
  is `v3c-dev5`.
- **Why:** v3b showed the ceiling was the reading (676 of 980 values never in the OCR text). v3c changes only the reader.
- **Small sample:** 20 forms is 40 vehicles, and one run of each version. Read the percentages as an early signal.

### Models that were tried first and dropped
Public rankings put these OCR vision models at the top, but those rankings score printed pages. Both were tested on dev form
`000000` (straightened) and neither was good enough to continue. The comparison is the number of answer-key values that
appear in the output text (of 49, strict match).

| Model | Setup | Result on the form |
|---|---|---|
| RapidOCR PP-OCRv6 (v3a, for comparison) | CPU, 4 s | 18 of 49 values found |
| PaddleOCR-VL 1.5 (GGUF) | CPU, llama.cpp (Ollama could not load it), 151 s | 11 of 49. Read the header, then repeated `NON` until the token cap |
| DeepSeek-OCR | CPU, Ollama build, 29 min | 10 of 49. Read the header and vehicle A, never vehicle B, then repeated a paragraph |
| PaddleOCR-VL-1.6 | GPU (L4), vLLM, 18 s | Read the header, then repeated `Véhicule B` until the token cap |
| DeepSeek-OCR-2 | GPU (L4), vLLM, with its repetition guard, 30 s | Header and some of vehicle A, then invented text (a made-up numbered list) until the token cap |
| **Chandra-OCR-2** | GPU (L4), vLLM, 200 s (H100: 54 s for a looped answer) | **28 of 49**, including 8 of vehicle B's 22, and it read the ticks |

- **Conclusion:** PaddleOCR-VL and DeepSeek-OCR were built for printed documents and failed on a dense, handwritten, bilingual form
  with the whole page as input. They were not pursued further. One untested guess: their default image size is about 1 megapixel,
  and our page is 4, so the handwriting may have been shrunk too far. Chandra keeps pages up to 6.3 megapixels.
- **Only one page was scored for these tests,** so this is a reason to choose, not a measurement of each model.

### Serving it
- **Speed is set by memory bandwidth.** Generating a token reads all the weights, so tokens per second is about bandwidth divided
  by weight size. On an L4 (300 GB/s, 10.6 GB of weights) that predicts 28 tokens per second, and 27.7 was measured: 200 s for a
  5,537-token page. On an H100 it measured 221 tokens per second (12,000 tokens in 54 s), 8 times faster.
- **The same page gave different text on the two GPUs** (the L4 run finished, the H100 run fell into a loop on the Arabic letters of
  a licence row). Different hardware rounds differently, and over thousands of tokens one different choice changes the rest.
  So a single run is weak evidence, and the loop retry is needed.
- **Loops:** 5 regenerations in 25 pages (form `000103` needed 2).
- **Throughput:** the runs used 5 and 8 parallel workers against one H100 container. OCR took 55 s per form on average (median 52 s,
  slowest 158 s), measured while 13 pages shared the GPU, so it is not the latency of a single page. The throughput test that would
  choose `--max-num-seqs` has not been run.

### v3c results (20 test forms)

| Metric | v2 | v3a | v3b | v3c (Chandra) |
|---|---|---|---|---|
| Field accuracy, critical fields | 56 of 380 (14.7%) | 54 (14.2%) | 55 (14.5%) | **168 of 380 (44.2%)** |
| Field accuracy, minor fields | 88 of 600 (14.7%) | 89 (14.8%) | 99 (16.5%) | **377 of 600 (62.8%)** |
| Forms with no critical error | 0 of 20 | 0 | 0 | **0 of 20** |
| Character error rate | 70.1% | 66.8% | 53.2% | **16.8%** (critical 17.5%, minor 16.3%) |
| Ticks found / missed / extra | 1 / 24 / 12 | 0 / 25 / 0 | 0 / 25 / 0 | **10 / 15 / 4** |
| Tick count written on the form | 0 of 40 | 0 | 0 | 4 of 40 |
| Vehicle type | 0 of 40 | 0 | 0 | 12 of 40 (always "car": 88%) |
| Impact zone | 0 of 40 | 0 | 0 | 4 of 40 (always the most common: 28%) |
| Licence category | 0 of 40 | 0 | 0 | 2 of 40 (always "B": 88%) |
| Other damage (yes/no) | 0 of 20 | 0 | 4 | 8 of 20 (always "no": 95%) |
| Cost of the LLM step | $0.0010 per form | $0.0010 | $0.0011 | $0.0012 per form (64,990 tokens in, 22,844 out) |
| OCR step | 4.2 s per form | 3.9 s | 4.3 s | 55 s per form on an H100, 13 pages in parallel |

- **The dev check agrees:** on the first 5 dev forms, 43 of 95 critical fields right (v3b: 17), 99 of 150 minor (40), character error
  rate 9.9% (54.4%).
- **The GPU cost is not in the table.** Chandra runs on rented GPU time, which the per-form cost does not include.

### Where the errors come from

Same method as before (`scripts/analyze_run.py v3c`): is the answer-key value anywhere in the OCR text?

| | Fields | Value never in the OCR text | In the text, no value returned | In the text, wrong value returned | Correct |
|---|---|---|---|---|---|
| Critical, top level | 20 | 9 | 0 | 0 | 11 |
| Critical, vehicle A | 180 | 79 | 0 | 5 | 96 |
| Critical, vehicle B | 180 | 92 | 2 | 25 | 61 |
| Minor, top level | 80 | 17 | 0 | 4 | 59 |
| Minor, vehicle A | 260 | 72 | 0 | 9 | 179 |
| Minor, vehicle B | 260 | 108 | 6 | 7 | 139 |
| **All text fields** | **980** | **377** | **8** | **50** | **545** |

- **The reader was the ceiling, and it moved.** Values never in the text fell from 676 (v3b) to 377, and correct text fields rose from
  154 to 545 of 980 (55.6%).
- **Vehicle B is read now.** 200 of its 440 text fields are right, against 26 in v3b. Vehicle A: 275 of 440, against 101.
- **The LLM is no longer the problem.** Only 8 values were in the text and not returned, and 50 were returned wrong.
- **Weakest fields (of 40):** attestation number 4, attestation start date 9, damage text 9, licence number 10, plate 15, policy
  number 17. These are long digit strings and free handwriting. **Strongest:** licence prefecture 32, licence expiry 32, make 29,
  insured last name 29, first names 28, licence issue date 28.
- **Ticks are read for the first time:** 10 of 25 found, 15 missed, 4 extra. The ticks the model returns are probably vehicle A's
  only (vehicle B's boxes were not in the HTML on the single page checked).
- **The category answers are worse than guessing the most common value** (vehicle type 12 of 40 against 88% for "car", licence
  category 2 of 40, other damage 8 of 20 against 95%). The prompt change that lets the model use the text for these fields has not
  been tuned, and it answers too often when unsure.
- **Still no form without a critical error** (0 of 20), so nothing could go through without a human.
- **No form failed in the end.** In the first pass 8 forms hit the free Groq plan's rate limit in the LLM step (one request is
  about 4,500 tokens against a limit of 8,000 a minute, with 13 forms in flight). They were rerun with `--reuse`, which reuses the
  saved Chandra text, so the GPU was called once per page.

### What this says about the next version
- **Reading was the bottleneck, and a handwriting-capable model fixes most of it:** critical fields went from 14.5% to 44.2%
  and the character error rate from 53.2% to 16.8%.
- **The next gains are in the long digit strings** (plates, policy, attestation and licence numbers) and in the category fields.
  Candidates: re-read those regions at higher resolution from the bounding boxes, validate formats and dates with the consistency
  rules the generator already follows, and fix the category prompt.
- **Before treating Chandra as the final choice:** read the OpenRAIL licence terms for company use, run the throughput test, and
  compare a general vision model (Gemini, GPT or Qwen3.8) as the upper bound.
- **Hosting:** an H100 makes a page about 8 times faster than an L4 here, but the cost per page and the cost of a mostly idle GPU
  still have to be measured.

### Reproduce

```bash
cd ~/projects/constat-ocr/backend && STRAIGHTENER=opencv OCR_ENGINE=chandra-ocr-2 STRUCTURING_PROMPT=chandra \
  uv run python -m pipeline.run --run-id v3c --dev 0 --test 20 --workers 8
```
Needs the Modal app of `serving/deploy/chandra_ocr_2.py` deployed and `CHANDRA_OCR_2_SERVER_URL` in `backend/.env`. With the free
Groq plan, rerun with `--reuse --workers 1` to finish forms that hit the rate limit.
