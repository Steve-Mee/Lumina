from __future__ import annotations
# ruff: noqa: E402

import base64
import html
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import subprocess
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
# ── Headless detection: must precede any Streamlit initialisation ──────────────
_IS_HEADLESS = "--headless" in sys.argv or "--stability-check" in sys.argv

if not _IS_HEADLESS:
    import streamlit as st  # type: ignore[import]
else:
    st = None  # type: ignore[assignment]  # placeholder; unused in headless path
import yaml

from lumina_core.container import create_application_container
from lumina_core.engine.hardware_inspector import HardwareInspector, HardwareSnapshot
from lumina_core.engine.model_catalog import ModelCatalog, ModelDescriptor
from lumina_core.engine.model_trainer import ModelTrainer
from lumina_core.engine.performance_validator import PerformanceValidator
from lumina_core.engine.setup_service import SetupService, SetupStepResult
from lumina_core.engine.sim_stability_checker import (
    format_stability_report,
    generate_stability_report,
)
from lumina_core.runtime_context import RuntimeContext

if not _IS_HEADLESS:
    st.set_page_config(page_title="LUMINA OS Launcher", layout="wide")

ENV_PATH = Path(".env")
CONFIG_PATH = Path("config.yaml")
RUNTIME_ENTRY = Path("lumina_core/engine/runtime_entrypoint.py")
LUMINA_LOG_PATH = Path("logs/lumina_full_log.csv")
STATE_PATH = Path("state/lumina_sim_state.json")
ADMIN_PASSWORD_HASH_PATH = Path("state/launcher_admin_password.json")
MODEL_CATALOG_STATE_PATH = Path("state/model_catalog_state.json")
SUPPORT_EVENTS_PATH = Path("state/launcher_support_events.jsonl")
PROCESS_STATE_PATH = Path("state/launcher_bot_process.json")
BACKEND_BASE_URL = os.getenv("LUMINA_BACKEND_URL", "http://localhost:8000").rstrip("/")
LAST_RUN_SUMMARY_PATH = Path("state/last_run_summary.json")
EVOLUTION_LOG_PATH = Path("state/evolution_log.jsonl")
SIM_HISTORY_PATH = Path("state/sim_stability_history.jsonl")


def _load_admin_password_record() -> dict[str, Any] | None:
    if not ADMIN_PASSWORD_HASH_PATH.exists():
        return None
    try:
        payload = json.loads(ADMIN_PASSWORD_HASH_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        required = {"salt_b64", "hash_b64", "iterations"}
        if not required.issubset(set(payload.keys())):
            return None
        return payload
    except Exception:
        return None


def _derive_password_hash(password: str, salt_bytes: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)


def _verify_admin_password(candidate: str) -> bool:
    record = _load_admin_password_record()
    if not record:
        return False
    try:
        salt_bytes = base64.b64decode(str(record.get("salt_b64", "")))
        expected_hash = base64.b64decode(str(record.get("hash_b64", "")))
        iterations = int(record.get("iterations", 0))
    except Exception:
        return False
    if iterations < 100_000 or not salt_bytes or not expected_hash:
        return False
    candidate_hash = _derive_password_hash(candidate, salt_bytes, iterations)
    return hmac.compare_digest(candidate_hash, expected_hash)


def _set_admin_password(new_password: str) -> None:
    salt_bytes = secrets.token_bytes(16)
    iterations = 240_000
    pwd_hash = _derive_password_hash(new_password, salt_bytes, iterations)
    ADMIN_PASSWORD_HASH_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "algo": "pbkdf2_sha256",
        "iterations": iterations,
        "salt_b64": base64.b64encode(salt_bytes).decode("ascii"),
        "hash_b64": base64.b64encode(pwd_hash).decode("ascii"),
    }
    ADMIN_PASSWORD_HASH_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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


def _load_yaml_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _sim_real_guard_launch_flags() -> tuple[bool, bool, bool]:
    enabled = str(os.getenv("ENABLE_SIM_REAL_GUARD", "false")).strip().lower() == "true"
    pilot_enabled = str(os.getenv("ENABLE_SIM_REAL_GUARD_PILOT", "false")).strip().lower() == "true"
    public_enabled = str(os.getenv("ENABLE_SIM_REAL_GUARD_PUBLIC", "false")).strip().lower() == "true"
    return enabled, pilot_enabled, public_enabled


def _available_launcher_trade_modes() -> list[str]:
    return ["paper", "sim", "sim_real_guard", "real"]


def _sim_real_guard_real_promotion_allowed() -> bool:
    return str(os.getenv("ALLOW_SIM_REAL_GUARD_REAL_PROMOTION", "false")).strip().lower() == "true"


def _runtime_command() -> list[str]:
    python_cmd = os.getenv("LUMINA_PYTHON", sys.executable)
    return [python_cmd, str(RUNTIME_ENTRY), "--mode", "auto"]


def _load_process_state() -> dict[str, Any]:
    if not PROCESS_STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(PROCESS_STATE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _save_process_state(*, pid: int, command: list[str]) -> None:
    PROCESS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": int(pid),
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "command": command,
    }
    PROCESS_STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _clear_process_state() -> None:
    try:
        PROCESS_STATE_PATH.unlink(missing_ok=True)
    except Exception:
        pass


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _pid_command_line(pid: int) -> str:
    if pid <= 0:
        return ""
    try:
        if os.name == "nt":
            query = f"(Get-CimInstance Win32_Process -Filter \"ProcessId = {pid}\").CommandLine"
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", query],
                check=False,
                capture_output=True,
                text=True,
            )
            return (result.stdout or "").strip()
        proc_cmdline = Path(f"/proc/{pid}/cmdline")
        if not proc_cmdline.exists():
            return ""
        raw = proc_cmdline.read_text(encoding="utf-8", errors="replace")
        return raw.replace("\x00", " ").strip()
    except Exception:
        return ""


def _pid_matches_runtime(pid: int, expected_command: list[str]) -> bool:
    cmdline = _pid_command_line(pid).lower()
    if not cmdline:
        return False
    runtime_token = str(RUNTIME_ENTRY).lower()
    if runtime_token not in cmdline:
        return False
    expected_python = str(expected_command[0]).lower() if expected_command else ""
    if expected_python and Path(expected_python).name.lower() not in cmdline:
        return False
    return True


def _process_is_alive() -> bool:
    proc = st.session_state.get("bot_process")
    if proc is not None and proc.poll() is None:
        return True
    st.session_state.bot_process = None
    state = _load_process_state()
    command = state.get("command", [])
    expected_command = command if isinstance(command, list) else []
    pid = int(state.get("pid", 0) or 0)
    if _pid_is_alive(pid) and _pid_matches_runtime(pid, expected_command):
        return True
    _clear_process_state()
    return False


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
        _save_process_state(pid=proc.pid, command=command)
        return True, f"Bot started (pid={proc.pid})"
    except Exception as exc:
        return False, f"Failed to start bot: {exc}"


def _stop_bot_process() -> tuple[bool, str]:
    proc = st.session_state.get("bot_process")
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=15)
            st.session_state.bot_process = None
            _clear_process_state()
            return True, "Bot stopped"
        except Exception as exc:
            return False, f"Failed to stop bot: {exc}"

    state = _load_process_state()
    pid = int(state.get("pid", 0) or 0)
    if not _pid_is_alive(pid):
        st.session_state.bot_process = None
        _clear_process_state()
        return True, "Bot process already stopped"

    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, capture_output=True, text=True)
        else:
            os.kill(pid, 15)
        st.session_state.bot_process = None
        _clear_process_state()
        return True, "Bot stopped"
    except Exception as exc:
        return False, f"Failed to stop bot: {exc}"


def _tail_file(path: Path, max_chars: int = 4000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-max_chars:]


def _file_age_seconds(path: Path) -> float | None:
    if not path.exists():
        return None
    return max(0.0, (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).total_seconds())


def _format_age(age_seconds: float | None) -> str:
    if age_seconds is None:
        return "Not available"
    if age_seconds < 60:
        return f"{int(age_seconds)}s ago"
    if age_seconds < 3600:
        return f"{int(age_seconds // 60)}m ago"
    return f"{int(age_seconds // 3600)}h ago"


def _format_timestamp(path: Path) -> str:
    if not path.exists():
        return "Not available"
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "Not available"


def _service_age_badge(age_seconds: float | None, healthy_threshold_seconds: float = 90.0) -> str:
    if age_seconds is None:
        return _status_badge("No feed yet", "warning")
    if age_seconds <= healthy_threshold_seconds:
        return _status_badge("Live", "available")
    return _status_badge("Stale", "warning")


def _render_live_age_cards(log_age: float | None, state_age: float | None, last_launch_text: str) -> None:
    if st is None:
        return

    now_ts = int(datetime.now().timestamp())
    log_base = int(log_age) if log_age is not None else -1
    state_base = int(state_age) if state_age is not None else -1
    safe_launch = html.escape(last_launch_text, quote=True)

    card_html = f"""
<div style=\"display:grid;grid-template-columns:repeat(3,minmax(140px,1fr));gap:0.6rem;margin:0.15rem 0 0.4rem 0;\">
    <div style=\"border:1px solid #e2e8f0;border-radius:0.6rem;padding:0.55rem 0.7rem;background:#f8fafc;\">
        <div style=\"font-size:0.74rem;color:#475569;\">Log heartbeat</div>
        <div id=\"lumina-live-log-age\" style=\"font-size:0.95rem;font-weight:600;color:#0f172a;\">-</div>
    </div>
    <div style=\"border:1px solid #e2e8f0;border-radius:0.6rem;padding:0.55rem 0.7rem;background:#f8fafc;\">
        <div style=\"font-size:0.74rem;color:#475569;\">Runtime state update</div>
        <div id=\"lumina-live-state-age\" style=\"font-size:0.95rem;font-weight:600;color:#0f172a;\">-</div>
    </div>
    <div style=\"border:1px solid #e2e8f0;border-radius:0.6rem;padding:0.55rem 0.7rem;background:#f8fafc;\">
        <div style=\"font-size:0.74rem;color:#475569;\">Last launch</div>
        <div style=\"font-size:0.95rem;font-weight:600;color:#0f172a;\">{safe_launch}</div>
    </div>
</div>
<script>
    const nowTs = {now_ts};
    const baseLog = {log_base};
    const baseState = {state_base};
    function prettyAge(seconds) {{
        if (seconds < 0) return 'Not available';
        if (seconds < 60) return `${{seconds}}s ago`;
        if (seconds < 3600) return `${{Math.floor(seconds / 60)}}m ago`;
        return `${{Math.floor(seconds / 3600)}}h ago`;
    }}
    function tick() {{
        const elapsed = Math.max(0, Math.floor(Date.now() / 1000) - nowTs);
        const logEl = document.getElementById('lumina-live-log-age');
        const stateEl = document.getElementById('lumina-live-state-age');
        if (logEl) logEl.textContent = prettyAge(baseLog < 0 ? -1 : baseLog + elapsed);
        if (stateEl) stateEl.textContent = prettyAge(baseState < 0 ? -1 : baseState + elapsed);
    }}
    tick();
    setInterval(tick, 1000);
</script>
"""
    data_url = "data:text/html;charset=utf-8," + urllib.parse.quote(card_html)
    st.iframe(data_url, height=105)


def _render_live_activity_panel(*, alive: bool, screen_share_enabled: bool, dashboard_enabled: bool) -> None:
    st.markdown("### Live Activity & Services")
    process_badge = _status_badge("Running", "available") if alive else _status_badge("Stopped", "blocked")
    st.markdown(f"Bot Process {process_badge}", unsafe_allow_html=True)
    if alive:
        auto_refresh = st.toggle(
            "Auto-refresh live status (5s)",
            value=bool(st.session_state.get("live_status_auto_refresh", True)),
            key="live_status_auto_refresh",
        )
        if auto_refresh:
            refresh_html = (
                "<html><body><script>"
                "setTimeout(function(){ window.parent.location.reload(); }, 5000);"
                "</script></body></html>"
            )
            refresh_url = "data:text/html;charset=utf-8," + urllib.parse.quote(refresh_html)
            st.iframe(refresh_url, height=0, width="content")
        st.markdown(
            """
            <style>
            @keyframes luminaPulse {
                0% { transform: scale(0.9); opacity: 0.8; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.5); }
                70% { transform: scale(1.0); opacity: 1; box-shadow: 0 0 0 10px rgba(16, 185, 129, 0.0); }
                100% { transform: scale(0.9); opacity: 0.8; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.0); }
            }
            .lumina-live-pulse {
                width: 10px;
                height: 10px;
                border-radius: 999px;
                background: #10b981;
                display: inline-block;
                margin-right: 8px;
                animation: luminaPulse 1.8s infinite;
            }
            .lumina-live-label {
                display: inline-flex;
                align-items: center;
                color: #065f46;
                font-size: 0.88rem;
                font-weight: 600;
                margin: 0.15rem 0 0.45rem 0;
            }
            </style>
            <div class=\"lumina-live-label\"><span class=\"lumina-live-pulse\"></span>Live execution heartbeat</div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.caption("Heartbeat indicator becomes active when the bot is running.")

    log_age = _file_age_seconds(LUMINA_LOG_PATH)
    state_age = _file_age_seconds(STATE_PATH)
    screen_share_path = Path("state/live_stream.jsonl")
    dashboard_path = Path("journal/swarm_dashboard.html")
    screen_share_age = _file_age_seconds(screen_share_path)
    dashboard_age = _file_age_seconds(dashboard_path)

    process_state = _load_process_state()
    persisted_start_ts = str(process_state.get("started_at", "")).strip() or "Not started"
    _render_live_age_cards(log_age, state_age, st.session_state.get("last_start_ts", persisted_start_ts))

    left, right = st.columns(2)
    with left:
        st.markdown("#### Live Chart Screen Share")
        if screen_share_enabled:
            st.markdown(_service_age_badge(screen_share_age), unsafe_allow_html=True)
            if screen_share_age is None:
                st.info("Screen share is enabled and waiting for the first chart frame feed.")
            else:
                st.caption(f"Last chart feed update timestamp: {_format_timestamp(screen_share_path)}")
        else:
            st.markdown(_status_badge("Disabled", "neutral"), unsafe_allow_html=True)
            st.caption("Enable this in the sidebar to publish live chart feed.")

    with right:
        st.markdown("#### Dashboard")
        if dashboard_enabled:
            st.markdown(_service_age_badge(dashboard_age, healthy_threshold_seconds=300.0), unsafe_allow_html=True)
            if dashboard_age is None:
                st.info("Dashboard is enabled but no dashboard artifact was found yet.")
            else:
                st.caption(f"Last dashboard update timestamp: {_format_timestamp(dashboard_path)}")
                st.caption("Artifact: journal/swarm_dashboard.html")
        else:
            st.markdown(_status_badge("Disabled", "neutral"), unsafe_allow_html=True)
            st.caption("Enable this in the sidebar to generate dashboard output.")

    if alive:
        primary_heartbeat_ok = log_age is not None and log_age <= 180
        secondary_heartbeat_ok = (
            (dashboard_age is not None and dashboard_age <= 300)
            or (screen_share_age is not None and screen_share_age <= 180)
        )
        if primary_heartbeat_ok:
            st.success("Bot is alive: log activity was updated in the last 3 minutes.")
        elif secondary_heartbeat_ok:
            st.info("Bot process is running and secondary services are live; primary log heartbeat is delayed.")
        else:
            st.warning("Bot process is running, but heartbeat artifacts look stale. Check runtime diagnostics.")

    st.markdown("#### Recent Bot Activity")
    recent_log = _tail_file(LUMINA_LOG_PATH, max_chars=8000).strip()
    if not recent_log:
        st.caption("No runtime log output yet.")
    else:
        lines = recent_log.splitlines()
        excerpt = "\n".join(lines[-24:])
        st.code(excerpt, language="text")


def _load_runtime_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _linear_trend(values: list[float]) -> list[float]:
    if len(values) < 2:
        return values[:]
    n = float(len(values))
    xs = list(range(len(values)))
    sum_x = float(sum(xs))
    sum_y = float(sum(values))
    sum_xx = float(sum(x * x for x in xs))
    sum_xy = float(sum(x * y for x, y in zip(xs, values)))
    denom = (n * sum_xx) - (sum_x * sum_x)
    if abs(denom) <= 1e-9:
        return [float(values[0])] * len(values)
    slope = ((n * sum_xy) - (sum_x * sum_y)) / denom
    intercept = (sum_y - (slope * sum_x)) / n
    return [float((slope * x) + intercept) for x in xs]


def _parse_iso_ts(raw_value: Any) -> datetime | None:
    if not raw_value:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_last_run_summary() -> dict[str, Any]:
    if not LAST_RUN_SUMMARY_PATH.exists():
        return {}
    try:
        payload = json.loads(LAST_RUN_SUMMARY_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _load_evolution_rows() -> list[dict[str, Any]]:
    if not EVOLUTION_LOG_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in EVOLUTION_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    rows.sort(key=lambda row: _parse_iso_ts(row.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc))
    return rows


def _window_metrics(summary: dict[str, Any], rows: list[dict[str, Any]], window_days: int) -> dict[str, float]:
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=window_days)
    filtered = [r for r in rows if (_parse_iso_ts(r.get("timestamp")) or now_utc) >= cutoff]

    pnl = _safe_float(summary.get("pnl_realized"))
    trades = _safe_int(summary.get("total_trades"))
    wins = _safe_int(summary.get("wins"))
    sharpe_values: list[float] = []
    summary_sharpe = _safe_float(summary.get("sharpe_annualized"), default=0.0)
    if summary_sharpe != 0.0:
        sharpe_values.append(summary_sharpe)
    risk_events = _safe_int(summary.get("risk_events"))

    for row in filtered:
        meta = row.get("meta_review") if isinstance(row.get("meta_review"), dict) else {}
        pnl += _safe_float(meta.get("net_pnl"))
        trades += _safe_int(meta.get("trades"))
        wins += _safe_int(meta.get("wins"))
        row_sharpe = _safe_float(meta.get("sharpe"), default=0.0)
        if row_sharpe != 0.0:
            sharpe_values.append(row_sharpe)
        risk_events += _safe_int(row.get("risk_events"))

    win_rate = (wins / trades) if trades > 0 else 0.0
    sharpe = (sum(sharpe_values) / len(sharpe_values)) if sharpe_values else 0.0
    expectancy = (pnl / trades) if trades > 0 else 0.0
    return {
        "pnl": pnl,
        "win_rate": win_rate,
        "sharpe": sharpe,
        "expectancy": expectancy,
        "risk_events": float(risk_events),
    }


def _proposal_snapshot(rows: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    proposals = [row for row in rows if str(row.get("status", "")).lower() == "proposed" or isinstance(row.get("proposal"), dict)]
    latest = list(reversed(proposals))[:5]
    rendered: list[dict[str, Any]] = []
    for row in latest:
        best = row.get("best_candidate") if isinstance(row.get("best_candidate"), dict) else {}
        rendered.append(
            {
                "timestamp": row.get("timestamp", "n/a"),
                "candidate": best.get("name", "n/a"),
                "score": round(_safe_float(best.get("score")), 4),
                "confidence": round(_safe_float((row.get("proposal") or {}).get("confidence")), 2),
            }
        )
    return len(proposals), rendered


def _last_5d_expectancy(rows: list[dict[str, Any]], summary: dict[str, Any]) -> list[float]:
    buckets: dict[str, dict[str, float]] = {}
    for row in rows:
        ts = _parse_iso_ts(row.get("timestamp"))
        if ts is None:
            continue
        day_key = ts.date().isoformat()
        slot = buckets.setdefault(day_key, {"pnl": 0.0, "trades": 0.0})
        meta = row.get("meta_review") if isinstance(row.get("meta_review"), dict) else {}
        slot["pnl"] += _safe_float(meta.get("net_pnl"))
        slot["trades"] += float(_safe_int(meta.get("trades")))

    summary_ts = _parse_iso_ts(summary.get("finished_at") or summary.get("started_at"))
    if summary_ts is None:
        summary_ts = datetime.now(timezone.utc)
    key = summary_ts.date().isoformat()
    slot = buckets.setdefault(key, {"pnl": 0.0, "trades": 0.0})
    slot["pnl"] += _safe_float(summary.get("pnl_realized"))
    slot["trades"] += float(_safe_int(summary.get("total_trades")))

    values: list[float] = []
    for day in sorted(buckets.keys(), reverse=True)[:5]:
        trades = buckets[day]["trades"]
        values.append((buckets[day]["pnl"] / trades) if trades > 0 else 0.0)
    return values


def _current_launcher_mode() -> str:
    env_mode = str(os.getenv("LUMINA_MODE", "")).strip().lower()
    if env_mode in {"sim", "paper", "real"}:
        return env_mode
    config_mode = str(_load_yaml_config().get("mode", "sim")).strip().lower()
    return config_mode if config_mode in {"sim", "paper", "real"} else "sim"


def _load_stability_history() -> list[dict[str, Any]]:
    """Load state/sim_stability_history.jsonl; rows sorted ascending by day."""
    if not SIM_HISTORY_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in SIM_HISTORY_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    rows.sort(key=lambda r: str(r.get("day", "")))
    return rows


def _render_sim_learning_tab() -> None:
    st.subheader("🚀 SIM Evolution Dashboard")

    # ── Load data ──────────────────────────────────────────────────────────────
    history_rows = _load_stability_history()
    report = generate_stability_report()
    consecutive = int(report.get("consecutive_green_days", 0))
    days_to_green = int(report.get("days_to_green", 5))
    history_count = int(report.get("history_row_count", len(history_rows)))
    criteria = report.get("criteria") if isinstance(report.get("criteria"), dict) else {}
    failures = report.get("failures", []) if isinstance(report.get("failures"), list) else []
    is_green = bool(report.get("READY_FOR_REAL", False))
    status_label = str(report.get("status", "RED")).strip().upper()
    sharpe_crit = criteria.get("extended_run_sharpe", {}) if isinstance(criteria.get("extended_run_sharpe"), dict) else {}
    latest_sharpe = _safe_float(sharpe_crit.get("latest_sharpe", 0.0))

    summary_color = "#16a34a" if is_green else "#dc2626"
    summary_failures = "none" if not failures else ", ".join(str(x) for x in failures)
    st.markdown(
        f"<div style='padding:10px 14px;border-radius:10px;border:1px solid {summary_color};"
        f"background:{summary_color}14;'><strong>Latest stability_report:</strong> "
        f"<span style='color:{summary_color};font-weight:700;'>{status_label}</span> "
        f"| failures: {summary_failures}</div>",
        unsafe_allow_html=True,
    )

    # ── Streak banner ──────────────────────────────────────────────────────────
    if is_green:
        st.success(f"✅ READY FOR REAL — {consecutive}/5 consecutive positive-expectancy days achieved!")
    elif consecutive >= 3:
        st.warning(f"🟡 {consecutive} / 5 consecutive positive-expectancy days — {days_to_green} more needed")
    else:
        st.error(f"🔴 {consecutive} / 5 consecutive positive-expectancy days — {days_to_green} more needed")
    st.markdown(f"### {consecutive} / 5 consecutive positive expectancy days")
    st.progress(min(max(consecutive / 5.0, 0.0), 1.0))

    # ── Summary metrics ────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "🟢 Streak Days",
        f"{consecutive} / 5",
        delta="✅ READY" if is_green else f"-{days_to_green} to REAL",
    )
    c2.metric("Days to REAL", days_to_green)
    c3.metric(
        "Latest Sharpe",
        f"{latest_sharpe:.4f}",
        delta="✅ > 1.8" if latest_sharpe > 1.8 else "❌ < 1.8",
    )
    c4.metric("History Rows", history_count)

    # ── Charts: rolling Sharpe + evolution proposals ───────────────────────────
    if history_rows:
        tail = history_rows[-7:]
        day_labels = [str(r.get("day", "")) for r in tail]
        sharpes = [_safe_float(r.get("sharpe_annualized")) for r in tail]
        proposals = [float(_safe_int(r.get("evolution_proposals"))) for r in tail]
        proposal_trend = _linear_trend(proposals)

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("##### 📈 Rolling Sharpe (last 7 days)")
            sharpe_df = pd.DataFrame(
                {"Sharpe": sharpes, "Threshold 1.8": [1.8] * len(sharpes)},
                index=day_labels,
            )
            st.line_chart(sharpe_df, height=200)

        with chart_col2:
            st.markdown("##### 🧬 Evolution Proposals Trend (last 7 days)")
            props_df = pd.DataFrame(
                {"Proposals": proposals, "Trend": proposal_trend},
                index=day_labels,
            )
            st.line_chart(props_df, height=200)
    else:
        st.info("No history data yet — run a SIM to start accumulating daily records.")

    # ── Criteria scorecard ─────────────────────────────────────────────────────
    st.markdown("#### 🎯 REAL Readiness Criteria")
    exp = criteria.get("positive_expectancy_5d", {}) if isinstance(criteria.get("positive_expectancy_5d"), dict) else {}
    consistent = criteria.get("consistent_sharpe", {}) if isinstance(criteria.get("consistent_sharpe"), dict) else {}
    risk = criteria.get("zero_risk_and_var", {}) if isinstance(criteria.get("zero_risk_and_var"), dict) else {}
    trend = criteria.get("evolution_proposals_trend", {}) if isinstance(criteria.get("evolution_proposals_trend"), dict) else {}

    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    sc1.metric(
        "5d Expectancy",
        "✅ PASS" if exp.get("ok") else "❌ FAIL",
        delta=f"streak {exp.get('streak_days', 0)}/{exp.get('required_days', 5)}",
    )
    sc2.metric(
        "Extended Sharpe",
        "✅ PASS" if sharpe_crit.get("ok") else "❌ FAIL",
        delta=f"{_safe_float(sharpe_crit.get('latest_sharpe')):.3f}",
    )
    sc3.metric(
        "Consistent Sharpe",
        "✅ PASS" if consistent.get("ok") else "❌ FAIL",
        delta=f"avg {_safe_float(consistent.get('average_sharpe')):.3f} ({int(consistent.get('available_runs', 0))}/5 runs)",
    )
    sc4.metric(
        "Zero Risk / VaR",
        "✅ PASS" if risk.get("ok") else "❌ FAIL",
        delta=f"events={risk.get('total_risk_events', 0)}",
    )
    sc5.metric(
        "Proposal Trend",
        "✅ PASS" if trend.get("ok") else "❌ FAIL",
        delta=f"7d={_safe_float(trend.get('slope_7d')):.2f}",
    )

    if failures:
        st.warning("⚠️ Failing criteria: " + ", ".join(failures))
    missing_days = report.get("missing_days_7d", []) if isinstance(report.get("missing_days_7d"), list) else []
    if missing_days:
        st.caption("📅 Missing days in rolling 7d window: " + ", ".join(str(d) for d in missing_days))

    with st.expander("📋 Full Stability Report", expanded=False):
        st.code(format_stability_report(report), language="text")

    # ── Action buttons ─────────────────────────────────────────────────────────
    st.markdown("#### ⚙️ Actions")
    btn_col1, btn_col2, btn_col3 = st.columns(3)

    with btn_col1:
        if st.button(
            "🚀 Run Aggressive Overnight SIM",
            type="primary",
            width='stretch',
            help="Launches: --headless --mode=sim --duration=240 --overnight-sim --stability-check",
        ):
            cmd = [
                sys.executable, "-m", "lumina_launcher",
                "--headless", "--mode=sim", "--duration=240",
                "--overnight-sim", "--stability-check",
            ]
            proc = subprocess.Popen(cmd, cwd=str(Path(".").resolve()), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            st.success(f"✅ Overnight SIM launched (PID {proc.pid}). Results appear in state/test_runs/ on completion.")

    with btn_col2:
        if st.button(
            "🔍 Check Stability Now",
            width='stretch',
            help="Re-generates the stability report from all available SIM summaries",
        ):
            st.rerun()

    with btn_col3:
        confirm = st.checkbox("✅ Confirm switch to REAL mode", key="confirm_real_switch_lnch")
        go_live_enabled = is_green and confirm
        if st.button(
            "🔴 Switch to REAL Mode",
            type="primary",
            width='stretch',
            disabled=not go_live_enabled,
            help="Only active when READY_FOR_REAL=True and operator confirmation is ticked above",
        ):
            current_mode = str(os.getenv("LUMINA_MODE", os.getenv("TRADE_MODE", "sim"))).strip().lower()
            if current_mode == "sim_real_guard" and not _sim_real_guard_real_promotion_allowed():
                st.error("SIM_REAL_GUARD -> REAL promotion is blocked by default. Set ALLOW_SIM_REAL_GUARD_REAL_PROMOTION=true after the required sign-off gate passes.")
            else:
                _write_env_file(ENV_PATH, {"LUMINA_MODE": "real"})
                os.environ["LUMINA_MODE"] = "real"
                st.success("✅ Stability GREEN + confirmed. LUMINA_MODE=real written to .env. Restart launcher to activate.")

    if not is_green:
        st.info(f"🔒 REAL mode locked until 5 consecutive positive-expectancy days. Progress: {consecutive}/5.")

    # ── Latest run summary ─────────────────────────────────────────────────────
    with st.expander("📄 Latest SIM Run Summary", expanded=False):
        summary = _load_last_run_summary()
        if summary:
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Trades", _safe_int(summary.get("total_trades")))
            s2.metric("PnL", f"${_safe_float(summary.get('pnl_realized')):.2f}")
            s3.metric("Sharpe", f"{_safe_float(summary.get('sharpe_annualized')):.4f}")
            s4.metric("Win Rate", f"{_safe_float(summary.get('win_rate')) * 100:.1f}%")
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Duration", f"{_safe_float(summary.get('duration_minutes')):.0f}m")
            d2.metric("Max Drawdown", f"${_safe_float(summary.get('max_drawdown')):.2f}")
            d3.metric("Risk Events", _safe_int(summary.get("risk_events")))
            d4.metric("Evolution Proposals", _safe_int(summary.get("evolution_proposals")))
        else:
            st.info("No run summary found yet.")


def _render_real_operations_tab(state: dict[str, Any]) -> None:
    st.subheader("REAL Operations Dashboard")
    summary = _load_last_run_summary()
    rows = _load_evolution_rows()

    m24 = _window_metrics(summary, rows, 1)
    m7 = _window_metrics(summary, rows, 7)
    m30 = _window_metrics(summary, rows, 30)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Realized PnL", f"${_safe_float(summary.get('pnl_realized')):.2f}")
    c2.metric("Max Drawdown", f"${_safe_float(summary.get('max_drawdown')):.2f}")
    c3.metric("Risk Events", _safe_int(summary.get("risk_events")))
    c4.metric("VaR Breaches", _safe_int(summary.get("var_breach_count")))

    p1, p2, p3 = st.columns(3)
    p1.metric("24h PnL", f"${m24['pnl']:.2f}")
    p2.metric("7d PnL", f"${m7['pnl']:.2f}")
    p3.metric("30d PnL", f"${m30['pnl']:.2f}")

    s1, s2, s3 = st.columns(3)
    s1.metric("Winrate", f"{_safe_float(summary.get('win_rate')) * 100:.2f}%")
    s2.metric("Sharpe", f"{_safe_float(summary.get('sharpe_annualized')):.2f}")
    s3.metric("Session Guard Blocks", _safe_int(summary.get("session_guard_blocks")))

    st.markdown("#### Exposure")
    e1, e2, e3 = st.columns(3)
    e1.metric("Live Position Qty", _safe_int(state.get("live_position_qty")))
    e2.metric("Pending Reconciliations", len(state.get("pending_trade_reconciliations", []) or []))
    e3.metric("Total Trades", _safe_int(summary.get("total_trades")))

    st.markdown("#### Capital Preservation Protocol")
    risk_events_ok = _safe_int(summary.get("risk_events")) == 0
    var_ok = _safe_int(summary.get("var_breach_count")) == 0
    drawdown_ok = _safe_float(summary.get("max_drawdown")) <= 500.0
    sharpe_ok = _safe_float(summary.get("sharpe_annualized")) >= 1.0
    pnl_24h_ok = m24["pnl"] >= 0.0
    protocol_green = risk_events_ok and var_ok and drawdown_ok and sharpe_ok and pnl_24h_ok

    g1, g2, g3, g4, g5 = st.columns(5)
    g1.metric("Risk Events = 0", "PASS" if risk_events_ok else "FAIL")
    g2.metric("VaR Breaches = 0", "PASS" if var_ok else "FAIL")
    g3.metric("Drawdown <= $500", "PASS" if drawdown_ok else "FAIL")
    g4.metric("Sharpe >= 1.0", "PASS" if sharpe_ok else "FAIL")
    g5.metric("24h PnL >= 0", "PASS" if pnl_24h_ok else "FAIL")

    if protocol_green:
        st.success("REAL protocol GREEN: system is within capital-preservation bounds.")
    else:
        st.error("REAL protocol RED: immediate operator review required.")


def _backend_get(path: str, timeout: float = 3.0) -> dict[str, Any]:
    url = f"{BACKEND_BASE_URL}{path}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _build_validation_context() -> RuntimeContext:
    """Bootstrap a validation-only container via ApplicationContainer (single bootstrap path)."""
    container = create_application_container()
    return container.runtime_context


def _load_catalog_state() -> dict[str, Any]:
    if not MODEL_CATALOG_STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(MODEL_CATALOG_STATE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _save_catalog_state(catalog: ModelCatalog, current_model_key: str) -> None:
    MODEL_CATALOG_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_CATALOG_STATE_PATH.write_text(
        json.dumps({"catalog_version": catalog.version(), "current_model_key": current_model_key}, indent=2),
        encoding="utf-8",
    )


def _status_badge(label: str, status: str) -> str:
    palette = {
        "available": "#0f766e",
        "blocked": "#b45309",
        "ready": "#1d4ed8",
        "warning": "#92400e",
        "neutral": "#374151",
    }
    color = palette.get(status, "#374151")
    return (
        f"<span style='display:inline-block;padding:0.2rem 0.55rem;border-radius:999px;"
        f"background:{color};color:white;font-size:0.78rem;font-weight:600;'>{label}</span>"
    )


def _render_kv_section(
    title: str,
    rows: list[tuple[str, Any]],
    help_map: dict[str, str] | None = None,
) -> None:
    st.markdown(f"#### {title}")
    explanations = help_map or {}
    for label, value in rows:
        left, right = st.columns([1, 2])
        tip = explanations.get(label)
        if tip:
            safe_tip = html.escape(tip, quote=True)
            left.markdown(
                f"{label} <span title=\"{safe_tip}\" style=\"display:inline-block;width:1rem;height:1rem;line-height:1rem;text-align:center;border-radius:999px;border:1px solid #94a3b8;color:#334155;font-size:0.72rem;margin-left:0.3rem;cursor:help;\">?</span>",
                unsafe_allow_html=True,
            )
        else:
            left.caption(label)
        if isinstance(value, bool):
            badge = _status_badge("Yes", "available") if value else _status_badge("No", "blocked")
            right.markdown(badge, unsafe_allow_html=True)
        else:
            right.markdown(str(value))


def _render_backend_unavailable_card(service_label: str, exc: Exception) -> None:
    st.warning(f"{service_label} backend is currently unavailable on localhost:8000.")
    st.caption("Start the backend service to load live data in this tab.")
    st.caption(f"Technical detail: {type(exc).__name__}")


def _render_live_runtime_card(current_dream: dict[str, Any]) -> None:
    rows = [
        ("Signal", current_dream.get("signal", "UNKNOWN")),
        ("Confidence", current_dream.get("confidence", 0)),
        ("Stop", current_dream.get("stop", 0)),
        ("Target", current_dream.get("target", 0)),
        ("Reason", current_dream.get("reason", "")),
        ("Why No Trade", current_dream.get("why_no_trade") or "N/A"),
        ("Confluence Score", current_dream.get("confluence_score", 0)),
        (
            "Fib Levels",
            "Set"
            if isinstance(current_dream.get("fib_levels"), dict) and current_dream.get("fib_levels")
            else "N/A",
        ),
        ("Swing High", current_dream.get("swing_high", 0)),
        ("Swing Low", current_dream.get("swing_low", 0)),
        ("A-B-EEN Direction", current_dream.get("a_been_direction", "NEUTRAL")),
        ("Chosen Strategy", current_dream.get("chosen_strategy", "None")),
    ]
    _render_kv_section(
        "Current Dream Decision",
        rows,
        help_map={
            "Signal": "The bot's current trade action: BUY, SELL, or HOLD.",
            "Confidence": "How sure the bot is about this signal (higher means more confidence).",
            "Stop": "The stop-loss price, used to limit loss if price moves against the trade.",
            "Target": "The take-profit price where the bot plans to lock in profit.",
            "Reason": "Short explanation of why the bot chose this signal.",
            "Why No Trade": "Reason why no position is opened right now, if applicable.",
            "Confluence Score": "Score showing how many indicators agree on the same direction.",
            "Fib Levels": "Fibonacci support and resistance levels used in the analysis.",
            "Swing High": "Recent local high price level used as a technical reference.",
            "Swing Low": "Recent local low price level used as a technical reference.",
            "A-B-EEN Direction": "Overall market direction from the internal trend model.",
            "Chosen Strategy": "Trading strategy currently selected by the bot for this setup.",
        },
    )


def _render_reports_section(reports_dir: Path) -> None:
    files = sorted([p for p in reports_dir.iterdir() if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        st.info("No reports found yet.")
        return

    report_rows: list[dict[str, Any]] = []
    for p in files[:20]:
        stat = p.stat()
        report_rows.append(
            {
                "File": p.name,
                "Type": p.suffix.lower().lstrip("."),
                "Size (KB)": round(stat.st_size / 1024.0, 1),
                "Modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            }
        )
    st.dataframe(pd.DataFrame(report_rows), width='stretch')

    selected_name = st.selectbox("Open report preview", [p.name for p in files[:20]], key="report_preview_select")
    selected_path = next((p for p in files if p.name == selected_name), None)
    if selected_path is None:
        return

    mime, _ = mimetypes.guess_type(str(selected_path))
    mime = mime or "application/octet-stream"
    file_bytes = selected_path.read_bytes()
    st.download_button(
        label=f"Download {selected_path.name}",
        data=file_bytes,
        file_name=selected_path.name,
        mime=mime,
        width='stretch',
        key=f"download_{selected_path.name}",
    )

    ext = selected_path.suffix.lower()
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        st.image(str(selected_path), caption=selected_path.name, width='stretch')
    elif ext in {".json", ".jsonl", ".txt", ".log", ".yaml", ".yml", ".csv"}:
        preview = selected_path.read_text(encoding="utf-8", errors="replace")[:8000]
        st.code(preview)
    elif ext == ".pdf":
        st.info("PDF preview is not embedded in this panel. Use the download button to open it locally.")


def _append_support_event(*, event_type: str, payload: dict[str, Any]) -> None:
    SUPPORT_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        **payload,
    }
    with SUPPORT_EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=True) + "\n")


def _render_guarded_action_button(
    *,
    label: str,
    allowed: bool,
    reason: str,
    command: list[str],
    trainer: ModelTrainer,
    current_model: ModelDescriptor,
    snapshot: HardwareSnapshot,
    action_key: str,
) -> None:
    if st.button(label, width='stretch'):
        if not allowed:
            _append_support_event(
                event_type="blocked_launcher_action",
                payload={
                    "action": action_key,
                    "reason": reason,
                    "hardware_tier": snapshot.profile_tier,
                    "os": snapshot.os_name,
                    "gpu": snapshot.gpu_name or "unknown",
                    "gpu_vram_gb": snapshot.gpu_vram_gb,
                    "ram_gb": snapshot.ram_gb,
                    "model_key": current_model.key,
                    "model_tag": current_model.ollama_tag,
                },
            )
            st.warning(f"{label} is blocked: {reason}")
            st.caption(f"Support event logged to {SUPPORT_EVENTS_PATH}")
            return
        ok, output = trainer.run_command(command)
        if ok:
            st.success(output)
        else:
            st.error(output)


def _find_model_key_for_reasoning_model(catalog: ModelCatalog, config_payload: dict[str, Any]) -> str:
    models = config_payload.get("models", {}) if isinstance(config_payload.get("models"), dict) else {}
    reasoning_model = str(models.get("reasoning", "")).strip()
    for descriptor in catalog.models():
        if descriptor.ollama_tag == reasoning_model or descriptor.key == reasoning_model:
            return descriptor.key
    return catalog.models()[0].key


def _refresh_hardware_snapshot() -> HardwareSnapshot:
    snapshot = HardwareInspector.capture()
    st.session_state["hardware_snapshot"] = snapshot
    return snapshot


def _get_hardware_snapshot() -> HardwareSnapshot:
    snapshot = st.session_state.get("hardware_snapshot")
    if isinstance(snapshot, HardwareSnapshot):
        return snapshot
    cached = HardwareInspector.load_cached()
    if cached is not None:
        st.session_state["hardware_snapshot"] = cached
        return cached
    return _refresh_hardware_snapshot()


def _render_step_result(result: SetupStepResult) -> None:
    if result.success:
        st.success(f"{result.name}: {result.message}")
    else:
        st.error(f"{result.name}: {result.message}")
    if result.command:
        st.caption(result.command)


def _runtime_supports_unsloth(snapshot: HardwareSnapshot) -> bool:
    return snapshot.os_name != "Windows" and snapshot.compute_capability >= 7.0 and snapshot.gpu_vram_gb >= 8.0


def _render_tier_requirements(snapshot: HardwareSnapshot) -> None:
    rows: list[dict[str, Any]] = []
    for tier, requirements in HardwareInspector.tier_requirements().items():
        rows.append(
            {
                "Tier": tier,
                "RAM Needed (GB)": requirements["ram_gb"],
                "VRAM Needed (GB)": requirements["gpu_vram_gb"],
                "Primary Provider": requirements["provider"],
                "Best Model": requirements["best_model_key"],
                "Current Machine Fits": "yes"
                if snapshot.ram_gb >= requirements["ram_gb"] and snapshot.gpu_vram_gb >= requirements["gpu_vram_gb"]
                else "no",
            }
        )
    st.dataframe(pd.DataFrame(rows), width='stretch')


def _render_hardware_summary(snapshot: HardwareSnapshot, recommended: ModelDescriptor) -> None:
    st.subheader("Hardware Snapshot")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Hardware Tier", snapshot.profile_tier.upper())
    col2.metric("RAM", f"{snapshot.ram_gb:.1f} GB")
    col3.metric("GPU VRAM", f"{snapshot.gpu_vram_gb:.1f} GB")
    col4.metric("Recommended Model", recommended.display_name)
    _render_kv_section(
        "System Details",
        [
            ("Operating System", snapshot.os_name),
            ("CPU", snapshot.cpu_name),
            ("CPU Physical Cores", snapshot.cpu_cores_physical),
            ("CPU Logical Cores", snapshot.cpu_cores_logical),
            ("GPU", snapshot.gpu_name or "No NVIDIA GPU detected"),
            ("Compute Capability", f"{snapshot.compute_capability:.1f}" if snapshot.compute_capability else "Unknown"),
            ("Ollama Installed", snapshot.ollama_installed),
            ("Ollama Running", snapshot.ollama_running),
            ("vLLM Supported", snapshot.vllm_supported),
        ],
        help_map={
            "Operating System": "The current operating system where LUMINA is running.",
            "CPU": "The main processor model used for general computation.",
            "CPU Physical Cores": "Number of real CPU cores available.",
            "CPU Logical Cores": "Total CPU threads available, including hyper-threading.",
            "GPU": "Detected NVIDIA GPU model used for acceleration.",
            "Compute Capability": "NVIDIA architecture capability level required by some GPU runtimes.",
            "Ollama Installed": "Shows whether Ollama is installed on this machine.",
            "Ollama Running": "Shows whether the Ollama service is currently running.",
            "vLLM Supported": "Shows if this runtime can use vLLM on current OS and GPU setup.",
        },
    )
    for note in snapshot.notes:
        st.info(note)
    st.write("What you need for better variants")
    _render_tier_requirements(snapshot)


def _run_guided_setup(
    *,
    setup_service: SetupService,
    snapshot: HardwareSnapshot,
    recommended_model: ModelDescriptor,
    install_unsloth: bool,
    admin_password: str,
) -> list[SetupStepResult]:
    results: list[SetupStepResult] = []
    results.append(setup_service.install_launcher_dependencies())
    results.append(setup_service.install_runtime_dependencies())
    results.append(setup_service.ensure_ollama())
    if results[-1].success:
        results.append(setup_service.pull_model(recommended_model))
    results.append(setup_service.apply_recommended_config(hardware=snapshot, model=recommended_model))
    if install_unsloth:
        results.append(setup_service.install_unsloth_dependencies())
    if admin_password and len(admin_password) >= 12:
        _set_admin_password(admin_password)
        results.append(SetupStepResult("admin_password", True, "Admin password configured"))
    elif admin_password:
        results.append(SetupStepResult("admin_password", False, "Admin password must be at least 12 characters"))
    setup_service.save_status({"steps": [result.to_dict() for result in results]})
    required_ok = all(
        result.success
        for result in results
        if result.name in {"launcher_dependencies", "runtime_dependencies", "ollama", "model_pull", "config_update"}
    )
    if required_ok:
        setup_service.mark_complete(hardware=snapshot, model=recommended_model)
    return results


def _render_setup_wizard(setup_service: SetupService, catalog: ModelCatalog) -> None:
    st.title("LUMINA OS - First Use Setup")
    st.markdown("Deze wizard maakt een nieuwe machine klaar voor de launcher, inference en toekomstig modelbeheer.")
    snapshot = _get_hardware_snapshot()
    recommended_model = catalog.recommended_for(
        ram_gb=snapshot.ram_gb,
        gpu_vram_gb=snapshot.gpu_vram_gb,
        vllm_supported=snapshot.vllm_supported,
    )
    _render_hardware_summary(snapshot, recommended_model)
    st.subheader("Recommended installation plan")
    unsloth_runtime_ready = _runtime_supports_unsloth(snapshot)
    _render_kv_section(
        "Installation Plan",
        [
            ("Provider", recommended_model.recommended_provider),
            ("Model", recommended_model.display_name),
            ("Ollama Tag", recommended_model.ollama_tag),
            ("Context Length", recommended_model.context_length),
            ("Supports Unsloth (Model)", recommended_model.supports_unsloth),
            ("Unsloth Runtime Ready", unsloth_runtime_ready),
        ],
    )
    if recommended_model.supports_unsloth and not unsloth_runtime_ready:
        st.info("Dit model ondersteunt Unsloth, maar deze runtime nog niet. Gebruik Linux/WSL2 met CUDA en sm_70+ GPU voor fine-tuning.")
    install_unsloth = st.checkbox(
        "Install optional Unsloth fine-tuning dependencies",
        value=False,
        help="Only useful on Linux/WSL2 with CUDA. On Windows this normally remains a future step.",
    )
    admin_password = st.text_input(
        "Initial Admin Password",
        type="password",
        help="Optional but strongly recommended during first setup.",
    )
    if st.button("Run Guided Installation", type="primary", width='stretch'):
        results = _run_guided_setup(
            setup_service=setup_service,
            snapshot=snapshot,
            recommended_model=recommended_model,
            install_unsloth=install_unsloth,
            admin_password=admin_password,
        )
        for result in results:
            _render_step_result(result)
        if all(result.success for result in results if result.name != "unsloth_dependencies"):
            st.success("Guided setup completed. Rerun the launcher if newly installed packages were added to the environment.")
    previous_status = setup_service.load_status()
    if previous_status:
        st.subheader("Last setup run")
        steps = previous_status.get("steps", [])
        if isinstance(steps, list) and steps:
            st.dataframe(pd.DataFrame(steps), width='stretch')
    st.info("If package installation changed the environment, rerun Streamlit once so the launcher loads those packages cleanly.")
    st.stop()


def _render_hardware_tab(snapshot: HardwareSnapshot, catalog: ModelCatalog, current_model: ModelDescriptor) -> None:
    recommended = catalog.recommended_for(
        ram_gb=snapshot.ram_gb,
        gpu_vram_gb=snapshot.gpu_vram_gb,
        vllm_supported=snapshot.vllm_supported,
    )
    hardware_fit_badge = _status_badge(snapshot.profile_tier.upper(), "ready")
    ollama_badge = _status_badge("Ready" if snapshot.ollama_running else "Needs Attention", "available" if snapshot.ollama_running else "warning")
    vllm_badge = _status_badge("Ready" if snapshot.vllm_supported else "Blocked", "available" if snapshot.vllm_supported else "blocked")
    st.markdown(f"Hardware Tier {hardware_fit_badge}", unsafe_allow_html=True)
    st.markdown(f"Ollama Runtime {ollama_badge}", unsafe_allow_html=True)
    st.markdown(f"vLLM Path {vllm_badge}", unsafe_allow_html=True)
    _render_hardware_summary(snapshot, recommended)
    if st.button("Refresh Hardware Scan", width='stretch', key="refresh_hardware_scan"):
        refreshed = _refresh_hardware_snapshot()
        st.success(f"Hardware scan refreshed: {refreshed.profile_tier}")
        st.rerun()
    st.subheader("Current model alignment")
    alignment_badge = _status_badge(
        "Recommended" if current_model.key == recommended.key else "Upgrade Suggested",
        "available" if current_model.key == recommended.key else "warning",
    )
    st.markdown(f"Model Alignment {alignment_badge}", unsafe_allow_html=True)
    _render_kv_section(
        "Model Alignment Details",
        [
            ("Current Model", current_model.display_name),
            ("Recommended Model", recommended.display_name),
            ("Provider", recommended.recommended_provider),
        ],
        help_map={
            "Current Model": "The model currently configured for reasoning and decisions.",
            "Recommended Model": "Best-fit model for your current hardware profile.",
            "Provider": "Inference engine used to run the recommended model.",
        },
    )


def _render_model_management_tab(
    *,
    setup_service: SetupService,
    catalog: ModelCatalog,
    snapshot: HardwareSnapshot,
    current_model: ModelDescriptor,
) -> None:
    installed_models = ModelCatalog.installed_ollama_models()
    recommended_model = catalog.recommended_for(
        ram_gb=snapshot.ram_gb,
        gpu_vram_gb=snapshot.gpu_vram_gb,
        vllm_supported=snapshot.vllm_supported,
    )
    st.subheader("Model Management")
    current_badge = _status_badge(current_model.recommended_tier.upper(), "ready")
    recommended_badge = _status_badge(
        "Installed" if recommended_model.ollama_tag in installed_models else "Not Installed",
        "available" if recommended_model.ollama_tag in installed_models else "warning",
    )
    upgrade_badge = _status_badge(
        "On Track" if current_model.key == recommended_model.key else "Heavier Option Available",
        "available" if current_model.key == recommended_model.key else "warning",
    )
    st.markdown(f"Current Tier Target {current_badge}", unsafe_allow_html=True)
    st.markdown(f"Recommended Model Status {recommended_badge}", unsafe_allow_html=True)
    st.markdown(f"Upgrade Outlook {upgrade_badge}", unsafe_allow_html=True)
    _render_kv_section(
        "Catalog Summary",
        [
            ("Catalog Version", catalog.version()),
            ("Current Model", current_model.display_name),
            ("Installed Ollama Models", ", ".join(installed_models) if installed_models else "None"),
            ("Recommended Model", recommended_model.display_name),
        ],
        help_map={
            "Catalog Version": "Version of the local model catalog used by the launcher.",
            "Current Model": "Model currently active in your configuration.",
            "Installed Ollama Models": "Models already downloaded and available in Ollama.",
            "Recommended Model": "Model suggested for your hardware and runtime.",
        },
    )
    rows = [
        {
            "Key": model.key,
            "Name": model.display_name,
            "Tier": model.recommended_tier,
            "Provider": model.recommended_provider,
            "Min RAM GB": model.ram_min_gb,
            "Min VRAM GB": model.vram_min_gb,
            "Tested": model.tested_by_lumina,
        }
        for model in catalog.models()
    ]
    st.dataframe(pd.DataFrame(rows), width='stretch')
    upgrade_targets = catalog.upgrade_targets(current_model.key)
    if not upgrade_targets:
        st.info("No higher upgrade targets registered for the current model.")
    else:
        target_labels = {f"{item.display_name} ({item.ollama_tag})": item.key for item in upgrade_targets}
        selected_label = st.selectbox("Upgrade target", list(target_labels.keys()))
        selected_model = catalog.get(target_labels[selected_label])
        if selected_model is not None:
            fits_hardware = snapshot.ram_gb >= selected_model.ram_min_gb and snapshot.gpu_vram_gb >= selected_model.vram_min_gb
            if fits_hardware:
                st.success("This upgrade fits the current machine.")
            else:
                st.warning("This upgrade is heavier than the current machine recommendation. The launcher still shows what hardware is needed.")
            st.write(selected_model.upgrade_notes)
            if st.button("Install or Upgrade Selected Model", type="primary", width='stretch'):
                results = setup_service.upgrade_model(selected_model)
                for result in results:
                    _render_step_result(result)
                _save_catalog_state(catalog, selected_model.key)
    if st.button("Install Recommended Model For This Hardware", width='stretch'):
        results = setup_service.upgrade_model(recommended_model)
        for result in results:
            _render_step_result(result)
        _save_catalog_state(catalog, recommended_model.key)


def _render_training_panel(current_model: ModelDescriptor, snapshot: HardwareSnapshot) -> None:
    trainer = ModelTrainer()
    report = trainer.inspect_environment()
    pipeline = trainer.build_full_pipeline_commands(
        base_model=current_model.ollama_tag,
        output_dir=Path("state/unsloth-output"),
        model_name="lumina-qwen-custom",
    )
    llama_cpp = trainer.inspect_llama_cpp_toolchain()
    gate = trainer.action_gate_status(
        gguf_path=Path(str(pipeline["gguf"])),
        modelfile_path=Path(str(pipeline["modelfile"])),
    )
    st.subheader("Unsloth Fine-Tuning")
    st.write(report.to_dict())
    if report.supported:
        st.success("Training environment supports the next Unsloth step.")
    else:
        for reason in report.reasons:
            st.warning(reason)
    if st.button("Build Dataset Preview", width='stretch'):
        preview_path = trainer.build_training_dataset()
        st.success(f"Dataset preview written to {preview_path}")
    preview_path = Path("state/finetune_dataset_preview.jsonl")
    if preview_path.exists():
        st.code(preview_path.read_text(encoding="utf-8", errors="replace")[:4000])
    st.write("Prepared training, export, and registration commands")
    st.code(" ".join(pipeline["train"]))
    st.code(" ".join(pipeline["export"]))
    st.code(" ".join(pipeline["register"]))
    st.caption(f"Modelfile: {pipeline['modelfile']}")
    st.caption(f"GGUF target: {pipeline['gguf']}")
    st.write("llama.cpp toolchain")
    st.write(llama_cpp)
    prepare_badge = _status_badge("Available" if gate["can_prepare_toolchain"] else "Blocked", "available" if gate["can_prepare_toolchain"] else "blocked")
    export_badge = _status_badge("Available" if gate["can_export"] else "Blocked", "available" if gate["can_export"] else "blocked")
    register_badge = _status_badge("Ready" if gate["can_register"] else "Blocked", "ready" if gate["can_register"] else "blocked")
    if not gate["linux_or_wsl2"]:
        st.info("Toolchain, export, and registration actions are blocked on this runtime. Use Linux or WSL2 to continue.")
    st.markdown(f"Prepare llama.cpp Toolchain {prepare_badge}", unsafe_allow_html=True)
    _render_guarded_action_button(
        label="Prepare llama.cpp Toolchain",
        allowed=bool(gate["can_prepare_toolchain"]),
        reason=str(gate["prepare_reason"]),
        command=list(llama_cpp["setup_command"]),
        trainer=trainer,
        current_model=current_model,
        snapshot=snapshot,
        action_key="prepare_llama_cpp_toolchain",
    )
    st.caption(str(gate["prepare_reason"]))
    st.markdown(f"Run GGUF Export {export_badge}", unsafe_allow_html=True)
    _render_guarded_action_button(
        label="Run GGUF Export",
        allowed=bool(gate["can_export"]),
        reason=str(gate["export_reason"]),
        command=list(pipeline["export"]),
        trainer=trainer,
        current_model=current_model,
        snapshot=snapshot,
        action_key="run_gguf_export",
    )
    st.caption(str(gate["export_reason"]))
    st.markdown(f"Register Model In Ollama {register_badge}", unsafe_allow_html=True)
    _render_guarded_action_button(
        label="Register Model In Ollama",
        allowed=bool(gate["can_register"]),
        reason=str(gate["register_reason"]),
        command=list(pipeline["register"]),
        trainer=trainer,
        current_model=current_model,
        snapshot=snapshot,
        action_key="register_model_in_ollama",
    )
    st.caption(str(gate["register_reason"]))
    st.write("What still depends on the correct environment")
    for instruction in trainer.create_export_instructions(base_model=current_model.ollama_tag, output_dir=Path("state/unsloth-output")):
        st.write(f"- {instruction}")


# ── Headless entry point (injected before Streamlit UI body) ───────────────────

def _headless_main() -> None:
    """Delegate headless launcher runtime to the central runtime entrypoint."""
    from lumina_core.engine.runtime_entrypoint import run_with_mode

    exit_code = run_with_mode("sim", argv=list(sys.argv[1:]))
    if exit_code != 0:
        raise SystemExit(exit_code)


# ── Headless entry point (injected before Streamlit UI body) ───────────────────
if _IS_HEADLESS:
    _headless_main()
    sys.exit(0)

setup_service = SetupService(config_path=CONFIG_PATH, env_path=ENV_PATH)
catalog = ModelCatalog()
if setup_service.is_first_run():
    _render_setup_wizard(setup_service, catalog)

snapshot = _get_hardware_snapshot()
config_payload = _load_yaml_config()
current_model_key = _find_model_key_for_reasoning_model(catalog, config_payload)
current_model = catalog.get(current_model_key) or catalog.models()[0]
catalog_state = _load_catalog_state()
if catalog_state.get("catalog_version") != catalog.version():
    _save_catalog_state(catalog, current_model.key)

st.title("LUMINA OS - Start Screen")
st.markdown("**Trading runtime, hardware-aware model selection, and controlled launch operations in one control plane.**")

recommended_start_model = catalog.recommended_for(
    ram_gb=snapshot.ram_gb,
    gpu_vram_gb=snapshot.gpu_vram_gb,
    vllm_supported=snapshot.vllm_supported,
)

with st.sidebar:
    st.header("Bot Configuration")
    trade_mode_options = _available_launcher_trade_modes()
    trade_mode = st.selectbox(
        "Trading Mode",
        options=trade_mode_options,
        index=0,
        help="Paper = simulatie | Sim = demo account | Sim Real Guard = sim-account met real guards | Real = echt geld",
    )
    risk_profile = st.selectbox("Risk Profile", options=["Conservative", "Balanced", "Aggressive"], index=1)
    instrument = st.selectbox("Instrument", options=["MES JUN26", "MNQ JUN26", "MYM JUN26", "ES JUN26"], index=0)
    voice_enabled = st.checkbox("Voice (TTS + input)", value=True)
    screen_share_enabled = st.checkbox("Live Chart Screen Share", value=True)
    dashboard_enabled = st.checkbox("Dashboard", value=True)
    st.divider()
    if st.button("Save Config and Start Bot", type="primary", width='stretch'):
        broker_backend = "paper" if trade_mode == "paper" else "live"
        account_mode = {
            "paper": "paper",
            "sim": "sim",
            "sim_real_guard": "sim",
            "real": "real",
        }.get(trade_mode, "paper")
        cfg_updates = {
            "TRADE_MODE": trade_mode,
            "LUMINA_MODE": trade_mode,
            "BROKER_BACKEND": broker_backend,
            "TRADERLEAGUE_ACCOUNT_MODE": account_mode,
            "ENABLE_SIM_REAL_GUARD": "true" if trade_mode == "sim_real_guard" else str(os.getenv("ENABLE_SIM_REAL_GUARD", "false")).lower(),
            "LUMINA_RISK_PROFILE": risk_profile.lower(),
            "INSTRUMENT": instrument,
            "VOICE_ENABLED": str(voice_enabled).lower(),
            "SCREEN_SHARE_ENABLED": str(screen_share_enabled).lower(),
            "DASHBOARD_ENABLED": str(dashboard_enabled).lower(),
        }
        _write_env_file(ENV_PATH, cfg_updates)
        ok, msg = _start_bot_process()
        if ok:
            st.session_state["last_start_ts"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state["screen_share_enabled"] = bool(screen_share_enabled)
            st.session_state["dashboard_enabled"] = bool(dashboard_enabled)
            st.success(msg)
            st.info("Services are starting. Check 'Live Activity & Services' on the main screen for live heartbeat.")
        else:
            st.error(msg)
    if st.button("Stop Bot", width='stretch'):
        ok, msg = _stop_bot_process()
        if ok:
            st.info(msg)
        else:
            st.error(msg)
    st.divider()
    st.subheader("Current Hardware")
    recommended_model = catalog.recommended_for(
        ram_gb=snapshot.ram_gb,
        gpu_vram_gb=snapshot.gpu_vram_gb,
        vllm_supported=snapshot.vllm_supported,
    )
    st.caption(f"Tier: {snapshot.profile_tier} | GPU VRAM: {snapshot.gpu_vram_gb:.1f} GB | RAM: {snapshot.ram_gb:.1f} GB")
    st.caption(f"Recommended model: {recommended_model.display_name}")
    st.divider()
    st.subheader("Admin Access")
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False
    admin_record_exists = _load_admin_password_record() is not None
    if not admin_record_exists:
        st.warning("Admin password is not configured")
    else:
        admin_password_input = st.text_input("Admin Password", type="password", key="admin_access_password")
        col_admin_a, col_admin_b = st.columns(2)
        if col_admin_a.button("Unlock", width='stretch'):
            if _verify_admin_password(admin_password_input):
                st.session_state.admin_authenticated = True
                st.success("Admin unlocked")
            else:
                st.error("Invalid admin password")
        if col_admin_b.button("Lock", width='stretch'):
            st.session_state.admin_authenticated = False
            st.info("Admin locked")
    admin_mode = bool(st.session_state.get("admin_authenticated", False))
    st.caption(f"Mode: {'Admin' if admin_mode else 'User'}")

alive = _process_is_alive()
runtime_label = "Running" if alive else "Ready"
runtime_status = "available" if alive else "warning"
runtime_value = "Active bot process" if alive else "Configure in sidebar and start"
if alive:
    bot_proc = st.session_state.get("bot_process")
    persisted = _load_process_state()
    pid = getattr(bot_proc, "pid", None) or persisted.get("pid") or "unknown"
    runtime_value = f"Active bot process (pid={pid})"

st.markdown(f"Runtime Status {_status_badge(runtime_label, runtime_status)}", unsafe_allow_html=True)
_render_kv_section(
    "Operations Overview",
    [
        ("Runtime", runtime_value),
        ("Hardware Tier", snapshot.profile_tier.upper()),
        ("Hardware Envelope", f"RAM {snapshot.ram_gb:.1f} GB | GPU VRAM {snapshot.gpu_vram_gb:.1f} GB"),
        ("Recommended Model", recommended_start_model.display_name),
        ("vLLM Path", "Ready" if snapshot.vllm_supported else "Blocked on current runtime"),
    ],
)
st.caption(
    "Beast profile requires 64 GB RAM, 20 GB VRAM, and Linux/WSL2 CUDA support for vLLM and Unsloth operations."
)

env_flags = _parse_env_file(ENV_PATH)
screen_share_flag = str(env_flags.get("SCREEN_SHARE_ENABLED", "true")).strip().lower() == "true"
dashboard_flag = str(env_flags.get("DASHBOARD_ENABLED", "true")).strip().lower() == "true"
screen_share_active = bool(st.session_state.get("screen_share_enabled", screen_share_flag))
dashboard_active = bool(st.session_state.get("dashboard_enabled", dashboard_flag))
_render_live_activity_panel(alive=alive, screen_share_enabled=screen_share_active, dashboard_enabled=dashboard_active)

state = _load_runtime_state()
current_dream = state.get("current_dream", {}) if isinstance(state.get("current_dream"), dict) else {}
active_mode = _current_launcher_mode()
tab_labels = [
    "Live Trader View",
    "Hardware & Install",
    "Model Management",
    "Trader League",
    "Community Bibles",
    "Performance Reports",
]
if active_mode == "sim":
    tab_labels.append("🚀 SIM Evolution Dashboard")
if active_mode == "real":
    tab_labels.append("🛡️ REAL Operations Dashboard")
if admin_mode:
    tab_labels.append("Admin / Backend")
tabs = st.tabs(tab_labels)
tab1 = tabs[0]
tab2 = tabs[1]
tab3 = tabs[2]
tab4 = tabs[3]
tab5 = tabs[4]
tab6 = tabs[5]
tab7 = None
tab8 = None
next_optional_idx = 6
if active_mode in {"sim", "real"} and len(tabs) > next_optional_idx:
    tab7 = tabs[next_optional_idx]
    next_optional_idx += 1
if admin_mode and len(tabs) > next_optional_idx:
    tab8 = tabs[next_optional_idx]

with tab1:
    st.subheader("Live Dream + Runtime State")
    if current_dream:
        _render_live_runtime_card(current_dream)
    else:
        st.info("Nog geen runtime state gevonden in state/lumina_sim_state.json")
    col1, col2, col3 = st.columns(3)
    col1.metric("Sim Position Qty", value=state.get("sim_position_qty", 0))
    col2.metric("Live Position Qty", value=state.get("live_position_qty", 0))
    col3.metric("Pending Reconciliations", value=len(state.get("pending_trade_reconciliations", []) or []))

with tab2:
    _render_hardware_tab(snapshot, catalog, current_model)

with tab3:
    _render_model_management_tab(setup_service=setup_service, catalog=catalog, snapshot=snapshot, current_model=current_model)

with tab4:
    st.subheader("Trader League Leaderboard")
    try:
        leaderboard_payload = _backend_get("/leaderboard")
        leaderboard = leaderboard_payload.get("leaderboard", [])
        if isinstance(leaderboard, list) and leaderboard:
            st.dataframe(pd.DataFrame(leaderboard), width='stretch')
        else:
            st.info("Leaderboard is leeg")
    except Exception as exc:
        _render_backend_unavailable_card("Trader League", exc)

with tab5:
    st.subheader("Global Community Bibles")
    try:
        wisdom_payload = _backend_get("/global_wisdom")
        top_bibles = wisdom_payload.get("top_bibles", [])
        if isinstance(top_bibles, list) and top_bibles:
            st.dataframe(pd.DataFrame(top_bibles), width='stretch')
        else:
            st.info("Nog geen community bible data")
    except Exception as exc:
        _render_backend_unavailable_card("Community Bibles", exc)

with tab6:
    st.subheader("Ultimate Performance Validation")
    if st.button("Run 3-Year Validation Now"):
        try:
            runtime_context = _build_validation_context()
            validator = PerformanceValidator(engine=runtime_context.engine)  # engine via ApplicationContainer
            report = validator.run_3year_validation()
            st.json(report)
        except Exception as exc:
            st.error(f"Validation failed: {exc}")
    reports_dir = Path("journal/reports")
    if reports_dir.exists():
        st.write("Recent reports")
        _render_reports_section(reports_dir)

if tab7 is not None:
    with tab7:
        if active_mode == "sim":
            _render_sim_learning_tab()
        elif active_mode == "real":
            _render_real_operations_tab(state)

if tab8 is not None:
    with tab8:
        st.subheader("Admin Backend")
        st.write("Runtime entry:")
        st.code(str(RUNTIME_ENTRY))
        st.write("Log tail (lumina_full_log.csv):")
        log_tail = _tail_file(LUMINA_LOG_PATH, max_chars=6000)
        if log_tail:
            st.code(log_tail)
        else:
            st.info("Nog geen logdata gevonden")
        st.divider()
        support_log_tail = _tail_file(SUPPORT_EVENTS_PATH, max_chars=4000)
        if support_log_tail:
            st.write("Recent blocked action support log:")
            st.code(support_log_tail)
            st.caption(str(SUPPORT_EVENTS_PATH))
        _render_training_panel(current_model, snapshot)
        st.divider()
        st.write("Wijzig admin wachtwoord")
        current_password = st.text_input("Current Password", type="password", key="admin_pwd_current")
        new_password = st.text_input("New Password", type="password", key="admin_pwd_new")
        confirm_password = st.text_input("Confirm New Password", type="password", key="admin_pwd_confirm")
        if st.button("Update Admin Password", width='stretch'):
            if not _verify_admin_password(current_password):
                st.error("Current password is incorrect")
            elif len(new_password) < 12:
                st.error("New password must be at least 12 characters")
            elif new_password != confirm_password:
                st.error("New password confirmation does not match")
            else:
                _set_admin_password(new_password)
                st.success("Admin wachtwoord is bijgewerkt")

st.caption("LUMINA OS v3.6 - guided setup, hardware-aware models, and future-ready fine-tuning.")
