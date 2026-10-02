# v3a: straighten the photo before OCR

Status: done

## Goal
v2 showed 81% of wrong values were never in the OCR text, and the photos are tilted and angled. v3a adds one step before
OCR: flatten the photo like a scanner app. Everything else stays the same as v2 (PP-OCRv6, `gpt-oss-120b`, prompt,
temperature, forms, metrics), so any change in the six metrics comes from the straightening alone.
Metrics: `docs/metrics.md`. v2 results: `docs/results-log.md`.

## How
`OpenCvStraightener` finds the page, crops it and warps it flat. OpenCV only, no model to download. (`docscan` was tried first and dropped: it downloads a 1 GB background-removal model.)

```python
# pipeline/straightening/opencv.py: threshold the page from the desk, take the largest outline,
# order its 4 corners, then cv2.getPerspectiveTransform + cv2.warpPerspective to the page size
class OpenCvStraightener:
    def straighten(self, image_path: Path, out_path: Path) -> None: ...
```

One new graph step before `ocr`; OCR reads its output. No working code is edited.

```python
# pipeline/flow/graph.py
def straighten_node(state):
    out = store.path("straightened", state["form_id"], ".jpg")
    if not (reuse and out.is_file()):
        straightener.straighten(Path(state["image_path"]), out)
    return {"straightened_path": str(out)}

# ocr_node reads: Path(state.get("straightened_path", state["image_path"]))
# wiring: START -> straighten -> ocr  (only when a straightener is given)
```

## Decisions
- **Off by default.** `STRAIGHTENER=opencv` turns it on, so v1 and v2 stay reproducible.
- **Same registry pattern as the OCR engines** (`straightening/factory.py`), a new method is a new class plus one entry.
- **`ArtifactStore` gets one method,** `path(step, form_id, suffix)`, because it only saves text and JSON today.
- **`run.json` records the straightener**, like the OCR engine.
- **Selection on dev forms only.** Test forms are run once, as run `v3a`.

## Work
```
backend/pipeline/straightening/   Straightener protocol, OpenCvStraightener, factory (new)
backend/pipeline/core/config.py   straightener setting
backend/pipeline/data/storage.py   path() method
backend/pipeline/flow/graph.py    straighten node, optional
backend/pipeline/run.py           build it from the setting
backend/pipeline/flow/runner.py   record it in run.json
backend/tests/unit/               one check: a drawn tilted page on a brown desk comes back upright; graph test with a fake
```

## Steps
1. Run the straightener on the 5 dev forms and look at the outputs: page upright, fully visible, not cut.
2. Run the 5 dev forms with `STRAIGHTENER=opencv`; compare with `v2-dev5-rapidocr-v6` (17 of 95 critical right).
3. Run the 20 test forms as run `v3a`:
   ```bash
   cd backend && STRAIGHTENER=opencv uv run python -m pipeline.run --run-id v3a --dev 0 --test 20
   ```
4. Log in `docs/results-log.md` next to v1 and v2; update the README table and `docs/pipeline.md`.

## Result
- `v3a` on the 20 test forms: 54 of 380 critical fields right against 56 for v2, character error rate 66.8% against 70.1%.
  Straightening alone changes almost nothing; it is the prerequisite for reading the columns separately.
- Full table and analysis: `docs/results-log.md`.

## Done when
- `v3a` is scored on the 20 test forms with the v2 prompt and model unchanged, and logged.
- Docs and `CLAUDE.md` project structure are updated.
