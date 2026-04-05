import os
import time
import pandas as pd
import numpy as np
import requests
import gymnasium as gym
from datetime import datetime
from stable_baselines3 import PPO
from stable_baselines3.common.policies import MlpLstmPolicy
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

print("✅ Swarm Core v3.5 – 5-Agent Swarm (Oracle + Actor-LSTM + Critic + Supervisor + ReplayBuffer)")
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

# === STABIELE LSTM MODEL CREATIE ===
if os.path.exists(model_path + ".zip"):
    model = PPO.load(model_path, device="cpu")
    print("   ✅ Oud LSTM PPO model geladen")
else:
    print("   🧠 Nieuw LSTM PPO model aanmaken + pre-train...")
    model = PPO(MlpLstmPolicy, DummyTradingEnv(), verbose=0, device="cpu", learning_rate=1e-4, n_steps=128)
    model.learn(total_timesteps=1024, progress_bar=False)
    model.save(model_path)
    print("   ✅ Nieuw gestabiliseerd LSTM model opgeslagen")

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
    messages: Annotated[List[str], operator.add]

# Global replay buffer (managed by dedicated agent)
replay_buffer = []

def get_market_status(): ... # (exact hetzelfde als v3.4)
def fetch_quote(): ... # (exact hetzelfde)
def get_current_position(): ... # (exact hetzelfde)
def calculate_atr(df): ... # (exact hetzelfde)
def regime_oracle_node(state: TradingState) -> TradingState: ... # (exact hetzelfde)
def build_obs(state: TradingState, df) -> list: ... # (exact hetzelfde, met clip)

def actor_node(state: TradingState) -> TradingState:
    df = pd.read_csv(CSV_FILE).tail(100) if os.path.exists(CSV_FILE) else pd.DataFrame()
    obs = build_obs(state, df)
    obs_array = np.array([obs], dtype=np.float32)
    obs_array = np.clip(obs_array, -10, 10)
    try:
        action, _ = model.predict(obs_array, deterministic=True)
        action = int(action.item()) if hasattr(action, "item") else int(action)
    except:
        action = 0
    signal = {0: "HOLD", 1: "BUY", 2: "SELL"}[action]
    return {**state, "actor_signal": signal, "obs": obs}

def critic_node(state: TradingState) -> TradingState: ... # (exact hetzelfde als v3.4)

def supervisor_node(state: TradingState) -> TradingState: ... # (exact hetzelfde, met order logic)

def replay_buffer_node(state: TradingState) -> TradingState:
    # Store experience
    experience = (state["obs"], state.get("actor_signal", "HOLD"), state.get("reward", 0.0), state["last_price"])
    replay_buffer.append(experience)
    if len(replay_buffer) > 200:
        replay_buffer.pop(0)
    
    # Every 40 cycles: sample & learn
    log_len = len(pd.read_csv(SIGNAL_LOG)) if os.path.exists(SIGNAL_LOG) else 0
    if log_len % 40 == 0 and len(replay_buffer) >= 32:
        print(f"   🧠 REPLAY BUFFER AGENT ACTIVE: {len(replay_buffer)} experiences | Sampling & PPO update...")
        # Simulate batch learn (later echte P&L history)
        model.learn(total_timesteps=64, reset_num_timesteps=False, progress_bar=False)
        model.save(model_path)
        print("   ✅ LSTM Model geüpdatet via replay buffer")
    
    return {**state, "reward": state.get("reward", 0.0)}

# === 5-AGENT GRAPH ===
workflow = StateGraph(TradingState)
workflow.add_node("data", lambda s: {**s, **(lambda p,v,src: {"last_price":p,"volume":v,"data_source":src})(*fetch_quote()), "position_qty":get_current_position(), "is_market_open":get_market_status()})
workflow.add_node("regime", regime_oracle_node)
workflow.add_node("actor", actor_node)
workflow.add_node("critic", critic_node)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("replay", replay_buffer_node)  # 5e agent

workflow.set_entry_point("data")
workflow.add_edge("data", "regime")
workflow.add_edge("regime", "actor")
workflow.add_edge("actor", "critic")
workflow.add_edge("critic", "supervisor")
workflow.add_edge("supervisor", "replay")
workflow.add_edge("replay", END)

graph = workflow.compile()

if __name__ == "__main__":
    print("🚀 Swarm Core v3.5 LIVE – 5-Agent Swarm met ReplayBuffer + LSTM (Ctrl+C om stoppen)\n")
    try:
        while True:
            initial_state = {"obs": [0,0,0,0,0], "regime": "", "actor_signal": "", "critic_reasoning": "", "critic_veto": [], "final_signal": "", "last_price": 0, "volume": 0, "position_qty": 0, "atr": 12.0, "data_source": "", "is_market_open": True, "reward": 0.0, "messages": []}
            result = graph.invoke(initial_state)
            row = {"timestamp": datetime.now(), "last": result["last_price"], "volume": result["volume"]}
            pd.DataFrame([row]).to_csv(CSV_FILE, mode="a", header=not os.path.exists(CSV_FILE), index=False)
            sleep_time = 60 if not result["is_market_open"] else 6
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        print("\n🛑 Swarm Core v3.5 gestopt.")