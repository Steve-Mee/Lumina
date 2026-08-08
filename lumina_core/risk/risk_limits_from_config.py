from __future__ import annotations

import logging
import os
import traceback
from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured
from lumina_core.risk.risk_limits import RiskLimits
from lumina_core.risk.risk_policy import get_effective_risk_overlay, load_risk_policy

logger = logging.getLogger(__name__)

_HANDLED_RISK_EXCEPTIONS = (
    AttributeError,
    ImportError,
    IndexError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)

def risk_limits_from_config(config: dict[str, Any] | None = None) -> RiskLimits:
    if config is None:
        try:
            config = ConfigLoader.get()
        except _HANDLED_RISK_EXCEPTIONS as _exc:
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                    code="RISK_CONFIG_LOAD_009",
                    message=str(_exc),
                    context={"traceback": traceback.format_exc()},
                )
            )
            config = {}
    config = config or {}

    def _as_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/risk/risk_controller.py:667")
            return int(default)

    def _as_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/risk/risk_controller.py:673")
            return float(default)

    global_mode = str(os.getenv("LUMINA_MODE") or os.getenv("TRADE_MODE") or config.get("mode", "sim")).strip().lower()
    is_sim = global_mode == "sim"
    merged_overlay = get_effective_risk_overlay(mode=global_mode, config=config)
    resolved_policy = load_risk_policy(config=config, mode=global_mode)
    trading_cfg = config.get("trading", {}) if isinstance(config.get("trading"), dict) else {}

    if is_sim:
        logger.info("[MODE=SIM] RiskLimits: all hard caps bypassed – MAXIMAL LEARNING MODE")
    else:
        logger.info("[MODE=%s] RiskLimits: capital preservation caps ENFORCED", global_mode.upper())

    return RiskLimits(
        daily_loss_cap=float(resolved_policy.daily_loss_cap),
        max_consecutive_losses=max(1, _as_int(merged_overlay.get("max_consecutive_losses", 3), 3)),
        max_open_risk_per_instrument=float(resolved_policy.max_open_risk_per_instrument),
        max_total_open_risk=float(resolved_policy.max_total_open_risk),
        max_exposure_per_regime=float(resolved_policy.max_exposure_per_regime),
        cooldown_after_streak=max(1, _as_int(merged_overlay.get("cooldown_after_streak", 30), 30)),
        session_cooldown_minutes=max(1, _as_int(merged_overlay.get("session_cooldown_minutes", 15), 15)),
        enforce_session_guard=bool(resolved_policy.enforce_session_guard),
        eod_force_close_minutes_before_session_end=_as_int(
            merged_overlay.get(
                "eod_force_close_minutes_before_session_end",
                trading_cfg.get("eod_force_close_minutes_before_session_end", 30),
            ),
            30,
        ),
        eod_no_new_trades_minutes_before_session_end=_as_int(
            merged_overlay.get(
                "eod_no_new_trades_minutes_before_session_end",
                trading_cfg.get("eod_no_new_trades_minutes_before_session_end", 60),
            ),
            60,
        ),
        margin_min_confidence=float(resolved_policy.margin_min_confidence),
        var_es_method=str(merged_overlay.get("var_es_method", "historical") or "historical").strip().lower(),
        var_es_window=max(20, _as_int(merged_overlay.get("var_es_window", 200), 200)),
        var_es_min_samples=max(10, _as_int(merged_overlay.get("var_es_min_samples", 40), 40)),
        var_es_fail_closed_on_insufficient_data=bool(
            merged_overlay.get("var_es_fail_closed_on_insufficient_data", False)
        ),
        var_es_insufficient_data_policy=str(
            merged_overlay.get("var_es_insufficient_data_policy", "fail_closed_real_only") or "fail_closed_real_only"
        )
        .strip()
        .lower(),
        enable_var_es_calc=bool(merged_overlay.get("enable_var_es_calc", True)),
        enable_var_es_enforce_sim_real_guard=bool(merged_overlay.get("enable_var_es_enforce_sim_real_guard", True)),
        enable_var_es_enforce_real=bool(merged_overlay.get("enable_var_es_enforce_real", True)),
        var_es_high_risk_limit_multiplier=_as_float(merged_overlay.get("var_es_high_risk_limit_multiplier", 0.8), 0.8),
        var_es_normal_risk_limit_multiplier=_as_float(
            merged_overlay.get("var_es_normal_risk_limit_multiplier", 1.0), 1.0
        ),
        var_es_reason_codes_enabled=bool(merged_overlay.get("var_es_reason_codes_enabled", True)),
        var_95_limit_usd=float(resolved_policy.var_95_limit_usd),
        var_99_limit_usd=float(resolved_policy.var_99_limit_usd),
        es_95_limit_usd=float(resolved_policy.es_95_limit_usd),
        es_99_limit_usd=float(resolved_policy.es_99_limit_usd),
        enable_mc_drawdown_calc=bool(merged_overlay.get("enable_mc_drawdown_calc", True)),
        mc_drawdown_paths=max(1000, _as_int(merged_overlay.get("mc_drawdown_paths", 10000), 10000)),
        mc_drawdown_horizon_days=max(20, _as_int(merged_overlay.get("mc_drawdown_horizon_days", 252), 252)),
        mc_drawdown_min_samples=max(10, _as_int(merged_overlay.get("mc_drawdown_min_samples", 40), 40)),
        mc_drawdown_insufficient_data_policy=str(
            merged_overlay.get("mc_drawdown_insufficient_data_policy", "advisory") or "advisory"
        )
        .strip()
        .lower(),
        enable_mc_drawdown_enforce_sim_real_guard=bool(
            merged_overlay.get("enable_mc_drawdown_enforce_sim_real_guard", True)
        ),
        enable_mc_drawdown_enforce_real=bool(merged_overlay.get("enable_mc_drawdown_enforce_real", True)),
        mc_drawdown_threshold_pct=_as_float(merged_overlay.get("mc_drawdown_threshold_pct", 12.0), 12.0),
        mc_drawdown_random_seed=_as_int(merged_overlay.get("mc_drawdown_random_seed", 4242), 4242),
        real_capital_safety_threshold_usd=_as_float(
            merged_overlay.get("real_capital_safety_threshold_usd", 1000.0), 1000.0
        ),
        runtime_mode=global_mode,
        sim_mode=is_sim,
    )
