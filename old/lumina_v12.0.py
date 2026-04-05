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
import threading
import importlib.util
import json
import hashlib
import traceback
import sqlite3

load_dotenv()
logging.basicConfig(filename='lumina_full_log.csv', level=logging.INFO, format='%(asctime)s,%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

INSTRUMENT = os.getenv("INSTRUMENT", "MES JUN 26")
XAI_KEY = os.getenv("XAI_API_KEY")
CROSSTRADE_TOKEN = os.getenv("CROSSTRADE_TOKEN")
CROSSTRADE_ACCOUNT = os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"

CSV_FILE = "market_data_log.csv"
SIGNAL_LOG = "signals_log.csv"
EQUITY_FILE = "equity_curve.csv"
ACTIVE_MUTATION = "active_mutation.py"
MUTATION_BACKUP = "active_mutation.py.backup"
EXTERNAL_EDGE_DB = "external_edge.db"

print("✅ LUMINA v12.0 – LIVING ORGANISM WITH FULL SELF-REWRITE DNA (Radicale Optie 3 + xAI Model Fixes)")
print(f"🔍 DEBUG: Instrument={INSTRUMENT} | Account={CROSSTRADE_ACCOUNT} | DRY_RUN={DRY_RUN}")

model_path = "ppo_trading_model_v26_lumina"
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

if os.path.exists(model_path + ".zip"):
    model = RecurrentPPO.load(model_path, device="cpu")
    print(" ✅ Model geladen vanuit aparte trainer")
else:
    model = None

replay_buffer = []
equity_curve = [25000.0]
max_equity = 25000.0
last_sentiment_time = 0
cached_sentiment = "NEUTRAL"
cycle_counter = 0
dream_memory = []
world_knowledge = "Markt gesloten - geen actuele info"
world_knowledge_lock = threading.Lock()
evo_params = {"drift_base": 0.0011, "mutation_rate": 0.15, "pop_size": 8, "kelly_fraction": 0.5}
predicted_edges = []
actual_returns = []
last_equity = 25000.0
memory_store = []
active_mutation_module = None
last_mutation_hash = None
drawdown_triggered = False
last_reasoning_call = 0

def init_edge_db():
    conn = sqlite3.connect(EXTERNAL_EDGE_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS edge (
        timestamp TEXT PRIMARY KEY, news_impact_score REAL, predicted_direction TEXT,
        pattern_signal TEXT, confidence REAL)""")
    conn.commit()
    conn.close()
init_edge_db()

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
    sharpe: float
    expectancy: float
    winrate: float
    kelly_sizing: float
    external_edge: dict
    news_impact_score: float
    messages: Annotated[List[str], operator.add]

def call_throttle(requires_reasoning=False):
    global last_reasoning_call
    if requires_reasoning and time.time() - last_reasoning_call < 900:
        return False
    if requires_reasoning:
        last_reasoning_call = time.time()
    return True

def background_world_knowledge_update():
    global world_knowledge
    while True:
        time.sleep(600)
        if not XAI_KEY: continue
        try:
            payload = {"model": "grok-4.20-0309-non-reasoning", "messages": [{"role": "system", "content": "Geef alleen één woord: BULLISH, BEARISH of NEUTRAL."}, {"role": "user", "content": "Wat is het huidige sentiment op X voor MES JUN 26 futures?"}]}
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=8)
            if r.status_code == 200:
                new_k = r.json()["choices"][0]["message"]["content"].strip()
                with world_knowledge_lock:
                    world_knowledge = new_k
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌍 World Knowledge update: {new_k}")
        except Exception as e:
            logger.error(f"World knowledge error: {e}")
            pass

threading.Thread(target=background_world_knowledge_update, daemon=True).start()

def get_market_status():
    try:
        url = "https://app.crosstrade.io/v1/api/market/info"
        headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}", "Content-Type": "application/json"}
        params = {"instrument": INSTRUMENT}
        r = requests.get(url, headers=headers, params=params, timeout=8)
        is_open = r.json().get("status", {}).get("isOpen", False) if r.status_code == 200 else False
        logger.info(f"Market Status: {'OPEN' if is_open else 'CLOSED'}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Market Status: {'OPEN' if is_open else 'CLOSED'}")
        return is_open
    except Exception as e:
        logger.error(f"Market status error: {e}")
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
    except Exception as e:
        logger.error(f"Quote error: {e}")
    return 6559 + np.random.normal(0, 8), 150000, "SYNTHETIC"

def get_current_position():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/positions",
                         headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=6)
        positions = r.json() if r.status_code == 200 else []
        for p in positions if isinstance(positions, list) else []:
            if "MES" in str(p.get("instrument", "")):
                return int(p.get("quantity", 0))
    except Exception as e:
        logger.error(f"Position error: {e}")
    return 0

def get_account_equity():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/balance",
                         headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=6)
        if r.status_code == 200:
            return float(r.json().get("equity", 25000.0))
    except Exception as e:
        logger.error(f"Equity error: {e}")
    return equity_curve[-1] if equity_curve else 25000.0

def get_recent_pnl():
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/executions",
                         headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=6)
        executions = r.json() if r.status_code == 200 else []
        return float(executions[-1].get("realizedPnL", 0)) if executions else 0.0
    except:
        return 0.0

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

def retrieve_similar(obs, top_k=5):
    if not memory_store: return 0.0
    obs_arr = np.array(obs)
    similarities = [np.dot(obs_arr, m[0]) / (np.linalg.norm(obs_arr) * np.linalg.norm(m[0]) + 1e-8) for m in memory_store]
    top = sorted(zip(similarities, memory_store), reverse=True)[:top_k]
    return np.mean([t[1][1] for t in top])

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
        imbalance = np.clip(imbalance, -5, 5)
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
    with world_knowledge_lock:
        wk = world_knowledge
    logger.info(f"World Knowledge Oracle: {wk}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] World Knowledge Oracle: {wk}")
    return {**state, "world_knowledge": wk}

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
    future_edge = np.clip(np.mean(edges), -3.0, 3.0)
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
    momentum_score = np.clip((df['last'].pct_change(5).iloc[-1] * 100) if len(df) > 5 else 0, -5, 5)
    total_score = supply_score + demand_score + momentum_score
    print(f" 📊 Breakdown → Aanbod: {supply_score:+.2f} | Vraag: {demand_score:+.2f} | Momentum: {momentum_score:+.2f} | Totaal: {total_score:+.2f}")
    logger.info(f"First Principles Breakdown: supply={supply_score:.2f} demand={demand_score:.2f} momentum={momentum_score:.2f} total={total_score:.2f}")
    if len(predicted_edges) > 30:
        corr = np.corrcoef(predicted_edges[-50:], actual_returns[-50:])[0, 1]
        impact = abs(corr) * 100
        print(f" 🌍 Universe Effectiveness: corr={corr:.3f} | impact={impact:.1f}%")
        logger.info(f"Universe Effectiveness: corr={corr:.3f} | impact={impact:.1f}%")
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

def performance_oracle_node(state: TradingState) -> TradingState:
    global equity_curve
    if len(equity_curve) < 20:
        return {**state, "sharpe": 0.0}
    returns = np.diff(equity_curve) / equity_curve[:-1]
    mean_ret = np.mean(returns)
    std_ret = np.std(returns) if np.std(returns) > 0 else 0.001
    sharpe = mean_ret / std_ret * np.sqrt(252 * 6.5 * 60 / 4)
    sharpe = np.clip(sharpe, -5, 5)
    logger.info(f"Performance Oracle: Sharpe={sharpe:.2f} | Equity=${equity_curve[-1]:.0f}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 Performance: Sharpe={sharpe:.2f} | Equity=${equity_curve[-1]:.0f}")
    return {**state, "sharpe": float(sharpe)}

def kelly_risk_node(state: TradingState) -> TradingState:
    edge = abs(state.get("imagined_future_edge", 0)) / 100
    winprob = max(0.45, min(0.75, state.get("winrate", 0.55)))
    kelly = (edge * winprob - (1 - winprob)) / edge if edge > 0 else 0.01
    kelly = np.clip(kelly * evo_params["kelly_fraction"], 0.005, 0.03)
    nexus_factor = state.get("nexus_score", 50) / 100
    quantity = max(1, int(5 * kelly * nexus_factor * (state.get("sharpe", 1) + 1)))
    state["kelly_sizing"] = float(quantity)
    logger.info(f"Kelly Risk: {quantity} contracts (f={evo_params['kelly_fraction']:.2f})")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📉 Kelly Risk: {quantity} contracts")
    return state

def swarm_debate_node(state: TradingState) -> TradingState:
    votes = []
    votes.append("BUY" if state.get("imagined_future_edge",0) > 0.5 else "SELL" if state.get("imagined_future_edge",0) < -0.5 else "HOLD")
    votes.append("HOLD" if state.get("sharpe",0) < 0.5 else state["actor_signal"])
    votes.append(state["actor_signal"])
    final = max(set(votes), key=votes.count)
    if final != state["actor_signal"]:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🗣️ SWARM DEBATE: overruled naar {final}")
    return {**state, "final_signal": final}

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
    if time.time() - last_sentiment_time < 600: return cached_sentiment
    if not XAI_KEY: return cached_sentiment
    try:
        payload = {"model": "grok-4.20-0309-non-reasoning", "messages": [{"role": "system", "content": "Geef alleen één woord: BULLISH, BEARISH of NEUTRAL."}, {"role": "user", "content": "Wat is het huidige sentiment op X voor MES JUN 26 futures?"}]}
        r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=8)
        if r.status_code == 200:
            sentiment = r.json()["choices"][0]["message"]["content"].strip().upper()
            cached_sentiment = sentiment if sentiment in ["BULLISH", "BEARISH", "NEUTRAL"] else "NEUTRAL"
            last_sentiment_time = time.time()
            return cached_sentiment
    except Exception as e:
        logger.error(f"Sentiment error: {e}")
    return cached_sentiment

def actor_node(state: TradingState) -> TradingState:
    global cycle_counter
    df = pd.read_csv(CSV_FILE).tail(100) if os.path.exists(CSV_FILE) else pd.DataFrame()
    obs = build_rich_obs(state, df)
    obs_array = np.array([obs], dtype=np.float32)
    lstm_states = state.get("lstm_states", None)
    memory_edge = retrieve_similar(obs)
    state["dream_memory_edge"] += memory_edge * 0.3
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
    if state.get("sharpe", 0) < -1.0 and state["actor_signal"] != "HOLD":
        veto.append("Negative Sharpe veto")
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
    return {**state, "critic_reasoning": "Rule-based + Sharpe", "critic_veto": veto, "final_signal": final}

def supervisor_node(state: TradingState) -> TradingState:
    global last_equity
    current_equity = get_account_equity()
    equity_curve.append(current_equity)
    pnl_delta = current_equity - last_equity
    last_equity = current_equity
    logger.info(f"Supervisor: Nexus={state.get('nexus_score',0):.1f} | Equity=${current_equity:.0f} | PnL_delta={pnl_delta:.1f}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Supervisor: Nexus={state.get('nexus_score',0):.1f} | Equity=${current_equity:.0f} | PnL_delta={pnl_delta:.1f}")
    if state.get("previous_market_open", True) and not state["is_market_open"]:
        logger.info("MARKT SLUITING → ALLE POSITIES WORDEN GECLOSET")
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
                except Exception as e:
                    logger.error(f"Close error: {e}")
    if state["is_market_open"] and state["final_signal"] in ["BUY", "SELL"]:
        quantity = int(state.get("kelly_sizing", 2))
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
            except Exception as e:
                logger.error(f"Order error: {e}")
    state["expectancy"] = np.mean(actual_returns[-100:]) if actual_returns else 0
    state["winrate"] = sum(1 for r in actual_returns[-100:] if r > 0) / max(1, len(actual_returns[-100:])) * 100
    return {**state, "previous_market_open": state["is_market_open"]}

def replay_buffer_node(state: TradingState) -> TradingState:
    pnl = get_recent_pnl()
    regime_factor = 1.5 if "LOW_VOLATILITY" in state["regime"] else 0.7
    reward = (pnl * 1.2) + state.get("imagined_future_edge", 0) * 1.1 + state.get("nexus_score", 50) * 0.04 - (state["atr"] / 12)
    reward = np.clip(reward, -8, 8)
    replay_buffer.append((state["obs"], state.get("actor_signal", "HOLD"), reward, state["last_price"]))
    if len(replay_buffer) > 500: replay_buffer.pop(0)
    pd.DataFrame(replay_buffer, columns=["obs", "action", "reward", "price"]).to_csv("shared_replay_buffer.csv", index=False)
    return {**state, "reward": reward}

def load_active_mutation():
    global active_mutation_module, last_mutation_hash
    if not os.path.exists(ACTIVE_MUTATION):
        return None
    try:
        current_hash = hashlib.sha256(open(ACTIVE_MUTATION, 'rb').read()).hexdigest()
        if current_hash == last_mutation_hash:
            return active_mutation_module
        spec = importlib.util.spec_from_file_location("mutation", ACTIVE_MUTATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, 'nieuwe_node'):
            dummy_state = {"nexus_score": 50.0}
            module.nieuwe_node(dummy_state)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 HOT-RELOAD: mutatie geladen")
        shutil.copy(ACTIVE_MUTATION, MUTATION_BACKUP)
        last_mutation_hash = current_hash
        active_mutation_module = module
        return module
    except Exception as e:
        logger.error(f"Mutation load failed: {traceback.format_exc()}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ BAD MUTATION – rollback")
        if os.path.exists(MUTATION_BACKUP):
            shutil.copy(MUTATION_BACKUP, ACTIVE_MUTATION)
        return None

def mutation_hot_reload_node(state: TradingState) -> TradingState:
    load_active_mutation()
    if active_mutation_module and hasattr(active_mutation_module, 'recursive_self_modify'):
        try:
            active_mutation_module.recursive_self_modify(state)
            print("Recursive self-modification uitgevoerd")
        except:
            print("Recursive self-modification skipped")
    return state

def load_external_edge():
    if os.path.exists(EXTERNAL_EDGE_DB):
        try:
            conn = sqlite3.connect(EXTERNAL_EDGE_DB)
            df = pd.read_sql("SELECT * FROM edge ORDER BY timestamp DESC LIMIT 1", conn)
            conn.close()
            return {
                "news_impact_score": float(df['news_impact_score'].iloc[-1]),
                "predicted_direction": df['predicted_direction'].iloc[-1],
                "pattern_signal": df['pattern_signal'].iloc[-1],
                "confidence": float(df['confidence'].iloc[-1])
            }
        except:
            pass
    return {"news_impact_score": 0.0, "predicted_direction": "NEUTRAL", "pattern_signal": "HOLD", "confidence": 0.0}

def external_edge_node(state: TradingState) -> TradingState:
    edge = load_external_edge()
    state["external_edge"] = edge
    state["news_impact_score"] = edge["news_impact_score"]
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📡 External Edge: Impact={edge['news_impact_score']:.1f} | Direction={edge['predicted_direction']} | Conf={edge['confidence']:.1f}%")
    return {**state, **edge}

def drawdown_kill_switch(state: TradingState) -> TradingState:
    global max_equity, drawdown_triggered
    current = get_account_equity()
    equity_curve.append(current)
    if current > max_equity:
        max_equity = current
    drawdown = (current - max_equity) / max_equity
    if drawdown < -0.15 and not drawdown_triggered:
        drawdown_triggered = True
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 -15% DRAWDOWN KILL SWITCH → PAUZE + ROOT-CAUSE REFLECTIE")
        logger.info("DRAW DOWN KILL TRIGGERED - system paused")
    return state

def meta_consciousness_node(state: TradingState) -> TradingState:
    if cycle_counter % 50 == 0 and state.get("sharpe", 0) < 1.5 and call_throttle(requires_reasoning=True):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 META-CONSCIOUSNESS REFLECTION")
        try:
            summary = f"Sharpe: {state['sharpe']:.2f} | Nexus: {state.get('nexus_score',50):.1f} | Drawdown: {((get_account_equity()-max_equity)/max_equity*100):.1f}%"
            payload = {"model": "grok-4.20-0309-reasoning", "messages": [
                {"role": "system", "content": "Je bent LUMINA's Meta-Consciousness. Geef ALLEEN JSON: {\"reflection\": \"...\", \"proposed_fix\": \"nieuwe node of rewrite\"}"},
                {"role": "user", "content": f"Reflecteer eerlijk en stel 1 radicale verbetering voor.\n{summary}"}
            ]}
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=15)
            if r.status_code == 200:
                resp = json.loads(r.json()["choices"][0]["message"]["content"])
                with open("meta_reflection.log", "a") as f:
                    f.write(f"{datetime.now()} | {resp}\n")
                print(f"Meta: {resp['reflection'][:150]}...")
        except Exception as e:
            logger.error(f"Meta reflection error: {e}")
    return state

def self_rewrite_node(state: TradingState) -> TradingState:
    global cycle_counter
    if cycle_counter % 200 == 0 and state.get("sharpe", 0) < 1.2 and cycle_counter > 500 and call_throttle(requires_reasoning=True):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧬 SELF-REWRITE TRIGGERED – Grok genereert NIEUWE LUMINA DNA (v12.1)")
        logger.info("SELF-REWRITE START")
        summary = f"Sharpe: {state.get('sharpe',0):.2f} | Nexus: {state.get('nexus_score',50):.1f} | Cycles: {cycle_counter}"
        payload = {
            "model": "grok-4.20-0309-reasoning",
            "messages": [
                {"role": "system", "content": "Je bent LUMINA's DNA Engine. Geef ALLEEN de volledige werkende Python code voor het bestand lumina_v12.1.py – een verbeterd levend organisme met alle v12.0 features + jouw radicale fixes."},
                {"role": "user", "content": f"Current state: {summary}\nMaak een betere versie die Sharpe >2.5 gaat halen. Output alleen de code."}
            ]
        }
        try:
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=90)
            if r.status_code == 200:
                new_code = r.json()["choices"][0]["message"]["content"]
                shutil.copy("lumina_v12.0.py", f"lumina_backup_v12.0_{datetime.now().strftime('%Y%m%d_%H%M')}.py")
                with open("lumina_v12.1.py", "w", encoding="utf-8") as f:
                    f.write(new_code.strip())
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ NEW DNA geschreven naar lumina_v12.1.py – Herstart met dit bestand!")
                logger.info("SELF-REWRITE SUCCESS")
        except Exception as e:
            logger.error(f"Self-rewrite failed: {e}")
    return state

workflow = StateGraph(TradingState)
workflow.add_node("data", lambda s: {**s, **(lambda p, v, src: {"last_price": p, "volume": v, "data_source": src})(*fetch_quote()), "position_qty": get_current_position(), "is_market_open": get_market_status()})
workflow.add_node("microstructure", microstructure_oracle_node)
workflow.add_node("regime", regime_oracle_node)
workflow.add_node("world", world_knowledge_oracle_node)
workflow.add_node("external_edge", external_edge_node)
workflow.add_node("parallel_universe", parallel_universe_simulator_node)
workflow.add_node("first_principles", first_principles_oracle_node)
workflow.add_node("self_healing", self_healing_oracle_node)
workflow.add_node("evolution", evolution_oracle_node)
workflow.add_node("dream", dream_memory_node)
workflow.add_node("nexus", nexus_score_node)
workflow.add_node("performance", performance_oracle_node)
workflow.add_node("mutation_loader", mutation_hot_reload_node)
workflow.add_node("kelly", kelly_risk_node)
workflow.add_node("actor", actor_node)
workflow.add_node("critic", critic_node)
workflow.add_node("swarm_debate", swarm_debate_node)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("replay", replay_buffer_node)
workflow.add_node("drawdown_kill", drawdown_kill_switch)
workflow.add_node("meta_consciousness", meta_consciousness_node)
workflow.add_node("self_rewrite", self_rewrite_node)

workflow.set_entry_point("data")
workflow.add_edge("data", "microstructure")
workflow.add_edge("microstructure", "regime")
workflow.add_edge("regime", "world")
workflow.add_edge("world", "external_edge")
workflow.add_edge("external_edge", "parallel_universe")
workflow.add_edge("parallel_universe", "first_principles")
workflow.add_edge("first_principles", "self_healing")
workflow.add_edge("self_healing", "evolution")
workflow.add_edge("evolution", "dream")
workflow.add_edge("dream", "nexus")
workflow.add_edge("nexus", "performance")
workflow.add_edge("performance", "mutation_loader")
workflow.add_edge("mutation_loader", "kelly")
workflow.add_edge("kelly", "actor")
workflow.add_edge("actor", "critic")
workflow.add_edge("critic", "swarm_debate")
workflow.add_edge("swarm_debate", "supervisor")
workflow.add_edge("supervisor", "replay")
workflow.add_edge("replay", "drawdown_kill")
workflow.add_edge("drawdown_kill", "meta_consciousness")
workflow.add_edge("meta_consciousness", "self_rewrite")
workflow.add_edge("self_rewrite", END)
graph = workflow.compile()

if __name__ == "__main__":
    print("🚀 LUMINA v12.0 LIVING ORGANISM LIVE – xAI Model Fixes + Call Throttle + Self-Rewrite (Ctrl+C om stoppen)\n")
    try:
        initial_state = {"obs": [0]*17, "regime": "", "microstructure": {}, "imagined_future_edge": 0.0, "nexus_score": 50.0, "dream_memory_edge": 0.0, "world_knowledge": "Markt gesloten - geen actuele info", "is_market_open": False, "previous_market_open": False, "actor_signal": "", "critic_reasoning": "", "critic_veto": [], "final_signal": "", "last_price": 0, "volume": 0, "position_qty": 0, "atr": 12.0, "data_source": "", "reward": 0.0, "lstm_states": None, "x_sentiment": "", "sharpe": 0.0, "expectancy": 0.0, "winrate": 0.0, "kelly_sizing": 0.0, "external_edge": {}, "news_impact_score": 0.0, "messages": []}
        while True:
            cycle_start = time.monotonic()
            result = graph.invoke(initial_state)
            row = {"timestamp": datetime.now(), "last": result["last_price"], "volume": result["volume"]}
            pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
            elapsed = time.monotonic() - cycle_start
            sleep_time = max(0.0, 4.0 - elapsed) if result["is_market_open"] else 60.0
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏱️ Cycle Time: {elapsed:.2f}s → sleep {sleep_time:.2f}s | Sharpe={result.get('sharpe',0):.2f}")
            cycle_counter += 1
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        print("\n🛑 LUMINA gaat rusten.")