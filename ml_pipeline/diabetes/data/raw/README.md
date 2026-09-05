# Raw Dataset — Pima Indians Diabetes Database

- **File**: `pima-diabetes-raw.csv` (768 rows, no header row)
- **Source**: National Institute of Diabetes and Digestive and Kidney Diseases, distributed via the UCI Machine Learning Repository. Retrieved from the widely-used public mirror at `https://raw.githubusercontent.com/jbrownlee/Datasets/master/pima-indians-diabetes.data.csv` (Jason Brownlee's `Datasets` GitHub repository, a standard, frequently-cited redistribution of this UCI dataset).
- **License / usage terms**: No restrictive license is attached to this dataset in its public distributions; it is a long-standing public-domain research/education dataset used extensively in academic ML coursework and tutorials. No proprietary or patient-identifiable data is included.
- **This file is untouched from the source** — do not edit it. All cleaning/imputation happens in `preprocessing.py` and is written to `../processed/`.

## Columns (in order, no header in the raw file)

| # | Column | Description |
|---|--------|-------------|
| 1 | Pregnancies | Number of times pregnant |
| 2 | Glucose | Plasma glucose concentration (2-hour oral glucose tolerance test) |
| 3 | BloodPressure | Diastolic blood pressure (mm Hg) |
| 4 | SkinThickness | Triceps skinfold thickness (mm) |
| 5 | Insulin | 2-hour serum insulin (mu U/ml) |
| 6 | BMI | Body mass index |
| 7 | DiabetesPedigreeFunction | A function scoring likelihood of diabetes based on family history |
| 8 | Age | Age in years |
| 9 | Outcome | 1 = diabetic, 0 = not diabetic (label) |

## Critical known data-quality issue

Columns **Glucose, BloodPressure, SkinThickness, Insulin, and BMI** use `0` as a placeholder for **missing** measurements (a value of 0 is not physiologically possible for any of these). This is a well-documented quirk of this specific public dataset. `preprocessing.py` treats these zeros as missing values (NaN) and imputes them — it does **not** treat them as literal clinical readings of zero.

## Critical population limitation

This dataset exclusively contains **female patients of Pima Indian heritage, age 21+**, examined by the study's original authors. A model trained on it should **not** be presented as generalizing to men, children, or other populations/ethnicities — this is documented as a stated limitation in the top-level `ml_pipeline/diabetes/README.md` per the project's fairness-and-limitations requirement, and the production API's output copy reflects this.
