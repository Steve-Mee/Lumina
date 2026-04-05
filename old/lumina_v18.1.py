import os
import time
import pandas as pd
import numpy as np
import requests
import threading
from datetime import datetime
from dotenv import load_dotenv
from typing import TypedDict
from langgraph.graph import StateGraph, END
import logging
import json

load_dotenv()
logging.basicConfig(filename='lumina_full_log.csv', level=logging.INFO, format='%(asctime)s,%(message)s')
logger = logging.getLogger(__name__)

INSTRUMENT = os.getenv("INSTRUMENT", "MES JUN 26")
XAI_KEY = os.getenv("XAI_API_KEY")
CROSSTRADE_TOKEN = os.getenv("CROSSTRADE_TOKEN")
CROSSTRADE_ACCOUNT = os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
SIMULATE_TRADES = os.getenv("SIMULATE_TRADES", "True").lower() == "true"

if not DRY_RUN:
    SIMULATE_TRADES = False

CSV_FILE = "market_data_log.csv"
VERSION_FILE = "lumina_version.txt"
MAX_RISK_PER_TRADE = 0.02
MAX_DRAWDOWN = -0.15

print("🌌 LUMINA v18.1 – IRONCLAD CORE + SL/TP + LIVE EQUITY CURVE")
print(f"Trading MES JUN 26 via CrossTrade | DRY_RUN={DRY_RUN} | SIMULATE_TRADES={SIMULATE_TRADES}")

if os.path.exists(VERSION_FILE):
    with open(VERSION_FILE, 'r') as f:
        current_version = f.read().strip()
else:
    current_version = "v18.1"
    with open(VERSION_FILE, 'w') as f:
        f.write(current_version)

# ====================== GLOBALS VOOR SIMULATOR ======================
sim_position_qty = 0
sim_entry_price = 0.0
sim_last_pnl = 0.0
sim_unrealized = 0.0
sim_peak = 50000.0
pnl_history = []
equity_curve = [50000.0]
max_equity = 50000.0

# ====================== DNA REWRITE ENGINE (alleen edge) ======================
def dna_rewrite_daemon():
    while True:
        try:
            if not XAI_KEY: 
                time.sleep(900)
                continue
            summary = f"Sharpe: {np.mean(pnl_history[-50:]) / (np.std(pnl_history[-50:]) + 1e-8) * np.sqrt(252) if len(pnl_history) > 50 else 0:.2f}"
            payload = {"model": "grok-4.20-0309-reasoning", "messages": [
                {"role": "system", "content": "Je bent LUMINA's DNA Rewrite Engine. Geef ALLEEN JSON: {\"description\": \"...\", \"new_edge_code\": \"def calculate_phoenix_edge(df): ...\"}"},
                {"role": "user", "content": f"Herschrijf de edge-functie zodat Sharpe >2.5 wordt. Huidige summary: {summary}"}
            ]}
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=20)
            if r.status_code == 200:
                suggestion = json.loads(r.json()["choices"][0]["message"]["content"])
                with open("phoenix_edge.py", "w") as f:
                    f.write(f"# AUTO DNA REWRITE {datetime.now()}\n# {suggestion['description']}\n\n{suggestion['new_edge_code']}\n")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 DNA REWRITE: nieuwe edge-functie geladen!")
        except: pass
        time.sleep(900)

threading.Thread(target=dna_rewrite_daemon, daemon=True).start()

# ====================== PURE LIVE API ======================
def fetch_quote():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/quote?instrument={INSTRUMENT}", headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=8)
        if r.status_code == 200:
            d = r.json()
            price = float(d.get("last", 0))
            vol = int(d.get("volume", 0))
            print(f"[{datetime.now().strftime('%H:%M:%S')}] LIVE PRIJS MES JUN 26: {price:.2f} | Volume: {vol}")
            return price, vol
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ QUOTE API ERROR {r.status_code}")
            return 0, 0
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ QUOTE API FAIL: {e}")
        return 0, 0

def get_real_portfolio_value():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}", headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=6)
        if r.status_code == 200:
            equity = float(r.json().get("item", {}).get("cashValue", 0))
            print(f"[{datetime.now().strftime('%H:%M:%S')}] LIVE PORTFOLIO VALUE: ${equity:.2f}")
            return equity
        else:
            return equity_curve[-1] if equity_curve else 50000.0
    except:
        return equity_curve[-1] if equity_curve else 50000.0

def get_market_status():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/market/info?instrument={INSTRUMENT}", headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=8)
        status = r.json().get("status", {}).get("isOpen", False) if r.status_code == 200 else False
        print(f"[{datetime.now().strftime('%H:%M:%S')}] MARKET STATUS: {'OPEN' if status else 'CLOSED'}")
        return status
    except: return False

# ====================== VERBETERDE EDGE (symmetrischer) ======================
def calculate_phoenix_edge(df):
    if len(df) < 40: return 0.0
    df = df.copy()
    df['ret'] = df['last'].pct_change()
    mom_short = df['ret'].rolling(8).mean().iloc[-1]
    mom_long  = df['ret'].rolling(34).mean().iloc[-1]
    recent_mean = df['last'].rolling(40).mean().iloc[-1]
    recent_std  = df['last'].rolling(40).std().iloc[-1]
    z_price = (df['last'].iloc[-1] - recent_mean) / (recent_std + 1e-9)
    vol_ma = df['volume'].rolling(20).mean().iloc[-1]
    vol_factor = np.clip((df['volume'].iloc[-1] / (vol_ma + 1)) - 1, -1.5, 1.5)
    edge = (1.8 * mom_short + 0.9 * mom_long + 1.4 * z_price * -0.75 + 0.6 * vol_factor)
    return float(np.clip(edge, -1.9, 1.9))

# ====================== NODES ======================
class TradingState(TypedDict):
    last_price: float
    volume: int
    is_market_open: bool
    imagined_future_edge: float
    nexus_score: float
    final_signal: str
    actor_signal: str
    critic_veto: list

def data_node(state):
    price, vol = fetch_quote()
    return {**state, "last_price": price, "volume": vol, "is_market_open": get_market_status()}

def phoenix_edge_node(state):
    df = pd.read_csv(CSV_FILE).tail(200) if os.path.exists(CSV_FILE) else pd.DataFrame()
    edge = calculate_phoenix_edge(df)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 PHOENIX EDGE: {edge:+.3f}%")
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
    global sim_position_qty, sim_entry_price, sim_last_pnl, sim_unrealized, sim_peak, max_equity
    real_equity = get_real_portfolio_value()
    equity_curve.append(real_equity)
    if real_equity > max_equity:
        max_equity = real_equity
    drawdown = (real_equity - max_equity) / max_equity
    if drawdown < MAX_DRAWDOWN:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 DRAWDOWN KILL SWITCH (-15%) → PAUZE")
        logger.info("DRAWDOWN KILL TRIGGERED")
        raise SystemExit("Drawdown kill switch activated")

    if SIMULATE_TRADES:
        current_price = state["last_price"]
        
        # SL / TP logica
        if sim_position_qty != 0:
            price_diff = current_price - sim_entry_price
            pnl_points = price_diff * sim_position_qty
            pnl_dollars = pnl_points * 5
            
            if sim_position_qty > 0:  # LONG
                if price_diff <= -25:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] SIM STOP-LOSS LONG @ {current_price:.2f} | PnL: {pnl_dollars:+.0f}")
                    sim_position_qty = 0
                elif price_diff >= 40:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] SIM TAKE-PROFIT LONG @ {current_price:.2f} | PnL: {pnl_dollars:+.0f}")
                    sim_position_qty = 0
            else:  # SHORT
                if price_diff >= 25:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] SIM STOP-LOSS SHORT @ {current_price:.2f} | PnL: {pnl_dollars:+.0f}")
                    sim_position_qty = 0
                elif price_diff <= -40:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] SIM TAKE-PROFIT SHORT @ {current_price:.2f} | PnL: {pnl_dollars:+.0f}")
                    sim_position_qty = 0
            
            if sim_position_qty != 0:
                sim_unrealized = pnl_dollars
            else:
                sim_unrealized = 0.0
            
            current_equity = 50000 + sim_unrealized
            sim_peak = max(sim_peak, current_equity)
            dd_pct = (current_equity - sim_peak) / sim_peak * 100
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Equity: ${current_equity:,.0f} | DD: {dd_pct:.2f}% | Unrealized: {sim_unrealized:+.0f}")
            
            pnl_delta = sim_unrealized - sim_last_pnl
            pnl_history.append(pnl_delta)
            sim_last_pnl = sim_unrealized

        # Nieuwe entry
        if sim_position_qty == 0:
            if state["final_signal"] == "BUY":
                sim_position_qty = 1
                sim_entry_price = current_price
                print(f"[{datetime.now().strftime('%H:%M:%S')}] SIM LONG OPEN @ {current_price:.2f}")
            elif state["final_signal"] == "SELL":
                sim_position_qty = -1
                sim_entry_price = current_price
                print(f"[{datetime.now().strftime('%H:%M:%S')}] SIM SHORT OPEN @ {current_price:.2f}")

    if not state["is_market_open"] and sim_position_qty != 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 MARKT SLUITING → SIM POSITIE GECLOSET")
        sim_position_qty = 0

    if state["is_market_open"] and state["final_signal"] in ["BUY", "SELL"]:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ORDER: {state['final_signal']} (DRY_RUN={DRY_RUN})")

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
    print("🚀 LUMINA v18.1 – GESTART MET SL/TP + LIVE EQUITY CURVE")
    initial_state = {"last_price":0.0,"volume":0,"is_market_open":False,"imagined_future_edge":0.0,"nexus_score":50.0,"final_signal":"","actor_signal":"","critic_veto":[]}
    try:
        while True:
            result = graph.invoke(initial_state)
            row = {"timestamp": datetime.now(), "last": result["last_price"], "volume": result["volume"]}
            pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
            time.sleep(1 if result["is_market_open"] else 5)
    except KeyboardInterrupt:
        print("\n🛑 LUMINA gestopt.")
    except SystemExit as e:
        print(e)