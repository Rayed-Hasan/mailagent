import urllib.request
import json

url = 'https://mailagent-public-demo.onrender.com/api/emails/with-classifications?account_id=gmail-d75649ee'
req = urllib.request.Request(url, headers={'User-Agent': 'Audit/1.0'})
with urllib.request.urlopen(req) as res:
    data = json.loads(res.read())
    print("Top-level keys:", list(data.keys()))
    emails = data.get("emails", [])
    print("Number of emails:", len(emails))
    for e in emails:
        print("ID:", e.get("id"))
        print("Subject:", e.get("subject", "")[:40])
        print("Sender:", e.get("sender", "")[:40])
        print("Priority:", e.get("priority_score"))
        print("Category:", e.get("category"))
        print("Has classification?:", e.get("classification") is not None)
        print("---")

