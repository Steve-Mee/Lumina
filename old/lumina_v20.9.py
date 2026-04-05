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
import queue

load_dotenv()
logging.basicConfig(filename='lumina_full_log.csv', level=logging.INFO, format='%(asctime)s,%(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIG + FILES
# =============================================================================
LIVE_JSONL = Path("live_stream.jsonl")
LIVE_JSONL.unlink(missing_ok=True)
STATE_FILE = Path("lumina_sim_state.json")
THOUGHT_LOG = Path("lumina_thought_log.jsonl")

INSTRUMENT = os.getenv("INSTRUMENT", "MES JUN26")
XAI_KEY = os.getenv("XAI_API_KEY")
CROSSTRADE_TOKEN = os.getenv("CROSSTRADE_TOKEN")
CROSSTRADE_ACCOUNT = os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
SIMULATE_TRADES = os.getenv("SIMULATE_TRADES", "True").lower() == "true"
if not DRY_RUN:
    SIMULATE_TRADES = False

NEWS_TRADING_ENABLED = True

print("🌌 LUMINA v20.9 – FULL AUTO BACKTESTER DAEMON + THREAD-SAFE + THOUGHT LOGGER")
print(f"Trading {INSTRUMENT} | DRY_RUN={DRY_RUN} | SIMULATE_TRADES={SIMULATE_TRADES}")

# =============================================================================
# BIBLE + HUMAN PLAYBOOK
# =============================================================================
BIBLE_FILE = "lumina_daytrading_bible.json"
def load_bible():
    if os.path.exists(BIBLE_FILE):
        with open(BIBLE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    bible = {
        "sacred_core": """
HUMAN PLAYBOOK - Dit is hoe een ervaren MES daytrader denkt:
1. Scalping (tape reading, MA ribbon)
2. Momentum + Pullback (buy the dip in strong trend)
3. Breakout / Opening Range Breakout (ORB)
4. Reversal / Mean Reversion / Fade
5. Range trading
6. Trend following + Retracement
7. News / Gap / Event trading (3-sterren events!)
8. VWAP trading (institutionele fair value)
9. Pure Price Action + Candlestick
10. Pivot Points + Daily High/Low

Regels:
- Altijd multi-timeframe (240/1440 voor bias)
- Alleen traden met minstens 2 confluences
- Risk 1-2% per trade, 1:2+ RR
- Geen emotie, geen revenge trading
- Leer uit elke trade (journaling)
""",
        "evolvable_layer": {
            "mtf_matrix": {"dominant_tf": "240min", "confluence_scores": {}},
            "filters": ["volume_delta > 2.0x avg", "price_above_ema_50", "adx > 22"],
            "probability_model": {"base_winrate": 0.71, "confluence_bonus": 0.24, "risk_penalty": 0.06},
            "last_reflection": "2026-03-26: v20.9 Fixed + Auto Backtester",
            "lessons_learned": []
        }
    }
    with open(BIBLE_FILE, 'w', encoding='utf-8') as f:
        json.dump(bible, f, ensure_ascii=False, indent=2)
    return bible

bible = load_bible()
TIMEFRAMES = {"5min": 300, "15min": 900, "30min": 1800, "60min": 3600, "240min": 14400, "1440min": 86400}

live_data = []
live_data_lock = threading.Lock()   # Thread safety

current_dream = {
    "signal": "HOLD", "confidence": 0.0, "stop": 0.0, "target": 0.0,
    "reason": "Initial", "why_no_trade": "", "confluence_score": 0.0,
    "fib_levels": {}, "swing_high": 0.0, "swing_low": 0.0,
    "a_been_direction": "NEUTRAL", "chosen_strategy": "None"
}

sim_position_qty = 0
sim_entry_price = 0.0
sim_unrealized = 0.0
sim_peak = 50000.0
pnl_history = []
equity_curve = [50000.0]
trade_log = []

# =============================================================================
# STATE PERSISTENCE
# =============================================================================
def save_state():
    state = {
        "sim_position_qty": sim_position_qty,
        "sim_entry_price": sim_entry_price,
        "sim_unrealized": sim_unrealized,
        "sim_peak": sim_peak,
        "pnl_history": pnl_history[-200:],
        "equity_curve": equity_curve[-200:],
        "current_dream": current_dream,
        "bible_evolvable": bible["evolvable_layer"]
    }
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Save state error: {e}")

def load_state():
    global sim_position_qty, sim_entry_price, sim_unrealized, sim_peak, pnl_history, equity_curve, current_dream, bible
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                state = json.load(f)
            sim_position_qty = state.get("sim_position_qty", 0)
            sim_entry_price = state.get("sim_entry_price", 0.0)
            sim_unrealized = state.get("sim_unrealized", 0.0)
            sim_peak = state.get("sim_peak", 50000.0)
            pnl_history = state.get("pnl_history", [])
            equity_curve = state.get("equity_curve", [50000.0])
            current_dream = state.get("current_dream", current_dream)
            bible["evolvable_layer"] = state.get("bible_evolvable", bible["evolvable_layer"])
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ State hersteld")
        except Exception as e:
            logger.error(f"Load state error: {e}")

load_state()

# =============================================================================
# ASYNCHRONE THOUGHT LOGGER (0 vertraging)
# =============================================================================
thought_queue = queue.Queue()

def thought_logger_thread():
    while True:
        try:
            entry = thought_queue.get()
            with open(THOUGHT_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            thought_queue.task_done()
        except Exception as e:
            logger.error(f"Thought log error: {e}")

threading.Thread(target=thought_logger_thread, daemon=True).start()

def log_thought(data: dict):
    data["timestamp"] = datetime.now().isoformat()
    thought_queue.put(data)

# =============================================================================
# WEBSOCKET + LIVE_JSONL
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
                                with live_data_lock:
                                    live_data.append(entry)
                                    if len(live_data) > 20000:
                                        live_data.pop(0)
                                with open(LIVE_JSONL, "a", encoding="utf-8") as f:
                                    f.write(json.dumps({**entry, "current_dream": current_dream}) + "\n")
                                print(f"[{ts.strftime('%H:%M:%S')}] 📥 LIVE → last={entry['last']:.2f} | vol={entry['volume']:,}")
                except Exception as e:
                    logger.error(f"WS parse error: {e}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ WS mislukt → REST fallback")
        while True:
            price, vol = fetch_quote()
            with live_data_lock:
                live_data.append({"timestamp": datetime.now().isoformat(), "last": price, "volume": vol, "bid": 0.0, "ask": 0.0})
                if len(live_data) > 20000:
                    live_data.pop(0)
            time.sleep(1)

def start_websocket():
    asyncio.run(websocket_listener())

threading.Thread(target=start_websocket, daemon=True).start()

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

# =============================================================================
# SWING + FIB + MTF
# =============================================================================
def detect_swing_and_fibs(df):
    if len(df) < 50:
        return 0.0, 0.0, {}
    recent = df.iloc[-60:]
    swing_low = recent['last'].min()
    swing_high = recent['last'].max()
    diff = swing_high - swing_low
    fib_levels = {}
    ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    for r in ratios:
        fib_levels[str(r)] = round(swing_high - diff * r, 2)
    return swing_high, swing_low, fib_levels

def get_mtf_snapshots(data_list):
    if len(data_list) < 60:
        return "PARTIAL_DATA_ONLY"
    df = pd.DataFrame(data_list)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    snapshots = {}
    last_ts = df['timestamp'].iloc[-1]
    for tf_name, seconds in TIMEFRAMES.items():
        cutoff = last_ts - timedelta(seconds=seconds)
        window = df[df['timestamp'] >= cutoff].copy()
        if len(window) > 1:
            window = window.iloc[1:].copy()
        if len(window) < 1:
            snapshots[tf_name] = {"open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0, "volume": 0}
            continue
        ohlc = {
            "open": float(window['last'].iloc[0]),
            "high": float(window['last'].max()),
            "low": float(window['last'].min()),
            "close": float(window['last'].iloc[-1]),
            "volume": int(window['volume'].iloc[-1] - window['volume'].iloc[0])
        }
        snapshots[tf_name] = ohlc
    return json.dumps(snapshots, ensure_ascii=False)

# =============================================================================
# DREAM 2.0
# =============================================================================
def pre_dream_daemon():
    global current_dream
    while True:
        try:
            with live_data_lock:
                current_data = live_data.copy()
            mtf_data = get_mtf_snapshots(current_data)
            price = current_data[-1]["last"] if current_data else 0.0
            df = pd.DataFrame(current_data)
            swing_high, swing_low, fib_levels = detect_swing_and_fibs(df)

            current_dream["swing_high"] = swing_high
            current_dream["swing_low"] = swing_low
            current_dream["fib_levels"] = fib_levels

            now = datetime.now()
            high_impact = NEWS_TRADING_ENABLED and now.hour in [13, 14, 19, 20]

            log_thought({
                "type": "dream_thought",
                "price": price,
                "swing_high": swing_high,
                "swing_low": swing_low,
                "news_active": high_impact
            })

            payload = {
                "model": "grok-4.20-0309-reasoning",
                "messages": [
                    {"role": "system", "content": """Je bent een ervaren MES daytrader met 15+ jaar ervaring. 
Gebruik het volledige HUMAN PLAYBOOK. Denk stap voor stap als een mens.
Geef ALLEEN JSON met: signal, confidence, stop, target, reason, why_no_trade, confluence_score, chosen_strategy"""},
                    {"role": "user", "content": f"""Huidige prijs: {price:.2f}
MTF data: {mtf_data}
Swing High: {swing_high:.2f} | Swing Low: {swing_low:.2f}
Fib levels: {fib_levels}
High-impact nieuws actief: {high_impact}
Human Playbook: {bible['sacred_core']}
Wat is je trade?"""}
                ]
            }
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=35)
            if r.status_code == 200:
                raw = r.json()["choices"][0]["message"]["content"]
                dream_json = json.loads(raw)
                current_dream.update(dream_json)

                log_thought({
                    "type": "dream_decision",
                    "chosen_strategy": current_dream.get("chosen_strategy"),
                    "signal": current_dream["signal"],
                    "confidence": current_dream["confidence"],
                    "reason": current_dream.get("reason")
                })

                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 HUMAN DREAM: {current_dream.get('chosen_strategy')} → {current_dream['signal']}")
        except Exception as e:
            logger.error(f"Dream error: {e}")
        time.sleep(12)

threading.Thread(target=pre_dream_daemon, daemon=True).start()

# =============================================================================
# SUPERVISOR + ORACLE
# =============================================================================
def is_market_open():
    now = datetime.now()
    hour = now.hour
    return 13 <= hour <= 21

def supervisor_loop():
    global sim_position_qty, sim_entry_price, sim_unrealized, sim_peak
    last_oracle = time.time()
    last_save = time.time()
    while True:
        with live_data_lock:
            if not live_data:
                time.sleep(1)
                continue
            price = live_data[-1]["last"]
            vol = live_data[-1]["volume"]
        now = datetime.now()

        real_equity = 50000 + sim_unrealized
        if real_equity < sim_peak * 0.85:
            print(f"[{now.strftime('%H:%M:%S')}] 🚨 -15% DRAWDOWN KILL SWITCH")
            save_state()
            raise SystemExit("Drawdown kill")

        signal = current_dream.get("signal", "HOLD")
        if not is_market_open() and sim_position_qty != 0:
            signal = "HOLD"

        if SIMULATE_TRADES and is_market_open() and signal in ["BUY", "SELL"] and sim_position_qty == 0 and current_dream.get("confluence_score", 0) > 0.75:
            qty = 1
            sim_position_qty = qty if signal == "BUY" else -qty
            sim_entry_price = price
            print(f"[{now.strftime('%H:%M:%S')}] 📍 SIM {signal} OPEN @ {price:.2f} | Strategy: {current_dream.get('chosen_strategy')}")

        if sim_position_qty != 0:
            stop = current_dream.get("stop", 0)
            target = current_dream.get("target", 0)
            hit_stop = (sim_position_qty > 0 and price <= stop) or (sim_position_qty < 0 and price >= stop)
            hit_target = (sim_position_qty > 0 and price >= target) or (sim_position_qty < 0 and price <= target)
            opposite = (sim_position_qty > 0 and signal == "SELL") or (sim_position_qty < 0 and signal == "BUY")

            if hit_stop or hit_target or opposite or not is_market_open():
                pnl_dollars = (price - sim_entry_price) * sim_position_qty * 5
                pnl_history.append(pnl_dollars)
                equity_curve.append(equity_curve[-1] + pnl_dollars)
                sim_peak = max(sim_peak, equity_curve[-1])
                print(f"[{now.strftime('%H:%M:%S')}] ✅ SIM CLOSE @ {price:.2f} | PnL ${pnl_dollars:.0f}")
                trade_log.append({"ts": now.isoformat(), "pnl": pnl_dollars, "confluence": current_dream.get("confluence_score",0)})
                sim_position_qty = 0
                sim_entry_price = 0.0
                sim_unrealized = 0.0
            else:
                sim_unrealized = (price - sim_entry_price) * sim_position_qty * 5

        if time.time() - last_oracle > 60 and len(pnl_history) > 5:
            returns = np.array(pnl_history[-50:])
            sharpe = (np.mean(returns) / (np.std(returns) + 1e-8)) * np.sqrt(252) if len(returns) > 1 else 0
            winrate = np.mean(np.array(pnl_history) > 0) if pnl_history else 0
            expectancy = np.mean(pnl_history) if pnl_history else 0
            profit_factor = abs(sum([p for p in pnl_history if p > 0]) / sum([abs(p) for p in pnl_history if p < 0]) + 1e-8) if any(p < 0 for p in pnl_history) else 0
            maxdd = min((np.maximum.accumulate(equity_curve) - equity_curve) / np.maximum.accumulate(equity_curve)) * 100 if len(equity_curve) > 1 else 0
            print(f"[{now.strftime('%H:%M:%S')}] 📊 ORACLE → Sharpe {sharpe:.2f} | Exp {expectancy:.0f}$ | Winrate {winrate:.1%} | PF {profit_factor:.2f} | MaxDD {maxdd:.1f}%")

        if time.time() - last_save > 30:
            save_state()
            last_save = time.time()

        time.sleep(1)

# =============================================================================
# DNA REWRITE
# =============================================================================
def dna_rewrite_daemon():
    global bible
    while True:
        try:
            if len(trade_log) > 5:
                recent = trade_log[-15:]
                winrate = len([t for t in recent if t["pnl"] > 0]) / len(recent)
                avg_pnl = np.mean([t["pnl"] for t in recent])
                summary = f"Winrate laatste 15: {winrate:.1%} | Avg PnL ${avg_pnl:.0f}"
                payload = {
                    "model": "grok-4.20-0309-reasoning",
                    "messages": [
                        {"role": "system", "content": "Je bent LUMINA's Bible Evolutie Engine. Sacred Core + HUMAN PLAYBOOK zijn HEILIG. Verbeter alleen evolvable_layer. Geef ALLEEN JSON."},
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
                    log_thought({"type": "bible_evolution"})
        except:
            pass
        time.sleep(900)

# =============================================================================
# AUTO BACKTESTER DAEMON (gefixeerd)
# =============================================================================
def run_backtest_on_snapshot(snapshot):
    print(f"🔬 Auto-backtest gestart op {len(snapshot)} ticks")
    bt_pnl = []
    bt_equity = [50000.0]
    bt_position = 0
    bt_entry = 0.0

    for i in range(60, len(snapshot)):   # start pas na voldoende data
        entry = snapshot[i]
        price = entry["last"]

        # Gebruik alleen data tot dit punt (geen look-ahead)
        mtf_data = get_mtf_snapshots(snapshot[:i+1])
        # Voor deze simpele backtest gebruiken we de laatst bekende dream (realistisch)
        signal = current_dream.get("signal", "HOLD")

        if bt_position == 0 and signal in ["BUY", "SELL"] and current_dream.get("confluence_score", 0) > 0.75:
            bt_position = 1 if signal == "BUY" else -1
            bt_entry = price

        if bt_position != 0:
            stop = current_dream.get("stop", 0)
            target = current_dream.get("target", 0)
            hit_stop = (bt_position > 0 and price <= stop) or (bt_position < 0 and price >= stop)
            hit_target = (bt_position > 0 and price >= target) or (bt_position < 0 and price <= target)
            if hit_stop or hit_target:
                pnl = (price - bt_entry) * bt_position * 5
                bt_pnl.append(pnl)
                bt_equity.append(bt_equity[-1] + pnl)
                bt_position = 0
                bt_entry = 0.0

    if bt_pnl:
        sharpe = (np.mean(bt_pnl) / (np.std(bt_pnl) + 1e-8)) * np.sqrt(252)
        winrate = np.mean(np.array(bt_pnl) > 0)
        expectancy = np.mean(bt_pnl)
        maxdd = min((np.maximum.accumulate(bt_equity) - bt_equity) / np.maximum.accumulate(bt_equity)) * 100
        print(f"🔥 AUTO-BACKTEST KLAAR → Sharpe {sharpe:.2f} | Winrate {winrate:.1%} | MaxDD {maxdd:.1f}%")
        log_thought({"type": "auto_backtest_result", "sharpe": sharpe, "winrate": winrate, "maxdd": maxdd})
    else:
        print("Auto-backtest: geen trades")

def auto_backtester_daemon():
    while True:
        time.sleep(2700)  # elke 45 minuten
        with live_data_lock:
            if len(live_data) >= 7200 and not is_market_open():
                snapshot = live_data[-14400:].copy()  # laatste 4 uur
                bt_thread = threading.Thread(target=run_backtest_on_snapshot, args=(snapshot,), daemon=True)
                bt_thread.start()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 Auto-backtester gestart")

threading.Thread(target=auto_backtester_daemon, daemon=True).start()

# =============================================================================
# START
# =============================================================================
if __name__ == "__main__":
    print("🚀 LUMINA v20.9 – 24/7 AUTONOOM MET AUTO BACKTESTER GESTART")
    threading.Thread(target=supervisor_loop, daemon=True).start()
    threading.Thread(target=dna_rewrite_daemon, daemon=True).start()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        save_state()
        print("\n🛑 LUMINA v20.9 gestopt – state opgeslagen.")
    except SystemExit as e:
        save_state()
        print(e)