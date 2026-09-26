# Liver Disease Risk Model — Evaluation Report

**Model version:** liver-ilpd-v1  
**Algorithm:** Random Forest  
**Dataset:** Indian_Liver_Patient_549_Clean_Dataset.xlsx (549 rows)  
**Trained at:** 2026-09-13T15:04:26.813481+00:00  

## Candidate Model Comparison (Validation Set)

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|---|
| Logistic Regression | 0.7000 | 0.8082 | 0.7564 | 0.7815 | 0.7476 |
| Random Forest | 0.7182 | 0.7327 | 0.9487 | 0.8268 | 0.6919 |
| Gradient Boosting | 0.7091 | 0.7347 | 0.9231 | 0.8182 | 0.6294 |
| XGBoost | 0.6818 | 0.7792 | 0.7692 | 0.7742 | 0.6775 |

**Selected:** Random Forest (best F1 on validation set)

## Final Test-Set Performance

| Metric | Value |
|---|---|
| Accuracy | 0.7818 |
| Precision | 0.8161 |
| Recall | 0.8987 |
| F1-score | 0.8554 |
| ROC-AUC | 0.7297 |
| Decision Threshold | 0.53 |

Confusion Matrix (TN/FP/FN/TP): [15, 16, 8, 71]
