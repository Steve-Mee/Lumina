"""
React dashboard enrichment + lokale dev CORS-hulp voor de FastAPI-backend.

De Vite SPA draait doorgaans op http://localhost:5173 en proxied naar :8000.
Dit module:
    * beschrijft `REACT_LOCAL_DEV_ORIGINS` die runtime aan `CORSMiddleware` worden toegevoegd,
    * bouwt `_lumina_ui` — een platte snapshot met dashboard-velden die ``useLuminaMetrics``
      (``frontend/src/hooks/useLuminaMetrics.ts``) direct kan normaliseren.

Injectie van echte training data
---------------------------------
Voor productie-metrics uit je PPO / infinite sim loop kun je óf Prometheus gauges zetten
(zie naamgeving onder **Prometheus-alias**) óf state-files bijwerken:

1. **``state/lumina_birth_progress.json``** (fallback ``state/first_boot_progress.json``) —
   bv. ``trades`` / ``sim_trades``, ``phase`` /
   ``stage``, ``actual_real_days_loaded``, ``estimated_real_days``,
   ``synthetic_blend_pct``, ``ppo_steps`` (custom keys worden hieronder gelezen indien aanwezig).
2. **``state/ppo_policy_metadata.json``** — bv. ``total_training_steps`` (wordt gebruikt als
   ``ppo_steps`` wanneer geen Prometheus-tegenhanger beschikbaar is).
3. **``ObservabilityService.collector`** — registreer zelf gauges/counters zoals
   ``lumina_ppo_training_steps_total``, ``lumina_hardware_cpu_pct``,
   ``lumina_training_eta_minutes``, ``lumina_approval_twin_reward``, enz.
   Deze waarden overrulen automatisch file-gebaseerde fallbacks waar beide aanwezig zijn
   volgens onderstaande prioriteit.

Prioriteit bij samenvoegen: **Prometheus-snapshot → state files → veilige defaults**
(voor ETA: ``None`` (= JSON ``null``) wanneer onbekend).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from lumina_core.first_boot_progress import (
    resolve_effective_first_boot_target_trades,
    resolve_ppo_training_progress,
    resolve_first_boot_completed_trades,
    resolve_first_boot_stage,
    resolve_first_boot_target_trades,
)
from lumina_core.runtime_session import resolve_runtime_session_state

logger = logging.getLogger(__name__)

# ── Vite / React SPA (development) ─────────────────────────────────────────────
REACT_LOCAL_DEV_ORIGINS: tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # Tauri Neural Command Deck (vite.config.ts strictPort 1420)
    "http://localhost:1420",
    "http://127.0.0.1:1420",
    # Tauri 2 production webview origins
    "https://tauri.localhost",
    "http://tauri.localhost",
)

# ── Canonical UI keys consumed by frontend useLuminaMetrics ───────────────────
LUMINA_UI_FIELDS: tuple[str, ...] = (
    "trades_completed",
    "training_completed_trades",
    "training_target_trades",
    "first_boot_stage",
    "ppo_steps",
    "ppo_timesteps_total",
    "ppo_progress_pct",
    "approval_twin_reward",
    "cpu",
    "gpu",
    "ram",
    "velocity",
    "phase",
    "historical_days",
    "synthetic_percent",
    "eta_minutes",
    "session_kind",
    "session_active",
    "training_target_applicable",
    "last_activity_ts",
    "activity_stale",
    "birth_certificate_ok",
    "birth_oos_sharpe",
)

_PROM_APPROVAL_NAMES = ("lumina_approval_twin_reward", "lumina_approval_twin_avg_reward")
_PROM_PPO_STEP_NAMES = ("lumina_ppo_training_steps_total", "lumina_ppo_steps_total")
_PROM_TRADE_NAMES = ("lumina_trades_completed_total", "lumina_model_decisions_total")
_PROM_CPU = ("lumina_hardware_cpu_pct", "lumina_cpu_percent")
_PROM_GPU = ("lumina_hardware_gpu_pct", "lumina_gpu_percent")
_PROM_RAM = ("lumina_hardware_ram_pct", "lumina_ram_percent")
_PROM_VELOCITY = ("lumina_training_velocity_trades_per_s", "lumina_training_throughput_ticks_per_s")
_PROM_SYNTH = ("lumina_training_synthetic_ratio_pct",)
_PROM_ETA = ("lumina_training_eta_minutes", "lumina_eta_minutes_remaining")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            return str(pid) in (result.stdout or "")
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _runtime_alive_from_state(state_dir: Path) -> bool:
    state_path = state_dir / "launcher_bot_process.json"
    if not state_path.exists():
        return False
    try:
        payload = _safe_read_json(state_path)
        pid = int(payload.get("pid", 0) or 0)
    except Exception:
        return False
    return _pid_alive(pid)


def extend_cors_origins_with_local_vite_dev(existing: Iterable[str]) -> list[str]:
    """Voeg lokale Vite-/React-origin(s) toe indien nog niet aanwezig (duplicate-safe).

    Extra origins kunnen optioneel gezet worden via:
    ``LUMINA_EXTRA_CORS_ORIGINS="http://localhost:4173,http://devbox:5173"``.
    """

    def norm_key(origin: str) -> str:
        return origin.strip().rstrip("/").lower()

    merged: list[str] = []
    keys: set[str] = set()
    for raw in existing:
        o = str(raw).strip()
        if not o:
            continue
        k = norm_key(o)
        if k not in keys:
            keys.add(k)
            merged.append(o)

    configured_extra = os.environ.get("LUMINA_EXTRA_CORS_ORIGINS", "")
    extra_origins = tuple(item.strip() for item in configured_extra.split(",") if item.strip())

    for o in (*REACT_LOCAL_DEV_ORIGINS, *extra_origins):
        k = norm_key(o)
        if k not in keys:
            keys.add(k)
            merged.append(o)

    return merged


def default_repo_root() -> Path:
    """``lumina_os/api/monitoring.py`` → repo root (= parent van ``lumina_os``)."""
    return Path(__file__).resolve().parents[2]


def resolve_state_directory() -> Path:
    raw = os.environ.get("LUMINA_STATE_DIR", "").strip()
    if raw:
        return Path(raw)
    return default_repo_root() / "state"


def _safe_read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Skipping unreadable JSON %s: %s", path, exc)
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _safe_read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        logger.debug("Skipping unreadable YAML %s: %s", path, exc)
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _last_json_object_from_jsonl(path: Path) -> dict[str, Any]:
    """Return last decoded JSON object on a line from a JSONL file (best-effort)."""
    if not path.is_file():
        return {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    for line in reversed(lines):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        try:
            row = json.loads(line_stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            return row
    return {}


def _collector_entry_float(entry: dict[str, Any]) -> float:
    try:
        return float(entry.get("value", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _sum_matching_metric_keys(snapshot: dict[str, Any], base_names: tuple[str, ...]) -> float | None:
    """Sum Prometheus collector blobs keyed ``name`` or ``name{labels}``."""
    total = 0.0
    hit = False
    for key, payload in snapshot.items():
        if key == "_meta" or not isinstance(payload, dict):
            continue
        for base in base_names:
            if key == base or key.startswith(f"{base}{{"):
                total += _collector_entry_float(payload)
                hit = True
                break
    return total if hit else None


def _first_metric_positive(snapshot: dict[str, Any], base_names: tuple[str, ...]) -> float | None:
    """Return first summed series for aliases (same as sum for single-series metrics)."""
    return _sum_matching_metric_keys(snapshot, base_names)


def _clamp_pct(v: float) -> float:
    if not isinstance(v, (int, float)) or v != v:
        return 0.0
    return max(0.0, min(100.0, float(v)))


def _phase_from_snapshot(snapshot: dict[str, Any]) -> str:
    """Read active regime label if present."""
    for key, payload in snapshot.items():
        if not key.startswith("lumina_regime_current"):
            continue
        if not isinstance(payload, dict):
            continue
        labels = payload.get("labels")
        if isinstance(labels, dict):
            regime = labels.get("regime") or labels.get("phase")
            if regime is not None and str(regime).strip():
                return str(regime).strip()
    return ""


def _coerce_eta_minutes(snapshot: dict[str, Any]) -> float | None:
    v = _first_metric_positive(snapshot, _PROM_ETA)
    return v if v is not None and v >= 0 and v == v else None  # filter NaN




__all__ = [
    "LUMINA_UI_FIELDS",
    "REACT_LOCAL_DEV_ORIGINS",
    "enrich_observability_snapshot_for_react_dashboard",
    "extend_cors_origins_with_local_vite_dev",
    "resolve_state_directory",
]

from lumina_os.api.monitoring_enrich import enrich_observability_snapshot_for_react_dashboard  # noqa: F401
