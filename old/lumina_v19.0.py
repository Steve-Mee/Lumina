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

print("🌌 LUMINA v19.0 – LEVEND ORGANISME MET ZELF-LERENDE BIBLE")
print(f"Trading MES JUN 26 | DRY_RUN={DRY_RUN} | SIMULATE_TRADES={SIMULATE_TRADES}")

# ====================== SACRED BIBLE (Immutable Core + Evolvable Layer) ======================
def load_bible():
    if os.path.exists(BIBLE_FILE):
        with open(BIBLE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    # Starter Bible – Sacred Core is beschermd
    bible = {
        "sacred_core": """ 
        JOUW DAYTRADING REGELS (ONVERANDERBAAR):
        - A-been = initiële impuls / trendrichting
        - B-been = retrace / pullback
        - Instap: eerste duidelijke blok/vorming in B-been (confluence met fib 0.618-0.786)
        - Uitstap: gekozen retrace-niveau of breakout van de 200 ms high/low
        - Altijd fibs gebruiken (0.382, 0.5, 0.618, 0.786, 1.0)
        - Volume delta + orderflow bevestiging verplicht
        - Geen trade zonder minstens 2 confluences
        """,
        "evolvable_layer": {
            "filters": ["volume_delta > 1.5x average", "no news in next 15 min"],
            "probability_model": {"base_winrate": 0.62, "confluence_bonus": 0.18},
            "last_reflection": "2026-03-24: nog geen aanpassingen"
        }
    }
    with open(BIBLE_FILE, 'w', encoding='utf-8') as f:
        json.dump(bible, f, ensure_ascii=False, indent=2)
    return bible

bible = load_bible()

# ====================== PRE-DREAMING DAEMON (oplossing 1 + 4-light) ======================
current_dream = {"signal": "HOLD", "confidence": 0.0, "stop": 0.0, "target": 0.0, "reason": "Initial"}

def pre_dream_daemon():
    global current_dream
    while True:
        try:
            df = pd.read_csv(CSV_FILE).tail(180) if os.path.exists(CSV_FILE) else pd.DataFrame()
            price = df['last'].iloc[-1] if not df.empty else 0
            vol = df['volume'].iloc[-1] if not df.empty else 0

            payload = {
                "model": "grok-4.20-0309-reasoning",
                "messages": [
                    {"role": "system", "content": f"Je bent LUMINA's brein. Je kent de SACRED CORE regels uit de Bible (die je NOOIT mag wijzigen). Je mag alleen de evolvable_layer verbeteren.\n\nSacred Core:\n{bible['sacred_core']}\n\nEvolvable layer:\n{json.dumps(bible['evolvable_layer'], ensure_ascii=False)}\n\nGeef ALLEEN JSON met keys: signal (BUY/SELL/HOLD), confidence (0-100), stop, target, reason."},
                    {"role": "user", "content": f"Huidige prijs: {price:.2f} | Volume: {vol} | Laatste 180 bars beschikbaar. Wat is je trade volgens mijn exacte regels?"}
                ]
            }
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=25)
            if r.status_code == 200:
                dream_json = json.loads(r.json()["choices"][0]["message"]["content"])
                current_dream = dream_json
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 DROOM: {dream_json['signal']} | Conf {dream_json['confidence']}% | {dream_json['reason'][:80]}...")
        except:
            pass
        time.sleep(10)  # elke 10 seconden een nieuwe droom

threading.Thread(target=pre_dream_daemon, daemon=True).start()

# ====================== LIVE API & RISK ======================
def fetch_quote():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/quote?instrument={INSTRUMENT}", headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=8)
        if r.status_code == 200:
            d = r.json()
            return float(d.get("last", 0)), int(d.get("volume", 0))
    except:
        pass
    return 0, 0

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

        # Handel op basis van laatste droom
        if SIMULATE_TRADES and is_open and current_dream["signal"] != "HOLD":
            if sim_position_qty == 0:
                if current_dream["signal"] == "BUY":
                    sim_position_qty = 1
                    sim_entry_price = price
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] SIM LONG OPEN @ {price:.2f} | Conf {current_dream['confidence']}%")
                elif current_dream["signal"] == "SELL":
                    sim_position_qty = -1
                    sim_entry_price = price
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] SIM SHORT OPEN @ {price:.2f} | Conf {current_dream['confidence']}%")

        # SL/TP update (simpel, gebaseerd op droom)
        if sim_position_qty != 0:
            price_diff = price - sim_entry_price
            pnl_dollars = price_diff * sim_position_qty * 5
            sim_unrealized = pnl_dollars
            current_equity = 50000 + sim_unrealized
            sim_peak = max(sim_peak, current_equity)
            dd_pct = (current_equity - sim_peak) / sim_peak * 100
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Equity: ${current_equity:,.0f} | DD: {dd_pct:.2f}% | Dream Conf: {current_dream['confidence']}%")

        # Log data
        row = {"timestamp": datetime.now(), "last": price, "volume": vol}
        pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)

        time.sleep(1)

# ====================== DNA REWRITE (alleen evolvable layer) ======================
def dna_rewrite_daemon():
    global bible
    while True:
        try:
            summary = f"Sharpe laatste 50: {np.mean(pnl_history[-50:]) / (np.std(pnl_history[-50:]) + 1e-8) * np.sqrt(252) if len(pnl_history) > 50 else 0:.2f}"
            payload = {
                "model": "grok-4.20-0309-reasoning",
                "messages": [
                    {"role": "system", "content": "Je bent LUMINA's Bible Evolutie Engine. Je mag NOOIT de sacred_core wijzigen. Je mag alleen de evolvable_layer verbeteren. Geef ALLEEN JSON met nieuwe evolvable_layer."},
                    {"role": "user", "content": f"Huidige Bible evolvable layer: {json.dumps(bible['evolvable_layer'])}\nSummary: {summary}\nVerbeter de filters/probabiliteit zonder sacred core aan te raken."}
                ]
            }
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=20)
            if r.status_code == 200:
                new_layer = json.loads(r.json()["choices"][0]["message"]["content"])
                bible["evolvable_layer"] = new_layer
                with open(BIBLE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(bible, f, ensure_ascii=False, indent=2)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 BIBLE EVOLVED – nieuwe filters/probabiliteit geladen")
        except:
            pass
        time.sleep(900)

threading.Thread(target=dna_rewrite_daemon, daemon=True).start()

# ====================== START ======================
if __name__ == "__main__":
    print("🚀 LUMINA v19.0 – LEVEND ORGANISME MET ZELF-LERENDE BIBLE GESTART")
    threading.Thread(target=supervisor_loop, daemon=True).start()
    try:
        while True:
            time.sleep(60)  # hoofdthread blijft leven
    except KeyboardInterrupt:
        print("\n🛑 LUMINA gestopt.")