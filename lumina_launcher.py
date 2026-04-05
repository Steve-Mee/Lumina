from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace
from typing import Any, cast

import pandas as pd
import requests
import streamlit as st

from lumina_core.engine.engine_config import EngineConfig
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.engine.performance_validator import PerformanceValidator
from lumina_core.runtime_context import RuntimeContext

st.set_page_config(page_title="LUMINA OS Launcher", layout="wide")

ENV_PATH = Path(".env")
RUNTIME_ENTRY = Path("lumina_v45.1.1.py")
LUMINA_LOG_PATH = Path("logs/lumina_full_log.csv")
STATE_PATH = Path("state/lumina_sim_state.json")
BACKEND_BASE_URL = os.getenv("LUMINA_BACKEND_URL", "http://localhost:8000").rstrip("/")
ADMIN_PASSWORD = os.getenv("LUMINA_ADMIN_PASSWORD", "lumina2026")


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_env_file(path: Path, updates: dict[str, str]) -> None:
    merged = _parse_env_file(path)
    merged.update({k: str(v) for k, v in updates.items()})
    content = "\n".join(f"{k}={v}" for k, v in sorted(merged.items())) + "\n"
    path.write_text(content, encoding="utf-8")


def _runtime_command() -> list[str]:
    python_cmd = os.getenv("LUMINA_PYTHON", sys.executable)
    return [python_cmd, str(RUNTIME_ENTRY)]


def _process_is_alive() -> bool:
    proc = st.session_state.get("bot_process")
    return proc is not None and proc.poll() is None


def _start_bot_process() -> tuple[bool, str]:
    if not RUNTIME_ENTRY.exists():
        return False, f"Runtime entry not found: {RUNTIME_ENTRY}"

    if _process_is_alive():
        return True, "Bot is already running"

    command = _runtime_command()
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    try:
        proc = subprocess.Popen(
            command,
            cwd=str(Path.cwd()),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        st.session_state.bot_process = proc
        return True, f"Bot started (pid={proc.pid})"
    except Exception as exc:
        return False, f"Failed to start bot: {exc}"


def _stop_bot_process() -> tuple[bool, str]:
    proc = st.session_state.get("bot_process")
    if proc is None:
        return True, "No running bot process"

    if proc.poll() is not None:
        st.session_state.bot_process = None
        return True, "Bot process already stopped"

    try:
        proc.terminate()
        proc.wait(timeout=15)
        st.session_state.bot_process = None
        return True, "Bot stopped"
    except Exception as exc:
        return False, f"Failed to stop bot: {exc}"


def _tail_file(path: Path, max_chars: int = 4000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-max_chars:]


def _load_runtime_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        import json

        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _backend_get(path: str, timeout: float = 3.0) -> dict[str, Any]:
    url = f"{BACKEND_BASE_URL}{path}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _build_validation_context() -> RuntimeContext:
    cfg = EngineConfig()
    engine = LuminaEngine(cfg)

    app = SimpleNamespace(
        logger=engine.logger,
        SWARM_SYMBOLS=[str(x).strip().upper() for x in cfg.swarm_symbols],
        INSTRUMENT=str(cfg.instrument).strip().upper(),
        CROSSTRADE_TOKEN=cfg.crosstrade_token or "",
        log_thought=lambda *_args, **_kwargs: None,
    )

    bound_app = cast(ModuleType, app)
    engine.bind_app(bound_app)
    return RuntimeContext(engine=engine, app=bound_app)


st.title("LUMINA OS - Start Screen")
st.markdown("**De nummer 1 trading bot ter wereld - nu voor iedereen**")

with st.sidebar:
    st.header("Bot Configuration")

    trade_mode = st.selectbox(
        "Trading Mode",
        options=["paper", "sim", "real"],
        index=0,
        help="Paper = simulatie | Sim = demo account | Real = echt geld",
    )

    risk_profile = st.selectbox(
        "Risk Profile",
        options=["Conservative", "Balanced", "Aggressive"],
        index=1,
    )

    instrument = st.selectbox(
        "Instrument",
        options=["MES JUN26", "MNQ JUN26", "MYM JUN26", "ES JUN26"],
        index=0,
    )

    voice_enabled = st.checkbox("Voice (TTS + input)", value=True)
    screen_share_enabled = st.checkbox("Live Chart Screen Share", value=True)
    dashboard_enabled = st.checkbox("Dashboard", value=True)

    st.divider()

    if st.button("Save Config and Start Bot", type="primary", use_container_width=True):
        cfg_updates = {
            "TRADE_MODE": trade_mode,
            "LUMINA_RISK_PROFILE": risk_profile.lower(),
            "INSTRUMENT": instrument,
            "VOICE_ENABLED": str(voice_enabled).lower(),
            "SCREEN_SHARE_ENABLED": str(screen_share_enabled).lower(),
            "DASHBOARD_ENABLED": str(dashboard_enabled).lower(),
        }
        _write_env_file(ENV_PATH, cfg_updates)
        ok, msg = _start_bot_process()
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    if st.button("Stop Bot", use_container_width=True):
        ok, msg = _stop_bot_process()
        if ok:
            st.info(msg)
        else:
            st.error(msg)

alive = _process_is_alive()
if alive:
    bot_proc = st.session_state.get("bot_process")
    pid = getattr(bot_proc, "pid", "unknown")
    st.success(f"BOT IS LIVE - pid={pid}")
else:
    st.info("Configureer links in de sidebar en klik op START BOT om te beginnen.")

state = _load_runtime_state()
current_dream = state.get("current_dream", {}) if isinstance(state.get("current_dream"), dict) else {}


tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "Live Trader View",
        "Trader League",
        "Community Bibles",
        "Performance Reports",
        "Admin / Backend",
    ]
)

with tab1:
    st.subheader("Live Dream + Runtime State")
    if current_dream:
        st.json(current_dream)
    else:
        st.info("Nog geen runtime state gevonden in state/lumina_sim_state.json")

    col1, col2, col3 = st.columns(3)
    col1.metric("Sim Position Qty", value=state.get("sim_position_qty", 0))
    col2.metric("Live Position Qty", value=state.get("live_position_qty", 0))
    col3.metric("Pending Reconciliations", value=len(state.get("pending_trade_reconciliations", []) or []))

with tab2:
    st.subheader("Trader League Leaderboard")
    try:
        leaderboard_payload = _backend_get("/leaderboard")
        leaderboard = leaderboard_payload.get("leaderboard", [])
        if isinstance(leaderboard, list) and leaderboard:
            st.dataframe(pd.DataFrame(leaderboard), use_container_width=True)
        else:
            st.info("Leaderboard is leeg")
    except Exception as exc:
        st.info(f"Leaderboard backend nog niet gestart ({exc})")

with tab3:
    st.subheader("Global Community Bibles")
    try:
        wisdom_payload = _backend_get("/global_wisdom")
        top_bibles = wisdom_payload.get("top_bibles", [])
        if isinstance(top_bibles, list) and top_bibles:
            st.dataframe(pd.DataFrame(top_bibles), use_container_width=True)
        else:
            st.info("Nog geen community bible data")
    except Exception as exc:
        st.info(f"Community backend nog niet gestart ({exc})")

with tab4:
    st.subheader("Ultimate Performance Validation")
    if st.button("Run 3-Year Validation Now"):
        try:
            runtime_context = _build_validation_context()
            validator = PerformanceValidator(engine=runtime_context.engine)
            report = validator.run_3year_validation()
            st.json(report)
        except Exception as exc:
            st.error(f"Validation failed: {exc}")

    reports_dir = Path("journal/reports")
    if reports_dir.exists():
        files = sorted([p.name for p in reports_dir.iterdir() if p.is_file()], reverse=True)
        if files:
            st.write("Recent reports:")
            st.write("\n".join(files[:10]))

with tab5:
    st.subheader("Admin Backend")
    password = st.text_input("Admin Password", type="password")
    if password == ADMIN_PASSWORD:
        st.success("Admin toegang verleend")

        st.write("Runtime entry:")
        st.code(str(RUNTIME_ENTRY))

        st.write("Log tail (lumina_full_log.csv):")
        log_tail = _tail_file(LUMINA_LOG_PATH, max_chars=6000)
        if log_tail:
            st.code(log_tail)
        else:
            st.info("Nog geen logdata gevonden")
    else:
        st.warning("Alleen voor admin")

st.caption("LUMINA OS v3.5 - gebouwd voor iedereen. Niets is onmogelijk.")
