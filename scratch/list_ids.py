import urllib.request
import json

url = 'https://mailagent-public-demo.onrender.com/api/emails/with-classifications?account_id=gmail-d75649ee'
req = urllib.request.Request(url, headers={'User-Agent': 'Audit/1.0'})
with urllib.request.urlopen(req) as res:
    data = json.loads(res.read())
    emails = data.get("emails", [])
    print(f"Total emails: {len(emails)}")
    for e in emails:
        print(f"ID: {e.get('id')}")

