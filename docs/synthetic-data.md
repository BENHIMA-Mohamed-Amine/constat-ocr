# Synthetic data: how it is generated and how it is tested

Real constat forms hold personal data and are not public, so every version of this project is evaluated on
**synthetic** forms. Each form is generated from a made-up record, so the **answer key exists before the image does**:
the ground truth is correct by construction, not labelled by hand.

## Contents
1. [Principles](#1-principles)
2. [Generate the dataset](#2-generate-the-dataset)
3. [How one form is generated](#3-how-one-form-is-generated)
4. [The record (answer key)](#4-the-record-answer-key)
5. [Sampling rules](#5-sampling-rules)
6. [Rendering](#6-rendering)
7. [Degradation](#7-degradation)
8. [The dataset: splits, files, manifest](#8-the-dataset-splits-files-manifest)
9. [How it is tested](#9-how-it-is-tested)
10. [Known limits](#10-known-limits)
11. [Code map](#11-code-map)

---

## 1. Principles
- **Ground truth by construction.** The answer key is the record the form was drawn from.
- **Deterministic.** Same seed, same form. Same command, same dataset.
- **Frozen.** One dataset, generated once, used by every version. Versions are compared on identical inputs.
- **Test set is never tuned on.** Tune on `dev`, report on `test`.
- **No personal data.** Every value is invented. The template was blanked from a filled form, and the filled original stays private in `_local/`.

## 2. Generate the dataset

From the `backend/` folder:

```bash
cd backend && uv run python -m generator.dataset --out ../data/synthetic --count 500 --dev 100 --seed 1
```

| Option | Default | Meaning |
|---|---|---|
| `--out` | `../data/synthetic` | Where the dataset goes |
| `--count` | 500 | Number of forms |
| `--dev` | 100 | How many of them are the dev split. The rest are the test split |
| `--seed` | 1 | Base seed. Form *i* uses seed `seed * 1_000_000 + i` |
| `--keep-clean` | off | Also save the undegraded render of each form (about 1 MB each) |
| `--workers` | all cores | Parallel processes |

- **Level:** every form is degraded at the `phone` level (see [Degradation](#7-degradation)).
- **Time and size:** about 2 to 3 seconds per form per core, so a few minutes on many cores. About 1.8 MB per form, so roughly 900 MB for 500 forms.
- **Do not change** `--seed`, `--count` or `--dev` once versions have been measured. That is what "frozen" means. If you must change the data, make it a new dataset with a new name and re-run every version on it.

Reproduce a single form, for debugging:

```bash
cd backend && uv run python -m generator --seed 1000026 --level phone --out ../_local/sample
```

Form 26 of the dataset above (`--seed 1`) is seed `1000026`. That command writes its image, its undegraded render and its answer key.

## 3. How one form is generated

```
seed ──► sample a record ──► draw it on the template ──► degrade to a phone photo ──► image + answer key
         (data.py)           (render.py, drawings.py)     (degrade.py)
```

One random generator, seeded once, is used for all four steps in a fixed order. That order is what makes a form reproducible from its seed.

1. **Sample a record** (`data.py`): a Python dictionary with every value on the form.
2. **Draw it** on the blank template page rasterised at 200 dpi (1654 × 2339 px): handwriting for the text, X marks for the ticks, a circle for the licence category, and the three pictures.
3. **Degrade** the clean render into a phone-style photo.
4. **Save** the JPEG and the record as JSON.

## 4. The record (answer key)

The JSON next to each image is the record itself. It is the schema an extractor is asked to produce.

**Top level**

| Field | Example | Note |
|---|---|---|
| `date`, `time` | `11/03/2026`, `19h00` | Accident date and time |
| `place` | `Bd Anfa Agadir` | Exact place |
| `phone_a`, `phone_b` | `0780475860` | Left and right phone fields of the header line. We read the left one as vehicle A's and the right one as vehicle B's |
| `other_damage` | `false` | "Dégâts matériels autres qu'aux véhicules A et B", yes or no |
| `vehicle_a`, `vehicle_b` | object | One per vehicle |
| `sketch` | object | Layout and both cars' positions |

**Per vehicle**

| Group | Fields |
|---|---|
| Vehicle | `vehicle_type` (`car`, `moto`, `tricycle`, `bus`, `truck`), `make`, `model`, `plate`, `coming_from`, `going_to` |
| Insured | `insured_last_name`, `insured_first_name`, `insured_address` |
| Insurance | `insurer`, `attestation_no`, `policy_no`, `valid_from`, `valid_to`, `agency` |
| Driver | `driver_last_name`, `driver_first_name`, `driver_address`, `license_no`, `license_category`, `license_issued`, `license_prefecture`, `license_valid_until` |
| Accident | `circumstances` (the ticked numbers, 1 to 23), `circumstance_count`, `impact_zone`, `damage` |

**Sketch**

| Field | Meaning |
|---|---|
| `layout` | `two_way` or `t_junction` |
| `junction` | `null` for a two-way road; for a T-junction, `x` and the `side` (`north` or `south`) the side road comes from |
| `a`, `b` | Each car's centre `x`, `y` (canvas units) and `heading` in degrees (0 = right, 90 = down) |

**Not in the record** (left empty or not drawn): signatures, observations, the witness name and address line, and page 2 (the insured's declaration).

## 5. Sampling rules

Values are invented but follow real formats and agree with each other.

**Formats and pools**
- **Names:** 24 first names and 23 surnames, Moroccan, in Latin letters. Insured surnames are upper case, as the form asks.
- **Places:** 12 cities, 12 street names, 10 districts. An address is `district city`.
- **Plates:** 1 to 5 digits, a letter, and a number from 1 to 89, like `41654-A-55`.
- **Phones:** `06` or `07` plus 8 digits.
- **Insurers:** 9 real insurer names. Attestation numbers look like `38A 158802852`, policy numbers have 12 or 15 digits.
- **Licences:** `NN/NNNNNN`. Category `B` for about 88% of drivers, with the others sampled at low rates.
- **Vehicles:** 88% cars, 5% motorbikes, 4% trucks, 2% three-wheelers, 1% buses. Make and model match the type, so a truck is never a Dacia Logan.
- **Damage:** one of 8 short French phrases.
- **Dates:** the accident falls between January 2022 and August 2026.

**Rules between fields**
- The accident date lies inside each vehicle's attestation period (one year).
- The licence was issued before the accident and is still valid on the accident date.
- The two plates differ.
- About 30% of drivers are not the insured person.
- `circumstance_count` always equals the number of ticks.

**Accidents**
- **19 scenarios** map to circumstances 1 to 23 of the form, for example "A overtakes (12) while B turns left (16)". Roles A and B are swapped at random.
- Each scenario lists plausible **impact zones** for each car. Eight zones exist: front, rear, left, right, and the four corners.
- Some scenarios tick nothing for one driver. That is normal on a real form.

**The sketch is built from the impact zones.**
- A's damaged zone must touch B's damaged zone. At the contact point the two outward directions are opposite, which fixes B's heading relative to A. B's position then follows.
- **Two-way road** if the cars end up roughly parallel; **T-junction** if roughly perpendicular. This gives about 78% and 22%.
- **Traffic drives on the right.** Cars heading right use the lower lane, cars heading left the upper lane. On a T-junction, B is in the side-road lane that matches its heading.
- Cars stay inside the canvas with a margin. B is kept on the road unless the zone geometry forces it aside, which happens in about a fifth of the two-way sketches (roadside or parked-type accidents).

## 6. Rendering

- **Template:** `backend/assets/constat-template.pdf`, made by `scripts/make_template.py` from a filled digital constat. The script removes every typed value, the signatures, the ticks and the picture selections, and keeps the layout, labels and pictures. It reads a private list of values from `_local/`, so it only runs on a machine that has the original.
- **Field map** (`fields.py`): each value has a writing box in PDF points. The 23 circumstance squares and the tick-count boxes are read from the template's own drawings, so they never drift from the layout.
- **Handwriting** (`render.py`):
  - Five open-licence fonts (Caveat, Kalam Regular and Light, Reenie Beanie, Indie Flower) in `backend/assets/fonts/`.
  - Each vehicle gets its own hand: a font, an ink colour and a slant.
  - Every character is drawn separately with its own tilt, slant, position and ink pressure.
  - Text shrinks until it fits its box. Sizes are normalised per font so that all hands write at a similar height.
- **Marks:** ticks are two wobbly strokes that overshoot the box. The licence category is circled by hand. Counts are written as digits in the count boxes.
- **Pictures** (`drawings.py`):
  - *Vehicle type:* the chosen tile is highlighted, teal for A and orange for B.
  - *Impact point:* a blue patch on the road over the car picture, with white arrows pointing at it. The car stays on top.
  - *Sketch:* lane arrows for the road (white = heading right or down, orange = left or up), then cars A and B with their letters, drawn at 4× and scaled down.

## 7. Degradation

A clean render never looks like a real upload, so it is degraded in `degrade.py` with Pillow only. The dataset uses the **`phone`** level. The other levels are available for experiments in `python -m generator --level`.

| Level | Rotation | Warp | Blur | Noise | Shadow | JPEG quality | Desk margin |
|---|---|---|---|---|---|---|---|
| `scan` | ±1° | 0.4% | 0.5 px | 6 | 10% | 82 | none |
| **`phone`** | **±3°** | **2%** | **0.9 px** | **10** | **30%** | **65** | **6%** |
| `bad` | ±5° | 4% | 1.5 px | 18 | 45% | 45 | 10% |

Steps, in order: warm paper tint, place on a desk-coloured background, rotate, perspective warp, lighting gradient, blur, grain, JPEG. The grain uses the seeded generator on purpose. Pillow's own noise function uses a global generator, which made images depend on which worker processed them.

## 8. The dataset: splits, files, manifest

```
data/synthetic/
  dev/000000.jpg  000000.json      forms 0 to dev-1     (tune here)
  test/000100.jpg 000100.json      the rest             (report here, never tune)
  clean/000000.png                 only with --keep-clean
  manifest.jsonl                   one line per form
  dataset.json                     counts, base seed, level, fingerprint
```

- **`manifest.jsonl`:** for each form: `id`, `split`, `level`, `seed`, paths, and the SHA-256 of the image and of the answer key.
- **`dataset.json`:** includes a **fingerprint**, the hash of all answer-key hashes. If it changes, the data changed.
- **In git:** `manifest.jsonl` and `dataset.json` are small and kept. The `dev/`, `test/` and `clean/` folders are ignored. Anyone can regenerate the images with the command in section 2 and check the hashes against the manifest.
- **What the fingerprint guarantees:** the records are identical. Images depend on the fonts and on Pillow, so their hashes can differ on another machine or library version. Check the answer-key hashes first.

## 9. How it is tested

Both live under `tests/regression/` (project-wide testing conventions: [docs/testing.md](testing.md)):

```bash
cd backend && uv run pytest tests/regression/test_data.py tests/regression/test_dataset.py
```

**`tests/regression/test_data.py`: 300 records, no images, one test function per property below (a few seconds)**

| Check | Why |
|---|---|
| `circumstance_count` equals the number of ticks | The count box must be derivable from the ticks |
| Attestation period contains the accident date | Coverage rule |
| Licence issued before, and valid on, the accident date | Driver rule |
| The two plates differ | Two distinct vehicles |
| A's and B's damaged zones touch in the sketch (gap under 3 px) | The sketch must match the impact zones |
| Both cars lie inside the canvas | Nothing is drawn off the sketch |
| A sits in the lane for its heading | Right-hand traffic |
| Two-way: both cars roughly parallel to the road | Layout matches the geometry |
| T-junction: B roughly vertical, side matches its heading, and B is in its side-road lane | Layout matches the geometry |

**`tests/regression/test_dataset.py`: the dataset command, real rendering (about 40 seconds)**
- The same command with 1 worker and with 2 workers gives an identical manifest, so identical **images and answer keys**, hash for hash.
- The same command gives the same fingerprint, and a different seed gives a different one.
- The split is as asked, every form is at the `phone` level, and every image and answer key file exists.

**Bugs these tests caught while building**
- A placement that fit by a fraction of a pixel and failed after rounding the stored pose. The sampler now keeps a 2 px margin.
- Non-reproducible images: Pillow's noise ignored our seed. Fixed by seeding the noise ourselves.

**Checked by eye, not by test**
- Every change to the renderer was reviewed on a rendered form: text position, marks, pictures, sketch.
- 30 forms across all levels were rendered without errors after each large change.

**Not tested**
- Whether the synthetic forms look like real ones. No automated check can say. The only real sample is one private image.
- Handwriting realism. It is judged visually.
- Any extraction or OCR quality. That belongs to the versions, not to the data.

## 10. Known limits

State these in the README and every write-up. They mean **scores on synthetic data are optimistic**.

- **Handwriting fonts are neater and more regular than real handwriting.** Latin script only. Arabic appears only in the printed labels.
- **One template layout:** the digital-style constat. A paper form differs in its lines and boxes.
- **Traffic side and arrow colours** are assumptions: right-hand traffic, white for right or down, orange for left or up. The original sample we looked at had white arrows in the upper lane, which would be left-hand traffic. Not verified against the real app.
- **Only two road layouts:** two-way road and T-junction. Roundabouts, one-way streets, dual carriageways and parking lots are not drawn.
- **The sketch is one plausible pose.** Real drivers draw messier and more varied sketches. Some scenario and zone pairs still look odd, for example two front corners meeting.
- **The impact picture is always a car**, even for a motorbike. We don't know whether the app changes it.
- **Not drawn or filled:** page 2, the witness name and address, observations, signatures.

## 11. Code map

| File | Role |
|---|---|
| `backend/generator/data.py` | Record sampler, scenarios, sketch geometry |
| `backend/generator/fields.py` | Writing boxes, checkbox and count positions |
| `backend/generator/render.py` | Handwriting, marks, ties the steps together |
| `backend/generator/drawings.py` | Vehicle type, impact patch, sketch |
| `backend/generator/degrade.py` | Phone / scan / bad effects |
| `backend/generator/dataset.py` | The dataset command |
| `backend/generator/__main__.py` | One form at a time, for experiments |
| `backend/scripts/make_template.py` | Blanks the filled PDF into the template |
| `backend/tests/` | The two test files above |
| `plans/synthetic-generator.md` | The plan and scope |

**To add an accident scenario:** append a line to `SCENARIOS` in `data.py` with the ticks for A and B and plausible zones. The sketch, the layout and the tests follow from it. Then regenerate the dataset under a new name.
