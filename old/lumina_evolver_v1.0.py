import os
import time
import pandas as pd
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
XAI_KEY = os.getenv("XAI_API_KEY")
SIGNAL_LOG = "signals_log.csv"
MUTATIONS_DIR = "lumina_mutations"
os.makedirs(MUTATIONS_DIR, exist_ok=True)
ACTIVE_MUTATION = "active_mutation.py"
print("🌌 lumina_evolver_v1.0 gestart – parallelle self-evolutie daemon")
while True:
    try:
        if not os.path.exists(SIGNAL_LOG):
            time.sleep(60)
            continue
        log_df = pd.read_csv(SIGNAL_LOG).tail(300)
        summary = f"Sharpe: {log_df['nexus'].mean():.2f} | Cycles: {len(log_df)}"
        payload = {
            "model": "grok-4.20-0309-reasoning",
            "messages": [
                {"role": "system", "content": "Je bent LUMINA's Self-Code Mutation Engine. Geef ALLEEN JSON: {\"description\": \"...\", \"code\": \"def nieuwe_node(state: TradingState) -> TradingState: ...\"}"},
                {"role": "user", "content": f"Maak 1 nieuwe oracle of veto die Sharpe >2.5 brengt.\nSamenvatting: {summary}"}
            ]
        }
        r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=15)
        if r.status_code == 200:
            suggestion = json.loads(r.json()["choices"][0]["message"]["content"])
            code = suggestion["code"]
            desc = suggestion["description"]
            with open(ACTIVE_MUTATION, "w") as f:
                f.write(f'# === AUTO GENERATED MUTATION {datetime.now()} ===\n# {desc}\n\n{code}\n')
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 Nieuwe mutatie geschreven naar active_mutation.py → trader laadt automatisch!")
    except Exception as e:
        print(f"⚠️ Evolver error (veilig): {e}")
    time.sleep(300)  # elke 5 minuten een nieuwe evolutie-poging