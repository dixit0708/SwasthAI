# Heart Disease Risk — ML Pipeline

## Overview

Trains an XGBoost-based binary classifier to predict **HeartDiseaseRisk** from
the CDC 2022 BRFSS / Behavioral Risk Factor Surveillance System dataset.

### Composite Target Definition

```
HeartDiseaseRisk = 1  if  HadHeartAttack == "Yes"  OR  HadAngina == "Yes"
HeartDiseaseRisk = 0  otherwise
```

---

## Dataset

| Property | Value |
|---|---|
| Source | CDC BRFSS 2022 (heart_2022_no_nans.csv) |
| Raw rows | 246,022 |
| Columns | 40 |
| Positive rate | ~8.79% |
| Post-dedup rows | 244,355 |
| Train / Test split | 80 / 20 stratified |

---

## Features (24 total)

| # | Feature | Type | Encoding |
|---|---|---|---|
| 1 | Sex | Binary | Female=0, Male=1 |
| 2 | AgeCategory | Ordinal | 18-24→1 … 80+→13 |
| 3 | BMI | Numeric | as-is |
| 4 | GeneralHealth | Ordinal | Poor=1 … Excellent=5 |
| 5 | PhysicalHealthDays | Numeric | as-is (0–30) |
| 6 | MentalHealthDays | Numeric | as-is (0–30) |
| 7 | SleepHours | Numeric | as-is |
| 8 | PhysicalActivities | Binary | No=0, Yes=1 |
| 9 | HadStroke | Binary | No=0, Yes=1 |
| 10 | HadAsthma | Binary | No=0, Yes=1 |
| 11 | HadCOPD | Binary | No=0, Yes=1 |
| 12 | HadDepressiveDisorder | Binary | No=0, Yes=1 |
| 13 | HadKidneyDisease | Binary | No=0, Yes=1 |
| 14 | HadArthritis | Binary | No=0, Yes=1 |
| 15 | HadDiabetes | Binary | Yes=1, all else=0 |
| 16 | DifficultyWalking | Binary | No=0, Yes=1 |
| 17 | DifficultyConcentrating | Binary | No=0, Yes=1 |
| 18 | DifficultyErrands | Binary | No=0, Yes=1 |
| 19 | SmokerStatus | Ordinal | Never=0 Former=1 SomeDays=2 EveryDay=3 |
| 20 | AlcoholDrinkers | Binary | No=0, Yes=1 |
| 21 | ChestScan | Binary | No=0, Yes=1 |
| 22 | HighRiskLastYear | Binary | No=0, Yes=1 |
| 23 | RemovedTeeth | Ordinal | None=0 1-5=1 6+notAll=2 All=3 |
| 24 | LastCheckupTime | Ordinal | <1yr=0 1-2yr=1 2-5yr=2 5+yr=3 |

**Excluded from features (used only for target construction):**
- `HadHeartAttack`
- `HadAngina`

---

## Pipeline Structure

```
preprocessing.py  ->  data/processed/heart_train.csv
                       data/processed/heart_test.csv
                       data/processed/heart_dataset_stats.json

train.py          ->  artifacts/heart_pipeline.pkl
                       artifacts/heart_metadata.json
                       reports/family_comparison.json
                       reports/tuned_results.json
                       reports/calibration_check.json
                       reports/threshold_sweep.json
                       reports/test_evaluation.json
                       reports/calibration_in_the_large.json
                       backend/app/ai/models/heart_disease_model.pkl  (production copy)

inference_test.py ->  smoke test of the production model
```

---

## Training Methodology

Follows the same leakage-safe methodology as `ml_pipeline/diabetes/train_brfss_v2.py`:

1. **Model-family comparison** — Logistic Regression, Random Forest, XGBoost, HistGradientBoosting compared by 5-fold CV ROC-AUC before committing to XGBoost.
2. **Hyperparameter search** — RandomizedSearchCV (n_iter=20, cv=3) on the winning family.
3. **Calibration decision** — OOF Brier score comparison (raw vs sigmoid). Calibration applied only if improvement > 0.0005.
4. **Threshold sweep** — Sweep 0.05–0.50; choose highest threshold that keeps OOF recall ≥ 0.80 (screening-first rule).
5. **Final fit** — ONE fit on the full training set, ONE evaluation on the held-out test set.

---

## Running the Pipeline

```bash
# 1. Preprocess
cd ml_pipeline/heart
python preprocessing.py

# 2. Train
python train.py

# 3. Verify production model
python inference_test.py
```

---

## Limitations

- All features are self-reported CDC 2022 survey responses, not clinical lab measurements.
- The composite target combines two self-reported items (HadHeartAttack, HadAngina).
- Single survey year (2022), U.S. population only.
- Family history of heart disease is not available in this dataset.
- No independent external validation dataset.

---

## Medical Safety Notice

> **This model output is a risk assessment, NOT a medical diagnosis.**
> It must never be presented as a definitive diagnosis.
> Users should always be encouraged to consult a qualified healthcare professional.
