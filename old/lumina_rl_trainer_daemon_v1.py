import time
import pandas as pd
from sb3_contrib import RecurrentPPO
from datetime import datetime
print("🔄 lumina_rl_trainer_daemon_v1 gestart – continual PPO training (parallel)")

model = RecurrentPPO.load("ppo_trading_model_v26_lumina", device="cpu") if os.path.exists("ppo_trading_model_v26_lumina.zip") else None
while True:
    try:
        # Replay buffer lezen uit shared file (in prod via pickle of csv)
        if os.path.exists("shared_replay_buffer.csv"):
            df = pd.read_csv("shared_replay_buffer.csv")
            # Train in background
            model.learn(total_timesteps=256, reset_num_timesteps=False)
            model.save("ppo_trading_model_v26_lumina")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Trainer: 256 steps geleerd en model opgeslagen")
    except:
        pass
    time.sleep(30)  # traint elke 30s zonder Lumina te blokkeren