import requests
import json

# Fresh JWT token from Keycloak
access_token = "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJLRTFiLVlSdWVqR3lRbE8zdXRJaURHYkpGNFlfdElLQ2QtOThPLXRUM3UwIn0.eyJleHAiOjE3NTcxMjgwMjQsImlhdCI6MTc1NzEyNzk2NCwianRpIjoiNWExZDUzZmYtYTYzNC00ODI3LWFlZTYtMDg2MmU3MjU1ZTE5IiwiaXNzIjoiaHR0cDovLzEwLjk3LjM2Ljg2OjgwNzAvcmVhbG1zL21hc3RlciIsInR5cCI6IkJlYXJlciIsImF6cCI6ImFkbWluLWNsaSIsInNpZCI6IjViZTA4YmVlLWQ1ZGMtNGQwYy05MDE0LTFkNTJmYmEzMzg4MyIsInNjb3BlIjoiZW1haWwgcHJvZmlsZSJ9.dvcOm20Nx6jz_3BNyyNnVL_OoDYC2QyIdB-z0Fyf6s5_m1kwloeid_tJNmQpUuRyzsjhs_HD_-hR-zl4tS4r76bF-ZCBZg5fE2sa_MoBxzabkE_jkw0Ui5QDZFvW-KERNM0b-WQCE-IwXQKIaQd2rI1_-PJL7hNFPCTV-CCkn3C6m-dyhjb3jyMead_qVLjbmKYh5Yo3lUIBucWauYRo2dLlBe7AQ_ITH4MuybEv0kUQWNSEAgD5cFVlfd_QnI6bE3aX4e7_mNYW3rUuuHppqZyHR_mq9rFtYCdRfzgCrVFmVRizZPAi-ulGKzWi7Wwr5WGmpio01UkzWG7edHq6xA"

# Test the authentication with our FastAPI server
test_url = "http://localhost:8000/auth/me"

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

try:
    response = requests.get(test_url, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("SUCCESS: Authentication working with fresh token!")
    else:
        print("FAILED: Authentication still has issues")
        
except requests.exceptions.RequestException as e:
    print(f"Error: {e}")

