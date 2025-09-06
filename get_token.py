import requests
import json

# Keycloak token endpoint
token_url = "http://10.97.36.86:8070/realms/master/protocol/openid-connect/token"

# Client credentials
client_id = "admin-cli"
client_secret = "lOghCsGxrVvozLXH3CNV2mzFucyKkVDx"
username = "admin"
password = "admin123"

# Request payload for password grant
data = {
    "grant_type": "password",
    "client_id": client_id,
    "client_secret": client_secret,
    "username": username,
    "password": password
}

try:
    # Make the token request
    response = requests.post(token_url, data=data)
    response.raise_for_status()
    
    token_data = response.json()
    access_token = token_data["access_token"]
    
    print("Successfully obtained access token!")
    print(f"Token starts with: {access_token[:50]}...")
    print(f"Token length: {len(access_token)} characters")
    print()
    print("Full token:")
    print(access_token)
    
except requests.exceptions.RequestException as e:
    print(f"Error requesting token: {e}")
    if hasattr(response, "status_code"):
        print(f"Response status: {response.status_code}")
    if hasattr(response, "text"):
        print(f"Response content: {response.text}")

