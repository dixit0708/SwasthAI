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
The model is designed around the **NHANES clinical dataset**. The specific features used for this risk assessment include:
* Age
* SBP (Systolic Blood Pressure)
* DBP (Diastolic Blood Pressure)
* Total Chol (Total Cholesterol)
* HDL (High-Density Lipoprotein)
* Fasting Glucose
* Pulse
* BMI (Body Mass Index)

*(Note: Local training artifacts currently reflect CDC BRFSS / YRBS 2022 survey data; the architecture is adaptable to the clinical feature set.)*

### Continuous Probabilistic Scaling (The UI Translation)
To translate the model's raw probabilities into a user-friendly format, custom `numpy.interp` backend logic is utilized. Raw tree-based probabilities mathematically cap between ~5% and ~14% due to the prevalence of the condition in the dataset. To make this intuitive for end-users, these raw probability scores are linearly interpolated to a **1% - 99% frontend visual gauge** using dynamic anchor points. This scaling maps the extremely narrow probability distribution into a full spectrum, allowing the UI to present a meaningful, continuous risk indicator.

### Statistical Performance
Based on the exact metrics extracted from the test evaluation reports (`test_evaluation.json`), the model achieves the following real-world performance metrics:

| Metric | Value |
| :--- | :--- |
| **Accuracy** | 91.35% (0.9135) |
| **ROC-AUC** | 84.65% (0.8465) |
| **Precision** | 56.53% (0.5653) |
| **Recall (Sensitivity)** | 9.42% (0.0942) |

*(Note: Feature importance scores (F-scores/P-values) were not explicitly exported in the current training logs.)*

### Testing & Validation
Thorough testing and validation are performed to ensure reliable output. The system is tested against extreme-value bounds:
* **Healthy baseline mappings:** Ensuring that ideal clinical inputs (e.g., normal BMI, healthy blood pressure and glucose) scale accurately to the lowest bounds of the risk gauge.
* **Fatal input mappings:** Validating that severe, extreme high-risk inputs maximize the `numpy.interp` anchor points, mapping cleanly to the 99% upper bound of the visual gauge.
