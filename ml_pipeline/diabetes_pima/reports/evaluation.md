# Diabetes Risk Model (Lab-Based / Pima) — Evaluation

Model: `diabetes-pima-v1` (logistic regression, sigmoid-calibrated)
Data: Pima Indians Diabetes Database (NIDDK/UCI, Smith et al. 1988) — see
`data/raw/README.md` for provenance and the authenticity checks run before
use (verified against a third-party's independent preprocessed copy —
every descriptive statistic matched exactly).

Independent of `diabetes-brfss-v2` and `liver-nhanes-v1` — separate data
source, separate artifact, never merged with either of them.

## Headline result

| Metric | Value |
|---|---|
| ROC-AUC | 0.803 |
| Recall (sensitivity) | 0.815 |
| Precision | 0.557 |
| Accuracy | 0.708 |
| Decision threshold | 0.26 |
| n_train / n_test | 614 / 154 |
| Positive rate | 34.9% |

These numbers sit squarely within the range reported across the large
published literature on this exact dataset (typical published ROC-AUC for
similar feature subsets: ~0.75-0.85) — a useful thing to be able to say in
a viva: the result is not an outlier, it's consistent with decades of
prior work on the same data.

Threshold chosen the same way as every other model in this project: sweep
thresholds, keep the lowest that still clears 80% recall. Pima's class
balance (34.9% positive) is much less extreme than a rare-disease dataset
would be, so the resulting threshold (0.26) and precision (0.56) are both
quite usable — roughly 1 in 2 people flagged "elevated risk" actually has
diabetes, catching 82% of real cases.

## Model selection

| Model | CV ROC-AUC | CV F1 | CV Recall |
|---|---|---|---|
| Logistic Regression | 0.840 | 0.667 | 0.720 |
| Random Forest | 0.807 | 0.650 | 0.682 |
| XGBoost | 0.790 | 0.623 | 0.621 |

Logistic regression won, consistent with a large body of published Pima
work — a small (768-row), low-dimensional, mostly-linearly-separable
dataset like this one generally favors a well-regularized linear model
over tree ensembles, which tend to overfit at this scale. Refit with
`CalibratedClassifierCV(method="sigmoid", cv=5)` for well-calibrated
probabilities, matching every other model in this project.

## Missing-value handling (the dataset's well-known "zero-as-missing" issue)

Pima's Glucose, BloodPressure, SkinThickness, and BMI columns record
missing values as a literal 0 (a documented, widely-discussed artifact of
this specific dataset — 0 is physiologically impossible for all four).
`preprocessing.py` converts these to NaN; `train.py` imputes them with
`SimpleImputer(strategy="median")` **inside the sklearn Pipeline**, so the
median is computed from the training fold only, both during
cross-validation (refit per fold) and for the final model (fit only on the
80% training split). This is the textbook-correct, leakage-free approach.
Contrast with the third-party preprocessed file inspected during dataset
selection, which appeared to impute Insulin using a value conditioned on
the Outcome label itself — a subtle leakage risk this project avoids.

Missing-value rates: SkinThickness 29.6%, BloodPressure 4.6%, BMI 1.4%,
Glucose 0.7%.

## Feature exclusions, and why

Two of the original 8 Pima columns are deliberately not used:

- **Insulin** — 48.7% missing, by far the least reliable column. Including
  a feature that's imputed for nearly half the dataset would make the
  model's real behavior hard to interpret or defend.
- **DiabetesPedigreeFunction** — a derived genetic-likelihood score based
  on family history, not something a user could plausibly self-report
  accurately.

## Not lab-free, and a narrow population

This is the deliberate counterpart to `diabetes-brfss-v2`: it exists for
users who already have a recent glucose reading, blood pressure, BMI, and
a skinfold measurement — not something answerable from memory alone.

The training population is exclusively **female, of Pima Indian heritage,
age 21+** (the original 1988 NIDDK study cohort) — a narrow, specific
population, not a general-population sample. Predictions for users outside
this population (any male user, or anyone outside this specific ancestry)
should be treated with real caution; this is a known, widely-discussed
limitation of this dataset in the literature, not something unique to this
project's use of it.
