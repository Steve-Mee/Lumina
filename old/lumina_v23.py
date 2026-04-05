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
        "regime_history": list(regime_history)
    }
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Save state error: {e}")

def load_state():
    global sim_position_qty, sim_entry_price, sim_unrealized, sim_peak, pnl_history, equity_curve, current_dream, bible, memory_buffer, narrative_memory, regime_history, dynamic_min_confluence
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
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ State hersteld (v22 narrative + regime)")
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
# v23 CHART VISION GENERATOR + LOGGING
# =============================================================================
def generate_multi_tf_chart() -> str:
    """Genereert chart + fibs + structure en retourneert base64 PNG"""
    start_time = time.perf_counter()

    with live_data_lock:
        if len(ohlc_1min) < 200:
            logger.info("CHART_GEN_SKIPPED,reason=insufficient_data")
            return ""
        df = ohlc_1min.copy()
        df.set_index("timestamp", inplace=True)

    tfs = [("1min", "1T"), ("5min", "5T"), ("15min", "15T"), ("30min", "30T"), ("60min", "60T"), ("240min", "240T")]
    fig = make_subplots(rows=3, cols=2, subplot_titles=[name for name, _ in tfs],
                        vertical_spacing=0.08, horizontal_spacing=0.05)

    row_col = [(1, 1), (1, 2), (2, 1), (2, 2), (3, 1), (3, 2)]
    swing_high, swing_low, fib_levels = detect_swing_and_fibs()

    for i, (tf_name, freq) in enumerate(tfs):
        res = df.resample(freq).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        if len(res) < 20:
            continue

        row, col = row_col[i]

        fig.add_trace(go.Candlestick(x=res.index, open=res["open"], high=res["high"],
                                     low=res["low"], close=res["close"], name=tf_name,
                                     increasing_line_color="#00ff88", decreasing_line_color="#ff4444"),
                      row=row, col=col)
        fig.add_trace(go.Bar(x=res.index, y=res["volume"], name="Volume",
                             marker_color="#8888ff", opacity=0.4), row=row, col=col)

        if tf_name in ["1min", "15min"]:
            for ratio, price in fib_levels.items():
                if ratio in ["0.382", "0.618", "0.786"]:
                    fig.add_hline(y=float(price), line_dash="dash", line_color="#ffff00",
                                  annotation_text=f"Fib {ratio}", row=row, col=col)  # type: ignore[arg-type]

        fig.add_hline(y=swing_high, line_color="#00ffff", line_dash="dot", row=row, col=col)  # type: ignore[arg-type]
        fig.add_hline(y=swing_low, line_color="#ff00ff", line_dash="dot", row=row, col=col)  # type: ignore[arg-type]

    current_price = df["close"].iloc[-1]
    regime = detect_market_regime(df.reset_index())
    fig.update_layout(
        title=f"LUMINA v23 - MES {INSTRUMENT} | Prijs {current_price:.2f} | Regime: {regime} | {datetime.now().strftime('%d %b %H:%M')}",
        height=900, width=1400, showlegend=False, template="plotly_dark",
        margin=dict(l=40, r=40, t=80, b=40)
    )

    img_bytes = BytesIO()
    fig.write_image(img_bytes, format="png", scale=2)
    img_bytes.seek(0)
    base64_img = base64.b64encode(img_bytes.read()).decode("utf-8")

    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(f"CHART_GEN_COMPLETE,duration_ms={duration_ms:.0f},base64_kb={len(base64_img)//1000},price={current_price:.2f}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🖼️ Chart Vision gegenereerd in {duration_ms:.0f} ms ({len(base64_img)//1000} kB)")

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
    global current_dream, dynamic_min_confluence
    while True:
        cycle_start = time.perf_counter()
        call_duration_ms = 0.0
        try:
            with live_data_lock:
                price = live_quotes[-1]["last"] if live_quotes else (ohlc_1min["close"].iloc[-1] if len(ohlc_1min) > 0 else 0.0)
                df = ohlc_1min.copy()

            # Regime + Structure
            regime = detect_market_regime(df)
            regime_history.append({"ts": datetime.now().isoformat(), "regime": regime})
            structure = detect_market_structure(df)

            # Dynamic confluence
            recent_winrate = float(np.mean(np.array(pnl_history[-15:]) > 0)) if len(pnl_history) > 10 else 0.5
            min_conf = calculate_dynamic_confluence(regime, recent_winrate)

            mtf_data = get_mtf_snapshots()
            swing_high, swing_low, fib_levels = detect_swing_and_fibs()
            pa_summary = generate_price_action_summary()

            # Narrative memory
            narrative_text = "\n".join([f"[{item['ts']}] {item['narrative']}" for item in narrative_memory])

            # === v23 CHART VISION ===
            logger.info(f"VISION_CYCLE_START,price={price:.2f},regime={regime}")
            chart_base64 = generate_multi_tf_chart()

            if not chart_base64:
                logger.info("VISION_SKIPPED,reason=no_chart")
                print("⚠️ Geen chart → tekst-only fallback")
                time.sleep(12)
                continue

            # Update memory
            narrative_memory.append({
                "ts": datetime.now().isoformat(),
                "narrative": f"Price {price:.2f} | Regime: {regime} | {pa_summary[:120]}"
            })

            news_info = get_high_impact_news()

            log_thought({"type": "dream_thought", "price": price, "regime": regime, "pa_summary": pa_summary[:200]})

            # Vision payload
            vision_content = [
                {
                    "type": "text",
                    "text": f"""Je bent een ervaren MES daytrader met 15+ jaar ervaring.
Je kijkt NU naar de echte chart image + alle data.
Gebruik market structure, fibs, candle patterns, regime en narrative.
Geef ALLEEN JSON met: signal, confidence, stop, target, reason, why_no_trade, confluence_score, chosen_strategy"""
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{chart_base64}"}
                }
            ]

            call_start = time.perf_counter()
            logger.info(f"VISION_API_CALL_START,model={VISION_MODEL},base64_kb={len(chart_base64)//1000}")

            payload = {
                "model": VISION_MODEL,
                "messages": [
                    {"role": "system", "content": "Je bent visueel getraind. Beschrijf wat je op de chart ziet en neem een trade-besluit."},
                    {"role": "user", "content": vision_content}
                ],
                "max_tokens": 800
            }

            r = requests.post("https://api.x.ai/v1/chat/completions",
                              headers={"Authorization": f"Bearer {XAI_KEY}"},
                              json=payload, timeout=45)

            call_duration_ms = (time.perf_counter() - call_start) * 1000
            logger.info(f"VISION_API_CALL_END,status={r.status_code},duration_ms={call_duration_ms:.0f}")

            if r.status_code == 200:
                response_text = r.json()["choices"][0]["message"]["content"]
                logger.info(f"VISION_RESPONSE_RECEIVED,chars={len(response_text)}")
                # Probeer JSON te extraheren (vision model geeft soms tekst + JSON)
                try:
                    dream_json = json.loads(response_text)
                    logger.info("VISION_JSON_PARSE_SUCCESS")
                except:
                    # Fallback: zoek naar JSON-blok
                    import re
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        dream_json = json.loads(json_match.group(0))
                        logger.info("VISION_JSON_PARSE_SUCCESS,method=regex_fallback")
                    else:
                        dream_json = {"signal": "HOLD", "reason": "Vision parse error"}
                        logger.info("VISION_JSON_PARSE_FAILED")

                current_dream.update(dream_json)
                current_dream["confluence_score"] = min_conf  # dynamic waarde gebruiken

                # Narrative updaten
                narrative_memory.append({
                    "ts": datetime.now().isoformat(),
                    "narrative": f"DREAM: {current_dream.get('chosen_strategy')} → {current_dream['signal']} | Conf {min_conf:.2f} | Regime {regime}"
                })

                log_thought({"type": "dream_decision", **dream_json})
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 👁️ v23 VISION DREAM: {current_dream.get('chosen_strategy')} → {current_dream['signal']} (conf={min_conf:.2f})")
            else:
                logger.error(f"VISION_API_ERROR,status={r.status_code},text={r.text[:300]}")
                print(f"❌ Vision API error {r.status_code}")
        except Exception as e:
            logger.error(f"VISION_CYCLE_CRASH,error={str(e)}", exc_info=True)
            print(f"⚠️ Vision cycle crash: {e}")

        total_cycle_ms = (time.perf_counter() - cycle_start) * 1000
        logger.info(f"VISION_CYCLE_COMPLETE,total_ms={total_cycle_ms:.0f},vision_ms={call_duration_ms:.0f}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏱️ Volledige vision-cyclus: {total_cycle_ms:.0f} ms")

        time.sleep(12)

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
            if not live_quotes and len(ohlc_1min) == 0:
                time.sleep(1)
                continue
            price = live_quotes[-1]["last"] if live_quotes else (ohlc_1min["close"].iloc[-1] if len(ohlc_1min) > 0 else 0.0)
        now = datetime.now()

        real_equity = 50000 + sim_unrealized
        if real_equity < sim_peak * 0.85:
            print(f"[{now.strftime('%H:%M:%S')}] 🚨 -15% DRAWDOWN KILL SWITCH")
            save_state()
            raise SystemExit("Drawdown kill")

        signal = current_dream.get("signal", "HOLD")
        if not is_market_open() and sim_position_qty != 0:
            signal = "HOLD"

        if SIMULATE_TRADES and is_market_open() and signal in ["BUY", "SELL"] and sim_position_qty == 0 and current_dream.get("confluence_score", 0) > MIN_CONFLUENCE:
            qty = 1
            sim_position_qty = qty if signal == "BUY" else -qty
            sim_entry_price = price
            print(f"[{now.strftime('%H:%M:%S')}] 📍 SIM {signal} OPEN @ {price:.2f} | Strategy: {current_dream.get('chosen_strategy')} | Risk Profile: {RISK_PROFILE.upper()}")

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
    print("🚀 LUMINA v21.6 – ECHTE CANDLE AGGREGATIE GESTART")
    
    print("🔥 Force initial historical load...")
    load_historical_ohlc(days_back=3, limit=5000)
    
    threading.Thread(target=supervisor_loop, daemon=True).start()
    threading.Thread(target=dna_rewrite_daemon, daemon=True).start()
    threading.Thread(target=gap_recovery_daemon, daemon=True).start()
    threading.Thread(target=pre_dream_daemon, daemon=True).start()
    
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        save_state()
        print("\n🛑 LUMINA v21.6 gestopt – state opgeslagen.")
    except SystemExit as e:
        save_state()
        print(e)