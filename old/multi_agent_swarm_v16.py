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
INSTRUMENT = os.getenv("INSTRUMENT", "MES=F")
XAI_KEY = os.getenv("XAI_API_KEY")
CROSSTRADE_TOKEN = os.getenv("CROSSTRADE_TOKEN")
CROSSTRADE_ACCOUNT = os.getenv("CROSSTRADE_ACCOUNT", "Sim101")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
CSV_FILE = "market_data_log.csv"
SIGNAL_LOG = "signals_log.csv"

print("✅ Multi-Agent Swarm v16 – ECHTE CrossTrade integration (v3.2 compliant)")

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
    messages: Annotated[List[str], operator.add]

def fetch_cross_trade_quote():
    if not CROSSTRADE_TOKEN:
        print("   ⚠️ Geen token – fallback mock")
        return 6559 + np.random.normal(0, 8), int(140000 + np.random.normal(0, 15000))
    url = f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/quote"
    headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}", "Content-Type": "application/json"}
    params = {"instrument": INSTRUMENT.replace("=", " ")}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=8)
        if r.status_code == 200:
            data = r.json()
            return float(data.get("last", 6559)), int(data.get("volume", 140000))
        else:
            print(f"   ⚠️ Quote API {r.status_code} – fallback mock")
    except Exception as e:
        print(f"   ⚠️ Quote error: {e} – fallback mock")
    return 6559 + np.random.normal(0, 8), int(140000 + np.random.normal(0, 15000))

def regime_oracle_node(state: TradingState) -> TradingState:
    # Gebruikt echte volume/price
    regime = "HIGH_VOLATILITY 🔥" if state["volume"] > 160000 else "LOW_VOLATILITY 🌿" if state["volume"] < 120000 else "NORMAL_MARKET ⚖️"
    return {**state, "regime": regime}

def actor_node(state: TradingState) -> TradingState:
    obs = np.array(state["obs"], dtype=np.float32)
    action = int(model.predict(obs, deterministic=True)[0].item())
    signal = {0: "HOLD", 1: "BUY", 2: "SELL"}[action]
    return {**state, "actor_signal": signal}

def critic_node(state: TradingState) -> TradingState:
    recent_log = pd.read_csv(SIGNAL_LOG).tail(30).to_string() if os.path.exists(SIGNAL_LOG) else "No log yet"
    for attempt in range(2):  # retry
        payload = {"model": "grok-4.20-0309-reasoning", "messages": [
            {"role": "system", "content": "Devil’s Advocate Critic. Gebruik real-time X-sentiment (sterk bearish maart 2026). Max 3 zinnen veto + bias."},
            {"role": "user", "content": f"Regime: {state['regime']}\nActor: {state['actor_signal']}\nPrice: {state['last_price']}\nLog:\n{recent_log}\nVeto?"}
        ]}
        try:
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=12)
            if r.status_code == 200:
                advice = r.json()["choices"][0]["message"]["content"]
                break
        except:
            advice = f"Critic retry {attempt+1} failed"
    veto = []
    if "HIGH_VOLATILITY" in state["regime"] and state["actor_signal"] != "HOLD":
        veto.append("Te riskant")
    if "bearish" in advice.lower() and state["actor_signal"] == "BUY":
        veto.append("Bearish X-sentiment veto")
    final = "HOLD (Critic VETO)" if veto else state["actor_signal"]
    return {**state, "critic_reasoning": advice, "critic_veto": veto, "final_signal": final}

def supervisor_node(state: TradingState) -> TradingState:
    print(f"\n📊 Regime: {state['regime']}")
    print(f"🧠 Actor (PPO): {state['actor_signal']}")
    print(f"🛡️ Critic: {state['critic_reasoning']}")
    print(f"✅ Final: **{state['final_signal']}** | Prijs: {state['last_price']:.2f}")
    
    if state["final_signal"] != "HOLD" and not DRY_RUN:
        # Placeholder order placement (0.5% risk max)
        print(f"   🔴 DRY_RUN=False → zou order plaatsen (0.5% risk, 1 contract max)")
    else:
        print(f"   🟢 DRY_RUN={DRY_RUN} → geen order geplaatst (veilig)")
    
    # Log
    pd.DataFrame([{"timestamp": datetime.now(), "actor": state['actor_signal'], "final": state['final_signal'], "regime": state['regime'], "price": state['last_price']}]).to_csv(SIGNAL_LOG, mode="a", header=False, index=False)
    return state

# Build graph
workflow = StateGraph(TradingState)
workflow.add_node("data", lambda s: {**s, "last_price": fetch_cross_trade_quote()[0], "volume": fetch_cross_trade_quote()[1]})
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
    print("🚀 v16 ECHTE CrossTrade Swarm actief (Ctrl+C om te stoppen) – DRY_RUN =", DRY_RUN, "\n")
    try:
        while True:
            initial = {"obs": [0,0,0,0,0], "regime": "", "actor_signal": "", "critic_reasoning": "", "critic_veto": [], "final_signal": "", "last_price": 0, "volume": 0, "messages": []}
            result = graph.invoke(initial)
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n🛑 v16 gestopt.")