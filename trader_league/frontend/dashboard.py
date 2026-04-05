import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import plotly.express as px

st.set_page_config(page_title="Trader League Live", layout="wide")
st.title("🌍 Trader League – LUMINA vs de wereld")

api_base_url = "http://localhost:8000"

if st.button("Refresh Leaderboard"):
	data = requests.get(f"{api_base_url}/leaderboard", timeout=5).json()
	df = pd.DataFrame(data["leaderboard"])
	st.dataframe(df, use_container_width=True)

# LUMINA spotlight
st.subheader("🔥 LUMINA Live Status")
st.metric("Current Mode", "PAPER" if "paper" else "REAL")
st.metric("Today PnL", "$2,847")
st.metric("Sharpe (30d)", "2.84")

st.subheader("🧩 Fill Reconciliation Status")
status_col_1, status_col_2, status_col_3 = st.columns(3)
try:
	status = requests.get(f"{api_base_url}/reconciliation-status", timeout=5).json()
	status_col_1.metric("Connection", str(status.get("connection_state", "unknown")).upper())
	status_col_2.metric("Pending Closes", int(status.get("pending_count", 0)))
	status_col_3.metric("Method", str(status.get("method", "unknown")).upper())

	st.caption(f"Last update: {status.get('updated_at', datetime.utcnow().isoformat())}")
	if status.get("pending_symbols"):
		st.write("Pending symbols:", ", ".join(status.get("pending_symbols", [])))
	if status.get("last_error"):
		st.warning(f"Last reconciler error: {status['last_error']}")

	recent_trades = requests.get(f"{api_base_url}/trades?limit=10&participant=LUMINA_v45_Steve", timeout=5).json()
	trades_df = pd.DataFrame(recent_trades)
	if not trades_df.empty:
		columns = [
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
			if column in trades_df.columns
		]
		st.dataframe(trades_df[columns], use_container_width=True)

	chart_trades = requests.get(f"{api_base_url}/trades?limit=100&participant=LUMINA_v45_Steve", timeout=5).json()
	chart_df = pd.DataFrame(chart_trades)
	if not chart_df.empty and "ts" in chart_df.columns:
		chart_df["ts"] = pd.to_datetime(chart_df["ts"], errors="coerce")
		chart_df = chart_df.sort_values("ts")
		left, right = st.columns(2)
		if "slippage_points" in chart_df.columns:
			slip_df = chart_df.dropna(subset=["slippage_points"]).copy()
			if not slip_df.empty:
				slip_fig = px.line(
					slip_df,
					x="ts",
					y="slippage_points",
					title="Slippage (points)",
					markers=True,
				)
				left.plotly_chart(slip_fig, use_container_width=True)
		if "fill_latency_ms" in chart_df.columns:
			lat_df = chart_df.dropna(subset=["fill_latency_ms"]).copy()
			if not lat_df.empty:
				latency_fig = px.line(
					lat_df,
					x="ts",
					y="fill_latency_ms",
					title="Fill latency (ms)",
					markers=True,
				)
				right.plotly_chart(latency_fig, use_container_width=True)
except Exception as exc:
	st.info(f"Reconciliation status nog niet beschikbaar: {exc}")

st.info("Trade replay + AI reflection komt binnenkort – elke trade is terug te kijken met chart + reflection.")
