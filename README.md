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
