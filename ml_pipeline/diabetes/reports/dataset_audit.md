# Dataset Audit — CDC BRFSS 2015 Diabetes Health Indicators

Three CSV files were provided (originally from Kaggle, all Downloads-folder paths point to the same "Diabetes Health Indicators" / BRFSS2015 family). This report documents what was actually found in each file — nothing here is assumed from prior familiarity with the public version of this dataset.

## Files audited

| File | Rows | Cols | Target | Target cardinality |
|---|---:|---:|---|---|
| `diabetes_binary_health_indicators_BRFSS2015.csv` | 253,680 | 22 | `Diabetes_binary` | 2 (0/1) |
| `diabetes_binary_5050split_health_indicators_BRFSS2015.csv` | 70,692 | 22 | `Diabetes_binary` | 2 (0/1), exactly 50/50 |
| `diabetes_012_health_indicators_BRFSS2015.csv` | 253,680 | 22 | `Diabetes_012` | 3 (0/1/2) |

All three share the same 21 feature columns: `HighBP, HighChol, CholCheck, BMI, Smoker, Stroke, HeartDiseaseorAttack, PhysActivity, Fruits, Veggies, HvyAlcoholConsump, AnyHealthcare, NoDocbcCost, GenHlth, MentHlth, PhysHlth, DiffWalk, Sex, Age, Education, Income`. Every column loads as numeric with no header issues.

## Cross-file relationship (verified programmatically)

- **`012` vs `binary`**: identical 253,680 rows, identical feature values row-for-row. `Diabetes_binary == 1` if and only if `Diabetes_012 == 2`. Respondents with `Diabetes_012 == 1` (prediabetes) are folded into the **negative** class of the binary target. So these two files are the *same population*, not independent datasets — `012` cannot be used to "externally validate" a model trained on `binary`.
- **`5050split` vs `binary`**: every row of the 5050-split file is a duplicate of a row already present in the full binary file (confirmed via exact row match) — it is an undersampled subset of `binary` (all 35,346 positives kept, an equal-sized random sample of the 218,334 negatives). It is therefore **not an independent dataset** either, and using it for "external" validation of a model trained on `binary` would validate on rows the model may have already trained on.

**Consequence**: none of the three files are mutually independent. There is exactly one underlying population here (253,680 BRFSS 2015 respondents). This directly affects the external-validation plan — see `reports/evaluation.md`.

## Missing values

**Zero** nulls in any of the three files (`df.isna().sum().sum() == 0` for all). Unlike the Pima dataset, there is no zero-as-missing-placeholder problem — every column here is an already-cleaned, already-encoded survey response (e.g. `Smoker=0` genuinely means "not a smoker," not "not measured"). No imputation is required for this dataset.

## Duplicates

| File | Exact duplicate rows | % of file |
|---|---:|---:|
| `binary` (primary) | 24,206 | 9.5% |
| `5050split` | 1,635 | 2.3% |
| `012` | 23,899 | 9.4% |

These are **not treated as data-entry errors**. With ~21 low-cardinality categorical/ordinal columns (mostly binary flags plus a handful of small ordinal scales) surveyed across 253,680 people, many genuinely different respondents will legitimately share an identical answer pattern by chance — this is a expected property of low-dimensional categorical data at this sample size, not evidence of duplicated submissions. They are still **dropped before the train/test split**, for the same leakage-prevention reason already applied to the Pima dataset in this repo (`preprocessing.py`): an identical row landing in both the training and test split would let the model "recognize" a memorized row rather than generalize, silently inflating test-set metrics.

## Invalid / implausible values

- No negative values in any column.
- `MentHlth` and `PhysHlth` (self-reported "days in past 30 days") are bounded to [0, 30] with no violations — consistent with the survey's own question design.
- `GenHlth` in [1, 5], `Age` in [1, 13], `Education` in [1, 6], `Income` in [1, 8] — all within their documented codebook ranges, no out-of-range values.
- `BMI` ranges 12-98. Values above ~50 are rare but medically real (morbid obesity is a documented, if uncommon, BMI range); an IQR check (Q1=24, Q3=31) flags 9,847 rows (3.88%) as statistical outliers, but none are physiologically impossible, so **none are removed** — consistent with the "do not blindly remove outliers" rule. These extreme-BMI rows are retained as real, if rare, patients.

## Class distribution (target)

| File | Negative | Positive | Positive rate |
|---|---:|---:|---:|
| `binary` (primary) | 218,334 | 35,346 | 13.93% |
| `5050split` | 35,346 | 35,346 | 50.00% (undersampled) |
| `012`: no diabetes / prediabetes / diabetes | 213,703 / 4,631 / 35,346 | — | 84.24% / 1.83% / 13.93% |

The primary file is imbalanced (~6.2:1), but not extremely so — well within the range class-weighting can handle without resampling.

## Column-level sanity check

- No ID columns, row-number columns, or free-text columns.
- No column is a direct restatement of the target (no "has_diabetes_medication," "diagnosed_by_doctor," etc. — everything is an independent lifestyle/health-history survey answer).
- No constant columns. The most skewed binary flags (`CholCheck` at 96.3% "yes", `AnyHealthcare` at 95.1% "yes") are still informative, not near-constant to the point of being unusable, and are kept.
- Binary-flag positive rates (feature name = % answering "yes"/1): `HighBP` 42.9%, `HighChol` 42.4%, `CholCheck` 96.3%, `Smoker` 44.3%, `Stroke` 4.1%, `HeartDiseaseorAttack` 9.4%, `PhysActivity` 75.7%, `Fruits` 63.4%, `Veggies` 81.1%, `HvyAlcoholConsump` 5.6%, `AnyHealthcare` 95.1%, `NoDocbcCost` 8.4%, `DiffWalk` 16.8%, `Sex` 44.0% (male).

## Suitability for the intended task

Suitable, with one important framing caveat: this is a **self-reported lifestyle/health-history risk-indicator dataset**, not a clinical lab-measurement dataset (contrast with the existing Pima pipeline's `Glucose`/`Insulin`/`BloodPressure` lab values). The resulting model answers "how do this person's survey-reported lifestyle and health-history factors compare to people who reported being diagnosed with diabetes," which is a legitimate and common screening/triage framing, but it is a different kind of model than a clinical-measurement-based one and must be described as such in every user-facing surface.

## Dataset selection decision

**Primary training dataset: `diabetes_binary_health_indicators_BRFSS2015.csv`** (253,680 rows, binary target), copied into this repo as `data/raw/brfss2015-diabetes-binary.csv`.

Rationale:
1. Binary target matches the production inference contract (`predict_diabetes` returns one risk probability), unlike the 3-class `012` file.
2. It is the largest independent sample of the three (the 5050-split file is a strict subset of it).
3. Training on the natural ~14% prevalence (rather than an artificially rebalanced 50/50 set) preserves real-world class priors, which matters for producing risk *probabilities* that are meaningfully comparable to actual population prevalence — imbalance is instead handled via class weighting inside the model pipeline (see `reports/evaluation.md`), not by discarding majority-class data.

The other two files are **not used for training or tuning**. `012` is used only for a bounded, clearly-labeled face-validity check on the already-held-out test rows (see `reports/evaluation.md`, "External validation" section) — not as an external validation set, since it shares the exact same rows as the primary file.
