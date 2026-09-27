# SwasthAI

SwasthAI is an AI-Powered Personalized Healthcare Ecosystem. It is a B.Tech CSE major project demonstrating integration of Artificial Intelligence, Machine Learning, Deep Learning, Computer Vision, and modern web application development.

## Features (Planned)
- Disease risk prediction (Diabetes, Heart Disease, Liver Disease, Pneumonia, Skin Disease)
- Medical image & report analysis
- AI Personalized health assistant
- Digital medical records and family health management
- Doctor discovery & appointment scheduling

## Technology Stack
- **Backend:** Python, FastAPI, Pydantic, Motor
- **Database:** MongoDB
- **Frontend:** HTML5, CSS3, Vanilla JS
- **AI/ML:** Scikit-learn, XGBoost, TensorFlow/PyTorch

## Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd swasthAI
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Copy `.env.example` to `.env` inside the `backend` directory and update the values.
   ```bash
   cp .env.example .env
   ```

5. **Run the application:**
   Make sure you are in the `backend` directory.
   ```bash
   uvicorn app.main:app --reload
   ```

6. **Check health endpoint:**
   Navigate to `http://127.0.0.1:8000/health` or `http://127.0.0.1:8000/docs` for the API documentation.


## Heart Disease Prediction Module

### Algorithm & Architecture
The Heart Disease Prediction module utilizes an **XGBClassifier**. An unweighted model approach was chosen to preserve the healthy baseline (preventing false-positive inflation), ensuring individuals at a naturally lower baseline risk are not incorrectly flagged due to artificial class balancing during inference. The backend is built on **FastAPI** which serves the model and executes the scaling logic, integrating seamlessly into the **React**-based frontend UI.

### Dataset & Features
The model is designed around the **CDC BRFSS / YRBS 2022 survey data**. The specific features used for this risk assessment include:
* Age
* SBP (Systolic Blood Pressure)
* DBP (Diastolic Blood Pressure)
* Total Chol (Total Cholesterol)
* HDL (High-Density Lipoprotein)
* Fasting Glucose
* Pulse
* BMI (Body Mass Index)

### Continuous Probabilistic Scaling (The UI Translation)
To translate the model's raw probabilities into a user-friendly format, custom `numpy.interp` backend logic is utilized. Raw tree-based probabilities mathematically cap between ~5% and ~14% due to the prevalence of the condition in the dataset. To make this intuitive for end-users, these raw probability scores are linearly interpolated to a **1% - 99% frontend visual gauge** using dynamic anchor points. This scaling maps the extremely narrow probability distribution into a full spectrum, allowing the UI to present a meaningful, continuous risk indicator.

### Statistical Performance
Based on the exact metrics extracted from the test evaluation reports (`test_evaluation.json`), the model achieves the following real-world performance metrics:

| Metric | Value |
| :--- | :--- |
| **Accuracy** | 70.89% (0.7089) |
| **ROC-AUC** | 84.65% (0.8465) |
| **Precision** | 21.11% (0.2111) |
| **Recall (Sensitivity)** | 83.71% (0.8371) |

*(Note: Feature importance scores (F-scores/P-values) were not explicitly exported in the current training logs. Metrics calculated using a custom calibrated threshold (0.08) rather than the default 0.5, aligning the statistical evaluation with the continuous UI scaling logic.)*

### Testing & Validation
Thorough testing and validation are performed to ensure reliable output. The system is tested against extreme-value bounds:
* **Healthy baseline mappings:** Ensuring that ideal clinical inputs (e.g., normal BMI, healthy blood pressure and glucose) scale accurately to the lowest bounds of the risk gauge.
* **Fatal input mappings:** Validating that severe, extreme high-risk inputs maximize the `numpy.interp` anchor points, mapping cleanly to the 99% upper bound of the visual gauge.


## API Documentation

Total Number of APIs: 14

1. `/health`
2. `/api/v1/auth/register`
3. `/api/v1/auth/login`
4. `/api/v1/auth/me`
5. `/api/v1/health-profile/me`
6. `/api/v1/health-profile/me` (PUT)
7. `/api/v1/health-profile/me/conditions`
8. `/api/v1/health-profile/me/conditions/{condition_id}`
9. `/api/v1/predict/pneumonia`
10. `/api/v1/predict/diabetes`
11. `/api/v1/predict/heart`
12. `/api/v1/predict/heart/clinical`
13. `/api/v1/predict/liver`
14. `/api/v1/predict/skin`

| HTTP Method | Endpoint / Route | Description | Request Payload | Response Data |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/health` | API Health Check | None | `{"status": "healthy", "project": "..."}` |
| **POST** | `/api/v1/auth/register` | Registers a new user | `UserCreate` (name, email, password) | `Token` (access_token, user_id, email, name) |
| **POST** | `/api/v1/auth/login` | Authenticates a user | `UserLogin` (email, password) | `Token` (access_token, user_id, email, name) |
| **GET** | `/api/v1/auth/me` | Retrieves the current user's info | None (Requires JWT) | `UserOut` (id, name, email) |
| **GET** | `/api/v1/health-profile/me` | Retrieves current user's health profile | None (Requires JWT) | `HealthProfileOut` |
| **PUT** | `/api/v1/health-profile/me` | Updates current user's basic health info | `HealthProfileUpdate` | `HealthProfileOut` |
| **POST** | `/api/v1/health-profile/me/conditions` | Adds a medical condition to the user's profile | `ConditionCreate` (label) | `HealthProfileOut` |
| **DELETE** | `/api/v1/health-profile/me/conditions/{condition_id}` | Removes a specific condition from profile | URL Parameter: `condition_id` | `HealthProfileOut` |
| **POST** | `/api/v1/predict/pneumonia` | Predicts Pneumonia from X-Ray Image | `UploadFile` (image) | CNN JSON Prediction Result |
| **POST** | `/api/v1/predict/diabetes` | Predicts Diabetes Risk from Health Params | `DiabetesPredictionInput` | `RiskPredictionOut` |
| **POST** | `/api/v1/predict/heart` | Predicts Heart Disease Risk from Survey Params | `HeartPredictionInput` | `HeartRiskPredictionOut` |
| **POST** | `/api/v1/predict/heart/clinical` | Predicts Heart Disease Risk from Lab Params | `HeartClinicalInput` | `HeartRiskPredictionOut` |
| **POST** | `/api/v1/predict/liver` | Predicts Liver Disease Risk | `LiverPredictionInput` | `RiskPredictionOut` |
| **POST** | `/api/v1/predict/skin` | Predicts Skin Disease from Image | `UploadFile` (image) | CNN JSON Prediction Result |
