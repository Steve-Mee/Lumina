import os
import requests
from dotenv import load_dotenv
import json
from datetime import datetime
import pandas as pd
import numpy as np

# Laad .env
load_dotenv()

SECRET = os.getenv("CROSS_TRADE_SECRET")
INSTRUMENT = os.getenv("INSTRUMENT")  # nu MES1!
BASE_URL = "https://app.crosstrade.io/v1/api"

headers = {
    "Authorization": f"Bearer {SECRET}",
    "Content-Type": "application/json"
}

def get_quote():
    """NIEUWE officiële endpoint (niet deprecated)"""
    url = f"{BASE_URL}/market/quote"
    params = {"instrument": INSTRUMENT}
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ {datetime.now()} | {INSTRUMENT} LIVE Quote:")
        print(f"   Last: {data.get('last')}")
        print(f"   Bid: {data.get('bid')} | Ask: {data.get('ask')}")
        print(f"   Volume: {data.get('volume')}")
        return data
    else:
        error_text = response.text.lower()
        if "market data unavailable" in error_text or response.status_code == 400:
            print(f"⚠️  Markt gesloten (weekend/nacht) of geen data – normaal gedrag.")
            print("   We schakelen over naar MOCK MODE voor ontwikkeling.")
            return get_mock_quote()
        else:
            print(f"❌ Onverwachte error {response.status_code}: {response.text}")
            return None

def get_mock_quote():
    """Mock data voor weekends → jij kunt nu al verder ontwikkelen"""
    mock = {
        "instrument": INSTRUMENT,
        "last": 5280.50 + np.random.uniform(-10, 10),
        "bid": 5280.00,
        "ask": 5281.00,
        "volume": int(150000 + np.random.uniform(-20000, 20000)),
        "mock": True
    }
    print(f"   MOCK Last: {mock['last']:.2f} | Volume: {mock['volume']}")
    return mock

def log_quote_to_csv(quote_data):
    """Eerste data logger – basis voor RL later"""
    df = pd.DataFrame([{
        "timestamp": datetime.now(),
        "instrument": quote_data.get("instrument"),
        "last": quote_data.get("last"),
        "volume": quote_data.get("volume"),
        "mock": quote_data.get("mock", False)
    }])
    filename = "market_data_log.csv"
    df.to_csv(filename, mode="a", header=not os.path.exists(filename), index=False)
    print(f"   📊 Gelogd naar {filename}")

def detect_simple_regime(df):
    """Eerste regime detection (stub) – leert je hoe we later multi-agent regimes doen"""
    if len(df) < 5:
        print("   🔄 Te weinig data voor regime detectie (mock data gebruikt)")
        return "UNKNOWN (nog opbouwen)"
    
    recent_vol = df["volume"].rolling(5).std().iloc[-1]
    price_change = df["last"].pct_change().std()
    
    if recent_vol > 50000 or price_change > 0.002:
        regime = "HIGH_VOL (agressief traden)"
    else:
        regime = "LOW_VOL (conservatief traden)"
    
    print(f"   📈 Huidig regime: {regime}")
    return regime

# === RUN DE TESTS ===
if __name__ == "__main__":
    print("🚀 CrossTrade Connector v2 – Lokaal op PC")
    print(f"Instrument: {INSTRUMENT}\n")
    
    quote = get_quote()
    if quote:
        log_quote_to_csv(quote)
        
        # Laad bestaande data voor regime
        try:
            df = pd.read_csv("market_data_log.csv")
            detect_simple_regime(df)
        except:
            detect_simple_regime(pd.DataFrame())  # eerste run
    
    print("\n✅ Test klaar! Run dit script gerust meerdere keren (ook in weekend).")