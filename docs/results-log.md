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

### How wrong are the wrong fields (`scripts/near_misses.py v3c`)

435 of the 980 text fields are wrong. Most are wrong by a hair.

| How far the final answer is from the truth | Fields | Share |
|---|---|---|
| No value returned | 101 | 23% |
| 1 edit | 151 | 35% |
| 2 edits | 97 | 22% |
| 3 or more edits | 86 | 20% |

| How close the truth is to the OCR text | Fields | Share |
|---|---|---|
| Exact in the text (the LLM got it wrong) | 58 | 13% |
| In the text, punctuation or spaces differ | 15 | 3% |
| 1 edit away | 85 | 20% |
| 2 edits away | 100 | 23% |
| 3 or more edits away (never read) | 177 | 41% |

- **57% of the wrong answers are one or two characters off,** and 59% have the truth within two edits of something in the text (or in it
  exactly). That is a pool a re-read or a repair rule can win back. The 41% never read are mostly plates (18 of 25), policy numbers (15 of 23),
  attestation and licence numbers, and free text such as damage (18 of 31).
- **Some errors are rules, not reading.** Vehicle B's validity dates are swapped in 20 cases where both dates are in the text exactly
  (for example the answer key has start 17/07/2025 and end 16/07/2026 and the model returned them the other way round). That line is
  written right to left, so the order of the dates is reversed. Start before end holds on any real attestation.
- **Spaces inside ID numbers** make correct reads count as wrong (`59a 15 0196573` against `59a 150196573`, 7 attestation numbers and
  more policy numbers). The comparison removes no spaces inside a value.
- **Some values in the text were not returned** (for example vehicle B's licence issue date and prefecture): a placement problem to look at.

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
Needs the Modal app of `serving/deploy/chandra_ocr_2.py` deployed, and `CHANDRA_OCR_2_SERVER_URL`, `MODAL_PROXY_TOKEN_ID` and `MODAL_PROXY_TOKEN_SECRET` in `backend/.env` (the server requires a Modal proxy token, see [serving.md](serving.md#authentication)). With the free
Groq plan, rerun with `--reuse --workers 1` to finish forms that hit the rate limit.

## v3d: repair the record with deterministic rules

- **What:** one optional step after the LLM and before the scoring, `repair`, runs small rules over the record and saves what it
  changed (`runs/v3d/repaired/<id>.json`: the repaired record and a list of rule, field, before, after). Rules in this run:
  - `validity-dates`: swap an attestation's start and end when the start is after the end;
  - `attestation-format`: write an attestation number as three characters, a space, then the digits;
  - `phone-digits`: remove spaces, dots and dashes from the phone numbers;
  - `policy-spaces`: remove spaces from policy numbers.
- **Why:** `scripts/near_misses.py v3c` showed 57% of the wrong text fields were one or two characters off, and some errors were rules:
  vehicle B's validity line is written right to left, so its two dates were read in reverse order, and ID numbers carried stray spaces.
- **One change only, from the same outputs.** The saved Chandra text and the saved LLM records of v3c were copied to the v3d run and
  scored again with `--reuse`, so no GPU or LLM call was made and the only difference is the repair step. Run `v3d`, dev run `v3d-dev5`.
- **Two rules are not equal in how far they can be trusted.** Dates in order and separator-free phone and policy numbers hold on any real
  form. The attestation format is the format of the synthetic forms, and real attestation numbers differ between insurers, so
  that rule is only trusted here. Snapping names, insurers and prefectures to lists was left out on purpose: the lists would come from
  the generator and inflate the score without the pipeline improving.

### v3d results (20 test forms)

| Metric | v3c | v3d (repaired) |
|---|---|---|
| Field accuracy, critical fields | 168 of 380 (44.2%) | **194 of 380 (51.1%)** |
| Field accuracy, minor fields | 377 of 600 (62.8%) | **381 of 600 (63.5%)** |
| Forms with no critical error | 0 of 20 | 0 of 20 |
| Character error rate | 16.8% (critical 17.5%, minor 16.3%) | **16.1%** (critical 16.1%, minor 16.2%) |
| Ticks, vehicle type, impact zone | unchanged | unchanged |
| Cost per form | $0.0012 | $0.0012 (the step is free) |

- **Dev check (5 forms):** 48 of 95 critical fields right (v3c: 43), 101 of 150 minor (99), character error rate 9.3% (9.9%).
- **40 fields were changed, 30 became right, none that was right became wrong,** and 10 had no effect (the value was still wrong
  after the repair).

| Rule | Fields changed | Became right | No effect |
|---|---|---|---|
| `validity-dates` | 20 (10 vehicles) | 18 | 2 |
| `attestation-format` | 13 | 7 | 6 |
| `phone-digits` | 5 | 4 | 1 |
| `policy-spaces` | 2 | 1 | 1 |

- **The gain is +26 critical fields and +4 minor fields.** The critical gain is 18 dates, 7 attestation numbers and 1 policy number. Without
  the attestation rule it is +19 critical.
- **Wrong text fields: 405 of 980** (435 before). Fields whose exact value is in the text but returned wrong fell from 58 to 28.
- **The forms are not close to automatic yet:** still 0 of 20 without a critical error, and 177 values (44% of the wrong ones) were never read,
  which no rule can repair.

### What this says about the next version
- **Rules take the cheap, certain errors.** What is left is reading: 185 wrong fields are one or two characters from something in the text
  (names, licence numbers, dates, plates), and 177 were not read.
- **Next candidates:** a second opinion for the digit fields (RapidOCR's text beside Chandra's), re-reading the hard fields from crops, and
  reading ticks and categories on the template without a model.

### Reproduce

```bash
cd ~/projects/constat-ocr/backend
mkdir -p ../runs/v3d && cp -r ../runs/v3c/{straightened,ocr,ocr_usage,structured} ../runs/v3d/
STRAIGHTENER=opencv OCR_ENGINE=chandra-ocr-2 STRUCTURING_PROMPT=chandra REPAIRS=all \
  uv run python -m pipeline.run --run-id v3d --dev 0 --test 20 --reuse
```

## v3e: read the ticks, tiles and circles from the template

- **What:** one optional step after the LLM, `marks`, reads what the driver marked from fixed positions on the blank template, with plain
  image processing: no model, no GPU, no LLM. The straightened page is aligned on the template (ECC homography on the printed content),
  then each mark is a measurement at a known place:
  - **ticks:** the share of ink pixels inside each of the 23 boxes of each vehicle (a pixel darker than the blank template is ink);
  - **tick count:** the number of ticks (the form asks the driver to write that number);
  - **vehicle type:** the tile with the most colour in the vehicle-type picture (the chosen tile is filled with the vehicle's highlight);
  - **licence category:** the letter with the most ink on a ring around it (the driver circles one);
  - **impact zone:** the zone rectangle that best matches the vivid blue patch on the impact picture;
  - **other damage:** more ink in the OUI cells or in the NON cells.
  The values replace the LLM's for those fields; the text fields are untouched. Same Chandra text and LLM records as v3d, scored again with
  `--reuse`, so the step is the only difference. Run `v3e`, dev run `v3e-dev5`.
- **Why:** after v3d the tick and category fields were still poor (ticks 10 found of 25, vehicle type 12 of 40, licence category 2 of 40).
  The form is a fixed template, so these are measurements at known places, not a reading problem.
- **Two things made it work:** the geometry comes from the blank template PDF, and the alignment is refined per box. Aligning the page once
  was not enough: a first version missed 4 of the 130 dev ticks because the page was a few pixels off (up to 7) at one end of the column.
  Placing each box on its own printed square, and thickening the template by 2 pixels so a printed line that lands off is not counted as
  ink, took the gap between the lowest ticked box and the highest empty box from negative to +0.167.
- **Thresholds were set on the dev forms only** (ticked boxes scored 0.225 and above, empty ones 0.058 and below, threshold 0.14).

### v3e results

**The reader alone, on whole splits** (`scripts/eval_marks.py`, no LLM, no GPU):

| | Dev, 100 forms (thresholds set here) | Test, 400 held-out forms (read once) |
|---|---|---|
| Ticks found / missed / extra | 130 / 0 / 0 | **542 / 0 / 0** |
| Tick count | 200 of 200 | **800 of 800** |
| Vehicle type | 200 of 200 | **800 of 800** |
| Licence category | 200 of 200 | **800 of 800** |
| Impact zone | 200 of 200 | **800 of 800** |
| Other damage | 100 of 100 | **400 of 400** |

**In the pipeline, on the same 20 test forms as v3d:**

| Metric | v3d | v3e |
|---|---|---|
| Ticks found / missed / extra | 10 / 15 / 4 | **25 / 0 / 0** |
| Tick count written on the form | 4 of 40 | **40 of 40** |
| Vehicle type | 12 of 40 (always "car": 88%) | **40 of 40** |
| Licence category | 2 of 40 (always "B": 88%) | **40 of 40** |
| Impact zone | 4 of 40 (always the most common: 28%) | **40 of 40** |
| Other damage (yes/no) | 8 of 20 (always "no": 95%) | **20 of 20** |
| Critical fields right | 194 of 380 (51.1%) | 194 of 380 (51.1%) |
| Minor fields right | 381 of 600 (63.5%) | 381 of 600 (63.5%) |
| Character error rate | 16.1% | 16.1% |
| Cost and time | $0.0012 per form | $0.0012, plus about 0.7 s per form on a CPU |

- **Every mark field now beats the "always guess the most common value" baseline,** which no earlier version did.
- **Vehicle B's ticks are covered** (Chandra returned only vehicle A's boxes).
- **The text metrics do not move:** the step reads marks, not text. The 405 wrong text fields of v3d are the same fields.
- **Dev check (5 forms):** ticks 6 / 0 / 0 against 2 / 4 / 1, tick count 10 of 10, all categories 10 of 10.

### What this does and does not show
- **The reader is perfect on the synthetic forms, and that is a statement about those forms.** Their marks are clean programmatic ink
  crosses, one circle, a colour fill and a blue patch, on a template the reader knows exactly. Real photographed forms have messier marks
  (a tick that is a stroke, a circle that misses, a blue ballpoint patch), so this is a baseline for what the template alone can tell, not a
  claim that the problem is solved on real forms.
- **Two readings depend on how the source app draws:** the filled tile and the blue patch are what the app puts on the form. A hand-drawn
  arrow would need a model.
- **The tick count is derived,** the number of ticks, not the handwritten digit in the box. On a real form a driver may miscount.
- **The geometry is imported from the generator package** (the template's definition lives there); one module, `pipeline/marks/layout.py`,
  crosses that line.

### What this says about the next version
- **The mark fields are done on this data.** What is left is text: 405 wrong text fields, 55% one or two characters off and 44% never read.
- **Next candidates:** a second opinion for the digit fields, re-reading the hard fields from crops, a general VLM as the upper bound,
  and testing the template reader on messier marks.

### Reproduce

```bash
cd ~/projects/constat-ocr/backend
mkdir -p ../runs/v3e && cp -r ../runs/v3d/{straightened,ocr,ocr_usage,structured} ../runs/v3e/
STRAIGHTENER=opencv OCR_ENGINE=chandra-ocr-2 STRUCTURING_PROMPT=chandra REPAIRS=all READ_MARKS=true \
  uv run python -m pipeline.run --run-id v3e --dev 0 --test 20 --reuse
uv run python -m scripts.eval_marks test        # the reader alone on the 400 held-out forms
```

## v4a: one open vision model reads the page and fills the record

- **What:** the OCR step and the text LLM are replaced by one general open vision model, **Qwen3.8-27B** (Apache 2.0), served on Modal with
  vLLM 0.30.0 on an H100 (`serving/deploy/qwen3_8_27b.py`, the Modal proxy token is required like for Chandra). It gets the straightened
  photo and a short prompt, and answers with JSON that follows the `Record` schema (guided decoding, thinking switched off), so the keys and
  types are always right. No `gpt-oss-120b` and no Groq call: the structurer is `VisionStructurer` (`STRUCTURER=vision`) and the OCR engine
  is `none`. The marks reader (v3e) and the repair rules (v3d) still run after it. Same 20 test forms (`000100` to `000119`). Run `v4a`;
  dev runs `v4a-dev5` (first prompt), `v4a-dev5-p2` and `v4a-dev5-p3`.
- **Why:** v3e left 405 wrong text fields, 44% of them never read. A general model that sees the page and the schema together removes the
  OCR-to-LLM hop where values were lost.
- **The prompt** (`VLM_SYSTEM_PROMPT`, about 20 lines): copy exactly and use `null` rather than guess (a plausible value that is not on the page
  is worse than null), read each digit on its own, leave the tick fields to the marks reader, and the written format of each value (dates,
  time, plate, attestation, licence number, policy and phone digits, capitals). Set on the 5 dev forms only.
- **Small sample:** 20 forms is 40 vehicles, one run. Read the percentages as an early signal.

### Prompt iterations on the 5 dev forms (the test forms were not used)

| Run | Prompt | Critical (of 95) | Minor (of 150) | Character error rate |
|---|---|---|---|---|
| v3e | Chandra + `gpt-oss-120b` | 48 | 101 | 9.3% |
| `v4a-dev5` | first prompt | **52** | 121 | 5.85% |
| `v4a-dev5-p2` | + capitals for names and places, licence slash hint | 50 | 121 | 5.78% |
| `v4a-dev5-p3` | + "the 3rd character is always the slash" | 49 | 120 | 5.74% |

- **The prompt is not the lever.** The three versions are within noise (a digit flips between runs). The only visible effect was the
  capitalisation ("Ain sebaa casablanca" became "Ain Sebaa Casablanca").
- **Licence numbers were the main error and the prompt did not fix them:** the thin `/` is read as `1` (`631063647` for `63/068647`) and
  often another digit is wrong too. A repair rule that puts the slash back would fix 2 of 9, so it was not added.
- **The kept prompt is the round-2 text.** Round 3's extra sentence did nothing, so it was removed.

### v4a results (20 test forms)

| Metric | v3c | v3d | v3e | v4a |
|---|---|---|---|---|
| Field accuracy, critical fields | 168 of 380 (44.2%) | 194 (51.1%) | 194 (51.1%) | **222 of 380 (58.4%)** |
| Field accuracy, minor fields | 377 of 600 (62.8%) | 381 (63.5%) | 381 (63.5%) | **482 of 600 (80.3%)** |
| Forms with no critical error | 0 of 20 | 0 | 0 | **0 of 20** |
| Character error rate | 16.8% | 16.1% | 16.1% | **5.3%** |
| Ticks found / missed / extra | 10 / 15 / 4 | 10 / 15 / 4 | 25 / 0 / 0 | 25 / 0 / 0 |
| Vehicle type, licence category, impact zone, other damage | | | 100% | 100% (same reader as v3e) |
| LLM cost (Groq) | $0.0012 per form | | | **none** (no LLM call) |
| GPU cost (H100, estimated) | Chandra: **$0.018 per form** | | | **$0.029 per form** |
| **Total cost per form** | **about $0.019** (v3c and v3e) | | | **about $0.029** |
| Tokens per form | | | | 5,547 in, 850 out |
| Time per form | 55 s OCR + LLM | | | 187 s mean, slowest 5% 233 s, with 8 forms at once on one H100 |

- **The text got much better:** critical fields +28 against v3e, minor +101, character error rate down by two thirds. Wrong text fields:
  **282 of 980** (405 in v3d).
- **The marks do not move:** the v3e reader still fills them, so they equal v3e. The VLM was told to leave them `null`.
- **Still no form without a critical error** (0 of 20), so nothing could go through without a human.
- **No form failed.** All 20 produced valid JSON (guided decoding).

### Where the errors are

How far each of the 282 wrong text fields is from the truth (edit distance, computed from `runs/v4a/repaired/`). The model always answered, so
there is no "never read" group: it is a misreading, not a gap.

| Distance | Fields | Share |
|---|---|---|
| 1 edit | 135 | 48% |
| 2 edits | 71 | 25% |
| 3 or more | 76 | 27% |

| Weakest fields (of 40) | Right | Strongest (of 40) | Right |
|---|---|---|---|
| licence number | 12 | licence prefecture | 39 |
| attestation number | 16 | make | 37 |
| validity start date | 16 | model | 36 |
| plate | 18 | agency | 35 |
| policy number | 18 | insurer | 34 |

- **73% of the wrong fields are one or two characters off.** The pool is long digit strings (licence, attestation, policy, plate) and dates,
  as in v3c: one digit flips, and a thin `/` becomes a `1`.
- **It reads, it does not invent,** with one exception seen on the dev forms: vehicle B's make and model were wrong together on one form
  (Dacia Logan for Toyota Yaris). Plausible-looking wrong values were not counted separately.
- **`scripts/near_misses.py` does not apply here:** it compares with the OCR text, and this pipeline has none.

### Cost and speed

- **No per-token cost.** The `dollars_per_form` in `summary.json` ($0.0013) applies the Groq price to the VLM's tokens and is not a real cost.
- **GPU cost** (H100 SXM5, $0.001097 per second on [modal.com/pricing](https://modal.com/pricing); wall-clock from the run log, not Modal's
  bill): the batch took about 532 s for 20 forms, 8 at once. With the 250 s cold start and the 120 s scale-down window the container was up
  for about 900 s: **about $0.99 for the batch, $0.05 per form**. Without the cold start and idle time, **about $0.029 per form**.
- **Chandra's GPU cost, estimated from the saved v3c files** so the comparison is fair (the file times and OCR seconds of `runs/v3c` and
  `runs/v3c-dev5`, which ran at the same time): 25 pages went through the H100 in about 406 s, so **16.3 s per page, $0.018 per form**.
  Add the Groq LLM step ($0.0012) and **v3e costs about $0.019 per form**.
- **So v4a is about 50% dearer per form** ($0.029 against $0.019), not free: it dropped the LLM bill but the 27B model uses more GPU time
  per page than Chandra (26.6 s against 16.3 s). Both numbers leave out the cold start and the idle scale-down window.
- **The two estimates are not on equal footing.** v3c ran 13 pages at once on the GPU and v4a 8 (the container's limit), so Chandra had a
  fuller batch. A single run each, wall-clock times and not Modal's bill. Treat the gap as "about 1.5 times", not a precise ratio.
- **Per-form latency is high (187 s)** because the 27B model shares the GPU between 8 pages; one page alone takes about 34 s.

### What this does and does not show
- **Same data caveat as before:** these are synthetic forms, and the VLM was never trained on them. The marks reader is still tuned to the
  clean synthetic marks.
- **The format rules in the prompt follow the generator** (plate, attestation, licence number shapes). On real forms those shapes would
  differ, so part of the gain on the format-related fields is only trusted here.
- **One run, one model, thinking off.** A 1 or 2 field gap between versions is noise.

### What this says about the next version
- **A general open VLM beats the OCR-model-plus-LLM chain on accuracy** on this data: 58% against 51% critical fields and 5% against 16%
  character error rate, with one model and no LLM bill. It costs about 1.5 times more per form once the GPU is counted on both sides.
- **The prompt is not the lever.** The remaining errors are digit-level misreadings.
- **v4b candidates:** thinking mode on (costs time), re-reading the digit fields from crops at higher resolution, voting between several
  samples, a bigger model (Gemini) as the upper bound, and raising the container's concurrency to cut GPU seconds per page, and measuring both GPU costs from Modal's bill.

### Reproduce

```bash
cd ~/projects/constat-ocr/backend
mkdir -p ../runs/v4a && cp -r ../runs/v3e/straightened ../runs/v4a/
STRAIGHTENER=opencv OCR_ENGINE=none STRUCTURER=vision STRUCTURING_PROMPT=vlm REPAIRS=all READ_MARKS=true \
  uv run python -m pipeline.run --run-id v4a --dev 0 --test 20 --workers 8 --reuse
```
Needs the Modal app of `serving/deploy/qwen3_8_27b.py` deployed, and `QWEN3_8_27B_SERVER_URL`, `MODAL_PROXY_TOKEN_ID` and `MODAL_PROXY_TOKEN_SECRET`
in `backend/.env`. The first request after a deploy takes about 5 to 10 minutes while 55 GB of weights load.

## v4b: re-read the hard digit fields from crops

- **What:** one optional step after the structurer, `refine` (`pipeline/refine/`). For each vehicle it cuts six fields out of the straightened page
  at their known place on the template (plate, attestation number, policy number, licence number, validity start and end dates), enlarges each
  crop 3 times, and sends the 12 crops in one request to the same Qwen3.8-27B server, which answers with schema-guided JSON. A read value
  replaces the page value; `null` or a failed call keeps it. Then the marks reader and the repair rules run as before. Same 20 test forms. The
  saved v4a records were reused (`--reuse`), so the crop step is the only difference. Run `v4b`, dev run `v4b-dev5`.
- **Why:** after v4a, 73% of the wrong text fields were one or two characters off, mostly long digit strings. The model sees a whole page at about
  one vision token per 32 by 32 pixels, so a handwritten digit is about half a token; a 3 times enlarged crop gives each digit several. A second
  model did not help (Chandra and Qwen agree on only 87 of the 240 digit fields, and 71 of those are right), so the lever is better pixels.
- **Geometry:** the field boxes are where the generator writes the values (`generator/fields.py`, through `pipeline/marks/layout.py`), with a margin of
  10 px across and 7 px down; the page is aligned on the template with the marks reader's alignment. Crops were checked by eye on a dev form.
- **No tuning:** the six fields were chosen from v4a's weakest, and the dev run improved all six, so none was dropped. The prompt is the v4a format lines
  plus "copy exactly, null if unreadable".

### v4b results (20 test forms)

| Metric | v3e | v4a | v4b |
|---|---|---|---|
| Critical fields right | 194 of 380 (51.1%) | 222 (58.4%) | **299 of 380 (78.7%)** |
| Minor fields right | 381 of 600 (63.5%) | 482 (80.3%) | 482 of 600 (80.3%) |
| Forms with no critical error | 0 of 20 | 0 | **2 of 20** |
| Character error rate | 16.1% | 5.3% | **3.7%** |
| Wrong text fields | 405 | 282 | **205** |
| Ticks, categories | 100% | 100% | 100% |

| Field (of 40) | v3e | v4a | v4b |
|---|---|---|---|
| licence number | 10 | 12 | **27** |
| attestation number | 11 | 16 | **30** |
| policy number | 18 | 18 | **31** |
| plate | 15 | 18 | **23** |
| validity start date | 17 | 16 | **34** |
| validity end date | 27 | 28 | **40** |

- **The dev run agrees:** on the 5 dev forms, 80 of 95 critical fields right (v4a: 50), character error rate 3.8% (5.8%), licence numbers 9 of 10 (1 of 10).
- **Of the 127 fields the step changed, 83 became right and 6 that were right became wrong.** Minor fields did not move: the six fields are all critical.
- **The first forms with no critical error:** 2 of 20 (0 before).
- **No call failed.** All 20 crop requests returned valid JSON.
- **The thin slash was a resolution problem, not a prompt one.** The v4a prompt could not stop `/` being read as `1` (licence numbers 12 of 40); on a crop the
  licence number is 27 of 40.

### Where the errors are now
205 wrong text fields: 111 are 1 edit off, 38 are 2, 56 are 3 or more, and none was left empty.

- **Plate (23 of 40) and the licence number (27 of 40) are still the weakest.** The handwriting is sloppy: on the dev crops a plate such as `14472-T-1` is written
  `1.447Z -J-1`, which is ambiguous to a person too.
- **The other text fields are untouched,** so the 205 remaining errors are mostly names, addresses and damage text (minor fields stay at 80.3%), and the plate and
  digit fields that crops did not fix.

### Cost and speed
- **The crop step cost about 256 s of GPU for the 20 forms** (wall-clock from the run log), so about **$0.014 per form** (H100, $0.001097 per second). v4b is
  therefore about **$0.043 per form** (v4a $0.029 plus the crops), against about $0.019 for v3e. The crop calls do not show in `summary.json`, which only
  counts the page request.
- **The crops are small calls:** 12 images of a few dozen tokens each in one request, so the step is cheap next to reading the whole page.

### What this does and does not show
- **The boxes come from the generator.** On a real photo the handwriting sits at other places on the line, so the margin would need to grow or a field detector
  would be needed. This is a baseline for what the template position gives, as for the marks reader in v3e.
- **One run on 20 forms, one model,** with the six fields fixed before the test run. The dev run gave the same direction on all six fields.
- **Format lines follow the generator** (as in v4a).

### What this says about the next version
- **Pixels were the lever:** crops raised critical fields from 58% to 79% with no prompt change and no second model.
- **Next candidates:** crop the remaining text fields (names, addresses, damage) and the header, which would move the minor fields; a larger enlargement for the
  plate; voting between several samples on the crops; thinking mode on the crops only; and raising the server's concurrency to cut GPU seconds per page.

### Reproduce

```bash
cd ~/projects/constat-ocr/backend
mkdir -p ../runs/v4b && cp -r ../runs/v4a/{straightened,structured} ../runs/v4b/
STRAIGHTENER=opencv OCR_ENGINE=none STRUCTURER=vision STRUCTURING_PROMPT=vlm REPAIRS=all READ_MARKS=true \
  REFINE_FIELDS=plate,attestation_no,policy_no,license_no,valid_from,valid_to \
  uv run python -m pipeline.run --run-id v4b --dev 0 --test 20 --workers 8 --reuse
```
