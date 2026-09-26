import requests

BASE_URL = 'http://127.0.0.1:8000/api/v1'

# 1. Register
requests.post(f"{BASE_URL}/auth/register", json={
    "email": "test_extreme@example.com",
    "password": "password123",
    "first_name": "Test",
    "last_name": "Extreme"
})

# 2. Login
resp = requests.post(f"{BASE_URL}/auth/login", data={
    "username": "test_extreme@example.com",
    "password": "password123"
})
token = resp.json().get('access_token')

# 3. Predict
payload = {
    'age': 75,
    'systolic_bp': 190,
    'diastolic_bp': 100,
    'total_cholesterol': 300,
    'hdl_cholesterol': 30,
    'fasting_glucose': 180,
    'pulse': 90,
    'bmi': 35.0
}
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
pred_resp = requests.post(f"{BASE_URL}/predict/heart/clinical", json=payload, headers=headers)
print('Status:', pred_resp.status_code)
print('Response:', pred_resp.json())
