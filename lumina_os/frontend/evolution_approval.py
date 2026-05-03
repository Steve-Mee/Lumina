"""Evolution Approval UI – renders the '🔄 Evolution Approvals' dashboard tab.

Displays all open challenger proposals from the backend, with per-challenger
approve buttons and a per-proposal reject form.  Integrates with the
ObservabilityService via the backend REST layer.

Auto-refreshes every 30 s when enabled.
"""

from __future__ import annotations
import logging

import time
from typing import Any

import requests
import streamlit as st


# ── Helpers ───────────────────────────────────────────────────────────────────


def _fetch_proposals(base_url: str, api_key: str) -> list[dict[str, Any]]:
    """GET /api/evolution/proposals – returns open proposals or empty list."""
    try:
        headers = {"X-API-Key": api_key} if api_key else {}
        resp = requests.get(f"{base_url}/api/evolution/proposals", headers=headers, timeout=5)
        if resp.ok:
            return resp.json()  # type: ignore[return-value]
        st.warning(f"Proposals fetch failed: HTTP {resp.status_code}")
        return []
    except Exception as exc:
        logging.exception("Unhandled broad exception fallback in lumina_os/frontend/evolution_approval.py:31")
        st.warning(f"Cannot reach evolution endpoint: {exc}")
        return []


def _diff_hyperparams(champion_hp: dict[str, Any], challenger_hp: dict[str, Any]) -> str:
    """Return a Markdown string showing changed / unchanged hyperparams."""
    lines: list[str] = []
    all_keys = sorted(set(champion_hp) | set(challenger_hp))
    for key in all_keys:
        old = champion_hp.get(key, "—")
        new = challenger_hp.get(key, "—")
        if old != new:
            lines.append(f"- **{key}**: `{old}` → **`{new}`**  ✏️")
        else:
            lines.append(f"- {key}: `{old}` *(unchanged)*")
    return "\n".join(lines) if lines else "*(no parameter changes)*"


def _post(base_url: str, path: str, api_key: str, payload: dict[str, Any]) -> requests.Response:
    return requests.post(
        f"{base_url}{path}",
        json=payload,
        headers={"X-API-Key": api_key} if api_key else {},
        timeout=10,
    )


# ── Main render function ───────────────────────────────────────────────────────


def render_evolution_approval_tab(base_url: str, api_key: str = "") -> None:
    """Render the Evolution Approvals tab inside the Lumina OS dashboard."""
    st.subheader("🔄 Evolution Approvals – Challenger Proposals")

    # ── Toolbar ───────────────────────────────────────────────────────────────
    col_key, col_refresh, col_auto = st.columns([3, 1, 2])

    with col_key:
        # Allow an API key override in the UI when not passed in
        if api_key:
            resolved_key = api_key
        else:
            resolved_key = st.text_input(
                "API Key",
                type="password",
                key="evo_api_key",
                placeholder="Required to approve / reject",
            )

    with col_refresh:
        st.write("")  # vertical alignment nudge
        if st.button("🔄 Refresh", key="evo_refresh_btn"):
            st.rerun()

    with col_auto:
        st.write("")
        auto_refresh = st.checkbox("Auto-refresh every 30 s", value=False, key="evo_auto_refresh")

    if auto_refresh:
        time.sleep(30)
        st.rerun()

    # ── Load proposals ────────────────────────────────────────────────────────
    proposals: list[dict[str, Any]] = _fetch_proposals(base_url, resolved_key)

    if not proposals:
        st.info("No open challenger proposals – all caught up! ✅")
        return

    st.caption(f"**{len(proposals)}** open proposal(s) awaiting human review.")

    # ── Render each proposal ──────────────────────────────────────────────────
    for idx, prop in enumerate(proposals):
        hash_val: str = str(prop.get("hash", ""))
        hash_short: str = hash_val[:8]
        ts: str = str(prop.get("timestamp", ""))[:19].replace("T", " ")

        champion: dict[str, Any] = prop.get("champion", {})
        champion_hp: dict[str, Any] = champion.get("hyperparams", {})
        challengers: list[dict[str, Any]] = prop.get("challengers", [])
        best: dict[str, Any] = prop.get("best_candidate", {})
        meta: dict[str, Any] = prop.get("meta_review", {})
        proposal_meta: dict[str, Any] = prop.get("proposal", {})

        # Expander title summarises the key decision point
        expander_title = (
            f"📋 Proposal `{hash_short}` — {ts} UTC  |  "
            f"Best challenger: **{best.get('name', '?')}**  "
            f"(score {float(best.get('score', 0)):.2f})"
        )

        with st.expander(expander_title, expanded=(idx == 0)):
            # ── Performance summary ───────────────────────────────────────
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Trades", int(meta.get("trades", 0)))
            m2.metric("Win Rate", f"{float(meta.get('win_rate', 0)) * 100:.1f}%")
            m3.metric("Net PnL", f"${float(meta.get('net_pnl', 0)):.0f}")
            m4.metric("Sharpe", f"{float(meta.get('sharpe', 0)):.2f}")

            safety_ok = bool(proposal_meta.get("safety_ok"))
            backtest_ok = bool(proposal_meta.get("backtest_green"))
            confidence_val = float(proposal_meta.get("confidence", 0.0))

            safety_badge = "✅ OK" if safety_ok else "⚠️ NOT OK"
            backtest_badge = "✅ Green" if backtest_ok else "🔴 Failed"

            st.caption(
                f"Backtest: {backtest_badge}  ·  Safety: {safety_badge}  ·  Confidence: **{confidence_val:.1f}%**"
            )

            st.divider()

            # ── Per-challenger cards ──────────────────────────────────────
            st.markdown("#### Challengers")

            for challenger in challengers:
                c_name: str = str(challenger.get("name", "?"))
                c_score = float(challenger.get("score", 0))
                c_conf = float(challenger.get("confidence", 0))
                c_risk = float(challenger.get("risk_penalty", 0))
                c_prompt: str = str(challenger.get("prompt_tweak", ""))
                c_hp: dict[str, Any] = challenger.get("hyperparam_suggestion", {})
                is_best = c_name == best.get("name")

                label = f"**{c_name}**" + ("  ⭐ *best candidate*" if is_best else "")
                st.markdown(label)

                sc1, sc2, sc3 = st.columns(3)
                sc1.metric("Score", f"{c_score:.2f}")
                sc2.metric("Confidence", f"{c_conf:.0f}%")
                sc3.metric("Risk Penalty", f"{c_risk:.1f}")

                with st.expander(f"↳ {c_name} – prompt & hyperparam diff"):
                    st.markdown("**Prompt tweak:**")
                    st.info(c_prompt if c_prompt else "*(no prompt change)*")
                    st.markdown("**Hyperparam diff vs current champion:**")
                    st.markdown(_diff_hyperparams(champion_hp, c_hp))

                approve_key = f"approve_{hash_short}_{c_name}_{idx}"
                if st.button(
                    f"✅ Approve {c_name}",
                    key=approve_key,
                    type="primary",
                    help="Promote this challenger to champion and apply its hyperparams",
                ):
                    if not resolved_key:
                        st.error("Enter an API key first.")
                    else:
                        try:
                            resp = _post(
                                base_url,
                                "/api/evolution/approve",
                                resolved_key,
                                {"hash": hash_val, "challenger_name": c_name},
                            )
                            if resp.ok:
                                st.success(
                                    f"✅ **{c_name}** approved and promoted to champion. "
                                    "Config updated, meta-agent triggered."
                                )
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"Approval failed: HTTP {resp.status_code} — {resp.text}")
                        except Exception as exc:
                            logging.exception(
                                "Unhandled broad exception fallback in lumina_os/frontend/evolution_approval.py:196"
                            )
                            st.error(f"Request error: {exc}")

                st.write("")  # spacing between challengers

            st.divider()

            # ── Reject form (per proposal) ────────────────────────────────
            st.markdown("#### ❌ Reject this Proposal")

            reject_reason = st.text_input(
                "Rejection reason",
                key=f"evo_reject_reason_{hash_short}_{idx}",
                placeholder="e.g. Sharpe too low, risk profile mismatch…",
            )
            if st.button(
                "❌ Reject Proposal",
                key=f"evo_reject_btn_{hash_short}_{idx}",
                help="Log this proposal as rejected and send an observability alert",
            ):
                if not resolved_key:
                    st.error("Enter an API key first.")
                elif not reject_reason.strip():
                    st.warning("Please provide a rejection reason before submitting.")
                else:
                    try:
                        resp = _post(
                            base_url,
                            "/api/evolution/reject",
                            resolved_key,
                            {"hash": hash_val, "reason": reject_reason.strip()},
                        )
                        if resp.ok:
                            st.success("Proposal rejected and logged. Observability alert sent.")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Rejection failed: HTTP {resp.status_code} — {resp.text}")
                    except Exception as exc:
                        logging.exception(
                            "Unhandled broad exception fallback in lumina_os/frontend/evolution_approval.py:234"
                        )
                        st.error(f"Request error: {exc}")
