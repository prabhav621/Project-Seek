import urllib.request, json
url = 'https://generativelanguage.googleapis.com/v1beta/models?key='
req = urllib.request.Request(url)
try:
    with urllib.request.urlopen(req) as response:
        models = json.loads(response.read().decode())['models']
        for m in models:
            if 'embed' in m['name'] or 'embedding' in m['name']:
                print(m['name'])
except Exception as e:
    print(e)
