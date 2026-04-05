import streamlit as st

from global_wisdom_view import render_global_wisdom_tab
from leaderboard_view import render_leaderboard_tab

st.set_page_config(page_title="LUMINA OS", layout="wide")
st.title("🌍 LUMINA OS – Trader League + Community Wisdom")

api_base_url = "http://localhost:8000"

tab1, tab2 = st.tabs(["🏆 Live Leaderboard", "📚 Global Community Bibles"])

with tab1:
	render_leaderboard_tab(api_base_url)

with tab2:
	render_global_wisdom_tab(api_base_url)

st.info("Upload your trades, Bibles or reflections via the bot webhook -> everything appears here instantly.")
