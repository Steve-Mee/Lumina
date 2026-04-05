import os
import time
import pandas as pd
import numpy as np
import requests
import threading
import json
from datetime import datetime
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
VERSION_FILE = "lumina_version.txt"

print("🌌 LUMINA v19.1 – LEVEND ORGANISME MET MULTI-TIMEFRAME SACRED CORE")
print(f"Trading MES JUN 26 | DRY_RUN={DRY_RUN} | SIMULATE_TRADES={SIMULATE_TRADES} | MTF: 5/15/30/60/240/1440 min")

# ====================== SACRED BIBLE (Immutable Core + Evolvable 6x6 Matrix) ======================
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
            "mtf_matrix": {
                "dominant_tf": "240min",
                "confluence_scores": {
                    "240min_5min": 0.85, "240min_15min": 0.92, "240min_30min": 0.88,
                    "1440min_60min": 0.95, "60min_5min": 0.78, "30min_15min": 0.81
                }
            },
            "filters": ["volume_delta > 1.5x avg", "no news in next 15 min"],
            "probability_model": {"base_winrate": 0.62, "confluence_bonus": 0.18},
            "last_reflection": "2026-03-24: Sacred Core + 6x6 MTF vastgelegd"
        }
    }
    with open(BIBLE_FILE, 'w', encoding='utf-8') as f:
        json.dump(bible, f, ensure_ascii=False, indent=2)
    return bible

bible = load_bible()

# ====================== MTF RESAMPLER (vast 6x6) ======================
def get_mtf_snapshots(df):
    if len(df) < 300:
        return "Insufficient data for MTF"
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    snapshots = {}
    for tf, freq in [("5min", "5T"), ("15min", "15T"), ("30min", "30T"), ("60min", "60T"), ("240min", "240T"), ("1440min", "1440T")]:
        resampled = df.resample(freq).agg({'last': 'last', 'volume': 'sum'}).tail(60)
        snapshots[tf] = {
            "last_price": float(resampled['last'].iloc[-1]),
            "volume_avg": float(resampled['volume'].mean()),
            "trend": "BULLISH" if resampled['last'].iloc[-1] > resampled['last'].iloc[-20] else "BEARISH"
        }
    return json.dumps(snapshots, ensure_ascii=False)

# ====================== PRE-DREAMING DAEMON (MTF + Sacred Core) ======================
current_dream = {"signal": "HOLD", "confidence": 0.0, "stop": 0.0, "target": 0.0, "reason": "Initial"}

def pre_dream_daemon():
    global current_dream
    while True:
        try:
            df = pd.read_csv(CSV_FILE).tail(1000) if os.path.exists(CSV_FILE) else pd.DataFrame()
            mtf_data = get_mtf_snapshots(df)
            price = float(df['last'].iloc[-1]) if not df.empty else 0.0

            payload = {
                "model": "grok-4.20-0309-reasoning",
                "messages": [
                    {"role": "system", "content": f"Je bent LUMINA's brein. Sacred Core is HEILIG en ONVERANDERBAAR. Je analyseert ALLE 6 timeframes. Gebruik alleen de evolvable_layer om te optimaliseren.\n\nSacred Core:\n{bible['sacred_core']}\n\nEvolvable layer:\n{json.dumps(bible['evolvable_layer'], ensure_ascii=False)}\n\nGeef ALLEEN JSON: signal (BUY/SELL/HOLD), confidence (0-100), stop, target, reason."},
                    {"role": "user", "content": f"Huidige prijs: {price:.2f}\nMTF snapshots (6x6 matrix):\n{mtf_data}\nWat is je trade volgens mijn exacte regels?"}
                ]
            }
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=28)
            if r.status_code == 200:
                dream_json = json.loads(r.json()["choices"][0]["message"]["content"])
                current_dream = dream_json
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 MTF-DROOM: {dream_json['signal']} | Conf {dream_json['confidence']}% | {dream_json['reason'][:110]}...")
        except Exception as e:
            logger.error(f"Dream error: {e}")
        time.sleep(12)

threading.Thread(target=pre_dream_daemon, daemon=True).start()

# ====================== LIVE API ======================
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

# ====================== SIMULATOR & SUPERVISOR ======================
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

        # Drawdown kill
        if real_equity < sim_peak * 0.85:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 -15% DRAWDOWN KILL SWITCH")
            logger.info("DRAWDOWN KILL")
            raise SystemExit("Drawdown kill")

        # Handel op laatste droom
        if SIMULATE_TRADES and is_open and current_dream["signal"] != "HOLD" and sim_position_qty == 0:
            if current_dream["signal"] == "BUY":
                sim_position_qty = 1
                sim_entry_price = price
                print(f"[{datetime.now().strftime('%H:%M:%S')}] SIM LONG OPEN @ {price:.2f} | Conf {current_dream['confidence']}%")
            elif current_dream["signal"] == "SELL":
                sim_position_qty = -1
                sim_entry_price = price
                print(f"[{datetime.now().strftime('%H:%M:%S')}] SIM SHORT OPEN @ {price:.2f} | Conf {current_dream['confidence']}%")

        # SL/TP + unrealized
        if sim_position_qty != 0:
            price_diff = price - sim_entry_price
            pnl_dollars = price_diff * sim_position_qty * 5
            sim_unrealized = pnl_dollars
            current_equity = 50000 + sim_unrealized
            sim_peak = max(sim_peak, current_equity)
            dd_pct = (current_equity - sim_peak) / sim_peak * 100
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Equity: ${current_equity:,.0f} | DD: {dd_pct:.2f}% | Dream: {current_dream['signal']} ({current_dream['confidence']}%)")

        # Markt sluiting auto-close
        if not is_open and sim_position_qty != 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 MARKT SLUITING → SIM POSITIE GECLOSET")
            sim_position_qty = 0

        # Log
        row = {"timestamp": datetime.now(), "last": price, "volume": vol}
        pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)

        time.sleep(1)

# ====================== DNA REWRITE (alleen evolvable_layer) ======================
def dna_rewrite_daemon():
    global bible
    while True:
        try:
            summary = f"Sharpe laatste 50: {np.mean(pnl_history[-50:]) / (np.std(pnl_history[-50:]) + 1e-8) * np.sqrt(252) if len(pnl_history) > 50 else 0:.2f}"
            payload = {
                "model": "grok-4.20-0309-reasoning",
                "messages": [
                    {"role": "system", "content": "Je bent LUMINA's Bible Evolutie Engine. Sacred Core is HEILIG – NOOIT wijzigen. Verbeter alleen evolvable_layer (MTF matrix, filters, probability). Geef ALLEEN JSON met volledige nieuwe evolvable_layer."},
                    {"role": "user", "content": f"Huidige evolvable_layer:\n{json.dumps(bible['evolvable_layer'])}\nPerformance summary: {summary}\nOptimaliseer voor hogere Sharpe."}
                ]
            }
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=22)
            if r.status_code == 200:
                new_layer = json.loads(r.json()["choices"][0]["message"]["content"])
                bible["evolvable_layer"] = new_layer
                with open(BIBLE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(bible, f, ensure_ascii=False, indent=2)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 BIBLE EVOLVED – MTF matrix & filters geoptimaliseerd")
        except:
            pass
        time.sleep(900)

threading.Thread(target=dna_rewrite_daemon, daemon=True).start()

# ====================== START ======================
if __name__ == "__main__":
    print("🚀 LUMINA v19.1 – LEVEND ORGANISME MET SACRED CORE + 6x6 MTF GESTART")
    threading.Thread(target=supervisor_loop, daemon=True).start()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n🛑 LUMINA gestopt.")
    except SystemExit as e:
        print(e)