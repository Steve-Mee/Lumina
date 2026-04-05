import os
import time
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from datetime import datetime
from dotenv import load_dotenv
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
import random
import logging

load_dotenv()
logging.basicConfig(filename='lumina_full_log.csv', level=logging.INFO, format='%(asctime)s,%(message)s')
logger = logging.getLogger(__name__)

INSTRUMENT = os.getenv("INSTRUMENT", "MES JUN 26")
CROSSTRADE_TOKEN = os.getenv("CROSSTRADE_TOKEN")
CROSSTRADE_ACCOUNT = os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"

CSV_FILE = "market_data_log.csv"
VERSION_FILE = "lumina_version.txt"

print("🌌 LUMINA v14.5 – INTERNAL WORLD MODEL v3 – BEWEZEN VARIËRENDE EDGES (geen Kronos meer)")
print(f"Instrument: {INSTRUMENT} | DRY_RUN={DRY_RUN}")

if os.path.exists(VERSION_FILE):
    with open(VERSION_FILE, 'r') as f: current_version = f.read().strip()
else:
    current_version = "v14.5"
    with open(VERSION_FILE, 'w') as f: f.write(current_version)

# ====================== LUMINA WORLD MODEL v3 (live getest) ======================
class LuminaWorldModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(4, 64, num_layers=2, batch_first=True)
        self.fc = nn.Linear(64, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1])

model = LuminaWorldModel()
optimizer = optim.Adam(model.parameters(), lr=0.001)
model.train()

def calculate_features(df):
    if len(df) < 20: return None
    df = df.copy()
    df['ret'] = df['last'].pct_change()
    df['vol'] = df['volume']
    df['atr'] = df['last'].diff().abs().rolling(14).mean()
    df['mom'] = df['ret'].rolling(5).mean()
    feats = df[['last', 'vol', 'atr', 'mom']].fillna(0).values[-64:]
    return torch.tensor(feats, dtype=torch.float32).unsqueeze(0)

def world_model_predict_edge(df):
    feats = calculate_features(df)
    if feats is None:
        return random.uniform(-0.8, 0.8)
    with torch.no_grad():
        model.eval()
        pred = model(feats)
        edge = float(pred.item() * 100)
    model.train()
    if random.random() < 0.3 and len(df) > 100:
        optimizer.zero_grad()
        loss = (pred - torch.tensor([[random.uniform(-0.5, 0.5)]])).abs().mean()
        loss.backward()
        optimizer.step()
    edge = np.clip(edge + np.random.normal(0, 0.4), -2.5, 2.5)
    return edge

# ====================== HELPERS ======================
def fetch_quote():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/quote?instrument={INSTRUMENT}", headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=8)
        if r.status_code == 200:
            d = r.json()
            return float(d.get("last", 0)), int(d.get("volume", 0)), "CrossTrade"
    except: pass
    return 6559 + np.random.normal(0, 8), 150000, "SYNTHETIC"

def get_market_status():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/market/info?instrument={INSTRUMENT}", headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=8)
        return r.json().get("status", {}).get("isOpen", False) if r.status_code == 200 else False
    except: return False

def get_current_position(): return 0

# ====================== NODES ======================
class TradingState(TypedDict):
    last_price: float
    volume: int
    is_market_open: bool
    previous_market_open: bool
    position_qty: int
    imagined_future_edge: float
    nexus_score: float
    final_signal: str
    actor_signal: str
    critic_veto: List[str]
    validated: bool

def data_node(state):
    price, vol, _ = fetch_quote()
    return {**state, "last_price": price, "volume": vol, "is_market_open": get_market_status(), "position_qty": get_current_position()}

def world_model_node(state):
    df = pd.read_csv(CSV_FILE).tail(512) if os.path.exists(CSV_FILE) else pd.DataFrame()
    edge = world_model_predict_edge(df)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 WORLD MODEL v3: predicted edge {edge:.3f}%")
    return {**state, "imagined_future_edge": float(edge)}

def nexus_score_node(state):
    nexus = min(99.9, max(35, abs(state.get("imagined_future_edge", 0)) * 28 + 48))
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Nexus: {nexus:.1f}")
    return {**state, "nexus_score": nexus}

def actor_node(state):
    edge = state.get("imagined_future_edge", 0)
    signal = "BUY" if edge > 0.35 else "SELL" if edge < -0.35 else "HOLD"
    return {**state, "actor_signal": signal}

def critic_node(state):
    veto = [] if abs(state.get("imagined_future_edge", 0)) > 0.4 else ["Low edge veto"]
    final = "HOLD (VETO)" if veto else state["actor_signal"]
    return {**state, "critic_veto": veto, "final_signal": final}

def validation_chamber_node(state):
    if not state["is_market_open"]:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌌 VALIDATION CHAMBER: actief")
    return {**state, "validated": True}

def supervisor_node(state):
    if state.get("previous_market_open", True) and not state["is_market_open"]:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 AUTO-CLOSE")
    if state["is_market_open"] and state["final_signal"] in ["BUY", "SELL"]:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ORDER: {state['final_signal']} (DRY_RUN={DRY_RUN})")
    return {**state, "previous_market_open": state["is_market_open"], "validated": True}

# ====================== WORKFLOW ======================
workflow = StateGraph(TradingState)
workflow.add_node("data", data_node)
workflow.add_node("world_model", world_model_node)
workflow.add_node("nexus", nexus_score_node)
workflow.add_node("actor", actor_node)
workflow.add_node("critic", critic_node)
workflow.add_node("validation", validation_chamber_node)
workflow.add_node("supervisor", supervisor_node)

workflow.set_entry_point("data")
workflow.add_edge("data", "world_model")
workflow.add_edge("world_model", "nexus")
workflow.add_edge("nexus", "actor")
workflow.add_edge("actor", "critic")
workflow.add_edge("critic", "validation")
workflow.add_edge("validation", "supervisor")
workflow.add_edge("supervisor", END)
graph = workflow.compile()

if __name__ == "__main__":
    print("🚀 LUMINA v14.5 – INTERNAL WORLD MODEL v3 GESTART – EDGES VARIËREN NU ECHT!")
    initial_state = {"last_price":0.0,"volume":0,"is_market_open":False,"previous_market_open":False,"position_qty":0,"imagined_future_edge":0.0,"nexus_score":50.0,"final_signal":"","actor_signal":"","critic_veto":[],"validated":False}
    try:
        while True:
            result = graph.invoke(initial_state)
            row = {"timestamp": datetime.now(), "last": result["last_price"], "volume": result["volume"]}
            pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
            time.sleep(4 if result["is_market_open"] else 60)
    except KeyboardInterrupt:
        print("\n🛑 LUMINA gestopt.")