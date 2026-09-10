# v2 Calibration — Decision, Method, and Calibration-in-the-Large

Full machine-readable output: `v2_calibration_check.json`, `v2_calibration_in_the_large.json`.

## 1. Calibration decision (must happen before threshold selection)

Decided via out-of-fold (OOF) Brier score comparison on the training split only — the deployed threshold is swept afterward on whichever probability space this decision selects, never the other one (see `v2_threshold_analysis.md`). The decision rule (applied uniformly to v1, the feature-ablation study, and v2): use calibration if `raw_brier - calibrated_brier > 0.0005`.

| | Brier score (OOF, training split) |
|---|--:|
| Raw (uncalibrated tuned XGBoost) | 0.18278 |
| Sigmoid-calibrated (Platt scaling) | 0.10626 |
| Improvement | 0.07652 |

0.07652 ≫ 0.0005 → **calibration is used.** This is a large, unambiguous improvement, not a marginal call — the tuned XGBoost's raw output is substantially overconfident (typical of boosted trees without calibration) and sigmoid calibration corrects this dramatically on held-out folds before the test set is ever touched.

## 2. Method

`CalibratedClassifierCV` with `method='sigmoid'` (Platt scaling), wrapping the tuned XGBoost classifier from `v2_model_comparison.md`, fit via cross-validation on the training split. This mirrors v1's calibration method exactly (same method, independently re-justified for this feature set rather than assumed).

## 3. Test-set calibration result

On the untouched test split, using the final fitted pipeline (tuned XGBoost + sigmoid calibration) at the deployed threshold of 0.10:

- **Brier score (test): 0.10530** — comparable to v1's 0.10499 (a difference of 0.00031, well within the range expected from a 7-feature reduction).

## 4. Calibration-in-the-large

| | Value |
|---|--:|
| Mean predicted probability (test set) | 0.15451 |
| Observed prevalence (test set) | 0.15294 |
| Absolute gap | 0.00157 |

The model's average predicted risk (15.45%) tracks the actual observed positive rate (15.29%) closely — a 0.16-percentage-point gap — confirming the model is not systematically over- or under-estimating risk in aggregate.

## 5. Reliability by probability decile (observed vs. predicted, test set)

| Predicted-probability bin | n | Mean predicted | Observed rate |
|---|--:|--:|--:|
| [0.0, 0.1) | 24,457 | 0.0388 | 0.0394 |
| [0.1, 0.2) | 7,182 | 0.1466 | 0.1488 |
| [0.2, 0.3) | 5,222 | 0.2469 | 0.2319 |
| [0.3, 0.4) | 4,024 | 0.3480 | 0.3178 |
| [0.4, 0.5) | 3,321 | 0.4462 | 0.4408 |
| [0.5, 0.6) | 1,641 | 0.5411 | 0.6076 |
| [0.6, 0.7) | 48 | 0.6069 | 0.7500 |

The first five bins (covering 44,206 of 45,895 test rows, ~96%) track observed rates within ~3 percentage points. The two highest bins diverge more (the [0.6, 0.7) bin is based on only 48 rows, so its 0.75 observed rate is a small-sample estimate, not a reliable signal) — this is the expected pattern for a model whose training data thins out sharply at high predicted-risk values, and matches the general shape (good calibration through the mid-range, noisier at the sparse high end) already documented for v1's calibration curve. No systematic miscalibration direction (neither uniformly over- nor under-confident) is evident.
