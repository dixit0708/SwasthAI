# Family History Investigation

**Bottom line up front: family history of diabetes is a well-established, clinically validated risk factor, but no dataset already in this repository or independently verified during this investigation combines it with BRFSS-style lifestyle features in a form ready to train on. It is not added to the model in this task. This document records the evidence and the concrete next data-acquisition step.**

## Why this matters

The current 21-feature BRFSS model has no family-history feature, because the CDC BRFSS 2015 core survey module our dataset is drawn from did not ask about it. That is a genuine gap: every major validated diabetes screening instrument checked below treats family history as a core factor.

## Established screening instruments checked (verified via web search, not from memory alone)

| Instrument | Family history included? | Other core factors | Source |
|---|---|---|---|
| ADA Diabetes Risk Test (7-item score, 0-11 points) | Yes — "any history of diabetes in mother, father, sister, or brother" is one of the 7 scored items | Age, sex, race, BMI (weight/height), gestational diabetes history, hypertension history, physical activity | [ADA Risk Calculator review, MDCalc](https://mdcalc.scholasticahq.com/article/159088-updated-review-of-the-american-diabetes-association-ada-risk-calculator) |
| FINDRISC (Finnish Diabetes Risk Score, 8-item, 0-26 points) | Yes — one of 8 scored items | Age, BMI, waist circumference, antihypertensive treatment history, history of high blood glucose, fruit/vegetable consumption, physical activity ≥30min/day | [FINDRISC scoring, ResearchGate](https://www.researchgate.net/figure/The-Finnish-diabetes-risk-score-FINDRISC_fig1_44640424) |
| CDC Prediabetes Risk Test (1-minute, 0-10 points) | Yes — "Do you have a mother, father, sister, or brother with diabetes?" scores 1 point | Age, sex, BMI, gestational diabetes history (women), physical activity <3x/week | [How Your Test is Scored, CDC](https://www.cdc.gov/diabetes/widgets/risktest/how-your-test-is-scored.html) |
| USPSTF 2021 screening recommendation (B grade, ages 35-70 + overweight/obesity) | Cited as a supporting risk factor alongside gestational diabetes and PCOS history, though the primary screening trigger is age + BMI | Age, BMI/overweight status | [USPSTF final recommendation](https://www.uspreventiveservicestaskforce.org/uspstf/recommendation/screening-for-prediabetes-and-type-2-diabetes) |

**All four** validated instruments checked include family history. This is strong, convergent evidence that it belongs in a well-designed patient-facing diabetes screening questionnaire — but validated-instrument inclusion is a *clinical evidence* question, separate from whether *this project's specific model* can currently use it, which depends entirely on whether a suitable dataset exists.

## Does BRFSS itself ever ask this question?

Yes, partially. BRFSS runs state-optional modules in addition to its core questionnaire, and a family-history-of-diabetes question ("Do you have a parent, brother, or sister related by blood, who has or has had diabetes?") has been fielded as an optional module in at least some years/states — for example, the 2003 Rhode Island BRFSS ([Preventing Chronic Disease, CDC](https://pmc.ncbi.nlm.nih.gov/articles/PMC2901584/)). It is **not** part of the 2015 core module the current dataset (and the Kaggle mirror it came from) is built on, which is why it's absent here. This is the single most promising lead for a *same-methodology* extension: a BRFSS year/state combination where both the diabetes and family-history modules were fielded would let a future model stay within the same survey instrument and population type, rather than merging two unrelated studies.

## Datasets evaluated as potential sources

### 1. NHANES (National Health and Nutrition Examination Survey)
- **Family history present?** Yes — variable `DIQ175A` ("family history of diabetes") in the Diabetes questionnaire section (`DIQ`), alongside `DIQ010` (diagnosed diabetes status) and other diabetes-management variables. Confirmed via CDC's own NHANES documentation (e.g. [2001-2002 DIQ_B codebook](https://wwwn.cdc.gov/Nchs/Nhanes/2001-2002/DIQ_B.htm), with equivalent variables present through the most recent published cycles).
- **Publicly/legitimately usable?** Yes — a US government (CDC/NCHS) survey, freely downloadable in SAS/XPT format from the official NHANES portal, extensively used in peer-reviewed diabetes-risk research (e.g. [Predicting youth diabetes risk using NHANES data and machine learning](https://pmc.ncbi.nlm.nih.gov/articles/PMC8160335/)).
- **Population match?** Reasonable — a nationally representative US sample, similar in spirit to BRFSS's state-representative sampling, but a *different survey instrument entirely* (different questions, different coding conventions, different sampling weights). It cannot be joined row-for-row with BRFSS; it would train an **independent model**, not extend the current one.
- **Sufficient scale?** Yes, NHANES cycles typically run several thousand to tens of thousands of respondents per 2-year cycle (much smaller than BRFSS's 250k+, but adequate for a diabetes-risk model, and NHANES's strength is combining survey answers with actual clinical/lab measurements when needed).
- **Known limitations**: 2-year cycles mean smaller per-cycle N than BRFSS; the questionnaire structure and diabetes definition differ from BRFSS's, so a NHANES-trained model's outputs would not be directly comparable to the current model's calibrated probabilities.
- **Verdict**: legitimate, authoritative, not currently downloaded or used in this repo. **Recommended as the primary next data-acquisition step if family history becomes a product priority** — as a new, separately-trained and separately-evaluated model, not a bolt-on to the current artifact.

### 2. Kaggle `rabieelkharoua/diabetes-health-dataset-analysis`
- **Family history present?** Reportedly yes — a `FamilyHistoryDiabetes` binary field, per the dataset's own Kaggle listing.
- **Authenticity concern (important)**: the dataset's own description states it is "original and has never been shared before," and its `PatientID` field is described as ranging narrowly from 6000 to 7878 (~1,878 rows) — phrasing and structure consistent with a number of recent Kaggle uploads that are **algorithmically generated/synthetic** rather than real collected patient data, a known pattern this project's own AGENTS.md-driven data-integrity rules explicitly guard against ("do not fabricate data"). This was **not independently downloaded, opened, or verified** in this task — the claim comes only from search-indexed summaries of the Kaggle listing page, not from inspecting the actual file.
- **Verdict**: **not recommended for use without independent, hands-on authenticity and provenance verification first** (download the file, inspect for synthetic-generation signatures — e.g. unnaturally clean distributions, deterministic ID patterns, lack of any real-world data quality issues — and confirm the author's actual data source before treating any row as a real patient). Training a production health-screening feature on a possibly-fabricated dataset would be a serious integrity failure; flagging this risk explicitly is the correct action here, not quietly using it.

### 3. Pima Indians Diabetes Database (`DiabetesPedigreeFunction`)
- **Family history present?** Yes, as a derived quantitative score — `DiabetesPedigreeFunction` "estimates the genetic likelihood of diabetes based on family history, considering how many relatives had diabetes and their age at diagnosis" ([Pima dataset documentation](https://tap.health/pima-indians-diabetes-dataset/)).
- **Already in this repo**: yes — this is the pre-existing (never-trained) Pima pipeline (`ml_pipeline/diabetes/preprocessing.py`, `train.py`, `data/raw/pima-diabetes-raw.csv`), preserved untouched per this task's rules.
- **Can it complement BRFSS?** No, not by merging. Pima's 8 features (`Pregnancies, Glucose, BloodPressure, SkinThickness, Insulin, BMI, DiabetesPedigreeFunction, Age`) are clinical lab measurements from a population that is exclusively **female patients of Pima Indian heritage, age 21+** — a completely different study, population, and feature schema from BRFSS's general-adult lifestyle survey. There is no valid way to add a `DiabetesPedigreeFunction`-like column to BRFSS rows; the two datasets describe different people measured with different instruments.

## Answering the ten evaluation questions from the task brief

1. **Does the dataset contain family history?** NHANES: yes, documented. Kaggle candidate: claimed, unverified. Pima: yes, as a derived score, but unusable here.
2. **Enough additional relevant features?** NHANES: yes (extensive health/demographic/lab data). Kaggle candidate: unknown pending verification.
3. **Publicly and legitimately usable?** NHANES: yes, unambiguously. Kaggle candidate: license claims CC BY 4.0 but authenticity of the underlying data is in question.
4. **Population appropriate?** NHANES: yes, US general population. Pima: no (narrow, non-general population).
5. **Target definition clear?** NHANES: yes (`DIQ010`, an established diabetes-status question). Kaggle candidate: unverified.
6. **Sufficiently large?** NHANES: likely adequate per cycle, smaller than BRFSS. Kaggle candidate: reportedly only ~1,878 rows — small.
7. **Known limitations?** See above per source.
8. **Dataset/population mismatch risk?** High for merging BRFSS with anything else at the row level — none of these can be joined to BRFSS; any of them would require an independently trained and independently evaluated model.
9. **Can it realistically replace or complement the BRFSS model?** Not as a bolt-on. It could **replace** it for a future iteration if a full retraining + revalidation effort is undertaken on NHANES (or another verified source), but that is new-project-scale work, not a feature addition.
10. **Can it support a defensible patient-facing questionnaire?** A family-history question itself is clearly defensible (per the four validated instruments above) — but presenting a "family history" question to users while the *deployed model ignores it* would misrepresent the product, which is exactly what this task's rules prohibit.

## Recommendation

**Do not add a `family_history` field to the current questionnaire or model now.** No verified, ready-to-use dataset combining it with comparable lifestyle features was found in this investigation. The concrete next step, if this is prioritized:

1. Acquire NHANES (most recent available cycle(s)) directly from the official CDC/NCHS portal, focusing on the `DIQ` (diabetes) and demographic/examination sections including `DIQ175A`.
2. Treat it as a **new, independent model project** — its own audit, its own preprocessing, its own leakage checks, its own calibration and threshold work — not an extension of `diabetes-brfss-v1`.
3. Independently verify the Kaggle `rabieelkharoua` dataset's authenticity before ever considering it, given the synthetic-data red flags identified above; do not use it on the strength of a search-result summary alone.
4. As a lower-priority parallel option, check whether a specific BRFSS survey year/state combination fielded both the diabetes core module and the family-history optional module simultaneously — this would be the most methodologically consistent path (same instrument family as the current model) if it exists in a usable, sufficiently large combination.

Until one of these is executed and its own evaluation completed, the honest, non-fabricated position is: **family history is evidence-supported but not currently modelable in this system.**
