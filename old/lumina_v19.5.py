import os
import time
import pandas as pd
import numpy as np
import requests
import threading
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging

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
BIBLE_FILE = "lumina_daytrading_bible.json"

print("🌌 LUMINA v19.5 – EXACT SECONDEN MTF + GRACE PERIOD + FULL LOGGING")
print(f"Trading MES JUN 26 | DRY_RUN={DRY_RUN} | SIMULATE_TRADES={SIMULATE_TRADES}")

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
            "filters": ["volume_delta > 2.0x avg", "no news in next 30 min", "atr_ratio < 1.5", "price_above_ema_50", "adx > 22"],
            "probability_model": {"base_winrate": 0.71, "confluence_bonus": 0.24, "risk_penalty": 0.06},
            "last_reflection": "2026-03-26: Grace period + full logging toegevoegd"
        }
    }
    with open(BIBLE_FILE, 'w', encoding='utf-8') as f:
        json.dump(bible, f, ensure_ascii=False, indent=2)
    return bible

bible = load_bible()

TIMEFRAMES = {"5min": 300, "15min": 900, "30min": 1800, "60min": 3600, "240min": 14400, "1440min": 86400}

def get_mtf_snapshots(df):
    if len(df) < 60:  # verlaagd voor snelle start
        return "PARTIAL_DATA_ONLY"
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    snapshots = {}
    last_ts = df['timestamp'].iloc[-1]
    for tf_name, seconds in TIMEFRAMES.items():
        cutoff = last_ts - timedelta(seconds=seconds)
        window = df[df['timestamp'] >= cutoff]
        if len(window) < 2:
            snapshots[tf_name] = {"last_price": 0.0, "volume_avg": 0.0, "trend": "NEUTRAL"}
            continue
        last_price = float(window['last'].iloc[-1])
        volume_avg = float(window['volume'].mean())
        trend = "BULLISH" if last_price > window['last'].iloc[0] else "BEARISH"
        snapshots[tf_name] = {"last_price": last_price, "volume_avg": volume_avg, "trend": trend, "bars": len(window)}
        print(f"[{datetime.now().strftime('%H:%M:%S')}] MTF → {tf_name} exact {seconds}s ({len(window)} bars)")
    return json.dumps(snapshots, ensure_ascii=False)

current_dream = {"signal": "HOLD", "confidence": 0.0, "stop": 0.0, "target": 0.0, "reason": "Initial", "why_no_trade": ""}

def pre_dream_daemon():
    global current_dream
    while True:
        try:
            df = pd.read_csv(CSV_FILE).tail(3000) if os.path.exists(CSV_FILE) else pd.DataFrame()
            mtf_data = get_mtf_snapshots(df)
            price = float(df['last'].iloc[-1]) if not df.empty else 0.0

            payload = {
                "model": "grok-4.20-0309-reasoning",
                "messages": [
                    {"role": "system", "content": f"Je bent LUMINA's brein. Sacred Core is HEILIG. Geef ALTIJD de exacte keys. Als data PARTIAL is, zeg dat duidelijk in why_no_trade maar zoek toch naar setups die aan de regels voldoen.\n\nSacred Core:\n{bible['sacred_core']}\n\nEvolvable layer:\n{json.dumps(bible['evolvable_layer'], ensure_ascii=False)}\n\nGeef ALLEEN JSON."},
                    {"role": "user", "content": f"Huidige prijs: {price:.2f}\nMTF status: {mtf_data}\nWat is je trade volgens mijn regels?"}
                ]
            }
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=28)
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
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 EXACT MTF-DROOM: {current_dream['signal']} | Conf {current_dream['confidence']}%")
                if current_dream['why_no_trade']:
                    print(f"   → Waarom geen trade: {current_dream['why_no_trade']}")
                logger.info(f"DROOM: {current_dream['signal']} | Conf {current_dream['confidence']}% | {current_dream['reason']}")
        except Exception as e:
            logger.error(f"Dream error: {e}")
        time.sleep(12)

threading.Thread(target=pre_dream_daemon, daemon=True).start()

# ====================== LIVE API & SUPERVISOR (robuust) ======================
def fetch_quote():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/quote?instrument={INSTRUMENT}", headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=8)
        if r.status_code == 200:
            d = r.json()
            return float(d.get("last", 0)), int(d.get("volume", 0))
    except:
        pass
    return 0.0, 0

def get_market_status():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/market/info?instrument={INSTRUMENT}", headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=8)
        return r.json().get("status", {}).get("isOpen", False) if r.status_code == 200 else False
    except:
        return False

def get_real_portfolio_value():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}", headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=6)
        return float(r.json().get("item", {}).get("cashValue", 50000.0))
    except:
        return 50000.0

sim_position_qty = 0
sim_entry_price = 0.0
sim_unrealized = 0.0
sim_peak = 50000.0
pnl_history = []
equity_curve = [50000.0]

def supervisor_loop():
    global sim_position_qty, sim_entry_price, sim_unrealized, sim_peak
    while True:
        price, vol = fetch_quote()
        is_open = get_market_status()
        real_equity = get_real_portfolio_value()
        equity_curve.append(real_equity)

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

        if not is_open and sim_position_qty != 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 MARKT SLUITING → SIM POSITIE GECLOSET")
            sim_position_qty = 0

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
    print("🚀 LUMINA v19.5 – GRACE PERIOD + FULLY ROBUUST GESTART")
    threading.Thread(target=supervisor_loop, daemon=True).start()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n🛑 LUMINA gestopt.")
    except SystemExit as e:
        print(e)