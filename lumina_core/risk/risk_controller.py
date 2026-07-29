from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import traceback
from typing import Any, Optional


from lumina_core.config_loader import ConfigLoader
from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured
from lumina_core.risk.pnl_provenance import PnlProvenance
from lumina_core.risk.risk_allocator import RiskAllocatorMixin
from lumina_core.risk.risk_gates import RiskGatesMixin
from lumina_core.risk.risk_controller_status import RiskControllerStatusMixin
from lumina_core.risk.risk_limits import RiskLimits
from lumina_core.risk.risk_policy import RiskPolicy, get_effective_risk_overlay, load_risk_policy
from lumina_core.risk.risk_state import MarginTracker, RiskState

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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HardRiskController(RiskAllocatorMixin, RiskGatesMixin, RiskControllerStatusMixin):
    def __init__(
        self,
        limits: RiskLimits,
        state_file: Optional[Path] = None,
        enforce_rules: bool = True,
        regime_limit_overrides: Optional[dict[str, dict[str, float | int]]] = None,
        session_guard=None,
        portfolio_var_allocator=None,
    ):
        if not limits.validate():
            raise ValueError("Invalid risk limits configuration")

        self.limits = limits
        self.state = RiskState()
        self.state_file = state_file
        self.enforce_rules = enforce_rules
        self._base_limits = limits
        self._active_limits = limits
        self._regime_limit_overrides = regime_limit_overrides if isinstance(regime_limit_overrides, dict) else {}
        self.session_guard = session_guard
        self.portfolio_var_allocator = portfolio_var_allocator
        if self.session_guard is None and self._base_limits.enforce_session_guard:
            try:
                from lumina_core.risk.session_guard import SessionGuard  # noqa: PLC0415

                self.session_guard = SessionGuard(calendar_name="CME")
            except _HANDLED_RISK_EXCEPTIONS as exc:
                logger.error("SessionGuard init failed: %s", exc)
                err = LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                    code="RISK_SESSION_GUARD_001",
                    message=str(exc),
                    context={"traceback": traceback.format_exc()},
                )
                log_structured(err)
                self.session_guard = None

        mode_str = "ENFORCED" if enforce_rules else "LEARNING/TESTING MODE (rules bypassed)"
        logger.info(f"HardRiskController initialized with limits: {limits}")
        logger.info(f"Risk enforcement: {mode_str}")

        if self.state_file and self.state_file.exists():
            self._load_state()

    def resolve_symbol_open_risk_cap(self, symbol: str) -> float:
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            return float(self._active_limits.max_open_risk_per_instrument)
        try:
            config = ConfigLoader.get()
            runtime_mode = str(
                os.getenv("LUMINA_MODE")
                or os.getenv("TRADE_MODE")
                or config.get("mode", "sim")
                or getattr(self._active_limits, "runtime_mode", "")
            ).strip()
            base_policy = RiskPolicy.get_effective_policy(mode=runtime_mode, instrument=None, config=config)
            symbol_policy = RiskPolicy.get_effective_policy(
                mode=runtime_mode, instrument=normalized_symbol, config=config
            )
            if float(symbol_policy.max_open_risk_per_instrument) != float(base_policy.max_open_risk_per_instrument):
                return float(symbol_policy.max_open_risk_per_instrument)
            return float(self._active_limits.max_open_risk_per_instrument)
        except _HANDLED_RISK_EXCEPTIONS:
            return float(self._active_limits.max_open_risk_per_instrument)

    def apply_regime_override(
        self,
        *,
        regime: str,
        risk_state: str = "NORMAL",
        risk_multiplier: float | None = None,
        cooldown_after_streak: int | None = None,
    ) -> None:
        normalized_regime = str(regime or "NEUTRAL").upper()
        normalized_risk_state = str(risk_state or "NORMAL").upper()
        multiplier = float(risk_multiplier if risk_multiplier is not None else 1.0)
        if normalized_risk_state == "HIGH_RISK":
            multiplier = min(multiplier, 0.6)

        override_cfg = self._regime_limit_overrides.get(normalized_regime, {})
        daily_loss_cap = float(override_cfg.get("daily_loss_cap", self._base_limits.daily_loss_cap * multiplier))
        max_consecutive_losses = int(
            override_cfg.get(
                "max_consecutive_losses",
                max(1, int(round(self._base_limits.max_consecutive_losses * max(0.5, multiplier)))),
            )
        )
        max_open_risk = float(
            override_cfg.get(
                "max_open_risk_per_instrument", self._base_limits.max_open_risk_per_instrument * multiplier
            )
        )
        max_regime_risk = float(
            override_cfg.get("max_exposure_per_regime", self._base_limits.max_exposure_per_regime * multiplier)
        )
        base_cooldown = self._base_limits.cooldown_after_streak
        cooldown = int(
            override_cfg.get(
                "cooldown_after_streak",
                cooldown_after_streak
                if cooldown_after_streak is not None
                else max(base_cooldown, int(base_cooldown / max(multiplier, 0.25))),
            )
        )
        self._active_limits = RiskLimits(
            daily_loss_cap=daily_loss_cap,
            max_consecutive_losses=max_consecutive_losses,
            max_open_risk_per_instrument=max_open_risk,
            max_total_open_risk=self._base_limits.max_total_open_risk,
            max_exposure_per_regime=max_regime_risk,
            cooldown_after_streak=cooldown,
            session_cooldown_minutes=self._base_limits.session_cooldown_minutes,
            enforce_session_guard=self._base_limits.enforce_session_guard,
            eod_force_close_minutes_before_session_end=self._base_limits.eod_force_close_minutes_before_session_end,
            eod_no_new_trades_minutes_before_session_end=self._base_limits.eod_no_new_trades_minutes_before_session_end,
            margin_min_confidence=self._base_limits.margin_min_confidence,
            var_es_method=self._base_limits.var_es_method,
            var_es_window=self._base_limits.var_es_window,
            var_es_min_samples=self._base_limits.var_es_min_samples,
            var_es_fail_closed_on_insufficient_data=self._base_limits.var_es_fail_closed_on_insufficient_data,
            var_es_insufficient_data_policy=self._base_limits.var_es_insufficient_data_policy,
            enable_var_es_calc=self._base_limits.enable_var_es_calc,
            enable_var_es_enforce_sim_real_guard=self._base_limits.enable_var_es_enforce_sim_real_guard,
            enable_var_es_enforce_real=self._base_limits.enable_var_es_enforce_real,
            var_es_high_risk_limit_multiplier=self._base_limits.var_es_high_risk_limit_multiplier,
            var_es_normal_risk_limit_multiplier=self._base_limits.var_es_normal_risk_limit_multiplier,
            var_es_reason_codes_enabled=self._base_limits.var_es_reason_codes_enabled,
            var_95_limit_usd=self._base_limits.var_95_limit_usd,
            var_99_limit_usd=self._base_limits.var_99_limit_usd,
            es_95_limit_usd=self._base_limits.es_95_limit_usd,
            es_99_limit_usd=self._base_limits.es_99_limit_usd,
            enable_mc_drawdown_calc=self._base_limits.enable_mc_drawdown_calc,
            mc_drawdown_paths=self._base_limits.mc_drawdown_paths,
            mc_drawdown_horizon_days=self._base_limits.mc_drawdown_horizon_days,
            mc_drawdown_min_samples=self._base_limits.mc_drawdown_min_samples,
            mc_drawdown_insufficient_data_policy=self._base_limits.mc_drawdown_insufficient_data_policy,
            enable_mc_drawdown_enforce_sim_real_guard=self._base_limits.enable_mc_drawdown_enforce_sim_real_guard,
            enable_mc_drawdown_enforce_real=self._base_limits.enable_mc_drawdown_enforce_real,
            mc_drawdown_threshold_pct=self._base_limits.mc_drawdown_threshold_pct,
            mc_drawdown_random_seed=self._base_limits.mc_drawdown_random_seed,
            real_capital_safety_threshold_usd=self._base_limits.real_capital_safety_threshold_usd,
            runtime_mode=self._base_limits.runtime_mode,
            sim_mode=self._base_limits.sim_mode,
        )
        self.state.active_regime = normalized_regime
        self.state.active_risk_state = normalized_risk_state

    def _load_state(self) -> None:
        try:
            if self.state_file is None:
                return
            with open(str(self.state_file), "r") as f:
                data = json.load(f)
                self.state.daily_pnl = data.get("daily_pnl", 0.0)
                self.state.consecutive_losses = data.get("consecutive_losses", 0)
                self.state.kill_switch_engaged = data.get("kill_switch_engaged", False)
                self.state.kill_switch_reason = data.get("kill_switch_reason", "")
                logger.info(
                    f"Loaded persistent risk state: daily_pnl={self.state.daily_pnl}, "
                    f"kill_switch={self.state.kill_switch_engaged}"
                )
        except _HANDLED_RISK_EXCEPTIONS as e:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                code="RISK_LOAD_STATE_002",
                message=str(e),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            logger.error(f"Failed to load risk state: {e}")

    def _save_state(self) -> None:
        if not self.state_file:
            return
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(
                    {
                        "daily_pnl": self.state.daily_pnl,
                        "consecutive_losses": self.state.consecutive_losses,
                        "kill_switch_engaged": self.state.kill_switch_engaged,
                        "kill_switch_reason": self.state.kill_switch_reason,
                        "timestamp": _utcnow().isoformat(),
                    },
                    f,
                    indent=2,
                )
        except _HANDLED_RISK_EXCEPTIONS as e:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                code="RISK_SAVE_STATE_003",
                message=str(e),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            logger.error(f"Failed to save risk state: {e}")

    def reset_daily(self) -> None:
        logger.info(
            f"Resetting daily metrics. Previous daily_pnl={self.state.daily_pnl}, "
            f"consecutive_losses={self.state.consecutive_losses}"
        )
        self.state.daily_pnl = 0.0
        self.state.consecutive_losses = 0
        self.state.last_loss_time = None
        self.state.open_risk_by_symbol.clear()
        self.state.symbol_regime_map.clear()
        self.state.open_risk_all_regimes.clear()
        self._save_state()

    def record_trade_result(
        self,
        symbol: str,
        regime: str,
        pnl: float,
        risk_taken: float,
        *,
        trade_mode: str | None = None,
        pnl_provenance: PnlProvenance | None = None,
    ) -> None:
        """Accumulate daily PnL for risk gates. REAL ignores non-broker-reconciled PnL (fail-closed)."""
        tm = str(trade_mode or "").strip().lower()
        if tm == "real" and pnl_provenance != PnlProvenance.BROKER_RECONCILED:
            logger.error(
                "REAL mode: skipping record_trade_result — PnL must be %s (got %r)",
                PnlProvenance.BROKER_RECONCILED,
                pnl_provenance,
            )
            return
        self.state.daily_pnl += pnl
        self.state.trade_history.append(
            {
                "timestamp": _utcnow().isoformat(),
                "symbol": symbol,
                "regime": regime,
                "pnl": pnl,
                "risk_taken": risk_taken,
            }
        )

        if pnl < 0:
            self.state.consecutive_losses += 1
            self.state.last_loss_time = _utcnow()
            logger.warning(f"Loss recorded: {pnl:.2f} USD. Consecutive losses: {self.state.consecutive_losses}")
        else:
            self.state.consecutive_losses = 0

        self._save_state()

    def set_open_risk(self, symbol: str, regime: str, risk_amount: float) -> None:
        sym = str(symbol or "").strip()
        reg = str(regime or "").strip().upper() or "UNKNOWN"
        self.state.open_risk_by_symbol[sym] = float(risk_amount)
        self.state.symbol_regime_map[sym] = reg
        self._recompute_open_risk_by_regime()

    def _get_regime_for_symbol(self, symbol: str) -> Optional[str]:
        sym = str(symbol or "").strip()
        if not sym:
            return None
        return self.state.symbol_regime_map.get(sym)

    def clear_open_risk(self, symbol: str) -> None:
        sym = str(symbol or "").strip()
        if not sym:
            return
        self.state.open_risk_by_symbol.pop(sym, None)
        self.state.symbol_regime_map.pop(sym, None)
        self._recompute_open_risk_by_regime()

    def _recompute_open_risk_by_regime(self) -> None:
        aggregate: dict[str, float] = {}
        for sym, risk in self.state.open_risk_by_symbol.items():
            regime = self.state.symbol_regime_map.get(sym)
            if not regime:
                continue
            aggregate[regime] = aggregate.get(regime, 0.0) + float(risk)
        self.state.open_risk_all_regimes = aggregate

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


__all__ = [
    "MarginTracker",
    "RiskLimits",
    "RiskState",
    "HardRiskController",
    "risk_limits_from_config",
]
