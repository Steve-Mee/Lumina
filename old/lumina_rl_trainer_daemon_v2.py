import time
import pandas as pd
from sb3_contrib import RecurrentPPO
from datetime import datetime
import os
print("🔄 lumina_rl_trainer_daemon_v2 gestart – continual PPO (nu echte shared csv)")
model = RecurrentPPO.load("ppo_trading_model_v26_lumina", device="cpu") if os.path.exists("ppo_trading_model_v26_lumina.zip") else None
while True:
    try:
        if os.path.exists("shared_replay_buffer.csv"):
            df = pd.read_csv("shared_replay_buffer.csv")
            model.learn(total_timesteps=512, reset_num_timesteps=False)
            model.save("ppo_trading_model_v26_lumina")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Trainer v2: 512 steps geleerd")
    except:
        pass
    time.sleep(45)