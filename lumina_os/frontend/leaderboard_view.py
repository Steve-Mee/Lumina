from __future__ import annotations
import logging

import os
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st


def _get_json(url: str, timeout: float = 5.0) -> dict[str, Any] | list[Any] | None:
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logging.exception("Unhandled broad exception fallback in lumina_os/frontend/leaderboard_view.py:19")
        st.warning(f"Data request failed for {url}: {exc}")
        return None


def render_leaderboard_tab(api_base_url: str) -> None:
    st.subheader("Trader League - Live Rankings")

    data = _get_json(f"{api_base_url}/leaderboard")
    leaderboard_rows = data.get("leaderboard", []) if isinstance(data, dict) else []
    leaderboard_df = pd.DataFrame(leaderboard_rows)

    # Positional index so rank = row position + 1 matches API sort order.
    lb = leaderboard_df.reset_index(drop=True)

    col1, col2, col3 = st.columns(3)
    participants = int(len(lb.index)) if not lb.empty else 0
    trades_total = 0
    if not lb.empty and "trades" in lb.columns:
        trades_numeric = pd.to_numeric(lb["trades"], errors="coerce")
        if isinstance(trades_numeric, pd.Series):
            trades_total = int(float(trades_numeric.fillna(0).sum()))

    lumina_rank = "-"
    lumina_pnl = 0.0
    if not lb.empty and "participant" in lb.columns:
        names = lb["participant"].astype(str)
        mask = names.str.contains("LUMINA", case=False, na=False)
        lumina_rows = lb.loc[mask]
        hit = mask.to_numpy(dtype=bool, copy=False)
        if hit.any():
            row_ix = int(np.argmax(hit))
            lumina_rank = str(row_ix + 1)
            if "total_pnl" in lb.columns and not lumina_rows.empty:
                lumina_pnl = float(lumina_rows.iloc[0]["total_pnl"] or 0.0)

    col1.metric("Participants", participants)
    col2.metric("Total Trades", trades_total)
    col3.metric("LUMINA Rank", lumina_rank)

    if lumina_rank != "-":
        st.caption(f"LUMINA total PnL: ${lumina_pnl:,.2f}")

    st.dataframe(lb, width="stretch")

    st.markdown("---")
    st.subheader("Fill Reconciliation Status")
    status_col_1, status_col_2, status_col_3 = st.columns(3)

    status_payload = _get_json(f"{api_base_url}/reconciliation-status")
    if isinstance(status_payload, dict):
        status_col_1.metric("Connection", str(status_payload.get("connection_state", "unknown")).upper())
        status_col_2.metric("Pending Closes", int(status_payload.get("pending_count", 0) or 0))
        status_col_3.metric("Method", str(status_payload.get("method", "unknown")).upper())

        st.caption(f"Last update: {status_payload.get('updated_at', datetime.now(UTC).isoformat())}")
        pending_symbols = status_payload.get("pending_symbols")
        if isinstance(pending_symbols, list) and pending_symbols:
            st.write("Pending symbols:", ", ".join(str(item) for item in pending_symbols))

        last_error = status_payload.get("last_error")
        if last_error:
            st.warning(f"Last reconciler error: {last_error}")

    _participant = os.getenv("LUMINA_TRADER_NAME") or os.getenv("TRADERLEAGUE_PARTICIPANT_HANDLE") or "LUMINA_Steve"
    recent_payload = _get_json(f"{api_base_url}/trades?limit=10&participant={_participant}")
    recent_df = pd.DataFrame(recent_payload if isinstance(recent_payload, list) else [])
    if not recent_df.empty:
        cols = [
            column
            for column in [
                "ts",
                "symbol",
                "signal",
                "entry",
                "exit",
                "pnl",
                "commission",
                "slippage_points",
                "fill_latency_ms",
                "reconciliation_status",
            ]
            if column in recent_df.columns
        ]
        st.dataframe(recent_df[cols], width="stretch")

    chart_payload = _get_json(f"{api_base_url}/trades?limit=100&participant={_participant}")
    chart_df = pd.DataFrame(chart_payload if isinstance(chart_payload, list) else [])
    if not chart_df.empty and "ts" in chart_df.columns:
        chart_df["ts"] = pd.to_datetime(chart_df["ts"], errors="coerce")
        chart_df = chart_df.sort_values("ts")
        left, right = st.columns(2)

        if "slippage_points" in chart_df.columns:
            slippage_df = chart_df.dropna(subset=["slippage_points"]).copy()
            if not slippage_df.empty:
                slippage_fig = px.line(
                    slippage_df,
                    x="ts",
                    y="slippage_points",
                    title="Slippage (points)",
                    markers=True,
                )
                left.plotly_chart(slippage_fig, width="stretch")

        if "fill_latency_ms" in chart_df.columns:
            latency_df = chart_df.dropna(subset=["fill_latency_ms"]).copy()
            if not latency_df.empty:
                latency_fig = px.line(
                    latency_df,
                    x="ts",
                    y="fill_latency_ms",
                    title="Fill latency (ms)",
                    markers=True,
                )
                right.plotly_chart(latency_fig, width="stretch")
