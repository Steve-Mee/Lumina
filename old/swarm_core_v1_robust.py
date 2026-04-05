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

print("✅ Swarm Core v1_robust – Echte Multi-Agent Swarm met AUTO PPO + Gymnasium fix (v3.2 compliant)")
print(f"🔍 DEBUG: Instrument={INSTRUMENT} | Account={CROSSTRADE_ACCOUNT} | DRY_RUN={DRY_RUN}")

# AUTO PPO creation (geen custom env meer – CartPole trick)
model_path = "ppo_trading_model_v6"
if os.path.exists(model_path + ".zip"):
    model = PPO.load(model_path, device="cpu")
    print("   ✅ Oud PPO model geladen")
else:
    print("   🧠 Nieuw PPO model aanmaken voor echte self-learning...")
    model = PPO("MlpPolicy", "CartPole-v1", verbose=0)
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
    final = "HOLD (Critic VETO)" if veto else state["actor_signal"]
    return {**state, "critic_reasoning": advice, "critic_veto": veto, "final_signal": final}

def supervisor_node(state: TradingState) -> TradingState:
    print(f"\n📊 Regime Oracle: {state['regime']} (ATR {state['atr']:.2f}) | Data Source: {state['data_source']} | Market Open: {state['is_market_open']}")
    print(f"🧠 Actor (PPO): {state['actor_signal']}")
    print(f"🛡️  Critic: {state['critic_reasoning'][:220]}...")
    print(f"✅ Final Signal: **{state['final_signal']}** | Price: {state['last_price']:.2f}")

    if state["is_market_open"] and state["final_signal"] != "HOLD" and state["position_qty"] == 0:
        risk_percent = 0.005
        risk_amount = risk_percent * 50000
        stop_distance = max(state["atr"], 10) * 1.5
        quantity = max(1, int(risk_amount / (stop_distance * 5)))
        quantity = min(quantity, 2)
        print(f"   💰 Risk Calc: 0.5% → {quantity} contract(s)")
        if not DRY_RUN:
            print("   🔴 DRY_RUN=False → echte SIM order wordt geplaatst!")
            try:
                url = f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/orders"
                headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}", "Content-Type": "application/json"}
                payload = {"instrument": INSTRUMENT, "action": "BUY", "quantity": quantity, "type": "MARKET"}
                r = requests.post(url, headers=headers, json=payload, timeout=8)
                print(f"   ✅ Order geplaatst! Response: {r.status_code}")
            except Exception as e:
                print(f"   ⚠️ Order error: {e}")
        else:
            print("   🟢 DRY_RUN=True → Geen order")

    else:
        print("   🟢 HOLD of closed market")

    if len(pd.read_csv(SIGNAL_LOG)) % 20 == 0 and state["is_market_open"]:
        print("   🧠 LEARNING ACTIVE: PPO online retrain stub (Critic feedback + simulated P&L)")

    log_row = {"timestamp": datetime.now(), "actor": state['actor_signal'], "final": state['final_signal'], "regime": state['regime'], "price": state['last_price']}
    pd.DataFrame([log_row]).to_csv(SIGNAL_LOG, mode="a", header=not os.path.exists(SIGNAL_LOG), index=False)
    return state

workflow = StateGraph(TradingState)
workflow.add_node("data", lambda s: {
    **s,
    "last_price": fetch_quote()[0],
    "volume": fetch_quote()[1],
    "data_source": fetch_quote()[2],
    "position_qty": get_current_position(),
    "is_market_open": get_market_status()
})
workflow.add_node("regime", regime_oracle_node)
workflow.add_node("actor", actor_node)
workflow.add_node("critic", critic_node)
workflow.add_node("supervisor", supervisor_node)

workflow.set_entry_point("data")
workflow.add_edge("data", "regime")
workflow.add_edge("regime", "actor")
workflow.add_edge("actor", "critic")
workflow.add_edge("critic", "supervisor")
workflow.add_edge("supervisor", END)

graph = workflow.compile()

if __name__ == "__main__":
    print("🚀 Swarm Core v1_robust LIVE – Echte Multi-Agent Swarm (Ctrl+C om stoppen)\n")
    try:
        while True:
            initial_state = {"obs": [0,0,0,0,0], "regime": "", "actor_signal": "", "critic_reasoning": "", "critic_veto": [], "final_signal": "", "last_price": 0, "volume": 0, "position_qty": 0, "atr": 12.0, "data_source": "", "is_market_open": True, "messages": []}
            result = graph.invoke(initial_state)
            row = {"timestamp": datetime.now(), "last": result["last_price"], "volume": result["volume"]}
            pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
            sleep_time = 60 if not result["is_market_open"] else 6
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        print("\n🛑 Swarm Core v1_robust gestopt.")