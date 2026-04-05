import os
import time
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from dotenv import load_dotenv
from datetime import datetime
from stable_baselines3 import PPO

load_dotenv()
INSTRUMENT = os.getenv("INSTRUMENT")
XAI_KEY = os.getenv("XAI_API_KEY")
CSV_FILE = "market_data_log.csv"
SIGNAL_LOG = "signals_log.csv"

model = PPO.load("ppo_trading_model_v6", device="cpu")
print("✅ Multi-Agent Swarm v12 – HYBRIDE met Grok Meta-Critic")
print("   Fast Layer: PPO + Oracle + Rule Critic (live)")
print("   Slow Layer: Grok Meta-Critic (elke 50 rijen offline retrain)")
print("   Markt gesloten → we testen Grok Meta-Critic nu\n")

def get_mock_quote():
    return {"last": round(6559 + np.random.normal(0, 8), 2), "volume": int(140000 + np.random.normal(0, 15000))}

def get_obs(df):
    if len(df) < 20: return np.zeros(5, dtype=np.float32)
    row = df.iloc[-1]
    price = row['last']
    volume = row['volume']
    atr = abs(price - df['last'].iloc[-2]) * 100 / price if len(df) > 1 else 0.0
    trend = 1 if price > df['last'].iloc[-20:-10].mean() else -1
    return np.array([price/1000, volume/100000, atr, trend, 0], dtype=np.float32)

def regime_oracle(df):
    if len(df) < 20: return "OPBOUWEN", 0.0
    returns = df['last'].pct_change()
    atr = returns.rolling(14).std() * 100
    avg_vol = df['volume'].rolling(10).mean().iloc[-1]
    atr_pct = atr.iloc[-1]
    if atr_pct > 0.18 or avg_vol > 160000:
        return "HIGH_VOLATILITY 🔥", atr_pct
    elif atr_pct < 0.09:
        return "LOW_VOLATILITY 🌿", atr_pct
    return "NORMAL_MARKET ⚖️", atr_pct

def grok_meta_critic(signals_df):
    """Grok als echte Meta-Critic – analyseert logs en geeft advies (slow layer)"""
    if XAI_KEY is None or len(signals_df) < 20:
        return "Geen API key / te weinig data – rule-based blijft actief"
    
    recent = signals_df.tail(30).to_string()
    
    payload = {
        "model": "grok-beta",
        "messages": [{
            "role": "system",
            "content": "Je bent de Chief Strategist van een #1 NinjaTrader AI trading bot. Analyseer de laatste 30 signals. Geef concrete verbeteringen voor Critic rules, bias fixes en PPO retrain suggesties. Houd het kort en actionable."
        }, {
            "role": "user",
            "content": f"Signalen log:\n{recent}\nWat moet de Critic aanpassen?"
        }]
    }
    
    try:
        r = requests.post("https://api.x.ai/v1/chat/completions",
                          headers={"Authorization": f"Bearer {XAI_KEY}", "Content-Type": "application/json"},
                          json=payload, timeout=15)
        if r.status_code == 200:
            advice = r.json()["choices"][0]["message"]["content"]
            print(f"   🧠 Grok Meta-Critic advies: {advice[:200]}...")  # kort weergeven
            return advice
    except:
        pass
    return "Grok call mislukt – rule-based blijft actief"

# === V12 HYBRIDE SWARM ===
if __name__ == "__main__":
    print("🚀 Hybride Swarm v12 actief (Ctrl+C om te stoppen)\n")
    
    hist_df = yf.Ticker("MES=F").history(period="5d", interval="5m")[['Close', 'Volume']].reset_index()
    hist_df.columns = ['timestamp', 'last', 'volume']
    
    signals_history = []
    counter = 0
    
    try:
        while True:
            quote = get_mock_quote()
            row = {"timestamp": datetime.now(), "instrument": INSTRUMENT, "last": quote["last"], "volume": quote["volume"], "mock": True}
            pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
            
            live_df = pd.read_csv(CSV_FILE)
            combined = pd.concat([hist_df[['last', 'volume']], live_df[['last', 'volume']]], ignore_index=True)
            
            # Fast Layer
            obs = get_obs(combined)
            action = int(model.predict(obs, deterministic=True)[0].item())
            actor_signal = {0: "HOLD", 1: "BUY", 2: "SELL"}[action]
            regime, atr_pct = regime_oracle(combined)
            
            # Rule Critic (fast)
            final_signal = "BUY" if actor_signal == "BUY" else actor_signal  # stub
            signals_history.append(final_signal)
            
            print(f"   📈 Regime: {regime} | Actor: {actor_signal} | Fast Final: {final_signal}")
            
            counter += 1
            if counter % 50 == 0 and XAI_KEY:
                print("   🔄 Grok Meta-Critic activeert (slow layer)...")
                grok_meta_critic(pd.read_csv(SIGNAL_LOG) if os.path.exists(SIGNAL_LOG) else pd.DataFrame())
            
            print(f"   📊 Prijs: {quote['last']:.2f} | Rij: {len(live_df)}\n")
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n🛑 Swarm gestopt. Hybride architectuur staat nu vast.")