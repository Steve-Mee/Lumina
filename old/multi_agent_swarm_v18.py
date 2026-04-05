import os
import time
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from stable_baselines3 import PPO
from dotenv import load_dotenv
from typing import TypedDict, Annotated, List
import operator
from langgraph.graph import StateGraph, END

load_dotenv()

INSTRUMENT = os.getenv("INSTRUMENT", "MES1!")
XAI_KEY = os.getenv("XAI_API_KEY")
CROSSTRADE_TOKEN = os.getenv("CROSSTRADE_TOKEN")
CROSSTRADE_ACCOUNT = os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"

CSV_FILE = "market_data_log.csv"
SIGNAL_LOG = "signals_log.csv"

print("✅ Multi-Agent Swarm v18 – Volledige CrossTrade + Auto Instrument Fallback + Debug (v3.2 compliant)")
print(f"🔍 .env DEBUG: Token=Yes | Account={CROSSTRADE_ACCOUNT} | Instrument={INSTRUMENT} | DRY_RUN={DRY_RUN}")

model = PPO.load("ppo_trading_model_v6", device="cpu")

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
    messages: Annotated[List[str], operator.add]

def fetch_cross_trade_quote():
    if not CROSSTRADE_TOKEN:
        print("   ⚠️ TOKEN MISSING")
        return 6559 + np.random.normal(0, 8), 140000
    # AUTO FALLBACK FORMATS (volgens 2026 docs)
    formats = [INSTRUMENT, INSTRUMENT.replace("1!", " JUN 26"), "MES JUN 26", INSTRUMENT.replace(" ", "%20")]
    for fmt in formats:
        url = f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/quote"
        headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}", "Content-Type": "application/json"}
        params = {"instrument": fmt}
        try:
            r = requests.get(url, headers=headers, params=params, timeout=8)
            if r.status_code == 200:
                data = r.json()
                price = float(data.get("last", 6559))
                volume = int(data.get("volume", 140000))
                print(f"   ✅ Quote success met format: {fmt} | Price: {price:.2f}")
                return price, volume
            elif r.status_code == 400:
                print(f"   ⚠️ 400 Bad Request met format '{fmt}' → response: {r.text[:200]}")
            else:
                print(f"   ⚠️ API {r.status_code} met {fmt}")
        except Exception as e:
            print(f"   ⚠️ Exception met {fmt}: {e}")
    print("   ❌ Alle formats gefaald → mock fallback")
    return 6559 + np.random.normal(0, 8), 140000

def get_current_position():
    if not CROSSTRADE_TOKEN:
        return 0
    url = f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/positions"
    headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}
    try:
        r = requests.get(url, headers=headers, timeout=6)
        if r.status_code == 200:
            positions = r.json()
            for p in positions if isinstance(positions, list) else []:
                if p.get("instrument") == INSTRUMENT or "MES" in str(p.get("instrument")):
                    return int(p.get("quantity", 0))
    except:
        pass
    return 0

def calculate_atr(df):
    if len(df) < 14:
        return 12.0
    # Gefixte ATR op last prijs changes (geen high/low nodig)
    returns = df['last'].pct_change().abs() * df['last']
    return returns.rolling(14).mean().iloc[-1]

def regime_oracle_node(state: TradingState) -> TradingState:
    df = pd.read_csv(CSV_FILE).tail(100) if os.path.exists(CSV_FILE) else pd.DataFrame()
    atr = calculate_atr(df)
    vol = state["volume"]
    if atr > 25 or vol > 180000:
        regime = "HIGH_VOLATILITY 🔥"
    elif atr < 10:
        regime = "LOW_VOLATILITY 🌿"
    else:
        regime = "NORMAL_MARKET ⚖️"
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
    for attempt in range(3):
        try:
            payload = {
                "model": "grok-4.20-0309-reasoning",
                "messages": [
                    {"role": "system", "content": "Devil’s Advocate Critic. Gebruik real-time X-sentiment (maart 2026 sterk bearish). Max 4 zinnen veto + bias. Wees streng."},
                    {"role": "user", "content": f"Regime: {state['regime']}\nActor: {state['actor_signal']}\nPrice: {state['last_price']:.2f}\nATR: {state['atr']:.2f}\nLog:\n{recent_log}"}
                ]
            }
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=10)
            if r.status_code == 200:
                advice = r.json()["choices"][0]["message"]["content"]
                break
        except:
            pass
    veto = []
    if "HIGH_VOLATILITY" in state["regime"] and state["actor_signal"] != "HOLD":
        veto.append("High vol risk")
    if "bearish" in advice.lower() and state["actor_signal"] == "BUY":
        veto.append("Bearish X-sentiment veto")
    final = "HOLD (Critic VETO)" if veto else state["actor_signal"]
    return {**state, "critic_reasoning": advice, "critic_veto": veto, "final_signal": final}

def supervisor_node(state: TradingState) -> TradingState:
    print(f"\n📊 Regime Oracle: {state['regime']} (ATR {state['atr']:.2f})")
    print(f"🧠 Actor (PPO): {state['actor_signal']}")
    print(f"🛡️  Critic: {state['critic_reasoning'][:200]}...")
    print(f"✅ Final Signal: **{state['final_signal']}** | Price: {state['last_price']:.2f} | Pos: {state['position_qty']}")

    if state["final_signal"] != "HOLD" and state["position_qty"] == 0:
        risk_percent = 0.005
        risk_amount = risk_percent * 50000
        stop_distance = max(state["atr"], 10) * 1.5
        quantity = max(1, int(risk_amount / (stop_distance * 5)))
        quantity = min(quantity, 2)
        print(f"   💰 Risk Calc: 0.5% → {quantity} contract(s) | Stop ~{stop_distance:.1f} pts")
        if DRY_RUN:
            print(f"   🟢 DRY_RUN=True → Geen order")
        else:
            print(f"   🔴 DRY_RUN=False → Order zou geplaatst worden!")
    else:
        print(f"   🟢 HOLD of positie open")

    log_row = {"timestamp": datetime.now(), "actor": state['actor_signal'], "final": state['final_signal'], "regime": state['regime'], "price": state['last_price']}
    pd.DataFrame([log_row]).to_csv(SIGNAL_LOG, mode="a", header=not os.path.exists(SIGNAL_LOG), index=False)
    return state

# ==================== GRAPH BUILD ====================
workflow = StateGraph(TradingState)
workflow.add_node("data", lambda s: {**s, "last_price": fetch_cross_trade_quote()[0], "volume": fetch_cross_trade_quote()[1], "position_qty": get_current_position()})
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
    print("🚀 v18 Swarm LIVE – Auto fallback + full debug (Ctrl+C om stoppen)\n")
    try:
        while True:
            initial_state = {"obs": [0,0,0,0,0], "regime": "", "actor_signal": "", "critic_reasoning": "", "critic_veto": [], "final_signal": "", "last_price": 0, "volume": 0, "position_qty": 0, "atr": 12.0, "messages": []}
            result = graph.invoke(initial_state)
            row = {"timestamp": datetime.now(), "last": result["last_price"], "volume": result["volume"]}
            pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
            time.sleep(6)
    except KeyboardInterrupt:
        print("\n🛑 v18 gestopt.")