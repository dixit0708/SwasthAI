# Original ILPD Dataset — Provenance, Integrity, and Model Investigation

**Status: investigation only.** No production file, backend route, or
frontend code was modified. No model artifact from this investigation was
saved to `artifacts/` or wired into the application. This report exists to
answer one question: does the original, documented 583-row ILPD dataset
support a trustworthy lab-based liver model, in contrast to the
30,691-row "LPD" file investigated separately (see
`ml_pipeline/liver_lpd/reports/data_integrity_investigation.md`), which was
found to have a near-deterministic, apparently synthetic label?

## 1. Exact source and provenance

The raw file used for the original `liver-ilpd-v1` model (retired,
`artifacts/liver_pipeline.pkl`) was `Indian_Liver_Patient_549_Clean_Dataset.xlsx`
— but that file is **no longer present anywhere in this project or in the
locations checked** (it was never committed, since `ml_pipeline/*/data/` is
gitignored, and it has since been deleted from wherever it was originally
downloaded). Per this task's instruction to use "the original, documented
583-row ILPD dataset," this investigation downloads that dataset fresh from
its canonical, citable academic source rather than trying to recover the
untraceable "549-row clean" derivative that no longer exists:

- **Source:** UCI Machine Learning Repository, dataset id 225 —
  `https://archive.ics.uci.edu/ml/machine-learning-databases/00225/Indian%20Liver%20Patient%20Dataset%20(ILPD).csv`
- **Citation:** Ramana, B. & Venkateswarlu, N. (2022). *ILPD (Indian Liver
  Patient Dataset)*. UCI Machine Learning Repository.
  https://doi.org/10.24432/C5D02C
- **License:** CC BY 4.0 (Creative Commons Attribution)
- **Collected from:** Northeast Andhra Pradesh, India
- Saved locally at `data/raw/ilpd_uci_original.csv`
  (SHA-256: `84feac16488de5cf89bd22bd802c77f25841fe93e9ddd32355683e94d46c3425`)
  — gitignored like every other `ml_pipeline/*/data/` directory in this
  repo, consistent with Section 7.

This is a different, smaller, independently-sourced file from the
30,691-row "LPD" file used in the parallel investigation — nothing here was
derived from that file.

## 2. Rows, columns, features, target

- **583 raw rows, 11 columns** (10 features + 1 target) — matches the
  canonical, widely-cited size of this dataset exactly.
- **Gender split: 441 Male / 142 Female** — matches UCI's stated
  demographic breakdown exactly, independently confirming this is the
  authentic file (not a mislabeled or substituted one).
- **Feature names used** (renamed to this project's existing snake_case
  convention, matching the retired `liver-ilpd-v1` contract exactly):
  `age_years, gender, total_bilirubin_mg_dl, direct_bilirubin_mg_dl,
  alkaline_phosphatase_u_l, alanine_aminotransferase_u_l,
  aspartate_aminotransferase_u_l, total_proteins_g_dl, albumin_g_dl,
  albumin_globulin_ratio`.
- **Target definition:** raw `Selector` column, 1 = liver patient, 2 = not
  a liver patient, remapped here to 1/0 (1 = disease-positive), identical
  convention to every other model in this project.

## 3. Class distribution

Raw: **416 liver patients (1) / 167 non-patients (2)** — matches UCI's
documentation exactly. After dropping exact duplicates (below): **406 / 164**
(positive rate 71.2%) — a real, if severe, class imbalance, but one that
comes from the actual population this dataset draws from (liver clinics
naturally see more positive than negative cases), not a fabricated skew.

## 4. Duplicate rows

**13 exact full-row duplicates out of 583 (2.2%).** Dropped before any
split, CV fold, or metric — the same discipline applied throughout this
project, but at a scale (2.2%) consistent with an authentic small clinical
dataset, not the 36.9% found in the "LPD" file, which was itself one of the
signals that file's labels looked artificially generated.

## 5. Missing values

**4 missing values, all in `albumin_globulin_ratio`.** Note: the UCI
project page's own summary states "no missing values reported" — that
claim was checked directly against the actual file rather than trusted,
and found to be incorrect; this is a minor, well-known discrepancy (several
independent ILPD tutorials/papers also report these same 4 missing A/G
Ratio values), not a concern about the file's authenticity. Handled here
via in-pipeline median imputation (see Section 7), not by dropping rows.

## 6. Target leakage check

Two independent checks, both negative (no leakage found):

**(a) Single-feature ROC-AUC** — checks whether any one column alone
near-encodes the label:

| Feature | Single-feature ROC-AUC |
|---|---:|
| aspartate_aminotransferase_u_l | 0.697 |
| total_bilirubin_mg_dl | 0.693 |
| direct_bilirubin_mg_dl | 0.686 |
| alanine_aminotransferase_u_l | 0.686 |
| alkaline_phosphatase_u_l | 0.674 |
| age_years | 0.583 |
| total_proteins_g_dl | 0.479 |
| albumin_g_dl | 0.393 |

All modest and clinically plausible (liver enzymes/bilirubin moderately
associated with liver disease, as expected) — nothing near-deterministic.

**(b) Decision-tree depth sweep** — the decisive test used on the
suspect LPD file. If a fully-grown single tree can achieve near-perfect
test accuracy, the label is a near-deterministic function of the inputs
(a red flag). Here:

| Max depth | Test accuracy | Test ROC-AUC | Leaves |
|---:|---:|---:|---:|
| 2 | 0.711 | 0.761 | 4 |
| 3 | 0.719 | 0.744 | 8 |
| 4 | 0.702 | 0.747 | 14 |
| 6 | 0.675 | 0.675 | 30 |
| **unlimited** | **0.614** | **0.513** | 92 |

**This is exactly the healthy pattern real, noisy clinical data should
show** — accuracy peaks at a shallow depth (2-3) and then *degrades* as the
tree is allowed to overfit, eventually reaching near-random performance
(ROC-AUC 0.513) at unlimited depth. This is the opposite of what the LPD
file showed (accuracy *improving* to a perfect 1.0 at unlimited depth) and
is strong evidence this dataset's labels reflect genuine, irreducible
diagnostic uncertainty rather than a hidden deterministic rule. **No target
leakage found.**

## 7. Is preprocessing fitted exclusively inside each training fold?

**Yes, in this investigation.** `ilpd_investigation.py` builds a single
`sklearn.pipeline.Pipeline` (median imputer → standard scaler → one-hot
encoder → classifier) and passes the *unfit* pipeline into
`cross_val_predict`, which refits it independently on each fold's training
portion only. No statistic (median, mean, scale, or category list) is ever
computed on data outside that fold's training split. The only step
performed before cross-validation is dropping exact duplicate rows, which
removes rows outright rather than computing any fitted statistic, so it
does not leak fold information.

**This was not true of the retired implementation** — see Section 8.

## 8. Retired `liver-ilpd-v1` implementation: what to preserve vs. discard

Reviewed `ml_pipeline/liver/train.py` (still present, untouched) against
what this investigation actually needed:

**Preserve** (still the right call):
- `ColumnTransformer` structure — `StandardScaler` on the 9 numeric
  columns, `OneHotEncoder(drop="first")` on `gender` — reused as-is here.
- `class_weight="balanced"` (LogisticRegression/RandomForest) and
  `scale_pos_weight` (XGBoost) to handle the 71%/29% imbalance — reused
  as-is.
- The exact feature-naming convention (`age_years`,
  `total_bilirubin_mg_dl`, etc.) — reused as-is, so this stays
  compatible with the existing (retired but preserved) `LiverPredictionInput`-style
  contract shape if this is ever revisited for production.

**Discard / do differently** (issues this investigation fixed):
- The retired script called `df.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN])`
  **before** any split — for the 4 missing `albumin_globulin_ratio` values
  this has no real leakage impact (dropping rows outright, not fitting a
  statistic), but it does needlessly throw away otherwise-usable rows.
  This investigation imputes them inside the pipeline instead.
- The retired script used a single 80/20 split with **no validation set
  and no threshold sweep** — it hardcoded `threshold = 0.4` with a
  one-line comment ("we choose 0.4 to bias slightly towards recall")
  rather than deriving it from data. This investigation instead reports
  the full accuracy/precision/recall/specificity/F1 trade-off across
  thresholds (Section 10) so any future threshold choice is evidence-based,
  not guessed.
- The retired script evaluated only ROC-AUC during model comparison — no
  PR-AUC, precision, recall, specificity, or F1 at the comparison stage,
  and accuracy was only checked at the end, on one arbitrary threshold.
  This investigation reports the full metric set at every stage, per this
  task's explicit "do not optimize for accuracy alone" instruction.

## 9. Leakage-safe model comparison (5-fold stratified CV, out-of-fold predictions)

`cross_val_predict(..., method="predict_proba")` with `StratifiedKFold(n_splits=5)`
produces genuine out-of-fold probabilities for all 570 rows (post-dedup) —
every row's prediction comes from a fold that never trained on it. Metrics
below are computed from those out-of-fold predictions at threshold 0.5
(full threshold sweep is Section 10 — this table is not meant to already
reflect an optimal decision point):

| Model | ROC-AUC | PR-AUC | Accuracy | Precision | Recall | Specificity | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Logistic Regression** | **0.745** | 0.890 | 0.633 | 0.880 | 0.562 | 0.811 | 0.686 |
| Random Forest | 0.717 | 0.876 | 0.690 | 0.805 | 0.744 | 0.555 | 0.773 |
| XGBoost | 0.691 | 0.861 | 0.670 | 0.777 | 0.754 | 0.463 | 0.765 |

Note on PR-AUC: with a 71.2% positive base rate, a random/no-skill
classifier's PR-AUC baseline is already ~0.71 — so 0.86-0.89 across all
three models is a real but modest lift above chance, not an
independently large number the way it would be on a rare-disease dataset.

**Logistic Regression wins by ROC-AUC** (0.745), consistent with:
- the retired `liver-ilpd-v1`'s own reported test ROC-AUC of 0.783 (same
  model family, similar-but-not-identical row count due to the "549 clean"
  vs. this investigation's "570 post-dedup" preprocessing difference),
  and
- published literature on this exact dataset, and
- this project's own `liver-nhanes-v1` (ROC-AUC 0.748) and
  `liver_lpd`'s honest Logistic Regression result (ROC-AUC 0.762) —
  three independent liver datasets, three independently-trained Logistic
  Regression models, all landing in the same realistic 0.74-0.78 band.
  That consistency is itself evidence this number is real, not noise.

Random Forest and XGBoost score *lower* here than Logistic Regression —
the opposite pattern from the suspect LPD file, where tree models
suspiciously *outscored* Logistic Regression by 0.24 ROC-AUC points. On
genuine data at this sample size (570 rows), a well-regularized linear
model outperforming higher-capacity tree ensembles is the expected,
textbook result — small, low-dimensional, mostly-linearly-separable
tabular datasets like this one generally favor linear models, exactly the
same conclusion already documented for `diabetes-pima-v1` in this project.

## 10. Threshold trade-off (out-of-fold predictions, Logistic Regression)

Full sweep, threshold 0.10 to 0.90, on the same out-of-fold probabilities
used above (n=570, 406 positive / 164 negative):

| Threshold | Accuracy | Precision | Recall | Specificity | F1 | TP | TN | FP | FN |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.10 | 0.712 | 0.712 | 1.000 | 0.000 | 0.832 | 406 | 0 | 164 | 0 |
| 0.15 | 0.711 | 0.712 | 0.998 | 0.000 | 0.831 | 405 | 0 | 164 | 1 |
| 0.20 | 0.707 | 0.712 | 0.990 | 0.006 | 0.828 | 402 | 1 | 163 | 4 |
| 0.25 | 0.716 | 0.729 | 0.956 | 0.122 | 0.827 | 388 | 20 | 144 | 18 |
| 0.30 | 0.707 | 0.748 | 0.887 | 0.262 | 0.812 | 360 | 43 | 121 | 46 |
| 0.35 | 0.705 | 0.779 | 0.818 | 0.427 | 0.798 | 332 | 70 | 94 | 74 |
| 0.40 | 0.693 | 0.816 | 0.734 | 0.591 | 0.773 | 298 | 97 | 67 | 108 |
| 0.45 | 0.654 | 0.838 | 0.638 | 0.695 | 0.724 | 259 | 114 | 50 | 147 |
| **0.50** | 0.633 | 0.880 | 0.562 | 0.811 | 0.686 | 228 | 133 | 31 | 178 |
| 0.55 | 0.623 | 0.917 | 0.517 | 0.884 | 0.661 | 210 | 145 | 19 | 196 |
| 0.60 | 0.591 | 0.935 | 0.458 | 0.921 | 0.615 | 186 | 151 | 13 | 220 |
| 0.65 | 0.579 | 0.951 | 0.431 | 0.945 | 0.593 | 175 | 155 | 9 | 231 |
| 0.70 | 0.561 | 0.964 | 0.399 | 0.963 | 0.564 | 162 | 158 | 6 | 244 |
| 0.75 | 0.544 | 0.974 | 0.369 | 0.976 | 0.536 | 150 | 160 | 4 | 256 |
| 0.80 | 0.512 | 0.971 | 0.325 | 0.976 | 0.487 | 132 | 160 | 4 | 274 |
| 0.85 | 0.475 | 0.973 | 0.271 | 0.982 | 0.424 | 110 | 161 | 3 | 296 |
| 0.90 | 0.440 | 0.968 | 0.222 | 0.982 | 0.361 | 90 | 161 | 3 | 316 |

The trade-off shape is the standard one this project's other models also
show: low thresholds catch nearly every true case at the cost of flagging
almost everyone (recall 1.00 / specificity 0.00 at t=0.10); high thresholds
become highly precise but miss most true cases (recall drops to 0.22 by
t=0.90). A sensitivity-first threshold in the same style used elsewhere in
this project (e.g., the lowest threshold still clearing ~80% recall) would
land around **t=0.35-0.38** here (recall ~0.82-0.87, specificity
~0.30-0.43) — noted for context only; **no threshold is being selected or
recommended by this report**, consistent with "do not claim a target
accuracy in advance" and this being an investigation, not a production
decision.

## 11. Does this dataset provide sufficient evidence to proceed to production integration?

**Yes, with the same standard caveats every other model in this project
already carries — this dataset's evidence quality is real, unlike the LPD
file's.**

Specifically:
- Provenance is fully documented and independently verifiable (UCI
  Machine Learning Repository, DOI-cited, CC BY 4.0).
- Both leakage checks (single-feature ROC-AUC, decision-tree depth sweep)
  came back clean — the label behaves like genuine, noisy clinical
  ground truth, not a synthetic or rule-derived one.
- The achieved ROC-AUC (0.745, Logistic Regression, out-of-fold) is
  consistent across three independent sources: this investigation, the
  retired `liver-ilpd-v1`'s original test result (0.783), and published
  literature on the same dataset — three-way agreement is meaningful
  evidence the number is real.
- Preprocessing is genuinely leakage-safe (in-fold imputation/scaling/
  encoding via `cross_val_predict`), which the retired implementation did
  not fully demonstrate.

**What this is not:** evidence that a 95% accuracy target is achievable
here, or that this dataset is large. At 570 rows (post-dedup) it is far
smaller than `liver-nhanes-v1`'s training data (12,147 rows) or the
LPD file's raw size, so any future confidence intervals on its metrics
would be wide, and it inherits the same small-regional-sample limitation
already known for the retired model (Northeast Andhra Pradesh, India;
441 male / 142 female — not necessarily generalizable to other
populations). If a production decision is made to proceed with this
dataset, that would be the next, separate step — this report only
establishes that the underlying evidence is trustworthy enough to make
that decision on, which the LPD file's evidence was not.

## Files touched by this investigation

- `ml_pipeline/liver/data/raw/ilpd_uci_original.csv` (new, gitignored —
  downloaded from UCI, not committed)
- `ml_pipeline/liver/data/raw/` directory created (did not previously
  exist for this pipeline)
- `ml_pipeline/liver/ilpd_investigation.py` (new, analysis-only, saves no
  artifact)
- `ml_pipeline/liver/reports/ilpd_model_investigation.md` (this file)

**Not touched:** `ml_pipeline/liver/artifacts/` (both the retired
`liver-ilpd-v1` and the production `liver-nhanes-v1` files are
unmodified), `backend/`, `frontend/`, and `ml_pipeline/liver_lpd/` (the
separate, still-unresolved investigation from the prior task).
