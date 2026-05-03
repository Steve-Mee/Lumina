from __future__ import annotations
import logging

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


METRICS_PATH = Path("logs/evolution_metrics.jsonl")
SHADOW_STATE_PATH = Path("state/evolution_shadow_runs.json")
GENERATED_BIBLE_PATH = Path("state/lumina_bible_generated_strategies.jsonl")
ROLLOUT_HISTORY_PATH = Path("state/evolution_rollout_history.jsonl")


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
                logging.exception(
                    "Unhandled broad exception fallback in lumina_core/evolution/evolution_dashboard.py:28"
                )
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
        logging.exception("Unhandled broad exception fallback in lumina_core/evolution/evolution_dashboard.py:43")
        return {}


def _load_generated_strategies(path: Path = GENERATED_BIBLE_PATH) -> list[dict[str, Any]]:
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
                logging.exception(
                    "Unhandled broad exception fallback in lumina_core/evolution/evolution_dashboard.py:58"
                )
                continue
            if isinstance(parsed, dict) and parsed.get("entry_type") == "generated_strategy_rule":
                rows.append(parsed)
    return rows


def _load_rollout_history(path: Path = ROLLOUT_HISTORY_PATH) -> list[dict[str, Any]]:
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
                logging.exception(
                    "Unhandled broad exception fallback in lumina_core/evolution/evolution_dashboard.py:76"
                )
                continue
            if isinstance(parsed, dict) and parsed.get("event") == "rollout_decision":
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

    st.subheader("Rollout Safety Gate")
    rollout_rows = _load_rollout_history(ROLLOUT_HISTORY_PATH)
    if rollout_rows:
        compact_rollout: list[dict[str, Any]] = []
        for item in rollout_rows[-20:]:
            compact_rollout.append(
                {
                    "mode": str(item.get("mode", "unknown")),
                    "stage": str(item.get("stage", "unknown")),
                    "allow_promotion": bool(item.get("allow_promotion", False)),
                    "radical_mutation": bool(item.get("radical_mutation", False)),
                    "human_required": bool(item.get("human_approval_required", False)),
                    "human_granted": bool(item.get("human_approval_granted", False)),
                    "ab_verdict": str(item.get("ab_verdict", "unknown")),
                    "reason": str(item.get("reason", "")),
                    "timestamp": str(item.get("timestamp", ""))[:19],
                }
            )
        st.dataframe(pd.DataFrame(compact_rollout), use_container_width=True)
    else:
        st.info("No rollout decisions recorded yet.")

    st.subheader("Neuroevolution Winners")
    neuro_rows: list[dict[str, Any]] = []
    for cycle_idx, cycle in enumerate(rows, start=1):
        for gen in list(cycle.get("generations", []) or []):
            if not isinstance(gen, dict):
                continue
            tested = int(gen.get("neuro_tested", 0) or 0)
            winners = int(gen.get("neuro_winners", 0) or 0)
            if tested <= 0 and winners <= 0:
                continue
            neuro_rows.append(
                {
                    "cycle": cycle_idx,
                    "generation": int(gen.get("generation", 0) or 0),
                    "tested": tested,
                    "winners": winners,
                    "winner_fitness": float(gen.get("winner_fitness", 0.0) or 0.0),
                }
            )

    if neuro_rows:
        neuro_df = pd.DataFrame(neuro_rows)
        st.dataframe(neuro_df.tail(20), use_container_width=True)
        st.caption(
            f"Total neuro winners: {int(sum(int(item['winners']) for item in neuro_rows))} | "
            f"total tested: {int(sum(int(item['tested']) for item in neuro_rows))}"
        )
    else:
        st.info("No neuroevolution winners recorded yet.")

    # FASE 3: Generated Strategies observability
    st.subheader("Generated Strategies")
    generated_rows = _load_generated_strategies(GENERATED_BIBLE_PATH)
    if not generated_rows:
        st.info("No generated strategy winners recorded yet.")
        return

    compact_rows: list[dict[str, Any]] = []
    for item in generated_rows[-20:]:
        compact_rows.append(
            {
                "dna_hash": str(item.get("dna_hash", ""))[:12],
                "generation": int(item.get("generation", 0) or 0),
                "fitness": float(item.get("fitness", 0.0) or 0.0),
                "status": str(item.get("status", "winner") or "winner"),
                "timestamp": str(item.get("timestamp", ""))[:19],
            }
        )

    st.dataframe(pd.DataFrame(compact_rows), use_container_width=True)

    latest = generated_rows[-1]
    st.caption(
        f"Latest generated DNA: {str(latest.get('dna_hash', ''))[:16]} | fitness={float(latest.get('fitness', 0.0) or 0.0):.4f} | status={str(latest.get('status', 'winner'))}"
    )

    latest_code = str(latest.get("code", "") or "").strip()
    if latest_code:
        st.code(latest_code[:1800], language="python")
