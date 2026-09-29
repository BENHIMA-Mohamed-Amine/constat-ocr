# v2: a stronger CPU OCR engine, same LLM

Status: approved

## Goal
v1 showed the OCR step is the bottleneck: 92% of the wrong text values were never in the text the LLM received. v2 changes
that one variable. Swap Tesseract for a stronger OCR engine that still runs on a CPU, and keep everything else identical
(LLM, prompt, schema, settings, forms, metrics). Any change in the six metrics is then caused by read quality alone.
Metrics: `docs/metrics.md`. v1 results: `docs/results-log.md`.

## Decisions
- **One variable changes: the OCR engine.** Same `gpt-oss-120b`, same prompt, same temperature, same forms
  (2 dev, 20 test). The new engine is a new class behind the existing `OcrEngine` interface; no working code is edited.
- **Pick: PP-OCRv6 through RapidOCR (ONNX Runtime).** The shortlist came from public numbers (below); the dev forms decided it. PP-OCRv5 was the first pick and came second.
- **Tesseract stays as the reference.** Its v1 numbers are the baseline every candidate is compared to.
- **Selection uses dev forms only.** The test forms are run once, for the chosen engine.
- **The public benchmark is the shortlist, not the verdict.** It is page-level and English or Chinese; our forms are
  handwritten French photos with Arabic labels.

## Why this engine: public benchmark evidence
Benchmark: **OmniDocBench** (CVPR 2025), text recognition on a page-level subset, normalized edit distance, lower is
better. It is the one benchmark that scores both CPU OCR engines and vision-language models on the same pages, so v3 and v4
candidates can be justified on the same table. English is the closest column to our Latin-script forms.

| Model | Type | English | Chinese | Mixed |
|---|---|---|---|---|
| PaddleOCR | OCR | 0.071 | 0.055 | 0.118 |
| Tesseract | OCR (v1) | 0.096 | 0.551 | 0.250 |
| EasyOCR | OCR | 0.260 | 0.398 | 0.445 |

Source: OmniDocBench repository, component-level table (v1.0). **To do: re-read the numbers from the README before
quoting them in docs** (this table was read through a page summary).

- PP-OCRv5 has 0.07B parameters, so it runs on a CPU. Its authors report 26% fewer errors than the previous version on
  non-standard handwriting (PaddleOCR 3.0 technical report).
- Its edge over Tesseract on English is small (0.071 vs 0.096), so the dev-form run decides.
- EasyOCR is worse than Tesseract on this table: dropped from the shortlist.

## Candidates (run on the dev forms)
| Candidate | Why | Open question |
|---|---|---|
| Tesseract (fra) | The v1 reference | none |
| PP-OCRv5 via RapidOCR | Best public evidence for a light CPU engine | Does the RapidOCR release include v5? Does its Latin model keep French accents? |
| docTR | Structured-document OCR, CPU | No public number on the shared benchmark |

## Selection method
1. For each candidate, run the pipeline on the 2 dev forms, with `--reuse` off for the OCR step only.
2. Score with the six metrics. Run `scripts/analyze_run.py` to see how many wrong values were never in the text.
3. Also record OCR seconds per form, on this machine's CPU.
4. Pick the engine with the best critical-field accuracy; use character error rate and time to break ties.
5. Run the winner once on the 20 test forms as run `v2`. Log it in `docs/results-log.md` next to v1.
Two dev forms is a very small selection set. If the candidates are close, raise the dev count before choosing.

## Work
```
backend/pipeline/ocr/rapidocr.py   RapidOcrEngine implementing OcrEngine (new file)
backend/pipeline/ocr/__init__.py   export it
backend/pipeline/config.py         ocr_engine setting (which engine to build)
backend/pipeline/run.py            build the engine from the setting
backend/tests/                     one fake-free unit check that the engine returns text and seconds on a sample image
```
- Engine selection goes through one small registry (name to constructor), so a new engine is one new class plus one
  entry, not an `if/elif` chain.
- `describe_run` records the engine name and version in `run.json`, so the run stays reproducible.

## Progress
- Done: `RapidOcrEngine` (`pipeline/ocr/rapidocr.py`), engine registry (`pipeline/ocr/factory.py`), `OCR_ENGINE` setting
  (default `tesseract`, so v1 stays reproducible), `run.json` records the engine name, one unit test (`test_ocr_engines.py`).
- Checked: RapidOCR 3.9.2 ships PP-OCRv5 with a `latin` recognizer, French accents come through, about 4.5 s per form on
  this CPU (Tesseract about 2.3 s).
- New candidate found and run: RapidOCR also ships PP-OCRv6 (`french` det and rec models).
- Dev run on 5 dev forms (runs `v2-dev5-*`), same LLM and prompt, ordered by critical fields right:

| Rank | OCR engine | Critical right (of 95) | Minor right (of 150) | Character error rate | OCR s/form |
|---|---|---|---|---|---|
| 1 | PP-OCRv6 (RapidOCR) | 17 | 34 | 65.4% | 4.1 |
| 2 | PP-OCRv5 (RapidOCR) | 6 | 19 | 72.8% | 5.3 |
| 3 | docTR | 4 | 9 | 82.1% | 1.9 |
| 4 | Tesseract (v1) | 1 | 7 | 87.3% | 4.4 |

  No engine gets a form with all critical fields right (0 of 5 for every engine). Five forms is still small.

- Test run done: `runs/v2`, results in `docs/results-log.md` (critical fields 3 of 380 to 56 of 380, no form fully right).

## Done when
- The chosen engine runs the 20 test forms as run `v2` with the v1 prompt and model unchanged.
- `docs/results-log.md` has a v2 entry: the same table as v1, the benchmark evidence for the choice, and the biggest
  failure found.
- README results section and `CLAUDE.md` project structure are updated.

## Open
- Whether ticks, circled letters and pictures are still unreadable with any text-only engine (expected yes; that is
  what the vision versions address).
