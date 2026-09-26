import requests

BASE_URL = 'http://127.0.0.1:8000/api/v1'

resp = requests.post(f"{BASE_URL}/auth/login", data={
    "username": "test_extreme@example.com",
    "password": "password123"
})
print("Login Resp:", resp.json())
