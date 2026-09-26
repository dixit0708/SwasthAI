import pandas as pd
import numpy as np
import os
import joblib
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix

def load_and_merge_data(data_dir):
    print("Loading datasets...")
    demo = pd.read_csv(os.path.join(data_dir, 'demographics.csv'))
    exam = pd.read_csv(os.path.join(data_dir, 'examination.csv'))
    labs = pd.read_csv(os.path.join(data_dir, 'laboratory.csv'))
    quest = pd.read_csv(os.path.join(data_dir, 'questionnaire.csv'))
    
    # Merge on SEQN
    df = demo.merge(exam, on='SEQN', how='inner')
    df = df.merge(labs, on='SEQN', how='inner')
    df = df.merge(quest, on='SEQN', how='inner')
    
    print(f"Merged shape: {df.shape}")
    return df

def preprocess_and_train(df, output_dir):
    print("Preprocessing data...")
    
    # Features
    features = ['RIDAGEYR', 'BPXSY1', 'BPXDI1', 'LBXTC', 'LBDHDD', 'LBXGLU', 'BPXPLS', 'BMXBMI']
    
    # Target
    # NHANES: 1 = Yes, 2 = No, 7 = Refused, 9 = Don't know
    # We define heart disease if MCQ160B (CHF), MCQ160C (CHD), or MCQ160E (Heart Attack) is 1.
    target_cols = ['MCQ160B', 'MCQ160C', 'MCQ160E']
    
    # Keep rows where target columns are not entirely nan
    df = df.dropna(subset=target_cols, how='all').copy()
    
    # Create binary target
    df['target'] = ((df['MCQ160B'] == 1) | (df['MCQ160C'] == 1) | (df['MCQ160E'] == 1)).astype(int)
    
    X = df[features].copy()
    y = df['target']
    
    # Impute missing values with median
    for col in features:
        X[col] = X[col].fillna(X[col].median())
        
    print(f"Dataset size after cleaning: {len(X)}")
    print(f"Target distribution:\n{y.value_counts()}")
    
    # Train-test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    print("Training XGBoost without scale_pos_weight...")
    base_model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
        eval_metric='logloss'
    )
    
    base_model.fit(X_train_scaled, y_train)
    model = base_model
    
    # Evaluate
    y_pred = model.predict(X_test_scaled)
    y_prob = model.predict_proba(X_test_scaled)[:, 1]
    
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred)
    rec = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_prob)
    cm = confusion_matrix(y_test, y_pred)
    
    print("\n--- Validation Metrics ---")
    print(f"Accuracy:  {acc:.4f}")
    print(f"Precision: {prec:.4f}")
    print(f"Recall:    {rec:.4f}")
    print(f"F1-Score:  {f1:.4f}")
    print(f"ROC-AUC:   {roc_auc:.4f}")
    print(f"Confusion Matrix:\n{cm}")
    
    # Save artifacts
    model_path = os.path.join(output_dir, 'heart_clinical_model.pkl')
    scaler_path = os.path.join(output_dir, 'scaler.pkl')
    
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    print(f"\nArtifacts saved to {output_dir}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, 'data')
    
    if not os.path.exists(data_dir):
        print(f"Data directory not found at {data_dir}")
        exit(1)
        
    df = load_and_merge_data(data_dir)
    preprocess_and_train(df, base_dir)
