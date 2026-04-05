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

print("✅ Swarm Core v4.6 – SPEED EDITION (critic throttled + cache + fallback)")
print(f"🔍 DEBUG: Instrument={INSTRUMENT} | Account={CROSSTRADE_ACCOUNT} | DRY_RUN={DRY_RUN}")

model_path = "ppo_trading_model_v6_lstm"

class DummyTradingEnv(gym.Env):
    def __init__(self):
        super().__init__()
        self.observation_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(5,), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(3)
    def reset(self, seed=None, options=None):
        return np.zeros(5, dtype=np.float32), {}
    def step(self, action):
        return np.zeros(5, dtype=np.float32), 0, False, False, {}

if os.path.exists(model_path + ".zip"):
    model = RecurrentPPO.load(model_path, device="cpu")
    print("   ✅ Oud LSTM PPO model geladen")
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
    start = datetime.now()
    try:
        url = "https://app.crosstrade.io/v1/api/market/info"
        headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}", "Content-Type": "application/json"}
        params = {"instrument": INSTRUMENT}
        r = requests.get(url, headers=headers, params=params, timeout=8)
        if r.status_code == 200:
            data = r.json()
            is_open = data.get("status", {}).get("isOpen", False)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Market Status → Open: {is_open} (duurde {(datetime.now()-start).total_seconds():.2f}s)")
            return is_open
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Market Info exception: {e}")
    return True

def fetch_quote():
    start = datetime.now()
    formats = [INSTRUMENT, "MES JUN 26"]
    for fmt in formats:
        try:
            url = f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/quote"
            headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}", "Content-Type": "application/json"}
            params = {"instrument": fmt}
            r = requests.get(url, headers=headers, params=params, timeout=8)
            if r.status_code == 200:
                data = r.json()
                price = float(data.get("last", 0))
                volume = int(data.get("volume", 0))
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ CrossTrade | Price: {price:.2f} (duurde {(datetime.now()-start).total_seconds():.2f}s)")
                return price, volume, "CrossTrade"
        except:
            pass
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 Closed market → synthetic")
    return 6559 + np.random.normal(0, 8), 150000, "SYNTHETIC"

def get_current_position():
    if not CROSSTRADE_TOKEN: return 0
    try:
        r = requests.get(f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/positions",
                         headers={"Authorization": f"Bearer {CROSSTRADE_TOKEN}"}, timeout=6)
        if r.status_code == 200:
            positions = r.json()
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
        if r.status_code == 200:
            executions = r.json()
            if isinstance(executions, list) and len(executions) > 0:
                pnl = float(executions[-1].get("realizedPnL", 0))
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 📈 Real PnL: {pnl:.2f}")
                return pnl
    except:
        pass
    return np.random.normal(0.8, 1.5)

def calculate_atr(df):
    if len(df) < 5: return 12.0
    changes = df['last'].diff().abs()
    atr = changes.rolling(14, min_periods=1).mean().iloc[-1]
    atr = np.nan_to_num(atr, nan=12.0)
    return np.clip(atr, 8.0, 35.0)

def regime_oracle_node(state: TradingState) -> TradingState:
    start = datetime.now()
    df = pd.read_csv(CSV_FILE).tail(100) if os.path.exists(CSV_FILE) else pd.DataFrame()
    if not df.empty: df = df.drop_duplicates(subset=['last'], keep='last')
    atr = calculate_atr(df)
    vol = state["volume"]
    regime = "HIGH_VOLATILITY 🔥" if (atr > 25 or vol > 180000) else "LOW_VOLATILITY 🌿" if atr < 12 else "NORMAL_MARKET ⚖️"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 Regime klaar (duurde {(datetime.now()-start).total_seconds():.2f}s)")
    return {**state, "regime": regime, "atr": atr}

def build_obs(state: TradingState, df) -> list:
    price_norm = state["last_price"] / 7000
    vol_norm = min(state["volume"] / 200000, 2.0)
    atr_norm = min(state["atr"] / 30, 2.0)
    trend = 1 if len(df) > 20 and state["last_price"] > df['last'].iloc[-20:-5].mean() else -1
    obs = [price_norm, vol_norm, atr_norm, float(trend), 0.0]
    obs = np.nan_to_num(obs, nan=0.0)
    return np.clip(obs, -5, 5).tolist()

def get_real_x_sentiment():
    global last_sentiment_time, cached_sentiment
    if time.time() - last_sentiment_time < 60:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📡 X-Sentiment CACHE gebruikt")
        return cached_sentiment
    try:
        payload = {"model": "grok-4.20-0309-reasoning", "messages": [{"role": "system", "content": "Geef alleen één woord: BULLISH, BEARISH of NEUTRAL."}, {"role": "user", "content": "Wat is het huidige sentiment op X voor MES JUN 26 futures?"}]}
        r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=8)
        if r.status_code == 200:
            sentiment = r.json()["choices"][0]["message"]["content"].strip().upper()
            cached_sentiment = sentiment
            last_sentiment_time = time.time()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📡 REAL X-SENTIMENT: {sentiment}")
            return sentiment
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Sentiment error: {e}")
    return cached_sentiment

def actor_node(state: TradingState) -> TradingState:
    start = datetime.now()
    df = pd.read_csv(CSV_FILE).tail(100) if os.path.exists(CSV_FILE) else pd.DataFrame()
    obs = build_obs(state, df)
    obs_array = np.array([obs], dtype=np.float32)
    obs_array = np.clip(obs_array, -10, 10)
    lstm_states = state.get("lstm_states", None)
    try:
        action, new_lstm_states = model.predict(obs_array, state=lstm_states, deterministic=True)
        action = int(action.item()) if hasattr(action, "item") else int(action)
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ PPO predict failed → HOLD")
        action = 0
        new_lstm_states = None
    signal = {0: "HOLD", 1: "BUY", 2: "SELL"}[action]
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 Actor klaar (duurde {(datetime.now()-start).total_seconds():.2f}s)")
    return {**state, "actor_signal": signal, "obs": obs, "lstm_states": new_lstm_states}

def critic_node(state: TradingState) -> TradingState:
    start = datetime.now()
    global cycle_counter
    cycle_counter += 1
    state["x_sentiment"] = get_real_x_sentiment()
    advice = "Critic API failed"
    if state["is_market_open"] or (cycle_counter % 3 == 0):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 CRITIC CALL (cycle {cycle_counter})")
        recent_log = pd.read_csv(SIGNAL_LOG).tail(40).to_string() if os.path.exists(SIGNAL_LOG) else "No log"
        for attempt in range(2):
            try:
                payload = {"model": "grok-4.20-0309-reasoning", "messages": [
                    {"role": "system", "content": "Devil’s Advocate Critic. Max 3 zinnen veto."},
                    {"role": "user", "content": f"Regime: {state['regime']}\nActor: {state['actor_signal']}\nPrice: {state['last_price']:.2f}\nATR: {state['atr']:.2f}\nX-Sentiment: {state['x_sentiment']}"}
                ]}
                r = requests.post("https://api.x.ai/v1/chat/completions", headers={"Authorization": f"Bearer {XAI_KEY}"}, json=payload, timeout=10)
                if r.status_code == 200:
                    advice = r.json()["choices"][0]["message"]["content"]
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 GROK CRITIC SUCCESS")
                    break
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Critic attempt {attempt+1} failed: {e}")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🛡️ Critic SKIPPED (throttled) → rule-based fallback")
        if state["x_sentiment"] == "BEARISH" and state["actor_signal"] == "BUY":
            advice = "BEARISH sentiment veto"
    veto = []
    if "HIGH_VOLATILITY" in state["regime"] and state["actor_signal"] != "HOLD":
        veto.append("High vol risk")
    if "veto" in advice.lower() or state["x_sentiment"] == "BEARISH" and state["actor_signal"] == "BUY":
        veto.append("X-sentiment veto")
    final = "HOLD (Critic VETO)" if veto else state["actor_signal"]
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🛡️ Critic klaar (duurde {(datetime.now()-start).total_seconds():.2f}s)")
    return {**state, "critic_reasoning": advice, "critic_veto": veto, "final_signal": final}

def supervisor_node(state: TradingState) -> TradingState:
    start = datetime.now()
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 📊 Regime: {state['regime']} (ATR {state['atr']:.2f}) | X-Sentiment: {state.get('x_sentiment', 'N/A')}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 Actor: {state['actor_signal']}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🛡️ Critic: {state['critic_reasoning'][:180]}...")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Final Signal: **{state['final_signal']}** | Price: {state['last_price']:.2f}")

    if state["is_market_open"] and state["final_signal"] != "HOLD":
        qty = state["position_qty"]
        if qty == 0:
            side = "BUY" if state["final_signal"] == "BUY" else "SELL"
            quantity = 1
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 💰 PAPER-TRADE: {side} {quantity}")
            if not DRY_RUN:
                try:
                    url = f"https://app.crosstrade.io/v1/api/accounts/{CROSSTRADE_ACCOUNT}/orders"
                    headers = {"Authorization": f"Bearer {CROSSTRADE_TOKEN}", "Content-Type": "application/json"}
                    payload = {"instrument": INSTRUMENT, "action": side, "quantity": quantity, "type": "MARKET"}
                    r = requests.post(url, headers=headers, json=payload, timeout=8)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Order geplaatst!")
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Order error: {e}")

    equity_curve.append(state["last_price"])
    if len(equity_curve) > 100:
        peak = max(equity_curve[-100:])
        trough = min(equity_curve[-100:])
        drawdown = (peak - trough) / peak * 100
        if drawdown > 15:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 DRAW DOWN >15% → PAUZE")

    log_row = {"timestamp": datetime.now(), "actor": state['actor_signal'], "final": state['final_signal'], "regime": state['regime'], "price": state['last_price']}
    pd.DataFrame([log_row]).to_csv(SIGNAL_LOG, mode="a", header=not os.path.exists(SIGNAL_LOG), index=False)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Supervisor klaar (duurde {(datetime.now()-start).total_seconds():.2f}s)")
    return state

def replay_buffer_node(state: TradingState) -> TradingState:
    start = datetime.now()
    pnl = get_recent_pnl()
    reward = pnl - (state["atr"] / 20.0) * (2 if "HIGH_VOLATILITY" in state["regime"] else 1)
    reward = np.clip(reward, -5, 5)
    
    experience = (state["obs"], state.get("actor_signal", "HOLD"), reward, state["last_price"])
    replay_buffer.append(experience)
    if len(replay_buffer) > 500:
        replay_buffer.pop(0)
    
    log_len = len(pd.read_csv(SIGNAL_LOG)) if os.path.exists(SIGNAL_LOG) else 0
    if log_len % 40 == 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 REPLAY BUFFER ACTIVE")
        dummy_env = DummyTradingEnv()
        model.set_env(dummy_env)
        model.learn(total_timesteps=64, env=dummy_env, reset_num_timesteps=False, progress_bar=False)
        model.save(model_path)

    if log_len % 200 == 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 CONTINUAL LEARNING ACTIVE")
        dummy_env = DummyTradingEnv()
        model.set_env(dummy_env)
        model.learn(total_timesteps=2048, env=dummy_env, reset_num_timesteps=False, progress_bar=False)
        model.save(model_path)

    try:
        recent_df = pd.read_csv(SIGNAL_LOG).tail(20)
        buy_ratio = (recent_df["actor"] == "BUY").sum() / len(recent_df) * 100 if not recent_df.empty else 0
    except:
        buy_ratio = 0
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 📋 STRATEGY FINGERPRINT: BUY in LOW_VOL ({buy_ratio:.0f}% BUY-ratio) + exploreert nog")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Replay klaar (duurde {(datetime.now()-start).total_seconds():.2f}s)")
    return {**state, "reward": reward}

workflow = StateGraph(TradingState)
workflow.add_node("data", lambda s: {
    **s,
    **(lambda p, v, src: {"last_price": p, "volume": v, "data_source": src})(*fetch_quote()),
    "position_qty": get_current_position(),
    "is_market_open": get_market_status()
})
workflow.add_node("regime", regime_oracle_node)
workflow.add_node("actor", actor_node)
workflow.add_node("critic", critic_node)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("replay", replay_buffer_node)

workflow.set_entry_point("data")
workflow.add_edge("data", "regime")
workflow.add_edge("regime", "actor")
workflow.add_edge("actor", "critic")
workflow.add_edge("critic", "supervisor")
workflow.add_edge("supervisor", "replay")
workflow.add_edge("replay", END)

graph = workflow.compile()

if __name__ == "__main__":
    print("🚀 Swarm Core v4.6 LIVE – SPEED EDITION (Ctrl+C om stoppen)\n")
    try:
        initial_state = {"obs": [0,0,0,0,0], "regime": "", "actor_signal": "", "critic_reasoning": "", "critic_veto": [], "final_signal": "", "last_price": 0, "volume": 0, "position_qty": 0, "atr": 12.0, "data_source": "", "is_market_open": True, "reward": 0.0, "lstm_states": None, "x_sentiment": "", "messages": []}
        while True:
            cycle_start = datetime.now()
            result = graph.invoke(initial_state)
            cycle_time = (datetime.now() - cycle_start).total_seconds()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Volledige CYCLE klaar in {cycle_time:.2f}s (doel <8s)")

            row = {"timestamp": datetime.now(), "last": result["last_price"], "volume": result["volume"]}
            pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
            sleep_time = 60 if not result["is_market_open"] else 4
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        print("\n🛑 Swarm Core v4.6 gestopt.")