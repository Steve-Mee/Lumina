import os
import requests
import time
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from datetime import datetime

# Laad .env
load_dotenv()

SECRET = os.getenv("CROSS_TRADE_SECRET")
INSTRUMENT = os.getenv("INSTRUMENT")  # MES1!
BASE_URL = "https://app.crosstrade.io/v1/api"

headers = {
    "Authorization": f"Bearer {SECRET}",
    "Content-Type": "application/json"
}

CSV_FILE = "market_data_log.csv"

def get_quote():
    """Probeer live quote, fallback naar mock"""
    url = f"{BASE_URL}/market/quote"
    params = {"instrument": INSTRUMENT}
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ LIVE {datetime.now().strftime('%H:%M:%S')} | {INSTRUMENT} Last: {data.get('last')}")
        return data
    else:
        print(f"⚠️ Markt gesloten → MOCK MODE")
        return get_mock_quote()

def get_mock_quote():
    """Verbeterde mock met realistische variatie"""
    mock = {
        "instrument": INSTRUMENT,
        "last": round(5280 + np.random.normal(0, 8), 2),
        "volume": int(140000 + np.random.normal(0, 15000)),
        "mock": True
    }
    return mock

def log_to_csv(quote):
    """Accumuleert data zonder dubbele headers"""
    row = {
        "timestamp": datetime.now(),
        "instrument": quote.get("instrument"),
        "last": quote.get("last"),
        "volume": quote.get("volume"),
        "mock": quote.get("mock", False)
    }
    df = pd.DataFrame([row])
    df.to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
    print(f"   📊 Gelogd (rij {len(pd.read_csv(CSV_FILE)) if os.path.exists(CSV_FILE) else 0})")

def calculate_regime(df):
    """Verbeterde regime detection – leert je echte feature engineering"""
    if len(df) < 10:
        return "OPBOUWEN (nog te weinig data)"
    
    # Simpele volatility (zoals ATR)
    df["returns"] = df["last"].pct_change()
    volatility = df["returns"].rolling(10).std() * 100  # in %
    avg_vol = volatility.iloc[-1]
    avg_volume = df["volume"].rolling(10).mean().iloc[-1]
    
    if avg_vol > 0.15 or avg_volume > 160000:
        regime = "HIGH_VOLATILITY 🔥 → agressiever traden + kleinere posities"
    elif avg_vol < 0.08:
        regime = "LOW_VOLATILITY 🌿 → conservatief traden + grotere posities"
    else:
        regime = "NORMAL_MARKET ⚖️ → standaard regels"
    
    print(f"   📈 Regime: {regime} (vol={avg_vol:.3f}%, avg_vol={avg_volume:,.0f})")
    return regime

def print_stats(df):
    """Basis statistieken zodat je leert wat de data vertelt"""
    if len(df) < 5:
        return
    print(f"   📊 Stats (laatste {len(df)} rijen):")
    print(f"      Gem. prijs: {df['last'].mean():.2f}")
    print(f"      Max prijs: {df['last'].max():.2f} | Min: {df['last'].min():.2f}")
    print(f"      Gem. volume: {df['volume'].mean():,.0f}")

# === DATA COLLECTOR LOOP ===
if __name__ == "__main__":
    print("🚀 Data Collector v3 – Lokaal op PC (draait door tot je Ctrl+C drukt)")
    print(f"Instrument: {INSTRUMENT} | Druk Ctrl+C om te stoppen\n")
    
    try:
        while True:
            quote = get_quote()
            if quote:
                log_to_csv(quote)
                
                df = pd.read_csv(CSV_FILE)
                regime = calculate_regime(df)
                print_stats(df)
            
            print("   ⏳ Wacht 5 seconden tot volgende quote...\n")
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n🛑 Collector gestopt. Data staat in market_data_log.csv")
        print("Volgende stap: we voegen historische bars + sentiment toe!")