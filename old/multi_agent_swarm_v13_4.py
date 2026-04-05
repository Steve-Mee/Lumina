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

# Automatische log-creatie
if not os.path.exists(SIGNAL_LOG):
    pd.DataFrame(columns=["timestamp", "actor", "final", "regime", "sentiment"]).to_csv(SIGNAL_LOG, index=False)
    print("✅ signals_log.csv automatisch aangemaakt")

model = PPO.load("ppo_trading_model_v6", device="cpu")
print("✅ Multi-Agent Swarm v13.4 – Volledige Grok Meta-Critic actief")

def grok_meta_critic():
    """Echte Grok analyse van signals_log.csv"""
    try:
        df = pd.read_csv(SIGNAL_LOG)
        if len(df) < 20:
            print("   (te weinig data voor Grok analyse)")
            return
        recent = df.tail(30).to_string()
        payload = {
            "model": "grok-4.20-0309-reasoning",
            "messages": [
                {"role": "system", "content": "Je bent Chief Strategist van de #1 NinjaTrader AI trading bot. Analyseer de laatste 30 signals. Geef concrete, actionable advies: welke Critic-regels moeten beter, hoe fixen we BUY-bias, en wat moet de PPO retrainen? Houd het kort en bruikbaar."},
                {"role": "user", "content": f"Signalen log:\n{recent}\nWat moet beter?"}
            ]
        }
        r = requests.post("https://api.x.ai/v1/chat/completions",
                          headers={"Authorization": f"Bearer {XAI_KEY}", "Content-Type": "application/json"},
                          json=payload, timeout=20)
        if r.status_code == 200:
            advice = r.json()["choices"][0]["message"]["content"]
            print(f"   🧠 Grok Meta-Critic advies:\n{advice}\n")
        else:
            print(f"   Grok call mislukt ({r.status_code})")
    except Exception as e:
        print(f"   Grok call mislukt: {e}")

print("\n🚀 v13.4 Hybride Swarm actief (Ctrl+C om te stoppen)\n")

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

if __name__ == "__main__":
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
            
            obs = get_obs(combined)
            action = int(model.predict(obs, deterministic=True)[0].item())
            actor_signal = {0: "HOLD", 1: "BUY", 2: "SELL"}[action]
            regime, atr_pct = regime_oracle(combined)
            
            veto = []
            if regime == "HIGH_VOLATILITY 🔥" and actor_signal in ["BUY", "SELL"]:
                veto.append("Te riskant in high-vol")
            if len(signals_history) >= 8 and signals_history[-8:].count("BUY") >= 6 and actor_signal == "BUY":
                veto.append("BUY-bias te sterk")
            
            final_signal = "HOLD (Critic VETO)" if veto else actor_signal
            if veto:
                print(f"   ❌ Critic VETO: {', '.join(veto)}")
            else:
                print("   ✅ Critic APPROVED")
            
            signals_history.append(final_signal)
            
            # Log naar signals_log voor Grok
            pd.DataFrame([{"timestamp": datetime.now(), "actor": actor_signal, "final": final_signal, "regime": regime, "sentiment": "NEUTRAL"}]).to_csv(SIGNAL_LOG, mode="a", header=False, index=False)
            
            print(f"   📈 Regime Oracle: {regime} (ATR {atr_pct:.3f}%)")
            print(f"   🧠 Actor (PPO): {actor_signal}")
            print(f"   🛡️  Final Signal: **{final_signal}**")
            print(f"   📊 Prijs: {quote['last']:.2f} | Rij: {len(live_df)}\n")
            
            counter += 1
            if counter % 50 == 0:
                print("   🔄 Grok-4.20-0309-reasoning activeert...")
                grok_meta_critic()
            
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n🛑 v13.4 gestopt.")