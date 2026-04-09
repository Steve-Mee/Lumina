"""
lumina_core/config_loader.py
============================
Centralized config.yaml loader — single read per process.

All modules that need YAML config should use ConfigLoader.get() instead of
opening config.yaml directly. This eliminates the multiple independent reads
that occurred during startup (EngineConfig, LuminaEngine._load_mode_risk_profile,
ApplicationContainer._init_observability, LocalInferenceEngine).

Internally delegates to engine_config._load_yaml_config() which is already
backed by functools.lru_cache(maxsize=1), so the file is only ever read once
during a process lifetime unless ConfigLoader.invalidate() is called.

LocalInferenceEngine hot-reload: call ConfigLoader.invalidate() then
ConfigLoader.get() to pick up config.yaml changes without a restart.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("lumina.config_loader")

# Strings that look like config placeholders — reject these at startup.
_PLACEHOLDER_PATTERNS = (
    "your_",
    "changeme",
    "<",
    "placeholder",
    "xxx",
    "todo",
    "fixme",
    "insert_",
)

# Required environment variable names.
_REQUIRED_ENV_SECRETS: tuple[str, ...] = (
    "XAI_API_KEY",
    "LUMINA_JWT_SECRET_KEY",
)
# Keys that must be present only when broker_backend == "live".
_LIVE_REQUIRED_ENV: tuple[str, ...] = ("CROSSTRADE_TOKEN",)


def _resolve_config_path() -> Path:
    return Path(os.getenv("LUMINA_CONFIG", "config.yaml"))


class ConfigLoader:
    """Process-scoped config.yaml cache.

    Usage::

        cfg = ConfigLoader.get()            # dict, read once per process
        cfg = ConfigLoader.get(reload=True) # force re-read (e.g. after write)
        ConfigLoader.invalidate()           # mark stale; next get() re-reads
    """

    _cache: dict[str, Any] | None = None

    @classmethod
    def get(cls, *, reload: bool = False) -> dict[str, Any]:
        """Return the parsed config.yaml dict, reading the file at most once.

        Args:
            reload: If True, discard the cached copy and re-read from disk.
        """
        if reload:
            cls.invalidate()

        if cls._cache is None:
            # Delegate to the lru_cache in engine_config so both code paths
            # share one in-memory copy.
            try:
                from lumina_core.engine.engine_config import _load_yaml_config  # noqa: PLC0415
                cls._cache = _load_yaml_config()
            except Exception:  # pragma: no cover
                # Fallback if engine_config is unavailable (e.g. isolated test).
                import yaml  # noqa: PLC0415
                cfg_path = _resolve_config_path()
                if not cfg_path.exists():
                    cls._cache = {}
                else:
                    try:
                        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
                        cls._cache = raw if isinstance(raw, dict) else {}
                    except Exception:
                        cls._cache = {}

        return cls._cache  # type: ignore[return-value]

    @classmethod
    def invalidate(cls) -> None:
        """Discard the cached copy.  Next call to get() will re-read the file."""
        cls._cache = None
        # Also clear the lru_cache in engine_config so both stay in sync.
        try:
            from lumina_core.engine.engine_config import _load_yaml_config  # noqa: PLC0415
            _load_yaml_config.cache_clear()
        except Exception:  # pragma: no cover
            pass

    @classmethod
    def section(cls, *keys: str, default: Any = None) -> Any:
        """Retrieve a nested value by key path.

        Example::

            trading = ConfigLoader.section("trading")
            kelly   = ConfigLoader.section("trading", "kelly_fraction_max", default=0.25)
        """
        current: Any = cls.get()
        for key in keys:
            if not isinstance(current, dict):
                return default
            current = current.get(key)
            if current is None:
                return default
        return current

    # ------------------------------------------------------------------
    # Fase 2.2 — Startup validation
    # ------------------------------------------------------------------

    @classmethod
    def validate_startup(cls, *, raise_on_error: bool = True) -> bool:
        """Validate config.yaml + env vars at process startup.

        Checks:
        - Required env secrets are set and non-placeholder
        - CROSSTRADE_TOKEN present when broker_backend == "live"
        - Emits a one-line startup config report to the logger

        Returns True if all checks pass.  If *raise_on_error* is True (default)
        raises RuntimeError on the first hard error.
        """
        cfg = cls.get()
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Required env secrets
        for var in _REQUIRED_ENV_SECRETS:
            val = os.getenv(var, "")
            if not val:
                errors.append(f"Missing required env var: {var}")
            elif any(p in val.lower() for p in _PLACEHOLDER_PATTERNS):
                errors.append(f"Placeholder value detected in env var {var!r}")

        # 2. Live-broker secrets (only when broker is live)
        broker_mode = str(cfg.get("broker_backend", os.getenv("BROKER_BACKEND", "paper"))).lower()
        if broker_mode == "live":
            for var in _LIVE_REQUIRED_ENV:
                val = os.getenv(var, "")
                if not val:
                    errors.append(f"Missing required env var for live broker: {var}")
                elif any(p in val.lower() for p in _PLACEHOLDER_PATTERNS):
                    errors.append(f"Placeholder value in live-broker env var {var!r}")

        # 3. Collect non-secret summary fields for the startup report
        trade_mode = str(cfg.get("trade_mode", os.getenv("TRADE_MODE", "paper"))).lower()
        symbols = cfg.get("swarm_symbols", [])
        model_name = cls.section("inference", "primary_model", default="<unset>")
        log_level = cls.section("logging", "level", default="INFO")

        if errors:
            for err in errors:
                _LOG.error("[ConfigLoader] %s", err)
            if raise_on_error:
                raise RuntimeError(
                    f"Config validation failed ({len(errors)} error(s)): "
                    + "; ".join(errors)
                )
            return False

        if warnings:
            for w in warnings:
                _LOG.warning("[ConfigLoader] %s", w)

        # Startup config report (single INFO line)
        _LOG.info(
            "[ConfigLoader] startup OK | broker=%s trade_mode=%s symbols=%s model=%s log_level=%s",
            broker_mode,
            trade_mode,
            symbols,
            model_name,
            log_level,
        )
        return True
