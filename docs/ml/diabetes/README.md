# SwasthAI Diabetes Risk Model

| | |
|---|---|
| **Current production model** | `diabetes-brfss-v2` (14 features) |
| **Retained rollback model** | `diabetes-brfss-v1` (21 features) — untouched on disk, not currently loaded by the backend's default `/predict/diabetes` route |
| **Task** | Binary screening: elevated vs. not-elevated diabetes risk indicator |
| **Algorithm** | XGBoost classifier, sigmoid (Platt) calibrated, metadata-driven decision threshold |
| **Endpoint** | `POST /api/v1/predict/diabetes` (authenticated) |

This directory documents **only** the diabetes risk model. See [`docs/ml/README.md`](../README.md) for what else is and isn't covered.

## Contents

- **[model_card.md](model_card.md)** — full model card: identification, inputs/outputs, dataset, algorithm, hyperparameters, calibration, threshold, performance, limitations, intended use, version history, reproducibility, production integration.
- **[methodology.md](methodology.md)** — how the model was built: dataset → cleaning → preprocessing → split → model comparison → training → calibration → threshold selection → artifact.
- **[evaluation.md](evaluation.md)** — full performance evidence: metrics, confusion matrix, ROC/PR curves, calibration, feature importance, v1-vs-v2 comparison, error analysis. Includes an **independent reproduction** of the headline metrics performed specifically for this documentation.
- **[limitations.md](limitations.md)** — dataset, model, and clinical limitations.
- **[results.json](results.json)** — machine-readable summary of the above.
- **[figures/](figures/)** — confusion matrix, ROC curve, precision-recall curve, calibration curve, and feature importance chart, all generated from the v2 artifact running on the actual held-out test split.
- **[independent_reproduction.json](independent_reproduction.json)** — raw output of the reproduction script for both v1 and v2, for anyone who wants to re-verify by eye against the metadata files.

## Technical summary

`diabetes-brfss-v2` is a scikit-learn `Pipeline` (`StandardScaler` → `XGBClassifier` wrapped in `CalibratedClassifierCV`, `method="sigmoid"`) trained on the CDC BRFSS 2015 Diabetes Health Indicators dataset, taking 14 self-reported lifestyle/health-history features and returning a calibrated probability, thresholded at a metadata-defined operating point (0.10) tuned for high sensitivity in a screening context. It supersedes `diabetes-brfss-v1` (21 features, same dataset and algorithm family), which is retained on disk unmodified as a rollback/comparison baseline. Full evidence in [evaluation.md](evaluation.md).

## Simple explanation

This model looks at answers to 14 questions about your health history and lifestyle (like blood pressure, cholesterol, general health, BMI, activity level) and estimates whether that pattern of answers looks similar to people in a large U.S. health survey who reported being diagnosed with diabetes. It is **not** a lab test and does not diagnose diabetes — it is a screening indicator meant to suggest when someone might want to talk to a healthcare professional or get an actual test done. The tool is deliberately tuned to catch more possible cases (fewer missed positives) even though that means it also flags more people who, on further testing, turn out not to have diabetes.

## What this model does NOT do

- It does not diagnose diabetes.
- It does not replace a blood glucose test, HbA1c test, or any laboratory measurement.
- It does not account for family history (not available in the training data — see [limitations.md](limitations.md)).
- It has not undergone independent external or clinical validation.

Every screening result returned by the API includes the disclaimer: *"This is an AI-generated risk indicator based on the values you entered, not a medical diagnosis. Please consult a qualified healthcare professional to discuss these results and any next steps."*
