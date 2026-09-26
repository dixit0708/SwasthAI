# Liver Disease Risk Model — NHANES (No-Lab) Evaluation Report

**Model version:** liver-nhanes-v1
**Algorithm:** Logistic Regression (best of 3 candidates by CV ROC-AUC)
**Dataset:** NHANES 2013-2014 / 2015-2016 / 2017-2018 pooled, 12,215 adult rows
**Trained at:** see `artifacts/liver_metadata_nhanes_v1.json`

## Why this model exists

`liver-ilpd-v1` (the original model, kept on disk untouched as the baseline)
was trained on the Indian Liver Patient Dataset, whose 9 features are the LFT
panel itself (bilirubin, ALP, ALT, AST, proteins, albumin, A/G ratio). A user
can only fill that form out if they already have lab results in hand — at
which point a clinician reading the same panel already tells them whether
they have liver disease. The model added no triage value; it never earns its
keep before a blood draw, only after one, when it's too late to matter.

`liver-nhanes-v1` fixes this by using **zero lab values**. Every one of its
9 features is something a person can answer from memory or a routine
physical exam:

| Feature | Type | Source |
|---|---|---|
| age_years | numeric | self-report |
| sex | categorical | self-report |
| race_ethnicity | categorical | self-report |
| bmi | numeric | height/weight (routine exam) |
| waist_circumference_cm | numeric | tape measure (routine exam) |
| general_health | categorical (5-point) | self-report |
| heavy_alcohol_use | categorical (Yes/No) | self-report |
| smoker | categorical (Yes/No) | self-report |
| diabetes_status | categorical (Yes/No/Borderline) | self-report |
| hypertension | categorical (Yes/No) | self-report |
| physical_activity | categorical (Yes/No) | self-report |

This mirrors the diabetes model's own design exactly (BRFSS, self-report,
no labs) — see `ml_pipeline/diabetes/reports/v2_final_recommendation.md`.

## Candidate Model Comparison (5-fold CV on training set)

| Model | ROC-AUC | F1 | Recall |
|---|---|---|---|
| Logistic Regression | 0.7299 | 0.1652 | 0.6390 |
| Random Forest | 0.7130 | 0.1211 | 0.0830 |
| XGBoost | 0.6825 | 0.1444 | 0.1494 |

**Selected:** Logistic Regression (best CV ROC-AUC).

## Final Test-Set Performance

| Metric | Value |
|---|---|
| Accuracy | 0.5608 |
| Precision | 0.0854 |
| Recall | 0.8099 |
| F1-score | 0.1545 |
| ROC-AUC | 0.7423 |
| Decision Threshold | 0.41 |

Confusion Matrix (TN/FP/FN/TP): [1272, 1050, 23, 98]

## Honest limitations — read before using this in a product

1. **Lower ceiling than a lab-based model, by design, not by accident.**
   Published NHANES studies restricting the target to a single, clean
   etiology (fatty liver only, confirmed by FibroScan/CAP, excluding heavy
   drinkers and viral hepatitis) report AUC 0.78–0.87 without lab features.
   This model's target (`MCQ160L`, "any kind of liver condition") is
   deliberately broader — it lumps fatty liver, viral hepatitis, cirrhosis,
   and other causes together, because that's the only liver-disease question
   NHANES's self-report module asks. A broader, more heterogeneous target is
   intrinsically harder to predict from a handful of shared risk factors,
   which is the main reason this model's AUC (0.74) sits below that
   published range rather than a fixable modeling gap.

2. **Self-reported target, not lab-confirmed.** `MCQ160L` is "has a doctor
   ever told you..." — subject to the same recall/reporting biases as the
   diabetes model's BRFSS target, and explicitly accepted as a trade-off for
   a much larger, non-invasive-to-collect sample (12,215 rows across 3
   cycles vs. 549 in ILPD).

3. **Precision is low (8.5%) at the chosen threshold.** At 0.41, roughly 1
   in 12 people flagged "elevated risk" actually have a reported liver
   condition; 1050 of 1322 true negatives in the test set are flagged. This
   is a deliberate sensitivity-first choice (recall 0.81, i.e. ~4 in 5 true
   cases caught) appropriate for a screening tool whose job is "should you
   go get an LFT," not a diagnosis — same positioning, same trade-off shape,
   as the diabetes model's own threshold choice (diabetes: recall 0.86 /
   specificity 0.60 at its chosen threshold).

4. **No external clinical validation.** Same caveat as the diabetes model:
   no prospective evaluation or clinician review has been performed.

5. **US population only.** NHANES samples the US non-institutionalized
   population; self-report base rates and risk-factor associations may not
   generalize to other populations.

## What this model is and isn't

- **Is:** a "should I get my liver checked" pre-screening flag, using only
  information a user already knows or can get from a routine physical.
- **Isn't:** a replacement for an LFT panel or a diagnosis. A user with an
  elevated-risk result should be told to get an LFT — the same message the
  diabetes model gives for an elevated glucose-risk result.
