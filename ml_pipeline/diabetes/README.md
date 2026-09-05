# Diabetes Risk Model

Structured-data risk-assessment model for the SwasthAI "Diabetes Risk" feature (`frontend/prediction-diabetes.html`).

## Dataset

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
