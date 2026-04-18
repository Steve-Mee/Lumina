from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


METRICS_PATH = Path("logs/evolution_metrics.jsonl")


def _load_metrics(path: Path = METRICS_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except Exception:
                continue
            if isinstance(parsed, dict) and parsed.get("status") == "complete":
                rows.append(parsed)
    return rows


def render_evolution_dashboard(path: Path = METRICS_PATH) -> None:
    st.subheader("Evolution Metrics")
    rows = _load_metrics(path)
    if not rows:
        st.info("No evolution metrics yet.")
        return

    latest = rows[-1]
    st.metric("Generations", int(latest.get("generations_run", 0) or 0))
    st.metric("Candidates", int(latest.get("total_candidates_evaluated", 0) or 0))
    st.metric("Promotions", int(latest.get("promotions", 0) or 0))

    generation_rows: list[dict[str, Any]] = []
    for cycle_idx, cycle in enumerate(rows, start=1):
        for gen in cycle.get("generations", []):
            if isinstance(gen, dict):
                generation_rows.append(
                    {
                        "cycle": cycle_idx,
                        "generation": int(gen.get("generation", 0) or 0),
                        "winner_fitness": float(gen.get("winner_fitness", 0.0) or 0.0),
                        "promoted": bool(gen.get("promoted", False)),
                    }
                )

    if generation_rows:
        df = pd.DataFrame(generation_rows)
        st.line_chart(df.pivot_table(index="generation", values="winner_fitness", aggfunc="mean"), height=220)
        st.dataframe(df.tail(25), use_container_width=True)

    latest_generations = latest.get("generations", []) if isinstance(latest.get("generations"), list) else []
    if latest_generations:
        top = max(latest_generations, key=lambda item: float(item.get("winner_fitness") or float("-inf")))
        st.caption(
            f"Top DNA hash: {str(top.get('winner_hash', ''))[:16]} | fitness={float(top.get('winner_fitness', 0.0) or 0.0):.4f}"
        )
