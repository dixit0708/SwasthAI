# Liver Model Feature Experiment — high_cholesterol / smoking_status

Logistic Regression only (the winning family from the baseline
comparison), 5-fold stratified CV on the full pooled dataset — same
methodology as `train_nhanes.py`, isolating the effect of the
feature change itself. Run once; numbers below are exactly what
this run produced, not adjusted.

| Variant | Rows | ROC-AUC (mean +/- std) | F1 | Recall |
|---|---|---|---|---|
| baseline (v1, production) | 12147 | 0.7380 +/- 0.0143 | 0.1696 | 0.6638 |
| + high_cholesterol | 12147 | 0.7378 +/- 0.0145 | 0.1686 | 0.6621 |
| smoker -> smoking_status | 12147 | 0.7372 +/- 0.0129 | 0.1687 | 0.6655 |
| both changes | 12147 | 0.7371 +/- 0.0134 | 0.1694 | 0.6688 |
