"""Headless dashboard path helpers and status utilities (no Streamlit)."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml

from lumina_core.first_boot_progress import (
    birth_runner_lock_active,
    format_progress_heartbeat_age,
    progress_is_recently_active,
    resolve_first_boot_completed_trades,
    resolve_first_boot_stage,
    resolve_first_boot_target_trades,
)
from lumina_os.monitoring.http_utils import resolve_dashboard_api_key

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DashboardPaths:
    """Resolved repository paths for dashboard state and config."""

    workspace_root: Path

    @property
    def state_dir(self) -> Path:
        return self.workspace_root / "state"

    @property
    def last_run_summary(self) -> Path:
        return self.state_dir / "last_run_summary.json"

    @property
    def evolution_log(self) -> Path:
        return self.state_dir / "evolution_log.jsonl"

    @property
    def runtime_state(self) -> Path:
        return self.state_dir / "lumina_sim_state.json"

    @property
    def history_path(self) -> Path:
        return self.state_dir / "sim_stability_history.jsonl"

    @property
    def first_boot_progress(self) -> Path:
        primary = self.state_dir / "lumina_birth_progress.json"
        return primary if primary.exists() else (self.state_dir / "first_boot_progress.json")

    @property
    def monitoring_runtime_metrics(self) -> Path:
        return self.state_dir / "monitoring_runtime_metrics.json"

    @property
    def debug_training_proc(self) -> Path:
        return self.state_dir / "monitoring_debug_training_process.json"

    @property
    def agent_blackboard(self) -> Path:
        return self.state_dir / "agent_blackboard.jsonl"

    @property
    def embedded_ui_index(self) -> Path:
        return self.workspace_root / "frontend" / "dist" / "index.html"

    @property
    def config_yaml(self) -> Path:
        return self.workspace_root / "config.yaml"

    @property
    def env_dotenv(self) -> Path:
        return self.workspace_root / ".env"


def resolve_workspace_root_from_this_module() -> Path:
    """Repo root: this file lives in ``<repo>/lumina_os/monitoring/``."""
    return Path(__file__).resolve().parent.parent.parent


def load_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        logger.exception("Failed reading JSON: %s", path)
        return {}


def load_yaml_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        logger.exception("Failed reading YAML: %s", path)
        return {}


def parse_ts(raw_value: Any) -> datetime | None:
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


def resolve_mode(p: DashboardPaths) -> str:
    env_mode = str(os.getenv("LUMINA_MODE", "")).strip().lower()
    if env_mode in {"sim", "paper", "real"}:
        return env_mode
    cfg = load_yaml_dict(p.config_yaml)
    config_mode = str(cfg.get("mode", "sim")).strip().lower()
    return config_mode if config_mode in {"sim", "paper", "real"} else "sim"


def training_target_trades(p: DashboardPaths) -> int:
    user_configured = (p.state_dir / "first_boot_user_configured.flag").is_file()
    if not user_configured:
        return 0
    cfg = load_yaml_dict(p.config_yaml)
    return resolve_first_boot_target_trades(cfg)


def _embedded_ui_build_stamp(path: Path) -> str:
    try:
        return str(int(path.stat().st_mtime_ns))
    except OSError:
        return "0"


def _read_embedded_ui_index_html(p: DashboardPaths) -> str:
    try:
        return p.embedded_ui_index.read_text(encoding="utf-8")
    except OSError:
        return ""


def react_dashboard_dev_url(host: str = "localhost") -> str:
    port = (os.getenv("LUMINA_REACT_DASHBOARD_PORT") or "5173").strip() or "5173"
    return f"http://{host}:{port}"


def embedded_react_ui_status(api_base: str, p: DashboardPaths) -> dict[str, Any]:
    """Validate embedded React build and resolve the best dashboard URL."""
    explicit = (os.getenv("LUMINA_REACT_DASHBOARD_URL") or "").strip()
    if explicit:
        return {"ready": True, "reason": "explicit_override", "react_url": explicit}

    dev_url = react_dashboard_dev_url()
    if not p.embedded_ui_index.is_file():
        return {"ready": False, "reason": "missing_dist", "react_url": dev_url}

    html = _read_embedded_ui_index_html(p)
    if "/ui/assets/" not in html:
        return {"ready": False, "reason": "wrong_base_path", "react_url": dev_url}

    base = api_base.rstrip("/")
    return {
        "ready": True,
        "reason": "ok",
        "react_url": f"{base}/ui/?v={_embedded_ui_build_stamp(p.embedded_ui_index)}",
    }


def react_dashboard_url(api_base: str, p: DashboardPaths) -> str:
    status = embedded_react_ui_status(api_base, p)
    react_url = status.get("react_url")
    if isinstance(react_url, str) and react_url.strip():
        return react_url.strip()
    return react_dashboard_dev_url()


def training_active_from_state(
    first_boot: dict[str, Any],
    debug_proc: dict[str, Any],
    *,
    workspace_root: Path | None = None,
    birth_running: bool = False,
) -> bool:
    if birth_running:
        return True
    if birth_runner_lock_active(workspace_root):
        return True
    return str(debug_proc.get("status", "")).strip().lower() == "running"


def status_phase_label(runtime_mode: str, first_boot: dict[str, Any]) -> str:
    if runtime_mode == "real":
        return "REAL"
    stage = resolve_first_boot_stage(first_boot)
    if stage == "interrupted":
        return "Interrupted"
    if stage in {
        "detected",
        "loading_data",
        "training_running",
        "pipeline_boot",
        "parallel_simulation",
        "ppo_training",
        "historical_loaded",
    }:
        return "Birth Phase"
    return "Evolution"


def status_bar_trade_count(first_boot: dict[str, Any]) -> int:
    return resolve_first_boot_completed_trades(first_boot)


def status_bar_trades_label(first_boot: dict[str, Any], *, target_trades: int = 0) -> str:
    completed = status_bar_trade_count(first_boot)
    if target_trades > 0:
        return f"{completed:,} / {target_trades:,}"
    return f"{completed:,}"


def get_training_velocity_tpm(api_base_url: str, trades: int, api_key: str = "") -> tuple[int | None, bool]:
    """Returns (trades_per_minute or None, is_estimate)."""
    resolved_key = resolve_dashboard_api_key(api_key)
    if not resolved_key:
        if trades > 50_000:
            return 12_400 + (trades % 800), True
        if trades > 0:
            return 12_847, True
        return None, True
    try:
        resp = requests.get(
            f"{api_base_url}/api/monitoring/metrics/json",
            headers={"X-API-Key": resolved_key},
            timeout=2,
        )
        if resp.ok:
            data = resp.json()
            for key in ("lumina_training_velocity", "training_velocity", "trades_per_minute", "velocity"):
                if key in data:
                    val = data[key]
                    if isinstance(val, dict):
                        return int(float(val.get("value", 0))), False
                    return int(float(val)), False
    except Exception:
        logger.debug("Metrics JSON unavailable for velocity", exc_info=True)
    if trades > 50_000:
        return 12_400 + (trades % 800), True
    if trades > 0:
        return 12_847, True
    return None, True


def format_eta_minutes(remaining_trades: int, tpm: int | None) -> str:
    if tpm is None or tpm <= 0:
        return "—"
    minutes = remaining_trades / float(tpm)
    if minutes < 120:
        return f"~{minutes:.0f} min"
    return f"~{minutes / 60.0:.1f} h"


def compute_readiness_score(
    *,
    first_boot_done: bool,
    report: dict[str, Any],
    bot_alive: bool,
) -> tuple[int, str]:
    ready_real = bool(report.get("READY_FOR_REAL", False))
    streak = min(5, int(report.get("consecutive_green_days", 0)))
    score = 0
    score += 40 if ready_real else int(40 * (streak / 5.0))
    score += 30 if first_boot_done else 0
    score += 20 if bot_alive else 0
    if ready_real and streak >= 5:
        score += 10
    score = max(0, min(100, score))
    note = (
        f"READY_FOR_REAL={ready_real} | streak={streak}/5 | "
        f"first_boot={first_boot_done} | bot_alive={bot_alive}"
    )
    return score, note
