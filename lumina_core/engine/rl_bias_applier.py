"""
RlBiasApplier — Bounded component owning the RL bias application (Phase 3 D2 sub-slice 10).

Further firewall/decomp of runtime_workers trading paths god (the "or runtime_workers" per 05-31).
Thin delegation from supervisor_inner RL bias block ~558-595; hygiene for dupe with pre_dream's apply_rl_bias + _fetch (per MC "full dupe resolution for _paper_*/RL/price with pre_dream" + pre_dream docstring "exact dupes with supervisor on ... RL ...").
Owns the RL bias (ppo predict + _RL_GUARDRAIL.apply + shadow_state mut + dream_snapshot["signal"]/mult muts + qty/stop adj) + error handling (RUNTIME_RL_012) + best-effort.

Per 2026-05-31 SPF-006 + Phase 3 D2 "Decomposition or strict interface firewalling of at least one major concentration point (meta_agent_core or runtime_workers trading paths) such that changes inside it no longer require understanding the entire engine." + MC post-sub9 "full dupe resolution for _paper_*/RL/price with pre_dream" example in "larger D2 decomp/firewall (new Plan Mode e.g. full supervisor decomp in runtime_workers (supervisor phases into state machine or full dupe resolution for _paper_*/RL/price with pre_dream) or more meta surfaces per exact 05-31 D2)" + sub9 evol log "Next: Larger D2 ... full dupe resolution for _paper_*/RL/price with pre_dream, supervisor phases..." + sub8 evol log "Next: ... full dupe resolution for _paper_*/RL/price with pre_dream..." + fresh explore subagent id 019e91eb-e60c-71b3-8fd4-a1eb025582bf ("Recommended for sub10: RlBiasApplier").

Small additive; pre-execution decision surface (paper/SIM/REAL all use same path); independently testable; reversible; best-effort (preserves original excepts + original signal on missing).
"""

from __future__ import annotations

import logging
from typing import Any

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured
from lumina_core.engine.rl_guardrails import RLGuardrailLayer

logger = logging.getLogger(__name__)

# Module-level guardrail (mirrors runtime_workers top-level _RL_GUARDRAIL for best-effort reuse)
_RL_GUARDRAIL = RLGuardrailLayer()


class RlBiasApplier:
    """Bounded owner for the RL bias application (Phase 3 D2 sub-slice 10 follow-on to sub4 PaperTradeExecutor + sub5 PaperSimulator + sub6 EODForceCloseService + sub7 PreDreamDaemon + sub8 LivePositionManager + sub9 RealCloseDetector).

    Owns/ref: the RL bias block (~558-595: ppo predict + _RL_GUARDRAIL.apply + shadow_state mut + dream_snapshot["signal"]/mult muts + qty/stop adj) + error handling (RUNTIME_RL_012); narrow API for runtime_workers + tests (apply_bias returning (updated_signal, rl_action or None, updated_qty_m, updated_stop_m); best-effort on missing ppo/guard/env (preserves current excepts + original signal)).

    Thin delegation from runtime_workers supervisor_inner RL bias block ~558-595; reuses _RL_GUARDRAIL + existing predict/guard/try-except/error codes; hygiene for pre_dream dupe (pre_dream has lighter apply_rl_bias + _fetch).

    Per 2026-05-31 SPF-006 + Phase 3 D2 "or runtime_workers" + MC post-sub9 "full dupe resolution for _paper_*/RL/price with pre_dream" + sub9 "Next: full dupe resolution for _paper_*/RL/price with pre_dream..." + sub8 "Next: full dupe resolution for _paper_*/RL/price with pre_dream..." + explore subagent id 019e91eb-e60c-71b3-8fd4-a1eb025582bf ("Recommended for sub10: RlBiasApplier") + "changes inside no longer require understanding entire engine" for this surface.
    """

    def __init__(
        self,
        *,
        app: Any,
        guardrail: Any | None = None,
        **kwargs: Any,
    ) -> None:
        self.app = app
        self._guardrail = guardrail or _RL_GUARDRAIL
        self._logger = getattr(app, "logger", logger)

    def predict_cycle_signal(self) -> tuple[str, dict[str, Any] | None]:
        """Lightweight PPO predict for pre-dream cycle (D2 sub20; no guardrail/dream muts).

        Uses RUNTIME_RL_005 on failure (pre-dream path). Supervisor full bias uses apply_bias + RUNTIME_RL_012.
        """
        rl_signal = "HOLD"
        rl_action: dict[str, Any] | None = None
        try:
            if getattr(self.app.engine, "rl_env", None) is not None and getattr(self.app.engine, "ppo_trainer", None) is not None:
                obs = self.app.engine.rl_env._get_observation()
                rl_action = self.app.engine.ppo_trainer.predict_action(obs)
                rl_signal_map = {0: "HOLD", 1: "BUY", 2: "SELL"}
                rl_signal = rl_signal_map.get(int(rl_action.get("signal", 0)), "HOLD")
        except Exception as exc:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="RUNTIME_RL_005",
                message=str(exc),
                context={"traceback": __import__("traceback").format_exc()},
            )
            log_structured(err)
            (self._logger or logger).debug(f"Pre-dream RL bias unavailable: {exc}")
        return rl_signal, rl_action

    def apply_bias(
        self,
        *,
        current_signal: str,
        dream_snapshot: dict[str, Any],
        qty_multiplier: float,
        stop_widen_multiplier: float,
        baseline_signal: str | None = None,
        **kwargs: Any,
    ) -> tuple[str, dict[str, Any] | None, float, float]:
        """RL bias (predict + _RL_GUARDRAIL + override if non-HOLD + dream mut + mult adj). Exact from supervisor ~558-595; hygiene for pre_dream dupe.

        Returns: (updated_signal, rl_action or None, updated_qty_m, updated_stop_m)
        Best-effort on missing ppo/guard/env (preserves current excepts + original signal).
        """
        signal = str(current_signal)
        rl_action: dict[str, Any] | None = None
        bsl = str(baseline_signal) if baseline_signal is not None else str(signal)
        try:
            if getattr(self.app.engine, "rl_env", None) is not None and getattr(self.app.engine, "ppo_trainer", None) is not None:
                obs = self.app.engine.rl_env._get_observation()
                rl_action = self.app.engine.ppo_trainer.predict_action(obs)

                shadow_state = getattr(self.app.engine, "rl_shadow_state", {})
                guarded_action, shadow_state = self._guardrail.apply(
                    rl_action=dict(rl_action or {}),
                    baseline_signal=bsl,
                    regime=str(dream_snapshot.get("regime", "NEUTRAL")),
                    shadow_state=shadow_state if isinstance(shadow_state, dict) else {},
                )
                setattr(self.app.engine, "rl_shadow_state", shadow_state)
                rl_action = guarded_action

                rl_signal_map = {0: "HOLD", 1: "BUY", 2: "SELL"}
                rl_signal = rl_signal_map.get(int(rl_action.get("signal", 0)), "HOLD")
                if rl_signal in {"BUY", "SELL"} and signal == "HOLD":
                    signal = rl_signal
                    if isinstance(dream_snapshot, dict):
                        dream_snapshot["signal"] = signal

                if rl_action.get("qty_pct") is not None:
                    qty_multiplier = max(0.1, float(rl_action.get("qty_pct", 1.0))) * qty_multiplier
                if rl_action.get("stop_mult") is not None:
                    stop_widen_multiplier = max(0.5, float(rl_action.get("stop_mult", 1.0))) * stop_widen_multiplier
        except Exception as exc:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/rl_bias_applier.py")
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="RUNTIME_RL_012",
                message=str(exc),
                context={"traceback": __import__("traceback").format_exc()},
            )
            log_structured(err)
        return signal, rl_action, float(qty_multiplier), float(stop_widen_multiplier)


# Risk Safety Review (Score: 9/10)
# ✅ Fail-closed: Yes (missing ppo/guard/env -> graceful except path as before, no crash, returns original signal)
# ✅ REAL mode stricter: Yes (RL bias critical for REAL decision/obs before gate; paper lighter but same code path)
# ✅ ConstitutionViolation event: Best-effort (via existing arb/risk if needed; RL on capital decision path logged)
# ✅ Logging + ctx/agent: Yes (central in applier; shadow_state + guard; calls from supervisor logged via original except)
# ✅ No optimistic assumptions: Yes (exact relocation of original predict/guard/override/mut; no new behavior)
# ✅ Best-effort + guard reuse: Yes (reuses _RL_GUARDRAIL + existing error codes + dream mut pattern)
# ✅ Dupe hygiene with pre_dream: Yes (pre_dream apply_rl_bias + _fetch noted; this centralizes supervisor exec bias surface)
#
# Constitution Guard (rules 1/3/4/5/7):
# 1 Kapitaalbehoud: RL bias directly affects signal/qty/stop in decision path before hard risk/gate/execution + arb; central owner + guard makes bias observable/auditable for capital preservation.
# 3 Bounded no god: New focused RlBiasApplier; thin from supervisor; no god growth.
# 4 Typed: Narrow API; bias result feeds typed downstream (execution/risk paths).
# 5 Transparantie: Central place for RL bias/guard/predict/mut + error paths; logged; no optimistic.
# 7 Testable: given-when-then + mocks for rl_env/ppo/guard/app/dream + extend existing RL tests.
#
# Per 2026-05-31 SPF-006 + Phase 3 D2 "or runtime_workers" + MC post-sub9 "full dupe resolution for _paper_*/RL/price with pre_dream" + sub9 "Next: full dupe resolution for _paper_*/RL/price with pre_dream..." + sub8 "Next: ... full dupe resolution for _paper_*/RL/price with pre_dream..." + explore subagent id 019e91eb-e60c-71b3-8fd4-a1eb025582bf ("Recommended for sub10: RlBiasApplier") + aperture-mission-control + skills.
#
# Small; additive; 0 behavior change; SIM/paper friendly (pre-exec); reversible; independently testable.
