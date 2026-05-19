# PPO Evolution Real-Time Streaming

Live PPO training metrics flow from the birth/training loop to the Neural Command Deck birth phase UI.

## End-to-end flow

```
PPOTrainer.train()
  → PPOEvolutionLogger (every 5000 timesteps)
      → state/ppo_training_log.jsonl
      → ppo_realtime_tailer.broadcast_new_line()  [in-process]
  → watchdog file watcher on jsonl                  [cross-process backup]
      → ppo_realtime_tailer._process_new_lines()
  → WebSocket /ws/ppo-evolution
      → usePPOEvolution (Tauri birth phase)
      → PPOEvolutionPanel
```

## Backend components

| Component | Path |
|-----------|------|
| Training logger | `lumina_core/ppo_evolution_logger.py` |
| JSONL log | `state/ppo_training_log.jsonl` |
| Realtime tailer | `lumina_launcher/services/ppo_realtime.py` |
| WebSocket route | `lumina_os/backend/ppo_websocket.py` |
| App startup | `lumina_os/backend/app.py` — `start_watching()` in FastAPI lifespan |

## WebSocket protocol

**URL:** `ws://127.0.0.1:8000/ws/ppo-evolution` (or derive from `VITE_LUMINA_BACKEND_URL`)

**On connect:** server sends the last **40** JSONL lines as separate text messages (history).

**Live updates:** each new log line is pushed as one WebSocket text frame containing raw JSON (no wrapper object).

**Keep-alive:** client may send `ping`; server replies `pong`.

## JSONL line schema

Each line is a JSON object with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string (ISO-8601 UTC) | Log time |
| `step` | number | PPO timesteps |
| `mean_reward` | number | SB3 `rollout/ep_rew_mean` |
| `policy_loss` | number | SB3 `train/policy_loss` |
| `value_loss` | number | SB3 `train/value_loss` |
| `entropy` | number | SB3 `train/entropy` |
| `explained_variance` | number | SB3 `train/explained_variance` |
| `winrate_rolling_5k` | number | Rolling win rate (last 5k steps) |
| `sharpe_rolling_5k` | number | Rolling Sharpe (last 5k steps) |
| `action_distribution` | object | `{ long, short, hold }` normalized |
| `avg_stop_pct` | number | Mean stop % from actions |
| `avg_target_pct` | number | Mean target % from actions |

Example:

```json
{"timestamp":"2026-05-19T12:00:00+00:00","step":5000,"mean_reward":1.25,"policy_loss":0.04,"value_loss":0.11,"entropy":0.33,"explained_variance":0.72,"winrate_rolling_5k":0.58,"sharpe_rolling_5k":1.2,"action_distribution":{"long":0.6,"short":0.3,"hold":0.1},"avg_stop_pct":0.009,"avg_target_pct":0.018}
```

## Frontend (Tauri)

| File | Role |
|------|------|
| `tauri-app/src/lib/ppoEvolutionTypes.ts` | TypeScript metric type |
| `tauri-app/src/lib/ppoEvolutionClient.ts` | URL resolver + JSONL parser |
| `tauri-app/src/hooks/usePPOEvolution.ts` | WebSocket hook with reconnect |
| `tauri-app/src/components/birth/PPOEvolutionPanel.tsx` | Birth phase dashboard |

Set `VITE_LUMINA_BACKEND_URL=http://127.0.0.1:8000` in dev; the hook derives `ws://127.0.0.1:8000/ws/ppo-evolution`.

## Tests

```powershell
cd c:\NinjaTraderAI_Bot
python -m pytest lumina_os/tests/test_ppo_websocket.py tests/test_ppo_realtime_tailer.py tests/test_ppo_evolution_logger.py -q

cd tauri-app
npm run test
```

## Related

- [lumina-core-api-contracts.md](lumina-core-api-contracts.md) — core WebSocket contracts (`/ws/core/live`)
- Birth phase UI: `tauri-app/src/components/birth/BirthPhaseScreen.tsx`
