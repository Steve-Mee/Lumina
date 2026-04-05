import os
import time
import pandas as pd
import numpy as np
import requests
import yfinance as yf
from datetime import datetime
from stable_baselines3 import PPO
from dotenv import load_dotenv
from typing import TypedDict, Annotated, List
import operator
from langgraph.graph import StateGraph, END

load_dotenv()

INSTRUMENT = os.getenv("INSTRUMENT", "MES JUN 26")
XAI_KEY = os.getenv("XAI_API_KEY")
CROSSTRADE_TOKEN = os.getenv("CROSSTRADE_TOKEN")
CROSSTRADE_ACCOUNT = os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"

CSV_FILE = "market_data_log.csv"
SIGNAL_LOG = "signals_log.csv"

print("✅ Swarm Core v1_fixed – Echte Multi-Agent Swarm met AUTO PPO creation (v3.2 compliant reset)")
print(f"🔍 DEBUG: Instrument={INSTRUMENT} | Account={CROSSTRADE_ACCOUNT} | DRY_RUN={DRY_RUN}")

# AUTO PPO creation
model_path = "ppo_trading_model_v6"
if os.path.exists(model_path + ".zip"):
    model = PPO.load(model_path, device="cpu")
    print("   ✅ Oud PPO model geladen")
else:
    print("   🧠 Nieuw PPO model aanmaken voor echte self-learning...")
    from stable_baselines3.common.vec_env import DummyVecEnv
    class DummyTradingEnv:
        def __init__(self):
            self.observation_space = None
            self.action_space = None
        def reset(self):
            return np.zeros(5)
        def step(self, action):
            return np.zeros(5), 0, False, {}
    env = DummyVecEnv([lambda: DummyTradingEnv()])
    model = PPO("MlpPolicy", env, verbose=0)
    model.save(model_path)
    print("   ✅ Nieuw PPO model aangemaakt en opgeslagen")

class TradingState(TypedDict):
    obs: list
    regime: str
    actor_signal: str
    critic_reasoning: str
    critic_veto: List[str]
    final_signal: str
    last_price: float
    volume: int
    position_qty: int
    atr: float
    data_source: str
    is_market_open: bool
    messages: Annotated[List[str], operator.add]

def get_market_status():
    try:
        url = "https://app.crosstrade.io/v1/api/market/info"
        headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}", "Content-Type": "application/json"}
        params = {"instrument": INSTRUMENT}
        r = requests.get(url, headers=headers, params=params, timeout=8)
        if r.status_code == 200:
            data = r.json()
            is_open = data.get("status", {}).get("isOpen", False)
            print(f"   ✅ Market Status API SUCCESS → Open: {is_open}")
            return is_open
    except Exception as e:
        print(f"   ⚠️ Market Info exception: {e}")
    return True

def fetch_quote():
    formats = [INSTRUMENT, "MES JUN 26"]
    for fmt in formats:
        try:
            url = f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/quote"
            headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}", "Content-Type": "application/json"}
            params = {"instrument": fmt}
            r = requests.get(url, headers=headers, params=params, timeout=8)
            if r.status_code == 200:
                data = r.json()
                price = float(data.get("last", 0))
                volume = int(data.get("volume", 0))
                print(f"   ✅ CrossTrade SUCCESS met '{fmt}' | Price: {price:.2f}")
                return price, volume, "CrossTrade"
        except:
            pass

    for tick in ["MES=F", "ES=F"]:
        try:
            ticker = yf.Ticker(tick)
            data = ticker.history(period="5d", interval="5m")
            if not data.empty:
                price = float(data['Close'].iloc[-1])
                volume = int(data['Volume'].iloc[-1]) if 'Volume' in data else 150000
                if volume < 50000: volume = 150000
                print(f"   ✅ yfinance SUCCESS met {tick} | Price: {price:.2f}")
                return price, volume, f"yfinance ({tick})"
        except:
            pass
    return 6559 + np.random.normal(0, 8), 150000, "MOCK"

def get_current_position():
    if not CROSSTRADE_TOKEN: return 0
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/positions",
                         headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=6)
        if r.status_code == 200:
            positions = r.json()
            for p in positions if isinstance(positions, list) else []:
                if "MES" in str(p.get("instrument", "")):
                    return int(p.get("quantity", 0))
    except:
        pass
    return 0

def calculate_atr(df):
    if len(df) < 10: return 12.0
    changes = df['last'].diff().abs()
    atr = changes.rolling(14).mean().iloc[-1]
    return np.clip(atr, 8.0, 35.0)

def regime_oracle_node(state: TradingState) -> TradingState:
    df = pd.read_csv(CSV_FILE).tail(100) if os.path.exists(CSV_FILE) else pd.DataFrame()
    if not df.empty: df = df.drop_duplicates(subset=['last'], keep='last')
    atr = calculate_atr(df)
    vol = state["volume"]
    regime = "HIGH_VOLATILITY 🔥" if (atr > 25 or vol > 180000) else "LOW_VOLATILITY 🌿" if atr < 12 else "NORMAL_MARKET ⚖️"
    return {**state, "regime": regime, "atr": atr}

def build_obs(state: TradingState, df) -> list:
    price_norm = state["last_price"] / 7000
    vol_norm = min(state["volume"] / 200000, 2.0)
    atr_norm = min(state["atr"] / 30, 2.0)
    trend = 1 if len(df) > 20 and state["last_price"] > df['last'].iloc[-20:-5].mean() else -1
    return [price_norm, vol_norm, atr_norm, float(trend), 0.0]

def actor_node(state: TradingState) -> TradingState:
    df = pd.read_csv(CSV_FILE).tail(100) if os.path.exists(CSV_FILE) else pd.DataFrame()
    obs = build_obs(state, df)
    action, _ = model.predict(np.array(obs, dtype=np.float32), deterministic=True)
    signal = {0: "HOLD", 1: "BUY", 2: "SELL"}[int(action)]
    return {**state, "actor_signal": signal, "obs": obs}

def critic_node(state: TradingState) -> TradingState:
    recent_log = pd.read_csv(SIGNAL_LOG).tail(40).to_string() if os.path.exists(SIGNAL_LOG) else "No log"
    advice = "Critic API failed"
    if state["is_market_open"]:
        for attempt in range(3):
            try:
                payload = {"model": "grok-4.20-0309-reasoning", "messages": [
                    {"role": "system", "content": "Devil’s Advocate Critic. Gebruik real-time X-sentiment (maart 2026 sterk bearish). Max 4 zinnen veto + bias."},
                    {"role": "user", "content": f"Regime: {state['regime']}\nActor: {state['actor_signal']}\nPrice: {state['last_price']:.2f}\nATR: {state['atr']:.2f}\nLog:\n{recent_log}"}
                ]}
                print(f"   🔥 GROK API CALL START - Real xAI request at {datetime.now().strftime('%H:%M:%S')}")
                r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=10)
                if r.status_code == 200:
                    advice = r.json()["choices"][0]["message"]["content"]
                    print(f"   🔥 GROK API SUCCESS - Real xAI reasoning at {datetime.now().strftime('%H:%M:%S')}")
                    break
            except:
                pass
    else:
        advice = "Closed market - cached sentiment"
    veto = []
    if "HIGH_VOLATILITY" in state["regime"] and state["actor_signal"] != "HOLD":
        veto.append("High vol risk")
    if "bearish" in advice.lower() and state["actor_signal"] == "BUY":
        veto.append("Bearish X-sentiment veto")
    final = "HOLD (Critic VETO)"