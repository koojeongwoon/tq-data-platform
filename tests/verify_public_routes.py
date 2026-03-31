import requests

BASE_URL = "http://localhost:8000"

def test_welfare_policies():
    print("Testing GET /welfare/policies...")
    response = requests.get(f"{BASE_URL}/welfare/policies")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Success")
    else:
        print("❌ Failed")
        print(response.text)

def test_welfare_policy_detail():
    print("Testing GET /welfare/policies/detail (ID based)...")
    # Using an ID mentioned in the user request WLF00003554
    response = requests.get(f"{BASE_URL}/welfare/policies/WLF00003554")
    print(f"Status: {response.status_code}")
    if response.status_code in [200, 404]: # 404 is still better than 401
        print("✅ Success (Accessible)")
    else:
        print("❌ Failed")
        print(response.text)

def test_semantic_search():
    print("Testing GET /search/semantic?q=housing...")
    response = requests.get(f"{BASE_URL}/search/semantic", params={"q": "housing"})
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Success")
    else:
        print("❌ Failed")
        print(response.text)

if __name__ == "__main__":
    test_welfare_policies()
    test_welfare_policy_detail()
    test_semantic_search()
