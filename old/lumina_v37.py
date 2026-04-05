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
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import base64
from io import BytesIO
import pyttsx3   # pip install pyttsx3 (eenmalig)
import tkinter as tk
from PIL import Image, ImageTk
import speech_recognition as sr
import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
import webbrowser
import chromadb
from chromadb.utils import embedding_functions

load_dotenv()
logging.basicConfig(filename='lumina_full_log.csv', level=logging.INFO, format='%(asctime)s,%(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIG + PARAMETERS
# =============================================================================
LIVE_JSONL = Path("live_stream.jsonl")
LIVE_JSONL.unlink(missing_ok=True)
STATE_FILE = Path("lumina_sim_state.json")
THOUGHT_LOG = Path("lumina_thought_log.jsonl")

INSTRUMENT = os.getenv("INSTRUMENT", "MES JUN26")
XAI_KEY = os.getenv("XAI_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
CROSSTRADE_TOKEN = os.getenv("CROSSTRADE_TOKEN")
CROSSTRADE_ACCOUNT = os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070")

if not CROSSTRADE_TOKEN:
    print("❌ FOUT: CROSSTRADE_TOKEN ontbreekt in .env !")
    exit(1)

DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
SIMULATE_TRADES = os.getenv("SIMULATE_TRADES", "True").lower() == "true"
if not DRY_RUN:
    SIMULATE_TRADES = False

RISK_PROFILE = os.getenv("LUMINA_RISK_PROFILE", "Balanced").lower()
if RISK_PROFILE == "conservative":
    MIN_CONFLUENCE = 0.82
    MAX_RISK_PERCENT = 0.8
elif RISK_PROFILE == "aggressive":
    MIN_CONFLUENCE = 0.65
    MAX_RISK_PERCENT = 2.0
else:
    MIN_CONFLUENCE = 0.75
    MAX_RISK_PERCENT = 1.5

NEWS_TRADING_ENABLED = True

print(f"🌌 LUMINA v21.6 – ECHTE CANDLE AGGREGATIE + ROBUUSTE API PARSING")
print(f"Risk Profile: {RISK_PROFILE.upper()} | Min Confluence: {MIN_CONFLUENCE} | Max Risk: {MAX_RISK_PERCENT}%")

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
            "last_reflection": "2026-03-27: v21.6 Echte Candle Aggregatie + Robuuste API Parsing",
            "lessons_learned": []
        }
    }
    with open(BIBLE_FILE, 'w', encoding='utf-8') as f:
        json.dump(bible, f, ensure_ascii=False, indent=2)
    return bible

bible = load_bible()
TIMEFRAMES = {"5min": 300, "15min": 900, "30min": 1800, "60min": 3600, "240min": 14400, "1440min": 86400}

# =============================================================================
# NIEUWE OHLC STRUCTUUR v21.6 – ECHTE CANDLES (SINGLE SOURCE OF TRUTH)
# =============================================================================
ohlc_1min = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
live_quotes = []
live_data_lock = threading.Lock()

# Live candle builder helpers
current_candle = None
candle_start_ts = None
prev_volume_cum = 0

# =============================================================================
# v21.7 SHORT-TERM MEMORY + PRICE-ACTION ANALYZER
# =============================================================================
from collections import deque

memory_buffer = deque(maxlen=5)

# =============================================================================
# v22 ADVANCED MARKET STRUCTURE + DYNAMIC CONFLUENCE + NARRATIVE MEMORY
# =============================================================================
regime_history = deque(maxlen=10)
narrative_memory = deque(maxlen=8)
dynamic_min_confluence = MIN_CONFLUENCE

# =============================================================================
# v23 CHART VISION - met uitgebreide logging
# =============================================================================
CHART_IMAGE_SIZE = (1400, 900)
VISION_MODEL = "grok-4-vision-0309"

# =============================================================================
# v24 VISUAL FIB DRAWER + AI ANNOTATIONS
# =============================================================================
AI_DRAWN_FIBS = {}

# =============================================================================
# v25 NARRATIVE VOICE + DISCORD OUTPUT
# =============================================================================
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "")   # vul in .env als je live naar Discord wilt

# =============================================================================
# v26 SELF-IMPROVING LOOP + VISUELE TRADE REFLECTIE
# =============================================================================
trade_reflection_history = deque(maxlen=20)   # laatste 20 reflecties voor langetermijngeheugen

# =============================================================================
# v27 FULL HUMAN PARTNER – Real-time Voice Output
# =============================================================================
VOICE_ENABLED = os.getenv("VOICE_ENABLED", "True").lower() == "true"
tts_engine = pyttsx3.init() if VOICE_ENABLED else None

# Stem instellen (Nederlands of Engels – pas aan als je wilt)
if tts_engine:
    tts_engine.setProperty('rate', 165)      # spreek-snelheid
    tts_engine.setProperty('volume', 0.9)
    # Optioneel: Nederlandse stem als je die hebt geïnstalleerd
    # tts_engine.setProperty('voice', 'nl')   # test met tts_engine.getProperty('voices')

# =============================================================================
# v28 SCREEN-SHARING SIMULATIE
# =============================================================================
SCREEN_SHARE_ENABLED = os.getenv("SCREEN_SHARE_ENABLED", "True").lower() == "true"
live_chart_window = None
latest_chart_image = None   # PhotoImage object voor Tkinter
chart_update_lock = threading.Lock()

# =============================================================================
# v29 REAL EXECUTION + DYNAMISCH RISK (3 modi: paper / sim / real)
# =============================================================================
TRADE_MODE = os.getenv("TRADE_MODE", "paper").lower()          # "paper", "sim" of "real"
MAX_RISK_PERCENT = float(os.getenv("MAX_RISK_PERCENT", 1.0))
DRAWDOWN_KILL_PERCENT = float(os.getenv("DRAWDOWN_KILL_PERCENT", 8.0))

# Live account status (wordt elke 10 sec opgehaald)
account_balance = 50000.0
account_equity = 50000.0
realized_pnl_today = 0.0
open_pnl = 0.0

# =============================================================================
# v30 INTERACTIVE HUMAN PARTNER – Voice Input + Manual Override
# =============================================================================
VOICE_INPUT_ENABLED = os.getenv("VOICE_INPUT_ENABLED", "True").lower() == "true"
voice_recognizer = sr.Recognizer() if VOICE_INPUT_ENABLED else None

# =============================================================================
# v32 LIVE DASHBOARD + AUTO JOURNAL
# =============================================================================
DASHBOARD_ENABLED = os.getenv("DASHBOARD_ENABLED", "True").lower() == "true"
JOURNAL_DIR = Path(os.getenv("JOURNAL_DIR", "journal"))
JOURNAL_DIR.mkdir(exist_ok=True)
dash_app = None

# =============================================================================
# v33 MULTI-AGENT INTERN OVERLEG + SELF-CONSISTENCY
# =============================================================================
AGENT_STYLES = {
    "scalper": "Je bent een agressieve scalper die focust op tape-reading, volume spikes en 1-5 min momentum.",
    "swing": "Je bent een geduldige swing-trader die higher-highs/lower-lows, fibs en MTF structure gebruikt.",
    "risk": "Je bent een strenge risk-manager die alleen trades toestaat met 1:2+ RR, lage drawdown en hoge confluence."
}

# =============================================================================
# v34 LONG-TERM VECTOR MEMORY & EXPERIENTIAL DATABASE
# =============================================================================
VECTOR_DB_PATH = Path("lumina_vector_db")
client = chromadb.PersistentClient(path=str(VECTOR_DB_PATH))
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
collection = client.get_or_create_collection(name="lumina_experience", embedding_function=embedding_fn)  # type: ignore[arg-type]

# =============================================================================
# v35 ADVANCED META-REASONING & COUNTER-FACTUAL SIMULATION
# =============================================================================
META_REASONING_ENABLED = True   # kan later via .env worden uitgeschakeld

# =============================================================================
# v36 DYNAMIC WORLD MODEL (MACRO + MICRO CONTEXT)
# =============================================================================
world_model = {
    "macro": {"vix": 18.5, "dxy": 103.2, "ten_year_yield": 4.15, "news_sentiment": "neutral"},
    "micro": {"regime": "NEUTRAL", "orderflow_bias": "balanced", "volume_profile": "fair_value", "last_update": None}
}

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
# v37 AUTOMATED BACKTESTING + REFLECTION FRAMEWORK
# =============================================================================
BACKTEST_ENABLED = True
BACKTEST_DAYS = 5   # aantal dagen terug voor backtest

# =============================================================================
# STATE + THOUGHT LOGGER
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
        "bible_evolvable": bible["evolvable_layer"],
        "memory_buffer": list(memory_buffer),
        "narrative_memory": list(narrative_memory),
        "regime_history": list(regime_history),
        "trade_reflection_history": list(trade_reflection_history)   # v26
    }
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Save state error: {e}")

def load_state():
    global sim_position_qty, sim_entry_price, sim_unrealized, sim_peak, pnl_history, equity_curve, current_dream, bible, memory_buffer, narrative_memory, regime_history, trade_reflection_history
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
            memory_buffer = deque(state.get("memory_buffer", []), maxlen=5)
            narrative_memory = deque(state.get("narrative_memory", []), maxlen=8)
            regime_history = deque(state.get("regime_history", []), maxlen=10)
            trade_reflection_history = deque(state.get("trade_reflection_history", []), maxlen=20)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ State hersteld (v26 met reflecties)")
        except Exception as e:
            logger.error(f"Load state error: {e}")

load_state()

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
    global current_candle, candle_start_ts, prev_volume_cum
    uri = "wss://app.crosstrade.io/ws/stream"
    headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}
    try:
        async with websockets.connect(uri, additional_headers=headers, ping_interval=20, ping_timeout=20) as ws:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ WS verbonden – 1-min candle builder actief")
            await ws.send(json.dumps({"action": "subscribe", "instruments": [INSTRUMENT]}))

            async for message in ws:
                try:
                    data = json.loads(message)
                    if data.get("type") != "marketData":
                        continue

                    for quote in data.get("quotes", []):
                        if quote.get("instrument") != INSTRUMENT:
                            continue

                        ts = datetime.now()
                        price = float(quote.get("last", 0))
                        vol_cum = int(quote.get("volume", 0))

                        with live_data_lock:
                            live_quotes.append({
                                "timestamp": ts.isoformat(),
                                "last": price,
                                "bid": float(quote.get("bid", 0)),
                                "ask": float(quote.get("ask", 0))
                            })
                            if len(live_quotes) > 3000:
                                live_quotes.pop(0)

                        minute_start = ts.replace(second=0, microsecond=0)
                        if current_candle is None or candle_start_ts != minute_start:
                            if current_candle is not None:
                                with live_data_lock:
                                    new_row = pd.DataFrame([current_candle])
                                    global ohlc_1min
                                    ohlc_1min = pd.concat([ohlc_1min, new_row]).drop_duplicates("timestamp") \
                                                  .sort_values("timestamp").reset_index(drop=True)
                                print(f"[{minute_start.strftime('%H:%M')}] 🕯️ 1-min candle gesloten → O={current_candle['open']:.2f} H={current_candle['high']:.2f} L={current_candle['low']:.2f} C={current_candle['close']:.2f} V={current_candle['volume']}")

                            current_candle = {
                                "timestamp": minute_start,
                                "open": price,
                                "high": price,
                                "low": price,
                                "close": price,
                                "volume": 0
                            }
                            candle_start_ts = minute_start
                        else:
                            current_candle["high"] = max(current_candle["high"], price)
                            current_candle["low"] = min(current_candle["low"], price)
                            current_candle["close"] = price
                            delta_vol = max(0, vol_cum - prev_volume_cum)
                            current_candle["volume"] += delta_vol
                            prev_volume_cum = vol_cum

                        print(f"[{ts.strftime('%H:%M:%S')}] 📥 LIVE tick → last={price:.2f} | candle in progress")
                except Exception as e:
                    logger.error(f"WS parse error: {e}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ WS mislukt → REST fallback")
        # (je REST fallback kun je later uitbreiden, nu even laten zoals was)

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
def detect_swing_and_fibs():
    """Swing & Fibs op echte candles (veel betrouwbaarder)"""
    with live_data_lock:
        if len(ohlc_1min) < 50:
            return 0.0, 0.0, {}
        recent = ohlc_1min.iloc[-60:]
    swing_low = float(recent["low"].min())
    swing_high = float(recent["high"].max())
    diff = swing_high - swing_low
    fib_levels = {}
    ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    for r in ratios:
        fib_levels[str(r)] = round(swing_high - diff * r, 2)
    return swing_high, swing_low, fib_levels

def get_mtf_snapshots():
    """Echte candle-resample naar alle timeframes – precies zoals een mens kijkt"""
    with live_data_lock:
        if len(ohlc_1min) < 60:
            return "PARTIAL_DATA_ONLY"
        df = ohlc_1min.copy()

    snapshots = {}
    for tf_name, seconds in TIMEFRAMES.items():
        resampled = df.set_index("timestamp").resample(f"{seconds//60}T").agg({
            "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
        }).dropna()

        if len(resampled) > 0:
            row = resampled.iloc[-1]
            snapshots[tf_name] = {
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"])
            }
        else:
            snapshots[tf_name] = {"open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0, "volume": 0}

    return json.dumps(snapshots, ensure_ascii=False)

# =============================================================================
# HISTORISCHE BARS v21.6 – CORRECTE OHLC INLADEN
# =============================================================================
def load_historical_ohlc(days_back=3, limit=5000):
    """Laadt echte 1-min OHLCV bars en zet ze in ohlc_1min"""
    print(f"📥 [v21.6] Ophalen {limit} echte 1-min OHLC bars (laatste {days_back} dagen)...")
    try:
        payload = {
            "instrument": INSTRUMENT,
            "periodType": "minute",
            "period": 1,
            "daysBack": days_back,
            "limit": limit
        }
        r = requests.post(
            "https://app.crosstrade.io/v1/api/market/bars",
            headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"},
            json=payload,
            timeout=40
        )
        if r.status_code != 200:
            print(f"❌ API error {r.status_code}: {r.text[:400]}")
            return False

        data = r.json()
        bars = (data if isinstance(data, list) else
                data.get("bars") or data.get("data") or data.get("result") or data.get("ohlc") or [])

        new_rows = []
        for bar in bars:
            ts_str = bar.get("timestamp") or bar.get("time")
            if not ts_str:
                continue
            ts = pd.to_datetime(ts_str)
            new_rows.append({
                "timestamp": ts,
                "open": float(bar.get("open") or bar.get("last") or 0),
                "high": float(bar.get("high") or bar.get("last") or 0),
                "low": float(bar.get("low") or bar.get("last") or 0),
                "close": float(bar.get("close") or bar.get("last") or 0),
                "volume": int(bar.get("volume", 0))
            })

        if new_rows:
            df_new = pd.DataFrame(new_rows)
            global ohlc_1min
            ohlc_1min = pd.concat([ohlc_1min, df_new]).drop_duplicates("timestamp") \
                          .sort_values("timestamp").reset_index(drop=True)
            print(f"✅ {len(new_rows)} historische 1-min candles geladen → ohlc_1min nu {len(ohlc_1min)} rijen")
            return True
        return False
    except Exception as e:
        print(f"❌ Historical load crash: {e}")
        logger.error(f"Historical load error: {e}")
        return False

# =============================================================================
# GAP RECOVERY
# =============================================================================
def gap_recovery_daemon():
    while True:
        time.sleep(300)
        try:
            with live_data_lock:
                if len(ohlc_1min) < 50:
                    continue
                df = ohlc_1min[["timestamp"]].copy()
                deltas = df["timestamp"].diff().dt.total_seconds()
                max_gap = deltas.max() if len(deltas) > 1 else 0
            if max_gap > 120:
                print(f"⚠️ GAP DETECTED ({max_gap/60:.1f} min) → recovery")
                load_historical_ohlc(days_back=2, limit=2000)
            else:
                load_historical_ohlc(days_back=2, limit=2000)
        except Exception as e:
            print(f"❌ Gap recovery crash: {e}")

# =============================================================================
# v21.7 PRICE-ACTION ANALYZER + CANDLE PATTERNS
# =============================================================================
def detect_candle_patterns(df: pd.DataFrame, tf: str = "1min") -> dict:
    """Simple rule-based candle patterns op de laatste 3 candles"""
    if len(df) < 3:
        return {"pattern": "unknown", "description": "te weinig data"}

    last3 = df.iloc[-3:]
    prev = last3.iloc[-2]
    curr = last3.iloc[-1]

    body = abs(curr["close"] - curr["open"])
    upper_wick = curr["high"] - max(curr["open"], curr["close"])
    lower_wick = min(curr["open"], curr["close"]) - curr["low"]
    range_size = curr["high"] - curr["low"]

    patterns = {}

    if (curr["close"] > prev["high"] and curr["open"] < prev["low"] and curr["close"] > curr["open"]):
        patterns["engulfing"] = "bullish_engulfing"
    elif (curr["close"] < prev["low"] and curr["open"] > prev["high"] and curr["close"] < curr["open"]):
        patterns["engulfing"] = "bearish_engulfing"

    if lower_wick > 2 * body and upper_wick < body * 0.5 and curr["close"] > curr["open"]:
        patterns["pinbar"] = "hammer"
    elif upper_wick > 2 * body and lower_wick < body * 0.5 and curr["close"] < curr["open"]:
        patterns["pinbar"] = "shooting_star"

    if body <= range_size * 0.1:
        patterns["doji"] = "doji"

    if curr["high"] < prev["high"] and curr["low"] > prev["low"]:
        patterns["inside"] = "inside_bar"

    if patterns:
        main = list(patterns.values())[0]
        return {"pattern": main, "description": f"{tf} {main.replace('_', ' ')}"}
    return {"pattern": "none", "description": "geen duidelijk patroon"}


def generate_price_action_summary() -> str:
    """Maakt een menselijke marktbeschrijving (HH/HL, trend, volume, patterns)"""
    with live_data_lock:
        if len(ohlc_1min) < 120:
            return "INSUFFICIENT_DATA"
        df = ohlc_1min.copy()

    summary_parts = []

    for tf_name, seconds in list(TIMEFRAMES.items())[:4]:
        res = df.set_index("timestamp").resample(f"{seconds//60}T").agg({"high": "max", "low": "min"}).dropna().iloc[-3:]
        if len(res) >= 2:
            prev_h, curr_h = res["high"].iloc[-2], res["high"].iloc[-1]
            prev_l, curr_l = res["low"].iloc[-2], res["low"].iloc[-1]
            if curr_h > prev_h and curr_l > prev_l:
                summary_parts.append(f"Higher High + Higher Low op {tf_name}")
            elif curr_h < prev_h and curr_l < prev_l:
                summary_parts.append(f"Lower High + Lower Low op {tf_name}")

    recent_vol = df["volume"].iloc[-20:].mean()
    last_vol = df["volume"].iloc[-1]
    if last_vol > recent_vol * 2.5:
        summary_parts.append(f"Volume spike {last_vol/recent_vol:.1f}x gemiddeld")

    df_5 = df.set_index("timestamp").resample("5T").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    df_15 = df.set_index("timestamp").resample("15T").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()

    pat5 = detect_candle_patterns(df_5, "5min")
    pat15 = detect_candle_patterns(df_15, "15min")
    if pat5["pattern"] != "none":
        summary_parts.append(pat5["description"])
    if pat15["pattern"] != "none":
        summary_parts.append(pat15["description"])

    current_price = df["close"].iloc[-1]
    ma20 = df["close"].rolling(20).mean().iloc[-1]
    bias = "BULLISH" if current_price > ma20 else "BEARISH"
    summary_parts.append(f"Overall bias: {bias} (prijs vs 20-period MA)")

    return " | ".join(summary_parts) if summary_parts else "NEUTRALE MARKT – geen duidelijke price action"

# =============================================================================
# v22 MARKET REGIME + STRUCTURE DETECTOR
# =============================================================================
def detect_market_regime(df: pd.DataFrame) -> str:
    """Detecteert marktregime op basis van ADX, range en volume"""
    if len(df) < 60:
        return "UNKNOWN"

    close = df["close"]
    high = df["high"]
    low = df["low"]
    vol = df["volume"]

    tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    up = (high - high.shift()).clip(lower=0)
    down = (low.shift() - low).clip(lower=0)
    plus_di = 100 * (up.ewm(alpha=1 / 14).mean() / atr)
    minus_di = 100 * (down.ewm(alpha=1 / 14).mean() / atr)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(14).mean().iloc[-1]

    avg_range = (high - low).rolling(20).mean().iloc[-1]
    recent_range = (high.iloc[-20:] - low.iloc[-20:]).mean()
    vol_spike = vol.iloc[-1] > vol.rolling(20).mean().iloc[-1] * 2.0

    if adx > 25 and recent_range > avg_range * 1.3:
        return "TRENDING"
    elif adx < 20 and recent_range < avg_range * 0.7:
        return "RANGING"
    elif vol_spike and recent_range > avg_range * 1.8:
        return "VOLATILE"
    elif abs(close.iloc[-1] - close.iloc[-20]) > avg_range * 3:
        return "BREAKOUT"
    return "NEUTRAL"


def detect_market_structure(df: pd.DataFrame) -> dict:
    """BOS, CHOCH, Order Blocks, FVG – simple maar krachtige structuur detectie"""
    if len(df) < 50:
        return {"bos": None, "choch": None, "order_blocks": [], "fvg": []}

    recent = df.iloc[-40:].reset_index(drop=True)
    highs = recent["high"]
    lows = recent["low"]

    structure = {"bos": None, "choch": None, "order_blocks": [], "fvg": []}

    last_swing_high = highs.iloc[-10:-1].max()
    last_swing_low = lows.iloc[-10:-1].min()
    current_high = highs.iloc[-1]
    current_low = lows.iloc[-1]

    if current_high > last_swing_high and current_low > last_swing_low:
        structure["bos"] = "bullish_BOS"
    elif current_high < last_swing_high and current_low < last_swing_low:
        structure["bos"] = "bearish_BOS"
    if (current_high < last_swing_high and current_low > last_swing_low) or (current_high > last_swing_high and current_low < last_swing_low):
        structure["choch"] = "CHOCH_detected"

    structure["order_blocks"] = [
        {"type": "bullish_OB", "price": float(lows.iloc[-15:-5].min())},
        {"type": "bearish_OB", "price": float(highs.iloc[-15:-5].max())}
    ]

    if len(recent) >= 3:
        c1_high = recent["high"].iloc[-3]
        c3_low = recent["low"].iloc[-1]
        if c3_low > c1_high:
            structure["fvg"].append({"type": "bullish_FVG", "price": float((c1_high + c3_low) / 2)})
        c1_low = recent["low"].iloc[-3]
        c3_high = recent["high"].iloc[-1]
        if c1_low > c3_high:
            structure["fvg"].append({"type": "bearish_FVG", "price": float((c1_low + c3_high) / 2)})

    return structure


def calculate_dynamic_confluence(regime: str, recent_winrate: float) -> float:
    """Dynamic MIN_CONFLUENCE – past zich aan aan regime en performance"""
    global dynamic_min_confluence
    base = 0.70
    if regime == "TRENDING":
        base += 0.08
    elif regime == "RANGING":
        base -= 0.05
    elif regime == "VOLATILE":
        base += 0.03
    elif regime == "BREAKOUT":
        base += 0.12

    if recent_winrate > 0.65:
        base += 0.05
    elif recent_winrate < 0.45:
        base -= 0.07

    dynamic_min_confluence = round(max(0.60, min(0.88, base)), 2)
    return dynamic_min_confluence

# =============================================================================
# v24 CHART GENERATOR – nu met AI-fib overlay + structure annotations
# =============================================================================
def generate_multi_tf_chart(ai_fibs: dict | None = None) -> str | None:
    """Genereert chart en retourneert base64 (en slaat ook lokaal op voor screen-share)"""
    start_time = time.perf_counter()

    with live_data_lock:
        if len(ohlc_1min) < 200:
            logger.info("CHART_GEN_SKIPPED,reason=insufficient_data")
            return None
        df = ohlc_1min.copy()
        df.set_index("timestamp", inplace=True)

    tfs = [("1min", "1T"), ("5min", "5T"), ("15min", "15T"), ("30min", "30T"), ("60min", "60T"), ("240min", "240T")]
    fig = make_subplots(rows=3, cols=2, subplot_titles=[name for name, _ in tfs],
                        vertical_spacing=0.08, horizontal_spacing=0.05)

    row_col = [(1, 1), (1, 2), (2, 1), (2, 2), (3, 1), (3, 2)]
    swing_high, swing_low, fib_levels = detect_swing_and_fibs()
    structure = detect_market_structure(ohlc_1min)

    for i, (tf_name, freq) in enumerate(tfs):
        res = df.resample(freq).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        if len(res) < 20:
            continue
        row, col = row_col[i]

        # Candlestick + Volume
        fig.add_trace(go.Candlestick(x=res.index, open=res["open"], high=res["high"],
                                     low=res["low"], close=res["close"], name=tf_name,
                                     increasing_line_color="#00ff88", decreasing_line_color="#ff4444"),
                      row=row, col=col)
        fig.add_trace(go.Bar(x=res.index, y=res["volume"], name="Volume",
                             marker_color="#8888ff", opacity=0.4), row=row, col=col)

        # Bot-auto fibs (geel)
        if tf_name in ["1min", "15min"]:
            for ratio, price in fib_levels.items():
                if ratio in ["0.382", "0.618", "0.786"]:
                    fig.add_hline(y=float(price), line_dash="dash", line_color="#ffff00",
                                  annotation_text=f"Bot Fib {ratio}", row=row, col=col)  # type: ignore[arg-type]

        # AI-getekende fibs (groen – v24!)
        if ai_fibs and tf_name in ["1min", "15min"]:
            for ratio, price in ai_fibs.items():
                fig.add_hline(y=float(price), line_dash="solid", line_color="#00ff00",
                              annotation_text=f"AI Fib {ratio}", row=row, col=col)  # type: ignore[arg-type]

        # Structure annotations
        if structure.get("bos"):
            fig.add_hline(y=swing_high if "bullish" in structure["bos"] else swing_low,
                          line_color="#00ffff", line_width=2, annotation_text=structure["bos"], row=row, col=col)  # type: ignore[arg-type]
        if structure.get("choch"):
            fig.add_hline(y=swing_high, line_color="#ff00ff", line_width=2, annotation_text="CHOCH", row=row, col=col)  # type: ignore[arg-type]

        # Simple OB/FVG labels
        fig.add_hline(y=structure["order_blocks"][0]["price"], line_color="#ff8800", line_dash="dot",
                      annotation_text="Bull OB", row=row, col=col)  # type: ignore[arg-type]
        fig.add_hline(y=structure["order_blocks"][1]["price"], line_color="#ff8800", line_dash="dot",
                      annotation_text="Bear OB", row=row, col=col)  # type: ignore[arg-type]

    current_price = df["close"].iloc[-1]
    regime = detect_market_regime(df.reset_index())
    fig.update_layout(
        title=f"LUMINA v24 – MES {INSTRUMENT} | Prijs {current_price:.2f} | Regime: {regime} | AI Fibs getekend | {datetime.now().strftime('%d %b %H:%M')}",
        height=900, width=1400, showlegend=False, template="plotly_dark",
        margin=dict(l=40, r=40, t=100, b=40)
    )

    img_bytes = BytesIO()
    fig.write_image(img_bytes, format="png", scale=2)
    img_bytes.seek(0)
    base64_img = base64.b64encode(img_bytes.read()).decode("utf-8")

    # v28: update screen-share venster
    if SCREEN_SHARE_ENABLED:
        update_live_chart(base64_img)

    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(f"CHART_GEN_COMPLETE,duration_ms={duration_ms:.0f},base64_kb={len(base64_img)//1000},screen_share_updated=YES")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🖼️ v28 Chart gegenereerd + screen-share geupdatet")

    return base64_img

# =============================================================================
# FINNHUB NEWS + DREAM + SUPERVISOR + DNA + BACKTESTER (ongewijzigd)
# =============================================================================
def get_high_impact_news():
    if not FINNHUB_API_KEY:
        return "No Finnhub key configured"
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        r = requests.get(
            f"https://finnhub.io/api/v1/calendar/economic?from={today}&to={today}",
            headers={"X-Finnhub-Token": FINNHUB_API_KEY},
            timeout=15
        )
        if r.status_code == 200:
            events = r.json().get("economicCalendar", [])
            high = [e for e in events if e.get("impact") in ["high", "3"] or e.get("event","").lower() in ["fomc","nfp","cpi","ppi"]]
            return high[:6] if high else "No high impact today"
        return f"Finnhub error {r.status_code}"
    except Exception as e:
        return f"Finnhub connection error: {e}"

def pre_dream_daemon():
    global current_dream, dynamic_min_confluence, AI_DRAWN_FIBS, world_model
    while True:
        cycle_start = time.perf_counter()
        try:
            with live_data_lock:
                price = live_quotes[-1]["last"] if live_quotes else (ohlc_1min["close"].iloc[-1] if len(ohlc_1min) > 0 else 0.0)
                df = ohlc_1min.copy()
            
            regime = detect_market_regime(df)
            regime_history.append({"ts": datetime.now().isoformat(), "regime": regime})
            structure = detect_market_structure(df)
            
            recent_winrate = float(np.mean(np.array(pnl_history[-15:]) > 0)) if len(pnl_history) > 10 else 0.5
            min_conf = calculate_dynamic_confluence(regime, recent_winrate)
            
            mtf_data = get_mtf_snapshots()
            swing_high, swing_low, fib_levels = detect_swing_and_fibs()
            pa_summary = generate_price_action_summary()
            
            chart_base64 = generate_multi_tf_chart()
            
            if not chart_base64:
                time.sleep(12)
                continue
            
            # v33 Multi-Agent
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🤖 Multi-Agent overleg gestart...")
            consensus = asyncio.run(multi_agent_consensus(price, mtf_data, pa_summary, structure, fib_levels))
            
            # v34 Vector Memory
            query = f"Prijs {price:.2f} | Regime {regime} | {pa_summary[:100]}"
            past_experiences = retrieve_relevant_experiences(query, n_results=4)
            
            # v35 Meta-Reasoning + Counter-Factuals
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 Meta-reasoning & counter-factuals gestart...")
            meta = asyncio.run(meta_reasoning_and_counterfactuals(consensus, price, pa_summary, past_experiences))
            
            # === v36 DYNAMIC WORLD MODEL ===
            world_model = update_world_model(df, regime, pa_summary)
            
            # Vision call met ALLE lagen (consensus + vector + meta + world model)
            vision_content = [
                {"type": "text", "text": f"""Multi-Agent Consensus: {consensus['signal']} (conf {consensus['confidence']:.2f})
Relevante ervaringen: {past_experiences}
Meta-reasoning: {meta.get('meta_reasoning', '')}
Counter-factuals: {meta.get('counterfactuals', [])}
World Model (Macro + Micro): 
Macro -> VIX {world_model['macro']['vix']:.1f}, DXY {world_model['macro']['dxy']:.1f}, 10y {world_model['macro']['ten_year_yield']:.2f}
Micro -> Regime {world_model['micro']['regime']}, Orderflow {world_model['micro']['orderflow_bias']}
Gebruik dit volledige wereld-model als basis voor je besluit.
Geef ALLEEN JSON met: signal, confidence, stop, target, reason, why_no_trade, confluence_score, chosen_strategy, fib_levels_drawn, narrative_reasoning"""},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{chart_base64}"}}
            ]
            
            # Vision call (rest exact hetzelfde als v35)
            payload = {
                "model": VISION_MODEL,
                "messages": [
                    {"role": "system", "content": "Je bent visueel getraind. Gebruik alle lagen inclusief het dynamische wereld-model."},
                    {"role": "user", "content": vision_content}
                ],
                "max_tokens": 1300
            }
            
            r = requests.post("https://api.x.ai/v1/chat/completions",
                              headers={"Authorization": f"Bearer {XAI_KEY}"},
                              json=payload, timeout=50)
            
            if r.status_code == 200:
                response_text = r.json()["choices"][0]["message"]["content"]
                try:
                    dream_json = json.loads(response_text)
                except:
                    import re
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    dream_json = json.loads(json_match.group(0)) if json_match else {"signal": "HOLD", "reason": "Parse error"}
                
                current_dream.update(dream_json)
                current_dream["confluence_score"] = max(min_conf, consensus["confidence"], meta.get("meta_score", 0.5))
                
                raw_fibs = dream_json.get("fib_levels_drawn", {})
                AI_DRAWN_FIBS = raw_fibs if isinstance(raw_fibs, dict) else {}
                narrative_reasoning = dream_json.get("narrative_reasoning", "")
                
                speak(narrative_reasoning)

                # Sla ervaring op in vector-DB
                store_experience_to_vector_db(
                    context=f"World Model Update + Dream: {narrative_reasoning[:150]}",
                    metadata={"type": "world_model_dream", "date": datetime.now().isoformat()}
                )
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌍 v36 WORLD MODEL + META DREAM: {current_dream.get('chosen_strategy')} → {current_dream['signal']} (conf={current_dream['confluence_score']:.2f})")
            
        except Exception as e:
            logger.error(f"VISION_CYCLE_CRASH: {e}", exc_info=True)
        
        time.sleep(12)

# =============================================================================
# v26 TRADE REFLECTION ENGINE
# =============================================================================
def reflect_on_trade(pnl_dollars: float, entry_price: float, exit_price: float, position_qty: int):
    """Visuele + narratieve reflectie na elke gesloten trade"""
    try:
        with live_data_lock:
            df = ohlc_1min.copy()
            price = df["close"].iloc[-1]
        
        # Chart op moment van trade-close (voor reflectie)
        chart_base64 = generate_multi_tf_chart(AI_DRAWN_FIBS if isinstance(AI_DRAWN_FIBS, dict) else {})
        
        reflection_prompt = [
            {"type": "text", "text": f"""Je hebt net een trade gesloten.
Resultaat: {'WIN' if pnl_dollars > 0 else 'LOSS'} van ${pnl_dollars:.0f}
Entry: {entry_price:.2f} | Exit: {exit_price:.2f} | Qty: {position_qty}
Kijk terug naar de chart image en je eigen vorige narrative_reasoning.
Schrijf een eerlijke 'lessons learned' in het veld 'reflection'.
Geef ALLEEN JSON met: reflection (max 400 chars), key_lesson, suggested_bible_update"""},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{chart_base64}" if chart_base64 else ""}}
        ]
        
        payload = {
            "model": VISION_MODEL,
            "messages": [
                {"role": "system", "content": "Je bent een eerlijke trading coach. Leer van elke trade en update de bible."},
                {"role": "user", "content": reflection_prompt}
            ],
            "max_tokens": 600
        }
        
        r = requests.post("https://api.x.ai/v1/chat/completions",
                          headers={"Authorization": f"Bearer {XAI_KEY}"},
                          json=payload, timeout=35)
        
        if r.status_code == 200:
            resp = r.json()["choices"][0]["message"]["content"]
            try:
                ref_json = json.loads(resp)
            except:
                import re
                m = re.search(r'\{.*\}', resp, re.DOTALL)
                ref_json = json.loads(m.group(0)) if m else {"reflection": "Parse error", "key_lesson": "N/A"}
            
            # Opslaan in geheugen
            trade_reflection_history.append({
                "ts": datetime.now().isoformat(),
                "pnl": pnl_dollars,
                "reflection": ref_json.get("reflection", ""),
                "key_lesson": ref_json.get("key_lesson", ""),
                "suggested_bible_update": ref_json.get("suggested_bible_update", {})
            })
            
            # Update bible (evolvable_layer)
            if ref_json.get("suggested_bible_update"):
                bible["evolvable_layer"].update(ref_json["suggested_bible_update"])
                with open(BIBLE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(bible, f, ensure_ascii=False, indent=2)
            
            # Mooi output
            print("\n" + "="*80)
            print(f"📝 TRADE REFLECTION @ {datetime.now().strftime('%H:%M:%S')}")
            print(f"Resultaat: {'✅ WIN' if pnl_dollars > 0 else '❌ LOSS'} ${pnl_dollars:.0f}")
            print(ref_json.get("reflection", "Geen reflectie ontvangen"))
            print(f"Key lesson: {ref_json.get('key_lesson', 'N/A')}")
            print("="*80 + "\n")
            
            logger.info(f"REFLECTION_COMPLETE,pnl={pnl_dollars:.0f},lesson={ref_json.get('key_lesson','N/A')[:80]}")
            
            # v27: Ook de reflectie hardop uitspreken
            reflection_text = ref_json.get("reflection", "Geen reflectie")
            speak(f"Trade reflection: {reflection_text}")
            
            # Naar Discord (al aanwezig)
            if DISCORD_WEBHOOK:
                try:
                    requests.post(DISCORD_WEBHOOK, json={"content": f"**📝 LUMINA REFLECTION**\nResultaat: {'WIN' if pnl_dollars > 0 else 'LOSS'} ${pnl_dollars:.0f}\n{reflection_text}"}, timeout=5)
                except:
                    pass
    except Exception as e:
        logger.error(f"REFLECTION_CRASH: {e}")

# =============================================================================
# v27 VOICE OUTPUT HELPER
# =============================================================================
def speak(text: str):
    """Laat de bot hardop praten – alleen als VOICE_ENABLED"""
    if not VOICE_ENABLED or not tts_engine:
        return
    try:
        print(f"🔊 SPEAKING: {text[:120]}...")
        tts_engine.say(text)
        tts_engine.runAndWait()
    except Exception as e:
        logger.error(f"TTS_ERROR: {e}")

# =============================================================================
# v29 ACCOUNT + ORDER HELPERS (3 modi)
# =============================================================================
def fetch_account_balance():
    global account_balance, account_equity, realized_pnl_today
    try:
        r = requests.get(
            f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}",
            headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"},
            timeout=8
        )
        if r.status_code == 200:
            data = r.json()
            account_balance = float(data.get("balance", 50000))
            account_equity = float(data.get("equity", account_balance))
            realized_pnl_today = float(data.get("realizedPnlToday", 0))
            print(f"💰 ACCOUNT [{TRADE_MODE.upper()}] -> Equity ${account_equity:,.0f} | Realized PnL ${realized_pnl_today:,.0f}")
            return True
    except Exception as e:
        logger.error(f"Balance fetch error: {e}")
    return False

def place_order(action: str, qty: int):
    """Plaats order - alleen bij 'sim' en 'real'"""
    if TRADE_MODE == "paper":
        return False  # paper doet niks naar broker

    try:
        payload = {
            "instrument": INSTRUMENT,
            "action": action.upper(),
            "orderType": "MARKET",
            "quantity": qty,
            "stopLoss": current_dream.get("stop", 0),
            "takeProfit": current_dream.get("target", 0)
        }
        r = requests.post(
            f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/orders/place",
            headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"},
            json=payload,
            timeout=10
        )
        if r.status_code in (200, 201):
            print(f"✅ {TRADE_MODE.upper()} ORDER -> {action} {qty}x @ MARKET")
            logger.info(f"{TRADE_MODE.upper()}_ORDER_SUCCESS,action={action},qty={qty}")
            return True
        else:
            logger.error(f"Order failed {r.status_code}")
            return False
    except Exception as e:
        logger.error(f"Place order error: {e}")
        return False

# =============================================================================
# v30 VOICE INPUT + MANUAL OVERRIDE
# =============================================================================
def voice_listener_thread():
    """Achtergrond thread die continu naar je stem luistert"""
    if not VOICE_INPUT_ENABLED or not voice_recognizer:
        return
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🎤 Voice Input actief - spreek commando's in (Lumina, ...)")
    
    while True:
        try:
            with sr.Microphone() as source:
                voice_recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = voice_recognizer.listen(source, timeout=8, phrase_time_limit=6)
            
            text = voice_recognizer.recognize_google(audio, language="nl-NL")  # type: ignore[attr-defined]  # of "en-US"
            text_lower = text.lower().strip()
            
            print(f"🎤 JIJ: {text}")
            
            # Simpele commando parsing
            if any(x in text_lower for x in ["status", "hoe gaat het", "wat is de status"]):
                speak(f"Huidige equity is {account_equity:,.0f} dollar. Open PnL is {open_pnl:,.0f}. Mode is {TRADE_MODE.upper()}.")
            
            elif "ga long" in text_lower or "buy" in text_lower or "long" in text_lower:
                current_dream["signal"] = "BUY"
                current_dream["confluence_score"] = 0.95
                speak("Oke, ik forceer een long positie.")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 👤 MANUAL OVERRIDE -> BUY")
            
            elif "ga short" in text_lower or "sell" in text_lower or "short" in text_lower:
                current_dream["signal"] = "SELL"
                current_dream["confluence_score"] = 0.95
                speak("Oke, ik forceer een short positie.")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 👤 MANUAL OVERRIDE -> SELL")
            
            elif "hold" in text_lower or "stop" in text_lower or "niet traden" in text_lower:
                current_dream["signal"] = "HOLD"
                speak("Begrepen, ik ga in HOLD modus.")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 👤 MANUAL OVERRIDE -> HOLD")
            
            elif "wat is je dream" in text_lower or "dream" in text_lower:
                speak(f"Mijn huidige dream is {current_dream.get('chosen_strategy', 'onbekend')} met signaal {current_dream.get('signal')}.")
            
            else:
                speak("Begrepen, maar ik ken dit commando nog niet. Probeer: Lumina status, ga long, ga short of hold.")
                
        except sr.UnknownValueError:
            pass  # stilte of onduidelijk
        except sr.RequestError as e:
            logger.error(f"Voice recognition error: {e}")
        except Exception as e:
            logger.error(f"Voice thread error: {e}")
        
        time.sleep(0.3)  # lichte pauze

# =============================================================================
# v32 DASHBOARD + AUTO JOURNAL
# =============================================================================
def generate_daily_journal():
    """Maakt een mooie HTML journal van de dag"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        file_path = JOURNAL_DIR / f"journal_{today}.html"
        
        html_content = f"""
        <html><head><title>LUMINA Journal {today}</title>
        <style>body{{font-family:Arial;background:#111;color:#0f0;}}</style></head><body>
        <h1>LUMINA v32 Daily Journal - {today}</h1>
        <h2>Account: {account_equity:,.0f} | Mode: {TRADE_MODE.upper()}</h2>
        <h3>Trades vandaag</h3>
        <table border="1" style="width:100%;border-collapse:collapse;">
        <tr><th>Tijd</th><th>Signal</th><th>PnL</th><th>Confluence</th><th>Reflection</th></tr>
        """
        for trade in trade_log[-50:]:  # laatste 50 trades
            html_content += f"<tr><td>{trade['ts']}</td><td>{trade.get('signal','')}</td><td>${trade.get('pnl',0):,.0f}</td><td>{trade.get('confluence',0):.2f}</td><td>{trade.get('reflection','')}</td></tr>"
        
        html_content += "</table><h3>Laatste reflections</h3><ul>"
        for ref in list(trade_reflection_history)[-10:]:
            html_content += f"<li>{ref['ts']} | PnL ${ref['pnl']:,.0f} -> {ref['key_lesson']}</li>"
        html_content += "</ul></body></html>"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"📄 Journal opgeslagen -> {file_path}")
        return str(file_path)
    except Exception as e:
        logger.error(f"Journal error: {e}")
        return None

def start_dashboard():
    """Start live Dash dashboard"""
    global dash_app
    if not DASHBOARD_ENABLED:
        return

    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
    
    app.layout = dbc.Container([
        html.H1("LUMINA v32 - Live Human Trading Partner", style={"textAlign": "center", "color": "#0f0"}),
        dbc.Row([
            dbc.Col([dcc.Graph(id="live-chart")], width=8),
            dbc.Col([
                html.H3("Account Status"),
                html.Div(id="status-panel", style={"fontSize": "18px", "color": "#0ff"}),
                html.H3("Equity Curve"),
                dcc.Graph(id="equity-curve"),
            ], width=4)
        ]),
        html.H3("Laatste Trades & Reflections"),
        dbc.Table(id="trade-table", bordered=True, dark=True),
        dcc.Interval(id="interval", interval=8000, n_intervals=0)
    ], fluid=True)

    @app.callback(
        [Output("live-chart", "figure"),
         Output("equity-curve", "figure"),
         Output("status-panel", "children"),
         Output("trade-table", "children")],
        Input("interval", "n_intervals")
    )
    def update_dashboard(_):
        # Live chart
        chart_base64 = generate_multi_tf_chart(AI_DRAWN_FIBS) if 'AI_DRAWN_FIBS' in globals() else None
        fig_chart = go.Figure()  # placeholder - je kunt hier later de echte chart inladen
        if chart_base64:
            # (voor simplicity tonen we een placeholder - je kunt dit later uitbreiden)
            fig_chart.add_annotation(text="Live AI Chart (zie screen-share venster)", showarrow=False)

        # Equity curve
        fig_equity = go.Figure(data=go.Scatter(y=equity_curve, mode="lines", name="Equity"))
        fig_equity.update_layout(title="Equity Curve", template="plotly_dark")

        # Status
        status = html.Div([
            html.P(f"Mode: {TRADE_MODE.upper()} | Equity: ${account_equity:,.0f}"),
            html.P(f"Open PnL: ${open_pnl:,.0f} | Realized PnL: ${realized_pnl_today:,.0f}"),
            html.P(f"Current Dream: {current_dream.get('chosen_strategy')} -> {current_dream.get('signal')} (conf {current_dream.get('confluence_score',0):.2f})")
        ])

        # Trade table
        table_header = [html.Thead(html.Tr([html.Th("Tijd"), html.Th("Signal"), html.Th("PnL"), html.Th("Conf")]))]
        rows = []
        for t in trade_log[-10:]:
            rows.append(html.Tr([html.Td(t.get("ts","")), html.Td(t.get("signal","")), html.Td(f"${t.get('pnl',0):,.0f}"), html.Td(f"{t.get('confluence',0):.2f}")]))
        table_body = [html.Tbody(rows)]
        
        return fig_chart, fig_equity, status, table_header + table_body

    dash_app = app
    print(f"🌐 Dashboard gestart -> http://127.0.0.1:8050")
    webbrowser.open("http://127.0.0.1:8050")
    app.run_server(debug=False, port=8050, use_reloader=False)

# Auto-journal daemon
def auto_journal_daemon():
    while True:
        time.sleep(3600)  # elk uur
        generate_daily_journal()

def auto_backtest_daemon():
    """Draait elke avond een backtest + reflection"""
    while True:
        time.sleep(3600 * 4)  # elke 4 uur (of pas aan naar 86400 voor dagelijks)
        if not is_market_open() and len(ohlc_1min) > 1000:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📈 Automated backtest gestart...")
            results = run_auto_backtest(BACKTEST_DAYS)
            asyncio.run(backtest_reflection(results))

# =============================================================================
# v33 MULTI-AGENT CONSENSUS ENGINE
# =============================================================================
async def multi_agent_consensus(price: float, mtf_data: str, pa_summary: str, structure: dict, fib_levels: dict) -> dict:
    """Laat 3 sub-agenten intern overleggen + self-consistency check.
    
    FUTURE-PROOF RATE-LIMIT HANDLING (belangrijk voor v34+):
    - Momenteel 3 aparte calls + 1 vision call = 4 calls per 12s.
    - Als we ooit rate-limits (429) krijgen:
        1. Parallel execution met asyncio.gather() -> latency daalt, calls blijven hetzelfde.
        2. Cache-consensus: als markt < 0.3% beweegt -> hergebruik vorige consensus (0 calls).
        3. Combineer 3 agenten in 1 prompt (met role-instructies) -> reduceert naar 1 call (kwaliteit blijft hoog, maar minder "zuiver" multi-agent).
        4. Multi-key round-robin (2-3 keys) als ultimate oplossing.
    - Dit ontwerp is future-proof: kwaliteit van bewustzijn blijft prioriteit, calls kunnen later geoptimaliseerd worden zonder architectuur te breken.
    """
    agent_votes = {}
    consistency_scores = []
    
    for agent_name, style in AGENT_STYLES.items():
        payload = {
            "model": "grok-4.20-0309-reasoning",
            "messages": [
                {"role": "system", "content": f"{style}\nGeef ALLEEN JSON met: signal (BUY/SELL/HOLD), confidence (0-1), reason (max 80 chars)"},
                {"role": "user", "content": f"""Huidige prijs: {price:.2f}
MTF: {mtf_data}
Price Action: {pa_summary}
Structure: BOS={structure.get('bos')}, CHOCH={structure.get('choch')}
Fibs: {fib_levels}
Wat is jouw trade-besluit?""" }
            ],
            "max_tokens": 150,
            "temperature": 0.3
        }
        
        try:
            r = requests.post("https://api.x.ai/v1/chat/completions",
                              headers={"Authorization": f"Bearer {XAI_KEY}"},
                              json=payload, timeout=12)
            if r.status_code == 200:
                resp = r.json()["choices"][0]["message"]["content"]
                vote = json.loads(resp)
                agent_votes[agent_name] = vote
                consistency_scores.append(vote.get("confidence", 0.5))
        except:
            agent_votes[agent_name] = {"signal": "HOLD", "confidence": 0.3, "reason": "API error"}
    
    # Self-consistency check
    signals = [v.get("signal", "HOLD") for v in agent_votes.values()]
    most_common_signal = max(set(signals), key=signals.count)
    consistency = signals.count(most_common_signal) / 3.0
    
    consensus = {
        "signal": most_common_signal if consistency >= 0.67 else "HOLD",
        "confidence": round(sum(consistency_scores) / 3 * consistency, 2),
        "reason": f"Consensus van {list(agent_votes.keys())} | Consistency {consistency:.2f}",
        "agent_votes": agent_votes
    }
    
    logger.info(f"MULTI_AGENT_CONSENSUS,signal={consensus['signal']},consistency={consistency:.2f}")
    return consensus

# =============================================================================
# v34 VECTOR MEMORY HELPERS
# =============================================================================
def store_experience_to_vector_db(context: str, metadata: dict):
    """Slaat een ervaring op in de vector-DB"""
    try:
        collection.add(
            documents=[context],
            metadatas=[metadata],
            ids=[datetime.now().isoformat()]
        )
    except Exception as e:
        logger.error(f"Vector DB store error: {e}")

def retrieve_relevant_experiences(query: str, n_results: int = 3) -> str:
    """Haalt meest relevante eerdere ervaringen op"""
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        documents = results.get("documents")
        metadatas = results.get("metadatas")
        if not documents or not metadatas or not documents[0] or not metadatas[0]:
            return "Geen relevante eerdere ervaringen gevonden."
        
        experiences = []
        for doc, meta in zip(documents[0], metadatas[0]):
            experiences.append(f"[{meta.get('date','')}] {doc} -> {meta.get('outcome','')}")
        return "\n".join(experiences)
    except Exception as e:
        logger.error(f"Vector DB retrieve error: {e}")
        return "Vector memory niet beschikbaar."

# =============================================================================
# v35 META-REASONING & COUNTER-FACTUAL ENGINE
# =============================================================================
async def meta_reasoning_and_counterfactuals(consensus: dict, price: float, pa_summary: str, past_experiences: str) -> dict:
    """Voert meta-reasoning + counter-factual simulaties uit.
    
    FUTURE-PROOF NOTE (voor v36+):
    - Momenteel 1 extra API-call.
    - Als rate-limits een probleem worden: combineer met de vision-call in een payload (minder calls, zelfde kwaliteit).
    - Counter-factuals kunnen later parallel met asyncio.gather() worden uitgevoerd.
    """
    payload = {
        "model": "grok-4.20-0309-reasoning",
        "messages": [
            {"role": "system", "content": """Je bent een strenge meta-trading coach. Geen emoties, alleen logica.
Voer de volgende twee stappen uit:
1. Meta-reasoning: Hoe goed was de huidige consensus? Wat zou een top-trader anders hebben gedaan?
2. Counter-factuals: Simuleer 3 alternatieven (geen trade, 2x groter, stop dichterbij) en geef de verwachte uitkomst.
Geef ALLEEN JSON met: meta_score (0-1), meta_reasoning (max 120 chars), counterfactuals (lijst van dicts)"""},
            {"role": "user", "content": f"""Huidige consensus: {consensus['signal']} (conf {consensus['confidence']:.2f})
Price Action: {pa_summary}
Relevante eerdere ervaringen: {past_experiences}
Prijs: {price:.2f}
Voer meta-reasoning + counter-factuals uit."""}
        ],
        "max_tokens": 400,
        "temperature": 0.2
    }
    
    try:
        r = requests.post("https://api.x.ai/v1/chat/completions",
                          headers={"Authorization": f"Bearer {XAI_KEY}"},
                          json=payload, timeout=15)
        if r.status_code == 200:
            resp = r.json()["choices"][0]["message"]["content"]
            meta = json.loads(resp)
            logger.info(f"META_REASONING_COMPLETE,meta_score={meta.get('meta_score',0.5):.2f}")
            return meta
    except Exception as e:
        logger.error(f"Meta-reasoning error: {e}")
    
    return {"meta_score": 0.6, "meta_reasoning": "Meta-reasoning niet gelukt", "counterfactuals": []}

# =============================================================================
# v36 DYNAMIC WORLD MODEL UPDATER
# =============================================================================
def update_world_model(df: pd.DataFrame, regime: str, pa_summary: str):
    """Update het dynamische wereld-model (macro + micro).
    
    FUTURE-PROOF NOTE (voor v37+):
    - Macro-data is nu placeholder (simulatie).
    - Later kunnen we echte API-calls toevoegen (Finnhub, TradingView, etc.) zonder code te breken.
    - Het model wordt automatisch in vector-DB opgeslagen zodat v34-memory het kan terugvinden.
    """
    global world_model
    
    # Micro update (direct uit data)
    world_model["micro"]["regime"] = regime
    world_model["micro"]["orderflow_bias"] = "bullish" if df["close"].iloc[-1] > df["close"].iloc[-20:].mean() else "bearish"
    world_model["micro"]["volume_profile"] = "high_volume_node" if df["volume"].iloc[-1] > df["volume"].iloc[-20:].mean() * 1.8 else "fair_value"
    world_model["micro"]["last_update"] = datetime.now().isoformat()
    
    # Macro placeholder (later echte API)
    # Voor nu simulatie op basis van regime
    if regime == "TRENDING":
        world_model["macro"]["vix"] = max(12, world_model["macro"]["vix"] - 0.3)
    elif regime == "VOLATILE":
        world_model["macro"]["vix"] = min(35, world_model["macro"]["vix"] + 0.8)
    
    # Sla het huidige wereld-model op in vector-DB voor langetermijngeheugen
    store_experience_to_vector_db(
        context=f"World Model Update: Regime {regime} | VIX {world_model['macro']['vix']:.1f} | DXY {world_model['macro']['dxy']:.1f}",
        metadata={"type": "world_model", "date": datetime.now().isoformat()}
    )
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌍 World Model geüpdatet → Regime: {regime} | VIX: {world_model['macro']['vix']:.1f}")
    return world_model

# =============================================================================
# v37 AUTOMATED BACKTESTER + REFLECTION
# =============================================================================
def run_auto_backtest(days: int = BACKTEST_DAYS) -> dict:
    """Voert een snelle backtest uit op de laatste dagen met huidige bible-regels."""
    try:
        with live_data_lock:
            df = ohlc_1min.copy()
        
        # Simpele backtest (kan later uitgebreid worden)
        bt_pnl = []
        bt_position = 0
        bt_entry = 0.0
        
        for i in range(60, len(df)):
            price = df["close"].iloc[i]
            # Gebruik dezelfde logica als supervisor (vereenvoudigd)
            signal = current_dream.get("signal", "HOLD")
            if bt_position == 0 and signal in ["BUY", "SELL"] and current_dream.get("confluence_score", 0) > MIN_CONFLUENCE:
                bt_position = 1 if signal == "BUY" else -1
                bt_entry = price
            if bt_position != 0:
                stop = current_dream.get("stop", 0)
                target = current_dream.get("target", 0)
                if (bt_position > 0 and price <= stop) or (bt_position < 0 and price >= stop) or \
                   (bt_position > 0 and price >= target) or (bt_position < 0 and price <= target):
                    pnl = (price - bt_entry) * bt_position * 5
                    bt_pnl.append(pnl)
                    bt_position = 0
        
        if not bt_pnl:
            return {"sharpe": 0, "winrate": 0, "maxdd": 0, "trades": 0}
        
        sharpe = (np.mean(bt_pnl) / (np.std(bt_pnl) + 1e-8)) * np.sqrt(252)
        winrate = np.mean(np.array(bt_pnl) > 0)
        maxdd = min((np.maximum.accumulate(np.cumsum(bt_pnl)) - np.cumsum(bt_pnl)) / np.maximum.accumulate(np.cumsum(bt_pnl))) * 100 if len(bt_pnl) > 1 else 0
        
        return {
            "sharpe": round(sharpe, 2),
            "winrate": round(winrate, 3),
            "maxdd": round(maxdd, 1),
            "trades": len(bt_pnl),
            "avg_pnl": round(np.mean(bt_pnl), 1)
        }
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        return {"sharpe": 0, "winrate": 0, "maxdd": 0, "trades": 0}

async def backtest_reflection(backtest_results: dict):
    """Laat de bot reflecteren op de backtest en de bible updaten."""
    payload = {
        "model": "grok-4.20-0309-reasoning",
        "messages": [
            {"role": "system", "content": "Je bent een strenge trading-coach. Analyseer de backtest en stel concrete bible-updates voor. Geef ALLEEN JSON."},
            {"role": "user", "content": f"""Backtest resultaten (laatste {BACKTEST_DAYS} dagen):
Sharpe: {backtest_results['sharpe']}
Winrate: {backtest_results['winrate']:.1%}
Max DD: {backtest_results['maxdd']}%
Trades: {backtest_results['trades']}
Avg PnL: ${backtest_results['avg_pnl']}
Huidige bible evolvable_layer: {json.dumps(bible['evolvable_layer'])}

Wat moet er verbeterd worden? Geef JSON met: reflection, suggested_bible_updates (dict)"""}
        ]
    }
    
    try:
        r = requests.post("https://api.x.ai/v1/chat/completions",
                          headers={"Authorization": f"Bearer {XAI_KEY}"},
                          json=payload, timeout=25)
        if r.status_code == 200:
            resp = r.json()["choices"][0]["message"]["content"]
            ref = json.loads(resp)
            
            # Update bible
            if ref.get("suggested_bible_updates"):
                bible["evolvable_layer"].update(ref["suggested_bible_updates"])
                with open(BIBLE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(bible, f, ensure_ascii=False, indent=2)
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 BACKTEST REFLECTION: {ref.get('reflection','')[:120]}")
            store_experience_to_vector_db(
                context=f"Backtest Reflection: Sharpe {backtest_results['sharpe']}, Winrate {backtest_results['winrate']:.1%}",
                metadata={"type": "backtest_reflection", "date": datetime.now().isoformat()}
            )
            return ref
    except Exception as e:
        logger.error(f"Backtest reflection error: {e}")
    return None

# =============================================================================
# v28 LIVE SCREEN-SHARING WINDOW
# =============================================================================
def update_live_chart(chart_base64: str):
    """Update het live venster met de nieuwste AI-chart"""
    global latest_chart_image
    if not SCREEN_SHARE_ENABLED or not live_chart_window:
        return
    try:
        # Base64 -> PIL Image -> Tkinter PhotoImage
        import base64
        from io import BytesIO
        img_data = base64.b64decode(chart_base64)
        pil_img = Image.open(BytesIO(img_data)).resize((1100, 620))  # mooi formaat
        with chart_update_lock:
            latest_chart_image = ImageTk.PhotoImage(pil_img)
            label_widget = getattr(live_chart_window, "label", None)
            if label_widget is not None:
                label_widget.config(image=latest_chart_image)
                label_widget.image = latest_chart_image  # reference houden
    except Exception as e:
        logger.error(f"SCREEN_SHARE_UPDATE_ERROR: {e}")

def start_screen_share_window():
    """Start het live venster (altijd bovenaan)"""
    global live_chart_window
    if not SCREEN_SHARE_ENABLED:
        return

    def create_window():
        global live_chart_window
        root = tk.Tk()
        root.title("LUMINA Live Trader Screen Share")
        root.attributes("-topmost", True)          # altijd bovenaan
        root.geometry("1120x680")
        root.configure(bg="#0f0f0f")

        label = tk.Label(root, bg="#0f0f0f")
        label.pack(padx=10, pady=10)
        setattr(root, "label", label)   # om later te updaten

        live_chart_window = root

        # Placeholder tekst tot eerste chart
        placeholder = tk.Label(root, text="Wachten op eerste AI-chart...", fg="#00ff88", bg="#0f0f0f", font=("Consolas", 14))
        placeholder.pack()
        setattr(root, "placeholder", placeholder)

        root.mainloop()

    threading.Thread(target=create_window, daemon=True).start()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🖥️ Screen-sharing venster gestart (altijd bovenaan)")

# =============================================================================
# SUPERVISOR + ORACLE
# =============================================================================
def is_market_open():
    now = datetime.now()
    hour = now.hour
    return 13 <= hour <= 21

def supervisor_loop():
    global sim_position_qty, sim_entry_price, sim_unrealized, sim_peak, account_balance, account_equity, open_pnl
    last_oracle = time.time()
    last_save = time.time()
    last_balance_fetch = time.time()

    while True:
        with live_data_lock:
            price = live_quotes[-1]["last"] if live_quotes else (ohlc_1min["close"].iloc[-1] if len(ohlc_1min) else 0.0)

        now = datetime.now()

        # Live balance ophalen
        if time.time() - last_balance_fetch > 10:
            fetch_account_balance()
            last_balance_fetch = time.time()

        # Dynamisch risk in dollars op basis van equity
        risk_dollars = account_equity * (MAX_RISK_PERCENT / 100)

        # Drawdown kill-switch ALLEEN bij echte real money
        if TRADE_MODE == "real" and account_equity < account_balance * (1 - DRAWDOWN_KILL_PERCENT/100):
            print(f"🚨 REAL DRAWDOWN KILL ({DRAWDOWN_KILL_PERCENT}%) - STOPPING")
            save_state()
            raise SystemExit("Drawdown kill - real money")

        signal = current_dream.get("signal", "HOLD")
        if not is_market_open():
            signal = "HOLD"

        # === TRADE LOGIC (3 modi) ===
        if signal in ["BUY", "SELL"] and current_dream.get("confluence_score", 0) > MIN_CONFLUENCE:
            stop_dist = abs(price - current_dream.get("stop", price * 0.99))
            qty = max(1, int(risk_dollars / (stop_dist * 5))) if stop_dist > 0 else 1

            if TRADE_MODE == "paper":
                # Pure interne sim
                if sim_position_qty == 0:
                    sim_position_qty = qty if signal == "BUY" else -qty
                    sim_entry_price = price
                    print(f"[{now.strftime('%H:%M:%S')}] 📍 PAPER {signal} {qty}x @ {price:.2f}")

            else:
                # 'sim' of 'real' -> echte order naar broker
                if place_order(signal, qty):
                    print(f"[{now.strftime('%H:%M:%S')}] ✅ {TRADE_MODE.upper()} {signal} {qty}x @ {price:.2f} (risk ${risk_dollars:.0f})")

        # PnL update
        if TRADE_MODE == "paper":
            open_pnl = (price - sim_entry_price) * sim_position_qty * 5 if sim_position_qty != 0 else 0.0
        else:
            open_pnl = account_equity - account_balance

        # DUIDELIJKE STATUSREGEL (elke seconde)
        mode_text = {"paper": "PAPER (internal sim)", "sim": "SIM (real orders on demo)", "real": "REAL MONEY"}.get(TRADE_MODE, TRADE_MODE.upper())
        print(f"[{now.strftime('%H:%M:%S')}] 💰 {mode_text} | Equity ${account_equity:,.0f} | Open PnL ${open_pnl:,.0f} | Realized ${realized_pnl_today:,.0f} | Conf {current_dream.get('confluence_score',0):.2f}")

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
# DNA REWRITE + AUTO BACKTESTER
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

def run_backtest_on_snapshot(snapshot):
    print(f"🔬 Auto-backtest gestart op {len(snapshot)} ticks")
    bt_pnl = []
    bt_equity = [50000.0]
    bt_position = 0
    bt_entry = 0.0

    for i in range(60, len(snapshot)):
        entry = snapshot[i]
        price = float(entry.get("close", entry.get("last", 0.0)))
        mtf_data = get_mtf_snapshots()
        signal = current_dream.get("signal", "HOLD")

        if bt_position == 0 and signal in ["BUY", "SELL"] and current_dream.get("confluence_score", 0) > MIN_CONFLUENCE:
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
        time.sleep(2700)
        with live_data_lock:
            if len(ohlc_1min) >= 7200 and not is_market_open():
                snapshot = ohlc_1min.tail(14400).copy().to_dict("records")
                bt_thread = threading.Thread(target=run_backtest_on_snapshot, args=(snapshot,), daemon=True)
                bt_thread.start()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 Auto-backtester gestart")

threading.Thread(target=auto_backtester_daemon, daemon=True).start()

# =============================================================================
# START – FORCE INITIAL LOAD
# =============================================================================
if __name__ == "__main__":
    print(f"🚀 LUMINA v32 – FULL HUMAN PARTNER + DASHBOARD + JOURNAL GESTART (Mode: {TRADE_MODE.upper()})")
    
    load_historical_ohlc(days_back=3, limit=5000)
    
    if SCREEN_SHARE_ENABLED:
        start_screen_share_window()
    if DASHBOARD_ENABLED:
        threading.Thread(target=start_dashboard, daemon=True).start()
    if VOICE_INPUT_ENABLED:
        threading.Thread(target=voice_listener_thread, daemon=True).start()
    
    threading.Thread(target=supervisor_loop, daemon=True).start()
    threading.Thread(target=dna_rewrite_daemon, daemon=True).start()
    threading.Thread(target=gap_recovery_daemon, daemon=True).start()
    threading.Thread(target=pre_dream_daemon, daemon=True).start()
    threading.Thread(target=auto_journal_daemon, daemon=True).start()
    threading.Thread(target=auto_backtest_daemon, daemon=True).start()
    
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        save_state()
        print("\n🛑 LUMINA v32 gestopt – alle journals en state opgeslagen.")