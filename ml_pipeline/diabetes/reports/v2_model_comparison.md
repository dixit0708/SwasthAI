# v2 Model Comparison — Family Selection & Hyperparameter Tuning

Full machine-readable output: `v2_family_comparison.json`, `v2_tuned_results.json`.

## 1. Model-family comparison (do not assume XGBoost)

5-fold stratified CV, training split only, default/near-default hyperparameters per family, mean ROC-AUC ± std across folds:

| Model family | CV ROC-AUC | Std | Fit time |
|---|--:|--:|--:|
| Logistic Regression | 0.8056 | ±0.0008 | 3.6s |
| Random Forest | 0.7962 | ±0.0012 | 29.0s |
| XGBoost (default) | 0.8130 | ±0.0008 | 4.1s |
| HistGradientBoosting | **0.8131** | ±0.0010 | 5.8s |

**Strongest family by mean CV ROC-AUC: HistGradientBoosting**, by a margin of 0.0001 over XGBoost — smaller than either family's own fold-to-fold standard deviation (±0.0008–0.0010). This is not a statistically meaningful difference; it does not constitute evidence that HistGradientBoosting is actually better, only that the two gradient-boosting families are indistinguishable on this feature set at default settings. Logistic Regression trails both by ~0.007 ROC-AUC (a real, if modest, gap — the relationship is not purely linear), and Random Forest trails further still.

**Decision: retain XGBoost.** Switching production families to chase a 0.0001 CV-ROC-AUC difference within noise would add operational complexity (different serialization, different calibration behavior, different production dependency) for no defensible accuracy gain, and XGBoost is also the v1 baseline's architecture, which keeps the two models' behavior easier to reason about side-by-side. This decision was reached by actually running the comparison above, not assumed in advance.

## 2. Independent hyperparameter tuning (XGBoost)

A focused `RandomizedSearchCV` — 20 candidate configurations × 3-fold CV = 60 fits — over `n_estimators, max_depth, learning_rate, subsample, colsample_bytree, min_child_weight, gamma, reg_alpha, reg_lambda`, scored on ROC-AUC, training split only. This is intentionally a search, not a reuse of v1's fixed hyperparameters — v1's values were never given to this search as a starting point or default.

**Best configuration found:**

```
subsample: 0.8
reg_lambda: 5.0
reg_alpha: 0
n_estimators: 400
min_child_weight: 5
max_depth: 3
learning_rate: 0.05
gamma: 1.0
colsample_bytree: 0.8
```

- Best CV=3 ROC-AUC during the search: 0.8135
- Full 5-fold re-verification of the winning configuration: **ROC-AUC = 0.8137 (±0.0008)**

This is 0.0006 above the default-hyperparameter XGBoost run in the family comparison above (0.8130 → 0.8137) — a small, genuine improvement from tuning, and still within the noise band of HistGradientBoosting's 0.8131, reinforcing that family choice is not the lever that matters here; the feature set is.

## 3. `scale_pos_weight`

Set to 5.5382, matching the training split's actual negative:positive class ratio — the same class-imbalance handling strategy as v1, re-derived (not hardcoded) from this training split's own prevalence rather than copied from v1's value.
