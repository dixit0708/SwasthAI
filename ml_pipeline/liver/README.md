# Liver Disease Risk Model

Structured-data risk-assessment model for the SwasthAI "Liver Disease Risk" feature (`frontend/prediction-liver.html`).

## Two model versions exist in this directory

1. **`liver-nhanes-v1` (production, `build_nhanes_dataset.py` / `train_nhanes.py`)** — a lab-free screening model trained on pooled NHANES 2013-2018 survey/exam data. **This is the live model** (`artifacts/liver_pipeline_nhanes_v1.pkl` + `artifacts/liver_metadata_nhanes_v1.json`). See "NHANES pipeline" below.
2. **`liver-ilpd-v1` (retired, `train.py`)** — the original model, trained on the Indian Liver Patient Dataset. **Kept on disk untouched as the historical baseline, no longer loaded by the backend.** See "Why it was retired" below.

---

## Why `liver-ilpd-v1` was retired

Its 9 input features (`total_bilirubin_mg_dl`, `direct_bilirubin_mg_dl`, `alkaline_phosphatase_u_l`, `alanine_aminotransferase_u_l`, `aspartate_aminotransferase_u_l`, `total_proteins_g_dl`, `albumin_g_dl`, `albumin_globulin_ratio`, plus age/gender) are literally the values on a Liver Function Test (LFT) panel. A user can only fill that form out if they already have lab results in hand — at which point a clinician reading the same panel already gives them the real answer. The model never adds triage value: it can only run *after* the exact test it would otherwise recommend. This is inconsistent with `ml_pipeline/diabetes`'s own design (BRFSS, fully self-reported, no lab values), which exists specifically to work as a *pre-lab* screening tool.

## NHANES pipeline

### Dataset

NHANES (National Health and Nutrition Examination Survey) 2013-2014 / 2015-2016 / 2017-2018, pooled — the three consecutive cycles in which `MCQ160L` ("has a doctor ever told you that you had any kind of liver condition?") was fielded. 12,215 adult (20+) rows after merging `DEMO` + `BMX` + `ALQ` + `SMQ` + `DIQ` + `BPQ` + `PAQ` + `HUQ` + `MCQ` on `SEQN` within each cycle and dropping ambiguous (Refused/Don't know/missing) answers. Raw `.XPT` files are not committed (see `data/nhanes_raw/` — download from `https://wwwn.cdc.gov/nchs/Data/Nhanes/Public/{year}/DataFiles/{FILE}.XPT`, e.g. `DEMO_H.XPT` for 2013-2014).

Every feature is something a person can answer from memory or a routine physical exam — no blood draw required:
`age_years, sex, race_ethnicity, bmi, waist_circumference_cm, general_health, heavy_alcohol_use, smoker, diabetes_status, hypertension, physical_activity`.

Target: `MCQ160L` (self-reported doctor-diagnosed liver condition), same self-report design as the diabetes model's BRFSS target — see `reports/evaluation_nhanes.md` for the honest trade-off discussion (a broader, self-reported, multi-etiology target vs. a smaller lab-confirmed one).

### Pipeline

```
python build_nhanes_dataset.py   # merge+filter raw NHANES XPT files -> data/processed/nhanes_liver_pooled.csv
python train_nhanes.py           # CV model comparison, threshold sweep, final fit -> artifacts/
```

Run from this directory, with the project's Python environment active (`pandas`, `scikit-learn`, `xgboost`, `joblib`).

### Model selection

5-fold stratified CV (training split only) compared Logistic Regression, Random Forest, and XGBoost, scored on ROC-AUC. Logistic Regression won (0.7299 CV ROC-AUC). Full numbers in `reports/evaluation_nhanes.md`.

### Threshold

Swept from 0.05 to 0.95 in steps of 0.01; the lowest threshold that still clears 80% test-set recall was kept (0.41), the same sensitivity-first screening framing the diabetes model uses.

### Artifacts

- `artifacts/liver_pipeline_nhanes_v1.pkl` — the fitted pipeline (`StandardScaler`/`OneHotEncoder` + Logistic Regression, bundled together)
- `artifacts/liver_metadata_nhanes_v1.json` — feature order, decision threshold, CV results, test metrics, data source
- `reports/evaluation_nhanes.md` — full write-up: why this model exists, feature table, model comparison, test metrics, and honest limitations (read before using this anywhere in the product)

### Limitations (read before using this model's output anywhere in the product)

1. **Lower ceiling than a lab-based model, by design.** Published NHANES studies targeting a single clean etiology (fatty liver only, FibroScan-confirmed) report AUC 0.78-0.87 without lab features; this model's broader "any liver condition" target (viral hepatitis, cirrhosis, fatty liver, etc. all lumped together, because that's the only self-report question NHANES asks) is intrinsically harder to predict, hence its lower 0.74 AUC.
2. **Self-reported target, not lab-confirmed** — same trade-off the diabetes model accepts for its BRFSS target.
3. **Low precision (8.5%) at the chosen threshold** — a deliberate sensitivity-first choice for a screening tool; see `reports/evaluation_nhanes.md` §3.
4. **No external clinical validation.**
5. **US population only** (NHANES samples the US non-institutionalized population).
6. **Not a diagnosis**: per AGENTS.md Section 11, this model's output is an AI-generated risk indicator, never a diagnosis — an elevated result means "consider getting an LFT," not "you have liver disease."

### Inference input/output

**Input**: 11 named features in `liver_metadata_nhanes_v1.json`'s `feature_order`. `backend/app/ai/models/liver_model.py`'s `predict_liver(pipeline, metadata, features_dict)` validates every value against `FEATURE_RANGES` before predicting, and fails with a clear `KeyError`/`ValueError` on bad input.

**Output**: `risk_probability` (float, 0-1) and `is_elevated` (bool, at threshold 0.41).
