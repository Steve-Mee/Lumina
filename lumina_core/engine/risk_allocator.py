from __future__ import annotations

import math
import os
from statistics import NormalDist

import numpy as np


class RiskAllocatorMixin:
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
    def _sample_next_regime(current: str, transition_weights: dict[str, dict[str, float]], rng: np.random.Generator) -> str:
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

    def _calculate_var_es_pair(self, *, returns: list[float], confidence: float, method: str) -> tuple[float, float]:
        if not returns:
            return 0.0, 0.0
        alpha = max(1e-6, 1.0 - float(confidence))
        arr = np.asarray(returns, dtype=np.float64)
        method_key = str(method or "historical").strip().lower()

        if method_key == "parametric":
            mu = float(arr.mean())
            sigma = float(arr.std(ddof=0))
            if sigma <= 1e-9:
                var_ret = abs(min(0.0, mu))
                return var_ret, var_ret
            z = NormalDist().inv_cdf(alpha)
            q = mu + (sigma * z)
            var_ret = abs(min(0.0, q))
            pdf = math.exp(-0.5 * (z**2)) / math.sqrt(2.0 * math.pi)
            es_tail = mu - (sigma * (pdf / alpha))
            es_ret = abs(min(0.0, es_tail))
            return float(var_ret), float(max(es_ret, var_ret))

        quantile = float(np.quantile(arr, alpha))
        var_ret = abs(min(0.0, quantile))
        tail = arr[arr <= quantile]
        if tail.size == 0:
            return var_ret, var_ret
        es_ret = abs(min(0.0, float(tail.mean())))
        return float(var_ret), float(max(es_ret, var_ret))

    def _var_es_enforcement_enabled(self) -> bool:
        mode = str(self._active_limits.runtime_mode or "sim").strip().lower()
        if not self.enforce_rules:
            return False
        if mode == "real":
            return bool(self._active_limits.enable_var_es_enforce_real)
        if mode == "sim_real_guard":
            return bool(self._active_limits.enable_var_es_enforce_sim_real_guard)
        return False

    def _should_fail_closed_on_var_es_data(self) -> bool:
        limits = self._active_limits
        mode = str(limits.runtime_mode or "sim").strip().lower()
        policy = str(limits.var_es_insufficient_data_policy or "fail_closed_real_only").strip().lower()

        if bool(limits.var_es_fail_closed_on_insufficient_data):
            return bool(self._var_es_enforcement_enabled())
        if policy == "advisory":
            return False
        if policy == "fail_closed_all_enforced":
            return bool(self._var_es_enforcement_enabled())
        if policy == "fail_closed_real_only":
            return bool(self._var_es_enforcement_enabled() and mode == "real")
        return False

    def check_var_es_pre_trade(self, proposed_risk: float) -> tuple[bool, str, dict[str, float | str | bool]]:
        limits = self._active_limits
        mode = str(limits.runtime_mode or "sim").strip().lower()
        reason_codes_enabled = bool(limits.var_es_reason_codes_enabled)

        if not bool(limits.enable_var_es_calc):
            reason = "VAR_ES disabled by feature flag"
            self.state.var_es_breached = False
            self.state.var_es_reason = reason
            payload: dict[str, float | str | bool] = {
                "method": str(limits.var_es_method),
                "samples": 0.0,
                "var_95_usd": 0.0,
                "var_99_usd": 0.0,
                "es_95_usd": 0.0,
                "es_99_usd": 0.0,
                "breached": False,
                "decision": "allow",
                "reason_code": "VAR_ES_DISABLED" if reason_codes_enabled else "",
                "mode": mode,
            }
            return True, reason, payload

        exposure_usd = sum(float(v) for v in self.state.open_risk_by_symbol.values()) + max(0.0, float(proposed_risk))  # type: ignore[misc]
        returns = self._portfolio_return_series()
        min_samples = max(10, int(limits.var_es_min_samples))

        if len(returns) < min_samples:
            reason = f"VAR_ES insufficient return samples ({len(returns)} < {min_samples})"
            self.state.var_es_breached = bool(self._should_fail_closed_on_var_es_data())
            self.state.var_es_reason = reason
            payload: dict[str, float | str | bool] = {
                "method": str(limits.var_es_method),
                "samples": float(len(returns)),
                "var_95_usd": 0.0,
                "var_99_usd": 0.0,
                "es_95_usd": 0.0,
                "es_99_usd": 0.0,
                "breached": bool(self.state.var_es_breached),
                "decision": "block" if self.state.var_es_breached else "allow",
                "reason_code": "VAR_ES_INSUFFICIENT_DATA" if reason_codes_enabled else "",
                "mode": mode,
            }
            if self.state.var_es_breached:
                return False, reason, payload
            return True, reason, payload

        var95_ret, es95_ret = self._calculate_var_es_pair(returns=returns, confidence=0.95, method=limits.var_es_method)
        var99_ret, es99_ret = self._calculate_var_es_pair(returns=returns, confidence=0.99, method=limits.var_es_method)

        self.state.var_95_usd = float(var95_ret * exposure_usd)
        self.state.es_95_usd = float(es95_ret * exposure_usd)
        self.state.var_99_usd = float(var99_ret * exposure_usd)
        self.state.es_99_usd = float(es99_ret * exposure_usd)

        risk_state = str(self.state.active_risk_state or "NORMAL").upper()
        limit_multiplier = float(
            limits.var_es_high_risk_limit_multiplier
            if risk_state in {"HIGH", "HIGH_RISK", "RISK_OFF"}
            else limits.var_es_normal_risk_limit_multiplier
        )
        eff_var95_limit = float(limits.var_95_limit_usd) * limit_multiplier
        eff_var99_limit = float(limits.var_99_limit_usd) * limit_multiplier
        eff_es95_limit = float(limits.es_95_limit_usd) * limit_multiplier
        eff_es99_limit = float(limits.es_99_limit_usd) * limit_multiplier

        breached_reasons: list[str] = []
        if self.state.var_95_usd > eff_var95_limit:
            breached_reasons.append(f"VaR95 {self.state.var_95_usd:.2f} > {eff_var95_limit:.2f}")
        if self.state.var_99_usd > eff_var99_limit:
            breached_reasons.append(f"VaR99 {self.state.var_99_usd:.2f} > {eff_var99_limit:.2f}")
        if self.state.es_95_usd > eff_es95_limit:
            breached_reasons.append(f"ES95 {self.state.es_95_usd:.2f} > {eff_es95_limit:.2f}")
        if self.state.es_99_usd > eff_es99_limit:
            breached_reasons.append(f"ES99 {self.state.es_99_usd:.2f} > {eff_es99_limit:.2f}")

        self.state.var_es_breached = len(breached_reasons) > 0
        self.state.var_es_reason = "VAR_ES OK" if not breached_reasons else "VAR_ES breached: " + " | ".join(breached_reasons)
        should_block = bool(self.state.var_es_breached and self._var_es_enforcement_enabled())
        payload = {
            "method": str(limits.var_es_method),
            "samples": float(len(returns)),
            "var_95_usd": float(self.state.var_95_usd),
            "var_99_usd": float(self.state.var_99_usd),
            "es_95_usd": float(self.state.es_95_usd),
            "es_99_usd": float(self.state.es_99_usd),
            "breached": bool(self.state.var_es_breached),
            "decision": "block" if should_block else "allow",
            "reason_code": ("VAR_ES_LIMIT_BREACH" if self.state.var_es_breached else "VAR_ES_OK") if reason_codes_enabled else "",
            "mode": mode,
            "risk_state": risk_state,
            "limit_multiplier": float(limit_multiplier),
            "effective_var_95_limit_usd": float(eff_var95_limit),
            "effective_var_99_limit_usd": float(eff_var99_limit),
            "effective_es_95_limit_usd": float(eff_es95_limit),
            "effective_es_99_limit_usd": float(eff_es99_limit),
        }
        if should_block:
            return False, self.state.var_es_reason, payload
        return True, self.state.var_es_reason, payload

    def get_var_es_snapshot(self, *, proposed_risk: float = 0.0) -> dict[str, float | str | bool]:
        _ok, _reason, payload = self.check_var_es_pre_trade(proposed_risk=float(proposed_risk))
        return payload
