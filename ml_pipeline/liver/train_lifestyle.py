import pandas as pd
import numpy as np
import joblib
import json
import os
from sklearn.model_selection import train_test_split
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
from sklearn.metrics import classification_report, accuracy_score, roc_auc_score

# 1. Load data
raw_path = r'C:\Users\aradh\.gemini\antigravity-ide\brain\389026c5-a0f5-4cfd-a509-7816c3e9c46b\.user_uploaded\media_1789311107907.csv'
df = pd.read_csv(raw_path)

# 2. Target Variable
# 1 if fatty_liver_grade >= 1 or liver_cirrhosis == 1, else 0
df['liver_disease'] = ((df['fatty_liver_grade'] >= 1) | (df['liver_cirrhosis'] == 1)).astype(int)

# 3. Features
df['gender'] = df['gender'].map({'M': 1, 'F': 0})
features = ['age', 'gender', 'bmi', 'alcohol_status', 'smoking_status', 'diabetes_type_2', 'hypertension']
X = df[features]
y = df['liver_disease']

# 4. Train-Test Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

# 5. Preprocessing
# We use indices so that the deployed pipeline doesn't require pandas DataFrames
num_idx = [features.index(c) for c in ['age', 'bmi']]
cat_idx = [features.index(c) for c in ['gender', 'alcohol_status', 'smoking_status', 'diabetes_type_2', 'hypertension']]

numeric_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler())
])

categorical_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='most_frequent'))
])

preprocessor = ColumnTransformer(
    transformers=[
        ('num', numeric_transformer, num_idx),
        ('cat', categorical_transformer, cat_idx)
    ])

# 6. Model
model = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('classifier', XGBClassifier(random_state=42, use_label_encoder=False, eval_metric='logloss'))
])

# 7. Train
model.fit(X_train.values, y_train.values)

# 8. Evaluate
y_pred = model.predict(X_test.values)
y_prob = model.predict_proba(X_test.values)[:, 1]

print("Accuracy:", accuracy_score(y_test, y_pred))
print("ROC AUC:", roc_auc_score(y_test, y_prob))
print("\nClassification Report:\n", classification_report(y_test, y_pred))

# 9. Save
os.makedirs(r'backend/app/ai/models', exist_ok=True)
joblib.dump(model, r'backend/app/ai/models/liver_lifestyle_pipeline.pkl')

metadata = {
    "model_name": "liver-lifestyle-v1",
    "version": "1.0.0",
    "features": features,
    "target": "liver_disease (binary)",
    "metrics": {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "roc_auc": float(roc_auc_score(y_test, y_prob))
    }
}
with open(r'backend/app/ai/models/liver_lifestyle_metadata.json', 'w') as f:
    json.dump(metadata, f, indent=4)

print("Model saved to backend/app/ai/models/liver_lifestyle_pipeline.pkl")
