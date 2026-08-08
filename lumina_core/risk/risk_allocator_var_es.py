"""VaR/ES allocation helpers for RiskAllocatorMixin (M5)."""
from __future__ import annotations

import logging
import math
from statistics import NormalDist

import numpy as np

logger = logging.getLogger(__name__)


class RiskAllocatorVarEsMixin:
    """VaR/ES pre-trade checks (extracted for LOC hygiene)."""

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
        self.state.var_es_reason = (
            "VAR_ES OK" if not breached_reasons else "VAR_ES breached: " + " | ".join(breached_reasons)
        )
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
            "reason_code": ("VAR_ES_LIMIT_BREACH" if self.state.var_es_breached else "VAR_ES_OK")
            if reason_codes_enabled
            else "",
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
