# Baseline Audit — BRFSS 21-Feature Calibrated XGBoost

This is the reference point every candidate model in this redesign is measured against. Nothing here was retrained for this task — these are the already-computed, already-audited results from the original BRFSS training run (`artifacts/metadata.json`, `data/processed/brfss_evaluation_results.json`, `reports/evaluation.md`, `reports/calibration_check.json`), re-verified by reading those files directly rather than from memory.

**Model identity: BASELINE — BRFSS 21-feature calibrated XGBoost (`diabetes-brfss-v1`)**

## Dataset

- **Source**: CDC BRFSS 2015 Diabetes Health Indicators (`data/raw/brfss2015-diabetes-binary.csv`), 253,680 raw rows.
- **Target**: `Diabetes_binary` — 1 only when the respondent reported a diagnosed-diabetes answer (equivalently, `Diabetes_012 == 2`); prediabetes-only responses are folded into the negative class. This is a diagnosed-diabetes classifier, not a prediabetes classifier.
- **Features**: 21 self-reported BRFSS survey items (see `data/raw/README_brfss2015.md` for the full codebook) — no clinical lab measurements.
- **Duplicates**: 24,206 exact duplicate rows (9.5%) dropped **before** the train/test split (leakage prevention) — not treated as data-entry errors, since 21 low-cardinality columns across 253k respondents will legitimately collide by chance.
- **Missing values**: none (0 nulls) — no imputation was required or performed.
- **Split**: 80/20 stratified, `random_state=42`, on the deduplicated 229,474 rows → 183,579 train / 45,895 test.
- **Class prevalence**: ~15.3% positive in both splits (stratified).
- **Leakage checks**: verified directly — 0 exact-row overlap between `brfss_train.csv` and `brfss_test.csv`; `train_rows + test_rows` exactly equals the deduplicated raw row count.

## Current Model

- **Architecture**: `StandardScaler` → `CalibratedClassifierCV(XGBClassifier, method="sigmoid", cv=5)`.
- **Hyperparameters** (from `RandomizedSearchCV`, cv=3, re-verified on full 5-fold): `n_estimators=400, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, min_child_weight=5, gamma=1.0, reg_lambda=5.0, reg_alpha=0`.
- **Class imbalance handling**: `scale_pos_weight=5.5382` (natural training-split prevalence ratio) — no resampling, so the calibrated probabilities remain interpretable against the real ~15% base rate.
- **Calibration**: sigmoid (Platt scaling) — selected because it cut the out-of-fold Brier score by 42% relative to the raw model (0.18163 → 0.10595).
- **Decision threshold**: **0.10** on the *calibrated* probability scale (not the raw one — an ordering mistake in the original build tuned the threshold on raw probabilities before calibration was decided; this was caught and fixed before the artifact shipped — see `reports/evaluation.md`).
- **Feature order / artifact format**: `artifacts/diabetes_pipeline.pkl` (joblib) + `artifacts/metadata.json` carrying `feature_order`, `decision_threshold`, `calibration_method`, and full provenance — the threshold is metadata-driven, never hardcoded into backend or frontend code.

## Current Performance (held-out test set, 45,895 rows, evaluated once)

| Metric | Value |
|---|--:|
| ROC-AUC | 0.8199 |
| PR-AUC | 0.4477 |
| Accuracy | 0.6460 |
| Precision | 0.2845 |
| Recall / Sensitivity | 0.8678 |
| Specificity | 0.6060 |
| F1 | 0.4285 |
| Brier (test set) | 0.10499 |
| Decision threshold | 0.10 (calibrated scale) |

**Confusion matrix (test)**: TP=6,091 · TN=23,558 · FP=15,318 · FN=928

Note on Brier score: the original build only computed the **training-split out-of-fold** calibrated Brier score (0.10595) to *decide* calibration (correct methodology — that decision must never touch test data). For a clean apples-to-apples comparison against the new candidates below (which all report test-set Brier), the test-set Brier score (0.10499) was computed for this comparison — this is read-only evaluation of the existing artifact, not a retrain, and does not change the baseline model, its threshold, or its calibration in any way.

Cross-validation summary (training split, 5-fold, tuned model): ROC-AUC 0.8155 ± 0.0010, PR-AUC 0.4337 ± 0.0054 — consistent with the test-set ROC-AUC (0.8199), i.e. no meaningful train/test drift.

## Feature Importance (exploratory evidence only — not causal, not clinical guidance)

**Tree gain-based** (top 8): HighBP 0.485, GenHlth 0.117, HighChol 0.102, Age 0.048, BMI 0.044, HeartDiseaseorAttack 0.040, DiffWalk 0.037, CholCheck 0.030.

**Permutation importance, ROC-AUC drop** (top 8): GenHlth 0.0508, BMI 0.0414, Age 0.0346, HighBP 0.0173, HighChol 0.0120, CholCheck 0.0063, HvyAlcoholConsump 0.0048, Sex 0.0033.

The two methods disagree on which single feature dominates (gain says `HighBP`; permutation says `GenHlth`) — both are reported in every downstream analysis rather than picking whichever ranks a preferred feature higher.

## Limitations already on record

- Self-reported survey data, not clinical lab measurements.
- Excludes prediabetes from the positive class.
- Single US survey year (2015); no cross-year or cross-population validation.
- No independent external validation dataset (the other two provided BRFSS files are non-independent subsets/relabelings of this same population — see `reports/dataset_audit.md`).
- Not clinically validated; output is a screening risk indicator, never a diagnosis.

This baseline is **not being retrained, deleted, or overwritten** as part of this task. It remains the comparison reference for every candidate below.
