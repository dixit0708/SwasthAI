# SwasthAI — ML Model Documentation

This directory holds evidence-based documentation for SwasthAI's trained AI/ML models.

## Coverage

This documentation currently covers:

- **[Diabetes risk model](diabetes/README.md)** — `diabetes-brfss-v2` (current production) and `diabetes-brfss-v1` (retained rollback/historical baseline).

Other models present in the repository (liver disease risk, diabetes-Pima lab-based model, pneumonia CNN, skin disease CNN) are **not documented here yet**. Do not infer their status, performance, or existence from this directory's absence of coverage — consult the relevant `ml_pipeline/<model>/` or `ml-services/` directory and `backend/app/main.py` directly for those.

## How this documentation was produced

Every numerical claim in `diabetes/` is traceable to one of:

- a saved training/evaluation artifact already in the repository (`ml_pipeline/diabetes/artifacts/*.json`, `ml_pipeline/diabetes/reports/*`), or
- an independent, read-only reproduction run against the existing trained pipeline artifacts and the existing held-out test split (`docs/ml/diabetes/independent_reproduction.json`), performed solely to generate documentation and figures.

No model was retrained, tuned, or modified to produce this documentation. See `diabetes/methodology.md` and `diabetes/evaluation.md` for the full evidence trail.
