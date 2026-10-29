import urllib.request
import json

url = 'https://mailagent-public-demo.onrender.com/api/emails/with-classifications?account_id=gmail-d75649ee'
req = urllib.request.Request(url, headers={'User-Agent': 'Audit/1.0'})
with urllib.request.urlopen(req) as res:
    items = json.loads(res.read())
    print('Emails count:', len(items))
    for i, it in enumerate(items):
        print(f"{i+1}. id={it.get('id')}")
        print(f"   subject={it.get('subject')}")
        print(f"   priority={it.get('priority_score')}")
        print(f"   category={it.get('category')}")

