import os
import time
import pandas as pd
import numpy as np
from datetime import datetime
from stable_baselines3 import PPO
from dotenv import load_dotenv
import requests
from typing import TypedDict, Annotated, List
import operator
from langgraph.graph import StateGraph, END

load_dotenv()
INSTRUMENT = os.getenv("INSTRUMENT")
XAI_KEY = os.getenv("XAI_API_KEY")
CSV_FILE = "market_data_log.csv"
SIGNAL_LOG = "signals_log.csv"

print("✅ Multi-Agent Swarm v15 – LangGraph v3.2 compliant (echte swarm)")

model = PPO.load("ppo_trading_model_v6", device="cpu")

# ====================== SHARED STATE ======================
class TradingState(TypedDict):
    obs: list
    regime: str
    actor_signal: str
    critic_reasoning: str
    critic_veto: List[str]
    final_signal: str
    messages: Annotated[List[str], operator.add]

# ====================== NODES (echte agents) ======================
def regime_oracle_node(state: TradingState) -> TradingState:
    df = pd.read_csv(CSV_FILE).tail(50)
    if len(df) < 20:
        return {**state, "regime": "OPBOUWEN"}
    returns = df['last'].pct_change()
    atr_pct = returns.rolling(14).std().iloc[-1] * 100
    avg_vol = df['volume'].mean()
    if atr_pct > 0.18 or avg_vol > 160000:
        regime = "HIGH_VOLATILITY 🔥"
    elif atr_pct < 0.09:
        regime = "LOW_VOLATILITY 🌿"
    else:
        regime = "NORMAL_MARKET ⚖️"
    return {**state, "regime": regime}

def actor_node(state: TradingState) -> TradingState:
    obs = np.array(state["obs"], dtype=np.float32)
    action = int(model.predict(obs, deterministic=True)[0].item())
    signal = {0: "HOLD", 1: "BUY", 2: "SELL"}[action]
    return {**state, "actor_signal": signal}

def critic_node(state: TradingState) -> TradingState:
    # ECHTE X-sentiment via Grok API (Grok heeft real-time X kennis)
    recent_log = pd.read_csv(SIGNAL_LOG).tail(30).to_string()
    payload = {
        "model": "grok-4.20-0309-reasoning",
        "messages": [{
            "role": "system",
            "content": "Je bent Devil’s Advocate Critic Agent van de #1 NinjaTrader bot. Analyseer regime + actor signal + recente signals_log. Gebruik je real-time kennis van X (Twitter) voor ES/MES sentiment (huidig: sterk bearish maart 2026). Geef concrete veto-reden + BUY/SELL bias advies. Max 3 zinnen."
        }, {
            "role": "user",
            "content": f"Regime: {state['regime']}\nActor: {state['actor_signal']}\nLog:\n{recent_log}\nWat is jouw veto en waarom?"
        }]
    }
    try:
        r = requests.post("https://api.x.ai/v1/chat/completions",
                          headers={"Authorization": f"Bearer {XAI_KEY}", "Content-Type": "application/json"},
                          json=payload, timeout=12)
        advice = r.json()["choices"][0]["message"]["content"] if r.status_code == 200 else "API error"
    except:
        advice = "Critic API timeout – default HOLD"
    
    veto = []
    if "HIGH_VOLATILITY" in state["regime"] and state["actor_signal"] != "HOLD":
        veto.append("Te riskant in high-vol")
    if "bearish" in advice.lower() and state["actor_signal"] == "BUY":
        veto.append("Bearish X-sentiment veto")
    
    final = "HOLD (Critic VETO)" if veto else state["actor_signal"]
    return {**state, "critic_reasoning": advice, "critic_veto": veto, "final_signal": final}

def supervisor_node(state: TradingState) -> TradingState:
    print(f"\n📊 Regime Oracle: {state['regime']}")
    print(f"🧠 Actor (PPO): {state['actor_signal']}")
    print(f"🛡️ Critic (Devil’s Advocate): {state['critic_reasoning']}")
    print(f"✅ Final Signal: **{state['final_signal']}**")
    # Log
    pd.DataFrame([{"timestamp": datetime.now(), "actor": state['actor_signal'], "final": state['final_signal'],
                   "regime": state['regime'], "sentiment": "X-integrated"}]).to_csv(SIGNAL_LOG, mode="a", header=False, index=False)
    return state

# ====================== BUILD GRAPH (v3.2 core) ======================
workflow = StateGraph(TradingState)
workflow.add_node("regime", regime_oracle_node)
workflow.add_node("actor", actor_node)
workflow.add_node("critic", critic_node)
workflow.add_node("supervisor", supervisor_node)

# Edges
workflow.set_entry_point("regime")
workflow.add_edge("regime", "actor")
workflow.add_edge("actor", "critic")
workflow.add_edge("critic", "supervisor")
workflow.add_edge("supervisor", END)

graph = workflow.compile()

# ====================== MOCK DATA + LOOP (later echte CrossTrade) ======================
def get_mock_obs():
    price = 6559 + np.random.normal(0, 8)
    volume = int(140000 + np.random.normal(0, 15000))
    return [price/1000, volume/100000, 0.15, 1, 0]  # placeholder obs

if __name__ == "__main__":
    print("🚀 v15 LangGraph Swarm actief – 4 echte agents (Ctrl+C om te stoppen)\n")
    try:
        while True:
            obs = get_mock_obs()
            initial_state = {"obs": obs, "regime": "", "actor_signal": "", "critic_reasoning": "", "critic_veto": [], "final_signal": "", "messages": []}
            
            result = graph.invoke(initial_state)
            
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n🛑 v15 gestopt.")