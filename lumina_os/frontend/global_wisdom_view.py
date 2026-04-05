from __future__ import annotations

from typing import Any

import pandas as pd
import requests
import streamlit as st


def _get_json(url: str, timeout: float = 5.0) -> dict[str, Any] | list[Any] | None:
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.warning(f"Data request failed for {url}: {exc}")
        return None


def render_global_wisdom_tab(api_base_url: str) -> None:
    st.subheader("Global Wisdom - Top Bibles")

    payload = _get_json(f"{api_base_url}/global_wisdom")
    if not isinstance(payload, dict):
        st.info("No global wisdom data available yet.")
        return

    top_bibles = payload.get("top_bibles", [])
    wisdom_df = pd.DataFrame(top_bibles if isinstance(top_bibles, list) else [])

    score = float(payload.get("global_wisdom_score", 0.0) or 0.0)
    count = int(len(wisdom_df.index)) if not wisdom_df.empty else 0

    col1, col2 = st.columns(2)
    col1.metric("Global Wisdom Score", f"{score:.2f}")
    col2.metric("Tracked Bibles", count)

    st.dataframe(wisdom_df, use_container_width=True)

    st.caption("Tip: upload bibles/reflections through backend endpoints to enrich collective intelligence.")
