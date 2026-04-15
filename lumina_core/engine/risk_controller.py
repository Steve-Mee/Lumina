# CANONICAL IMPLEMENTATION – v50 Living Organism
# Hard Risk Controller: Unbreakable Safety Layer
# Fail-closed architecture: blocks ALL trading when limits breached
# SIM mode: all caps bypassed – maximal learning
# REAL mode: all caps enforced – capital preservation only

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from collections import deque
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from .margin_snapshot_provider import MarginSnapshot, MarginSnapshotProvider

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class MarginTracker:
    """Track CME futures margin requirements per instrument (capital preservation)."""
    
    # CME maintenance margin requirements now come from MarginSnapshotProvider.
    snapshot: MarginSnapshot = field(default_factory=MarginSnapshotProvider.from_config)
    account_equity: float = 50000.0  # Current account equity
    
    def get_margin_requirement(self, symbol: str) -> float:
        """Get maintenance margin for a symbol. Defaults to 3% of equity if unknown."""
        symbol_upper = str(symbol).strip().upper()
        return self.snapshot.margins.get(symbol_upper, self.account_equity * 0.03)

    def is_snapshot_stale(self) -> bool:
        return bool(self.snapshot.stale)

    def snapshot_status(self) -> dict[str, Any]:
        return {
            "source": self.snapshot.source,
            "as_of": self.snapshot.as_of.isoformat(),
            "confidence": float(self.snapshot.confidence),
            "stale_after_hours": int(self.snapshot.stale_after_hours),
            "age_hours": float(round(self.snapshot.age_hours, 3)),
            "stale": bool(self.snapshot.stale),
        }
    
    def available_margin(self, positions_margin_used: float) -> float:
        """Calculate available margin after positions."""
        return max(0.0, self.account_equity - positions_margin_used)
    
    def can_open_position(self, symbol: str, positions_margin_used: float, safety_buffer_pct: float = 0.2) -> bool:
        """
        Check if we can open a position without violating CME margin requirements.
        safety_buffer_pct: keep this % of available margin as buffer (default 20%).
        """
        required_margin = self.get_margin_requirement(symbol)
        available = self.available_margin(positions_margin_used)
        margin_with_buffer = required_margin * (1.0 + safety_buffer_pct)
        return available >= margin_with_buffer
    
    def margin_utilization_pct(self, positions_margin_used: float) -> float:
        """Get margin utilization as percentage of account equity."""
        if self.account_equity <= 0:
            return 100.0
        return (positions_margin_used / self.account_equity) * 100.0


@dataclass
class RiskLimits:
    """Risk configuration limits (from config.yaml)."""
    daily_loss_cap: float = -1000.0  # USD: max daily loss before hard stop
    max_consecutive_losses: int = 3  # trades in a row
    max_open_risk_per_instrument: float = 500.0  # USD per symbol
    max_total_open_risk: float = 3000.0  # USD across all symbols
    max_exposure_per_regime: float = 2000.0  # USD across all symbols in regime
    cooldown_after_streak: int = 30  # minutes to halt trading after loss streak
    session_cooldown_minutes: int = 15  # minimum intraday cooldown after streak
    enforce_session_guard: bool = True  # fail-closed when calendar data unavailable
    eod_force_close_minutes_before_session_end: int = 30  # force-close window in REAL mode
    eod_no_new_trades_minutes_before_session_end: int = 60  # block new entries near EOD in REAL mode
    margin_min_confidence: float = 0.6  # minimum snapshot confidence required in REAL enforced mode
    sim_mode: bool = False  # SIM=True bypasses all caps; REAL=False enforces them
    
    def validate(self) -> bool:
        """Validate that limits are sensible."""
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
        return True


@dataclass
class RiskState:
    """Current risk state tracking (runtime)."""
    daily_pnl: float = 0.0  # accumulated P&L today
    consecutive_losses: int = 0  # count of consecutive losing trades
    last_loss_time: Optional[datetime] = None  # when last loss occurred
    open_risk_by_symbol: dict[str, float] = field(default_factory=dict)  # symbol -> open risk
    open_risk_all_regimes: dict[str, float] = field(default_factory=dict)  # regime -> total exposure
    kill_switch_engaged: bool = False  # hard stop: no new orders allowed
    kill_switch_reason: str = ""  # why kill switch was engaged
    kill_switch_time: Optional[datetime] = None  # when kill switch was engaged
    trade_history: deque = field(default_factory=lambda: deque(maxlen=100))  # last 100 trades for analysis
    active_regime: str = "NEUTRAL"
    active_risk_state: str = "NORMAL"
    portfolio_var_usd: float = 0.0
    portfolio_var_limit_usd: float = 1200.0
    portfolio_var_breached: bool = False
    portfolio_var_reason: str = ""
    margin_tracker: Optional[MarginTracker] = field(default_factory=MarginTracker)  # Capital preservation


class HardRiskController:
    """
    Unbreakable safety layer for Lumina trading.
    
    Every trade decision MUST pass through these checks:
    1. Daily loss cap check
    2. Consecutive loss check (+ cooldown)
    3. Per-instrument risk check
    4. Per-regime exposure check
    5. Kill-switch override (emergency stop)
    
    Architecture:
    - FIRST check: immediately after market open (in lumina_engine._run_cycle)
    - LAST check: just before order submission (in trade_workers.submit_order)
    - Fail-closed: any check failure = NO TRADING
    """
    
    def __init__(
        self,
        limits: RiskLimits,
        state_file: Optional[Path] = None,
        enforce_rules: bool = True,
        regime_limit_overrides: Optional[dict[str, dict[str, float | int]]] = None,
        session_guard=None,
        portfolio_var_allocator=None,
    ):
        """
        Initialize risk controller with limits and optional state persistence.
        
        Args:
            limits: RiskLimits configuration
            state_file: Optional path to persist kill-switch state across restarts
            enforce_rules: If False, risk rules are bypassed (for learning/testing/backtesting)
        """
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
                from .session_guard import SessionGuard  # noqa: PLC0415

                self.session_guard = SessionGuard(calendar_name="CME")
            except Exception as exc:
                logger.error("SessionGuard init failed: %s", exc)
                self.session_guard = None
        
        mode_str = "ENFORCED" if enforce_rules else "LEARNING/TESTING MODE (rules bypassed)"
        logger.info(f"HardRiskController initialized with limits: {limits}")
        logger.info(f"Risk enforcement: {mode_str}")
        
        # Load persistent state if available (e.g., kill-switch from previous crash)
        if self.state_file and self.state_file.exists():
            self._load_state()

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
            override_cfg.get("max_open_risk_per_instrument", self._base_limits.max_open_risk_per_instrument * multiplier)
        )
        max_regime_risk = float(
            override_cfg.get("max_exposure_per_regime", self._base_limits.max_exposure_per_regime * multiplier)
        )
        base_cooldown = self._base_limits.cooldown_after_streak
        cooldown = int(
            override_cfg.get(
                "cooldown_after_streak",
                cooldown_after_streak if cooldown_after_streak is not None else max(base_cooldown, int(base_cooldown / max(multiplier, 0.25))),
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
        )
        self.state.active_regime = normalized_regime
        self.state.active_risk_state = normalized_risk_state
    
    def _load_state(self) -> None:
        """Load persistent state from disk (kill-switch, daily_pnl recovery)."""
        try:
            if self.state_file is None:
                return
            with open(str(self.state_file), 'r') as f:
                data = json.load(f)
                self.state.daily_pnl = data.get('daily_pnl', 0.0)
                self.state.consecutive_losses = data.get('consecutive_losses', 0)
                self.state.kill_switch_engaged = data.get('kill_switch_engaged', False)
                self.state.kill_switch_reason = data.get('kill_switch_reason', '')
                logger.info(f"Loaded persistent risk state: daily_pnl={self.state.daily_pnl}, "
                           f"kill_switch={self.state.kill_switch_engaged}")
        except Exception as e:
            logger.error(f"Failed to load risk state: {e}")
    
    def _save_state(self) -> None:
        """Persist state to disk (mainly for kill-switch recovery)."""
        if not self.state_file:
            return
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump({
                    'daily_pnl': self.state.daily_pnl,
                    'consecutive_losses': self.state.consecutive_losses,
                    'kill_switch_engaged': self.state.kill_switch_engaged,
                    'kill_switch_reason': self.state.kill_switch_reason,
                    'timestamp': _utcnow().isoformat(),
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save risk state: {e}")
    
    def reset_daily(self) -> None:
        """Reset daily P&L and loss counters (call at market close or next day open)."""
        logger.info(f"Resetting daily metrics. Previous daily_pnl={self.state.daily_pnl}, "
                   f"consecutive_losses={self.state.consecutive_losses}")
        self.state.daily_pnl = 0.0
        self.state.consecutive_losses = 0
        self.state.last_loss_time = None
        self.state.open_risk_by_symbol.clear()
        self.state.open_risk_all_regimes.clear()
        # Do NOT reset kill_switch here; it's persistent
        self._save_state()
    
    def record_trade_result(self, symbol: str, regime: str, pnl: float, risk_taken: float) -> None:
        """
        Record completed trade result and update risk state.
        
        Args:
            symbol: Instrument symbol
            regime: Market regime label
            pnl: Profit/loss from trade (positive or negative)
            risk_taken: Risk exposure that was on the trade
        """
        self.state.daily_pnl += pnl
        self.state.trade_history.append({
            'timestamp': _utcnow().isoformat(),
            'symbol': symbol,
            'regime': regime,
            'pnl': pnl,
            'risk_taken': risk_taken,
        })
        
        # Update consecutive loss counter
        if pnl < 0:
            self.state.consecutive_losses += 1
            self.state.last_loss_time = _utcnow()
            logger.warning(f"Loss recorded: {pnl:.2f} USD. Consecutive losses: {self.state.consecutive_losses}")
        else:
            self.state.consecutive_losses = 0
        
        self._save_state()
    
    def set_open_risk(self, symbol: str, regime: str, risk_amount: float) -> None:
        """
        Update open risk for a symbol/regime (called when opening positions).
        
        Args:
            symbol: Instrument symbol
            regime: Market regime
            risk_amount: Current risk exposure (USD)
        """
        self.state.open_risk_by_symbol[symbol] = risk_amount
        
        # Aggregate regime exposure
        regime_risk = sum(
            v for k, v in self.state.open_risk_by_symbol.items()
            if self._get_regime_for_symbol(k) == regime
        )
        self.state.open_risk_all_regimes[regime] = regime_risk
    
    def _get_regime_for_symbol(self, symbol: str) -> Optional[str]:
        """Get regime for a symbol (helper; in real code, query from RuntimeContext)."""
        # Placeholder: in actual integration, query from runtime_context.market_regime[symbol]
        for regime, symbols in self.state.open_risk_all_regimes.items():
            if symbol in str(symbols):
                return regime
        return None
    
    def check_can_trade(self, symbol: str, regime: str, proposed_risk: float) -> tuple[bool, str]:
        """
        Main entry point: check if new trade is allowed.
        
        Call this FIRST (immediately after market open) and LAST (before order submission).
        Fail-closed: any check failure = return (False, reason).
        
        In learning/testing/backtest mode, rules are bypassed (returns OK).
        
        Args:
            symbol: Instrument to trade
            regime: Current market regime
            proposed_risk: Risk amount for proposed trade (USD)
        
        Returns:
            (allowed: bool, reason: str)
        """
        # SIM mode: bypass all hard caps – organism learns freely
        if self.limits.sim_mode or not self.enforce_rules:
            return True, "OK (SIM learning mode – all caps bypassed)"

        # 1. Kill-switch check (highest priority, persistent)
        if self.state.kill_switch_engaged:
            return False, f"KILL SWITCH ENGAGED: {self.state.kill_switch_reason} (since {self.state.kill_switch_time})"
        
        # 2. Daily loss cap check
        limits = self._active_limits

        # 2a. Session guard (fail-closed when configured)
        if limits.enforce_session_guard:
            if self.session_guard is None:
                return False, "SESSION GUARD unavailable (fail-closed)"
            if self.session_guard.is_rollover_window():
                return False, "SESSION GUARD blocked order: rollover window active"
            if not self.session_guard.is_market_open():
                nxt = self.session_guard.next_open()
                suffix = f" | next_open={nxt.isoformat()}" if nxt is not None else ""
                return False, f"SESSION GUARD blocked order: market closed{suffix}"
            if limits.eod_no_new_trades_minutes_before_session_end > 0 and self.session_guard.should_block_new_eod_trades(
                no_new_trades_minutes=limits.eod_no_new_trades_minutes_before_session_end
            ):
                minutes_to_close = self.session_guard.minutes_to_session_end()
                return False, (
                    "SESSION GUARD blocked order: within EOD no-new-trades window "
                    f"({minutes_to_close:.1f}m to close)"
                )

        # 3. Daily loss cap check
        if self.state.daily_pnl <= limits.daily_loss_cap:
            reason = f"DAILY LOSS CAP breached: {self.state.daily_pnl:.2f} USD <= {limits.daily_loss_cap:.2f}"
            self._engage_kill_switch("daily_loss_cap", reason)
            return False, reason
        
        # 4. Consecutive loss streak + cooldown
        if self.state.consecutive_losses >= limits.max_consecutive_losses:
            if self.state.last_loss_time:
                elapsed = _utcnow() - self.state.last_loss_time
                cooldown_minutes = max(limits.cooldown_after_streak, limits.session_cooldown_minutes)
                cooldown_period = timedelta(minutes=cooldown_minutes)
                if elapsed < cooldown_period:
                    remaining = cooldown_period - elapsed
                    reason = f"LOSS STREAK COOLDOWN: {self.state.consecutive_losses} consecutive losses, " \
                            f"{remaining.total_seconds():.0f}s remaining"
                    return False, reason
                else:
                    # Cooldown period expired, reset counter
                    logger.info(f"Loss streak cooldown expired; resetting consecutive loss counter")
                    self.state.consecutive_losses = 0
            else:
                reason = f"MAX CONSECUTIVE LOSSES breached: {self.state.consecutive_losses} >= {limits.max_consecutive_losses}"
                self._engage_kill_switch("max_consecutive_losses", reason)
                return False, reason

        # 5. Portfolio-level VaR + total open risk check
        total_open_risk = sum(float(v) for v in self.state.open_risk_by_symbol.values()) + float(proposed_risk)
        if total_open_risk > limits.max_total_open_risk:
            reason = (
                f"MAX TOTAL OPEN RISK exceeded: {total_open_risk:.2f} > "
                f"{limits.max_total_open_risk:.2f}"
            )
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
        
        # 6. CME Margin requirement check (capital preservation)
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
                self.state.margin_tracker.get_margin_requirement(sym)
                for sym in self.state.open_risk_by_symbol.keys()
            )
            if not self.state.margin_tracker.can_open_position(symbol, total_margin_used, safety_buffer_pct=0.2):
                margin_avail = self.state.margin_tracker.available_margin(total_margin_used)
                margin_req = self.state.margin_tracker.get_margin_requirement(symbol)
                reason = f"CME MARGIN insufficient for {symbol}: {margin_req:.0f} required, {margin_avail:.0f} available (20% buffer applied)"
                return False, reason
        
        # 7. Per-instrument open risk check
        current_symbol_risk = self.state.open_risk_by_symbol.get(symbol, 0.0)
        total_symbol_risk = current_symbol_risk + proposed_risk
        if total_symbol_risk > limits.max_open_risk_per_instrument:
            reason = f"MAX INSTRUMENT RISK exceeded for {symbol}: {total_symbol_risk:.2f} > {limits.max_open_risk_per_instrument:.2f}"
            return False, reason
        
        # 8. Per-regime exposure check
        current_regime_risk = self.state.open_risk_all_regimes.get(regime, 0.0)
        total_regime_risk = current_regime_risk + proposed_risk
        if total_regime_risk > limits.max_exposure_per_regime:
            reason = f"MAX REGIME EXPOSURE exceeded for {regime}: {total_regime_risk:.2f} > {limits.max_exposure_per_regime:.2f}"
            return False, reason
        
        # All checks passed
        return True, "OK"
    
    def _engage_kill_switch(self, rule: str, reason: str) -> None:
        """
        Engage the hard kill-switch (persistent state).
        
        This is PERMANENT until manually reset (fail-closed safety model).
        """
        if self.state.kill_switch_engaged:
            return  # Already engaged
        
        self.state.kill_switch_engaged = True
        self.state.kill_switch_reason = f"{rule}: {reason}"
        self.state.kill_switch_time = _utcnow()
        
        logger.critical(f"!!! KILL SWITCH ENGAGED !!!\nReason: {self.state.kill_switch_reason}\n"
                       f"Time: {self.state.kill_switch_time}\nNO NEW ORDERS ALLOWED")
        
        self._save_state()
    
    def reset_kill_switch(self, authorization_code: str = "") -> bool:
        """
        Manually reset kill-switch (requires authorization in production).
        
        This is intentionally restricted to prevent accidental re-engagement of trading.
        In production, this should require:
        - Admin API key
        - Time delay (e.g., 5 minute cooldown)
        - Audit logging
        """
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
        """
        Change enforcement mode (learning/testing vs. live).
        
        Args:
            enforce: True for live mode (rules enforced), False for learning/testing
        """
        mode_str = "ENFORCED" if enforce else "LEARNING/TESTING (rules bypassed)"
        logger.info(f"Risk enforcement changed: {mode_str}")
        self.enforce_rules = enforce
    
    def health_check_market_open(self, symbol: str, regime: str) -> tuple[bool, str]:
        """
        FIRST check: called immediately after market open.
        Verifies risk state is healthy before trading begins.
        
        This is separate from check_can_trade to allow for initialization/warmup logic.
        
        Args:
            symbol: Primary trading symbol
            regime: Current market regime
        
        Returns:
            (healthy: bool, status_message: str)
        """
        if not self.enforce_rules:
            return True, "Market open health check passed (learning mode)"
        
        # Check if kill-switch is engaged
        if self.state.kill_switch_engaged:
            return False, f"KILL SWITCH ENGAGED at market open: {self.state.kill_switch_reason}"
        
        # Check if we're in cooldown
        limits = self._active_limits
        if self.state.consecutive_losses >= limits.max_consecutive_losses:
            if self.state.last_loss_time:
                elapsed = _utcnow() - self.state.last_loss_time
                cooldown_minutes = max(limits.cooldown_after_streak, limits.session_cooldown_minutes)
                cooldown_period = timedelta(minutes=cooldown_minutes)
                if elapsed < cooldown_period:
                    remaining = cooldown_period - elapsed
                    return False, f"LOSS STREAK COOLDOWN active: {remaining.total_seconds():.0f}s remaining"
        
        # All good
        logger.info(f"Market open health check passed. Daily P&L: {self.state.daily_pnl:.2f}, "
                   f"Consecutive losses: {self.state.consecutive_losses}")
        return True, "Market open health check passed"
    
    def get_status(self) -> dict:
        """Return current risk state for monitoring/dashboards."""
        return {
            'daily_pnl': self.state.daily_pnl,
            'daily_pnl_cap': self._active_limits.daily_loss_cap,
            'daily_pnl_remaining': self._active_limits.daily_loss_cap - self.state.daily_pnl,
            'consecutive_losses': self.state.consecutive_losses,
            'max_consecutive_losses': self._active_limits.max_consecutive_losses,
            'last_loss_time': self.state.last_loss_time.isoformat() if self.state.last_loss_time else None,
            'cooldown_remaining_minutes': self._cooldown_remaining_minutes(),
            'open_risk_by_symbol': dict(self.state.open_risk_by_symbol),
            'open_risk_by_regime': dict(self.state.open_risk_all_regimes),
            'kill_switch_engaged': self.state.kill_switch_engaged,
            'kill_switch_reason': self.state.kill_switch_reason,
            'kill_switch_time': self.state.kill_switch_time.isoformat() if self.state.kill_switch_time else None,
            'active_regime': self.state.active_regime,
            'active_risk_state': self.state.active_risk_state,
            'active_limits': {
                'daily_loss_cap': self._active_limits.daily_loss_cap,
                'max_consecutive_losses': self._active_limits.max_consecutive_losses,
                'max_open_risk_per_instrument': self._active_limits.max_open_risk_per_instrument,
                'max_total_open_risk': self._active_limits.max_total_open_risk,
                'max_exposure_per_regime': self._active_limits.max_exposure_per_regime,
                'cooldown_after_streak': self._active_limits.cooldown_after_streak,
                'session_cooldown_minutes': self._active_limits.session_cooldown_minutes,
                'enforce_session_guard': self._active_limits.enforce_session_guard,
                'eod_force_close_minutes_before_session_end': self._active_limits.eod_force_close_minutes_before_session_end,
                'eod_no_new_trades_minutes_before_session_end': self._active_limits.eod_no_new_trades_minutes_before_session_end,
                'margin_min_confidence': self._active_limits.margin_min_confidence,
            },
            'portfolio_var': {
                'value_usd': self.state.portfolio_var_usd,
                'limit_usd': self.state.portfolio_var_limit_usd,
                'breached': self.state.portfolio_var_breached,
                'reason': self.state.portfolio_var_reason,
            },
            'margin_snapshot': (
                self.state.margin_tracker.snapshot_status() if self.state.margin_tracker is not None else {
                    'source': 'unavailable',
                    'stale': True,
                }
            ),
            'recent_trades': list(self.state.trade_history)[-10:],
        }
    
    def _cooldown_remaining_minutes(self) -> float:
        """Calculate remaining cooldown time in minutes."""
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
        """Return whether REAL mode should force-close open positions near session end."""
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


# ---------------------------------------------------------------------------
# Public factory: mode-aware RiskLimits constructor
# ---------------------------------------------------------------------------

def risk_limits_from_config(config: dict[str, Any] | None = None) -> RiskLimits:
    """
    Build a RiskLimits from config.yaml honoring the top-level ``mode`` key.

    SIM mode (mode=="sim"):
      - sim_mode=True  → all hard caps bypassed in check_can_trade
      - daily_loss_cap overridden to a very large negative (effectively unlimited)
      - enforce_session_guard=False  (let organism trade freely in SIM)

    REAL mode (mode=="real" or any other value):
      - sim_mode=False  → all caps from risk_controller section are enforced
      - real profile overrides applied on top of risk_controller defaults
    """
    if config is None:
        try:
            import yaml as _yaml

            cfg_path = os.getenv("LUMINA_CONFIG", "config.yaml")
            with open(cfg_path, "r", encoding="utf-8") as _fh:
                config = _yaml.safe_load(_fh) or {}
        except Exception:
            config = {}

    global_mode = str(
        os.getenv("LUMINA_MODE")
        or os.getenv("TRADE_MODE")
        or config.get("mode", "sim")
    ).strip().lower()
    is_sim = global_mode == "sim"

    risk_cfg = config.get("risk_controller", {}) if isinstance(config.get("risk_controller"), dict) else {}
    trading_cfg = config.get("trading", {}) if isinstance(config.get("trading"), dict) else {}

    # Start with risk_controller section defaults
    daily_loss_cap = float(risk_cfg.get("daily_loss_cap", -1000.0) or -1000.0)
    max_consecutive_losses = int(risk_cfg.get("max_consecutive_losses", 3))
    max_open_risk_per_instrument = float(risk_cfg.get("max_open_risk_per_instrument", 500.0))
    max_total_open_risk = float(risk_cfg.get("max_total_open_risk", 3000.0))
    max_exposure_per_regime = float(risk_cfg.get("max_exposure_per_regime", 2000.0))
    cooldown_after_streak = int(risk_cfg.get("cooldown_after_streak", 30))
    session_cooldown_minutes = int(risk_cfg.get("session_cooldown_minutes", 15))
    enforce_session_guard = bool(risk_cfg.get("enforce_session_guard", True))
    eod_force_close_minutes_before_session_end = int(
        trading_cfg.get("eod_force_close_minutes_before_session_end", 30)
    )
    eod_no_new_trades_minutes_before_session_end = int(
        trading_cfg.get("eod_no_new_trades_minutes_before_session_end", 60)
    )
    margin_min_confidence = float(risk_cfg.get("margin_min_confidence", 0.6) or 0.6)

    if is_sim:
        # SIM: override to unlimited
        sim_profile = config.get("sim", {}) if isinstance(config.get("sim"), dict) else {}
        sim_daily_cap = sim_profile.get("daily_loss_cap", None)
        daily_loss_cap = float(sim_daily_cap) if sim_daily_cap is not None else -1_000_000.0
        enforce_session_guard = False  # SIM trades around the clock
        logger.info("[MODE=SIM] RiskLimits: all hard caps bypassed – MAXIMAL LEARNING MODE")
    else:
        # REAL: apply real profile overrides
        real_profile = config.get("real", {}) if isinstance(config.get("real"), dict) else {}
        if real_profile.get("daily_loss_cap") is not None:
            daily_loss_cap = float(real_profile["daily_loss_cap"])
        if real_profile.get("max_consecutive_losses") is not None:
            max_consecutive_losses = int(real_profile["max_consecutive_losses"])
        if real_profile.get("max_open_risk_per_instrument") is not None:
            max_open_risk_per_instrument = float(real_profile["max_open_risk_per_instrument"])
        if real_profile.get("max_total_open_risk") is not None:
            max_total_open_risk = float(real_profile["max_total_open_risk"])
        if real_profile.get("max_exposure_per_regime") is not None:
            max_exposure_per_regime = float(real_profile["max_exposure_per_regime"])
        if real_profile.get("cooldown_after_streak") is not None:
            cooldown_after_streak = int(real_profile["cooldown_after_streak"])
        if real_profile.get("session_cooldown_minutes") is not None:
            session_cooldown_minutes = int(real_profile["session_cooldown_minutes"])
        if real_profile.get("enforce_session_guard") is not None:
            enforce_session_guard = bool(real_profile["enforce_session_guard"])
        if real_profile.get("eod_force_close_minutes_before_session_end") is not None:
            eod_force_close_minutes_before_session_end = int(real_profile["eod_force_close_minutes_before_session_end"])
        if real_profile.get("eod_no_new_trades_minutes_before_session_end") is not None:
            eod_no_new_trades_minutes_before_session_end = int(real_profile["eod_no_new_trades_minutes_before_session_end"])
        if real_profile.get("margin_min_confidence") is not None:
            margin_min_confidence = float(real_profile["margin_min_confidence"])
        logger.info("[MODE=REAL] RiskLimits: capital preservation caps ENFORCED")

    return RiskLimits(
        daily_loss_cap=daily_loss_cap,
        max_consecutive_losses=max_consecutive_losses,
        max_open_risk_per_instrument=max_open_risk_per_instrument,
        max_total_open_risk=max_total_open_risk,
        max_exposure_per_regime=max_exposure_per_regime,
        cooldown_after_streak=cooldown_after_streak,
        session_cooldown_minutes=session_cooldown_minutes,
        enforce_session_guard=enforce_session_guard,
        eod_force_close_minutes_before_session_end=eod_force_close_minutes_before_session_end,
        eod_no_new_trades_minutes_before_session_end=eod_no_new_trades_minutes_before_session_end,
        margin_min_confidence=margin_min_confidence,
        sim_mode=is_sim,
    )
