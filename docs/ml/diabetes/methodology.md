# Methodology — SwasthAI Diabetes Risk Model

Evidence sources for this document: `ml_pipeline/diabetes/reports/dataset_audit.md`, `evaluation.md`, `v2_model_comparison.md`, `v2_calibration.md`, `v2_threshold_analysis.md`, `v2_final_recommendation.md`, and the metadata files `metadata.json` (v1) / `diabetes_metadata_v2.json` (v2).

## 1. Dataset

- **Source**: CDC BRFSS 2015 Diabetes Health Indicators, Kaggle/UCI mirror.
- **Files provided**: three CSVs were audited (`diabetes_binary_health_indicators_BRFSS2015.csv`, `diabetes_binary_5050split_health_indicators_BRFSS2015.csv`, `diabetes_012_health_indicators_BRFSS2015.csv`). All three were verified (`dataset_audit.md`) to be the **same underlying population of 253,680 respondents** — the `5050split` file is a subset of the primary `binary` file, and the `012` file shares identical rows under a different target encoding. Only the primary `binary` file (253,680 rows, 22 columns) was used for training.
- **Target**: `Diabetes_binary` — 1 for a diagnosed-diabetes response, 0 for no-diabetes **or prediabetes-only**.
- **Selection rationale** (`dataset_audit.md`): the binary target matches the production inference contract (one risk probability), it is the largest independent sample of the three, and training on the natural ~14% prevalence (rather than an artificially rebalanced 50/50 set) preserves real-world class priors — important for producing probabilities comparable to actual population prevalence.

## 2. Target Definition

- `Diabetes_binary == 1` ⇔ original 3-class `Diabetes_012 == 2` (diagnosed diabetes).
- `Diabetes_binary == 0` covers both `Diabetes_012 == 0` (no diabetes) and `Diabetes_012 == 1` (prediabetes) — **prediabetes is grouped into the negative class**. This means the model does not flag prediabetes as elevated risk, verified from `dataset_audit.md` and stated explicitly as a limitation in both `evaluation.md` (v1) and `v2_final_recommendation.md` (v2).
- No target rows were removed or relabeled beyond this binary collapse.

## 3. Data Cleaning (before train/test split)

| Step | Finding | Action |
|---|---|---|
| Missing values | Zero nulls across all columns (`dataset_audit.md`) | No imputation performed |
| Duplicates | 24,206 exact duplicate rows (9.5% of the primary file) | Dropped **before** the train/test split, for leakage prevention |
| Invalid/out-of-codebook values | None found; BMI ranges 12–98, all other columns within documented codebook ranges | No rows removed as "invalid" |
| Outliers | IQR check flags 9,847 rows (3.88%) as statistical BMI outliers | **Not removed** — extreme BMI values are physiologically real, not data errors |

## 4. Preprocessing (inside the training pipeline, fit on training split only)

- `StandardScaler`, fit only on the training split, saved as the first step of the persisted `sklearn.Pipeline` — never re-fit or altered by inference code.
- No imputation (not required — zero missing values).
- Class imbalance handled via `scale_pos_weight` (XGBoost's native class weighting) rather than resampling (SMOTE/undersampling), to preserve the natural ~14% prevalence needed for meaningful calibrated probabilities.

## 5. Train/Test Split

- 80/20 stratified split, `random_state=42`.
- Shared between v1 and v2 (`diabetes_metadata_v2.json`, field `train_test_split`: *"shared with v1 — same split files"*) — both versions are evaluated on the identical held-out 45,895-row test set, which is what makes their metrics directly comparable.
- Cross-validation during model selection/tuning: `StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`.
- The test split is touched **exactly once** per version, for the single final evaluation — never used for model selection, hyperparameter tuning, calibration decision, or threshold selection (all of those stages use out-of-fold predictions on the training split only).

## 6. Model Family Comparison

**v1**: 5-fold CV comparison of logistic regression, random forest, XGBoost, HistGradientBoosting, and SVM (SVM on an 8,000-row subsample only, due to scaling limits) — see `cv_baseline_results.json`. XGBoost selected as the strongest scalable baseline by mean CV ROC-AUC, then tuned via `RandomizedSearchCV` (20 iterations, cv=3).

**v2** (independently re-run for the reduced feature set, not assumed from v1):

| Model family | CV ROC-AUC | Std |
|---|--:|--:|
| Logistic Regression | 0.8056 | ±0.0008 |
| Random Forest | 0.7962 | ±0.0012 |
| XGBoost (default) | 0.8130 | ±0.0008 |
| HistGradientBoosting | 0.8131 | ±0.0010 |

HistGradientBoosting's 0.0001 edge over XGBoost is smaller than either family's fold-to-fold standard deviation — not treated as a meaningful difference. **XGBoost was retained**, per `v2_model_comparison.md`, to avoid the operational cost of switching production families for a statistically indistinguishable gain, and because it keeps v1/v2 architecturally comparable.

## 7. Hyperparameter Tuning (v2)

`RandomizedSearchCV`, 20 candidate configurations × 3-fold CV, scored on ROC-AUC, training split only — a fresh search, not a reuse of v1's fixed values as a default. The winning configuration (see [model_card.md](model_card.md) §12) reached full 5-fold CV ROC-AUC = 0.8137 (±0.0008), a 0.0006 improvement over the default-hyperparameter XGBoost run.

## 8. Feature Selection (v1 → v2)

v2's 14-feature set was derived from v1's 21 by removing 7 features: `Income`, `Education`, `AnyHealthcare`, `NoDocbcCost` (sensitive/socioeconomic-access proxies with no clinical necessity for a screening tool), `MentHlth`, `PhysHlth` (high recall-burden, low marginal value), and `Veggies` (redundant with the retained `Fruits` feature, near-zero importance). Full rationale: `ml_pipeline/diabetes/reports/feature_selection_analysis.md`, `candidate_assessments.md`, and `diabetes_metadata_v2.json` field `feature_reduction_rationale`. This decision was independently re-validated in the v2 validation pass by re-running the full model-comparison, calibration, and threshold-selection process on the 14-feature set rather than assuming the earlier study's conclusion — see `v2_final_recommendation.md`.

## 9. Calibration Decision

Decided via out-of-fold Brier score comparison on the training split only, using the rule `raw_brier − calibrated_brier > 0.0005`, applied identically to v1 and v2:

| | v2 OOF Brier |
|---|--:|
| Raw (uncalibrated XGBoost) | 0.18278 |
| Sigmoid-calibrated | 0.10626 |
| Improvement | 0.07652 (≫ 0.0005 threshold → calibration used) |

Method: `CalibratedClassifierCV(method="sigmoid")` (Platt scaling), fit via cross-validation on the training split.

## 10. Threshold Selection

Swept over `{0.05, 0.10, ..., 0.50}` on the OOF **calibrated** probability space (after the calibration decision above), using training-split OOF predictions only. Selection rule (applied identically across v1, the earlier feature-ablation study, and v2): *the highest grid threshold at which training-OOF sensitivity is still ≥ 0.85.* At 0.10, OOF sensitivity was 0.8599; at 0.15 it dropped to 0.7792 (below the floor) — so **0.10** was selected. The full sweep is in `v2_threshold_sweep.json` and reproduced in [evaluation.md](evaluation.md).

## 11. Final Evaluation

Each version's chosen configuration (algorithm + hyperparameters + calibration + threshold, all decided on training-split OOF data) was evaluated **once** on the untouched test split. Results in [evaluation.md](evaluation.md), independently re-verified for this documentation by re-running inference on the same test split — see `docs/ml/diabetes/independent_reproduction.json`.

## 12. Artifact Generation

The final fitted `Pipeline` (scaler + calibrated classifier) is serialized with `joblib` to `diabetes_pipeline_v2.pkl` (or `diabetes_pipeline.pkl` for v1); the feature order, decision threshold, calibration method, training date, dataset provenance, hyperparameters, and test metrics are saved separately to the corresponding metadata JSON. Production inference code (`backend/app/ai/models/diabetes_model.py`) loads both files together and fails loudly (raises) if either is missing or malformed, rather than falling back to a guessed threshold or feature order.

## Full Pipeline (Training → Production)

```text
Raw BRFSS 2015 CSV (253,680 rows)
  ↓
Dataset audit (duplicate/missing/invalid-value checks — dataset_audit.md)
  ↓
Drop 24,206 exact duplicate rows (leakage prevention)
  ↓
80/20 stratified train/test split (random_state=42) — SHARED between v1 and v2
  ↓
[v2 only] Feature reduction: 21 → 14 columns
  ↓
5-fold CV model-family comparison (training split only)
  ↓
RandomizedSearchCV hyperparameter tuning (training split only)
  ↓
StandardScaler fit + XGBoost fit (training split only)
  ↓
Sigmoid (Platt) calibration via CalibratedClassifierCV, OOF Brier-improvement decision
  ↓
Threshold sweep on OOF calibrated probabilities (training split only) → 0.10 selected
  ↓
Single final evaluation on the untouched test split (45,895 rows)
  ↓
Artifact saved: {version}_pipeline{_v2}.pkl + {version}_metadata{_v2}.json
  ↓
Loaded once at FastAPI startup (backend/app/main.py) — v2 only, in production today
  ↓
Inference: request → Pydantic validation → feature dict → pipeline.predict_proba
   → compare to metadata threshold → build_screening_response() → API response
   → persisted to MongoDB `predictions` collection, scoped to the authenticated user
```
