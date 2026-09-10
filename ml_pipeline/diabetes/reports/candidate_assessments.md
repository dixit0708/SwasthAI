# Candidate Assessments — Minimal / Balanced / Expanded

All three candidates are **nested** (Minimal ⊂ Balanced ⊂ Expanded) and drawn from `reports/feature_selection_analysis.md`'s Keep-rated features only. None includes `Income`, `Education`, `AnyHealthcare`, or `NoDocbcCost` (the poor-patient-fit socioeconomic/access items), regardless of their raw ML importance rank — see that report for why. `PhysActivity` is included in every candidate on clinical-evidence grounds (every validated screening instrument checked includes it) despite its near-zero importance in this specific BRFSS-trained model. None includes family history — see `reports/family_history_investigation.md` for why not.

Question wording below matches the already-shipped frontend implementation (`frontend/prediction-diabetes.html`) exactly, so no frontend copy needs inventing later if a candidate is adopted.

## Candidate A — Minimal (7 questions)

| Question (patient-facing) | Why it's here | Evidence | Model feature | Answer format | Directly measured / derived |
|---|---|---|---|---|---|
| "How do you identify your sex for this health assessment?" | Required for correct model input | N/A — structural | `Sex` | Female/Male toggle | Direct |
| "Which age range do you belong to?" | Core factor in every validated screening tool | ADA / FINDRISC / CDC / USPSTF; combined-rank 4 | `Age` | 13-band select | Direct |
| Height + Weight (→ BMI shown live) | Core factor in every validated screening tool | ADA / FINDRISC / CDC / USPSTF; combined-rank 3 | `BMI` | Two number inputs | **Derived** (BMI computed client-side from height/weight, same as today) |
| "In general, would you say your health is..." | Highest permutation-importance feature; self-rated health is an independently well-known general predictor | This model's evidence (combined-rank 1) | `GenHlth` | 5-point select | Direct |
| "Have you done any physical activity or exercise in the past 30 days, other than your regular job?" | Core factor in every validated screening tool, despite near-zero importance in this model | ADA / FINDRISC / CDC (clinical evidence overrides this model's own signal — see `feature_selection_analysis.md`) | `PhysActivity` | Yes/No toggle | Direct |
| "Have you ever been told by a doctor, nurse, or other health professional that you have high blood pressure?" | Highest gain-importance feature; core factor in every validated tool | Combined-rank 2; ADA / FINDRISC / CDC | `HighBP` | Yes/No toggle | Direct |
| "Have you ever been told that you have high cholesterol?" | Strong, consistent importance in this model | Combined-rank 5 | `HighChol` | Yes/No toggle | Direct |

**Limitations**: no family history; no lipid-check/access context; drops several moderate-signal comorbidity items (heart disease, stroke, difficulty walking) that Balanced restores. Intended as the "fastest possible" screen, not the most discriminating one — see empirical cost in `reports/model_comparison.md`.

## Candidate B — Balanced (11 questions)

Minimal's 7, plus:

| Question | Why it's here | Evidence | Model feature | Answer format |
|---|---|---|---|---|
| "Have you ever been told you had coronary heart disease or a heart attack?" | Recognized diabetes-associated comorbidity, easy to answer, moderate ML signal | Combined-rank 7 | `HeartDiseaseorAttack` | Yes/No toggle |
| "Do you have serious difficulty walking or climbing stairs?" | Functional-status marker, easy to answer | Combined-rank 10 | `DiffWalk` | Yes/No toggle |
| "Have you smoked at least 100 cigarettes in your entire life (about 5 packs)?" | Well-known general health risk factor, easy to answer | Combined-rank 18 (low in this model, but a standard general-health-history question) | `Smoker` | Yes/No toggle |
| "Are you a heavy drinker (adult men having more than 14 drinks per week, adult women having more than 7 drinks per week)?" | Modifiable lifestyle factor with a precisely-defined, unambiguous question | Combined-rank 8 | `HvyAlcoholConsump` | Yes/No toggle |

**Limitations**: same family-history gap; still excludes cholesterol-check/access context and the two day-count wellbeing questions (mental/physical health days), which carry a real recall burden for their marginal signal.

## Candidate C — Expanded (14 questions)

Balanced's 11, plus:

| Question | Why it's here | Evidence | Model feature | Answer format |
|---|---|---|---|---|
| "Have you had your cholesterol checked within the past 5 years?" | Decent gain-importance; a common, low-burden question | Combined-rank 6 | `CholCheck` | Yes/No toggle |
| "Have you ever been told you had a stroke?" | Recognized comorbidity, trivial to answer even though its own ML signal is low | Combined-rank 13 | `Stroke` | Yes/No toggle |
| "Do you eat fruit one or more times per day?" | Validated in FINDRISC specifically, despite near-zero signal in this model | FINDRISC; combined-rank 20 | `Fruits` | Yes/No toggle |

**Limitations**: still no family history. `Veggies` and the two day-count questions (`MentHlth`, `PhysHlth`) were deliberately left out even at this size — `Veggies` is highly redundant with `Fruits` (both near-zero, correlated dietary items; including one captures most of the qualitative signal without doubling the burden), and the day-count questions' answerability cost was judged not worth their marginal contribution at any candidate size based on the evidence table. If the empirical ablation results below show this judgment was wrong, that is exactly what the results are for — this is a candidate assessment, not a final decision.

## What determines which candidate (if any) should ship

Not question count alone. See `reports/model_comparison.md` for how each candidate's *actual* trained-and-tested performance compares to the 21-feature baseline and to the pure-importance-ranked ablation curve at the same feature counts, and `reports/final_recommendation.md` for the resulting decision.
