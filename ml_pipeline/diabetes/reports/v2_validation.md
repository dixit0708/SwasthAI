# v2 Validation — Independent Re-Verification of the 14-Feature Candidate

This is an independent validation pass, not a re-statement of `feature_selection_analysis.md` / `candidate_assessments.md` / `model_comparison.md`'s conclusions. Those documents recommended the 14-feature "Expanded" candidate using hyperparameters held constant at the v1 baseline's values. This pass re-derives everything from scratch for that specific feature set — its own hyperparameter search, its own model-family comparison, its own calibration decision, its own threshold sweep, and exactly one held-out test evaluation — using `train_brfss_v2.py`, and does not assume the earlier study's numbers still hold once the feature set is tuned on its own terms.

## 1. Dataset integrity re-check

Same source as v1: `diabetes_binary_5050split_health_indicators_BRFSS2015.csv` is **not** used (it is artificially class-balanced, which would bias prevalence-dependent metrics); the full, naturally-imbalanced `diabetes_012_health_indicators_BRFSS2015.csv` collapsed to binary (`Diabetes_binary`: 0 = no diabetes, 1 = prediabetes or diabetes) is used, identical to v1's target definition. Re-checked before training:

- **Duplicates**: removed *before* the train/test split (not after), so no duplicate row can appear in both splits.
- **Missing values**: none in the 14 selected columns (BRFSS's own coding already excludes "don't know"/"refused" responses from this cleaned CSV).
- **Categorical ranges**: every binary field (`HighBP, HighChol, CholCheck, Smoker, Stroke, HeartDiseaseorAttack, PhysActivity, Fruits, HvyAlcoholConsump, DiffWalk, Sex`) confirmed restricted to {0,1}; `GenHlth` confirmed restricted to {1..5}; `Age` confirmed restricted to {1..13}; `BMI` confirmed within a physiologically plausible range.
- **Target leakage**: none of the 14 features are derived from or definitionally overlapping with `Diabetes_binary`.
- **Train/test separation**: stratified 80/20 split, `random_state=42`, performed once, before any model fitting, tuning, or calibration; the test split's labels are not touched again until the single final evaluation in Stage 5 of `train_brfss_v2.py`.
- **Class prevalence**: consistent with v1's audited prevalence (~15.3% positive class) since this is the same underlying dataset with a feature-column subset, not a resample.

No feature selection, hyperparameter tuning, or calibration fitting used the test split's labels at any point — every model-family comparison, tuning search, calibration decision, and threshold sweep in Stages 1-4 runs on out-of-fold (OOF) predictions from the training split only.

## 2. Ordering-correctness re-verification

The same ordering bug class caught during v1's original build (sweeping a decision threshold on raw probabilities while planning to deploy calibrated ones) was checked again for v2 by construction: `train_brfss_v2.py`'s Stage 3 decides whether to calibrate *before* Stage 4 sweeps the threshold, and Stage 4 explicitly sweeps on whichever probability space (raw or calibrated) Stage 3 selected for deployment — never the other one. See `v2_calibration.md` for the calibration decision and `v2_threshold_analysis.md` for the sweep that consumed it.

## 3. Pipeline stages (as implemented in `train_brfss_v2.py`)

1. **Model-family comparison** (Logistic Regression, Random Forest, XGBoost default, HistGradientBoosting) via 5-fold CV on the training split only — see `v2_model_comparison.md`.
2. **Independent hyperparameter tuning** of XGBoost via `RandomizedSearchCV` (20 candidates × 3 folds = 60 fits) — a deliberately focused search, not a large grid — see `v2_model_comparison.md`.
3. **Calibration decision** via OOF Brier score comparison on the training split — see `v2_calibration.md`.
4. **Threshold sweep** on the OOF probability space that will actually be deployed — see `v2_threshold_analysis.md`.
5. **One final fit** on the full training split and **one evaluation** on the untouched test split — see `v2_final_recommendation.md` for the resulting metrics and the v1-vs-v2 comparison.

## 4. Conclusion of this validation pass

The independently re-tuned 14-feature candidate does not materially outperform the feature-selection study's constant-hyperparameter estimate (test ROC-AUC 0.8180 in both cases, to 4 decimal places), nor does it reveal that XGBoost was the wrong choice — HistGradientBoosting was compared and edged it out by 0.0001 ROC-AUC, statistically indistinguishable from the fold-to-fold CV noise (±0.0008-0.0012 across all four families), so switching families would add complexity without a defensible accuracy justification. This validates rather than overturns the earlier recommendation, on independently-derived grounds. Full numbers and the v1-vs-v2 decision are in `v2_final_recommendation.md`.
