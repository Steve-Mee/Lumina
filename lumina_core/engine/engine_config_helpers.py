from __future__ import annotations
import logging

import os
from pathlib import Path
import json
from functools import lru_cache
from typing import Any

import yaml


def _resolve_config_yaml_path() -> Path:
    """Resolve config.yaml from LUMINA_CONFIG or cwd (never cache empty wrong-cwd forever)."""
    env = str(os.getenv("LUMINA_CONFIG") or "").strip()
    if env:
        p = Path(env)
        if p.is_file():
            return p.resolve()
        # Allow LUMINA_CONFIG pointing at a workspace directory.
        if p.is_dir() and (p / "config.yaml").is_file():
            return (p / "config.yaml").resolve()
    return (Path.cwd() / "config.yaml").resolve()


@lru_cache(maxsize=8)
def _load_yaml_config_at(path_str: str) -> dict:
    config_path = Path(path_str)
    if not config_path.is_file():
        return {}
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/engine/engine_config_helpers")
        return {}
    return raw if isinstance(raw, dict) else {}


def _load_yaml_config() -> dict:
    """Load workspace config.yaml. Path-aware so wrong first cwd cannot poison SSOT forever."""
    path = _resolve_config_yaml_path()
    data = _load_yaml_config_at(str(path))
    # Never cache a permanent empty miss for a path that may appear after chdir —
    # only positive loads are sticky via lru; empty result: clear that path entry.
    if not data:
        try:
            _load_yaml_config_at.cache_clear()
        except Exception:
            pass
        # Retry once after clear in case of race.
        data = _load_yaml_config_at(str(path)) if path.is_file() else {}
    return data if isinstance(data, dict) else {}


def clear_yaml_config_cache() -> None:
    """Call after chdir / LUMINA_CONFIG change so EngineConfig sees fresh yaml."""
    try:
        _load_yaml_config_at.cache_clear()
    except Exception:
        pass
    # Back-compat: some callers still invoke ``_load_yaml_config.cache_clear()``.
    try:
        setattr(_load_yaml_config, "cache_clear", clear_yaml_config_cache)
    except Exception:
        pass


# Allow ``_load_yaml_config.cache_clear()`` used by config_loader invalidate hooks.
_load_yaml_config.cache_clear = clear_yaml_config_cache  # type: ignore[attr-defined]


def _config_yaml_value(key: str, default):
    config = _load_yaml_config()
    if key in config:
        return config[key]
    trading_cfg = config.get("trading", {}) if isinstance(config.get("trading"), dict) else {}
    return trading_cfg.get(key, default)


def _config_yaml_section_value(section: str, key: str, default):
    config = _load_yaml_config()
    section_cfg = config.get(section)
    if isinstance(section_cfg, dict) and key in section_cfg:
        return section_cfg.get(key, default)
    return default


def _config_yaml_section(section: str) -> dict:
    config = _load_yaml_config()
    section_cfg = config.get(section)
    return section_cfg if isinstance(section_cfg, dict) else {}


def _config_yaml_nested(default, *keys: str):
    current: Any = _load_yaml_config()
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def _env_or_yaml(env_name: str, yaml_key: str, default):
    raw = os.getenv(env_name)
    if raw is not None:
        return raw
    return _config_yaml_value(yaml_key, default)


def _env_or_yaml_bool(env_name: str, yaml_key: str, default: bool) -> bool:
    raw = _env_or_yaml(env_name, yaml_key, default)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() == "true"


def _env_or_yaml_float(env_name: str, yaml_key: str, default: float) -> float:
    raw = _env_or_yaml(env_name, yaml_key, default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def _safe_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _default_trading_instrument() -> str:
    """SSOT: INSTRUMENT env > trading.instrument yaml > non-expired fallback."""
    env = str(os.getenv("INSTRUMENT") or "").strip()
    if env:
        return env.upper()
    yaml_inst = str(_config_yaml_nested("", "trading", "instrument") or "").strip()
    if yaml_inst:
        return yaml_inst.upper()
    return "MES SEP26"


def _parse_swarm_symbols() -> list[str]:
    env_raw = os.getenv("SWARM_SYMBOLS")
    yaml_raw = _config_yaml_nested(None, "trading", "swarm_symbols")
    if env_raw is not None and str(env_raw).strip():
        raw = str(env_raw).strip()
    elif isinstance(yaml_raw, list) and yaml_raw:
        return [str(s).strip().upper() for s in yaml_raw if str(s).strip()] or [
            _default_trading_instrument()
        ]
    elif isinstance(yaml_raw, str) and yaml_raw.strip():
        raw = yaml_raw.strip()
    else:
        # Derive a single-symbol swarm from the primary instrument SSOT.
        return [_default_trading_instrument()]

    symbols: list[str]
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            symbols = [str(s).strip().upper() for s in parsed if str(s).strip()]
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/engine_config.py:92")
            symbols = []
    else:
        symbols = [part.strip().upper() for part in raw.split(",") if part.strip()]

    return symbols or [_default_trading_instrument()]


