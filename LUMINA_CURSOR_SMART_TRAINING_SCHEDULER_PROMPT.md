# LUMINA — Cursor Prompt: Smart Automatic Training Scheduler

**Doel:** Implementeer een volledig automatische training scheduler die **geen enkele menselijke tussenkomst** vereist. De training moet automatisch starten en stoppen binnen de juiste tijdswindows (markturen, dagelijkse onderhoudsstop, weekend).

---

## Cursor Prompt (kopieer dit volledig)

```
You are building a fully automatic Smart Training Scheduler for Lumina. The goal is zero human intervention — training must start, run, pause, and stop automatically based on time windows.

### Core Requirements:

1. **New configuration section** (add to config.yaml)
   ```yaml
   training:
     enabled: true
     intensity: balanced          # light | balanced | aggressive

     schedule:
       background:
         enabled: true
         max_trades_per_hour: 150000
         cpu_priority: low        # low | normal | high

       daily_maintenance:
         enabled: true
         window_start: "17:00"    # ET time (MES maintenance window)
         window_end: "18:00"
         max_trades: 500000

       weekend:
         enabled: true
         start_day: "friday"
         start_time: "18:00"
         end_day: "sunday"
         end_time: "20:00"
         max_trades: 1500000
   ```

2. **Fully automatic scheduler**
   - Create a new file: `lumina_core/training_scheduler.py`
   - The scheduler must start automatically when Lumina boots (background thread or daemon).
   - It must continuously check the current time and decide which training mode to run:
     - **Background mode**: During normal market hours (low priority, limited trades/hour)
     - **Daily maintenance mode**: During the ~1h window (higher intensity)
     - **Weekend mode**: Very heavy training (Friday evening → Sunday evening)

3. **Time window respect (critical)**
   - The scheduler must **exactly respect** the configured time windows.
   - It must start training automatically at the beginning of a window.
   - It must **gracefully stop or pause** training when the window ends (even mid-training).
   - Support clean pause/resume functionality in InfiniteSimulator.
   - If training overruns the window, it must pause cleanly and resume in the next available window.

4. **Training intensity logic**
   - `light`: ~150k trades/hour in background + 300k during maintenance
   - `balanced`: ~200k trades/hour + 500k during maintenance + 1.2M in weekend
   - `aggressive`: maximum allowed within each window

5. **Integration with InfiniteSimulator**
   - Extend `InfiniteSimulator` with:
     - `run_training(target_trades: int, priority: str, stop_event=None)`
     - Support for pause/resume via threading.Event or similar
     - Ability to save progress mid-training (checkpointing)
   - The scheduler decides the `target_trades` based on remaining time in the current window.

6. **No human intervention**
   - Everything must be automatic.
   - On first boot: run first-boot training (from previous prompt) and then hand over to the scheduler.
   - The scheduler must survive restarts (save state: last training timestamp, progress, current mode).

7. **Logging & status**
   - Log clearly:
     - When each training window starts and stops
     - Current mode + remaining time in window
     - Trades completed in current session
     - Real vs synthetic data ratio
   - Expose current scheduler status so the Monitoring Dashboard can display it.

8. **Fail-safe & robustness**
   - If the market maintenance window is missed, the scheduler should still run background training.
   - Handle edge cases (daylight saving time, unexpected downtime, etc.).
   - Never block the main trading loop.

### Output instructions:
- First show the new config section.
- Then provide the complete code for `lumina_core/training_scheduler.py`.
- Show the necessary modifications to `lumina_core/infinite_simulator.py` (pause/resume + checkpointing).
- Show how to start the scheduler automatically from `runtime_entrypoint.py` or `lumina_launcher.py`.
- Add clear comments everywhere new logic is added.
```

---

## Extra aanbeveling (niet in prompt)

Omdat MES bijna 24u per dag open is met slechts een korte dagelijkse stop, raad ik aan om:

- **Background training** de hele dag op lage intensiteit te laten draaien (niet alleen ’s nachts).
- De **zwaardere training** vooral te concentreren in het weekend + de dagelijkse onderhoudsstop.
- Dit geeft de beste balans tussen continue verbetering en respect voor de tijdswindows.

---

**Klaar.**  
Je kunt deze prompt nu direct in Cursor plakken. 

Wil je daarna dat ik een **gecombineerde prompt** maak die zowel de First Boot Training + Smart Scheduler + Monitoring Dashboard in één keer aanpakt? Of wil je eerst één van de drie implementeren?