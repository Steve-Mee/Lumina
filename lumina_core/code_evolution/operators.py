"""Fixed operator catalog for trading code evolution v1.

Deterministic proposers only — no open-ended LLM full-file generation.
All changes target sandbox logical namespaces, never live risk/broker paths.
"""

from __future__ import annotations

import hashlib
import textwrap
import uuid
from dataclasses import dataclass
from typing import Any

from lumina_core.code_evolution.proposal import (
    ALLOWED_TARGETS,
    CodeMutationOperator,
    CodeMutationProposal,
)

# Whitelisted numeric strategy parameters (sandbox fixture only — not engine risk keys).
PARAMETER_CATALOG: dict[str, dict[str, float]] = {
    "ema_fast_window": {"min": 3.0, "max": 30.0, "default": 8.0, "max_rel_delta": 0.5},
    "ema_slow_window": {"min": 10.0, "max": 80.0, "default": 21.0, "max_rel_delta": 0.4},
    "confluence_threshold": {"min": 0.40, "max": 0.90, "default": 0.65, "max_rel_delta": 0.2},
    "volume_spike_mult": {"min": 1.1, "max": 3.0, "default": 1.5, "max_rel_delta": 0.35},
    "rsi_period": {"min": 5.0, "max": 28.0, "default": 14.0, "max_rel_delta": 0.4},
}

# Risk / capital keys must never be proposed here (those use RiskConfigMutationProposal).
FORBIDDEN_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "max_risk_percent",
        "drawdown_kill_percent",
        "kelly_fraction",
        "daily_loss_cap",
        "max_total_open_risk",
        "max_open_risk_per_instrument",
    }
)

_MAX_SNIPPET_LOC = 40
_MAX_INDICATOR_LOC = 25


def _proposal_id(operator: str, seed: str) -> str:
    h = hashlib.sha256(f"{operator}:{seed}".encode()).hexdigest()[:12]
    return f"codevo_{operator[:8]}_{h}"


def default_param_snapshot() -> dict[str, float]:
    return {k: float(v["default"]) for k, v in PARAMETER_CATALOG.items()}


def validate_parameter_tweak(key: str, old_value: float, new_value: float) -> list[str]:
    """Return fatal violation names if tweak is out of bounds."""
    violations: list[str] = []
    if key in FORBIDDEN_PARAMETER_KEYS:
        violations.append("forbidden_parameter_key")
        return violations
    if key not in PARAMETER_CATALOG:
        violations.append("parameter_not_whitelisted")
        return violations
    bounds = PARAMETER_CATALOG[key]
    lo, hi = float(bounds["min"]), float(bounds["max"])
    if new_value < lo or new_value > hi:
        violations.append("parameter_out_of_bounds")
    base = abs(float(old_value)) if abs(float(old_value)) > 1e-9 else 1.0
    rel = abs(float(new_value) - float(old_value)) / base
    if rel > float(bounds["max_rel_delta"]) + 1e-9:
        violations.append("parameter_delta_too_large")
    return violations


def sma_indicator_template(window: int = 5) -> str:
    """Pure list SMA — no imports, AST-safe."""
    w = max(2, min(int(window), 30))
    return textwrap.dedent(
        f"""\
        def indicator(series):
            \"\"\"Simple moving average over list of floats.\"\"\"
            n = {w}
            out = []
            for i in range(len(series)):
                if i + 1 < n:
                    out = out + [float(series[i])]
                else:
                    chunk = series[i + 1 - n : i + 1]
                    s = 0.0
                    for x in chunk:
                        s = s + float(x)
                    out = out + [s / float(n)]
            return out
        """
    )


def strategy_snippet_template(*, fast_window: int = 3, confidence: float = 0.6) -> str:
    """Minimal generated_strategy snippet for sandbox probe."""
    fw = max(2, min(int(fast_window), 10))
    conf = max(0.4, min(float(confidence), 0.9))
    return textwrap.dedent(
        f"""\
        def generated_strategy(context):
            \"\"\"Sandbox-safe strategy snippet (code evolution v1).\"\"\"
            close = context.get("close") or []
            if len(close) < {fw}:
                return {{
                    "name": "codevo_snippet",
                    "regime_focus": "neutral",
                    "signal_bias": "neutral",
                    "confidence": 0.0,
                    "rules": ["insufficient_data"],
                }}
            tail = close[-{fw}:]
            s = 0.0
            for x in tail:
                s = s + float(x)
            mean = s / float(len(tail))
            last = float(close[-1])
            bias = "buy" if last >= mean else "sell"
            return {{
                "name": "codevo_snippet",
                "regime_focus": "trending",
                "signal_bias": bias,
                "confidence": {conf},
                "rules": ["mean_vs_last"],
            }}
        """
    )


@dataclass(slots=True)
class CodeEvolutionController:
    """SSOT for proposing small trading-code mutations. Pure-ish; no live apply.

    Default disabled. Callers must run proposals through the pipeline
    (constitution → twin → sandbox → journal).
    """

    enabled: bool = False
    max_proposals_per_cycle: int = 1
    proposals_generated: int = 0

    def propose(
        self,
        *,
        current_params: dict[str, float] | None = None,
        seed: str | None = None,
    ) -> list[CodeMutationProposal]:
        if not self.enabled:
            return []
        seed_s = seed or uuid.uuid4().hex[:8]
        params = dict(current_params or default_param_snapshot())
        proposals: list[CodeMutationProposal] = []

        # Prefer a single PARAMETER_TWEAK when room for one proposal.
        tweak = self._propose_parameter_tweak(params, seed_s)
        if tweak is not None:
            proposals.append(tweak)

        if len(proposals) < self.max_proposals_per_cycle:
            ind = self._propose_simple_indicator(seed_s)
            if ind is not None:
                proposals.append(ind)

        if len(proposals) < self.max_proposals_per_cycle:
            snip = self._propose_strategy_snippet(params, seed_s)
            if snip is not None:
                proposals.append(snip)

        proposals = proposals[: max(0, int(self.max_proposals_per_cycle))]
        self.proposals_generated += len(proposals)
        return proposals

    def _propose_parameter_tweak(
        self, params: dict[str, float], seed: str
    ) -> CodeMutationProposal | None:
        key = "ema_fast_window"
        if key not in PARAMETER_CATALOG:
            return None
        old = float(params.get(key, PARAMETER_CATALOG[key]["default"]))
        # Deterministic small bump within bounds.
        step = 1.0 if old < 20 else -1.0
        new = old + step
        bounds = PARAMETER_CATALOG[key]
        new = max(float(bounds["min"]), min(float(bounds["max"]), new))
        if abs(new - old) < 1e-9:
            new = min(float(bounds["max"]), old + 1.0)
        viol = validate_parameter_tweak(key, old, new)
        if viol:
            return None
        before = {key: old}
        after = {key: new}
        return CodeMutationProposal(
            proposal_id=_proposal_id("parameter_tweak", f"{seed}:{key}:{new}"),
            operator=CodeMutationOperator.PARAMETER_TWEAK,
            target="sandbox.params",
            description=f"Tweak {key}: {old} → {new}",
            payload={"key": key, "old_value": old, "new_value": new},
            rationale="Small indicator window adjustment within whitelist bounds (sandbox only).",
            estimated_loc=1,
            before_snapshot=before,
            after_snapshot=after,
            decision_context_id=f"codevo_{seed}",
        )

    def _propose_simple_indicator(self, seed: str) -> CodeMutationProposal | None:
        window = 5 + (int(hashlib.sha256(seed.encode()).hexdigest()[:4], 16) % 5)
        code = sma_indicator_template(window)
        loc = code.count("\n") + 1
        if loc > _MAX_INDICATOR_LOC:
            return None
        return CodeMutationProposal(
            proposal_id=_proposal_id("add_simple_indicator", f"{seed}:sma:{window}"),
            operator=CodeMutationOperator.ADD_SIMPLE_INDICATOR,
            target="sandbox.indicator",
            description=f"Add pure SMA indicator window={window}",
            payload={"name": "sma", "window": window, "code": code},
            rationale="Add a pure list-based SMA for sandbox evaluation only.",
            estimated_loc=loc,
            before_snapshot={"indicator": None},
            after_snapshot={"indicator": "sma", "window": window, "code_hash": hashlib.sha256(code.encode()).hexdigest()[:16]},
            decision_context_id=f"codevo_{seed}",
        )

    def _propose_strategy_snippet(
        self, params: dict[str, float], seed: str
    ) -> CodeMutationProposal | None:
        fw = int(params.get("ema_fast_window", 3))
        fw = max(2, min(fw, 10))
        code = strategy_snippet_template(fast_window=fw, confidence=0.62)
        loc = code.count("\n") + 1
        if loc > _MAX_SNIPPET_LOC:
            return None
        return CodeMutationProposal(
            proposal_id=_proposal_id("strategy_snippet_adjust", f"{seed}:fw:{fw}"),
            operator=CodeMutationOperator.STRATEGY_SNIPPET_ADJUST,
            target="sandbox.strategy_snippet",
            description=f"Minor strategy snippet adjust fast_window={fw}",
            payload={"code": code, "function_name": "generated_strategy"},
            rationale="Probe a small pure strategy snippet under AST + sandbox rules.",
            estimated_loc=loc,
            before_snapshot={"snippet": None},
            after_snapshot={"code_hash": hashlib.sha256(code.encode()).hexdigest()[:16]},
            decision_context_id=f"codevo_{seed}",
        )

    def metrics_payload(self) -> dict[str, Any]:
        return {
            "code_evolution_enabled": bool(self.enabled),
            "code_evolution_proposals_generated": int(self.proposals_generated),
            "code_evolution_allowed_targets": sorted(ALLOWED_TARGETS),
            "code_evolution_param_keys": sorted(PARAMETER_CATALOG.keys()),
        }
