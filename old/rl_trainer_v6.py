import os
import pandas as pd
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from datetime import datetime

CSV_FILE = "market_data_log.csv"

class TradingEnv(gym.Env):
    """Custom Gym omgeving – dit is de 'wereld' waarin de RL-agent traint"""
    def __init__(self, df):
        super().__init__()
        self.df = df.reset_index(drop=True)
        self.current_step = 0
        self.balance = 10000  # startkapitaal simulatie
        self.position = 0     # 1 = long, -1 = short, 0 = flat
        
        # Observatie: prijs, volume, ATR, regime, trend
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(5,), dtype=np.float32)
        self.action_space = spaces.Discrete(3)  # 0=HOLD, 1=BUY, 2=SELL

    def reset(self, seed=None):
        self.current_step = 20  # start na genoeg data
        self.balance = 10000
        self.position = 0
        return self._get_obs(), {}

    def _get_obs(self):
        row = self.df.iloc[self.current_step]
        price = row['last']
        volume = row['volume']
        # Simpele ATR & regime uit vorige code
        atr = abs(price - self.df['last'].iloc[self.current_step-1]) * 100 / price
        trend = 1 if price > self.df['last'].iloc[self.current_step-10:self.current_step].mean() else -1
        obs = np.array([price/1000, volume/100000, atr, trend, self.position], dtype=np.float32)
        return obs

    def step(self, action):
        row = self.df.iloc[self.current_step]
        price = row['last']
        reward = 0
        
        # Actie uitvoeren
        if action == 1 and self.position == 0:      # BUY
            self.position = 1
        elif action == 2 and self.position == 0:   # SELL
            self.position = -1
        elif action == 0:                          # HOLD
            pass
        
        # Simuleer P&L (1 contract)
        if self.position != 0:
            next_price = self.df.iloc[self.current_step + 1]['last'] if self.current_step + 1 < len(self.df) else price
            pnl = (next_price - price) * self.position * 5  # Micro E-mini multiplier = $5 per punt
            self.balance += pnl
            reward = pnl - 0.5  # kleine kosten penalty
        
        self.current_step += 1
        done = self.current_step >= len(self.df) - 1
        
        return self._get_obs(), reward, done, False, {}

# === V6 RL TRAINER ===
if __name__ == "__main__":
    print("🚀 RL Trainer v6 – Echte PPO Brain (Self-Improving!)")
    print("Laad data en train de agent...\n")
    
    df = pd.read_csv(CSV_FILE)
    env = TradingEnv(df)
    vec_env = make_vec_env(lambda: env, n_envs=1)
    
    model = PPO("MlpPolicy", vec_env, verbose=1, learning_rate=0.001, n_steps=128)
    
    print("Training start (1000 timesteps – duurt ~10-20 seconden)...")
    model.learn(total_timesteps=1000)
    
    # Save model voor later gebruik
    model.save("ppo_trading_model_v6")
    print("✅ Training klaar! Model opgeslagen als ppo_trading_model_v6.zip")
    print("Volgende stap: we integreren dit model in de data collector om LIVE signals te geven!")