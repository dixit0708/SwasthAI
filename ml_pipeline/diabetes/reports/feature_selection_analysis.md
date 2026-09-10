# Feature Selection Analysis

Two independent forms of evidence are combined here, deliberately kept separate: (1) this model's own ML importance signal (exploratory only — never causal, never clinical guidance), and (2) each feature's fitness as a *question a patient can and should be asked directly*. A feature can score high on one axis and low on the other, and several do — that divergence is exactly what this analysis is for, not something to paper over.

## Question Quality Table

Combined-rank = average of tree-gain rank and permutation-importance rank (both from `reports/feature_importance.json`, the already-audited baseline model; 1 = most important of 21).

| Feature | Combined ML rank | Predictive contribution | User answerability | Patient relevance | Keep/Remove/Investigate | Reason |
|---|--:|---|---|---|---|---|
| GenHlth | 1 | Highest (permutation) / high (gain) | High — one familiar "how is your health" question | High — self-rated health is itself a well-known general predictor of many outcomes, not a diabetes-specific artifact | **Keep** | Strong on every axis |
| HighBP | 2 | Highest (gain) / high (permutation) | High — most adults know if they've been told this | High — universally included in every validated screening tool checked (ADA, FINDRISC, CDC) | **Keep** | Strong on every axis |
| BMI | 3 | High (both methods) | Medium — needs height+weight, not a single yes/no, but this project already computes it live from those two numbers | High — in every validated instrument | **Keep** | Strong; already implemented as a guided mini-interaction |
| Age | 4 | High (both methods) | High — but must stay a coarse band (as already implemented), never raw years | High — in every validated instrument | **Keep** | Strong on every axis |
| HighChol | 5 | High (both methods) | High | Medium — a real, common risk marker, though slightly less universal across the four screening tools than BP/BMI/age | **Keep** | Strong ML + reasonable clinical fit |
| CholCheck | 6 | Medium (gain) / low (permutation) | Medium — a healthcare-access/process question, not a risk factor itself | Low-Medium — measures access to care more than diabetes risk directly | **Investigate** | Divergence: decent gain-importance, weak permutation-importance, ambiguous clinical framing (is "have you had it checked" really a *risk* question, or an access question?) |
| HeartDiseaseorAttack | 7 | Medium | High — a serious, memorable diagnosis people know | High — a recognized comorbidity/risk cluster with diabetes | **Keep** | Solid on every axis, moderate ML contribution |
| HvyAlcoholConsump | 8 | Medium (gain) / low-medium (permutation) | Medium — the precise "14/7 drinks per week" definition is already spelled out in the current questionnaire but is cognitively demanding | Medium — a real modifiable-lifestyle factor, but not in the four validated instruments checked | **Investigate** | Reasonable ML signal, but the answerability burden is real and it's not clinically core to the major screening scores |
| Sex | 9 | Low-medium | High — one tap | Medium — used for model calibration but not a "risk factor" a patient reasons about | **Keep** | Needed for the model to work correctly; low burden |
| DiffWalk | 10 | Low-medium | High | Medium — a functional-status marker correlated with several conditions, not diabetes-specific | **Keep** | Easy to answer, non-trivial signal |
| Income | 11 | Medium (by rank, driven mostly by gain) | Low — sensitive, and many people are uncomfortable disclosing it in a health app | **Poor** | **Remove** | This is exactly the socioeconomic/access category flagged in the task brief: decent raw ML signal, poor product fit. The ablation study (below) measures the actual cost of removing it rather than asserting it |
| MentHlth | 12 | Low-medium | Medium — a 30-day recall count is more cognitively demanding than a yes/no | Medium — general wellbeing, not diabetes-specific | **Investigate** | Marginal ML value for a real answerability cost |
| Stroke | 13 | Low | High | Medium | **Investigate** | Low marginal ML value; keep only if it doesn't cost sensitivity in the ablation |
| PhysHlth | 14 | Low | Medium — same recall burden as MentHlth | Medium | **Investigate** | Same profile as MentHlth |
| Education | 15 | Low | Low — sensitive/socioeconomic | **Poor** | **Remove** | Same category as Income |
| AnyHealthcare | 16 | Low | Low-Medium — an access question, not a risk factor | **Poor** | **Remove** | Access/socioeconomic proxy, not a risk factor a patient would expect in a *risk* questionnaire |
| Veggies | 17 | Very low | High — simple yes/no | Medium — validated in FINDRISC specifically | **Investigate** | Clinically legitimate in FINDRISC, but contributes almost nothing in this model/dataset (see divergence note below) |
| Smoker | 18 | Very low | High | Medium — well-known general health risk factor | **Investigate** | Low ML value here despite plausible clinical relevance |
| PhysActivity | 19 | Very low (in *this* model) | High | High — in every validated instrument checked | **Keep anyway, flagged** | Rare case where established clinical evidence should override this model's near-zero importance — see note below |
| Fruits | 20 | Very low | High | Medium — validated in FINDRISC | **Investigate** | Same profile as Veggies |
| NoDocbcCost | 21 | Lowest | Low-Medium — access question | **Poor** | **Remove** | Same category as Income/Education/AnyHealthcare |
| *Family history* | *not in model* | *not in model* | High | **Highest** (in every validated instrument checked) | **Missing but important** | See `reports/family_history_investigation.md` — no valid dataset/model strategy currently supports adding it |

### A deliberate divergence worth stating plainly

`PhysActivity`, `Fruits`, and `Veggies` are near-zero importance in *this specific BRFSS-trained XGBoost model*, yet all three are core, validated items in FINDRISC and/or the ADA/CDC tools. Two explanations are both plausible and neither can be confirmed from this data alone: (a) BRFSS's blunt yes/no framing of these questions is a much weaker instrument than the more detailed 30-min/day or frequency-graded questions in the validated scores, or (b) their signal is genuinely redundant with `GenHlth`/`BMI`/`HighBP` in a model that already has those. Either way, **this model's importance ranking is not treated as evidence against these factors' real-world validity** — that would be presenting an artifact of one BRFSS-trained classifier as if it overturned peer-reviewed screening research, which the task explicitly warns against. `PhysActivity` in particular is kept in every candidate assessment below on clinical-evidence grounds, in spite of its near-zero ML contribution here.

## Ablation Results

See `reports/model_comparison.md` for the full experimental comparison (importance-ranked reduced sets at 15/12/10/8/6 features, and the three patient-facing candidates below), all evaluated with the same leakage-safe train→CV→calibrate→threshold→test methodology as the baseline.
