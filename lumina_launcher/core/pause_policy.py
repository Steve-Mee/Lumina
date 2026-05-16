from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PausePolicy:
    mode: str
    require_risk_warning: bool
    require_emergency_flatten: bool
    label: str


def resolve_pause_policy(*, context: str, runtime_mode: str, process_alive: bool) -> PausePolicy:
    mode = str(runtime_mode or "").strip().lower()
    ctx = str(context or "").strip().lower()
    if ctx == "first_boot_training":
        return PausePolicy(
            mode="cooperative_training_pause",
            require_risk_warning=False,
            require_emergency_flatten=False,
            label="checkpoint pause",
        )
    live_exposure = process_alive and mode in {"sim", "sim_real_guard", "real"}
    if live_exposure:
        return PausePolicy(
            mode="live_risk_pause",
            require_risk_warning=True,
            require_emergency_flatten=True,
            label="live safety pause",
        )
    return PausePolicy(
        mode="soft_stop",
        require_risk_warning=False,
        require_emergency_flatten=False,
        label="soft stop",
    )

