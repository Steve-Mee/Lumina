import os
import requests
import time
import yfinance as yf
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from datetime import datetime

# Laad .env
load_dotenv()

SECRET = os.getenv("CROSS_TRADE_SECRET")
INSTRUMENT = os.getenv("INSTRUMENT")
BASE_URL = "https://app.crosstrade.io/v1/api"
CSV_FILE = "market_data_log.csv"

headers = {"Authorization": f"Bearer {SECRET}", "Content-Type": "application/json"}

def get_quote():
    url = f"{BASE_URL}/market/quote"
    params = {"instrument": INSTRUMENT}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ LIVE {datetime.now().strftime('%H:%M:%S')} | Last: {data.get('last')}")
            return data
    except:
        pass
    print(f"⚠️ Markt gesloten → MOCK MODE")
    return get_mock_quote()

def get_mock_quote(base_price=5280):
    """Mock nu dynamisch afgestemd op historische laatste prijs"""
    return {
        "instrument": INSTRUMENT,
        "last": round(base_price + np.random.normal(0, 8), 2),
        "volume": int(140000 + np.random.normal(0, 15000)),
        "mock": True
    }

def load_historical_bars(days=5):
    print(f"📥 Ophalen {days} dagen 5-min bars...")
    ticker = yf.Ticker("MES=F")
    df = ticker.history(period=f"{days}d", interval="5m")
    if df.empty:
        print("   ⚠️ yfinance geen data – mock history")
        return pd.DataFrame()
    df = df[['Close', 'Volume']].reset_index()
    df.columns = ['timestamp', 'last', 'volume']
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    print(f"   ✅ {len(df)} bars geladen | Laatste close: {df['last'].iloc[-1]:.2f}")
    return df

def safe_log_to_csv(row):
    """ROBUSTE write – voorkomt PermissionError voor altijd"""
    try:
        pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
        print(f"   📊 Gelogd (rij {len(pd.read_csv(CSV_FILE))})")
    except PermissionError:
        print("   ❌ CSV open in Excel! Sluit het bestand en druk op Enter om door te gaan...")
        input("   Druk Enter als CSV gesloten is...")
        safe_log_to_csv(row)  # probeer opnieuw
    except Exception as e:
        print(f"   ❌ Onverwachte schrijffout: {e}")

def calculate_atr_regime(df, period=14):
    if len(df) < period + 10:
        return "OPBOUWEN", 0.0
    df['returns'] = df['last'].pct_change()
    df['high_low'] = df['last'].rolling(2).max() - df['last'].rolling(2).min()
    df['atr'] = df['high_low'].rolling(period).mean()
    atr_pct = (df['atr'].iloc[-1] / df['last'].iloc[-1]) * 100
    avg_vol = df['volume'].rolling(10).mean().iloc[-1]
    
    if atr_pct > 0.18 or avg_vol > 160000:
        regime = "HIGH_VOLATILITY 🔥 → agressiever + kleinere posities"
    elif atr_pct < 0.09:
        regime = "LOW_VOLATILITY 🌿 → conservatief + grotere posities"
    else:
        regime = "NORMAL_MARKET ⚖️ → standaard regels"
    print(f"   📈 Regime: {regime} (ATR={atr_pct:.3f}%, vol={avg_vol:,.0f})")
    return regime, atr_pct

def simple_sentiment_and_signal(df):
    """Eerste echte brain stub: trend + random sentiment → trading signal"""
    if len(df) < 20:
        return "NEUTRAL", "WACHTEN"
    recent = df['last'].iloc[-10:].mean()
    older = df['last'].iloc[-20:-10].mean()
    trend = "BULLISH" if recent > older else "BEARISH"
    sentiment = np.random.choice(["BULLISH", "BEARISH", "NEUTRAL"], p=[0.4, 0.3, 0.3])
    signal = "BUY" if trend == "BULLISH" and sentiment in ["BULLISH", "NEUTRAL"] else \
             "SELL" if trend == "BEARISH" and sentiment in ["BEARISH", "NEUTRAL"] else "HOLD"
    print(f"   🧠 Brain: Trend={trend} | Sentiment={sentiment} → Signal={signal}")
    return sentiment, signal

# === V5 DATA COLLECTOR + EERSTE BRAIN ===
if __name__ == "__main__":
    print("🚀 Data Collector v5 – ROBUST + Dynamische mock + Eerste Brain")
    print(f"Instrument: {INSTRUMENT} | Ctrl+C om te stoppen\n")
    
    hist_df = load_historical_bars()
    last_hist_price = hist_df['last'].iloc[-1] if not hist_df.empty else 5280
    
    try:
        while True:
            quote = get_quote()
            if quote:
                # Dynamische mock base op historische prijs
                if quote.get("mock"):
                    quote["last"] = round(last_hist_price + np.random.normal(0, 8), 2)
                
                row = {
                    "timestamp": datetime.now(),
                    "instrument": quote.get("instrument"),
                    "last": quote.get("last"),
                    "volume": quote.get("volume"),
                    "mock": quote.get("mock", False)
                }
                safe_log_to_csv(row)
                
                live_df = pd.read_csv(CSV_FILE)
                combined = pd.concat([hist_df, live_df[['timestamp', 'last', 'volume']]], ignore_index=True)
                
                regime, atr = calculate_atr_regime(combined)
                sentiment, signal = simple_sentiment_and_signal(combined)
                
                print(f"   📊 Live rij {len(live_df)} | Prijs: {quote.get('last'):.2f} | Signal: {signal}\n")
            
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n🛑 Gestopt. Data + eerste brain klaar voor RL!")