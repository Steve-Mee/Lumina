import os
import time
import pandas as pd
import numpy as np
import requests
import threading
import json
import asyncio
import websockets
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
from pathlib import Path

load_dotenv()

logging.basicConfig(filename='lumina_full_log.csv', level=logging.INFO, format='%(asctime)s,%(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# LIVE STREAM JSONL + INSTRUMENT (exact zoals in NT8 chart)
# =============================================================================
LIVE_JSONL = Path("live_stream.jsonl")
LIVE_JSONL.unlink(missing_ok=True)  # schone start bij elke run

INSTRUMENT = os.getenv("INSTRUMENT", "MES JUN26")   # ← GEEN spatie!
XAI_KEY = os.getenv("XAI_API_KEY")
CROSSTRADE_TOKEN = os.getenv("CROSSTRADE_TOKEN")
CROSSTRADE_ACCOUNT = os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
SIMULATE_TRADES = os.getenv("SIMULATE_TRADES", "True").lower() == "true"

if not DRY_RUN:
    SIMULATE_TRADES = False

CSV_FILE = "market_data_log.csv"
BIBLE_FILE = "lumina_daytrading_bible.json"

print("🌌 LUMINA v20.1 – LIVE_JSONL + VISUALIZER READY")
print(f"Trading {INSTRUMENT} | DRY_RUN={DRY_RUN} | SIMULATE_TRADES={SIMULATE_TRADES}")

# =============================================================================
# BIBLE
# =============================================================================
def load_bible():
    if os.path.exists(BIBLE_FILE):
        with open(BIBLE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    bible = { ... }  # ← je originele bible dict hier (ik heb hem niet herhaald)
    with open(BIBLE_FILE, 'w', encoding='utf-8') as f:
        json.dump(bible, f, ensure_ascii=False, indent=2)
    return bible

bible = load_bible()

TIMEFRAMES = {"5min": 300, "15min": 900, "30min": 1800, "60min": 3600, "240min": 14400, "1440min": 86400}
live_data = []

current_dream = {"signal": "HOLD", "confidence": 0.0, "stop": 0.0, "target": 0.0, "reason": "Initial", "why_no_trade": ""}

# =============================================================================
# WEBSOCKET + LIVE_JSONL (schoon & efficiënt)
# =============================================================================
async def websocket_listener():
    if not CROSSTRADE_TOKEN:
        print("❌ CROSSTRADE_TOKEN ontbreekt!")
        return

    uri = "wss://app.crosstrade.io/ws/stream"
    headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}

    try:
        async with websockets.connect(uri, additional_headers=headers, ping_interval=20, ping_timeout=20) as ws:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ WebSocket verbonden")
            await ws.send(json.dumps({"action": "subscribe", "instruments": [INSTRUMENT]}))
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📡 Subscribe verstuurd voor {INSTRUMENT}")

            async for message in ws:
                try:
                    data = json.loads(message)
                    if data.get("type") == "marketData":
                        for quote in data.get("quotes", []):
                            if quote.get("instrument") == INSTRUMENT:
                                ts = datetime.now()
                                entry = {
                                    "timestamp": ts.isoformat(),
                                    "last": float(quote.get("last", 0)),
                                    "volume": int(quote.get("volume", 0)),
                                    "bid": float(quote.get("bid", 0)),
                                    "ask": float(quote.get("ask", 0))
                                }
                                live_data.append(entry)
                                if len(live_data) > 20000:
                                    live_data.pop(0)

                                # === SCHRIJF NAAR SHARED FILE (licht & snel) ===
                                with open(LIVE_JSONL, "a", encoding="utf-8") as f:
                                    f.write(json.dumps({
                                        **entry,
                                        "current_dream": current_dream
                                    }) + "\n")   # mtf verwijderen = veel sneller

                                print(f"[{ts.strftime('%H:%M:%S')}] 📥 LIVE → last={entry['last']:.2f} | vol={entry['volume']:,}")
                except Exception as e:
                    logger.error(f"WS parse error: {e}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ WS mislukt ({e}) → REST fallback")
        while True:
            price, vol = fetch_quote()
            live_data.append({"timestamp": datetime.now().isoformat(), "last": price, "volume": vol, "bid": 0.0, "ask": 0.0})
            if len(live_data) > 20000:
                live_data.pop(0)
            time.sleep(1)

def start_websocket():
    asyncio.run(websocket_listener())

threading.Thread(target=start_websocket, daemon=True).start()

# =============================================================================
# REST + MTF + DREAM + SUPERVISOR (onveranderd)
# =============================================================================
def fetch_quote():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/quote?instrument={INSTRUMENT}",
                         headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=8)
        if r.status_code == 200:
            d = r.json()
            return float(d.get("last", 0)), int(d.get("volume", 0))
    except:
        pass
    return 0.0, 0

def get_mtf_snapshots():
    if len(live_data) < 60:
        return "PARTIAL_DATA_ONLY"
    df = pd.DataFrame(live_data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    snapshots = {}
    last_ts = df['timestamp'].iloc[-1]
    for tf_name, seconds in TIMEFRAMES.items():
        cutoff = last_ts - timedelta(seconds=seconds)
        window = df[df['timestamp'] >= cutoff].copy()
        if len(window) < 2:
            snapshots[tf_name] = {"open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0, "volume": 0}
            continue
        ohlc = {
            "open": float(window['last'].iloc[0]),
            "high": float(window['last'].max()),
            "low": float(window['last'].min()),
            "close": float(window['last'].iloc[-1]),
            "volume": int(window['volume'].iloc[-1] - window['volume'].iloc[0])  # echte delta
        }
        snapshots[tf_name] = ohlc
    return json.dumps(snapshots, ensure_ascii=False)

def pre_dream_daemon():
    global current_dream
    while True:
        try:
            mtf_data = get_mtf_snapshots()
            price = live_data[-1]["last"] if live_data else 0.0
            payload = {
                "model": "grok-4.20-0309-reasoning",
                "messages": [
                    {"role": "system", "content": f"Je bent LUMINA's brein. Je krijgt nu VOLLEDIGE OHLC bars (exact zoals NinjaTrader). Sacred Core is HEILIG.\n\nSacred Core:\n{bible['sacred_core']}\n\nEvolvable layer:\n{json.dumps(bible['evolvable_layer'], ensure_ascii=False)}\n\nGeef ALLEEN JSON."},
                    {"role": "user", "content": f"Huidige prijs: {price:.2f}\nVolledige MTF OHLC bars:\n{mtf_data}\nWat is je trade volgens mijn regels?"}
                ]
            }
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=30)
            if r.status_code == 200:
                raw = r.json()["choices"][0]["message"]["content"]
                dream_json = json.loads(raw)
                current_dream = {
                    "signal": dream_json.get("signal", "HOLD"),
                    "confidence": dream_json.get("confidence", 0),
                    "stop": dream_json.get("stop", 0),
                    "target": dream_json.get("target", 0),
                    "reason": dream_json.get("reason", ""),
                    "why_no_trade": dream_json.get("why_no_trade", "")
                }
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 FULL OHLC MTF-DROOM: {current_dream['signal']} | Conf {current_dream['confidence']}%")
                if current_dream['why_no_trade']:
                    print(f" → Waarom geen trade: {current_dream['why_no_trade']}")
        except Exception as e:
            logger.error(f"Dream error: {e}")
        time.sleep(12)
threading.Thread(target=pre_dream_daemon, daemon=True).start()

# Supervisor + DNA (volledig)
sim_position_qty = 0
sim_entry_price = 0.0
sim_unrealized = 0.0
sim_peak = 50000.0
pnl_history = []
equity_curve = [50000.0]

def supervisor_loop():
    global sim_position_qty, sim_entry_price, sim_unrealized, sim_peak
    while True:
        price = live_data[-1]["last"] if live_data else 0.0
        vol = live_data[-1]["volume"] if live_data else 0
        is_open = True
        real_equity = 50000.0
        if real_equity < sim_peak * 0.85:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 -15% DRAWDOWN KILL SWITCH")
            raise SystemExit("Drawdown kill")
        signal = current_dream.get("signal", "HOLD")
        if SIMULATE_TRADES and is_open and signal in ["BUY", "SELL"] and sim_position_qty == 0:
            qty = 1
            if signal == "BUY":
                sim_position_qty = qty
                sim_entry_price = price
                print(f"[{datetime.now().strftime('%H:%M:%S')}] SIM LONG OPEN @ {price:.2f} | Conf {current_dream.get('confidence', 0)}%")
            elif signal == "SELL":
                sim_position_qty = -qty
                sim_entry_price = price
                print(f"[{datetime.now().strftime('%H:%M:%S')}] SIM SHORT OPEN @ {price:.2f} | Conf {current_dream.get('confidence', 0)}%")
        if sim_position_qty != 0:
            price_diff = price - sim_entry_price
            pnl_dollars = price_diff * sim_position_qty * 5
            sim_unrealized = pnl_dollars
            current_equity = 50000 + sim_unrealized
            sim_peak = max(sim_peak, current_equity)
            dd_pct = (current_equity - sim_peak) / sim_peak * 100
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Equity: ${current_equity:,.0f} | DD: {dd_pct:.2f}% | Dream: {signal} ({current_dream.get('confidence', 0)}%)")
        row = {"timestamp": datetime.now(), "last": price, "volume": vol}
        pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
        time.sleep(1)

def dna_rewrite_daemon():
    global bible
    while True:
        try:
            summary = f"Sharpe laatste 50: {np.mean(pnl_history[-50:]) / (np.std(pnl_history[-50:]) + 1e-8) * np.sqrt(252) if len(pnl_history) > 50 else 0:.2f}"
            payload = {
                "model": "grok-4.20-0309-reasoning",
                "messages": [
                    {"role": "system", "content": "Je bent LUMINA's Bible Evolutie Engine. Sacred Core is HEILIG. Verbeter alleen evolvable_layer. Geef ALLEEN JSON met volledige nieuwe evolvable_layer."},
                    {"role": "user", "content": f"Huidige evolvable_layer:\n{json.dumps(bible['evolvable_layer'])}\nPerformance: {summary}\nOptimaliseer voor hogere Sharpe."}
                ]
            }
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=22)
            if r.status_code == 200:
                new_layer = json.loads(r.json()["choices"][0]["message"]["content"])
                bible["evolvable_layer"] = new_layer
                with open(BIBLE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(bible, f, ensure_ascii=False, indent=2)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 BIBLE EVOLVED")
        except:
            pass
        time.sleep(900)
threading.Thread(target=dna_rewrite_daemon, daemon=True).start()

if __name__ == "__main__":
    print("🚀 LUMINA v20.1 – LIVE_JSONL GESTART (visualizer kan nu draaien)")
    threading.Thread(target=supervisor_loop, daemon=True).start()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n🛑 LUMINA gestopt.")
    except SystemExit as e:
        print(e)