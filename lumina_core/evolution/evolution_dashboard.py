from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


METRICS_PATH = Path("logs/evolution_metrics.jsonl")
SHADOW_STATE_PATH = Path("state/evolution_shadow_runs.json")


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


def _load_shadow_runs(path: Path = SHADOW_STATE_PATH) -> dict[str, Any]:
    """Load shadow run state tracking real vs hypothetical performance."""
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


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
                        "shadow_status": str(gen.get("shadow_status", "not_required")),
                        "shadow_pnl": float(gen.get("shadow_total_pnl", 0.0) or 0.0),
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

    # FASE 3: Shadow run monitoring
    st.subheader("Shadow Run Status")
    shadow_runs = _load_shadow_runs(SHADOW_STATE_PATH)
    if shadow_runs:
        shadow_rows: list[dict[str, Any]] = []
        for dna_hash, record in shadow_runs.items():
            if isinstance(record, dict):
                daily_pnl = list(record.get("daily_pnl", []) or [])
                shadow_rows.append(
                    {
                        "dna_hash": str(dna_hash)[:12],
                        "status": str(record.get("status", "unknown")),
                        "target_days": int(record.get("target_days", 0) or 0),
                        "completed_days": len(daily_pnl),
                        "total_pnl": float(record.get("shadow_total_pnl", 0.0) or 0.0),
                        "started": str(record.get("started_at", ""))[:10],
                    }
                )
        if shadow_rows:
            shadow_df = pd.DataFrame(shadow_rows).tail(10)
            st.dataframe(shadow_df, use_container_width=True)

            # Real vs Shadow comparison
            if len(shadow_rows) >= 2:
                pnl_comparison = [row["total_pnl"] for row in shadow_rows[-5:]]
                st.bar_chart(pd.Series(pnl_comparison, name="Shadow PnL"), height=200)
    else:
        st.info("No active shadow runs.")
