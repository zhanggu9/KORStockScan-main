"""Kiwoom REST OAuth token smoke test.

Credentials are read from environment variables; never hard-code them here.
    export KIWOOM_APP_KEY="..."
    export KIWOOM_SECRET_KEY="..."
"""

import os

import requests

url = "https://api.kiwoom.com/oauth2/token"
app_key = os.environ.get("KIWOOM_APP_KEY")
secret_key = os.environ.get("KIWOOM_SECRET_KEY")

if not app_key or not secret_key:
    raise SystemExit("Set KIWOOM_APP_KEY and KIWOOM_SECRET_KEY environment variables.")

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
