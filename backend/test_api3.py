import requests

BASE_URL = 'http://127.0.0.1:8000/api/v1'

# 1. Register
requests.post(f"{BASE_URL}/auth/register", json={
    "email": "test_extreme100@example.com",
    "password": "password123",
    "name": "Test Extreme"
})

# 2. Login
resp = requests.post(f"{BASE_URL}/auth/login", json={
    "email": "test_extreme100@example.com",
    "password": "password123"
})
if resp.status_code != 200:
    print('Login Failed:', resp.json())
    exit(1)
token = resp.json().get('access_token')

# 3. Predict
payload = {
    'age': 75,
    'sex': 1,
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
