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
INSTRUMENT = os.getenv("INSTRUMENT")  # MES1!
BASE_URL = "https://app.crosstrade.io/v1/api"

headers = {"Authorization": f"Bearer {SECRET}", "Content-Type": "application/json"}
CSV_FILE = "market_data_log.csv"

def get_quote():
    """Live via CrossTrade of mock"""
    url = f"{BASE_URL}/market/quote"
    params = {"instrument": INSTRUMENT}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ LIVE {datetime.now().strftime('%H:%M:%S')} | {INSTRUMENT} Last: {data.get('last')}")
            return data
    except:
        pass
    print(f"⚠️ Markt gesloten → MOCK MODE")
    return get_mock_quote()

def get_mock_quote():
    return {"instrument": INSTRUMENT, "last": round(5280 + np.random.normal(0, 8), 2), "volume": int(140000 + np.random.normal(0, 15000)), "mock": True}

def load_historical_bars(days=5):
    """NIEUWE laag: echte historische 5-min bars via yfinance (MES=F = Micro E-mini S&P)"""
    print(f"📥 Ophalen historische data ({days} dagen 5-min bars)...")
    ticker = yf.Ticker("MES=F")  # continuous Micro E-mini S&P futures
    df = ticker.history(period=f"{days}d", interval="5m")
    if df.empty:
        print("   ⚠️ yfinance tijdelijk geen data – gebruik mock history")
        return pd.DataFrame()
    df = df[['Close', 'Volume']].reset_index()
    df.columns = ['timestamp', 'last', 'volume']
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    print(f"   ✅ {len(df)} historische bars geladen (laatste close: {df['last'].iloc[-1]:.2f})")
    return df

def calculate_atr_regime(df, period=14):
    """Verbeterde regime met echte ATR (Average True Range) – leert je echte quant features"""
    if len(df) < period + 10:
        return "OPBOUWEN (nog te weinig data)", 0.0
    
    df['returns'] = df['last'].pct_change()
    df['high_low'] = df['last'].rolling(2).max() - df['last'].rolling(2).min()  # simpele range
    df['atr'] = df['high_low'].rolling(period).mean()
    current_atr_pct = (df['atr'].iloc[-1] / df['last'].iloc[-1]) * 100
    avg_vol = df['volume'].rolling(10).mean().iloc[-1]
    
    if current_atr_pct > 0.18 or avg_vol > 160000:
        regime = "HIGH_VOLATILITY 🔥 → agressiever + kleinere posities"
    elif current_atr_pct < 0.09:
        regime = "LOW_VOLATILITY 🌿 → conservatief + grotere posities"
    else:
        regime = "NORMAL_MARKET ⚖️ → standaard regels"
    
    print(f"   📈 Regime: {regime} (ATR={current_atr_pct:.3f}%, avg_vol={avg_vol:,.0f})")
    return regime, current_atr_pct

def get_sentiment_stub():
    """Eerste sentiment laag (stub) – later vervangen door echte X + news API"""
    # Mock voor nu – in v5 integreren we echte X semantic search + nieuws
    sentiments = ["bullish", "bearish", "neutral"]
    sentiment = np.random.choice(sentiments, p=[0.35, 0.25, 0.40])
    print(f"   📰 Sentiment stub: {sentiment.upper()} (later echte multi-bron analyse)")
    return sentiment

# === V4 DATA COLLECTOR ===
if __name__ == "__main__":
    print("🚀 Data Collector v4 – Lokaal + Historische bars + Sentiment")
    print(f"Instrument: {INSTRUMENT} | Druk Ctrl+C om te stoppen\n")
    
    # Laad historische data één keer bij start
    hist_df = load_historical_bars(days=5)
    
    try:
        while True:
            quote = get_quote()
            if quote:
                # Log live/mock
                row = {"timestamp": datetime.now(), "instrument": quote.get("instrument"), "last": quote.get("last"), "volume": quote.get("volume"), "mock": quote.get("mock", False)}
                pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
                
                # Combineer live + historical voor regime
                live_df = pd.read_csv(CSV_FILE)
                combined = pd.concat([hist_df, live_df[['timestamp', 'last', 'volume']]], ignore_index=True)
                
                regime, atr = calculate_atr_regime(combined)
                get_sentiment_stub()
                
                print(f"   📊 Live rij {len(live_df)} | Laatste prijs: {quote.get('last'):.2f}\n")
            
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n🛑 Gestopt. Data + historische bars klaar voor RL-training!")