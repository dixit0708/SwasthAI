# Liver Disease Risk Model — NHANES (No-Lab) Evaluation Report

**Model version:** liver-nhanes-v1
**Algorithm:** Logistic Regression (best of 3 candidates by CV ROC-AUC)
**Dataset:** NHANES 2013-2014 / 2015-2016 / 2017-2018 pooled, 12,147 adult rows
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

## Candidate Model Comparison (5-fold CV on train+val, test set untouched)

| Model | ROC-AUC | F1 | Recall |
|---|---|---|---|
| Logistic Regression | 0.7302 | 0.1646 | 0.6444 |
| Random Forest | 0.7048 | 0.1107 | 0.0754 |
| XGBoost | 0.6609 | 0.1322 | 0.1423 |

**Selected:** Logistic Regression (best CV ROC-AUC).

## Final Test-Set Performance

**Split methodology (revised):** 60/20/20 train/validation/test, stratified.
The decision threshold below was chosen by sweeping recall on the
**validation** split only (fit on train, evaluated on val) — the test set
plays no part in that choice, then the final pipeline is refit on
train+val and the test set is touched exactly once, for the numbers
below. The original version of this evaluation swept the threshold
directly against the test set it then reported metrics on — a real, if
narrow, form of the test-data-influencing-model-selection leak AGENTS.md
Section 8 warns against (one scalar threshold, not full retraining, so the
practical distortion was small — compare to the numbers this replaced:
accuracy 0.561, precision 0.085, recall 0.810, ROC-AUC 0.742, threshold
0.41 — close to, not dramatically different from, the corrected numbers
below, which is itself evidence the original leak wasn't hiding a large
effect). Fixed anyway, because "the leak turned out small this time" isn't
a reason to leave it in.

| Metric | Value |
|---|---|
| Accuracy | 0.5243 |
| Precision | 0.0823 |
| Recall | 0.8500 |
| F1-score | 0.1500 |
| ROC-AUC | 0.7480 |
| Decision Threshold | 0.39 |

Confusion Matrix (TN/FP/FN/TP): [1172, 1138, 18, 102]

## Investigated and rejected: two candidate feature additions

While reviewing this model, two more lab-free NHANES fields already
present in the raw downloaded files (no new data needed) were tested as
candidate additions, since they're plausible NAFLD/metabolic-syndrome risk
factors not yet captured: **`high_cholesterol`** (self-reported,
doctor-told — directly analogous to the existing diabetes/hypertension
fields) and **`smoking_status`** (a 3-level Never/Former/Current
refinement of the existing binary "ever smoked" flag). Full methodology
and numbers: `reports/feature_experiment.md`.

**Neither improved the model.** All four variants (baseline, +cholesterol,
+smoking refinement, both) landed within 0.0009-0.0010 ROC-AUC of each
other on 5-fold CV — well inside the ±0.013-0.015 fold-to-fold standard
deviation, i.e. noise, not signal. A hyperparameter search over Logistic
Regression's regularization strength and penalty type found the same
thing: the best configuration found (C=0.1, L1) beat the production
default (C=1.0, L2) by 0.001 ROC-AUC, again noise-level. Per AGENTS.md
Section 9 ("never fabricate or artificially improve metrics"), neither is
adopted — a change that doesn't move the needle isn't worth the extra
question it would add to the user-facing form. The two new columns remain
in `data/processed/nhanes_liver_pooled.csv` (unused by the production
model) as a record of what was tried, so this doesn't need re-investigating
from scratch later.

**What this confirms, not just for this attempt:** the model's ~0.74-0.75
AUC ceiling looks like a real property of "predict a broad, self-reported,
multi-etiology target from ~11 shared metabolic/demographic risk factors,"
not a fixable modeling gap. The honest path to a materially better number
is a different lever than this file's `class_weight`/`C`/feature-list
knobs — either a narrower, more homogeneous target (see limitation #1
below) or genuinely new information (a signal not already correlated with
age/BMI/waist/diabetes/hypertension/alcohol), not more tuning of the same
lever.

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
   which is the main reason this model's AUC (0.75) sits below that
   published range rather than a fixable modeling gap. Confirmed, not just
   assumed: neither adding plausible new lab-free features nor tuning
   hyperparameters moved this number beyond noise — see "Investigated and
   rejected" above.

2. **Self-reported target, not lab-confirmed.** `MCQ160L` is "has a doctor
   ever told you..." — subject to the same recall/reporting biases as the
   diabetes model's BRFSS target, and explicitly accepted as a trade-off for
   a much larger, non-invasive-to-collect sample (12,147 rows across 3
   cycles vs. 549 in ILPD).

3. **Precision is low (8.2%) at the chosen threshold, and the flagging rate
   is high.** At 0.39, roughly 1 in 12 people flagged "elevated risk"
   actually have a reported liver condition; 1138 of 2310 true negatives in
   the test set are flagged (47%, i.e. close to half of everyone without
   the condition still sees an "elevated" result). This is a deliberate
   sensitivity-first choice (recall 0.85, i.e. ~17 in 20 true cases caught)
   appropriate for a screening tool whose job is "should you go get an
   LFT," not a diagnosis — same positioning, same trade-off shape, as the
   diabetes model's own threshold choice (diabetes: recall 0.86 /
   specificity 0.60 at its chosen threshold). **Worth a product decision,
   not just a modeling one:** a screening tool that flags "elevated" for
   nearly half of all users may cause alarm fatigue even though the
   underlying trade-off is defensible — if that's a concern, the fix is
   choosing a stricter recall target (e.g. 65-70% instead of 80%), not a
   different model; ask before changing it, since it directly trades away
   catching some true cases.

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
