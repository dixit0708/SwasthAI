# Diabetes Risk Model — Lab-Based (Pima)

An **independent** diabetes risk model — the "I have recent lab results"
counterpart to `ml_pipeline/diabetes` (BRFSS, lab-free). Separate from
that model and `ml_pipeline/liver`: different data source, different
artifact, never merged with either of them.

## Data

**Pima Indians Diabetes Database** — NIDDK/UCI, originally published in
Smith, J.W., Everhart, J.E., Dickson, W.C., Knowler, W.C., & Johannes, R.S.
(1988), *"Using the ADAP Learning Algorithm to Forecast the Onset of
Diabetes Mellitus,"* Proc. Symposium on Computer Applications and Medical
Care. One of the most cited medical ML datasets in existence. See
`data/raw/README.md` for full provenance, the known zero-as-missing
quirk, and the authenticity check run against an independently-sourced
copy of the same data before use.

768 rows, 6 features used: Pregnancies, Glucose, BloodPressure,
SkinThickness, BMI, Age. Population: female, Pima Indian heritage, 21+ —
a narrow, specific population (see `reports/evaluation.md`).

## Model

Logistic regression, sigmoid-calibrated, ROC-AUC 0.803, threshold tuned
for 80% recall. Missing values (the dataset's well-known 0-as-missing
placeholders) imputed with a training-fold-only median inside the
pipeline — no leakage. Full results: `reports/evaluation.md`.

## Important disclosures

1. **Not lab-free.** Requires an actual glucose reading, blood pressure,
   BMI, and skinfold measurement — this is the model for someone who
   already has recent labs, not a pre-lab-visit triage tool.
2. **Narrow training population** (female, Pima Indian heritage, 21+) —
   predictions for other users should be treated with added caution.
3. Two original Pima columns are excluded on purpose: `Insulin` (48.7%
   missing) and `DiabetesPedigreeFunction` (a derived, hard-to-self-report
   family-history score).

## Files

- `data/raw/pima_indians_diabetes.csv` — the canonical dataset with headers
  added (see `data/raw/README.md`)
- `preprocessing.py` — marks physiologically-impossible zeros as missing →
  `data/processed/pima_processed.csv`
- `train.py` — model comparison, leakage-free imputation, calibration,
  threshold selection → `artifacts/diabetes_pima_pipeline_v1.pkl` +
  `artifacts/diabetes_pima_metadata_v1.json`
- `reports/evaluation.md` — full results and limitations
