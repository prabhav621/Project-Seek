import os
import re
import requests

print("\n🔍 QUERYING GROQ LIVE HARDWARE...")
groq_key = None
if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("GROQ_API_KEY="):
                groq_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

if not groq_key:
    print("❌ Could not find GROQ_API_KEY in .env")
    exit(1)
    
headers = {"Authorization": f"Bearer {groq_key}"}
res = requests.get("https://api.groq.com/openai/v1/models", headers=headers)
if res.status_code != 200:
    print("❌ Failed to fetch Groq models")
    exit(1)
    
models = [m['id'] for m in res.json().get('data', [])]

# Find the best 70b model
target_model = None
for m in models:
    if '70b' in m.lower() and 'tool' not in m.lower():
        target_model = m
        break

if not target_model:
    target_model = models[0]
    
print(f"✅ Active 70B Model Found: {target_model}")

# Patch config.py
print("⚙️  Wiring PRO node to the dynamic Groq endpoint...")
with open("src/config.py", "r", encoding="utf-8") as f:
    config_content = f.read()

config_content = re.sub(r'PRO = ".*?"', f'PRO = "groq/{target_model}"', config_content)

with open("src/config.py", "w", encoding="utf-8") as f:
    f.write(config_content)
    
print("✅ Success! Config updated.")
print("▶️  Running test_llm.py...\n")
os.system("python test_llm.py")
