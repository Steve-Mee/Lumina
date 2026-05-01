from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RiskGatesMixin:
    # Type stubs for mixin attributes provided by mixing class
    limits: Any
    state: Any
    enforce_rules: bool
    _active_limits: Any
    session_guard: Any
    portfolio_var_allocator: Any

    def check_var_es_pre_trade(self, proposed_risk: float) -> tuple[bool, str, dict[str, Any]]:
        """Stub for mixin method provided by mixing class."""
        raise NotImplementedError

    def check_monte_carlo_drawdown_pre_trade(self, proposed_risk: float) -> tuple[bool, str, dict[str, Any]]:
        """Stub for mixin method provided by mixing class."""
        raise NotImplementedError

    def _save_state(self) -> None:
        """Stub for mixin method provided by mixing class."""
        raise NotImplementedError

    def check_can_trade(self, symbol: str, regime: str, proposed_risk: float) -> tuple[bool, str]:
        if self.limits.sim_mode or not self.enforce_rules:
            return True, "OK (SIM learning mode – all caps bypassed)"

        if self.state.kill_switch_engaged:
            return False, f"KILL SWITCH ENGAGED: {self.state.kill_switch_reason} (since {self.state.kill_switch_time})"

        limits = self._active_limits

        if limits.enforce_session_guard:
            if self.session_guard is None:
                return False, "SESSION GUARD unavailable (fail-closed)"
            if self.session_guard.is_rollover_window():
                return False, "SESSION GUARD blocked order: rollover window active"
            if not self.session_guard.is_market_open():
                nxt = self.session_guard.next_open()
                suffix = f" | next_open={nxt.isoformat()}" if nxt is not None else ""
                return False, f"SESSION GUARD blocked order: market closed{suffix}"
            if (
                limits.eod_no_new_trades_minutes_before_session_end > 0
                and self.session_guard.should_block_new_eod_trades(
                    no_new_trades_minutes=limits.eod_no_new_trades_minutes_before_session_end
                )
            ):
                minutes_to_close = self.session_guard.minutes_to_session_end()
                return False, (
                    f"SESSION GUARD blocked order: within EOD no-new-trades window ({minutes_to_close:.1f}m to close)"
                )

        if self.state.daily_pnl <= limits.daily_loss_cap:
            reason = f"DAILY LOSS CAP breached: {self.state.daily_pnl:.2f} USD <= {limits.daily_loss_cap:.2f}"
            self._engage_kill_switch("daily_loss_cap", reason)
            return False, reason

        if self.state.consecutive_losses >= limits.max_consecutive_losses:
            if self.state.last_loss_time:
                elapsed = _utcnow() - self.state.last_loss_time
                cooldown_minutes = max(limits.cooldown_after_streak, limits.session_cooldown_minutes)
                cooldown_period = timedelta(minutes=cooldown_minutes)
                if elapsed < cooldown_period:
                    remaining = cooldown_period - elapsed
                    reason = (
                        f"LOSS STREAK COOLDOWN: {self.state.consecutive_losses} consecutive losses, "
                        f"{remaining.total_seconds():.0f}s remaining"
                    )
                    return False, reason
                logger.info("Loss streak cooldown expired; resetting consecutive loss counter")
                self.state.consecutive_losses = 0
            else:
                reason = f"MAX CONSECUTIVE LOSSES breached: {self.state.consecutive_losses} >= {limits.max_consecutive_losses}"
                self._engage_kill_switch("max_consecutive_losses", reason)
                return False, reason

        total_open_risk = sum(float(v) for v in self.state.open_risk_by_symbol.values()) + float(proposed_risk)  # type: ignore[misc]
        if total_open_risk > limits.max_total_open_risk:
            reason = f"MAX TOTAL OPEN RISK exceeded: {total_open_risk:.2f} > {limits.max_total_open_risk:.2f}"
            self.state.portfolio_var_breached = True
            self.state.portfolio_var_reason = reason
            return False, reason

        if self.portfolio_var_allocator is not None:
            ok, var_reason, snapshot = self.portfolio_var_allocator.evaluate_proposed_trade(
                symbol=symbol,
                proposed_risk=proposed_risk,
                open_risk_by_symbol=self.state.open_risk_by_symbol,
            )
            self.state.portfolio_var_usd = float(snapshot.var_usd)
            self.state.portfolio_var_limit_usd = float(snapshot.max_var_usd)
            self.state.portfolio_var_breached = bool(snapshot.breached)
            self.state.portfolio_var_reason = str(snapshot.reason)
            if not ok:
                return False, var_reason
        else:
            self.state.portfolio_var_breached = False
            self.state.portfolio_var_reason = "Portfolio VaR allocator unavailable"

        var_ok, var_reason, _payload = self.check_var_es_pre_trade(float(proposed_risk))
        if not var_ok:
            return False, var_reason

        mc_ok, mc_reason, _mc_payload = self.check_monte_carlo_drawdown_pre_trade(float(proposed_risk))
        if not mc_ok:
            return False, mc_reason

        if self.state.margin_tracker is not None:
            snapshot_conf = float(self.state.margin_tracker.snapshot.confidence)
            if snapshot_conf < float(limits.margin_min_confidence):
                conf_reason = (
                    "CME MARGIN snapshot confidence too low: "
                    f"confidence={snapshot_conf:.3f} < min={float(limits.margin_min_confidence):.3f}"
                )
                if self.enforce_rules and (not self.limits.sim_mode):
                    return False, conf_reason
                logger.warning(conf_reason)

            if self.state.margin_tracker.is_snapshot_stale():
                status = self.state.margin_tracker.snapshot_status()
                stale_reason = (
                    "CME MARGIN snapshot stale: "
                    f"age={status['age_hours']}h > ttl={status['stale_after_hours']}h "
                    f"source={status['source']}"
                )
                if self.enforce_rules and (not self.limits.sim_mode):
                    return False, stale_reason
                logger.warning(stale_reason)

            total_margin_used = sum(
                self.state.margin_tracker.get_margin_requirement(sym) for sym in self.state.open_risk_by_symbol.keys()
            )
            if not self.state.margin_tracker.can_open_position(symbol, total_margin_used, safety_buffer_pct=0.2):
                margin_avail = self.state.margin_tracker.available_margin(total_margin_used)
                margin_req = self.state.margin_tracker.get_margin_requirement(symbol)
                reason = f"CME MARGIN insufficient for {symbol}: {margin_req:.0f} required, {margin_avail:.0f} available (20% buffer applied)"
                return False, reason

        current_symbol_risk = self.state.open_risk_by_symbol.get(symbol, 0.0)
        total_symbol_risk = current_symbol_risk + proposed_risk
        if total_symbol_risk > limits.max_open_risk_per_instrument:
            reason = f"MAX INSTRUMENT RISK exceeded for {symbol}: {total_symbol_risk:.2f} > {limits.max_open_risk_per_instrument:.2f}"
            return False, reason

        current_regime_risk = self.state.open_risk_all_regimes.get(regime, 0.0)
        total_regime_risk = current_regime_risk + proposed_risk
        if total_regime_risk > limits.max_exposure_per_regime:
            reason = f"MAX REGIME EXPOSURE exceeded for {regime}: {total_regime_risk:.2f} > {limits.max_exposure_per_regime:.2f}"
            return False, reason

        return True, "OK"

    def _engage_kill_switch(self, rule: str, reason: str) -> None:
        if self.state.kill_switch_engaged:
            return

        self.state.kill_switch_engaged = True
        self.state.kill_switch_reason = f"{rule}: {reason}"
        self.state.kill_switch_time = _utcnow()

        logger.critical(
            f"!!! KILL SWITCH ENGAGED !!!\nReason: {self.state.kill_switch_reason}\n"
            f"Time: {self.state.kill_switch_time}\nNO NEW ORDERS ALLOWED"
        )

        self._save_state()

    def reset_kill_switch(self, authorization_code: str = "") -> bool:
        if not self.state.kill_switch_engaged:
            logger.info("Kill-switch is not engaged, no reset needed")
            return True

        logger.warning(f"Resetting kill-switch. Previous reason: {self.state.kill_switch_reason}")
        self.state.kill_switch_engaged = False
        self.state.kill_switch_reason = ""
        self.state.kill_switch_time = None
        self._save_state()
        return True

    def set_enforce_rules(self, enforce: bool) -> None:
        mode_str = "ENFORCED" if enforce else "LEARNING/TESTING (rules bypassed)"
        logger.info(f"Risk enforcement changed: {mode_str}")
        self.enforce_rules = enforce

    def health_check_market_open(self, symbol: str, regime: str) -> tuple[bool, str]:
        if not self.enforce_rules:
            return True, "Market open health check passed (learning mode)"

        if self.state.kill_switch_engaged:
            return False, f"KILL SWITCH ENGAGED at market open: {self.state.kill_switch_reason}"

        limits = self._active_limits
        if self.state.consecutive_losses >= limits.max_consecutive_losses and self.state.last_loss_time:
            elapsed = _utcnow() - self.state.last_loss_time
            cooldown_minutes = max(limits.cooldown_after_streak, limits.session_cooldown_minutes)
            cooldown_period = timedelta(minutes=cooldown_minutes)
            if elapsed < cooldown_period:
                remaining = cooldown_period - elapsed
                return False, f"LOSS STREAK COOLDOWN active: {remaining.total_seconds():.0f}s remaining"

        logger.info(
            f"Market open health check passed. Daily P&L: {self.state.daily_pnl:.2f}, "
            f"Consecutive losses: {self.state.consecutive_losses}"
        )
        return True, "Market open health check passed"

    def get_status(self) -> dict:
        return {
            "daily_pnl": self.state.daily_pnl,
            "daily_pnl_cap": self._active_limits.daily_loss_cap,
            "daily_pnl_remaining": self._active_limits.daily_loss_cap - self.state.daily_pnl,
            "consecutive_losses": self.state.consecutive_losses,
            "max_consecutive_losses": self._active_limits.max_consecutive_losses,
            "last_loss_time": self.state.last_loss_time.isoformat() if self.state.last_loss_time else None,
            "cooldown_remaining_minutes": self._cooldown_remaining_minutes(),
            "open_risk_by_symbol": dict(self.state.open_risk_by_symbol),
            "open_risk_by_regime": dict(self.state.open_risk_all_regimes),
            "kill_switch_engaged": self.state.kill_switch_engaged,
            "kill_switch_reason": self.state.kill_switch_reason,
            "kill_switch_time": self.state.kill_switch_time.isoformat() if self.state.kill_switch_time else None,
            "active_regime": self.state.active_regime,
            "active_risk_state": self.state.active_risk_state,
            "active_limits": {
                "daily_loss_cap": self._active_limits.daily_loss_cap,
                "max_consecutive_losses": self._active_limits.max_consecutive_losses,
                "max_open_risk_per_instrument": self._active_limits.max_open_risk_per_instrument,
                "max_total_open_risk": self._active_limits.max_total_open_risk,
                "max_exposure_per_regime": self._active_limits.max_exposure_per_regime,
                "cooldown_after_streak": self._active_limits.cooldown_after_streak,
                "session_cooldown_minutes": self._active_limits.session_cooldown_minutes,
                "enforce_session_guard": self._active_limits.enforce_session_guard,
            },
            "portfolio_var": {
                "value_usd": self.state.portfolio_var_usd,
                "limit_usd": self.state.portfolio_var_limit_usd,
                "breached": self.state.portfolio_var_breached,
                "reason": self.state.portfolio_var_reason,
            },
            "var_es": {
                "var_95_usd": self.state.var_95_usd,
                "var_99_usd": self.state.var_99_usd,
                "es_95_usd": self.state.es_95_usd,
                "es_99_usd": self.state.es_99_usd,
                "breached": self.state.var_es_breached,
                "reason": self.state.var_es_reason,
                "method": self._active_limits.var_es_method,
                "window": self._active_limits.var_es_window,
            },
            "monte_carlo_drawdown": {
                "p50_pct": self.state.mc_drawdown_p50_pct,
                "p95_pct": self.state.mc_drawdown_p95_pct,
                "p99_pct": self.state.mc_drawdown_p99_pct,
                "projected_max_pct": self.state.mc_drawdown_worst_pct,
                "threshold_pct": self.state.mc_drawdown_threshold_pct,
                "breached": self.state.mc_drawdown_breached,
                "reason": self.state.mc_drawdown_reason,
                "samples": self.state.mc_drawdown_samples,
                "paths_run": self.state.mc_drawdown_paths_run,
            },
            "margin_snapshot": (
                self.state.margin_tracker.snapshot_status()
                if self.state.margin_tracker is not None
                else {"source": "unavailable", "stale": True}
            ),
            "recent_trades": list(self.state.trade_history)[-10:],
        }

    def _cooldown_remaining_minutes(self) -> float:
        if not self.state.last_loss_time or self.state.consecutive_losses < self._active_limits.max_consecutive_losses:
            return 0.0

        elapsed = _utcnow() - self.state.last_loss_time
        cooldown_minutes = max(
            self._active_limits.cooldown_after_streak,
            self._active_limits.session_cooldown_minutes,
        )
        cooldown_period = timedelta(minutes=cooldown_minutes)
        remaining = cooldown_period - elapsed

        return max(0.0, remaining.total_seconds() / 60.0)

    def should_force_close_eod(self) -> tuple[bool, str]:
        if self.limits.sim_mode or not self.enforce_rules:
            return False, "SIM/learning mode"
        limits = self._active_limits
        if not limits.enforce_session_guard:
            return False, "session guard disabled"
        if self.session_guard is None:
            return False, "session guard unavailable"
        window = int(limits.eod_force_close_minutes_before_session_end)
        if window <= 0:
            return False, "force-close window disabled"
        if self.session_guard.should_force_close_eod(force_close_minutes=window):
            mins = self.session_guard.minutes_to_session_end()
            return True, f"within EOD force-close window ({mins:.1f}m to close)"
        return False, "outside force-close window"
