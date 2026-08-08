from __future__ import annotations

import os
from typing import Any

import numpy as np


from lumina_core.risk.risk_allocator_var_es import RiskAllocatorVarEsMixin

class RiskAllocatorMixin(RiskAllocatorVarEsMixin):
    # Type stubs for mixin attributes provided by mixing class
    _active_limits: Any
    state: Any
    enforce_rules: bool

    # NOTE: `_portfolio_return_series` is implemented by RiskControllerStatusMixin.
    # Do not stub it here — MRO would otherwise shadow the real implementation.

    def _mc_enforcement_enabled(self) -> bool:
        mode = str(self._active_limits.runtime_mode or "sim").strip().lower()
        if not self.enforce_rules:
            return False
        if mode == "real":
            return bool(self._active_limits.enable_mc_drawdown_enforce_real)
        if mode == "sim_real_guard":
            return bool(self._active_limits.enable_mc_drawdown_enforce_sim_real_guard)
        return False

    def _should_fail_closed_on_mc_data(self) -> bool:
        limits = self._active_limits
        mode = str(limits.runtime_mode or "sim").strip().lower()
        policy = str(limits.mc_drawdown_insufficient_data_policy or "fail_closed_real_only").strip().lower()
        if policy == "advisory":
            return False
        if policy == "fail_closed_all_enforced":
            return bool(self._mc_enforcement_enabled())
        if policy == "fail_closed_real_only":
            return bool(self._mc_enforcement_enabled() and mode == "real")
        return False

    def _regime_transition_weights(self) -> dict[str, dict[str, float]]:
        history: list[str] = []
        history.extend(
            str(item.get("label", "NEUTRAL") or "NEUTRAL").upper()
            for item in self.state.regime_detector_history
            if isinstance(item, dict)
        )
        history.extend(
            str(item.get("label", "NEUTRAL") or "NEUTRAL").upper()
            for item in self.state.regime_history
            if isinstance(item, dict)
        )
        if len(history) < 2:
            return {}
        transitions: dict[str, dict[str, float]] = {}
        for idx in range(len(history) - 1):
            src = history[idx]
            dst = history[idx + 1]
            bucket = transitions.setdefault(src, {})
            bucket[dst] = float(bucket.get(dst, 0.0) + 1.0)
        for src, bucket in transitions.items():
            total = max(1.0, sum(bucket.values()))
            transitions[src] = {k: float(v / total) for k, v in bucket.items()}
        return transitions

    def _regime_return_buckets(self) -> dict[str, list[float]]:
        buckets: dict[str, list[float]] = {}
        for item in list(self.state.regime_detector_history):
            if not isinstance(item, dict):
                continue
            regime = str(item.get("label", self.state.active_regime) or self.state.active_regime).upper()
            ret = float(item.get("return_pct", 0.0) or 0.0)
            buckets.setdefault(regime, []).append(float(np.clip(ret, -0.95, 0.95)))
        for trade in list(self.state.trade_history):
            if not isinstance(trade, dict):
                continue
            regime = str(trade.get("regime", self.state.active_regime) or self.state.active_regime).upper()
            pnl = float(trade.get("pnl", 0.0) or 0.0)
            risk_taken = max(1.0, abs(float(trade.get("risk_taken", 0.0) or 0.0)))
            buckets.setdefault(regime, []).append(float(pnl / risk_taken))
        return buckets

    @staticmethod
    def _sample_next_regime(
        current: str, transition_weights: dict[str, dict[str, float]], rng: np.random.Generator
    ) -> str:
        bucket = transition_weights.get(current, {})
        if not bucket:
            return current
        labels = list(bucket.keys())
        probs = np.asarray([float(bucket[label]) for label in labels], dtype=np.float64)
        if float(probs.sum()) <= 0.0:
            return current
        probs = probs / probs.sum()
        idx = int(rng.choice(len(labels), p=probs))
        return labels[idx]

    def _simulate_path_drawdown_pct(
        self,
        *,
        regime_returns: dict[str, list[float]],
        global_returns: list[float],
        transition_weights: dict[str, dict[str, float]],
        exposure_scale: float,
        start_regime: str,
        rng: np.random.Generator,
    ) -> float:
        equity = 1.0
        peak = 1.0
        max_drawdown = 0.0
        regime = str(start_regime or "NEUTRAL").upper()
        horizon = max(1, int(self._active_limits.mc_drawdown_horizon_days))
        for _ in range(horizon):
            series = regime_returns.get(regime) or global_returns
            sampled = float(rng.choice(series)) if series else 0.0
            scaled = float(np.clip(sampled * exposure_scale, -0.95, 0.95))
            equity = max(1e-6, equity * (1.0 + scaled))
            peak = max(peak, equity)
            drawdown = (peak - equity) / max(peak, 1e-9)
            max_drawdown = max(max_drawdown, drawdown)
            regime = self._sample_next_regime(regime, transition_weights, rng)
        return float(max_drawdown * 100.0)

    def check_monte_carlo_drawdown_pre_trade(
        self, proposed_risk: float
    ) -> tuple[bool, str, dict[str, float | str | bool | list[float]]]:
        limits = self._active_limits
        mode = str(limits.runtime_mode or "sim").strip().lower()
        threshold_pct = float(limits.mc_drawdown_threshold_pct)
        if not bool(limits.enable_mc_drawdown_calc):
            payload = {
                "breached": False,
                "decision": "allow",
                "mode": mode,
                "paths": 0.0,
                "horizon_days": float(limits.mc_drawdown_horizon_days),
                "projected_max_drawdown_pct": 0.0,
                "threshold_pct": threshold_pct,
                "distribution": [],
                "reason_code": "MC_DISABLED",
            }
            self.state.mc_drawdown_breached = False
            self.state.mc_drawdown_reason = "Monte Carlo drawdown disabled"
            return True, self.state.mc_drawdown_reason, payload

        global_returns = self._portfolio_return_series()
        min_samples = max(10, int(limits.mc_drawdown_min_samples))
        if len(global_returns) < min_samples:
            should_block = bool(self._should_fail_closed_on_mc_data())
            reason = f"MC insufficient return samples ({len(global_returns)} < {min_samples})"
            self.state.mc_drawdown_breached = should_block
            self.state.mc_drawdown_reason = reason
            self.state.mc_drawdown_samples = int(len(global_returns))
            payload = {
                "breached": should_block,
                "decision": "block" if should_block else "allow",
                "mode": mode,
                "paths": 0.0,
                "horizon_days": float(limits.mc_drawdown_horizon_days),
                "projected_max_drawdown_pct": 0.0,
                "threshold_pct": threshold_pct,
                "distribution": [],
                "reason_code": "MC_INSUFFICIENT_DATA",
                "samples": float(len(global_returns)),
            }
            return (not should_block), reason, payload

        regime_returns = self._regime_return_buckets()
        transition_weights = self._regime_transition_weights()
        current_exposure = sum(float(v) for v in self.state.open_risk_by_symbol.values())  # type: ignore[misc]
        total_exposure = max(0.0, current_exposure + float(proposed_risk))
        max_exposure = max(1.0, float(limits.max_total_open_risk))
        exposure_scale = max(0.25, min(2.0, total_exposure / max_exposure))
        start_regime = str(self.state.active_regime or "NEUTRAL").upper()

        seed = int(limits.mc_drawdown_random_seed) + int(len(self.state.trade_history))
        rng = np.random.default_rng(seed)
        configured_path_count = int(max(1000, limits.mc_drawdown_paths))
        horizon_days = max(1, int(limits.mc_drawdown_horizon_days))
        max_steps = int(max(100_000, float(os.getenv("LUMINA_MC_DRAWDOWN_MAX_STEPS", "500000"))))
        max_paths_for_budget = max(1000, max_steps // horizon_days)
        effective_path_count = int(min(configured_path_count, max_paths_for_budget))
        dist: list[float] = []
        for _ in range(effective_path_count):
            dist.append(
                self._simulate_path_drawdown_pct(
                    regime_returns=regime_returns,
                    global_returns=global_returns,
                    transition_weights=transition_weights,
                    exposure_scale=exposure_scale,
                    start_regime=start_regime,
                    rng=rng,
                )
            )

        dist_arr = np.asarray(dist, dtype=np.float64)
        p50 = float(np.quantile(dist_arr, 0.50))
        p95 = float(np.quantile(dist_arr, 0.95))
        p99 = float(np.quantile(dist_arr, 0.99))
        worst = float(dist_arr.max()) if dist else 0.0

        self.state.mc_drawdown_p50_pct = p50
        self.state.mc_drawdown_p95_pct = p95
        self.state.mc_drawdown_p99_pct = p99
        self.state.mc_drawdown_worst_pct = worst
        self.state.mc_drawdown_threshold_pct = threshold_pct
        self.state.mc_drawdown_samples = int(len(global_returns))
        self.state.mc_drawdown_paths_run = int(effective_path_count)

        breached = bool(worst > threshold_pct)
        should_block = bool(breached and self._mc_enforcement_enabled())
        self.state.mc_drawdown_breached = breached
        self.state.mc_drawdown_reason = (
            f"MC projected max drawdown {worst:.2f}% > threshold {threshold_pct:.2f}%" if breached else "MC drawdown OK"
        )

        payload = {
            "breached": breached,
            "decision": "block" if should_block else "allow",
            "mode": mode,
            "paths": float(configured_path_count),
            "paths_effective": float(effective_path_count),
            "horizon_days": float(limits.mc_drawdown_horizon_days),
            "projected_max_drawdown_pct": worst,
            "p50_max_drawdown_pct": p50,
            "p95_max_drawdown_pct": p95,
            "p99_max_drawdown_pct": p99,
            "threshold_pct": threshold_pct,
            "samples": float(len(global_returns)),
            "distribution": [float(x) for x in dist[-256:]],
            "reason_code": "MC_DRAWDOWN_BREACH" if breached else "MC_DRAWDOWN_OK",
        }
        if should_block:
            return False, self.state.mc_drawdown_reason, payload
        return True, self.state.mc_drawdown_reason, payload

    def get_monte_carlo_snapshot(self, *, proposed_risk: float = 0.0) -> dict[str, float | str | bool | list[float]]:
        _ok, _reason, payload = self.check_monte_carlo_drawdown_pre_trade(proposed_risk=float(proposed_risk))
        return payload

