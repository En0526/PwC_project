import requests
import json

BASE_URL = 'http://127.0.0.1:5000'
session = requests.Session()

def test_api():
    print("--- 0. Registering/Logging in ---")
    reg_data = {'email': 'testuser@example.com', 'password': 'password123'}
    try:
        # Try to register
        r = session.post(f'{BASE_URL}/auth/register', data=reg_data, timeout=10, allow_redirects=False)
        if r.status_code == 302:
            print("Successfully registered or already exists and logged in.")
        else:
            # Try to login if registration failed (likely already exists)
            r = session.post(f'{BASE_URL}/auth/login', data=reg_data, timeout=10, allow_redirects=False)
            if r.status_code == 302:
                print("Successfully logged in.")
            else:
                print(f"Login/Register failed with status {r.status_code}")
    except Exception as e:
        print(f"Auth Error: {e}")

    print("\n--- 1. Testing /api/subscriptions (Auth Check) ---")
    try:
        r = session.get(f'{BASE_URL}/api/subscriptions', timeout=10)
        print(f"Status Code: {r.status_code}")
        print(f"Response: {r.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

    print("\n--- 2. Testing /api/subscriptions/rss/detect ---")
    detect_payload = {"url": "https://www.bbc.com/news"}
    try:
        r = session.post(f'{BASE_URL}/api/subscriptions/rss/detect', json=detect_payload, timeout=10)
        print(f"Status Code: {r.status_code}")
        # Decode response if it contains unicode escaping
        print(f"Response: {json.dumps(r.json(), indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"Error: {e}")

    print("\n--- 3. Testing /api/subscriptions/rss/validate ---")
    validate_payload = {"url": "http://feeds.bbci.co.uk/news/rss.xml"}
    try:
        r = session.post(f'{BASE_URL}/api/subscriptions/rss/validate', json=validate_payload, timeout=10)
        print(f"Status Code: {r.status_code}")
        print(f"Response: {json.dumps(r.json(), indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    test_api()
