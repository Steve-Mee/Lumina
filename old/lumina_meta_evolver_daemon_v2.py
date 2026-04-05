import time
import pandas as pd
import requests
import json
import os
from dotenv import load_dotenv
from datetime import datetime
load_dotenv()
XAI_KEY = os.getenv("XAI_API_KEY")
print("🌌 lumina_meta_evolver_daemon_v2 gestart – Grok-4.20-0309-reasoning met call throttle")
while True:
    try:
        log_df = pd.read_csv("signals_log.csv").tail(300)
        summary = f"Sharpe: {log_df['nexus'].mean():.2f} | Cycles: {len(log_df)}"
        if time.time() % 900 > 30:  # max 1 call per 15 min
            payload = {"model": "grok-4.20-0309-reasoning", "messages": [{"role": "system", "content": "Geef ALLEEN JSON met nieuwe node code"}, {"role": "user", "content": summary}]}
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=15)
            if r.status_code == 200:
                code = json.loads(r.json()["choices"][0]["message"]["content"])["code"]
                with open("active_mutation.py", "w") as f:
                    f.write(code)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Evolver v2: nieuwe mutatie geschreven")
    except:
        pass
    time.sleep(900)