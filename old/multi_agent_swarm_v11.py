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
SIGNAL_LOG = "signals_log.csv"

model = PPO.load("ppo_trading_model_v6", device="cpu")
print("✅ Multi-Agent Swarm v11 – Sentiment + Stats + Voorbereiding Retraining")
print("   • Actor: PPO")
print("   • Oracle: Regime Detector")
print("   • Critic: Devil’s Advocate + Sentiment Stub")
print("   Markt gesloten → we bouwen verder op mock data\n")

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

def get_sentiment_stub():
    """Sentiment Stub – later vervangen door echte X semantic search + news"""
    return np.random.choice(["BULLISH", "BEARISH", "NEUTRAL"], p=[0.35, 0.30, 0.35])

def critic_agent(actor_signal, regime, atr_pct, sentiment, signals_history):
    veto_reasons = []
    
    # 1. BUY-bias (laatste 15 final signals)
    if len(signals_history) >= 5:
        recent_buys = sum(1 for s in signals_history[-15:] if "BUY" in s)
        if actor_signal == "BUY" and recent_buys >= 8:
            veto_reasons.append("BUY-bias te sterk")
    
    # 2. Regime mismatch
    if regime == "HIGH_VOLATILITY 🔥" and actor_signal in ["BUY", "SELL"]:
        veto_reasons.append("Te riskant in high-vol")
    
    # 3. Sentiment mismatch
    if sentiment == "BEARISH" and actor_signal == "BUY":
        veto_reasons.append("Sentiment bearish → geen BUY")
    
    # 4. ATR extremum
    if atr_pct > 0.25:
        veto_reasons.append("ATR te extreem")
    
    if veto_reasons:
        final_signal = "HOLD (Critic VETO)"
        print(f"   ❌ Critic VETO: {', '.join(veto_reasons)}")
    else:
        final_signal = actor_signal
        print("   ✅ Critic APPROVED")
    
    # Log voor retraining
    pd.DataFrame([{"timestamp": datetime.now(), "actor": actor_signal, "final": final_signal, "regime": regime, "sentiment": sentiment}]).to_csv(SIGNAL_LOG, mode="a", header=not os.path.exists(SIGNAL_LOG), index=False)
    
    return final_signal

# === V11 SWARM LOOP ===
if __name__ == "__main__":
    print("🚀 Multi-Agent Swarm v11 actief (Ctrl+C om te stoppen)\n")
    
    hist_df = yf.Ticker("MES=F").history(period="5d", interval="5m")[['Close', 'Volume']].reset_index()
    hist_df.columns = ['timestamp', 'last', 'volume']
    
    signals_history = []
    
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
            
            # Oracle + Sentiment
            regime, atr_pct = regime_oracle(combined)
            sentiment = get_sentiment_stub()
            
            # Critic
            final_signal = critic_agent(actor_signal, regime, atr_pct, sentiment, signals_history)
            signals_history.append(final_signal)
            
            print(f"   📈 Regime Oracle: {regime} (ATR {atr_pct:.3f}%)")
            print(f"   🧠 Actor (PPO): {actor_signal}")
            print(f"   📰 Sentiment Stub: {sentiment}")
            print(f"   🛡️  Final Signal na Critic: **{final_signal}**")
            print(f"   📊 Prijs: {quote['last']:.2f} | Rij: {len(live_df)}\n")
            
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n🛑 Swarm gestopt. v11 Architectuur staat nu klaar voor echte sentiment + retraining.")