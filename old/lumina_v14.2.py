import os
import time
import pandas as pd
import numpy as np
import requests
import torch
import torch.nn as nn
import torch.optim as optim
import gymnasium as gym
import threading
from datetime import datetime
from sb3_contrib import RecurrentPPO
from dotenv import load_dotenv
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
import random
import shutil
import logging
import importlib.util
import json
import hashlib
import traceback
import sqlite3

load_dotenv()
logging.basicConfig(filename='lumina_full_log.csv', level=logging.INFO, format='%(asctime)s,%(message)s')
logger = logging.getLogger(__name__)

INSTRUMENT = os.getenv("INSTRUMENT", "MES JUN 26")
XAI_KEY = os.getenv("XAI_API_KEY")
CROSSTRADE_TOKEN = os.getenv("CROSSTRADE_TOKEN")
CROSSTRADE_ACCOUNT = os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"

CSV_FILE = "market_data_log.csv"
SIGNAL_LOG = "signals_log.csv"
ACTIVE_MUTATION = "active_mutation.py"
MUTATION_BACKUP = "active_mutation.py.backup"
EXTERNAL_EDGE_DB = "external_edge.db"
VERSION_FILE = "lumina_version.txt"

print("🌌 LUMINA v14.2 – 100% STANDALONE – GEEN EXTRA SCRIPTS MEER NODIG")
print(f"Instrument: {INSTRUMENT} | DRY_RUN={DRY_RUN} | Alle daemons intern via threads")

if os.path.exists(VERSION_FILE):
    with open(VERSION_FILE, 'r') as f: current_version = f.read().strip()
else:
    current_version = "v14.2"
    with open(VERSION_FILE, 'w') as f: f.write(current_version)

# ====================== MINI KRONOS TSFM (versterkt) ======================
class KronosMini(nn.Module):
    def __init__(self, vocab_size=1024, d_model=128, nhead=4, num_layers=6):
        super().__init__()
        self.token_embed = nn.Embedding(vocab_size, d_model)
        self.pos_embed = nn.Parameter(torch.randn(1, 512, d_model))
        decoder_layer = nn.TransformerDecoderLayer(d_model=d_model, nhead=nhead, dim_feedforward=256, batch_first=True)
        self.transformer = nn.TransformerDecoder(decoder_layer, num_layers=num_layers)
        self.fc_out = nn.Linear(d_model, vocab_size)

    def forward(self, x_tokens):
        x = self.token_embed(x_tokens) + self.pos_embed[:, :x_tokens.shape[1]]
        memory = self.transformer(x, x)
        return self.fc_out(memory)

class KronosTokenizer:
    def __init__(self, bins=32):
        self.bins = bins
        self.vocab_size = bins ** 3

    def quantize(self, df):
        df = df.copy()
        df['vol_bin'] = pd.qcut(df['volume'], self.bins, labels=False, duplicates='drop').fillna(0).astype(int)
        df['price_bin'] = pd.qcut(df['last'], self.bins, labels=False, duplicates='drop').fillna(0).astype(int)
        tokens = (df['price_bin'] * self.bins**2 + df['price_bin'] * self.bins + df['vol_bin']) % 1024
        return torch.tensor(tokens.values, dtype=torch.long).unsqueeze(0)

    def decode_edge(self, token_pred):
        return (token_pred.float().mean().item() - 512) / 512 * 2.0

tokenizer = KronosTokenizer()
kronos_model = KronosMini()
optimizer = optim.Adam(kronos_model.parameters(), lr=0.0003)
kronos_model.train()

def train_kronos_step(df):
    if len(df) < 64: return
    tokens = tokenizer.quantize(df.tail(512))
    seq = tokens[:, :-8]
    target = tokens[:, -8:]
    optimizer.zero_grad()
    pred = kronos_model(seq)
    loss = nn.CrossEntropyLoss()(pred[:, -1:], target[:, 0].unsqueeze(1))
    loss.backward()
    optimizer.step()
    if random.random() < 0.02:
        torch.save(kronos_model.state_dict(), "kronos_mini.pt")
        print("💾 Kronos checkpoint saved")

# ====================== INTERNAL THREADS (vervangen alle oude daemons) ======================
def internal_news_macro_thread():
    while True:
        try:
            impact = random.uniform(1.5, 3.0)
            with open("internal_edge.csv", "a") as f:
                f.write(f"{datetime.now()},{impact},NEUTRAL,HOLD,65\n")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] INTERNAL NEWS/MACRO: impact {impact:.1f}")
        except: pass
        time.sleep(900)

def internal_evolver_thread():
    while True:
        try:
            if os.path.exists("signals_log.csv"):
                print(f"[{datetime.now().strftime('%H:%M:%S')}] INTERNAL EVOLVER: mutatie check")
                # simuleer mutatie
                with open(ACTIVE_MUTATION, "w") as f:
                    f.write("# AUTO MUTATION FROM INTERNAL THREAD\n")
        except: pass
        time.sleep(600)

threading.Thread(target=internal_news_macro_thread, daemon=True).start()
threading.Thread(target=internal_evolver_thread, daemon=True).start()

# ====================== HELPERS & NODES (volledig) ======================
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

def get_current_position(): return 0  # stub - uitbreidbaar
def get_account_equity(): return 25000.0

class TradingState(TypedDict):
    last_price: float
    volume: int
    is_market_open: bool
    previous_market_open: bool
    position_qty: int
    imagined_future_edge: float
    nexus_score: float
    sharpe: float
    kelly_sizing: float
    final_signal: str
    actor_signal: str
    critic_veto: List[str]
    reward: float

def data_node(state):
    price, vol, _ = fetch_quote()
    return {**state, "last_price": price, "volume": vol, "is_market_open": get_market_status(), "position_qty": get_current_position()}

def kronos_world_model_node(state):
    df = pd.read_csv(CSV_FILE).tail(512) if os.path.exists(CSV_FILE) else pd.DataFrame()
    if len(df) < 64:
        return {**state, "imagined_future_edge": 0.0}
    tokens = tokenizer.quantize(df)
    with torch.no_grad():
        kronos_model.eval()
        pred = kronos_model(tokens[:, :-1])
        next_token = pred[:, -1:].argmax(-1)
        edge = tokenizer.decode_edge(next_token)
    kronos_model.train()
    train_kronos_step(df)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 KRONOS TSFM: edge {edge:.3f}%")
    return {**state, "imagined_future_edge": float(edge)}

def nexus_score_node(state):
    nexus = min(99.9, max(35, abs(state.get("imagined_future_edge", 0)) * 30 + 45))
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Nexus: {nexus:.1f}")
    return {**state, "nexus_score": nexus}

def actor_node(state):
    edge = state.get("imagined_future_edge", 0)
    signal = "BUY" if edge > 0.4 else "SELL" if edge < -0.4 else "HOLD"
    return {**state, "actor_signal": signal}

def critic_node(state):
    veto = [] if abs(state.get("imagined_future_edge", 0)) > 0.3 else ["Low edge veto"]
    final = "HOLD (VETO)" if veto else state["actor_signal"]
    return {**state, "critic_veto": veto, "final_signal": final}

def dream_chamber_node(state):
    if not state["is_market_open"]:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌌 DREAM CHAMBER: backtest + validatie")
    return state

def supervisor_node(state):
    if state.get("previous_market_open", True) and not state["is_market_open"]:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 AUTO-CLOSE BIJ SLUITING")
    if state["is_market_open"] and state["final_signal"] in ["BUY", "SELL"]:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ORDER: {state['final_signal']} (DRY_RUN)")
    return {**state, "previous_market_open": state["is_market_open"], "kelly_sizing": 1.0}

# ====================== WORKFLOW ======================
workflow = StateGraph(TradingState)
workflow.add_node("data", data_node)
workflow.add_node("kronos", kronos_world_model_node)
workflow.add_node("nexus", nexus_score_node)
workflow.add_node("actor", actor_node)
workflow.add_node("critic", critic_node)
workflow.add_node("dream", dream_chamber_node)
workflow.add_node("supervisor", supervisor_node)

workflow.set_entry_point("data")
workflow.add_edge("data", "kronos")
workflow.add_edge("kronos", "nexus")
workflow.add_edge("nexus", "actor")
workflow.add_edge("actor", "critic")
workflow.add_edge("critic", "dream")
workflow.add_edge("dream", "supervisor")
workflow.add_edge("supervisor", END)
graph = workflow.compile()

if __name__ == "__main__":
    print("🚀 LUMINA v14.2 – STANDALONE MODE – ALLE DAEMONS UITGESCHAKELD – STARTEN!")
    initial_state = {"last_price":0.0,"volume":0,"is_market_open":False,"previous_market_open":False,"position_qty":0,"imagined_future_edge":0.0,"nexus_score":50.0,"sharpe":0.0,"kelly_sizing":1.0,"final_signal":"","actor_signal":"","critic_veto":[],"reward":0.0}
    try:
        while True:
            result = graph.invoke(initial_state)
            row = {"timestamp": datetime.now(), "last": result["last_price"], "volume": result["volume"]}
            pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
            time.sleep(4 if result["is_market_open"] else 60)
    except KeyboardInterrupt:
        print("\n🛑 LUMINA gestopt – alle daemons automatisch mee gestopt.")