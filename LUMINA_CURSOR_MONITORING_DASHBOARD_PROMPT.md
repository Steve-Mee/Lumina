# LUMINA — Cursor Prompt: Monitoring Dashboard

**Doel:** Bouw een professioneel, overzichtelijk Monitoring Dashboard zodat we Lumina volledig kunnen volgen, debuggen en verbeteren.

---

## Cursor Prompt (kopieer dit volledig)

```
You are building a professional Monitoring Dashboard for Lumina.

Your task is to create a clean, real-time dashboard (preferably in Streamlit to match the existing launcher) that gives full visibility into the system's behavior.

### Requirements:

1. **File location**
   Create: `lumina_os/frontend/monitoring_dashboard.py`
   (or integrate it into the existing launcher if that makes more sense)

2. **Main sections (must include)**

   **A. System Overview**
   - Current mode (SIM / PAPER / REAL)
   - First boot completed? + timestamp
   - Current training mode (Background / Daily Maintenance / Weekend)
   - Last training run: date, duration, trades completed, real vs synthetic %
   - PPO Policy version + total training steps
   - ApprovalTwin last update + avg error + reward

   **B. First Boot Training Status**
   - If first boot training is running: progress bar + current status
   - Historical days loaded
   - Real vs synthetic percentage
   - Final result after completion (trades, policy improvement)

   **C. Training History**
   - Table or cards showing the last 10 training runs:
     - Date & time window (Background / Maintenance / Weekend)
     - Trades executed
     - Real data ratio
     - Duration
     - Key metrics (Sharpe improvement, new Bible rules, etc.)

   **D. ApprovalTwin Activity**
   - Last 15-20 decisions made by the twin:
     - DNA hash (short)
     - Score
     - Recommendation (Approve / Veto)
     - Risk flags
     - Timestamp
   - Weekly veto count + top reasons

   **E. Shadow Deployment**
   - Currently active shadow runs with status
   - Recently promoted strategies with key metrics (Sharpe, PnL, statistical significance)

   **F. Live Trading Metrics** (when in runtime mode)
   - Current exposure, daily PnL, consecutive losses
   - Gate rejections today (count + top 3 reasons)
   - Last 10 executed trades with result

   **G. System Health & Logs**
   - Recent WARNING and ERROR logs (filterable by component)
   - Latency SLA breaches (count + recent)
   - Model loading times
   - CPU / Memory usage (if easy to add)

3. **Technical requirements**
   - Real-time auto-refresh (every 15-30 seconds)
   - Clean, dark theme consistent with the launcher
   - Use sidebar or tabs for navigation
   - Make heavy use of the existing logging files and state JSONs
   - Add export buttons for logs and training history

4. **Nice to have**
   - Simple charts: training reward over time, twin confidence trend, daily PnL
   - Searchable log viewer
   - Quick links to start/stop training manually (for debugging)

### Output:
- Show the new file structure.
- Provide the complete code for the dashboard.
- Include instructions on how to launch it (e.g. button in launcher or separate command).
- Add clear comments in the code.
```

---

**Bestand opgeslagen als:**  
`/home/workdir/artifacts/LUMINA_CURSOR_MONITORING_DASHBOARD_PROMPT.md`