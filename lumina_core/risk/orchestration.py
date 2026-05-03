from __future__ import annotations

from dataclasses import dataclass, field

from lumina_core.engine.engine_ports import SupportsRisk
from lumina_core.engine.session_guard import SessionGuard
from lumina_core.risk.dynamic_kelly import DynamicKellyEstimator
from lumina_core.risk.final_arbitration import FinalArbitration
from lumina_core.risk.risk_controller import HardRiskController, risk_limits_from_config
from lumina_core.risk.risk_policy import RiskPolicy, load_risk_policy


@dataclass(slots=True)
class RiskOrchestrator:
    """Owns risk-policy/risk-controller composition and adaptive sizing."""

    engine: SupportsRisk
    session_guard: SessionGuard | None = None
    risk_controller: HardRiskController | None = None
    risk_policy: RiskPolicy | None = None
    final_arbitration: FinalArbitration | None = None
    mode_risk_profile: dict[str, float] = field(default_factory=dict)
    dynamic_kelly_estimator: DynamicKellyEstimator | None = None

    def initialize(self) -> None:
        if self.session_guard is None:
            self.session_guard = SessionGuard(calendar_name="CME")

        if self.risk_controller is None:
            session_config = getattr(self.engine.config, "session", {})
            if not isinstance(session_config, dict):
                session_config = {}
            self.risk_policy = load_risk_policy(mode=str(getattr(self.engine.config, "trade_mode", "paper")))
            limits = risk_limits_from_config()
            limits.enforce_session_guard = bool(session_config.get("enforce_calendar", limits.enforce_session_guard))

            state_file = getattr(self.engine.config, "state_dir", None)
            if state_file:
                from pathlib import Path  # noqa: PLC0415

                state_file = Path(state_file) / "risk_controller_state.json"

            enforce_rules = self.engine.config.trade_mode == "real"
            self.risk_controller = HardRiskController(
                limits,
                state_file=state_file,
                enforce_rules=enforce_rules,
                session_guard=self.session_guard,
            )
        if self.risk_policy is None:
            self.risk_policy = load_risk_policy(mode=str(getattr(self.engine.config, "trade_mode", "paper")))
        if self.final_arbitration is None and self.risk_policy is not None:
            self.final_arbitration = FinalArbitration(self.risk_policy)

        self.mode_risk_profile = self._load_mode_risk_profile()
        self.dynamic_kelly_estimator = self._build_dynamic_kelly_estimator()

    def _load_mode_risk_profile(self) -> dict[str, float]:
        from lumina_core.config_loader import ConfigLoader  # noqa: PLC0415

        data = ConfigLoader.get()
        sim_policy = RiskPolicy.get_effective_policy(mode="sim", config=data)
        real_policy = RiskPolicy.get_effective_policy(mode="real", config=data)
        sim_kelly = float(sim_policy.kelly_fraction)
        real_kelly = float(real_policy.kelly_fraction)
        min_conf = float(real_policy.kelly_min_confidence)
        baseline = max(0.01, min(1.0, real_kelly))
        return {
            "sim_kelly_fraction": max(0.05, sim_kelly),
            "real_kelly_fraction": max(0.01, min(1.0, real_kelly)),
            "kelly_min_confidence": max(0.0, min(1.0, min_conf)),
            "kelly_baseline": baseline,
        }

    def _build_dynamic_kelly_estimator(self) -> DynamicKellyEstimator:
        rc = getattr(self.engine.config, "risk_controller", {})
        rc = rc if isinstance(rc, dict) else {}
        profile = self.mode_risk_profile if isinstance(self.mode_risk_profile, dict) else {}
        return DynamicKellyEstimator(
            window=int(rc.get("kelly_rolling_window", 50) or 50),
            min_kelly=0.01,
            fractional_kelly_real=float(profile.get("real_kelly_fraction", 0.25) or 0.25),
            fractional_kelly_sim=float(profile.get("sim_kelly_fraction", 1.0) or 1.0),
            config_fallback_real=float(profile.get("real_kelly_fraction", 0.25) or 0.25),
            config_fallback_sim=float(profile.get("sim_kelly_fraction", 1.0) or 1.0),
            vol_target_annual=float(rc.get("kelly_vol_target_annual", 0.15) or 0.15),
            vol_lookback_trades=int(rc.get("kelly_vol_lookback_trades", 20) or 20),
            vol_scaling_enabled=bool(rc.get("kelly_vol_scaling_enabled", True)),
        )

    def calculate_adaptive_risk_and_qty(
        self,
        price: float,
        regime: str,
        stop_price: float,
        confidence: float | None = None,
    ) -> int:
        multiplier = float(self.engine.config.regime_risk_multipliers.get(regime, 1.0))
        profile = self.mode_risk_profile if isinstance(self.mode_risk_profile, dict) else {}
        baseline_kelly = max(1e-6, float(profile.get("kelly_baseline", 0.25) or 0.25))
        mode = str(getattr(self.engine.config, "trade_mode", "paper") or "paper").strip().lower()
        try:
            dynamic_fraction = (
                self.dynamic_kelly_estimator.fractional_kelly(mode)
                if self.dynamic_kelly_estimator is not None
                else None
            )
        except Exception:
            dynamic_fraction = None

        if mode == "sim":
            static_fraction = float(profile.get("sim_kelly_fraction", 1.0) or 1.0)
            kelly_fraction = dynamic_fraction if dynamic_fraction is not None else static_fraction
            kelly_multiplier = max(1.0, kelly_fraction / baseline_kelly)
        elif mode == "real":
            static_fraction = float(profile.get("real_kelly_fraction", 0.25) or 0.25)
            kelly_fraction = dynamic_fraction if dynamic_fraction is not None else static_fraction
            kelly_multiplier = max(0.05, min(1.0, kelly_fraction / baseline_kelly))
        else:
            static_fraction = float(profile.get("real_kelly_fraction", 0.25) or 0.25)
            kelly_fraction = dynamic_fraction if dynamic_fraction is not None else static_fraction
            kelly_multiplier = max(0.05, min(1.0, kelly_fraction / baseline_kelly))

        kelly_min_conf = max(0.0, min(1.0, float(profile.get("kelly_min_confidence", 0.65) or 0.65)))
        conf_val = 1.0 if confidence is None else max(0.0, min(1.0, float(confidence)))
        if conf_val >= kelly_min_conf or kelly_min_conf <= 0.0:
            confidence_scale = 1.0
        else:
            confidence_scale = max(0.1, conf_val / max(kelly_min_conf, 1e-6))

        adaptive_risk_percent = self.engine.config.max_risk_percent * multiplier * kelly_multiplier * confidence_scale
        if mode == "real":
            adaptive_risk_percent = min(adaptive_risk_percent, float(self.engine.config.max_risk_percent))
        risk_dollars = self.engine.account_equity * (adaptive_risk_percent / 100)

        stop_distance = abs(price - stop_price)
        if stop_distance <= 0:
            stop_distance = price * 0.005
        instrument = str(getattr(self.engine.config, "instrument", "MES"))
        point_value = getattr(self.engine.valuation_engine, "point_value_for", lambda x: 1.0)(instrument)
        risk_per_contract = max(1e-9, stop_distance * point_value)
        if mode == "real" and (risk_dollars / risk_per_contract) < 1.0:
            if self.engine.app is not None and hasattr(self.engine.app, "logger"):
                self.engine.app.logger.warning(
                    "ADAPTIVE_RISK_REAL_FLOOR,reason=under_one_contract,"
                    f"risk_dollars={risk_dollars:.2f},risk_per_contract={risk_per_contract:.2f}"
                )
            return 0
        qty = max(1, int(risk_dollars / risk_per_contract))
        if self.engine.app is not None and hasattr(self.engine.app, "logger"):
            self.engine.app.logger.info(
                f"ADAPTIVE_RISK,mode={mode},regime={regime},kelly={kelly_fraction:.2f},"
                f"risk_percent={adaptive_risk_percent:.2f},qty={qty}"
            )
        return qty
