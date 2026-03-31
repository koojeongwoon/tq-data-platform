import requests
import json
import sys

# Base URL
BASE_URL = "http://localhost:8000"

def test_dashboard_auth_auto_filter():
    print("--- Testing Dashboard Auto-Filter via Auth ---")
    
    # 1. Login to get token (user 1 is '청년')
    login_url = f"{BASE_URL}/auth/login"
    login_data = {
        "email": "test@example.com", # Assuming user 1 has this email from earlier logs
        "password": "password123"
    }
    
    # Actually let's try to find a user first or just use a known one
    # For CI/Verification consistency, I'll use the user I found in the DB (test@example.com / user_id 1)
    
    try:
        print(f"Logging in as {login_data['email']}...")
        resp = requests.post(login_url, json=login_data)
        if resp.status_code != 200:
            print(f"❌ Login failed: {resp.status_code} {resp.text}")
            return
            
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ Login successful")
        
        # 2. Call personalized recommendations WITHOUT parameters
        recommend_url = f"{BASE_URL}/dashboard/personalized"
        print(f"\nRequesting: {recommend_url} (with Auth header)")
        
        resp = requests.get(recommend_url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            print("✅ Response 200 OK")
            
            # Verify National Results
            print("\n--- Personalized Recommendations (With Reranking & Threshold 0.5) ---")
            for p in data.get('recommendations', []):
                print(f"- {p['title']} ({p['region']}) | Score: {p['match_score']:.4f}")
                
            # Check if any score is below 0.5
            low_scores = [p for p in data.get('recommendations', []) if p['match_score'] < 0.5]
            if not low_scores:
                print("\n✨ SUCCESS: All recommendations meet the quality threshold (>= 0.5)!")
            else:
                print(f"\n❌ FAILED: Found {len(low_scores)} recommendations below the 0.5 threshold.")
                
        else:
            print(f"❌ Failed: {resp.status_code}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_dashboard_auth_auto_filter()
