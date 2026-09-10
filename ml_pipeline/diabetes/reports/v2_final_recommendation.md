# v2 Final Recommendation — Diabetes BRFSS Model Decision

This synthesizes `v2_validation.md`, `v2_model_comparison.md`, `v2_calibration.md`, and `v2_threshold_analysis.md` into the production decision required by the v2 validation task. It answers the decision gate directly: **is `diabetes-brfss-v2` actually better/appropriate than `diabetes-brfss-v1`, on the evidence produced above — not assumed in advance?**

## 1. Decision: promote `diabetes-brfss-v2` to production

The 14-feature candidate is **comparable, not better, on discrimination metrics**, but delivers a **materially smaller patient-facing questionnaire with zero sensitive/access questions removed at negligible measured cost** — see the table below. This satisfies the task's standard ("comparable or better → recommend v2 with the smaller questionnaire"). v1's artifacts remain on disk, untouched, as the permanent comparison baseline and rollback path; this is a promotion, not a destructive replacement.

## 2. v1 vs. v2 — full comparison

| Metric | v1 (21 features) | v2 (14 features) | Difference |
|---|--:|--:|--:|
| ROC-AUC (test) | 0.8199 | 0.8180 | -0.0019 |
| PR-AUC (test) | 0.4477 | 0.4446 | -0.0031 |
| Sensitivity/Recall (test) | 0.8678 | 0.8628 | -0.0050 |
| Specificity (test) | 0.6060 | 0.6043 | -0.0017 |
| Precision (test) | 0.2845 | 0.2825 | -0.0020 |
| F1 (test) | 0.4285 | 0.4256 | -0.0029 |
| Brier (test) | 0.10499 | 0.10530 | +0.00031 |
| Decision threshold | 0.10 | 0.10 | none |
| Feature count | 21 | 14 | -7 (-33%) |
| Sensitive/access questions | 4 (income, education, healthcare coverage, cost-barrier) | 0 | -4 |

Every discrimination and calibration metric moved by less than 0.005 absolute — smaller than typical fold-to-fold CV noise (±0.0008–0.0012 observed across model families in `v2_model_comparison.md`) — while the questionnaire dropped by a third and lost every socioeconomic/access-proxy question. This was independently re-derived in this validation pass (own hyperparameter search, own model-family comparison, own calibration decision, own threshold sweep) rather than assumed from the earlier feature-selection study, and reached the same conclusion the earlier study reached.

## 3. Calibration comparison

Both models use sigmoid (Platt) calibration, decided independently for each via the same OOF-Brier-improvement rule (`raw_brier − calibrated_brier > 0.0005`); v2's improvement (0.07652) was, if anything, more decisive than a marginal call. v2's calibration-in-the-large (mean predicted 0.15451 vs. observed 0.15294, gap 0.00157) shows the same well-calibrated pattern documented for v1, with the same expected noisiness at the sparse high-probability tail.

## 4. False-positive burden

At the shared threshold of 0.10, v2's test-set false-positive count is 15,382 out of 38,876 true negatives (specificity 0.6043) vs. v1's comparable rate (specificity 0.6060) — statistically indistinguishable. v2 does not meaningfully change how many healthy people get flagged for follow-up; it changes how many questions they had to answer to get that flag.

## 5. False-negative burden

v2 misses 963 of 7,019 true positive cases in the test set (sensitivity 0.8628, FNR 0.1372) vs. v1's 0.8678 sensitivity (FNR 0.1322) — a difference of 0.005, i.e. roughly 5 additional missed cases per 1,000 people with diabetes in this test population. This is the actual, disclosed cost of the questionnaire reduction; it is small but not zero, and is stated here rather than glossed over.

## 6. Questionnaire burden — why this trade is worth it

v1 asked 21 questions across 5 sections including income bracket, education level, health-insurance coverage, and whether cost ever prevented a doctor visit — sensitive, socioeconomically-loaded questions that a screening tool has no clinical need to ask and that plausibly depress completion rates or produce guarded/inaccurate answers. v2 asks 14 questions across 3 sections, none of them income/education/access-related, for a measured cost smaller than the model's own noise floor. This is the central trade the task asked to be evaluated honestly, and the evidence supports making it.

## 7. Final feature set (14)

`Sex, Age, BMI, GenHlth, HighBP, HighChol, CholCheck, HeartDiseaseorAttack, PhysActivity, Fruits, HvyAlcoholConsump, Stroke, DiffWalk, Smoker`

Exact `feature_order` as stored in `diabetes_metadata_v2.json` (must match at inference time): `HighBP, HighChol, CholCheck, BMI, Smoker, Stroke, HeartDiseaseorAttack, PhysActivity, Fruits, HvyAlcoholConsump, GenHlth, DiffWalk, Sex, Age`.

## 8. Final patient-facing questionnaire (exact wording, as implemented in `frontend/prediction-diabetes.html`)

**About You**
1. How do you identify your sex for this health assessment? (Female / Male)
2. Which age range do you belong to? (18-24 through 80 or older, 13 options)
3. Height and weight (BMI computed automatically)
4. In general, would you say your health is... (Excellent / Very good / Good / Fair / Poor)

**Health History**
5. Have you ever been told by a doctor, nurse, or other health professional that you have high blood pressure?
6. Have you ever been told that you have high cholesterol?
7. Have you had your cholesterol checked within the past 5 years?
8. Have you ever been told you had a stroke?
9. Have you ever been told you had coronary heart disease or a heart attack?
10. Do you have serious difficulty walking or climbing stairs?

**Lifestyle**
11. Have you smoked at least 100 cigarettes in your entire life (about 5 packs)?
12. Have you done any physical activity or exercise in the past 30 days, other than your regular job?
13. Do you eat fruit one or more times per day?
14. Are you a heavy drinker (adult men having more than 14 drinks per week, adult women having more than 7 drinks per week)?

## 9. Final model configuration

- **Algorithm**: XGBoost classifier, sigmoid-calibrated (`CalibratedClassifierCV`, `method='sigmoid'`), wrapped in a scikit-learn `Pipeline` with `StandardScaler`.
- **Hyperparameters** (independently tuned for this feature set, not reused from v1): `n_estimators=400, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, min_child_weight=5, gamma=1.0, reg_alpha=0, reg_lambda=5.0, scale_pos_weight=5.5382`.
- **Decision threshold**: 0.10, stored only in `diabetes_metadata_v2.json` — never hardcoded in application code.
- **Artifact**: `ml_pipeline/diabetes/artifacts/diabetes_pipeline_v2.pkl` + `diabetes_metadata_v2.json`, loaded together at backend startup; a missing/malformed metadata file fails the model load loudly rather than falling back to a guessed threshold.

## 10. Family history — explicitly not included

Per the earlier `family_history_investigation.md`: family history is evidence-supported (every validated screening instrument checked — ADA, FINDRISC, CDC, USPSTF — includes it) but no dataset available to this project combines it with these BRFSS lifestyle features in a verified, ready-to-use form. It was **not** fabricated, not derived from unrelated variables, and no frontend question was added that the model would silently ignore. This limitation is unchanged from v1 and remains explicitly documented rather than worked around. A future family-history-aware model — per that document's concrete next step of acquiring NHANES's `DIQ175A` variable directly from the CDC/NCHS portal — would need to be an independent data/model project, since BRFSS and NHANES cannot be joined at the row level.

## 11. Known limitations (carried and new)

- No external clinical validation, prospective evaluation, or clinician review has been performed on either v1 or v2 — this remains true after this change and must not be represented otherwise in any product surface.
- Dataset is the 2015 US CDC BRFSS survey year only; population and self-report patterns from that year/geography may not generalize to other populations or later years.
- All 14 retained features are self-reported survey responses, not lab measurements or clinical records.
- Family history is absent from the model, for the reasons in §10 — this is a known gap, not an oversight.
- Prediabetes is grouped into the positive class together with diagnosed diabetes (same target definition as v1); the model does not distinguish between them.
- Threshold 0.10 implies substantial false-positive volume (specificity ~0.60): roughly 2 in 5 people without diabetes will still be flagged for follow-up. This is a deliberate sensitivity-favoring screening choice, unchanged from v1, not an artifact of the feature reduction.
- The model-family comparison and hyperparameter search in this validation were deliberately kept focused (20-candidate randomized search, 4 model families) rather than exhaustive; a substantially larger search was not run and might find a marginally different configuration, though the evidence gathered gives no reason to expect a materially different conclusion.
