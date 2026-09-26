# liver-nhanes-v2 — Removal of `general_health`

## What changed and why

`general_health` (the self-rated "In general, would you say your health
is: Excellent / Very good / Good / Fair / Poor" question) was removed from
the feature set by explicit product decision — this was not prompted by a
data-quality problem, a leakage finding, or a fairness concern. The
feature passed every integrity check applied during v1's development.

This is a straight feature removal, not a re-investigation: the exact same
methodology as v1 was rerun on the 10 remaining features (60/20/20 stratified
split, same 3-model-family comparison, same validation-only recall-sweep
threshold selection, same final refit-on-train+val). See `train_nhanes_v2.py`.

## Honest before/after comparison

| Metric | v1 (11 features, incl. general_health) | v2 (10 features) | Change |
|---|---:|---:|---:|
| Test ROC-AUC | 0.748 | 0.719 | **-0.029** |
| Test Accuracy | 52.4% | 45.8% | -6.6 pp |
| Test Precision | 8.2% | 7.2% | -1.0 pp |
| Test Recall | 85.0% | 84.2% | -0.8 pp (both sensitivity-first, ~equivalent) |
| Test F1 | 0.150 | 0.133 | -0.017 |
| Decision threshold | 0.390 | 0.380 | ~unchanged |
| False positives (test, n=2310 negatives) | 1,138 (49.3%) | 1,297 (56.1%) | **+159 FP (+6.9 pp)** |
| False negatives (test, n=120 positives) | 18 | 19 | +1 |
| Winning model family | Logistic Regression | Logistic Regression | unchanged |

**Do not describe v2 as equivalent to v1.** `general_health` was a real,
non-trivial contributor to this model's discrimination ability — removing
it cost 0.029 ROC-AUC points and, at a matched recall target (~84-85%),
increased the false-positive rate by nearly 7 percentage points (159 more
people out of 2,310 true negatives would see an "elevated" result under
v2 than under v1, for roughly the same number of true cases caught). This
is a genuine, measured cost of the removal, not a modeling artifact —
consistent with published BRFSS/NHANES literature, where self-rated
general health is consistently one of the stronger predictors available
short of lab values, because it implicitly summarizes a person's
subjective sense of many symptoms and comorbidities the other retained
features (BMI, waist circumference, smoking, alcohol, diabetes/hypertension
status, activity) capture only partially.

## What did not change

- Model family selected: Logistic Regression (both v1 and v2)
- Split methodology, random seed, threshold-selection rule
- All other 10 features and their definitions
- The production disclaimer and non-diagnostic framing

## Artifacts

- `artifacts/liver_pipeline_nhanes_v2.pkl` / `artifacts/liver_metadata_nhanes_v2.json` (new)
- `artifacts/liver_pipeline_nhanes_v1.pkl` / `artifacts/liver_metadata_nhanes_v1.json` (unchanged, preserved as the historical baseline this table compares against)
