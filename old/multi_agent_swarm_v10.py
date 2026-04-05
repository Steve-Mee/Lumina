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
SIGNAL_LOG = "signals_log.csv"  # NIEUW: aparte log voor alle signals

model = PPO.load("ppo_trading_model_v6", device="cpu")
print("✅ Multi-Agent Swarm v10 gestart – Sterkere Critic + Signal Logging")
print("   • Actor: PPO")
print("   • Oracle: Regime Detector")
print("   • Critic: Verbeterde Devil’s Advocate (bias + history check)")
print("   Markt gesloten → we trainen de swarm verder op mock data\n")

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

def critic_agent(actor_signal, regime, atr_pct, current_price, signals_history):
    """Sterkere Critic – nu met bias-detectie op basis van laatste 15 signals"""
    veto_reasons = []
    
    # 1. BUY-bias check (laatste 15 signals)
    if len(signals_history) >= 5:
        recent_buys = signals_history[-15:].count("BUY")
        if actor_signal == "BUY" and recent_buys >= 8:
            veto_reasons.append("BUY-bias te sterk (8+ van laatste 15)")
    
    # 2. Regime mismatch (strenger dan v9.1)
    if regime == "HIGH_VOLATILITY 🔥" and actor_signal in ["BUY", "SELL"]:
        veto_reasons.append("Te riskant in high-vol")
    
    # 3. ATR extremum
    if atr_pct > 0.25:
        veto_reasons.append("ATR te extreem (>0.25%)")
    
    if veto_reasons:
        final_signal = "HOLD (Critic VETO)"
        print(f"   ❌ Critic VETO: {', '.join(veto_reasons)}")
    else:
        final_signal = actor_signal
        print("   ✅ Critic APPROVED")
    
    # Log signal voor toekomstige bias-detectie
    pd.DataFrame([{"timestamp": datetime.now(), "actor_signal": actor_signal, "final_signal": final_signal, "regime": regime}]).to_csv(SIGNAL_LOG, mode="a", header=not os.path.exists(SIGNAL_LOG), index=False)
    
    return final_signal

# === V10 SWARM LOOP ===
if __name__ == "__main__":
    print("🚀 Multi-Agent Swarm v10 actief (Ctrl+C om te stoppen)\n")
    
    hist_df = yf.Ticker("MES=F").history(period="5d", interval="5m")[['Close', 'Volume']].reset_index()
    hist_df.columns = ['timestamp', 'last', 'volume']
    
    signals_history = []  # houdt laatste signals bij voor Critic
    
    try:
        while True:
            quote = get_mock_quote()
            
            # Log quote
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
            final_signal = critic_agent(actor_signal, regime, atr_pct, quote["last"], signals_history)
            signals_history.append(final_signal)  # update history
            
            print(f"   📈 Regime Oracle: {regime} (ATR {atr_pct:.3f}%)")
            print(f"   🧠 Actor (PPO): {actor_signal}")
            print(f"   🛡️  Final Signal na Critic: **{final_signal}**")
            print(f"   📊 Prijs: {quote['last']:.2f} | Rij: {len(live_df)}\n")
            
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n🛑 Swarm gestopt. v10 Architectuur staat nu nog sterker vast.")