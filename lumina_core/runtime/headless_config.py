# CANONICAL IMPLEMENTATION – Lumina v51
# HeadlessRuntime config / duration helpers.
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from lumina_core.config_loader import ConfigLoader
from lumina_core.evolution.simulator_data_support import MIN_SIMULATOR_BARS

logger = logging.getLogger("lumina.headless")

_SUMMARY_SCHEMA_VERSION = "1.0"
_DEFAULT_SIMULATION_SEED = 51


def _resolve_summary_archive_enabled(cfg: dict[str, Any]) -> bool:
    raw = cfg.get("summary_archive_enabled", True)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_summary_archive_dir(cfg: dict[str, Any]) -> Path:
    raw = str(cfg.get("summary_archive_dir", "state/test_runs")).strip()
    return Path(raw) if raw else Path("state/test_runs")


def _load_headless_config() -> dict[str, Any]:
    config_path = Path("config.yaml")
    if not config_path.exists():
        return {}
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/runtime/headless_config.py")
        return {}
    if not isinstance(payload, dict):
        return {}
    section = payload.get("headless")
    return section if isinstance(section, dict) else {}


def _resolve_simulation_seed(cfg: dict[str, Any]) -> int:
    env_seed = os.getenv("LUMINA_HEADLESS_SEED")
    if env_seed is not None:
        try:
            return int(env_seed)
        except ValueError:
            logger.warning("Invalid LUMINA_HEADLESS_SEED=%r; using defaults", env_seed)

    raw = cfg.get("simulation_seed", _DEFAULT_SIMULATION_SEED)
    try:
        seed = int(raw)
    except (TypeError, ValueError):
        seed = _DEFAULT_SIMULATION_SEED

    # Enforce deterministic behavior by default.
    if seed == 0:
        return _DEFAULT_SIMULATION_SEED
    return seed


def _resolve_ticks_per_minute(cfg: dict[str, Any]) -> int:
    raw = cfg.get("ticks_per_minute", 200)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 200
    return max(1, value)


def _resolve_headless_historical_days_back(headless_cfg: dict[str, Any]) -> int:
    raw = headless_cfg.get("historical_days_back")
    if raw is not None and str(raw).strip().lower() not in {"", "null", "none"}:
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            pass
    neuro = ConfigLoader.section("evolution", "neuroevolution", default={}) or {}
    try:
        return max(1, int(neuro.get("fetch_days_back", 90) or 90))
    except (TypeError, ValueError):
        return 90


def _resolve_headless_historical_limit(headless_cfg: dict[str, Any]) -> int:
    raw = headless_cfg.get("historical_limit")
    if raw is not None and str(raw).strip().lower() not in {"", "null", "none"}:
        try:
            return max(MIN_SIMULATOR_BARS, int(raw))
        except (TypeError, ValueError):
            pass
    neuro = ConfigLoader.section("evolution", "neuroevolution", default={}) or {}
    try:
        return max(MIN_SIMULATOR_BARS, int(neuro.get("fetch_limit", 20000) or 20000))
    except (TypeError, ValueError):
        return 20000


def _resolve_sim_learning_duration_minutes(cfg: dict[str, Any]) -> float:
    raw = cfg.get("sim_learning_duration_minutes", 60)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 60.0
    return max(1.0, value)


def _resolve_sim_overnight_mode(cfg: dict[str, Any]) -> bool:
    raw = cfg.get("sim_overnight_mode", False)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_test_bypass_readiness_gate() -> bool:
    return str(os.getenv("LUMINA_TEST_BYPASS_READINESS_GATE", "false")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def parse_duration_minutes(value: str) -> float:
    """
    Parse a duration string like "15m", "5m", "30s", "1h" into minutes.
    Raises ValueError for unrecognised formats.
    """
    value = value.strip().lower()
    if value.endswith("h"):
        return float(value[:-1]) * 60.0
    if value.endswith("m"):
        return float(value[:-1])
    if value.endswith("s"):
        return float(value[:-1]) / 60.0
    # Bare number treated as minutes
    return float(value)

