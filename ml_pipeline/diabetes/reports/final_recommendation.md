# Final Recommendation — Diabetes Assessment Redesign

This synthesizes `baseline_comparison.md`, `feature_selection_analysis.md`, `family_history_investigation.md`, `candidate_assessments.md`, and `model_comparison.md`. It is a recommendation for the next implementation phase — **nothing described here has been implemented in the backend, frontend, or production artifact yet** (see the implementation plan at the end, which is explicitly a plan, not a change log).

## 1. Which questions should the final diabetes assessment ask?

The **Expanded (14-question)** set, per `candidate_assessments.md`:

Sex, age range, height+weight (→BMI), self-rated general health, physical activity in the past 30 days, high blood pressure history, high cholesterol history, cholesterol check in the past 5 years, coronary heart disease/heart attack history, difficulty walking/climbing stairs, smoking history, heavy alcohol consumption, stroke history, and fruit consumption.

## 2. Which existing questions should be removed?

`Income`, `Education`, `AnyHealthcare`, `NoDocbcCost` (poor patient-facing fit — sensitive/socioeconomic access proxies, per `feature_selection_analysis.md`), and `MentHlth`, `PhysHlth`, `Veggies` (real but small marginal value not worth their answerability cost at this size — `Veggies` in particular is largely redundant with the retained `Fruits`).

## 3. Should family history be included?

**Not yet.** It is evidence-supported (every validated screening instrument checked — ADA, FINDRISC, CDC, USPSTF — includes it) but no dataset available to this project combines it with comparable lifestyle features in a verified, ready-to-use form. See #4.

## 4. If yes, what valid data/model strategy supports it?

None currently. `family_history_investigation.md`'s concrete next step: acquire NHANES (`DIQ175A` variable) directly from the CDC/NCHS portal and train an **independent** model on it — not a bolt-on to the BRFSS model, since the two surveys cannot be joined at the row level. A specific Kaggle dataset (`rabieelkharoua/diabetes-health-dataset-analysis`) claims a family-history field but shows signs consistent with synthetic/fabricated data and was **not** used or recommended without independent verification.

## 5. Which model should be used?

**XGBoost, sigmoid-calibrated** — the same architecture as the current baseline. The ablation study found no evidence that a different algorithm or hyperparameter configuration is needed; the entire discrimination cost of feature reduction tracks the feature set, not the model family. (Hyperparameters were held constant across candidates by design — see the methodology note in `model_comparison.md` — so this recommendation does not claim the *exact* baseline hyperparameters are optimal for the reduced feature set, only that there's no evidence a different architecture is needed.)

## 6. What is the final feature set?

14 features: `Sex, Age, BMI, GenHlth, PhysActivity, HighBP, HighChol, CholCheck, HeartDiseaseorAttack, DiffWalk, Smoker, HvyAlcoholConsump, Stroke, Fruits`.

## 7. What is the final threshold?

**0.10**, on the calibrated probability scale — identical to the baseline, and independently re-derived (not assumed) via the same OOF-calibrated-probability threshold sweep, using a rule applied uniformly across every candidate in this study.

## 8. How does it compare with the current 21-feature baseline?

| | Baseline (21) | Recommended (14) | Difference |
|---|--:|--:|--:|
| ROC-AUC | 0.8199 | 0.8180 | -0.0019 |
| PR-AUC | 0.4477 | 0.4447 | -0.0030 |
| Recall/Sensitivity | 0.8678 | 0.8631 | -0.0047 |
| Specificity | 0.6060 | 0.6042 | -0.0018 |
| Brier (test) | 0.10499 | 0.10530 | +0.00031 |
| Questions asked | 21 | 14 | -7 |
| Sensitive/access questions | 4 | 0 | -4 |

A 33% shorter questionnaire, with every socioeconomic/access question removed, for a discrimination cost smaller than the model's own fold-to-fold variance (baseline CV ROC-AUC std ±0.001; this gap is 0.0019).

## 9. What are the limitations?

- All limitations already on record for the baseline still apply unchanged: self-reported survey data (not lab measurements), 2015 US survey year only, prediabetes excluded from the positive class, no external validation dataset.
- The 14-feature set was evaluated with the baseline's hyperparameters held constant, not independently re-tuned — a full re-tuning might close some or all of the 0.0019 ROC-AUC gap, or might not; this was not tested.
- Family history remains absent. The recommended assessment is a genuine improvement in patient-facing quality, not a claim of covering every clinically-relevant factor.
- The "patient-facing fit" classification in `feature_selection_analysis.md` (which items are "sensitive," "high burden," etc.) reflects this project's own judgment applied to the evidence, not a separately validated user-research finding — no user testing of question comprehension or completion rates was conducted.
- Threshold 0.10 implies substantial false-positive volume (specificity ~0.60): roughly 2 in 5 people without diabetes will still be flagged. This was already true of the baseline and is unchanged by this redesign; it is a deliberate screening-sensitivity choice, not newly introduced here.

## 10. What still requires clinical validation?

Everything about this system, both before and after this redesign: it has not undergone external clinical validation, prospective evaluation, or review by a qualified clinician, and must not be presented as diagnostic or clinically validated in any product surface. This redesign changes which questions are asked and how many; it does not change that fundamental status.

---

## Implementation Plan (not executed in this task)

```text
Dataset
  -> No new dataset. Same brfss_train.csv / brfss_test.csv, column-subsetted
     to the 14-feature list. No re-preprocessing needed (already leakage-safe).
Preprocessing
  -> Unchanged (StandardScaler only; still no missing values in the retained columns).
Training
  -> New train script (e.g. train_brfss_14feature.py, adapted from train_brfss.py)
     using the locked 14-feature list and the same XGBoost hyperparameter
     search process used for the baseline (re-run RandomizedSearchCV on this
     feature set specifically, rather than reusing the 21-feature tuning
     unchanged, to give the new model its own honest tuning pass).
Calibration
  -> Same sigmoid-calibration methodology as the baseline; re-verify the
     calibration decision on this feature set's own OOF probabilities
     rather than assuming the ablation study's provisional result.
Threshold
  -> Re-sweep on this feature set's own calibrated OOF probabilities using
     the same recall>=0.85 rule; confirm 0.10 still holds under full tuning
     before locking it.
Artifact + metadata
  -> New artifact (e.g. artifacts/diabetes_pipeline_v2.pkl +
     metadata_v2.json) alongside the existing baseline artifact — the
     baseline is never overwritten, so it remains available for comparison
     or rollback.
Backend request schema
  -> New DiabetesPredictionInput fields matching the 14-feature list;
     this is a breaking API contract change and needs its own explicit
     sign-off pass, same as the original 21-feature integration did.
Prediction service
  -> Update the feature-mapping dict to the 14-feature list; feature order
     still sourced from metadata, never hardcoded.
Frontend questionnaire
  -> Remove the Income/Education/AnyHealthcare/NoDocbcCost/MentHlth/PhysHlth/
     Veggies questions and their sections from the existing wizard; the
     bounded step-state-machine architecture from the recent redesign
     needs no structural change, only fewer fields per section.
Review screen
  -> Fewer rows per section; no structural change needed.
Result screen
  -> No change — same risk_level/is_elevated/message/disclaimer contract.
Regression tests
  -> Update tests/e2e/diabetes.spec.js's field list and FIELD_CONFIG-equivalent
     mapping to the 14 fields; the existing 76-test suite's structure
     (boundary-attack tests, error-path tests, accessibility tests) carries
     over unchanged in spirit.
```

**Do not execute this plan without explicit confirmation** — it changes the production API contract and the live frontend, both called out as requiring separate sign-off in the task's own rules.
