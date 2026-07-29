from __future__ import annotations

from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskLimits:
    daily_loss_cap: float = -1000.0
    max_consecutive_losses: int = 3
    max_open_risk_per_instrument: float = 500.0
    max_total_open_risk: float = 3000.0
    max_exposure_per_regime: float = 2000.0
    cooldown_after_streak: int = 30
    session_cooldown_minutes: int = 15
    enforce_session_guard: bool = True
    eod_force_close_minutes_before_session_end: int = 30
    eod_no_new_trades_minutes_before_session_end: int = 60
    margin_min_confidence: float = 0.6
    var_es_method: str = "historical"
    var_es_window: int = 200
    var_es_min_samples: int = 40
    var_es_fail_closed_on_insufficient_data: bool = False
    var_es_insufficient_data_policy: str = "advisory"
    enable_var_es_calc: bool = True
    enable_var_es_enforce_sim_real_guard: bool = True
    enable_var_es_enforce_real: bool = True
    var_es_high_risk_limit_multiplier: float = 0.8
    var_es_normal_risk_limit_multiplier: float = 1.0
    var_es_reason_codes_enabled: bool = True
    var_95_limit_usd: float = 1200.0
    var_99_limit_usd: float = 1800.0
    es_95_limit_usd: float = 1500.0
    es_99_limit_usd: float = 2200.0
    enable_mc_drawdown_calc: bool = True
    mc_drawdown_paths: int = 10000
    mc_drawdown_horizon_days: int = 252
    mc_drawdown_min_samples: int = 40
    mc_drawdown_insufficient_data_policy: str = "advisory"
    enable_mc_drawdown_enforce_sim_real_guard: bool = True
    enable_mc_drawdown_enforce_real: bool = True
    mc_drawdown_threshold_pct: float = 12.0
    mc_drawdown_random_seed: int = 4242
    real_capital_safety_threshold_usd: float = 1000.0
    runtime_mode: str = "real"
    sim_mode: bool = False

    def validate(self) -> bool:
        if self.daily_loss_cap >= 0:
            logger.warning("daily_loss_cap should be negative (e.g., -1000)")
        if self.max_consecutive_losses < 1:
            logger.error("max_consecutive_losses must be >= 1")
            return False
        if self.max_open_risk_per_instrument <= 0:
            logger.error("max_open_risk_per_instrument must be > 0")
            return False
        if self.max_total_open_risk <= 0:
            logger.error("max_total_open_risk must be > 0")
            return False
        if self.max_exposure_per_regime <= 0:
            logger.error("max_exposure_per_regime must be > 0")
            return False
        if self.cooldown_after_streak < 1:
            logger.error("cooldown_after_streak must be >= 1 minute")
            return False
        if self.session_cooldown_minutes < 1:
            logger.error("session_cooldown_minutes must be >= 1 minute")
            return False
        if self.eod_force_close_minutes_before_session_end < 0:
            logger.error("eod_force_close_minutes_before_session_end must be >= 0")
            return False
        if self.eod_no_new_trades_minutes_before_session_end < 0:
            logger.error("eod_no_new_trades_minutes_before_session_end must be >= 0")
            return False
        if self.margin_min_confidence < 0.0 or self.margin_min_confidence > 1.0:
            logger.error("margin_min_confidence must be within 0.0..1.0")
            return False
        if str(self.var_es_method).strip().lower() not in {"historical", "parametric"}:
            logger.error("var_es_method must be historical or parametric")
            return False
        if self.var_es_window < 20:
            logger.error("var_es_window must be >= 20")
            return False
        if self.var_es_min_samples < 10:
            logger.error("var_es_min_samples must be >= 10")
            return False
        if str(self.var_es_insufficient_data_policy).strip().lower() not in {
            "advisory",
            "fail_closed_real_only",
            "fail_closed_all_enforced",
        }:
            logger.error(
                "var_es_insufficient_data_policy must be advisory | fail_closed_real_only | fail_closed_all_enforced"
            )
            return False
        if self.var_es_high_risk_limit_multiplier <= 0.0 or self.var_es_high_risk_limit_multiplier > 2.0:
            logger.error("var_es_high_risk_limit_multiplier must be within (0.0, 2.0]")
            return False
        if self.var_es_normal_risk_limit_multiplier <= 0.0 or self.var_es_normal_risk_limit_multiplier > 2.0:
            logger.error("var_es_normal_risk_limit_multiplier must be within (0.0, 2.0]")
            return False
        if str(self.runtime_mode).strip().lower() not in {"sim", "real", "sim_real_guard", "paper"}:
            logger.error("runtime_mode must be sim | real | sim_real_guard | paper")
            return False
        if (
            self.var_95_limit_usd <= 0
            or self.var_99_limit_usd <= 0
            or self.es_95_limit_usd <= 0
            or self.es_99_limit_usd <= 0
        ):
            logger.error("VaR/ES limits must be > 0")
            return False
        if self.mc_drawdown_paths < 1000:
            logger.error("mc_drawdown_paths must be >= 1000")
            return False
        if self.mc_drawdown_horizon_days < 20:
            logger.error("mc_drawdown_horizon_days must be >= 20")
            return False
        if self.mc_drawdown_min_samples < 10:
            logger.error("mc_drawdown_min_samples must be >= 10")
            return False
        if str(self.mc_drawdown_insufficient_data_policy).strip().lower() not in {
            "advisory",
            "fail_closed_real_only",
            "fail_closed_all_enforced",
        }:
            logger.error(
                "mc_drawdown_insufficient_data_policy must be advisory | fail_closed_real_only | fail_closed_all_enforced"
            )
            return False
        if self.mc_drawdown_threshold_pct <= 0.0 or self.mc_drawdown_threshold_pct > 100.0:
            logger.error("mc_drawdown_threshold_pct must be within (0.0, 100.0]")
            return False
        if self.real_capital_safety_threshold_usd <= 0:
            logger.error("real_capital_safety_threshold_usd must be > 0")
            return False
        return True


__all__ = ["RiskLimits"]
