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

print("Testing live draft generation...")
test_email_id = "29401c28-756d-4e91-b172-4279f66595be"
status, body = post_json("/api/demo/drafts/generate", {"email_id": test_email_id})
print(f"Status: {status}")
try:
    data = json.loads(body.decode("utf-8"))
    print("Keys in response:", list(data.keys()))
    if "draft" in data:
        print("Draft subject:", data["draft"].get("subject"))
        print("Draft body preview:", repr(data["draft"].get("body", ""))[:80])
        print("Provider used:", data.get("provider_used"))
    elif "detail" in data:
        print("Detail:", data["detail"])
except Exception as exc:
    print("Error parsing response:", exc)
    print("Body snippet:", body[:200])

