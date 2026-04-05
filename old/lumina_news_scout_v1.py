import requests
import pandas as pd
from datetime import datetime
import time
import os

EXTERNAL_EDGE_FILE = "external_edge_intelligence.csv"
print("🌍 lumina_news_scout_v1 gestart – scant high-impact nieuws elke 30 min")

while True:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get("https://www.investing.com/economic-calendar/", headers=headers, timeout=10)
        impact_score = 3.0 if "High Volatility Expected" in r.text or "Red" in r.text else 1.5
        row = {
            "timestamp": datetime.now(),
            "news_impact_score": impact_score,
            "predicted_direction": "NEUTRAL",
            "pattern_signal": "HOLD",
            "confidence": 60.0
        }
        pd.DataFrame([row]).to_csv(EXTERNAL_EDGE_FILE, mode="a", header=not os.path.exists(EXTERNAL_EDGE_FILE), index=False)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] News Scout: high-impact score {impact_score} opgeslagen")
    except Exception as e:
        print(f"News Scout error (veilig): {e}")
    time.sleep(1800)