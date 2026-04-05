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
INSTRUMENT = os.getenv("INSTRUMENT", "MES JUN26")  # ← GEEN spatie!
XAI_KEY = os.getenv("XAI_API_KEY")
CROSSTRADE_TOKEN = os.getenv("CROSSTRADE_TOKEN")
CROSSTRADE_ACCOUNT = os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
SIMULATE_TRADES = os.getenv("SIMULATE_TRADES", "True").lower() == "true"
if not DRY_RUN:
    SIMULATE_TRADES = False

CSV_FILE = "market_data_log.csv"
BIBLE_FILE = "lumina_daytrading_bible.json"

print("🌌 LUMINA v20.2 – PERFORMANCE ORACLE + CLOSED-LOOP TRADING + BACKTESTER SKELETON")
print(f"Trading {INSTRUMENT} | DRY_RUN={DRY_RUN} | SIMULATE_TRADES={SIMULATE_TRADES}")

# =============================================================================
# BIBLE
# =============================================================================
def load_bible():
    if os.path.exists(BIBLE_FILE):
        with open(BIBLE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    bible = {
        "sacred_core": """
Multi-Timeframe Bias: Altijd 5/15/30/60/240/1440 min scannen. 240/1440 bepaalt hoofdtrend (A-been richting). Lagere TFs bevestigen B-been retrace.
A-been / B-been: A-been = impuls/trendstart. B-been = retrace/pullback. Alleen traden in A-been richting.
Instap: Eerste duidelijke blok/vorming in B-been + fib 0.618-0.786 confluence + volume delta >1.5× avg + orderflow bevestiging. Minstens 2 confluences over 2+ TFs.
Uitstap: Retrace-niveau (fib extension) of breakout 200 ms high/low op lagere TF. Trail stop met 200 ms structuur.
Fibs: Altijd 0.382/0.5/0.618/0.786/1.0. Golden pocket (0.618-0.786) = hoogste-probabiliteit zone.
Volume & Orderflow: Verplichte confirmatie. Geen trade zonder volume spike op instap.
Risk Rules: Max 2% risico per trade. Harde SL. Geen overnight. Drawdown >15% = kill switch.
Psychologie: Trade alleen wat de regels zeggen – geen emotie, geen revenge trading.
""",
        "evolvable_layer": {
            "mtf_matrix": {"dominant_tf": "240min", "confluence_scores": {"240min_5min": 0.93, "240min_15min": 0.97, "240min_30min": 0.95, "1440min_60min": 0.98, "60min_5min": 0.88, "30min_15min": 0.89}},
            "filters": [
                "volume_delta > 2.0x avg",
                "no news in next 30 min",
                "atr_ratio < 1.5",
                "price_above_ema_50",
                "adx > 22"
            ],
            "probability_model": {"base_winrate": 0.71, "confluence_bonus": 0.24, "risk_penalty": 0.06},
            "last_reflection": "2026-03-26: v20.2 Performance Oracle + Closed-Loop"
        }
    }
    def make_json_serializable(obj):
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, dict):
            return {k: make_json_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [make_json_serializable(item) for item in obj]
        return obj
    bible = make_json_serializable(bible)
    with open(BIBLE_FILE, 'w', encoding='utf-8') as f:
        json.dump(bible, f, ensure_ascii=False, indent=2)
    return bible

bible = load_bible()
TIMEFRAMES = {"5min": 300, "15min": 900, "30min": 1800, "60min": 3600, "240min": 14400, "1440min": 86400}

live_data = []
current_dream = {"signal": "HOLD", "confidence": 0.0, "stop": 0.0, "target": 0.0, "reason": "Initial", "why_no_trade": "", "confluence_score": 0.0}

# =============================================================================
# WEBSOCKET + LIVE_JSONL (100% ongewijzigd zoals gevraagd)
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
                                with open(LIVE_JSONL, "a", encoding="utf-8") as f:
                                    f.write(json.dumps({
                                        **entry,
                                        "current_dream": current_dream
                                    }) + "\n")
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
# REST + MTF (exact zoals v20.1)
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
            "volume": int(window['volume'].iloc[-1] - window['volume'].iloc[0])
        }
        snapshots[tf_name] = ohlc
    return json.dumps(snapshots, ensure_ascii=False)

# =============================================================================
# DREAM 2.0 – gestructureerde reasoning
# =============================================================================
def pre_dream_daemon():
    global current_dream
    while True:
        try:
            mtf_data = get_mtf_snapshots()
            price = live_data[-1]["last"] if live_data else 0.0
            payload = {
                "model": "grok-4.20-0309-reasoning",
                "messages": [
                    {"role": "system", "content": f"""Je bent LUMINA's brein. Sacred Core is HEILIG. Denk stap-voor-stap:
1. Bepaal A/B-been bias op 240/1440
2. Check confluences (min 2 over 2+ TFs)
3. Golden pocket + volume delta + filters
4. Geef ALLEEN JSON met: signal, confidence, stop, target, reason, why_no_trade, confluence_score (0-1)"""},
                    {"role": "user", "content": f"Huidige prijs: {price:.2f}\nVolledige MTF OHLC bars:\n{mtf_data}\nEvolvable layer:\n{json.dumps(bible['evolvable_layer'], ensure_ascii=False)}\nWat is je trade volgens mijn regels?"}
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
                    "why_no_trade": dream_json.get("why_no_trade", ""),
                    "confluence_score": dream_json.get("confluence_score", 0.0)
                }
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 DREAM 2.0: {current_dream['signal']} | Conf {current_dream['confidence']}% | Confluence {current_dream['confluence_score']:.2f}")
                if current_dream['why_no_trade']:
                    print(f" → Waarom geen trade: {current_dream['why_no_trade']}")
        except Exception as e:
            logger.error(f"Dream error: {e}")
        time.sleep(12)

threading.Thread(target=pre_dream_daemon, daemon=True).start()

# =============================================================================
# SUPERVISOR + PERFORMANCE ORACLE + BACKTESTER SKELETON
# =============================================================================
sim_position_qty = 0
sim_entry_price = 0.0
sim_unrealized = 0.0
sim_peak = 50000.0
pnl_history = []          # realised PnL per closed trade
equity_curve = [50000.0]
trade_log = []

def is_market_open():
    # MES RTH (9:30-16:00 ET) – eenvoudige guard
    now = datetime.now()
    hour = now.hour
    return 13 <= hour <= 21  # UTC → ET +4 (summer) approx

def supervisor_loop():
    global sim_position_qty, sim_entry_price, sim_unrealized, sim_peak
    last_oracle = time.time()
    while True:
        if not live_data:
            time.sleep(1)
            continue
        price = live_data[-1]["last"]
        vol = live_data[-1]["volume"]
        now = datetime.now()

        # Drawdown kill
        real_equity = 50000 + sim_unrealized
        if real_equity < sim_peak * 0.85:
            print(f"[{now.strftime('%H:%M:%S')}] 🚨 -15% DRAWDOWN KILL SWITCH")
            raise SystemExit("Drawdown kill")

        # Markt-uren guard
        signal = current_dream.get("signal", "HOLD")
        if not is_market_open() and sim_position_qty != 0:
            print(f"[{now.strftime('%H:%M:%S')}] 🌙 Markt gesloten → force close")
            signal = "HOLD"

        # Entry
        if SIMULATE_TRADES and is_market_open() and signal in ["BUY", "SELL"] and sim_position_qty == 0 and current_dream.get("confluence_score", 0) > 0.75:
            qty = 1
            sim_position_qty = qty if signal == "BUY" else -qty
            sim_entry_price = price
            print(f"[{now.strftime('%H:%M:%S')}] 📍 SIM {signal} OPEN @ {price:.2f} | Conf {current_dream.get('confidence',0)}%")

        # Exit + trailing
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
                print(f"[{now.strftime('%H:%M:%S')}] ✅ SIM { 'LONG' if sim_position_qty>0 else 'SHORT'} CLOSE @ {price:.2f} | PnL ${pnl_dollars:.0f}")
                trade_log.append({"ts": now, "pnl": pnl_dollars, "confluence": current_dream.get("confluence_score",0)})
                sim_position_qty = 0
                sim_entry_price = 0.0
                sim_unrealized = 0.0

            else:
                # unrealized
                price_diff = price - sim_entry_price
                sim_unrealized = price_diff * sim_position_qty * 5
                current_equity = 50000 + sim_unrealized
                sim_peak = max(sim_peak, current_equity)

        # Performance Oracle (elke 60s)
        if time.time() - last_oracle > 60 and len(pnl_history) > 5:
            last_oracle = time.time()
            returns = np.array(pnl_history[-50:])
            sharpe = (np.mean(returns) / (np.std(returns) + 1e-8)) * np.sqrt(252) if len(returns) > 1 else 0
            winrate = np.mean(np.array(pnl_history) > 0) if pnl_history else 0
            expectancy = np.mean(pnl_history) if pnl_history else 0
            profit_factor = abs(sum([p for p in pnl_history if p > 0]) / sum([abs(p) for p in pnl_history if p < 0]) + 1e-8) if any(p < 0 for p in pnl_history) else 0
            maxdd = min((np.maximum.accumulate(equity_curve) - equity_curve) / np.maximum.accumulate(equity_curve)) * 100 if len(equity_curve) > 1 else 0

            print(f"[{now.strftime('%H:%M:%S')}] 📊 ORACLE → Sharpe {sharpe:.2f} | Exp {expectancy:.0f}$ | Winrate {winrate:.1%} | PF {profit_factor:.2f} | MaxDD {maxdd:.1f}% | Trades {len(pnl_history)}")

        # logging
        row = {"timestamp": now, "last": price, "volume": vol}
        pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
        time.sleep(1)

# =============================================================================
# DNA + BACKTESTER SKELETON (hergebruikt exact dezelfde MTF/dream logic)
# =============================================================================
def dna_rewrite_daemon():
    global bible
    while True:
        try:
            sharpe = np.mean(pnl_history[-50:]) / (np.std(pnl_history[-50:]) + 1e-8) * np.sqrt(252) if len(pnl_history) > 50 else 0
            summary = f"Sharpe: {sharpe:.2f} | Trades: {len(pnl_history)} | Equity: ${equity_curve[-1]:,.0f}"
            payload = {
                "model": "grok-4.20-0309-reasoning",
                "messages": [
                    {"role": "system", "content": "Je bent LUMINA's Bible Evolutie Engine. Sacred Core is HEILIG. Verbeter alleen evolvable_layer. Geef ALLEEN JSON."},
                    {"role": "user", "content": f"Huidige evolvable_layer:\n{json.dumps(bible['evolvable_layer'])}\nPerformance: {summary}\nTrade log samenvatting: {len(trade_log)} trades.\nOptimaliseer voor hogere Sharpe + lagere DD."}
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

def run_backtester(historical_jsonl_path: str = "historical_stream.jsonl"):
    """Backtester skeleton – replayt exact dezelfde logic als live"""
    print("🔬 Backtester gestart – replayt MTF + Dream + Oracle")
    # Hier laad je historische ticks en simuleer je supervisor_loop + dream
    # (implementatie in volgende sessie als we data hebben)
    print("✅ Backtester skeleton klaar voor echte historische data")

threading.Thread(target=dna_rewrite_daemon, daemon=True).start()

if __name__ == "__main__":
    print("🚀 LUMINA v20.2 – LIVE + ORACLE GESTART")
    threading.Thread(target=supervisor_loop, daemon=True).start()
    # run_backtester()  # uncomment als je wilt testen
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n🛑 LUMINA gestopt.")
    except SystemExit as e:
        print(e)