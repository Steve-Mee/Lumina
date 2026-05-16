"""
UI Tab - Admin Panel
Volledig functionele admin interface met backend integratie.
"""

import asyncio
import json
import logging
from pathlib import Path

import streamlit as st
import yaml

from lumina_launcher.core.blank_reset import (
    PRESERVED_STATE_FILES,
    WIPE_DIRECTORIES,
    DELETE_TARGETS,
    run_post_setup_blank_reset,
)
from lumina_launcher.observability import log_event, timed_event
from lumina_launcher.services.backend_client import BackendClient
from lumina_launcher.core.process_manager import ProcessManager

logger = logging.getLogger(__name__)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _load_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def _render_reset_stepper(root: Path, process_manager: ProcessManager | None) -> None:
    st.markdown("### Volledige reset naar post-setup")
    st.error(
        "Deze reset verwijdert training/policy/historiek en zet de bot terug naar net na setup. "
        "Je moet first-boot training daarna opnieuw doorlopen."
    )
    st.caption("Na reset verdwijnt de Admin-tab tijdelijk tot first boot opnieuw is afgerond.")

    step_key = "admin_blank_reset_step"
    confirm1_key = "admin_blank_reset_confirm_1"
    confirm2_key = "admin_blank_reset_confirm_2"
    phrase_key = "admin_blank_reset_phrase"
    required_phrase = "RESET FIRST BOOT"
    current_step = int(st.session_state.get(step_key, 1))

    st.markdown(f"**Reset stap {current_step}/3**")
    if current_step == 1:
        st.warning(
            "- Alle first-boot artefacten worden verwijderd.\n"
            "- Historische simulator-journals en logs worden gewist.\n"
            "- Er wordt eerst automatisch een backup gemaakt."
        )
        confirm1 = st.checkbox(
            "Ik begrijp dat deze actie niet ongedaan kan worden gemaakt.",
            key=confirm1_key,
        )
        if st.button("Ga naar stap 2", disabled=not confirm1, use_container_width=True):
            st.session_state[step_key] = 2
            st.rerun()
        return

    if current_step == 2:
        left, right = st.columns(2)
        with left:
            st.markdown("**Wordt verwijderd**")
            for item in WIPE_DIRECTORIES:
                st.caption(f"- `{item}`")
            for item in DELETE_TARGETS:
                st.caption(f"- `{item}`")
        with right:
            st.markdown("**Blijft behouden**")
            st.caption("- `config.yaml`")
            st.caption("- `.env`")
            for item in PRESERVED_STATE_FILES:
                st.caption(f"- `state/{item}`")
        confirm2 = st.checkbox(
            "Ik wil doorgaan met de volledige reset.",
            key=confirm2_key,
        )
        col_prev, col_next = st.columns(2)
        with col_prev:
            if st.button("Terug naar stap 1", use_container_width=True):
                st.session_state[step_key] = 1
                st.rerun()
        with col_next:
            if st.button("Ga naar stap 3", disabled=not confirm2, use_container_width=True):
                st.session_state[step_key] = 3
                st.rerun()
        return

    st.warning(
        f"Laatste bevestiging: typ exact `{required_phrase}` om de permanente reset uit te voeren."
    )
    st.text_input("Typ de bevestigingszin", key=phrase_key)
    phrase_ok = st.session_state.get(phrase_key, "") == required_phrase
    can_execute = bool(st.session_state.get(confirm1_key)) and bool(st.session_state.get(confirm2_key)) and phrase_ok
    if st.button(
        "Uitvoeren — permanente reset",
        type="primary",
        disabled=not can_execute,
        use_container_width=True,
    ):
        with st.spinner("Reset wordt uitgevoerd..."):
            stop_fn = process_manager.stop_bot if process_manager is not None else None
            result = run_post_setup_blank_reset(root, stop_runtime=stop_fn)
        if not result.success:
            st.error(result.message)
            return
        backup_label = str(result.backup_path) if result.backup_path else "(onbekend)"
        st.success(f"Reset voltooid. Backup opgeslagen in: `{backup_label}`")
        st.info("Start opnieuw via First Boot tab om training te herstarten.")
        st.session_state.pop(step_key, None)
        st.session_state.pop(confirm1_key, None)
        st.session_state.pop(confirm2_key, None)
        st.session_state.pop(phrase_key, None)
        st.rerun()

    col_back, col_abort = st.columns(2)
    with col_back:
        if st.button("Terug naar stap 2", use_container_width=True):
            st.session_state[step_key] = 2
            st.rerun()
    with col_abort:
        if st.button("Annuleer resetflow", use_container_width=True):
            st.session_state.pop(step_key, None)
            st.session_state.pop(confirm1_key, None)
            st.session_state.pop(confirm2_key, None)
            st.session_state.pop(phrase_key, None)
            st.rerun()


def render_admin_tab(
    backend_client: BackendClient | None = None,
    *,
    workspace_root: Path | None = None,
    process_manager: ProcessManager | None = None,
) -> None:
    st.subheader("🛠️ Admin Panel")

    root = workspace_root.resolve() if workspace_root is not None else Path(__file__).resolve().parents[3]
    setup_complete = _load_json(root / "state" / "lumina_setup_complete.json")
    setup_status = _load_json(root / "state" / "lumina_setup_status.json")
    config_yaml = _load_yaml(root / "config.yaml")
    env_map = _load_env(root / ".env")
    first_boot_cfg = config_yaml.get("first_boot", {}) if isinstance(config_yaml.get("first_boot"), dict) else {}

    st.markdown("### Setup & Training Configuration")
    c1, c2, c3 = st.columns(3)
    c1.metric("Setup completed", "Yes" if bool(setup_complete.get("completed")) else "No")
    c2.metric("Runtime mode", str(env_map.get("TRADE_MODE") or config_yaml.get("mode", "unknown")).upper())
    c3.metric(
        "Configured first-boot trades",
        f"{int(first_boot_cfg.get('training_trades', 0) or 0):,}" if first_boot_cfg else "n/a",
    )
    with st.expander("Show setup/config details", expanded=False):
        st.json(
            {
                "setup_complete": setup_complete,
                "setup_status": setup_status,
                "first_boot_config": first_boot_cfg,
                "runtime_env_subset": {
                    "TRADE_MODE": env_map.get("TRADE_MODE", ""),
                    "LUMINA_MODE": env_map.get("LUMINA_MODE", ""),
                    "BROKER_BACKEND": env_map.get("BROKER_BACKEND", ""),
                    "ENABLE_SIM_REAL_GUARD": env_map.get("ENABLE_SIM_REAL_GUARD", ""),
                },
            }
        )

    st.divider()
    st.warning("⚠️ Deze acties zijn permanent en kunnen niet ongedaan gemaakt worden!")

    client = backend_client or BackendClient()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🗑️ Verwijder ALLE Trades", type="primary", width="stretch"):
            with st.spinner("Bezig met verwijderen..."):
                with timed_event("launcher.admin.mutation", action="delete_all_trades"):
                    result = asyncio.run(client.delete_all_trades())
                if result.get("error"):
                    log_event("launcher.admin.mutation_result", level=logging.ERROR, action="delete_all_trades", status="error")
                    st.error(f"Fout: {result.get('error')}")
                else:
                    log_event("launcher.admin.mutation_result", action="delete_all_trades", status="ok")
                    st.success("Alle trades succesvol verwijderd!")
                    st.json(result)

    with col2:
        if st.button("🧹 Verwijder DEMO Data", width="stretch"):
            with st.spinner("Bezig met verwijderen..."):
                with timed_event("launcher.admin.mutation", action="delete_demo_data"):
                    result = asyncio.run(client.delete_demo_data())
                if result.get("error"):
                    logger.warning("Admin mutation failed: delete_demo_data")
                    log_event("launcher.admin.mutation_result", level=logging.ERROR, action="delete_demo_data", status="error")
                    st.error(f"Fout: {result.get('error')}")
                else:
                    log_event("launcher.admin.mutation_result", action="delete_demo_data", status="ok")
                    st.success("Demo data succesvol verwijderd!")
                    st.json(result)

    st.divider()
    _render_reset_stepper(root, process_manager)
    st.divider()
    st.caption("Admin Panel — Volledig geïntegreerd met backend")
