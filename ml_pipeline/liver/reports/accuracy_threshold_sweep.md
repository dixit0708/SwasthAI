# Liver Model — Full Accuracy/Threshold Sweep (Validation Only, 0.10–0.90)

**This is an analysis only.** No model was retrained, refit, or modified. No
feature, preprocessing step, or production threshold was changed. This
extends `threshold_analysis.md` (which compared a handful of recall-targeted
operating points) with a complete sweep of every threshold from 0.10 to 0.90
in steps of 0.01 (81 points), scored on the same validation split, so the
full accuracy/precision/recall/specificity/F1 curve can be inspected rather
than a handful of sampled points.

## Data split and validation-only confirmation

Identical reproduction to `threshold_analysis.md`: 60/20/20 train/validation/
test, stratified, `random_state=42`, split constants imported directly from
`train_nhanes.py`. **Validation set: n=2,430.** The test set is never
scored or inspected anywhere in this script.

## Positive-class prevalence (read this before the accuracy numbers below)

**Prevalence in the validation set: 4.94% (120 of 2,430 rows are positive).**

This dataset is heavily imbalanced. A trivial classifier that predicts
"no liver condition" for every single row, with zero medical reasoning,
would already score **95.06% accuracy** on this validation set just by
majority-class guessing. That baseline number is the correct lens for
reading every accuracy figure below — a high accuracy here is not, by
itself, evidence the model has learned anything useful; it can equally
reflect the model predicting the majority class almost all the time. This
is exactly why `evaluation_nhanes.md` and `threshold_analysis.md` lead with
precision/recall/F1/ROC-AUC rather than accuracy as the primary metrics for
this model.

## Method

Loads the already-fit, already-shipped production artifact
(`joblib.load`, zero `.fit()` calls) and calls `predict_proba` once on the
validation split. Every threshold below is evaluated against that same
fixed set of predicted probabilities — sweeping the threshold does not
re-run inference, it only changes where the cutoff for "positive" is drawn.
Production artifacts were verified byte-identical (SHA-256) before and
after running this analysis:

```
liver_pipeline_nhanes_v1.pkl:  ffd64c2b6ba6cfb75f5979a456d223e7af5a46eed7612996cd846a88d8b1505b
liver_metadata_nhanes_v1.json: 5363e1900bca971e581c1b941eb3cf88ae677068860ef1d498ce8b2a55e4f1d7
```

Same methodological caveat as `threshold_analysis.md` applies: the shipped
artifact was refit on train+val, so it saw this exact validation subset
during its final fit — the *relative* shape of the curve below (how
accuracy/precision/recall trade off against each other as the threshold
moves) is a fair comparison; the *absolute* numbers likely skew a little
optimistic versus a fully independent holdout.

## Full sweep (threshold 0.10 to 0.90, step 0.01)

| Thresh | Accuracy | Precision | Recall | Specificity | F1 | TP | TN | FP | FN | Pred.Pos.% |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.10 | 0.066 | 0.050 | 1.000 | 0.017 | 0.096 | 120 | 40 | 2270 | 0 | 98.4% |
| 0.11 | 0.070 | 0.050 | 0.992 | 0.022 | 0.095 | 119 | 50 | 2260 | 1 | 97.9% |
| 0.12 | 0.077 | 0.050 | 0.992 | 0.029 | 0.096 | 119 | 68 | 2242 | 1 | 97.2% |
| 0.13 | 0.086 | 0.051 | 0.992 | 0.039 | 0.097 | 119 | 91 | 2219 | 1 | 96.2% |
| 0.14 | 0.094 | 0.051 | 0.992 | 0.048 | 0.098 | 119 | 110 | 2200 | 1 | 95.4% |
| 0.15 | 0.103 | 0.052 | 0.992 | 0.057 | 0.098 | 119 | 132 | 2178 | 1 | 94.5% |
| 0.16 | 0.119 | 0.053 | 0.992 | 0.073 | 0.100 | 119 | 169 | 2141 | 1 | 93.0% |
| 0.17 | 0.136 | 0.054 | 0.992 | 0.092 | 0.102 | 119 | 212 | 2098 | 1 | 91.2% |
| 0.18 | 0.150 | 0.055 | 0.992 | 0.106 | 0.103 | 119 | 246 | 2064 | 1 | 89.8% |
| 0.19 | 0.160 | 0.055 | 0.992 | 0.116 | 0.104 | 119 | 269 | 2041 | 1 | 88.9% |
| 0.20 | 0.179 | 0.056 | 0.992 | 0.136 | 0.107 | 119 | 315 | 1995 | 1 | 87.0% |
| 0.21 | 0.198 | 0.058 | 0.992 | 0.156 | 0.109 | 119 | 361 | 1949 | 1 | 85.1% |
| 0.22 | 0.216 | 0.058 | 0.983 | 0.176 | 0.110 | 118 | 407 | 1903 | 2 | 83.2% |
| 0.23 | 0.229 | 0.059 | 0.983 | 0.190 | 0.112 | 118 | 439 | 1871 | 2 | 81.9% |
| 0.24 | 0.244 | 0.060 | 0.983 | 0.206 | 0.114 | 118 | 476 | 1834 | 2 | 80.3% |
| 0.25 | 0.264 | 0.062 | 0.983 | 0.227 | 0.117 | 118 | 524 | 1786 | 2 | 78.4% |
| 0.26 | 0.279 | 0.063 | 0.983 | 0.243 | 0.119 | 118 | 561 | 1749 | 2 | 76.8% |
| 0.27 | 0.297 | 0.064 | 0.975 | 0.262 | 0.120 | 117 | 605 | 1705 | 3 | 75.0% |
| 0.28 | 0.314 | 0.064 | 0.950 | 0.281 | 0.120 | 114 | 650 | 1660 | 6 | 73.0% |
| 0.29 | 0.331 | 0.066 | 0.950 | 0.299 | 0.123 | 114 | 690 | 1620 | 6 | 71.4% |
| 0.30 | 0.348 | 0.066 | 0.933 | 0.318 | 0.124 | 112 | 734 | 1576 | 8 | 69.5% |
| 0.31 | 0.365 | 0.068 | 0.933 | 0.335 | 0.127 | 112 | 775 | 1535 | 8 | 67.8% |
| 0.32 | 0.387 | 0.070 | 0.925 | 0.359 | 0.130 | 111 | 829 | 1481 | 9 | 65.5% |
| 0.33 | 0.403 | 0.069 | 0.892 | 0.378 | 0.129 | 107 | 873 | 1437 | 13 | 63.5% |
| 0.34 | 0.426 | 0.071 | 0.883 | 0.403 | 0.132 | 106 | 930 | 1380 | 14 | 61.2% |
| 0.35 | 0.442 | 0.073 | 0.875 | 0.419 | 0.134 | 105 | 969 | 1341 | 15 | 59.5% |
| 0.36 | 0.457 | 0.074 | 0.867 | 0.435 | 0.136 | 104 | 1006 | 1304 | 16 | 57.9% |
| 0.37 | 0.472 | 0.075 | 0.858 | 0.452 | 0.138 | 103 | 1043 | 1267 | 17 | 56.4% |
| 0.38 | 0.485 | 0.076 | 0.850 | 0.466 | 0.140 | 102 | 1077 | 1233 | 18 | 54.9% |
| **0.39** † | **0.501** | **0.077** | **0.833** | **0.484** | **0.142** | **100** | **1118** | **1192** | **20** | **53.2%** |
| 0.40 | 0.519 | 0.079 | 0.817 | 0.503 | 0.144 | 98 | 1163 | 1147 | 22 | 51.2% |
| 0.41 | 0.530 | 0.078 | 0.792 | 0.517 | 0.143 | 95 | 1194 | 1116 | 25 | 49.8% |
| 0.42 | 0.553 | 0.081 | 0.783 | 0.541 | 0.147 | 94 | 1249 | 1061 | 26 | 47.5% |
| 0.43 | 0.567 | 0.083 | 0.775 | 0.556 | 0.150 | 93 | 1284 | 1026 | 27 | 46.0% |
| 0.44 | 0.581 | 0.084 | 0.758 | 0.571 | 0.152 | 91 | 1320 | 990 | 29 | 44.5% |
| 0.45 | 0.598 | 0.087 | 0.750 | 0.590 | 0.156 | 90 | 1363 | 947 | 30 | 42.7% |
| 0.46 | 0.617 | 0.089 | 0.733 | 0.611 | 0.159 | 88 | 1412 | 898 | 32 | 40.6% |
| 0.47 | 0.630 | 0.089 | 0.708 | 0.626 | 0.159 | 85 | 1445 | 865 | 35 | 39.1% |
| 0.48 | 0.645 | 0.092 | 0.700 | 0.642 | 0.163 | 84 | 1484 | 826 | 36 | 37.4% |
| 0.49 | 0.660 | 0.091 | 0.658 | 0.660 | 0.161 | 79 | 1525 | 785 | 41 | 35.6% |
| 0.50 | 0.671 | 0.092 | 0.642 | 0.672 | 0.161 | 77 | 1553 | 757 | 43 | 34.3% |
| 0.51 | 0.685 | 0.093 | 0.617 | 0.689 | 0.162 | 74 | 1591 | 719 | 46 | 32.6% |
| 0.52 | 0.694 | 0.095 | 0.608 | 0.698 | 0.164 | 73 | 1613 | 697 | 47 | 31.7% |
| 0.53 | 0.707 | 0.098 | 0.600 | 0.712 | 0.168 | 72 | 1645 | 665 | 48 | 30.3% |
| 0.54 | 0.721 | 0.098 | 0.567 | 0.729 | 0.167 | 68 | 1685 | 625 | 52 | 28.5% |
| 0.55 | 0.735 | 0.100 | 0.550 | 0.744 | 0.170 | 66 | 1719 | 591 | 54 | 27.0% |
| 0.56 | 0.750 | 0.105 | 0.542 | 0.761 | 0.176 | 65 | 1758 | 552 | 55 | 25.4% |
| 0.57 | 0.760 | 0.106 | 0.517 | 0.773 | 0.175 | 62 | 1785 | 525 | 58 | 24.2% |
| 0.58 | 0.769 | 0.104 | 0.483 | 0.784 | 0.171 | 58 | 1810 | 500 | 62 | 23.0% |
| 0.59 | 0.779 | 0.109 | 0.483 | 0.794 | 0.177 | 58 | 1834 | 476 | 62 | 22.0% |
| 0.60 | 0.789 | 0.111 | 0.467 | 0.806 | 0.179 | 56 | 1862 | 448 | 64 | 20.7% |
| 0.61 | 0.799 | 0.112 | 0.442 | 0.818 | 0.178 | 53 | 1889 | 421 | 67 | 19.5% |
| 0.62 | 0.812 | 0.120 | 0.442 | 0.831 | 0.188 | 53 | 1920 | 390 | 67 | 18.2% |
| 0.63 | 0.821 | 0.122 | 0.425 | 0.842 | 0.190 | 51 | 1944 | 366 | 69 | 17.2% |
| 0.64 | 0.828 | 0.120 | 0.392 | 0.851 | 0.184 | 47 | 1965 | 345 | 73 | 16.1% |
| 0.65 | 0.834 | 0.119 | 0.367 | 0.858 | 0.179 | 44 | 1983 | 327 | 76 | 15.3% |
| 0.66 | 0.841 | 0.120 | 0.350 | 0.867 | 0.179 | 42 | 2002 | 308 | 78 | 14.4% |
| 0.67 | 0.849 | 0.124 | 0.342 | 0.875 | 0.182 | 41 | 2021 | 289 | 79 | 13.6% |
| 0.68 | 0.855 | 0.125 | 0.325 | 0.882 | 0.181 | 39 | 2038 | 272 | 81 | 12.8% |
| 0.69 | 0.863 | 0.128 | 0.308 | 0.891 | 0.181 | 37 | 2059 | 251 | 83 | 11.9% |
| 0.70 | 0.869 | 0.130 | 0.292 | 0.899 | 0.180 | 35 | 2076 | 234 | 85 | 11.1% |
| 0.71 | 0.878 | 0.130 | 0.258 | 0.910 | 0.173 | 31 | 2103 | 207 | 89 | 9.8% |
| 0.72 | 0.885 | 0.140 | 0.258 | 0.918 | 0.182 | 31 | 2120 | 190 | 89 | 9.1% |
| 0.73 | 0.890 | 0.134 | 0.225 | 0.924 | 0.168 | 27 | 2135 | 175 | 93 | 8.3% |
| 0.74 | 0.895 | 0.138 | 0.217 | 0.930 | 0.169 | 26 | 2148 | 162 | 94 | 7.7% |
| 0.75 | 0.900 | 0.145 | 0.208 | 0.936 | 0.171 | 25 | 2163 | 147 | 95 | 7.1% |
| 0.76 | 0.906 | 0.148 | 0.192 | 0.943 | 0.167 | 23 | 2178 | 132 | 97 | 6.4% |
| 0.77 | 0.911 | 0.156 | 0.183 | 0.948 | 0.169 | 22 | 2191 | 119 | 98 | 5.8% |
| 0.78 | 0.916 | 0.163 | 0.167 | 0.955 | 0.165 | 20 | 2207 | 103 | 100 | 5.1% |
| 0.79 | 0.921 | 0.174 | 0.158 | 0.961 | 0.166 | 19 | 2220 | 90 | 101 | 4.5% |
| 0.80 | 0.926 | 0.186 | 0.150 | 0.966 | 0.166 | 18 | 2231 | 79 | 102 | 4.0% |
| 0.81 | 0.932 | 0.212 | 0.142 | 0.973 | 0.170 | 17 | 2247 | 63 | 103 | 3.3% |
| 0.82 | 0.935 | 0.209 | 0.117 | 0.977 | 0.150 | 14 | 2257 | 53 | 106 | 2.8% |
| 0.83 | 0.938 | 0.228 | 0.108 | 0.981 | 0.147 | 13 | 2266 | 44 | 107 | 2.3% |
| 0.84 | 0.941 | 0.250 | 0.100 | 0.984 | 0.143 | 12 | 2274 | 36 | 108 | 2.0% |
| 0.85 | 0.941 | 0.227 | 0.083 | 0.985 | 0.122 | 10 | 2276 | 34 | 110 | 1.8% |
| 0.86 | 0.944 | 0.273 | 0.075 | 0.990 | 0.118 | 9 | 2286 | 24 | 111 | 1.4% |
| 0.87 | 0.946 | 0.300 | 0.075 | 0.991 | 0.120 | 9 | 2289 | 21 | 111 | 1.2% |
| 0.88 | 0.948 | 0.360 | 0.075 | 0.993 | 0.124 | 9 | 2294 | 16 | 111 | 1.0% |
| 0.89 | 0.948 | 0.364 | 0.067 | 0.994 | 0.113 | 8 | 2296 | 14 | 112 | 0.9% |
| **0.90** | **0.949** | 0.400 | 0.050 | 0.996 | 0.089 | 6 | 2301 | 9 | 114 | 0.6% |

† Row 0.39 is the current production threshold.

## Threshold giving maximum accuracy

**Threshold 0.90 (the top edge of the requested sweep range) gives the
maximum accuracy in this range: 94.94%.**

Read this in light of the prevalence figure above, not on its own: at
threshold 0.90 the model predicts "positive" for only 0.6% of the
validation set (15 people out of 2,430) and catches just **6 of 120** true
cases (recall 5.0%). Its accuracy is high almost entirely *because* it
predicts the majority class ("no liver condition") for 99.4% of everyone,
which is very close to the 95.06% you'd get by predicting the majority
class unconditionally for every single row. This is not evidence of a
better model at 0.90 than at 0.39 — it is evidence that accuracy is the
wrong optimization target on a 4.94%-prevalence dataset for a screening
tool whose stated purpose is catching true cases (see `evaluation_nhanes.md`
and `threshold_analysis.md`, both of which lead with recall/precision/F1/
ROC-AUC for exactly this reason).

## Thresholds reaching 80%, 85%, 90% accuracy

- **≥80% accuracy:** thresholds 0.62 through 0.90 (29 of the 81 swept
  thresholds), recall at those points ranging from 44.2% down to 5.0%.
- **≥85% accuracy:** thresholds 0.68 through 0.90 (23 of the 81 swept
  thresholds), recall ranging from 32.5% down to 5.0%.
- **≥90% accuracy:** thresholds 0.75 through 0.90 (16 of the 81 swept
  thresholds), recall ranging from 20.8% down to 5.0%.

In every one of these bands, accuracy rises specifically because recall is
falling — the model is simply predicting "negative" more often, which is
cheap to do correctly when 95% of the validation set actually is negative.
None of these three accuracy bands overlaps with the 65–85% recall range
examined in `threshold_analysis.md`; reaching 80%+ accuracy on this dataset
requires recall below ~44%, which would mean missing more than half of all
true cases — not a trade this report recommends or evaluates as
acceptable, consistent with the instruction not to select or rank a "best"
threshold here.

## Why accuracy is a misleading headline metric for this model

This is the concrete illustration of the point `evaluation_nhanes.md`
limitation #3 already makes in the abstract: a 4.94%-prevalence target
means a model can score arbitrarily close to 95% accuracy by refusing to
flag almost anyone, while providing zero screening value. The sweep above
shows this directly — accuracy and recall move in *opposite* directions
across nearly the entire threshold range (accuracy climbs from 6.6% to
94.9% as threshold rises from 0.10 to 0.90, while recall falls from 100%
to 5.0% over the same range). Any threshold chosen to maximize accuracy on
this dataset will, by construction, undermine the model's stated purpose
as a sensitivity-first screening flag.

## Limitations

1. **Not a fully independent holdout for the exact shipped artifact** — same
   caveat as `threshold_analysis.md`: the production pipeline was refit on
   train+val, so absolute numbers here likely skew a little optimistic; the
   relative shape of the curve is still a fair comparison.
2. **Validation set is small for the positive class** (120 positive cases in
   2,430 rows) — at high thresholds, single-digit true-positive counts mean
   each additional missed case moves recall by roughly 0.8 percentage
   points; the exact recall value at very strict thresholds (e.g. 0.85-0.90)
   should be read as approximate, not precise to the decimal shown.
3. **Test-set performance at any threshold shown here is unknown and
   deliberately not measured** — the test set is untouched, consistent with
   "touched exactly once, only after a threshold is explicitly approved,"
   which has not happened.
4. **This analysis does not change what ships.** Every number above
   describes what *would* happen at each threshold; the production artifact
   and its metadata are unmodified (see checksums above).

## Was the production threshold changed?

**No.** `liver_pipeline_nhanes_v1.pkl` and `liver_metadata_nhanes_v1.json`
are unmodified (byte-identical SHA-256 before and after this analysis, see
above). No `.fit()` call occurs anywhere in `accuracy_threshold_sweep.py` —
it only loads the existing artifact and calls `predict_proba`. No threshold
is recommended, ranked, or selected here; per the task's own instructions,
this report stops at presenting the sweep and its correct interpretation.
