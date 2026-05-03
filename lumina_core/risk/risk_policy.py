from __future__ import annotations
import logging

import os
from dataclasses import asdict, dataclass, fields, replace
from typing import Any

from lumina_core.config_loader import ConfigLoader

_VALID_MODES = {"sim", "paper", "real", "sim_real_guard"}
_INSTRUMENT_OVERLAY_KEYS = ("risk_instrument_overrides", "instrument_risk_overrides")


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/risk/risk_policy.py:16")
        return float(default)


def _safe_mode(mode: str | None, config: dict[str, Any]) -> str:
    candidate = (
        str(mode or os.getenv("LUMINA_MODE") or os.getenv("TRADE_MODE") or config.get("mode", "sim")).strip().lower()
    )
    return candidate if candidate in _VALID_MODES else "sim"


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _normalize_symbol(symbol: str | None) -> str | None:
    if symbol is None:
        return None
    normalized = str(symbol).strip().upper()
    return normalized if normalized else None


@dataclass(slots=True)
class RiskPolicy:
    daily_loss_cap: float = -1000.0
    max_consecutive_losses: int = 3
    max_open_risk_per_instrument: float = 500.0
    max_total_open_risk: float = 3000.0
    max_exposure_per_regime: float = 2000.0
    cooldown_after_streak: int = 30
    session_cooldown_minutes: int = 15
    enforce_session_guard: bool = True
    kelly_fraction: float = 0.25
    kelly_min_confidence: float = 0.65
    var_95_limit_usd: float = 1200.0
    var_99_limit_usd: float = 1800.0
    es_95_limit_usd: float = 1500.0
    es_99_limit_usd: float = 2200.0
    margin_min_confidence: float = 0.6
    runtime_mode: str = "real"

    @classmethod
    def _field_names(cls) -> set[str]:
        return {f.name for f in fields(cls)}

    @classmethod
    def _mode_defaults(cls, mode: str) -> dict[str, Any]:
        normalized = _safe_mode(mode, {})
        if normalized == "sim":
            return {
                "daily_loss_cap": -1_000_000.0,
                "enforce_session_guard": False,
                "kelly_fraction": 1.0,
            }
        return {}

    @classmethod
    def _merge_layers(
        cls,
        *,
        config: dict[str, Any],
        mode: str,
        instrument: str | None,
    ) -> dict[str, Any]:
        mode_cfg = _safe_dict(config.get(mode))
        base_cfg = _safe_dict(config.get("risk_controller"))
        merged: dict[str, Any] = dict(base_cfg)
        merged.update(mode_cfg)
        normalized_symbol = _normalize_symbol(instrument)
        if normalized_symbol:
            for key in _INSTRUMENT_OVERLAY_KEYS:
                overlays = _safe_dict(config.get(key))
                raw_overlay = overlays.get(normalized_symbol)
                if isinstance(raw_overlay, dict):
                    merged.update(raw_overlay)
                    break
        merged.update(cls._mode_defaults(mode))
        return merged

    @classmethod
    def _from_merged(cls, *, merged: dict[str, Any], mode: str) -> RiskPolicy:
        # Keep conversion explicit for predictable fail-closed behavior.
        policy = cls(
            daily_loss_cap=_safe_float(merged.get("daily_loss_cap", -1000.0), -1000.0),
            max_consecutive_losses=max(1, int(merged.get("max_consecutive_losses", 3) or 3)),
            max_open_risk_per_instrument=_safe_float(
                merged.get("max_open_risk_per_instrument", 500.0),
                500.0,
            ),
            max_total_open_risk=_safe_float(merged.get("max_total_open_risk", 3000.0), 3000.0),
            max_exposure_per_regime=_safe_float(merged.get("max_exposure_per_regime", 2000.0), 2000.0),
            cooldown_after_streak=max(1, int(merged.get("cooldown_after_streak", 30) or 30)),
            session_cooldown_minutes=max(1, int(merged.get("session_cooldown_minutes", 15) or 15)),
            enforce_session_guard=bool(merged.get("enforce_session_guard", True)),
            kelly_fraction=_safe_float(
                merged.get("kelly_fraction", merged.get("kelly_fraction_max", 0.25)),
                0.25,
            ),
            kelly_min_confidence=_safe_float(merged.get("kelly_min_confidence", 0.65), 0.65),
            var_95_limit_usd=_safe_float(merged.get("var_95_limit_usd", 1200.0), 1200.0),
            var_99_limit_usd=_safe_float(merged.get("var_99_limit_usd", 1800.0), 1800.0),
            es_95_limit_usd=_safe_float(merged.get("es_95_limit_usd", 1500.0), 1500.0),
            es_99_limit_usd=_safe_float(merged.get("es_99_limit_usd", 2200.0), 2200.0),
            margin_min_confidence=_safe_float(merged.get("margin_min_confidence", 0.6), 0.6),
            runtime_mode=_safe_mode(mode, {}),
        )
        if policy.validate():
            return policy
        fallback = cls(runtime_mode=_safe_mode(mode, {}))
        if fallback.runtime_mode == "sim":
            fallback = replace(fallback, daily_loss_cap=-1_000_000.0, enforce_session_guard=False, kelly_fraction=1.0)
        return fallback

    @classmethod
    def get_effective_policy(
        cls,
        mode: str,
        instrument: str | None = None,
        *,
        config: dict[str, Any] | None = None,
        reload_config: bool = False,
    ) -> RiskPolicy:
        cfg = _safe_dict(config) if config is not None else _safe_dict(ConfigLoader.get(reload=reload_config))
        runtime_mode = _safe_mode(mode, cfg)
        merged = cls._merge_layers(config=cfg, mode=runtime_mode, instrument=instrument)
        return cls._from_merged(merged=merged, mode=runtime_mode)

    def validate(self) -> bool:
        mode = _safe_mode(self.runtime_mode, {})
        if self.daily_loss_cap >= 0:
            return False
        if self.max_consecutive_losses < 1:
            return False
        if self.max_open_risk_per_instrument <= 0:
            return False
        if self.max_total_open_risk <= 0:
            return False
        if self.max_exposure_per_regime <= 0:
            return False
        if self.cooldown_after_streak < 1:
            return False
        if self.session_cooldown_minutes < 1:
            return False
        if self.var_95_limit_usd <= 0 or self.var_99_limit_usd <= 0:
            return False
        if self.es_95_limit_usd <= 0 or self.es_99_limit_usd <= 0:
            return False
        if self.margin_min_confidence < 0.0 or self.margin_min_confidence > 1.0:
            return False
        if self.kelly_min_confidence < 0.0 or self.kelly_min_confidence > 1.0:
            return False
        if self.kelly_fraction <= 0.0:
            return False
        if mode == "real" and self.kelly_fraction > 0.25:
            return False
        if mode == "paper" and self.kelly_fraction > 0.5:
            return False
        if mode in {"sim", "sim_real_guard"} and self.kelly_fraction > 1.0:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_effective_risk_overlay(
    *,
    mode: str | None = None,
    instrument: str | None = None,
    config: dict[str, Any] | None = None,
    reload_config: bool = False,
) -> dict[str, Any]:
    cfg = _safe_dict(config) if config is not None else _safe_dict(ConfigLoader.get(reload=reload_config))
    runtime_mode = _safe_mode(mode, cfg)
    return RiskPolicy._merge_layers(config=cfg, mode=runtime_mode, instrument=instrument)


def load_risk_policy(
    config: dict[str, Any] | None = None,
    mode: str | None = None,
    instrument: str | None = None,
    *,
    reload_config: bool = False,
) -> RiskPolicy:
    cfg = _safe_dict(config) if config is not None else _safe_dict(ConfigLoader.get(reload=reload_config))
    runtime_mode = _safe_mode(mode, cfg)
    return RiskPolicy.get_effective_policy(
        mode=runtime_mode,
        instrument=instrument,
        config=cfg,
        reload_config=reload_config,
    )
