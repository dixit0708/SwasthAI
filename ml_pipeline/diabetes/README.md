# Diabetes Risk Model

Structured-data risk-assessment model for the SwasthAI "Diabetes Risk" feature (`frontend/prediction-diabetes.html`).

## Two pipelines exist in this directory

1. **BRFSS pipeline (`preprocessing_brfss.py` / `train_brfss.py` / `evaluate_brfss.py` / `inference_test_brfss.py`)** — trained on the CDC BRFSS 2015 Diabetes Health Indicators dataset. **This is the only pipeline with an actual trained, saved artifact** (`artifacts/diabetes_pipeline.pkl` + `artifacts/metadata.json`). See "BRFSS pipeline" below.
2. **Pima pipeline (`preprocessing.py` / `train.py` / `evaluate.py` / `inference_test.py`)** — the original pipeline for the Pima Indians Diabetes Database. The code is complete and documented (see "Pima pipeline" below), but **no artifact was ever trained/committed for it** — `models/diabetes_model.joblib` does not exist on disk. `backend/app/main.py` handles this gracefully (`app.state.diabetes_model = None` on `FileNotFoundError`).

These two pipelines use **entirely different feature sets** (Pima: 8 clinical lab-measurement features; BRFSS: 21 self-reported lifestyle/health-history survey features) and are not interchangeable — see each pipeline's own section below. Integrating the BRFSS pipeline into the live backend requires updating `backend/app/ai/models/diabetes_model.py`'s `FEATURE_ORDER`, `backend/app/models/prediction.py`'s input schema, `backend/app/services/prediction_service.py`, and the `frontend/prediction-diabetes.html` form fields — this has **not** been done yet; see the integration notes at the end of this file.

---

## BRFSS pipeline

### Dataset

CDC BRFSS 2015 Diabetes Health Indicators (Kaggle / UCI mirror), 253,680 respondents, 21 self-reported survey features + 1 binary label (`Diabetes_binary`). Three related files were provided; only the full binary file was used for training — see `reports/dataset_audit.md` for why the other two (a 50/50-undersampled subset, and a 3-class variant sharing the same rows) are not independent datasets and were not used for training or as external validation. Full source, license, and column codebook: `data/raw/README_brfss2015.md`. **The raw files are never modified.**

### Pipeline

```
python preprocessing_brfss.py    # quality checks + dedup + train/test split -> data/processed/
python train_brfss.py            # CV model comparison, tuning, calibration, threshold, final fit -> artifacts/
python evaluate_brfss.py         # one-time held-out test evaluation, plots, explainability -> reports/
python inference_test_brfss.py   # fresh-process smoke test + robustness checks
```

Run in that order from this directory, with the project's Python environment active (`pip install -r ../requirements.txt -r ../../backend/requirements.txt`, plus `matplotlib` for the evaluation plots — a training-only addition, not part of `backend/requirements.txt`).

### Model selection

5-fold stratified CV (training split only) compared logistic regression, random forest, XGBoost, HistGradientBoosting, and SVM (SVM scored on an 8,000-row stratified subsample only — kernel SVM does not scale to 183,579 training rows, and was never eligible for production selection regardless of score). XGBoost was the strongest scalable candidate and was carried into `RandomizedSearchCV` tuning. Full numbers: `reports/cv_baseline_results.json`, `reports/cv_tuned_results.json`.

### Preprocessing

No imputation — the dataset has zero missing values (see `reports/dataset_audit.md`). `StandardScaler` only, fit on the training split inside the saved pipeline. Imbalance (~15% positive after dedup) is handled via `scale_pos_weight`, not resampling, to preserve real-world class prevalence for calibration.

### Calibration and threshold

Raw XGBoost probabilities (trained with `scale_pos_weight`) are poorly calibrated for direct interpretation as probabilities — sigmoid (Platt) calibration cut the out-of-fold Brier score by ~42% (`reports/calibration_check.json`) and is used in the final saved model. **The decision threshold was tuned on the calibrated probability scale, not the raw one** — tuning it on raw probabilities and then applying it after calibration would silently pick the wrong cutoff, since calibration reshapes the probability scale. Locked threshold: **0.10** (not 0.50), chosen to prioritize recall/sensitivity for a screening use case — see `reports/threshold_analysis.json` and `reports/evaluation.md` for the full sweep and reasoning.

### Artifacts

- `artifacts/diabetes_pipeline.pkl` — the fitted pipeline (scaler + calibrated XGBoost, bundled together)
- `artifacts/metadata.json` — full training/evaluation metadata per the project's model-artifact documentation requirement
- `reports/evaluation.md` — full write-up: dataset, cleaning, training, model comparison, final test metrics, confusion matrix, threshold/calibration rationale, feature importance, face-validity check, limitations
- `reports/dataset_audit.md` — the dataset inspection/comparison that determined which of the three provided files to use as primary
- `reports/*.png` — confusion matrix, ROC curve, precision-recall curve, feature importance chart
- `data/processed/brfss_dataset_stats.json`, `data/processed/brfss_evaluation_results.json` — machine-readable stats

### Limitations (read before using this model's output anywhere in the product)

1. **Self-reported survey data, not clinical measurements**: every feature is a BRFSS survey answer (e.g. "have you been told you have high blood pressure?"), not a lab reading. This model answers a different question than a clinical-measurement model would.
2. **Prediabetes is not a positive label**: `Diabetes_binary` is 1 only for a diagnosed-diabetes response; prediabetic respondents are folded into the negative class. This model does not flag prediabetes as elevated risk on its own (though the face-validity check in `reports/evaluation.md` shows predicted risk does trend higher for prediabetic respondents than for non-diabetic ones).
3. **Single country/year**: U.S. CDC survey, 2015. Generalization to other populations, countries, or years is unverified.
4. **No independent external validation**: the two other provided files are not independent of the primary training file (documented in `reports/dataset_audit.md`), so no true external validation was possible for this training run.
5. **Not a diagnosis**: per AGENTS.md Section 11, this model's output is an AI-generated risk indicator, never a diagnosis.

### Inference input/output

**Input**: 21 named features in `metadata.json`'s `feature_order` (see `data/raw/README_brfss2015.md` for the exact codebook — e.g. `Sex` is 0/1, `GenHlth` is 1-5, `Age` is a 13-band category, not raw years). `inference_test_brfss.py` demonstrates a `predict_diabetes_risk(pipeline, metadata, features_dict)` helper that validates every value against its codebook range before predicting, and fails with a clear `KeyError`/`ValueError` rather than silently predicting on bad input.

**Output**: `risk_probability` (float, calibrated, 0-1) and `predicted_class` (0/1 at threshold 0.10).

### Backend integration (not yet done)

To make this the live model, at minimum: (1) point `backend/app/main.py`'s model-loading path at `ml_pipeline/diabetes/artifacts/diabetes_pipeline.pkl`; (2) replace `FEATURE_ORDER` in `backend/app/ai/models/diabetes_model.py` with the 21 BRFSS features above, and add the same range validation `inference_test_brfss.py` uses; (3) rewrite `DiabetesPredictionInput` in `backend/app/models/prediction.py` and `prediction_service.py`'s feature-dict construction for the new fields; (4) replace the form fields in `frontend/prediction-diabetes.html` / `frontend/js/prediction-diabetes.js` (lifestyle/history questions instead of lab values). This is a cross-cutting change to a user-facing form, so it was intentionally left for a separate, explicit integration pass rather than done silently here.

---

## Pima pipeline

### Dataset

Pima Indians Diabetes Database (UCI / NIDDK), 768 rows, 8 input features + 1 binary label. Full source, license notes, and the raw-file column layout are documented in `data/raw/README.md`. **The raw file is never modified** — `preprocessing.py` reads it, runs data-quality checks, marks known missing-value placeholders, and writes cleaned train/test splits to `data/processed/`.

## Pipeline

```
python preprocessing.py    # quality checks + train/test split -> data/processed/
python train.py            # compares logistic regression / random forest / XGBoost, saves the winner
python evaluate.py         # test-set metrics + age-group slice check -> data/processed/evaluation_results.json, appended to EXPERIMENTS.md
python inference_test.py   # smoke-tests the saved model on hand-picked sample inputs
```

Run them in that order from this directory (`ml_pipeline/diabetes/`), with the project's Python environment active.

## Model selection

Per AGENTS.md Section 6, XGBoost is never assumed to be the best choice — `train.py` runs 5-fold stratified cross-validation (scored on ROC-AUC, since the label is imbalanced ~65/35) over logistic regression, random forest, and XGBoost, and only the highest-scoring candidate is kept. The actual algorithm selected, and the CV scores for all three, are recorded in `models/diabetes_model_metadata.json` after each training run.

## Preprocessing

`Glucose`, `BloodPressure`, `SkinThickness`, `Insulin`, and `BMI` use `0` as a "not measured" placeholder in the source data (a real value of 0 is not physiologically possible for any of them). These are converted to `NaN` in `preprocessing.py` — real imputation (median, fit on the training split only) happens inside the saved `sklearn.Pipeline` itself (`SimpleImputer` → `StandardScaler` → classifier), so the exact same fitted transform is applied at both training and inference time and no test-set statistic ever leaks into training.

## Artifacts

- `models/diabetes_model.joblib` — the fitted pipeline (imputer + scaler + classifier bundled together)
- `models/diabetes_model_metadata.json` — model name/version, dataset source, training date, feature order, preprocessing version, CV results, and stated limitations
- `data/processed/dataset_stats.json` — data-quality check results from `preprocessing.py`
- `data/processed/evaluation_results.json` — held-out test metrics from `evaluate.py`
- `EXPERIMENTS.md` — append-only run log, same convention as `ml-services/cnn-detector/EXPERIMENTS.md`

## Evaluation results

See `EXPERIMENTS.md` for the actual run log and `data/processed/evaluation_results.json` for the full metrics (accuracy, precision, recall, F1, ROC-AUC, confusion matrix — never accuracy alone, per AGENTS.md Section 9) from the most recent run.

## Limitations (read before using this model's output anywhere in the product)

1. **Population**: the training data is exclusively **female patients of Pima Indian heritage, age 21+**. This model must never be presented as generalizing to men, children, or other ethnic/demographic groups — that would be a false and potentially harmful claim of clinical validity it does not have.
2. **Dataset size**: 768 rows is small by modern ML standards. Held-out metrics carry real sampling uncertainty; treat reported scores as indicative, not precise.
3. **Missing-data rate**: several features had a non-trivial fraction of missing (zero-placeholder) values in the source data — see `data/processed/dataset_stats.json` for exact rates — and are median-imputed. Predictions for inputs far outside the training distribution on these fields should be treated with lower confidence.
4. **Not a diagnosis**: per AGENTS.md Section 11, this model's output is an AI-generated risk indicator, never a diagnosis. The API and frontend must always present it using non-diagnostic language ("elevated risk indicators," not "you have diabetes") and encourage professional consultation.

## Inference input/output (for the backend integration)

**Input** (all required, `float`/`int`):
`Pregnancies, Glucose, BloodPressure, SkinThickness, Insulin, BMI, DiabetesPedigreeFunction, Age`

**Output**: `predicted_class` (0/1) and `risk_probability` (float, 0-1) — the production API wraps this in non-diagnostic language before returning it to the frontend (see `backend/app/ai/safety/`).
