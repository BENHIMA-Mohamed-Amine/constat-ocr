# Synthetic constat generator

Status: done

## Goal
Generate filled, handwritten, scan-degraded constat images with an exact JSON answer key, from a seed.
The answer key is the sampled record itself, so ground truth exists by construction.

## Scope (v1 fields)
- Header: date, time, place, phone A and phone B, other-damage yes/no.
- Per vehicle (A, B): model, make, plate, coming from / going to, insured name/address, insurer, attestation no., policy no.,
  validity dates, agency, driver name/address, licence no./category/issue date/prefecture/valid-until, damage text.
- 23 circumstance ticks per vehicle + the derived tick count.
- Vehicle type (highlighted tile), impact zone (blue patch + arrows), accident sketch - added to v1 at the user's request.
  The sketch is built from the impact zones (damaged zones touch) on a two-way road or a T-junction, right-hand traffic.
- Out of scope: signatures, observations, witness name/address, page 2.

## Design
- `backend/generator/fields.py`: where each value goes (points on the template); checkbox squares are read from the template drawings.
- `backend/generator/data.py`: record sampler (Moroccan names/plates/insurers, cross-field rules, accident scenarios -> ticks).
- `backend/generator/drawings.py`: selected vehicle-type tile, impact patch, sketch cars.
- `backend/generator/render.py`: template -> raster, per-character handwriting jitter, X marks, category circle.
- `backend/generator/degrade.py`: scan / phone-photo effects (Pillow only; Augraphy only if these look too fake).
- `python -m generator --seed N --level phone` writes image, clean image and answer key.
- `python -m generator.dataset` writes the frozen dataset (500 forms, 100 dev / 400 test, phone level) with a manifest and fingerprint.

## Known limits (state in README)
- Handwriting fonts are neater than real handwriting. Latin script only. One template layout (digital variant).

## Outcome
- Five OFL handwriting fonts downloaded and compared against the stopgap font.
- Dataset generated: seed 1, 500 forms, fingerprint 3ba968bd8c4281e6ed76a1c94c0b60e6101a80011b6593a2751a8212ed73e291.
- Tests: `tests/test_data.py` (300 records) and `tests/test_dataset.py` (determinism). Docs: `docs/synthetic-data.md`.

## Possible later work (not planned)
- Paper-layout template, more road layouts (roundabout, one-way, dual carriageway), page 2, real-handwriting synthesis.
