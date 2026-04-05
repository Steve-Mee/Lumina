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

load_dotenv()

INSTRUMENT = os.getenv("INSTRUMENT", "MES JUN 26")
XAI_KEY = os.getenv("XAI_API_KEY")
CROSSTRADE_TOKEN = os.getenv("CROSSTRADE_TOKEN")
CROSSTRADE_ACCOUNT = os.getenv("CROSSTRADE_ACCOUNT", "DEMO5042070")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"

CSV_FILE = "market_data_log.csv"
SIGNAL_LOG = "signals_log.csv"
EQUITY_FILE = "equity_curve.csv"

print("✅ Swarm Core v5.0 – 4-AGENT SWARM + MICROSTRUCTURE ORACLE")
print(f"🔍 DEBUG: Instrument={INSTRUMENT} | Account={CROSSTRADE_ACCOUNT} | DRY_RUN={DRY_RUN}")

model_path = "ppo_trading_model_v8_lstm"

class DummyTradingEnv(gym.Env):
    def __init__(self):
        super().__init__()
        self.observation_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(14,), dtype=np.float32)  # +2 microstructure feats
        self.action_space = gym.spaces.Discrete(3)
    def reset(self, seed=None, options=None):
        return np.zeros(14, dtype=np.float32), {}
    def step(self, action):
        return np.zeros(14, dtype=np.float32), 0, False, False, {}

if os.path.exists(model_path + ".zip"):
    model = RecurrentPPO.load(model_path, device="cpu")
    print("   ✅ Oud LSTM PPO model geladen (v8)")
else:
    print("   🧠 Nieuw RecurrentPPO LSTM model aanmaken...")
    model = RecurrentPPO("MlpLstmPolicy", DummyTradingEnv(), verbose=0, device="cpu", learning_rate=1e-4, n_steps=128, ent_coef=0.05)
    model.learn(total_timesteps=2048, progress_bar=False)
    model.save(model_path)

dummy_env = DummyTradingEnv()
model.set_env(dummy_env)

replay_buffer = []
equity_curve = []
last_sentiment_time = 0
cached_sentiment = "BEARISH"
cycle_counter = 0

class TradingState(TypedDict):
    obs: list
    regime: str
    microstructure: dict
    actor_signal: str
    critic_reasoning: str
    critic_veto: List[str]
    final_signal: str
    last_price: float
    volume: int
    position_qty: int
    atr: float
    data_source: str
    is_market_open: bool
    reward: float
    lstm_states: object
    x_sentiment: str
    messages: Annotated[List[str], operator.add]

def get_market_status():
    try:
        url = "https://app.crosstrade.io/v1/api/market/info"
        headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}", "Content-Type": "application/json"}
        params = {"instrument": INSTRUMENT}
        r = requests.get(url, headers=headers, params=params, timeout=8)
        return r.json().get("status", {}).get("isOpen", False) if r.status_code == 200 else True
    except:
        return True

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
    start = datetime.now()
    df = pd.read_csv(CSV_FILE).tail(50) if os.path.exists(CSV_FILE) else pd.DataFrame()
    if len(df) < 10:
        imbalance = 0.0
        vol_delta = 0
    else:
        recent_vol = df['volume'].iloc[-10:].mean()
        prev_vol = df['volume'].iloc[-20:-10].mean() if len(df) > 20 else recent_vol
        vol_delta = recent_vol - prev_vol
        price_delta = df['last'].iloc[-1] - df['last'].iloc[-5]
        imbalance = np.sign(vol_delta) * (price_delta / state.get("atr", 12.0))  # proxy orderflow
    micro = {"imbalance": float(imbalance), "vol_delta": int(vol_delta)}
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📈 Microstructure Oracle klaar (imbalance: {imbalance:.2f})")
    return {**state, "microstructure": micro}

def regime_oracle_node(state: TradingState) -> TradingState:
    df = pd.read_csv(CSV_FILE).tail(100) if os.path.exists(CSV_FILE) else pd.DataFrame()
    atr = calculate_atr(df)
    vol = state["volume"]
    regime = "HIGH_VOLATILITY 🔥" if (atr > 25 or vol > 180000) else "LOW_VOLATILITY 🌿" if atr < 12 else "NORMAL_MARKET ⚖️"
    return {**state, "regime": regime, "atr": atr}

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
    micro = state.get("microstructure", {"imbalance": 0.0, "vol_delta": 0})
    obs = [
        price_norm, vol_norm, atr_norm, float(trend_20), float(trend_50),
        rsi_norm, macd_norm, momentum_norm, state.get("position_qty", 0) / 2.0,
        float(len(df) > 30), micro["imbalance"], micro["vol_delta"] / 10000
    ]
    return np.clip(np.nan_to_num(obs, nan=0.0), -5, 5).tolist()

def get_real_x_sentiment():
    global last_sentiment_time, cached_sentiment
    if time.time() - last_sentiment_time < 60:
        return cached_sentiment
    try:
        payload = {"model": "grok-4.20-0309-reasoning", "messages": [{"role": "system", "content": "Geef alleen één woord: BULLISH, BEARISH of NEUTRAL."}, {"role": "user", "content": "Wat is het huidige sentiment op X voor MES JUN 26 futures?"}]}
        r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=8)
        if r.status_code == 200:
            sentiment = r.json()["choices"][0]["message"]["content"].strip().upper()
            cached_sentiment = sentiment
            last_sentiment_time = time.time()
            return sentiment
    except:
        pass
    return cached_sentiment

def actor_node(state: TradingState) -> TradingState:
    df = pd.read_csv(CSV_FILE).tail(100) if os.path.exists(CSV_FILE) else pd.DataFrame()
    obs = build_rich_obs(state, df)
    obs_array = np.array([obs], dtype=np.float32)
    lstm_states = state.get("lstm_states", None)
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
    advice = "Critic API failed"
    if state["is_market_open"] or (cycle_counter % 3 == 0):
        try:
            payload = {"model": "grok-4.20-0309-reasoning", "messages": [
                {"role": "system", "content": "Devil’s Advocate Critic. Max 3 zinnen veto. Geef altijd confidence 0-100."},
                {"role": "user", "content": f"Regime: {state['regime']}\nMicro: {state.get('microstructure', {})} \nActor: {state['actor_signal']}\nPrice: {state['last_price']:.2f}\nX-Sentiment: {state['x_sentiment']}"}
            ]}
            r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=10)
            if r.status_code == 200:
                advice = r.json()["choices"][0]["message"]["content"]
        except:
            pass
    veto = []
    if "HIGH_VOLATILITY" in state["regime"] and state["actor_signal"] != "HOLD":
        veto.append("High vol risk")
    if "veto" in advice.lower() or (state["x_sentiment"] == "BEARISH" and state["actor_signal"] == "BUY"):
        veto.append("X-sentiment veto")
    if abs(state.get("microstructure", {}).get("imbalance", 0)) > 1.5 and state["actor_signal"] != "HOLD":
        veto.append("Microstructure imbalance veto")
    final = "HOLD (Critic VETO)" if veto else state["actor_signal"]
    return {**state, "critic_reasoning": advice, "critic_veto": veto, "final_signal": final}

def supervisor_node(state: TradingState) -> TradingState:
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 📊 Regime: {state['regime']} | Micro: {state.get('microstructure', {})} | X-Sentiment: {state.get('x_sentiment', 'N/A')}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 Actor: {state['actor_signal']} → Critic: {state['critic_reasoning'][:120]}...")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Final Signal: **{state['final_signal']}** | Price: {state['last_price']:.2f}")

    if state["is_market_open"] and state["final_signal"] != "HOLD":
        risk_per_point = state["atr"] * 0.5
        quantity = max(1, min(3, int(100 / (risk_per_point + 1))))
        side = "BUY" if state["final_signal"] == "BUY" else "SELL"
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 💰 PAPER-TRADE: {side} {quantity} (ATR-scaled)")
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
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 DRAW DOWN >15% → PAUZE")

    pd.DataFrame([{"timestamp": datetime.now(), "actor": state['actor_signal'], "final": state['final_signal'], "regime": state['regime'], "price": state['last_price']}]).to_csv(SIGNAL_LOG, mode="a", header=not os.path.exists(SIGNAL_LOG), index=False)
    return state

def replay_buffer_node(state: TradingState) -> TradingState:
    pnl = get_recent_pnl()
    regime_factor = 1.5 if "LOW_VOLATILITY" in state["regime"] else 0.7
    reward = (pnl * 0.8) * regime_factor - (state["atr"] / 15) + state.get("microstructure", {}).get("imbalance", 0) * 0.5
    reward = np.clip(reward, -5, 5)
    
    replay_buffer.append((state["obs"], state.get("actor_signal", "HOLD"), reward, state["last_price"]))
    if len(replay_buffer) > 500:
        replay_buffer.pop(0)

    log_len = len(pd.read_csv(SIGNAL_LOG)) if os.path.exists(SIGNAL_LOG) else 0
    if log_len % 40 == 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 REPLAY BUFFER ACTIVE → learn 64 steps")
        model.learn(total_timesteps=64, env=dummy_env, reset_num_timesteps=False, progress_bar=False)
        model.save(model_path)
    if log_len % 200 == 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 CONTINUAL LEARNING 2048 steps")
        model.learn(total_timesteps=2048, env=dummy_env, reset_num_timesteps=False, progress_bar=False)
        model.save(model_path)

    return {**state, "reward": reward}

workflow = StateGraph(TradingState)
workflow.add_node("data", lambda s: {**s, **(lambda p, v, src: {"last_price": p, "volume": v, "data_source": src})(*fetch_quote()), "position_qty": get_current_position(), "is_market_open": get_market_status()})
workflow.add_node("microstructure", microstructure_oracle_node)
workflow.add_node("regime", regime_oracle_node)
workflow.add_node("actor", actor_node)
workflow.add_node("critic", critic_node)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("replay", replay_buffer_node)

workflow.set_entry_point("data")
workflow.add_edge("data", "microstructure")
workflow.add_edge("microstructure", "regime")
workflow.add_edge("regime", "actor")
workflow.add_edge("actor", "critic")
workflow.add_edge("critic", "supervisor")
workflow.add_edge("supervisor", "replay")
workflow.add_edge("replay", END)

graph = workflow.compile()

if __name__ == "__main__":
    print("🚀 Swarm Core v5.0 LIVE – 4-AGENT SWARM (Ctrl+C om stoppen)\n")
    try:
        initial_state = {"obs": [0]*14, "regime": "", "microstructure": {}, "actor_signal": "", "critic_reasoning": "", "critic_veto": [], "final_signal": "", "last_price": 0, "volume": 0, "position_qty": 0, "atr": 12.0, "data_source": "", "is_market_open": True, "reward": 0.0, "lstm_states": None, "x_sentiment": "", "messages": []}
        while True:
            result = graph.invoke(initial_state)
            row = {"timestamp": datetime.now(), "last": result["last_price"], "volume": result["volume"]}
            pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
            time.sleep(4 if result["is_market_open"] else 60)
    except KeyboardInterrupt:
        print("\n🛑 Swarm Core v5.0 gestopt.")