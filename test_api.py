import requests

url = "http://127.0.0.1:8000/api/v1/predict/heart"

payload = {
    "sex": "Male",
    "age_category": "Age 65 to 69",
    "bmi": 28.5,
    "general_health": "Fair",
    "physical_health_days": 5,
    "mental_health_days": 0,
    "sleep_hours": 7,
    "physical_activities": "No",
    "had_stroke": "No",
    "had_asthma": "No",
    "had_copd": "No",
    "had_depressive_disorder": "No",
    "had_kidney_disease": "No",
    "had_arthritis": "Yes",
    "had_diabetes": "Yes",
    "difficulty_walking": "Yes",
    "difficulty_concentrating": "No",
    "difficulty_errands": "No",
    "smoker_status": "Former smoker",
    "alcohol_drinkers": "No",
    "chest_scan": "Yes",
    "high_risk_last_year": "No",
    "removed_teeth": "1 to 5",
    "last_checkup_time": "Within past year (anytime less than 12 months ago)"
}

response = requests.post(url, json=payload)
print("Status Code:", response.status_code)
try:
    print("Prediction Result:", response.json())
except:
    print("Raw Response:", response.text)