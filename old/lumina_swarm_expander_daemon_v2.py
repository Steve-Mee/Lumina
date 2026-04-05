import time
import requests
import json
import pandas as pd
import os
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()
XAI_KEY = os.getenv("XAI_API_KEY")
AGENT_DIR = "lumina_agents"
os.makedirs(AGENT_DIR, exist_ok=True)
print("🌟 lumina_swarm_expander_daemon_v2 gestart – Grok-4.20-0309-reasoning")
while True:
    try:
        summary = "Huidige performance summary uit signals_log"
        if time.time() % 1200 > 60:
            payload = {"model": "grok-4.20-0309-reasoning", "messages": [{"role": "system", "content": "Genereer een volledige nieuwe agent script"}, {"role": "user", "content": summary}]}
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=20)
            if r.status_code == 200:
                result = json.loads(r.json()["choices"][0]["message"]["content"])
                filename = os.path.join(AGENT_DIR, result["filename"])
                with open(filename, "w") as f:
                    f.write(result["full_code"])
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Expander v2: nieuwe agent {filename} gemaakt!")
    except:
        pass
    time.sleep(1200)