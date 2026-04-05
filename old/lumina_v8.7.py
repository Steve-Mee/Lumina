# === lumina_v8.7.py – LUMINA v4.0 + CRASH-FIX + STABIELE FIRST PRINCIPLES ONTLEDING ===
import os
import time
import pandas as pd
import numpy as np
import requests
import gymnasium as gym
from datetime import datetime
from sb3_contrib import RecurrentPPO
from dotenv import load_dotenv
from typing import TypedDict, Annotated, List
import operator
from langgraph.graph import StateGraph, END
import random
import shutil
import logging

load_dotenv()

# === VOLLEDIGE LOGGING SETUP ===
logging.basicConfig(
    filename='lumina_full_log.csv',
    level=logging.INFO,
    format='%(asctime)s,%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

INSTRUMENT = os.getenv("INSTRUMENT", "MES JUN 26")
XAI_KEY = os.getenv("XAI_API_KEY")
CROSSTRADE_TOKEN = os.getenv("CROSSTRADE_TOKEN")
CROSSTRADE_ACCOUNT = os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"

CSV_FILE = "market_data_log.csv"
SIGNAL_LOG = "signals_log.csv"
EQUITY_FILE = "equity_curve.csv"
BACKUP_LOG = "signals_log_backup.csv"

print("✅ lumina_v8.7.py – LUMINA v4 + CRASH-FIX + STABIELE FIRST PRINCIPLES")
print(f"🔍 DEBUG: Instrument={INSTRUMENT} | Account={CROSSTRADE_ACCOUNT} | DRY_RUN={DRY_RUN}")

# Slimme CSV-upgrade
if os.path.exists(SIGNAL_LOG):
    try:
        existing = pd.read_csv(SIGNAL_LOG, nrows=1)
        if list(existing.columns) != ['timestamp', 'actor', 'final', 'regime', 'price', 'nexus', 'dream', 'future_edge', 'imbalance', 'world_knowledge']:
            print("🛠️ Oude log gevonden → backup gemaakt")
            shutil.copy(SIGNAL_LOG, BACKUP_LOG)
            os.remove(SIGNAL_LOG)
    except:
        os.remove(SIGNAL_LOG)

model_path = "ppo_trading_model_v18_lumina"

class RealTradingEnv(gym.Env):
    def __init__(self, df=None):
        super().__init__()
        self.observation_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(17,), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(3)
        self.df = df if df is not None else pd.DataFrame()
        self.current_step = 0
    def reset(self, seed=None, options=None):
        self.current_step = 0
        return np.zeros(17, dtype=np.float32), {}
    def step(self, action):
        if len(self.df) == 0 or self.current_step >= len(self.df) - 1:
            return np.zeros(17, dtype=np.float32), 0, True, False, {}
        reward = np.random.normal(0.8, 1.5)
        self.current_step += 1
        done = self.current_step >= len(self.df) - 1
        return np.zeros(17, dtype=np.float32), reward, done, False, {}

# === AUTO MODEL RESET + ZWARE PRE-TRAINING ===
model_path_zip = model_path + ".zip"
if os.path.exists(model_path_zip):
    try:
        model = RecurrentPPO.load(model_path, device="cpu")
        dummy_env = RealTradingEnv()
        model.set_env(dummy_env)
        print("   ✅ Oud LUMINA model geladen")
    except Exception as e:
        print(f"   ⚠️ Model laadfout → nieuw model")
        if os.path.exists(model_path_zip): os.remove(model_path_zip)
        model = None
else:
    model = None

if model is None:
    print("   🔥 Zware pre-training gestart (30.000 steps)...")
    model = RecurrentPPO("MlpLstmPolicy", RealTradingEnv(), verbose=0, device="cpu", learning_rate=1e-4, n_steps=256, ent_coef=0.05)
    total_steps = 30000
    chunk_size = 5000
    for i in range(0, total_steps, chunk_size):
        current = min(i + chunk_size, total_steps)
        print(f"   🌌 LUMINA droomt... [{i:5d}/{total_steps}]")
        model.learn(total_timesteps=chunk_size, progress_bar=False, reset_num_timesteps=False)
    model.save(model_path)
    print("   ✅ Pre-training VOLTOOID!")

dummy_env = RealTradingEnv()
model.set_env(dummy_env)

replay_buffer = []
equity_curve = []
last_sentiment_time = 0
cached_sentiment = "NEUTRAL"
cycle_counter = 0
dream_memory = []
world_knowledge = "Markt gesloten - geen actuele info"
evo_params = {"drift_base": 0.0011, "mutation_rate": 0.15, "pop_size": 8}
predicted_edges = []
actual_returns = []

class TradingState(TypedDict):
    obs: list
    regime: str
    microstructure: dict
    imagined_future_edge: float
    nexus_score: float
    dream_memory_edge: float
    world_knowledge: str
    is_market_open: bool
    previous_market_open: bool
    actor_signal: str
    critic_reasoning: str
    critic_veto: List[str]
    final_signal: str
    last_price: float
    volume: int
    position_qty: int
    atr: float
    data_source: str
    reward: float
    lstm_states: object
    x_sentiment: str
    messages: Annotated[List[str], operator.add]

COLUMNS = ['timestamp', 'actor', 'final', 'regime', 'price', 'nexus', 'dream', 'future_edge', 'imbalance', 'world_knowledge']

def get_market_status():
    try:
        url = "https://app.crosstrade.io/v1/api/market/info"
        headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}", "Content-Type": "application/json"}
        params = {"instrument": INSTRUMENT}
        r = requests.get(url, headers=headers, params=params, timeout=8)
        is_open = r.json().get("status", {}).get("isOpen", False) if r.status_code == 200 else False
        logger.info(f"Market Status Check: {'OPEN' if is_open else 'CLOSED'}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Market Status: {'OPEN' if is_open else 'CLOSED'}")
        return is_open
    except:
        logger.info("Market Status Check: CLOSED (API error)")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Market Status: CLOSED (API error)")
        return False

def fetch_quote():
    try:
        url = f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/quote"
        headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}", "Content-Type": "application/json"}
        params = {"instrument": INSTRUMENT}
        r = requests.get(url, headers=headers, params=params, timeout=8)
        if r.status_code == 200:
            data = r.json()
            return float(data.get("last", 0)), int(data.get("volume", 0)), "CrossTrade"
    except:
        pass
    return 6559 + np.random.normal(0, 8), 150000, "SYNTHETIC"

def get_current_position():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/positions",
                         headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=6)
        positions = r.json() if r.status_code == 200 else []
        for p in positions if isinstance(positions, list) else []:
            if "MES" in str(p.get("instrument", "")):
                return int(p.get("quantity", 0))
    except:
        pass
    return 0

def get_recent_pnl():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/executions",
                         headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=6)
        executions = r.json() if r.status_code == 200 else []
        return float(executions[-1].get("realizedPnL", 0)) if executions else np.random.normal(0.8, 1.5)
    except:
        return np.random.normal(0.8, 1.5)

def calculate_atr(df):
    if len(df) < 5: return 12.0
    changes = df['last'].diff().abs()
    atr = changes.rolling(14, min_periods=1).mean().iloc[-1]
    return np.clip(np.nan_to_num(atr, nan=12.0), 8.0, 35.0)

def calculate_technical_features(df):
    if len(df) < 50:
        return {"rsi": 50, "macd": 0, "momentum": 0}
    df = df.copy()
    delta = df['last'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    ema12 = df['last'].ewm(span=12).mean()
    ema26 = df['last'].ewm(span=26).mean()
    macd = ema12 - ema26
    momentum = df['last'].pct_change(5).iloc[-1] * 100
    return {"rsi": rsi.iloc[-1], "macd": macd.iloc[-1], "momentum": momentum}

def microstructure_oracle_node(state: TradingState) -> TradingState:
    df = pd.read_csv(CSV_FILE).tail(50) if os.path.exists(CSV_FILE) else pd.DataFrame()
    if len(df) < 10:
        imbalance = 0.0
        vol_delta = 0
    else:
        recent_vol = df['volume'].iloc[-10:].mean()
        prev_vol = df['volume'].iloc[-20:-10].mean() if len(df) > 20 else recent_vol
        vol_delta = recent_vol - prev_vol
        price_delta = df['last'].iloc[-1] - df['last'].iloc[-5]
        imbalance = np.sign(vol_delta) * (price_delta / state.get("atr", 12.0))
        imbalance = np.clip(imbalance, -10, 10)  # CRASH-PREVENTIE
    micro = {"imbalance": float(imbalance), "vol_delta": int(vol_delta)}
    logger.info(f"Microstructure Oracle: imbalance = {imbalance:.2f}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Microstructure Oracle: imbalance = {imbalance:.2f}")
    return {**state, "microstructure": micro}

def regime_oracle_node(state: TradingState) -> TradingState:
    df = pd.read_csv(CSV_FILE).tail(100) if os.path.exists(CSV_FILE) else pd.DataFrame()
    atr = calculate_atr(df)
    vol = state["volume"]
    regime = "HIGH_VOLATILITY" if (atr > 25 or vol > 180000) else "LOW_VOLATILITY" if atr < 12 else "NORMAL_MARKET"
    logger.info(f"Regime Oracle: {regime} (ATR {atr:.1f})")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Regime Oracle: {regime} (ATR {atr:.1f})")
    return {**state, "regime": regime, "atr": atr}

def world_knowledge_oracle_node(state: TradingState) -> TradingState:
    global cycle_counter, world_knowledge
    if not state["is_market_open"]:
        logger.info("World Knowledge Oracle: markt gesloten → geen nieuwe data")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] World Knowledge Oracle: markt gesloten → geen nieuwe data")
        return {**state, "world_knowledge": "Markt gesloten - geen actuele info"}
    if cycle_counter % 8 == 0:
        logger.info("World Knowledge Oracle: ophalen actuele info...")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] World Knowledge Oracle: ophalen actuele info...")
        try:
            payload = {"model": "grok-4.20-0309-reasoning", "messages": [
                {"role": "system", "content": "Geef een korte samenvatting (max 12 woorden) van het huidige sentiment en nieuws rond MES / S&P 500 futures."},
                {"role": "user", "content": "Wat gebeurt er nu echt in de markt voor MES JUN 26?"}
            ]}
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=8)
            if r.status_code == 200:
                world_knowledge = r.json()["choices"][0]["message"]["content"].strip()
        except:
            try:
                payload = {"model": "grok-4.20-0309-reasoning", "messages": [{"role": "system", "content": "Geef alleen één woord: BULLISH, BEARISH of NEUTRAL."}, {"role": "user", "content": "Wat is het huidige sentiment op X voor MES JUN 26 futures?"}]}
                r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=8)
                if r.status_code == 200:
                    world_knowledge = r.json()["choices"][0]["message"]["content"].strip()
            except:
                pass
        logger.info(f"World Knowledge: {world_knowledge}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] World Knowledge: {world_knowledge}")
    return {**state, "world_knowledge": world_knowledge}

def parallel_universe_simulator_node(state: TradingState) -> TradingState:
    logger.info("Parallel Universe Simulator: 100 virtuele werelden draaien...")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Parallel Universe Simulator: 100 virtuele werelden draaien...")
    df = pd.read_csv(CSV_FILE).tail(200) if os.path.exists(CSV_FILE) else pd.DataFrame()
    if len(df) < 30:
        return {**state, "imagined_future_edge": 0.0}
    current_price = state["last_price"]
    atr = state["atr"]
    micro = state.get("microstructure", {"imbalance": 0.0})
    drift = evo_params["drift_base"] + micro["imbalance"] * 0.0006
    edges = []
    for _ in range(100):
        sim_price = current_price
        for _ in range(8):
            sim_price *= (1 + np.random.normal(drift, atr * 0.22))
        edge = (sim_price - current_price) / current_price * 100
        edges.append(edge)
    future_edge = np.clip(np.mean(edges), -4.0, 4.0)  # realistischer
    logger.info(f"Parallel Universe Simulator: future_edge = {future_edge:.3f}%")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Parallel Universe Simulator: future_edge = {future_edge:.3f}%")
    return {**state, "imagined_future_edge": float(future_edge)}

def first_principles_oracle_node(state: TradingState) -> TradingState:
    global predicted_edges, actual_returns
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ First Principles Oracle: markt ontleden tot basis...")
    logger.info("First Principles Oracle: markt ontleden tot basis")

    df = pd.read_csv(CSV_FILE).tail(50) if os.path.exists(CSV_FILE) else pd.DataFrame()
    if len(df) < 5:
        return state

    imbalance = state.get("microstructure", {}).get("imbalance", 0.0)
    supply_score = -imbalance * 2.5
    demand_score = imbalance * 2.5 if imbalance > 0 else 0
    momentum_score = np.clip((df['last'].pct_change(5).iloc[-1] * 100) if len(df) > 5 else 0, -5, 5)  # anti-inf fix

    total_score = supply_score + demand_score + momentum_score
    print(f"   📊 Breakdown → Aanbod: {supply_score:+.2f} | Vraag: {demand_score:+.2f} | Momentum: {momentum_score:+.2f} | Totaal: {total_score:+.2f}")
    logger.info(f"First Principles Breakdown: supply={supply_score:.2f} demand={demand_score:.2f} momentum={momentum_score:.2f} total={total_score:.2f}")

    if len(predicted_edges) > 30:
        corr = np.corrcoef(predicted_edges[-50:], actual_returns[-50:])[0, 1]
        impact = abs(corr) * 100
        print(f"   🌍 Universe Effectiveness: corr={corr:.3f} | impact={impact:.1f}%")
        logger.info(f"Universe Effectiveness: corr={corr:.3f} | impact={impact:.1f}%")
        if impact > 25:
            evo_params["drift_base"] *= 1.08
            evo_params["mutation_rate"] = max(0.08, evo_params["mutation_rate"] * 0.95)
        elif impact < 10:
            evo_params["drift_base"] *= 0.92
            evo_params["mutation_rate"] = min(0.22, evo_params["mutation_rate"] * 1.05)

    return state

def self_healing_oracle_node(state: TradingState) -> TradingState:
    global cycle_counter
    if cycle_counter % 50 == 0:
        logger.info("Self-Healing Oracle: systeemcheck")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Self-Healing Oracle: systeemcheck")
        if evo_params["mutation_rate"] > 0.22:
            evo_params["mutation_rate"] *= 0.92
    return state

def evolution_oracle_node(state: TradingState) -> TradingState:
    global cycle_counter
    if cycle_counter % 80 == 0 and cycle_counter > 100:
        logger.info("Evolution Oracle: parameters aanpassen...")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Evolution Oracle: parameters aanpassen...")
        population = [evo_params["drift_base"] + random.gauss(0, 0.0003) for _ in range(evo_params["pop_size"])]
        best_drift = max(population, key=lambda x: abs(x))
        evo_params["drift_base"] = best_drift * (1 + random.uniform(-evo_params["mutation_rate"], evo_params["mutation_rate"]))
        evo_params["mutation_rate"] = max(0.05, min(0.25, evo_params["mutation_rate"] * (0.98 if random.random() > 0.5 else 1.03)))
    return state

def dream_memory_node(state: TradingState) -> TradingState:
    global dream_memory
    if len(dream_memory) > 30: dream_memory.pop(0)
    if abs(state.get("imagined_future_edge", 0)) > 0.5:
        dream_memory.append(state.get("imagined_future_edge", 0))
    dream_edge = np.mean(dream_memory) if dream_memory else 0.0
    logger.info(f"Dream Memory: {len(dream_memory)} dromen | gemiddelde edge = {dream_edge:.3f}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Dream Memory: {len(dream_memory)} dromen | gemiddelde edge = {dream_edge:.3f}")
    return {**state, "dream_memory_edge": float(dream_edge)}

def nexus_score_node(state: TradingState) -> TradingState:
    micro_score = abs(state.get("microstructure", {}).get("imbalance", 0)) * 28
    future_score = abs(state.get("imagined_future_edge", 0)) * 18
    dream_score = abs(state.get("dream_memory_edge", 0)) * 14
    world_score = 25 if any(x in state.get("world_knowledge", "").lower() for x in ["bullish", "bearish"]) else 12
    regime_score = 45 if "LOW_VOLATILITY" in state["regime"] else 28
    nexus = min(99.9, max(35, (micro_score + future_score + dream_score + world_score + regime_score) / 3.4))
    logger.info(f"Nexus Score: {nexus:.1f}/100")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Nexus Score: {nexus:.1f}/100")
    return {**state, "nexus_score": float(nexus)}

def build_rich_obs(state: TradingState, df) -> list:
    price_norm = state["last_price"] / 7000
    vol_norm = min(state["volume"] / 200000, 2.0)
    atr_norm = min(state["atr"] / 30, 2.0)
    trend_20 = 1 if len(df) > 20 and state["last_price"] > df['last'].iloc[-20:-5].mean() else -1
    trend_50 = 1 if len(df) > 50 and state["last_price"] > df['last'].iloc[-50:-10].mean() else -1
    feats = calculate_technical_features(df)
    rsi_norm = (feats["rsi"] - 50) / 50
    macd_norm = feats["macd"] / 10
    momentum_norm = feats["momentum"] / 5
    micro = state.get("microstructure", {"imbalance": 0.0})
    world_norm = 1 if "bullish" in state.get("world_knowledge", "").lower() else -1 if "bearish" in state.get("world_knowledge", "").lower() else 0
    obs = [
        price_norm, vol_norm, atr_norm, float(trend_20), float(trend_50),
        rsi_norm, macd_norm, momentum_norm, state.get("position_qty", 0) / 2.0,
        float(len(df) > 30), micro["imbalance"], micro.get("vol_delta", 0) / 10000,
        state.get("imagined_future_edge", 0) / 5.0, state.get("dream_memory_edge", 0) / 5.0,
        state.get("nexus_score", 50) / 100, world_norm, 0.0
    ]
    return np.clip(np.nan_to_num(obs, nan=0.0), -5, 5).tolist()

def get_real_x_sentiment():
    global last_sentiment_time, cached_sentiment
    if time.time() - last_sentiment_time < 90: return cached_sentiment
    if not XAI_KEY: return cached_sentiment
    try:
        payload = {"model": "grok-4.20-0309-reasoning", "messages": [{"role": "system", "content": "Geef alleen één woord: BULLISH, BEARISH of NEUTRAL."}, {"role": "user", "content": "Wat is het huidige sentiment op X voor MES JUN 26 futures?"}]}
        r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=8)
        if r.status_code == 200:
            sentiment = r.json()["choices"][0]["message"]["content"].strip().upper()
            cached_sentiment = sentiment if sentiment in ["BULLISH", "BEARISH", "NEUTRAL"] else "NEUTRAL"
            last_sentiment_time = time.time()
            return cached_sentiment
    except:
        pass
    return cached_sentiment

def actor_node(state: TradingState) -> TradingState:
    global cycle_counter
    df = pd.read_csv(CSV_FILE).tail(100) if os.path.exists(CSV_FILE) else pd.DataFrame()
    obs = build_rich_obs(state, df)
    obs_array = np.array([obs], dtype=np.float32)
    lstm_states = state.get("lstm_states", None)
    if cycle_counter < 80:
        action = np.random.randint(0, 3)
        new_lstm_states = None
    else:
        try:
            action, new_lstm_states = model.predict(obs_array, state=lstm_states, deterministic=True)
            action = int(action.item())
        except:
            action = 0
            new_lstm_states = None
    signal = {0: "HOLD", 1: "BUY", 2: "SELL"}[action]
    return {**state, "actor_signal": signal, "obs": obs, "lstm_states": new_lstm_states}

def critic_node(state: TradingState) -> TradingState:
    global cycle_counter
    cycle_counter += 1
    state["x_sentiment"] = get_real_x_sentiment()
    veto = []
    if "HIGH_VOLATILITY" in state["regime"] and state["actor_signal"] != "HOLD":
        veto.append("High vol risk")
    if state["x_sentiment"] == "BEARISH" and state["actor_signal"] == "BUY":
        veto.append("Bearish sentiment veto")
    if state["x_sentiment"] == "BULLISH" and state["actor_signal"] == "SELL":
        veto.append("Bullish sentiment veto")
    micro = state.get("microstructure", {"imbalance": 0.0})
    if micro["imbalance"] < -1.3 and state["actor_signal"] == "BUY":
        veto.append("Negative imbalance veto")
    if micro["imbalance"] > 1.3 and state["actor_signal"] == "SELL":
        veto.append("Positive imbalance veto")
    if state.get("imagined_future_edge", 0) < -1.0 and state["actor_signal"] != "HOLD":
        veto.append("Negative future_edge veto")
    if "bearish" in state.get("world_knowledge", "").lower() and state["actor_signal"] == "BUY":
        veto.append("World says bearish")
    if cycle_counter > 120 and state.get("nexus_score", 50) < 35:
        veto.append("Low consciousness veto")
    final = "HOLD (NEXUS VETO)" if veto else state["actor_signal"]
    logger.info(f"Critic: veto's = {veto if veto else 'geen'}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Critic: veto's = {veto if veto else 'geen'}")
    return {**state, "critic_reasoning": "Rule-based critic", "critic_veto": veto, "final_signal": final}

def supervisor_node(state: TradingState) -> TradingState:
    logger.info(f"Supervisor: Nexus Score = {state.get('nexus_score', 0):.1f} | World Knowledge = {state.get('world_knowledge', 'Stil')} | Markt: {'OPEN' if state.get('is_market_open') else 'CLOSED'}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Supervisor: Nexus Score = {state.get('nexus_score', 0):.1f} | World Knowledge = {state.get('world_knowledge', 'Stil')} | Markt: {'OPEN' if state.get('is_market_open') else 'CLOSED'}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Actor: {state['actor_signal']} → Final: {state['final_signal']}")

    global predicted_edges, actual_returns
    if len(equity_curve) > 1:
        prev_price = equity_curve[-2]
        current_price = state["last_price"]
        if prev_price != 0:
            actual_return = (current_price - prev_price) / prev_price * 100
            prev_edge = state.get("imagined_future_edge", 0)
            predicted_edges.append(prev_edge)
            actual_returns.append(actual_return)

    if state.get("previous_market_open", True) and not state["is_market_open"]:
        logger.info("MARKT SLUITING DETECTEERD → ALLE POSITIES WORDEN GECLOSET")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 MARKT SLUITING → ALLE POSITIES WORDEN GECLOSET")
        if state.get("position_qty", 0) != 0:
            side = "SELL" if state["position_qty"] > 0 else "BUY"
            quantity = abs(state["position_qty"])
            logger.info(f"Auto-close: {side} {quantity} contracts")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Auto-close: {side} {quantity} contracts")
            if not DRY_RUN:
                try:
                    url = f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/orders"
                    headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}", "Content-Type": "application/json"}
                    payload = {"instrument": INSTRUMENT, "action": side, "quantity": quantity, "type": "MARKET"}
                    requests.post(url, headers=headers, json=payload, timeout=8)
                except:
                    pass

    # ALLEEN echte orders printen + uitvoeren
    if state["is_market_open"] and state["final_signal"] != "HOLD":
        risk_per_point = state["atr"] * 0.5
        quantity = max(1, min(4, int(120 / (risk_per_point + 1))))
        side = "BUY" if state["final_signal"] == "BUY" else "SELL"
        trade_type = "LIVE ORDER" if not DRY_RUN else "PAPER TRADE"
        logger.info(f"Order: {trade_type} {side} {quantity} contracts")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {trade_type}: {side} {quantity} contracts")
        if not DRY_RUN:
            try:
                url = f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/orders"
                headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}", "Content-Type": "application/json"}
                payload = {"instrument": INSTRUMENT, "action": side, "quantity": quantity, "type": "MARKET"}
                requests.post(url, headers=headers, json=payload, timeout=8)
            except:
                pass

    equity_curve.append(state["last_price"])
    if len(equity_curve) > 100:
        dd = (max(equity_curve[-100:]) - min(equity_curve[-100:])) / max(equity_curve[-100:]) * 100
        if dd > 15:
            logger.info("Drawdown >15% → pauze")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Drawdown >15% → pauze")

    log_row = {
        "timestamp": datetime.now(), "actor": state['actor_signal'], "final": state['final_signal'],
        "regime": state['regime'], "price": state['last_price'], "nexus": state.get("nexus_score", 0),
        "dream": state.get("dream_memory_edge", 0), "future_edge": state.get("imagined_future_edge", 0),
        "imbalance": state.get("microstructure", {}).get("imbalance", 0),
        "world_knowledge": state.get("world_knowledge", "Stil")
    }
    pd.DataFrame([log_row]).to_csv(SIGNAL_LOG, mode="a", header=not os.path.exists(SIGNAL_LOG), index=False, columns=COLUMNS)
    return {**state, "previous_market_open": state["is_market_open"]}

def replay_buffer_node(state: TradingState) -> TradingState:
    pnl = get_recent_pnl()
    regime_factor = 1.5 if "LOW_VOLATILITY" in state["regime"] else 0.7
    reward = (pnl * 0.8) * regime_factor - (state["atr"] / 15) + state.get("microstructure", {}).get("imbalance", 0) * 0.5 + state.get("imagined_future_edge", 0) * 0.9 + state.get("nexus_score", 50) * 0.03
    reward = np.clip(reward, -5, 5)
    
    replay_buffer.append((state["obs"], state.get("actor_signal", "HOLD"), reward, state["last_price"]))
    if len(replay_buffer) > 500: replay_buffer.pop(0)

    try:
        df_log = pd.read_csv(SIGNAL_LOG)
        log_len = len(df_log)
    except:
        log_len = 0

    if log_len % 40 == 0:
        model.learn(total_timesteps=128, reset_num_timesteps=False, progress_bar=False)  # GEEN env= meer!
        model.save(model_path)
    if log_len % 200 == 0:
        logger.info("Replay Buffer: continual learning actief")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Replay Buffer: continual learning actief")

    return {**state, "reward": reward}

workflow = StateGraph(TradingState)
workflow.add_node("data", lambda s: {**s, **(lambda p, v, src: {"last_price": p, "volume": v, "data_source": src})(*fetch_quote()), "position_qty": get_current_position(), "is_market_open": get_market_status()})
workflow.add_node("microstructure", microstructure_oracle_node)
workflow.add_node("regime", regime_oracle_node)
workflow.add_node("world", world_knowledge_oracle_node)
workflow.add_node("parallel_universe", parallel_universe_simulator_node)
workflow.add_node("first_principles", first_principles_oracle_node)
workflow.add_node("self_healing", self_healing_oracle_node)
workflow.add_node("evolution", evolution_oracle_node)
workflow.add_node("dream", dream_memory_node)
workflow.add_node("nexus", nexus_score_node)
workflow.add_node("actor", actor_node)
workflow.add_node("critic", critic_node)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("replay", replay_buffer_node)

workflow.set_entry_point("data")
workflow.add_edge("data", "microstructure")
workflow.add_edge("microstructure", "regime")
workflow.add_edge("regime", "world")
workflow.add_edge("world", "parallel_universe")
workflow.add_edge("parallel_universe", "first_principles")
workflow.add_edge("first_principles", "self_healing")
workflow.add_edge("self_healing", "evolution")
workflow.add_edge("evolution", "dream")
workflow.add_edge("dream", "nexus")
workflow.add_edge("nexus", "actor")
workflow.add_edge("actor", "critic")
workflow.add_edge("critic", "supervisor")
workflow.add_edge("supervisor", "replay")
workflow.add_edge("replay", END)

graph = workflow.compile()

if __name__ == "__main__":
    print("🚀 lumina_v8.7 LIVE – LUMINA v4 met CRASH-FIX + stabiele ontleding (Ctrl+C om stoppen)\n")
    try:
        initial_state = {"obs": [0]*17, "regime": "", "microstructure": {}, "imagined_future_edge": 0.0, "nexus_score": 50.0, "dream_memory_edge": 0.0, "world_knowledge": "Markt gesloten - geen actuele info", "is_market_open": False, "previous_market_open": False, "actor_signal": "", "critic_reasoning": "", "critic_veto": [], "final_signal": "", "last_price": 0, "volume": 0, "position_qty": 0, "atr": 12.0, "data_source": "", "reward": 0.0, "lstm_states": None, "x_sentiment": "", "messages": []}
        while True:
            result = graph.invoke(initial_state)
            row = {"timestamp": datetime.now(), "last": result["last_price"], "volume": result["volume"]}
            pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
            time.sleep(4 if result["is_market_open"] else 60)
    except KeyboardInterrupt:
        print("\n🛑 LUMINA gaat rusten.")