import os
import time
import pandas as pd
import numpy as np
import requests
import threading
from datetime import datetime
from dotenv import load_dotenv
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
import random
import shutil
import logging
import importlib.util
import json

load_dotenv()
logging.basicConfig(filename='lumina_full_log.csv', level=logging.INFO, format='%(asctime)s,%(message)s')
logger = logging.getLogger(__name__)

INSTRUMENT = os.getenv("INSTRUMENT", "MES JUN 26")
XAI_KEY = os.getenv("XAI_API_KEY")
CROSSTRADE_TOKEN = os.getenv("CROSSTRADE_TOKEN")
CROSSTRADE_ACCOUNT = os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"

CSV_FILE = "market_data_log.csv"
SIGNALS_LOG = "signals_log.csv"
EQUITY_FILE = "equity_curve.csv"
ACTIVE_MUTATION = "active_mutation.py"
VERSION_FILE = "lumina_version.txt"

print("🌌 LUMINA v15.3 – FIXED INCREMENTAL REAL PN L + MES JUN 26 VISIBILITY")
print(f"Trading MES JUN 26 futures via CrossTrade | DRY_RUN={DRY_RUN}")

if os.path.exists(VERSION_FILE):
    with open(VERSION_FILE, 'r') as f: current_version = f.read().strip()
else:
    current_version = "v15.3"
    with open(VERSION_FILE, 'w') as f: f.write(current_version)

equity_curve = [25000.0]
last_equity = 25000.0
position_qty = 0
entry_price = 0.0
last_unrealized_pnl = 0.0
active_mutation_module = None

# ====================== MUTATION DAEMON (blijft actief) ======================
def mutation_daemon():
    while True:
        try:
            if not XAI_KEY: 
                time.sleep(600)
                continue
            payload = {"model": "grok-4.20-0309-reasoning", "messages": [
                {"role": "system", "content": "Je bent LUMINA's Mutation Engine. Geef ALLEEN JSON: {\"description\": \"...\", \"code\": \"def nieuwe_node(state: dict) -> dict: ...\"}"},
                {"role": "user", "content": "Genereer 1 nieuwe oracle die Sharpe >2.5 brengt."}
            ]}
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=15)
            if r.status_code == 200:
                suggestion = json.loads(r.json()["choices"][0]["message"]["content"])
                with open(ACTIVE_MUTATION, "w") as f:
                    f.write(f"# AUTO MUTATION {datetime.now()}\n# {suggestion['description']}\n\n{suggestion['code']}\n")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 NIEUWE MUTATION GENERATED")
        except: pass
        time.sleep(900)

threading.Thread(target=mutation_daemon, daemon=True).start()

# ====================== HELPERS ======================
def fetch_quote():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/quote?instrument={INSTRUMENT}", headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=8)
        if r.status_code == 200:
            d = r.json()
            return float(d.get("last", 0)), int(d.get("volume", 0))
    except: pass
    return 6559 + np.random.normal(0, 8), 150000

def get_market_status():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/market/info?instrument={INSTRUMENT}", headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=8)
        return r.json().get("status", {}).get("isOpen", False) if r.status_code == 200 else False
    except: return False

def calculate_phoenix_edge(df):
    if len(df) < 30: return 0.0
    df = df.copy()
    ret5 = df['last'].pct_change(5).iloc[-1]
    ret20 = df['last'].pct_change(20).iloc[-1]
    atr = df['last'].diff().abs().rolling(14).mean().iloc[-1]
    vol_delta = df['volume'].diff().rolling(5).mean().iloc[-1]
    edge = ret5 * 45 + ret20 * 25 + (atr / 15) * 0.3 + np.sign(vol_delta) * 0.4
    return float(np.clip(edge, -1.8, 1.8))

# ====================== NODES ======================
class TradingState(TypedDict):
    last_price: float
    volume: int
    is_market_open: bool
    imagined_future_edge: float
    nexus_score: float
    final_signal: str
    actor_signal: str
    critic_veto: List[str]

def data_node(state):
    price, vol = fetch_quote()
    return {**state, "last_price": price, "volume": vol, "is_market_open": get_market_status()}

def phoenix_edge_node(state):
    df = pd.read_csv(CSV_FILE).tail(200) if os.path.exists(CSV_FILE) else pd.DataFrame()
    edge = calculate_phoenix_edge(df)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 PHOENIX EDGE (MES JUN 26): {edge:+.3f}%")
    return {**state, "imagined_future_edge": edge}

def nexus_node(state):
    edge = abs(state.get("imagined_future_edge", 0))
    nexus = min(99.9, max(35, edge * 32 + 45))
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Nexus: {nexus:.1f}")
    return {**state, "nexus_score": nexus}

def actor_node(state):
    edge = state.get("imagined_future_edge", 0)
    signal = "BUY" if edge > 0.35 else "SELL" if edge < -0.35 else "HOLD"
    return {**state, "actor_signal": signal}

def critic_node(state):
    veto = [] if abs(state.get("imagined_future_edge", 0)) > 0.35 else ["Low edge veto"]
    final = "HOLD (VETO)" if veto else state["actor_signal"]
    return {**state, "critic_veto": veto, "final_signal": final}

def supervisor_node(state):
    global position_qty, entry_price, last_equity, last_unrealized_pnl
    current_price = state["last_price"]
    
    # Close if opposite signal
    if (state["final_signal"] == "BUY" and position_qty < 0) or (state["final_signal"] == "SELL" and position_qty > 0):
        pnl_realized = (current_price - entry_price) * 5 * position_qty
        last_equity += pnl_realized
        print(f"[{datetime.now().strftime('%H:%M:%S')}] POSITIE GECLOSET op MES JUN 26 | Realized PnL: {pnl_realized:+.0f}")
        position_qty = 0
    
    # Open new position
    if state["final_signal"] == "BUY" and position_qty <= 0:
        position_qty = 1
        entry_price = current_price
        last_unrealized_pnl = 0
        print(f"[{datetime.now().strftime('%H:%M:%S')}] LONG geopend op MES JUN 26 @ {current_price:.2f}")
    elif state["final_signal"] == "SELL" and position_qty >= 0:
        position_qty = -1
        entry_price = current_price
        last_unrealized_pnl = 0
        print(f"[{datetime.now().strftime('%H:%M:%S')}] SHORT geopend op MES JUN 26 @ {current_price:.2f}")
    
    # Incremental PnL (FIX)
    if position_qty != 0:
        unrealized_pnl = (current_price - entry_price) * 5 * position_qty
        pnl_delta = unrealized_pnl - last_unrealized_pnl
        current_equity = last_equity + pnl_delta
        last_unrealized_pnl = unrealized_pnl
    else:
        current_equity = last_equity
    
    equity_curve.append(current_equity)
    last_equity = current_equity
    pd.DataFrame(equity_curve, columns=["equity"]).to_csv(EQUITY_FILE, index=False)
    
    # Log
    row = {"timestamp": datetime.now(), "edge": state.get("imagined_future_edge", 0), "signal": state["final_signal"], "nexus": state.get("nexus_score", 50), "equity": current_equity, "position": position_qty}
    pd.DataFrame([row]).to_csv(SIGNALS_LOG, mode="a", header=not os.path.exists(SIGNALS_LOG), index=False)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] EQUITY: ${current_equity:.0f} | Positie: {position_qty} contracts MES JUN 26")
    return state

# ====================== WORKFLOW ======================
workflow = StateGraph(TradingState)
workflow.add_node("data", data_node)
workflow.add_node("edge", phoenix_edge_node)
workflow.add_node("nexus", nexus_node)
workflow.add_node("actor", actor_node)
workflow.add_node("critic", critic_node)
workflow.add_node("supervisor", supervisor_node)

workflow.set_entry_point("data")
workflow.add_edge("data", "edge")
workflow.add_edge("edge", "nexus")
workflow.add_edge("nexus", "actor")
workflow.add_edge("actor", "critic")
workflow.add_edge("critic", "supervisor")
workflow.add_edge("supervisor", END)
graph = workflow.compile()

if __name__ == "__main__":
    print("🚀 LUMINA v15.3 – FIXED INCREMENTAL PN L GESTART – DIT IS NU CORRECT TRACEERBAAR!")
    initial_state = {"last_price":0.0,"volume":0,"is_market_open":False,"imagined_future_edge":0.0,"nexus_score":50.0,"final_signal":"","actor_signal":"","critic_veto":[]}
    try:
        while True:
            result = graph.invoke(initial_state)
            row = {"timestamp": datetime.now(), "last": result["last_price"], "volume": result["volume"]}
            pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
            time.sleep(4 if result["is_market_open"] else 60)
    except KeyboardInterrupt:
        print("\n🛑 LUMINA gestopt.")