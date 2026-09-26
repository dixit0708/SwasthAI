# Diabetes Model — 85% Accuracy Investigation

**Objective**: determine whether `diabetes-brfss-v2` can be improved to reach ≥85% test accuracy while maintaining meaningful diabetes-detection (sensitivity) performance, without modifying or overwriting the production model.

**Result: threshold tuning alone can reach ≥85% accuracy, but only by collapsing sensitivity to roughly 15–25% — an unacceptable tradeoff for a screening tool. No legitimate model-family, hyperparameter, or feature-configuration experiment changes this conclusion. No v3 is recommended. v2 (threshold 0.10) remains the production model, unmodified.**

## Contents

- **[threshold_analysis.json](threshold_analysis.json)** — extended OOF threshold sweep (0.05–0.70, with accuracy), training data only.
- **[model_comparison.json](model_comparison.json)** — Phase 4 experiments (hyperparameter tuning, model-family comparison, feature configuration), citing existing repository evidence.
- **[final_comparison.json](final_comparison.json)** — the ONE final held-out-test-set evaluation of the selected candidate threshold(s), vs. the v2 baseline.
- **[figures/](figures/)** — `accuracy_vs_threshold.png`, `precision_recall_vs_threshold.png`, `confusion_matrix_candidate.png`.

---

## Phase 1 — Audit (existing v2 model)

The existing `diabetes_pipeline_v2.pkl` + `diabetes_metadata_v2.json` were loaded read-only and run against `ml_pipeline/diabetes/data/processed/brfss_test.csv`. The reproduced metrics were an **exact match** to `diabetes_metadata_v2.json`'s stored `test_metrics` (accuracy 0.6439, ROC-AUC 0.8180, all confusion-matrix cells identical) — no discrepancy found. Verified: feature order (14, matches `feature_order`), threshold (0.10), calibration (`CalibratedClassifierCV`, sigmoid). Proceeded to Phase 2.

## Phase 2 — Threshold Analysis (OOF, training data only — test set untouched)

Methodology: replicated **exactly** the nested cross-validation procedure `ml_pipeline/diabetes/train_brfss_v2.py`'s `compute_oof_probabilities()` already uses — an outer `StratifiedKFold(5, shuffle=True, random_state=42)` via `cross_val_predict`, where each outer fold's classifier is itself a `CalibratedClassifierCV(XGBoost, method="sigmoid", cv=5)` fit only on that fold's training portion. v2's already-selected hyperparameters were reused unchanged (no new tuning in this phase). **Sanity check**: the resulting OOF Brier score (0.10626) matched `ml_pipeline/diabetes/reports/v2_calibration_check.json`'s recorded value exactly — confirming this is a faithful reproduction of the original training-time OOF computation, not a new/different procedure.

The held-out test set (`brfss_test.csv`) was never read anywhere in this phase.

| Threshold | Accuracy | Sensitivity | Specificity | Precision | F1 |
|--:|--:|--:|--:|--:|--:|
| 0.05 | 0.5234 | 0.9394 | 0.4482 | 0.2351 | 0.3761 |
| 0.10 (v2 production) | 0.6431 | 0.8599 | 0.6039 | 0.2816 | 0.4243 |
| 0.15 | 0.7082 | 0.7792 | 0.6953 | 0.3159 | 0.4496 |
| 0.20 | 0.7536 | 0.6994 | 0.7634 | 0.3480 | 0.4647 |
| 0.25 | 0.7887 | 0.6158 | 0.8200 | 0.3818 | 0.4713 |
| 0.30 | 0.8143 | 0.5217 | 0.8671 | 0.4149 | 0.4622 |
| 0.35 | 0.8327 | 0.4304 | 0.9053 | 0.4508 | 0.4404 |
| 0.40 | 0.8447 | 0.3342 | 0.9369 | 0.4889 | 0.3970 |
| **0.45** | **0.8513** | **0.2305** | **0.9634** | **0.5324** | **0.3217** |
| 0.50 (accuracy peak) | 0.8534 | 0.1392 | 0.9824 | 0.5883 | 0.2252 |
| 0.55 | 0.8514 | 0.0597 | 0.9943 | 0.6544 | 0.1094 |
| 0.60 | 0.8476 | 0.0050 | 0.9997 | 0.7692 | 0.0099 |
| 0.65 | 0.8471 | 0.0000 | 1.0000 | 0.0000 | 0.0000 |
| 0.70 | 0.8471 | 0.0000 | 1.0000 | 0.0000 | 0.0000 |

Full data: [threshold_analysis.json](threshold_analysis.json). Figures: [figures/accuracy_vs_threshold.png](figures/accuracy_vs_threshold.png), [figures/precision_recall_vs_threshold.png](figures/precision_recall_vs_threshold.png).

**Key observation**: beyond threshold ≈0.65, the model predicts "negative" for every single row (sensitivity = precision = 0) and accuracy plateaus at 0.8471 — this is the class-imbalance floor (test-set positive prevalence is 15.29%, so "always predict negative" alone scores ~84.7%). Accuracy above that floor is only reachable by trading away sensitivity, not by the model getting meaningfully "better" at detecting positive cases.

**Lowest threshold reaching ≥85% OOF accuracy: 0.45** (accuracy 0.8513, sensitivity 0.2305, specificity 0.9634). This means that even at the *best* accuracy-qualifying threshold, the model would (on training data) miss roughly 77% of true positive cases — down from missing 14% at the current production threshold (0.10).

## Phase 3 — Is Threshold Tuning Alone Enough?

**No — not with acceptable sensitivity.** Threshold tuning alone technically clears the 85% accuracy bar (Phase 2), but only by sacrificing the great majority of true-positive detections. Per the Phase 7 decision rules, this is explicitly **Case 2**: *"achieves ≥85% accuracy but sensitivity becomes very low → do not call it a superior model, document it as a tradeoff."* Model retraining experiments (Phase 4) were therefore still performed, to check whether a different model could shift the accuracy/sensitivity frontier rather than just move along it.

```
v2 threshold:        0.10  →  accuracy 0.6439, sensitivity 0.8628, specificity 0.6043
Candidate threshold: 0.45  →  accuracy 0.8513 (OOF) / 0.8546 (test), sensitivity 0.2478 (test), specificity 0.9642 (test)
```

This is **not** presented as an improved model — it is the same, unmodified v2 pipeline with a different operating point, and the tradeoff is severe (see Phase 6).

## Phase 4 — Model Experiments (citing existing repository evidence)

Full detail and source citations: [model_comparison.json](model_comparison.json).

**Experiment A — hyperparameter tuning.** Already performed for v2 (`ml_pipeline/diabetes/reports/v2_tuned_results.json`): `RandomizedSearchCV`, 20 candidates, cv=3, training data only. Tuned CV ROC-AUC 0.8137 vs. default 0.8130 — a 0.0007 improvement. This tuned configuration **is** the one already deployed as v2 and already used in the Phase 2 sweep above. Not re-run (redundant — same seed, same data, same deterministic search would reproduce the same result).

**Experiment B — model family comparison.** Already performed for v2 (`ml_pipeline/diabetes/reports/v2_family_comparison.json`): 5-fold CV, training data only, comparing Logistic Regression, Random Forest, XGBoost, HistGradientBoosting on the identical 14-feature dataset.

| Family | CV Accuracy (@0.5) | CV ROC-AUC | CV PR-AUC | CV Recall | CV Specificity | CV F1 |
|---|--:|--:|--:|--:|--:|--:|
| Logistic Regression | 0.7165 | 0.8056 | 0.4025 | 0.7534 | 0.7098 | 0.4484 |
| Random Forest | **0.7383** | 0.7962 | 0.4007 | 0.6843 | 0.7481 | 0.4444 |
| XGBoost (default) | 0.7051 | 0.8130 | 0.4298 | 0.7814 | 0.6913 | 0.4477 |
| HistGradientBoosting | 0.7050 | **0.8131** | 0.4294 | 0.7811 | 0.6913 | 0.4476 |

Even the highest-CV-accuracy family (Random Forest, at its own default 0.5 threshold) reaches only 73.8% — 11.2 points short of 85%. ROC-AUC across all four families is tightly clustered (0.796–0.813), meaning no family offers materially better discrimination to work with.

**Experiment C — feature configuration.** `diabetes-brfss-v1` (already trained and evaluated) is, by construction, the "use every legitimate BRFSS column" configuration — all 21 original features, including the 7 v2 removed. v1's test ROC-AUC (0.8199) is only 0.0019 higher than v2's (0.8180). No feature outside the BRFSS codebook (family history, HbA1c, fasting glucose) was added or fabricated — none are available in this dataset (see `docs/ml/diabetes/limitations.md`).

**Conclusion of Phase 4**: the achievable ROC-AUC ceiling across every legitimate lever tested (tuning, model family, full feature set) is approximately 0.80–0.82. This ceiling, combined with the dataset's ~15% positive prevalence, is what produces the accuracy/sensitivity tradeoff in Phase 2 — it is not a symptom of under-tuning.

## Phase 6 — Final Candidate Evaluation (ONE pass, untouched test set)

The candidate (threshold=0.45, selected from OOF training data only — see Phase 2) was evaluated exactly once on the held-out test set. **This is the same, unmodified v2 pipeline** — only the decision threshold differs; no retraining occurred.

| Metric | v2 (threshold 0.10) | Candidate (threshold 0.45) | Change |
|---|--:|--:|--:|
| Accuracy | 0.6439 | **0.8546** | **+0.2107** |
| Precision | 0.2825 | 0.5552 | +0.2727 |
| Recall / Sensitivity | 0.8628 | **0.2478** | **−0.6150** |
| Specificity | 0.6043 | 0.9642 | +0.3598 |
| F1 | 0.4256 | 0.3426 | −0.0830 |
| ROC-AUC | 0.8180 | 0.8180 | 0 (threshold-independent) |
| PR-AUC | 0.4446 | 0.4446 | 0 (threshold-independent) |
| Brier score | 0.10530 | 0.10530 | 0 (threshold-independent) |
| TP | 6,056 | 1,739 | −4,317 |
| TN | 23,494 | 37,483 | +13,989 |
| FP | 15,382 | 1,393 | −13,989 |
| FN | 963 | **5,280** | **+4,317** |

Full data (including the threshold=0.50 accuracy-peak candidate for comparison): [final_comparison.json](final_comparison.json). Figure: [figures/confusion_matrix_candidate.png](figures/confusion_matrix_candidate.png).

**In plain terms**: accuracy improves by 21 points, but the candidate now misses 5,280 of the 7,019 diabetes-positive people in the test set (75.2% missed, vs. 13.7% missed by the current production model). For a screening tool whose entire purpose (as documented in `docs/ml/diabetes/evaluation.md`'s threshold-selection rationale) is to keep sensitivity ≥0.85 so that few at-risk people go unflagged, this is a direct contradiction of the model's intended use — it would now fail to flag 3 out of every 4 people it's meant to catch.

## Phase 7 — Decision

**Case 2 applies**: the candidate reaches ≥85% accuracy but sensitivity is unacceptably low (0.2478, vs. a design floor of ≥0.85 used to select every other threshold in this model's history). **This is documented as a tradeoff, not reported as a superior model.**

## Phase 8 — Should v3 Be Created?

**No.** No `diabetes_pipeline_v3.pkl` / `diabetes_metadata_v3.json` was created. The evidence in Phases 2, 4, and 6 shows that reaching 85% accuracy on this dataset, with this task's ~15% class prevalence, requires abandoning the screening-sensitivity design principle that both v1 and v2 were deliberately built around — this is not a "better model" being left undeployed, it is a different (and, for this application, worse) operating point on the *same* model. Promoting it to v3 would misrepresent an accuracy/sensitivity tradeoff as an improvement.

`diabetes-brfss-v2` (threshold 0.10) remains the current production model, completely unmodified by this investigation. `diabetes-brfss-v1` remains the rollback baseline, also unmodified.

---

## Metric Definitions

See `docs/ml/diabetes/evaluation.md` "Metric Definitions" for the standard definitions (accuracy, precision, recall/sensitivity, specificity, F1, ROC-AUC, PR-AUC, Brier score) used throughout this report.

## Data Leakage Safeguards (Phase 5 compliance)

- Threshold selection (Phase 2) used only out-of-fold training predictions, generated via nested cross-validation — the test set was not loaded until Phase 6.
- No preprocessing was fit on the full dataset before splitting; `StandardScaler` is fit fresh inside each CV fold, exactly as in the original v2 training pipeline.
- No hyperparameter search was performed in this task (Experiment A reused v2's already-tuned, already-cross-validated values).
- The test set was evaluated exactly once per candidate threshold in Phase 6, and never used to choose which threshold to evaluate.
- No synthetic, duplicated, or oversampled records were introduced anywhere in this investigation.
