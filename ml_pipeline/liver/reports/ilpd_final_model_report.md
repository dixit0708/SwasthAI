# Liver Disease Risk Model (Lab-Based / ILPD) — Logistic Regression Candidate

**Status: production candidate artifact only. Not integrated.** No backend
route, frontend page, or API endpoint references this model. The
currently-shipped `liver-nhanes-v1` (lab-free) is unmodified and remains
the only liver assessment actually served by the application. This report
documents a standalone candidate for future integration, built and
evaluated per the task's own explicit methodology.

**This is not a medical diagnostic device.** It produces a liver-disease
risk/assessment score for informational and educational purposes only —
never a diagnosis, never a doctor replacement, never claimed to be
clinically proven or 100% accurate.

## 1. Dataset provenance

- **Name:** ILPD (Indian Liver Patient Dataset)
- **Source:** UCI Machine Learning Repository, dataset id 225 —
  `https://archive.ics.uci.edu/ml/machine-learning-databases/00225/Indian%20Liver%20Patient%20Dataset%20(ILPD).csv`
- **Citation:** Ramana, B. & Venkateswarlu, N. (2022). UCI Machine Learning
  Repository. https://doi.org/10.24432/C5D02C
- **License:** CC BY 4.0
- **Collected from:** Northeast Andhra Pradesh, India
- **Local path:** `ml_pipeline/liver/data/raw/ilpd_uci_original.csv`
  (gitignored, matching every other `ml_pipeline/*/data/` directory)

This is the same file verified in the prior investigation
(`reports/ilpd_model_investigation.md`) — authenticity independently
confirmed there via exact match on gender split (441M/142F) and class
split (416/167) against UCI's own documentation. The rejected 30,691-row
"LPD" file (`ml_pipeline/liver_lpd/`) was **not used anywhere in this
training run**.

## 2. Dataset statistics (verified from the actual file, not assumed)

| Property | Value |
|---|---:|
| Raw rows | 583 |
| Raw columns | 11 (10 features + 1 target) |
| Duplicate rows | 13 |
| Rows after duplicate removal | 570 |
| Missing values (total) | 4 (all in `albumin_globulin_ratio`) |
| Final usable row count | 570 |
| Class distribution | 406 positive (liver patient) / 164 negative |
| Positive rate | 71.23% |

These figures were printed directly by `train_ilpd_logistic.py` at run
time — the task's expected approximate values (583 rows, 13 duplicates, 4
missing, ~570 usable) matched exactly.

## 3. Data cleaning

Exact full-row duplicates were dropped **before** any cross-validation
fold, threshold sweep, or final fit — no duplicate row can appear in more
than one fold. This mirrors the same discipline already applied in the
prior LPD and ILPD investigations.

## 4. Duplicate handling

13 of 583 rows (2.2%) were exact duplicates of another row across all 11
columns. Dropped via `DataFrame.drop_duplicates()` immediately after
loading, before the target column is even separated from the features.

## 5. Missing-value handling

4 missing values, all in `albumin_globulin_ratio` — handled by
`SimpleImputer(strategy="median")` **inside** the `ColumnTransformer`,
never dropped and never imputed on the full dataset before splitting. During
cross-validation this median is recomputed independently on each fold's
training portion only; for the final shipped artifact it is computed once
on the full 570-row cleaned dataset (see Section 9 for why no separate
held-out test set is carved out here).

## 6. Feature list

10 features, in the exact order the pipeline expects
(`metadata["feature_names"]`):

1. `age_years`
2. `total_bilirubin_mg_dl`
3. `direct_bilirubin_mg_dl`
4. `alkaline_phosphatase_u_l`
5. `alanine_aminotransferase_u_l` (ALT/SGPT)
6. `aspartate_aminotransferase_u_l` (AST/SGOT)
7. `total_proteins_g_dl`
8. `albumin_g_dl`
9. `albumin_globulin_ratio`
10. `gender`

**Target:** `liver_disease_status` — derived from the raw `Selector`
column (1 = liver patient -> mapped to 1, 2 = not a liver patient ->
mapped to 0). `Selector`/the target is never included among the input
features.

## 7. Preprocessing

A single `sklearn.pipeline.Pipeline` combining preprocessing and the
classifier, so inference can never accidentally use different
preprocessing than training:

```
ColumnTransformer(
    num: [age_years, total_bilirubin_mg_dl, direct_bilirubin_mg_dl,
          alkaline_phosphatase_u_l, alanine_aminotransferase_u_l,
          aspartate_aminotransferase_u_l, total_proteins_g_dl,
          albumin_g_dl, albumin_globulin_ratio]
      -> SimpleImputer(strategy="median") -> StandardScaler()
    cat: [gender] -> OneHotEncoder(drop="first", handle_unknown="ignore")
) -> LogisticRegression(...)
```

**Critical requirement satisfied:** during the 5-fold cross-validation
used for every reported metric, a **fresh, unfit clone** of this pipeline
is fit independently on each fold's training portion only
(`sklearn.base.clone()` inside the fold loop) — the imputer's median,
the scaler's mean/std, and the encoder's category list are never computed
using a row that fold will then be scored on. The only step performed
before cross-validation is dropping exact duplicate rows outright, which
removes rows rather than fitting a statistic, so it introduces no fold
leakage.

## 8. Model configuration

| Hyperparameter | Value |
|---|---|
| Model type | LogisticRegression |
| Solver | lbfgs |
| Penalty | l2 (scikit-learn default; not passed explicitly to avoid a 1.8+ `FutureWarning` about the deprecated `penalty` kwarg — behavior is identical) |
| C | 1.0 |
| Class weight | balanced |
| Max iterations | 1000 |
| Random state | 42 |

No hyperparameter search was performed — the task explicitly asked to
keep the model simple and reproducible, and Logistic Regression was
already selected (not re-litigated here) based on the prior investigation's
finding that it outperformed Random Forest (ROC-AUC 0.717) and XGBoost
(ROC-AUC 0.691) on this exact dataset.

## 9. Cross-validation methodology

- **Method:** `StratifiedKFold`, 5 folds, `shuffle=True`, `random_state=42`
- **Per fold:** a fresh clone of the pipeline is fit on that fold's
  training rows only; predictions on the held-out fold rows are collected
  as out-of-fold (OOF) probabilities. Every row in the dataset ends up with
  exactly one OOF probability, always produced by a model that never saw
  that row during training.
- **No separate held-out test set is carved out.** At only 570 rows,
  reserving an additional test slice would shrink an already-small dataset
  further without adding rigor beyond what 5-fold OOF cross-validation
  already provides as an unbiased performance estimate — no threshold or
  model-family decision in this script ever touches data after the CV
  loop completes, so there is nothing left for a held-out test set to
  protect against here. (This differs from `train_nhanes.py`'s 60/20/20
  split, which exists there because that pipeline *also* selects a model
  family and threshold from validation and needs a final, doubly-blind
  test set — this script's model family was already fixed *before* this
  run, by the separate prior investigation.)
- All reported CV metrics reflect only held-out fold predictions — no
  training-set (in-sample) performance is reported anywhere in this
  document.

## 10. Final CV metrics

Per-fold results:

| Fold | ROC-AUC | PR-AUC | Accuracy | Precision | Recall | Specificity | F1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.7656 | 0.9059 | 0.5526 | 0.8780 | 0.4390 | 0.8438 | 0.5854 |
| 2 | 0.7482 | 0.8929 | 0.6579 | 0.8750 | 0.6049 | 0.7879 | 0.7153 |
| 3 | 0.7314 | 0.8754 | 0.6579 | 0.8889 | 0.5926 | 0.8182 | 0.7111 |
| 4 | 0.7026 | 0.8732 | 0.6316 | 0.8545 | 0.5802 | 0.7576 | 0.6912 |
| 5 | 0.7856 | 0.9100 | 0.6667 | 0.9057 | 0.5926 | 0.8485 | 0.7164 |

**Mean ± standard deviation across folds:**

| Metric | Mean | Std |
|---|---:|---:|
| ROC-AUC | 0.7467 | 0.0285 |
| PR-AUC | 0.8915 | 0.0151 |
| Accuracy | 0.6333 | 0.0420 |
| Precision | 0.8804 | 0.0168 |
| Recall | 0.5619 | 0.0619 |
| Specificity | 0.8112 | 0.0344 |
| F1 | 0.6839 | 0.0501 |

Note: these accuracy/recall figures are computed at the default 0.5
probability threshold (standard for a fold-level comparison table) — the
**actual selected production threshold** is 0.35, chosen in Section 12
below for materially better recall, at a real cost to specificity.

**Aggregate out-of-fold confusion matrix at threshold 0.5** (n=570):
TP=228, TN=133, FP=31, FN=178.

This 0.7467 ROC-AUC is consistent with three independent sources: the
retired `liver-ilpd-v1`'s own historical test result (0.783, similar
dataset, slightly different cleaning), the rejected `liver_lpd` file's
honest Logistic Regression run (0.762), and this project's
`liver-nhanes-v1` (0.748) — three separately-trained models on three
different datasets landing in the same realistic band is itself evidence
this number reflects genuine signal, not noise.

## 11. Threshold analysis

Full sweep, threshold 0.10 to 0.90 (step 0.01, 81 points), computed on the
same out-of-fold probabilities used above. Selected rows shown below;
every 0.05 step across the full range:

| Threshold | Accuracy | Precision | Recall | Specificity | F1 | TP | TN | FP | FN |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.10 | 0.712 | 0.712 | 1.000 | 0.000 | 0.832 | 406 | 0 | 164 | 0 |
| 0.15 | 0.711 | 0.712 | 0.998 | 0.000 | 0.831 | 405 | 0 | 164 | 1 |
| 0.20 | 0.707 | 0.712 | 0.990 | 0.006 | 0.828 | 402 | 1 | 163 | 4 |
| 0.25 | 0.716 | 0.729 | 0.956 | 0.122 | 0.827 | 388 | 20 | 144 | 18 |
| 0.30 | 0.707 | 0.748 | 0.887 | 0.262 | 0.812 | 360 | 43 | 121 | 46 |
| **0.35** | **0.705** | **0.779** | **0.818** | **0.427** | **0.798** | 332 | 70 | 94 | 74 |
| 0.40 | 0.693 | 0.816 | 0.734 | 0.591 | 0.773 | 298 | 97 | 67 | 108 |
| 0.45 | 0.654 | 0.838 | 0.638 | 0.695 | 0.724 | 259 | 114 | 50 | 147 |
| 0.50 | 0.633 | 0.880 | 0.562 | 0.811 | 0.686 | 228 | 133 | 31 | 178 |
| 0.55 | 0.623 | 0.917 | 0.517 | 0.884 | 0.661 | 210 | 145 | 19 | 196 |
| 0.60 | 0.591 | 0.935 | 0.458 | 0.921 | 0.615 | 186 | 151 | 13 | 220 |
| 0.65 | 0.579 | 0.951 | 0.431 | 0.945 | 0.593 | 175 | 155 | 9 | 231 |
| 0.70 | 0.561 | 0.964 | 0.399 | 0.963 | 0.564 | 162 | 158 | 6 | 244 |
| 0.75 | 0.544 | 0.974 | 0.369 | 0.976 | 0.536 | 150 | 160 | 4 | 256 |
| 0.80 | 0.512 | 0.971 | 0.325 | 0.976 | 0.487 | 132 | 160 | 4 | 274 |
| 0.85 | 0.475 | 0.973 | 0.271 | 0.982 | 0.424 | 110 | 161 | 3 | 296 |
| 0.90 | 0.440 | 0.968 | 0.222 | 0.982 | 0.361 | 90 | 161 | 3 | 316 |

**Accuracy-maximizing threshold (reference only, not selected):** 0.27,
accuracy 0.7263, recall 0.9458, but **specificity only 0.1829** (134 of
164 true negatives misclassified as elevated). Because positives are the
*majority* class here (71% prevalence — the opposite skew from
`liver-nhanes-v1`'s 4.94%), accuracy is maximized near the low-threshold
end, where nearly everyone is predicted positive: that's cheap to get
"right" on 71% of rows by construction, not evidence of a good
sensitivity/specificity balance. This is precisely the scenario the
task's "do not select a threshold simply because it produces the highest
accuracy" instruction warns against. See Section 12 for the actual
selection rule used.

## 12. Selected threshold and rationale

**Selected threshold: 0.35**

Selection rule: the lowest threshold (from the 0.10-0.90 sweep) that still
clears **80% recall** on out-of-fold predictions — the same
sensitivity-first convention already used for `liver-nhanes-v1`,
`diabetes-brfss-v2`, and `diabetes-pima-v1` in this project. At 0.35:
recall 81.8%, specificity 42.7%, precision 77.9%, F1 0.798, accuracy
70.5%.

**This was not chosen to maximize accuracy.** The accuracy-maximizing
threshold in this sweep is 0.27 (accuracy 0.7263) — rejected as the
production threshold because, at a positive prevalence of 71%, accuracy
alone is a poor proxy for a screening tool's real job (catching true
cases); the sensitivity-first threshold was chosen deliberately instead,
consistent with the task's explicit "do not select a threshold simply
because it produces the highest accuracy" instruction.

## 13. Confusion matrix (at selected threshold 0.35, out-of-fold, n=570)

| | Predicted Negative | Predicted Positive |
|---|---:|---:|
| **Actual Negative** | TN = 70 | FP = 94 |
| **Actual Positive** | FN = 74 | TP = 332 |

Roughly 4 in 10 people without liver disease would still see an "elevated"
result at this threshold (specificity 42.7%) — a real trade-off, disclosed
plainly rather than minimized, consistent with how every other model in
this project documents its false-positive rate.

## 14. Limitations

1. **Small dataset (570 usable rows).** Confidence intervals on these
   metrics are wide (fold-to-fold ROC-AUC std alone is 0.0285); a few
   different rows landing in a different fold could shift the numbers
   noticeably. This is not a large-sample result.
2. **Single-region population.** Northeast Andhra Pradesh, India; 441 male
   / 142 female in the raw file — predictions for users outside this
   population (different regions, different demographics) should be
   treated with added caution, a known and disclosed limitation of this
   exact dataset in the wider literature, not unique to this project's use
   of it.
3. **No external clinical validation.** No prospective evaluation or
   clinician review has been performed on this candidate.
4. **Not a diagnosis.** Per AGENTS.md Section 11, this model's output is
   an AI-generated risk indicator only — an elevated result means
   "consider getting your liver function checked further," never "you
   have liver disease."
5. **Specificity trade-off at the selected threshold is real (42.7%).**
   Roughly 4 in 10 people without the condition would see an elevated
   result — the same kind of sensitivity/specificity trade every other
   screening model in this project makes explicit, not hidden behind an
   accuracy figure.
6. **Class imbalance direction differs from this project's other liver
   model.** At 71% positive prevalence, this dataset skews toward
   liver-patients (likely because ILPD was collected at liver clinics,
   not from a general population survey like NHANES) — `liver-nhanes-v1`
   skews the opposite way (4.94% positive, a general-population survey).
   These two models are not directly comparable and, if both are ever
   integrated, should never have their outputs blended or averaged.

## 15. Reproducibility information

- **Random seed:** 42, used consistently for the `StratifiedKFold` split
  and the `LogisticRegression` solver.
- **Library versions:** recorded in
  `artifacts/liver_ilpd_logistic_metadata_v1.json` (`library_versions`
  key) — `scikit-learn`, `pandas`, `numpy`, captured at training time.
- **Script:** `ml_pipeline/liver/train_ilpd_logistic.py` — deterministic
  given the same input file and library versions; re-running it reproduces
  the same fold assignments, CV metrics, threshold sweep, and final
  artifact byte-for-byte (subject to normal floating-point/library-version
  variation across machines, per the task's own caveat).

## 16. Artifact locations

Following this project's existing convention (a single `artifacts/`
directory per model, as already used by `liver-nhanes-v1` and the retired
`liver-ilpd-v1` in this same `ml_pipeline/liver/` folder) rather than
introducing new `models/`/`metadata/` subdirectories — per the task's own
instruction to adapt to an established convention rather than duplicate
structure:

- **Model artifact:** `ml_pipeline/liver/artifacts/liver_ilpd_logistic_v1.pkl`
- **Metadata:** `ml_pipeline/liver/artifacts/liver_ilpd_logistic_metadata_v1.json`
- **Training script:** `ml_pipeline/liver/train_ilpd_logistic.py`
- **This report:** `ml_pipeline/liver/reports/ilpd_final_model_report.md`
- **Prior investigation this builds on:** `ml_pipeline/liver/reports/ilpd_model_investigation.md`

Neither the retired `liver-ilpd-v1` (`artifacts/liver_pipeline.pkl` +
`liver_metadata.json`) nor the production `liver-nhanes-v1`
(`artifacts/liver_pipeline_nhanes_v1.pkl` + `liver_metadata_nhanes_v1.json`)
were modified, read-written, or overwritten by this task.

## 17. SHA-256 checksums

```
liver_ilpd_logistic_v1.pkl:          551e957e0ff027dc07f48b8e6756a0ca00043b828e32950c1598ecab0eafb6db
liver_ilpd_logistic_metadata_v1.json: 10885b0bdb69ec1100191bbb5f52ee33a1823309b0ebe0dade171d213340339a
```

## Final verification performed

- Artifact loaded successfully via `joblib.load()`.
- Inference run on 5 representative samples: a low-risk profile (proba
  0.220, not elevated), a high-risk profile (proba 0.982, elevated), a
  borderline profile (proba 0.523, elevated), a profile with a missing
  `albumin_globulin_ratio` value (proba 0.186, not elevated — the
  in-pipeline median imputer handled it without error), and the low-risk
  profile again with its dict keys deliberately scrambled (proba 0.220,
  identical to the ordered version) — confirming the row is always
  rebuilt from `metadata["feature_names"]`, never from dict iteration
  order.
- Preprocessing and prediction confirmed working together end-to-end
  (single `Pipeline` object, no separate preprocessing step that could
  drift from what was fit at training time).
- Missing/invalid input handling: numeric missing values are imputed by
  the pipeline's `SimpleImputer` (median, fit at training time); this is
  documented here and in the metadata's `preprocessing_steps` field. No
  categorical-value validation (e.g. rejecting an unrecognized `gender`
  value) is implemented in this training script itself, since this
  candidate is not yet wired to any input-validation layer — if this
  model is integrated in the future, it should get the same
  `validate_features()`-style guard every other model in
  `backend/app/ai/models/` already has, per Section 12's own advice to
  extend, not duplicate, the existing pattern.
- No backend or frontend file was modified by this task (verified via
  `git status`, below).
- The `liver_lpd` dataset/model was not used anywhere in this training run.
- `liver-nhanes-v1` artifacts (`liver_pipeline_nhanes_v1.pkl`,
  `liver_metadata_nhanes_v1.json`) are unmodified.
