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
from typing import Any
from dotenv import load_dotenv
from pathlib import Path
import queue
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.figure_factory as ff
import base64
from io import BytesIO
import pyttsx3   # pip install pyttsx3 (one-time)
import tkinter as tk
from PIL import Image, ImageTk
from fpdf import FPDF
import warnings

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message="aifc was removed in Python 3.13.*",
        category=DeprecationWarning,
    )
    import speech_recognition as sr
import dash
from dash import dcc, html, Input, Output, no_update
import dash_bootstrap_components as dbc
import webbrowser
import chromadb
from chromadb.utils import embedding_functions
from lumina_core.logging_utils import build_logger
from lumina_core.news_utils import resolve_news_multiplier
from lumina_core import backtest_workers
from lumina_core.runtime_bootstrap import start_runtime_services
from lumina_core import runtime_workers
from lumina_core import trade_workers
from lumina_core.runtime_context import RuntimeContext
from lumina_core.threading_utils import start_daemon
from lumina_core.xai_client import post_xai_chat as core_post_xai_chat

load_dotenv()
LOG_LEVEL = os.getenv("LUMINA_LOG_LEVEL", "INFO").upper()
logger = build_logger("lumina", log_level=LOG_LEVEL, file_path="lumina_full_log.csv")
RUNTIME_CONTEXT = RuntimeContext(app=__import__("sys").modules[__name__])


def post_xai_chat(payload: dict, timeout: int = 20, context: str = "xai", max_retries: int = 2):
    """Centrale XAI-call met retry + 429 backoff zodat alle paden consistent zijn."""
    return core_post_xai_chat(
        payload=payload,
        xai_key=XAI_KEY,
        logger=logger,
        timeout=timeout,
        context=context,
        max_retries=max_retries,
        on_rate_limited=rate_limit_backoff,
    )

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
    print("⚠️ CROSSTRADE_TOKEN ontbreekt in .env – runtime trading blijft uit tot startup-validatie.")


def validate_runtime_config() -> bool:
    if not CROSSTRADE_TOKEN:
        logger.error("Config validation failed: CROSSTRADE_TOKEN ontbreekt")
        print("❌ FOUT: CROSSTRADE_TOKEN ontbreekt in .env !")
        return False
    return True

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
# OHLC STRUCTURE v21.6 - REAL CANDLES (SINGLE SOURCE OF TRUTH)
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
# v23 CHART VISION - with extended logging
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
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "")   # Set in .env to post live updates to Discord

# =============================================================================
# v26 SELF-IMPROVING LOOP + VISUAL TRADE REFLECTION
# =============================================================================
trade_reflection_history = deque(maxlen=20)   # Keep recent reflections for long-term adaptation

# =============================================================================
# v41 NATURAL TTS + CONVERSATIONAL UPGRADE
# =============================================================================
VOICE_ENABLED = os.getenv("VOICE_ENABLED", "True").lower() == "true"
TTS_LANGUAGE = "nl"   # "nl" for Dutch, "en" for English
tts_engine = pyttsx3.init() if VOICE_ENABLED else None

if tts_engine:
    tts_engine.setProperty('rate', 172)      # Slightly slower for natural speech
    tts_engine.setProperty('volume', 0.95)
    
    # Prefer a Dutch voice when available on the host system.
    try:
        voices = tts_engine.getProperty('voices')
        if voices:
            # Iterate through voices and pick the best Dutch match.
            for voice in voices:  # type: ignore
                if TTS_LANGUAGE in voice.id.lower() or "dutch" in voice.name.lower():
                    tts_engine.setProperty('voice', voice.id)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🎤 TTS stem ingesteld: {voice.name}")
                    break
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ No Dutch voice found - using default")
    except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Voice detection error: {e} - using default")
    
    # Future option: swap pyttsx3 with ElevenLabs/Azure TTS by changing speak() only.

# =============================================================================
# v28 SCREEN-SHARING SIMULATION
# =============================================================================
SCREEN_SHARE_ENABLED = os.getenv("SCREEN_SHARE_ENABLED", "True").lower() == "true"
live_chart_window = None
latest_chart_image = None   # Tkinter PhotoImage reference
chart_update_lock = threading.Lock()

# =============================================================================
# v29 REAL EXECUTION + DYNAMIC RISK (3 modes: paper / sim / real)
# =============================================================================
TRADE_MODE = os.getenv("TRADE_MODE", "paper").lower()          # "paper", "sim", or "real"
MAX_RISK_PERCENT = float(os.getenv("MAX_RISK_PERCENT", 1.0))
DRAWDOWN_KILL_PERCENT = float(os.getenv("DRAWDOWN_KILL_PERCENT", 8.0))

# Live account status (refreshed every 10 seconds)
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
META_REASONING_ENABLED = True   # Can be toggled via .env later

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
current_dream_lock = threading.RLock()


def get_current_dream_snapshot() -> dict:
    with current_dream_lock:
        return dict(current_dream)


def set_current_dream_fields(updates: dict) -> None:
    with current_dream_lock:
        current_dream.update(updates)


def set_current_dream_value(key: str, value) -> None:
    with current_dream_lock:
        current_dream[key] = value

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
BACKTEST_DAYS = 5   # Number of days used for auto-backtests

# =============================================================================
# v38 ADVANCED PERFORMANCE ANALYTICS & STRATEGY HEATMAPS
# =============================================================================
performance_log = []   # Trade analytics rows (trade + regime + strategy)

# =============================================================================
# v39 PROFESSIONAL PDF JOURNAL & STRUCTURED TRADE REVIEW
# =============================================================================
JOURNAL_PDF_DIR = Path("journal/pdf")
JOURNAL_PDF_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# v40 ADAPTIVE REGIME-BASED RISK & POSITION SIZING
# =============================================================================
REGIME_RISK_MULTIPLIERS = {
    "TRENDING": 1.4,
    "BREAKOUT": 1.6,
    "VOLATILE": 0.7,
    "RANGING": 0.5,
    "NEUTRAL": 0.9
}

# =============================================================================
# v41 NATURAL CONVERSATIONAL VOICE SYSTEM
# =============================================================================
VOICE_WAKE_WORD = "lumina"
# TTS_LANGUAGE is already defined in the v41 TTS section above

# =============================================================================
# v42 USER FEEDBACK LOOP & CUSTOM STRATEGY INTEGRATION
# =============================================================================
FEEDBACK_ENABLED = True

# =============================================================================
# v43 REAL-TIME NEWS SENTIMENT & EVENT IMPACT
# =============================================================================
NEWS_IMPACT_MULTIPLIERS = {
    "high_bullish": 1.3,
    "high_bearish": 0.6,
    "high_neutral": 0.9,
    "medium_bullish": 1.1,
    "medium_bearish": 0.9,
    "medium_neutral": 1.0
}

# =============================================================================
# v44 FINAL SYSTEM STABILITY, ERROR HANDLING & OPTIMIZATION
# =============================================================================
RATE_LIMIT_BACKOFF = 0      # Backoff seconds applied after 429 responses
MAX_RESTARTS = 5
restart_count = 0
TICK_PRINT_INTERVAL_SEC = 2.0
STATUS_PRINT_INTERVAL_SEC = 5.0

# =============================================================================
# v45 HUMAN-LIKE KOSTEN-EFFICIENTE ARCHITECTUUR
# =============================================================================
LAST_CANDLE_TIME = None
COST_TRACKER = {"today": 0.0, "reasoning_tokens": 0, "vision_tokens": 0, "cached_analyses": 0}
EVENT_THRESHOLD = 0.003   # 0.3% prijsbeweging = trigger voor diepe analyse
USE_HUMAN_MAIN_LOOP = os.getenv("USE_HUMAN_MAIN_LOOP", "True").lower() == "true"
START_PRE_DREAM_BACKUP = os.getenv("START_PRE_DREAM_BACKUP", "False").lower() == "true"
DASHBOARD_CHART_REFRESH_SEC = int(os.getenv("DASHBOARD_CHART_REFRESH_SEC", "20"))
DASHBOARD_LAST_CHART_TS = 0.0
DASHBOARD_LAST_HAS_IMAGE = False
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))
DEEP_ANALYSIS_CACHE_LOCK = threading.Lock()
LAST_DEEP_ANALYSIS = {
    "timestamp": None,
    "price": 0.0,
    "regime": "UNKNOWN",
    "pa_signature": "",
    "consensus": None,
    "meta": None,
    "dream_snapshot": None,
}

# =============================================================================
# STATE + THOUGHT LOGGER
# =============================================================================
def save_state():
    dream_snapshot = get_current_dream_snapshot()
    state = {
        "sim_position_qty": sim_position_qty,
        "sim_entry_price": sim_entry_price,
        "sim_unrealized": sim_unrealized,
        "sim_peak": sim_peak,
        "pnl_history": pnl_history[-200:],
        "equity_curve": equity_curve[-200:],
        "current_dream": dream_snapshot,
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
    global sim_position_qty, sim_entry_price, sim_unrealized, sim_peak, pnl_history, equity_curve, bible, memory_buffer, narrative_memory, regime_history, trade_reflection_history
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
            loaded_dream = state.get("current_dream")
            if isinstance(loaded_dream, dict):
                set_current_dream_fields(loaded_dream)
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

def log_thought(data: dict):
    data["timestamp"] = datetime.now().isoformat()
    thought_queue.put(data)

# =============================================================================
# WEBSOCKET + LIVE_JSONL
# =============================================================================
async def websocket_listener():
    global current_candle, candle_start_ts, prev_volume_cum
    last_tick_print = 0.0
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

                        if time.time() - last_tick_print >= TICK_PRINT_INTERVAL_SEC:
                            print(f"[{ts.strftime('%H:%M:%S')}] 📥 LIVE tick → last={price:.2f} | candle in progress")
                            last_tick_print = time.time()
                except Exception as e:
                    logger.error(f"WS parse error: {e}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ WS mislukt → REST fallback")
        # REST fallback can be extended later; keep current behavior for now.

def start_websocket():
    asyncio.run(websocket_listener())

def fetch_quote():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/quote?instrument={INSTRUMENT}",
                         headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=8)
        if r.status_code == 200:
            d = r.json()
            return float(d.get("last", 0)), int(d.get("volume", 0))
    except requests.RequestException as e:
        logger.error(f"Fetch quote request error: {e}")
    except (ValueError, TypeError) as e:
        logger.error(f"Fetch quote parse error: {e}")
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

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    snapshots = {}
    for tf_name, seconds in TIMEFRAMES.items():
        resampled = df.set_index("timestamp").resample(f"{seconds//60}min").agg({
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
# HISTORICAL BARS v21.6 - LOAD CANONICAL OHLC DATA
# =============================================================================
def load_historical_ohlc(days_back=3, limit=5000):
    """Load real 1-minute OHLCV bars into ohlc_1min."""
    print(f"📥 [v21.6] Loading {limit} real 1-min OHLC bars (last {days_back} days)...")
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
            # Normalize to tz-naive so live WS timestamps (datetime.now()) stay comparable.
            if ts.tzinfo is not None:
                ts = ts.tz_convert(None)
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

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    summary_parts = []

    for tf_name, seconds in list(TIMEFRAMES.items())[:4]:
        res = df.set_index("timestamp").resample(f"{seconds//60}min").agg({"high": "max", "low": "min"}).dropna().iloc[-3:]
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

    df_5 = df.set_index("timestamp").resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    df_15 = df.set_index("timestamp").resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()

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
# v24 CHART GENERATOR - with AI fib overlay + structure annotations
# =============================================================================
def generate_multi_tf_chart(ai_fibs: dict | None = None) -> str | None:
    """Genereert chart en retourneert base64 (en slaat ook lokaal op voor screen-share)"""
    start_time = time.perf_counter()

    with live_data_lock:
        if len(ohlc_1min) < 200:
            logger.info("CHART_GEN_SKIPPED,reason=insufficient_data")
            return None
        df = ohlc_1min.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)

    tfs = [("1min", "1min"), ("5min", "5min"), ("15min", "15min"), ("30min", "30min"), ("60min", "60min"), ("240min", "240min")]
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

    # Update the live screen-share window.
    if SCREEN_SHARE_ENABLED:
        update_live_chart(base64_img)

    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(f"CHART_GEN_COMPLETE,duration_ms={duration_ms:.0f},base64_kb={len(base64_img)//1000},screen_share_updated=YES")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🖼️ v28 Chart gegenereerd + screen-share geupdatet")

    return base64_img

# =============================================================================
# FINNHUB NEWS + DREAM + SUPERVISOR + DNA + BACKTESTER
# =============================================================================
def get_high_impact_news():
    """Haalt nieuws op en bepaalt sentiment + impact"""
    if not FINNHUB_API_KEY:
        return {"events": [], "overall_sentiment": "neutral", "impact": "medium"}
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        r = requests.get(
            f"https://finnhub.io/api/v1/calendar/economic?from={today}&to={today}",
            headers={"X-Finnhub-Token": FINNHUB_API_KEY},
            timeout=15
        )
        if r.status_code == 200:
            events = r.json().get("economicCalendar", [])
            high_impact = [e for e in events if e.get("impact") in ["high", "3"] or e.get("event","").lower() in ["fomc","nfp","cpi","ppi"]]
            
            # Simple sentiment estimate; can be upgraded with LLM scoring later.
            sentiment = "neutral"
            if any("rate" in e.get("event","").lower() or "fomc" in e.get("event","").lower() for e in high_impact):
                sentiment = "bullish" if len([e for e in high_impact if "cut" in str(e).lower()]) > 0 else "bearish"
            
            return {
                "events": high_impact[:4],
                "overall_sentiment": sentiment,
                "impact": "high" if high_impact else "medium"
            }
    except requests.RequestException as e:
        logger.error(f"Finnhub request error: {e}")
    except (ValueError, TypeError) as e:
        logger.error(f"Finnhub parse error: {e}")
    return {"events": [], "overall_sentiment": "neutral", "impact": "medium"}

def pre_dream_daemon():
    return runtime_workers.pre_dream_daemon(RUNTIME_CONTEXT)

# =============================================================================
# v26 TRADE REFLECTION ENGINE
# =============================================================================
def reflect_on_trade(pnl_dollars: float, entry_price: float, exit_price: float, position_qty: int):
    return trade_workers.reflect_on_trade(RUNTIME_CONTEXT, pnl_dollars, entry_price, exit_price, position_qty)

# =============================================================================
# v27 VOICE OUTPUT HELPER
# =============================================================================
def speak(text: str):
    """Natuurlijke spraakoutput met conversational flow"""
    if not VOICE_ENABLED or not tts_engine:
        return
    try:
        # Normalize pauses so TTS sounds less robotic.
        clean_text = text.replace("...", ". ").replace(" – ", ", ")
        print(f"🔊 SPEAKING: {clean_text[:140]}...")
        tts_engine.say(clean_text)
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
        return False  # Paper mode does not send broker orders.

    try:
        dream_snapshot = get_current_dream_snapshot()
        payload = {
            "instrument": INSTRUMENT,
            "action": action.upper(),
            "orderType": "MARKET",
            "quantity": qty,
            "stopLoss": dream_snapshot.get("stop", 0),
            "takeProfit": dream_snapshot.get("target", 0)
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
    return runtime_workers.voice_listener_thread(RUNTIME_CONTEXT)

# =============================================================================
# v32 DASHBOARD + AUTO JOURNAL
# =============================================================================
def generate_daily_journal():
    """Generate a simple HTML journal for the current trading day."""
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
        for trade in trade_log[-50:]:  # Last 50 trades
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
    """v45 - Dashboard met kosten-meter + resultaat-meter + procentuele vergelijking"""
    global dash_app
    if not DASHBOARD_ENABLED:
        return

    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])

    app.layout = dbc.Container([
        html.H1(
            "LUMINA v45 - Live Human Trading Partner",
            style={"textAlign": "center", "color": "#00ff88", "marginBottom": "20px"},
        ),
        html.Div([
            html.Div(id="shutdown-feedback", style={"color": "#ff8080", "fontWeight": "600"}),
            dbc.Button("Sluit Alles", id="shutdown-btn", color="danger", n_clicks=0, className="shadow"),
        ], style={
            "display": "flex",
            "justifyContent": "flex-end",
            "alignItems": "center",
            "gap": "12px",
            "position": "fixed",
            "top": "12px",
            "right": "4px",
            "zIndex": 99999,
            "background": "rgba(0, 0, 0, 0.72)",
            "padding": "8px 10px",
            "borderRadius": "10px",
        }),

        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5("API Kosten Vandaag", className="text-muted text-center"),
                        html.H2(id="cost-meter", className="text-center", style={"fontSize": "42px", "fontWeight": "bold"}),
                    ])
                ], color="dark", outline=True)
            ], width=3),

            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5("Netto Resultaat Vandaag", className="text-muted text-center"),
                        html.H2(id="pnl-meter", className="text-center", style={"fontSize": "42px", "fontWeight": "bold"}),
                    ])
                ], color="dark", outline=True)
            ], width=3),

            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5("Kosten als % van Resultaat", className="text-muted text-center"),
                        html.H2(id="percentage-meter", className="text-center", style={"fontSize": "42px", "fontWeight": "bold"}),
                    ])
                ], color="dark", outline=True)
            ], width=3),

            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5("Cache Hits Vandaag", className="text-muted text-center"),
                        html.H2(id="cache-meter", className="text-center", style={"fontSize": "42px", "fontWeight": "bold"}),
                    ])
                ], color="dark", outline=True)
            ], width=3),
        ], className="mb-4"),

        dbc.Row([
            dbc.Col([dcc.Graph(id="live-chart")], width=8),
            dbc.Col([
                html.H5("Account Status & Equity Curve"),
                html.Div(id="status-panel", style={"fontSize": "18px", "color": "#0ff"}),
                dcc.Graph(id="equity-curve"),
            ], width=4),
        ]),

        html.H5("Strategy Heatmap - Winrate per Regime"),
        dcc.Graph(id="heatmap"),

        html.H5("Laatste Trades & Reflections"),
        dbc.Table(id="trade-table", bordered=True, color="dark"),

        dbc.Modal([
            dbc.ModalHeader("Afsluiten bevestigen"),
            dbc.ModalBody("Weet je zeker dat je LUMINA volledig wilt afsluiten?"),
            dbc.ModalFooter([
                dbc.Button("Annuleren", id="shutdown-cancel-btn", className="ms-auto", n_clicks=0),
                dbc.Button("Afsluiten", id="shutdown-confirm-btn", color="danger", n_clicks=0),
            ]),
        ], id="shutdown-modal", centered=True, is_open=False),

        dcc.Interval(id="interval", interval=8000, n_intervals=0),
    ], fluid=True)

    @app.callback(
        [Output("live-chart", "figure"),
         Output("equity-curve", "figure"),
         Output("status-panel", "children"),
         Output("trade-table", "children"),
         Output("heatmap", "figure"),
         Output("cost-meter", "children"),
         Output("pnl-meter", "children"),
         Output("percentage-meter", "children"),
         Output("cache-meter", "children"),
         Output("cost-meter", "style"),
         Output("pnl-meter", "style"),
         Output("percentage-meter", "style"),
         Output("cache-meter", "style")],
        Input("interval", "n_intervals")
    )
    def update_dashboard(_):
        global DASHBOARD_LAST_CHART_TS, DASHBOARD_LAST_HAS_IMAGE

        now_ts = time.time()
        if now_ts - DASHBOARD_LAST_CHART_TS >= DASHBOARD_CHART_REFRESH_SEC:
            chart_base64 = generate_multi_tf_chart(AI_DRAWN_FIBS) if 'AI_DRAWN_FIBS' in globals() else None
            DASHBOARD_LAST_HAS_IMAGE = bool(chart_base64)
            DASHBOARD_LAST_CHART_TS = now_ts

        fig_chart = go.Figure()
        if DASHBOARD_LAST_HAS_IMAGE:
            fig_chart.add_annotation(text="Live AI Chart (zie screen-share venster)", showarrow=False)

        fig_equity = go.Figure(data=go.Scatter(y=equity_curve, mode="lines", name="Equity"))
        fig_equity.update_layout(title="Equity Curve", template="plotly_dark")

        dream_snapshot = get_current_dream_snapshot()
        status = html.Div([
            html.P(f"Mode: {TRADE_MODE.upper()} | Equity: ${account_equity:,.0f}"),
            html.P(f"Open PnL: ${open_pnl:,.0f} | Realized PnL: ${realized_pnl_today:,.0f}"),
            html.P(f"Current Dream: {dream_snapshot.get('chosen_strategy')} -> {dream_snapshot.get('signal')} (conf {dream_snapshot.get('confluence_score',0):.2f})"),
        ])

        table_header = [html.Thead(html.Tr([html.Th("Tijd"), html.Th("Signal"), html.Th("PnL"), html.Th("Conf")]))]
        rows = []
        for t in trade_log[-10:]:
            rows.append(html.Tr([html.Td(t.get("ts","")), html.Td(t.get("signal","")), html.Td(f"${t.get('pnl',0):,.0f}"), html.Td(f"{t.get('confluence',0):.2f}")]))
        table_body = [html.Tbody(rows)]

        heatmap_fig = generate_strategy_heatmap()

        cost_today = COST_TRACKER.get("today", 0.0)
        pnl_today = realized_pnl_today + open_pnl

        if pnl_today > 0:
            percentage = (cost_today / abs(pnl_today)) * 100
            perc_text = f"{percentage:.1f}%"
            perc_color = "#00ff88" if percentage < 8 else "#ff4444"
        else:
            perc_text = "N/A"
            perc_color = "#aaaaaa"

        cost_color = "#ffaa00" if cost_today < 50 else "#ff4444"
        cost_text = f"${cost_today:.2f}"
        pnl_color = "#00ff88" if pnl_today >= 0 else "#ff4444"
        pnl_text = f"${pnl_today:,.0f}"
        cache_hits = int(COST_TRACKER.get("cached_analyses", 0))
        cache_color = "#00d4ff" if cache_hits > 0 else "#888888"

        return (
            fig_chart,
            fig_equity,
            status,
            table_header + table_body,
            heatmap_fig or go.Figure(),
            cost_text,
            pnl_text,
            perc_text,
            f"{cache_hits}",
            {"color": cost_color, "fontSize": "42px", "fontWeight": "bold"},
            {"color": pnl_color, "fontSize": "42px", "fontWeight": "bold"},
            {"color": perc_color, "fontSize": "42px", "fontWeight": "bold"},
            {"color": cache_color, "fontSize": "42px", "fontWeight": "bold"},
        )

    @app.callback(
        Output("shutdown-modal", "is_open"),
        Input("shutdown-btn", "n_clicks"),
        Input("shutdown-cancel-btn", "n_clicks"),
        Input("shutdown-confirm-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_shutdown_modal(open_clicks, cancel_clicks, confirm_clicks):
        # If cancel or close button clicked, close modal
        if cancel_clicks > 0 or (open_clicks == 0 and confirm_clicks == 0):
            return False
        # If open button clicked, open modal
        if open_clicks > 0:
            return True
        return False

    @app.callback(
        Output("shutdown-feedback", "children"),
        Input("shutdown-confirm-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def execute_shutdown(confirm_clicks):
        if confirm_clicks > 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🛑 Shutdown button confirmed from dashboard")
            # Directly start the shutdown without delay
            threading.Thread(target=emergency_stop, daemon=False).start()
            return "App wordt afgesloten..."
        return ""

    dash_app = app
    print(f"🌐 Dashboard gestart -> http://127.0.0.1:8050  (met kosten, resultaat en procentuele vergelijking)")
    webbrowser.open("http://127.0.0.1:8050")
    try:
        app.run(debug=False, port=8050, use_reloader=False)
    except Exception:
        app.run_server(debug=False, port=8050, use_reloader=False)

# Auto-journal daemon
def auto_journal_daemon():
    """Generate a professional PDF journal once per day."""
    while True:
        time.sleep(86400)  # Every 24 hours (set to 3600 for testing)
        if len(ohlc_1min) > 500:
            generate_professional_pdf_journal()

# =============================================================================
# v44 GLOBAL ERROR HANDLER + WATCHDOG + AUTO-RESTART
# =============================================================================
def global_exception_handler(exctype, value, traceback):
    global restart_count
    logger.error(f"UNHANDLED EXCEPTION: {exctype.__name__}: {value}", exc_info=True)
    print(f"🚨 Kritieke fout gedetecteerd – herstart over 5 seconden...")
    
    if restart_count < MAX_RESTARTS:
        restart_count += 1
        time.sleep(5)
        os.execv(sys.executable, ['python'] + sys.argv)  # Full process restart
    else:
        print("❌ Te veel herstarts – bot stopt definitief.")
        save_state()
        sys.exit(1)

# Install global exception hooks
import sys
sys.excepthook = global_exception_handler

def thread_exception_handler(args):
    """Route thread exceptions naar de globale watchdog handler."""
    global_exception_handler(args.exc_type, args.exc_value, args.exc_traceback)

threading.excepthook = thread_exception_handler

def emergency_stop():
    """Emergency stop via voice of keyboard"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🛑 EMERGENCY STOP – bot wordt afgesloten")

    # Best-effort: close the screen-share window explicitly before hard exit.
    try:
        global live_chart_window
        if live_chart_window is not None:
            try:
                live_chart_window.after(0, live_chart_window.destroy)
            except Exception:
                live_chart_window.destroy()
    except Exception as e:
        logger.warning(f"Emergency stop window close warning: {e}")

    save_state()
    os._exit(0)   # Hard process stop


def rate_limit_backoff():
    """Intelligente backoff bij rate-limits"""
    global RATE_LIMIT_BACKOFF
    RATE_LIMIT_BACKOFF = min(RATE_LIMIT_BACKOFF + 5, 60)  # Cap at 60 seconds
    print(f"⏳ Rate-limit backoff: {RATE_LIMIT_BACKOFF} seconden")
    time.sleep(RATE_LIMIT_BACKOFF)

def auto_backtest_daemon():
    """Draait elke avond een backtest + reflection"""
    while True:
        time.sleep(3600 * 4)  # Every 4 hours (set to 86400 for daily)
        if not is_market_open() and len(ohlc_1min) > 1000:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📈 Automated backtest gestart...")
            results = run_auto_backtest(BACKTEST_DAYS)
            asyncio.run(backtest_reflection(results))

# =============================================================================
# v38 PERFORMANCE ANALYTICS & HEATMAPS
# =============================================================================
def update_performance_log(trade_data: dict):
    """Slaat trade-data op voor analytics"""
    performance_log.append({
        "ts": datetime.now().isoformat(),
        "signal": trade_data.get("signal"),
        "chosen_strategy": trade_data.get("chosen_strategy", "unknown"),
        "regime": trade_data.get("regime", "NEUTRAL"),
        "confluence": trade_data.get("confluence", 0),
        "pnl": trade_data.get("pnl", 0),
        "drawdown": trade_data.get("drawdown", 0)
    })
    # Keep only the most recent 500 trades.
    if len(performance_log) > 500:
        performance_log.pop(0)

def generate_strategy_heatmap():
    """Maakt een heatmap van winrate per strategie x regime"""
    if len(performance_log) < 20:
        return None
    
    df_perf = pd.DataFrame(performance_log)
    pivot = df_perf.groupby(["chosen_strategy", "regime"])["pnl"].agg(["mean", "count", lambda x: (x > 0).mean()]).reset_index()
    pivot.columns = ["strategy", "regime", "avg_pnl", "trades", "winrate"]
    
    # Build heatmap matrix by strategy x regime.
    strategies = pivot["strategy"].unique()
    regimes = pivot["regime"].unique()
    z = np.zeros((len(strategies), len(regimes)))
    for i, strat in enumerate(strategies):
        for j, reg in enumerate(regimes):
            row = pivot[(pivot["strategy"] == strat) & (pivot["regime"] == reg)]
            z[i, j] = row["winrate"].iloc[0] if not row.empty else 0.5
    
    fig = ff.create_annotated_heatmap(
        z, x=list(regimes), y=list(strategies),
        annotation_text=np.round(z, 2),
        colorscale="RdYlGn",
        showscale=True
    )
    fig.update_layout(title="Strategy Heatmap – Winrate per Regime", template="plotly_dark")
    return fig

def generate_performance_summary():
    """Geeft samenvatting voor dashboard"""
    if not performance_log:
        return {"sharpe": 0, "winrate": 0, "trades": 0}
    
    pnls = [t["pnl"] for t in performance_log if t["pnl"] != 0]
    if not pnls:
        return {"sharpe": 0, "winrate": 0, "trades": 0}
    
    sharpe = (np.mean(pnls) / (np.std(pnls) + 1e-8)) * np.sqrt(252)
    winrate = np.mean(np.array(pnls) > 0)
    return {
        "sharpe": round(sharpe, 2),
        "winrate": round(winrate, 3),
        "trades": len(pnls),
        "avg_pnl": round(np.mean(pnls), 1)
    }

# =============================================================================
# v39 PROFESSIONAL PDF JOURNAL
# =============================================================================
class LuminaPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "LUMINA v39 – Professional Trading Journal", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

def generate_professional_pdf_journal():
    """Genereert een volledige professionele PDF-journal van de dag + wekelijkse review"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        filename = JOURNAL_PDF_DIR / f"LUMINA_Journal_{today}.pdf"
        
        pdf = LuminaPDF()
        pdf.add_page()
        
        # Header and account summary
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"Daily Journal – {today} | Mode: {TRADE_MODE.upper()}", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 8, f"Equity: ${account_equity:,.0f} | Open PnL: ${open_pnl:,.0f} | Realized PnL: ${realized_pnl_today:,.0f}", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(10)
        
        # Equity curve image
        if len(equity_curve) > 10:
            fig = go.Figure(data=go.Scatter(y=equity_curve, mode="lines", name="Equity"))
            fig.update_layout(title="Equity Curve", template="plotly_dark", height=400)
            fig.write_image("temp_equity.png")
            pdf.image("temp_equity.png", x=10, y=pdf.get_y(), w=190)
            pdf.ln(85)
            Path("temp_equity.png").unlink(missing_ok=True)
        
        # Performance summary and heatmap
        summary = generate_performance_summary()
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Performance Summary", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Arial", "", 11)
        pdf.cell(0, 6, f"Sharpe: {summary['sharpe']} | Winrate: {summary['winrate']:.1%} | Trades: {summary['trades']} | Avg PnL: ${summary['avg_pnl']}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(10)
        
        # Heatmap image
        heatmap_fig = generate_strategy_heatmap()
        if heatmap_fig:
            heatmap_fig.write_image("temp_heatmap.png")
            pdf.image("temp_heatmap.png", x=10, y=pdf.get_y(), w=190)
            pdf.ln(90)
            Path("temp_heatmap.png").unlink(missing_ok=True)
        
        # Recent trades
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Laatste Trades", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Arial", "", 10)
        for t in trade_log[-15:]:
            pdf.cell(0, 6, f"{t.get('ts','')} | {t.get('signal','')} | PnL ${t.get('pnl',0):,.0f} | Conf {t.get('confluence',0):.2f}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(10)
        
        # Reflections and lessons learned
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "Reflections & Lessons Learned", new_x="LMARGIN", new_y="NEXT")
        for ref in list(trade_reflection_history)[-8:]:
            pdf.multi_cell(0, 6, f"{ref['ts']} | PnL ${ref['pnl']:,.0f} → {ref.get('key_lesson','')}")
        
        # Structured weekly review (AI-generated)
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "WEEKLY REVIEW – Generated by LUMINA", new_x="LMARGIN", new_y="NEXT", align="C")
        
        # Extract recent lessons for weekly review prompt
        recent_lessons = [r['key_lesson'] for r in list(trade_reflection_history)[-10:]]
        
        weekly_payload = {
            "model": "grok-4.20-0309-reasoning",
            "messages": [
                {"role": "system", "content": "Schrijf een professionele, eerlijke weekly review. Geen emoties, alleen feiten en concrete verbeterpunten."},
                {"role": "user", "content": f"Week van {today}. Performance: Sharpe {summary['sharpe']}, Winrate {summary['winrate']:.1%}, Max DD {summary.get('maxdd','N/A')}. Laatste reflections: {json.dumps(recent_lessons)}"}
            ]
        }
        r = post_xai_chat(weekly_payload, timeout=20, context="weekly_review")
        if r and r.status_code == 200:
            review_text = r.json()["choices"][0]["message"]["content"]
            pdf.multi_cell(0, 6, review_text)
        
        pdf.output(str(filename))
        print(f"📄 PROFESSIONAL PDF JOURNAL gegenereerd → {filename}")
        return str(filename)
    except Exception as e:
        logger.error(f"PDF journal error: {e}")
        return None

# =============================================================================
# v40 ADAPTIVE RISK & POSITION SIZING ENGINE
# =============================================================================
def calculate_adaptive_risk_and_qty(price: float, regime: str, stop_price: float) -> int:
    """Berekent dynamische risk in dollars + qty op basis van equity + regime.
    
    FUTURE-PROOF NOTE (voor v41+):
    - Multipliers zijn in een dict zodat we later makkelijk nieuwe regimes kunnen toevoegen.
    - Kan later uitgebreid worden met VIX, news-impact of vector-memory lookup.
    """
    global account_equity
    
    base_risk_percent = MAX_RISK_PERCENT
    multiplier = REGIME_RISK_MULTIPLIERS.get(regime, 1.0)
    adaptive_risk_percent = base_risk_percent * multiplier
    
    risk_dollars = account_equity * (adaptive_risk_percent / 100)
    
    stop_distance = abs(price - stop_price)
    if stop_distance <= 0:
        stop_distance = price * 0.005  # minimale afstand als stop niet ingesteld
    
    # MES multiplier = $5 per punt
    qty = max(1, int(risk_dollars / (stop_distance * 5)))
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📏 Adaptive Risk → Regime: {regime} | Multiplier: {multiplier:.1f} | Risk ${risk_dollars:.0f} | Qty: {qty}")
    logger.info(f"ADAPTIVE_RISK,regime={regime},risk_percent={adaptive_risk_percent:.2f},qty={qty}")
    
    return qty

# =============================================================================
# v42 USER FEEDBACK PROCESSING
# =============================================================================
def process_user_feedback(feedback_text: str, trade_data: dict | None = None):
    return trade_workers.process_user_feedback(RUNTIME_CONTEXT, feedback_text, trade_data)

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
            r = post_xai_chat(payload, timeout=12, context=f"multi_agent_{agent_name}")
            if r and r.status_code == 200:
                body = r.json()
                update_cost_tracker_from_usage(body.get("usage"), "reasoning")
                resp = body["choices"][0]["message"]["content"]
                vote = json.loads(resp)
                agent_votes[agent_name] = vote
                consistency_scores.append(vote.get("confidence", 0.5))
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Multi-agent parse error ({agent_name}): {e}")
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
        r = post_xai_chat(payload, timeout=15, context="meta_reasoning")
        if r and r.status_code == 200:
            body = r.json()
            update_cost_tracker_from_usage(body.get("usage"), "reasoning")
            resp = body["choices"][0]["message"]["content"]
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
    
    # Persist the current world model in vector DB for long-term recall.
    store_experience_to_vector_db(
        context=f"World Model Update: Regime {regime} | VIX {world_model['macro']['vix']:.1f} | DXY {world_model['macro']['dxy']:.1f}",
        metadata={"type": "world_model", "date": datetime.now().isoformat()}
    )
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌍 World Model geüpdatet → Regime: {regime} | VIX: {world_model['macro']['vix']:.1f}")
    return world_model

# =============================================================================
# v45 EVENT-DRIVEN 5-MIN CANDLE TRIGGER
# =============================================================================
def is_significant_event(current_price: float, previous_price: float, regime: str) -> bool:
    """Bepaalt of een diepe analyse nodig is"""
    price_change = abs(current_price - previous_price) / previous_price
    if price_change > EVENT_THRESHOLD:
        return True
    if regime in ["TRENDING", "BREAKOUT", "VOLATILE"]:
        return True
    return False

def update_cost_tracker_from_usage(usage: dict | None, channel: str = "reasoning"):
    """Werk token- en kosteninschatting bij op basis van usage uit API-responses."""
    if not usage:
        return

    tokens = usage.get("total_tokens")
    if tokens is None:
        tokens = (usage.get("prompt_tokens") or usage.get("input_tokens") or 0) + (usage.get("completion_tokens") or usage.get("output_tokens") or 0)

    try:
        token_count = int(tokens)
    except (TypeError, ValueError):
        return

    if channel == "vision":
        COST_TRACKER["vision_tokens"] += token_count
        COST_TRACKER["today"] += (token_count / 1000.0) * 0.015
    else:
        COST_TRACKER["reasoning_tokens"] += token_count
        COST_TRACKER["today"] += (token_count / 1000.0) * 0.007

def run_async_safely(coro):
    """Run coroutine veilig vanuit sync code, ook als er al een event loop draait."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def parse_json_loose(raw_text: str) -> dict:
    """Probeer JSON te extraheren, inclusief fenced code blocks."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return json.loads(text)

def build_pa_signature(pa_summary: str) -> str:
    """Normaliseer PA-summary voor cache-validatie."""
    return " ".join(str(pa_summary).lower().split())[:220]

def get_cached_analysis(current_price: float, regime: str, pa_summary: str):
    """Geef cache terug als die nog valide is voor huidige context."""
    with DEEP_ANALYSIS_CACHE_LOCK:
        ts = LAST_DEEP_ANALYSIS.get("timestamp")
        cached_price = float(LAST_DEEP_ANALYSIS.get("price", 0.0) or 0.0)
        cached_regime = LAST_DEEP_ANALYSIS.get("regime")
        cached_sig = LAST_DEEP_ANALYSIS.get("pa_signature")
        cached_dream = LAST_DEEP_ANALYSIS.get("dream_snapshot")
        cached_consensus = LAST_DEEP_ANALYSIS.get("consensus")

    if not ts or not cached_dream or not cached_consensus or cached_price <= 0:
        return None

    age_sec = (datetime.now() - ts).total_seconds()
    if age_sec > CACHE_TTL_SECONDS:
        return None

    price_change = abs(current_price - cached_price) / cached_price
    if price_change >= EVENT_THRESHOLD:
        return None

    if cached_regime != regime:
        return None

    if cached_sig != build_pa_signature(pa_summary):
        return None

    return {
        "dream_snapshot": dict(cached_dream),
        "consensus": dict(cached_consensus),
    }

def human_like_main_loop():
    """Nieuwe hoofdcyclus: 5-min candle driven"""
    global LAST_CANDLE_TIME

    while True:
        try:
            with live_data_lock:
                if len(ohlc_1min) < 10:
                    time.sleep(5)
                    continue

                last_ts = pd.to_datetime(ohlc_1min["timestamp"].iloc[-1], errors="coerce")
                if pd.isna(last_ts):
                    time.sleep(5)
                    continue
                current_candle_time = last_ts.floor("5min")
                current_price = ohlc_1min["close"].iloc[-1]
                previous_price = ohlc_1min["close"].iloc[-2]
                regime = detect_market_regime(ohlc_1min)

            # Nieuwe 5-min candle?
            if LAST_CANDLE_TIME is None or current_candle_time != LAST_CANDLE_TIME:
                LAST_CANDLE_TIME = current_candle_time
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🕯️ Nieuwe 5-min candle → lichte scan")

                # Lichte scan (goedkoop)
                mtf_data = get_mtf_snapshots()
                pa_summary = generate_price_action_summary()

                cached = get_cached_analysis(current_price, regime, pa_summary)
                if cached is not None:
                    set_current_dream_fields(cached["dream_snapshot"])
                    COST_TRACKER["cached_analyses"] = int(COST_TRACKER.get("cached_analyses", 0)) + 1
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 Cache hit → vorige analyse hergebruikt (0 calls)")
                    time.sleep(5)
                    continue

                # Alleen diepe analyse bij significant event
                if is_significant_event(current_price, previous_price, regime):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 Significant event → diepe analyse (vision + agents)")
                    # Hier roepen we de volledige v33-v36 stack aan (multi-agent, meta, world-model, vision)
                    # (de code voor de diepe analyse komt hieronder)
                    deep_analysis(current_price, regime, mtf_data, pa_summary)
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🟢 Lichte scan – geen actie nodig")

            # Kostentracker updaten (elke minuut)
            if int(datetime.now().second) == 0:
                print(
                    f"💰 Kosten vandaag: ${COST_TRACKER['today']:.2f} | Cached: {COST_TRACKER.get('cached_analyses', 0)} | "
                    f"Reasoning: {COST_TRACKER['reasoning_tokens']} tokens | Vision: {COST_TRACKER['vision_tokens']} tokens"
                )

            time.sleep(5)   # lichte polling

        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(10)

def deep_analysis(price: float, regime: str, mtf_data: str, pa_summary: str):
    """Volledige intelligente analyse alleen bij significante events"""
    global COST_TRACKER, AI_DRAWN_FIBS

    with live_data_lock:
        if len(ohlc_1min) < 80:
            logger.warning("DEEP_ANALYSIS_SKIPPED,reason=insufficient_data")
            return
        df_snapshot = ohlc_1min.copy()

    recent = df_snapshot.iloc[-60:]
    swing_low = float(recent["low"].min())
    swing_high = float(recent["high"].max())
    diff = swing_high - swing_low
    fib_levels = {}
    for r in [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]:
        fib_levels[str(r)] = round(swing_high - diff * r, 2)

    cost_before = float(COST_TRACKER.get("today", 0.0))

    # v33 Multi-Agent + v35 Meta + v36 World Model + v34 Vector Memory
    consensus = run_async_safely(
        multi_agent_consensus(
            price,
            mtf_data,
            pa_summary,
            detect_market_structure(df_snapshot),
            fib_levels,
        )
    )
    past_experiences = retrieve_relevant_experiences(f"Prijs {price:.2f} | Regime {regime}")
    meta = run_async_safely(meta_reasoning_and_counterfactuals(consensus, price, pa_summary, past_experiences))
    world_model = update_world_model(df_snapshot, regime, pa_summary)

    signal = consensus.get("signal", "HOLD")
    confidence = float(consensus.get("confidence", 0.0))
    stop = 0.0
    target = 0.0
    if signal == "BUY":
        stop = float(fib_levels.get("0.786", price * 0.997))
        if stop >= price:
            stop = price * 0.997
        target = price + (price - stop) * 2
    elif signal == "SELL":
        stop = float(fib_levels.get("0.236", price * 1.003))
        if stop <= price:
            stop = price * 1.003
        target = price - (stop - price) * 2

    reason_text = f"{consensus.get('reason', '')} | Meta: {meta.get('meta_reasoning', '')[:80]}"
    set_current_dream_fields(
        {
            "reason": reason_text,
            "signal": signal,
            "confidence": confidence,
            "confluence_score": confidence,
            "chosen_strategy": "v45_event_driven",
            "stop": round(stop, 2) if stop else 0.0,
            "target": round(target, 2) if target else 0.0,
            "fib_levels": fib_levels,
            "swing_high": round(swing_high, 2),
            "swing_low": round(swing_low, 2),
        }
    )

    # Vision call (duurste deel)
    chart_base64 = generate_multi_tf_chart()
    if chart_base64:
        vision_obj = {}
        vision_payload = {
            "model": VISION_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "Je bent een professionele chart-analist. Geef ALLEEN JSON met keys: summary (string), ai_fibs (dict met fib-ratio->prijs).",
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Analyseer deze chart voor {INSTRUMENT}. Prijs={price:.2f}, Regime={regime}. Geef compact trading-advies.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{chart_base64}"},
                        },
                    ],
                },
            ],
            "max_tokens": 220,
            "temperature": 0.2,
        }
        try:
            rv = post_xai_chat(vision_payload, timeout=20, context="v45_vision")
            if rv and rv.status_code == 200:
                body = rv.json()
                update_cost_tracker_from_usage(body.get("usage"), "vision")
                vision_raw = body["choices"][0]["message"]["content"]
                vision_obj = parse_json_loose(vision_raw)
                ai_fibs = vision_obj.get("ai_fibs", {})
                if isinstance(ai_fibs, dict) and ai_fibs:
                    AI_DRAWN_FIBS = ai_fibs

                set_current_dream_fields(
                    {
                        "reason": f"{reason_text} | Vision: {str(vision_obj.get('summary', ''))[:80]}",
                    }
                )
        except Exception as e:
            logger.error(f"Vision deep_analysis error: {e}")

    logger.info(
        f"DEEP_ANALYSIS_V45,signal={consensus.get('signal','HOLD')},conf={float(consensus.get('confidence', 0.0)):.2f},regime={regime},vix={world_model['macro']['vix']:.1f}"
    )

    # Fallback only: voeg schatting toe als usage-based accounting niets heeft bijgewerkt.
    if float(COST_TRACKER.get("today", 0.0)) <= cost_before:
        COST_TRACKER["today"] += 0.08

    with DEEP_ANALYSIS_CACHE_LOCK:
        LAST_DEEP_ANALYSIS.update(
            {
                "timestamp": datetime.now(),
                "price": float(price),
                "regime": regime,
                "pa_signature": build_pa_signature(pa_summary),
                "consensus": dict(consensus),
                "meta": dict(meta),
                "dream_snapshot": get_current_dream_snapshot(),
            }
        )

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
            dream_snapshot = get_current_dream_snapshot()
            signal = dream_snapshot.get("signal", "HOLD")
            if bt_position == 0 and signal in ["BUY", "SELL"] and dream_snapshot.get("confluence_score", 0) > MIN_CONFLUENCE:
                bt_position = 1 if signal == "BUY" else -1
                bt_entry = price
            if bt_position != 0:
                stop = dream_snapshot.get("stop", 0)
                target = dream_snapshot.get("target", 0)
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
        r = post_xai_chat(payload, timeout=25, context="backtest_reflection")
        if r and r.status_code == 200:
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
# v28 + v44 – SUPER LEESBARE SCREEN-SHARE (clean 2x2 layout)
# =============================================================================
def start_screen_share_window():
    global live_chart_window
    if not SCREEN_SHARE_ENABLED:
        return

    def create_window():
        global live_chart_window
        root = tk.Tk()
        root.title("LUMINA Live Trader Screen Share – Clean Professional View")
        root.attributes("-topmost", True)
        root.geometry("1480x920")          # groter en rustiger
        root.configure(bg="#0a0a0a")

        # Titel met live info
        title = tk.Label(root, text="LUMINA Live Trader Screen Share",
                         font=("Consolas", 18, "bold"), fg="#00ff88", bg="#0a0a0a")
        title.pack(pady=8)

        chart_label = tk.Label(root, bg="#0a0a0a")
        chart_label.pack(padx=20, pady=10, fill="both", expand=True)
        root_any: Any = root
        root_any.chart_label = chart_label

        # Live status bar (groter en duidelijker)
        status_frame = tk.Frame(root, bg="#0a0a0a")
        status_frame.pack(fill="x", padx=20, pady=10)

        status_dot = tk.Label(status_frame, text="●", font=("Consolas", 22), fg="#00ff88", bg="#0a0a0a")
        status_dot.pack(side="left")
        root_any.status_dot = status_dot

        status_text = tk.Label(status_frame, text="AI Decision & Chart updated",
                               font=("Consolas", 14), fg="#00ff88", bg="#0a0a0a")
        status_text.pack(side="left", padx=12)
        root_any.status_text = status_text

        last_update = tk.Label(status_frame, text="Laatste update: —",
                               font=("Consolas", 11), fg="#888888", bg="#0a0a0a")
        last_update.pack(side="right")
        root_any.last_update = last_update

        live_chart_window = root
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🖥️ Schone & goed leesbare screen-share geopend")
        root.mainloop()

    threading.Thread(target=create_window, daemon=True).start()


def update_live_chart(chart_base64: str, status_msg: str = "AI Decision & Chart updated"):
    global latest_chart_image
    if not SCREEN_SHARE_ENABLED or not live_chart_window:
        return
    try:
        img_data = base64.b64decode(chart_base64)
        pil_img = Image.open(BytesIO(img_data)).resize((1400, 800), Image.Resampling.LANCZOS)

        with chart_update_lock:
            win: Any = live_chart_window
            latest_chart_image = ImageTk.PhotoImage(pil_img)
            win.chart_label.config(image=latest_chart_image)
            win.chart_label.image = latest_chart_image

            # Live status update
            win.status_dot.config(fg="#00ff88")
            win.status_text.config(text=status_msg, fg="#00ff88")
            win.last_update.config(text=f"Laatste update: {datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        logger.error(f"Screen-share update error: {e}")
        if live_chart_window:
            win: Any = live_chart_window
            win.status_dot.config(fg="#ff4444")
            win.status_text.config(text="ERROR – zie log", fg="#ff4444")

# =============================================================================
# SUPERVISOR + ORACLE
# =============================================================================
def is_market_open():
    now = datetime.now()
    hour = now.hour
    return 13 <= hour <= 21

def supervisor_loop():
    return runtime_workers.supervisor_loop(RUNTIME_CONTEXT)

# =============================================================================
# DNA REWRITE + AUTO BACKTESTER
# =============================================================================
def dna_rewrite_daemon():
    return trade_workers.dna_rewrite_daemon(RUNTIME_CONTEXT)

def run_backtest_on_snapshot(snapshot):
    return backtest_workers.run_backtest_on_snapshot(RUNTIME_CONTEXT, snapshot)

def auto_backtester_daemon():
    return backtest_workers.auto_backtester_daemon(RUNTIME_CONTEXT)


def bootstrap_runtime() -> None:
    """Validate config, pre-load history, and start all runtime services."""
    if not validate_runtime_config():
        raise SystemExit(1)

    load_historical_ohlc(days_back=3, limit=5000)
    start_runtime_services(
        start_daemon_fn=start_daemon,
        screen_share_enabled=SCREEN_SHARE_ENABLED,
        dashboard_enabled=DASHBOARD_ENABLED,
        voice_input_enabled=VOICE_INPUT_ENABLED,
        start_screen_share_window_fn=start_screen_share_window,
        thought_logger_thread_fn=thought_logger_thread,
        start_websocket_fn=start_websocket,
        auto_backtester_daemon_fn=auto_backtester_daemon,
        start_dashboard_fn=start_dashboard,
        voice_listener_thread_fn=voice_listener_thread,
        supervisor_loop_fn=supervisor_loop,
        dna_rewrite_daemon_fn=dna_rewrite_daemon,
        gap_recovery_daemon_fn=gap_recovery_daemon,
        pre_dream_daemon_fn=pre_dream_daemon if START_PRE_DREAM_BACKUP else None,
        auto_journal_daemon_fn=auto_journal_daemon,
        auto_backtest_daemon_fn=auto_backtest_daemon,
    )

    print("🛡️ v44 Stability & Watchdog active - bot is now 24/7 production-ready")


def run_forever_loop() -> None:
    """Keep runtime alive until explicit shutdown."""
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n🛑 Graceful shutdown gestart...")
        save_state()
        print("✅ Alle data veilig opgeslagen.")
    except SystemExit:
        save_state()

# =============================================================================
# START – FORCE INITIAL LOAD
# =============================================================================
if __name__ == "__main__":
    print(f"🚀 LUMINA v44 – FINAL STABLE VERSION GESTART (Mode: {TRADE_MODE.upper()})")
    bootstrap_runtime()
    if USE_HUMAN_MAIN_LOOP:
        threading.Thread(target=human_like_main_loop, daemon=True).start()
    else:
        print("ℹ️ USE_HUMAN_MAIN_LOOP=False -> human-like loop niet gestart")
    run_forever_loop()