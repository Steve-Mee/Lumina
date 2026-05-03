from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

ADMISSION_STEP_CONSTITUTION = "constitution"
ADMISSION_STEP_RISK_POLICY = "risk_policy"
ADMISSION_STEP_EQUITY_SNAPSHOT = "equity_snapshot"
ADMISSION_STEP_FINAL_ARBITRATION = "final_arbitration"
ADMISSION_STEP_SESSION_GUARD = "session_guard"

_EXPERIMENTAL_BYPASS_ENV = "LUMINA_ADMISSION_BYPASS_STEPS"
_REAL_MODE = "real"
_DEFAULT_ADMISSION_STEPS = (
    ADMISSION_STEP_CONSTITUTION,
    ADMISSION_STEP_RISK_POLICY,
    ADMISSION_STEP_EQUITY_SNAPSHOT,
    ADMISSION_STEP_FINAL_ARBITRATION,
    ADMISSION_STEP_SESSION_GUARD,
)

AdmissionStepHandler = Callable[["AdmissionContext"], tuple[bool, str]]


@dataclass(slots=True)
class AdmissionStepResult:
    step_id: str
    ok: bool
    reason: str
    bypassed: bool = False


@dataclass(slots=True)
class AdmissionTrace:
    results: list[AdmissionStepResult] = field(default_factory=list)

    def add_result(self, result: AdmissionStepResult) -> None:
        self.results.append(result)

    @property
    def last_step_id(self) -> str:
        if not self.results:
            return "admission_chain_uninitialized"
        return str(self.results[-1].step_id)

    @property
    def approved(self) -> bool:
        return bool(self.results) and all(item.ok for item in self.results)


@dataclass(slots=True)
class AdmissionContext:
    engine: Any
    mode: str
    symbol: str
    regime: str
    proposed_risk: float
    order_side: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    step_handlers: dict[str, AdmissionStepHandler] = field(default_factory=dict)
    experimental_bypass_step_ids: frozenset[str] = frozenset()

    def normalized_mode(self) -> str:
        return str(self.mode or "").strip().lower()

    def effective_bypass_step_ids(self) -> frozenset[str]:
        configured = set(self.experimental_bypass_step_ids)
        raw = os.getenv(_EXPERIMENTAL_BYPASS_ENV, "")
        if raw.strip():
            configured.update(segment.strip() for segment in raw.split(",") if segment.strip())
        return frozenset(configured)


@dataclass(slots=True)
class AdmissionChain:
    steps: Sequence[str]

    def run(self, ctx: AdmissionContext) -> tuple[bool, str, AdmissionTrace]:
        trace = AdmissionTrace()
        mode = ctx.normalized_mode()
        bypass_step_ids = ctx.effective_bypass_step_ids()

        for step_id in self.steps:
            if step_id in bypass_step_ids:
                if mode == _REAL_MODE:
                    reason = f"experimental_bypass_forbidden_in_real:{step_id}"
                    trace.add_result(
                        AdmissionStepResult(
                            step_id=step_id,
                            ok=False,
                            reason=reason,
                            bypassed=False,
                        )
                    )
                    return False, reason, trace

                _warning = (
                    "ADMISSION_EXPERIMENTAL_BYPASS,"
                    f"mode={mode},step={step_id},symbol={ctx.symbol},source={_EXPERIMENTAL_BYPASS_ENV}"
                )
                self._log_warning(ctx.engine, _warning)
                trace.add_result(
                    AdmissionStepResult(
                        step_id=step_id,
                        ok=True,
                        reason="bypassed_in_non_real_mode",
                        bypassed=True,
                    )
                )
                continue

            handler = ctx.step_handlers.get(step_id)
            if handler is None:
                reason = f"admission_step_handler_missing:{step_id}"
                trace.add_result(AdmissionStepResult(step_id=step_id, ok=False, reason=reason))
                return False, reason, trace

            try:
                ok, reason = handler(ctx)
            except Exception as exc:
                reason = f"admission_step_exception:{step_id}:{exc.__class__.__name__}"
                trace.add_result(AdmissionStepResult(step_id=step_id, ok=False, reason=reason))
                return False, reason, trace

            trace.add_result(
                AdmissionStepResult(
                    step_id=step_id,
                    ok=bool(ok),
                    reason=str(reason or ""),
                )
            )
            if not ok:
                return False, str(reason), trace

        if not trace.results:
            return False, "admission_chain_empty", trace
        return True, str(trace.results[-1].reason or "approved"), trace

    @staticmethod
    def _log_warning(engine: Any, message: str) -> None:
        app = getattr(engine, "app", None)
        logger = getattr(app, "logger", None)
        if logger is not None:
            logger.warning(message)


def default_chain_for_mode(mode: str) -> AdmissionChain:
    # Canonical sequence for all modes: keep trusted equity context before arbitration.
    # Experiments can still swap in a custom AdmissionChain(steps=...) per runtime.
    return AdmissionChain(steps=_DEFAULT_ADMISSION_STEPS)
