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
    "replace_me",
    "example",
)

# Required environment variable names.
_REQUIRED_ENV_SECRETS: tuple[str, ...] = (
    "XAI_API_KEY",
    "LUMINA_JWT_SECRET_KEY",
)
# Keys that must be present only when broker_backend == "live".
_LIVE_REQUIRED_ENV: tuple[str, ...] = ("CROSSTRADE_TOKEN",)


def _looks_like_placeholder(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return True
    if text.startswith("${") and text.endswith("}"):
        return True
    return any(p in text for p in _PLACEHOLDER_PATTERNS)


def _normalize_mode(value: Any, default: str) -> str:
    text = str(value or "").strip().lower()
    if text in {"paper", "sim", "sim_real_guard", "real"}:
        return text
    return default


def _normalize_broker_backend(value: Any, default: str) -> str:
    text = str(value or "").strip().lower()
    if text in {"paper", "live"}:
        return text
    return default


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
                logging.exception("Unhandled broad exception fallback in lumina_core/config_loader.py:107")
                import yaml  # noqa: PLC0415

                cfg_path = _resolve_config_path()
                if not cfg_path.exists():
                    cls._cache = {}
                else:
                    try:
                        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
                        cls._cache = raw if isinstance(raw, dict) else {}
                    except Exception:
                        logging.exception("Unhandled broad exception fallback in lumina_core/config_loader.py:118")
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
            logging.exception("Unhandled broad exception fallback in lumina_core/config_loader.py:132")
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
    def _resolve_runtime_modes(cls, cfg: dict[str, Any]) -> tuple[str, str]:
        env_override = str(os.getenv("LUMINA_ENFORCE_ENV_RUNTIME_MODE", "false")).strip().lower() == "true"
        if env_override:
            trade_mode_raw = (
                os.getenv("TRADE_MODE")
                or os.getenv("LUMINA_MODE")
                or cfg.get("trade_mode")
                or cfg.get("mode")
                or cls.section("launcher", "default_mode", default="paper")
            )
            broker_mode_raw = (
                os.getenv("BROKER_BACKEND")
                or cfg.get("broker_backend")
                or cls.section("broker", "backend", default=None)
                or cls.section("launcher", "default_broker", default="paper")
            )
        else:
            trade_mode_raw = (
                cfg.get("trade_mode")
                or cfg.get("mode")
                or os.getenv("TRADE_MODE")
                or os.getenv("LUMINA_MODE")
                or cls.section("launcher", "default_mode", default="paper")
            )
            broker_mode_raw = (
                cfg.get("broker_backend")
                or cls.section("broker", "backend", default=None)
                or os.getenv("BROKER_BACKEND")
                or cls.section("launcher", "default_broker", default="paper")
            )

        trade_mode = _normalize_mode(trade_mode_raw, "paper")
        broker_mode = _normalize_broker_backend(broker_mode_raw, "paper")
        return trade_mode, broker_mode

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

        security_cfg = cls.section("security", default={})
        strict_secret_hygiene = bool(
            (security_cfg.get("strict_secret_hygiene", False) if isinstance(security_cfg, dict) else False)
        )

        # 1. Required env secrets
        for var in _REQUIRED_ENV_SECRETS:
            val = os.getenv(var, "")
            if not val:
                if strict_secret_hygiene:
                    errors.append(f"Missing required env var: {var}")
                else:
                    warnings.append(f"Missing env var (non-strict mode): {var}")
            elif _looks_like_placeholder(val):
                if strict_secret_hygiene:
                    errors.append(f"Placeholder value detected in env var {var!r}")
                else:
                    warnings.append(f"Placeholder-like env value detected (non-strict): {var!r}")

        # 2. Live-broker secrets (only when broker is live)
        trade_mode, broker_mode = cls._resolve_runtime_modes(cfg)

        # 2a. Dark-launch feature flag for SIM_REAL_GUARD.
        sim_real_guard_enabled = str(os.getenv("ENABLE_SIM_REAL_GUARD", "false")).strip().lower() == "true"
        if trade_mode == "sim_real_guard" and not sim_real_guard_enabled:
            errors.append("sim_real_guard is disabled by feature flag: set ENABLE_SIM_REAL_GUARD=true")

        # 2b. Canonical mode/broker matrix validation.
        # paper => broker backend must remain paper (never real routing).
        # sim/sim_real_guard/real => backend must be live to preserve canonical execution semantics.
        if trade_mode == "paper" and broker_mode != "paper":
            errors.append("Invalid mode matrix: trade_mode=paper requires broker_backend=paper")
        if trade_mode in {"sim", "sim_real_guard", "real"} and broker_mode != "live":
            errors.append(f"Invalid mode matrix: trade_mode={trade_mode} requires broker_backend=live")

        # 2c. Live-broker secrets when a live backend is active.
        hard_secret_mode = (trade_mode == "real") or strict_secret_hygiene
        if broker_mode == "live":
            for var in _LIVE_REQUIRED_ENV:
                val = os.getenv(var, "")
                if not val:
                    if hard_secret_mode:
                        errors.append(f"Missing required env var for live broker: {var}")
                    else:
                        warnings.append(f"Missing live-broker env var (advisory mode): {var}")
                elif _looks_like_placeholder(val):
                    if hard_secret_mode:
                        errors.append(f"Placeholder value in live-broker env var {var!r}")
                    else:
                        warnings.append(f"Placeholder live-broker env value (advisory mode): {var!r}")

        # 2d. Detect placeholder/default API keys in active security config.
        api_keys = {}
        if isinstance(security_cfg, dict):
            raw_api_keys = security_cfg.get("api_keys", {})
            if isinstance(raw_api_keys, dict):
                api_keys = raw_api_keys
        for api_key, meta in api_keys.items():
            enabled = bool(meta.get("enabled", True)) if isinstance(meta, dict) else True
            if not enabled:
                continue
            if _looks_like_placeholder(api_key):
                msg = f"Placeholder/default API key active in security.api_keys: {api_key!r}"
                if hard_secret_mode:
                    errors.append(msg)
                else:
                    warnings.append(msg)

        # 3. Collect non-secret summary fields for the startup report
        symbols = cfg.get("swarm_symbols", [])
        model_name = cls.section("inference", "primary_model", default="<unset>")
        log_level = cls.section("logging", "level", default="INFO")

        if errors:
            for err in errors:
                _LOG.error("[ConfigLoader] %s", err)
            if raise_on_error:
                raise RuntimeError(f"Config validation failed ({len(errors)} error(s)): " + "; ".join(errors))
            return False

        if warnings:
            for w in warnings:
                _LOG.warning("[ConfigLoader] %s", w)

        secret_hygiene_status = "pass" if not errors and not warnings else ("fail" if errors else "warn")

        # Startup config report (single INFO line)
        _LOG.info(
            "[ConfigLoader] startup OK | broker=%s trade_mode=%s symbols=%s model=%s log_level=%s secret_hygiene_status=%s",
            broker_mode,
            trade_mode,
            symbols,
            model_name,
            log_level,
            secret_hygiene_status,
        )
        return True
