import pandas as pd
import numpy as np
from datetime import datetime
import time
import os

EXTERNAL_EDGE_FILE = "external_edge_intelligence.csv"
print("📊 lumina_technical_analyst_v1 gestart – detecteert patterns elke 10 min")

while True:
    try:
        if os.path.exists("market_data_log.csv"):
            df = pd.read_csv("market_data_log.csv").tail(200)
            if len(df) > 50:
                price = df['last'].iloc[-1]
                support = df['last'].rolling(50).min().iloc[-1]
                resistance = df['last'].rolling(50).max().iloc[-1]
                pattern = "BUY" if price < support * 1.002 else "SELL" if price > resistance * 0.998 else "HOLD"
                confidence = 75 if abs(price - support) < 5 else 55
                row = {
                    "timestamp": datetime.now(),
                    "news_impact_score": 1.5,
                    "predicted_direction": "NEUTRAL",
                    "pattern_signal": pattern,
                    "confidence": confidence
                }
                pd.DataFrame([row]).to_csv(EXTERNAL_EDGE_FILE, mode="a", header=not os.path.exists(EXTERNAL_EDGE_FILE), index=False)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Technical Analyst: {pattern} (conf {confidence}%)")
    except Exception as e:
        print(f"Technical Analyst error (veilig): {e}")
    time.sleep(600)