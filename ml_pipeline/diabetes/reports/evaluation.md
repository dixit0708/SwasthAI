# Final Evaluation Report — BRFSS Diabetes Risk Model

## Dataset

- Name: CDC BRFSS 2015 Diabetes Health Indicators (Kaggle / UCI mirror)
- Source file: `data/raw/brfss2015-diabetes-binary.csv`
- Target: `Diabetes_binary` — 1 only for a diagnosed-diabetes response, 0 for no-diabetes or prediabetes-only (see data/raw/README_brfss2015.md)
- Class distribution after dedup: see `data/processed/brfss_dataset_stats.json` (train ~15.3% positive, test ~15.3% positive, stratified)

## Cleaning

- No missing values in the source data — no imputation performed.
- 24,206 exact duplicate rows (9.5%) dropped before the train/test split, for leakage prevention (see `preprocessing_brfss.py`).
- No invalid/out-of-codebook values found; extreme BMI values (up to 98) retained as plausible, not removed as outliers.

## Training

- Split: 80/20 stratified, `random_state=42`.
- Cross-validation: `StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`.
- Imbalance handling: class weighting (`scale_pos_weight`/`class_weight='balanced'`), not SMOTE/undersampling — this keeps the natural ~15% prevalence intact, which matters for probability calibration; see `reports/cv_baseline_results.json`.
- Preprocessing: `StandardScaler` only (fit on the training split only, inside the saved pipeline).

## Models compared (5-fold CV, training split only)

See `reports/cv_baseline_results.json` for the full metric set (accuracy/precision/recall/specificity/F1/ROC-AUC/PR-AUC, mean ± std) across logistic regression, random forest, XGBoost, HistGradientBoosting, and SVM (SVM evaluated on an 8,000-row stratified subsample only — kernel SVM does not scale to 183,579 training rows, and is ineligible for production selection regardless of score).

## Model selection

Selected: **xgboost_sigmoid_calibrated**. XGBoost was the strongest scalable baseline by mean CV ROC-AUC and was carried into hyperparameter tuning (`RandomizedSearchCV`, 20 iterations, cv=3 for search efficiency, re-verified with the full 5-fold protocol afterward — see `reports/cv_tuned_results.json`).

## Hyperparameters

```json
{
  "subsample": 0.8,
  "reg_lambda": 5.0,
  "reg_alpha": 0,
  "n_estimators": 400,
  "min_child_weight": 5,
  "max_depth": 3,
  "learning_rate": 0.05,
  "gamma": 1.0,
  "colsample_bytree": 0.8
}
```

## Threshold

Decision threshold locked at **0.1** (not the default 0.5). See `reports/threshold_analysis.json` for the full sensitivity/specificity/precision/F1 sweep on out-of-fold CV predictions. For a screening/risk-assessment tool over an imbalanced (~15% positive) population, a lowered threshold trades some precision for materially higher recall/sensitivity — missing an at-risk person is a worse outcome than one extra person being told to consult a doctor.

## Calibration

Calibration method: **sigmoid (Platt scaling)**. Decision based on out-of-fold Brier score comparison — see `reports/calibration_check.json`.

## Final Test Metrics (evaluated once, held-out test set, never used for selection/tuning)

- Accuracy: 0.6460
- Precision: 0.2845
- Recall / Sensitivity: 0.8678
- Specificity: 0.6060
- F1: 0.4285
- ROC-AUC: 0.8199
- PR-AUC: 0.4477

## Confusion Matrix (test set)

- True Positives: 6091
- True Negatives: 23558
- False Positives: 15318
- False Negatives: 928

See `confusion_matrix.png`, `roc_curve.png`, `precision_recall_curve.png` in this directory.

## Feature importance (explainability)

Two methods were used because they can disagree, and did here — gain-based importance can overweight a feature used in many early tree splits even if it does not move held-out ranking performance much, while permutation importance measures the actual ROC-AUC drop when a feature is shuffled on the test set. Both are reported rather than picking whichever looks better.

**XGBoost gain-based importance (top 8):**

- `HighBP`: 0.4850
- `GenHlth`: 0.1165
- `HighChol`: 0.1020
- `Age`: 0.0479
- `BMI`: 0.0444
- `HeartDiseaseorAttack`: 0.0398
- `DiffWalk`: 0.0368
- `CholCheck`: 0.0303

**Permutation importance, mean ROC-AUC drop on the test set (top 8):**

- `GenHlth`: 0.05084
- `BMI`: 0.04139
- `Age`: 0.03459
- `HighBP`: 0.01732
- `HighChol`: 0.01196
- `CholCheck`: 0.00631
- `HvyAlcoholConsump`: 0.00475
- `Sex`: 0.00330

`GenHlth` (self-rated general health), `BMI`, and `Age` rank highest by permutation importance; `HighBP` dominates the gain-based ranking. Both agree that `HighBP`, `GenHlth`, `HighChol`, `Age`, and `BMI` are among the most influential features overall.

These features were influential for the model's predictions — this is not evidence that any one of them causes diabetes.

## External validation

**Not performed as a true external validation.** Of the two other provided files, `diabetes_binary_5050split_health_indicators_BRFSS2015.csv` is a strict undersampled subset of the primary training file (every row already appears in it), and `diabetes_012_health_indicators_BRFSS2015.csv` shares the exact same 253,680 rows/features as the primary file under a different target encoding — neither is an independent sample, so evaluating on either would not measure generalization. See `reports/dataset_audit.md` for the row-level verification.

Instead, a bounded face-validity check was run on the already-held-out test rows only, joining back to the 3-class label by feature-value match (ambiguous for the small fraction of rows sharing an identical feature pattern across people with different severities — acceptable for a face-validity check, not for a validation claim):

```json
{
  "matched_rows": 45895,
  "total_test_rows": 45895,
  "no_diabetes": {
    "mean_predicted_risk": 0.12319301928840852,
    "n": 38100
  },
  "prediabetes": {
    "mean_predicted_risk": 0.2428807384992912,
    "n": 841
  },
  "diabetes": {
    "mean_predicted_risk": 0.3155282184771319,
    "n": 6954
  }
}
```

If mean predicted risk increases monotonically from no-diabetes to prediabetes to diabetes, that supports the model tracking real clinical severity gradients, even though prediabetes is not a positive label it was trained on.

## Limitations

- All features are self-reported survey answers (BRFSS 2015), not clinical lab measurements — this is a lifestyle/health-history risk indicator, not a lab-based clinical model.
- The binary target excludes prediabetes from the positive class (Diabetes_binary==1 only when the original 3-class label was 2, i.e. diagnosed diabetes) — this model does not flag prediabetes as elevated risk.
- Training data is a single U.S. CDC survey year (2015) and U.S. population; generalization to other countries/years is unverified.
- No external, independent validation dataset was available for this training run — see reports/evaluation.md.

This model is an **AI-generated diabetes risk indicator, not a medical diagnosis**. It has not undergone independent external clinical validation.