"""Verification script for Dashboard and Contextual Chat"""

import httpx
import json

BASE_URL = "http://localhost:8000"

def test_dashboard_summary(token: str):
    print("\n--- Testing Dashboard Summary ---")
    headers = {"Authorization": f"Bearer {token}"}
    response = httpx.get(f"{BASE_URL}/dashboard/summary", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Data: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

def test_dashboard_personalized(token: str):
    print("\n--- Testing Personalized Recommendations ---")
    headers = {"Authorization": f"Bearer {token}"}
    response = httpx.get(f"{BASE_URL}/dashboard/personalized", headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Data: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

def test_contextual_chat(token: str):
    print("\n--- Testing Contextual Chat (Pre-loading) ---")
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "message": "", # No message, just pre-loading
        "pre_load_policy_id": "policy_123"
    }
    response = httpx.post(f"{BASE_URL}/chat/conversation", headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    res_data = response.json()
    print(f"Response: {res_data.get('response')}")
    print(f"Intent detected: {res_data.get('intent')}")

if __name__ == "__main__":
    # Note: Requires a valid token for testing
    print("Verification script ready. (Note: Run with a valid Bearer token)")
    # Example usage:
    # token = "..."
    # test_dashboard_summary(token)
    # test_dashboard_personalized(token)
    # test_contextual_chat(token)
