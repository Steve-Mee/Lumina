from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import traceback
from typing import Any, Optional

import numpy as np

from lumina_core.config_loader import ConfigLoader
from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured
from lumina_core.engine.margin_snapshot_provider import MarginSnapshot, MarginSnapshotProvider
from lumina_core.risk.risk_allocator import RiskAllocatorMixin
from lumina_core.risk.risk_gates import RiskGatesMixin
from lumina_core.risk.risk_policy import RiskPolicy, get_effective_risk_overlay, load_risk_policy

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


@dataclass
class MarginTracker:
    """Track CME futures margin requirements per instrument."""

    snapshot: MarginSnapshot = field(default_factory=MarginSnapshotProvider.from_config)
    account_equity: float = 50000.0

    def get_margin_requirement(self, symbol: str) -> float:
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
        return max(0.0, self.account_equity - positions_margin_used)

    def can_open_position(self, symbol: str, positions_margin_used: float, safety_buffer_pct: float = 0.2) -> bool:
        required_margin = self.get_margin_requirement(symbol)
        available = self.available_margin(positions_margin_used)
        margin_with_buffer = required_margin * (1.0 + safety_buffer_pct)
        return available >= margin_with_buffer

    def margin_utilization_pct(self, positions_margin_used: float) -> float:
        if self.account_equity <= 0:
            return 100.0
        return (positions_margin_used / self.account_equity) * 100.0


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


@dataclass
class RiskState:
    daily_pnl: float = 0.0
    consecutive_losses: int = 0
    last_loss_time: Optional[datetime] = None
    open_risk_by_symbol: dict[str, float] = field(default_factory=dict)
    symbol_regime_map: dict[str, str] = field(default_factory=dict)
    open_risk_all_regimes: dict[str, float] = field(default_factory=dict)
    kill_switch_engaged: bool = False
    kill_switch_reason: str = ""
    kill_switch_time: Optional[datetime] = None
    trade_history: deque = field(default_factory=lambda: deque(maxlen=100))
    active_regime: str = "NEUTRAL"
    active_risk_state: str = "NORMAL"
    portfolio_var_usd: float = 0.0
    portfolio_var_limit_usd: float = 1200.0
    portfolio_var_breached: bool = False
    portfolio_var_reason: str = ""
    var_95_usd: float = 0.0
    var_99_usd: float = 0.0
    es_95_usd: float = 0.0
    es_99_usd: float = 0.0
    var_es_breached: bool = False
    var_es_reason: str = ""
    mc_drawdown_p50_pct: float = 0.0
    mc_drawdown_p95_pct: float = 0.0
    mc_drawdown_p99_pct: float = 0.0
    mc_drawdown_worst_pct: float = 0.0
    mc_drawdown_threshold_pct: float = 0.0
    mc_drawdown_breached: bool = False
    mc_drawdown_reason: str = ""
    mc_drawdown_samples: int = 0
    mc_drawdown_paths_run: int = 0
    regime_history: deque = field(default_factory=lambda: deque(maxlen=2000))
    regime_detector_history: deque = field(default_factory=lambda: deque(maxlen=5000))
    regime_detector_last_anchor: str = ""
    margin_tracker: Optional[MarginTracker] = field(default_factory=MarginTracker)


class HardRiskController(RiskAllocatorMixin, RiskGatesMixin):
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

    def record_trade_result(self, symbol: str, regime: str, pnl: float, risk_taken: float) -> None:
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

    def _portfolio_return_series(self) -> list[float]:
        window = max(20, int(self._active_limits.var_es_window))
        returns: list[float] = []
        for trade in list(self.state.trade_history)[-window:]:
            pnl = float(trade.get("pnl", 0.0) or 0.0)
            risk_taken = float(trade.get("risk_taken", 0.0) or 0.0)
            denom = max(abs(risk_taken), 1.0)
            returns.append(pnl / denom)
        return returns

    def record_regime_snapshot(self, snapshot: dict[str, Any] | None) -> None:
        if not isinstance(snapshot, dict):
            return
        label = str(snapshot.get("label", self.state.active_regime) or self.state.active_regime).upper()
        features = snapshot.get("features", {}) if isinstance(snapshot.get("features", {}), dict) else {}
        self.state.regime_history.append(
            {
                "ts": _utcnow().isoformat(),
                "label": label,
                "risk_state": str(snapshot.get("risk_state", "NORMAL") or "NORMAL").upper(),
                "realized_vol_ratio": float(features.get("realized_vol_ratio", 1.0) or 1.0),
            }
        )

    def record_regime_detector_history(self, *, detector: Any, market_df: Any, instrument: str) -> int:
        if detector is None or market_df is None:
            return 0
        if not all(hasattr(market_df, attr) for attr in ("tail", "reset_index", "iloc", "columns")):
            return 0
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        try:
            columns = set(str(col) for col in list(market_df.columns))
        except _HANDLED_RISK_EXCEPTIONS as _exc:
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="RISK_REGIME_HISTORY_004",
                    message=str(_exc),
                    context={"traceback": traceback.format_exc()},
                )
            )
            return 0
        if not required.issubset(columns):
            return 0

        try:
            anchor = str(market_df.iloc[-1].get("timestamp", "") or "")
        except _HANDLED_RISK_EXCEPTIONS as _exc:
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="RISK_REGIME_HISTORY_005",
                    message=str(_exc),
                    context={"traceback": traceback.format_exc()},
                )
            )
            return 0
        if anchor and anchor == self.state.regime_detector_last_anchor:
            return 0

        lookback = max(20, int(getattr(detector, "lookback_bars", 120) or 120))
        stride = max(1, min(10, lookback // 12))
        max_windows = 300
        tail_size = max(lookback + 2, lookback + (max_windows * stride))
        try:
            rows = market_df.tail(tail_size).reset_index(drop=True)
        except _HANDLED_RISK_EXCEPTIONS as _exc:
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="RISK_REGIME_HISTORY_006",
                    message=str(_exc),
                    context={"traceback": traceback.format_exc()},
                )
            )
            return 0
        if len(rows) <= lookback:
            return 0

        last_ts = ""
        if self.state.regime_detector_history:
            try:
                last_ts = str(self.state.regime_detector_history[-1].get("ts", "") or "")
            except _HANDLED_RISK_EXCEPTIONS as _exc:
                log_structured(
                    LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                        code="RISK_REGIME_HISTORY_007",
                        message=str(_exc),
                        context={"traceback": traceback.format_exc()},
                    )
                )
                last_ts = ""

        appended = 0
        for end_idx in range(lookback, len(rows), stride):
            window = rows.iloc[: end_idx + 1]
            try:
                snapshot = detector.detect(window, instrument=str(instrument))
            except _HANDLED_RISK_EXCEPTIONS as _exc:
                log_structured(
                    LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                        code="RISK_REGIME_DETECT_008",
                        message=str(_exc),
                        context={"traceback": traceback.format_exc()},
                    )
                )
                continue
            label = str(getattr(snapshot, "label", self.state.active_regime) or self.state.active_regime).upper()
            risk_state = str(getattr(snapshot, "risk_state", "NORMAL") or "NORMAL").upper()
            features = getattr(snapshot, "features", {}) or {}
            features = features if isinstance(features, dict) else {}
            ts = str(getattr(snapshot, "timestamp", "") or window.iloc[-1].get("timestamp", ""))
            if last_ts and ts and ts <= last_ts:
                continue

            close_now = float(window.iloc[-1].get("close", 0.0) or 0.0)
            close_prev = float(window.iloc[-2].get("close", close_now) or close_now)
            ret = 0.0 if abs(close_prev) < 1e-9 else (close_now - close_prev) / abs(close_prev)
            self.state.regime_detector_history.append(
                {
                    "ts": ts,
                    "label": label,
                    "risk_state": risk_state,
                    "realized_vol_ratio": float(features.get("realized_vol_ratio", 1.0) or 1.0),
                    "return_pct": float(np.clip(ret, -0.95, 0.95)),
                }
            )
            last_ts = ts
            appended += 1

        if anchor:
            self.state.regime_detector_last_anchor = anchor
        return appended


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
