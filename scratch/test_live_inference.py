import urllib.request
import json
import time

BASE_URL = "https://mailagent-public-demo.onrender.com"

def post_json(path, data):
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "AuditScript/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()

test_email_id = "368d877e-0fde-466e-89fa-798bb529fe9c"
print(f"Testing live draft generation with valid ID: {test_email_id}...")
status, body = post_json("/api/demo/drafts/generate", {"email_id": test_email_id})
print(f"Draft Status: {status}")
try:
    print("Draft Response:", json.loads(body.decode("utf-8")))
except Exception as e:
    print("Draft Raw:", body[:300])

print(f"\nTesting live classification with valid ID: {test_email_id}...")
status, body = post_json("/api/demo/classify", {"email_id": test_email_id})
print(f"Classify Status: {status}")
try:
    print("Classify Response:", json.loads(body.decode("utf-8")))
except Exception as e:
    print("Classify Raw:", body[:300])

