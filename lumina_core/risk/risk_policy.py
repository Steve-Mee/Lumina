from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class RiskPolicy:
    daily_loss_cap: float = -1000.0
    max_open_risk_per_instrument: float = 500.0
    max_total_open_risk: float = 3000.0
    max_exposure_per_regime: float = 2000.0
    kelly_fraction: float = 0.25
    var_95_limit_usd: float = 1200.0
    var_99_limit_usd: float = 1800.0
    es_95_limit_usd: float = 1500.0
    es_99_limit_usd: float = 2200.0
    margin_min_confidence: float = 0.6
    runtime_mode: str = "real"

    def validate(self) -> bool:
        mode = str(self.runtime_mode or "real").strip().lower()
        if mode not in {"sim", "paper", "real", "sim_real_guard"}:
            return False
        if self.daily_loss_cap >= 0:
            return False
        if self.max_open_risk_per_instrument <= 0:
            return False
        if self.max_total_open_risk <= 0:
            return False
        if self.max_exposure_per_regime <= 0:
            return False
        if self.var_95_limit_usd <= 0 or self.var_99_limit_usd <= 0:
            return False
        if self.es_95_limit_usd <= 0 or self.es_99_limit_usd <= 0:
            return False
        if self.margin_min_confidence < 0.0 or self.margin_min_confidence > 1.0:
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


def _load_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if config is not None:
        return dict(config)
    try:
        import yaml as _yaml

        cfg_path = os.getenv("LUMINA_CONFIG", "config.yaml")
        with open(cfg_path, "r", encoding="utf-8") as _fh:
            loaded = _yaml.safe_load(_fh) or {}
        return dict(loaded) if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _mode_from_env_or_config(config: dict[str, Any], mode: str | None) -> str:
    if mode:
        return str(mode).strip().lower()
    return str(os.getenv("LUMINA_MODE") or os.getenv("TRADE_MODE") or config.get("mode", "sim")).strip().lower()


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def load_risk_policy(config: dict[str, Any] | None = None, mode: str | None = None) -> RiskPolicy:
    cfg = _load_config(config)
    runtime_mode = _mode_from_env_or_config(cfg, mode)

    risk_cfg = cfg.get("risk_controller", {}) if isinstance(cfg.get("risk_controller"), dict) else {}
    mode_cfg = cfg.get(runtime_mode, {}) if isinstance(cfg.get(runtime_mode), dict) else {}

    policy = RiskPolicy(
        daily_loss_cap=_safe_float(risk_cfg.get("daily_loss_cap", -1000.0), -1000.0),
        max_open_risk_per_instrument=_safe_float(
            risk_cfg.get("max_open_risk_per_instrument", 500.0),
            500.0,
        ),
        max_total_open_risk=_safe_float(risk_cfg.get("max_total_open_risk", 3000.0), 3000.0),
        max_exposure_per_regime=_safe_float(risk_cfg.get("max_exposure_per_regime", 2000.0), 2000.0),
        kelly_fraction=_safe_float(
            risk_cfg.get("kelly_fraction", risk_cfg.get("kelly_fraction_max", 0.25)),
            0.25,
        ),
        var_95_limit_usd=_safe_float(risk_cfg.get("var_95_limit_usd", 1200.0), 1200.0),
        var_99_limit_usd=_safe_float(risk_cfg.get("var_99_limit_usd", 1800.0), 1800.0),
        es_95_limit_usd=_safe_float(risk_cfg.get("es_95_limit_usd", 1500.0), 1500.0),
        es_99_limit_usd=_safe_float(risk_cfg.get("es_99_limit_usd", 2200.0), 2200.0),
        margin_min_confidence=_safe_float(risk_cfg.get("margin_min_confidence", 0.6), 0.6),
        runtime_mode=runtime_mode,
    )

    policy.daily_loss_cap = _safe_float(mode_cfg.get("daily_loss_cap", policy.daily_loss_cap), policy.daily_loss_cap)
    policy.max_open_risk_per_instrument = _safe_float(
        mode_cfg.get("max_open_risk_per_instrument", policy.max_open_risk_per_instrument),
        policy.max_open_risk_per_instrument,
    )
    policy.max_total_open_risk = _safe_float(
        mode_cfg.get("max_total_open_risk", policy.max_total_open_risk),
        policy.max_total_open_risk,
    )
    policy.max_exposure_per_regime = _safe_float(
        mode_cfg.get("max_exposure_per_regime", policy.max_exposure_per_regime),
        policy.max_exposure_per_regime,
    )
    policy.kelly_fraction = _safe_float(
        mode_cfg.get("kelly_fraction", mode_cfg.get("kelly_fraction_max", policy.kelly_fraction)),
        policy.kelly_fraction,
    )
    policy.var_95_limit_usd = _safe_float(mode_cfg.get("var_95_limit_usd", policy.var_95_limit_usd), policy.var_95_limit_usd)
    policy.var_99_limit_usd = _safe_float(mode_cfg.get("var_99_limit_usd", policy.var_99_limit_usd), policy.var_99_limit_usd)
    policy.es_95_limit_usd = _safe_float(mode_cfg.get("es_95_limit_usd", policy.es_95_limit_usd), policy.es_95_limit_usd)
    policy.es_99_limit_usd = _safe_float(mode_cfg.get("es_99_limit_usd", policy.es_99_limit_usd), policy.es_99_limit_usd)
    policy.margin_min_confidence = _safe_float(
        mode_cfg.get("margin_min_confidence", policy.margin_min_confidence),
        policy.margin_min_confidence,
    )

    if not policy.validate():
        fallback = RiskPolicy(runtime_mode=runtime_mode if runtime_mode in {"sim", "paper", "real", "sim_real_guard"} else "real")
        if fallback.runtime_mode == "sim":
            fallback.daily_loss_cap = -1_000_000.0
            fallback.kelly_fraction = 1.0
        return fallback
    return policy

