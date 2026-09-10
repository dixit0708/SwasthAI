# Model Comparison — Baseline vs. Feature-Reduced Candidates

Methodology, applied identically to every row below (`feature_ablation.py`): fixed hyperparameters (held constant at the baseline's already-tuned values, to isolate the feature-set effect from a re-tuning effect) → 5-fold `StratifiedKFold` CV on the training split → out-of-fold calibration decision (sigmoid Platt scaling, Brier-score-gated) → threshold selected on the *deployed* (calibrated) out-of-fold probabilities, using one rule applied uniformly to every candidate (highest threshold, in 0.05 steps, that keeps training-OOF recall ≥ 0.85 — never tuned per-model to flatter it) → **one** final fit on the full training split → **one** evaluation on the untouched test split (45,895 rows). No candidate saw the test set until that last step.

Full machine-readable results: `reports/feature_ablation_results.json`. Baseline reference: `reports/baseline_comparison.md`.

## A) Importance-Ranked Ablation (pure ML evidence — answers "what does raw feature-count reduction cost?")

| Features | n | ROC-AUC | PR-AUC | Accuracy | Precision | Recall | Specificity | F1 | Brier (test) | Threshold |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **Baseline (all 21)** | 21 | **0.8199** | **0.4477** | 0.6460 | 0.2845 | 0.8678 | 0.6060 | 0.4285 | 0.10499 | 0.10 |
| Top 15 by importance | 15 | 0.8197 | 0.4477 | 0.6450 | 0.2838 | 0.8671 | 0.6048 | 0.4276 | 0.10501 | 0.10 |
| Top 12 by importance | 12 | 0.8192 | 0.4462 | 0.6449 | 0.2838 | 0.8674 | 0.6048 | 0.4276 | 0.10512 | 0.10 |
| Top 10 by importance | 10 | 0.8176 | 0.4431 | 0.6418 | 0.2815 | 0.8647 | 0.6016 | 0.4247 | 0.10538 | 0.10 |
| Top 8 by importance | 8 | 0.8158 | 0.4406 | 0.6408 | 0.2805 | 0.8619 | 0.6008 | 0.4233 | 0.10567 | 0.10 |
| Top 6 by importance | 6 | 0.8123 | 0.4334 | 0.6332 | 0.2765 | 0.8651 | 0.5913 | 0.4190 | 0.10630 | 0.10 |

**Reading this**: dropping the bottom 6 features (`AnyHealthcare, Veggies, Smoker, PhysActivity, Fruits, NoDocbcCost` — exactly the near-zero-importance items identified in `feature_selection_analysis.md`) costs essentially nothing: ROC-AUC moves from 0.8199 to 0.8197, a 0.0002 difference, smaller than the model's own 5-fold CV standard deviation (±0.001 in the baseline). Performance degrades **gradually and monotonically** from there, not with a cliff — even the 6-feature set retains 99% of the baseline's ROC-AUC (0.8123 vs 0.8199) and a comparable recall (0.8651 vs 0.8678), at the cost of specificity (0.5913 vs 0.6060 — more false positives per true positive caught).

## B) Patient-Facing Candidates (evidence + answerability-constrained — see `candidate_assessments.md`)

| Candidate | n | ROC-AUC | PR-AUC | Accuracy | Precision | Recall | Specificity | F1 | Brier (test) | Threshold |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Expanded | 14 | 0.8180 | 0.4447 | 0.6438 | 0.2825 | 0.8631 | 0.6042 | 0.4256 | 0.10530 | 0.10 |
| Balanced | 11 | 0.8165 | 0.4420 | 0.6424 | 0.2816 | 0.8627 | 0.6027 | 0.4246 | 0.10551 | 0.10 |
| Minimal | 7 | 0.8129 | 0.4333 | 0.6344 | 0.2771 | 0.8641 | 0.5929 | 0.4196 | 0.10621 | 0.10 |

**Confusion matrices (test, n=45,895)**:

| Candidate | TP | TN | FP | FN |
|---|--:|--:|--:|--:|
| Baseline (21) | 6,091 | 23,558 | 15,318 | 928 |
| Expanded (14) | 6,058 | 23,488 | 15,388 | 961 |
| Balanced (11) | 6,055 | 23,430 | 15,446 | 964 |
| Minimal (7) | 6,065 | 23,051 | 15,825 | 954 |

## The key comparison: patient-facing curation vs. pure statistical trimming at matched size

| Size | Pure importance-ranked ROC-AUC | Patient-facing ROC-AUC | Gap |
|--:|--:|--:|--:|
| ~14-15 | 0.8197 (top-15) | 0.8180 (Expanded, 14) | -0.0017 |
| ~11-12 | 0.8192 (top-12) | 0.8165 (Balanced, 11) | -0.0027 |
| ~6-7 | 0.8123 (top-6) | 0.8129 (Minimal, 7) | **+0.0006** |

Excluding the sensitive/access items (`Income, Education, AnyHealthcare, NoDocbcCost`) and the two day-count recall questions in favor of clinically-validated-but-locally-weak items (`PhysActivity`, and at Balanced/Expanded sizes `Smoker`, `HvyAlcoholConsump`, `CholCheck`, `Stroke`, `Fruits`) costs on the order of **0.002-0.003 ROC-AUC** at matched question counts — and at the smallest size, the patient-facing set actually performs *marginally better* than the pure-importance set (0.8129 vs 0.8123), because `Sex` (needed structurally) and `PhysActivity` (clinically core) turned out to be reasonable substitutes for `CholCheck` at that size. **This is genuine evidence, not a forced conclusion: preferring answerable, non-sensitive questions over raw statistical importance is close to free at every size tested.**

## Calibration and Threshold — consistent across every candidate

- **Every candidate** showed the same pattern as the baseline: raw (uncalibrated, `scale_pos_weight`-trained) Brier scores of 0.182-0.186, cut to 0.105-0.107 by sigmoid calibration — calibration is warranted regardless of feature count, not an artifact specific to the 21-feature model.
- **Every candidate's** threshold-selection rule (highest threshold keeping training-OOF recall ≥ 0.85) converged on **0.10** — the same value as the baseline. This was not assumed going in (the task explicitly warns not to assume the new model should reuse 0.10); it is a genuine result: this dataset's ~15% base rate and the calibrated probability distribution's shape are stable enough across feature-set size that the sensitivity-driven threshold choice doesn't move. Threshold remains stored in each candidate's own metadata, never hardcoded into application code, per the reproducibility requirement.
- Test-set Brier scores across all candidates (0.105-0.106) are close enough to each other and to the baseline (0.10499) that **calibration quality is not the deciding factor** between candidates — discrimination (ROC-AUC/PR-AUC/recall/specificity) is.

## Decision Matrix

| Criterion | Baseline (21) | Expanded (14) | Balanced (11) | Minimal (7) |
|---|---|---|---|---|
| Discrimination (ROC-AUC) | Best (0.8199) | Near-identical (0.8180) | Slightly lower (0.8165) | Materially lower (0.8129) |
| PR-AUC | Best (0.4477) | Near-identical (0.4447) | Lower (0.4420) | Lower (0.4333) |
| Sensitivity | Best (0.8678) | Comparable (0.8631) | Comparable (0.8627) | Comparable (0.8641) |
| Specificity | Best (0.6060) | Comparable (0.6042) | Comparable (0.6027) | Lower (0.5929) |
| Calibration/Brier | Comparable across all — not a differentiator | | | |
| Questionnaire length | 21 questions | 14 questions | 11 questions | 7 questions |
| Sensitive/access questions asked | 4 (Income, Education, AnyHealthcare, NoDocbcCost) | **0** | **0** | **0** |
| User burden (recall-based day-count questions) | 2 (MentHlth, PhysHlth) | **0** | **0** | **0** |
| Interpretability / product fit | Weak — half the discrimination cost isn't traceable to a defensible patient-facing reason | Strong | Strong | Strong, but at a real accuracy cost |
| Deployment complexity | Already built and shipped | Same architecture, smaller schema — low incremental complexity | Same | Same |

**Per the task's own rule** ("if the smaller model performs similarly, recommend it; if materially worse, say so"): Expanded and Balanced perform *similarly* to the baseline (ROC-AUC within 0.002-0.003, recall/specificity within a percentage point) while removing every poor-patient-fit question — recommend adopting one of them. Minimal shows a *real, if modest* discrimination and specificity cost (0.007 ROC-AUC, 1.3-point specificity drop vs. baseline) — it is not "free" the way Expanded/Balanced are, and should be positioned as a deliberately-faster, lower-fidelity option if offered at all, not a like-for-like replacement.

See `reports/final_recommendation.md` for the resulting recommendation.
