import requests
import json

url = "https://api.kiwoom.com/oauth2/token"
app_key = "fkNM-w9TA-dlgHO1R3uF9PwTgTz1zusP3DljaAPeY7o"
secret_key = "vCAHfFLJ6wkgXgaGQPjesiAKueT6054eCBCAW_KAfD0"

params = {
    "grant_type": "client_credentials",
    "appkey": app_key,
    "secretkey": secret_key,
}
headers = {"Content-Type": "application/json;charset=UTF-8"}

try:
    res = requests.post(url, headers=headers, json=params, timeout=10)
    print(f"Status: {res.status_code}")
    print(f"Response: {res.text}")
except Exception as e:
    print(f"Error: {e}")
