import requests
import pandas as pd
import json
from datetime import datetime
import time
import os
from dotenv import load_dotenv

load_dotenv()
XAI_KEY = os.getenv("XAI_API_KEY")
EXTERNAL_EDGE_FILE = "external_edge_intelligence.csv"
print("📈 lumina_macro_predictor_v1 gestart – Grok voorspelt richting elke 15 min")

while True:
    try:
        if not os.path.exists(EXTERNAL_EDGE_FILE):
            time.sleep(60)
            continue
        df = pd.read_csv(EXTERNAL_EDGE_FILE).tail(5)
        last_impact = df['news_impact_score'].mean()
        payload = {
            "model": "grok-4.20-0309-reasoning",
            "messages": [
                {"role": "system", "content": "Je bent LUMINA Macro Predictor. Geef ALLEEN JSON: {'predicted_direction': 'BULLISH/BEARISH/NEUTRAL', 'confidence': 0-100}"},
                {"role": "user", "content": f"Voorspel richting voor MES JUN 26 op basis van impact {last_impact:.1f} en laatste nieuws. Geef alleen JSON."}
            ]
        }
        r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=12)
        if r.status_code == 200:
            pred = json.loads(r.json()["choices"][0]["message"]["content"])
            row = df.iloc[-1].to_dict()
            row["predicted_direction"] = pred.get("predicted_direction", "NEUTRAL")
            row["confidence"] = pred.get("confidence", 65)
            pd.DataFrame([row]).to_csv(EXTERNAL_EDGE_FILE, mode="a", header=False, index=False)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Macro Predictor: {pred['predicted_direction']} (conf {pred['confidence']}%)")
    except Exception as e:
        print(f"Macro Predictor error (veilig): {e}")
    time.sleep(900)