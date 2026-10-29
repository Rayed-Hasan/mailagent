import urllib.request
import json
import time

BASE_URL = "https://mailagent-public-demo.onrender.com"

def get(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "AuditScript/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()

def post_json(path, data):
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "AuditScript/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()

print("--- 1. Testing GET /api/demo/inbox ---")
status, body = get("/api/demo/inbox")
print(f"Status: {status}")
email_id = None
if status == 200:
    data = json.loads(body.decode())
    items = data.get("items", [])
    print(f"Total inbox items: {len(items)}")
    if items:
        email_id = items[0]["id"]
        print(f"First email: id={email_id}, subject={items[0].get('subject')}, sender={items[0].get('sender')}")

print(f"\n--- 2. Testing POST /api/demo/drafts/generate (email_id={email_id}) ---")
if email_id:
    # Render may be building commit 81a0625, let's see current response
    status, body = post_json("/api/demo/drafts/generate", {"email_id": email_id})
    print(f"Status: {status}")
    try:
        res = json.loads(body.decode())
        print(f"Response: {res}")
    except:
        print(f"Raw response: {body.decode()[:300]}")

print("\n--- 3. Testing POST /api/demo/classify ---")
if email_id:
    status, body = post_json("/api/demo/classify", {"email_id": email_id})
    print(f"Status: {status}")
    try:
        res = json.loads(body.decode())
        print(f"Response: {res}")
    except:
        print(f"Raw response: {body.decode()[:300]}")

print("\n--- 4. Testing POST /api/demo/send (Must be 403 Forbidden) ---")
status, body = post_json("/api/demo/send", {"draft_id": "test-draft-123"})
print(f"Status: {status} (Expected: 403)")
try:
    print("Response:", json.loads(body.decode()))
except:
    print("Raw response:", body.decode()[:200])

print("\n--- 5. Testing POST /api/demo/reset (Must be 403 Forbidden) ---")
status, body = post_json("/api/demo/reset", {})
print(f"Status: {status} (Expected: 403)")

print("\n--- 6. Testing GET /api/owner/gmail/auth-url (Must be 401 Unauthorized) ---")
status, body = get("/api/owner/gmail/auth-url")
print(f"Status: {status} (Expected: 401)")

