---
agent: ask
description: "Implement or refine Lumina hybrid NewsAgent using xAI tools with safe fallbacks and zero breaking changes"
---

You are an expert Python AI-trading engineer specialized in the Lumina architecture.

PROJECT CONTEXT (respect this 100% – this is the real repo):
- Repository: https://github.com/Steve-Mee/Lumina
- Root folder contains: config.yaml, lumina_runtime.py (main runtime entrypoint), watchdog.py, nightly_infinite_sim.py
- Key folders:
  - lumina_agents/          -> here new agents live
  - lumina_core/            -> core engine (engine/, runtime_context.py, pre_dream_daemon, WorldModel, etc.)
  - lumina_bible/           -> used for WorldModel
  - state/, logs/, config.yaml (root)
- Existing architecture: RuntimeContext, pre_dream_daemon, WorldModel, lumina_daytrading_bible.json, live_stream.jsonl, lumina_full_log.csv
- Current setup: local Ollama + Qwen models. Add only a lightweight hybrid NewsAgent for real-time X sentiment + high-impact news.

DELIVERY RULES:
1. Preserve local Ollama/Qwen flow and runtime stability.
2. Use existing RuntimeContext and logger.
3. Keep fail-safe fallback: neutral sentiment and multiplier 1.0 if xAI is unavailable.
4. Keep Docker/watchdog/nightly compatibility.
5. Use clean type hints and minimal-risk edits.

TARGET IMPLEMENTATION:
- NewsAgent with xAI SDK Client, model grok-4.1-fast.
- Use tools x_semantic_search + x_keyword_search for X sentiment.
- Use web_search + browse_page for high-impact/economic context.
- Compute bullish/bearish/neutral and score in range [-1, 1].
- Detect high-impact events (FOMC, CPI, NFP, etc.) and enforce 3-minute avoidance window.
- Produce dynamic impact multiplier in range [0.5, 2.0] and inject into WorldModel.
- Cache updates on a 60-second interval.
- Emit logger line: NEWS_CYCLE,sentiment=...,multiplier=...,avoid=...

When implementing, always show a clear diff summary and list validations you ran.
