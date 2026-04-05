import os
import requests
import time
import yfinance as yf
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from datetime import datetime
from stable_baselines3 import PPO

# Laad .env + model
load_dotenv()
SECRET = os.getenv("CROSS_TRADE_SECRET")
INSTRUMENT = os.getenv("INSTRUMENT")
BASE_URL = "https://app.crosstrade.io/v1/api"
CSV_FILE = "market_data_log.csv"

headers = {"Authorization": f"Bearer {SECRET}", "Content-Type": "application/json"}

# Laad model op CPU (stabiel + snel)
model = PPO.load("ppo_trading_model_v6", device="cpu")
print("✅ PPO Model geladen (CPU) – klaar voor live voorspellingen!")

DRY_RUN = True  # Zet op False als je echte test-orders wilt plaatsen (SIM)

def get_quote():
    url = f"{BASE_URL}/market/quote"
    params = {"instrument": INSTRUMENT}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            print(f"✅ LIVE {datetime.now().strftime('%H:%M:%S')} | Last: {data.get('last')}")
            return data
    except:
        pass
    print("⚠️ Markt gesloten → MOCK MODE")
    return {"instrument": INSTRUMENT, "last": round(6559 + np.random.normal(0, 8), 2), "volume": int(140000 + np.random.normal(0, 15000)), "mock": True}

def get_obs(df):
    """Veilige observatie voor RL-agent"""
    if len(df) < 20:
        return np.zeros(5, dtype=np.float32)
    row = df.iloc[-1]
    price = row['last']
    volume = row['volume']
    atr = abs(price - df['last'].iloc[-2]) * 100 / price if len(df) > 1 else 0.0
    trend = 1 if price > df['last'].iloc[-20:-10].mean() else -1
    position = 0
    return np.array([price/1000, volume/100000, atr, trend, position], dtype=np.float32)

def calculate_regime(df):
    if len(df) < 20:
        return "OPBOUWEN"
    returns = df['last'].pct_change()
    atr = returns.rolling(14).std() * 100
    avg_vol = df['volume'].rolling(10).mean().iloc[-1]
    atr_pct = atr.iloc[-1]
    if atr_pct > 0.18 or avg_vol > 160000:
        return "HIGH_VOLATILITY 🔥"
    elif atr_pct < 0.09:
        return "LOW_VOLATILITY 🌿"
    return "NORMAL_MARKET ⚖️"

# === V8 LIVE TRADER MET PPO BRAIN ===
if __name__ == "__main__":
    print("🚀 Live Trader v8 – Gefixt + PPO AI Brain + DRY_RUN")
    print(f"Instrument: {INSTRUMENT} | DRY_RUN={DRY_RUN} | Ctrl+C om te stoppen\n")
    
    hist_df = yf.Ticker("MES=F").history(period="5d", interval="5m")[['Close', 'Volume']].reset_index()
    hist_df.columns = ['timestamp', 'last', 'volume']
    
    try:
        while True:
            quote = get_quote()
            if quote:
                # Log quote
                row = {"timestamp": datetime.now(), "instrument": quote.get("instrument"), "last": quote.get("last"), "volume": quote.get("volume"), "mock": quote.get("mock", False)}
                pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
                
                live_df = pd.read_csv(CSV_FILE)
                combined = pd.concat([hist_df[['last', 'volume']], live_df[['last', 'volume']]], ignore_index=True)
                
                obs = get_obs(combined)
                action_array, _ = model.predict(obs, deterministic=True)
                action = int(action_array.item() if isinstance(action_array, np.ndarray) else action_array)  # FIX HIER
                
                regime = calculate_regime(combined)
                action_map = {0: "HOLD", 1: "BUY", 2: "SELL"}
                signal = action_map[action]
                
                print(f"   📈 Regime: {regime}")
                print(f"   🧠 PPO AI Signal: **{signal}**")
                print(f"   📊 Prijs: {quote.get('last'):.2f} | Rij: {len(live_df)}\n")
                
                if signal != "HOLD" and not DRY_RUN:
                    print(f"   🔥 ECHTE ORDER zou geplaatst worden: {signal} (DRY_RUN=False)")
            
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n🛑 Live Trader gestopt. Model blijft getraind!")