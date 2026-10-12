# Model Card — SwasthAI Diabetes Risk Model

## 1. Model Overview

Two versions exist in the repository:

| | `diabetes-brfss-v2` | `diabetes-brfss-v1` |
|---|---|---|
| Status | **Current production** | **Rollback / historical baseline** |
| Features | 14 | 21 |
| Artifact | `ml_pipeline/diabetes/artifacts/diabetes_pipeline_v2.pkl` | `ml_pipeline/diabetes/artifacts/diabetes_pipeline.pkl` |
| Metadata | `ml_pipeline/diabetes/artifacts/diabetes_metadata_v2.json` | `ml_pipeline/diabetes/artifacts/metadata.json` |
| Loaded by backend at startup | Yes (`backend/app/main.py`, `app.state.diabetes_model`) | No — file is left on disk, untouched, as the immutable comparison baseline; not wired into any live endpoint |

Both share the same underlying algorithm family (XGBoost + sigmoid calibration), the same dataset (CDC BRFSS 2015), and the same train/test split. v2 uses a reduced 14-feature subset of v1's 21 features. Full v1-vs-v2 evidence is in [evaluation.md](evaluation.md).

**Do not confuse the two when reading any metric in this documentation — every table below is labeled by version.**

## 2. Model Version

- Current: `diabetes-brfss-v2` (`ml_pipeline/diabetes/artifacts/diabetes_metadata_v2.json`, field `model_version`)
- Superseded/rollback: `diabetes-brfss-v1` (`ml_pipeline/diabetes/artifacts/metadata.json`, field `model_version`)
- `diabetes_metadata_v2.json` field `supersedes`: `"diabetes-brfss-v1"`

## 3. Current Status

- `diabetes-brfss-v2`: **Current Production** — loaded eagerly at FastAPI startup (`backend/app/main.py`), served at `POST /api/v1/predict/diabetes`.
- `diabetes-brfss-v1`: **Rollback / Historical Baseline** — artifact and metadata files are present and loadable (verified, see §Reproducibility), but not referenced by any current backend route.

## 4. Intended Use

An AI-generated diabetes risk/screening indicator, based on self-reported lifestyle and health-history inputs, for informational purposes within the SwasthAI platform. Per `diabetes_metadata_v2.json`, field `intended_use`: *"AI-generated diabetes risk indicator for informational/screening purposes."*

## 5. Not Intended For

- A confirmed or definitive medical diagnosis.
- A replacement for laboratory testing (e.g. fasting glucose, HbA1c, oral glucose tolerance test).
- A replacement for evaluation by a qualified healthcare professional.
- Emergency medical decision-making.
- Standalone treatment decisions.

Every API response routes through `build_screening_response()` (`backend/app/ai/safety/response_filter.py`), which attaches the fixed disclaimer from `backend/app/ai/safety/medical_disclaimer.py`:

> "This is an AI-generated risk indicator based on the values you entered, not a medical diagnosis. Please consult a qualified healthcare professional to discuss these results and any next steps."

## 6. Prediction Task

**Binary classification / screening.** Given a set of self-reported health and lifestyle inputs, the model outputs a calibrated probability that the respondent's profile resembles the profile of people in the training data who reported a diabetes diagnosis. This probability is compared against a fixed decision threshold to produce a binary "elevated risk" / "not elevated" screening outcome.

- **Positive class (`Diabetes_binary == 1`)**: respondent reported being diagnosed with diabetes. Confirmed in `ml_pipeline/diabetes/artifacts/diabetes_metadata_v2.json`, field `target_classes`: `{"0": "no diabetes (or prediabetes only)", "1": "diagnosed diabetes"}`.
- **Negative class (`Diabetes_binary == 0`)**: no diabetes diagnosis **or prediabetes only**. Per `dataset_audit.md` and `evaluation.md`: prediabetes (`Diabetes_012 == 1` in the original 3-class source) is folded into the negative class — the model does **not** treat prediabetes as a positive/elevated-risk case.
- The model produces a continuous calibrated probability (`predict_proba`), not a bare class label; the binary decision is derived by comparing that probability to `decision_threshold` from metadata (0.10 for v2).

**What the prediction means:** the model's calibrated probability estimates how closely a respondent's answers to this specific 14-question (v2) or 21-question (v1) survey pattern resemble people who reported a diabetes diagnosis in the CDC BRFSS 2015 survey.

**What the prediction does NOT mean:** it is not a diagnosis, it does not confirm or rule out diabetes, and it does not account for information outside the listed feature set (e.g. family history, lab values — see [limitations.md](limitations.md)).

## 7. Input Features (v2 — current production, 14 features)

See the full feature table (with types, ranges, and meanings) in [evaluation.md](evaluation.md) §"v2 — Feature Contract". Field names below are the production API's snake_case names (`backend/app/models/prediction.py`, `DiabetesPredictionInput`); the model's internal training-time names (BRFSS codebook) are shown in parentheses.

`sex (Sex)`, `age (Age)`, `bmi (BMI)`, `high_bp (HighBP)`, `high_chol (HighChol)`, `chol_check (CholCheck)`, `heart_disease_or_attack (HeartDiseaseorAttack)`, `phys_activity (PhysActivity)`, `fruits (Fruits)`, `hvy_alcohol_consump (HvyAlcoholConsump)`, `stroke (Stroke)`, `gen_hlth (GenHlth)`, `diff_walk (DiffWalk)`, `smoker (Smoker)`.

## 8. Output

Verified from `backend/app/models/prediction.py` (`RiskPredictionOut`) and `backend/app/ai/safety/response_filter.py` (`build_screening_response`):

| Field | Type | Meaning |
|---|---|---|
| `risk_level` | `"screening_negative"` \| `"screening_elevated"` | Whether the calibrated probability is ≥ the metadata threshold |
| `risk_probability` | float, rounded to 4 dp | The calibrated probability from `pipeline.predict_proba` |
| `threshold` | float | The decision threshold used, sourced from metadata (never hardcoded) |
| `is_elevated` | bool | `risk_probability >= threshold` |
| `message` | string | Non-diagnostic, patient-facing explanation |
| `model_version` | string | e.g. `"diabetes-brfss-v2"`, sourced from metadata |
| `disclaimer` | string | Fixed non-diagnostic disclaimer text |

The API never returns a bare "yes/no diabetes" label — only the risk band, the underlying probability, and the threshold used.

## 9. Dataset

CDC BRFSS 2015 Diabetes Health Indicators (Kaggle/UCI mirror). Full details, cleaning, and audit trail in [methodology.md](methodology.md) and `ml_pipeline/diabetes/reports/dataset_audit.md`.

## 10. Training Method

Summarized in [methodology.md](methodology.md); full detail in `ml_pipeline/diabetes/reports/evaluation.md` (v1) and `ml_pipeline/diabetes/reports/v2_final_recommendation.md`, `v2_model_comparison.md`, `v2_calibration.md`, `v2_threshold_analysis.md` (v2).

## 11. Algorithm

Both v1 and v2: **XGBoost classifier**, wrapped in `sklearn.calibration.CalibratedClassifierCV(method="sigmoid")`, preceded by `StandardScaler`, assembled as a single `sklearn.Pipeline`. Verified directly against the loaded v2 artifact: `pipeline.named_steps["classifier"]` is a `CalibratedClassifierCV` with `method="sigmoid"` (confirmed by `ml_pipeline/diabetes/inference_test_brfss_v2.py`, which asserts this at runtime and which was re-run during this documentation pass — all assertions passed).

## 12. Hyperparameters (v2, from `diabetes_metadata_v2.json` field `hyperparameters`)

| Parameter | Value |
|---|---|
| Algorithm | XGBoost (`xgboost_sigmoid_calibrated`) |
| n_estimators | 400 |
| max_depth | 3 |
| learning_rate | 0.05 |
| subsample | 0.8 |
| colsample_bytree | 0.8 |
| min_child_weight | 5 |
| gamma | 1.0 |
| reg_alpha | 0 |
| reg_lambda | 5.0 |
| scale_pos_weight | 5.5382 |
| Calibration method | sigmoid (Platt scaling) |
| Decision threshold | 0.10 |

v1 uses the **identical** hyperparameter values (`ml_pipeline/diabetes/artifacts/metadata.json`, field `hyperparameters`) — v2's search independently re-derived the same configuration for its reduced feature set rather than reusing v1's values verbatim (`v2_model_comparison.md`).

## 13. Calibration

Both v1 and v2 use sigmoid (Platt) calibration, each independently selected via the rule `raw_brier − calibrated_brier > 0.0005` on out-of-fold training predictions. For v2: raw OOF Brier 0.18278 → calibrated OOF Brier 0.10626 (improvement 0.07652). Full detail in [evaluation.md](evaluation.md) §Calibration.

## 14. Threshold

`decision_threshold = 0.10` for both v1 and v2, sourced only from metadata (`decision_threshold` field), never hardcoded in application code (`backend/app/ai/models/diabetes_model.py` reads it from the metadata dict at inference time; this is also covered by an explicit regression test, `test_diabetes_prediction_threshold_is_metadata_driven_not_hardcoded`, re-run during this documentation pass — passed).

## 15. Performance

See [evaluation.md](evaluation.md) for the full table, confusion matrix, and curves. Headline v2 test-set metrics (independently reproduced and bit-for-bit matching `diabetes_metadata_v2.json`'s stored `test_metrics` and `docs/ml/diabetes/independent_reproduction.json`):

| Metric | v2 |
|---|--:|
| Accuracy | 0.6439 |
| Precision | 0.2825 |
| Recall / Sensitivity | 0.8628 |
| Specificity | 0.6043 |
| F1 | 0.4256 |
| ROC-AUC | 0.8180 |
| PR-AUC | 0.4446 |
| Brier score | 0.10530 |

## 16. Confusion Matrix

v2, test set (n=45,895), threshold 0.10 — see `figures/confusion_matrix.png`:

|  | Predicted: Negative | Predicted: Elevated |
|---|--:|--:|
| **Actual: Negative** | TN = 23,494 | FP = 15,382 |
| **Actual: Positive** | FN = 963 | TP = 6,056 |

## 17. Feature Importance

XGBoost gain-based importance, independently extracted from the fitted v2 artifact (averaged across the `CalibratedClassifierCV`'s per-fold estimators — see `docs/ml/diabetes/v2_feature_importance_reproduced.json` and `figures/feature_importance.png`). Top 5: `HighBP` (0.486), `GenHlth` (0.145), `HighChol` (0.097), `Age` (0.050), `BMI` (0.045).

> Feature importance describes how the model uses variables for prediction. It does not establish causality and should not be interpreted as an individual's independent medical risk contribution.

## 18. Limitations

See [limitations.md](limitations.md) for the full list.

## 19. Bias / Generalization Considerations

- Single U.S. CDC survey year (2015), U.S. population only — generalization to other countries, years, or populations is unverified.
- All features are self-reported, not clinically measured.
- No demographic-slice (age/sex) performance breakdown has been produced in the repository evidence for either v1 or v2 — this is a gap, stated as such rather than assumed benign.

## 20. Clinical Safety

This model is a machine-learning risk/screening tool and is **not** a clinically validated diagnostic system. No external clinical validation, prospective evaluation, or clinician review has been performed on either v1 or v2 (`v2_final_recommendation.md`, §11).

## 21. Version History

| Version | Status | Training date (metadata) | Notes |
|---|---|---|---|
| `diabetes-brfss-v1` | Rollback | 2026-09-08 (`metadata.json`, field `training_date`) | 21 features, original BRFSS baseline |
| `diabetes-brfss-v2` | Current production | 2026-09-09 (`diabetes_metadata_v2.json`, field `training_date`) | 14 features, reduced questionnaire, supersedes v1 |

## 22. Reproducibility

- Python: 3.13.5 (`backend/runtime.txt`)
- Library versions used at training time (`diabetes_metadata_v2.json`, field `library_versions`): scikit-learn 1.9.0, xgboost 3.4.1, pandas 3.0.5, numpy 2.5.2
- Versions installed in this repository's `venv/` at the time this documentation was generated: scikit-learn 1.9.0, xgboost 3.4.1, pandas 3.0.5, numpy 2.5.2, matplotlib 3.11.1 — **exact match** to the training-time versions recorded above.
- Random seed: 42 (`metadata.json` / `diabetes_metadata_v2.json`, field `random_seed`)
- Train/test split: 80/20 stratified, `random_state=42`, shared between v1 and v2 (`diabetes_metadata_v2.json`, field `train_test_split`)
- Dataset source file: `ml_pipeline/diabetes/data/raw/brfss2015-diabetes-binary.csv`
- Training scripts: `ml_pipeline/diabetes/train_brfss.py` (v1), `ml_pipeline/diabetes/train_brfss_v2.py` (v2)
- Evaluation scripts: `ml_pipeline/diabetes/evaluate_brfss.py` (v1 figures), `ml_pipeline/diabetes/inference_test_brfss.py` / `inference_test_brfss_v2.py` (inference smoke tests, re-run during this documentation pass)
- Feature order: authoritative source is `feature_order` in each version's metadata JSON, never re-derived elsewhere in production code
- Independent reproduction performed for this documentation: loaded both artifacts, ran `predict_proba` against `ml_pipeline/diabetes/data/processed/brfss_test.csv` (the same 45,895-row held-out split referenced by both versions' metadata), and recomputed all metrics from scratch — see `docs/ml/diabetes/independent_reproduction.json`. Result: **exact match** to v2's stored `test_metrics`, and match (to reported precision) with v1's `evaluation.md` figures.

## 23. Production Integration

See [evaluation.md](evaluation.md) §Production Integration and §Security for full detail. Summary:

- Endpoint: `POST /api/v1/predict/diabetes`
- Authentication: required (`Depends(get_current_user)`, HTTP Bearer JWT)
- Model loaded once at FastAPI startup from `ml_pipeline/diabetes/artifacts/diabetes_pipeline_v2.pkl` + `diabetes_metadata_v2.json`; load failure sets `app.state.diabetes_model = None` and the endpoint returns HTTP 503 rather than crashing
- Request body validated by `DiabetesPredictionInput` (Pydantic, `extra="forbid"`) — rejects unknown fields, out-of-range values, and non-codebook categorical values at the HTTP layer
- Predictions persisted per-user via `prediction_repo.create()`, scoped by `user_id` from the authenticated token
