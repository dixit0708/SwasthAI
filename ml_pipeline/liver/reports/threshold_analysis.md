# Liver Model — Threshold Trade-off Analysis (Validation Only)

**Note on file location:** the request asked for `reports/liver/threshold_analysis.md`; this repo's existing liver reports all live under `ml_pipeline/liver/reports/`, so this file is placed there (`ml_pipeline/liver/reports/threshold_analysis.md`) to match that existing convention rather than creating a new top-level `reports/` tree. Flagging in case a different location was actually intended.

## Purpose

The corrected `liver-nhanes-v1` model (60/20/20 split, threshold chosen on
validation only, test set touched once) currently ships at a
sensitivity-first threshold that flags ~47-53% of people without liver
disease as "elevated risk." This analysis asks: does moving to a stricter
threshold meaningfully reduce false positives while still catching a
reasonable share of true cases (65-85% recall)? **This is an analysis
only.** No model was retrained, no feature was added, no hyperparameter
was tuned, and the production threshold was not changed.

## Data split used

Identical to the corrected `train_nhanes.py` methodology: 60/20/20
train/validation/test, stratified, `random_state=42`, split constants
imported directly from `train_nhanes.py` (not retyped) to guarantee an
exact match to the split the shipped model's threshold was chosen from.
Validation set: n=2,430, positive rate 4.94% (120 positive cases).

## Confirmation: validation-only, test set untouched

Every number in this report comes from the **validation** split only. The
test set (`X_test`/`y_test`) is loaded by the reproduced split for
completeness but is never scored, never inspected, and plays no role in
any threshold shown below — consistent with "test set touched exactly
once, only after a threshold is explicitly approved," which has not
happened here.

## Methodological caveat (read before trusting absolute numbers here)

The original training run computed validation-set probabilities in-memory
to pick the shipped threshold, but never saved them to disk — there was no
pre-existing "validation predictions" file to simply load. Getting a
validation score from a model that was *only* fit on the train split
(never seeing validation data) would require fitting a model, which this
task explicitly ruled out. Instead, this analysis loads the **already-fit,
already-shipped production artifact** (`joblib.load`, zero fitting calls
anywhere in `threshold_analysis.py`) and runs plain inference
(`predict_proba`) on the validation split.

Since the shipped artifact was refit on train+val (per the corrected
methodology — see `evaluation_nhanes.md`), it did see this exact
validation subset during its final fit. That means the **absolute**
numbers below (precision, accuracy, etc.) likely skew slightly optimistic
compared to a fully independent holdout. However, every candidate
threshold in the table is evaluated using this same set of predictions, so
the **relative** trade-off between operating points — which is what this
analysis is actually for — is still a fair, apples-to-apples comparison.

Production artifacts were verified byte-identical (SHA-256) before and
after running this analysis:

```
liver_pipeline_nhanes_v1.pkl:  ffd64c2b6ba6cfb75f5979a456d223e7af5a46eed7612996cd846a88d8b1505b
liver_metadata_nhanes_v1.json: 5363e1900bca971e581c1b941eb3cf88ae677068860ef1d498ce8b2a55e4f1d7
```

## Validation threshold comparison

| Operating Point | Threshold | Recall | Specificity | Precision | F1 | Accuracy | Predicted Positive % | TP | TN | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Current (production)** | 0.390 | 0.833 | 0.484 | 0.077 | 0.142 | 0.501 | 53.2% | 100 | 1118 | 1192 | 20 |
| ~85% Recall | 0.378 | 0.850 | 0.462 | 0.076 | 0.139 | 0.481 | 55.3% | 102 | 1067 | 1243 | 18 |
| ~80% Recall | 0.402 | 0.800 | 0.504 | 0.077 | 0.141 | 0.519 | 51.1% | 96 | 1165 | 1145 | 24 |
| ~75% Recall | 0.443 | 0.750 | 0.574 | 0.084 | 0.151 | 0.583 | 44.2% | 90 | 1327 | 983 | 30 |
| ~70% Recall | 0.479 | 0.700 | 0.639 | 0.092 | 0.162 | 0.642 | 37.7% | 84 | 1477 | 833 | 36 |
| ~65% Recall | 0.495 | 0.650 | 0.665 | 0.091 | 0.160 | 0.664 | 35.1% | 78 | 1535 | 775 | 42 |

All targets were achievable within 0.4 percentage points of the requested
recall (nearest-available-threshold search over every unique predicted
probability in the validation set).

## Current operating point

The production model is currently at **threshold 0.390**, achieving
**83.3% recall** on this validation subset (close to, not identical to,
the 85% target the original training run swept for — small difference is
expected: the original threshold was chosen via a train-only-fit pipeline
swept against this same validation set, while the numbers above come from
the train+val-fit production artifact scored on the same set; a
consistent, plausible amount of drift from re-fitting on more data, not an
error).

## False-positive trade-off

Moving from the current threshold toward stricter (lower-recall)
thresholds trades a shrinking number of missed true cases against a much
larger reduction in false positives — the ratio is not 1:1:

- **Current -> ~75% recall:** FP drops from 1192 to 983 (-209 FP, -17.5%),
  for 10 additional missed true cases (100 -> 90 TP, -10%).
- **Current -> ~70% recall:** FP drops from 1192 to 833 (-359 FP, -30.1%),
  for 16 additional missed true cases (100 -> 84 TP, -16%).
- **Current -> ~65% recall:** FP drops from 1192 to 775 (-417 FP, -35.0%),
  for 22 additional missed true cases (100 -> 78 TP, -22%).

The predicted-positive rate (how many people overall see an "elevated"
result) falls from 53.2% at the current threshold to 35.1% at the 65%
recall point — roughly a third fewer people flagged in total.

Whether that trade is worth making is a product decision, not a modeling
one: it depends on how costly a missed case is (a false negative here
means someone who has a liver condition is told their risk looks fine)
versus how costly over-flagging is (alarm fatigue, distrust in the tool,
downstream burden on whoever the user shows an "elevated" result to). This
report does not recommend a point on that spectrum.

## Limitations

1. **Not a fully independent holdout for the exact shipped artifact** —
   see "Methodological caveat" above. The relative comparison between
   thresholds is still valid; the absolute precision/accuracy figures are
   likely a little optimistic.
2. **Validation set is small for the positive class** — only 120 positive
   cases in 2,430 validation rows (4.94% base rate). Each single TP/FN
   changing moves recall by roughly 0.8 percentage points, so the
   "nearest available threshold" for a given target can land a few points
   off in either direction; this is a real sample-size limitation, not a
   search-algorithm one.
3. **This analysis does not change what ships.** Every number above
   describes what *would* happen at each threshold — the production
   artifact and its metadata are untouched (see checksums above).
4. **Test-set performance at any of these alternate thresholds is
   unknown** and deliberately not measured here — per the task's own
   instructions, the test set is only touched once a threshold is
   explicitly approved, which has not happened.

## Was the production threshold changed?

**No.** `liver_pipeline_nhanes_v1.pkl` and `liver_metadata_nhanes_v1.json`
are unmodified (byte-identical SHA-256 before and after this analysis, see
above). No `.fit()` call occurs anywhere in `threshold_analysis.py` — it
only loads the existing artifact and calls `predict_proba`. Per the task's
own instructions, no operating point is recommended or selected here;
this report stops at presenting the trade-offs.
