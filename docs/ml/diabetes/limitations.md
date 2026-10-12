# Limitations — SwasthAI Diabetes Risk Model

Applies to both `diabetes-brfss-v2` (current production) and `diabetes-brfss-v1` (rollback), unless noted otherwise. Source: `ml_pipeline/diabetes/artifacts/diabetes_metadata_v2.json` (field `limitations`), `ml_pipeline/diabetes/reports/evaluation.md`, `v2_final_recommendation.md`.

## Dataset Limitations

- **Self-reported, not clinical**: every input is a self-reported survey answer from the CDC BRFSS 2015 telephone survey, not a laboratory measurement (contrast with a fasting glucose or HbA1c test). This is a lifestyle/health-history risk indicator, not a lab-based clinical model.
- **Single survey year and country**: training data is exclusively the 2015 U.S. CDC BRFSS. Generalization to other years, other countries, or populations not represented in a 2015 U.S. telephone survey is **unverified**.
- **No independent external validation dataset**: the only two other files considered (`5050split`, `012`) were verified (`dataset_audit.md`) to share the same underlying 253,680-respondent population as the primary training file, not an independent sample — so no true external validation has been performed for either v1 or v2.
- **Population vs. SwasthAI users**: no evidence in the repository establishes that SwasthAI's actual user population matches the demographic or geographic distribution of 2015 U.S. BRFSS respondents.
- **No demographic-slice performance breakdown**: neither v1 nor v2's evaluation reports include accuracy/sensitivity/specificity broken out by age group, sex, or other subgroup — whether performance is equitable across demographic slices is **not independently verified**.

## Target Definition Limitations

- **Prediabetes is not flagged as elevated risk**: the binary target groups prediabetes together with "no diabetes" in the negative class (verified in `dataset_audit.md`) — the model does not distinguish a prediabetes pattern from a no-diabetes pattern, and does not treat prediabetes as a positive/elevated case.
- **Diagnosed diabetes only**: the positive class requires a self-reported diabetes diagnosis; undiagnosed diabetes in the survey population (if any) would appear in the training data's negative class, which the model has no way to correct for.

## Feature Limitations

- **v2 excludes family history**: investigated explicitly (`ml_pipeline/diabetes/reports/family_history_investigation.md`) and found to be evidence-supported by other validated screening instruments (ADA, FINDRISC, CDC, USPSTF all include it), but **no dataset was available to this project** that combines family history with these BRFSS lifestyle features in a verified, ready-to-use form. This was not worked around by fabricating or approximating a family-history-like feature. It remains a known, disclosed gap in both v1 and v2 — not an oversight.
- **v2's 14-feature reduction has a small, disclosed cost**: relative to v1, v2 misses roughly 5 additional true-positive cases per 1,000 people with diabetes in the test population (sensitivity 0.8628 vs. 0.8678) — see the v1-vs-v2 comparison in [evaluation.md](evaluation.md). This was an accepted, explicitly-evaluated trade-off in exchange for removing 4 sensitive/access-related questions (income, education, healthcare coverage, cost barrier) from the questionnaire, not an accidental regression.
- **v1's removed features are not "worse", they are unused in production**: v1's 21-feature set (still on disk, unmodified, as `diabetes_pipeline.pkl` + `metadata.json`) is retained purely as a comparison baseline/rollback, not because it is considered more accurate — the two versions are, per the evidence, comparable in discrimination and calibration.

## Class Imbalance

- Test-set positive prevalence is 15.29% — imbalanced enough that accuracy alone is a misleading summary metric (see [evaluation.md](evaluation.md) "Class Imbalance" section for the "always predict negative" illustration).
- Handled via `scale_pos_weight` class weighting inside XGBoost, not resampling — this preserves real-world prevalence for calibration but means the model was never shown an artificially balanced dataset.

## Threshold Limitations

- The 0.10 decision threshold is a deliberate high-sensitivity choice for a screening context, not a universally "optimal" value — at this threshold, roughly 4 in 10 people without diabetes are still flagged for follow-up (specificity ≈ 0.60). A different downstream use case (e.g. one where false positives are more costly) might reasonably choose a different threshold; that would require re-deriving the sweep, not simply changing the number, because the calibration and threshold were selected together.
- The same threshold is used for both v1 and v2 by design (`v2_threshold_analysis.md`) — it was independently re-derived for v2's feature set and happened to land on the same value as v1's, not copied over unverified.

## Calibration Limitations

- Calibration and its reliability were evaluated on the training split (out-of-fold) and the held-out test split only. The two highest predicted-probability bins in the test-set reliability check are based on very small sample sizes (48–1,689 rows out of 45,895) and their apparent miscalibration in that range should not be treated as a robust finding (`v2_calibration.md`).
- Calibration quality has not been assessed on any population outside the BRFSS 2015 test split.

## False-Positive / False-Negative Burden

- **False positives** (15,382 in the v2 test set): a person without diabetes (or with prediabetes only) is told their inputs show elevated risk indicators and encouraged to consult a professional. This is a burden (unnecessary concern, possible unnecessary follow-up testing) but not a diagnosis and not an automated clinical action.
- **False negatives** (963 in the v2 test set, ~13.7% of true positives): a person with a diabetes diagnosis in the training-data sense is told their inputs do not show elevated risk. This is the more consequential error type for a screening tool, and is the reason the threshold is set low (favoring sensitivity) rather than at the default 0.5.

## Generalization / Distribution-Shift Limitations

- No monitoring or re-validation process is documented in the repository for detecting if the model's real-world input distribution (SwasthAI's actual users) drifts from the 2015 BRFSS training distribution over time.
- No evidence exists of periodic re-evaluation, retraining schedule, or drift-detection tooling for either version.

## Clinical Validation Status

**This model is a machine-learning risk/screening tool. It is not a clinically validated diagnostic system.** No external clinical validation, prospective clinical study, or review by a licensed clinician is documented anywhere in the repository for either v1 or v2 (`v2_final_recommendation.md` §11, explicit). This must not be represented otherwise in any product surface, consistent with the platform's own safety rules (`AGENTS.md` §11, §44).

## Appropriate Use Boundary (restated)

- Use: an AI-generated screening/risk indicator to inform a conversation with a healthcare professional.
- Do not use: as a diagnosis, as a substitute for laboratory testing, as a basis for emergency decisions, or as a standalone treatment decision. See [model_card.md](model_card.md) §5 for the full list, and the fixed disclaimer text attached to every API response.
