# v2 Threshold Analysis — Independent Threshold Selection

Full machine-readable output: `v2_threshold_sweep.json`.

## 1. Methodology

The threshold is swept over a grid of {0.05, 0.10, 0.15, ..., 0.50} on the OOF **calibrated** probability space (calibration was selected as the deployed probability space in `v2_calibration.md`, and the sweep happens after that decision, on that space — never on raw probabilities that won't actually be deployed). All values below come from the training split's OOF predictions; the test split is not touched until the single final evaluation.

Selection rule (applied uniformly across v1, the ablation study, and this v2 validation — never cherry-picked per model): **the highest threshold in the grid at which training-OOF recall/sensitivity is still ≥ 0.85.**

## 2. Full sweep

| Threshold | Sensitivity | Specificity | Precision | F1 | FPR | FNR | FP | FN |
|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 0.05 | 0.9394 | 0.4482 | 0.2351 | 0.3761 | 0.5518 | 0.0606 | 85,799 | 1,701 |
| **0.10** | **0.8599** | **0.6039** | **0.2816** | **0.4243** | **0.3961** | **0.1401** | **61,591** | **3,933** |
| 0.15 | 0.7792 | 0.6953 | 0.3159 | 0.4496 | 0.3047 | 0.2208 | 47,375 | 6,200 |
| 0.20 | 0.6994 | 0.7634 | 0.3480 | 0.4647 | 0.2366 | 0.3006 | 36,795 | 8,440 |
| 0.25 | 0.6158 | 0.8200 | 0.3818 | 0.4713 | 0.1800 | 0.3842 | 27,996 | 10,788 |
| 0.30 | 0.5217 | 0.8671 | 0.4149 | 0.4622 | 0.1329 | 0.4783 | 20,659 | 13,430 |
| 0.35 | 0.4304 | 0.9053 | 0.4508 | 0.4404 | 0.0947 | 0.5696 | 14,720 | 15,993 |
| 0.40 | 0.3342 | 0.9369 | 0.4889 | 0.3970 | 0.0631 | 0.6658 | 9,809 | 18,695 |
| 0.45 | 0.2305 | 0.9634 | 0.5324 | 0.3217 | 0.0366 | 0.7695 | 5,684 | 21,607 |
| 0.50 | 0.1392 | 0.9824 | 0.5883 | 0.2252 | 0.0176 | 0.8608 | 2,736 | 24,169 |

## 3. Selected threshold: 0.10

0.15 already drops sensitivity to 0.7792 (below the 0.85 floor), so **0.10** (sensitivity 0.8599) is the highest grid value that still clears the bar — identical to v1's independently-derived threshold, and to the earlier feature-ablation study's, arrived at again here from this candidate's own tuned-and-calibrated OOF probabilities rather than assumed from either prior result.

## 4. Trade-off being accepted

At threshold 0.10, roughly 4 in 10 people without diabetes (specificity 0.60, FPR 0.40) will still be flagged as elevated-risk in training-OOF terms, in exchange for missing only ~14% of true positive cases (FNR 0.14). This is a deliberate screening-sensitivity choice — a screening tool's purpose is to flag people for further (cheap, low-risk) follow-up, so favoring sensitivity over specificity is appropriate as long as this trade-off is disclosed, which it is here and in the production disclaimer text. This is the same trade-off v1 already made; v2 does not change the risk posture, only the number of questions needed to reach it.

## 5. Confirmation against the test set

This threshold, applied to the untouched test split exactly once, produced sensitivity 0.8628 and specificity 0.6043 (see `v2_final_recommendation.md` for the full test-metrics table) — consistent with the training-OOF sweep above, confirming the threshold generalizes and was not overfit to the training folds.
