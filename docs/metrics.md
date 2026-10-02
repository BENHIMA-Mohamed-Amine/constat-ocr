# Metrics

How every version of the project is scored. All numbers are computed on the **test forms** of the frozen dataset
(see [synthetic-data.md](synthetic-data.md)) and compared with each form's answer key. Tune on the dev forms, never on the
test forms. The evaluation set is small because of the LLM provider's free-plan limits: the first 5 dev forms and the
first 20 test forms (see `plans/done/v1-baseline.md`). With so few forms, report counts next to percentages.

## The six metrics

| # | Metric | In simple words | Example |
|---|---|---|---|
| 1 | **Field accuracy** | For each field, the share of forms where the value is exactly right. Reported separately for **critical** and **minor** fields (see below) | Plate is right on 80 of 100 forms: 80% |
| 2 | **Forms with no critical error** | The share of forms where every critical field is right. The number closest to "could this go through without a human" | 12 of 100 forms have all critical fields right: 12% |
| 3 | **Character error rate** | How many letters and digits are wrong. Partial credit: one wrong digit is a small miss, not a total failure | `41654-A-55` read as `41654-A-56`: 1 wrong out of 10 characters: 10% |
| 4 | **Checkbox score** | For the 23 circumstance boxes: ticks found, ticks missed, and extra ticks that were not there | Real ticks 8 and 10, read 8 and 11: one right, one missed, one extra |
| 5 | **Category accuracy** | For choices from a short list (vehicle type, impact zone): how often the right one is picked. Always shown next to the "always guess the most common answer" score | Right zone on 60 of 100 forms. Always answering "front" would give 25% |
| 6 | **Cost and time** | Dollars per form, and the time the slowest 5% of forms take | $0.004 per form; the slowest 5% take 12 s |

## Why not plain accuracy alone

- **Mostly empty checkboxes.** A driver ticks 0 to 2 of 23 boxes. Ticking nothing would score about 95% accuracy and be useless. So we count ticks found, missed and extra (metric 4).
- **Lopsided categories.** 88% of vehicles are cars, so always answering "car" scores 88%. So category accuracy is always shown next to the guess-the-most-common score (metric 5).
- **Not all errors cost the same.** A wrong policy number can send a claim to the wrong contract. A misspelled street barely matters. So fields are split into critical and minor (metrics 1 and 2).

## Critical and minor fields

| Group | Fields |
|---|---|
| **Critical** | plate, policy number, attestation number, insurer, licence number, and the dates: accident date, attestation start and end, licence issue and expiry |
| **Minor** | first and last names, addresses, phone numbers, vehicle make and model, damage text, place, "coming from" and "going to" |

## Which metric applies to which field

| Field type | Metrics |
|---|---|
| Identifiers and dates (plate, numbers, dates, insurer) | 1, 2, 3 |
| Names, addresses, free text | 1 (minor), 3 |
| Circumstance ticks and the tick count | 4 |
| Vehicle type, impact zone, layout | 5 |
| Whole pipeline | 6 |

## Left out for now

- **The sketch** (car positions and directions). No standard way to score it exists. Revisit when a version tries to read it.
- **Confidence and "how many forms need no human".** These need a version that says how sure it is about each field. They are the natural next metrics once one does: how many forms can be approved automatically at an acceptable error rate, and how often the system is wrong while being sure.
- **Table and formula metrics.** The form has neither.

## Notes

- **Ground truth is per field.** There is no full-page text answer, so character error rate is computed on each field's value, not on the whole page.
- **Compare like with like.** Every version runs on the same test forms, so results go in one table: version, the six metrics, and the biggest failure found.
- **Optimistic scores.** The data is neater than real forms (see the limits in synthetic-data.md), so absolute numbers will look better than on real forms. The comparison between versions is what counts.
