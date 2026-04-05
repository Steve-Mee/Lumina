import os
import time
import yfinance as yf
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from datetime import datetime
from stable_baselines3 import PPO

load_dotenv()
INSTRUMENT = os.getenv("INSTRUMENT")
CSV_FILE = "market_data_log.csv"

# Laad Actor (PPO)
model = PPO.load("ppo_trading_model_v6", device="cpu")
print("✅ Multi-Agent Swarm v9.1 gestart")
print("   • Actor: PPO (beslissingen)")
print("   • Critic: Devil’s Advocate (veto checks)")
print("   • Oracle: Regime Detector")
print("   Markt gesloten → we trainen critic op mock data\n")

def get_mock_quote():
    return {"last": round(6559 + np.random.normal(0, 8), 2), "volume": int(140000 + np.random.normal(0, 15000))}

def get_obs(df):
    if len(df) < 20:
        return np.zeros(5, dtype=np.float32)
    row = df.iloc[-1]
    price = row['last']
    volume = row['volume']
    atr = abs(price - df['last'].iloc[-2]) * 100 / price if len(df) > 1 else 0.0
    trend = 1 if price > df['last'].iloc[-20:-10].mean() else -1
    return np.array([price/1000, volume/100000, atr, trend, 0], dtype=np.float32)

def regime_oracle(df):
    """Regime Oracle Agent"""
    if len(df) < 20:
        return "OPBOUWEN", 0.0
    returns = df['last'].pct_change()
    atr = returns.rolling(14).std() * 100
    avg_vol = df['volume'].rolling(10).mean().iloc[-1]
    atr_pct = atr.iloc[-1]
    if atr_pct > 0.18 or avg_vol > 160000:
        return "HIGH_VOLATILITY 🔥", atr_pct
    elif atr_pct < 0.09:
        return "LOW_VOLATILITY 🌿", atr_pct
    return "NORMAL_MARKET ⚖️", atr_pct

def critic_agent(actor_signal, regime, atr_pct, current_price):
    """Devil’s Advocate Critic – veto logic (dit is wat ons #1 maakt)"""
    veto_reasons = []
    
    # Regel 1: Bias fix – te veel BUY achter elkaar
    if actor_signal == "BUY" and len(pd.read_csv(CSV_FILE)) > 10:
        recent_signals = pd.read_csv(CSV_FILE).tail(10)  # later echte signal-log
        if "BUY" in recent_signals.values:  # stub voor nu
            veto_reasons.append("BUY-bias te sterk")
    
    # Regel 2: Regime mismatch
    if regime == "HIGH_VOLATILITY 🔥" and actor_signal == "BUY":
        veto_reasons.append("Te riskant in high-vol")
    
    # Regel 3: ATR te hoog
    if atr_pct > 0.25:
        veto_reasons.append("ATR te extreem")
    
    if veto_reasons:
        final_signal = "HOLD (Critic VETO)"
        print(f"   ❌ Critic VETO: {', '.join(veto_reasons)}")
    else:
        final_signal = actor_signal
        print("   ✅ Critic APPROVED")
    
    return final_signal

# === MULTI-AGENT SWARM LOOP ===
if __name__ == "__main__":
    print("🚀 Multi-Agent Swarm actief (Ctrl+C om te stoppen)\n")
    
    hist_df = yf.Ticker("MES=F").history(period="5d", interval="5m")[['Close', 'Volume']].reset_index()
    hist_df.columns = ['timestamp', 'last', 'volume']
    
    try:
        while True:
            quote = get_mock_quote()
            
            # Log
            row = {"timestamp": datetime.now(), "instrument": INSTRUMENT, "last": quote["last"], "volume": quote["volume"], "mock": True}
            pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
            
            live_df = pd.read_csv(CSV_FILE)
            combined = pd.concat([hist_df[['last', 'volume']], live_df[['last', 'volume']]], ignore_index=True)
            
            # Actor
            obs = get_obs(combined)
            action_array, _ = model.predict(obs, deterministic=True)
            action = int(action_array.item())
            action_map = {0: "HOLD", 1: "BUY", 2: "SELL"}
            actor_signal = action_map[action]
            
            # Oracle
            regime, atr_pct = regime_oracle(combined)
            
            # Critic
            final_signal = critic_agent(actor_signal, regime, atr_pct, quote["last"])
            
            print(f"   📈 Regime Oracle: {regime} (ATR {atr_pct:.3f}%)")
            print(f"   🧠 Actor (PPO): {actor_signal}")
            print(f"   🛡️  Final Signal na Critic: **{final_signal}**")
            print(f"   📊 Prijs: {quote['last']:.2f} | Rij: {len(live_df)}\n")
            
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n🛑 Swarm gestopt. Architectuur staat nu vast.")